
Working with various Graphene clients
=====================================

The BTS Tools have originally been developed for managing BitShares
witnesses (delegates at the time), but thanks to Graphene providing a common substrate
for blockchains they are now able to handle all the following blockchains:

- ``bts``: BitShares
- ``steem``: Steem
- ``ppy``: PeerPlays
- ``muse``: Muse

Support for the various Graphene clients is built-in directly in the ``bts``
cmdline tool, and you only need to specify the corresponding build
environment, e.g.::

    $ bts build steem    # build the Steem client
    $ bts run muse       # run the Muse client

If you don't specify a environment, it will use the ``bts`` environment by default.
As a convenience feature, the following aliases to the ``bts`` command-line tool are provided:

- ``steem``: uses the Steem environment by default
- ``ppy``: uses the PeerPlays environment by default
- ``muse`` : uses the Muse environment by default

This means that::

    $ steem build

and

::

    $ bts build steem

are exactly equivalent.



Working with other types of nodes
---------------------------------

Originally, the focus of the tools has been on maintaining witness nodes on
the BitShares network, but they now support more types of specialized nodes.

Concretely, you can now manage the following types of nodes:

- witness
- feed_publisher
- seed
- backbone  [FIXME: not implemented yet!]

You can define which type of node to run using the ``roles`` directive of the
client configuration (see :doc:`core_concepts`)

Seed nodes are public, do not need an open wallet to run and usually have
a high number of network connections.

Feed publishers will check feed prices on external feed providers and provide a feed
aggregate to publish on the blockchain.

Backbone nodes are public, do not need an open wallet to run, and do not perform
peer exchange (in order to hide IP addresses of the witnesses connected to them).
They also try to maintain at all time an open connection to all other backbone nodes
in order to have the backbone being a fully-connected graph of its nodes.

Command-line arguments and monitoring plugins are automatically defined depending on
the type of node (seed or backbone), so config should be straightforward.