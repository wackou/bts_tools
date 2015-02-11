
Install the bts_tools package
=============================

The first step in your quest for being a delegate is to install the
``bts_tools`` python package. Make sure you have installed the dependencies as
described in the previous section, and run (as root [#f1]_)::

    # pip3 install bts_tools

That's it, the tools are installed and you should now be setup for building the
BitShares client! To see all that the tools provide, try running::

    $ bts -h

which should show the online help for the tools. You should definitely get
accustomed to the list of commands that are provided.

.. rubric:: Footnotes

.. [#f1] This installs the tools system-wide, and is the simplest way of doing
   it. However, if you have time to invest in learning about them, it is highly
   recommended to look into python virtualenvs and how to deal with them. You
   can find a quick overview about them here: :doc:`virtualenv`

