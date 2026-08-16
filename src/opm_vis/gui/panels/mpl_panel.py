"""The matplotlib grid panel: opm-vis-mpl, drawn into an embedded canvas"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QVBoxLayout, QWidget
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from opm_vis.gui.panels.base import Panel


class MplCanvas(QWidget):
    """
    A matplotlib canvas with its navigation toolbar

    Attributes
    ----------
    figure : Figure
        The figure drawn into. Made here rather than by pyplot, so that it belongs to this
        widget and survives the plotting code's own show()/close() - see the fig argument of
        SummaryPlot and the slice collections.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Build the canvas

        Parameters
        ----------
        parent : QWidget | None, optional
            Parent widget, by default None
        """
        super().__init__(parent)
        self.figure = Figure()
        self.canvas = FigureCanvasQTAgg(self.figure)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas, 1)

    def redraw(self) -> None:
        """Show whatever has just been drawn on the figure"""
        self.canvas.draw_idle()


class MplPanel(Panel):
    """
    One grid slice, drawn with the matplotlib backend

    Notes
    -----
    run_mpl is given this panel's figure, so it draws here instead of opening a pyplot window,
    and its show() becomes a redraw of this canvas. Everything else about the run - the option
    checks, the report step handling, the file names - is the command line program's own.
    """

    def _make_view(self) -> QWidget:
        self._canvas = MplCanvas(self)
        return self._canvas

    def _execute(self, values: dict[str, Any]) -> None:
        self._collection = self.program.run(**values, fig=self._canvas.figure)
        self._canvas.redraw()

    def _write(self, path: str) -> None:
        # Saved straight off the figure rather than by running again: the case has already
        # been read, and re-running would only risk drawing something subtly different.
        self._canvas.figure.savefig(path)
