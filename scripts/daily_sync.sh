#!/bin/bash
set -eo pipefail

# Determine project directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/logs"

LOG_FILE="$SCRIPT_DIR/logs/daily_sync.log"
exec >> "$LOG_FILE" 2>&1

echo "========================================================"
echo "MindWeave Automated Daily Ingestion Started: $(date)"
echo "Directory: $SCRIPT_DIR"

# Activate virtual environment
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
else
    echo "Error: Virtual environment not found at $SCRIPT_DIR/.venv"
    exit 1
fi

# Run daily-sync with link discovery
python -m backend.cli daily-sync --discover-links

echo "MindWeave Automated Daily Ingestion Completed: $(date)"
echo "========================================================"
