#!/bin/bash
# Developer setup script for veld-fm

# Exit immediately if a command fails
set -e

VENV_DIR=".venv"
PYTHON_EXEC="python3"

echo "--- Starting Veld Developer Setup ---"

# 1. Set up virtual environment
echo "[1/3] Setting up virtual environment in './${VENV_DIR}'..."
if [ ! -d "$VENV_DIR" ]; then
  $PYTHON_EXEC -m venv "$VENV_DIR"
  echo "Virtual environment created."
else
  echo "Virtual environment already exists."
fi

# 2. Activate the virtual environment (for this script's scope)
source "$VENV_DIR/bin/activate"
echo "[2/3] Activated virtual environment."

# 3. Install the project in editable mode with its dependencies
echo "[3/3] Installing project in editable mode..."
# This command reads dependencies from pyproject.toml and installs them.
# The '-e' flag makes it so your local code changes are used when you run 'veld'.
pip install -e .

echo
echo "--- Developer Setup Complete! ---"
echo "To activate the environment in your shell, run: source ${VENV_DIR}/bin/activate"
echo "You can now run 'veld' to test your local code."
