import inspect
import asyncio

from typing import (TYPE_CHECKING, Union, Awaitable, Any, List, Dict, Iterable,
                    Optional)
from fortnitepy.typedefs import MaybeCoro

from ._types import _BaseCommand
from .context import Context

if TYPE_CHECKING:
    from .bot import Bot


__all__ = (
    'CogMeta',
    'Cog',
)


class CogMeta(type):
    """A metaclass for defining a cog.

    Note that you should probably not use this directly. It is exposed
    purely for documentation purposes.

    .. note::

        When passing an attribute of a metaclass that is documented below, note
        that you must pass it as a keyword-only argument to the class creation
        like the following example:

        .. code-block:: python3

            class MyCog(commands.Cog, name='My Cog'):
                pass

    Attributes
    -----------
    name: :class:`str`
        The cog name. By default, it is the name of the class with no
        modification.
    command_attrs: :class:`dict`
        A list of attributes to apply to every command inside this cog.
        The dictionary is passed into the :class:`Command` (or its subclass)
        options at ``__init__``. If you specify attributes inside the command
        attribute in the class, it will override the one specified inside this
        attribute. For example:

        .. code-block:: python3

            class MyCog(commands.Cog, command_attrs=dict(hidden=True)):

                @commands.command()
                async def foo(self, ctx):
                    pass # hidden -> True

                @commands.command(hidden=False)
                async def bar(self, ctx):
                    pass # hidden -> False
    """

    def __new__(cls, *args: list, **kwargs: dict) -> None:
        name, bases, attrs = args
        attrs['__cog_name__'] = cog_name = kwargs.pop('name', name)

        last = cog_name.split()[-1]
        try:
            int(last)
        except ValueError:
            pass
        else:
            raise NameError('Cog names cannot end with a space followed by a '
                            'number or solely consist of a number.')

        command_attrs = kwargs.pop('command_attrs', {})
        attrs['__cog_settings__'] = command_attrs

        commands = {}
        event_handlers = {}
        no_bot_cog = ('Commands or listeners must not start with cog_ or bot_ '
                      '(in method {0.__name__}.{1})')

        new_cls = super().__new__(cls, name, bases, attrs, **kwargs)
        for base in reversed(new_cls.__mro__):
            for elem, value in base.__dict__.items():
                if elem in commands:
                    del commands[elem]
                if elem in event_handlers:
                    del event_handlers[elem]

                is_static_method = isinstance(value, staticmethod)
                if is_static_method:
                    value = value.__func__

                if isinstance(value, _BaseCommand):
                    if is_static_method:
                        raise TypeError(
                            'Command in method {0}.{1!r} must not be '
                            'staticmethod.'.format(base, elem)
                        )

                    commands[elem] = value

                elif asyncio.iscoroutinefunction(value):
                    try:
                        getattr(value, '__cog_event_handler__')
                    except AttributeError:
                        pass
                    else:
                        if elem.startswith(('cog_', 'bot_')):
                            raise TypeError(no_bot_cog.format(base, elem))
                        event_handlers[elem] = value

        new_cls.__cog_commands__ = list(commands.values())

        event_handlers_as_list = []
        for handler in event_handlers.values():
            for handler_name, was_def in handler.__cog_event_handler_names__:
                event_handlers_as_list.append((
                    handler_name,
                    handler.__name__,
                    was_def
                ))

        new_cls.__cog_event_handlers__ = event_handlers_as_list
        return new_cls

    def __init__(self, *args: list, **kwargs: dict) -> None:
        super().__init__(*args, **kwargs)

    @classmethod
    def qualified_name(cls) -> str:
        return cls.__cog_name__


def _cog_special_method(func: MaybeCoro) -> MaybeCoro:
    func.__cog_special_method__ = None
    return func


class Cog(metaclass=CogMeta):
    """The base class that all cogs must inherit from.

    A cog is a collection of commands, listeners, and optional state to
    help group commands together. More information on them can be found on
    the :ref:`ext_commands_cogs` page.

    When inheriting from this class, the options shown in :class:`CogMeta`
    are equally valid here.
    """

    def __new__(cls, *args: list, **kwargs: dict) -> None:
        self = super().__new__(cls)
        cmd_attrs = cls.__cog_settings__

        self.__cog_commands__ = tuple(
            c._update_copy(cmd_attrs) for c in cls.__cog_commands__
        )

        lookup = {
            cmd.qualified_name: cmd for cmd in self.__cog_commands__
        }

        for command in self.__cog_commands__:
            setattr(self, command.callback.__name__, command)
            parent = command.parent
            if parent is not None:
                parent = lookup[parent.qualified_name]

                parent.remove_command(command.name)
                parent.add_command(command)

        return self

    def get_commands(self) -> List[_BaseCommand]:
        r"""Returns a :class:`list` of :class:`.Command`\s that are
        defined inside this cog.

        .. note::

            This does not include subcommands.
        """
        return [c for c in self.__cog_commands__ if c.parent is None]

    @property
    def qualified_name(self) -> str:
        """:class:`str`: Returns the cog's specified name, not
        the class name.
        """
        return self.__cog_name__

    @property
    def description(self) -> str:
        """:class:`str`: Returns the cog's description, typically
        the cleaned docstring.
        """
        try:
            return self.__cog_cleaned_doc__
        except AttributeError:
            self.__cog_cleaned_doc__ = inspect.getdoc(self)
            return self.__cog_cleaned_doc__

    def walk_commands(self) -> Iterable:
        """An iterator that recursively walks through this cog's
        commands and subcommands.
        """
        from .core import GroupMixin

        for command in self.__cog_commands__:
            if command.parent is None:
                yield command
                if isinstance(command, GroupMixin):
                    yield from command.walk_commands()

    @property
    def event_handlers(self) -> Dict[str, Awaitable]:
        """:class:`list`: A list of (name, function) event handler pairs
        that are defined in this cog.
        """
        return {
            name: getattr(self, method_name)
            for name, method_name, _
            in self.__cog_event_handlers__
        }

    @classmethod
    def _get_overridden_method(cls, method: MaybeCoro) -> MaybeCoro:
        """Return None if the method is not overridden. Otherwise returns the
        overridden method.
        """
        return getattr(method.__func__, '__cog_special_method__', method)

    @classmethod
    def event(cls, event: Union[str, Awaitable[Any]] = None) -> Awaitable:
        """A decorator to register an event.

        Usage: ::

            @commands.Cog.event()
            async def event_friend_message(message):
                await message.reply('Thanks for your message!')

            @commands.Cog.event('friend_message')
            async def my_message_handler(message):
                await message.reply('Thanks for your message!')

        Raises
        ------
        TypeError
            The decorated function is not a coroutine.
        TypeError
            Event is not specified as argument or function name with event
            prefix.
        """
        is_coro = callable(event)

        def pred(coro):
            if isinstance(coro, staticmethod):
                coro = coro.__func__

            if not asyncio.iscoroutinefunction(coro):
                raise TypeError('the decorated function must be a coroutine')

            if is_coro or event is None:
                name = coro.__name__
                name_defined = False
            else:
                name = event
                name_defined = True

            coro.__cog_event_handler__ = True

            try:
                coro.__cog_event_handler_names__.append((name, name_defined))
            except AttributeError:
                coro.__cog_event_handler_names__ = [(name, name_defined)]

            return coro
        return pred(event) if is_coro else pred

    def _inject(self, bot: 'Bot') -> 'Cog':
        cls = self.__class__

        for index, command in enumerate(self.__cog_commands__):
            command.cog = self
            if command.parent is None:
                try:
                    bot.add_command(command)
                except Exception as e:
                    for to_undo in self.__cog_commands__[:index]:
                        bot.remove_command(to_undo)
                    raise e

        if cls.bot_check is not Cog.bot_check:
            bot.add_check(self.bot_check)

        if cls.bot_check_once is not Cog.bot_check_once:
            bot.add_check(self.bot_check_once, call_once=True)

        # We need to do this to remove all prefixes of events registered
        # with the coro's name instead of manually specifying the name.
        new = []
        for name, method, name_was_defined in self.__cog_event_handlers__:
            if not name_was_defined:
                if name.startswith(bot.event_prefix):
                    name = name[len(bot.event_prefix):]

            new.append((name, method, name_was_defined))

        self.__cog_event_handlers__ = new

        for name, method_name, _ in self.__cog_event_handlers__:
            bot.add_event_handler(name, getattr(self, method_name))

        return self

    def _eject(self, bot: 'Bot') -> None:
        cls = self.__class__

        try:
            for command in self.__cog_commands__:
                if command.parent is None:
                    bot.remove_command(command.name)

            for name, method_name, _ in self.__cog_event_handlers__:
                bot.remove_event_handler(name, getattr(self, method_name))

            if cls.bot_check is not Cog.bot_check:
                bot.remove_check(self.bot_check)

            if cls.bot_check_once is not Cog.bot_check_once:
                bot.remove_check(self.bot_check_once, call_once=True)

        finally:
            self.cog_unload()

    @_cog_special_method
    def cog_unload(self) -> None:
        """A special method that is called when the cog gets removed.

        This function **cannot** be a coroutine. It must be a regular
        function.

        Subclasses must replace this if they want special unloading behaviour.
        """
        pass

    @_cog_special_method
    def bot_check_once(self, ctx: 'Context') -> bool:
        """A special method that registers as a :meth:`.Bot.check_once`
        check.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def bot_check(self, ctx: 'Context') -> bool:
        """A special method that registers as a :meth:`.Bot.check`
        check.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def cog_check(self, ctx: 'Context') -> bool:
        """A special method that registers as a :func:`commands.check`
        for every command and subcommand in this cog.

        This function **can** be a coroutine and must take a sole parameter,
        ``ctx``, to represent the :class:`.Context`.
        """
        return True

    @_cog_special_method
    def cog_command_error(self, ctx: 'Context',
                          error: Exception) -> Optional[bool]:
        """A special method that is called whenever an error
        is dispatched inside this cog.

        This is similar to :func:`.event_command_error` except only applying
        to the commands inside this cog.

        Command error handlers are raised in a specific order. Returning
        ``False`` in any of them will invoke the next handler in the chain. If
        there are no handlers left to call, the error is printed.

        The order goes as follows:
        1. The local command error handler is called. (Handler specified by
        :meth:`.Command.check`)
        2. The local cog command error handler is called. (This)
        3. All :func:`.event_command_error()` handlers are called
        simultaneously. If any of them return False, the error will
        be printed.

        This **must** be a coroutine.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context where the error happened.
        error: :class:`CommandError`
            The error that happened.
        """
        return False

    @_cog_special_method
    async def cog_before_invoke(self, ctx: 'Context') -> None:
        """A special method that acts as a cog local pre-invoke hook.

        This is similar to :meth:`.Command.before_invoke`.

        This **must** be a coroutine.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context.
        """
        pass

    @_cog_special_method
    async def cog_after_invoke(self, ctx: Context) -> None:
        """A special method that acts as a cog local post-invoke hook.

        This is similar to :meth:`.Command.after_invoke`.

        This **must** be a coroutine.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context.
        """
        pass
