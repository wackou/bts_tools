TODO
====

This is the day-to-day todo list. For a more high-level overview, see the `roadmap`_.

Main
----

* better error logging: https://pymotw.com/3/cgitb/index.html
* deploy to witness using given wallet or private active (not owner) keys from deploy_config file
* monitoring plugin that checks feed publishing and warns on old feeds
* feed script should work in 2 steps:
  1- first get all the feeds that we can. Don't wait to be pulled for it, get all markets. It's also easier to parallelize efficiently
  2- then, publish what we can from what we have. This way, if all chinese exchanges time out, for instance, then we don't try to publish a wrong feed
* feed script should get all markets at once from a single feed provider (when possible)
  in order to avoid spamming the service
* "bts deploy_seed <ip_addr>" completely sets up a new instance. Should also communicate with
  dns provider to update the dns entry of the new seed node
* remove deprecated bts-rpc tool, was unusably slow anyway (and we can do better in graphene anyway)
* update doc / screenshots
* write detailed doc about how the feed script works
* fix all FIXMEs left in the code and finalize port to graphene
* new node type: the librarian / the snapshotting node: every now and then, stops itself, makes a copy of the blockchain data
  and restart again. the snapshots are made available for quickly deploying a new node without synchronizing
  the entire blockchain from scratch. Should also prove useful in case of forks, too, for getting back on the main one


Misc / Minor
------------

* use pid to detect when a node goes offline and comes back up immediately
* show total number of potential peers, even though the table only contains a subset of them
* fix terminology for feeds (quote, base, etc.) see: http://www.wikiwand.com/en/Currency_pair
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
