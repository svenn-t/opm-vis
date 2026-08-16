"""
Running work without leaving the window unresponsive, and reporting what went wrong

Two things happen here. Opening a case - which reads its restart and summary files to fill the
keyword lists - is plain Python and numpy, touches no widget, and so is done on a worker
thread. Drawing is not: both backends render into a widget, and VTK in particular must be
driven from the thread that owns its render window, so a plot runs on the GUI thread behind a
wait cursor instead.
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import click
from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QCursor, Qt
from PySide6.QtWidgets import QApplication

from opm_vis.gui.case import CaseBundle


@contextmanager
def busy() -> Iterator[None]:
    """
    Show a wait cursor for the duration of a piece of work

    Yields
    ------
    None
        While the cursor is set

    Notes
    -----
    Drawing happens on the GUI thread - see the module docstring - so the window is genuinely
    unresponsive meanwhile, and the cursor is what says so. Restored even if the work raises,
    or an error would leave the window looking permanently stuck.
    """
    QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
    try:
        yield
    finally:
        QApplication.restoreOverrideCursor()


def error_message(exc: BaseException) -> str:
    """
    A one-line explanation of a failure, fit for a status bar

    Parameters
    ----------
    exc : BaseException
        Whatever the work raised

    Returns
    -------
    str
        The message

    Notes
    -----
    A click.UsageError is the interesting case: the command line programs raise it for every
    combination of options that does not make sense, with a message already written to be read
    by a person. Reusing it is what gives the GUI the same diagnostics as the CLI for free -
    see the resolve_* helpers in opm_vis.cli.common.
    """
    if isinstance(exc, click.UsageError):
        return exc.format_message()

    return f"{type(exc).__name__}: {exc}"


class CaseLoader(QObject):
    """
    Opens a case on a worker thread and reports the result back

    Attributes
    ----------
    loaded : Signal
        Emitted with the ready CaseBundle
    failed : Signal
        Emitted with a message when the case could not be opened
    """

    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, paths: list[str]) -> None:
        """
        Note the case to open

        Parameters
        ----------
        paths : list[str]
            Filename prefixes of the case
        """
        super().__init__()
        self.paths = paths

    def run(self) -> None:
        """
        Open the case and read everything the controls will ask for

        Notes
        -----
        The readers are lazy, so they are deliberately used here rather than merely built:
        doing that on this thread is the whole point, since it is the reading - a restart
        file's keyword list, a summary file's vectors - that takes the time.
        """
        try:
            bundle = CaseBundle(self.paths)
            bundle.report_steps()
            bundle.grid_keywords()
            bundle.summary_keywords()
        # pylint: disable=broad-exception-caught
        # Anything at all going wrong here is a case that cannot be opened, which is a message
        # in the status bar rather than a traceback in a terminal the user may not be watching.
        except Exception as exc:
            self.failed.emit(error_message(exc))
            return

        self.loaded.emit(bundle)


def load_case(
    paths: list[str],
    on_loaded: Callable[[CaseBundle], None],
    on_failed: Callable[[str], None],
) -> tuple[QThread, CaseLoader]:
    """
    Start opening a case in the background

    Parameters
    ----------
    paths : list[str]
        Filename prefixes of the case
    on_loaded : Callable[[CaseBundle], None]
        Called on the GUI thread with the ready bundle
    on_failed : Callable[[str], None]
        Called on the GUI thread with a message if it could not be opened

    Returns
    -------
    tuple[QThread, CaseLoader]
        The running thread and its worker. Both must be kept referenced by the caller until
        the thread finishes, or Python would collect them mid-run.
    """
    thread = QThread()
    loader = CaseLoader(paths)
    loader.moveToThread(thread)

    thread.started.connect(loader.run)
    loader.loaded.connect(on_loaded)
    loader.failed.connect(on_failed)
    loader.loaded.connect(thread.quit)
    loader.failed.connect(thread.quit)

    thread.start()
    return thread, loader
