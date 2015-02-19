
Build and run the BitShares client
==================================

To build the BitShares client, just type the following::

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
Please refer to the `BitShares wiki <http://wiki.bitshares.org/index.php/Delegate/How-To>`_
for instructions.

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

.. note:: The keyboard shortcuts are somewhat arcane, but this is the bare minimum you have to remember:

   when outside of tmux:

   - ``tmux`` : create a new tmux session
   - ``tmux attach`` : re-attach to a running session

   when inside of tmux:

   - ``ctrl+b d`` : detach the session - do this before disconnecting from your server
   - ``ctrl+b [`` : enter "scrolling mode" - you can scroll back the screen (normal arrows and sliders from
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

