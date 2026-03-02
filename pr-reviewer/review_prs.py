#!/usr/bin/env python3
"""
Automated PR reviewer — multi-repo, review-request-triggered.

Features
--------
1. Reviews new PRs where the configured reviewer is explicitly requested.
2. Re-reviews PRs when new commits are pushed; incorporates prior review
   comments and any teammate corrections into the updated review prompt,
   so repeated mistakes are avoided.
3. Sends an email alert when a PR that had critical issues is merged.

Config:  config.json   ← add SMTP credentials here (do NOT commit this file)
State:   reviewed_prs.json  (auto-created, tracks reviewed PR+SHA pairs)
Logs:    stdout / reviewer.log (when run via Task Scheduler)
"""

import base64
import json
import os
import re
import shutil
import smtplib
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
STATE_FILE = BASE_DIR / "reviewed_prs.json"

MAX_DIFF_LINES = 3_000
MAX_COMMENTS_CHARS = 6_000      # prior PR comments injected into re-review prompt
MERGED_PR_LOOKBACK_HOURS = 25   # window for scanning recently-merged PRs

# Documentation files to fetch from each repo, in priority order.
MD_FILES_TO_SCAN = [
    "AGENTS.md",
    "CLAUDE.md",
    ".claude/CLAUDE.md",
    "README.md",
    "CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
]
MAX_MD_FILE_CHARS = 8_000    # per file — trim before injecting
MAX_TOTAL_MD_CHARS = 24_000  # total across all files in one repo

# ---------------------------------------------------------------------------
# Prompt templates  ← all bot language lives here; edit freely
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert code reviewer. Analyse the PR diff and output ONLY a valid JSON array of issues.

## Output rules
- Output ONLY raw JSON — no prose, no markdown fences, no explanation before or after.
- Each element must have exactly these keys:
  "file"     — path relative to repo root (string)
  "line"     — absolute line number in the NEW version of the file where the issue appears (integer)
  "severity" — "critical" or "major" (string)
  "message"  — short description of the issue, max 250 chars (string)
- Only include issues you can tie to a specific line in the diff. Skip anything you cannot pin to a line.
- Output [] if there is nothing to report.

## Severity definitions
- "critical": security vulnerability (SQL injection, exposed secrets, auth bypass), correctness bug,
  or data-loss risk that was **introduced by this PR**. Must be addressed.
- "major": meaningful architectural violation (business logic in controller, significant duplication),
  missing required tests for a new public endpoint, or a change that appears unrelated to the PR's
  stated purpose (flag the out-of-scope file/line with a note explaining the apparent scope mismatch).

## Do NOT report
- PR title or description format issues
- Minor style, naming, or formatting preferences
- Code that existed before this PR and was not modified
- Vague suggestions without a specific line to attach them to

## Project Context

{repo_context}

## Output example
[
  {{"file": "app/Http/Controllers/FooController.php", "line": 42, "severity": "critical", "message": "SQL injection: $locale is interpolated directly into whereRaw() — validate against ['en','ru','kk'] allowlist before use"}},
  {{"file": "app/Services/BarService.php", "line": 87, "severity": "major", "message": "identical pagination logic duplicated from FooService:34 — extract to shared base class"}}
]\
"""

# Prepended to every claude invocation when a local repo path is set.
READONLY_NOTICE = (
    "STRICT REQUIREMENT: You are operating in READ-ONLY mode. "
    "You MUST NOT create, modify, or delete any files in the repository under any circumstances. "
    "Do not use any file-writing, editing, or shell-execution tools. "
    "Your sole task is to analyse the PR diff and return a JSON array as instructed.\n\n"
)

# Header injected before existing PR comments on a re-review.
PRIOR_COMMENTS_PREAMBLE = (
    "## Existing PR Discussion\n\n"
    "The comments below are from the PR timeline, including a previous automated review "
    "and teammate responses. You MUST follow these rules strictly:\n\n"
    "1. **Pre-existing issues**: If a teammate states that something was already in production "
    "or existed before this PR, do NOT flag it. It is out of scope.\n"
    "2. **Factual corrections**: If a teammate corrects a previous finding as wrong, "
    "accept the correction and drop the finding entirely.\n"
    "3. **Out-of-scope items**: If a teammate explains something is intentional or tracked "
    "separately, do not re-raise it.\n"
    "4. **Focus**: Only raise issues that are genuinely new in the latest diff AND have not "
    "already been addressed or explained by the team.\n\n"
    "Repeating already-disputed findings is worse than missing a real issue.\n\n"
)

# User-turn content sent to claude for a first review.
# Placeholders: {pr_title}, {diff}
NEW_REVIEW_USER_PROMPT = (
    "Review this PR and output the JSON array: **{pr_title}**\n\n"
    "```diff\n{diff}\n```"
)

# User-turn content sent to claude for a re-review.
# Placeholders: {pr_title}, {prior_ctx}, {diff}
RE_REVIEW_USER_PROMPT = (
    "New commits were pushed. Output an updated JSON array for: **{pr_title}**\n\n"
    "{prior_ctx}"
    "## Current Full Diff\n\n```diff\n{diff}\n```"
)


# ---------------------------------------------------------------------------
# Config / State
# ---------------------------------------------------------------------------

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"ERROR: config.json not found at {CONFIG_FILE}", file=sys.stderr)
        sys.exit(1)
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# GitHub helpers
# ---------------------------------------------------------------------------

def run_gh(*args: str) -> str:
    result = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return result.stdout or ""


def get_review_requested_prs(repo: str, reviewer: str) -> list[dict]:
    """Return open PRs where `reviewer` is explicitly listed as a requested reviewer."""
    output = run_gh(
        "pr", "list",
        "--repo", repo,
        "--state", "open",
        "--json", "number,title,author,headRefOid,reviewRequests",
    )
    prs = json.loads(output)
    return [
        pr for pr in prs
        if any(r.get("login") == reviewer for r in pr.get("reviewRequests", []))
    ]


def get_pr_diff(repo: str, pr_number: int) -> str:
    return run_gh("pr", "diff", str(pr_number), "--repo", repo)


def post_comment(repo: str, pr_number: int, body: str) -> None:
    run_gh("pr", "comment", str(pr_number), "--repo", repo, "--body", body)


def fetch_md_file(repo: str, path: str) -> tuple[str, str] | None:
    """
    Fetch a file from the repo via the GitHub API.
    Returns (path, decoded_content) or None if the file does not exist.
    """
    try:
        raw = run_gh("api", f"repos/{repo}/contents/{path}", "--jq", ".content")
        content = base64.b64decode(raw.strip().replace("\n", "")).decode("utf-8")
        return (path, content)
    except subprocess.CalledProcessError:
        return None


def get_pr_all_comments(repo: str, pr_number: int) -> list[dict]:
    """
    Fetch all PR comments: timeline comments, formal review bodies, and
    inline review thread comments (via REST API).
    Returns [{author, body, at}] sorted chronologically.
    """
    # Timeline comments + formal review bodies
    output = run_gh(
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "comments,reviews",
    )
    data = json.loads(output)
    items: list[dict] = []

    for c in data.get("comments", []):
        body = (c.get("body") or "").strip()
        if body:
            items.append({
                "author": (c.get("author") or {}).get("login", "unknown"),
                "body": body,
                "at": c.get("createdAt", ""),
            })

    for r in data.get("reviews", []):
        body = (r.get("body") or "").strip()
        if body:
            items.append({
                "author": (r.get("author") or {}).get("login", "unknown"),
                "body": body,
                "at": r.get("submittedAt", ""),
            })

    # Inline review thread comments — separate REST endpoint
    # (gh pr view does not expose these via --json)
    try:
        inline_output = run_gh("api", f"repos/{repo}/pulls/{pr_number}/comments")
        for c in json.loads(inline_output):
            body = (c.get("body") or "").strip()
            if body:
                path = c.get("path", "")
                line = c.get("line") or c.get("original_line", "")
                location = f"`{path}`" + (f":{line}" if line else "")
                items.append({
                    "author": (c.get("user") or {}).get("login", "unknown"),
                    "body": f"[inline comment on {location}]\n{body}",
                    "at": c.get("created_at", ""),
                })
    except Exception as e:
        print(f"    Warning: could not fetch inline review comments: {e}", file=sys.stderr)

    items.sort(key=lambda x: x.get("at", ""))
    return items


def get_recently_merged_prs(repo: str) -> list[dict]:
    """Fetch PRs merged within MERGED_PR_LOOKBACK_HOURS."""
    output = run_gh(
        "pr", "list",
        "--repo", repo,
        "--state", "merged",
        "--json", "number,title,author,mergedAt,headRefOid",
        "--limit", "30",
    )
    prs = json.loads(output)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MERGED_PR_LOOKBACK_HOURS)
    return [
        pr for pr in prs
        if pr.get("mergedAt")
        and datetime.fromisoformat(pr["mergedAt"].replace("Z", "+00:00")) > cutoff
    ]


def is_already_blocked_by_changes_request(repo: str, pr_number: int) -> bool:
    """
    Return True if the PR already has a CHANGES_REQUESTED review that is newer
    than the most recent commit — meaning the block is still active and the
    author has already been notified, so no additional email is needed.
    """
    output = run_gh(
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "reviews,commits",
    )
    data = json.loads(output)

    changes_requested_times = [
        r["submittedAt"] for r in data.get("reviews", [])
        if r.get("state") == "CHANGES_REQUESTED" and r.get("submittedAt")
    ]
    if not changes_requested_times:
        return False

    latest_request = max(changes_requested_times)

    commit_times = [
        c.get("committedDate") or c.get("authoredDate", "")
        for c in data.get("commits", [])
    ]
    commit_times = [t for t in commit_times if t]
    if not commit_times:
        return False

    return latest_request > max(commit_times)


def has_team_approval(repo: str, pr_number: int, pr_author: str) -> bool:
    """
    Return True if the PR has at least one APPROVED review from someone
    other than the PR author (i.e. a real teammate sign-off).
    """
    output = run_gh(
        "pr", "view", str(pr_number),
        "--repo", repo,
        "--json", "reviews",
    )
    reviews = json.loads(output).get("reviews", [])
    return any(
        r.get("state") == "APPROVED"
        and (r.get("author") or {}).get("login", "") != pr_author
        for r in reviews
    )


# ---------------------------------------------------------------------------
# Repo context (documentation)
# ---------------------------------------------------------------------------

def gather_repo_context(repo: str, repo_config: dict) -> str:
    """
    Fetch documentation MD files from the repo and build a context block
    for the system prompt. Enforces per-file and total character budgets.
    Falls back to a generic notice if no files are found.
    """
    name = repo_config.get("name", repo)
    found: list[tuple[str, str]] = []
    total_chars = 0

    for md_path in MD_FILES_TO_SCAN:
        result = fetch_md_file(repo, md_path)
        if result is None:
            continue
        path, content = result

        if len(content) > MAX_MD_FILE_CHARS:
            content = content[:MAX_MD_FILE_CHARS] + (
                f"\n\n... [{path} truncated at {MAX_MD_FILE_CHARS} chars] ..."
            )

        if total_chars + len(content) > MAX_TOTAL_MD_CHARS:
            remaining = MAX_TOTAL_MD_CHARS - total_chars
            if remaining > 500:
                content = content[:remaining] + f"\n\n... [{path} truncated] ..."
                found.append((path, content))
            break

        found.append((path, content))
        total_chars += len(content)

    if not found:
        return (
            f"**Project:** {name} (`{repo}`)\n\n"
            "No documentation files (AGENTS.md, CLAUDE.md, README.md, CONTRIBUTING.md) "
            "were found in this repository. Apply general best practices for the "
            "detected tech stack and language."
        )

    header = (
        f"**Project:** {name} (`{repo}`)\n\n"
        f"The following documentation files were fetched from the repository. "
        f"They contain project-specific conventions, architecture decisions, and rules. "
        f"Enforce them during the review:\n"
    )
    sections = [f"---\n#### `{path}`\n\n{content}" for path, content in found]
    return header + "\n\n" + "\n\n".join(sections)


def build_system_prompt(repo: str, repo_config: dict) -> str:
    context = gather_repo_context(repo, repo_config)
    return SYSTEM_PROMPT.format(repo_context=context)


# ---------------------------------------------------------------------------
# Review helpers
# ---------------------------------------------------------------------------

def parse_review_comments(raw: str) -> list[dict]:
    """
    Parse Claude's JSON output into a list of comment dicts.
    Strips accidental markdown fences. Returns [] on any parse error.
    Each valid entry has: file (str), line (int), severity (str), message (str).
    """
    text = raw.strip()
    # Strip optional ```json ... ``` or ``` ... ``` fences
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"    Warning: could not parse review JSON: {e}", file=sys.stderr)
        return []
    if not isinstance(data, list):
        print("    Warning: review JSON is not an array, ignoring.", file=sys.stderr)
        return []
    valid = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            valid.append({
                "file": str(item["file"]),
                "line": int(item["line"]),
                "severity": str(item.get("severity", "major")),
                "message": str(item["message"]),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return valid


def has_critical_issues(comments: list[dict]) -> bool:
    """Return True if any comment has severity 'critical'."""
    return any(c.get("severity") == "critical" for c in comments)


def post_inline_review(
    repo: str,
    pr_number: int,
    comments: list[dict],
    request_changes: bool = False,
) -> int:
    """
    Post inline review comments via GitHub Pull Request Reviews API.
    Uses event=REQUEST_CHANGES when request_changes=True (blocks the PR),
    otherwise event=COMMENT.
    Falls back to a regular PR comment for any line not in the diff.
    Returns count of successfully posted inline comments.
    """
    if not comments:
        return 0

    event = "REQUEST_CHANGES" if request_changes else "COMMENT"
    review_body = "⚠️ Critical issues found — changes required before this PR can be merged." if request_changes else ""

    review_comments = [
        {
            "path": c["file"],
            "line": c["line"],
            "side": "RIGHT",
            "body": f"[AI] ({c['severity']}) {c['message']}",
        }
        for c in comments
    ]

    def gh_post_review(batch: list[dict], ev: str = event, body: str = review_body) -> None:
        payload: dict = {"event": ev, "comments": batch}
        if body:
            payload["body"] = body
        result = subprocess.run(
            ["gh", "api", f"repos/{repo}/pulls/{pr_number}/reviews",
             "--method", "POST", "--input", "-"],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode, "gh api", output=result.stdout, stderr=result.stderr
            )

    # Attempt 1: post all inline comments at once with the appropriate event
    try:
        gh_post_review(review_comments)
        return len(review_comments)
    except subprocess.CalledProcessError:
        pass  # fall through to per-comment retry

    # Attempt 2: post each comment individually with COMMENT event
    posted = 0
    failed: list[dict] = []
    for rc, c in zip(review_comments, comments):
        try:
            gh_post_review([rc], ev="COMMENT", body="")
            posted += 1
        except subprocess.CalledProcessError:
            failed.append(c)

    # If blocking was requested but the batch failed, post a standalone
    # REQUEST_CHANGES review (body only) so the PR is still blocked.
    if request_changes:
        try:
            gh_post_review([], ev="REQUEST_CHANGES", body=review_body)
        except subprocess.CalledProcessError as e:
            print(f"    Warning: could not post REQUEST_CHANGES review: {e}", file=sys.stderr)

    # Fallback: post failures as a regular PR comment so nothing is silently dropped
    if failed:
        lines = ["**AI review — could not attach inline (line not in diff):**\n"]
        for c in failed:
            lines.append(f"- [AI] `({c['severity']})` `{c['file']}:{c['line']}` — {c['message']}")
        fallback_body = "\n".join(lines)
        try:
            post_comment(repo, pr_number, fallback_body)
        except Exception as e:
            print(f"    Warning: fallback comment post failed: {e}", file=sys.stderr)

    return posted


def find_pr_previous_state(state: dict, repo: str, pr_number: int) -> dict | None:
    """Return the most recent non-skipped state entry for a PR (any SHA)."""
    prefix = f"{repo}#{pr_number}:"
    entries = [
        (k, v)
        for k, v in state.items()
        if k.startswith(prefix)
        and not v.get("skipped")
        and not k.endswith(":merged")
    ]
    if not entries:
        return None
    return max(entries, key=lambda x: x[1].get("reviewed_at", ""))[1]


def build_prior_comments_context(comments: list[dict]) -> str:
    """
    Format existing PR comments as context for a re-review prompt.
    Instructs Claude to respect teammate corrections of previous AI mistakes.
    """
    if not comments:
        return ""
    lines = [PRIOR_COMMENTS_PREAMBLE]
    total = 0
    for c in comments:
        entry = f"**@{c['author']}:**\n{c['body']}\n\n---\n\n"
        if total + len(entry) > MAX_COMMENTS_CHARS:
            lines.append("*(earlier comments omitted — character limit reached)*\n\n")
            break
        lines.append(entry)
        total += len(entry)
    return "".join(lines)


def find_cli(names: tuple[str, ...], label: str) -> str:
    """Locate a CLI executable, checking multiple possible names (e.g. .cmd Windows wrapper)."""
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(f"{label} not found in PATH.")


def sync_local_repo_to_dev(local_path: str) -> None:
    """
    Fetch and switch the local clone to the latest 'dev' branch.
    Raises RuntimeError if the git operations fail.
    """
    def git(*args: str) -> None:
        result = subprocess.run(
            ["git", *args],
            cwd=local_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}"
            )

    git("fetch", "--all", "--prune")
    git("checkout", "dev")
    git("pull", "--ff-only", "origin", "dev")


def _build_prompts(
    system: str,
    pr_title: str,
    diff: str,
    prior_comments: list[dict] | None,
) -> tuple[str, str]:
    """Return (system_prompt, user_content) ready to send to any LLM backend."""
    diff_lines = diff.splitlines()
    truncated = len(diff_lines) > MAX_DIFF_LINES
    if truncated:
        diff_lines = diff_lines[:MAX_DIFF_LINES]
    diff_text = "\n".join(diff_lines)
    if truncated:
        diff_text += f"\n\n... [diff truncated — showing first {MAX_DIFF_LINES} lines] ..."

    prior_ctx = build_prior_comments_context(prior_comments) if prior_comments else ""
    if prior_comments:
        user_content = RE_REVIEW_USER_PROMPT.format(
            pr_title=pr_title, prior_ctx=prior_ctx, diff=diff_text
        )
    else:
        user_content = NEW_REVIEW_USER_PROMPT.format(pr_title=pr_title, diff=diff_text)

    return system, user_content


def call_claude_cli(
    system: str,
    pr_title: str,
    diff: str,
    prior_comments: list[dict] | None = None,
    local_path: str | None = None,
    claude_cfg: dict | None = None,
) -> str:
    """Call the Claude Code CLI subprocess (original backend)."""
    system_prompt, user_content = _build_prompts(system, pr_title, diff, prior_comments)
    # Only prepend READONLY_NOTICE when a local repo is provided; without local_path
    # Claude has no file-system access anyway, so the notice just wastes tokens.
    notice = READONLY_NOTICE if local_path else ""
    full_prompt = f"{notice}{system_prompt}\n\n---\n\n{user_content}"

    if local_path:
        sync_local_repo_to_dev(local_path)

    cfg = claude_cfg or {}
    # Default to Haiku — cheapest Claude model, adequate for structured JSON output.
    model = cfg.get("model", "claude-haiku-4-5-20251001")

    claude = find_cli(("claude", "claude.cmd"), "Claude Code CLI")
    print(f"    [claude] CLI path: {claude}")
    print(f"    [claude] model: {model}")
    cmd = [claude, "-p", "--model", model]
    print(f"    [claude] Running: {' '.join(cmd[:3])} ...  (stdin: {len(full_prompt)} chars, cwd: {local_path or 'inherited'})")
    result = subprocess.run(
        cmd,
        input=full_prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=None,
        creationflags=subprocess.CREATE_NO_WINDOW,
        cwd=local_path or None,
    )
    print(f"    [claude] exit code: {result.returncode}")
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    if stderr:
        print(f"    [claude] stderr ({len(stderr)} chars):\n{stderr}")
    if stdout:
        print(f"    [claude] stdout ({len(stdout)} chars): {stdout[:500]}"
              + (" ... [truncated]" if len(stdout) > 500 else ""))
    else:
        print(f"    [claude] stdout: (empty)")
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI exited with code {result.returncode}: {stderr}")
    if not stdout:
        raise RuntimeError("claude CLI returned an empty response")
    return stdout


def call_ollama(
    system: str,
    pr_title: str,
    diff: str,
    ollama_cfg: dict,
    prior_comments: list[dict] | None = None,
) -> str:
    """Call a local Ollama model via its REST API."""
    import urllib.request

    system_prompt, user_content = _build_prompts(system, pr_title, diff, prior_comments)
    host = ollama_cfg.get("host", "http://localhost:11434").rstrip("/")
    model = ollama_cfg["model"]
    print(f"    [ollama] model: {model}, host: {host}")

    payload_obj = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,   # low temp = more deterministic JSON output
            "num_ctx": 65536,     # large diffs can reach 40K+ tokens; 64K gives headroom
        },
    }
    payload = json.dumps(payload_obj).encode("utf-8")

    # Save full payload to a debug file so prompts can be replayed individually.
    debug_dir = BASE_DIR / "ollama_prompts"
    debug_dir.mkdir(exist_ok=True)
    slug = re.sub(r"[^\w\-]", "_", pr_title)[:40]
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_file = debug_dir / f"{slug}.json"
    debug_file.write_text(json.dumps(payload_obj, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"    [ollama] prompt saved → {debug_file}")

    print(f"    [ollama] sending request ({len(payload)} bytes, "
          f"prompt={len(system_prompt)+len(user_content)} chars)...")

    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    raw = (body.get("message", {}).get("content") or "").strip()
    # Strip <think>...</think> blocks produced by reasoning models (e.g. qwen3-thinking).
    # This lets the model reason internally while still returning clean JSON.
    output = re.sub(r"<think>[\s\S]*?</think>", "", raw).strip()
    if raw != output:
        stripped_chars = len(raw) - len(output)
        print(f"    [ollama] stripped {stripped_chars} chars of <think> blocks")
    print(f"    [ollama] response ({len(output)} chars): {output[:500]}"
          + (" ... [truncated]" if len(output) > 500 else ""))
    if not output:
        raise RuntimeError("Ollama returned an empty response")
    return output


def _run_cli_subprocess(cmd: list[str], prompt: str, label: str) -> str:
    """Run a CLI subprocess with the prompt on stdin, return stripped stdout."""
    cmd_display = " ".join(cmd)
    print(f"    [{label}] Running: {cmd_display}")
    if prompt:
        print(f"    [{label}] stdin: {len(prompt)} chars")
    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=None,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    print(f"    [{label}] exit code: {result.returncode}")
    stderr = (result.stderr or "").strip()
    stdout = (result.stdout or "").strip()
    if stderr:
        print(f"    [{label}] stderr ({len(stderr)} chars):\n{stderr}")
    if stdout:
        print(f"    [{label}] stdout ({len(stdout)} chars):\n{stdout[:2000]}"
              + (" ... [truncated]" if len(stdout) > 2000 else ""))
    else:
        print(f"    [{label}] stdout: (empty)")
    if result.returncode != 0:
        raise RuntimeError(f"{label} exited with code {result.returncode}: {stderr}")
    output = stdout
    if not output:
        raise RuntimeError(f"{label} returned an empty response")
    return output


def call_gemini_cli(
    system: str,
    pr_title: str,
    diff: str,
    prior_comments: list[dict] | None = None,
) -> str:
    """Call the Gemini CLI subprocess (stdin-based, same pattern as Claude CLI)."""
    system_prompt, user_content = _build_prompts(system, pr_title, diff, prior_comments)
    full_prompt = f"{READONLY_NOTICE}{system_prompt}\n\n---\n\n{user_content}"
    gemini = find_cli(("gemini", "gemini.cmd"), "Gemini CLI")
    print(f"    [gemini] CLI path: {gemini}")
    return _run_cli_subprocess([gemini, "-p"], full_prompt, "gemini CLI")


def call_opencode(
    system: str,
    pr_title: str,
    diff: str,
    opencode_cfg: dict | None = None,
    prior_comments: list[dict] | None = None,
) -> str:
    """Call the OpenCode CLI via `opencode run <message>`."""
    import tempfile
    system_prompt, user_content = _build_prompts(system, pr_title, diff, prior_comments)
    full_prompt = f"{READONLY_NOTICE}{system_prompt}\n\n---\n\n{user_content}"
    oc = find_cli(("opencode", "opencode.cmd"), "OpenCode CLI")
    print(f"    [opencode] CLI path: {oc}")
    cfg = opencode_cfg or {}
    # Windows limits command-line length to ~32 KB, so the full prompt can't be
    # passed as an argument. Write it to a temp file and attach with --file.
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".md", encoding="utf-8", delete=False)
    try:
        tmp.write(full_prompt)
        tmp.close()
        print(f"    [opencode] prompt temp file: {tmp.name} ({len(full_prompt)} chars)")
        cmd = [
            oc, "run",
            "Follow the instructions in the attached file exactly. "
            "Output ONLY the raw JSON array, nothing else.",
            "--file", tmp.name,
        ]
        if cfg.get("model"):
            cmd.extend(["--model", cfg["model"]])
            print(f"    [opencode] model override: {cfg['model']}")
        raw = _run_cli_subprocess(cmd, "", "opencode CLI")
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    # opencode prepends a session header line (e.g. "> build · session-name").
    # Strip those lines so the JSON parser only sees the LLM response.
    lines_before = raw.splitlines()
    lines = [ln for ln in lines_before if not ln.lstrip().startswith(">")]
    stripped = "\n".join(lines).strip()
    removed = len(lines_before) - len(lines)
    if removed:
        print(f"    [opencode] stripped {removed} header line(s) starting with '>'")
    print(f"    [opencode] response after strip ({len(stripped)} chars): {stripped[:500]}"
          + (" ... [truncated]" if len(stripped) > 500 else ""))
    return stripped


def call_aider(
    system: str,
    pr_title: str,
    diff: str,
    aider_cfg: dict | None = None,
    prior_comments: list[dict] | None = None,
) -> str:
    """Call Aider in non-interactive mode for code review (no files, no git edits)."""
    system_prompt, user_content = _build_prompts(system, pr_title, diff, prior_comments)
    full_prompt = f"{system_prompt}\n\n---\n\n{user_content}"
    cfg = aider_cfg or {}
    aider = find_cli(("aider", "aider.cmd"), "Aider")
    cmd = [aider, "--message", full_prompt, "--yes-always", "--no-git", "--no-auto-commits"]
    if cfg.get("model"):
        cmd.extend(["--model", cfg["model"]])
    return _run_cli_subprocess(cmd, "", "aider")


def call_llm(
    config: dict,
    system: str,
    pr_title: str,
    diff: str,
    prior_comments: list[dict] | None = None,
    local_path: str | None = None,
) -> str:
    """Dispatch to the configured LLM backend."""
    llm_cfg = config.get("llm", {})
    backend = llm_cfg.get("backend", "opencode")
    print(f"    [llm] backend: {backend}")

    if backend == "ollama":
        ollama_cfg = llm_cfg.get("ollama", {})
        if not ollama_cfg.get("model"):
            raise RuntimeError("config.json: llm.ollama.model is required when backend=ollama")
        return call_ollama(system, pr_title, diff, ollama_cfg, prior_comments)

    if backend == "gemini":
        return call_gemini_cli(system, pr_title, diff, prior_comments)

    if backend == "opencode":
        opencode_cfg = llm_cfg.get("opencode", {})
        return call_opencode(system, pr_title, diff, opencode_cfg, prior_comments)

    if backend == "aider":
        aider_cfg = llm_cfg.get("aider", {})
        return call_aider(system, pr_title, diff, aider_cfg, prior_comments)

    # Fallback / explicit: claude CLI
    claude_cfg = llm_cfg.get("claude", {})
    return call_claude_cli(system, pr_title, diff, prior_comments, local_path, claude_cfg)


# ---------------------------------------------------------------------------
# Email alerts (feature 3)
# ---------------------------------------------------------------------------

def send_email_alert(smtp_config: dict, subject: str, body_html: str) -> None:
    """Send an HTML email via SMTP (Gmail-compatible with STARTTLS on port 587)."""
    msg = MIMEMultipart("alternative")
    msg["From"] = smtp_config["from_email"]
    msg["To"] = smtp_config["to_email"]
    msg["Subject"] = subject
    msg.attach(MIMEText(body_html, "html"))

    with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_config["username"], smtp_config["password"])
        server.send_message(msg)


def send_clean_review_alert(
    smtp_config: dict,
    repo: str,
    pr_number: int,
    title: str,
    author: str,
    is_re_review: bool,
) -> None:
    """Send an email when a PR review finds no issues — PR is ready to merge."""
    pr_url = f"https://github.com/{repo}/pull/{pr_number}"
    review_label = "Re-review (issues resolved)" if is_re_review else "New Review"
    subject = f"[PR Ready to Merge] {repo} #{pr_number} — {title}"
    body_html = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:680px;margin:auto;padding:24px">
  <h2 style="color:#27ae60">&#9989; PR Ready to Merge</h2>
  <table cellpadding="8" style="border-collapse:collapse;width:100%">
    <tr style="background:#f8f8f8">
      <td><b>Repository</b></td><td>{repo}</td>
    </tr>
    <tr>
      <td><b>PR</b></td>
      <td><a href="{pr_url}">#{pr_number} &mdash; {title}</a></td>
    </tr>
    <tr style="background:#f8f8f8">
      <td><b>Author</b></td><td>@{author}</td>
    </tr>
    <tr>
      <td><b>Review type</b></td><td>{review_label}</td>
    </tr>
  </table>
  <p style="margin-top:20px">The automated AI code review found <strong>no issues</strong>. The PR looks good to merge.</p>
  <p>
    <a href="{pr_url}" style="background:#27ae60;color:#fff;padding:8px 16px;
      text-decoration:none;border-radius:4px">View PR on GitHub &rarr;</a>
  </p>
</body>
</html>"""
    send_email_alert(smtp_config, subject, body_html)


def send_critical_issues_alert(
    smtp_config: dict,
    repo: str,
    pr_number: int,
    title: str,
    author: str,
    comments: list[dict],
    is_re_review: bool,
) -> None:
    """Send an immediate email alert when a PR review finds critical issues."""
    pr_url = f"https://github.com/{repo}/pull/{pr_number}"
    critical = [c for c in comments if c.get("severity") == "critical"]
    def esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    issues_html = "\n".join(
        f"<li><code>{esc(c['file'])}:{c['line']}</code> — {esc(c['message'])}</li>"
        for c in critical
    )
    review_label = "Updated Review" if is_re_review else "New Review"
    subject = f"[PR Critical Issues] {repo} #{pr_number} — {title}"
    body_html = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:680px;margin:auto;padding:24px">
  <h2 style="color:#c0392b">&#9888;&#65039; Critical Issues Found in PR</h2>
  <table cellpadding="8" style="border-collapse:collapse;width:100%">
    <tr style="background:#f8f8f8">
      <td><b>Repository</b></td><td>{repo}</td>
    </tr>
    <tr>
      <td><b>PR</b></td>
      <td><a href="{pr_url}">#{pr_number} &mdash; {title}</a></td>
    </tr>
    <tr style="background:#f8f8f8">
      <td><b>Author</b></td><td>@{author}</td>
    </tr>
    <tr>
      <td><b>Review type</b></td><td>{review_label}</td>
    </tr>
  </table>
  <h3 style="margin-top:20px">Critical Issues</h3>
  <ul style="background:#fff8f8;border-left:4px solid #c0392b;padding:12px 16px 12px 32px;font-size:14px">
    {issues_html}
  </ul>
  <p style="margin-top:20px">
    <a href="{pr_url}" style="background:#2980b9;color:#fff;padding:8px 16px;
      text-decoration:none;border-radius:4px">View PR on GitHub &rarr;</a>
  </p>
</body>
</html>"""
    send_email_alert(smtp_config, subject, body_html)


def check_merged_prs(config: dict, state: dict) -> None:
    """
    Scan recently merged PRs across all repos.
    For any PR we reviewed that had Critical Issues, send a one-time email alert.
    """
    smtp_config = config.get("smtp")
    if not smtp_config:
        print("  [merge-check] No 'smtp' section in config.json — skipping merged-PR alerts.")
        return

    state_changed = False

    for repo_config in config["repositories"]:
        repo = repo_config["repo"]
        try:
            merged_prs = get_recently_merged_prs(repo)
        except subprocess.CalledProcessError as e:
            print(f"  [{repo}] ERROR fetching merged PRs: {e.stderr.strip()}", file=sys.stderr)
            continue

        for pr in merged_prs:
            number = pr["number"]
            merge_key = f"{repo}#{number}:merged"

            if merge_key in state:
                continue  # already processed this merge

            prev = find_pr_previous_state(state, repo, number)
            if not prev:
                # We never reviewed this PR — nothing to alert about
                state[merge_key] = {"notified_at": None, "reason": "not_reviewed"}
                state_changed = True
                continue

            if not prev.get("has_critical_issues"):
                # Reviewed but no critical issues — no alert needed
                state[merge_key] = {"notified_at": None, "reason": "no_critical_issues"}
                state_changed = True
                continue

            # PR had Critical Issues and was merged — check for team approval first
            title = pr["title"]
            author = pr["author"]["login"]

            # If commits were pushed after our last review, we can't confirm the
            # issues are still present — skip the alert to avoid false positives.
            last_reviewed_sha = prev.get("sha", "")
            merged_sha = pr.get("headRefOid", "")
            if last_reviewed_sha and merged_sha and last_reviewed_sha != merged_sha:
                print(
                    f"  [{repo}] PR #{number} — new commits pushed after last review "
                    f"(reviewed {last_reviewed_sha[:7]}, merged {merged_sha[:7]}); "
                    f"skipping alert (issues may have been fixed)."
                )
                state[merge_key] = {"notified_at": None, "reason": "unreviewed_commits_at_merge"}
                state_changed = True
                continue

            try:
                approved = has_team_approval(repo, number, author)
            except Exception as e:
                print(
                    f"  [{repo}] PR #{number} — could not fetch approval status: {e}",
                    file=sys.stderr,
                )
                approved = False

            if approved:
                print(
                    f"  [{repo}] PR #{number} — had critical issues but was approved "
                    f"by a teammate, skipping alert."
                )
                state[merge_key] = {"notified_at": None, "reason": "approved_by_team"}
                state_changed = True
                continue
            pr_url = f"https://github.com/{repo}/pull/{number}"
            reviewed_at = prev.get("reviewed_at", "unknown")
            merged_at = pr.get("mergedAt", "unknown")

            subject = f"[PR Alert] Critical issues merged without fix — {repo} #{number}"
            body_html = f"""\
<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;max-width:680px;margin:auto;padding:24px">
  <h2 style="color:#c0392b">&#9888;&#65039; PR with Critical Issues Was Merged</h2>
  <table cellpadding="8" style="border-collapse:collapse;width:100%">
    <tr style="background:#f8f8f8">
      <td><b>Repository</b></td><td>{repo}</td>
    </tr>
    <tr>
      <td><b>PR</b></td>
      <td><a href="{pr_url}">#{number} &mdash; {title}</a></td>
    </tr>
    <tr style="background:#f8f8f8">
      <td><b>Author</b></td><td>@{author}</td>
    </tr>
    <tr>
      <td><b>AI review posted at</b></td><td>{reviewed_at}</td>
    </tr>
    <tr style="background:#f8f8f8">
      <td><b>Merged at</b></td><td>{merged_at}</td>
    </tr>
  </table>
  <p style="margin-top:20px">
    The automated AI code review flagged <strong>Critical Issues</strong> on this PR.
    The PR was merged before those issues were resolved.
  </p>
  <p>Please review the changes and take corrective action if needed.</p>
  <p>
    <a href="{pr_url}" style="background:#2980b9;color:#fff;padding:8px 16px;
      text-decoration:none;border-radius:4px">View PR on GitHub &rarr;</a>
  </p>
</body>
</html>"""

            try:
                send_email_alert(smtp_config, subject, body_html)
                print(f"  [{repo}] PR #{number} — ⚠ merge alert sent to {smtp_config['to_email']}")
                state[merge_key] = {
                    "notified_at": datetime.now().isoformat(),
                    "repo": repo,
                    "pr": number,
                    "title": title,
                    "merged_at": merged_at,
                }
            except Exception as e:
                print(
                    f"  [{repo}] PR #{number} — failed to send merge alert: {e}",
                    file=sys.stderr,
                )
                continue  # don't mark as processed — retry on next run

            state_changed = True

    if state_changed:
        save_state(state)


# ---------------------------------------------------------------------------
# CLI: reset-review
# ---------------------------------------------------------------------------

def cmd_reset_review() -> None:
    """
    Subcommand: reset-review

    Usage:
      python review_prs.py reset-review --all
          Remove the latest review entry for every tracked PR (triggers re-review
          on the next run).

      python review_prs.py reset-review REPO#PR
          Remove the latest review entry for a specific PR.
          Example: python review_prs.py reset-review org/repo#123

      python review_prs.py reset-review REPO#PR SHA
          Remove a specific review entry identified by its commit SHA (full or
          short prefix).
          Example: python review_prs.py reset-review org/repo#123 f8f9277
    """
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    raw_args = sys.argv[2:]

    if not raw_args:
        print(__doc__ if False else cmd_reset_review.__doc__)
        sys.exit(1)

    state = load_state()

    # ── --all mode ──────────────────────────────────────────────────────────
    if raw_args[0] == "--all":
        # For each PR (keyed by "repo#number"), collect the latest review entry.
        pr_best: dict[str, tuple[str, str]] = {}  # pr_id -> (full_key, reviewed_at)
        for k, v in state.items():
            if k.endswith(":merged") or v.get("skipped"):
                continue
            pr_id = k.rsplit(":", 1)[0]  # "repo#number"
            reviewed_at = v.get("reviewed_at", "")
            if pr_id not in pr_best or reviewed_at > pr_best[pr_id][1]:
                pr_best[pr_id] = (k, reviewed_at)

        if not pr_best:
            print("No review entries found in state.")
            sys.exit(0)

        for full_key, _ in pr_best.values():
            del state[full_key]
        save_state(state)

        print(f"Removed {len(pr_best)} latest review entry(ies):")
        for full_key, reviewed_at in pr_best.values():
            print(f"  {full_key}  (reviewed_at: {reviewed_at})")
        return

    # ── REPO#PR mode ────────────────────────────────────────────────────────
    pr_spec = raw_args[0]
    sha_prefix = raw_args[1] if len(raw_args) > 1 else None

    if "#" not in pr_spec:
        print(
            f"ERROR: expected REPO#PR format (e.g. org/repo#123), got: {pr_spec!r}\n"
            f"Run without arguments for usage help."
        )
        sys.exit(1)

    repo, pr_num_str = pr_spec.rsplit("#", 1)
    try:
        pr_number = int(pr_num_str)
    except ValueError:
        print(f"ERROR: PR number must be an integer, got: {pr_num_str!r}")
        sys.exit(1)

    prefix = f"{repo}#{pr_number}:"
    candidates = [
        (k, v) for k, v in state.items()
        if k.startswith(prefix) and not k.endswith(":merged") and not v.get("skipped")
    ]

    if not candidates:
        print(f"No review entries found for {repo}#{pr_number}.")
        sys.exit(1)

    if sha_prefix:
        # Find entry whose SHA starts with the given prefix.
        matches = [
            (k, v) for k, v in candidates
            if k[len(prefix):].startswith(sha_prefix)
        ]
        if not matches:
            print(
                f"No review entry found for {repo}#{pr_number} with SHA starting with {sha_prefix!r}.\n"
                f"Known entries:"
            )
            for k, v in candidates:
                print(f"  {k}  (reviewed_at: {v.get('reviewed_at', '?')})")
            sys.exit(1)
        target_key = matches[0][0]
    else:
        # Remove the most recent entry.
        target_key = max(candidates, key=lambda x: x[1].get("reviewed_at", ""))[0]

    del state[target_key]
    save_state(state)
    print(f"Removed: {target_key}")
    print("The PR will be re-reviewed on the next run.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

LOG_FILE = BASE_DIR / "reviewer.log"
LOG_MAX_LINES = 500


def rotate_log() -> None:
    """Keep only the last LOG_MAX_LINES lines in the log file."""
    if not LOG_FILE.exists():
        return
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    if len(lines) > LOG_MAX_LINES:
        LOG_FILE.write_text("".join(lines[-LOG_MAX_LINES:]), encoding="utf-8")


def main() -> None:
    # pythonw.exe (windowless) sets sys.stdout/stderr to None.
    # Redirect both to the log file so output is preserved.
    if sys.stdout is None:
        rotate_log()
        _log = open(LOG_FILE, "a", encoding="utf-8")
        sys.stdout = sys.stderr = _log
    else:
        # Console mode (manual run): ensure UTF-8 so emoji chars don't crash.
        # NOTE: console mode does NOT write to reviewer.log — output goes to terminal only.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        print(f"[NOTE] Running in console mode — output is NOT written to {LOG_FILE}")

    config = load_config()
    reviewer = config["reviewer_username"]
    repos = config["repositories"]

    state = load_state()
    total_reviewed = 0

    ts = lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
    print(
        f"[{ts()}] PR reviewer started. "
        f"Monitoring {len(repos)} repo(s) for review requests to @{reviewer}."
    )

    # ── 1. Review open PRs (new + re-reviews on new commits) ──────────────
    for repo_config in repos:
        repo = repo_config["repo"]
        print(f"\n  [{repo}] Checking open PRs...")

        try:
            prs = get_review_requested_prs(repo, reviewer)
        except subprocess.CalledProcessError as e:
            print(f"  [{repo}] ERROR fetching PRs: {e.stderr.strip()}", file=sys.stderr)
            continue

        if not prs:
            print(f"  [{repo}] No review-requested PRs.")
            continue

        print(f"  [{repo}] Found {len(prs)} PR(s) requesting review from @{reviewer}.")
        print(f"  [{repo}] Fetching repo documentation ({', '.join(MD_FILES_TO_SCAN)})...")
        system_prompt = build_system_prompt(repo, repo_config)

        for pr in prs:
            number = pr["number"]
            sha = pr["headRefOid"]
            key = f"{repo}#{number}:{sha}"

            if key in state:
                print(f"    PR #{number} — already reviewed at this commit, skipping.")
                continue

            title = pr["title"]
            author = pr["author"]["login"]

            # Detect re-review: same PR number reviewed before at a different SHA.
            # Also handles state manually reset via reset-review — the bot's
            # previous comment still exists on the PR even after the state entry
            # is deleted, so we detect it by checking for the reviewer's comment.
            prev_state_entry = find_pr_previous_state(state, repo, number)

            # Always fetch existing comments for context and re-review detection.
            prior_comments: list[dict] = []
            try:
                prior_comments = get_pr_all_comments(repo, number)
            except Exception as e:
                print(
                    f"    PR #{number} — could not fetch prior comments: {e}",
                    file=sys.stderr,
                )

            # is_re_review if we have a state entry (normal re-review on new
            # commits) OR the bot already has a comment on the PR (handles
            # manual state reset via reset-review).
            is_re_review = prev_state_entry is not None or any(
                c.get("author") == reviewer for c in prior_comments
            )

            if is_re_review:
                reason = "new commits pushed" if prev_state_entry else "state was reset"
                print(f"    PR #{number} — re-reviewing ({reason}): {title}")
                if prior_comments:
                    print(
                        f"    PR #{number} — fetched {len(prior_comments)} existing "
                        f"comment(s) for context."
                    )
            else:
                print(f"    PR #{number} — new review: {title}")

            try:
                diff = get_pr_diff(repo, number)

                if not diff.strip():
                    print(f"    PR #{number} — empty diff, skipping.")
                    state[key] = {
                        "skipped": True,
                        "reason": "empty diff",
                        "at": datetime.now().isoformat(),
                    }
                    save_state(state)
                    continue

                raw = call_llm(config, system_prompt, title, diff, prior_comments, repo_config.get("local_path"))
                comments = parse_review_comments(raw)
                is_critical = has_critical_issues(comments)

                if comments:
                    posted = post_inline_review(repo, number, comments, request_changes=is_critical)
                    flag = " ⚠ (critical issues found — changes requested)" if is_critical else ""
                    print(f"    PR #{number} — {posted}/{len(comments)} inline comment(s) posted.{flag} ✓")
                else:
                    print(f"    PR #{number} — no issues found, nothing posted. ✓")
                    smtp_config = config.get("smtp")
                    if smtp_config:
                        prev_had_issues = (
                            prev_state_entry is not None
                            and prev_state_entry.get("has_critical_issues", False)
                        )
                        # Email on first clean review, or when issues were fixed
                        if prev_state_entry is None or prev_had_issues:
                            try:
                                send_clean_review_alert(
                                    smtp_config, repo, number, title, author, is_re_review,
                                )
                                print(f"    PR #{number} — ready-to-merge alert sent.")
                            except Exception as e:
                                print(
                                    f"    PR #{number} — failed to send clean review alert: {e}",
                                    file=sys.stderr,
                                )

                if is_critical:
                    smtp_config = config.get("smtp")
                    if smtp_config:
                        # Don't re-email if the previous review already flagged
                        # critical issues — avoids spam on successive re-reviews
                        # of the same unresolved issues. Re-notify only if the
                        # issues reappear after a clean review.
                        prev_had_critical_issues = (
                            prev_state_entry is not None
                            and prev_state_entry.get("has_critical_issues", False)
                        )
                        if prev_had_critical_issues:
                            print(
                                f"    PR #{number} — critical issues already flagged in "
                                f"previous review, skipping email."
                            )
                        else:
                            try:
                                blocked = is_already_blocked_by_changes_request(repo, number)
                            except Exception as e:
                                print(
                                    f"    PR #{number} — could not check block status: {e}",
                                    file=sys.stderr,
                                )
                                blocked = False

                            if blocked:
                                print(
                                    f"    PR #{number} — already has an active changes-request, "
                                    f"skipping email."
                                )
                            else:
                                try:
                                    send_critical_issues_alert(
                                        smtp_config, repo, number, title, author,
                                        comments, is_re_review,
                                    )
                                    print(f"    PR #{number} — critical issues alert sent.")
                                except Exception as e:
                                    print(
                                        f"    PR #{number} — failed to send critical issues alert: {e}",
                                        file=sys.stderr,
                                    )

                state[key] = {
                    "reviewed_at": datetime.now().isoformat(),
                    "repo": repo,
                    "pr": number,
                    "sha": sha,
                    "title": title,
                    "author": author,
                    "has_critical_issues": is_critical,
                    "is_re_review": is_re_review,
                }
                total_reviewed += 1

            except subprocess.CalledProcessError as e:
                print(f"    PR #{number} — gh error: {e.stderr.strip()}", file=sys.stderr)
            except Exception as e:
                print(f"    PR #{number} — unexpected error: {e}", file=sys.stderr)

            save_state(state)

    # ── 2. Alert on merged PRs that had critical issues ───────────────────
    print(f"\n  Checking recently merged PRs for critical-issue alerts...")
    check_merged_prs(config, state)

    print(f"\n[{ts()}] Done. Reviewed {total_reviewed} PR(s) across {len(repos)} repo(s).")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset-review":
        cmd_reset_review()
    else:
        main()
