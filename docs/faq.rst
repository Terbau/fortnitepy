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

.. code-block:: python3

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
have created tools to make this easier for others. Here are some of them: 
- `FunGames' API <http://benbotfn.tk:8080/api/docs>`_.
- `NotOfficer's API <https://fortnite-api.com/>`_.


How can I use Two Factor Authentication when logging into the client?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the user the client attempts to log in as requires two factor authentication it 
will ask for the code on startup. Then just type it into console and if accepted, 
the login process will continue.

Alternatively, you might pass the code when intitializing :class:`Client` with the keyword ``two_factor_code``.


How can I fix the "Incompatible net_cl" error?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

    Since fortnitepy v0.9.0 net_cl is not needed and this error will therefore not be an issue.

When fortnite releases a new content update they also update a specific number named netcl needed for the party 
service to work. When updating this lib I also update the net_cl to match the new one. However, since fortnite 
seems to update their game every week I sometimes don't keep up and you have to find and initialize the client 
with the correct one yourself.

**Guide to find netcl:**

1. Navigate to the folder where you find your fortnite logs. Usually something like this: ``C:\Users\%your_user%\AppData\Local\FortniteGame\Saved\Logs``.
2. Go into the latest log file (Typically named ``FortniteGame``).
3. Press ctrl + f and do a search for ``netcl``. You should then find a seven digit number.

**This is how you launch the client with the manual netcl:**

.. code-block::

    # pass the netcl to with the net_cl keyword when initializing the client.
    client = fortnitepy.Client(
        email='email',
        password='password',
        net_cl='7605985'
    )




