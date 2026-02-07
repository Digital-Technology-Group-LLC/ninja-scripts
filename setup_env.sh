#!/bin/bash
# This script activates the Python virtual environment.
# Assumes the virtual environment is located at 'venv' in the project root.

echo "Activating virtual environment..."

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
VENV_PATH="$SCRIPT_DIR/venv/bin/activate"

if [ -f "$VENV_PATH" ]; then
  source "$VENV_PATH"
  echo "Virtual environment activated. You can now run the Python scripts."
else
  echo "Error: Virtual environment not found at '$SCRIPT_DIR/venv'."
  echo "Please create it first using: python3 -m venv venv"
  exit 1
fi
