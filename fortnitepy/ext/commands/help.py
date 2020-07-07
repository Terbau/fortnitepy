import copy
import functools
import inspect
import re
import unicodedata

from collections import OrderedDict
from typing import (TYPE_CHECKING, Any, List, Dict, Optional, Iterable,
                    Callable, Sequence, Union, Tuple)
from fortnitepy.typedefs import MaybeCoro
from fortnitepy.party import ClientParty
from fortnitepy.friend import Friend

from .core import Group, Command
from .errors import CommandError
from .context import Context
from .cog import Cog

if TYPE_CHECKING:
    from .bot import Bot


__all__ = (
    'Paginator',
    'HelpCommand',
    'FortniteHelpCommand',
)

_IS_ASCII = re.compile(r'^[\x00-\x7f]+$')


def _string_width(string: str, *, _IS_ASCII: Any = _IS_ASCII) -> int:
    """Returns string's width."""
    match = _IS_ASCII.match(string)
    if match:
        return match.endpos

    UNICODE_WIDE_CHAR_TYPE = 'WFA'
    width = 0
    func = unicodedata.east_asian_width
    for char in string:
        width += 2 if func(char) in UNICODE_WIDE_CHAR_TYPE else 1
    return width


async def maybe_coroutine(func: MaybeCoro,
                          *args: list,
                          **kwargs: dict) -> Any:
    value = func(*args, **kwargs)
    if inspect.isawaitable(value):
        return await value
    else:
        return value


class Paginator:
    """A class that aids in paginating code blocks for Fortnite messages.

    .. container:: operations

        .. describe:: len(x)
            Returns the total number of characters in the paginator.

    Attributes
    -----------
    prefix: :class:`str`
        The prefix inserted to every page.
    suffix: :class:`str`
        The suffix appended at the end of every page.
    max_size: :class:`int`
        The maximum amount of codepoints allowed in a page.
    """

    def __init__(self, prefix: str = '',
                 suffix: str = '',
                 max_size: int = 10000) -> None:
        self.prefix = prefix
        self.suffix = suffix
        self.max_size = max_size
        self.clear()

    def clear(self) -> None:
        """Clears the paginator to have no pages."""
        if self.prefix is not None:
            self._current_page = [self.prefix]
            self._count = len(self.prefix)
        else:
            self._current_page = []
            self._count = 0

        self._pages = []

    @property
    def _prefix_len(self) -> int:
        return len(self.prefix) if self.prefix else 0

    @property
    def _suffix_len(self) -> int:
        return len(self.suffix) if self.suffix else 0

    def add_page(self, text: str) -> None:
        """Adds a page to the paginator with no additional checks done."""
        self._pages.append(text)

    def add_line(self, line: str = '', *, empty: bool = False) -> None:
        """Adds a line to the current page.

        If the line exceeds the :attr:`max_size` then an exception
        is raised.

        Parameters
        -----------
        line: :class:`str`
            The line to add.
        empty: :class:`bool`
            Indicates if another empty line should be added.

        Raises
        ------
        RuntimeError
            The line was too big for the current :attr:`max_size`.
        """
        max_page_size = self.max_size - self._prefix_len - self._suffix_len
        if len(line) > max_page_size:
            raise RuntimeError('Line exceeds maximum page size '
                               '{}'.format(max_page_size))

        if self._count + len(line) + 1 > self.max_size - self._suffix_len:
            self.close_page()

        self._count += len(line) + 1
        self._current_page.append(line)

        if empty:
            self._current_page.append('')
            self._count += 1

    def close_page(self) -> None:
        """Prematurely terminate a page."""

        if self.suffix is not None:
            self._current_page.append(self.suffix)

        self._pages.append('\n'.join(self._current_page))

        if self.prefix is not None:
            self._current_page = []
            self._count = len(self.prefix)
        else:
            self._current_page = []
            self._count = 0

    def __len__(self) -> int:
        total = sum(len(p) for p in self._pages)
        return total + self._count

    @property
    def pages(self) -> List[str]:
        """Returns the rendered list of pages."""

        if len(self._current_page) > (0 if self.prefix is None else 1):
            self.close_page()

        return self._pages

    def __repr__(self) -> str:
        fmt = ('<Paginator prefix: {0.prefix} suffix: {0.suffix} max_size: '
               '{0.max_size} count: {0._count}>')
        return fmt.format(self)


def _not_overridden(func: MaybeCoro) -> MaybeCoro:
    func.__fnpy_help_command_not_overridden__ = True
    return func


class _HelpCommandImpl(Command):
    def __init__(self, inject: Command, *args: list, **kwargs: dict) -> None:
        super().__init__(inject.command_callback, *args, **kwargs)
        self._original = inject
        self._injected = inject

    async def prepare(self, ctx: Context) -> None:
        self._injected = injected = self._original.copy()
        injected.context = ctx
        self.callback = injected.command_callback

        error_handler = injected.help_command_error_handler
        if not hasattr(error_handler, '__fnpy_help_command_not_overridden__'):
            if self.cog is not None:
                self.error_handler = self._error_handler_cog_implementation
            else:
                self.error_handler = error_handler

        await super().prepare(ctx)

    async def _parse_arguments(self, ctx: Context) -> None:
        # Make the parser think we don't have a cog so it doesn't
        # inject the parameter into `ctx.args`.
        original_cog = self.cog
        self.cog = None
        try:
            await super()._parse_arguments(ctx)
        finally:
            self.cog = original_cog

    async def _error_handler_cog_implementation(self, _,
                                                ctx: Context,
                                                error: Exception) -> None:
        await self._injected.help_command_error_handler(ctx, error)

    @property
    def clean_params(self) -> OrderedDict:
        result = self.params.copy()
        try:
            result.popitem(last=False)
        except Exception:
            raise ValueError('Missing context parameter') from None
        else:
            return result

    def _inject_into_cog(self, cog: Cog) -> None:
        # Warning: hacky

        # Make the cog think that get_commands returns this command
        # as well if we inject it without modifying __cog_commands__
        # since that's used for the injection and ejection of cogs.
        def wrapped_get_commands(*, _original=cog.get_commands):
            ret = _original()
            ret.append(self)
            return ret

        # Ditto here
        def wrapped_walk_commands(*, _original=cog.walk_commands):
            yield from _original()
            yield self

        functools.update_wrapper(wrapped_get_commands, cog.get_commands)
        functools.update_wrapper(wrapped_walk_commands, cog.walk_commands)
        cog.get_commands = wrapped_get_commands
        cog.walk_commands = wrapped_walk_commands
        self.cog = cog

    def _eject_cog(self) -> None:
        if self.cog is None:
            return

        # revert back into their original methods
        cog = self.cog
        cog.get_commands = cog.get_commands.__wrapped__
        cog.walk_commands = cog.walk_commands.__wrapped__
        self.cog = None


class HelpCommand:
    r"""The base implementation for help command formatting.

    .. note::

        Internally instances of this class are deep copied every time
        the command itself is invoked to prevent a race condition
        mentioned in discord.py issue 2123.

        This means that relying on the state of this class to be
        the same between command invocations would not work as expected.

    Attributes
    -----------
    context: Optional[:class:`Context`]
        The context that invoked this help formatter. This is generally set
        after the help command assigned, :func:`command_callback`\, has been
        called.
    show_hidden: :class:`bool`
        Specifies if hidden commands should be shown in the output.
        Defaults to ``False``.
    verify_checks: :class:`bool`
        Specifies if commands should have their :attr:`.Command.checks` called
        and verified. Defaults to ``True``.
    command_attrs: :class:`dict`
        A dictionary of options to pass in for the construction of the help
        command. This allows you to change the command behaviour without
        actually changing the implementation of the command. The attributes
        will be the same as the ones passed in the :class:`.Command`
        constructor.
    """

    def __new__(cls, *args: list, **kwargs: dict) -> 'HelpCommand':
        # To prevent race conditions of a single instance while also allowing
        # for settings to be passed the original arguments passed must be
        # assigned to allow for easier copies (which will be made when the
        # help command is actually called)
        # see discord.py issue 2123
        self = super().__new__(cls)

        # Shallow copies cannot be used in this case since it is not unusual
        # to pass instances that need state, e.g. Paginator or what have you
        # into the function. The keys can be safely copied as-is since they're
        # 99.99% certain of being string keys
        deepcopy = copy.deepcopy
        self.__original_kwargs__ = {
            k: deepcopy(v)
            for k, v in kwargs.items()
        }
        self.__original_args__ = deepcopy(args)
        return self

    def __init__(self, **options: dict) -> None:
        self.show_hidden = options.pop('show_hidden', False)
        self.verify_checks = options.pop('verify_checks', True)
        self.command_attrs = attrs = options.pop('command_attrs', {})
        attrs.setdefault('name', 'help')
        attrs.setdefault('help', 'Shows this message')
        self.context = None
        self._command_impl = None

    def copy(self) -> 'HelpCommand':
        o = self.__class__(*self.__original_args__, **self.__original_kwargs__)
        o._command_impl = self._command_impl
        return o

    def _add_to_bot(self, bot: 'Bot') -> None:
        command = _HelpCommandImpl(self, **self.command_attrs)
        bot.add_command(command)
        self._command_impl = command

    def _remove_from_bot(self, bot: 'Bot') -> None:
        bot.remove_command(self._command_impl.name)
        self._command_impl._eject_cog()
        self._command_impl = None

    def get_bot_mapping(self) -> Dict[Optional[Cog], List[Command]]:
        """Retrieves the bot mapping passed to :meth:`send_bot_help`."""
        bot = self.context.bot
        mapping = {
            cog: cog.get_commands()
            for cog in bot.cogs.values()
        }
        mapping[None] = [c for c in bot.all_commands.values() if c.cog is None]
        return mapping

    @property
    def command_prefix(self) -> str:
        """The prefix used to invoke the help command."""
        return self.context.prefix

    @property
    def invoked_with(self) -> str:
        """Similar to :attr:`Context.invoked_with` except properly handles
        the case where :meth:`Context.send_help` is used.

        If the help command was used regularly then this returns
        the :attr:`Context.invoked_with` attribute. Otherwise, if
        it the help command was called using :meth:`Context.send_help`
        then it returns the internal command name of the help command.

        Returns
        ---------
        :class:`str`
            The command name that triggered this invocation.
        """

        command_name = self._command_impl.name
        ctx = self.context
        if (ctx is None or ctx.command is None
                or ctx.command.qualified_name != command_name):
            return command_name
        return ctx.invoked_with

    def get_command_signature(self, command: Command) -> str:
        """Retrieves the signature portion of the help page.

        Parameters
        ----------
        command: :class:`Command`
            The command to get the signature of.

        Returns
        -------
        :class:`str`
            The signature for the command.
        """

        parent = command.full_parent_name
        if len(command.aliases) > 0:
            aliases = '|'.join(command.aliases)
            fmt = '[%s|%s]' % (command.name, aliases)
            if parent:
                fmt = parent + ' ' + fmt
            alias = fmt
        else:
            alias = command.name if not parent else parent + ' ' + command.name

        return '%s%s %s' % (self.command_prefix, alias, command.signature)

    @property
    def cog(self) -> Optional[Cog]:
        """A property for retrieving or setting the cog for the help command.

        When a cog is set for the help command, it is as-if the help command
        belongs to that cog. All cog special methods will apply to the help
        command and it will be automatically unset on unload.

        To unbind the cog from the help command, you can set it to ``None``.

        Returns
        --------
        Optional[:class:`Cog`]
            The cog that is currently set for the help command.
        """
        return self._command_impl.cog

    @cog.setter
    def cog(self, cog: Cog) -> None:
        # Remove whatever cog is currently valid, if any
        self._command_impl._eject_cog()

        # If a new cog is set then inject it.
        if cog is not None:
            self._command_impl._inject_into_cog(cog)

    def command_not_found(self, string: str) -> str:
        """|maybecoro|

        A method called when a command is not found in the help command.
        This is useful to override for i18n.

        Defaults to ``No command called {0} found.``

        Parameters
        ------------
        string: :class:`str`
            The string that contains the invalid command. Note that this has
            had mentions removed to prevent abuse.

        Returns
        ---------
        :class:`str`
            The string to use when a command has not been found.
        """
        return 'No command called "{}" found.'.format(string)

    def subcommand_not_found(self, command: Command, string: str) -> str:
        """|maybecoro|

        A method called when a command did not have a subcommand requested in
        the help command. This is useful to override for i18n.

        Defaults to either:

        - ``'Command "{command.qualified_name}" has no subcommands.'``
            - If there is no subcommand in the ``command`` parameter.
        - ``'Command "{command.qualified_name}" has no subcommand named {string}'``
            - If the ``command`` parameter has subcommands but not one named ``string``.

        Parameters
        ------------
        command: :class:`Command`
            The command that did not have the subcommand requested.
        string: :class:`str`
            The string that contains the invalid subcommand.

        Returns
        ---------
        :class:`str`
            The string to use when the command did not have the subcommand
            requested.
        """  # noqa

        if isinstance(command, Group) and len(command.all_commands) > 0:
            return ('Command "{0.qualified_name}" has no subcommand named '
                    '{1}'.format(command, string))
        return 'Command "{0.qualified_name}" has no subcommands.'.format(
            command
        )

    async def filter_commands(self, commands: Iterable[Command], *,
                              sort: bool = False,
                              key: Optional[Callable] = None
                              ) -> List[Command]:
        """|coro|

        Returns a filtered list of commands and optionally sorts them.

        This takes into account the :attr:`verify_checks` and
        :attr:`show_hidden` attributes.

        Parameters
        ------------
        commands: Iterable[:class:`Command`]
            An iterable of commands that are getting filtered.
        sort: :class:`bool`
            Whether to sort the result.
        key: Optional[Callable[:class:`Command`, Any]]
            An optional key function to pass to :func:`py:sorted` that
            takes a :class:`Command` as its sole parameter. If ``sort`` is
            passed as ``True`` then this will default as the command name.

        Returns
        ---------
        List[:class:`Command`]
            A list of commands that passed the filter.
        """

        if sort and key is None:
            key = lambda c: c.name  # noqa

        if self.show_hidden:
            iterator = commands
        else:
            iterator = filter(lambda c: not c.hidden, commands)

        if not self.verify_checks:
            # if we do not need to verify the checks then we can just
            # run it straight through normally without using await.
            return sorted(iterator, key=key) if sort else list(iterator)

        # if we're here then we need to check every command if it can run
        async def predicate(cmd):
            try:
                return await cmd.can_run(self.context)
            except CommandError:
                return False

        ret = []
        for cmd in iterator:
            valid = await predicate(cmd)
            if valid:
                ret.append(cmd)

        if sort:
            ret.sort(key=key)

        return ret

    def get_max_size(self, commands: Sequence[Command]) -> int:
        """Returns the largest name length of the specified command list.

        Parameters
        ------------
        commands: Sequence[:class:`Command`]
            A sequence of commands to check for the largest size.

        Returns
        --------
        :class:`int`
            The maximum width of the commands.
        """

        as_lengths = (
            _string_width(c.name)
            for c in commands
        )
        return max(as_lengths, default=0)

    def get_destination(self) -> Union[Friend, ClientParty]:
        """Returns either :class:`fortnitepy.Friend` or
        :class:`fortnitepy.ClientParty` where the help command will be output.

        You can override this method to customise the behaviour.

        By default this returns the context's destination.
        """
        return self.context.get_destination()

    async def send_error_message(self, error: Exception) -> None:
        """|coro|

        Handles the implementation when an error happens in the help command.
        For example, the result of :meth:`command_not_found` or
        :meth:`command_has_no_subcommand_found` will be passed here.

        You can override this method to customise the behaviour.

        By default, this sends the error message to the destination
        specified by :meth:`get_destination`.

        .. note::

            You can access the invocation context with
            :attr:`HelpCommand.context`.

        Parameters
        ------------
        error: :class:`str`
            The error message to display to the user.
        """

        destination = self.get_destination()
        await destination.send(error)

    @_not_overridden
    async def help_command_error_handler(self, ctx: Context,
                                         error: Exception) -> None:
        """|coro|

        The help command's error handler, as specified by
        :ref:`ext_commands_error_handler`.

        Useful to override if you need some specific behaviour when the
        error handler is called.

        By default this method does nothing and just propagates to the default
        error handlers.

        Parameters
        ------------
        ctx: :class:`Context`
            The invocation context.
        error: :class:`CommandError`
            The error that was raised.
        """
        pass

    async def send_bot_help(self, page: int) -> None:
        """|coro|

        Handles the implementation of the bot command page in the help command.
        This function is called when the help command is called with no
        arguments.

        It should be noted that this method does not return anything -- rather
        the actual message sending should be done inside this method. Well
        behaved subclasses should use :meth:`get_destination` to know where to
        send, as this is a customisation point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with
            :attr:`HelpCommand.context`. Also, the commands in the mapping are
            not filtered. To do the filtering you will have to call
            :meth:`filter_commands` yourself.

        Parameters
        ----------
        page: :class:`int`
            The page to send.
        """
        return None

    async def send_cog_help(self, cog: Cog, page: int) -> None:
        """|coro|

        Handles the implementation of the cog page in the help command.
        This function is called when the help command is called with a cog as
        the argument.

        It should be noted that this method does not return anything -- rather
        the actual message sending should be done inside this method. Well
        behaved subclasses should use :meth:`get_destination` to know where to
        send, as this is a customisation point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with
            :attr:`HelpCommand.context`. To get the commands that belong to
            this cog see :meth:`Cog.get_commands`. The commands returned not
            filtered. To do the filtering you will have to call
            :meth:`filter_commands` yourself.

        Parameters
        -----------
        cog: :class:`Cog`
            The cog that was requested for help.
        page: :class:`int`
            The page to send.
        """
        return None

    async def send_group_help(self, group: Group) -> None:
        """|coro|

        Handles the implementation of the group page in the help command.
        This function is called when the help command is called with a group
        as the argument.

        It should be noted that this method does not return anything -- rather
        the actual message sending should be done inside this method. Well
        behaved subclasses should use :meth:`get_destination` to know where to
        send, as this is a customisation point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with
            :attr:`HelpCommand.context`. To get the commands that belong to
            this group without aliases see :attr:`Group.commands`. The
            commands returned not filtered. To do the filtering you will have
            to call :meth:`filter_commands` yourself.

        Parameters
        -----------
        group: :class:`Group`
            The group that was requested for help.
        """
        return None

    async def send_command_help(self, command: Command) -> None:
        """|coro|

        Handles the implementation of the single command page in the help
        command.

        It should be noted that this method does not return anything -- rather
        the actual message sending should be done inside this method. Well
        behaved subclasses should use :meth:`get_destination` to know where to
        send, as this is a customisation point for other users.

        You can override this method to customise the behaviour.

        .. note::

            You can access the invocation context with
            :attr:`HelpCommand.context`.

        .. admonition:: Showing Help
            :class: helpful

            There are certain attributes and methods that are helpful for a
            help command to show such as the following:

            - :attr:`Command.help`
            - :attr:`Command.brief`
            - :attr:`Command.short_doc`
            - :attr:`Command.description`
            - :meth:`get_command_signature`

            There are more than just these attributes but feel free to play
            around with these to help you get started to get the output that
            you want.

        Parameters
        -----------
        command: :class:`Command`
            The command that was requested for help.
        """
        return None

    async def prepare_help_command(self, ctx: Context,
                                   command: Optional[Command] = None) -> None:
        """|coro|

        A low level method that can be used to prepare the help command
        before it does anything. For example, if you need to prepare
        some state in your subclass before the command does its processing
        then this would be the place to do it.

        The default implementation does nothing.

        .. note::

            This is called *inside* the help command callback body. So all
            the usual rules that happen inside apply here as well.

        Parameters
        -----------
        ctx: :class:`Context`
            The invocation context.
        command: Optional[:class:`str`]
            The argument passed to the help command.
        """
        pass

    # Not typehinting because its a command callback
    async def command_callback(self, ctx, *, command=None, page: int = 1):
        """|coro|

        The actual implementation of the help command.

        It is not recommended to override this method and instead change
        the behaviour through the methods that actually get dispatched.

        - :meth:`send_bot_help`
        - :meth:`send_cog_help`
        - :meth:`send_group_help`
        - :meth:`send_command_help`
        - :meth:`get_destination`
        - :meth:`command_not_found`
        - :meth:`subcommand_not_found`
        - :meth:`send_error_message`
        - :meth:`on_help_command_error`
        - :meth:`prepare_help_command`
        """

        # page will never get a value but we just include it here for
        # the param list. The actual conversion is done below.
        if command is not None:
            split = command.split()
            try:
                page = int(split[-1])
            except ValueError:
                page = 1
                new = command
            else:
                new = None if len(split) == 1 else ' '.join(split[:-1])
        else:
            new = command

        await self.prepare_help_command(ctx, command)
        bot = ctx.bot

        if new is None:
            # mapping = self.get_bot_mapping()
            return await self.send_bot_help(page)

        # Check if it's a cog
        if not command.startswith(self.command_prefix):
            cog = bot.get_cog(new)
            if cog is not None:
                return await self.send_cog_help(cog, page)

        if command.startswith(self.command_prefix):
            command = command[len(self.command_prefix):]

        maybe_coro = maybe_coroutine

        # If it's not a cog then it's a command.
        # Since we want to have detailed errors when someone
        # passes an invalid subcommand, we need to walk through
        # the command group chain ourselves.
        keys = command.split(' ')
        cmd = bot.all_commands.get(keys[0])
        if cmd is None:
            string = await maybe_coro(self.command_not_found, keys[0])
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, key)
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = await maybe_coro(
                        self.subcommand_not_found,
                        cmd,
                        key
                    )
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)


class FortniteHelpCommand(HelpCommand):
    """The implementation of the default help command.

    This inherits from :class:`HelpCommand`.

    It extends it with the following attributes.

    Attributes
    ------------
    dm_help: Optional[:class:`bool`]
        A tribool that indicates if the help command should DM the user
        instead of sending it to the channel it received it from. If the
        boolean is set to ``True``, then all help output is DM'd. If ``False``,
        none of the help output is DM'd.
    paginator: :class:`Paginator`
        The paginator used to paginate the help command output.
    commands_title: :class:`str`
        The commands title. Defaults to ``Commands:``.
    cog_title: :class:`str`
        The cog title. Defaults to ``Category:``.
    usage_title: :class:`str`
        The usage title. Defaults to ``Usage:``.
    description_title: :class:`str`
        The description title. Defaults to ``Description:``.
    help_title: :class:`str`
        The help title. Defaults to ``Help:``.
    sub_commands_title: :class:`str`
        The sub commands title. Defaults to ``Help Commands:``.
    no_category_heading: :class:`str`
        The text to use as heading if no category (cog) is found
        for the command.
        Defaults to ``No Category``.
    height: :class:`int`
        The maximum number of lines to fit.
        Defaults to ``15``.
    width: :class:`int`
        The maximum number of characters that fit in a line.
        Defaults to ``60``.
    indent: :class:`int`
        How much to indent the commands and other text from a title.
        Defaults to ``4``.
    title_prefix: :class:`str`
        The prefix to use for the help title.
        Defaults to `` +``.
    title_suffix: :class:`str`
        The suffix to use for the help title.
        Defaults to ``+``.
    title_char: :class:`str`
        The char to use for the help title.
        Defaults to ``=``.
    line_prefix: :class:`str`
        The prefix to use for all lines.
        Defaults to ``   ``. (Three spaces)
    line_suffix: :class:`str`
        The prefix to use for all lines.
        Defaults to ````. (Empty)
    footer_prefix: :class:`str`
        The prefix to use for the help footer.
        Defaults to `` +``.
    footer_suffix: :class:`str`
        The suffix to use for the help footer.
        Defaults to ``+``.
    footer_char: :class:`str`
        The char to use for the help footer.
        Defaults to ``=``.
    """

    def __init__(self, **options: dict) -> None:
        self.dm_help = options.pop('dm_help', False)
        self.paginator = options.pop('paginator', None)

        self.commands_title = options.pop('commands_title', 'Commands:')
        self.cog_title = options.pop('cog_title', 'Category:')
        self.usage_title = options.pop('usage_title', 'Usage:')
        self.description_title = options.pop('description_title', 'Description:')  # noqa
        self.help_title = options.pop('help_title', 'Help:')
        self.sub_commands_title = options.pop('sub_commands_title', 'Sub Commands:')  # noqa

        self.no_category = options.pop('no_category_heading', 'No Category')

        self.height = options.pop('height', 15)
        self.width = options.pop('width', 60)
        self.indent = options.pop('indent', 4)

        self.title_prefix = options.pop('title_prefix', ' +')
        self.title_suffix = options.pop('title_suffix', '+')
        self.title_char = options.pop('title_char', '=')

        self.line_prefix = options.pop('line_prefix', '   ')
        self.line_suffix = options.pop('line_suffix', '')

        self.footer_prefix = options.pop('footer_prefix', ' +')
        self.footer_suffix = options.pop('footer_suffix', '+')
        self.footer_char = options.pop('footer_char', '=')

        if self.paginator is None:
            self.paginator = Paginator()

        super().__init__(**options)

    def get_command_name(self, command: Command) -> str:
        """Gets the name of a command.

        This method can be overridden for custom text.

        Parameters
        ----------
        command: :class:`.Command`
            The command to get the name for.

        Returns
        -------
        :class:`str`
            | The command name.
            | Defaults to ``self.command_prefix + command.qualified_name``
        """
        return self.command_prefix + command.qualified_name

    def get_sub_command_name(self, sub_command: Command) -> str:
        """Gets the name of a sub command.

        This method can be overridden for custom text.

        Parameters
        ----------
        sub_command: :class:`.Command`
            The sub command to get the name for.

        Returns
        -------
        :class:`str`
            | The sub command name.
            | Defaults to ``{self.command_prefix} {sub_command.qualified_name}``
        """  # noqa 
        return self.command_prefix + sub_command.qualified_name

    def get_bot_header(self, page_num: int, pages_amount: int) -> str:
        """Gets the name of a sub command.

        This method can be overridden for custom text.

        Parameters
        ----------
        page_num: :class:`int`
            The page being built.
        pages_amount: :class:`int`
            The amount of pages available.

        Returns
        -------
        :class:`str`
            | The sub command name.
            | Defaults to ``{self.command_prefix} {sub_command.qualified_name}``
        """  # noqa

        return '{0} - {1} / {2}'.format(
            'All Commands',
            page_num,
            pages_amount
        )

    def get_bot_footer(self, page_num: int, pages_amount: str) -> str:
        """Gets the text to appear in the footer when
        :meth:`send_bot_help()` is called.

        This method can be overridden for custom text.

        Parameters
        ----------
        page_num: :class:`int`
            The page being built.
        pages_amount: :class:`int`
            The amount of pages available.

        Returns
        -------
        :class:`str`
            | The bot footer.
            | Defaults to ```` (Empty)
        """
        return ''

    def get_command_header(self, command: Command) -> str:
        """Gets the text to appear in the header when
        :meth:`send_command_help()` is called.

        This method can be overridden for custom text.

        Parameters
        ----------
        command: :class:`.Command`
            The command to get the header for.

        Returns
        -------
        :class:`str`
            | The header text.
            | Defaults to ``Command | {self.command_prefix}{command.qualified_name}``
        """  # noqa
        return 'Command | {0}{1}'.format(
            self.command_prefix,
            command.qualified_name
        )

    def get_command_footer(self, command: Command) -> str:
        """Gets the text to appear in the footer when
        :meth:`send_command_help()` is called.

        This method can be overridden for custom text.

        Parameters
        ----------
        command: :class:`.Command`
            The command to get the footer for.

        Returns
        -------
        :class:`str`
            | The footer text.
            | Defaults to ```` (Empty)
        """
        return ''

    def get_group_header(self, group: Group) -> str:
        """Gets the text to appear in the header when
        :meth:`send_group_help()` is called.

        This method can be overridden for custom text.

        Parameters
        ----------
        command: :class:`.Group`
            The group to get the header for.

        Returns
        -------
        :class:`str`
            | The header text.
            | Defaults to ``Command | {self.command_prefix}{group.qualified_name}``
        """  # noqa
        return 'Command | {0}{1}'.format(
            self.command_prefix,
            group.qualified_name
        )

    def get_group_footer(self, group: Group) -> str:
        """Gets the text to appear in the footer when
        :meth:`send_group_help()` is called.

        This method can be overridden for custom text.

        Parameters
        ----------
        command: :class:`.Group`
            The group to get the footer for.

        Returns
        -------
        :class:`str`
            | The footer text.
            | Defaults to ```` (Empty)
        """
        return ''

    def get_cog_header(self, cog: Cog,
                       page_num: int,
                       pages_amount: int) -> str:
        """Gets the text to appear in the header when
        :meth:`send_cog_help()` is called.

        This method can be overridden for custom text.

        Parameters
        ----------
        cog: :class:`.Cog`
            The cog to get the header for.
        page_num: :class:`int`
            The page being built.
        pages_amount: :class:`int`
            The amount of pages available.

        Returns
        -------
        :class:`str`
            | The header text.
            | Defaults to ``Category | {cog.qualified_name} - {page_num} / {pages_amount}``
        """  # noqa
        return 'Category | {0} - {1} / {2}'.format(
            cog.qualified_name,
            page_num,
            pages_amount
        )

    def get_cog_footer(self, cog: Cog,
                       page_num: int,
                       pages_amount: int) -> str:
        """Gets the text to appear in the footer when
        :meth:`send_cog_help()` is called.

        This method can be overridden for custom text.

        Parameters
        ----------
        cog: :class:`.Cog`
            The cog to get the footer for.
        page_num: :class:`int`
            The page being built.
        pages_amount: :class:`int`
            The amount of pages available.

        Returns
        -------
        :class:`str`
            | The footer text.
            | Defaults to ``{self.command_prefix}{self.invoked_with} {cog.qualified_name} <page> | {self.command_prefix}{self.invoked_with} <command>``
        """  # noqa
        return '{0}{1} {2} <page> | {0}{1} <command>'.format(
            self.command_prefix,
            self.invoked_with,
            cog.qualified_name
        )

    def shorten_text(self, text: str,
                     max_len: int,
                     dot_amount: int = 3) -> str:
        """Shortens text to fit into the :attr:`width`."""

        if len(text) > max_len:
            return text[:max_len-dot_amount] + '.'*dot_amount
        return text

    def construct_title(self, t: str) -> str:
        _title = ' ' + t + ' ' if t else ''
        w = self.width - len(self.title_prefix) - len(self.title_suffix)
        return '{0}{1:{2}^{3}}{4}'.format(
            self.title_prefix,
            _title,
            self.title_char,
            w,
            self.title_suffix
        )

    def construct_footer(self, f: str) -> str:
        _footer = ' ' + f + ' ' if f else ''
        w = self.width - len(self.footer_prefix) - len(self.footer_suffix)
        return '{0}{1:{2}^{3}}{4}'.format(
            self.footer_prefix,
            _footer,
            self.footer_char,
            w,
            self.footer_suffix
        )

    def fix_too_long(self, string: str,
                     length: int,
                     start_length: int) -> Tuple[str, List[str]]:
        first = string[:start_length-1]
        string = string[start_length-1:]

        return (
            first,
            [string[0+i:length-1+i] for i in range(0, len(string), length-1)]
        )

    def chunkstring(self, string: str, length: int) -> List[str]:
        lines = []
        curr = ''
        split = string.split()
        for c, word in enumerate(split, 1):
            spaces = 1 if c != len(split) else 0
            if len(word) + spaces > length:
                space_left = (length - len(curr))
                start_length = space_left if space_left > 5 else 0
                first, too_long = self.fix_too_long(word, length, start_length)
                if first:
                    curr += first + '-'

                if curr:
                    lines.append(curr)
                    curr = ''

                for cc, new in enumerate(too_long, 1):
                    if cc != len(too_long):
                        new += '-'
                        lines.append(new)
                    else:
                        curr += new
                continue

            if len(curr) + len(word) > length:
                lines.append(curr[:-1])
                curr = ''

            curr += word + ' '

        if curr:
            lines.append(curr)

        return lines

    def construct_single_line(self, text: str, extra_indent: int = 0) -> str:
        prefix = self.line_prefix + ' '*extra_indent
        suffix = self.line_suffix

        w = self.width - len(prefix) - len(suffix)
        return '{0}{1:<{2}}{3}'.format(
            prefix,
            text,
            w,
            suffix
        )

    def construct_category(self, name: str,
                           brief: str,
                           extra_indent: int = 0,
                           raw: bool = False) -> List[str]:
        prefix = self.line_prefix + ' '*extra_indent
        suffix = self.line_suffix

        indent = self.indent

        w = self.width - len(prefix) - len(suffix)
        name_line = '{0}{1:<{2}}{3}'.format(
            prefix,
            self.shorten_text(name, w),
            w,
            suffix
        )

        brief_w = w - indent
        lines = [name_line]

        if not raw:
            gen = self.chunkstring(brief, brief_w)
        else:
            gen = brief.splitlines()

        for c, line in enumerate(gen, 2):
            fmt = '{0}{1}{2:<{3}}{4}'.format(
                prefix,
                ' '*indent,
                line,
                brief_w,
                suffix
            )
            if c == self.height - 2:
                to_cut = 3 + len(suffix)
                new = fmt[:to_cut] + '...' + suffix
                lines.append(new)
                break

            lines.append(fmt)

        return lines

    async def send_pages(self) -> None:
        """A helper utility to send the page output from :attr:`paginator` to
        the destination.
        """

        destination = self.get_destination()
        for page in self.paginator.pages:
            await destination.send(page)

    async def send_page(self, page_num: int) -> None:
        """A helper utility to send a page output from :attr:`paginator` to
        the destination.
        """

        pages = self.paginator.pages
        if page_num <= 0 or page_num > len(pages):
            return await self.send_error_message(
                'Could not find the page you were looking for'
            )

        destination = self.get_destination()
        await destination.send(pages[page_num-1])

    def get_destination(self) -> Union[Friend, ClientParty]:
        ctx = self.context
        if self.dm_help is True:
            return ctx.author
        elif (self.dm_help is None
                and len(self.paginator) > self.dm_help_threshold):
            return ctx.author
        else:
            return ctx.get_destination()

    async def prepare_help_command(self, ctx: Context,
                                   command: Command) -> None:
        self.paginator.clear()
        await super().prepare_help_command(ctx, command)

    def construct_command_help(self, command: Command) -> List[str]:
        fmt = {}
        if command.cog:
            fmt[self.cog_title] = command.cog.qualified_name

        fmt[self.usage_title] = self.get_command_signature(command)

        if command.description:
            fmt[self.description_title] = command.description

        result = []
        for title, value in fmt.items():
            lines = self.construct_category(title, value)

            result.extend(lines)

        if command.help:
            title = self.help_title
            value = command.help
            lines = self.construct_category(title, value, raw=True)

            result.extend(lines)

        return result

    async def send_bot_help(self, page: int) -> None:
        ctx = self.context
        bot = ctx.bot

        no_category = '\u200b{0.no_category}:'.format(self)

        def get_category(command, *, no_category=no_category):
            cog = command.cog
            return cog.qualified_name if cog is not None else no_category

        filtered = await self.filter_commands(
            bot.commands,
            sort=True,
            key=get_category
        )

        chunks = []
        curr = []

        if bot.description:
            parts = self.construct_category(
                self.description_title,
                bot.description
            )
            curr.extend(parts)

        for command in filtered:
            name = self.get_command_name(command)
            brief = command.brief or ''
            lines = self.construct_category(name, brief)

            if len(lines) + len(curr) > self.height - 2:
                chunks.append(curr)
                curr = []

            curr.extend(lines)

        if curr:
            chunks.append(curr)

        chunks_length = len(chunks)
        for c, chunk in enumerate(chunks, 1):

            footer_fmt = self.get_bot_footer(c, chunks_length) or ''
            page_chunks = [
                self.construct_title(
                    self.get_bot_header(c, chunks_length) or ''
                ),
                *chunk,
                self.construct_footer(footer_fmt.format(
                    self.command_prefix,
                    self.invoked_with,
                ))
            ]
            self.paginator.add_page(
                '\u200b\n' + '\n'.join(page_chunks)
            )

        await self.send_page(page)

    async def send_command_help(self, command: Command) -> None:
        result = self.construct_command_help(command)

        title = self.construct_title(self.get_command_header(command) or '')
        footer = self.construct_footer(self.get_command_footer(command) or '')
        self.paginator.add_page(
            '\u200b\n' + '\n'.join([title, *result, footer])
        )

        await self.send_pages()

    async def send_group_help(self, group: Group) -> None:
        result = self.construct_command_help(group)

        filtered = await self.filter_commands(
            group.commands,
            sort=True
        )

        for c, command in enumerate(filtered):
            if c == 0:
                title = self.sub_commands_title
                result.append('\n'+self.construct_single_line(title))

            name = self.get_sub_command_name(command)
            brief = command.brief or ''
            lines = self.construct_category(
                name,
                brief,
                extra_indent=self.indent
            )

            result.extend(lines)

        title = self.construct_title(
            self.get_group_header(group)
        )
        footer = self.construct_footer('')
        self.paginator.add_page(
            '\u200b\n' + '\n'.join([title, *result, footer])
        )

        await self.send_pages()

    async def send_cog_help(self, cog: Cog, page: str) -> None:
        filtered = await self.filter_commands(
            cog.get_commands(),
            sort=True
        )

        chunks = []
        curr = []

        if cog.description:
            parts = self.construct_category(
                self.description_title,
                cog.description
            )
            curr.extend(parts)

        for c, command in enumerate(filtered):
            if c == 0:
                title = self.commands_title
                pre = '\n' if curr else ''
                curr.append(pre+self.construct_single_line(title))

            name = self.get_command_name(command)
            brief = command.brief or ''
            lines = self.construct_category(
                name,
                brief,
                extra_indent=self.indent
            )

            if len(lines) + len(curr) > self.height - 2:
                chunks.append(curr)
                curr = []

            curr.extend(lines)

        if curr:
            chunks.append(curr)

        chunks_length = len(chunks)
        for c, chunk in enumerate(chunks, 1):
            title = self.construct_title(
                self.get_cog_header(cog, c, chunks_length) or ''
            )
            fmt = self.get_cog_footer(cog, c, chunks_length) or ''
            footer = self.construct_footer(fmt)
            page_chunks = [
                title,
                *chunk,
                footer
            ]
            self.paginator.add_page(
                '\u200b\n' + '\n'.join(page_chunks)
            )

        await self.send_page(page)
