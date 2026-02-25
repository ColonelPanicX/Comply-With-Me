"""Custom Textual messages for thread-safe worker → UI communication."""

from __future__ import annotations

from textual.message import Message

from comply_with_me.downloaders.base import DownloadResult


class SyncProgress(Message):
    """Posted by the sync worker when a framework sync begins."""

    def __init__(self, key: str) -> None:
        super().__init__()
        self.key = key


class SyncComplete(Message):
    """Posted by the sync worker when a framework sync finishes successfully."""

    def __init__(self, key: str, result: DownloadResult) -> None:
        super().__init__()
        self.key = key
        self.result = result


class SyncError(Message):
    """Posted by the sync worker when a framework sync raises an unhandled exception."""

    def __init__(self, key: str, error: str) -> None:
        super().__init__()
        self.key = key
        self.error = error
