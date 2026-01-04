import logging
import os

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("slack.log"), logging.StreamHandler()],
)

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


def register_handlers(app: App):
    from handlers import ai, fun, help, miscellaneous, welcome, xkcd

    ai.register(app)
    fun.register(app)
    help.register(app)
    miscellaneous.register(app)
    welcome.register(app)
    xkcd.register(app)


register_handlers(app)


if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logging.info("Starting Dragon Bot for Slack...")
    handler.start()
