"""
opm-vis-gui: the entry point

Also the one place a missing PySide6 is turned into an explanation rather than a traceback -
opm_vis.gui itself imports nothing, so that its introspection half stays usable without a GUI
toolkit installed. See the package docstring.
"""
from __future__ import annotations

import os
import sys

_MISSING_QT = (
    "opm-vis-gui needs PySide6, which is not installed.\n\n"
    "Install the GUI extra with:\n"
    "    pip install 'opm-vis[gui]'\n"
)


def use_x11_for_vtk() -> None:
    """
    Ask Qt for the X11 platform where VTK needs it and it is available

    Notes
    -----
    VTK's OpenGL render window - which is what the 3D tab embeds - has no Wayland backend, and
    on a Wayland session Qt would pick one by default and the widget would fail to be created
    at all. XWayland is what bridges that, so the X11 plugin is asked for whenever a DISPLAY
    exists to serve it.

    Only ever a default: an explicit QT_QPA_PLATFORM is left alone, which is also how a
    headless run asks for the offscreen plugin. Set before QApplication is built, since that
    is when Qt reads it.
    """
    if os.environ.get("QT_QPA_PLATFORM"):
        return

    if os.environ.get("WAYLAND_DISPLAY") and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def main() -> int:
    """
    Open the window and run until it is closed

    Returns
    -------
    int
        Process exit status: Qt's own, or 1 when the GUI dependencies are missing
    """
    use_x11_for_vtk()

    try:
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415
    except ImportError:  # pragma: no cover - depends on what is installed
        print(_MISSING_QT, file=sys.stderr)
        return 1

    from opm_vis.gui.mainwindow import MainWindow  # noqa: PLC0415

    app = QApplication(sys.argv)
    app.setApplicationName("opm-vis")

    window = MainWindow()
    window.show()

    # A case named on the command line is loaded straight away, so that `opm-vis-gui CASE`
    # behaves like the plotting programs do.
    if len(sys.argv) > 1:
        window.set_case_paths(sys.argv[1:])
        window.load()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
