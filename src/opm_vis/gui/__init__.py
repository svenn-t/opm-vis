"""
opm-vis-gui: one window over all four opm-vis command line programs

Controls are generated from each click command's own parameters rather than written out by
hand, and the values they collect are passed to that command's run_* function, so an option
added to a program appears here and is acted on without this package being touched. See
opm_vis.cli.registry for the pairing and opm_vis.gui.introspect for the introspection.

Nothing is imported here on purpose: opm_vis.gui.introspect is meant to be usable - and
testable - without PySide6 installed, which importing a widget module from this file would
prevent. The friendly "install opm-vis[gui]" message lives in opm_vis.gui.app, which is where
someone without PySide6 actually arrives.
"""
