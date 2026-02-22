import base64
import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List

import psycopg2
import requests
from dotenv import load_dotenv
from slack_bolt import Assistant, Say, SetStatus
from slack_bolt.context.set_suggested_prompts import SetSuggestedPrompts

load_dotenv()

AI_API_KEY = os.getenv("AI_API_KEY")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")
CHAT_CHANNEL = os.getenv("CHAT_CHANNEL")
OWNER_USER_ID = os.getenv("OWNER_USER_ID")
URL = "https://ai.hackclub.com/proxy/v1/chat/completions"
DAILY_LIMIT = 20

CHAT_SYSTEM_PROMPT = (
    "You are Dragon Bot, a helpful and friendly Slack bot for the Hack Club community. "
    "Keep your responses concise and conversational. "
    "Use the web_search tool if you need current information or facts you're unsure about. "
    "Format your responses using Slack mrkdwn syntax: "
    "*bold*, _italic_, ~strikethrough~, `code`, ```code blocks```, > blockquotes, "
    "and <url|text> for links. "
    "NEVER use standard Markdown like **bold**, [text](url), or ### headers."
)

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current information when you need up-to-date facts or answers you're unsure about.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                }
            },
            "required": ["query"],
        },
    },
}


def do_web_search(query):
    """Search using Hack Club Search API."""
    headers = {"Authorization": f"Bearer {SEARCH_API_KEY}"}
    resp = requests.get(
        "https://search.hackclub.com/res/v1/web/search",
        params={"q": query, "count": 5},
        headers=headers,
    )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("web", {}).get("results", [])
    formatted = []
    for r in results:
        formatted.append(
            f"Title: {r.get('title', '')}\n"
            f"URL: {r.get('url', '')}\n"
            f"Snippet: {r.get('description', '')}"
        )
    return "\n\n".join(formatted) if formatted else "No results found."


def call_ai_with_search(messages: List[Dict[str, str]]) -> str:
    """Call the AI API with optional search tool support. Returns the response text."""
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": messages,
        "stream": False,
    }
    if SEARCH_API_KEY:
        payload["tools"] = [SEARCH_TOOL]

    response = requests.post(URL, headers=headers, json=payload)
    response.raise_for_status()
    result = response.json()

    choice = result.get("choices", [{}])[0]
    message = choice.get("message", {})

    if message.get("tool_calls"):
        tool_call = message["tool_calls"][0]
        if tool_call["function"]["name"] == "web_search":
            args = json.loads(tool_call["function"]["arguments"])
            search_query = args.get("query", "")
            logging.info(f"AI requested web search: {search_query}")

            search_results = do_web_search(search_query)

            messages.append(message)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": search_results,
                }
            )

            payload["messages"] = messages
            payload.pop("tools", None)

            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})

    return message.get("content", "")


def _md_to_slack_mrkdwn(text: str) -> str:
    """Convert standard Markdown artifacts to Slack mrkdwn syntax."""
    # Convert images ![alt](url) to just the URL (before link conversion)
    text = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", r"\1", text)
    # Convert links [text](url) to <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    # Convert headers (## Header) to bold text
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Convert bold **text** or __text__ to *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.+?)__", r"*\1*", text)
    # Convert horizontal rules
    text = re.sub(r"^---+$", "───", text, flags=re.MULTILINE)
    return text


PERSONALITY = [
    "discord zoomer",
    "potter head",
    "roasting mode",
    "'You are absolutely right' mode",
]


def _init_db():
    """Create the ai_usage table if it doesn't exist."""
    if not DATABASE_URL:
        return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ai_usage (
                        usage_date DATE PRIMARY KEY,
                        count INTEGER NOT NULL DEFAULT 0
                    )
                """)
            conn.commit()
        finally:
            conn.close()
        logging.info("Database initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize database: {e}")


def check_and_increment_usage(user_id: str | None = None) -> bool:
    """Check and increment the daily AI usage count using PostgreSQL."""
    if user_id and user_id == OWNER_USER_ID:
        return True

    if not DATABASE_URL:
        logging.warning("DATABASE_URL not set, skipping usage tracking")
        return True

    today = datetime.now().date()

    try:
        conn = psycopg2.connect(DATABASE_URL)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count FROM ai_usage WHERE usage_date = %s",
                    (today,),
                )
                row = cur.fetchone()

                if row and row[0] >= DAILY_LIMIT:
                    logging.warning(f"Daily limit reached: {row[0]}/{DAILY_LIMIT}")
                    return False

                cur.execute(
                    """INSERT INTO ai_usage (usage_date, count) VALUES (%s, 1)
                       ON CONFLICT (usage_date) DO UPDATE SET count = ai_usage.count + 1""",
                    (today,),
                )
                conn.commit()
                logging.debug(f"Usage incremented for {today}")
                return True
        finally:
            conn.close()
    except Exception as e:
        logging.error(f"Database error in usage tracking: {e}")
        return True


def _build_thread_messages(replies):
    """Build AI message list from thread replies."""
    messages = [
        {"role": "system", "content": CHAT_SYSTEM_PROMPT},
    ]
    for msg in replies["messages"]:
        role = "user" if msg.get("bot_id") is None else "assistant"
        msg_text = msg.get("text", "")
        if role == "user":
            msg_text = re.sub(r"<@[A-Z0-9]+>", "", msg_text).strip()
        if msg_text:
            messages.append({"role": role, "content": msg_text})
    return messages


def handle_thread_followup(event, say, client, context):
    """Respond to thread replies where the bot has already participated."""
    thread_ts = event.get("thread_ts")
    if not thread_ts:
        return

    if event.get("bot_id") or event.get("subtype"):
        return

    channel_type = event.get("channel_type", "")
    if channel_type in ("im", "mpim"):
        return

    channel = event.get("channel")
    if CHAT_CHANNEL and channel != CHAT_CHANNEL:
        return

    text = event.get("text", "")
    bot_user_id = getattr(context, "bot_user_id", None)
    if bot_user_id and f"<@{bot_user_id}>" in text:
        return

    try:
        replies = client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=20,
        )
    except Exception:
        return

    bot_participated = any(
        msg.get("bot_id") for msg in replies.get("messages", [])
    )
    if not bot_participated:
        return

    if not AI_API_KEY:
        return

    user_id = event.get("user")

    if not check_and_increment_usage(user_id):
        return
    user_message = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
    if not user_message:
        return

    logging.info(f"Thread follow-up from <@{user_id}>: {user_message[:50]}...")

    messages = _build_thread_messages(replies)

    try:
        content = call_ai_with_search(messages)
        if content:
            content = _md_to_slack_mrkdwn(content)
            say(text=content, thread_ts=thread_ts)
        else:
            say(text="I couldn't come up with a response.", thread_ts=thread_ts)
    except Exception as e:
        logging.error(f"Error in thread follow-up: {e}")
        say(text=f":x: Something went wrong: {e}", thread_ts=thread_ts)


def register(app):
    _init_db()

    @app.command("/generate-image")
    def generate_image(ack, command):
        ack()
        logging.info(f"/generate-image used by <@{command['user_id']}>")

        if CHAT_CHANNEL and command["channel_id"] != CHAT_CHANNEL:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: This command can only be used in <#{CHAT_CHANNEL}>.",
            )
            return

        if not AI_API_KEY:
            logging.error("AI API key not configured")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: The AI API key is not configured.",
            )
            return

        if not check_and_increment_usage(command["user_id"]):
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
            )
            return

        prompt = command.get("text", "").strip()
        if not prompt:
            logging.debug("No prompt provided for /generate-image")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/generate-image <prompt>`",
            )
            return

        logging.info(f"Generating image with prompt: {prompt[:50]}...")
        app.client.chat_postMessage(
            channel=command["channel_id"],
            text="Generating image... please wait.",
        )

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "google/gemini-2.5-flash-image",
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
            "image_config": {"aspect_ratio": "16:9"},
        }

        try:
            logging.debug(f"Sending image generation request to {URL}")
            response = requests.post(URL, headers=headers, json=payload)
            logging.debug(f"API response status: {response.status_code}")
            result = response.json()

            if result.get("choices"):
                message = result["choices"][0]["message"]
                if message.get("images"):
                    logging.info("Image generated successfully, uploading to Slack")
                    image_url = message["images"][0]["image_url"]["url"]
                    if "," in image_url:
                        base64_data = image_url.split(",")[1]
                    else:
                        base64_data = image_url

                    image_bytes = base64.b64decode(base64_data)

                    app.client.files_upload_v2(
                        channel=command["channel_id"],
                        file=image_bytes,
                        filename="generated_image.png",
                        initial_comment=f"Generated image for: {prompt}",
                    )
                    logging.info("Image uploaded to Slack successfully")
                    return

            logging.warning("API returned no image in response")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="I couldn't generate an image. The API returned no image.",
            )
        except Exception as e:
            logging.error(f"Error generating image: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f"Failed to generate image: {e}",
            )

    @app.command("/ask-ai")
    def ask_ai(ack, command):
        ack()
        logging.info(f"/ask-ai used by <@{command['user_id']}>")

        if CHAT_CHANNEL and command["channel_id"] != CHAT_CHANNEL:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: This command can only be used in <#{CHAT_CHANNEL}>.",
            )
            return

        if not AI_API_KEY:
            logging.error("AI API key not configured")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: The AI API key is not configured.",
            )
            return

        if not check_and_increment_usage(command["user_id"]):
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
            )
            return

        prompt = command.get("text", "").strip()
        if not prompt:
            logging.debug("No prompt provided for /ask-ai")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/ask-ai <prompt>`",
            )
            return

        logging.info(f"Asking AI with prompt: {prompt[:50]}...")
        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        try:
            logging.debug(f"Sending AI request to {URL}")
            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            logging.debug(f"API response status: {response.status_code}")
            result = response.json()

            if result.get("choices") and result["choices"][0]["message"].get("content"):
                content = _md_to_slack_mrkdwn(result["choices"][0]["message"]["content"])
                logging.info(f"AI response received, length: {len(content)} chars")
                app.client.chat_postMessage(channel=command["channel_id"], text=content)
            else:
                logging.warning("AI returned empty response")
                app.client.chat_postMessage(
                    channel=command["channel_id"],
                    text="I couldn't get a response from the AI.",
                )
        except Exception as e:
            logging.error(f"Error asking AI: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f"Failed to communicate with the AI API: {e}",
            )

    @app.event("app_mention")
    def handle_mention(event, say, client):
        channel = event.get("channel")
        if CHAT_CHANNEL and channel != CHAT_CHANNEL:
            return

        user_id = event.get("user")
        text = event.get("text", "")
        thread_ts = event.get("thread_ts") or event.get("ts")

        user_message = re.sub(r"<@[A-Z0-9]+>", "", text).strip()
        if not user_message:
            say(text="Hey! What can I help you with?", thread_ts=thread_ts)
            return

        if not AI_API_KEY:
            say(text=":x: The AI API key is not configured.", thread_ts=thread_ts)
            return

        if not check_and_increment_usage(user_id):
            if not event.get("thread_ts"):
                say(
                    text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
                    thread_ts=thread_ts,
                )
            return

        logging.info(f"AI mention from <@{user_id}>: {user_message[:50]}...")

        replies = client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=20,
        )
        messages = _build_thread_messages(replies)

        try:
            content = call_ai_with_search(messages)
            if content:
                content = _md_to_slack_mrkdwn(content)
                logging.info(f"AI mention response sent, length: {len(content)} chars")
                say(text=content, thread_ts=thread_ts)
            else:
                say(text="I couldn't come up with a response.", thread_ts=thread_ts)
        except Exception as e:
            logging.error(f"Error in AI mention: {e}")
            say(text=f":x: Something went wrong: {e}", thread_ts=thread_ts)

    assistant = Assistant()

    @assistant.thread_started
    def handle_thread_started(
        say: Say,
        set_suggested_prompts: SetSuggestedPrompts,
        logger: logging.Logger,
    ):
        try:
            if CHAT_CHANNEL:
                say(f"Hey! I only respond in <#{CHAT_CHANNEL}>. Mention me there to chat!")
            else:
                say("Hey! How can I help you today?")
        except Exception as e:
            logger.exception(f"Failed to handle assistant_thread_started: {e}")
            say(f":warning: Something went wrong! ({e})")

    @assistant.user_message
    def handle_user_message(
        logger: logging.Logger,
        say: Say,
        set_status: SetStatus,
        **kwargs,
    ):
        if CHAT_CHANNEL:
            say(f":x: I only respond in <#{CHAT_CHANNEL}>. Mention me there to chat!")
            return

    app.use(assistant)

    @app.command("/ask-ai-personality")
    def ask_ai_with_personality(ack, command):
        ack()
        logging.info(f"/ask-ai-personality used by <@{command['user_id']}>")

        if CHAT_CHANNEL and command["channel_id"] != CHAT_CHANNEL:
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: This command can only be used in <#{CHAT_CHANNEL}>.",
            )
            return

        if not AI_API_KEY:
            logging.error("AI API key not configured")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=":x: The AI API key is not configured.",
            )
            return

        if not check_and_increment_usage(command["user_id"]):
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f":x: The daily AI command limit of {DAILY_LIMIT} has been reached.",
            )
            return

        prompt = command.get("text", "").strip()
        if not prompt:
            logging.debug("No prompt provided for /ask-ai-personality")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text="Please provide a prompt. Usage: `/ask-ai-personality <prompt>`",
            )
            return

        import random

        selected_personality = random.choice(PERSONALITY)
        logging.info(f"Using personality: {selected_personality}")
        logging.info(f"Asking AI with prompt: {prompt[:50]}...")

        headers = {
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "google/gemini-2.5-flash",
            "messages": [
                {"role": "system", "content": f"Act like a {selected_personality}. Format responses using Slack mrkdwn: *bold*, _italic_, ~strikethrough~, `code`, ```code blocks```, > blockquotes, <url|text> for links. NEVER use **bold**, [text](url), or ### headers."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }

        try:
            logging.debug(f"Sending AI request to {URL}")
            response = requests.post(URL, headers=headers, json=payload)
            response.raise_for_status()
            logging.debug(f"API response status: {response.status_code}")
            result = response.json()

            if result.get("choices") and result["choices"][0]["message"].get("content"):
                content = _md_to_slack_mrkdwn(result["choices"][0]["message"]["content"])
                logging.info(f"AI response received, length: {len(content)} chars")
                app.client.chat_postMessage(channel=command["channel_id"], text=content)
            else:
                logging.warning("AI returned empty response")
                app.client.chat_postMessage(
                    channel=command["channel_id"],
                    text="I couldn't get a response from the AI.",
                )
        except Exception as e:
            logging.error(f"Error asking AI: {e}")
            app.client.chat_postMessage(
                channel=command["channel_id"],
                text=f"Failed to communicate with the AI API: {e}",
            )
