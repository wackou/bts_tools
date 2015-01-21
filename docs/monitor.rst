
Monitoring web app
==================

To run the debug/development monitoring web app, just do the following:

::

    $ bts monitor

and it will launch on ``localhost:5000``.

For production deployments, it is recommended to put it behind a WSGI
server, in which case the entry point is
``bts_tools.wsgi:application``.

Do not forget to edit the ``~/.bts_tools/config.yaml`` file to configure
it to suit your needs.

Screenshots
~~~~~~~~~~~

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
to have an overview while running backup nodes and re-compiling your main node.:

.. image:: ../bts_tools_screenshot3.png
   :alt: Info screenshot
