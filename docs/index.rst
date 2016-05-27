.. BTS Tools documentation master file, created by
   sphinx-quickstart on Wed Jan 21 12:02:39 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to the BTS Tools documentation!
=======================================

The BTS Tools will help you build, run and monitor any graphene-based client
(currently BitShares, Steem, Muse). There is still support for older clients
(DACPlay, DPoS-PTS), however this functionality is deprecated and will be removed
in a future version.

.. note:: these tools were originally developed for the BitShares network, and
          later expanded to support any graphene-based network. This means that everywhere
          you will see BitShares mentioned in this documentation, it should be understood
          as BitShares, Steem or Muse. Similarly, ``bts`` can be interchanged with ``steem``
          and ``muse``.

There are 2 tools currently provided:

- command line utility allowing to quickly build and run any graphene-based client
- web application allowing to monitor a running instance of the client and send
  an email or push notification on failure

If you like these tools, please vote for `witness wackou`_ on the Steem, BitShares
and Muse networks. Thanks!

To get started, just type the following in a shell::

    $ pip3 install bts_tools

If you're not familiar with installing python packages or if you run into
problems during installation, please visit the :doc:`install` section for
more details.

With the tools installed, you can refer to each section of the documentation
for more information about how a certain aspect of the tools work.

Otherwise, if you prefer a more hands-on approach to setting up a delegate from
scratch, please head to the following section: :doc:`howto`

Documentation contents
----------------------

.. toctree::
   :maxdepth: 2

   install
   cmdline
   monitor
   variants
   howto
   config_format
   virtualenv
   tips_and_tricks



.. _witness wackou: https://steemit.com/witness-category/@wackou/wackou-witness-post
