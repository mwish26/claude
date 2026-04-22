#!/usr/bin/env bash
# Sets up a cron job to run MAP checks twice daily (8 AM and 8 PM).
# Usage: bash setup_cron.sh [/path/to/project]

set -euo pipefail

PROJECT_DIR="${1:-$(cd "$(dirname "$0")" && pwd)}"
PYTHON="$(command -v python3)"
SCRIPT="$PROJECT_DIR/run_check.py"
LOG="$PROJECT_DIR/cron.log"

if [ ! -f "$SCRIPT" ]; then
    echo "Error: $SCRIPT not found. Run this from the project root."
    exit 1
fi

CRON_LINE_AM="0 8 * * * cd $PROJECT_DIR && $PYTHON $SCRIPT >> $LOG 2>&1"
CRON_LINE_PM="0 20 * * * cd $PROJECT_DIR && $PYTHON $SCRIPT >> $LOG 2>&1"

# Add to crontab without duplicating
( crontab -l 2>/dev/null | grep -v "run_check.py"; echo "$CRON_LINE_AM"; echo "$CRON_LINE_PM" ) | crontab -

echo "Cron jobs installed:"
echo "  $CRON_LINE_AM"
echo "  $CRON_LINE_PM"
echo ""
echo "To verify: crontab -l"
echo "To remove:  crontab -l | grep -v run_check.py | crontab -"
