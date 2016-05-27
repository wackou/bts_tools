
Installing the tools
====================


Installing dependencies for the tools
-------------------------------------

You will need some dependencies installed first before you can install the
tools proper.

Linux
~~~~~

On Debian-derived OSes (Ubuntu, Mint, etc.), install with::

      # apt-get install build-essential libyaml-dev python3-dev python3-pip

Mac OSX
~~~~~~~

On OSX, you can install the dependencies like that::

      $ brew install libyaml


Installing the tools
--------------------

If the dependencies for the tools are properly installed, you should be able
to install the bts_tools package with the following command::

    $ pip3 install bts_tools

.. note:: You might need to run this as root on linux systems


.. note:: In general, when dealing with python packages, it is good practice to learn how
   to work with virtualenvs, as they make installing python packages more
   self-contained and avoid potential conflicts with python packages installed by
   the system. They do require to invest some time learning about them first, so
   only do it if you feel like you can dedicate that time to it. It is very
   recommended to do so, though, as it can potentially save you a few headaches in
   the future.

   Please refer to the :doc:`virtualenv` section for more details.




Installing dependencies for building the BitShares command-line client
----------------------------------------------------------------------

Even though the tools are properly installed and functional, you also need some
dependencies for being able to compile the BitShares client.

The reference documentation for building the BitShares client can be found on
the `Graphene wiki`_


Linux
~~~~~

On Debian-derived systems, install them with::

    # apt-get install build-essential git cmake libssl-dev libdb++-dev libncurses5-dev \
                      libreadline-dev libffi-dev libboost-all-dev

For Steem, you will also need the qt5 libs::

    # apt-get install build-essential git cmake libssl-dev libdb++-dev libncurses5-dev \
                      libreadline-dev libffi-dev libboost-all-dev qt5-default qttools5-dev-tools



Mac OSX
~~~~~~~

On OSX, you should install dependencies with brew instead of building your own,
as the current libs in brew are recent enough to allow to compile the BitShares
client. You will also need to force the install of ``readline`` system-wide and
override OSX's native version, as it is antiquated.

::

    $ brew install git cmake boost berkeley-db readline openssl
    $ brew link --force readline


If you already had an "old" version of boost installed (< 1.55.0_2), please upgrade to a
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


.. _Graphene wiki: https://github.com/cryptonomex/graphene/wiki#build-instructions
