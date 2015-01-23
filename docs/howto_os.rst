
Setup the base OS and build environment
=======================================

Linux
-----

We will do the install on Debian Jessie (testing, currently unreleased but
frozen, meaning the packages only accept bugfixes and so will be very similar
to the ones in the final release).

It should be very similar on Ubuntu, however some packages might have slightly
different names. Adapting it for Ubuntu is left as an exercise to the reader.

Note about the text editor: there are countless wars about which editor is the
best, but ultimately it is up to you to pick the one you like best, so no details
will be provided when needing to edit text files, it will just be mentioned that
you need to do it.

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

Choosing the correct version of XCode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: This happens on the author's computer and may or may not happen to you,
          so take with a grain of salt. YMMV.

It appears that the most recent version of XCode cannot build the BitShares client,
at least on Mavericks (OSX 10.9), because the API generator segfaults.
XCode 5.1 does work properly, though, so the recommended way is to:

- download XCode 5.1.1 from the Apple developer center
- install it on your computer, say in ``/Applications/Xcode-5.1.1``
  (you can use it in parallel with the latest version if you like)
- tell your system to use this version on the command-line by running::

      $ sudo xcode-select -s /Applications/Xcode-5.1.1.app/Contents/Developer

- you can now proceed normally!


.. _homebrew: http://brew.sh/

