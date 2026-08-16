"""
The opm-vis command line programs, described in one place

Every program is a click command paired with the plain function holding its actual work - see
each cli module's run_* function. A GUI builds its controls from the click command's own
parameters and then calls that run function with them, so the two stay in step by
construction: an option added to a command shows up as a control and is acted on, without the
GUI knowing anything about it. tests/test_gui_parity.py is what holds that promise to account.

Both halves are imported lazily, so that a program whose backend is not installed - opm-vis-pv
needs the optional pyvista extra - costs nothing until something actually asks for it.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property
from importlib import import_module

import click


@dataclass(frozen=True)
class Program:
    """
    One opm-vis command line program

    Attributes
    ----------
    script : str
        Name it is installed as, e.g. "opm-vis-pv"; see [project.scripts] in pyproject.toml
    label : str
        Short human-readable name, for a GUI tab or menu entry
    module : str
        Import path of the cli module the program lives in
    run_name : str
        Name of the module's run_* function - the one doing the work, taking the click
        command's parameters by their own names
    shell_only : frozenset[str]
        Parameters the click shell keeps to itself rather than passing to the run function,
        because they are about a terminal rather than about a plot: an output format only
        stdout has, or a listing mode that draws nothing. A GUI serves these its own way.
    injects : frozenset[str]
        Keyword-only parameters of the run function that no click option corresponds to: the
        canvas or render window to draw into. Left out, each run function makes its own.
    """

    script: str
    label: str
    module: str
    run_name: str
    shell_only: frozenset[str] = frozenset()
    injects: frozenset[str] = frozenset()

    @cached_property
    def command(self) -> click.Command:
        """
        The click command, imported on first use

        Returns
        -------
        click.Command
            The module's main, with every option this program takes
        """
        return getattr(import_module(self.module), "main")

    @cached_property
    def run(self) -> Callable:
        """
        The function doing the program's work, imported on first use

        Returns
        -------
        Callable
            The module's run_* function
        """
        return getattr(import_module(self.module), self.run_name)

    def option_names(self) -> set[str]:
        """
        Names of the parameters this program's run function takes from the command line

        Returns
        -------
        set[str]
            Every click parameter name except --help and the shell_only ones, which is exactly
            the set a caller is expected to pass to run
        """
        return {
            param.name
            for param in self.command.params
            if param.name is not None and param.name != "help"
        } - self.shell_only


# Ordered as a GUI would show them: the two grid backends, then the time series, then the
# report step listing that needs no plot at all.
PROGRAMS: tuple[Program, ...] = (
    Program(
        script="opm-vis-pv",
        label="3D grid (PyVista)",
        module="opm_vis.cli.pvplot_cli",
        run_name="run_pv",
        injects=frozenset({"plotter"}),
    ),
    Program(
        script="opm-vis-mpl",
        label="Grid slice (Matplotlib)",
        module="opm_vis.cli.plot_cli",
        run_name="run_mpl",
        injects=frozenset({"fig"}),
    ),
    Program(
        script="opm-vis-sum",
        label="Summary vectors",
        module="opm_vis.cli.summary_cli",
        run_name="run_sum",
        # --list-keywords prints the case's vectors instead of plotting, which a GUI does with
        # a dropdown; --export writes CSV, to stdout when given no path; --save rides along
        # with it so that the export still comes out before the plot window blocks. See
        # summary_cli.main.
        shell_only=frozenset({"list_keywords", "export", "save"}),
        injects=frozenset({"fig"}),
    ),
    Program(
        script="opm-vis-rdates",
        label="Report dates",
        module="opm_vis.cli.rdates_cli",
        run_name="run_rdates",
        # run_rdates returns the timeline as text; where it goes is the caller's business.
        shell_only=frozenset({"save"}),
    ),
)

PROGRAMS_BY_SCRIPT: dict[str, Program] = {program.script: program for program in PROGRAMS}
