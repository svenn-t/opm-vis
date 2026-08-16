"""
Tests driving the panels the way the window does: load a case, fill the form, press Run

These go through the real readers and the real plotting code, so they are what shows that the
generated controls really do reach each program's run function - the parity tests in
test_gui_parity.py only check that the two sides agree on names.
"""
from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtWidgets", reason="the GUI needs the opm-vis[gui] extra")

# pylint: disable=wrong-import-position
from opm_vis.cli.registry import PROGRAMS_BY_SCRIPT  # noqa: E402
from opm_vis.gui.case import CaseBundle  # noqa: E402
from opm_vis.gui.panels import MplPanel, RdatesPanel, SummaryPanel  # noqa: E402


@pytest.fixture(name="pv_panel")
def pv_panel_fixture(qapp, bundle):
    """
    The 3D panel, skipped where its render window cannot be created

    Parameters
    ----------
    qapp : QApplication
        The application, from pytest-qt
    bundle : CaseBundle
        Case to load into the panel

    Returns
    -------
    PvPanel
        The panel, pointed at the case

    Notes
    -----
    A QtInteractor needs pyvistaqt, an OpenGL context and - since VTK has no Wayland
    backend - the X11 platform plugin. None of those are guaranteed on a build machine, and
    the failure is an X protocol error rather than a Python exception, so it is probed for
    here in the same way conftest probes off-screen VTK.
    """
    pytest.importorskip("pyvistaqt", reason="the 3D panel needs the opm-vis[gui] extra")

    from opm_vis.gui.panels import PvPanel  # noqa: PLC0415

    try:
        panel = PvPanel(PROGRAMS_BY_SCRIPT["opm-vis-pv"])
    # pylint: disable=broad-exception-caught
    except Exception as exc:  # pragma: no cover - depends on the render environment
        pytest.skip(f"A Qt render window is unavailable: {exc}")

    panel.set_case(bundle)
    return panel


def test_pyvista_panel_renders_into_the_embedded_window(pv_panel) -> None:
    """The interactor is handed to run_pv, so the scene lands in this widget"""
    pv_panel.form.set_value("keyword", "SGAS")
    pv_panel.form.set_value("slice_k", (1,))
    pv_panel.form.set_value("rstep", "60")
    pv_panel.run()

    assert pv_panel._plotter.plotter is pv_panel._interactor
    assert pv_panel._plotter.keyword == "SGAS"
    assert pv_panel._plotter.rstep == 60
    # -k 1 is 1-based on the command line and 0-based inside; see resolve_slices.
    assert "k0" in pv_panel._plotter.actor_names()


def test_replotting_clears_the_previous_scene(pv_panel) -> None:
    """
    A second run must replace the first, not pile up on it

    Notes
    -----
    The render window outlives each run, so the actors of the previous one have to go
    explicitly; that is what close() does for a plotter that does not own its window.
    """
    pv_panel.form.set_value("keyword", "SGAS")
    pv_panel.form.set_value("slice_k", (1,))
    pv_panel.form.set_value("rstep", "60")
    pv_panel.run()
    pv_panel.form.set_value("slice_k", (3,))
    pv_panel.run()

    names = pv_panel._plotter.actor_names()

    assert "k2" in names
    assert "k0" not in names


@pytest.fixture(name="bundle")
def bundle_fixture(case1) -> CaseBundle:
    """
    SPE1CASE1, opened as the window's case loader would

    Parameters
    ----------
    case1 : str
        Filename prefix of the dataset

    Returns
    -------
    CaseBundle
        The case, ready for a panel
    """
    return CaseBundle([case1])


def _panel(panel_class, script: str, bundle: CaseBundle):
    """
    Build a panel and point it at a case

    Parameters
    ----------
    panel_class : type
        Panel class to build
    script : str
        Name of the program it drives
    bundle : CaseBundle
        Case to load into it

    Returns
    -------
    Panel
        The panel, with its form filled in from the case
    """
    panel = panel_class(PROGRAMS_BY_SCRIPT[script])
    panel.set_case(bundle)
    return panel


def test_case_fills_the_paths_control_and_the_preview(qapp, bundle, case1) -> None:
    """Loading a case must reach the hidden PATHS control, not be held to one side"""
    panel = _panel(RdatesPanel, "opm-vis-rdates", bundle)

    assert panel.run_values()["paths"] == (case1,)
    assert panel._preview.text() == f"opm-vis-rdates {case1}"


def test_report_dates_panel_lists_the_timeline(qapp, bundle) -> None:
    """The simplest program end to end: form to run function to view"""
    panel = _panel(RdatesPanel, "opm-vis-rdates", bundle)
    panel.form.set_value("rstep", "0:2")
    panel.run()

    text = panel.text()

    assert "Report step" in text
    assert "01.01.2015" in text
    # 0, 1 and 2, plus the header row
    assert len(text.splitlines()) == 4


def test_report_dates_panel_follows_the_format_option(qapp, bundle) -> None:
    """An option with no hint of its own still reaches the run function"""
    panel = _panel(RdatesPanel, "opm-vis-rdates", bundle)
    panel.form.set_value("rstep", "0:1")
    panel.form.set_value("fmt", "csv")
    panel.run()

    assert panel.text().splitlines()[0] == "rstep,date,days,years"


def test_summary_panel_draws_the_chosen_vectors(qapp, bundle) -> None:
    """A repeatable option, typed as a list, must arrive as the tuple click would build"""
    panel = _panel(SummaryPanel, "opm-vis-sum", bundle)
    panel.form.set_value("keywords", ("FOPR", "FGOR"))
    panel.form.set_value("subplots", True)
    panel.run()

    assert panel._selected == ["FOPR", "FGOR"]
    assert len(panel._plot.axes) == 2
    assert len(panel._plot.lines) == 2


def test_summary_panel_exports_what_it_drew(qapp, bundle) -> None:
    """The plot is kept after the run, so exporting need not read the case again"""
    panel = _panel(SummaryPanel, "opm-vis-sum", bundle)
    panel.form.set_value("keywords", ("FOPR",))
    panel.run()

    csv = panel._plot.export_csv(panel._selected, x_axis="date")

    assert csv.splitlines()[0] == "date,FOPR"


def test_matplotlib_panel_draws_into_the_embedded_figure(qapp, bundle) -> None:
    """The canvas's own figure is used, rather than a pyplot window being opened"""
    panel = _panel(MplPanel, "opm-vis-mpl", bundle)
    panel.form.set_value("keyword", "SGAS")
    panel.form.set_value("slice_k", (1,))
    panel.form.set_value("rstep", "60")
    panel.run()

    assert panel._collection.fig is panel._canvas.figure
    assert len(panel._collection.ax_.collections) == 1


def test_replotting_reuses_the_same_figure(qapp, bundle) -> None:
    """
    A second run must land on the same canvas

    Notes
    -----
    The figure is cleared and rebuilt rather than replaced, which is what keeps the canvas
    this panel is showing the one being drawn on; see the fig argument of the collections.
    """
    panel = _panel(MplPanel, "opm-vis-mpl", bundle)
    panel.form.set_value("keyword", "SGAS")
    panel.form.set_value("slice_k", (1,))
    panel.form.set_value("rstep", "60")
    panel.run()
    panel.form.set_value("rstep", "80")
    panel.run()

    assert panel._collection.fig is panel._canvas.figure
    assert len(panel._collection.ax_.collections) == 1


def test_a_bad_combination_is_reported_rather_than_raised(qapp, bundle) -> None:
    """
    The command line's own usage errors are what the status bar shows

    Notes
    -----
    opm-vis-mpl plots exactly one slice, and says so through click.UsageError. A GUI must
    survive that and pass the message on, which is the whole reason the run functions keep
    raising it - see runner.error_message.
    """
    panel = _panel(MplPanel, "opm-vis-mpl", bundle)
    panel.form.set_value("keyword", "SGAS")
    panel.form.set_value("slice_k", (1, 2))
    panel.form.set_value("rstep", "60")

    messages: list[str] = []
    panel.status.connect(messages.append)
    panel.run()

    assert messages
    assert "only supports one slice" in messages[-1]


def test_running_without_a_case_says_so(qapp) -> None:
    """Pressing Run before loading anything must explain itself, not raise"""
    panel = RdatesPanel(PROGRAMS_BY_SCRIPT["opm-vis-rdates"])

    messages: list[str] = []
    panel.status.connect(messages.append)
    panel.run()

    assert messages == ["Load a case first: type a path in the case bar and press Load."]


def test_preview_reproduces_the_form_on_a_command_line(qapp, bundle, case1) -> None:
    """
    What the preview shows must be what was run

    Notes
    -----
    This is the promise the preview makes to the user, and it only holds while the argv is
    built from the same values the run function is given.
    """
    panel = _panel(MplPanel, "opm-vis-mpl", bundle)
    panel.form.set_value("keyword", "SGAS")
    panel.form.set_value("slice_k", (1,))
    panel.form.set_value("rstep", "60")
    panel.form.set_value("view", "3d")

    assert panel._preview.text() == (
        f"opm-vis-mpl {case1} --keyword SGAS --k-index 1 --rstep 60 --view 3d"
    )
