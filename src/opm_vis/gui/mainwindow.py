"""
The window: one case bar over a tab per program

The case bar is what makes this one GUI rather than four. A case is opened once and handed to
every tab, so switching from the 3D grid to the summary vectors keeps whatever was loaded, and
each tab's PATHS control is filled from the same place.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from opm_vis.cli.registry import PROGRAMS, Program
from opm_vis.gui.case import CaseBundle
from opm_vis.gui.panels import PANELS, Panel
from opm_vis.gui.runner import load_case

_WINDOW_SIZE = (1400, 900)


class MainWindow(QMainWindow):
    """
    The whole application window

    Attributes
    ----------
    panels : list[Panel]
        One per program that could be built; a program whose backend is missing is left out
    bundle : CaseBundle | None
        The case every panel is currently pointed at
    """

    def __init__(self) -> None:
        """Build the case bar, the tabs and the status bar"""
        super().__init__()
        self.setWindowTitle("opm-vis")
        self.resize(*_WINDOW_SIZE)

        self.bundle: CaseBundle | None = None
        self.panels: list[Panel] = []
        self._thread = None
        self._loader = None

        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.addLayout(self._case_bar())

        self._tabs = QTabWidget(body)
        for program in PROGRAMS:
            self._add_panel(program)
        layout.addWidget(self._tabs, 1)

        self.setCentralWidget(body)
        self.statusBar().showMessage(
            "Type a case prefix - a path without its extension, e.g. /runs/CASE - and press "
            "Load."
        )

    def _case_bar(self) -> QHBoxLayout:
        """
        The row naming the case every tab works on

        Returns
        -------
        QHBoxLayout
            Label, path box, browse and load buttons
        """
        self._paths_edit = QLineEdit(self)
        self._paths_edit.setPlaceholderText(
            "Case prefix, e.g. /runs/SPE1CASE1 - add restart runs after it, separated by "
            "spaces"
        )
        self._paths_edit.returnPressed.connect(self.load)

        browse = QPushButton("Browse…", self)
        browse.clicked.connect(self.browse)
        load = QPushButton("Load", self)
        load.clicked.connect(self.load)

        row = QHBoxLayout()
        row.addWidget(QLabel("Case:", self))
        row.addWidget(self._paths_edit, 1)
        row.addWidget(browse)
        row.addWidget(load)
        return row

    def _add_panel(self, program: Program) -> None:
        """
        Add the tab for one program, if it can be built

        Parameters
        ----------
        program : Program
            Entry from opm_vis.cli.registry

        Notes
        -----
        A panel whose backend is not installed - the 3D one needs pyvista and pyvistaqt - is
        reported as a disabled tab rather than bringing the window down, so the rest stays
        usable on a matplotlib-only install.
        """
        panel_class = PANELS.get(program.script)
        if panel_class is None:
            return

        try:
            panel = panel_class(program, self)
        except ImportError as exc:
            placeholder = QLabel(
                f"{program.script} needs an optional dependency that is not installed:\n\n"
                f"{exc}\n\nInstall it with:  pip install 'opm-vis[gui]'",
                self,
            )
            self._tabs.addTab(placeholder, f"{program.label} (unavailable)")
            self._tabs.setTabEnabled(self._tabs.count() - 1, False)
            return

        panel.status.connect(self.statusBar().showMessage)
        self.panels.append(panel)
        self._tabs.addTab(panel, program.label)

    def browse(self) -> None:
        """
        Pick a case file and reduce it to the prefix the readers want

        Notes
        -----
        Every reader in opm_vis takes a filename prefix and globs for the extensions itself,
        so the chosen file's extension is dropped. Picking a file rather than a directory is
        what lets two cases share one directory, which SPE1CASE2 and its restart do.
        """
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Pick any file of the case",
            "",
            "Simulation output (*.EGRID *.UNRST *.SMSPEC *.INIT *.UNSMRY);;All files (*)",
        )
        if not path:
            return

        prefix = path.rsplit(".", 1)[0]
        self._paths_edit.setText(prefix)
        self.load()

    def set_case_paths(self, paths: list[str]) -> None:
        """
        Put a case into the case bar without opening it yet

        Parameters
        ----------
        paths : list[str]
            Filename prefixes: the main run first, any restart runs after it
        """
        self._paths_edit.setText(" ".join(paths))

    def load(self) -> None:
        """Open the case named in the case bar, in the background"""
        paths = [part for part in self._paths_edit.text().split() if part]
        if not paths:
            self.statusBar().showMessage("Type a case prefix first.")
            return

        self.statusBar().showMessage(f"Opening {paths[0]}…")
        self._thread, self._loader = load_case(paths, self._case_loaded, self._case_failed)

    def _case_loaded(self, bundle: CaseBundle) -> None:
        """
        Point every panel at the case that has just been opened

        Parameters
        ----------
        bundle : CaseBundle
            The case, already read
        """
        self.bundle = bundle
        for panel in self.panels:
            panel.set_case(bundle)

        steps = bundle.report_steps()
        summary = len(bundle.summary_keywords())
        self.statusBar().showMessage(
            f"{bundle.paths[0]}: {len(steps)} report steps, "
            f"{len(bundle.grid_keywords())} grid keywords, {summary} summary vectors"
        )

    def _case_failed(self, message: str) -> None:
        """
        Report a case that could not be opened

        Parameters
        ----------
        message : str
            What went wrong
        """
        self.statusBar().showMessage(f"Could not open the case: {message}")
