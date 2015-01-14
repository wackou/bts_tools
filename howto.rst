======================
Howto setup a delegate
======================

**WARNING: this is very much a work-in-progress. Information might be incorrect / incomplete**

Overview of what this guide covers
==================================

This guide will try to show you how to setup all the infrastructure needed to
build, run and monitor a delegate easily and effortlessly.
We will start from scratch, and end up with a fully functional delegate client
running and being monitored for crashes and missed blocks.

These are the following steps that this guide will cover:

- setup and install the operating system
- setup the bts_tools needed for building and maintaining the delegate
- build your first client and run it (TODO: do wallet & account creation, as well as approval)
- run the monitoring webapp

  - configure the RPC params
  - configure the webapp itself (config.yaml)

- success!

Note that there are some choices of software that are quite opinionated in this
guide, however this should not be considered as the ony way to do things, but
rather just a way that the author thinks makes sense and found convenient for
himself.

Setup the base OS and build environment
=======================================

Linux
-----

We will do the install on Debian Jessie (testing, currently unreleased but
frozen, meaning the packages only accept bugfixes and so will be very similar
to the ones in the final release).

It should be very similar on Ubuntu, however some packages might have slightly
different names. Adapting it for Ubuntu is left as an exercise to the reader.

Note about the text editor: the author likes ``vi``, but ``nano`` is easier to
handle without previous experience, so no details will be provided when needing
to edit text files, it will just be mentioned that you need to do it.

Install base up-to-date OS
~~~~~~~~~~~~~~~~~~~~~~~~~~

Installing the base OS will depend on your VPS provider, so check their
documentation for that. As Debian Jessie is not released yet, install
Debian Wheezy instead (Debian stable, or 7.0), and upgrade to Jessie by
doing the following:

Edit the file ``/etc/apt/sources.list`` and add those lines (or replace
what's there with them)::

    deb http://mirrors.gandi.net/debian jessie main contrib non-free
    deb http://mirrors.gandi.net/debian-security jessie/updates main contrib non-free

Then run the following in your shell (as root, no sudo by default on debian)::

    # apt-get update && apt-get dist-upgrade

At this point, you might want to reboot to get on the new kernel.

Install required dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Next step is to install the required dependencies to compile the BitShares
client (still as root)::

    # apt-get install build-essential git cmake  libssl-dev libdb5.3++-dev libncurses5-dev libreadline-dev python3-dev libffi-dev virtualenvwrapper libboost-dev libboost-thread1.55-dev libboost-date-time1.55-dev libboost-system1.55-dev libboost-filesystem1.55-dev libboost-program-options1.55-dev libboost-signals1.55-dev libboost-serialization1.55-dev libboost-chrono1.55-dev libboost-context1.55-dev libboost-locale1.55-dev libboost-coroutine1.55-dev libboost-iostreams1.55-dev libboost-test1.55-dev



Mac OSX
-------

It is possible, and hence recommended, to build the BitShares client using only
libraries pulled out of `homebrew`_, as you don't have to compile and maintain
dependencies yourself.

::

    brew install cmake boost berkeley-db readline
    brew link --force readline

If you already had an "old" version of boost installed, please upgrade to a
newer one::

    $ brew upgrade boost

Also make sure that you are running a constantly up-to-date version of cmake,
you might encounter weird configuration errors otherwise (ie: cmake not finding
properly installed dependencies, etc.)

::

    $ brew upgrade cmake

temp note
~~~~~~~~~

need xcode-5.1 on 10.9 (?)

::

    $ sudo xcode-select -s /Applications/Xcode-5.1.1.app/Contents/Developer


Install the bts_tools
=====================

The first step in your quest for being a delegate is to install the ``bts_tools`` python package,
and you want to do this in a ``virtualenv``. A ``virtualenv`` in python is
like a sandbox where you can install python packages without interfering at all
with your system, which makes it very safe and convenient, as you never break
your system and you can make new virtualenvs and dispose them at will.

However nice the virtualenvs, their usage is a bit cumbersome, so that is why
we previously installed the ``virtualenvwrapper`` package too, that provides
easy to use functions for dealing with virtualenvs. In particular:

- ``mkvirtualenv`` creates a new virtualenv (``rmvirtualenv`` deletes one)
- ``workon`` allows to "activate" a virtualenv, meaning all packages that you
  install after that will be installed in this virtualenv, and all packages installed
  inside this virtualenv will take precedence over those of the system
  (basically, they will be active)

So let's get started by creating our virtualenv, and make sure they use python 3::

    $ mkvirtualenv -p /usr/bin/python3 bts_tools

Note that after creating it, it is already active, so no need to call
``workon bts_tools`` now. You will have to do it next time you reboot or open a shell, though.

Let's install the tools now::

    $ pip install bts_tools

That's it, you should now be setup for building the client! To see all that the tools
provide, try running::

    $ bts -h

which should show the online help for the tools. You should definitely get
accustomed to the list of commands that are provided.


Build the BitShares client
==========================

Assuming your ``bts_tools`` virtualenv is active (if not, please run
``workon bts_tools`` in your shell), just type the following::

    $ bts build

This will take some time, but you should end up with a BitShares binary ready
to be executed. To make sure this worked, and see all the versions available
on your system, type::

    $ bts list

This should also show you the default version of the client that will be run.

To run it, you just need to::

    $ bts --norpc run

The first time you run it, you need to pass it the ``--norpc`` param (or ``-r``)
in order to not launch the RPC server, as it is not configured yet. After the
first run, this will have created the ``~/.BitShares`` directory (``~/Library/Application Support/BitShares`` on OSX)
and you should go there, edit the ``config.json`` file, and fill in the user and
password for the RPC connection. Next time you will only need to::

    $ bts run

to launch the client.

**TODO** explain how to run the client in a tmux session



Run the monitoring webapp
=========================

This is the good part :)

- monitoring online/offline, connections, etc

  - configuring notifications

- publishing feeds
- watching version number


Other notes
===========

setup a seed node with a supervisord agent to restart the seed node when it crashes

apt-get install supervisor

vi /etc/supervisor/conf.d/seednode.conf

::

    [program:seednode]
    user=admin
    command=/home/user/.BitShares_bin/bitshares_client --data-dir XX --p2p-port XX  --daemon --rpcuser XX --rpcpassword XX --rpcport 0 --httpport 5678 --max-connections 400
    autorestart=true




.. _homebrew: http://brew.sh/
