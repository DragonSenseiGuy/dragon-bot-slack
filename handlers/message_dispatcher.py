import logging

from handlers import ai, fun, leveling, miscellaneous

logger = logging.getLogger(__name__)


def register(app):
    @app.event("message")
    def dispatch_message(event, say, client, context):
        """Single consolidated message event handler that dispatches to all modules."""
        try:
            fun.handle_message(event, say, client)
        except Exception as e:
            logger.error(f"Error in fun message handler: {e}")

        try:
            ai.handle_thread_followup(event, say, client, context)
        except Exception as e:
            logger.error(f"Error in AI thread followup handler: {e}")

        try:
            leveling.handle_message_xp(event, say, client)
        except Exception as e:
            logger.error(f"Error in leveling message handler: {e}")

        try:
            miscellaneous.handle_message(event, say, client)
        except Exception as e:
            logger.error(f"Error in miscellaneous message handler: {e}")
