"""The summary panel: opm-vis-sum's time series, drawn into an embedded canvas"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QPushButton, QWidget

from opm_vis.gui.panels.base import Panel
from opm_vis.gui.panels.mpl_panel import MplCanvas


class SummaryPanel(Panel):
    """
    Summary vectors over time

    Notes
    -----
    Carries one control the other panels do not: --export writes the plotted numbers rather
    than a picture of them, so it gets a button of its own beside Save rather than a place on
    the form. That is why "export" is listed as shell_only for this program - see
    opm_vis.cli.registry.
    """

    def _make_view(self) -> QWidget:
        self._canvas = MplCanvas(self)
        return self._canvas

    def __init__(self, program, parent: QWidget | None = None) -> None:
        """
        Build the panel and add its Export button

        Parameters
        ----------
        program : Program
            Entry from opm_vis.cli.registry
        parent : QWidget | None, optional
            Parent widget, by default None
        """
        super().__init__(program, parent)
        self._plot = None
        self._selected: list[str] = []

        self._export_button = QPushButton("Export CSV…", self)
        self._export_button.setToolTip(
            "Write the plotted numbers as CSV, the same data --export produces."
        )
        self._export_button.clicked.connect(self.export)

        # Placed next to Save, at the end of the button row the base class built.
        self.button_row.addWidget(self._export_button)

    def _execute(self, values: dict[str, Any]) -> None:
        self._plot, self._selected = self.program.run(**values, fig=self._canvas.figure)
        self._canvas.redraw()

    def _write(self, path: str) -> None:
        self._canvas.figure.savefig(path)

    def export(self) -> None:
        """
        Write the plotted data as CSV

        Notes
        -----
        Uses the plot returned by the last run rather than reading the case again, which is
        why run_sum hands it back together with the keywords it drew.
        """
        if self._plot is None:
            self.status.emit("Run the plot first, then export the data it drew.")
            return

        from PySide6.QtWidgets import QFileDialog  # noqa: PLC0415

        path, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "", "CSV file (*.csv);;All files (*)"
        )
        if not path:
            return

        x_axis = self.form.values().get("x_axis", "date")
        Path(path).write_text(
            self._plot.export_csv(self._selected, x_axis=x_axis) + "\n", encoding="utf-8"
        )
        self.status.emit(f"Exported to {path}")
