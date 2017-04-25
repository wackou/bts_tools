TODO
====

- split feed fetching into a separate webapp (micro-service architecture)
  each feed for each provider is stored with its timestamp and kept in history
  api for fetching data:
    GET data?since=2017-04-22T00:47:23Z

- feed for RUBLE and ALTCAP.XDR (http://cryptofresh.com/a/ALTCAP.XDR)

- rename "bts run_cli" to "bts cli"

- deploy security: https://github.com/jlund/streisand


----------------

xeroc in telegram:

We should have the option to disable plugins for witnesses ... until we have that .. witnesses can comment those two lines, recompile and have the witness running on less RAM ..
 https://github.com/bitshares/bitshares-core/blob/master/programs/witness_node/main.cpp#L75-L76

----

add option to configure shared memory file size (and maybe swappiness, etc. although that should probably go
into the deployment script)

----------------------

price feed from alt: https://bitsharestalk.org/index.php?topic=20529

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

----------------------

other feed source: https://bitsharestalk.org/index.php/topic,23827.0/topicseen.html


-----------------------

from telegram about feeds:

for good cny price, you really need to have something like these in config.py:
"CNY" : {
                    "metric" : "weighted",
                    "sources" : ["btc38",
                                 "yunbi",
                                 "huobi",
                                 "btcchina",
                                 "okcoin",
                                 "poloniex",
                                 "bittrex",
                                 ]
                },

                now btc38 is migrating to www.bit.cc



if steem doesn't build on graphene, check one of those 2 commits: 0d258d2091b28270877aefe81bbc5369e64875af f172b576cce56de5b9d191843e49cfcd382c53b7

steem seed: @cervantes is up and running: 88.99.33.113 2001

add proper GOLD feed (ie: not yahoo) https://bitsharestalk.org/index.php/topic,23614.0/topicseen.html

you need the account_key_by_api

public-api = database_api login_api account_by_key_api
enable-plugin = witness account_by_key


example config for the new feed script config:

ASSETS:
  USD:
    {'BTS/USD': ['coinmarketcap', 'openledger']}
    {'BTS/BTC': ['xxx', 'xxx],
     'BTC/USD': ['xxx', 'xxx']
  CNY:

GOLD:
  BTS/BTC  BTC/USD  USD/GOLD


get back the mkr we have: https://bitsharestalk.org/index.php/topic,23634.msg301232.html#msg301232


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

TELEGRAM BOT

token overmint_bot: 322625129:AAGXMxWFALhQ73qL7kDSDwmMELQfC2uJDU4

chat_id: 13442656


https://www.reddit.com/r/Python/comments/5hctvj/tutorials_building_telegram_bots_using_python/

--

import os
import sys

#vars in .env, source them
#telegram_bot can be setup via @botfather
#telegram_id can be found via @MyTelegramID_bot

telegram_token = os.environ['feed_telegram_token']
telegram_id    = os.environ['feed_telegram_id']


#function
def telegram(method, params=None):
    url = "https://api.telegram.org/bot"+telegram_token+"/"
    params = params
    r = requests.get(url+method, params = params).json()
    return r

custom_keyboard = [["shit hit fan!"]]
reply_markup = json.dumps({"keyboard":custom_keyboard, "resize_keyboard": True})
conf_msg = ("ALERT! ALERT! SWITCHED FROM WITNESS TO BACKUPNODE! GA DIE SHIT FIXEN")
payload = {"chat_id":telegram_id, "text":conf_msg, "reply_markup":reply_markup}
m = telegram("sendMessage", payload)

===========================

This is the day-to-day todo list. For a more high-level overview, see the `roadmap`_.

- pass everything to using cachetools and wrapt

- ./cli_wallet -s wss://this.piston.rocks`

- ask svk for script to build bts .dmg

- deploy api node, proper nginx forwarding
- test suite for deploy script should deploy at least all node types that I need:
  - test deploy seed node -> seed.steemmnodes.com
  - test deploy witness   -> witness.digitalgaia.io
  - test deploy feed_publisher with compile capabilities -> graphene.digitalgaia.io
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
* fix for steem going active/inactive when position > 19
* find a way for supervisord to properly shutdown the client
* duplicate feed checking when client for both bts and steem is running on same host
* implement single dispatch methods on GrapheneClient to properly handle differences between the various graphene-based chains
* fix "bts build_gui" and "bts run_gui"


* check potential DDoS attack on seed nodes using threaded telnet connections that do nothing; all coming from same IP.
  client should restrict number of connections coming from same ip address

* https://github.com/clayop/steemfeed/blob/master/steemfeed.py   //  https://steemit.com/steem/@clayop/steemfeed--simple-price-feed-python-script
* NOTIFICATIONS SEEM BROKEN!!!
* check for 'localhost' everywhere, make sure we're 100% good
* make sure security on proxy_host is properly verified, otherwise it's a huge security issue!!!
* is payroll still valid?
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

* update doc / screenshots
* fix all FIXMEs left in the code and finalize port to graphene

worker proposal
---------------

benefits:

for the general user:
* network info: https://bitnodes.21.co/ + add seed nodes and backbone nodes

[ref] interesting algo for graph: https://github.com/IntelLedger/sawtooth-core/blob/master/gossip/topology/barabasi_albert.py

for the witnesses / seed node operators
* dev tools:
** sleep tight knowing you'll get notified of anything relevant happening to the health of your nodes and of the blockchain
** easily deploy or take off the grid new nodes in an organic way, allowing maximum flexibility during an attack on the network
** contribute resources to the network and help ensure it is as secure, robust and efficient as possible
* global monitoring and notification system for publishing of feeds for witnesses
see: http://docs.bitshares.eu/_downloads/bitshares-financial-platform.pdf

"Obviously, the shareholders are required to constantly monitor the published prices of their witnesses
and should make a public note about any discrepancies. This is similar to traditional quality management for the
Smart Coin products (e.g. bitUSD) and BitShares system can offer a paid position to perform this service."

----

* new node type: the librarian / the snapshotting node: every now and then, stops itself, makes a copy of the blockchain data
  and restart again. the snapshots are made available for quickly deploying a new node without synchronizing
  the entire blockchain from scratch. Should also prove useful in case of forks, too, for getting back on the main one

* architecture:
  1 overmind, centralizes all information, can deploy new nodes if required (or replicated, as in paxos/raft with 3 nodes). Firewall should reject any connection from someone who isn't one of the deployed nodes
  n feed fetchers (various IPs) get feed price and publish it to the overmind
  1 active wallet publishes the feed price at a given time
  1 active signing node + n backup nodes ready to kick in
  1 librarian taking snapshots of the blockchain, available to the overmind and other nodes (see also: https://github.com/cryptonomex/graphene/issues/499)
  1 continous deployment compiles and makes bin images of the clien available (can be same as librarian)
  n seed nodes
  n backbone nodes / relay nodes
  n network mapping nodes, geographically diverse, that maintain lots of connections and publish the list of online nodes to the overmind

  nodes can be grouped by functionality
   - witness management: [feed fetchers & publisher, signing] (this is private to each witness)
   - general network health and monitoring: [librarian, CI, seed, backbone, mapper] (this is public infrastructure)


  the overmind can monitor which nodes go offline and can switch to a new signing node if one goes down. If a node goes offline for whatever reason, replace it: deploy a new node, wait for it to be synced, and destroy the old one.


Misc / Minor
------------

* replace gethostbyname with getaddrinfo
* better library for ip addr geolocalization
* use pid to detect when a node goes offline and comes back up immediately
* show total number of potential peers, even though the table only contains a subset of them
* feed script enhancements:
  * fix terminology for feeds (quote, base, etc.) see: http://www.wikiwand.com/en/Currency_pair
  * feed script should work in 2 steps:
    1- first get all the feeds that we can. Don't wait to be pulled for it, get all markets. It's also easier to parallelize efficiently
    2- then, publish what we can from what we have. This way, if all chinese exchanges time out, for instance, then we don't try to publish a wrong feed
  * feed script should get all markets at once from a single feed provider (when possible)
    in order to avoid spamming the service
  * monitoring plugin that checks feed publishing and warns on old feeds
  * write detailed doc about how the feed script works
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
