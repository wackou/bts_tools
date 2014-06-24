BitShares delegate tools
------------------------

just run the bts.py file with the command you want to execute:

    $ python bts.py -h
    usage: bts.py [-h] [-r] {clean_homedir,clean,build,run,list} [hash]

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
      -r, --rpc             run binary with RPC server activated

    You should also look into config.json to tune it to your liking.