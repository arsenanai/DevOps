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

GENERIC_SYSTEM_PROMPT = """\
You are an expert code reviewer. Review pull request diffs and provide concise, actionable feedback.

## General Review Criteria

### Security
- Never interpolate user input directly into raw SQL — always use parameterized queries
- Validate and sanitize user-provided data at system boundaries
- No hardcoded credentials, secrets, or API keys in code

### Architecture & Code Quality
- Business logic belongs in service/use-case classes, not in controllers or route handlers
- Functions and classes should have single, clear responsibility
- New public endpoints and non-trivial business logic should have tests
- Follow the project's existing naming and structural conventions

### Pull Request Hygiene
- PR title should follow Conventional Commits: `type(scope): description`
- PR should include a description and link to the related issue/ticket

## Project Context

{repo_context}

## Review Format

Write a concise review in Markdown with these four sections:

### Summary
1–2 sentences describing what the PR does.

### Critical Issues
Security vulnerabilities, correctness bugs, or data-loss risks — must be fixed before merge.
If none: write "None."

### Improvements
Architecture violations, missing tests, code quality issues — should be addressed.
If none: write "None."

### Positives
What was done well. Always include at least one positive observation.

Reference specific file names and line context where relevant. Be professional and constructive.\
"""


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
    Fetch all PR comments (timeline comments + formal review bodies).
    Returns [{author, body, at}] sorted chronologically.
    """
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
    return GENERIC_SYSTEM_PROMPT.format(repo_context=context)


# ---------------------------------------------------------------------------
# Review helpers
# ---------------------------------------------------------------------------

def extract_critical_issues_flag(review_text: str) -> bool:
    """Return True if the Critical Issues section contains actual issues."""
    match = re.search(
        r"###\s+Critical Issues\s*\n+(.*?)(?=###|\Z)",
        review_text,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return False
    content = match.group(1).strip()
    return content.lower() not in ("none.", "none")


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
    lines = [
        "## Existing PR Comments\n\n",
        "The following comments are already on this PR. "
        "Some are from a previous automated AI review; others may be teammate corrections or feedback. "
        "**If any teammate has disputed or corrected a previous AI finding, do not repeat that mistake.** "
        "Focus your updated review on issues remaining or introduced in the latest commits.\n\n",
    ]
    total = 0
    for c in comments:
        entry = f"**@{c['author']}:**\n{c['body']}\n\n---\n\n"
        if total + len(entry) > MAX_COMMENTS_CHARS:
            lines.append("*(earlier comments omitted — character limit reached)*\n\n")
            break
        lines.append(entry)
        total += len(entry)
    return "".join(lines)


def find_claude_cmd() -> str:
    """Locate the claude CLI executable (handles Windows .cmd wrapper)."""
    for name in ("claude", "claude.cmd"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError(
        "claude CLI not found in PATH. Make sure Claude Code is installed and logged in."
    )


def call_claude(
    system: str,
    pr_title: str,
    diff: str,
    prior_comments: list[dict] | None = None,
) -> str:
    diff_lines = diff.splitlines()
    truncated = len(diff_lines) > MAX_DIFF_LINES
    if truncated:
        diff_lines = diff_lines[:MAX_DIFF_LINES]
    diff_text = "\n".join(diff_lines)
    if truncated:
        diff_text += f"\n\n... [diff truncated — showing first {MAX_DIFF_LINES} lines] ..."

    is_re_review = bool(prior_comments)
    prior_ctx = build_prior_comments_context(prior_comments) if prior_comments else ""

    if is_re_review:
        user_content = (
            f"New commits were pushed to this PR. "
            f"Please provide an **updated review** for: **{pr_title}**\n\n"
            + prior_ctx
            + f"## Current Full Diff\n\n```diff\n{diff_text}\n```"
        )
    else:
        user_content = (
            f"Please review this PR: **{pr_title}**\n\n"
            f"```diff\n{diff_text}\n```"
        )

    # Combine system instructions + user content into a single prompt for the CLI.
    # Sent via stdin to avoid Windows command-line length limits.
    full_prompt = f"{system}\n\n---\n\n{user_content}"

    claude = find_claude_cmd()
    result = subprocess.run(
        [claude, "-p"],
        input=full_prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        raise RuntimeError(f"claude CLI exited with code {result.returncode}: {stderr}")
    output = (result.stdout or "").strip()
    if not output:
        raise RuntimeError("claude CLI returned an empty response")
    return output


def format_comment(author: str, review: str, is_re_review: bool = False) -> str:
    label = "Updated AI Code Review" if is_re_review else "AI Code Review"
    update_note = (
        "\n> ℹ️ This is an updated review following new commits pushed to this PR.\n"
        if is_re_review
        else ""
    )
    return (
        f"@{author} please have a look at this review made by AI, it may contain mistakes, "
        f"so that it's not blocking your changes from being merged, just for you to be aware of:\n\n"
        f"---\n\n"
        f"## {label}\n"
        f"{update_note}\n"
        f"{review}"
    )


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
# Main
# ---------------------------------------------------------------------------

LOG_FILE = BASE_DIR / "reviewer.log"
LOG_MAX_LINES = 100


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
        # Console mode (manual run / old bat): ensure UTF-8 so emoji chars don't crash.
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

            # Detect re-review: same PR number reviewed before at a different SHA
            prev_state_entry = find_pr_previous_state(state, repo, number)
            is_re_review = prev_state_entry is not None

            prior_comments: list[dict] | None = None
            if is_re_review:
                print(f"    PR #{number} — re-reviewing (new commits pushed): {title}")
                try:
                    prior_comments = get_pr_all_comments(repo, number)
                    print(
                        f"    PR #{number} — fetched {len(prior_comments)} existing "
                        f"comment(s) for context."
                    )
                except Exception as e:
                    print(
                        f"    PR #{number} — could not fetch prior comments: {e}",
                        file=sys.stderr,
                    )
                    prior_comments = []
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

                review = call_claude(system_prompt, title, diff, prior_comments)
                has_issues = extract_critical_issues_flag(review)
                comment = format_comment(author, review, is_re_review=is_re_review)
                post_comment(repo, number, comment)

                state[key] = {
                    "reviewed_at": datetime.now().isoformat(),
                    "repo": repo,
                    "pr": number,
                    "sha": sha,
                    "title": title,
                    "author": author,
                    "has_critical_issues": has_issues,
                    "is_re_review": is_re_review,
                }
                total_reviewed += 1
                flag = " ⚠ (critical issues found)" if has_issues else ""
                print(f"    PR #{number} — review posted.{flag} ✓")

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
    main()
