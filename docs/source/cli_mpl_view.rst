View and appearance
=====================

``--view``
------------

Camera preset, ``2d`` (default) or ``3d``.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --view 3d

``--cmap``
------------

Matplotlib colour map name. Default: ``viridis``.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --cmap plasma

``--clim``
------------

Colour limits ``MIN MAX``. Defaults to the data range of the report step(s) shown.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --clim 0.0 0.8

``--no-colorbar``
--------------------

Hides the colorbar.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --no-colorbar

``--figsize``
---------------

Figure size in inches, also the size of a saved image (at Matplotlib's 100 dpi). With
``--view 2d`` the default follows the slice's own proportions, so a square map view gets
square axes. The ratio is clamped between 1:2 and 2.5:1, so a cross-section, which is often
100 times wider than it is deep, still gets a usable height. With ``--view 3d`` the default
is Matplotlib's own figure size.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -i 5 -r 60 --figsize 12 4

``--show-edges``
-------------------

Draws each cell's outline on top of its fill colour.

.. code-block:: bash

   opm-vis-mpl -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --show-edges
