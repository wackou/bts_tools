
Monitoring web app
==================

Launch the monitoring web app locally
-------------------------------------

The main entry point to the monitoring app is the ``~/.bts_tools/config.yaml``
file. You should edit it first and set the values to correspond to your
delegate's configuration. See the :doc:`config_format` page for details.

If this file doesn't exist yet, run the tools
once (for instance: ``bts -h``) and it will create a default one.

To run the debug/development monitoring web app, just do the following:

::

    $ bts monitor

and it will launch on ``localhost:5000``.


.. _production server:

Setting up on a production server
---------------------------------

For production deployments, it is recommended to put it behind a WSGI
server, in which case the entry point is
``bts_tools.wsgi:application``.

Do not forget to edit the ``~/.bts_tools/config.yaml`` file to configure
it to suit your needs.

Example
~~~~~~~

We will run the monitoring tools using nginx as frontend. Install using::

    # apt-get install nginx uwsgi uwsgi-plugin-python3

The tools will have to be run from a virtualenv, so let's create it::

    $ mkvirtualenv -p `which python3` bts_tools
    $ pip3 install bts_tools

Edit the following configuration files:

``/etc/uwsgi/apps-available/bts_tools.ini`` (need symlink to ``/etc/uwsgi/apps-enabled/bts_tools.ini``)
::

    [uwsgi]
    uid = myuser
    gid = mygroup
    chmod-socket = 666
    plugin = python34
    virtualenv = /home/myuser/.virtualenvs/bts_tools
    enable-threads = true
    lazy-apps = true
    workers = 1
    module = bts_tools.wsgi
    callable: application

``/etc/nginx/sites-available/default`` (need symlink to ``/etc/nginx/sites-enabled/default``)
::

    server {
            listen 80;
            server_name myserver.com;
            charset utf-8;
            location / { try_files $uri @bts_tools; }
            location @bts_tools {
                    # optional password protection
                    #auth_basic "Restricted";
                    #auth_basic_user_file /home/myuser/.htpasswd;
                    include uwsgi_params;
                    uwsgi_pass unix:/run/uwsgi/app/bts_tools/socket;
            }
    }

After having changed those files, you should::

    # service uwsgi restart
    # service nginx restart


Screenshots
-----------

Monitoring the status of your running bts client binary:

.. image:: ../bts_tools_screenshot.png
   :alt: Status screenshot

|

You can host multiple delegates accounts in the same wallet, and check feed info:

.. image:: ../bts_tools_screenshot2.png
   :alt: Info screenshot

|
|

Monitoring multiple instances (ie: running on different hosts) at the same time,
to have an overview while running backup nodes and re-compiling your main node:

.. image:: ../bts_tools_screenshot3.png
   :alt: Info screenshot
