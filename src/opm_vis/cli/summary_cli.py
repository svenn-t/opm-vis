"""opm-vis-sum: plot summary vectors (time series) from a case's .SMSPEC/.UNSMRY files"""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import click
from click.core import ParameterSource

from opm_vis.cli.common import (
    COMMAND_SETTINGS,
    PATHS_ARGUMENT,
    SAVE_OPTION,
    check_curve_option_count,
    default_summary_output_name,
    handle_errors,
    resolve_paths,
    resolve_subplot_layout,
    resolve_summary_keywords,
)
from opm_vis.plot.plot_summary import LINE_STYLES, X_AXES, SummaryPlot, resolve_curve_option
from opm_vis.utils.summary import SummaryReader

# --xlim's date form, matching the ISO-8601 dates opm-vis-rdates prints in csv/json: on a
# command line an unambiguous, sortable date matters more than matching the dd.mm.yyyy the plot
# titles use.
_XLIM_DATE_FORMAT = "%Y-%m-%d"


def _options_given(ctx: click.Context, ignore: frozenset[str]) -> list[str]:
    """
    Names of the options actually typed on this command line

    Parameters
    ----------
    ctx : click.Context
        Context of the running command
    ignore : frozenset[str]
        Parameter names to leave out of the result, i.e. the option the conflict is about

    Returns
    -------
    list[str]
        Display names ("-K/--keyword", "--grid/--no-grid") of the options given explicitly, in
        declaration order

    Notes
    -----
    Click's parameter source is what separates "given on the command line" from "left at its
    default", which a plain truthiness test cannot do for an option whose default is truthy -
    --grid, --legend and --x-axis all are. Naming the offending options is what lets the
    --list-keywords error say which ones to drop, instead of vaguely blaming "the plotting
    options".
    """
    return [
        "/".join(param.opts + param.secondary_opts)
        for param in ctx.command.params
        if isinstance(param, click.Option)
        and param.name is not None
        and param.name not in ignore
        and ctx.get_parameter_source(param.name) is ParameterSource.COMMANDLINE
    ]


def _parse_xlim(raw: tuple[str, str] | None, x_axis: str) -> tuple[Any, Any] | None:
    """
    Parse --xlim into the pair the chosen x axis actually takes

    Parameters
    ----------
    raw : tuple[str, str] | None
        Raw values of --xlim
    x_axis : str
        Value of --x-axis

    Returns
    -------
    tuple[Any, Any] | None
        None if --xlim was not given; a (datetime, datetime) pair with --x-axis date, otherwise
        a (float, float) pair

    Raises
    ------
    click.UsageError
        If the values do not parse as the axis's own kind, or do not increase

    Notes
    -----
    --xlim is typed as a pair of strings rather than a pair of floats because the axis it limits
    is a date axis by default; --ylim, which is always numeric, is a plain (float, float).
    """
    if raw is None:
        return None

    values: tuple[Any, Any]
    if x_axis == "date":
        try:
            values = (
                dt.datetime.strptime(raw[0], _XLIM_DATE_FORMAT),
                dt.datetime.strptime(raw[1], _XLIM_DATE_FORMAT),
            )
        except ValueError as exc:
            raise click.UsageError(
                "--xlim values must be ISO dates (YYYY-MM-DD) with --x-axis date; got "
                f"'{raw[0]} {raw[1]}'."
            ) from exc
    else:
        try:
            values = (float(raw[0]), float(raw[1]))
        except ValueError as exc:
            raise click.UsageError(
                f"--xlim values must be numbers with --x-axis {x_axis}; got "
                f"'{raw[0]} {raw[1]}'."
            ) from exc

    if values[0] >= values[1]:
        raise click.UsageError(f"--xlim MIN MAX must be increasing; got {raw[0]} {raw[1]}.")

    return values


@click.command(**COMMAND_SETTINGS)
@PATHS_ARGUMENT
# Deliberately not common.py's KEYWORD_OPTION: that one is single-valued, because the grid
# plotters colour by exactly one keyword at a time. Putting several time series in the same plot
# is the whole point of a summary plot, so this -K is repeatable and takes fnmatch patterns -
# the same short form, a different shape. It stays local rather than bending the shared option
# into something neither program wants, the way rdates_cli.py declares its own --save.
@click.option(
    "-K",
    "--keyword",
    "keywords",
    multiple=True,
    metavar="VECTOR",
    help="Summary vector to plot, e.g. FOPR or WBHP:PROD. An fnmatch pattern such as 'WOPR*' "
    "plots every vector matching it. Repeatable.",
)
@click.option(
    "--list-keywords",
    is_flag=True,
    default=False,
    help="Print the summary vectors this case has and exit, instead of plotting.",
)
@click.option(
    "--compare",
    is_flag=True,
    default=False,
    help="Read each PATHS entry as a case of its own, one line per case and vector, instead of "
    "stitching them into a single restart chain.",
)
@click.option(
    "--x-axis",
    type=click.Choice(X_AXES),
    default="date",
    show_default=True,
    help="Plot against report dates, days since the start of the simulation, or years of "
    "365.25 days (as in the YEARS vector).",
)
@click.option(
    "--subplots",
    is_flag=True,
    default=False,
    help="Give each vector its own subplot, sharing the x axis, instead of drawing them all in "
    "one axes.",
)
@click.option(
    "--layout",
    type=(int, int),
    default=None,
    metavar="ROWS COLS",
    help="Shape of the --subplots grid. Defaults to the squarest grid that fits every vector. "
    "Only used with --subplots.",
)
@click.option("--log-y", is_flag=True, default=False, help="Use a logarithmic y axis.")
@click.option(
    "--xlim",
    type=(str, str),
    default=None,
    metavar="MIN MAX",
    help="X axis limits: ISO dates (YYYY-MM-DD) with --x-axis date, numbers otherwise. "
    "Defaults to the span of the data.",
)
@click.option(
    "--ylim",
    type=(float, float),
    default=None,
    metavar="MIN MAX",
    help="Y axis limits. Defaults to the range of the data.",
)
@click.option(
    "--title",
    default=None,
    metavar="TEXT",
    help="Figure title. Defaults to the case name, or none when comparing several cases.",
)
@click.option(
    "--figsize",
    type=(float, float),
    default=None,
    metavar="WIDTH HEIGHT",
    help="Figure size in inches. Defaults to Matplotlib's own figure size for a single axes, "
    "and to a size scaled to the --subplots grid otherwise.",
)
@click.option(
    "--grid/--no-grid",
    default=True,
    show_default=True,
    help="Draw grid lines behind the curves.",
)
@click.option(
    "--legend/--no-legend",
    default=True,
    show_default=True,
    help="Label each curve with its vector name, and with its case when --compare is given.",
)
@click.option(
    "--linewidth",
    "--lw",
    "linewidth",
    type=click.FloatRange(min=0, min_open=True),
    default=None,
    metavar="WIDTH",
    help="Line width of every curve. Defaults to Matplotlib's own default.",
)
@click.option(
    "--linestyle",
    "--ls",
    "linestyle",
    type=click.Choice(LINE_STYLES),
    multiple=True,
    help="Line style of every curve, or one per -K/--keyword (matched in the same order, "
    "after any wildcard is expanded). Left out, curves default to solid, or a dash pattern per "
    "vector when several share one axes under --compare. Given together with --marker for a "
    "vector, both are drawn; given alone, it defaults to 'none' for that vector so the marker "
    "replaces the line. Repeatable.",
)
@click.option(
    "--marker",
    multiple=True,
    metavar="MARKER",
    help="Matplotlib marker for every data point, e.g. 'o', 's' or '^' - or one per "
    "-K/--keyword, matched the same way as --linestyle. Replaces the line for a vector unless "
    "--linestyle is also given for it. Repeatable.",
)
@click.option(
    "--color",
    "-c",
    "color",
    multiple=True,
    metavar="COLOR",
    help="Matplotlib colour for every curve, e.g. a name, 'C0'/'C1'/... or a hex code - or one "
    "per -K/--keyword, matched the same way as --linestyle. Defaults to one colour per "
    "keyword, or one per case under --compare. Repeatable.",
)
# Independent of --save: --export writes the plotted data itself, not an image of it, so both
# can be given together to get a PNG and a CSV from one invocation. Three states, the same
# mechanism as --save: not given (no export), given with no value (print to stdout, since a
# CSV - unlike an image - is as useful on the terminal as in a file), given a path (write there).
@click.option(
    "--export",
    "-e",
    is_flag=False,
    flag_value="",
    default=None,
    metavar="[PATH]",
    help="Export the plotted data as CSV, in addition to (or instead of) drawing it. Prints to "
    "stdout if PATH is omitted. Combine with --save to skip the interactive window and only "
    "write files.",
)
@SAVE_OPTION
@handle_errors
def main(**params) -> None:
    """
    Plot summary vectors - the time series in a case's .SMSPEC/.UNSMRY files - such as FOPR,
    FGOR or WBHP:PROD.

    PATHS are filename prefixes: the first is the main run, any further ones are restart runs,
    read as a single stitched time series. Defaults to searching the working directory (./) if
    not given. With --compare, each path is a separate case instead, drawn as its own line.

    Pick vectors with -K/--keyword, once per vector; a value containing a wildcard is an fnmatch
    pattern, so -K 'WOPR*' plots the oil rate of every well. Run --list-keywords to see what
    the case has.

    --export writes the same data as CSV, alongside the plot or instead of it.

    See the documentation for the full option reference with examples.
    """
    # Popped rather than passed on: --list-keywords is a mode this command line is in rather
    # than a property of a plot; --export can print to stdout, which only a command line has;
    # and --save is left alongside it so that the export still comes out before show() blocks
    # on the plot window, as it did when both lived in one function. Everything else is
    # forwarded as a whole, so an option added to the decorators above reaches run_sum - and
    # every other caller of it, such as the GUI - without this shell having to be touched as
    # well. See run_sum and the signature-parity test.
    list_keywords = params.pop("list_keywords")
    export = params.pop("export")
    save = params.pop("save")

    if list_keywords:
        given = _options_given(click.get_current_context(), frozenset({"list_keywords"}))
        if given:
            raise click.UsageError(
                "--list-keywords only prints the case's summary vectors; drop "
                f"{', '.join(given)} to list them, or drop --list-keywords to plot."
            )
        for name in sorted(SummaryReader(resolve_paths(params["paths"])).available_keywords()):
            click.echo(name)
        return

    plot, selected = run_sum(**params)

    if export is not None:
        csv_text = plot.export_csv(selected, x_axis=params["x_axis"])
        if export:
            Path(export).write_text(csv_text + "\n", encoding="utf-8")
        else:
            click.echo(csv_text)

    if save is None:
        plot.show()
    else:
        plot.save_plot(
            Path(save)
            if save
            else default_summary_output_name(
                selected, x_axis=params["x_axis"], compare=params["compare"]
            )
        )


# pylint: disable=too-many-arguments,too-many-locals
def run_sum(
    paths: tuple[str, ...],
    keywords: tuple[str, ...],
    compare: bool,
    x_axis: str,
    subplots: bool,
    layout: tuple[int, int] | None,
    log_y: bool,
    xlim: tuple[str, str] | None,
    ylim: tuple[float, float] | None,
    title: str | None,
    figsize: tuple[float, float] | None,
    grid: bool,
    legend: bool,
    linewidth: float | None,
    linestyle: tuple[str, ...],
    marker: tuple[str, ...],
    color: tuple[str, ...],
    *,
    fig: Any = None,
) -> tuple[SummaryPlot, list[str]]:
    """
    Validate the options of one opm-vis-sum run and draw its curves

    Parameters
    ----------
    fig : Figure | None, optional
        Figure to draw into, by default None, which creates one of its own. Passed straight to
        SummaryPlot; give an embedding canvas's figure to plot into a GUI, where show() only
        redraws that canvas rather than opening a window of its own.

    Returns
    -------
    tuple[SummaryPlot, list[str]]
        The plot and the keywords it drew - --keyword's wildcards expanded against the cases.
        Both are returned so a caller that passed its own figure can keep hold of them, to
        export the plotted data later without reading the cases again.

    Raises
    ------
    click.UsageError
        If the options do not make sense together; the message is meant to be shown as is, on
        a terminal or in a GUI's status bar alike.

    Notes
    -----
    Every parameter other than fig is one of opm-vis-sum's own options, named exactly after
    it - see that command's --help for what each one does. Naming them identically is what
    lets main forward its parameters as a whole, and so what lets an option added to the
    command reach here without main being touched; tests/test_gui_parity.py checks that the
    two have not drifted apart. --list-keywords, --export and --save are the exceptions main
    keeps to itself; see its own comment for why.
    """
    resolved_paths = resolve_paths(paths)

    # Everything that can be checked without opening a file is checked before one is opened
    if not keywords:
        raise click.UsageError(
            "Pass -K/--keyword at least once to pick a summary vector to plot, or "
            "--list-keywords to see what the case has."
        )
    if compare and len(resolved_paths) < 2:
        raise click.UsageError(
            "--compare needs at least two PATHS, one per case to compare. A single path is "
            "read as one case with its restarts, which is what this command does anyway "
            "without --compare."
        )
    if ylim is not None and ylim[0] >= ylim[1]:
        raise click.UsageError(f"--ylim MIN MAX must be increasing; got {ylim[0]} {ylim[1]}.")
    if figsize is not None and (figsize[0] <= 0 or figsize[1] <= 0):
        raise click.UsageError(
            f"--figsize WIDTH HEIGHT must both be positive; got {figsize[0]} {figsize[1]}."
        )
    xlim_values = _parse_xlim(xlim, x_axis)

    # Keywords are resolved against the plot's own cases rather than a reader of their own, so a
    # pattern under --compare can match a vector any of them has; --layout, --linestyle,
    # --marker and --color are then checked against however many that turned out to be.
    plot = SummaryPlot(resolved_paths, compare=compare, figsize=figsize, fig=fig)
    selected = resolve_summary_keywords(keywords, plot.available_keywords())
    layout_shape = resolve_subplot_layout(layout, subplots, len(selected))

    check_curve_option_count("--linestyle", linestyle, selected)
    check_curve_option_count("--marker", marker, selected)
    check_curve_option_count("--color", color, selected)
    linestyles = resolve_curve_option(linestyle, selected)
    markers = resolve_curve_option(marker, selected)
    for keyword in selected:
        if linestyles[keyword] == "none" and markers[keyword] is None:
            raise click.UsageError(
                f"--linestyle none needs --marker as well for {keyword}, or nothing would be "
                "drawn; pass --marker to plot markers instead of a line."
            )

    plot.plot(
        selected,
        x_axis=x_axis,
        subplots=subplots,
        layout=layout_shape,
        log_y=log_y,
        xlim=xlim_values,
        ylim=ylim,
        title=title,
        grid=grid,
        legend=legend,
        linewidth=linewidth,
        linestyle=linestyle,
        marker=marker,
        color=color,
    )

    return plot, selected


if __name__ == "__main__":
    main()
