
Format of the config.yaml file
==============================

The ``config.yaml`` file contains the configuration about the delegates. It
contains the following main sections:


Build environments
------------------

These are the types of clients that you can build. ``bts``, ``dvs``, ``pts``, etc.
Mostly the default should work and you shouldn't change those values.


Run environments
----------------

These represent the clients that you can run. The default should mostly work, here
but you may want to edit them if you want to have multiple instances of the client
running, for instance a delegate node and a seed node.

The clients define the following variables:
 - **type**: the type of build you want to run. Needs to be a valid build env (ie: bts, pts, ...)
 - **debug**: set to true to run client in gdb (only available in linux for now)
 - **data_dir**: *[optional]* the data dir (blockchain, wallet, etc.) of the bts client. If not
   specified, uses the standard location of the client
 - **run_args**: *[optional]* any additional flags you want to pass to the cmdline invocation of the client

To run a specific client, type::

    $ bts run client_name

If you don't specify a client on the command-line (ie: ``bts run``), the tools will
run the client using the ``bts`` run environment by default.

Example
~~~~~~~

::

    run_environments:
        seed-bts:
            type: bts
            debug: false
            run_args: ['--p2p-port', '1778', '--clear-peer-database']

This allows you to run a seed node on port 1778, and clear its peer database
each time you run it.


Nodes list
----------

This is the part that you should edit to configure it to your needs.

In the ``nodes`` variable you should specify the list of delegate accounts that
you want the tools to monitor.

For each node, you need to specify the following attributes:

- ``client``: the client being monitored. This needs to be a valid run environment, and
  will allow to fetch the RPC parameters automatically. If you don't specify it, you need
  to fill in the ``rpc_host``, ``rpc_port``, ``rpc_user``, ``rpc_password`` and ``venv_path``
  instead. You will need ssh access if it is a remote host. **TODO:** expand doc about ssh
- ``type``: the type of the node being monitored. Either ``seed``, ``delegate`` or ``backbone``
- ``name``: the name of the node (delegate account name)
- ``monitoring``: the list of monitoring plugins that should be run on this node
- ``notification``: the type of notification to be sent for events of this node

Nodes can be of 3 types:

- delegate nodes
- seed nodes
- backbone nodes

The choice of node type will tune a bit the interface and enable/disable
functionality, such as feed publishing for delegates but not for seed nodes
or backbone nodes


Monitoring plugins
~~~~~~~~~~~~~~~~~~

For each node you can specify which type of monitoring you want:

- ``seed``: will set the number of desired/max connections as specified in the ``monitoring`` config section
- ``backbone``: will check that the backbone node runs as intended
- ``feeds``: check price feeds, and optionally publish them if the node is a delegate
- ``version``: check if version number matches published one, publishes it otherwise
- ``missed``: check for missed blocks for a delegate
- ``network_connections``: check that number of active connections to the network is higher than a threshold
- ``payroll``: periodically distribute delegate pay amongst the configured accounts in the ``monitoring`` section.
- ``wallet_state``: check when wallet is opened/closed and locked/unlocked
- ``fork``: tries to detect whether client is being moved to a minority fork
- ``voted_in``: check when a delegate is voted in/out

You can also use the following special monitoring plugins as wildcards:

- ``delegate``: use for monitoring a full-fledged delegate. It will activate the following plugins: ``missed``,
  ``network_connections``, ``voted_in``, ``wallet_state``, ``fork``, ``version``, ``feeds``
- ``inactive_delegate``: use for monitoring a delegate without publishing any information (feeds or version).
  It will activate the following plugins: ``missed``, ``network_connections``, ``voted_in``, ``wallet_state``, ``fork``


Notification plugins
~~~~~~~~~~~~~~~~~~~~

You should also configure which type of notification you want to receive:

- ``email``: send an email notification when client crashes or loses network connections
- ``boxcar``: send an iOS push notification to the Boxcar app when client crashes or loses network connections


Example
~~~~~~~

::

    nodes:
        -
            client: bts
            type: delegate          # delegate node type: run a single delegate account
            name: delegate1         # the name of the delegate. This needs to be an existing account
            monitoring: [delegate]  # activate default monitoring plugins for delegate
            notification: [email]
        -
            type: seed       # seed node type: no need for open wallet, high number of connections
            name: seed01     # the name for this seed node. This is just for you, it serves no other purpose
            # you can specify the rpc connection params. This will override the values
            # from the data directory
            rpc_port: 5678
            rpc_user: username
            rpc_password: secret-password
            monitoring: [seed, network_connections]
        -
            type: delegate   # remote delegate node type: access to a remote node's delegate info. You need to have ssh access to this node for this to work
            name: delegate3  # the name for this remote node. This is just for you, it serves no other purpose
            venv_path: ~/.virtualenvs/bts_tools # virtualenv dir in which the bts tools are installed on the remote machine
            rpc_host: user@myhost  # hostname. Anything you can pass to "ssh" you can put here (eg: your aliases in ~/.ssh/config)
            rpc_port: 5678
            rpc_user: username
            rpc_password: secret-password


Monitoring plugins configuration
--------------------------------

In the ``monitoring`` section comes the configuration of the various monitoring
plugins. Configure to your taste!


Notifications
-------------

In the ``notification`` section, you will be able to configure how notifications
will be sent to you. There are 2 ways of being notified: ``email`` and ``boxcar``
(iOS push notifications).
