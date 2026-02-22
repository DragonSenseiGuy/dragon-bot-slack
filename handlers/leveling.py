import logging
import math
import os
import time

import psycopg2

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
XP_PER_MESSAGE = 10
COOLDOWN_SECONDS = 60

_cooldowns: dict[str, float] = {}


def _init_db():
    """Create the user_xp table if it doesn't exist."""
    if not DATABASE_URL:
        return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS user_xp (
                        user_id TEXT PRIMARY KEY,
                        xp INTEGER NOT NULL DEFAULT 0
                    )
                """)
            conn.commit()
        finally:
            conn.close()
        logger.info("Leveling database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize leveling database: {e}")


def _calculate_level(xp: int) -> int:
    """Calculate level from XP. Formula: level = floor(sqrt(xp / 100))."""
    return int(math.floor(math.sqrt(xp / 100)))


def handle_message_xp(event, say, client):
    """Award XP for messages with a 60-second cooldown per user."""
    if event.get("bot_id") or event.get("subtype"):
        return

    if not DATABASE_URL:
        return

    user_id = event.get("user")
    if not user_id:
        return

    now = time.time()
    last_time = _cooldowns.get(user_id, 0)
    if now - last_time < COOLDOWN_SECONDS:
        return

    _cooldowns[user_id] = now

    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT xp FROM user_xp WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
                old_xp = row[0] if row else 0
                new_xp = old_xp + XP_PER_MESSAGE

                cur.execute(
                    """INSERT INTO user_xp (user_id, xp) VALUES (%s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET xp = %s""",
                    (user_id, new_xp, new_xp),
                )
            conn.commit()

            old_level = _calculate_level(old_xp)
            new_level = _calculate_level(new_xp)

            if new_level > old_level:
                ts = event.get("ts")
                logger.info(f"<@{user_id}> leveled up to {new_level}")
                say(
                    text=f":tada: <@{user_id}> leveled up to *Level {new_level}*!",
                    thread_ts=ts,
                )
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error tracking XP: {e}")


def register(app):
    _init_db()

    @app.command("/level")
    def level_command(ack, command):
        ack()
        user_id = command["user_id"]
        logger.info(f"/level used by <@{user_id}>")

        if not DATABASE_URL:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Database not configured.",
            )
            return

        try:
            conn = psycopg2.connect(DATABASE_URL)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT xp FROM user_xp WHERE user_id = %s", (user_id,)
                    )
                    row = cur.fetchone()
            finally:
                conn.close()

            xp = row[0] if row else 0
            level = _calculate_level(xp)
            next_level = level + 1
            xp_needed = (next_level**2) * 100

            app.client.chat_postMessage(
                channel=command["channel_id"],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*Level Stats for <@{user_id}>*\n\n"
                                f":star: *Level:* {level}\n"
                                f":sparkles: *XP:* {xp}\n"
                                f":dart: *Next level:* {xp_needed - xp} XP needed (Level {next_level})"
                            ),
                        },
                    }
                ],
            )
        except Exception as e:
            logger.error(f"Error fetching level: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve level data.",
            )

    @app.command("/leaderboard")
    def leaderboard_command(ack, command):
        ack()
        logger.info(f"/leaderboard used by <@{command['user_id']}>")

        if not DATABASE_URL:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Database not configured.",
            )
            return

        try:
            conn = psycopg2.connect(DATABASE_URL)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT user_id, xp FROM user_xp ORDER BY xp DESC LIMIT 10"
                    )
                    rows = cur.fetchall()
            finally:
                conn.close()

            if not rows:
                app.client.chat_postMessage(
                    channel=command["channel_id"],
                    text="No leaderboard data yet. Start chatting to earn XP!",
                )
                return

            medals = [
                ":first_place_medal:",
                ":second_place_medal:",
                ":third_place_medal:",
            ]
            lines = []
            for i, (uid, xp) in enumerate(rows):
                level = _calculate_level(xp)
                prefix = medals[i] if i < 3 else f"`{i + 1}.`"
                lines.append(f"{prefix} <@{uid}> — Level {level} ({xp} XP)")

            app.client.chat_postMessage(
                channel=command["channel_id"],
                blocks=[
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": "XP Leaderboard"},
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "\n".join(lines)},
                    },
                ],
            )
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve leaderboard data.",
            )
