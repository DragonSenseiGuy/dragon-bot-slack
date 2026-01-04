import json
import logging
import random
from pathlib import Path

import requests

ALL_VIDS = json.loads(Path("resources/fun/april_fools_vids.json").read_text("utf-8"))

TRIGGER_WORDS = ["dragon", "hackclub", "dragonsenseiguy"]


def register(app):
    @app.command("/joke")
    def joke(ack, command):
        ack()
        import pyjokes

        category = command.get("text", "").strip() or "all"
        if category not in ["neutral", "chuck", "all"]:
            category = "all"

        joke_text = pyjokes.get_joke(category=category)
        app.client.chat_postMessage(channel=command["channel_id"], text=joke_text)

    @app.command("/fool")
    def april_fools(ack, command):
        ack()
        video = random.choice(ALL_VIDS)
        app.client.chat_postMessage(
            channel=command["channel_id"],
            text=f"Check out this April Fools' video by *{video['channel']}*: {video['url']}",
            unfurl_links=True,
            unfurl_media=True,
        )

    @app.command("/quote")
    def quote(ack, command):
        ack()
        subcommand = command.get("text", "").strip() or "random"

        if subcommand == "daily":
            url = "https://zenquotes.io/api/today"
        else:
            url = "https://zenquotes.io/api/random"

        try:
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            quote_text = f">{data[0]['q']}\n>— _{data[0]['a']}_\n\n_Powered by zenquotes.io_"
            app.client.chat_postMessage(
                channel=command["channel_id"],
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": quote_text},
                    }
                ],
            )
        except Exception as e:
            logging.error(f"Error fetching quote: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve quote from API.",
            )

    @app.command("/rock-paper-scissors")
    def rock_paper_scissors(ack, command):
        ack()
        choice = command.get("text", "").strip().capitalize()

        if choice not in ["Rock", "Paper", "Scissors"]:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please choose Rock, Paper, or Scissors. Usage: `/rock-paper-scissors Rock`",
            )
            return

        bot_choice = random.choice(["Rock", "Paper", "Scissors"])

        if bot_choice == choice:
            result = "tied"
        elif (bot_choice == "Rock" and choice == "Scissors") or \
             (bot_choice == "Paper" and choice == "Rock") or \
             (bot_choice == "Scissors" and choice == "Paper"):
            result = "lost"
        else:
            result = "won"

        app.client.chat_postMessage(
            channel=command["channel_id"],
            text=f"You chose {choice} and the bot chose {bot_choice}, you {result}!",
        )

    @app.command("/dadjoke")
    def dad_joke(ack, command):
        ack()
        try:
            headers = {"Accept": "application/json"}
            resp = requests.get("https://icanhazdadjoke.com", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            app.client.chat_postMessage(
                channel=command["channel_id"],
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*Random Dad Joke*\n\n{data['joke']}\n\n<https://icanhazdadjoke.com/j/{data['id']}|Permalink>",
                        },
                    }
                ],
            )
        except Exception as e:
            logging.error(f"Error fetching dad joke: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve dad joke from API.",
            )

    @app.command("/dog-picture")
    def dog_picture(ack, command):
        ack()
        try:
            resp = requests.get("https://dog.ceo/api/breeds/image/random")
            resp.raise_for_status()
            data = resp.json()
            app.client.chat_postMessage(
                channel=command["channel_id"],
                blocks=[
                    {
                        "type": "image",
                        "title": {"type": "plain_text", "text": "Random Dog Picture"},
                        "image_url": data["message"],
                        "alt_text": "A random dog",
                    },
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": "_Powered by dog.ceo_"}],
                    },
                ],
            )
        except Exception as e:
            logging.error(f"Error fetching dog picture: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve dog picture from API.",
            )

    @app.command("/cat-picture")
    def cat_picture(ack, command):
        ack()
        try:
            resp = requests.get("https://api.thecatapi.com/v1/images/search")
            resp.raise_for_status()
            data = resp.json()
            app.client.chat_postMessage(
                channel=command["channel_id"],
                blocks=[
                    {
                        "type": "image",
                        "title": {"type": "plain_text", "text": "Random Cat Picture"},
                        "image_url": data[0]["url"],
                        "alt_text": "A random cat",
                    },
                    {
                        "type": "context",
                        "elements": [{"type": "mrkdwn", "text": "_Powered by thecatapi.com_"}],
                    },
                ],
            )
        except Exception as e:
            logging.error(f"Error fetching cat picture: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: Could not retrieve cat picture from API.",
            )

    @app.event("message")
    def handle_message_events(body, say, logger):
        event = body.get("event", {})
        text = event.get("text", "").lower()

        if event.get("bot_id"):
            return

        if "dragonsenseiguy is the best person in the world" in text:
            say(
                "Access granted, You have been promoted to Administrator role. "
                "You are one of the few people who actually read the source code!"
            )
            return

        for word in TRIGGER_WORDS:
            if word in text:
                say(f"{word} detected")
                return
