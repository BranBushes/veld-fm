# veld

A modern, tileable, terminal-based file manager built with Python and Textual.

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.9+-brightgreen.svg)](https://www.python.org/downloads/)
[![PyPI version](https://img.shields.io/pypi/v/veld-fm.svg)](https://pypi.org/project/veld-fm/) <!-- Add this line when you publish to PyPI -->

</div>

![A screenshot of the veld file manager in action.](https://raw.githubusercontent.com/BranBushes/veld-fm/master/.assets/ss.png)

---

## About

`veld` is a powerful, modern file manager that runs directly in your terminal. Inspired by classic TUIs like Ranger and Midnight Commander, `veld` offers a fresh take with an emphasis on simplicity, ease of use, and multi-panel navigation.

## ✨ Features

*   🗂️ **Tileable Panels:** Open multiple directory views side-by-side to streamline your workflow.
*   ⌨️ **Intuitive Navigation:** Navigate your filesystem and switch between panels with familiar, ergonomic keybindings.
*   ⚙️ **Powerful File Operations:** Perform common operations like copy, move, delete, and rename in the active panel.
*   **ዚ  Archive Management:** Create and extract zip/tar archives directly within the file manager.
*   🎨 **Customizable Keybindings:** Don't like the defaults? Change every keybinding by editing a simple configuration file.
*   🐧 **Cross-Platform:** Built with Python and Textual, `veld` runs on Linux, macOS, and Windows.

## 🚀 Installation

You need Python 3.9+ and `pip` installed.

Install the latest development version directly from GitHub:

```bash
pip install git+https://github.com/BranBushes/veld-fm.git
```

Or using `uv`:
```bash
uv pip install git+https://github.com/BranBushes/veld-fm.git
```

This will install `veld` and make the `veld` command available in your terminal.

## 💻 Usage

Once installed, you can run `veld` from anywhere in your terminal. You can also provide an optional starting directory for the first panel.

```bash
# Start in the default home directory
veld

# Start in the ~/Documents directory
veld ~/Documents
```

### Navigating Panels

Use `Tab` and `Shift+Tab` to cycle focus between open panels. The active panel is highlighted with a colored border.

## ⌨️ Keybindings

Keybindings are organized by function and can be fully customized (see Configuration section).

### Application & Panel Management

| Key           | Action                 |
|---------------|------------------------|
| **q**         | Quit the application   |
| **o**         | Open a new panel       |
| **w**         | Close the active panel |

### File & Directory Operations

| Key         | Action                |
|-------------|-----------------------|
| **space**   | Toggle file selection |
| **n**       | Rename a file         |
| **d**       | Create a directory    |
| **r**       | Delete selected files |
| **m**       | Move selected files   |
| **c**       | Copy selected files   |
| **a**       | Archive selected items|
| **x**       | Extract highlighted archive |

## 🔧 Configuration

On the first run, a config file is created at `~/.config/veld-fm/config.toml`. You can edit this file to change keybindings.

## 🧑‍💻 For Developers

To set up a development environment:
```bash
git clone https://github.com/BranBushes/veld-fm.git
cd veld-fm
./setup.sh # This creates a venv and installs in editable mode
source .venv/bin/activate
```

---

<p align="center">
  Made with ❤️ from Bangladesh!
</p>
