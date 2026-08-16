"""The report dates panel: opm-vis-rdates' timeline, as text"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QPlainTextEdit, QWidget


from opm_vis.gui.panels.base import Panel


class RdatesPanel(Panel):
    """
    Report steps with their dates and elapsed time

    Notes
    -----
    The one program that draws nothing, so its "view" is a text area. Its run function returns
    the rendered timeline rather than writing it anywhere - see run_rdates - which is what lets
    the same call serve both the terminal and this panel.
    """

    save_filter = "Text file (*.txt);;CSV file (*.csv);;JSON file (*.json);;All files (*)"

    # --rstep here picks which steps to list, and the listing is the whole point; scrubbing to
    # one at a time would only narrow it to a single row.
    show_step_slider = False

    def _make_view(self) -> QWidget:
        # Kept under a name of its own as well as returned: the base class holds the view as a
        # plain QWidget, and this panel needs the text methods of the real one.
        self._text_view = QPlainTextEdit(self)
        self._text_view.setReadOnly(True)
        # The table format lines its columns up with spaces, so it needs a fixed-width font to
        # line up on screen too.
        self._text_view.setFont(QFont("monospace"))
        return self._text_view

    def text(self) -> str:
        """
        The timeline currently shown

        Returns
        -------
        str
            What the last run produced, or "" before the first one
        """
        return self._text_view.toPlainText()

    def _execute(self, values: dict[str, Any]) -> None:
        self._text_view.setPlainText(self.program.run(**values))

    def _write(self, path: str) -> None:
        # Written from whatever is on screen, so that Save always produces the format that was
        # actually asked for in --format.
        Path(path).write_text(self.text() + "\n", encoding="utf-8")
