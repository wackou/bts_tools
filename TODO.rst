TODO
====

This is the day-to-day todo list. For a more high-level overview, see the `roadmap`_.

Main
----

* fix network views

  * show total number of potential peers, even though the table only contains a subset of them

* fix blocks missed / produced
* "bts deploy_seed <ip_addr>" completely sets up a new instance. Should also communicate with
  dns provider to update the dns entry of the new seed node
* bts_tools uwsgi instance should also expose a json-rpc interface. This would allow to
  communicate between instances directly and implement needed apis in the tools instead of
  in the witness node
  * then, fix "signing key active" display in view header (need bts_tools json-rpc for that)
* update doc / screenshots and finalize port to graphene


Misc / Minor
------------

* implement more robust BtsProxy.is_localhost()
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


ROADMAP
=======

* Fully port the bts_tools to graphene
* Make it easy to properly support multiple remote nodes -> easy to manage any topology
* Define strategy for best handling of a witness node with backup nodes, feed publisher nodes,
  seed nodes, etc.
* Reboot the backbone proposal
