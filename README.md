# Dragon Bot

Dragon Bot is a Slack bot designed to provide fun and useful commands. It's built with Python using the Slack Bolt framework.

## Commands

Type `/` in your Slack workspace to see available commands:

| Command | Description |
|---------|-------------|
| `/ping` | Gets the response time of the bot |
| `/about` | Info about the bot |
| `/credits` | Credits for the bot |
| `/help` | Shows all available commands |
| `/joke` | Get a random joke (optional: neutral, chuck, all) |
| `/fool` | Get a random April Fools' video |
| `/quote` | Get a quote (daily or random) |
| `/rock-paper-scissors` | Play rock paper scissors |
| `/dadjoke` | Get a random dad joke |
| `/dog-picture` | Get a random dog picture |
| `/cat-picture` | Get a random cat picture |
| `/xkcd-fetch` | Fetch a specific XKCD comic by ID |
| `/xkcd-random` | Fetch a random XKCD comic |
| `/xkcd-latest` | Fetch the latest XKCD comic |
| `/ask-ai` | Ask AI a question |
| `/ask-ai-personality` | Ask AI with a random personality |
| `/generate-image` | Generate an image using AI |

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/DragonSenseiGuy/dragon-bot
cd dragon-bot
```

### 2. Install dependencies
```bash
uv sync
```

### 3. Create a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. Enable **Socket Mode** and generate an App-Level Token with `connections:write` scope
3. Add **Bot Token Scopes** under OAuth & Permissions:
   - `chat:write`
   - `commands`
   - `files:write`
4. Create slash commands (see table below)
5. Install the app to your workspace

#### Slash Command Configuration

| Command | Short Description | Usage Hint |
|---------|------------------|------------|
| `/ping` | Gets the response time of the bot | |
| `/about` | Info about the bot | |
| `/credits` | Credits for the bot | |
| `/help` | Shows all available commands | |
| `/joke` | Get a random joke | `[neutral\|chuck\|all]` |
| `/fool` | Get a random April Fools' video | |
| `/quote` | Get a quote | `[daily\|random]` |
| `/rock-paper-scissors` | Play rock paper scissors | `Rock\|Paper\|Scissors` |
| `/dadjoke` | Get a random dad joke | |
| `/dog-picture` | Get a random dog picture | |
| `/cat-picture` | Get a random cat picture | |
| `/xkcd-fetch` | Fetch a specific XKCD comic | `<comic_id>` |
| `/xkcd-random` | Fetch a random XKCD comic | |
| `/xkcd-latest` | Fetch the latest XKCD comic | |
| `/ask-ai` | Ask AI a question | `<your question>` |
| `/ask-ai-personality` | Ask AI with a random personality | `<your question>` |
| `/generate-image` | Generate an image using AI | `<prompt>` |

**Note:** Leave "Request URL" blank when using Socket Mode.

### 4. Create a `.env` file
```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_APP_TOKEN=xapp-your-app-level-token
AI_API_KEY=your-ai-api-key-here
```

#### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SLACK_BOT_TOKEN` | Bot User OAuth Token (starts with `xoxb-`) | Yes |
| `SLACK_APP_TOKEN` | App-Level Token for Socket Mode (starts with `xapp-`) | Yes |
| `AI_API_KEY` | API key for Hack Club AI proxy | No |

### 5. Run the bot
```bash
uv run app.py
```

Or use the provided scripts:
```bash
./run.sh   # Start in background
./stop.sh  # Stop the bot
```

## Troubleshooting

### "not_authed" error
- Verify `SLACK_BOT_TOKEN` starts with `xoxb-`
- Verify `SLACK_APP_TOKEN` starts with `xapp-`

### Commands not appearing
- Ensure Socket Mode is enabled
- Reinstall the app to your workspace after adding commands

### "missing_scope" error
- Add the required scope under OAuth & Permissions
- Reinstall the app after adding scopes

## Contributing

Contributions are welcome! Feel free to open an issue or submit a pull request.
