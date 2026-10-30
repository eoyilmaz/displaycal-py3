"""Reusable file drag-and-drop support for the Qt UI.

This is the Qt counterpart of the legacy :class:`DisplayCAL.wx_addons.FileDrop`
/ :class:`DisplayCAL.wx_windows.FileDrop`. Instead of subclassing a drop target
per widget, a :class:`FileDropTarget` is an event filter you install on any
widget, mapping file *suffixes* to handler callables.

Improvements over the wx version:

* Matching is by suffix (``str.endswith``), longest first, so multi-part
  extensions such as ``.vrml.gz`` are handled correctly (the wx version relied
  on :func:`os.path.splitext` and silently failed to match those).
* No global event/timer juggling; dispatch happens directly in the drop event.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Callable

from qtpy.QtCore import QEvent, QObject

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

#: A drop handler receives the dropped file path.
DropHandler = Callable[[str], None]


class FileDropTarget(QObject):
    """Event filter that routes dropped files to per-suffix handlers.

    Args:
        drophandlers (dict[str, DropHandler] | None): Mapping of lowercased file
            suffix (e.g. ``".vrml"``) to a callable invoked with each matching
            dropped path.
        unsupported_handler (Callable[[list[str]], None] | None): Optional
            callable invoked (with the list of unmatched paths) when none of the
            dropped files are supported.
        parent (QObject | None): Optional Qt parent for ownership.
    """

    def __init__(
        self,
        drophandlers: dict[str, DropHandler] | None = None,
        unsupported_handler: Callable[[list[str]], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.drophandlers: dict[str, DropHandler] = drophandlers or {}
        self.unsupported_handler = unsupported_handler

    def install_on(self, widget: QWidget) -> None:
        """Enable drops on ``widget`` and route them through this target.

        Args:
            widget (QWidget): The widget to accept dropped files on.
        """
        widget.setAcceptDrops(True)
        widget.installEventFilter(self)

    def _match(self, path: str) -> DropHandler | None:
        """Return the handler for ``path`` (longest matching suffix wins).

        Args:
            path (str): The dropped file path to match.

        Returns:
            DropHandler | None: The handler whose suffix matches ``path``, or
            ``None`` if none do.
        """
        lower = path.lower()
        for suffix in sorted(self.drophandlers, key=len, reverse=True):
            if lower.endswith(suffix):
                return self.drophandlers[suffix]
        return None

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Accept file drags and dispatch dropped paths to handlers.

        Args:
            obj (QObject): The object the event was sent to.
            event (QEvent): The Qt event being filtered.

        Returns:
            bool: True if the drag/drop event was handled here, otherwise the
            result of the base-class filter.
        """
        etype = event.type()
        if etype in (QEvent.DragEnter, QEvent.DragMove):
            mime = event.mimeData()
            if mime.hasUrls() and any(
                self._match(url.toLocalFile())
                for url in mime.urls()
                if url.isLocalFile()
            ):
                event.acceptProposedAction()
                return True
            return False
        if etype == QEvent.Drop:
            return self._handle_drop(event)
        return super().eventFilter(obj, event)

    def _handle_drop(self, event: QEvent) -> bool:
        """Dispatch a drop event's local files.

        Args:
            event (QEvent): The Qt drop event.

        Returns:
            bool: True if a matching or unsupported-handler dispatch occurred.
        """
        # toLocalFile() uses forward slashes on Windows too, see file_dialog
        paths = [
            os.path.normpath(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        matched = [(path, handler) for path in paths if (handler := self._match(path))]
        if matched:
            event.acceptProposedAction()
            for path, handler in matched:
                handler(path)
            return True
        if self.unsupported_handler and paths:
            event.acceptProposedAction()
            self.unsupported_handler(paths)
            return True
        return False

    # Backwards-compatible alias for code paths (e.g. macOS file-open) that call
    # the wx-era entry point with explicit paths.
    def drop_files(self, paths: list[str]) -> None:
        """Dispatch ``paths`` as if they had been dropped on the widget.

        Args:
            paths (list[str]): File paths to dispatch to their matching handlers.
        """
        unmatched = []
        for path in paths:
            handler = self._match(path)
            if handler:
                handler(path)
            else:
                unmatched.append(path)
        if unmatched and self.unsupported_handler:
            self.unsupported_handler(unmatched)
