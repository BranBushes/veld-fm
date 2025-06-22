# veld

A modern, tileable, terminal-based file manager built with Python and Textual.

<div align="center">

![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)
![Python Version](https://img.shields.io/badge/python-3.8+-brightgreen.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

</div>

![A screenshot of the veld file manager in action.](https://raw.githubusercontent.com/BranBushes/veld-fm/master/.assets/ss.png)

---

## About

`veld` is a powerful, modern file manager that runs directly in your terminal. Inspired by classic TUIs like Ranger and Midnight Commander, `veld` offers a fresh take with an emphasis on simplicity, ease of use, and multi-panel navigation.

## ✨ Features

*   🗂️ **Tileable Panels:** Open multiple directory views side-by-side to streamline your workflow.
*   ⌨️ **Intuitive Navigation:** Navigate your filesystem and switch between panels with familiar, ergonomic keybindings.
*   ⚙️ **Powerful File Operations:** Perform common operations like copy, move, delete, and rename in the active panel.
*   🎨 **Customizable Keybindings:** Don't like the defaults? Change every keybinding by editing a simple configuration file.
*   ✨ **Modern Interface:** A clean and aesthetically pleasing interface that focuses on your files, not on chrome.
*   🐧 **Cross-Platform:** Built with Python and Textual, `veld` runs on Linux, macOS, and Windows.

## 🚀 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/BranBushes/veld-fm.git
    cd veld-fm
    ```

2.  **Run the setup script:**
    This will install dependencies into a local virtual environment and create the system-wide `veld` command.
    ```bash
    chmod +x setup.sh
    sudo ./setup.sh
    ```

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
| **Tab**       | Focus next panel       |
| **Shift+Tab** | Focus previous panel   |

### File & Directory Operations

These actions apply to the currently active panel.

| Key         | Action                |
|-------------|-----------------------|
| **space**   | Toggle file selection |
| **n**       | Rename a file         |
| **d**       | Create a directory    |
| **r**       | Delete selected files |
| **m**       | Move selected files   |
| **c**       | Copy selected files   |

## 🔧 Configuration

`veld` allows you to customize all keybindings via a `config.toml` file.

### Config File Location

On the first run, a default config file will be created for you. The location varies by operating system:

```sh
# Linux & macOS
~/.config/veld-fm/config.toml

# Windows
%APPDATA%\BranBushes\veld-fm\config\config.toml
```

### Example Configuration

You can edit this file to change the keys for different actions.

```toml
# Veld File Manager Keybindings
[keybindings]
quit = "q" # Quit
add_panel = "o" # Open Panel
close_panel = "w" # Close Panel
toggle_selection = "space" # Select
rename = "n" # Rename
create_directory = "d" # New Dir
delete_selected = "r" # Delete
move_selected = "m" # Move
copy_selected = "c" # Copy
```

---

<p align="center">
  Made with ❤️ from Bangladesh!
</p>
