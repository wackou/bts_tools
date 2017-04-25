TODO
====


- rename "bts run_cli" to "bts cli"

- future: json schema provides a contract for the format of config.yaml that also serves as always up-to-date documentation
  all temporary variables (black-swanned markets, enabled/disabled plugins, ...) should go there and not in the code,
  except maybe for objective default configurations values.


----------------

xeroc in telegram:

We should have the option to disable plugins for witnesses ... until we have that .. witnesses can comment those two lines, recompile and have the witness running on less RAM ..
 https://github.com/bitshares/bitshares-core/blob/master/programs/witness_node/main.cpp#L75-L76

----

add option to configure shared memory file size (and maybe swappiness, etc. although that should probably go
into the deployment script)


------------------

import json
from itertools import repeat

import time
import websocket
import ssl



for _ in repeat(None):
    ws = None

    sslopt_ca_certs = {'cert_reqs': ssl.CERT_NONE}
    ws = websocket.WebSocket(sslopt=sslopt_ca_certs)
    ws.connect('wss://steemit.com/wspa')

    payload = {'params': [0, 'get_block', [9029927]], 'method': 'call', 'id': 20, 'jsonrpc': '2.0'}
    ws.send(json.dumps(payload, ensure_ascii=False).encode('utf8'))

    print(ws.recv())
    time.sleep(1)


==============

0.16 release
------------

get new options from https://github.com/steemit/steem/releases/tag/v0.16.0

https://steemit.com/witness-category/@bhuz/steemd-v0-16-0-and-chainbase-i-o-issues-and-possible-solutions

https://steemit.com/steem/@steemitblog/steem-0-16-0-official-release

original parameters on Gandi (graphene):

wackou@graphene:~$ cat /proc/sys/vm/dirty_background_ratio
10

wackou@graphene:~$ cat /proc/sys/vm/dirty_expire_centisecs
3000

wackou@graphene:~$ cat /proc/sys/vm/dirty_ratio
20

wackou@graphene:~$ cat /proc/sys/vm/dirty_writeback_centisecs
500


-----------

===========================

This is the day-to-day todo list. For a more high-level overview, see the `roadmap`_.

- pass everything to using cachetools and wrapt

- ./cli_wallet -s wss://this.piston.rocks`

- ask svk for script to build bts .dmg

- deploy api node, proper nginx forwarding
- test suite for deploy script should deploy at least the following node types:
  - test deploy seed node
  - test deploy witness
  - test deploy feed_publisher with compile capabilities (ie: dev machine)
  - test deploy api node

-------

- general info
  - account mined: keys =  sha256(sha512(brain key string))
  - see this link for raft orchestration: https://lwn.net/Articles/694146/


Main
----

* add "enable-plugin" to config.ini for deploy script (for steem, check for bts too)
  NOTE: even when specified on cmdline, it will merge with what's in config.ini, and "witness account_history" by default
        => config.ini needs to have "enable-plugin = witness" always, otherwise RAM goes up
* need to check with public-api and other apis too

* deploy script should define security models:

TODO TODO: also only allow needed apis for the witness node in config.ini

https://steemit.com/piston/@xeroc/this-piston-rocks-public-steem-steem-api-for-piston-users-and-developers

- seed:
  enable-plugin = [witness]
  keys = []

- feed_publisher:
  enable-plugin = [witness]  # no need for witness here?
  keys = [active]

- witness:
  enable-plugin = [witness]
  keys = [signing]

- api_node:
  enable-plugin = [witness, account_history] # no need for witness here
  keys = [signing]


see: xeroc's piston doc: http://piston.readthedocs.io/en/develop/public-api.html#running-your-own-node

if a node has multiple models assigned, we do the union of all the properties, ie:
  enable-plugin = set_union(r['enable-plugin'] for r in roles)


* make the client fully REST (do not keep active node view as a state...)
* steem: always run with --replay
* more sources for feed price for SD

* have a global list of witness nodes monitored, but also seed nodes and ipfs nodes,
  including their reliability (uptime). This way, all nodes are publically accountable,
  and we can have the blockchain pay for them and they get elected in the same way as witnesses.
  Pay should be sufficient that there is a sane amount of competition for the place of node
  provider.

    make a monitoring plugin that monitors all nodes every 10 mins and fetches their status, and store
    it in the global db.

* map.steemnodes.com
  use highcharts and geoip2 databases to have a world map with:
    - [DONE] number of nodes per country
    - [DONE] detailed view of lat/lon for all connected nodes
    - [TODO] wave map of groups of versions of the clients (fc git time)

* feed should have a safeguard in case of too big a variation (eg: the yahoo debacle)
* FIND ALTERNATIVE SOURCE OF FOREX DATA TO YAHOO: http://www.bloomberg.com/news/articles/2016-06-01/oil-traders-may-be-the-only-people-who-want-yahoo-to-thrive
* implement single dispatch methods on GrapheneClient to properly handle differences between the various graphene-based chains
* fix "bts build_gui" and "bts run_gui"

* https://github.com/clayop/steemfeed/blob/master/steemfeed.py   //  https://steemit.com/steem/@clayop/steemfeed--simple-price-feed-python-script
* check for 'localhost' everywhere, make sure we're 100% good
* make sure security on proxy_host is properly verified, can be a potential security issue!!!
* deploy to witness using given wallet or private active (not owner) keys from deploy_config file
* "bts deploy_seed <ip_addr>" completely sets up a new instance. Should also communicate with
  dns provider to update the dns entry of the new seed node
* catch rpc call exception:

    try:
        result = rpc_call('localhost', int(args.rpc_port), args.rpc_user,
                          args.rpc_password, args.method, *args.args)
    except Exception as e:
        log.exception(e)
        result = { 'error': str(e), 'type': '%s.%s' % (e.__class__.__module__,
                                                       e.__class__.__name__) }

    --------------

    # re-raise original exception
    log.debug('Received error in RPC result: %s(%s)'
              % (result['type'], result['error']))
    try:
        exc_module, exc_class = result['type'].rsplit('.', 1)
    except ValueError:
        exc_module, exc_class = 'builtins', result['type']

    exc_class = getattr(importlib.import_module(exc_module), exc_class)
    raise exc_class(result['error'])



Misc / Minor
------------

* replace gethostbyname with getaddrinfo
* better library for ip addr geolocalization
* use pid to detect when a node goes offline and comes back up immediately
* show total number of potential peers, even though the table only contains a subset of them
* status view has total cpu on top of process cpu, z-order should be reversed
* views_public.py:170 needs some desperate caching
* RUN_ENV looks unused


Devops
------

* security hardened ubuntu: https://major.io/2015/10/14/what-i-learned-while-securing-ubuntu/
* using logwatch: https://www.digitalocean.com/community/tutorials/how-to-install-and-use-logwatch-log-analyzer-and-reporter-on-a-vps
* secure delegate key: https://bitsharestalk.org/index.php?topic=14360.0
* secure owner key: https://bitsharestalk.org/index.php?topic=14344.0
* securing a server: https://www.debian.org/doc/manuals/securing-debian-howto/

* https://steemit.com/steemit/@spaced/5p9jb-security-bug-report-steemit-com-is-vulnerable-to-slow-post-and-slowloris-dos-attacks
* https://steemit.com/steem/@spaced/steemit-com-administrators-you-should-not-allow-root-login-you-should-not-accept-passwords-and-you-should-not-let-anyone-just
* https://steemit.com/bitshares/@ihashfury/distributed-access-to-the-bitshares-decentralised-exchange



Misc / informative threads
--------------------------

* git forking model: https://bitsharestalk.org/index.php?topic=19690
* how to use websocket subscribe: https://bitsharestalk.org/index.php?topic=19661
* failover script: https://bitsharestalk.org/index.php/topic,18875.msg254099/topicseen.html#msg254099
* api threads
  * get_account_history: https://bitsharestalk.org/index.php/topic,20133.0/topicseen.html



ROADMAP
=======

* Fully port the bts_tools to graphene
* switch to morepath :) (http://morepath.readthedocs.io/)
* Make it easy to properly support multiple remote nodes -> easy to manage any topology
* Define strategy for best handling of a witness node with backup nodes, feed publisher nodes,
  seed nodes, etc.
* Reboot the backbone proposal
