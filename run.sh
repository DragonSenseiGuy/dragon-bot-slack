#!/bin/bash

# Start the bot in the background
nohup uv run app.py > bot.log 2> bot.err &

# Get the process ID of the last background command
PID=$!

# Save the PID to a file
echo $PID > bot.pid

echo "Bot started in the background with PID: $PID"
echo "Logs are being saved to bot.log and bot.err"
echo "To stop the bot, run: ./stop.sh"
