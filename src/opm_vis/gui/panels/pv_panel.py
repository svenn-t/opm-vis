"""The 3D grid panel: opm-vis-pv, rendered into an embedded VTK widget"""
from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QVBoxLayout, QWidget

from opm_vis.gui.panels.base import Panel


class PvPanel(Panel):
    """
    The grid in 3D, rendered with the PyVista backend

    Notes
    -----
    The render window is a pyvistaqt.QtInteractor, which is a pv.Plotter subclass, so it can
    be handed to run_pv as its plotter and everything the command line program does - slices,
    wells, glyphs, thresholds, clips - lands in this widget instead of a window of its own.

    It is made once and reused: building the hexahedral mesh from an EGRID is by far the
    slowest part of a plot, and a fresh interactor per run would rebuild the whole scene. The
    previous run's actors are cleared instead, which is what GridPlotter.close does for a
    render window it does not own.
    """

    def _make_view(self) -> QWidget:
        # Imported here rather than at module scope so that a missing 3D extra costs only this
        # tab, leaving the matplotlib, summary and report-date panels usable.
        from pyvistaqt import QtInteractor  # noqa: PLC0415

        view = QWidget(self)
        layout = QVBoxLayout(view)
        layout.setContentsMargins(0, 0, 0, 0)

        self._interactor = QtInteractor(view)
        layout.addWidget(self._interactor)

        self._plotter = None
        return view

    def _execute(self, values: dict[str, Any]) -> None:
        # The previous scene is taken off the interactor before the next one is built on it;
        # close() on a plotter that does not own its render window clears rather than destroys.
        if self._plotter is not None:
            self._plotter.close()

        self._plotter = self.program.run(**values, plotter=self._interactor)
        self._interactor.render()

    def _write(self, path: str) -> None:
        if self._plotter is None:
            raise RuntimeError("Nothing has been rendered yet; press Run first.")

        self._plotter.screenshot(path)

    def closeEvent(self, event) -> None:
        """
        Shut the render window down with the panel

        Parameters
        ----------
        event : QCloseEvent
            The close event

        Notes
        -----
        A QtInteractor holds a VTK render window, which has to be closed explicitly or the
        process can hang on exit waiting for it.
        """
        self._interactor.close()
        super().closeEvent(event)
