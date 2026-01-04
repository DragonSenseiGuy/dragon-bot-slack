#!/bin/bash

if [ -f bot.pid ]; then
    PID=$(cat bot.pid)
    echo "Stopping bot with PID: $PID"
    kill $PID
    rm bot.pid
    echo "Bot stopped."
else
    echo "Bot PID file not found. Is the bot running?"
fi
