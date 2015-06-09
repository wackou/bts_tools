.. This is your project NEWS file which will contain the release notes.
.. Example: http://www.python.org/download/releases/2.6/NEWS.txt
.. The content of this file, along with README.rst, will appear in your
.. project's PyPI page.

History
=======

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
  see: http://bts-tools.readthedocs.org/en/latest/config_format.html#nodes-list
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
