Output
=======

``--save``, ``-s``
--------------------

Saves to a file instead of opening an interactive window. The file name is generated from the
keyword, slice and report step(s), e.g. ``SGAS_k1_r60.png`` or ``SGAS_k1_r0-120.gif``. Images
go in ``pv-figs/`` and animations in ``pv-gifs/``, inside the case's ``-f``/``--folder``
(the first one, if several are given; the current folder if none), unless ``--save-folder``
says otherwise.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 --save
   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 --animate --save

``--save-folder``, ``-sf``
---------------------------

Folder to save to, instead of the default ``pv-figs/`` (images) or ``pv-gifs/``
(animations) inside the case folder. A relative path is taken from the current folder, not the
case folder. Giving it implies ``--save``. A folder that does not exist yet is created,
along with any missing parent folders, and the program prints ``Created folder <path>`` when it
does so.

.. code-block:: bash

   opm-vis-pv -f tests/data/SPE1CASE1 -K SGAS -k 1 -r 60 -sf results/plots
