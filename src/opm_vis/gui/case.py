"""
The case the window is looking at, and the values it can offer the controls

A CaseBundle opens a set of path prefixes once and keeps the readers, so that filling a
keyword drop-down or moving the report step slider does not reopen the files. Every reader is
opened lazily and independently: a case with no summary files is still perfectly usable for
grid plots, and asking whether it has any must not be what makes it fail.

Deliberately built on opm_vis.utils only, none of which needs pyvista, so the matplotlib,
summary and report-date tabs work on an install without the 3D extra.
"""
from __future__ import annotations

import warnings
from functools import cached_property

from matplotlib import colormaps

from opm_vis.gui.hints import COLOUR_MAPS, GRID_KEYWORDS, REPORT_STEPS, SUMMARY_KEYWORDS
from opm_vis.utils.restart import Report, RestartReader
from opm_vis.utils.static import InitReader
from opm_vis.utils.summary import SummaryReader


class CaseBundle:
    """
    One case - a main run plus any restart runs - and the readers over it

    Attributes
    ----------
    paths : list[str]
        Filename prefixes, as every opm_vis reader takes them: the first is the main run, any
        further ones are restart runs
    """

    def __init__(self, paths: list[str]) -> None:
        """
        Note the paths; nothing is read until something asks for it

        Parameters
        ----------
        paths : list[str]
            Filename prefixes of the case
        """
        self.paths = paths

    # Each reader warns rather than raising when its files are missing - see the readers in
    # opm_vis.utils - so the warnings are swallowed here and answered by the has_* properties
    # instead, which is what the window needs in order to grey out a tab.

    @cached_property
    def report(self) -> Report:
        """
        Report steps and dates of the case

        Returns
        -------
        Report
            Reader over the restart files
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return Report(self.paths)

    @cached_property
    def restart(self) -> RestartReader:
        """
        Dynamic (per report step) keywords of the case

        Returns
        -------
        RestartReader
            Reader over the restart files
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return RestartReader(self.paths)

    @cached_property
    def static(self) -> InitReader:
        """
        Static keywords of the case

        Returns
        -------
        InitReader
            Reader over the .INIT file of the main run, which is the only one it has
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return InitReader(self.paths[0])

    @cached_property
    def summary(self) -> SummaryReader:
        """
        Summary vectors of the case

        Returns
        -------
        SummaryReader
            Reader over the .SMSPEC/.UNSMRY files
        """
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return SummaryReader(self.paths)

    @property
    def has_restart(self) -> bool:
        """
        Whether the case has restart files to plot from

        Returns
        -------
        bool
            True when at least one .UNRST/.X file was found
        """
        return bool(self.restart.rst)

    @property
    def has_summary(self) -> bool:
        """
        Whether the case has summary files to plot from

        Returns
        -------
        bool
            True when at least one .SMSPEC file was found
        """
        return bool(self.summary.smry)

    def report_steps(self) -> list[int]:
        """
        Report steps present in the case

        Returns
        -------
        list[int]
            Step numbers in order, empty when the case has no restart files
        """
        return self.report.report_steps() if self.has_restart else []

    def grid_keywords(self) -> list[str]:
        """
        Keywords that can be plotted on the grid

        Returns
        -------
        list[str]
            Dynamic keywords of the first report step together with the static ones from the
            .INIT file, sorted and without duplicates

        Notes
        -----
        Probed at the first report step only. A keyword introduced part-way through a run
        would be missing from the list, which is why --keyword stays typeable rather than
        being a closed drop-down.
        """
        keywords: set[str] = set()

        if self.has_restart:
            steps = self.report.report_steps()
            if steps:
                keywords.update(self.restart.available_keywords(steps[0]))

        if self.static.init is not None:
            keywords.update(self.static.available_keywords())

        return sorted(keywords)

    def summary_keywords(self) -> list[str]:
        """
        Summary vectors the case holds

        Returns
        -------
        list[str]
            Vector names, sorted, empty when the case has no summary files
        """
        return sorted(self.summary.available_keywords()) if self.has_summary else []

    def choices(self, source: str) -> list[str]:
        """
        Values to offer the controls asking for a given source

        Parameters
        ----------
        source : str
            One of the source names in gui.hints

        Returns
        -------
        list[str]
            Values for that source, empty for a source this case cannot supply or one that
            does not exist
        """
        if source == GRID_KEYWORDS:
            return self.grid_keywords()
        if source == SUMMARY_KEYWORDS:
            return self.summary_keywords()
        if source == REPORT_STEPS:
            return [str(step) for step in self.report_steps()]
        if source == COLOUR_MAPS:
            return sorted(colormaps)

        return []
