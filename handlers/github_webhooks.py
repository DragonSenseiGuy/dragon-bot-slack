import logging
import os
import threading
import time
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

CHAT_CHANNEL = os.getenv("CHAT_CHANNEL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
POLL_INTERVAL = int(os.getenv("GITHUB_POLL_INTERVAL", "60"))

WATCHED_REPOS = [
    "hackclub/cad",
    "hackclub/club-dashboard",
    "hackclub/clubs-website",
    "hackclub/leaders-portal",
    "hackclub/pancakes",
    "hackclub/school-toolbox",
    "hackclub/spaces",
    "hackclub/spaces-backend",
    "hackclub/toolbox",
    "hackclub/webdev",
]

_slack_client = None
_seen_prs: set[int] = set()
_initialized = False


def _get_headers():
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def _seed_seen_prs():
    """Populate seen PRs on startup so we don't notify for existing ones."""
    global _initialized
    for repo in WATCHED_REPOS:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=_get_headers(),
                params={"state": "open", "sort": "created", "direction": "desc", "per_page": 30},
                timeout=10,
            )
            if resp.status_code == 200:
                for pr in resp.json():
                    _seen_prs.add(pr["id"])
            else:
                logger.warning(f"Failed to seed PRs for {repo}: {resp.status_code}")
        except Exception:
            logger.exception(f"Error seeding PRs for {repo}")
    _initialized = True
    logger.info(f"Seeded {len(_seen_prs)} existing PRs")


def _poll_for_new_prs():
    for repo in WATCHED_REPOS:
        try:
            resp = requests.get(
                f"https://api.github.com/repos/{repo}/pulls",
                headers=_get_headers(),
                params={"state": "open", "sort": "created", "direction": "desc", "per_page": 10},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning(f"GitHub API error for {repo}: {resp.status_code}")
                continue

            for pr in resp.json():
                if pr["id"] not in _seen_prs:
                    _seen_prs.add(pr["id"])
                    _notify_new_pr(repo, pr)
        except Exception:
            logger.exception(f"Error polling PRs for {repo}")


def _notify_new_pr(repo: str, pr: dict):
    if not CHAT_CHANNEL:
        logger.warning("CHAT_CHANNEL not set, skipping PR notification")
        return

    pr_url = pr["html_url"]
    pr_title = pr["title"]
    repo_url = f"https://github.com/{repo}"

    message = (
        f"New Pull Request (<{pr_url}|{pr_title}>) opened in <{repo_url}|{repo}>\n"
        f"Check it out here: <{pr_url}>"
    )

    try:
        _slack_client.chat_postMessage(channel=CHAT_CHANNEL, text=message)
        logger.info(f"Sent PR notification for {repo}#{pr['number']}")
    except Exception:
        logger.exception("Failed to send PR notification to Slack")


def _poll_loop():
    _seed_seen_prs()
    while True:
        time.sleep(POLL_INTERVAL)
        _poll_for_new_prs()


def register(app):
    global _slack_client
    _slack_client = app.client

    thread = threading.Thread(target=_poll_loop, daemon=True)
    thread.start()
    logger.info(f"GitHub PR poller started (interval: {POLL_INTERVAL}s)")
