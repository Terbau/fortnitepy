.. currentmodule:: fortnitepy

Frequently Asked Questions (FAQ)
================================

.. contents:: Questions
    :local:

General
-------

How can I get a users K/D or Win Percentage?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since the stats request does not return a K/D or win percentage, you must
calculate them yourself. Just to make it easy :class:`StatsV2` includes 
functions that calculates these values for you.

Take a closer look at :meth:`StatsV2.get_kd` and 
:meth:`StatsV2.get_winpercentage`.

How can I set a status?
~~~~~~~~~~~~~~~~~~~~~~~
You can pass a status message for the client to use when creating 
client. 

.. code-block::

    client = fortnitepy.Client(
        email="email@email.com,
        password="password1",
        status="This is my status"
    )

.. warning::

    This will override all status messages in the future. The standard
    status message (``Battle Royale Lobby {party size} / {party max size}``)
    will also be overridden. If you just want to send a status message once
    and not override all upcoming status messages, :meth:`Client.send_status`
    is the function you are looking for.

Alternatively you can change the presence with :meth:`Client.set_status`.


How can I get the CID of skin?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There is no good easy way to obtain these yourself. However, some great minds
have created tools to make this easier for others. One of these tools is  
`FunGames' API
<http://benbotfn.tk:8080/api/docs>`_.


How can I use Two Factor Authentication when logging into the client?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Currently this is not possible in fortnitepy. This is a planned feature though!




