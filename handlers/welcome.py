import logging
import os

import requests

from handlers.join_manager import _get_all_enabled_configs, _get_config

WELCOME_CHANNEL = os.getenv("WELCOME_CHANNEL")
OWNER_USER_ID = os.getenv("OWNER_USER_ID")
NOTIFY_USER = "U09H4M0523Z"
PING_GROUP = "S0A3L9DHB8F"


logger = logging.getLogger(__name__)


def _resolve_log_channel():
    """Find where join requests get sent, and use that for leave notices too."""
    config = _get_config(WELCOME_CHANNEL) if WELCOME_CHANNEL else None
    log_channel = config.get("log_channel") if config else None

    if not log_channel:
        configs = _get_all_enabled_configs()
        if configs:
            log_channel = configs[0][1].get("log_channel")

    return log_channel or OWNER_USER_ID


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

    @app.event("member_left_channel")
    def handle_member_left(event, client):
        channel_id = event.get("channel")
        user_id = event.get("user")

        if channel_id != WELCOME_CHANNEL:
            logger.debug(f"Ignoring member_left_channel for channel {channel_id}")
            return

        logger.info(f"User <@{user_id}> left welcome channel")

        removed = None  # None = unknown (API failed)
        try:
            current_users = client.usergroups_users_list(usergroup=PING_GROUP)
            user_list = current_users.get("users", [])
            if user_id in user_list:
                user_list.remove(user_id)
                client.usergroups_users_update(usergroup=PING_GROUP, users=user_list)
                removed = True
                logger.info(f"Removed <@{user_id}> from ping group {PING_GROUP}")
            else:
                removed = False
                logger.debug(f"<@{user_id}> was not in ping group")
        except Exception as e:
            logger.error(f"Failed to remove user from ping group: {e}")

        log_channel = _resolve_log_channel()
        if not log_channel:
            logger.error("No log channel or OWNER_USER_ID configured for leave notice")
            return

        if removed is True:
            group_note = " Removed from the ping group aditya-squad."
        elif removed is False:
            group_note = " They weren't in the ping group aditya-squad."
        else:
            group_note = " :warning: Couldn't check the ping group aditya-squad."
        client.chat_postMessage(
            channel=log_channel,
            text=f":door: <@{user_id}> left <#{channel_id}>.{group_note}",
        )
        logger.info(f"Leave notice sent for <@{user_id}> to {log_channel}")

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
