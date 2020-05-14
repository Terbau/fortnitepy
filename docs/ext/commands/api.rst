.. currentmodule:: fortnitepy

API Reference
===============

The following section outlines the API of fortnitepy's command extension module.

.. _ext_commands_api_bot:

Bot
----

.. autoclass:: fortnitepy.ext.commands.Bot
    :members:
    :inherited-members:

.. _ext_commands_api_events:

Event Reference
-----------------

These events function similar to :ref:`the regular events <fortnitepy-api-events>`, except they
are custom to the command extension module.

.. function:: on_command_error(ctx, error)

    An error handler that is called when an error is raised
    inside a command either through user input error, check
    failure, or an error in your own code.

    Command error handlers are raised in a specific order. Returning
    ``False`` in any of them will invoke the next handler in the chain. If
    there are no handlers left to call, then the error is printed to
    stderr (console).

    The order goes as follows:
    1. The local command error handler is called. (Handler specified by decorating a command error handler with :meth:`Command.error()`)
    2. The local cog command error handler is called.
    3. All :func:`.event_command_error()` handlers are called
    simultaneously. If any of them return False, then the error will
    be printed.

    :param ctx: The invocation context.
    :type ctx: :class:`.Context`
    :param error: The error that was raised.
    :type error: :class:`.CommandError` derived

.. function:: on_command(ctx)

    An event that is called when a command is found and is about to be invoked.

    This event is called regardless of whether the command itself succeeds via
    error or completes.

    :param ctx: The invocation context.
    :type ctx: :class:`.Context`

.. function:: on_command_completion(ctx)

    An event that is called when a command has completed its invocation.

    This event is called only if the command succeeded, i.e. all checks have
    passed and the user input it correctly.

    :param ctx: The invocation context.
    :type ctx: :class:`.Context`

.. _ext_commands_api_command:

Command
--------

.. autofunction:: fortnitepy.ext.commands.command

.. autofunction:: fortnitepy.ext.commands.group

.. autoclass:: fortnitepy.ext.commands.Command
    :members:
    :special-members: __call__

.. autoclass:: fortnitepy.ext.commands.Group
    :members:
    :inherited-members:

.. autoclass:: fortnitepy.ext.commands.GroupMixin
    :members:

.. _ext_commands_api_cogs:

Cogs
------

.. autoclass:: fortnitepy.ext.commands.Cog
    :members:

.. autoclass:: fortnitepy.ext.commands.CogMeta
    :members:

.. _ext_commands_api_formatters:

Help Commands
-----------------

.. autoclass:: fortnitepy.ext.commands.HelpCommand
    :members:

.. autoclass:: fortnitepy.ext.commands.FortniteHelpCommand
    :members:
    :exclude-members: send_bot_help, send_cog_help, send_group_help, send_command_help, prepare_help_command

.. autoclass:: fortnitepy.ext.commands.Paginator
    :members:

Enums
------

.. class:: fortnitepy.ext.commands.BucketType

    Specifies a type of bucket for, e.g. a cooldown.

    .. attribute:: default

        The default bucket operates on a global basis.
    .. attribute:: user

        The user bucket operates on a per-user basis.


.. _ext_commands_api_checks:

Checks
-------

.. autofunction:: fortnitepy.ext.commands.check

.. autofunction:: fortnitepy.ext.commands.check_any

.. autofunction:: fortnitepy.ext.commands.cooldown

.. autofunction:: fortnitepy.ext.commands.max_concurrency

.. autofunction:: fortnitepy.ext.commands.before_invoke

.. autofunction:: fortnitepy.ext.commands.after_invoke

.. autofunction:: fortnitepy.ext.commands.party_only

.. autofunction:: fortnitepy.ext.commands.dm_only

.. autofunction:: fortnitepy.ext.commands.is_owner

.. _ext_commands_api_context:

Context
--------

.. autoclass:: fortnitepy.ext.commands.Context
    :members:
    :inherited-members:

.. _ext_commands_api_converters:

Converters
------------

.. autoclass:: fortnitepy.ext.commands.Converter
    :members:

.. autoclass:: fortnitepy.ext.commands.UserConverter
    :members:

.. autoclass:: fortnitepy.ext.commands.FriendConverter
    :members:

.. autoclass:: fortnitepy.ext.commands.PartyMemberConverter
    :members:

.. data:: ext.commands.Greedy

    A special converter that greedily consumes arguments until it can't.
    As a consequence of this behaviour, most input errors are silently discarded,
    since it is used as an indicator of when to stop parsing.

    When a parser error is met the greedy converter stops converting, undoes the
    internal string parsing routine, and continues parsing regularly.

    For example, in the following code:

    .. code-block:: python3

        @commands.command()
        async def test(ctx, numbers: Greedy[int], reason: str):
            await ctx.send("numbers: {}, reason: {}".format(numbers, reason))

    An invocation of ``[p]test 1 2 3 4 5 6 hello`` would pass ``numbers`` with
    ``[1, 2, 3, 4, 5, 6]`` and ``reason`` with ``hello``\.

    For more information, check :ref:`ext_commands_special_converters`.

.. _ext_commands_api_errors:

Exceptions
-----------

.. autoexception:: fortnitepy.ext.commands.CommandError
    :members:

.. autoexception:: fortnitepy.ext.commands.ConversionError
    :members:

.. autoexception:: fortnitepy.ext.commands.MissingRequiredArgument
    :members:

.. autoexception:: fortnitepy.ext.commands.ArgumentParsingError
    :members:

.. autoexception:: fortnitepy.ext.commands.UnexpectedQuoteError
    :members:

.. autoexception:: fortnitepy.ext.commands.InvalidEndOfQuotedStringError
    :members:

.. autoexception:: fortnitepy.ext.commands.ExpectedClosingQuoteError
    :members:

.. autoexception:: fortnitepy.ext.commands.BadArgument
    :members:

.. autoexception:: fortnitepy.ext.commands.BadUnionArgument
    :members:

.. autoexception:: fortnitepy.ext.commands.PrivateMessageOnly
    :members:

.. autoexception:: fortnitepy.ext.commands.PartyMessageOnly
    :members:

.. autoexception:: fortnitepy.ext.commands.CheckFailure
    :members:

.. autoexception:: fortnitepy.ext.commands.CheckAnyFailure
    :members:

.. autoexception:: fortnitepy.ext.commands.CommandNotFound
    :members:

.. autoexception:: fortnitepy.ext.commands.DisabledCommand
    :members:

.. autoexception:: fortnitepy.ext.commands.CommandInvokeError
    :members:

.. autoexception:: fortnitepy.ext.commands.TooManyArguments
    :members:

.. autoexception:: fortnitepy.ext.commands.UserInputError
    :members:

.. autoexception:: fortnitepy.ext.commands.CommandOnCooldown
    :members:

.. autoexception:: fortnitepy.ext.commands.MaxConcurrencyReached
    :members:

.. autoexception:: fortnitepy.ext.commands.NotOwner
    :members:

.. autoexception:: fortnitepy.ext.commands.ExtensionError
    :members:

.. autoexception:: fortnitepy.ext.commands.ExtensionAlreadyLoaded
    :members:

.. autoexception:: fortnitepy.ext.commands.ExtensionNotLoaded
    :members:

.. autoexception:: fortnitepy.ext.commands.ExtensionMissingEntryPoint
    :members:

.. autoexception:: fortnitepy.ext.commands.ExtensionFailed
    :members:

.. autoexception:: fortnitepy.ext.commands.ExtensionNotFound
    :members:
