"""
One panel per opm-vis program: its generated form beside the view it draws into

Every panel is the same shape - a form on the left, a view on the right, Run and Save below -
and differs only in what it draws into and how it saves. Panel holds all of that; a subclass
supplies the view widget and the two or three lines that call its program's run function.
"""
from __future__ import annotations

from opm_vis.gui.panels.base import Panel
from opm_vis.gui.panels.mpl_panel import MplPanel
from opm_vis.gui.panels.pv_panel import PvPanel
from opm_vis.gui.panels.rdates_panel import RdatesPanel
from opm_vis.gui.panels.summary_panel import SummaryPanel

# Which panel serves which program, by the name it is installed as. A program with no entry
# here is simply not shown; see MainWindow, which walks opm_vis.cli.registry.PROGRAMS.
PANELS = {
    "opm-vis-pv": PvPanel,
    "opm-vis-mpl": MplPanel,
    "opm-vis-sum": SummaryPanel,
    "opm-vis-rdates": RdatesPanel,
}

__all__ = ["PANELS", "MplPanel", "Panel", "PvPanel", "RdatesPanel", "SummaryPanel"]
