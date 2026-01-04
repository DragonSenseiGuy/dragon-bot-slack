import logging

WELCOME_CHANNEL = "C0A417YGV3L"
NOTIFY_USER = "U09H4M0523Z"
PING_GROUP = "S0A3L9DHB8F"


def register(app):
    @app.event("member_joined_channel")
    def handle_member_joined(event, say, client):
        channel_id = event.get("channel")
        user_id = event.get("user")

        if channel_id != WELCOME_CHANNEL:
            return

        try:
            current_users = client.usergroups_users_list(usergroup=PING_GROUP)
            user_list = current_users.get("users", [])
            if user_id not in user_list:
                user_list.append(user_id)
                client.usergroups_users_update(usergroup=PING_GROUP, users=user_list)
        except Exception as e:
            logging.error(f"Failed to add user to ping group: {e}")

        client.chat_postMessage(
            channel=channel_id,
            text=(
                f"Welcome to Aditya tries to Code <@{user_id}>, <@{NOTIFY_USER}> get in here. "
                "Also btw you have been added to the ping group aditya-squad, "
                "you can leave if you want to (I don't ping often)"
            ),
        )
