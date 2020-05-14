from typing import Any, Optional, Union
from fortnitepy.party import ClientParty, PartyMember, ClientPartyMember
from fortnitepy.friend import Friend
from fortnitepy.user import ClientUser


class Context:
    r"""Represents the context in which a command is being invoked under.

    This class contains a lot of meta data to help you understand more about
    the invocation context. This class is not created manually and is instead
    passed around to commands as the first parameter.

    Attributes
    -----------
    message: Union[:class:`.FriendMessage`, :class:`.PartyMessage`]
        The message that triggered the command being executed.
    bot: :class:`.Bot`
        The bot that contains the command being executed.
    args: :class:`list`
        The list of transformed arguments that were passed into the command.
        If this is accessed during the :func:`event_command_error` event
        then this list could be incomplete.
    kwargs: :class:`dict`
        A dictionary of transformed arguments that were passed into the
        command. Similar to :attr:`args`\, if this is accessed in the
        :func:`event_command_error` event then this dict could be incomplete.
    prefix: :class:`str`
        The prefix that was used to invoke the command.
    command
        The command (i.e. :class:`.Command` or its subclasses) that is being
        invoked currently.
    invoked_with: :class:`str`
        The command name that triggered this invocation. Useful for finding out
        which alias called the command.
    invoked_subcommand
        The subcommand (i.e. :class:`.Command` or its subclasses) that was
        invoked. If no valid subcommand was invoked then this is equal to
        ``None``.
    subcommand_passed: Optional[:class:`str`]
        The string that was attempted to call a subcommand. This does not have
        to point to a valid registered subcommand and could just point to a
        nonsense string. If nothing was passed to attempt a call to a
        subcommand then this is set to ``None``.
    command_failed: :class:`bool`
        A boolean that indicates if the command failed to be parsed, checked,
        or invoked.
    """

    def __init__(self, **attrs: dict) -> None:
        self.message = attrs.pop('message', None)
        self.bot = attrs.pop('bot', None)
        self.args = attrs.pop('args', [])
        self.kwargs = attrs.pop('kwargs', {})
        self.prefix = attrs.pop('prefix')
        self.command = attrs.pop('command', None)
        self.view = attrs.pop('view', None)
        self.invoked_with = attrs.pop('invoked_with', None)
        self.invoked_subcommand = attrs.pop('invoked_subcommand', None)
        self.subcommand_passed = attrs.pop('subcommand_passed', None)
        self.command_failed = attrs.pop('command_failed', False)

    async def invoke(self, *args: list, **kwargs: dict) -> Any:
        r"""|coro|

        Calls a command with the arguments given.

        This is useful if you want to just call the callback that a
        :class:`.Command` holds internally.

        .. note::

            This does not handle converters, checks, cooldowns, pre-invoke,
            or after-invoke hooks in any matter. It calls the internal callback
            directly as-if it was a regular function.

            You must take care in passing the proper arguments when
            using this function.

        .. warning::

            The first parameter passed **must** be the command being invoked.

        Parameters
        -----------
        command: :class:`.Command`
            A command or subclass of a command that is going to be called.
        \*args
            The arguments to to use.
        \*\*kwargs
            The keyword arguments to use.
        """

        try:
            command = args[0]
        except IndexError:
            raise TypeError('Missing command to invoke.') from None

        arguments = []
        if command.cog is not None:
            arguments.append(command.cog)

        arguments.append(self)
        arguments.append(args[1:])

        ret = await command.callback(*args, **kwargs)
        return ret

    async def reinvoke(self, *, call_hooks: bool = False,
                       restart: bool = True) -> None:
        """|coro|

        Calls the command again.

        This is similar to :meth:`~.Context.invoke` except that it bypasses
        checks, cooldowns, and error handlers.

        .. note::
            If you want to bypass :exc:`.UserInputError` derived exceptions,
            it is recommended to use the regular :meth:`~.Context.invoke`
            as it will work more naturally. After all, this will end up
            using the old arguments the user has used and will thus just
            fail again.

        Parameters
        ------------
        call_hooks: :class:`bool`
            Whether to call the before and after invoke hooks.
        restart: :class:`bool`
            Whether to start the call chain from the very beginning
            or where we left off (i.e. the command that caused the error).
            The default is to start where we left off.
        """

        cmd = self.command
        view = self.view
        if cmd is None:
            raise ValueError('This context is not valid.')

        index, previous = view.index, view.previous
        invoked_with = self.invoked_with
        invoked_subcommand = self.invoked_subcommand
        subcommand_passed = self.subcommand_passed

        if restart:
            to_call = cmd.root_parent or cmd
            view.index = len(self.prefix)
            view.previous = 0
            view.get_word()  # advance to get the root command
        else:
            to_call = cmd

        try:
            await to_call.reinvoke(self, call_hooks=call_hooks)
        finally:
            self.command = cmd
            view.index = index
            view.previous = previous
            self.invoked_with = invoked_with
            self.invoked_subcommand = invoked_subcommand
            self.subcommand_passed = subcommand_passed

    @property
    def valid(self) -> bool:
        """:class:`bool`: Checks if the invocation context is valid to be
        invoked with.
        """
        return self.prefix is not None and self.command is not None

    @property
    def cog(self) -> Optional['Cog']:
        """Optional[:class:`.Cog`]: Returns the cog associated with this
        context's command. ``None`` if it does not exist.
        """

        if self.command is None:
            return None

        return self.command.cog

    @property
    def party(self) -> ClientParty:
        """Optional[:class:`fortnitepy.ClientParty`]: The party this message
        was sent from. ``None`` if the message was not sent from a party.
        """
        return getattr(self.message, 'party', None)

    @property
    def author(self) -> Union[Friend, PartyMember]:
        """Optional[:class:`fortnitepy.Friend`, :class:`fortnitepy.PartyMember`]:
        The author of the message.
        """  # noqa
        return self.message.author

    @property
    def me(self) -> Union[ClientPartyMember, ClientUser]:
        """Union[:class:`fortnitepy.ClientPartyMember`, :class:`fortnitepy.ClientUser`]:
        Similar to :attr:`fortnitepy.ClientPartyMember` except that it returns
        :class:`fortnitepy.ClientUser` when not sent from a party.
        """  # noqa
        return self.party.me if self.party is not None else self.bot.user

    def get_destination(self) -> Union[ClientParty, Friend]:
        return self.party if self.party is not None else self.author

    async def send(self, content):
        """|coro|

        Sends a message to the context destination.

        Parameters
        ----------
        content: :class:`str`
            The contents of the message.
        """
        destination = self.get_destination()
        await destination.send(content)

    async def send_help(self, *args: list, page: int = 1) -> Any:
        """send_help(entity=<bot>, page=1)

        |coro|

        Shows the help command for the specified entity if given.
        The entity can be a command or a cog.

        If no entity is given, then it'll show help for the
        entire bot.

        If the entity is a string, then it looks up whether it's a
        :class:`Cog` or a :class:`Command`.

        .. note::

            Due to the way this function works, instead of returning
            something similar to
            :meth:`~.commands.HelpCommand.command_not_found`
            this returns :class:`None` on bad input or no help command.

        Parameters
        ------------
        entity: Optional[Union[:class:`Command`, :class:`Cog`, :class:`str`]]
            The entity to show help for.
        page: :class:`int`
            The page to show. Only has an effect if the entity is either
            the bot or a cog.

        Returns
        --------
        Any
            The result of the help command, if any.
        """

        from .core import Group, Command, wrap_callback
        from .errors import CommandError

        bot = self.bot
        cmd = bot.help_command

        if cmd is None:
            return None

        cmd = cmd.copy()
        cmd.context = self
        if len(args) == 0:
            await cmd.prepare_help_command(self, None)
            injected = wrap_callback(cmd.send_bot_help)
            try:
                return await injected(page=page)
            except CommandError as e:
                await cmd.help_command_error_handler(self, e)
                return None

        entity = args[0]
        if entity is None:
            return None

        if isinstance(entity, str):
            entity = bot.get_cog(entity) or bot.get_command(entity)

        if not hasattr(entity, 'qualified_name'):
            return None

        await cmd.prepare_help_command(self, entity.qualified_name)

        try:
            if hasattr(entity, '__cog_commands__'):
                injected = wrap_callback(cmd.send_cog_help)
                return await injected(entity, page=page)
            elif isinstance(entity, Group):
                injected = wrap_callback(cmd.send_group_help)
                return await injected(entity)
            elif isinstance(entity, Command):
                injected = wrap_callback(cmd.send_command_help)
                return await injected(entity)
            else:
                return None
        except CommandError as e:
            await cmd.help_command_error_handler(self, e)
