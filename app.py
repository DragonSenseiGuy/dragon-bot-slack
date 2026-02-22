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
    from handlers import (
        ai,
        channel_request,
        fun,
        help,
        join_manager,
        leveling,
        message_dispatcher,
        miscellaneous,
        welcome,
        xkcd,
    )

    logging.info("Registering handlers...")
    ai.register(app)
    logging.debug("Registered ai handlers")
    channel_request.register(app)
    logging.debug("Registered channel_request handlers")
    fun.register(app)
    logging.debug("Registered fun handlers")
    help.register(app)
    logging.debug("Registered help handlers")
    join_manager.register(app)
    logging.debug("Registered join_manager handlers")
    leveling.register(app)
    logging.debug("Registered leveling handlers")
    miscellaneous.register(app)
    logging.debug("Registered miscellaneous handlers")
    welcome.register(app)
    logging.debug("Registered welcome handlers")
    xkcd.register(app)
    logging.debug("Registered xkcd handlers")
    message_dispatcher.register(app)
    logging.debug("Registered message dispatcher")
    logging.info("All handlers registered successfully")


register_handlers(app)


if __name__ == "__main__":
    logging.info("Initializing Socket Mode handler...")
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logging.info("Starting Dragon Bot for Slack...")
    logging.info("Bot is now running and listening for events")
    handler.start()
