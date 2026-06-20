#!/bin/bash
# Usage: bash deploy.sh
# Pulls latest code from GitHub on the server and updates dependencies.

set -e

SERVER="ethan@192.168.1.113"
REMOTE_DIR="/home/ethan/star-signal"

ssh "$SERVER" "cd $REMOTE_DIR && git pull && venv/bin/pip install -r requirements.txt -q"

echo "✓ Server updated."
