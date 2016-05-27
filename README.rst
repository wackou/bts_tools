BitShares delegate tools
========================

The BTS Tools will help you build, run and monitor any graphene-based client
(currently BitShares, Steem, Muse). There is still support for older clients
(DACPlay, DPoS-PTS), however this functionality is deprecated and will be removed
in a future version.

.. note:: these tools were originally developed for the BitShares network, and
          later expanded to support any graphene-based network. This means that everywhere
          you will see BitShares mentioned in this documentation, it should be understood
          as BitShares, Steem or Muse. Similarly, ``bts`` can be interchanged with ``steem``
          and ``muse``.

There are 2 tools currently provided:

- command line utility allowing to quickly build and run any graphene-based client
- web application allowing to monitor a running instance of the client and send
  an email or push notification on failure

If you like these tools, please vote for `witness wackou`_ on the Steem, BitShares
and Muse networks. Thanks!

Documentation
-------------

The main documentation for the tools, as well as a tutorial, can be found
on `ReadTheDocs <https://bts-tools.readthedocs.io/>`_.

Command-line client
-------------------

just run the ``bts`` script with the command you want to execute:

::

    $ bts -h
    usage: bts [-h] [-r]
               {version,clean_homedir,clean,build,build_gui,run,run_gui,list,monitor,publish_slate}
               [environment] [args [args ...]]

    following commands are available:
      - version          : show version of the tools
      - clean_homedir    : clean home directory. WARNING: this will delete your wallet!
      - clean            : clean build directory
      - build            : update and build bts client
      - build_gui        : update and build bts gui client
      - run              : run latest compiled bts client, or the one with the given hash or tag
      - run_gui          : run latest compiled bts gui client
      - list             : list installed bts client binaries
      - monitor          : run the monitoring web app
      - publish_slate    : publish the slate as described in the given file

    Examples:
      $ bts build          # build the latest bts client by default
      $ bts build v0.4.27  # build specific version
      $ bts run
      $ bts run debug  # run the client inside gdb

      $ bts build pts-dev v2.0.1  # build a specific client/version
      $ bts run seed-test         # run environments are defined in the config.yaml file

      $ bts build_gui
      $ bts run_gui

      $ bts publish_slate                      # will show a sample slate
      $ bts publish_slate /path/to/slate.yaml  # publish the given slate


    positional arguments:
      {version,clean_homedir,clean,build,build_gui,run,run_gui,list,monitor,publish_slate}
                            the command to run
      environment           the build/run environment (bts, pts, ...)
      args                  additional arguments to be passed to the given command

    optional arguments:
      -h, --help            show this help message and exit
      -r, --norpc           run binary with RPC server deactivated

    You should also look into ~/.bts_tools/config.yaml to tune it to your liking.

Monitoring web app
------------------

To run the debug/development monitoring web app, just do the following:

::

    $ bts monitor

and it will launch on ``localhost:5000``.

For production deployments, it is recommended to put it behind a WSGI
server, in which case the entry point is
``bts_tools.wsgi:application``.

Do not forget to edit the ``~/.bts_tools/config.yaml`` file to configure
it to suit your needs.

Screenshots
~~~~~~~~~~~

You can see a live instance of the bts tools monitoring the state of the
seed nodes I am making available for the BitShares, Muse and Steem networks
here: http://seed.steemnodes.com


.. _witness wackou: https://steemit.com/witness-category/@wackou/wackou-witness-post
