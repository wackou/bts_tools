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

**FIXME:** add section about NTP


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


Build and run the BitShares client
==================================

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

At this point, you want to create a wallet, an account and register it as delegate.
Please look at the `BitShares wiki <http://wiki.bitshares.org/index.php/Delegate/How-To>`_
on how to do this.

Pro Tip: running the client in tmux
-----------------------------------

Running the client inside your shell after having logged in to your VPS is what
you want to do in order to be able to run it 24/7. However, you want the client
to still keep running even after logging out. The solution to this problem is to
use what is called a terminal multiplexer, such as `screen`_ or `tmux`_. Don't
worry about the complicated name, what a terminal multiplexer allows you to do is to
run a shell to which you can "attach" and "detach" at will, and which will keep
running in the background. When you re-attach to it, you will see your screen as
if you had never disconnected.

Here we will use ``tmux``, but the process with ``screen`` is extremely similar
(although a few keyboard shortcuts change).

The first thing to do is to launch ``tmux`` itself, simply by running the following
in your shell::

    $ tmux

You should now see the same shell prompt, but a status bar should have appeared
at the bottom of your screen, meaning you are now running "inside" tmux.

.. hint:: The keyboard shortcuts are somewhat arcane, but this is the bare minimum you have to remember:

   when outside of tmux:

   - ``tmux`` : create a new tmux session
   - ``tmux attach`` : re-attach to a running session

   when inside of tmux:

   - ``ctrl+b d`` : detach the session - do this before disconnecting from your server
   - ``ctrl+b [`` : enter "scrolling mode" - you can scroll back the screen (normal arrowsand sliders from
     your terminal application don't work with tmux...) Use ``q`` to quit this mode


So let's try attaching/detaching our tmux session now:
as you just ran 'tmux', you are now inside it
type ``ctrl-b d``, and you should now be back to your shell before launching it

::

   $ tmux attach  # this re-attaches to our session
   $ bts run      # we run the bitshares client inside tmux

type ``ctrl-b d``, you are now outside of tmux, and doesn't see anything from the bts client

::

   $ tmux attach  # this re-attaches your session, and you should see the bts client still in action


To get more accustomed to tmux, it is recommended to find tutorials on the web,
`this one`_ for instance seems to do a good job of showing the power of tmux while
not being too scary...

.. _tmux: http://tmux.sourceforge.net/
.. _screen: http://www.gnu.org/software/screen/
.. _this one: https://danielmiessler.com/study/tmux/


Run the monitoring webapp
=========================

This is the good part :)

Now that you know how to build and run the delegate client, let's
look into setting up the monitoring of the client. Say you want to monitor the
delegate called ``mydelegate``. The possible events that we can monitor and
the actions that we can take also are the following:

- monitor when the client comes online / goes offline (crash), and send
  notifications when that happens (email or iOS)
- monitor when the client loses network connection
- monitor when the client misses a block
- publishing feeds
- ensuring that version number is the same as the one published on the
  blockchain, and if not, publish a new version

These can be set independently for each delegate that you monitor, and need
to be specified in the ``nodes`` attribute of the ``config.yaml`` file.

Each node specifies the type of client that it runs (BitShares, PTS, ...) In
our case here, this will be ``"bts"``.

The type of the node will be ``"delegate"`` (could be ``"seed"`` too, but we're
setting up a delegate here).

The name here will be set to ``"mydelegate"``, and we want to put the following
in the ``"monitoring"`` variable: ``[version, feeds, email]``. As online status,
network connections and missed blocks are always monitored for a delegate node,
you only need to specify whether you want to receive the notifications by email
or boxcar, in this case here we want ``email``. You will also need to configure
the email section later in the ``config.yaml`` in order to be able to receive
them.

This gives the following::

    nodes:
        -
            client: bts
            type: delegate
            name: mydelegate
            monitoring: [version, feeds, email]

Once you have properly edited the ``~/.bts_tools/config.yaml`` file, it is just
a matter of running::

    $ bts monitor

and you can now go to `http://localhost:5000/ <http://localhost:5000/>`_ in
order to see it.

**TODO:** install it inside uwsgi + nginx


Format of the config.yaml file
==============================

- build environments
- run environments
- nodes list


Other notes
===========

**TODO:** publish slate



setup a seed node with a supervisord agent to restart the seed node when it crashes

apt-get install supervisor

vi /etc/supervisor/conf.d/seednode.conf

::

    [program:seednode]
    user=admin
    command=/home/user/.BitShares_bin/bitshares_client --data-dir XX --p2p-port XX  --daemon --rpcuser XX --rpcpassword XX --rpcport 0 --httpport 5678 --max-connections 400
    autorestart=true




.. _homebrew: http://brew.sh/
