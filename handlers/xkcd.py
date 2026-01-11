import logging
from random import randint

import requests


def fetch_xkcd(xkcd_id: str = None) -> dict:
    url = "https://xkcd.com/info.0.json" if xkcd_id is None else f"https://xkcd.com/{xkcd_id}/info.0.json"
    logging.debug(f"Fetching XKCD from: {url}")
    resp = requests.get(url)
    resp.raise_for_status()
    logging.debug(f"XKCD API response status: {resp.status_code}")
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
        logging.info(f"/xkcd-fetch used by <@{command['user_id']}>")
        xkcd_id = command.get("text", "").strip()

        if not xkcd_id:
            logging.debug("No XKCD ID provided")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide an XKCD ID. Usage: `/xkcd-fetch <id>`",
            )
            return

        logging.info(f"Fetching XKCD comic #{xkcd_id}")
        try:
            info = fetch_xkcd(xkcd_id)
            logging.info(f"XKCD #{xkcd_id} fetched: '{info['safe_title']}'")
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
        logging.info(f"/xkcd-random used by <@{command['user_id']}>")
        try:
            logging.debug("Fetching latest XKCD to determine range")
            latest = fetch_xkcd()
            random_id = str(randint(1, latest["num"]))
            logging.info(f"Random XKCD ID selected: {random_id} (out of {latest['num']})")
            info = fetch_xkcd(random_id)
            logging.info(f"XKCD #{random_id} fetched: '{info['safe_title']}'")
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
        logging.info(f"/xkcd-latest used by <@{command['user_id']}>")
        try:
            info = fetch_xkcd()
            logging.info(f"Latest XKCD #{info['num']} fetched: '{info['safe_title']}'")
            app.client.chat_postMessage(channel=command["channel_id"], blocks=format_xkcd_blocks(info))
        except Exception as e:
            logging.error(f"Error fetching latest XKCD: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve XKCD comic.",
            )
