# opm-vis
Visualization tools for OPM simulation results.

## Install

```bash
pip install -e .                 # Matplotlib backend only
pip install -e ".[pyvista]"      # adds the PyVista/VTK backend
pip install -e ".[gui]"          # adds opm-vis-gui (includes the PyVista backend)
```

## Documentation

Usage guide and API reference: https://norce-energy.github.io/opm-vis/

## CLI

Plot a keyword on a grid slice without writing any Python:

```bash
opm-vis-pv tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --save sgas_k1.png
```

Plot summary vectors (time series) from the case's `.SMSPEC`/`.UNSMRY` files, one line per
vector or one subplot each:

```bash
opm-vis-sum tests/data/SPE1CASE1 -K FOPR -K 'WBHP:*' --subplots --save rates.png
```

List the case's report steps with their dates and the time since the simulation started:

```bash
opm-vis-rdates tests/data/SPE1CASE1
```

## GUI

All four programs in one window, over a shared case:

```bash
opm-vis-gui tests/data/SPE1CASE1
```

Every control is generated from the command line programs' own options, so the window keeps up
with them on its own. Each tab shows the command line that reproduces whatever it is set to, so
exploring in the window and scripting from the terminal stay one and the same thing.

## API

The same plot, driven from Python with `opm_vis.pvplot`:

```python
from opm_vis.pvplot import GridPlotter

plotter = GridPlotter(["tests/data/SPE1CASE1"])
plotter.add_slice("k", 0)
plotter.set_scalars("SGAS", rstep=60)
plotter.show()
```

## Tests

```bash
python -m pytest -q
```

Tests for `pvplot` render off-screen and skip themselves if no OpenGL context is available, so
a headless machine needs `vtk-osmesa` or `xvfb-run` for those to run.
