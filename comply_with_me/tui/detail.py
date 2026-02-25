"""DetailScreen — per-framework file listing."""

from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header

from comply_with_me.downloaders import ServiceDef


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _fmt_dt(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%Y-%m-%d %H:%M")


class DetailScreen(Screen):
    """Shows the per-file inventory for a single framework."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("b", "go_back", "Back"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, svc: ServiceDef, entries: dict) -> None:
        super().__init__()
        self._svc = svc
        self._entries = entries

    def compose(self) -> ComposeResult:
        yield Header()
        yield DataTable(id="detail-table", zebra_stripes=True, cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "cwm"
        self.sub_title = self._svc.label

        table = self.query_one("#detail-table", DataTable)
        table.add_column("File", key="file")
        table.add_column("Size", key="size")
        table.add_column("Last Synced", key="last_sync")

        prefix = self._svc.subdir + "/"
        svc_entries = {k: v for k, v in self._entries.items() if k.startswith(prefix)}

        if not svc_entries:
            table.add_row(
                f"No files synced yet — run: cwm sync {self._svc.key}", "", "",
            )
        else:
            for key in sorted(svc_entries):
                entry = svc_entries[key]
                table.add_row(
                    key[len(prefix):],
                    _human_size(entry["size"]),
                    _fmt_dt(entry["recorded_at"]),
                )

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_quit_app(self) -> None:
        self.app.exit()
