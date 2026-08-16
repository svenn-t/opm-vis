"""
The generated form for one command: every option, grouped, with a live command line preview

OptionForm is the whole GUI-facing description of a program's options. It builds itself from
the command's own parameters, so it needs no per-program code, and it hands back a plain dict
keyed by click parameter name - exactly what that program's run_* function takes.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import click
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from opm_vis.gui.hints import GROUP_ORDER, OTHER, hint_for
from opm_vis.gui.introspect import ParamSpec, command_line, describe
from opm_vis.gui.widgets import Control, build_control


class OptionForm(QScrollArea):
    """
    Controls for every option of one click command

    Attributes
    ----------
    changed : Signal
        Emitted whenever any control changes, so the window can refresh its preview
    specs : list[ParamSpec]
        Every parameter of the command, hidden ones included
    controls : dict[str, Control]
        Control per click parameter name, hidden ones included - a hidden control still holds
        a value, it just has no place on the form
    """

    changed = Signal()

    def __init__(self, command: click.Command, parent: QWidget | None = None) -> None:
        """
        Build a form for a command

        Parameters
        ----------
        command : click.Command
            One of the opm-vis commands
        parent : QWidget | None, optional
            Parent widget, by default None
        """
        super().__init__(parent)
        self.specs = describe(command)
        self.controls: dict[str, Control] = {}

        self._body = QWidget(self)
        body = self._body
        layout = QVBoxLayout(body)

        for group, specs in self._grouped():
            box = self._group_box(group, specs)
            if box is not None:
                layout.addWidget(box)

        layout.addStretch(1)
        self.setWidget(body)
        self.setWidgetResizable(True)
        self._wire_enabling()

    def _grouped(self) -> list[tuple[str, list[ParamSpec]]]:
        """
        The parameters, split into their groups and ordered as GROUP_ORDER says

        Returns
        -------
        list[tuple[str, list[ParamSpec]]]
            (group name, its parameters in declaration order), empty groups left out

        Notes
        -----
        A parameter whose hint names a group nobody listed still has to go somewhere, so it
        joins the unhinted ones in "More options" rather than vanishing.
        """
        buckets: dict[str, list[ParamSpec]] = {group: [] for group in GROUP_ORDER}

        for spec in self.specs:
            group = hint_for(spec.name).group
            buckets.setdefault(group if group in buckets else OTHER, []).append(spec)

        return [(group, buckets[group]) for group in GROUP_ORDER if buckets[group]]

    def _group_box(self, group: str, specs: Sequence[ParamSpec]) -> QGroupBox | None:
        """
        One group box, with a labelled row per visible option

        Parameters
        ----------
        group : str
            Group name, shown as the box's title
        specs : Sequence[ParamSpec]
            Parameters belonging to it

        Returns
        -------
        QGroupBox | None
            The box, or None when every parameter in the group is hidden - PATHS and the file
            options are, so their groups would otherwise be empty boxes

        Notes
        -----
        The controls are built first and the box only afterwards, for the groups that turn out
        to have anything to show. Building the box first and discarding it later is what leaves
        a stray title painted over the form, since a widget parented to the scroll area is
        shown from the moment it exists, whatever is later done with it.
        """
        visible = [spec for spec in specs if not hint_for(spec.name).hidden]

        # A hidden control still has to exist, and still has to have a home: it carries the
        # value the window sets on it - the case bar's paths, the save button's filename - into
        # the run function. It is parented to the form body and never laid out.
        for spec in specs:
            if hint_for(spec.name).hidden:
                self._add_control(spec, self._body).setVisible(False)

        if not visible:
            return None

        box = QGroupBox(group, self._body)
        layout = QFormLayout(box)
        for spec in visible:
            layout.addRow(f"{spec.label}:", self._add_control(spec, box))

        return box

    def _add_control(self, spec: ParamSpec, parent: QWidget) -> Control:
        """
        Build one control and register it

        Parameters
        ----------
        spec : ParamSpec
            Description of the parameter
        parent : QWidget
            Widget to parent the control to

        Returns
        -------
        Control
            The control, already connected to this form's changed signal
        """
        hint = hint_for(spec.name)
        control = (
            hint.widget(spec, parent) if hint.widget is not None else build_control(spec, parent)
        )
        control.changed.connect(self.changed)
        self.controls[spec.name] = control
        return control

    def _wire_enabling(self) -> None:
        """
        Grey out each control whose governing option is switched off

        Notes
        -----
        Purely a hint to the reader: the command line rejects the same combinations itself,
        and greying out is never the only thing stopping an invalid run. An enabled_by naming
        a parameter this command does not have - the table is shared by all four - is simply
        skipped.
        """
        for name, control in self.controls.items():
            governor_name = hint_for(name).enabled_by
            governor = self.controls.get(governor_name) if governor_name else None
            if governor is None:
                continue

            governor.changed.connect(self._refresh_enabled)

        self._refresh_enabled()

    def _refresh_enabled(self) -> None:
        """Apply every enabled_by rule to its control"""
        for name, control in self.controls.items():
            governor_name = hint_for(name).enabled_by
            governor = self.controls.get(governor_name) if governor_name else None
            if governor is None:
                continue

            control.setEnabled(bool(governor.value()))

    def values(self) -> dict[str, Any]:
        """
        What every control currently holds

        Returns
        -------
        dict[str, Any]
            Value per click parameter name, ready to pass to the program's run function as
            keyword arguments
        """
        return {name: control.value() for name, control in self.controls.items()}

    def set_value(self, name: str, value: Any) -> None:
        """
        Set one control, if the command has it

        Parameters
        ----------
        name : str
            Click parameter name
        value : Any
            Value in the parameter's own type

        Notes
        -----
        Silently ignores a name this command does not have, so that the window can push a
        shared value - the case paths, a report step picked on the slider - at every tab
        without checking which of them takes it.
        """
        control = self.controls.get(name)
        if control is not None:
            control.set_value(value)

    def offer_choices(self, source: str, choices: Sequence[str]) -> None:
        """
        Fill in the values a loaded case can supply

        Parameters
        ----------
        source : str
            Name of the value list, one of the constants in gui.hints
        choices : Sequence[str]
            Values to offer

        Notes
        -----
        Pushed at every control whose hint asks for this source, so a case being loaded fills
        the keyword drop-downs of whichever tabs want them without the window knowing which.
        """
        for name, control in self.controls.items():
            if hint_for(name).choices_from == source:
                control.set_choices(choices)

    def command_line(self, script: str) -> str:
        """
        The command line reproducing the current form

        Parameters
        ----------
        script : str
            Name the program is installed as, e.g. "opm-vis-pv"

        Returns
        -------
        str
            A command that can be pasted into a terminal; options left at their defaults are
            left off it
        """
        return command_line(script, self.specs, self.values())
