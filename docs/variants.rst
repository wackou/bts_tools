
Working with other DPOS clients
===============================

The BTS Tools have originally been developed for managing BitShares
delegates, but due to the similarity with other DPOS clients they are
able to handle all the following blockchains:

- BitShares
- DevShares
- PTS-DPOS
- Sparkle (experimental support)


Support for the other DPOS clients is built-in directly in the ``bts``
cmdline tool, and you only need to specify the corresponding build or run
environment, e.g.::

    $ bts build_gui dvs  # builds the DevShares GUI client
    $ bts build pts      # builds the PTS command-line client

As a convenience feature, the following aliases to the ``bts`` tool are provided:

- ``dvs``: builds using the DevShares environment by default
- ``pts``: builds using the PTS environment by default

This means that::

    $ pts build

and

::

    $ bts build pts

are exactly equivalent.



Working with other types of nodes
=================================

At the moment, the focus of the tools has been on maintaining delegate nodes on
the BitShares network, but it is planned to support more types of specialized
nodes in the future (when they appear).

It is currently possible to maintain seed nodes, too, which can define additional
properties in the ``config.yaml`` file:

- ``desired_number_of_connections``
- ``maximum_number_of_connections``

which will be set once upon launch of the client.
