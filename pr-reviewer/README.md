# PR Reviewer

Automated AI code reviewer that monitors GitHub repositories and posts Claude-generated reviews on pull requests. Runs silently in the background via Windows Task Scheduler.

## Features

- **Auto-review** — posts a review when a PR is opened and your GitHub account is listed as a requested reviewer
- **Re-review on new commits** — re-reviews automatically when new commits are pushed to an already-reviewed PR, incorporating prior discussion context so the bot doesn't repeat already-addressed findings
- **Immediate email alert** — sends you an email the moment critical issues are found, so you can request changes before the PR is merged
- **Merge alert** — sends a second email if a PR with unresolved critical issues is merged without team approval or subsequent fixes
- **Smart suppression** — skips email alerts when:
  - A teammate already requested changes on the current commit (PR is already blocked)
  - A teammate approved the PR (conscious sign-off)
  - New commits were pushed after the last review (issues may have been fixed)
- **Respects team feedback** — on re-reviews, Claude is explicitly instructed not to repeat findings that teammates have marked as pre-existing, incorrect, or out-of-scope
- **Silent background execution** — runs via `pythonw.exe` with no CMD window flashing
- **Log rotation** — keeps the last 100 lines in `reviewer.log`

## Requirements

- Python 3.11+
- [GitHub CLI (`gh`)](https://cli.github.com/) — authenticated (`gh auth login`)
- [Claude Code CLI (`claude`)](https://github.com/anthropics/claude-code) — authenticated

```
pip install -r requirements.txt
```

## Setup

### 1. Configure

```
cp config.json.example config.json
```

Edit `config.json`:

```json
{
  "reviewer_username": "your_github_username",
  "smtp": {
    "host": "smtp.gmail.com",
    "port": 587,
    "username": "you@gmail.com",
    "password": "your_gmail_app_password",
    "from_email": "you@gmail.com",
    "to_email": "you@gmail.com"
  },
  "repositories": [
    { "repo": "org/repo-name", "name": "RepoName" }
  ]
}
```

**Gmail App Password**: go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), create a 16-character app password. Requires 2FA enabled on your Google account.

> `config.json` is gitignored — do not commit it.

### 2. Register the scheduled task (Windows)

Run once from PowerShell (no Administrator required):

```powershell
.\setup_task.ps1
```

This registers a task named `RoqedPRReviewer` that runs at logon and every 15 minutes. Re-run to update after changing config.

## Usage

### Trigger manually

```powershell
Start-ScheduledTask -TaskName 'RoqedPRReviewer'
```

### Watch live log output

```powershell
Get-Content .\reviewer.log -Tail 20 -Wait
```

### Reset review state (force re-review)

Use `reset-review` to clear a review entry so the bot will re-post a fresh review on the next run. Useful when you delete a stale review comment and want a new one, or when a teammate's context response now makes the original findings moot.

```powershell
# Remove latest review for a specific PR
python review_prs.py reset-review org/repo#123

# Remove a specific review by commit SHA (full or short prefix)
python review_prs.py reset-review org/repo#123 f8f9277

# Remove the latest review for every tracked PR
python review_prs.py reset-review --all
```

After running, trigger the reviewer immediately to get a fresh review:

```powershell
Start-ScheduledTask -TaskName 'RoqedPRReviewer'
```

### Other task management

```powershell
# Check last run status
Get-ScheduledTaskInfo -TaskName 'RoqedPRReviewer'

# Remove the task
Unregister-ScheduledTask -TaskName 'RoqedPRReviewer' -Confirm:$false
```

## Files

| File | Purpose |
|------|---------|
| `review_prs.py` | Main script |
| `config.json` | Your configuration (gitignored) |
| `config.json.example` | Template for config |
| `setup_task.ps1` | Registers/updates the Windows scheduled task |
| `run_reviewer.bat` | Manual launcher (not used by the task) |
| `reviewed_prs.json` | Auto-created state file — tracks reviewed PRs and sent alerts |
| `reviewer.log` | Rolling log, last 100 lines |

## How review triggering works

1. The script polls all configured repos for open PRs where `reviewer_username` is an **explicitly requested reviewer**
2. Each PR+commit SHA combination is reviewed exactly once
3. When new commits are pushed, the PR is re-reviewed; the full comment history (including inline thread replies) is passed to Claude so it can account for what teammates have already addressed
4. Reviews are posted as inline GitHub review comments. Critical issues trigger `REQUEST_CHANGES` (blocks merge); major-only findings use `COMMENT`. Any issues that can't be attached to a diff line fall back to a regular PR comment

## Email alerts

Two types of alerts are sent (requires `smtp` in config):

| Alert | When sent |
|-------|-----------|
| **Critical issues found** | Immediately after a review that finds critical issues, if the PR isn't already blocked by a changes-request review |
| **Merged with unresolved issues** | When a PR is merged that had critical issues in the last review, was not approved by a teammate, and no new commits were pushed after the review |
