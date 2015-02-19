BitShares delegate tools
------------------------

There are 2 tools currently provided:

- command line util allowing to quickly build and run the BitShares client
- web app allowing to monitor a running instance of the client and send
  an email or push notification on failure

If you like these tools, please vote for `my
delegate <http://digitalgaia.io/btstools.html>`_ to support further
development, and feel free to visit my page for other delegate proposals
at `digitalgaia.io <http://digitalgaia.io>`_. Thanks!

Documentation
=============

The main documentation for the tools, as well as a tutorial, can be found
on `ReadTheDocs <http://bts-tools.readthedocs.org/>`_.

Command-line client
===================

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
==================

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

Monitoring the status of your running bts client binary

.. figure:: https://github.com/wackou/bts_tools/raw/master/bts_tools_screenshot.png
   :width: 800
   :alt: Status screenshot

You can host multiple delegates accounts in the same wallet, and check feed info

.. figure:: https://github.com/wackou/bts_tools/raw/master/bts_tools_screenshot2.png
   :width: 800
   :alt: Info screenshot

Monitoring multiple instances (ie: running on different hosts) at the same time,
to have an overview while running backup nodes and re-compiling your main node.

.. figure:: https://github.com/wackou/bts_tools/raw/master/bts_tools_screenshot3.png
   :width: 800
   :alt: Info screenshot
