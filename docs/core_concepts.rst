
Core concepts / architecture
============================

In order to better understand how the tools are structured and work internally, here are a few
key concepts that should be understood:


- there are a number of blockchains for which we know a git repo that we can use to build a client.
  these are called "build environments", and currently can be any one of [bts, steem, ppy, muse]
- when a binary is compiled, you want to run an instance of it. This is called a "client" and
  each has its own data dir, network ports, etc. so you can run more than 1 simultaneously.
- furthermore, each client can assume 1 or more "roles", which describe its function to the
  network and will tune the client in order to better fulfill it.
  Currently: [witness, feed_publisher, seed]   # planned: API node



Build environments
------------------

These are the types of clients that you can build. ``bts``, ``steem``, ``ppy``, etc.

The full list can be found here:
https://github.com/wackou/bts_tools/blob/master/bts_tools/templates/config/build_environments.yaml


Clients
-------


A client definition contains all the information needed to launch a witness client,
a cli_wallet that connects to it, and have the bts_tools web app monitor all of it.

A client has a name and defines at least the following properties:

 - **type**: the type of build you want to run. Needs to be a valid build env (ie: bts, steem, ...)
 - **data_dir**: *[required]* the data dir (blockchain, wallet, etc.) of the bts client
 - **api_access**: the location of the api_access.json file. It contains authentication data for the RPC communication and needs to be created according to `this spec <https://github.com/bitshares/bitshares-core#accessing-restricted-apis>`_
 - **witness_user**: user for authentication with the witness client
 - **witness_password**: password for authentication with the witness client


A list of default clients can be found here: https://github.com/wackou/bts_tools/blob/master/bts_tools/templates/config/clients.yaml


To run a specific client, type::

    $ bts run client_name

If you don't specify a client on the command-line (ie: ``bts run``), the tools will
run the client using the ``bts`` run environment by default.



Roles
-----

The roles are the main mechanism with which you control what type of monitoring plugins are
launched for a given client.

Roles also contain additional information (e.g.: witness name, id and signing key) that allow
the client to be monitored more efficiently (the web UI will show whether a witness signing key
is currently active, for instance)

A client can assume one or more roles, and these are the roles that you can use:

- the **witness** role monitors a valid witness on the network, whether it is signing blocks
  (ie: its signing key is active) and activates the following monitoring plugins:
  ``missed``, ``voted_in``, ``wallet_state``, ``network_connections``, ``fork``

- the **feed_publisher** role activates the ``feeds`` monitoring plugin that checks feed prices
  on external feed providers and publishes an aggregate price on the blockchain.
  Note: for feed publishing to work, you need to have an unlocked wallet in order to be able
  to publish the transaction.

- the **seed** role activates the ``seed``, ``network_connections`` and ``fork`` monitoring plugin
  which will make the client monitor network health and increase its number of connections to higher
  than normal in order to better serve as an entry point to the network



Monitoring plugins
~~~~~~~~~~~~~~~~~~

As a reference, here are the monitoring plugins that can be activated via the roles:

- ``seed``: will set the number of desired/max connections as specified in the ``monitoring`` config section
- ``feeds``: check price feeds and publish them
- ``missed``: check for missed blocks for a witness
- ``network_connections``: check that number of active connections to the network is higher than a threshold
- ``payroll``: periodically distribute delegate pay amongst the configured accounts in the ``monitoring`` section.
- ``wallet_state``: check when wallet is opened/closed and locked/unlocked
- ``fork``: tries to detect whether client is being moved to a minority fork
- ``voted_in``: check when a witness is voted in/out
- ``cpu_ram_usage``: always active, monitor CPU and RAM usage of the witness client
- ``free_disk_space``: always active, check whether the amount of free disk space falls below a threshold

