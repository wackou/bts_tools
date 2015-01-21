
Command-line client
===================

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

