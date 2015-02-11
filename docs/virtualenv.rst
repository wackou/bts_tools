
Appendix: dealing with virtualenvs
==================================

TODO: write properly

It is very recommended to install inside a virtualenv. See :doc:`install` for more
Actually, that's the whole point of the virtualenvs, is that you don't need to install anything as root, so you don't mess up your system. Everything is contained in your project, which you should run as a normal user anyway. The only thing really needed to install as root with apt-get are: python3, virtualenvwrapper, and maybe python3-pip. All the rest, creation of the virtualenv and pip installing stuff inside should be run as a normal user. I will also add this to the doc.



--------- old notes from the tutorial

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
