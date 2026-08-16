"""
Reading the shape of a click command's options, so controls can be built from them

This is the half of the GUI that knows about click but nothing about Qt: it turns each
parameter of a command into a ParamSpec saying what kind of value it holds, and turns a set of
values back into the command line that would produce them. opm_vis.gui.widgets then decides
what control to show for a spec, and never has to look at a click object itself.

Deliberately importable without PySide6, both so the shape of a command can be tested headless
and so nothing here is tempted to reach for a widget.
"""
from __future__ import annotations

import shlex
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import click

# Click 8.4 marks "no default declared" with a sentinel rather than None; older versions have
# no such object, so a private stand-in that nothing can equal takes its place. Fetched by name
# because click does not export it.
_UNSET: Any = getattr(click.core, "UNSET", object())


class Kind(Enum):
    """
    The shape of a parameter's value, which is what decides the control shown for it

    Notes
    -----
    Deliberately coarse: a control is chosen by how a value is entered - a switch, a choice, a
    number, a row of numbers, a list - rather than by what the value means. That is what lets
    an option nobody anticipated still get a usable control, since every click parameter falls
    into one of these.
    """

    FLAG = "flag"
    """A switch: is_flag, with or without a --no- counterpart"""

    CHOICE = "choice"
    """One of a fixed set of strings"""

    INT = "int"
    """A whole number"""

    FLOAT = "float"
    """A number"""

    TEXT = "text"
    """Free text"""

    TUPLE = "tuple"
    """A fixed-length row of values, e.g. --clim MIN MAX"""

    MULTI = "multi"
    """Repeatable: the option can be given more than once, collecting a list"""

    PATH = "path"
    """The PATHS argument: the case prefixes every program starts from"""


@dataclass(frozen=True)
class ParamSpec:
    """
    One parameter of a command, described in terms of the control it needs

    Attributes
    ----------
    name : str
        Click parameter name, e.g. "slice_i". This is the key run functions take it by.
    kind : Kind
        Shape of the value; see Kind
    flag : str
        Longest flag, e.g. "--i-index", or "PATHS" for the positional argument. What a caller
        would type, and what the command line preview writes.
    label : str
        Human-readable name for the control, derived from flag
    default : Any
        Click's own default, used as the control's starting value
    help : str
        Click's help text, shown as a tooltip
    metavar : str
        Click's metavar, e.g. "MIN MAX", used as placeholder text and to name the boxes of a
        TUPLE row
    choices : tuple[str, ...]
        Allowed values for a CHOICE, empty otherwise
    arity : int
        Number of values a TUPLE holds; 1 for everything else
    inner : Kind | None
        Shape of each value of a MULTI or TUPLE, e.g. INT for -i/-j/-k
    minimum, maximum : float | None
        Bounds of an INT/FLOAT declared with click's IntRange/FloatRange, or None
    optional_value : bool
        True for an option that may be given with no value at all, like --save: three states,
        not two. See click's is_flag=False, flag_value="" pattern.
    required : bool
        Whether click would refuse to run without it
    """

    name: str
    kind: Kind
    flag: str
    label: str
    default: Any = None
    help: str = ""
    metavar: str = ""
    choices: tuple[str, ...] = ()
    arity: int = 1
    inner: Kind | None = None
    minimum: float | None = None
    maximum: float | None = None
    optional_value: bool = False
    required: bool = False
    secondary_flag: str = ""
    """The --no- counterpart of a boolean flag pair, e.g. "--no-axes", or "" """

    aliases: tuple[str, ...] = field(default_factory=tuple)
    """Every flag this parameter answers to, longest first; used for the command line preview"""


def _kind_of_type(param_type: click.ParamType) -> Kind:
    """
    Map a click parameter type to the shape of the value it produces

    Parameters
    ----------
    param_type : click.ParamType
        Type of a click parameter, or of one element of a composite one

    Returns
    -------
    Kind
        CHOICE, INT, FLOAT or TEXT; anything unrecognised is treated as text, which every
        click type can at least be typed as
    """
    if isinstance(param_type, click.Choice):
        return Kind.CHOICE
    if isinstance(param_type, click.IntRange) or param_type is click.INT:
        return Kind.INT
    if isinstance(param_type, click.FloatRange) or param_type is click.FLOAT:
        return Kind.FLOAT

    # click.INT/click.FLOAT are singletons, but a type declared as the bare builtin (type=int)
    # becomes a distinct IntParamType instance, so the name is what identifies it.
    if param_type.name == "integer":
        return Kind.INT
    if param_type.name == "float":
        return Kind.FLOAT

    return Kind.TEXT


def _bounds(param_type: click.ParamType) -> tuple[float | None, float | None]:
    """
    Lower and upper bound of a click range type

    Parameters
    ----------
    param_type : click.ParamType
        Type of a click parameter

    Returns
    -------
    tuple[float | None, float | None]
        (min, max), either of which is None when unbounded or when the type is not a range

    Notes
    -----
    An open bound (min_open, as --linewidth uses to demand a positive number) is reported as
    the bound itself: a spin box cannot express "greater than 0 but not 0", and click still
    rejects the endpoint if it is ever actually submitted.
    """
    if isinstance(param_type, (click.IntRange, click.FloatRange)):
        return param_type.min, param_type.max

    return None, None


def _label_of(flag: str) -> str:
    """
    Turn a flag into a control label

    Parameters
    ----------
    flag : str
        Flag as typed, e.g. "--glyph-every-n" or "PATHS"

    Returns
    -------
    str
        e.g. "Glyph every n", "Paths"
    """
    return flag.lstrip("-").replace("-", " ").replace("_", " ").capitalize()


def _longest(opts: list[str]) -> str:
    """
    The most descriptive of a parameter's flags

    Parameters
    ----------
    opts : list[str]
        Flags of a click parameter, e.g. ["-K", "--keyword"]

    Returns
    -------
    str
        The longest one, which is the long form wherever there is one
    """
    return max(opts, key=len) if opts else ""


def describe_param(param: click.Parameter) -> ParamSpec:
    """
    Describe one click parameter in terms of the control it needs

    Parameters
    ----------
    param : click.Parameter
        A parameter of a command, either an Option or the PATHS Argument

    Returns
    -------
    ParamSpec
        Its shape, defaults and help text

    Notes
    -----
    The order of the checks matters: a repeatable option is MULTI whatever its element type
    is, and a composite one is TUPLE, because in both cases it is the repetition rather than
    the element that decides what the control looks like. The element type is kept in `inner`
    so the control can still show number boxes rather than text boxes.
    """
    name = param.name or ""
    opts = list(param.opts)
    flag = _longest(opts) if opts else name.upper()
    metavar = param.metavar or ""
    help_text = getattr(param, "help", "") or ""
    secondary = _longest(list(param.secondary_opts)) if param.secondary_opts else ""
    aliases = tuple(sorted(opts, key=len, reverse=True))

    common: dict[str, Any] = {
        "name": name,
        "flag": flag,
        "label": _label_of(flag),
        "default": _default_of(param),
        "help": help_text,
        "metavar": metavar,
        "required": bool(param.required),
        "secondary_flag": secondary,
        "aliases": aliases,
    }

    # The PATHS argument: a list of case prefixes, and the one thing every program shares.
    if isinstance(param, click.Argument):
        return ParamSpec(kind=Kind.PATH, inner=Kind.TEXT, **common)

    # A composite type, e.g. --clim's (float, float). click.Tuple carries one type per value.
    if isinstance(param.type, click.Tuple):
        element_types = list(param.type.types)
        return ParamSpec(
            kind=Kind.TUPLE,
            arity=len(element_types),
            inner=_kind_of_type(element_types[0]) if element_types else Kind.TEXT,
            **common,
        )

    if getattr(param, "multiple", False):
        inner = _kind_of_type(param.type)
        return ParamSpec(
            kind=Kind.MULTI,
            inner=inner,
            choices=_choices_of(param.type),
            **common,
        )

    if getattr(param, "is_flag", False):
        return ParamSpec(kind=Kind.FLAG, **common)

    kind = _kind_of_type(param.type)
    minimum, maximum = _bounds(param.type)
    return ParamSpec(
        kind=kind,
        choices=_choices_of(param.type),
        minimum=minimum,
        maximum=maximum,
        # --save and --export take a value or stand alone; see SAVE_OPTION in cli/common.py.
        optional_value=getattr(param, "is_flag", False) is False
        and getattr(param, "flag_value", None) == "",
        **common,
    )


def _default_of(param: click.Parameter) -> Any:
    """
    The value click would pass for a parameter left alone

    Parameters
    ----------
    param : click.Parameter
        A parameter of a command

    Returns
    -------
    Any
        Its default, with click's "no default declared" sentinel resolved to the value the
        callback actually receives: an empty tuple where values accumulate - a repeatable
        option or the variadic PATHS argument - and None everywhere else

    Notes
    -----
    Click 8.4 marks an undeclared default with a sentinel rather than None, and get_default
    hands that sentinel straight back, so it has to be resolved here. Left as it was, it would
    reach a control as a starting value that is neither empty nor a number and, worse, compare
    unequal to the default in the command line preview, putting every such option on it.
    """
    default = param.default
    if default is not _UNSET:
        return default

    accumulates = getattr(param, "multiple", False) or param.nargs == -1
    return () if accumulates else None


def _choices_of(param_type: click.ParamType) -> tuple[str, ...]:
    """
    Allowed values of a click.Choice

    Parameters
    ----------
    param_type : click.ParamType
        Type of a click parameter

    Returns
    -------
    tuple[str, ...]
        The choices as strings, or empty for any other type
    """
    if isinstance(param_type, click.Choice):
        return tuple(str(choice) for choice in param_type.choices)

    return ()


def spec_argv(spec: ParamSpec, value: Any) -> list[str]:
    """
    The command line fragment one parameter's value would be typed as

    Parameters
    ----------
    spec : ParamSpec
        Description of the parameter
    value : Any
        Value held for it

    Returns
    -------
    list[str]
        Words to add to the command line, empty when the value is the default - an option
        nobody touched has no business appearing on it

    Notes
    -----
    The inverse of what click does when parsing, which is what makes the preview a command
    that really reproduces the run rather than a description of it.
    """
    if value is None or value == spec.default:
        return []

    if spec.kind is Kind.PATH:
        return [str(item) for item in value]

    if spec.kind is Kind.FLAG:
        # A flag pair carries its own way of saying "off"; a lone flag can only be left out,
        # which the default check above has already handled.
        if value:
            return [spec.flag]
        return [spec.secondary_flag] if spec.secondary_flag else []

    if spec.kind is Kind.MULTI:
        argv: list[str] = []
        for item in value:
            argv += [spec.flag, str(item)]
        return argv

    if spec.kind is Kind.TUPLE:
        return [spec.flag] + [str(item) for item in value]

    # --save and friends: given with no value at all, the flag stands alone.
    if spec.optional_value and value == "":
        return [spec.flag]

    return [spec.flag, str(value)]


def to_argv(specs: Sequence[ParamSpec], values: dict[str, Any]) -> list[str]:
    """
    The arguments a set of values would be typed as, in declaration order

    Parameters
    ----------
    specs : Sequence[ParamSpec]
        Parameters of the command, as returned by describe
    values : dict[str, Any]
        Value per click parameter name; parameters left out keep their default and so
        contribute nothing

    Returns
    -------
    list[str]
        Arguments, ready to hand to a CliRunner or to join into a shell command

    Notes
    -----
    PATHS comes first, as it is written by hand, even though click itself accepts the
    positional argument anywhere among the options.
    """
    paths: list[str] = []
    options: list[str] = []

    for spec in specs:
        if spec.name not in values:
            continue
        argv = spec_argv(spec, values[spec.name])
        if spec.kind is Kind.PATH:
            paths += argv
        else:
            options += argv

    return paths + options


def command_line(script: str, specs: Sequence[ParamSpec], values: dict[str, Any]) -> str:
    """
    The whole command line for a set of values, ready to paste into a terminal

    Parameters
    ----------
    script : str
        Name the program is installed as, e.g. "opm-vis-pv"
    specs : Sequence[ParamSpec]
        Parameters of the command
    values : dict[str, Any]
        Value per click parameter name

    Returns
    -------
    str
        e.g. "opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60", with anything a shell would
        misread quoted - a wildcard such as 'WOPR*' above all, which is meant to reach the
        program rather than be expanded on the way
    """
    return " ".join([script] + [shlex.quote(word) for word in to_argv(specs, values)])


def describe(command: click.Command) -> list[ParamSpec]:
    """
    Describe every parameter of a command, in declaration order

    Parameters
    ----------
    command : click.Command
        One of the opm-vis commands

    Returns
    -------
    list[ParamSpec]
        One spec per parameter, --help left out - it is click's own and has nothing to set
    """
    return [
        describe_param(param)
        for param in command.params
        if param.name is not None and param.name != "help"
    ]
