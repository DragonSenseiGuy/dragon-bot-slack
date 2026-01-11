import logging
import os

logger = logging.getLogger(__name__)

OWNER_USER_ID = os.environ.get("OWNER_USER_ID")


def register(app):
    @app.command("/joinadityaschannel")
    def open_request_modal(ack, body, client):
        ack()
        logger.info(f"/request-channel used by <@{body['user_id']}>")

        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "channel_request_modal",
                "title": {"type": "plain_text", "text": "Channel Request"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "why_add",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "why_add_input",
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Tell me why I should add you...",
                            },
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Why should I add you to my channel?",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "do_i_know",
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "do_i_know_input",
                            "multiline": True,
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Have we met before?",
                            },
                        },
                        "label": {"type": "plain_text", "text": "Do I know you?"},
                    },
                ],
            },
        )

    @app.view("channel_request_modal")
    def handle_modal_submission(ack, body, client, view):
        ack()

        user_id = body["user"]["id"]
        user_name = body["user"]["username"]

        why_add = view["state"]["values"]["why_add"]["why_add_input"]["value"]
        do_i_know = view["state"]["values"]["do_i_know"]["do_i_know_input"]["value"]

        logger.info(f"Channel request submitted by <@{user_id}>")

        if not OWNER_USER_ID:
            logger.error("OWNER_USER_ID environment variable not set")
            return

        client.chat_postMessage(
            channel=OWNER_USER_ID,
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "New Channel Request"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*From:* <@{user_id}> ({user_name})",
                    },
                },
                {"type": "divider"},
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Why should I add you to my channel?*\n{why_add}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Do I know you?*\n{do_i_know}",
                    },
                },
            ],
            text=f"New channel request from <@{user_id}>",
        )
