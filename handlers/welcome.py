import logging
import os

import requests

WELCOME_CHANNEL = os.getenv("WELCOME_CHANNEL")
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
                "Also btw you have been added to the ping group aditya-squad "
                "(I don't ping often)."
            ),
        )
        logger.info(f"Welcome message sent for <@{user_id}>")

        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="You've been added to the ping group aditya-squad.",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "You've been added to the ping group *aditya-squad*. You can leave it anytime.",
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Leave group"},
                            "style": "danger",
                            "action_id": "leave_ping_group",
                            "value": user_id,
                        }
                    ],
                },
            ],
        )

    @app.action("leave_ping_group")
    def handle_leave_ping_group(ack, body, client):
        ack()
        user_id = body["actions"][0]["value"]
        response_url = body.get("response_url")

        logger.info(f"<@{user_id}> requested to leave ping group {PING_GROUP}")

        try:
            current_users = client.usergroups_users_list(usergroup=PING_GROUP)
            user_list = current_users.get("users", [])
            if user_id in user_list:
                user_list.remove(user_id)
                client.usergroups_users_update(usergroup=PING_GROUP, users=user_list)
                logger.info(f"Removed <@{user_id}> from ping group {PING_GROUP}")
                result_text = "You've left the ping group aditya-squad."
            else:
                logger.debug(f"<@{user_id}> was not in ping group")
                result_text = "You're not in the ping group aditya-squad."
        except Exception as e:
            logger.error(f"Failed to remove user from ping group: {e}")
            result_text = ":x: Failed to leave the ping group. Please try again later."

        if response_url:
            requests.post(
                response_url,
                json={"text": result_text, "replace_original": True},
                timeout=10,
            )
