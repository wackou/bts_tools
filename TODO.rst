TODO
====

This is the day-to-day todo list. For a more high-level overview, see the `roadmap`_.

Main
----

* log output to file with all log levels set to debug. rotate them.
* check core_exchange_factor value in config.yaml (see xeroc)
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
  1 overmind, centralizes all information, can deploy new nodes if required
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


TODO: resubmit pull request for seed nodes

Misc / Minor
------------

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

* secure delegate key: https://bitsharestalk.org/index.php?topic=14360.0
* secure owner key: https://bitsharestalk.org/index.php?topic=14344.0
* securing a server: https://www.debian.org/doc/manuals/securing-debian-howto/


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
* Make it easy to properly support multiple remote nodes -> easy to manage any topology
* Define strategy for best handling of a witness node with backup nodes, feed publisher nodes,
  seed nodes, etc.
* Reboot the backbone proposal
