COMMANDS = [
    {"name": "/ping", "desc": "Response time"},
    {"name": "/about", "desc": "Bot info"},
    {"name": "/credits", "desc": "Credits"},
    {"name": "/help", "desc": "This message"},
    {"name": "/joke", "desc": "Random joke"},
    {"name": "/fool", "desc": "April Fools' video"},
    {"name": "/quote", "desc": "Daily/random quote"},
    {"name": "/rock-paper-scissors", "desc": "Play RPS"},
    {"name": "/dadjoke", "desc": "Dad joke"},
    {"name": "/dog-picture", "desc": "Dog pic"},
    {"name": "/cat-picture", "desc": "Cat pic"},
    {"name": "/xkcd-fetch", "desc": "XKCD by ID"},
    {"name": "/xkcd-random", "desc": "Random XKCD"},
    {"name": "/xkcd-latest", "desc": "Latest XKCD"},
    {"name": "/ask-ai", "desc": "Ask AI"},
    {"name": "/ask-ai-personality", "desc": "AI + personality"},
    {"name": "/generate-image", "desc": "Generate image"},
]


def register(app):
    @app.command("/help")
    def help_command(ack, respond, command):
        ack()

        left_col = COMMANDS[: len(COMMANDS) // 2 + 1]
        right_col = COMMANDS[len(COMMANDS) // 2 + 1 :]

        left_text = "\n".join([f"`{c['name']}` - {c['desc']}" for c in left_col])
        right_text = "\n".join([f"`{c['name']}` - {c['desc']}" for c in right_col])

        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": "Dragon Bot Commands"}},
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": left_text},
                    {"type": "mrkdwn", "text": right_text},
                ],
            },
        ]

        app.client.chat_postMessage(channel=command["channel_id"], blocks=blocks)
