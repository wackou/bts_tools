
Appendix: dealing with virtualenvs
==================================

When dealing with python packages, it is possible to install them as root and
make them available for the entire system. This is not always recommended as it
can sometimes cause conflicts with the packages installed by your OS.

In the python world a solution to deal with that problem has emerged and allows
to create sandboxes in which to install python packages, so that they do not
interfere with those of the system. These sandboxes are called `virtualenvs`_,
short for "virtual environments".

Although very powerful, the usage of the bare virtualenv functionality can
sometimes be cumbersome, so it is very recommended to use another project
instead that gives you an easier API to work with: `virtualenvwrapper`_

The main commands that virtualenvwrapper provides are the following:

- ``mkvirtualenv`` creates a new virtualenv (``rmvirtualenv`` deletes it)
- ``workon`` allows to "activate" a virtualenv, meaning all packages that you
  install after that will be installed inside this virtualenv, and they will
  take precedence over those of the system (basically, they will be active).
  (use ``deactivate`` to stop using it)


Example
-------

If you want to create a new virtualenv with python3 being used as interpreter
of choice, you would run the following::

    $ mkvirtualenv -p `which python3` bts_tools

Note that after creating it, the virtualenv is already active, so you don't
need to call ``workon bts_tools`` right after creating it. You will have to
do it next time you reboot or open a shell, though.

If you then run the following::

    $ pip install bts_tools

it will install the tools inside the virtualenv, and won't interfere with
your system.


.. _virtualenvs: https://virtualenv.pypa.io/
.. _virtualenvwrapper: https://virtualenvwrapper.readthedocs.io/

