
Command-line tools
==================

just run the ``bts`` script with the command you want to execute:

::

    $ bts -h
    usage: bts [-h] [-r]
               {clean_homedir,clean,build,build_gui,run,run_gui,list,monitor,publish_slate}
               [environment] [hash]

    following commands are available:
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
      {clean_homedir,clean,build,build_gui,run,run_gui,list,monitor,publish_slate}
                            the command to run
      environment           the build/run environment (bts, pts, ...)
      hash                  the hash or tag of the desired commit

    optional arguments:
      -h, --help            show this help message and exit
      -r, --norpc           run binary with RPC server deactivated

    You should also look into ~/.bts_tools/config.yaml to tune it to your liking.



Building and running the BitShares command-line client
------------------------------------------------------

To build and run the command-line client, you can use the following two commands::

    $ bts build
    $ bts run

By default, ``bts build`` will build the latest version of the BitShares client
(available on the master branch). If you want to build a specific version, you
can do so by specifying either the tag, shortened tag (without ``bts/`` or
``dvs/`` prepended), or the git hash. For instance, all those are equivalent
and will build the same binary::

    $ bts build bts/0.5.3
    $ bts build 0.5.3
    $ bts build 8c908f8

After the command-line client is successfully built, it will be installed in
the $BIN_DIR directory as defined in the ``build_environments`` section of the
``config.yaml`` file. The last built version will also be symlinked as
``bitshares_client`` in that directory, and this is the binary that a call
to ``bts run`` will execute.

You can see a list of all binaries available by typing::

    $ bts list


Building and running the BitShares GUI client
---------------------------------------------

To build and run the GUI client, the procedure is very similar to the one for
the command-line client::

    $ bts build_gui
    $ bts run_gui

There is one major difference though: the GUI client will not be installed
anywhere and will always be run from the build directory. This is done so in
order to be as little intrusive as possible (ie: not mess with a wallet you
already have installed) and as install procedures are not as clear-cut as for
the command-line client.


Publishing a slate
------------------

Once you have your delegate up and running, you might want to publish a slate
of recommended delegates. To do so, you will need to have your wallet unlocked
and have a file with the following format somewhere, say in ``/tmp/slate.yaml``::

    delegate: publishing_delegate_name
    paying: paying_account  # optional, defaults to publishing delegate
    slate:
     - delegate_1
     - delegate_2
     - ...
     - delegate_N


You can then publish your slate like so::

    $ bts publish_slate /tmp/slate.yaml
