"""
Controls for the parameters of a click command

One Control class per Kind, and a registry mapping the two, so that build_control can serve
any parameter of any opm-vis command - including one added after this file was last touched.
The fallback for an unrecognised shape is a text box, which every click type can at least be
typed into, so a new option is never silently missing from the window.

Every control reports its value as the click parameter's own Python type, ready to hand
straight to a run_* function, and reports None for "not given at all" so that an option left
alone keeps whatever default the command line would have used.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from opm_vis.gui.introspect import Kind, ParamSpec

# Shown in a number box standing at its lowest value when the option has no default of its
# own, i.e. when "not given" is a state the command line distinguishes - --calc-count and
# --glyph-factor both do. Qt draws this text in place of the number, which is the standard way
# to give a spin box an empty state. It must not be the empty string: Qt reads that as "no
# special value at all" and would show the sentinel number itself.
_UNSET_TEXT = "—"

# The blank first entry of a drop-down whose option can be left out. A combo box has no such
# rule, so this one really is empty.
_UNSET_CHOICE = ""

# How far below the real minimum the "unset" position of a number box sits.
_UNSET_STEP = 1

# Separator between the values of a repeatable option, e.g. -K FOPR -K FGOR typed as
# "FOPR, FGOR". Chosen over whitespace because a summary vector never contains a comma but
# --title-style free text might contain a space.
_MULTI_SEPARATOR = ","


class Control(QWidget):
    """
    Base class for the control of one parameter

    Attributes
    ----------
    changed : Signal
        Emitted whenever the value changes, so a form can refresh its command line preview
    spec : ParamSpec
        The parameter this control stands for
    """

    changed = Signal()

    def __init__(self, spec: ParamSpec, parent: QWidget | None = None) -> None:
        """
        Build the control and set it to the parameter's default

        Parameters
        ----------
        spec : ParamSpec
            Description of the parameter
        parent : QWidget | None, optional
            Parent widget, by default None
        """
        super().__init__(parent)
        self.spec = spec
        self._build()
        if spec.help:
            self.setToolTip(spec.help)
        self.set_value(spec.default)

    def _build(self) -> None:
        """Create the inner widgets; overridden by each subclass"""
        raise NotImplementedError

    def value(self) -> Any:
        """
        Current value, in the type the click parameter uses

        Returns
        -------
        Any
            The value, or None when the option is not given at all
        """
        raise NotImplementedError

    def set_value(self, value: Any) -> None:
        """
        Set the control to a value

        Parameters
        ----------
        value : Any
            Value in the click parameter's own type, or None for "not given"
        """
        raise NotImplementedError

    def set_choices(self, choices: Sequence[str]) -> None:
        """
        Offer a set of values to pick from, where the control can show one

        Parameters
        ----------
        choices : Sequence[str]
            Values read from the loaded case, e.g. its restart keywords or summary vectors

        Notes
        -----
        Does nothing by default. A case's keywords are only known once it has been opened, so
        the window pushes them into every control and lets those that can use them - the
        repeatable ones and the editable drop-downs - do so, rather than keeping a list of
        which controls those are.
        """

    def _row(self) -> QHBoxLayout:
        """
        A tight horizontal layout for the inner widgets

        Returns
        -------
        QHBoxLayout
            Layout with no margins, so a control lines up with its label in a form
        """
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        return layout


class FlagControl(Control):
    """A switch, for is_flag options and for --x/--no-x pairs alike"""

    def _build(self) -> None:
        self._box = QCheckBox(self)
        self._box.toggled.connect(self.changed)
        self._row().addWidget(self._box)

    def value(self) -> bool:
        return self._box.isChecked()

    def set_value(self, value: Any) -> None:
        self._box.setChecked(bool(value))


class ChoiceControl(Control):
    """A drop-down, for click.Choice options"""

    def _build(self) -> None:
        self._combo = QComboBox(self)

        # An option whose default is None can be left unset, so the list needs a way to say
        # so; one that always has a value - --view, --diff-kind - does not, and an empty entry
        # would only be a way to make it invalid.
        self._nullable = self.spec.default is None
        if self._nullable:
            self._combo.addItem(_UNSET_CHOICE, userData=None)
        for choice in self.spec.choices:
            self._combo.addItem(choice, userData=choice)

        self._combo.currentIndexChanged.connect(self.changed)
        self._row().addWidget(self._combo)

    def value(self) -> str | None:
        return self._combo.currentData()

    def set_value(self, value: Any) -> None:
        index = self._combo.findData(value)
        self._combo.setCurrentIndex(max(index, 0))


class _NumberControl(Control):
    """
    Shared behaviour of the whole-number and decimal controls

    Notes
    -----
    A parameter with no default of its own needs to be able to say "not given", which a spin
    box has no natural state for. Qt's special value text covers exactly this: one step below
    the real minimum is reserved as an empty position and drawn blank.
    """

    def _make_box(self) -> QSpinBox | QDoubleSpinBox:
        """
        The spin box itself; overridden to pick the whole-number or decimal one

        Returns
        -------
        QSpinBox | QDoubleSpinBox
            An unconfigured box
        """
        raise NotImplementedError

    def _cast(self, value: float) -> Any:
        """
        Convert the box's number to the click parameter's own type

        Parameters
        ----------
        value : float
            Raw value from the box

        Returns
        -------
        Any
            int or float, matching the parameter
        """
        raise NotImplementedError

    def _limits(self) -> tuple[float, float]:
        """
        Range for the box, from the parameter's own bounds where it declares any

        Returns
        -------
        tuple[float, float]
            (minimum, maximum). Where click sets no bound, a wide one stands in: a spin box
            must have limits, and these are far outside any grid index, report step or scale
            factor a case could have.
        """
        minimum = self.spec.minimum if self.spec.minimum is not None else -1e9
        maximum = self.spec.maximum if self.spec.maximum is not None else 1e9
        return minimum, maximum

    def _build(self) -> None:
        self._box = self._make_box()
        minimum, maximum = self._limits()

        # Only an option that can be left out gets the extra position below its range. Both
        # ends go through _cast, since a whole-number box will not take a float even for a
        # bound that happens to be whole.
        self._nullable = self.spec.default is None
        self._unset = self._cast(minimum - _UNSET_STEP if self._nullable else minimum)
        if self._nullable:
            self._box.setSpecialValueText(_UNSET_TEXT)

        self._box.setRange(self._unset, self._cast(maximum))
        self._box.valueChanged.connect(self.changed)
        self._row().addWidget(self._box)

    def value(self) -> Any:
        raw = self._box.value()
        if self._nullable and raw == self._unset:
            return None
        return self._cast(raw)

    def set_value(self, value: Any) -> None:
        self._box.setValue(self._unset if value is None else self._cast(value))


class IntControl(_NumberControl):
    """A whole-number box, for int and IntRange options"""

    def _make_box(self) -> QSpinBox:
        return QSpinBox(self)

    def _cast(self, value: float) -> int:
        return int(value)

    def _limits(self) -> tuple[float, float]:
        minimum, maximum = super()._limits()
        # QSpinBox is a C int, so the stand-in bounds of the base class have to come back
        # inside that range before Qt clamps them itself.
        return max(minimum, -(2**31 - 2)), min(maximum, 2**31 - 1)


class FloatControl(_NumberControl):
    """A decimal box, for float and FloatRange options"""

    def _make_box(self) -> QDoubleSpinBox:
        box = QDoubleSpinBox(self)
        box.setDecimals(3)
        box.setSingleStep(0.1)
        return box

    def _cast(self, value: float) -> float:
        return float(value)


class TextControl(Control):
    """A text box, for plain string options and as the fallback for anything unrecognised"""

    def _build(self) -> None:
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(self.spec.metavar or self.spec.label)
        self._edit.textChanged.connect(self.changed)
        self._row().addWidget(self._edit)

    def value(self) -> str | None:
        text = self._edit.text().strip()
        if text:
            return text
        # An empty box means "not given" for an option with no default; for one that has a
        # default, it means "back to that default", which is the same thing on a command line.
        return None if self.spec.default is None else self.spec.default

    def set_value(self, value: Any) -> None:
        self._edit.setText("" if value is None else str(value))


class EditableChoiceControl(Control):
    """
    A text box with a drop-down of suggestions, for options whose values a case supplies

    Notes
    -----
    For --keyword above all: the values are a case's own keywords, so they cannot be a
    click.Choice, but picking SGAS from a list beats remembering how it is spelled. Typing is
    still allowed, both because the list is only what the case happens to have at the report
    step probed and because a GUI should never be able to express less than the command line.
    """

    def _build(self) -> None:
        self._combo = QComboBox(self)
        self._combo.setEditable(True)
        self._combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._combo.setPlaceholderText(self.spec.metavar or self.spec.label)
        self._combo.currentTextChanged.connect(self.changed)
        self._row().addWidget(self._combo)

    def set_choices(self, choices: Sequence[str]) -> None:
        # Editing the item list resets the line edit, so what the user has typed is put back
        # afterwards - a case being reloaded must not silently clear the chosen keyword.
        typed = self._combo.currentText()
        self._combo.clear()
        self._combo.addItems(list(choices))
        self._combo.setCurrentText(typed)

    def value(self) -> str | None:
        text = self._combo.currentText().strip()
        if text:
            return text
        return None if self.spec.default is None else self.spec.default

    def set_value(self, value: Any) -> None:
        self._combo.setCurrentText("" if value is None else str(value))


class TupleControl(Control):
    """
    A row of boxes, for options taking a fixed number of values, e.g. --clim MIN MAX

    Notes
    -----
    The whole option is given or left out as one - click has no way to accept half of a
    --clim - so the row reports None unless every box has been filled in.
    """

    def _build(self) -> None:
        layout = self._row()
        self._boxes: list[Control] = []

        # Each box is itself a control of the element's kind, so a --clim gets number boxes
        # and a --glyphs gets text boxes, without this class knowing which is which.
        names = self.spec.metavar.split() if self.spec.metavar else []
        for index in range(self.spec.arity):
            element = ParamSpec(
                name=f"{self.spec.name}_{index}",
                kind=self.spec.inner or Kind.TEXT,
                flag=self.spec.flag,
                label=names[index] if index < len(names) else "",
                default=None,
                metavar=names[index] if index < len(names) else "",
            )
            box = build_control(element, parent=self)
            box.changed.connect(self.changed)
            self._boxes.append(box)
            layout.addWidget(box)

    def value(self) -> tuple | None:
        values = [box.value() for box in self._boxes]
        if any(value is None for value in values):
            return None
        return tuple(values)

    def set_value(self, value: Any) -> None:
        values = value if value is not None else [None] * self.spec.arity
        for box, element in zip(self._boxes, values):
            box.set_value(element)


class MultiControl(Control):
    """
    A list, for repeatable options such as -K/--keyword or -i/-j/-k

    Notes
    -----
    Values are typed into one box separated by commas rather than collected in a list widget:
    a program takes up to ten repeatable options at once, and a full list widget each would
    leave no room for anything else. Where the values come from a known set - a case's summary
    vectors, or a click.Choice - a drop-down beside the box appends to it, so the list can be
    built by picking as well as by typing.
    """

    def _build(self) -> None:
        layout = self._row()

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText(
            f"{self.spec.metavar or self.spec.label}, comma separated"
        )
        self._edit.textChanged.connect(self.changed)
        layout.addWidget(self._edit)

        self._picker = QComboBox(self)
        self._picker.setPlaceholderText("add")
        self._picker.setMaximumWidth(140)
        self._picker.activated.connect(self._append_picked)
        layout.addWidget(self._picker)
        self.set_choices(self.spec.choices)

    def set_choices(self, choices: Sequence[str]) -> None:
        """
        Fill the drop-down beside the box

        Parameters
        ----------
        choices : Sequence[str]
            Values to offer, e.g. a case's summary vectors. Hides the drop-down when empty,
            which is the right thing for an option whose values are free text.
        """
        self._picker.clear()
        self._picker.addItems(list(choices))
        self._picker.setVisible(bool(choices))
        self._picker.setCurrentIndex(-1)

    def _append_picked(self, index: int) -> None:
        """
        Add the picked value to the box

        Parameters
        ----------
        index : int
            Row picked in the drop-down
        """
        picked = self._picker.itemText(index)
        if not picked:
            return

        current = [item for item in self._split(self._edit.text()) if item]
        if picked not in current:
            current.append(picked)
        self._edit.setText(f"{_MULTI_SEPARATOR} ".join(current))
        self._picker.setCurrentIndex(-1)

    @staticmethod
    def _split(text: str) -> list[str]:
        """
        Split typed text into the individual values

        Parameters
        ----------
        text : str
            Contents of the box

        Returns
        -------
        list[str]
            Values, trimmed, with empties dropped so a trailing comma is harmless
        """
        return [part.strip() for part in text.split(_MULTI_SEPARATOR) if part.strip()]

    def value(self) -> tuple:
        parts = self._split(self._edit.text())
        if self.spec.inner is Kind.INT:
            # A half-typed number is simply not a value yet; the box is live, so this runs on
            # every keystroke and must not raise on "1," or "-".
            return tuple(int(part) for part in parts if _is_int(part))
        return tuple(parts)

    def set_value(self, value: Any) -> None:
        values = value or ()
        self._edit.setText(f"{_MULTI_SEPARATOR} ".join(str(item) for item in values))


class PathControl(Control):
    """
    The PATHS argument: the case prefixes a program reads

    Notes
    -----
    The window has one case bar shared by every tab, so this control is normally hidden and
    fed from there rather than filled in per tab; it exists so that PATHS is a parameter like
    any other as far as the form and the command line preview are concerned.
    """

    def _build(self) -> None:
        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("case prefix, e.g. /runs/CASE")
        self._edit.textChanged.connect(self.changed)
        self._row().addWidget(self._edit)

    def value(self) -> tuple[str, ...]:
        return tuple(part.strip() for part in self._edit.text().split() if part.strip())

    def set_value(self, value: Any) -> None:
        self._edit.setText(" ".join(str(item) for item in (value or ())))


def _is_int(text: str) -> bool:
    """
    Whether a typed value is a whole number yet

    Parameters
    ----------
    text : str
        One value from a repeatable option's box

    Returns
    -------
    bool
        True if int() would accept it
    """
    try:
        int(text)
    except ValueError:
        return False
    return True


# The registry: one entry per shape a parameter's value can take. build_control falls back to
# a text box for anything missing, so a new Kind cannot leave a parameter without a control.
CONTROLS: dict[Kind, type[Control]] = {
    Kind.FLAG: FlagControl,
    Kind.CHOICE: ChoiceControl,
    Kind.INT: IntControl,
    Kind.FLOAT: FloatControl,
    Kind.TEXT: TextControl,
    Kind.TUPLE: TupleControl,
    Kind.MULTI: MultiControl,
    Kind.PATH: PathControl,
}


def control_class(spec: ParamSpec) -> type[Control]:
    """
    The control class for a parameter

    Parameters
    ----------
    spec : ParamSpec
        Description of the parameter

    Returns
    -------
    type[Control]
        Its control class, or TextControl for a shape with no entry of its own - every click
        value can be typed as text, so this keeps an unforeseen option usable rather than
        absent
    """
    return CONTROLS.get(spec.kind, TextControl)


def build_control(spec: ParamSpec, parent: QWidget | None = None) -> Control:
    """
    Build the control for a parameter

    Parameters
    ----------
    spec : ParamSpec
        Description of the parameter
    parent : QWidget | None, optional
        Parent widget, by default None

    Returns
    -------
    Control
        A control set to the parameter's default
    """
    return control_class(spec)(spec, parent)
