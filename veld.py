import os
import shutil
from pathlib import Path
from typing import Optional, Set

from rich.style import Style
from rich.text import Text
from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import DirectoryTree, Footer, Input, Label, Tree
from textual.widgets._directory_tree import DirEntry
from textual.widgets.tree import TreeNode
from textual_autocomplete import PathAutoComplete


class SelectableDirectoryTree(DirectoryTree):
    """A DirectoryTree that highlights selected nodes."""

    def __init__(
        self, path: str, *, app: "FileExplorerApp", id: str | None = None, name: str | None = None
    ) -> None:
        self.app_ref = app
        super().__init__(path, id=id, name=name)

    def render_label(
        self, node: TreeNode[DirEntry], base_style: Style, style: Style
    ) -> Text:
        """Render a node's label with a custom style if it's selected."""
        rendered_label = super().render_label(node, base_style, style)
        if node.data:
            node_path = node.data.path
            if node_path in self.app_ref.selected_paths:
                rendered_label.style = "b black on green"
        return rendered_label


class FileExplorerApp(App):
    """A file explorer app with multi-file selection and deletion."""

    selected_paths: Set[Path] = set()
    cursor_path: Path | None = None
    current_action: Optional[str] = None

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_selection", "Toggle Selection"),
        ("n", "rename", "Rename"),
        ("d", "create_directory", "New Directory"),
        ("r", "delete_selected", "Delete Selected"),
        ("m", "move_selected", "Move Selected"),
        ("c", "copy_selected", "Copy Selected"),
    ]

    def compose(self) -> ComposeResult:
        """Create the child widgets for the app."""
        home_path = str(Path.home())
        self.directory_tree = SelectableDirectoryTree(
            home_path, app=self, id="dir_tree"
        )
        yield self.directory_tree
        yield Label(id="path_label")
        yield Footer()

    def on_mount(self) -> None:
        """Set the initial cursor path when the app starts."""
        if self.directory_tree.cursor_node and self.directory_tree.cursor_node.data:
            self.cursor_path = self.directory_tree.cursor_node.data.path
            self._update_path_label()

    def _update_path_label(self) -> None:
        """Updates the path label with the current cursor and selection status."""
        cursor_str = str(self.cursor_path) if self.cursor_path else "None"
        label_text = f"Highlighted: {cursor_str}\n"
        label_text += f"Selected: {len(self.selected_paths)} item(s)"
        self.query_one("#path_label", Label).update(label_text)

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[DirEntry]) -> None:
        """Handle the node being highlighted in the DirectoryTree."""
        if event.node and event.node.data:
            self.cursor_path = event.node.data.path
            self._update_path_label()

    def on_key(self, event: Key) -> None:
        """Handle key presses."""
        if event.key == "space":
            event.prevent_default()
            self.action_toggle_selection()

    def action_toggle_selection(self) -> None:
        """Toggle the selection of the currently highlighted path."""
        if self.cursor_path:
            if self.cursor_path in self.selected_paths:
                self.selected_paths.remove(self.cursor_path)
            else:
                self.selected_paths.add(self.cursor_path)

            self.directory_tree.refresh()
            self._update_path_label()

    def action_delete_selected(self) -> None:
        """Prompt for deletion when 'r' is pressed and paths are selected."""
        if self.selected_paths and not self.query(Input):
            self.current_action = "delete"
            input_widget = Input(
                placeholder=f"Delete {len(self.selected_paths)} items? (y/n)"
            )
            self.mount(input_widget)
            self.set_focus(input_widget)

    def _mount_autocomplete_input(self, placeholder: str):
        """Mounts an Input widget and a PathAutoComplete widget to assist it."""
        input_widget = Input(placeholder=placeholder, id="path_input")
        # The PathAutoComplete widget targets the input and provides suggestions.
        # The `only_directories` parameter is removed to fix the TypeError.
        autocomplete = PathAutoComplete(target="#path_input")
        self.mount(input_widget, autocomplete)
        self.set_focus(input_widget)

    def action_move_selected(self) -> None:
        """Prompt for a destination path to move selected items."""
        if self.selected_paths and not self.query("#path_input"):
            self.current_action = "move"
            self._mount_autocomplete_input("Move to:")

    def action_copy_selected(self) -> None:
        """Prompt for a destination path to copy selected items."""
        if self.selected_paths and not self.query("#path_input"):
            self.current_action = "copy"
            self._mount_autocomplete_input("Copy to:")

    def action_rename(self) -> None:
        """Prompt to rename the currently highlighted item."""
        if self.cursor_path and not self.query(Input):
            self.current_action = "rename"
            input_widget = Input(
                value=self.cursor_path.name, placeholder="Rename to:"
            )
            self.mount(input_widget)
            self.set_focus(input_widget)

    def action_create_directory(self) -> None:
        """Prompt for the name of a new directory to create."""
        if not self.query(Input):
            self.current_action = "create_directory"
            input_widget = Input(placeholder="New directory name:")
            self.mount(input_widget)
            self.set_focus(input_widget)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle the submission of any input."""
        user_input = event.value.strip()

        if self.current_action == "delete":
            self._handle_delete(user_input)
        elif self.current_action in ("move", "copy"):
            self._handle_move_copy(user_input)
        elif self.current_action == "rename":
            self._handle_rename(user_input)
        elif self.current_action == "create_directory":
            # Corrected a typo here from the previous version
            self._handle_create_directory(user_input)

        # Cleanup: If the submitted input was for path autocompletion,
        # remove the PathAutoComplete widget as well.
        if event.input.id == "path_input":
            try:
                self.query_one(PathAutoComplete).remove()
            except Exception:
                pass

        if event.input.parent:
            event.input.remove()
        self.current_action = None

    def _handle_delete(self, user_input: str) -> None:
        """Handles the deletion of selected files and directories."""
        if user_input.lower() == "y" and self.selected_paths:
            try:
                num_deleted = len(self.selected_paths)
                for path in list(self.selected_paths):
                    if path.is_dir():
                        shutil.rmtree(path)
                    elif path.is_file():
                        path.unlink()

                self.notify(f"Deleted {num_deleted} items.")
                self.directory_tree.reload()

                self.selected_paths.clear()
                self.cursor_path = None
                self._update_path_label()

            except Exception as e:
                self.notify(f"Error deleting: {e}", severity="error")

        elif user_input.lower() == "n":
            self.notify("Deletion canceled.")
        else:
            self.notify("Invalid input. Please enter 'y' or 'n'.", severity="warning")

    def _handle_move_copy(self, dest_path_str: str) -> None:
        """Handles moving or copying selected files and directories."""
        dest_path = Path(dest_path_str).expanduser()

        if not dest_path.exists() or not dest_path.is_dir():
            self.notify(
                f"Error: Destination '{dest_path}' is not a valid directory.",
                severity="error",
            )
            return

        try:
            num_items = len(self.selected_paths)
            action_past_tense = "moved" if self.current_action == "move" else "copied"

            for src_path in list(self.selected_paths):
                if self.current_action == "move":
                    shutil.move(str(src_path), str(dest_path))
                elif self.current_action == "copy":
                    if src_path.is_dir():
                        shutil.copytree(src_path, dest_path / src_path.name)
                    else:
                        shutil.copy(src_path, dest_path)

            self.notify(f"{num_items} item(s) {action_past_tense} to '{dest_path}'.")
            self.directory_tree.reload()
            self.selected_paths.clear()
            self._update_path_label()

        except Exception as e:
            self.notify(f"Error {self.current_action}ing: {e}", severity="error")

    def _handle_rename(self, new_name: str) -> None:
        """Handles renaming the highlighted file or directory."""
        if not self.cursor_path or not new_name:
            return

        try:
            new_path = self.cursor_path.with_name(new_name)
            if new_path.exists():
                self.notify(f"Error: '{new_name}' already exists.", severity="error")
                return

            self.cursor_path.rename(new_path)
            self.notify(f"Renamed '{self.cursor_path.name}' to '{new_name}'.")

            if self.cursor_path in self.selected_paths:
                self.selected_paths.remove(self.cursor_path)
                self.selected_paths.add(new_path)

            self.cursor_path = new_path
            self.directory_tree.reload()
            self._update_path_label()

        except Exception as e:
            self.notify(f"Error renaming: {e}", severity="error")

    def _handle_create_directory(self, dir_name: str) -> None:
        """Handles creating a new directory."""
        if not dir_name:
            return

        parent_dir = Path(self.directory_tree.path)
        if self.cursor_path:
            parent_dir = (
                self.cursor_path if self.cursor_path.is_dir() else self.cursor_path.parent
            )

        try:
            new_dir_path = parent_dir / dir_name
            if new_dir_path.exists():
                self.notify(
                    f"Error: Directory '{dir_name}' already exists.", severity="error"
                )
                return

            new_dir_path.mkdir()
            self.notify(f"Created directory '{dir_name}'.")
            self.directory_tree.reload()

        except Exception as e:
            self.notify(f"Error creating directory: {e}", severity="error")


if __name__ == "__main__":
    app = FileExplorerApp()
    app.run()
