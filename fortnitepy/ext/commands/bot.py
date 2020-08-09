import logging
import inspect
import asyncio
import types
import sys
import importlib
import collections
import traceback

from typing import Any, List, Optional, Mapping, Set
from fortnitepy.client import Client
from fortnitepy.auth import Auth
from fortnitepy.typedefs import MaybeCoro, ListOrTuple

from ._types import _BaseCommand
from .errors import (ExtensionFailed, ExtensionMissingEntryPoint,
                     ExtensionNotLoaded, ExtensionAlreadyLoaded,
                     ExtensionNotFound, CheckFailure, CommandError,
                     CommandNotFound)
from .core import GroupMixin
from .cog import Cog
from .view import StringView
from .context import Context
from .help import HelpCommand, FortniteHelpCommand
from .typedefs import Message


log = logging.getLogger(__name__)


def _is_submodule(parent: str, child: str) -> bool:
    return parent == child or child.startswith(parent + ".")


class _DefaultRepr:
    def __repr__(self) -> str:
        return '<default-help-command>'


_default = _DefaultRepr()


class Bot(GroupMixin, Client):
    """Represents a fortnite bot.

    This class is a subclass of :class:`fortnitepy.Client` and as a result
    anything that you can do with a :class:`fortnitepy.Client` you can do with
    this bot.

    This class also subclasses :class:`.GroupMixin` to provide the
    functionality to manage commands.

    Attributes
    -----------
    command_prefix
        The command prefix is what the message content must contain initially
        to have a command invoked. This prefix could either be a string to
        indicate what the prefix should be, or a callable that takes in the bot
        as its first parameter and :class:`fortnitepy.FriendMessage` or
        :class:`fortnitepy.PartyMessage` as its second parameter and returns
        the prefix. This is to facilitate "dynamic" command prefixes. This
        callable can be either a regular function or a coroutine.

        An empty string as the prefix always matches, enabling prefix-less
        command invocation.

        The command prefix could also be an iterable of strings indicating that
        multiple checks for the prefix should be used and the first one to
        match will be the invocation prefix. You can get this prefix via
        :attr:`.Context.prefix`. To avoid confusion empty iterables are not
        allowed.

        .. note::
            When passing multiple prefixes be careful to not pass a prefix
            that matches a longer prefix occurring later in the sequence.  For
            example, if the command prefix is ``('!', '!?')``  the ``'!?'``
            prefix will never be matched to any message as the previous one
            matches messages starting with ``!?``. This is especially important
            when passing an empty string, it should always be last as no prefix
            after it will be matched.

    case_insensitive: :class:`bool`
        Whether the commands should be case insensitive. Defaults to ``False``.
        This attribute does not carry over to groups. You must set it to every
        group if you require group commands to be case insensitive as well.
    description: :class:`str`
        The content prefixed into the default help message.
    help_command: Optional[:class:`.HelpCommand`]
        The help command implementation to use. This can be dynamically
        set at runtime. To remove the help command pass ``None``. For more
        information on implementing a help command, see
        :ref:`ext_commands_help_command`.
    owner_id: Optional[:class:`int`]
        The user ID that owns the bot. This is used by :meth:`.is_owner()`
        and checks that call this method.
    owner_ids: Optional[Collection[:class:`int`]]
        The user IDs that owns the bot. This is similar to `owner_id`.
        For performance reasons it is recommended to use a :class:`set`
        for the collection. You cannot set both `owner_id` and `owner_ids`.
        This is used by :meth:`.is_owner()` and checks that call this method.
    """

    def __init__(self, command_prefix: Any, auth: Auth, *,
                 help_command: Optional[HelpCommand] = _default,
                 description: Optional[str] = None,
                 **kwargs: Any) -> None:
        super().__init__(auth, **kwargs)

        self.command_prefix = command_prefix
        self.description = inspect.cleandoc(description) if description else ''
        self.owner_id = kwargs.get('owner_id')
        self.owner_ids = kwargs.get('owner_ids', set())

        if self.owner_id and self.owner_ids:
            raise TypeError('Both owner_id and owner_ids are set.')

        if (self.owner_ids and not isinstance(self.owner_ids,
                                              collections.abc.Collection)):
            raise TypeError(
                'owner_ids must be a collection not '
                '{0.__class__!r}'.format(self.owner_ids)
            )

        self.__cogs = {}
        self.__extensions = {}
        self._checks = []
        self._check_once = []
        self._help_command = None
        self._before_invoke = None
        self._after_invoke = None

        if help_command is _default:
            self.help_command = FortniteHelpCommand()
        else:
            self.help_command = help_command

        self.add_event_handler('friend_message', self.process_commands)
        self.add_event_handler('party_message', self.process_commands)

    def register_methods(self) -> None:
        for _, obj in inspect.getmembers(self):
            if isinstance(obj, _BaseCommand):
                obj.instance = self

                try:
                    self.add_command(obj)
                except CommandError:
                    traceback.print_exc()
                    continue

        super().register_methods()

    async def close(self, *,
                    close_http: bool = True,
                    dispatch_close: bool = True) -> None:
        if dispatch_close:
            await self.dispatch_and_wait_event('close')

        for extension in tuple(self.__extensions):
            try:
                self.unload_extension(extension)
            except Exception:
                pass

        for cog in tuple(self.__cogs):
            try:
                self.remove_cog(cog)
            except Exception:
                pass

        await self._close(
            close_http=close_http,
            dispatch_close=dispatch_close
        )

    def check(self, func: MaybeCoro) -> MaybeCoro:
        r"""A decorator that adds a check globally to every command.

        .. note::

            This function can either be a regular function or a coroutine.

        This function takes a single parameter, :class:`.Context`, and can
        only raise exceptions inherited from :exc:`.CommandError`.

        Example
        -------
        .. code-block:: python3

            @bot.check
            def global_check(ctx):
                # Allows only party commands.
                return ctx.party is not None
        """
        self.add_check(func)
        return func

    def add_check(self, func: MaybeCoro, *,
                  call_once: bool = False) -> None:
        """Adds a global check to the bot.

        This is the non-decorator interface to :meth:`.check`
        and :meth:`.check_once`.

        Parameters
        ----------
        func
            The function that was used as a global check.
        call_once: :class:`bool`
            If the function should only be called once per
            :meth:`Command.invoke` call.
        """
        if call_once:
            self._check_once.append(func)
        else:
            self._checks.append(func)

    def remove_check(self, func: MaybeCoro, *,
                     call_once: bool = False) -> None:
        """Removes a global check from the bot.

        Parameters
        ----------
        func
            The function to remove from the global checks.
        call_once: :class:`bool`
            If the function was added with ``call_once=True`` in
            the :meth:`.Bot.add_check` call or using :meth:`.check_once`.
        """
        list_ = self._check_once if call_once else self._checks

        try:
            list_.remove(func)
        except ValueError:
            pass

    def check_once(self, func: MaybeCoro) -> MaybeCoro:
        r"""A decorator that adds a "call once" global check to the bot.

        Unlike regular global checks, this one is called only once
        per :meth:`Command.invoke` call.

        Regular global checks are called whenever a command is called
        or :meth:`.Command.can_run` is called. This type of check
        bypasses that and ensures that it's called only once, even inside
        the default help command.

        .. note::

            This function can either be a regular function or a coroutine.

        This function takes a single parameter, :class:`.Context`, and can
        only raise exceptions inherited from :exc:`.CommandError`.

        Example
        -------
        .. code-block:: python3

            @bot.check_once
            def whitelist(ctx):
                return ctx.message.author.id in my_whitelist

        """
        self.add_check(func, call_once=True)
        return func

    async def can_run(self, ctx: Context, *,
                      call_once: bool = False) -> bool:
        data = self._check_once if call_once else self._checks

        if len(data) == 0:
            return True

        for func in data:
            if asyncio.iscoroutinefunction(func):
                res = await func(ctx)
            else:
                res = func(ctx)

            if not res:
                return False

        return True

    async def is_owner(self, user_id: str) -> bool:
        """|coro|

        Checks if a user id is the owner of the bot.

        Parameters
        ----------
        user_id: :class:`str`
            The user id to check for.

        Returns
        -------
        :class:`bool`
            Whether the user is the owner.
        """
        if self.owner_id:
            return user_id == self.owner_id
        else:
            return user_id in self.owner_ids

    def before_invoke(self, coro: MaybeCoro) -> MaybeCoro:
        """A decorator that registers a coroutine as a pre-invoke hook.

        A pre-invoke hook is called directly before the command is
        called. This makes it a useful function to set up database
        connections or any type of set up required.

        This pre-invoke hook takes a sole parameter, a :class:`.Context`.

        .. note::

            The :meth:`~.Bot.before_invoke` and :meth:`~.Bot.after_invoke`
            hooks are only called if all checks and argument parsing
            procedures pass without error. If any check or argument parsing
            procedures fail then the hooks are not called.

        Parameters
        ----------
        coro
            The coroutine to register as the pre-invoke hook.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('The pre-invoke hook must be a coroutine.')

        self._before_invoke = coro
        return coro

    def after_invoke(self, coro: MaybeCoro) -> MaybeCoro:
        r"""A decorator that registers a coroutine as a post-invoke hook.

        A post-invoke hook is called directly after the command is
        called. This makes it a useful function to clean-up database
        connections or any type of clean up required.

        This post-invoke hook takes a sole parameter, a :class:`.Context`.

        .. note::

            Similar to :meth:`~.Bot.before_invoke`\, this is not called unless
            checks and argument parsing procedures succeed. This hook is,
            however, **always** called regardless of the internal command
            callback raising an error (i.e. :exc:`.CommandInvokeError`\).
            This makes it ideal for clean-up scenarios.

        Parameters
        ----------
        coro:
            The coroutine to register as the post-invoke hook.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('The post-invoke hook must be a coroutine.')

        self._after_invoke = coro
        return coro

    def add_cog(self, cog: Cog) -> None:
        """Adds a "cog" to the bot.

        A cog is a class that has its own event listeners and commands.

        Parameters
        ----------
        cog: :class:`.Cog`
            The cog to register to the bot.

        Raises
        ------
        TypeError
            The cog does not inherit from :class:`.Cog`.
        CommandError
            An error happened during loading.
        """

        if not isinstance(cog, Cog):
            raise TypeError('Cogs must derive from Cog.')

        cog = cog._inject(self)
        self.__cogs[cog.__cog_name__] = cog

    def remove_cog(self, name: str) -> None:
        """Removes a cog from the bot.

        All registered commands and event listeners that the
        cog has registered will be removed as well.

        If no cog is found then this method has no effect.

        Parameters
        ----------
        name: :class:`str`
            The name of the cog to remove.
        """
        cog = self.__cogs.pop(name, None)
        if cog is None:
            return

        help_command = self.help_command
        if help_command and help_command.cog is cog:
            help_command.cog = None

        cog._eject(self)

    def get_cog(self, name: str) -> Optional[Cog]:
        """Gets the cog instance requested.

        If the cog is not found, ``None`` is returned instead.

        Parameters
        -----------
        name: :class:`str`
            The name of the cog you are requesting.
            This is equivalent to the name passed via keyword
            argument in class creation or the class name if unspecified.
        """
        return self.__cogs.get(name)

    @property
    def cogs(self) -> Mapping[str, Cog]:
        """Mapping[:class:`str`, :class:`Cog`]: A read-only mapping of cog
        name to cog.
        """
        return types.MappingProxyType(self.__cogs)

    def _remove_module_references(self, name: str) -> None:
        # find all references to the module
        # remove the cogs registered from the module
        for cogname, cog in self.__cogs.copy().items():
            if _is_submodule(name, cog.__module__):
                self.remove_cog(cogname)

        # remove all the commands from the module
        for cmd in self.all_commands.copy().values():
            if cmd.module is not None and _is_submodule(name, cmd.module):
                if isinstance(cmd, GroupMixin):
                    cmd.recursively_remove_all_commands()
                self.remove_command(cmd.name)

        # remove all the listeners from the module
        for event_list in self._events.copy().values():
            remove = []
            for index, event in enumerate(event_list):
                if (event.__module__ is not None
                        and _is_submodule(name, event.__module__)):
                    remove.append(index)

            for index in reversed(remove):
                del event_list[index]

    def _call_module_finalizers(self, lib: object, key: str) -> None:
        try:
            func = getattr(lib, 'cog_teardown')
        except AttributeError:
            pass
        else:
            try:
                func(self)
            except Exception:
                pass
        finally:
            self.__extensions.pop(key, None)
            sys.modules.pop(key, None)
            name = lib.__name__
            for module in list(sys.modules.keys()):
                if _is_submodule(name, module):
                    del sys.modules[module]

    def _load_from_module_spec(self, spec: types.ModuleType,
                               key: str) -> None:
        # precondition: key not in self.__extensions
        lib = importlib.util.module_from_spec(spec)
        sys.modules[key] = lib
        try:
            spec.loader.exec_module(lib)
        except Exception as e:
            del sys.modules[key]
            raise ExtensionFailed(key, e) from e

        try:
            setup = getattr(lib, 'extension_setup')
        except AttributeError:
            del sys.modules[key]
            raise ExtensionMissingEntryPoint(key)

        try:
            setup(self)
        except Exception as e:
            del sys.modules[key]
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, key)
            raise ExtensionFailed(key, e) from e
        else:
            self.__extensions[key] = lib

    def load_extension(self, name: str) -> None:
        """Loads an extension.

        An extension is a python module that contains commands, cogs, or
        listeners.

        An extension must have a global function, ``extension_setup`` defined
        as the entry point on what to do when the extension is loaded. This
        entry point must have a single argument, the ``bot``.

        Parameters
        ----------
        name: :class:`str`
            The extension name to load. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.

        Raises
        ------
        ExtensionNotFound
            The extension could not be imported.
        ExtensionAlreadyLoaded
            The extension is already loaded.
        ExtensionMissingEntryPoint
            The extension does not have a extension_setup function.
        ExtensionFailed
            The extension or its setup function had an execution error.
        """
        if name in self.__extensions:
            raise ExtensionAlreadyLoaded(name)

        spec = importlib.util.find_spec(name)
        if spec is None:
            raise ExtensionNotFound(name)

        self._load_from_module_spec(spec, name)

    def unload_extension(self, name: str) -> None:
        """Unloads an extension.

        When the extension is unloaded, all commands, listeners, and cogs are
        removed from the bot and the module is un-imported.

        The extension can provide an optional global function,
        ``cog_teardown``, to do miscellaneous clean-up if necessary. This
        function takes a single parameter, the ``bot``, similar to
        ``extension_setup`` from :meth:`~.Bot.load_extension`.

        Parameters
        ------------
        name: :class:`str`
            The extension name to unload. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.

        Raises
        -------
        ExtensionNotLoaded
            The extension was not loaded.
        """
        lib = self.__extensions.get(name)
        if lib is None:
            raise ExtensionNotLoaded(name)

        self._remove_module_references(lib.__name__)
        self._call_module_finalizers(lib, name)

    def reload_extension(self, name: str) -> None:
        """Atomically reloads an extension.

        This replaces the extension with the same extension, only refreshed.
        This is equivalent to a :meth:`unload_extension` followed by
        a :meth:`load_extension` except done in an atomic way. That is, if an
        operation fails mid-reload then the bot will roll-back to the prior
        working state.

        Parameters
        ------------
        name: :class:`str`
            The extension name to reload. It must be dot separated like
            regular Python imports if accessing a sub-module. e.g.
            ``foo.test`` if you want to import ``foo/test.py``.

        Raises
        -------
        ExtensionNotLoaded
            The extension was not loaded.
        ExtensionNotFound
            The extension could not be imported.
        ExtensionMissingEntryPoint
            The extension does not have a extension_setup function.
        ExtensionFailed
            The extension setup function had an execution error.
        """
        lib = self.__extensions.get(name)
        if lib is None:
            raise ExtensionNotLoaded(name)

        # get the previous module states from sys modules
        modules = {
            name: module
            for name, module in sys.modules.items()
            if _is_submodule(lib.__name__, name)
        }

        try:
            # Unload and then load the module...
            self._remove_module_references(lib.__name__)
            self._call_module_finalizers(lib, name)
            self.load_extension(name)
        except Exception:
            # if the load failed, the remnants should have been
            # cleaned from the load_extension function call
            # so let's load it from our old compiled library.
            lib.extension_setup(self)
            self.__extensions[name] = lib

            # revert sys.modules back to normal and raise back to caller
            sys.modules.update(modules)
            raise

    @property
    def extensions(self) -> Mapping[str, types.ModuleType]:
        """Mapping[:class:`str`, :class:`py:types.ModuleType`]: A read-only
        mapping of extension name to extension.
        """
        return types.MappingProxyType(self.__extensions)

    @property
    def help_command(self) -> Optional[HelpCommand]:
        return self._help_command

    @help_command.setter
    def help_command(self, value: Optional[HelpCommand]) -> None:
        if value is not None:
            if not isinstance(value, HelpCommand):
                raise TypeError('help_command must be a subclass '
                                'of HelpCommand')
            if self._help_command is not None:
                self._help_command._remove_from_bot(self)
            self._help_command = value
            value._add_to_bot(self)
        elif self._help_command is not None:
            self._help_command._remove_from_bot(self)
            self._help_command = None
        else:
            self._help_command = None

    async def get_prefix(self, message: Message) -> Any:
        """|coro|

        Retrieves the prefix the bot is listening to with the message as
        a context.

        Parameters
        ----------
        message: Union[:class:`fortnitepy.FriendMessage`, :class:`fortnitepy.PartyMessage`]
            The message context to get the prefix of.

        Returns
        --------
        Union[List[:class:`str`], :class:`str`]
            A list of prefixes or a single prefix that the bot is
            listening for.
        """  # noqa

        prefix = ret = self.command_prefix
        if callable(prefix):
            if asyncio.iscoroutinefunction(prefix):
                ret = await prefix(self, message)
            else:
                ret = prefix(self, message)

        if not isinstance(ret, str):
            try:
                ret = list(ret)
            except TypeError:
                # It's possible that a generator raised this exception.  Don't
                # replace it with our own error if that's the case.
                if isinstance(ret, collections.abc.Iterable):
                    raise

                raise TypeError('command_prefix must be plain string, '
                                'iterable of strings, or callable '
                                'returning either of these, not '
                                '{}'.format(ret.__class__.__name__))

            if not ret:
                raise ValueError('Iterable command_prefix must contain at '
                                 'least one prefix')

        return ret

    async def get_context(self, message: Message, *,
                          cls: Context = Context) -> Context:
        r"""|coro|

        Returns the invocation context from the message.

        This is a more low-level counter-part for :meth:`.process_commands`
        to allow users more fine grained control over the processing.

        The returned context is not guaranteed to be a valid invocation
        context, :attr:`.Context.valid` must be checked to make sure it is.

        If the context is not valid then it is not a valid candidate to be
        invoked under :meth:`~.Bot.invoke`.

        Parameters
        ----------
        message: Union[:class:`fortnitepy.FriendMessage`, :class:`fortnitepy.PartyMessage`]
            The message to get the invocation context from.
        cls
            The factory class that will be used to create the context.
            By default, this is :class:`.Context`. Should a custom
            class be provided, it must be similar enough to :class:`.Context`\'s
            interface.

        Returns
        -------
        :class:`.Context`
            The invocation context. The type of this can change via the
            ``cls`` parameter.
        """  # noqa

        view = StringView(message.content)
        ctx = cls(prefix=None, view=view, bot=self, message=message)

        prefix = await self.get_prefix(message)
        invoked_prefix = prefix

        if isinstance(prefix, str):
            if not view.skip_string(prefix):
                return ctx
        else:
            try:
                if message.content.startswith(tuple(prefix)):
                    for element in prefix:
                        if view.skip_string(element):
                            invoked_prefix = element
                            break
                    else:
                        invoked_prefix = None
                else:
                    return ctx

            except TypeError:
                if not isinstance(prefix, list):
                    raise TypeError('get_prefix must return either a string '
                                    'or a list of string, not '
                                    '{}'.format(prefix.__class__.__name__))

                for value in prefix:
                    if not isinstance(value, str):
                        raise TypeError('Iterable command_prefix or list '
                                        'returned from get_prefix must '
                                        'contain only strings, not '
                                        '{}'.format(value.__class__.__name__))

                raise

        invoker = view.get_word()
        ctx.invoked_with = invoker
        ctx.prefix = invoked_prefix
        ctx.command = self.all_commands.get(invoker)
        return ctx

    def _print_error(self, ctx: Context, error: Exception) -> None:
        print(
            'Ignoring exception in command {}:'.format(ctx.command),
            file=sys.stderr
        )
        traceback.print_exception(
            type(error),
            error,
            error.__traceback__,
            file=sys.stderr
        )

    async def wait_for_futures(self, futures: ListOrTuple, *,
                               check: Optional[callable] = None,
                               timeout: Optional[int] = None,
                               cancel: bool = False) -> None:

        def _cancel_futs(pending_futures: Set[asyncio.Future]) -> None:
            for p in pending_futures:
                if not p.cancelled():
                    p.cancel()

        pending = futures
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout
            )

            # Set should only contain one value
            for future in done:
                if check is None or check(future):
                    if cancel:
                        _cancel_futs(pending)
                    return future

    async def _wait_for_error_return(self, futures: List[asyncio.Future],
                                     ctx: Context,
                                     error: Exception) -> None:
        def check(future):
            return future.result() is False

        ret = await self.wait_for_futures(futures, check=check)
        if isinstance(ret, asyncio.Future):
            self._print_error(ctx, error)

    def dispatch_error(self, ctx: Context, error: Exception) -> None:
        if self._event_has_handler('command_error'):
            futures = self.dispatch_event('command_error', ctx, error)
            asyncio.ensure_future(self._wait_for_error_return(
                futures,
                ctx,
                error
            ))
        else:
            self._print_error(ctx, error)

    async def invoke(self, ctx: Context) -> None:
        """|coro|

        Invokes the command given under the invocation context and
        handles all the internal event dispatch mechanisms.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context to invoke.
        """

        if ctx.command is not None:
            self.dispatch_event('command', ctx)

            try:
                if await self.can_run(ctx, call_once=True):
                    await ctx.command.invoke(ctx)
                else:
                    raise CheckFailure('The global check once functions '
                                       'failed.')
            except CommandError as exc:
                await ctx.command.dispatch_error(ctx, exc)
            else:
                self.dispatch_event('command_completion', ctx)

        elif ctx.invoked_with:
            exc = CommandNotFound('Command "{}" is not found'
                                  ''.format(ctx.invoked_with))
            self.dispatch_error(ctx, exc)

    async def process_commands(self, message: Message) -> None:
        """|coro|

        This function processes the commands that have been registered
        to the bot and other groups. Without this coroutine, none of the
        commands will be triggered.

        By default, this coroutine is called automatically when a new
        message is received.

        This is built using other low level tools, and is equivalent to a
        call to :meth:`~.Bot.get_context` followed by a call to
        :meth:`~.Bot.invoke`.

        Parameters
        -----------
        message: Union[:class:`fortnitepy.FriendMessage`, :class:`fortnitepy.PartyMessage`]
            The message to process commands for.
        """  # noqa

        if message.author.id == self.user.id:
            return

        ctx = await self.get_context(message)
        await self.invoke(ctx)
