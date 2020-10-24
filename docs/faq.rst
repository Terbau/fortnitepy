.. currentmodule:: fortnitepy

Frequently Asked Questions (FAQ)
================================

.. contents:: Questions
    :local:

Authentication
--------------

Why are there so many different authentication methods?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the introduction of captcha on email and password authentication, there was
a need of different ways to authenticate. Therefore, fortnitepy tries to offer
as many different authentication methods as possible. You can read more about the
different possibilities over `here <https://github.com/MixV2/EpicResearch/tree/master/docs/auth/grant_types>`_.


Which authentication method should I use?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The answer to this question depends completely on what information you already
have, but it usually comes down to :class:`AdvancedAuth` no matter what. It's
simply the best right now as it combines other authentication methods and handles
all of the annoying stuff like creating device auths etc. If you are unsure how to
use :class:`AdvancedAuth`, you can take a look at the `examples folder <https://github.com/Terbau/fortnitepy/tree/master/examples>`_
where it's used in all of the examples.


Whats the best way of storing the device auth details of an account?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This depends on the complexity of the bot with multiple accounts in mind. For
a program running a single bot, the easiest method of storage would be using
a json file. A method for this is showcased in all `examples <https://github.com/Terbau/fortnitepy/tree/master/examples>`_.

For bots with multiple accounts I suggest using a database for the single reason
that file io is blocking and sometimes the operating system might spit out
errors because too many files are opened at the same time. 

**Note:** If you're going to use a database for anything in the same program as
the fortnite bot, please use an asynchronous database library. I can personally
recommend using a postgresql database and `asyncpg <https://github.com/MagicStack/asyncpg>`_
as the library.


General
-------

What is async/await and how do I use it?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Asynchronous programming lets the program sort of perform multiple actions at
once. For newcomers to python/programming in general, the `discord.py faq <https://benbot.stoplight.io/docs/benbot-docs>`_
has a great simplified explanation of its basic concepts. For people with existing
knowledge of asynchronous programming that want to know even more about it, I can
suggest `this article <https://realpython.com/async-io-python/>`_ on it. As well as
breakign down pretty much all you need to know about asynchronous programming, it
also explains the differences between multiprocessing, threading and asyncio in python
in an understandable way.


Where can I find usage examples?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can find example code in the `examples folder <https://github.com/Terbau/fortnitepy/tree/master/examples>`_
in the github repository.


How can I access the clients current party object?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The clients current party object can be accessed through :attr:`Client.party`.


How can I access the clients current party member object?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The clients current party member object can be accessed through :attr:`ClientParty.me`.
Example usage: ``await client.party.me.set_emote('EID_Floss')``


How can I send a DM?
~~~~~~~~~~~~~~~~~~~~

To send a DM you first need the :class:`Friend` object of the friend you
want to send the dm to and then use :meth:`Friend.send()`. Example: ::

    friend = client.get_friend('7e9f8dd37a924496bc5083733887b44c')
    await friend.send('Hello friend!')

If you want to respond to a friend message in :func:`event_friend_message()`, you
can do this by using :meth:`FriendMessage.reply()`. Example: ::

    @client.event
    async def event_friend_message(message):
        await message.reply('Thanks for the message!')

        # Not as clean but would still work:
        await message.author.send('Thanks for the message!')


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
    and not override all upcoming status messages, :meth:`Client.send_presence`
    is the function you are looking for.

Alternatively you can change the presence with :meth:`Client.set_presence`.


How can I get the CID of a skin?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There is no good easy way to obtain these yourself. However, some great minds
have created tools to make this easier for others. Here are some of them: 
- `FunGames' API <https://benbot.stoplight.io/docs/benbot-docs>`_.
- `NotOfficer's API <https://fortnite-api.com/>`_.


How can I use Two Factor Authentication when logging into the client?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If the user the client attempts to log in as requires two factor authentication, the code will
be prompted in console on startup. Then just type it into console and if accepted, 
the login process will continue.

Alternatively, you might pass the code when intitializing :class:`Client` with the keyword ``two_factor_code``.


How can I get a users K/D or Win Percentage?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since the stats request does not return a K/D or win percentage, you must
calculate them yourself. Just to make it easy :class:`StatsV2` includes 
functions that calculates these values for you.

Take a closer look at :meth:`StatsV2.get_kd` and 
:meth:`StatsV2.get_winpercentage`.


How can I fix the "Incompatible net_cl" error?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note::

    Since fortnitepy v0.9.0 net_cl is not needed and this error will therefore not be an issue. For legacy and possibly
    future use, it will remain in the faq.

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




