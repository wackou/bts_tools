
Installing the tools
====================

The tools need python3 to run, and usually it is just matter of::

    $ pip3 install bts_tools


Installing dependencies for the tools
-------------------------------------

However, there are some specificities depending on which OS you want to
install them.

- on some Debian-derived OSes (Ubuntu, Mint, etc.), the ``pyyaml`` module
  requires ``libyaml`` to be installed as well as the development headers for
  it and python3. These can be installed with::

      # apt-get install libyaml-dev python3-dev

- on OSX, it is also recommended to install the ``libyaml`` package::

      $ brew install libyaml


Installing dependencies for building the BitShares command-line client
----------------------------------------------------------------------

Even though the tools are properly installed and functional, you also need some
dependencies for being able to compile the BitShares client.

The reference documentation for building the BitShares client can be found on
the `BitShares wiki`_

Linux
~~~~~

On Debian-derived systems, install them with::

    # apt-get install build-essential git cmake  libssl-dev libdb5.3++-dev libncurses5-dev
      libreadline-dev python3-dev libffi-dev libboost-all-dev

Mac OSX
~~~~~~~

On OSX, you should install dependencies with brew instead of building your own,
as the current libs in brew are recent enough to allow to compile the BitShares
client. You will also need to force the install of ``readline`` system-wide and
override OSX's native version, as it is antiquated.

::

    $ brew install cmake boost berkeley-db readline
    $ brew link --force readline


If you already had an "old" version of boost installed (<1.55.0_2), please upgrade to a
newer one::

    $ brew upgrade boost



Installing dependencies for building the BitShares GUI client
-------------------------------------------------------------

To build the GUI client, you will need the same dependencies as for the command-line client,
plus the following additional ones.

Linux
~~~~~

On Debian-derived systems, install them with::

    # apt-get install qt5-default libqt5webkit5-dev qttools5-dev qttools5-dev-tools npm nodejs-legacy


Mac OSX
~~~~~~~

TODO


.. _BitShares wiki: http://wiki.bitshares.org/index.php/Developer/Build
