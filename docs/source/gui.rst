Graphical interface
===================

``opm-vis-gui`` puts all four command line programs in one window: the 3D grid, the Matplotlib
grid slice, the summary vectors and the report dates, each on its own tab, over a single case
bar they all share.

.. code-block:: bash

   pip install -e ".[gui]"
   opm-vis-gui                      # or: opm-vis-gui /runs/SPE1CASE1

Using it
--------

1. Type a case prefix into the **Case** bar — a path without its extension, e.g.
   ``/runs/SPE1CASE1`` — or press **Browse…** and pick any file of the case, whose extension is
   dropped for you. Add restart runs after the main one, separated by spaces.
2. Press **Load**. The case is opened in the background and every tab is filled in from it: the
   keyword lists, the report steps, the grid dimensions.
3. Pick a tab, fill in the options, and press **Run**. **Save…** writes what is on screen to a
   file, and the summary tab additionally has **Export CSV…** for the plotted numbers.

The **Command** box at the bottom of every tab shows the command line that reproduces what the
tab is currently set to. Options left at their defaults are left off it, so it stays short.
Copying it into a terminal runs exactly the same plot — which makes it a way to move from
exploring in the window to scripting, and a way to report a problem precisely.

An option that does not make sense together with another is reported in the status bar in the
same words the command line uses, since it is the same check doing the reporting.

What the window adds
--------------------

- **One case for every tab.** Switching from the grid to the summary vectors keeps the case
  loaded; it is read once, not once per tab.
- **Keywords you can pick.** ``--keyword`` and ``--cmap`` become drop-downs filled from the
  case itself, and stay typeable, since the list is only what the first report step happened to
  have.
- **Options in groups.** The controls are grouped the way :doc:`the option reference <cli>`
  groups them, and options that only matter alongside another — ``--diff-rstep`` with
  ``--diff``, ``--fps`` with ``--animate`` — are greyed out until it is switched on.

What it leaves to the command line
----------------------------------

- ``--animate`` is best used with **Save…**, writing a GIF or MP4. Playing an animation inside
  the window is not supported: it would need the render window's own event loop, which the
  window already has one of.
- ``--list-keywords`` has no control, because the keyword drop-down already is the list.

.. note::

   The 3D tab renders through VTK, which has no Wayland backend. On a Wayland session
   ``opm-vis-gui`` therefore asks Qt for the X11 plugin, which XWayland serves. Setting
   ``QT_QPA_PLATFORM`` yourself overrides that.

How it stays current
--------------------

The window contains no list of what options each program has. Every control is generated from
the click command's own parameters — its type, choices, default and help text — and the values
they collect are passed straight to that program's ``run_*`` function, whose keyword arguments
are those same parameter names.

Adding an option to a command line program therefore adds a control to the window and has it
acted on, with no change to :mod:`opm_vis.gui` at all. It lands in the **More options** group
until :mod:`opm_vis.gui.hints` is told where it belongs, which is the only thing that is ever
written by hand — and is optional.

``tests/test_gui_parity.py`` is what holds this to account: it checks, for every program, that
the run function accepts exactly the options its command declares and that each one gets a
control that starts where click would. An option added to only one of the two halves fails
there rather than going quietly missing from the window.
