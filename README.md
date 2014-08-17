BitShares delegate tools
------------------------

there are 2 tools currently provided:
 - command line util allowing to quickly build and run the bitshares client
 - web app allowing to monitor a running instance of the client with rpc
   activated


Command-line client
===================

just run the ``bts`` script with the command you want to execute:

    $ bts -h
    usage: bts [-h] [-r] {clean_homedir,clean,build,run,list} [hash]

    following commands are available:
     - clean_homedir : clean home directory. WARNING: this will delete your wallet!
     - clean         : clean build directory
     - build [hash]  : update and build bts client
     - run [hash]    : run latest compiled bts client, or the one with the given hash
     - list          : list installed bitshares client binaries

    positional arguments:
      {clean_homedir,clean,build,run,list}
                            the command to run
      hash                  the hash of the desired commit

    optional arguments:
      -h, --help            show this help message and exit
      -r, --norpc           run binary with RPC server deactivated

    You should also look into config.json to tune it to your liking.


Monitoring web app
==================

TODO: write better instructions for setup/running

You should edit the bitshares_delegate_tools/config.json file and then run:

    $ python -m bitshares_delegate_tools.wsgi
     

### Screenshots ###

Monitoring the status of your running bts client binary

![Status screenshot](bts_tools_screenshot.png)

Monitoring multiple instances at the same time, to have an overview while
running backup nodes and re-compiling your main node.

![Info screenshot](bts_tools_screenshot2.png)


Things to know (best practices and "issues") READ IT !!!
========================================================

- to properly build the bitshares client in MacOSX:
  + you can (and should) build the binary with only homebrew libraries.
    Previous versions had trouble compiling and could require you to hand-compile
    some dependencies, but newer homebrew libs should compile properly
  + ```readline``` needs to be installed by brew and you need to run
    ```brew link --force readline``` to take precedence over the outdated
    version of the system

- when running the web client in uWSGI, make sure to:
  + set ```enable-threads = true```, otherwise you won't get the monitoring
    thread properly launched
  + set ```lazy-apps = true```, otherwise the stats object
    will not get properly shared between the master process and the workers,
    and you won't get any monitoring data
  + set ```workers = 1```, otherwise you will get multiple instances of the
    worker thread active at the same time
