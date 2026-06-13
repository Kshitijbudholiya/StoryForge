"""
storyforge.ui.chat_panel
~~~~~~~~~~~~~~~~~~~~~~~~
The main chat area widget — scroll area of message bubbles + input bar.
All state is kept here; the MainWindow feeds it data and reads from it.
"""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore    import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui     import QKeySequence, QShortcut
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QScrollArea, QFrame, QPushButton, QTextEdit,
                              QSizePolicy, QProgressBar)

from storyforge.ui.style  import C_AMBER, C_TEXT_DIM, C_TEXT_MUTED, C_BG, C_PANEL
from storyforge.ui.widgets import MessageBubble, EmptyState


class ChatPanel(QWidget):
    """
    Full chat panel composed of:
      • A header bar (novel title / chapter breadcrumb)
      • A scrollable message list
      • A thin animated progress bar (shown while busy)
      • An input area (multiline input + Send button)
    """

    message_sent = pyqtSignal(str)   # user hit Send with non-empty text

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("chat_area")

        self._history: list[dict] = []   # {role, text, time}
        self._interactive = True

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── header bar ────────────────────────────────────────────────────────
        self._header = self._build_header()
        root.addWidget(self._header)

        # ── progress bar (hidden by default) ─────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)        # indeterminate
        self._progress.setFixedHeight(3)
        self._progress.setTextVisible(False)
        self._progress.hide()
        root.addWidget(self._progress)

        # ── scroll area ───────────────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setObjectName("chat_scroll")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._msg_container = QWidget()
        self._msg_container.setObjectName("chat_area")
        self._msg_layout = QVBoxLayout(self._msg_container)
        self._msg_layout.setContentsMargins(0, 12, 0, 12)
        self._msg_layout.setSpacing(2)
        self._msg_layout.addStretch()

        self._scroll.setWidget(self._msg_container)
        root.addWidget(self._scroll, 1)

        # ── input area ────────────────────────────────────────────────────────
        self._input_area = self._build_input()
        root.addWidget(self._input_area)

        # initial empty state
        self._show_empty(has_novel=False)

    # ── public API ────────────────────────────────────────────────────────────

    def set_context(
        self,
        novel_title: str,
        chapter: int | None = None,
        history: list[dict] | None = None,
    ) -> None:
        """Switch the panel to a different novel/chapter context."""
        self._update_header(novel_title, chapter)
        self._history = list(history or [])
        self._rebuild_messages()
        self._set_input_enabled(self._interactive)

    def add_message(self, role: str, text: str) -> None:
        ts = datetime.now().strftime("%H:%M")
        entry = {"role": role, "text": text, "time": ts}
        self._history.append(entry)
        self._append_bubble(role, text, ts)
        self._scroll_to_bottom()

    def get_history(self) -> list[dict]:
        return list(self._history)

    def set_interactive(self, val: bool) -> None:
        self._interactive = val
        self._set_input_enabled(val)

    def set_busy(self, busy: bool, status: str = "") -> None:
        if busy:
            self._progress.show()
            self._send_btn.setEnabled(False)
            self._input.setEnabled(False)
            self._send_btn.setText("…")
            if status:
                self._set_status(status)
        else:
            self._progress.hide()
            self._send_btn.setText("Send  ▶")
            if self._interactive:
                self._send_btn.setEnabled(True)
                self._input.setEnabled(True)
            self._set_status("")

    def update_status(self, msg: str) -> None:
        self._set_status(msg)

    def clear(self) -> None:
        self._history.clear()
        self._clear_messages()
        self._show_empty(has_novel=False)

    # ── header ────────────────────────────────────────────────────────────────

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet(
            f"background: {C_PANEL}; border-bottom: 1px solid #343A56;"
        )
        bar.setFixedHeight(46)

        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 0, 16, 0)
        h.setSpacing(6)

        self._hdr_icon = QLabel("✦")
        self._hdr_icon.setStyleSheet(
            f"color: {C_AMBER}; font-size: 14px; background: transparent;"
        )

        self._hdr_novel = QLabel("StoryForge")
        self._hdr_novel.setStyleSheet(
            f"color: {C_AMBER}; font-size: 14px; font-weight: 700;"
            f" background: transparent;"
        )

        self._hdr_chevron = QLabel("›")
        self._hdr_chevron.setStyleSheet(
            f"color: #424A6A; font-size: 15px; background: transparent;"
        )
        self._hdr_chevron.hide()

        self._hdr_chapter = QLabel("")
        self._hdr_chapter.setStyleSheet(
            f"color: {C_TEXT_DIM}; font-size: 13px; background: transparent;"
        )
        self._hdr_chapter.hide()

        self._hdr_status = QLabel("")
        self._hdr_status.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent;"
        )

        h.addWidget(self._hdr_icon)
        h.addSpacing(2)
        h.addWidget(self._hdr_novel)
        h.addWidget(self._hdr_chevron)
        h.addWidget(self._hdr_chapter)
        h.addStretch()
        h.addWidget(self._hdr_status)

        return bar

    def _update_header(self, novel_title: str, chapter: int | None) -> None:
        self._hdr_novel.setText(novel_title or "StoryForge")
        if chapter is not None:
            self._hdr_chevron.show()
            self._hdr_chapter.setText(f"Chapter {chapter}")
            self._hdr_chapter.show()
        else:
            self._hdr_chevron.hide()
            self._hdr_chapter.hide()

    def _set_status(self, msg: str) -> None:
        self._hdr_status.setText(msg)

    # ── input ─────────────────────────────────────────────────────────────────

    def _build_input(self) -> QWidget:
        area = QFrame()
        area.setObjectName("input_area")

        h = QHBoxLayout(area)
        h.setContentsMargins(12, 10, 12, 10)
        h.setSpacing(10)

        self._input = QTextEdit()
        self._input.setObjectName("chat_input")
        self._input.setPlaceholderText(
            "Write a chapter instruction or ask a question about the story…"
        )
        self._input.setFixedHeight(46)
        self._input.setAcceptRichText(False)
        self._input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Ctrl+Enter = send
        self._input.installEventFilter(self)

        self._send_btn = QPushButton("Send  ▶")
        self._send_btn.setObjectName("btn_send")
        self._send_btn.setFixedSize(100, 46)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._on_send)

        h.addWidget(self._input, 1)
        h.addWidget(self._send_btn)
        return area

    def eventFilter(self, obj, event) -> bool:
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui  import QKeyEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            ke = event
            # Ctrl+Enter or Ctrl+Return → send
            if (ke.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and
                    ke.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._on_send()
                return True
            # plain Enter → newline (natural for a multiline input)
        return super().eventFilter(obj, event)

    def _on_send(self) -> None:
        text = self._input.toPlainText().strip()
        if not text:
            return
        self._input.clear()
        self.message_sent.emit(text)

    def _set_input_enabled(self, val: bool) -> None:
        self._input.setEnabled(val)
        self._send_btn.setEnabled(val)

    # ── messages ──────────────────────────────────────────────────────────────

    def _rebuild_messages(self) -> None:
        self._clear_messages()
        if not self._history:
            self._show_empty(has_novel=True)
            return
        for msg in self._history:
            self._append_bubble(msg["role"], msg["text"], msg.get("time", ""))
        self._scroll_to_bottom()

    def _append_bubble(self, role: str, text: str, ts: str) -> None:
        # remove empty-state widget if present
        self._remove_empty()
        bubble = MessageBubble(role, text, ts)
        # insert before the trailing stretch
        idx = self._msg_layout.count() - 1
        self._msg_layout.insertWidget(idx, bubble)
        self._scroll_to_bottom()

    def _clear_messages(self) -> None:
        self._remove_empty()
        # remove all MessageBubble children
        while self._msg_layout.count() > 1:  # keep the trailing stretch
            item = self._msg_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_empty(self, has_novel: bool) -> None:
        self._remove_empty()
        self._empty = EmptyState(has_novel=has_novel)
        self._msg_layout.insertWidget(0, self._empty)

    def _remove_empty(self) -> None:
        if hasattr(self, "_empty") and self._empty is not None:
            self._msg_layout.removeWidget(self._empty)
            self._empty.deleteLater()
            self._empty = None

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(
            50,
            lambda: self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            ),
        )
