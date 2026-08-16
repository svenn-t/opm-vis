"""
Tests keeping the GUI in step with the command line programs

The GUI builds its controls by introspecting each click command and then calls that command's
run_* function with what the user typed into them. That only works while the two halves agree
on what a program's options are, which is what these tests check - so that adding an option to
a CLI either reaches the GUI on its own or fails loudly here, rather than silently going
missing from it. See opm_vis.cli.registry.
"""
from __future__ import annotations

import inspect

import pytest

from opm_vis.cli.registry import PROGRAMS, Program
from opm_vis.gui.introspect import describe, to_argv

# The controls need PySide6, which is an optional extra; the introspection above does not, so
# the halves of this file are skipped independently.
_qt = pytest.importorskip("PySide6.QtWidgets", reason="the GUI needs the opm-vis[gui] extra")
from opm_vis.gui.widgets import CONTROLS, build_control  # noqa: E402


def _programs() -> list:
    """
    Every program, as pytest parameters named after the script they install as

    Returns
    -------
    list
        pytest.param entries, one per Program
    """
    return [pytest.param(program, id=program.script) for program in PROGRAMS]


@pytest.fixture(name="program")
def program_fixture(request) -> Program:
    """
    One program, skipped when its backend is not installed

    Parameters
    ----------
    request : pytest.FixtureRequest
        Request carrying the Program to serve

    Returns
    -------
    Program
        The program under test, with both halves imported
    """
    program = request.param
    try:
        program.command, program.run
    except ImportError as exc:  # pragma: no cover - only on an install without the extra
        pytest.skip(f"{program.script} needs an optional backend: {exc}")
    return program


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_run_function_takes_every_option_of_its_command(program: Program) -> None:
    """A GUI passes the command's parameters straight to run, so run must accept them all"""
    accepted = set(inspect.signature(program.run).parameters) - program.injects

    assert accepted == program.option_names(), (
        f"{program.script}: {program.run_name} and its click command disagree on options. "
        f"Only in the command: {sorted(program.option_names() - accepted)}. "
        f"Only in {program.run_name}: {sorted(accepted - program.option_names())}. "
        "Add the option to both, or list it in the program's shell_only if the click shell "
        "is meant to handle it itself."
    )


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_shell_only_options_really_exist(program: Program) -> None:
    """A shell_only name that no longer matches an option would silently exempt nothing"""
    declared = {
        param.name for param in program.command.params if param.name is not None
    }

    assert program.shell_only <= declared, (
        f"{program.script}: shell_only names no option of the command: "
        f"{sorted(program.shell_only - declared)}"
    )


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_injected_parameters_are_keyword_only_and_optional(program: Program) -> None:
    """
    The canvas to draw into is an extra the command line never passes

    Notes
    -----
    Keyword-only keeps it from ever being filled by accident when a caller forwards the click
    parameters positionally, and a default keeps every existing caller - the click shells
    included - working without mentioning it at all.
    """
    parameters = inspect.signature(program.run).parameters

    for name in program.injects:
        assert name in parameters, f"{program.script}: {program.run_name} takes no {name}"
        assert parameters[name].kind is inspect.Parameter.KEYWORD_ONLY, (
            f"{program.script}: {name} must be keyword-only"
        )
        assert parameters[name].default is None, (
            f"{program.script}: {name} must default to None, so the command line need not "
            "pass it"
        )


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_every_option_is_described(program: Program) -> None:
    """Introspection must cover the whole command, or a control would simply be missing"""
    specs = describe(program.command)

    assert {spec.name for spec in specs} == program.option_names() | (
        program.shell_only & {param.name for param in program.command.params}
    )
    for spec in specs:
        assert spec.flag, f"{program.script}: {spec.name} has no flag to write on a command line"
        assert spec.kind is not None


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_every_option_gets_a_control_sitting_at_its_default(
    program: Program, qapp
) -> None:
    """
    Every parameter must build a control, and that control must start where click would

    Notes
    -----
    The second half is what keeps the command line preview honest: a control that started
    anywhere other than its parameter's default would put that option on the preview - and so
    into the run - without the user having touched it.
    """
    for spec in describe(program.command):
        control = build_control(spec)

        assert control is not None, f"{program.script}: no control for {spec.flag}"
        assert control.value() == spec.default, (
            f"{program.script}: {spec.flag} starts at {control.value()!r}, but click would "
            f"use {spec.default!r}"
        )


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_untouched_controls_produce_an_empty_command_line(program: Program, qapp) -> None:
    """A form nobody has typed into must add nothing to the command line"""
    specs = describe(program.command)
    values = {spec.name: build_control(spec).value() for spec in specs}

    assert to_argv(specs, values) == []


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_every_kind_in_use_has_a_control_of_its_own(program: Program) -> None:
    """
    The text box fallback is a safety net, not the plan

    Notes
    -----
    build_control never fails, since it falls back to a text box for a shape it does not know.
    That keeps a new option usable, but it would also hide the fact that a shape needs a
    control of its own - so the shapes actually in use are checked to have one.
    """
    for spec in describe(program.command):
        assert spec.kind in CONTROLS, (
            f"{program.script}: {spec.flag} is a {spec.kind.name}, which has no control of "
            "its own and is falling back to a text box. Add one to widgets.CONTROLS."
        )


@pytest.mark.parametrize("program", _programs(), indirect=True)
def test_every_option_has_a_usable_name(program: Program) -> None:
    """
    Options are matched to controls by name, so each needs one, and --help is not an option

    Notes
    -----
    Click gives every parameter a name derived from its longest flag unless one is declared,
    so this is really a check that nothing exotic - a parameter with no flags at all - has
    crept in and would leave the GUI with a control it cannot label or read back.
    """
    for param in program.command.params:
        assert param.name, f"{program.script}: a parameter of the command has no name"

    assert "help" not in program.option_names()
