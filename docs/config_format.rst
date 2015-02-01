
Format of the config.yaml file
==============================

The ``config.yaml`` file contains the configuration about the delegates. There
are 3 main sections:


Build environments
------------------

These are the types of clients that you can build. ``bts``, ``dvs``, ``pts``, etc.
Mostly the default should work and you shouldn't change those values.


Run environments
----------------

These represent the clients that you can run. The default should mostly work, here
but you may want to edit it if you want to have multiple instances of the client
running, for instance a delegate node and a seed node.


Nodes list
----------

This is the part that you should edit to configure it to your needs.

In the ``nodes`` variable you should specify the list of delegate accounts that
you want the tools to monitor.

Nodes can be of 2 types:

- seed nodes
- delegate nodes

The choice of node type will tune a bit the interface and enable/disable
functionality, such as feed publishing for delegates but not for seed nodes

Delegate nodes can either be on ``localhost``, or on a different host.
In that case, you need ssh access to the remote host where you also have the
bts_tools installed in a virtualenv. TODO: expand doc about ssh

For each node you can specify which type of monitoring you want:

- ``feeds``: check price feeds, and optionally publish them if the node is a delegate
- ``version``: check if version number matches published one, publishes it otherwise
- ``email``: send an email notification when client crashes or loses network connections
- ``boxcar``: send an iOS push notification to the Boxcar app when client crashes or loses network connections

Example
~~~~~~~

::

    nodes:
        -
            # you must specify the run environment of the client
            # this will fetch rpc connections params automatically
            # NOTE: this needs to be a valid run environment!
            client: bts
            type: delegate   # delegate node type: run a single delegate account
            name: delegate1  # the name of the delegate. This needs to be an existing account
            monitoring: [version,feeds,email]
        -
            client: bts
            type: seed    # seed node type: no need for open wallet, high number of connections
            name: seed01  # the name for this seed node. This is just for you, it serves no other purpose
            desired_number_of_connections: 200
            maximum_number_of_connections: 400
            # you can specify the rpc connection params. This will override the values
            # from the data directory
            rpc_port: 5678
            rpc_user: username
            rpc_password: secret-password
            monitoring: [email]
        -
            client: bts
            type: delegate   # remote delegate node type: access to a remote node's delegate info. You need to have ssh access to this node for this to work
            name: delegate3  # the name for this remote node. This is just for you, it serves no other purpose
            venv_path: ~/.virtualenvs/bts_tools # virtualenv dir in which the bts tools are installed on the remote machine
            rpc_host: user@myhost  # hostname. Anything you can pass to "ssh" you can put here (eg: your aliases in ~/.ssh/config)
            rpc_port: 5678
            rpc_user: username
            rpc_password: secret-password

