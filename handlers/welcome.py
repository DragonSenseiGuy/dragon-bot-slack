import logging

WELCOME_CHANNEL = "C0A417YGV3L"
NOTIFY_USER = "U09H4M0523Z"
PING_GROUP = "S0A3L9DHB8F"


logger = logging.getLogger(__name__)


def register(app):
    @app.event("member_joined_channel")
    def handle_member_joined(event, say, client):
        channel_id = event.get("channel")
        user_id = event.get("user")

        if channel_id != WELCOME_CHANNEL:
            logger.debug(f"Ignoring member_joined_channel for channel {channel_id}")
            return

        inviter_id = event.get("inviter")
        logger.info(f"User <@{user_id}> joined welcome channel (invited by <@{inviter_id}>)")

        try:
            logger.debug(f"Fetching current users in ping group {PING_GROUP}")
            current_users = client.usergroups_users_list(usergroup=PING_GROUP)
            user_list = current_users.get("users", [])
            if user_id not in user_list:
                user_list.append(user_id)
                client.usergroups_users_update(usergroup=PING_GROUP, users=user_list)
                logger.info(f"Added <@{user_id}> to ping group {PING_GROUP}")
            else:
                logger.debug(f"User <@{user_id}> already in ping group")
        except Exception as e:
            logger.error(f"Failed to add user to ping group: {e}")

        inviter_mention = f" (added by <@{inviter_id}>)" if inviter_id else ""
        logger.debug("Sending welcome message")
        client.chat_postMessage(
            channel=channel_id,
            text=(
                f"Welcome to Aditya tries to Code <@{user_id}>{inviter_mention}, <@{NOTIFY_USER}> get in here. "
                "Also btw you have been added to the ping group aditya-squad, "
                "you can leave if you want to (I don't ping often)"
            ),
        )
        logger.info(f"Welcome message sent for <@{user_id}>")
