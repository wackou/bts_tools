TODO
====

This is the day-to-day todo list. For a more high-level overview, see the `roadmap`_.

Main
----

* use pid to detect when a node goes offline and comes back up immediately
* when witness is online, but cli offline, we should still be able to monitor cpu/ram usage
* rename bts2 to bts
* implement feed for tcny
* feed script should get all markets at once from a single feed provider (when possible)
  in order to avoid spamming the service
* fix blocks missed / produced
* "bts deploy_seed <ip_addr>" completely sets up a new instance. Should also communicate with
  dns provider to update the dns entry of the new seed node
* bts_tools uwsgi instance should also expose a json-rpc interface. This would allow to
  communicate between instances directly and implement needed apis in the tools instead of
  in the witness node
  * then, fix "signing key active" display in view header (need bts_tools json-rpc for that)
* remove deprecated bts-rpc tool, was unusably slow anyway (and we can do better in graphene anyway)
* update doc / screenshots
* write detailed doc about how the feed script works
* fix all FIXMEs left in the code and finalize port to graphene


Misc / Minor
------------

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
