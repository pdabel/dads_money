#!/bin/bash
# Launcher script for Dad's Money on macOS

# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Activate virtual environment
source "$DIR/venv/bin/activate"

# Launch the application
exec python "$DIR/run.py"
