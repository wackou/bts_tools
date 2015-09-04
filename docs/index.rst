.. BTS Tools documentation master file, created by
   sphinx-quickstart on Wed Jan 21 12:02:39 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to the BTS Tools documentation!
=======================================

There are 2 tools currently provided:

- command line util allowing to quickly build and run the BitShares client
- web app allowing to monitor a running instance of the client and send
  an email or push notification on failure

If you like these tools, please vote for `my delegate`_
(web page: `http://digitalgaia.io/btstools.html <http://digitalgaia.io/btstools.html>`_)
to support further development, and feel free to visit my page for other
delegate proposals at `digitalgaia.io <http://digitalgaia.io>`_. Thanks!

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



.. _my delegate: bts://delegate.verbaltech/approve
