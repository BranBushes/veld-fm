import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Set, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import toml
    except ImportError:
        sys.exit("Error: 'toml' package not found. Please run 'pip install toml' or the setup script.")

import platformdirs
from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.widgets import DirectoryTree, Footer, Input, Label, Tree
from textual.widgets._directory_tree import DirEntry
from textual.widgets.tree import TreeNode
from textual_autocomplete import PathAutoComplete

# --- Configuration Setup ---
APP_NAME = "veld-fm"
APP_AUTHOR = "BranBushes"

DEFAULT_KEYBINDINGS = {
    "quit": {"key": "q", "description": "Quit"},
    "add_panel": {"key": "o", "description": "Open Panel"},
    "close_panel": {"key": "w", "description": "Close Panel"},
    "toggle_selection": {"key": "space", "description": "Select"},
    "open_file": {"key": "enter", "description": "Open File"},
    "rename": {"key": "n", "description": "Rename"},
    "create_directory": {"key": "d", "description": "New Dir"},
    "delete_selected": {"key": "r", "description": "Delete"},
    "move_selected": {"key": "m", "description": "Move"},
    "copy_selected": {"key": "c", "description": "Copy"},
    "archive_selected": {"key": "a", "description": "Archive"},
    "extract_archive": {"key": "x", "description": "Extract"},
}

SUPPORTED_ARCHIVE_EXTENSIONS = tuple(
    ext for _, exts, _ in shutil.get_unpack_formats() for ext in exts
)


def load_or_create_config() -> dict:
    config_dir = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
    config_path = config_dir / "config.toml"
    keybindings = {action: details["key"] for action, details in DEFAULT_KEYBINDINGS.items()}

    if not config_path.is_file():
        config_dir.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("# Veld File Manager Keybindings\n[keybindings]\n")
            for action, details in DEFAULT_KEYBINDINGS.items():
                f.write(f'{action} = "{details["key"]}" # {details["description"]}\n')
        return keybindings

    try:
        if sys.version_info >= (3, 11):
            with open(config_path, "rb") as f: user_config = tomllib.load(f)
        else:
            with open(config_path, "r", encoding="utf-8") as f: user_config = toml.load(f)
        keybindings.update(user_config.get("keybindings", {}))
    except Exception:
        return keybindings
    return keybindings

# --- Tiling Components ---

class SelectableDirectoryTree(DirectoryTree):
    def __init__(self, path: str, *, panel: "FilePanel", key_map: dict, id: str | None = None) -> None:
        self.panel_ref = panel
        self.key_map = key_map
        super().__init__(path, id=id)

    def on_mount(self) -> None:
        if self.cursor_node and self.cursor_node.data:
            self.panel_ref.cursor_path = self.cursor_node.data.path

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        if event.node and event.node.data:
            self.panel_ref.cursor_path = event.node.data.path

    def render_label(self, node: TreeNode[DirEntry], base_style: Style, style: Style) -> Text:
        rendered = super().render_label(node, base_style, style)
        if node.data and node.data.path in self.panel_ref.selected_paths:
            rendered.style = "b black on green"
        return rendered

    def on_key(self, event: Key) -> None:
        """Called when the user presses a key."""
        if event.key == self.key_map.get("toggle_selection"):
            event.prevent_default()
            self.panel_ref.action_toggle_selection()
        elif event.key == self.key_map.get("open_file"):
            if self.panel_ref.cursor_path and self.panel_ref.cursor_path.is_file():
                event.prevent_default()
                # --- THIS IS THE FIX ---
                # We `cast` self.app to our specific class to satisfy the linter.
                cast("FileExplorerApp", self.app).action_open_file()

class FilePanel(Vertical):
    # We remove the incorrect override from here.
    # app: "FileExplorerApp" <--- This line is deleted.

    def __init__(self, path: str, *, key_map: dict, **kwargs) -> None:
        super().__init__(**kwargs)
        self.start_path = path
        self.key_map = key_map
        self.selected_paths: Set[Path] = set()
        self._cursor_path: Path | None = None
        self.directory_tree = SelectableDirectoryTree(
            self.start_path, panel=self, key_map=self.key_map, id="dir_tree"
        )
        self.path_label = Label(self.start_path, id="path_label")

    @property
    def cursor_path(self) -> Path | None:
        return self._cursor_path

    @cursor_path.setter
    def cursor_path(self, new_path: Path | None) -> None:
        self._cursor_path = new_path
        self.update_path_label()

    def compose(self) -> ComposeResult:
        yield self.directory_tree
        yield self.path_label

    def update_path_label(self) -> None:
        path_str = str(self.cursor_path) if self.cursor_path else "None"
        self.path_label.update(f"{path_str}\nSelected: {len(self.selected_paths)}")

    def reload_tree(self) -> None:
        self.directory_tree.reload()
        self.selected_paths.clear()
        self.cursor_path = None
        self.update_path_label()

    def action_toggle_selection(self) -> None:
        if self.cursor_path:
            if self.cursor_path in self.selected_paths:
                self.selected_paths.remove(self.cursor_path)
            else:
                self.selected_paths.add(self.cursor_path)
            self.directory_tree.refresh()
            self.update_path_label()

    def handle_file_operation(self, operation: str, src_paths: list[Path], dest_path: Path) -> None:
        for src_path in src_paths:
            if operation == "move":
                shutil.move(str(src_path), str(dest_path))
            elif operation == "copy":
                if src_path.is_dir(): shutil.copytree(src_path, dest_path / src_path.name)
                else: shutil.copy(src_path, dest_path)


class FileExplorerApp(App):
    DEFAULT_CSS = """
    Screen { layers: base input; }
    #main_container { layout: horizontal; }
    FilePanel {
        border: solid gray; width: 1fr; height: 100%; padding: 0 1;
    }
    FilePanel:focus-within { border: heavy cyan; }
    #path_label { height: 2; dock: bottom; }
    Input { layer: input; dock: bottom; height: 3; }
    """

    def __init__(self, start_path: Optional[str] = None) -> None:
        super().__init__()
        self.key_map = load_or_create_config()
        self.start_path = self._validate_start_path(start_path)
        self.current_action: Optional[str] = None
        self.action_target_panel: Optional[FilePanel] = None

    def _validate_start_path(self, path: Optional[str]) -> str:
        if path:
            candidate_path = Path(path).expanduser().resolve()
            if candidate_path.is_dir():
                return str(candidate_path)
        return str(Path.home())

    def _refresh_panels_at_path(self, path: Path) -> None:
        for panel in self.query(FilePanel):
            if Path(panel.start_path) == path or path.is_relative_to(Path(panel.start_path)):
                panel.reload_tree()

    def compose(self) -> ComposeResult:
        yield Horizontal(id="main_container")
        yield Footer()

    def on_mount(self) -> None:
        for action, details in DEFAULT_KEYBINDINGS.items():
            self.bind(self.key_map.get(action, details["key"]), action, description=details["description"])

        first_panel = FilePanel(self.start_path, key_map=self.key_map)
        self.query_one("#main_container").mount(first_panel)
        first_panel.focus()

    @property
    def active_panel(self) -> FilePanel | None:
        focused = self.focused
        if focused is None: return None
        if isinstance(focused, FilePanel): return focused
        if focused.parent and isinstance(focused.parent, FilePanel): return focused.parent
        return None

    def _prompt(self, placeholder: str, autocomplete: bool = False, value: str = "") -> None:
        if self.query(Input): return
        if autocomplete:
            input_widget = Input(placeholder=placeholder, value=value, id="path_input")
            self.mount(input_widget, PathAutoComplete(target="#path_input"))
        else:
            input_widget = Input(placeholder=placeholder, value=value)
        self.mount(input_widget)
        input_widget.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        user_input = event.value.strip()
        action = self.current_action
        panel = self.action_target_panel
        event.input.remove()
        try: self.query_one(PathAutoComplete).remove()
        except: pass
        self.current_action = None
        self.action_target_panel = None

        if not user_input and action not in ("extract",):
            return

        if action == "add_panel":
            new_path = self._validate_start_path(user_input)
            new_panel = FilePanel(path=new_path, key_map=self.key_map)
            self.query_one("#main_container").mount(new_panel)
            new_panel.focus()
            return

        if not panel: return

        if action == "delete" and user_input.lower() == "y":
            try:
                paths_to_refresh = {p.parent for p in panel.selected_paths if p.parent}
                for path in list(panel.selected_paths):
                    if path.is_dir(): shutil.rmtree(path)
                    else: path.unlink()
                self.notify(f"Deleted {len(panel.selected_paths)} items.")
                for path in paths_to_refresh:
                    self._refresh_panels_at_path(path)
            except Exception as e: self.notify(f"Error deleting: {e}", severity="error")

        elif action == "archive":
            archive_path = Path(user_input).expanduser()
            archive_format = archive_path.suffix.lstrip('.')
            if not archive_format:
                self.notify("Error: Archive path must have an extension (e.g., .zip).", severity="error")
                return
            archive_base_name = str(archive_path.with_suffix(''))
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    for item_path in panel.selected_paths:
                        dest_path = Path(tmpdir) / item_path.name
                        if item_path.is_dir(): shutil.copytree(item_path, dest_path)
                        else: shutil.copy2(item_path, dest_path)
                    shutil.make_archive(archive_base_name, archive_format, tmpdir)
                self.notify(f"Created archive '{archive_path.name}'.")
                self._refresh_panels_at_path(archive_path.parent)
            except Exception as e: self.notify(f"Error creating archive: {e}", severity="error")

        elif action == "extract":
            if panel.cursor_path:
                dest_path = Path(user_input).expanduser() if user_input else panel.cursor_path.parent
                dest_path.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.unpack_archive(panel.cursor_path, dest_path)
                    self.notify(f"Extracted to '{dest_path}'.")
                    self._refresh_panels_at_path(dest_path)
                except Exception as e: self.notify(f"Error extracting archive: {e}", severity="error")
        elif action in ("move", "copy"):
            dest_path = Path(user_input).expanduser()
            if not dest_path.is_dir():
                self.notify(f"Error: '{dest_path}' is not a valid directory.", severity="error")
                return
            try:
                src_paths = list(panel.selected_paths)
                src_parent_dirs = {p.parent for p in src_paths if p.parent}
                panel.handle_file_operation(action, src_paths, dest_path)
                op_past_tense = "moved" if action == "move" else "copied"
                self.notify(f"{len(src_paths)} item(s) {op_past_tense} to '{dest_path}'.")
                if action == "move":
                    for d in src_parent_dirs: self._refresh_panels_at_path(d)
                self._refresh_panels_at_path(dest_path)
            except Exception as e: self.notify(f"Error {action}ing: {e}", severity="error")
        elif action == "rename" and panel.cursor_path:
            try:
                old_path = panel.cursor_path
                new_path = old_path.with_name(user_input)
                if new_path.exists():
                    self.notify(f"Error: '{user_input}' already exists.", severity="error")
                    return
                old_path.rename(new_path)
                self.notify(f"Renamed to '{user_input}'.")
                self._refresh_panels_at_path(new_path.parent)
            except Exception as e: self.notify(f"Error renaming: {e}", severity="error")
        elif action == "create_directory":
            parent = panel.cursor_path if panel.cursor_path and panel.cursor_path.is_dir() else (panel.cursor_path.parent if panel.cursor_path else Path(panel.start_path))
            try:
                new_dir = parent / user_input
                new_dir.mkdir()
                self.notify(f"Created directory '{user_input}'.")
                self._refresh_panels_at_path(new_dir.parent)
            except Exception as e: self.notify(f"Error creating directory: {e}", severity="error")

    # --- Action Methods ---
    def action_open_file(self) -> None:
        """Opens the highlighted file using the system's default application."""
        panel = self.active_panel
        if panel and panel.cursor_path and panel.cursor_path.is_file():
            file_path = panel.cursor_path
            try:
                self.notify(f"Opening {file_path.name}...")
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":  # macOS
                    subprocess.run(["open", file_path], check=True)
                else:  # Linux and other Unix-like OS
                    subprocess.run(["xdg-open", file_path], check=True, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                self.notify(f"Error: Command not found. Cannot open file.", severity="error")
            except Exception as e:
                self.notify(f"Error opening file: {e}", severity="error")

    def action_add_panel(self) -> None:
        self.current_action = "add_panel"
        self._prompt("Open path:", autocomplete=True)

    def action_close_panel(self) -> None:
        all_panels = list(self.query(FilePanel))
        active = self.active_panel
        if len(all_panels) > 1 and active:
            try: current_index = all_panels.index(active)
            except ValueError: return
            active.remove()
            remaining_panels = list(self.query(FilePanel))
            focus_index = min(current_index, len(remaining_panels) - 1)
            if remaining_panels: remaining_panels[focus_index].focus()

    def action_archive_selected(self) -> None:
        panel = self.active_panel
        if panel and panel.selected_paths:
            self.current_action = "archive"
            self.action_target_panel = panel
            current_dir = panel.cursor_path.parent if panel.cursor_path else Path(panel.start_path)
            first_item_name = Path(list(panel.selected_paths)[0]).stem
            default_name = f"{first_item_name}.zip" if len(panel.selected_paths) == 1 else "archive.zip"
            default_path = current_dir / default_name
            self._prompt("Archive to (full path):", autocomplete=True, value=str(default_path))

    def action_extract_archive(self) -> None:
        panel = self.active_panel
        if panel and panel.cursor_path and str(panel.cursor_path).endswith(SUPPORTED_ARCHIVE_EXTENSIONS):
            self.current_action = "extract"
            self.action_target_panel = panel
            self._prompt("Extract to (blank for current dir):", autocomplete=True, value=str(panel.cursor_path.parent))
        else:
            self.notify("Highlighted item is not a supported archive.", severity="warning")

    def action_delete_selected(self) -> None:
        panel = self.active_panel
        if panel and panel.selected_paths:
            self.current_action = "delete"
            self.action_target_panel = panel
            self._prompt(f"Delete {len(panel.selected_paths)} items? (y/n)")

    def action_move_selected(self) -> None:
        panel = self.active_panel
        if panel and panel.selected_paths:
            self.current_action = "move"
            self.action_target_panel = panel
            self._prompt("Move to:", autocomplete=True)

    def action_copy_selected(self) -> None:
        panel = self.active_panel
        if panel and panel.selected_paths:
            self.current_action = "copy"
            self.action_target_panel = panel
            self._prompt("Copy to:", autocomplete=True)

    def action_rename(self) -> None:
        panel = self.active_panel
        if panel and panel.cursor_path:
            self.current_action = "rename"
            self.action_target_panel = panel
            self._prompt(f"Rename to:", value=panel.cursor_path.name)

    def action_create_directory(self) -> None:
        panel = self.active_panel
        if panel:
            self.current_action = "create_directory"
            self.action_target_panel = panel
            self._prompt("New directory name:")


def main():
    start_dir = sys.argv[1] if len(sys.argv) > 1 else None
    app = FileExplorerApp(start_path=start_dir)
    app.run()

if __name__ == "__main__":
    main()
