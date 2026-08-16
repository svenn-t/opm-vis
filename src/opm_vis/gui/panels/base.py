"""
The shape every panel shares: generated form, view, Run/Save, and the command line preview
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from opm_vis.cli.registry import Program
from opm_vis.gui.case import CaseBundle
from opm_vis.gui.form import OptionForm
from opm_vis.gui.hints import hint_for
from opm_vis.gui.runner import busy, error_message

# Roughly a third of the window for the controls, the rest for the plot. The starting widths
# are set as well as the stretch factors: a splitter otherwise divides the space evenly at
# first, which leaves the form too narrow for a label, its control and the "add" picker beside
# it. Both are only a starting point - the splitter can be dragged.
_FORM_STRETCH = 1
_VIEW_STRETCH = 2
_FORM_WIDTH = 430
_VIEW_WIDTH = 970


class Panel(QWidget):
    """
    One program's controls beside the view it draws into

    Attributes
    ----------
    status : Signal
        Emitted with a message to show in the window's status bar
    program : Program
        The program this panel drives
    form : OptionForm
        Its generated controls
    bundle : CaseBundle | None
        The case currently loaded, or None before one is
    """

    status = Signal(str)

    #: Filter for the save dialog; overridden by panels saving something other than an image.
    save_filter = "PNG image (*.png);;All files (*)"

    #: Whether dragging through the report steps makes sense here. Set False by a panel that
    #: has --rstep but does not show one step at a time; a panel without --rstep at all - the
    #: summary one - needs no flag, since there is nothing for the slider to write to.
    show_step_slider = True

    def __init__(self, program: Program, parent: QWidget | None = None) -> None:
        """
        Build the panel for a program

        Parameters
        ----------
        program : Program
            Entry from opm_vis.cli.registry
        parent : QWidget | None, optional
            Parent widget, by default None
        """
        super().__init__(parent)
        self.program = program
        self.bundle: CaseBundle | None = None

        self.form = OptionForm(program.command, self)
        self.view = self._make_view()

        split = QSplitter(Qt.Orientation.Horizontal, self)
        split.addWidget(self.form)
        split.addWidget(self.view)
        split.setStretchFactor(0, _FORM_STRETCH)
        split.setStretchFactor(1, _VIEW_STRETCH)
        split.setSizes([_FORM_WIDTH, _VIEW_WIDTH])

        self._step_row, self._step_slider, self._step_label = self._step_widgets()

        self._preview = QLineEdit(self)
        self._preview.setReadOnly(True)
        self._preview.setToolTip(
            "The command line that reproduces this panel. Copy it to run the same plot in a "
            "terminal."
        )

        self._run_button = QPushButton("Run", self)
        self._run_button.clicked.connect(self.run)
        self._save_button = QPushButton("Save…", self)
        self._save_button.clicked.connect(self.save)

        # Kept as an attribute so a panel with an action of its own - the summary one has
        # Export CSV - can add a button to it without digging through the layout.
        self.button_row = QHBoxLayout()
        self.button_row.addWidget(QLabel("Command:", self))
        self.button_row.addWidget(self._preview, 1)
        self.button_row.addWidget(self._run_button)
        self.button_row.addWidget(self._save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addLayout(self._step_row)
        layout.addLayout(self.button_row)

        self.form.changed.connect(self._refresh_preview)
        self._refresh_preview()

    def _step_widgets(self) -> tuple[QHBoxLayout, QSlider, QLabel]:
        """
        The report step scrubber shown under the view

        Returns
        -------
        tuple[QHBoxLayout, QSlider, QLabel]
            Its row, the slider itself and the label reading out the current step

        Notes
        -----
        The slider stands where an animation would in a command line run: dragging it replots
        at that step, which is a better way to look through a run than a fixed-rate animation
        and needs no second event loop. Writing the step into the --rstep control rather than
        passing it separately keeps the command line preview - and so the run - honest.

        Hidden until a case with report steps is loaded, and left out entirely for a panel
        that has no --rstep to write to.
        """
        row = QHBoxLayout()
        label = QLabel("Report step:", self)
        slider = QSlider(Qt.Orientation.Horizontal, self)
        readout = QLabel("", self)

        slider.setEnabled(False)
        # Replotted when the drag ends rather than on every pixel: a step of a large grid can
        # take a moment to read, and rendering each one along the way would make the slider
        # unusable.
        slider.sliderReleased.connect(self._step_chosen)
        slider.valueChanged.connect(self._show_step)

        row.addWidget(label)
        row.addWidget(slider, 1)
        row.addWidget(readout)

        for widget in (label, slider, readout):
            widget.setVisible(False)

        self._step_widgets_all = (label, slider, readout)
        return row, slider, readout

    def _steps(self) -> list[int]:
        """
        Report steps the slider moves over

        Returns
        -------
        list[int]
            The case's steps, or empty when there is no case, none to show, or no --rstep on
            this command to write them into
        """
        if self.bundle is None or "rstep" not in self.form.controls:
            return []

        return self.bundle.report_steps()

    def _show_step(self, index: int) -> None:
        """
        Read the slider's position out beside it

        Parameters
        ----------
        index : int
            Position of the slider, an index into the case's report steps
        """
        steps = self._steps()
        if 0 <= index < len(steps):
            self._step_label.setText(f"{steps[index]} of {steps[-1]}")

    def _step_chosen(self) -> None:
        """Write the chosen step into --rstep and replot"""
        steps = self._steps()
        index = self._step_slider.value()
        if not 0 <= index < len(steps):
            return

        self.form.set_value("rstep", str(steps[index]))
        self.run()

    def _setup_step_slider(self) -> None:
        """Fit the slider to the loaded case, or hide it if there is nothing to scrub"""
        steps = self._steps()
        usable = self.show_step_slider and len(steps) > 1

        for widget in self._step_widgets_all:
            widget.setVisible(usable)

        self._step_slider.setEnabled(usable)
        if usable:
            self._step_slider.setRange(0, len(steps) - 1)
            self._show_step(self._step_slider.value())

    def _make_view(self) -> QWidget:
        """
        The widget this panel draws into

        Returns
        -------
        QWidget
            A canvas, a render window or a text area, depending on the program
        """
        raise NotImplementedError

    def _execute(self, values: dict[str, Any]) -> None:
        """
        Run the program and put the result in the view

        Parameters
        ----------
        values : dict[str, Any]
            The options to run with, keyed by click parameter name and already narrowed to
            the ones the run function takes
        """
        raise NotImplementedError

    def _write(self, path: str) -> None:
        """
        Write the current result to a file

        Parameters
        ----------
        path : str
            File chosen in the save dialog
        """
        raise NotImplementedError

    def run_values(self) -> dict[str, Any]:
        """
        What to pass the program's run function

        Returns
        -------
        dict[str, Any]
            The form's values, narrowed to the parameters the run function accepts - the
            others are the click shell's own, e.g. --export, and are served by this panel's
            buttons instead
        """
        accepted = self.program.option_names()
        return {
            name: value
            for name, value in self.form.values().items()
            if name in accepted
        }

    def run(self) -> None:
        """
        Draw, reporting anything that goes wrong in the status bar

        Notes
        -----
        Every failure is caught on purpose. The command line programs raise click.UsageError
        for a combination of options that does not make sense, and a GUI that closed itself
        over a mistyped report step would be unusable; see runner.error_message.
        """
        if not self._require_case():
            return

        try:
            with busy():
                self._execute(self.run_values())
        # pylint: disable=broad-exception-caught
        except Exception as exc:
            self.status.emit(error_message(exc))
            return

        self.status.emit(f"{self.program.script}: done")

    def save(self) -> None:
        """Ask for a file and write the current result to it"""
        if not self._require_case():
            return

        path, _ = QFileDialog.getSaveFileName(self, "Save", "", self.save_filter)
        if not path:
            return

        try:
            with busy():
                self._write(path)
        # pylint: disable=broad-exception-caught
        except Exception as exc:
            self.status.emit(error_message(exc))
            return

        self.status.emit(f"Written to {path}")

    def _require_case(self) -> bool:
        """
        Whether a case has been loaded yet

        Returns
        -------
        bool
            True if there is one; otherwise says so in the status bar and returns False
        """
        if self.bundle is None:
            self.status.emit("Load a case first: type a path in the case bar and press Load.")
            return False

        return True

    def set_case(self, bundle: CaseBundle) -> None:
        """
        Point the panel at a newly loaded case

        Parameters
        ----------
        bundle : CaseBundle
            The case, already read

        Notes
        -----
        The paths go into the hidden PATHS control rather than being held separately, so that
        they reach the run function and the command line preview the same way every other
        option does.
        """
        self.bundle = bundle
        self.form.set_value("paths", tuple(bundle.paths))

        # Every control asking for values gets them, whichever source it named; a source this
        # case cannot supply simply yields an empty list.
        for source in {hint_for(name).choices_from for name in self.form.controls}:
            if source:
                self.form.offer_choices(source, bundle.choices(source))

        self._setup_step_slider()
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        """Rewrite the command line preview from the form"""
        self._preview.setText(self.form.command_line(self.program.script))
