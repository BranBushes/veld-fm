import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Optional, Set, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import toml
    except ImportError:
        sys.exit("Error: 'toml' package not found. Please run 'pip install toml' or the setup script.")

import platformdirs
from PIL import Image
from rich.style import Style
from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.widgets import DirectoryTree, Footer, Input, Label, Static, Tree
from textual.widgets._directory_tree import DirEntry
from textual.widgets.tree import TreeNode
from textual_autocomplete import PathAutoComplete
from term_image.image import BlockImage
from term_image.exceptions import TermImageError

# --- Configuration Setup ---
APP_NAME = "veld-fm"
APP_AUTHOR = "BranBushes"

DEFAULT_KEYBINDINGS = {
    # App & Panel Management
    "quit": {"key": "q", "description": "Quit"},
    "add_panel": {"key": "o", "description": "Open Panel"},
    "close_panel": {"key": "w", "description": "Close Panel"},
    "toggle_preview": {"key": "p", "description": "Toggle Preview"},
    "close_search_panel": {"key": "backspace", "description": "Close Search"},
    # Navigation & Selection
    "nav_up": {"key": "up", "description": "Navigate Up"},
    "nav_down": {"key": "down", "description": "Navigate Down"},
    "nav_parent": {"key": "left", "description": "Go to Parent"},
    "select_item": {"key": "enter", "description": "Open / Enter Dir"},
    "toggle_selection": {"key": "space", "description": "Select"},
    # File Operations
    "find": {"key": "f", "description": "Find"},
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
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".bmp")


def generate_duplicate_path(original_path: Path) -> Path:
    parent = original_path.parent
    stem = original_path.stem
    suffix = original_path.suffix
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


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
            with open(config_path, "rb") as f:
                user_config = tomllib.load(f)
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = toml.load(f)
        keybindings.update(user_config.get("keybindings", {}))
    except Exception:
        return keybindings
    return keybindings


# --- Search Functionality ---
class SearchResultTree(Tree[Path]):
    def __init__(self, search_results: Iterable[Path], **kwargs) -> None:
        super().__init__("Search Results", data=Path(), **kwargs)
        self.search_results = search_results

    def on_mount(self) -> None:
        for path in self.search_results:
            self.root.add(str(path), data=path)


class SearchPanel(Vertical):
    def __init__(self, search_results: Iterable[Path], **kwargs) -> None:
        super().__init__(**kwargs)
        self.search_results = search_results

    def compose(self) -> ComposeResult:
        yield SearchResultTree(self.search_results, id="search_tree")


# --- Tiling Components ---
class SelectableDirectoryTree(DirectoryTree):
    def __init__(self, path: str, *, panel: "FilePanel", key_map: dict, id: str | None = None) -> None:
        self.panel_ref = panel
        self.key_map = key_map
        super().__init__(path, id=id)

    def on_mount(self) -> None:
        super().on_mount()
        if self.cursor_node and self.cursor_node.data:
            self.panel_ref.cursor_path = self.cursor_node.data.path

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        if event.node and event.node.data:
            self.panel_ref.cursor_path = event.node.data.path
            cast("FileExplorerApp", self.app).update_preview(event.node.data.path)

    def render_label(self, node: TreeNode[DirEntry], base_style: Style, style: Style) -> Text:
        rendered = super().render_label(node, base_style, style)
        if node.data and node.data.path in self.panel_ref.selected_paths:
            rendered.style = "b black on green"
        return rendered

    def on_key(self, event: Key) -> None:
        key = event.key

        # --- Custom Navigation & Selection Handling ---
        # We check if the pressed key matches a custom binding. If it does,
        # we perform the action and then crucially call event.stop()
        # to prevent Textual's default key bindings from also firing,
        # which caused the "double action" bug.

        if key == self.key_map.get("nav_up"):
            event.stop()
            self.action_cursor_up()
        elif key == self.key_map.get("nav_down"):
            event.stop()
            self.action_cursor_down()
        elif key == self.key_map.get("nav_parent"):
            event.stop()
            self.action_cursor_parent()  # Correct method to go to parent
        elif key == self.key_map.get("select_item"):
            event.stop()
            if self.cursor_node and self.cursor_node.data:
                path = self.cursor_node.data.path
                if path.is_file():
                    cast("FileExplorerApp", self.app).action_open_file()
                elif path.is_dir():
                    self.action_toggle_node() # Expands/collapses directory
        elif key == self.key_map.get("toggle_selection"):
            event.stop()
            self.panel_ref.action_toggle_selection()


class FilePanel(Vertical):
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


class PreviewPanel(Static):
    def __init__(self, **kwargs) -> None:
        super().__init__("Preview", **kwargs)

    def update_preview(self, content) -> None:
        self.update(content)


class FileExplorerApp(App):
    DEFAULT_CSS = """
    Screen { layers: base input; }
    #app_container {
        layout: horizontal;
    }
    #main_container {
        layout: horizontal;
        width: 3fr;
    }
    #preview_panel {
        width: 2fr;
        height: 100%;
        border: solid gray;
        padding: 1;
    }
    FilePanel, SearchPanel {
        border: solid gray;
        width: 1fr;
        height: 100%;
        padding: 0 1;
    }
    FilePanel:focus-within, SearchPanel:focus-within {
        border: heavy cyan;
    }
    #path_label {
        height: 2;
        dock: bottom;
    }
    Input {
        layer: input;
        dock: bottom;
        height: 3;
    }
    """

    def __init__(self, start_path: Optional[str] = None) -> None:
        super().__init__()
        self.key_map = load_or_create_config()
        self.start_path = self._validate_start_path(start_path)
        self.current_action: Optional[str] = None
        self.action_target_panel: Optional[FilePanel] = None
        self.action_context: dict = {}

        # Pre-initialize term-image to avoid ghost input on first render.
        # Use BlockImage specifically to avoid terminal queries.
        try:
            dummy_image = Image.new("RGB", (1, 1))
            str(BlockImage(dummy_image))
        except (TermImageError, ImportError):
            # This can happen in terminals without proper support or if Pillow isn't installed.
            # We can ignore it as term-image will handle it gracefully later.
            pass

    def _validate_start_path(self, path: Optional[str]) -> str:
        if path:
            candidate_path = Path(path).expanduser().resolve()
            if candidate_path.is_dir():
                return str(candidate_path)
        return str(Path.home())

    def _refresh_panels_at_path(self, path: Path) -> None:
        if not path.exists():
            return
        for panel in self.query(FilePanel):
            if Path(panel.start_path) == path or path.is_relative_to(Path(panel.start_path)):
                panel.reload_tree()

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Horizontal(id="main_container"),
            PreviewPanel(id="preview_panel"),
            id="app_container",
        )
        yield Footer()

    def on_mount(self) -> None:
        # Bind all actions EXCEPT the ones that are now handled exclusively
        # by the SelectableDirectoryTree's on_key method.
        actions_handled_by_widget = [
            "nav_up", "nav_down", "nav_parent", "select_item", "toggle_selection"
        ]
        for action, details in DEFAULT_KEYBINDINGS.items():
            if action not in actions_handled_by_widget:
                self.bind(self.key_map.get(action, details["key"]), action, description=details["description"])

        first_panel = FilePanel(self.start_path, key_map=self.key_map)
        self.query_one("#main_container").mount(first_panel)
        first_panel.focus()

    @property
    def active_panel(self) -> FilePanel | None:
        focused = self.focused
        if focused is None:
            return None
        if isinstance(focused, FilePanel):
            return focused
        if focused.parent and isinstance(focused.parent, FilePanel):
            return focused.parent
        return None

    def update_preview(self, path: Path) -> None:
        preview_panel = self.query_one(PreviewPanel)
        if path.is_file():
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                try:
                    # Subtract 2 for padding
                    width = self.query_one(PreviewPanel).size.width - 2
                    image = BlockImage.from_file(path, width=width)
                    preview_panel.update_preview(Text.from_ansi(str(image)))
                except TermImageError as e:
                    preview_panel.update_preview(f"Image preview failed:\n{e}")
                except Exception as e:
                    preview_panel.update_preview(f"Error: {e}")
            else:
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read(1024 * 10)  # Read up to 10KB
                        syntax = Syntax(content, path.name, theme="monokai", line_numbers=True, word_wrap=True)
                        preview_panel.update_preview(syntax)
                except Exception:
                    preview_panel.update_preview(f"Cannot preview binary file: {path.name}")
        else:
            preview_panel.update_preview("Directory - No preview available")

    def _prompt(self, placeholder: str, autocomplete: bool = False, value: str = "") -> None:
        if self.query(Input):
            return
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
        try:
            self.query_one(PathAutoComplete).remove()
        except:
            pass
        self.current_action = None
        self.action_target_panel = None

        if not user_input and action not in ("extract", "copy_choice_prompt", "move_choice_prompt", "find"):
            return

        if action == "find":
            if not panel:
                self.notify("Error: No active panel to search in.", severity="error")
                return
            search_dir = Path(panel.start_path)
            results = [p for p in search_dir.rglob(f"*{user_input}*")]
            if results:
                search_panel = SearchPanel(results)
                self.query_one("#main_container").mount(search_panel)
                search_panel.focus()
            else:
                self.notify("No results found.")
            return

        if action == "copy_choice_prompt":
            choice = user_input.lower()
            src_path = self.action_context.get("src_path")
            dest_dir = self.action_context.get("dest_dir")
            if not src_path or not dest_dir:
                return

            did_copy = False
            if choice == 'r':
                if src_path.is_dir():
                    shutil.copytree(src_path, dest_dir / src_path.name, dirs_exist_ok=True)
                else:
                    shutil.copy2(src_path, dest_dir)
                did_copy = True
            elif choice == 'd':
                shutil.copy2(src_path, generate_duplicate_path(dest_dir / src_path.name))
                did_copy = True

            if did_copy:
                self._refresh_panels_at_path(dest_dir)

            self.run_worker(self._process_copy_queue, thread=True, exclusive=True)
            return

        elif action == "move_choice_prompt":
            choice = user_input.lower()
            src_path = self.action_context.get("src_path")
            dest_dir = self.action_context.get("dest_dir")
            if not src_path or not dest_dir:
                return

            src_parent = src_path.parent
            did_move = False

            if choice == 'r':  # Replace
                dest_item = dest_dir / src_path.name
                if dest_item.is_dir():
                    shutil.rmtree(dest_item)
                else:
                    dest_item.unlink()
                shutil.move(str(src_path), str(dest_dir))
                did_move = True
            elif choice == 'd':  # Duplicate name on move (copy -> delete source)
                new_path = generate_duplicate_path(dest_dir / src_path.name)
                if src_path.is_dir():
                    shutil.copytree(src_path, new_path)
                    shutil.rmtree(src_path)
                else:
                    shutil.copy2(src_path, new_path)
                    src_path.unlink()
                did_move = True

            if src_parent:
                self._refresh_panels_at_path(src_parent)
            if did_move:
                self._refresh_panels_at_path(dest_dir)

            self.run_worker(self._process_move_queue, thread=True, exclusive=True)
            return

        if action == "add_panel":
            new_path = self._validate_start_path(user_input)
            new_panel = FilePanel(path=new_path, key_map=self.key_map)
            self.query_one("#main_container").mount(new_panel)
            new_panel.focus()
            return

        if not panel:
            return

        if action == "delete_selected" and user_input.lower() == "y":
            try:
                paths_to_refresh = {p.parent for p in panel.selected_paths if p.parent}
                for path in list(panel.selected_paths):
                    if path.is_dir():
                        shutil.rmtree(path)
                    else:
                        path.unlink()
                self.notify(f"Deleted {len(panel.selected_paths)} items.")
                for path in paths_to_refresh:
                    self._refresh_panels_at_path(path)
            except Exception as e:
                self.notify(f"Error deleting: {e}", severity="error")

        elif action == "archive_selected":
            archive_path = Path(user_input).expanduser().resolve()
            archive_format = archive_path.suffix.lstrip('.')
            if not archive_format:
                self.notify("Error: Archive path must have an extension (e.g., .zip).", severity="error")
                return
            archive_base_name = str(archive_path.with_suffix(''))
            try:
                with tempfile.TemporaryDirectory() as tmpdir:
                    for item_path in panel.selected_paths:
                        dest_path = Path(tmpdir) / item_path.name
                        if item_path.is_dir():
                            shutil.copytree(item_path, dest_path)
                        else:
                            shutil.copy2(item_path, dest_path)
                    shutil.make_archive(archive_base_name, archive_format, tmpdir)
                self.notify(f"Created archive '{archive_path.name}'.")
                self._refresh_panels_at_path(archive_path.parent)
            except Exception as e:
                self.notify(f"Error creating archive: {e}", severity="error")

        elif action == "extract_archive":
            if panel.cursor_path:
                dest_path = Path(user_input).expanduser().resolve() if user_input else panel.cursor_path.parent
                dest_path.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.unpack_archive(panel.cursor_path, dest_path)
                    self.notify(f"Extracted to '{dest_path}'.")
                    self._refresh_panels_at_path(dest_path)
                except Exception as e:
                    self.notify(f"Error extracting archive: {e}", severity="error")
        elif action == "copy_selected":
            dest_path = Path(user_input).expanduser().resolve()
            if not dest_path.is_dir():
                self.notify(f"Error: '{dest_path}' is not a valid directory.", severity="error")
                return
            self.action_context = {"copy_queue": list(panel.selected_paths), "dest_dir": dest_path}
            self.run_worker(self._process_copy_queue, thread=True, exclusive=True)

        elif action == "move_selected":
            dest_path = Path(user_input).expanduser().resolve()
            if not dest_path.is_dir():
                self.notify(f"Error: '{dest_path}' is not a valid directory.", severity="error")
                return
            self.action_context = {"move_queue": list(panel.selected_paths), "dest_dir": dest_path}
            self.run_worker(self._process_move_queue, thread=True, exclusive=True)

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
            except Exception as e:
                self.notify(f"Error renaming: {e}", severity="error")
        elif action == "create_directory":
            parent = panel.cursor_path if panel.cursor_path and panel.cursor_path.is_dir() else (
                panel.cursor_path.parent if panel.cursor_path else Path(panel.start_path))
            try:
                new_dir = parent / user_input
                new_dir.mkdir()
                self.notify(f"Created directory '{user_input}'.")
                self._refresh_panels_at_path(new_dir.parent)
            except Exception as e:
                self.notify(f"Error creating directory: {e}", severity="error")

    def _process_move_queue(self) -> None:
        move_queue = self.action_context.get("move_queue", [])
        dest_dir = self.action_context.get("dest_dir")

        if not move_queue or not dest_dir:
            if dest_dir:
                self.call_from_thread(self._refresh_panels_at_path, dest_dir)
            self.call_from_thread(self.notify, "Move operation complete.")
            self.action_context = {}
            return

        src_path = move_queue.pop(0)
        full_dest_path = dest_dir / src_path.name

        if full_dest_path.exists():
            self.current_action = "move_choice_prompt"
            self.action_context["src_path"] = src_path
            self.call_from_thread(self._prompt, f"'{src_path.name}' exists. Replace (r), Duplicate (d), or Skip (s)?")
            return

        try:
            src_parent = src_path.parent
            shutil.move(str(src_path), str(dest_dir))
            if src_parent:
                self.call_from_thread(self._refresh_panels_at_path, src_parent)
            self.run_worker(self._process_move_queue, thread=True, exclusive=True)
        except Exception as e:
            self.call_from_thread(self.notify, f"Error moving {src_path.name}: {e}", severity="error")
            self.run_worker(self._process_move_queue, thread=True, exclusive=True)

    def _process_copy_queue(self) -> None:
        copy_queue = self.action_context.get("copy_queue", [])
        dest_dir = self.action_context.get("dest_dir")

        if not copy_queue or not dest_dir:
            self.call_from_thread(self.notify, "Copy operation complete.")
            self.action_context = {}
            return

        src_path = copy_queue.pop(0)
        full_dest_path = dest_dir / src_path.name

        if full_dest_path.exists() and src_path.resolve() != full_dest_path.resolve():
            self.current_action = "copy_choice_prompt"
            self.action_context["src_path"] = src_path
            self.call_from_thread(self._prompt, f"'{src_path.name}' exists. Replace (r), Duplicate (d), or Skip (s)?")
            return

        try:
            if src_path.is_dir():
                shutil.copytree(src_path, full_dest_path, dirs_exist_ok=True)
            else:
                shutil.copy2(src_path, full_dest_path)
            self.call_from_thread(self._refresh_panels_at_path, dest_dir)
            self.run_worker(self._process_copy_queue, thread=True, exclusive=True)
        except Exception as e:
            self.call_from_thread(self.notify, f"Error copying {src_path.name}: {e}", severity="error")
            self.run_worker(self._process_copy_queue, thread=True, exclusive=True)

    # --- Action Methods (bound to keys in on_mount) ---
    def action_toggle_preview(self) -> None:
        """Toggles the visibility of the preview panel."""
        preview_panel = self.query_one(PreviewPanel)
        if preview_panel.styles.display == "none":
            preview_panel.styles.display = "block"
        else:
            preview_panel.styles.display = "none"

    def action_open_file(self) -> None:
        panel = self.active_panel
        if panel and panel.cursor_path and panel.cursor_path.is_file():
            file_path = panel.cursor_path
            try:
                self.notify(f"Opening {file_path.name}...")
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    subprocess.run(["open", file_path], check=True)
                else:
                    subprocess.run(["xdg-open", file_path], check=True, stderr=subprocess.DEVNULL)
            except FileNotFoundError:
                self.notify(f"Error: Command not found.", severity="error")
            except Exception as e:
                self.notify(f"Error opening file: {e}", severity="error")

    def action_find(self) -> None:
        panel = self.active_panel
        if panel:
            self.current_action = "find"
            self.action_target_panel = panel
            self._prompt("Find:")

    def action_add_panel(self) -> None:
        self.current_action = "add_panel"
        self._prompt("Open path:", autocomplete=True)

    def action_close_panel(self) -> None:
        all_panels = list(self.query(FilePanel))
        active = self.active_panel
        if len(all_panels) > 1 and active:
            try:
                current_index = all_panels.index(active)
            except ValueError:
                return
            active.remove()
            remaining_panels = list(self.query(FilePanel))
            focus_index = min(current_index, len(remaining_panels) - 1)
            if remaining_panels:
                remaining_panels[focus_index].focus()

    def action_close_search_panel(self) -> None:
        search_panels = self.query(SearchPanel)
        if search_panels:
            search_panels.last().remove()
            if self.active_panel:
                self.active_panel.focus()


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
            self._prompt("Extract to (blank for current dir):", autocomplete=True,
                         value=str(panel.cursor_path.parent))
        else:
            self.notify("Highlighted item is not a supported archive.", severity="warning")

    def action_delete_selected(self) -> None:
        panel = self.active_panel
        if panel and panel.selected_paths:
            self.current_action = "delete_selected"
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
