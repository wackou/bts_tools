===========================================
How to setup a delegate - the easy tutorial
===========================================


This guide will try to show you how to setup all the infrastructure needed to
build, run and monitor a delegate easily and effortlessly.
We will start from scratch, and end up with a fully functional delegate client
running and being monitored for crashes and missed blocks.

Note also that this guide will not only show you the mininum number of steps
required to get it working once, but it will try to guide you into using best
practices and useful tools that make maintenance of the delegate over time a
seamless experience.
(For the curious, that means using virtualenvs, tmux, etc... If you have no
idea what these are, don't worry, we'll get to it)

Once everything it setup properly, building the latest version of the client,
running it, and launching the monitoring webapp that publishes feeds and sends
you notifications is just a matter of::

    $ bts build
    $ bts run
    $ bts monitor

In details, these are the following steps that this guide will cover:

.. toctree::
   howto_os
   howto_install
   howto_build
   howto_monitor


Note that there are some choices of software that are quite opinionated in this
guide, however this should not be considered as the only way to do things, but
rather just a way that the author thinks makes sense and found convenient for
himself.
