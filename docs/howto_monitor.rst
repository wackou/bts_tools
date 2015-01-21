
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

