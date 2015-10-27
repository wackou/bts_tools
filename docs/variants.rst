
Working with other DPOS clients
===============================

The BTS Tools have originally been developed for managing BitShares
delegates, but due to the similarity with other DPOS clients they are
able to handle all the following blockchains:

- 'bts': BitShares
- 'dvs': DevShares
- 'pts': PTS-DPOS
- 'pls': DAC PLAY
- 'bts2': BitShares 2.0 (aka Graphene)
- 'muse': Muse

Support for the other DPOS clients is built-in directly in the ``bts``
cmdline tool, and you only need to specify the corresponding build or run
environment, e.g.::

    $ bts build_gui dvs  # builds the DevShares GUI client
    $ bts build pts      # builds the PTS command-line client

As a convenience feature, the following aliases to the ``bts`` tool are provided:

- ``dvs``: builds using the DevShares environment by default
- ``pts``: builds using the PTS environment by default
- ``pls``: builds using the DAC PLAY environment by default
- ``bts2``: builds using the BitShares 2.0 environment by default
- ``muse``: builds using the Muse environment by default

This means that::

    $ pts build

and

::

    $ bts build pts

are exactly equivalent.



Working with other types of nodes
=================================

Originally, the focus of the tools has been on maintaining delegate nodes on
the BitShares network, but they now support more types of specialized nodes.

Concretely, you can now manage the following types of nodes:
- delegate
- seed
- backbone

Seed nodes are public, do not need an open wallet to run and usually have
a high number of network connections.

Backbone nodes are public, do not need an open wallet to run, and do not perform
peer exchange (in order to hide IP addresses of the delegates connected to them).
They also try to maintain at all time an open connection to all other backbone nodes
in order to have the backbone being a fully-connected graph of its nodes.

Command-line arguments and monitoring plugins are automatically defined depending on
the type of node (seed or backbone), so config should be straightforward. For delegate
nodes, you still have to specify whether you want a 'delegate' or 'watcher_delegate' in
the monitoring section of the node.
