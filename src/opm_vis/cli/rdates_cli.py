"""opm-vis-rdates: list report dates and time since simulation start"""
from __future__ import annotations

from pathlib import Path

import click

from opm_vis.cli.common import (
    PATHS_ARGUMENT,
    handle_errors,
    resolve_paths,
    resolve_rstep_selection,
)
from opm_vis.utils.restart import Report
from opm_vis.utils.timeline import TIMELINE_FORMATS


# COMMAND_SETTINGS is deliberately not used here: its no_args_is_help only makes sense for the
# plotting commands, which have nothing to do without a --keyword. Run bare in a case
# directory, this command has an obvious job - list that case's report dates.
@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@PATHS_ARGUMENT
@click.option(
    "-r",
    "--rstep",
    default=None,
    metavar="STEP | START:END[:STEP]",
    help="Report step, or range of report steps, to list. Default: every report step.",
)
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(TIMELINE_FORMATS),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--save",
    "-s",
    "save",
    default=None,
    metavar="PATH",
    help="Write the output to a file instead of printing it.",
)
@handle_errors
def main(**params) -> None:
    """
    List the report steps in a case with their dates and the time since the simulation started.

    PATHS are filename prefixes: the first is the main run, any further ones are restart runs.
    Defaults to searching the working directory (./) if not given.

    Dates are read from the restart files (.UNRST/.X), at day resolution - no summary file is
    needed. Elapsed time is measured from the first report step, in days and in years (365.25
    days), matching the TIME and YEARS summary vectors.

    See the documentation for the full option reference with examples.
    """
    # Forwarded as a whole rather than parameter by parameter, so that an option added to the
    # decorators above reaches run_rdates - and every other caller of it, such as the GUI -
    # without this shell having to be touched as well. See run_rdates.
    save = params.pop("save")
    output = run_rdates(**params)

    if save is None:
        click.echo(output)
    else:
        Path(save).write_text(output + "\n", encoding="utf-8")


def run_rdates(paths: tuple[str, ...], rstep: str | None, fmt: str) -> str:
    """
    Render a case's report step timeline

    Parameters
    ----------
    paths : tuple[str, ...]
        Value of the PATHS argument
    rstep : str | None
        Value of --rstep: a report step or a START:END[:STEP] range, or None for all of them
    fmt : str
        Value of --format; one of TIMELINE_FORMATS

    Returns
    -------
    str
        The timeline, rendered in fmt

    Notes
    -----
    Takes --save's siblings but not --save itself: what to do with the text is the caller's
    business, since a GUI shows it in a widget rather than writing it anywhere. Every other
    parameter is named exactly after the click option it comes from, which is what lets main
    forward its parameters as a whole - see the signature-parity test.
    """
    report = Report(resolve_paths(paths))
    rsteps = resolve_rstep_selection(report.report_steps(), rstep)
    return report.format_timeline(fmt, rsteps)


if __name__ == "__main__":
    main()
