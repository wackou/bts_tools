
Other notes / TODO
==================

**TODO:** publish slate



setup a seed node with a supervisord agent to restart the seed node when it crashes

apt-get install supervisor

vi /etc/supervisor/conf.d/seednode.conf

::

    [program:seednode]
    user=admin
    command=/home/user/.BitShares_bin/bitshares_client --data-dir XX --p2p-port XX  --daemon --rpcuser XX --rpcpassword XX --rpcport 0 --httpport 5678 --max-connections 400
    autorestart=true



