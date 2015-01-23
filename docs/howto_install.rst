
Install the bts_tools package
=============================

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

    $ mkvirtualenv -p `which python3` bts_tools

Note that after creating it, it is already active, so no need to call
``workon bts_tools`` now. You will have to do it next time you reboot or open a shell, though.

Let's install the tools now::

    $ pip install bts_tools

That's it, you should now be setup for building the client! To see all that the tools
provide, try running::

    $ bts -h

which should show the online help for the tools. You should definitely get
accustomed to the list of commands that are provided.
