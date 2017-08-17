
Setup the base OS and build environment
=======================================

Linux
-----

We will do the install on Debian Jessie. It should be very similar on Ubuntu,
however some packages might have slightly different names. Adapting it for Ubuntu
is left as an exercise to the reader.

Note about the text editor: there are countless wars about which editor is the
best, but ultimately it is up to you to pick the one you like best, so no details
will be provided when needing to edit text files, it will just be mentioned that
you need to do it.

Install base up-to-date OS
~~~~~~~~~~~~~~~~~~~~~~~~~~

Installing the base OS will depend on your VPS provider, so check their
documentation for that. The tutorial will use Debian Jessie as base distro,
so you should install it directly whenever possible. You can download the
most recent release of the Debian Jessie installer
`here <https://www.debian.org/devel/debian-installer/>`_,
preferably the netinst version.


Install required dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The first step is to install the dependencies necessary for installing the
tools and for compiling the BitShares client (still as root)::

    # apt-get install build-essential git cmake libssl-dev libdb++-dev libncurses5-dev libreadline-dev \
                      python3-dev python3-pip libyaml-dev libboost-all-dev ntp

Note that we also install the ``ntp`` client here, this is needed to keep your
server's time correctly adjusted, which is a requirement for a witness wanting
to sign blocks (given that the time slot for a block is 3 seconds, you need
to be pretty much spot on when it's your turn to sign a block)

Mac OSX
-------

It is possible, and hence recommended, to build the BitShares client using only
libraries pulled out of `homebrew`_, as you don't have to compile and maintain
dependencies yourself.

::

    brew install git cmake boost berkeley-db readline openssl libyaml
    brew link --force readline

If you already had an "old" version of boost installed, please upgrade to a
newer one::

    $ brew upgrade boost

Also make sure that you are running a constantly up-to-date version of cmake,
you might encounter weird configuration errors otherwise (ie: cmake not finding
properly installed dependencies, etc.)

::

    $ brew upgrade cmake


.. _homebrew: http://brew.sh/

