import logging
import time

logger = logging.getLogger(__name__)

GITHUB_URL = "https://github.com/dragonsenseiguy/dragon-bot"


def register(app):
    @app.command("/ping")
    def ping(ack, respond, command):
        start = time.time()
        ack()
        logger.info(f"/ping used by <@{command['user_id']}>")
        latency = (time.time() - start) * 1000
        logger.debug(f"Ping latency: {latency:.2f}ms")
        app.client.chat_postMessage(
            channel=command["channel_id"],
            text=f":table_tennis_paddle_and_ball: Pong! Response time: {latency:.2f}ms",
        )

    @app.command("/about")
    def about(ack, command):
        ack()
        logger.info(f"/about used by <@{command['user_id']}>")
        logger.debug("Sending about message")
        app.client.chat_postMessage(
            channel=command["channel_id"],
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Dragon Bot*\n\nA Slack bot designed to provide fun and useful commands.",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*GitHub:*\n<{GITHUB_URL}|Repository>"},
                        {"type": "mrkdwn", "text": "*Creator:*\nDragonSenseiGuy"},
                    ],
                },
            ],
        )

    @app.command("/credits")
    def credits(ack, command):
        ack()
        logger.info(f"/credits used by <@{command['user_id']}>")
        logger.debug("Sending credits message")
        app.client.chat_postMessage(
            channel=command["channel_id"],
            blocks=[
                {"type": "header", "text": {"type": "plain_text", "text": "Credits"}},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Inspiration/Code Style:* <https://github.com/python-discord/bot|Python Discord's bot>",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*ask-ai-personality:* Suggested by @the space man on the Hack Club Slack",
                    },
                },
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": "Huge thanks to them all!"}],
                },
            ],
        )
