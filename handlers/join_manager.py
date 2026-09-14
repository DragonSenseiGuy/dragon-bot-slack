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
                        ban_list JSONB DEFAULT '[]',
                        notify_on_leave BOOLEAN NOT NULL DEFAULT TRUE,
                        remove_from_group_on_leave BOOLEAN NOT NULL DEFAULT TRUE
                    )
                """)
                # Existing deployments predate the leave columns.
                cur.execute("""
                    ALTER TABLE join_manager_config
                    ADD COLUMN IF NOT EXISTS notify_on_leave
                        BOOLEAN NOT NULL DEFAULT TRUE
                """)
                cur.execute("""
                    ALTER TABLE join_manager_config
                    ADD COLUMN IF NOT EXISTS remove_from_group_on_leave
                        BOOLEAN NOT NULL DEFAULT TRUE
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
                    "SELECT enabled, log_channel, questions, ban_list, "
                    "notify_on_leave, remove_from_group_on_leave "
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
                        "notify_on_leave": row[4],
                        "remove_from_group_on_leave": row[5],
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
                    "SELECT channel_id, log_channel, questions, ban_list, "
                    "notify_on_leave, remove_from_group_on_leave "
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
                            "notify_on_leave": row[4],
                            "remove_from_group_on_leave": row[5],
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
        if subcommand not in ("setup", "edit"):
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Usage: `/join-manager setup` or `/join-manager edit`",
            )
            return

        if subcommand == "edit":
            configs = _get_all_enabled_configs()
            if not configs:
                app.client.chat_postMessage(
                    channel=command["channel_id"],
                    text=":x: No join manager configurations exist yet. Use `/join-manager setup` first.",
                )
                return

            ch_id, cfg = configs[0]
            _open_setup_modal(client, body["trigger_id"], existing_channel=ch_id, existing_config=cfg)
            return

        _open_setup_modal(client, body["trigger_id"])

    def _open_setup_modal(client, trigger_id, existing_channel=None, existing_config=None):
        """Open the join manager setup/edit modal, optionally pre-filled."""
        existing_questions = (existing_config or {}).get("questions", [])
        existing_ban_list = (existing_config or {}).get("ban_list", [])
        existing_log_channel = (existing_config or {}).get("log_channel")
        # New configs default both leave behaviours on.
        existing_notify_on_leave = (existing_config or {}).get("notify_on_leave", True)
        existing_remove_on_leave = (existing_config or {}).get(
            "remove_from_group_on_leave", True
        )

        question_blocks = []
        for i in range(1, 6):
            element = {
                "type": "plain_text_input",
                "action_id": f"q{i}_input",
                "placeholder": {
                    "type": "plain_text",
                    "text": f"Enter question {i}",
                },
            }
            if i <= len(existing_questions):
                element["initial_value"] = existing_questions[i - 1]
            question_blocks.append(
                {
                    "type": "input",
                    "block_id": f"q{i}",
                    "optional": i > 1,
                    "element": element,
                    "label": {"type": "plain_text", "text": f"Question {i}"},
                }
            )

        channel_element = {
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
        }
        if existing_channel:
            channel_element["initial_conversation"] = existing_channel

        log_channel_element = {
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
        }
        if existing_log_channel:
            log_channel_element["initial_conversation"] = existing_log_channel

        ban_list_element = {
            "type": "plain_text_input",
            "action_id": "ban_list_input",
            "placeholder": {
                "type": "plain_text",
                "text": "Comma-separated user IDs (e.g., U123,U456)",
            },
        }
        if existing_ban_list:
            ban_list_element["initial_value"] = ",".join(existing_ban_list)

        leave_options = [
            {
                "text": {"type": "plain_text", "text": "Notify the log channel on leave"},
                "value": "notify_on_leave",
            },
            {
                "text": {"type": "plain_text", "text": "Remove from ping group on leave"},
                "value": "remove_from_group_on_leave",
            },
        ]
        initial_leave_options = [
            opt
            for opt, enabled in zip(
                leave_options, (existing_notify_on_leave, existing_remove_on_leave)
            )
            if enabled
        ]
        leave_element = {
            "type": "checkboxes",
            "action_id": "leave_settings_input",
            "options": leave_options,
        }
        if initial_leave_options:
            leave_element["initial_options"] = initial_leave_options

        client.views_open(
            trigger_id=trigger_id,
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
                        "element": channel_element,
                        "label": {
                            "type": "plain_text",
                            "text": "Channel to manage",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "log_channel",
                        "optional": True,
                        "element": log_channel_element,
                        "label": {
                            "type": "plain_text",
                            "text": "Log channel (optional)",
                        },
                    },
                    {
                        "type": "input",
                        "block_id": "leave_settings",
                        "optional": True,
                        "element": leave_element,
                        "label": {
                            "type": "plain_text",
                            "text": "When someone leaves the channel",
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
                        "element": ban_list_element,
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

        selected_leave = {
            opt["value"]
            for opt in values["leave_settings"]["leave_settings_input"].get(
                "selected_options"
            )
            or []
        }
        notify_on_leave = "notify_on_leave" in selected_leave
        remove_from_group_on_leave = "remove_from_group_on_leave" in selected_leave

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
                    cur.execute("DELETE FROM join_manager_config")
                    cur.execute(
                        """INSERT INTO join_manager_config
                               (channel_id, enabled, log_channel, questions, ban_list,
                                notify_on_leave, remove_from_group_on_leave)
                           VALUES (%s, TRUE, %s, %s, %s, %s, %s)""",
                        (
                            channel_id,
                            log_channel,
                            json.dumps(questions),
                            json.dumps(ban_list),
                            notify_on_leave,
                            remove_from_group_on_leave,
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

    @app.command("/joindsgschannel")
    def request_join(ack, body, client, command):
        ack()
        user_id = command["user_id"]
        logger.info(f"/joindsgschannel used by <@{user_id}>")

        configs = _get_all_enabled_configs()
        if not configs:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: No channels are configured for join requests.",
            )
            return

        ch_id, cfg = configs[0]

        if user_id in cfg["ban_list"]:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":no_entry: You are not allowed to request access.",
            )
            return

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
                            "text": "Please answer the following to request access:",
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
        except Exception as e:
            if "already_in_channel" in str(e):
                logger.info(f"User <@{user_id}> already in <#{channel_id}>")
                client.chat_update(
                    channel=body["channel"]["id"],
                    ts=body["message"]["ts"],
                    text=f":information_source: <@{user_id}> is already in <#{channel_id}>.",
                    blocks=[],
                )
                return
            logger.error(f"Error approving join request: {e}")
            client.chat_postMessage(
                channel=approver_id,
                text=f":x: Failed to invite <@{user_id}> to <#{channel_id}>: {e}",
            )
            return

        client.chat_postMessage(
            channel=user_id,
            text=":white_check_mark: Your join request has been approved!",
        )
        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text=f":white_check_mark: Approved — <@{user_id}> was invited to <#{channel_id}> by <@{approver_id}>.",
            blocks=[],
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
            text=":no_entry: Your join request has been denied.",
        )

        client.chat_update(
            channel=body["channel"]["id"],
            ts=body["message"]["ts"],
            text=f":no_entry: Denied — <@{user_id}>'s request for <#{channel_id}> was denied by <@{denier_id}>.",
            blocks=[],
        )
