.. This is your project NEWS file which will contain the release notes.
.. Example: http://www.python.org/download/releases/2.6/NEWS.txt
.. The content of this file, along with README.rst, will appear in your
.. project's PyPI page.

History
=======

0.4.5 (2017-01-02)
------------------

* [bts] fetch correct gold price from Yahoo


0.4.4 (2016-12-30)
------------------

* [all] added Telegram notification plugin
* [all] better subprocess management
* [bts] properly authenticate bit20 feed publication on the blockchain


0.4.3 (2016-10-30)
------------------

* [steem] new config var 'steem_dollar_adjustment' to help maintain SD stability,
          price is published so that bias shows properly on steemd.com
* [steem] added Poloniex feed price provider for Steem
* [bts] new asset feeds: BTWTY, GRIDCOIN (currently disabled due to black swan)
* [bts] fixed precision bug when publishing feed price for expensive assets (eg: BTWTY, GOLD, ...)
* [all] updated seed nodes list, faster page rendering (cache seed nodes status)
* [all] general cleanup fixes, deploy script WIP


0.4.2 (2016-08-09)
------------------

* [all] pre-release of "bts deploy_node" command: complete setup of a
        fresh VPS node, with bts/muse/steem client, nginx/uwsgi,
        supervisor, etc.
* [all] added view for seed nodes of BTS, MUSE and STEEM networks
* [all] added world map view of connected peers and seed nodes along with
        country detection (requires geoip2 account)
* [bts] added ARS (Argentine peso) market pegged asset
* [bts] reactivated GOLD and SILVER (Yahoo issue only temporary)
* [bts] removed Yunbi and CCEDK as feed providers for BTS/BTC
* [all] internal cleanups and refactoring, innumerable minor bug fixes


0.4.1 (2016-06-30)
------------------

* deactivated GOLD and SILVER feed publishing (issue with Yahoo)


0.4 (2016-05-01)
----------------

* API CHANGE: complete rework of the configuration system, please delete
  your old config.yaml file if you have any
* added full support for Steem, including feed publishing
* added feed publishing for BTS assets: TUSD, CASH.USD, CASH.BTC, ALTCAP
* added monitoring plugin that checks on the amount of free disk space
* fixed missed block notification for Graphene clients
* logs are now also present as rotating logfiles in the ~/.bts_tools folder


0.3.4 (2015-12-21)
------------------

* added support for publishing TCNY feed; generally more robust feeds fetching/publishing
* renamed 'bts2' commandline tool to 'bts'. 'bts2' still working for convenience,
  old 'bts' is still available as 'bts1'.
* change in the config.yaml format: https://github.com/wackou/bts_tools/commit/24e962820775a8a23e0b45d26c501aa7e723ff64


0.3.3 (2015-12-10)
------------------

* NOTE: requires the latest version (v2.0.151209) of the BitShares witness client
* better integration with the websocket event loop
* network views available again
* overall lots of minor fixes and general stability improvements


0.3.2 (2015-12-06)
------------------

* interim release that fixes feed for CNY markets


0.3.1 (2015-11-01)
------------------

* support for Muse clients
* better feeds script. Process is now the following:
  - get the BTS/BTC valuation from Poloniex, CCEDK, Bter, Btc38 (configurable)
  - get the BTC/USD valuation from BitcoinAverage, with fallback on Bitfinex and Bitstamp
  - get the BTS valuation in other fiat currencies using Yahoo forex rates
  - get market indices using Yahoo, Google, Bloomberg (configurable)
* can specify 'boost_root' option in build environment in config.yaml
* minor bugfixes everywhere


0.3 (2015-10-27)
----------------

* first release with support for BitShares 2 clients (and graphene-based in general)
  use: bts2 build, bts2 run, bts2 run_cli, bts2 monitor, etc...
* a lot of functionality still missing... Here be dragons!!


0.2.11 (2015-09-26)
-------------------

* fix issue with BitShares 0.9.3 client
* build environments can now specify the "debug" flag to produce debug builds
* extremely preliminary support for graphene clients, only for the brave


0.2.10 (2015-09-03)
-------------------

* added support for managing backbone nodes
* new view in menu "network > backbone status" that shows the configured backbone nodes and
  whether we are connected to them or not
* added monitoring plugins:
  - 'voted_in': monitors when a delegate is voted in or out
  - 'wallet_state': monitors when a wallet is opened/closed and locked/unlocked
  - 'fork': tries to detect when the client is being on a fork and/or out-of-sync
* simplified config yaml file: there are now wildcards monitoring plugins you can use for most
  common tasks:

  - for delegate:

    + 'delegate': used to monitor an active delegate. This will activate the 'missed',
      'network_connections', 'voted_in', 'wallet_state', 'fork', 'version' and 'feeds'
      monitoring plugins
    + 'watcher_delegate': used to monitor a watcher delegate, i.e. without publishing
      any info (version, feeds) to the blockchain. This will activate the 'missed',
      'network_connections', 'voted_in', 'wallet_state' and 'fork' monitoring plugins

  - for seed nodes and delegate nodes, you don't have to specify required command-line args or
    monitoring plugins any longer, it is added automatically in function of the node type

* added "bts deploy" command to copy built binary to specified ssh host(s)


0.2.9 (2015-06-19)
------------------

* feeds for composite indices are now priced in BTS
* active feed providers can be configured in the config.yaml file


0.2.8 (2015-06-10)
------------------

* more robust feed monitoring


0.2.7 (2015-06-09)
------------------

* feeds for market indices are now fetched from Yahoo, Google and Bloomberg
* added Poloniex feed provider for BTS/BTC
* fixed monitoring of DACPLAY instances on linux


0.2.6 (2015-06-05)
------------------

* workaround for 0.2.5 not being installable from pypi


0.2.5 (2015-06-05)
------------------

* added feed for SHANGHAI market-pegged asset


0.2.4 (2015-06-03)
------------------

* added feed for NASDAQC, NIKKEI, HANGSENG market-pegged assets
* list of visible feeds can be configured in config.yaml file


0.2.3 (2015-06-02)
------------------

* added feed for SHENZHEN market-pegged asset
* fixed payroll plugin (contributed by @ThomasFreedman)


0.2.2 (2015-05-04)
------------------

* fixed slate publishing for BTS >= 0.9.0


0.2.1 (2015-04-22)
------------------

* fixed feeds publishing for BTS >= 0.9.0


0.2 (2015-04-14)
----------------

* now requires python3.4
* API CHANGE: format of the config.yaml file has changed, and you will need to update it.
  Run "bts list" and it should tell you what to fix in your config file. For more details,
  see: http://bts-tools.readthedocs.io/en/latest/config_format.html#nodes-list
* added support for building DVS and BTS client >= 0.9.0
* added support for building PLAY client (pls)
* internal refactoring and modularization of the monitoring plugins


0.1.10 (2015-03-23)
-------------------

* modularized monitoring to make it easier to write monitoring plugins
* more robust feed checking
* added payroll distribution system, contributed by user Thom
* general fixes and enhancements


0.1.9 (2015-02-19)
------------------

* allow to pass additional args to "bts run", eg: "bts run --rebuild-index"
* fixed feeds due to bter being down
* completed (for now) documentation and tutorial
* tools display their version in footer of web pages, or using "bts version"


0.1.8 (2015-02-11)
------------------

* fixed minor quirks and annoyances
* enhanced documentation and tutorial


0.1.7 (2015-02-05)
------------------

* fixed bugs
* more documentation


0.1.6 (2015-01-26)
------------------

* started writing reference doc and tutorial
* full support for DevShares
* fixed issue with new naming of tags (bts/X.X.X and dvs/X.X.X)
* include slate for btstools.digitalgaia as an example slate
* send notifications grouped by clients (for multiple delegates in same wallet)
* fixed tools for new API in 0.6.0 (blockchain_get_delegate_slot_records)


0.1.5 (2015-01-06)
------------------

* smarter caching of some RPC calls (improves CPU usage of the client a lot!)
* automatically publish version of the client if not up-to-date
* added ``pts`` command-line tool that defaults to building/running PTS binaries
* new ``publish_slate`` command for the command-line tool
* bugfixes / small enhancements


0.1.4 (2014-12-21)
------------------

* now publishes feeds for BitBTC, BitGold, BitSilver + all fiat BitAssets
* full support for building and monitoring PTS-DPOS clients
* preliminary support for building Sparkle clients
* the usual bugfixes


0.1.3 (2014-11-16)
------------------

* renamed project from bitshares_delegate_tools to bts_tools
* some fixes, up-to-date as of release date (bts: 0.4.24)


0.1.2 (2014-11-09)
------------------

* updated for building following rebranding BitSharesX -> BitShares
  (0.4.24 and above)


0.1.1 (2014-11-03)
------------------

* added view for connected peers and potential peers


0.1 (2014-10-28)
----------------

* first public release
