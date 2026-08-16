"""
Optional polish for the generated controls: grouping, ordering and case-supplied values

Nothing here is required. A parameter with no hint still gets a control, still ends up on the
form and still reaches the run function - it simply lands in the "More options" group at the
bottom, in declaration order. That is the point: an option added to a CLI works on day one,
and a hint is only how it is later given a better home.

Hints are keyed by click parameter name, which the commands deliberately share - --keyword is
"keyword" in both grid backends, --rstep is "rstep" in three of them - so one entry covers
every program that has the option.
"""
from __future__ import annotations

from dataclasses import dataclass

from opm_vis.gui.widgets import Control, EditableChoiceControl

# Groups, in the order they are shown. The split follows the option reference in docs/source,
# which already divides these options the way someone reading about them expects.
CASE = "Case"
WHAT = "What to plot"
SLICING = "Slicing"
REPORT_STEP = "Report step"
DIFFERENCE = "Difference"
CALCULATOR = "Calculator"
VIEW = "View"
COLOUR = "Colour"
WELLS = "Wells"
THRESHOLD = "Threshold"
CLIP = "Clip"
GLYPHS = "Glyphs"
AXES = "Axes"
LAYOUT = "Layout"
APPEARANCE = "Appearance"
OUTPUT = "Output"
OTHER = "More options"

GROUP_ORDER: tuple[str, ...] = (
    CASE,
    WHAT,
    SLICING,
    REPORT_STEP,
    DIFFERENCE,
    CALCULATOR,
    AXES,
    LAYOUT,
    VIEW,
    COLOUR,
    WELLS,
    THRESHOLD,
    CLIP,
    GLYPHS,
    APPEARANCE,
    OUTPUT,
    OTHER,
)

# Names of the value sources a case can fill a control from; see gui.case.CaseBundle.choices.
GRID_KEYWORDS = "grid_keywords"
SUMMARY_KEYWORDS = "summary_keywords"
REPORT_STEPS = "report_steps"
COLOUR_MAPS = "colour_maps"


@dataclass(frozen=True)
class Hint:
    """
    How one parameter should be presented, over and above what its type already says

    Attributes
    ----------
    group : str
        Group box to put the control in; one of the names above
    hidden : bool
        Keep the control off the form entirely. For the parameters the window drives itself:
        PATHS comes from the shared case bar, and --save/--export from the buttons, since a
        file to write to belongs in a file dialog rather than a text box.
    choices_from : str
        Name of the case-supplied value list to offer, or "" for none
    widget : type[Control] | None
        Control class to use instead of the one the parameter's type would pick
    enabled_by : str
        Name of another parameter that must be switched on for this one to have any effect,
        e.g. --diff-rstep only matters with --diff. Greyed out rather than hidden, so the
        option is still discoverable.
    """

    group: str = OTHER
    hidden: bool = False
    choices_from: str = ""
    widget: type[Control] | None = None
    enabled_by: str = ""


HINTS: dict[str, Hint] = {
    # The case bar above the tabs feeds PATHS to every program at once.
    "paths": Hint(group=CASE, hidden=True),
    # What is being plotted.
    "keyword": Hint(group=WHAT, choices_from=GRID_KEYWORDS, widget=EditableChoiceControl),
    "keywords": Hint(group=WHAT, choices_from=SUMMARY_KEYWORDS),
    "grid_only": Hint(group=WHAT),
    "grid_color": Hint(group=WHAT, enabled_by="grid_only"),
    "compare": Hint(group=WHAT),
    # --list-keywords is a mode of the command line; here the keyword drop-down is already the
    # list, so the option has nothing left to do.
    "list_keywords": Hint(hidden=True),
    "slice_i": Hint(group=SLICING),
    "slice_j": Hint(group=SLICING),
    "slice_k": Hint(group=SLICING),
    "quads": Hint(group=SLICING),
    "rstep": Hint(group=REPORT_STEP, choices_from=REPORT_STEPS, widget=EditableChoiceControl),
    "animate": Hint(group=REPORT_STEP),
    "fps": Hint(group=REPORT_STEP, enabled_by="animate"),
    "fmt": Hint(group=REPORT_STEP),
    "diff": Hint(group=DIFFERENCE),
    "diff_rstep": Hint(group=DIFFERENCE, enabled_by="diff"),
    "diff_kind": Hint(group=DIFFERENCE, enabled_by="diff"),
    "calc_kind": Hint(group=CALCULATOR),
    "calc_count": Hint(group=CALCULATOR, enabled_by="calc_kind"),
    # Summary axes and layout.
    "x_axis": Hint(group=AXES),
    "xlim": Hint(group=AXES),
    "ylim": Hint(group=AXES),
    "log_y": Hint(group=AXES),
    "subplots": Hint(group=LAYOUT),
    "layout": Hint(group=LAYOUT, enabled_by="subplots"),
    "figsize": Hint(group=LAYOUT),
    # Camera.
    "view": Hint(group=VIEW),
    "azimuth": Hint(group=VIEW),
    "elevation": Hint(group=VIEW),
    "z_scale": Hint(group=VIEW),
    "axes": Hint(group=VIEW),
    "window_size": Hint(group=VIEW),
    "cmap": Hint(group=COLOUR, choices_from=COLOUR_MAPS, widget=EditableChoiceControl),
    "clim": Hint(group=COLOUR),
    "log_scale": Hint(group=COLOUR),
    "no_colorbar": Hint(group=COLOUR),
    "opacity": Hint(group=COLOUR),
    "color": Hint(group=COLOUR),
    "wells": Hint(group=WELLS),
    "all_wells": Hint(group=WELLS),
    "threshold": Hint(group=THRESHOLD),
    "threshold_invert": Hint(group=THRESHOLD, enabled_by="threshold"),
    "clip": Hint(group=CLIP),
    "clip_origin": Hint(group=CLIP, enabled_by="clip"),
    "clip_invert": Hint(group=CLIP, enabled_by="clip"),
    "clip_crinkle": Hint(group=CLIP, enabled_by="clip"),
    "glyphs": Hint(group=GLYPHS),
    "glyph_scale": Hint(group=GLYPHS, enabled_by="glyphs"),
    "glyph_every_n": Hint(group=GLYPHS, enabled_by="glyphs"),
    "glyph_factor": Hint(group=GLYPHS, enabled_by="glyphs"),
    "glyph_color": Hint(group=GLYPHS, enabled_by="glyphs"),
    "show_edges": Hint(group=APPEARANCE),
    "wireframe": Hint(group=APPEARANCE),
    "no_title": Hint(group=APPEARANCE),
    "title": Hint(group=APPEARANCE),
    "grid": Hint(group=APPEARANCE),
    "legend": Hint(group=APPEARANCE),
    "linewidth": Hint(group=APPEARANCE),
    "linestyle": Hint(group=APPEARANCE),
    "marker": Hint(group=APPEARANCE),
    # Driven by the Run/Save/Export buttons: where a file goes belongs in a file dialog, and
    # leaving these on the form would offer two ways of saying the same thing.
    "save": Hint(group=OUTPUT, hidden=True),
    "export": Hint(group=OUTPUT, hidden=True),
}

_DEFAULT = Hint()


def hint_for(name: str) -> Hint:
    """
    The hint for a parameter, or a neutral one

    Parameters
    ----------
    name : str
        Click parameter name

    Returns
    -------
    Hint
        Its hint, or a default hint putting it in "More options" with the control its type
        would pick - which is what an option added since this table was written gets
    """
    return HINTS.get(name, _DEFAULT)
