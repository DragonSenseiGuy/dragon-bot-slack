import json
import logging
import os

import psycopg2

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL")
OWNER_USER_ID = os.getenv("OWNER_USER_ID")


def _init_db():
    """Create the join_manager_config table if it doesn't exist."""
    if not DATABASE_URL:
        return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS join_manager_config (
                        channel_id TEXT PRIMARY KEY,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        log_channel TEXT,
                        questions JSONB DEFAULT '[]',
                        ban_list JSONB DEFAULT '[]'
                    )
                """)
            conn.commit()
        finally:
            conn.close()
        logger.info("Join manager database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize join manager database: {e}")


def _get_config(channel_id):
    """Fetch join manager config for a channel."""
    if not DATABASE_URL:
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT enabled, log_channel, questions, ban_list "
                    "FROM join_manager_config WHERE channel_id = %s",
                    (channel_id,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "enabled": row[0],
                        "log_channel": row[1],
                        "questions": row[2] if isinstance(row[2], list) else json.loads(row[2]),
                        "ban_list": row[3] if isinstance(row[3], list) else json.loads(row[3]),
                    }
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error fetching join manager config: {e}")
    return None


def _get_all_enabled_configs():
    """Fetch all enabled join manager configs."""
    if not DATABASE_URL:
        return []
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT channel_id, log_channel, questions, ban_list "
                    "FROM join_manager_config WHERE enabled = TRUE"
                )
                rows = cur.fetchall()
                return [
                    (
                        row[0],
                        {
                            "log_channel": row[1],
                            "questions": row[2] if isinstance(row[2], list) else json.loads(row[2]),
                            "ban_list": row[3] if isinstance(row[3], list) else json.loads(row[3]),
                        },
                    )
                    for row in rows
                ]
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"Error fetching all join manager configs: {e}")
    return []


def _build_question_blocks(questions):
    """Build modal input blocks for a list of questions."""
    blocks = []
    for i, q in enumerate(questions, 1):
        blocks.append(
            {
                "type": "input",
                "block_id": f"answer_{i}",
                "element": {
                    "type": "plain_text_input",
                    "action_id": f"answer_{i}_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": "Your answer..."},
                },
                "label": {"type": "plain_text", "text": q},
            }
        )
    return blocks


def register(app):
    _init_db()

    @app.command("/join-manager")
    def join_manager_command(ack, body, client, command):
        ack()
        logger.info(f"/join-manager used by <@{command['user_id']}>")

        if command["user_id"] != OWNER_USER_ID:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":no_entry: Only the bot owner can use this command.",
            )
            return

        subcommand = command.get("text", "").strip()
        if subcommand != "setup":
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Usage: `/join-manager setup`",
            )
            return

        question_blocks = []
        for i in range(1, 6):
            question_blocks.append(
                {
                    "type": "input",
                    "block_id": f"q{i}",
                    "optional": i > 1,
                    "element": {
                        "type": "plain_text_input",
                        "action_id": f"q{i}_input",
                        "placeholder": {
                            "type": "plain_text",
                            "text": f"Enter question {i}",
                        },
                    },
                    "label": {"type": "plain_text", "text": f"Question {i}"},
                }
            )

        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "join_manager_setup_modal",
                "title": {"type": "plain_text", "text": "Join Manager Setup"},
                "submit": {"type": "plain_text", "text": "Save"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "input",
                        "block_id": "channel",
                        "element": {
                            "type": "conversations_select",
                            "action_id": "channel_input",
                            "filter": {
                                "include": ["public", "private"],
                                "exclude_bot_users": True,
                                "exclude_external_shared_channels": True,
                            },
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select channel to manage",
                            },
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Channel to manage",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "log_channel",
                        "optional": True,
                        "element": {
                            "type": "conversations_select",
                            "action_id": "log_channel_input",
                            "filter": {
                                "include": ["public", "private"],
                                "exclude_bot_users": True,
                                "exclude_external_shared_channels": True,
                            },
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Select log channel",
                            },
                        },
                        "label": {
                            "type": "plain_text",
                            "text": "Log channel (optional)",
                        },
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "*Questionnaire (up to 5 questions)*",
                        },
                    },
                    *question_blocks,
                    {"type": "divider"},
                    {
                        "type": "input",
                        "block_id": "ban_list",
                        "optional": True,
                        "element": {
                            "type": "plain_text_input",
                            "action_id": "ban_list_input",
                            "placeholder": {
                                "type": "plain_text",
                                "text": "Comma-separated user IDs (e.g., U123,U456)",
                            },
                        },
                        "label": {"type": "plain_text", "text": "Banned users"},
                    },
                ],
            },
        )

    @app.view("join_manager_setup_modal")
    def handle_setup_submission(ack, view, body, client):
        ack()
        user_id = body["user"]["id"]
        values = view["state"]["values"]

        channel_id = values["channel"]["channel_input"]["selected_conversation"]
        log_channel = values["log_channel"]["log_channel_input"].get(
            "selected_conversation"
        )

        questions = []
        for i in range(1, 6):
            q_val = values[f"q{i}"][f"q{i}_input"].get("value")
            if q_val:
                questions.append(q_val)

        ban_list_raw = values["ban_list"]["ban_list_input"].get("value", "") or ""
        ban_list = [uid.strip() for uid in ban_list_raw.split(",") if uid.strip()]

        logger.info(
            f"Join manager setup for channel {channel_id} by <@{user_id}>"
        )

        try:
            conn = psycopg2.connect(DATABASE_URL)
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO join_manager_config
                               (channel_id, enabled, log_channel, questions, ban_list)
                           VALUES (%s, TRUE, %s, %s, %s)
                           ON CONFLICT (channel_id) DO UPDATE SET
                               enabled = TRUE,
                               log_channel = EXCLUDED.log_channel,
                               questions = EXCLUDED.questions,
                               ban_list = EXCLUDED.ban_list""",
                        (
                            channel_id,
                            log_channel,
                            json.dumps(questions),
                            json.dumps(ban_list),
                        ),
                    )
                conn.commit()
            finally:
                conn.close()

            client.chat_postMessage(
                channel=user_id,
                text=f":white_check_mark: Join manager configured for <#{channel_id}> with {len(questions)} question(s).",
            )

            if log_channel:
                client.chat_postMessage(
                    channel=log_channel,
                    text=f":gear: Join manager configured for <#{channel_id}> by <@{user_id}>.",
                )
        except Exception as e:
            logger.error(f"Error saving join manager config: {e}")
            client.chat_postMessage(
                channel=user_id,
                text=":x: Failed to save join manager configuration.",
            )

    @app.command("/joinadityaschannel")
    def request_join(ack, body, client, command):
        ack()
        user_id = command["user_id"]
        logger.info(f"/joinadityaschannel used by <@{user_id}>")

        configs = _get_all_enabled_configs()
        if not configs:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: No channels are configured for join requests.",
            )
            return

        # Filter out channels where user is banned
        available = [
            (ch_id, cfg)
            for ch_id, cfg in configs
            if user_id not in cfg["ban_list"]
        ]

        if not available:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":no_entry: You are not allowed to request access.",
            )
            return

        if len(available) == 1:
            ch_id, cfg = available[0]
            questions = cfg["questions"]
            if not questions:
                app.client.chat_postMessage(
                    channel=command["channel_id"],
                    text=":x: No questions configured for this channel.",
                )
                return

            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "join_request_modal",
                    "private_metadata": json.dumps(
                        {"channel_id": ch_id, "questions": questions}
                    ),
                    "title": {"type": "plain_text", "text": "Join Request"},
                    "submit": {"type": "plain_text", "text": "Submit"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"Requesting to join <#{ch_id}>. Please answer the following:",
                            },
                        },
                        {"type": "divider"},
                        *_build_question_blocks(questions),
                    ],
                },
            )
        else:
            # Multiple channels available — show a picker
            options = []
            for ch_id, cfg in available:
                try:
                    info = client.conversations_info(channel=ch_id)
                    name = info["channel"]["name"]
                except Exception:
                    name = ch_id
                options.append(
                    {
                        "text": {"type": "plain_text", "text": f"#{name}"},
                        "value": ch_id,
                    }
                )

            client.views_open(
                trigger_id=body["trigger_id"],
                view={
                    "type": "modal",
                    "callback_id": "join_channel_picker_modal",
                    "title": {"type": "plain_text", "text": "Join Request"},
                    "submit": {"type": "plain_text", "text": "Next"},
                    "close": {"type": "plain_text", "text": "Cancel"},
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": "Which channel would you like to join?",
                            },
                        },
                        {
                            "type": "input",
                            "block_id": "channel_pick",
                            "element": {
                                "type": "static_select",
                                "action_id": "channel_pick_input",
                                "options": options,
                            },
                            "label": {
                                "type": "plain_text",
                                "text": "Select a channel",
                            },
                        },
                    ],
                },
            )

    @app.view("join_channel_picker_modal")
    def handle_channel_pick(ack, view, body, client):
        """Handle channel picker → replace modal with the questionnaire."""
        values = view["state"]["values"]
        channel_id = values["channel_pick"]["channel_pick_input"][
            "selected_option"
        ]["value"]
        config = _get_config(channel_id)

        if not config or not config["questions"]:
            ack()
            client.chat_postMessage(
                channel=body["user"]["id"],
                text=":x: No questions configured for this channel.",
            )
            return

        questions = config["questions"]
        ack(
            response_action="update",
            view={
                "type": "modal",
                "callback_id": "join_request_modal",
                "private_metadata": json.dumps(
                    {"channel_id": channel_id, "questions": questions}
                ),
                "title": {"type": "plain_text", "text": "Join Request"},
                "submit": {"type": "plain_text", "text": "Submit"},
                "close": {"type": "plain_text", "text": "Cancel"},
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"Requesting to join <#{channel_id}>. Please answer the following:",
                        },
                    },
                    {"type": "divider"},
                    *_build_question_blocks(questions),
                ],
            },
        )

    @app.view("join_request_modal")
    def handle_join_request(ack, view, body, client):
        ack()
        user_id = body["user"]["id"]
        metadata = json.loads(view.get("private_metadata", "{}"))
        target_channel = metadata.get("channel_id")
        questions = metadata.get("questions", [])
        values = view["state"]["values"]

        answers = []
        for i in range(1, len(questions) + 1):
            answer = values[f"answer_{i}"][f"answer_{i}_input"].get("value", "")
            answers.append(answer)

        logger.info(
            f"Join request from <@{user_id}> for channel {target_channel}"
        )

        config = _get_config(target_channel)
        notification_channel = (
            config.get("log_channel") if config else None
        ) or OWNER_USER_ID

        if not notification_channel:
            logger.error("No log channel or OWNER_USER_ID configured")
            return

        qa_blocks = []
        for q, a in zip(questions, answers):
            qa_blocks.append(
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{q}*\n{a}"},
                }
            )

        action_value = json.dumps(
            {"user_id": user_id, "channel_id": target_channel}
        )

        client.chat_postMessage(
            channel=notification_channel,
            blocks=[
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "New Join Request"},
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*From:* <@{user_id}>\n*Channel:* <#{target_channel}>",
                    },
                },
                {"type": "divider"},
                *qa_blocks,
                {"type": "divider"},
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Approve"},
                            "style": "primary",
                            "action_id": "join_request_approve",
                            "value": action_value,
                        },
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Deny"},
                            "style": "danger",
                            "action_id": "join_request_deny",
                            "value": action_value,
                        },
                    ],
                },
            ],
            text=f"New join request from <@{user_id}> for <#{target_channel}>",
        )

    @app.action("join_request_approve")
    def handle_approve(ack, body, client):
        ack()
        data = json.loads(body["actions"][0]["value"])
        user_id = data["user_id"]
        channel_id = data["channel_id"]
        approver_id = body["user"]["id"]

        logger.info(
            f"Join request approved: <@{user_id}> -> <#{channel_id}> by <@{approver_id}>"
        )

        try:
            client.conversations_invite(channel=channel_id, users=user_id)
            client.chat_postMessage(
                channel=user_id,
                text=f":white_check_mark: Your request to join <#{channel_id}> has been approved!",
            )

            client.chat_update(
                channel=body["channel"]["id"],
                ts=body["message"]["ts"],
                text=f":white_check_mark: Approved — <@{user_id}> was invited to <#{channel_id}> by <@{approver_id}>.",
                blocks=[],
            )
        except Exception as e:
            logger.error(f"Error approving join request: {e}")
            client.chat_postMessage(
                channel=approver_id,
                text=f":x: Failed to invite <@{user_id}> to <#{channel_id}>: {e}",
            )

    @app.action("join_request_deny")
    def handle_deny(ack, body, client):
        ack()
        data = json.loads(body["actions"][0]["value"])
        user_id = data["user_id"]
        channel_id = data["channel_id"]
        denier_id = body["user"]["id"]

        logger.info(
            f"Join request denied: <@{user_id}> -> <#{channel_id}> by <@{denier_id}>"
        )

        client.chat_postMessage(
            channel=user_id,
            text=f":no_entry: Your request to join <#{channel_id}> has been denied.",
        )

        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text=f":no_entry: Denied — <@{user_id}>'s request for <#{channel_id}> was denied by <@{denier_id}>.",
            blocks=[],
        )
