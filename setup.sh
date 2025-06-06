#!/bin/bash

# Exit immediately if a command fails
set -e

echo "--- Starting Veld Project Setup (PEP 668 Compliant) ---"

# --- Prerequisite Check: python3-venv ---
# Check if the venv module is available, as it's needed to create virtual environments.
echo "[1/4] Checking for Python's 'venv' module..."
if ! python3 -c 'import venv' &>/dev/null; then
  echo "Error: The 'python3-venv' package is not installed."
  echo "Please install it using your system's package manager."
  echo "Example for Debian/Ubuntu: sudo apt install python3-venv"
  echo "Example for Fedora/CentOS: sudo dnf install python3-venv"
  echo "Example for Arch Linux: sudo pacman -S python-venv"
  exit 1
fi
echo "'venv' module found."

# --- Step 2: Create Virtual Environment ---
# A virtual environment keeps your project's dependencies isolated.
VENV_DIR=".venv"
echo "[2/4] Setting up virtual environment in './${VENV_DIR}'..."
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  echo "Virtual environment created."
else
  echo "Virtual environment already exists."
fi

# --- Step 3: Install Dependencies into Virtual Environment ---
echo "[3/4] Installing dependencies from requirements.txt..."
if [ -f "requirements.txt" ]; then
  # Use the pip from the virtual environment to install packages.
  "$VENV_DIR/bin/pip" install -r requirements.txt
  echo "Dependencies installed successfully into the virtual environment."
else
  echo "Warning: requirements.txt not found. Skipping dependency installation."
fi

# --- Step 4: Create the 'veld' Command ---
# This makes your script runnable system-wide by using the virtual environment's Python.
echo "[4/4] Creating the 'veld' command..."

# Get the absolute path of the project directory.
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)
PYTHON_EXEC="$SCRIPT_DIR/$VENV_DIR/bin/python"
VELD_PY_PATH="$SCRIPT_DIR/veld.py"

# The launcher script now points to the Python executable inside the virtual environment.
# "$@" ensures any arguments passed to 'veld' are forwarded to your python script.
LAUNCHER_CONTENT="#!/bin/bash
\"$PYTHON_EXEC\" \"$VELD_PY_PATH\" \"\$@\""

# Install the command to /usr/local/bin, which is a standard location for user-installed executables.
CMD_PATH="/usr/local/bin/veld"

echo "Creating command at ${CMD_PATH}. You may be asked for your administrator password."
# Use sudo to write the file and set its permissions.
echo -e "${LAUNCHER_CONTENT}" | sudo tee "${CMD_PATH}" >/dev/null
sudo chmod +x "${CMD_PATH}"

echo
echo "--- Setup Complete! ---"
echo "A virtual environment has been created in the '${VENV_DIR}' directory."
echo "You can now run your application from any terminal by typing: veld"
echo
echo "Recommendation: Add '.venv' to your .gitignore file to avoid committing it to version control."
