import logging
from random import randint

import requests


def fetch_xkcd(xkcd_id: str = None) -> dict:
    url = "https://xkcd.com/info.0.json" if xkcd_id is None else f"https://xkcd.com/{xkcd_id}/info.0.json"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def format_xkcd_blocks(info: dict) -> list:
    date = f"{info['year']}/{info['month']}/{info['day']}"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*<https://xkcd.com/{info['num']}|XKCD comic #{info['num']}>*\n\n_{info['alt']}_",
            },
        }
    ]

    if info["img"].endswith(("jpg", "png", "gif")):
        blocks.append(
            {
                "type": "image",
                "image_url": info["img"],
                "alt_text": info["safe_title"],
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"{date} - #{info['num']}, '{info['safe_title']}'"}],
        }
    )

    return blocks


def register(app):
    @app.command("/xkcd-fetch")
    def xkcd_fetch(ack, command):
        ack()
        xkcd_id = command.get("text", "").strip()

        if not xkcd_id:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide an XKCD ID. Usage: `/xkcd-fetch <id>`",
            )
            return

        try:
            info = fetch_xkcd(xkcd_id)
            app.client.chat_postMessage(channel=command["channel_id"], blocks=format_xkcd_blocks(info))
        except Exception as e:
            logging.error(f"Error fetching XKCD: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve XKCD comic.",
            )

    @app.command("/xkcd-random")
    def xkcd_random(ack, command):
        ack()
        try:
            latest = fetch_xkcd()
            random_id = str(randint(1, latest["num"]))
            info = fetch_xkcd(random_id)
            app.client.chat_postMessage(channel=command["channel_id"], blocks=format_xkcd_blocks(info))
        except Exception as e:
            logging.error(f"Error fetching random XKCD: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve XKCD comic.",
            )

    @app.command("/xkcd-latest")
    def xkcd_latest(ack, command):
        ack()
        try:
            info = fetch_xkcd()
            app.client.chat_postMessage(channel=command["channel_id"], blocks=format_xkcd_blocks(info))
        except Exception as e:
            logging.error(f"Error fetching latest XKCD: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve XKCD comic.",
            )
