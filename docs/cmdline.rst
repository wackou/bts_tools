
Command-line tools
==================

just run the ``bts`` script with the command you want to execute:

::

    $ bts -h
    usage: bts [-h] [-p PIDFILE] [-f]
               {version,clean_homedir,clean,build,build_gui,run,run_cli,run_gui,list,monitor,deploy,deploy_node}
               [environment] [args [args ...]]

    following commands are available:
      - version                : show version of the tools
      - clean_homedir          : clean home directory. WARNING: this will delete your wallet!
      - save_blockchain_dir    : save a snapshot of the current state of the blockchain
      - restore_blockchain_dir : restore a snapshot of the current state of the blockchain
      - clean                  : clean build directory
      - build                  : update and build bts client
      - build_gui              : update and build bts gui client
      - run                    : run latest compiled bts client, or the one with the given hash or tag
      - run_cli                : run latest compiled bts cli wallet (graphene)
      - run_gui                : run latest compiled bts gui client
      - list                   : list installed bts client binaries
      - monitor                : run the monitoring web app
      - deploy                 : deploy built binaries to a remote server
      - deploy_node            : full deploy of a seed or witness node on given ip address. Needs ssh root access

    Examples:
      $ bts build                 # build the latest bts client by default
      $ bts build v0.4.27         # build specific version
      $ bts build ppy-dev v0.1.8  # build a specific client/version
      $ bts run                   # run the latest compiled client by default
      $ bts run seed-test         # clients are defined in the config.yaml file

      $ bts build_gui   # FIXME: broken...
      $ bts run_gui     # FIXME: broken...



    positional arguments:
      {version,clean_homedir,clean,build,build_gui,run,run_cli,run_gui,list,monitor,deploy,deploy_node}
                            the command to run
      environment           the build/run environment (bts, pts, ...)
      args                  additional arguments to be passed to the given command

    optional arguments:
      -h, --help            show this help message and exit
      -p PIDFILE, --pidfile PIDFILE
                            filename in which to write PID of child process
      -f, --forward-signals
                            forward unix signals to spawned witness client child process

    You should also look into ~/.bts_tools/config.yaml to tune it to your liking.



Building and running the BitShares command-line client
------------------------------------------------------

To build and run the command-line client, you can use the following two commands::

    $ bts build
    $ bts run

By default, ``bts build`` will build the latest version of the BitShares client
(available on the master branch). If you want to build a specific version, you
can do so by specifying either the tag or the git hash.::

    $ bts build 0.5.3
    $ bts build 8c908f8

After the command-line client is successfully built, it will be installed in
the ``bin_dir`` directory as defined in the ``build_environments`` section of the
``config.yaml`` file. The last built version will also be symlinked as
``witness_node`` in that directory, and this is the binary that a call
to ``bts run`` will execute.

You can see a list of all binaries available by typing::

    $ bts list


Passing additional arguments to "bts run"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can pass additional arguments to "bts run" and the tools will forward them
to the actual invocation of the bts client. This can be useful for options that
you only use from time to time, eg: re-indexing the blockchain, or clearing the
peer database. If they are args that start with a double dash (eg: --my-option),
then you need to also prepend those with an isolated double dash, ie::

    $ bts run -- --resync-blockchain --clear-peer-database

otherwise, the "--resync-blockchain" and "--clear-peer-database" would be
considered to be an option for the bts script, and not an argument that should
be forwarded.


Building and running the BitShares GUI client
---------------------------------------------

[FIXME: currently broken]

To build and run the GUI client, the procedure is very similar to the one for
the command-line client::

    $ bts build_gui
    $ bts run_gui

There is one major difference though: the GUI client will not be installed
anywhere and will always be run from the build directory. This is done so in
order to be as little intrusive as possible (ie: not mess with a wallet you
already have installed) and as install procedures are not as clear-cut as for
the command-line client.

