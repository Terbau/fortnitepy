import asyncio
import functools
import inspect
import datetime

from collections import OrderedDict
from typing import Iterable, Optional, Union, Awaitable, Any, Set
from fortnitepy.errors import FortniteException
from fortnitepy.typedefs import MaybeCoro

from . import converter as converters
from . import errors
from ._types import _BaseCommand
from .cog import Cog
from .cooldown import Cooldown, BucketType, CooldownMapping, MaxConcurrency
from .context import Context
from .converter import Converter


__all__ = (
    'Command',
    'Group',
    'GroupMixin',
    'command',
    'group',
    'check',
    'check_any',
    'before_invoke',
    'after_invoke',
    'cooldown',
    'max_concurrency',
    'dm_only',
    'party_only',
    'is_owner',
)


def wrap_callback(coro: Awaitable) -> Awaitable:
    @functools.wraps(coro)
    async def wrapped(*args: list, **kwargs: dict) -> Any:
        try:
            ret = await coro(*args, **kwargs)
        except errors.CommandError:
            raise
        except asyncio.CancelledError:
            return
        except Exception as exc:
            raise errors.CommandInvokeError(exc) from exc
        return ret
    return wrapped


def hooked_wrapped_callback(command: 'Command',
                            ctx: Context,
                            coro: Awaitable) -> Awaitable:
    @functools.wraps(coro)
    async def wrapped(*args: list, **kwargs: dict) -> Awaitable:
        try:
            ret = await coro(*args, **kwargs)
        except errors.CommandError:
            ctx.command_failed = True
            raise
        except asyncio.CancelledError:
            ctx.command_failed = True
            return
        except Exception as exc:
            ctx.command_failed = True
            raise errors.CommandInvokeError(exc) from exc
        finally:
            if command._max_concurrency is not None:
                await command._max_concurrency.release(ctx)

            await command.call_after_hooks(ctx)

        return ret
    return wrapped


def _convert_to_bool(argument: str) -> bool:
    lowered = argument.lower()
    if lowered in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
        return True
    elif lowered in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
        return False
    else:
        raise errors.BadArgument(
            lowered + ' is not a recognised boolean option'
        )


class _CaseInsensitiveDict(dict):
    def __contains__(self, k):
        return super().__contains__(k.casefold())

    def __delitem__(self, k):
        return super().__delitem__(k.casefold())

    def __getitem__(self, k):
        return super().__getitem__(k.casefold())

    def get(self, k, default=None):
        return super().get(k.casefold(), default)

    def pop(self, k, default=None):
        return super().pop(k.casefold(), default)

    def __setitem__(self, k, v):
        super().__setitem__(k.casefold(), v)


class Command(_BaseCommand):
    r"""A class that implements the protocol for a bot text command.
    These are not created manually, instead they are created via the
    decorator or functional interface.

    Attributes
    -----------
    name: :class:`str`
        The name of the command.
    callback:
        The coroutine that is executed when the command is called.
    help: :class:`str`
        The long help text for the command.
    brief: :class:`str`
        The short help text for the command. If this is not specified
        then the first line of the long help text is used instead.
    usage: :class:`str`
        A replacement for arguments in the default help text.
    aliases: Union[:class:`list`, :class:`tuple`]
        The list of aliases the command can be invoked under.
    enabled: :class:`bool`
        A boolean that indicates if the command is currently enabled.
        If the command is invoked while it is disabled, then
        :exc:`.DisabledCommand` is raised to the :func:`.event_command_error`
        event. Defaults to ``True``.
    parent: Optional[:class:`Command`]
        The parent command that this command belongs to. ``None`` if there
        isn't one.
    cog: Optional[:class:`Cog`]
        The cog that this command belongs to. ``None`` if there isn't one.
    checks: List[Callable[..., :class:`bool`]]
        A list of predicates that verifies if the command could be executed
        with the given :class:`.Context` as the sole parameter. If an exception
        is necessary to be thrown to signal failure, then one inherited from
        :exc:`.CommandError` should be used. Note that if the checks fail then
        :exc:`.CheckFailure` exception is raised to the
        :func:`.event_command_error` event.
    description: :class:`str`
        The message prefixed into the default help command.
    hidden: :class:`bool`
        If ``True``\, the default help command does not show this in the
        help output.
    rest_is_raw: :class:`bool`
        If ``False`` and a keyword-only argument is provided then the keyword
        only argument is stripped and handled as if it was a regular argument
        that handles :exc:`.MissingRequiredArgument` and default values in a
        regular matter rather than passing the rest completely raw. If ``True``
        then the keyword-only argument will pass in the rest of the arguments
        in a completely raw matter. Defaults to ``False``.
    invoked_subcommand: Optional[:class:`Command`]
        The subcommand that was invoked, if any.
    ignore_extra: :class:`bool`
        If ``True``\, ignores extraneous strings passed to a command if all its
        requirements are met (e.g. ``?foo a b c`` when only expecting ``a``
        and ``b``). Otherwise :func:`.event_command_error` and local error
        handlers are called with :exc:`.TooManyArguments`. Defaults to
        ``True``.
    cooldown_after_parsing: :class:`bool`
        If ``True``\, cooldown processing is done after argument parsing,
        which calls converters. If ``False`` then cooldown processing is done
        first and then the converters are called second. Defaults to ``False``.
    """

    def __new__(cls, *args: list, **kwargs: dict) -> 'Command':
        self = super().__new__(cls)

        self.__fnpy_original_kwargs__ = kwargs.copy()
        return self

    def __init__(self, coro: Awaitable, **kwargs: dict) -> None:
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Command callback must be a coroutine')

        self.name = kwargs.get('name') or coro.__name__
        if not isinstance(self.name, str):
            raise TypeError('The name of the command must be a string')

        self.callback = coro
        self.enabled = kwargs.get('enabled', True)

        help_doc = kwargs.get('help')
        if help_doc is not None:
            help_doc = inspect.cleandoc(help_doc)
        else:
            help_doc = inspect.getdoc(coro)
            if isinstance(help_doc, bytes):
                help_doc = help_doc.decode('utf-8')

        self.help = help_doc

        self.brief = kwargs.get('brief')
        self.usage = kwargs.get('usage')
        self.rest_is_raw = kwargs.get('rest_is_raw', False)
        self.aliases = kwargs.get('aliases', [])

        if not isinstance(self.aliases, (list, tuple)):
            raise TypeError('aliases must be a list or tuple')

        self.description = inspect.cleandoc(kwargs.get('description', ''))
        self.hidden = kwargs.get('hidden', False)

        try:
            checks = coro.__fnpy_commands_checks__
            checks.reverse()
        except AttributeError:
            checks = kwargs.get('checks', [])
        finally:
            self.checks = checks

        try:
            cooldown = coro.__fnpy_commands_cooldown__
        except AttributeError:
            cooldown = kwargs.get('cooldown')
        finally:
            self._buckets = CooldownMapping(cooldown)

        try:
            max_concurrency = coro.__fnpy_commands_max_concurrency__
        except AttributeError:
            max_concurrency = kwargs.get('max_concurrency')
        finally:
            self._max_concurrency = max_concurrency

        self.ignore_extra = kwargs.get('ignore_extra', True)
        self.cooldown_after_parsing = kwargs.get('cooldown_after_parsing',
                                                 False)
        self.cog = None
        self.instance = None

        # bandaid for the fact that sometimes parent can be the bot instance
        parent = kwargs.get('parent')
        self.parent = parent if isinstance(parent, Command) else None

        try:
            before_invoke = coro.__fnpy_before_invoke__
        except AttributeError:
            self._before_invoke = None
        else:
            self.before_invoke(before_invoke)

        try:
            after_invoke = coro.__fnpy_after_invoke__
        except AttributeError:
            self._after_invoke = None
        else:
            self.after_invoke(after_invoke)

    @property
    def callback(self) -> Awaitable:
        return self._callback

    @callback.setter
    def callback(self, function: Awaitable) -> None:
        self._callback = function
        self.module = function.__module__

        signature = inspect.signature(function)
        self.params = signature.parameters.copy()

        for key, value in self.params.items():
            if isinstance(value.annotation, str):
                self.params[key] = value = value.replace(
                    annotation=eval(value.annotation, function.__globals__)
                )

    @property
    def self_instance(self) -> Union[Cog, object]:
        return self.cog or self.instance

    def add_check(self, func: MaybeCoro) -> None:
        """Adds a check to the command.

        This is the non-decorator interface to :func:`.check`.


        Parameters
        ----------
        func
            The function that will be used as a check.
        """
        self.checks.append(func)

    def remove_check(self, func: MaybeCoro) -> None:
        """Removes a check from the command.

        This function is idempotent and will not raise an exception
        if the function is not in the command's checks.

        Parameters
        -----------
        func
            The function to remove from the checks.
        """

        try:
            self.checks.remove(func)
        except ValueError:
            pass

    def update(self, **kwargs: dict) -> None:
        """Updates :class:`Command` instance with updated attribute.

        This works similarly to the :func:`.command` decorator in terms
        of parameters in that they are passed to the :class:`Command` or
        subclass constructors, sans the name and callback.
        """
        self.__init__(
            self.callback,
            **dict(self.__fnpy_original_kwargs__, **kwargs)
        )

    async def __call__(self, *args: list, **kwargs: dict) -> Any:
        """|coro|

        Calls the internal callback that the command holds.

        .. note::

            This bypasses all mechanisms -- including checks, converters,
            invoke hooks, cooldowns, etc. You must take care to pass
            the proper arguments and types to this function.
        """

        if self.self_instance is not None:
            return await self.callback(self.self_instance, *args, **kwargs)
        else:
            return await self.callback(*args, **kwargs)

    def _ensure_assignment_on_copy(self, other: 'Command') -> 'Command':
        other._before_invoke = self._before_invoke
        other._after_invoke = self._after_invoke
        if self.checks != other.checks:
            other.checks = self.checks.copy()
        if self._buckets.valid and not other._buckets.valid:
            other._buckets = self._buckets.copy()
        if self._max_concurrency != other._max_concurrency:
            other._max_concurrency = self._max_concurrency.copy()

        try:
            other.error_handler = self.error_handler
        except AttributeError:
            pass
        return other

    def copy(self) -> 'Command':
        ret = self.__class__(self.callback, **self.__fnpy_original_kwargs__)
        return self._ensure_assignment_on_copy(ret)

    def _update_copy(self, kwargs: dict) -> 'Command':
        if kwargs:
            kw = kwargs.copy()
            kw.update(self.__fnpy_original_kwargs__)
            copy = self.__class__(self.callback, **kw)
            return self._ensure_assignment_on_copy(copy)
        else:
            return self.copy()

    async def dispatch_error(self, ctx: Context, error: Exception) -> Any:
        ctx.command_failed = True
        cog = self.cog
        instance = self.self_instance

        ret = False

        try:
            coro = self.error_handler
        except AttributeError:
            pass
        else:
            injected = wrap_callback(coro)
            if instance is not None:
                ret = await injected(instance, ctx, error)
            else:
                ret = await injected(ctx, error)

        if ret is False:
            if cog is not None:
                local = Cog._get_overridden_method(cog.cog_command_error)
                if local is not None:
                    wrapped = wrap_callback(local)
                    ret = await wrapped(ctx, error)

        if ret is False:
            ctx.bot.dispatch_error(ctx, error)

    async def _actual_conversion(self,
                                 ctx: Context,
                                 converter: Converter,
                                 argument: str,
                                 param: inspect.Parameter) -> Any:
        if converter is bool:
            return _convert_to_bool(argument)

        try:
            module = converter.__module__
        except AttributeError:
            pass
        else:
            if module is not None and (module.startswith('fortnitepy.')
                                       and not module.endswith('converter')):
                converter = getattr(
                    converters,
                    converter.__name__ + 'Converter',
                    converter
                )

        try:
            if inspect.isclass(converter):
                if issubclass(converter, converters.Converter):
                    instance = converter()
                    ret = await instance.convert(ctx, argument)
                    return ret
                else:
                    method = getattr(converter, 'convert', None)
                    if method is not None and inspect.ismethod(method):
                        ret = await method(ctx, argument)
                        return ret

            elif isinstance(converter, converters.Converter):
                ret = await converter.convert(ctx, argument)
                return ret

        except errors.CommandError:
            raise
        except Exception as exc:
            raise errors.ConversionError(converter, exc) from exc

        try:
            return converter(argument)
        except errors.CommandError:
            raise
        except Exception as exc:
            try:
                name = converter.__name__
            except AttributeError:
                name = converter.__class__.__name__

            raise errors.BadArgument('Converting to "{}" failed for parameter '
                                     '"{}".'.format(name, param.name)) from exc

    async def do_conversion(self, ctx: Context,
                            converter: Converter,
                            argument: str,
                            param: inspect.Parameter) -> Any:
        try:
            origin = converter.__origin__
        except AttributeError:
            pass
        else:
            if origin is Union:
                errors = []
                NoneType = type(None)
                for conv in converter.__args__:
                    if conv is NoneType and param.kind != param.VAR_POSITIONAL:
                        ctx.view.undo()
                        if param.default is param.empty:
                            return None
                        else:
                            return param.default

                    try:
                        value = await self._actual_conversion(
                            ctx,
                            conv,
                            argument,
                            param
                        )
                    except errors.CommandError as exc:
                        errors.append(exc)
                    else:
                        return value

                raise errors.BadUnionArgument(
                    param,
                    converter.__args__,
                    errors
                )

        return await self._actual_conversion(ctx, converter, argument, param)

    def _get_converter(self, param: inspect.Parameter) -> inspect.Parameter:
        conv = param.annotation
        if conv is param.empty:
            if param.default is not param.empty:
                conv = str if param.default is None else type(param.default)
            else:
                conv = str

        return conv

    async def transform(self, ctx: Context, param: inspect.Parameter) -> Any:
        required = param.default is param.empty
        converter = self._get_converter(param)
        consume_rest_is_special = (param.kind == param.KEYWORD_ONLY
                                   and not self.rest_is_raw)
        view = ctx.view
        view.skip_ws()

        if type(converter) is converters._Greedy:
            if param.kind == param.POSITIONAL_OR_KEYWORD:
                return await self._transform_greedy_pos(
                    ctx,
                    param,
                    required,
                    converter.converter
                )
            elif param.kind == param.VAR_POSITIONAL:
                return await self._transform_greedy_var_pos(
                    ctx,
                    param,
                    converter.converter
                )
            else:
                converter = converter.converter

        if view.eof:
            if param.kind == param.VAR_POSITIONAL:
                raise RuntimeError()

            if required:
                if self._is_typing_optional(param.annotation):
                    return None
                raise errors.MissingRequiredArgument(param)
            return param.default

        previous = view.index
        if consume_rest_is_special:
            argument = view.read_rest().strip()
        else:
            argument = view.get_quoted_word()
        view.previous = previous

        return await self.do_conversion(ctx, converter, argument, param)

    async def _transform_greedy_pos(self, ctx: Context,
                                    param: inspect.Parameter,
                                    required: bool,
                                    converter: Converter) -> Any:
        view = ctx.view
        result = []
        while not view.eof:
            previous = view.index

            view.skip_ws()
            try:
                argument = view.get_quoted_word()
                value = await self.do_conversion(
                    ctx,
                    converter,
                    argument,
                    param
                )
            except (errors.CommandError, errors.ArgumentParsingError):
                view.index = previous
                break
            else:
                result.append(value)

        if not result and not required:
            return param.default
        return result

    async def _transform_greedy_var_pos(self, ctx: Context,
                                        param: inspect.Parameter,
                                        converter: Converter) -> Any:
        view = ctx.view
        previous = view.index
        try:
            argument = view.get_quoted_word()
            value = await self.do_conversion(ctx, converter, argument, param)
        except (errors.CommandError, errors.ArgumentParsingError):
            view.index = previous
            raise RuntimeError() from None
        else:
            return value

    @property
    def clean_params(self) -> OrderedDict:
        """OrderedDict[:class:`str`, :class:`typing.Parameter`]: Retrieves the
        parameter OrderedDict without the context or self parameters.

        Useful for inspecting signature.
        """

        result = self.params.copy()
        if self.self_instance is not None:
            result.popitem(last=False)

        try:
            result.popitem(last=False)
        except Exception:
            raise ValueError('Missing context parameter') from None

        return result

    @property
    def full_parent_name(self) -> str:
        """:class:`str`: Retrieves the fully qualified parent command name.

        This is the base command name required to execute it. For example,
        in ``?one two three`` the parent name would be ``one two``.
        """

        elems = []
        command = self
        while command.parent is not None:
            command = command.parent
            elems.append(command.name)

        return ' '.join(reversed(elems))

    @property
    def parents(self) -> 'Command':
        """:class:`Command`: Retrieves the parents of this command.

        If the command has no parents then it returns an empty :class:`list`.

        For example in commands ``?a b c test``, the parents are ``[c, b, a]``.
        """

        elems = []
        command = self
        while command.parent is not None:
            command = command.parent
            elems.append(command)

        return elems

    @property
    def root_parent(self) -> 'Command':
        """Retrieves the root parent of this command.

        If the command has no parents then it returns ``None``.

        For example in commands ``?a b c test``, the root parent is ``a``.
        """

        if not self.parent:
            return None

        return self.parents[-1]

    @property
    def qualified_name(self) -> str:
        """:class:`str`: Retrieves the fully qualified command name.

        This is the full parent name with the command name as well.

        For example, in ``?one two three`` the qualified name would be
        ``one two three``.
        """

        parent_name = self.full_parent_name
        if parent_name:
            return '{} {}'.format(parent_name, self.name)
        else:
            return self.name

    def __str__(self) -> str:
        return self.qualified_name

    async def _parse_arguments(self, ctx: Context) -> None:
        instance = self.self_instance
        ctx.args = [ctx] if instance is None else [instance, ctx]
        ctx.kwargs = {}
        args = ctx.args
        kwargs = ctx.kwargs

        view = ctx.view
        iterator = iter(self.params.items())

        if instance is not None:
            try:
                next(iterator)
            except StopIteration:
                raise FortniteException(
                    'Callback for {0.name} command is missing '
                    '"self" parameter.'.format(self)
                )

        try:
            next(iterator)
        except StopIteration:
            raise FortniteException(
                'Callback for {0.name} command is missing '
                '"ctx" parameter.'.format(self)
            )

        for name, param in iterator:
            if param.kind == param.POSITIONAL_OR_KEYWORD:
                transformed = await self.transform(ctx, param)
                args.append(transformed)

            elif param.kind == param.KEYWORD_ONLY:
                if self.rest_is_raw:
                    converter = self._get_converter(param)
                    argument = view.read_rest()
                    kwargs[name] = await self.do_conversion(
                        ctx,
                        converter,
                        argument,
                        param
                    )
                else:
                    kwargs[name] = await self.transform(ctx, param)
                break

            elif param.kind == param.VAR_POSITIONAL:
                while not view.eof:
                    try:
                        transformed = await self.transform(ctx, param)
                        args.append(transformed)
                    except RuntimeError:
                        break

        if not self.ignore_extra:
            if not view.eof:
                fmt = 'Too many arguments passed to ' + self.qualified_name
                raise errors.TooManyArguments(fmt)

    async def call_before_hooks(self, ctx: Context) -> None:
        inst = self.self_instance
        cog = self.cog
        if self._before_invoke is not None:
            try:
                instance = self._before_invoke.__self__
            except AttributeError:
                if inst:
                    await self._before_invoke(inst, ctx)
                else:
                    await self._before_invoke(ctx)
            else:
                await self._before_invoke(instance, ctx)

        if cog is not None:
            hook = Cog._get_overridden_method(cog.cog_before_invoke)
            if hook is not None:
                await hook(ctx)

        hook = ctx.bot._before_invoke
        if hook is not None:
            await hook(ctx)

    async def call_after_hooks(self, ctx: Context) -> None:
        inst = self.self_instance
        cog = self.cog
        if self._after_invoke is not None:
            try:
                instance = self._after_invoke.__self__
            except AttributeError:
                if inst:
                    await self._after_invoke(inst, ctx)
                else:
                    await self._after_invoke(ctx)
            else:
                await self._after_invoke(instance, ctx)

        if cog is not None:
            hook = Cog._get_overridden_method(cog.cog_after_invoke)
            if hook is not None:
                await hook(ctx)

        hook = ctx.bot._after_invoke
        if hook is not None:
            await hook(ctx)

    def _prepare_cooldowns(self, ctx: Context) -> None:
        if self._buckets.valid:
            current = ctx.message.created_at.replace(
                tzinfo=datetime.timezone.utc
            )
            timestamp = current.timestamp()

            bucket = self._buckets.get_bucket(ctx.message, timestamp)
            retry_after = bucket.update_rate_limit(timestamp)
            if retry_after:
                raise errors.CommandOnCooldown(bucket, retry_after)

    async def prepare(self, ctx: Context) -> None:
        ctx.command = self

        if not await self.can_run(ctx):
            raise errors.CheckFailure(
                'The checks for command {0.qualified_name} failed'.format(self)
            )

        if self.cooldown_after_parsing:
            await self._parse_arguments(ctx)
            self._prepare_cooldowns(ctx)
        else:
            self._prepare_cooldowns(ctx)
            await self._parse_arguments(ctx)

        if self._max_concurrency is not None:
            await self._max_concurrency.acquire(ctx)

        await self.call_before_hooks(ctx)

    def is_on_cooldown(self, ctx: Context) -> bool:
        """Checks whether the command is currently on cooldown.

        Parameters
        ----------
        ctx: :class:`.Context`
            The invocation context to use when checking the commands
            cooldown status.

        Returns
        --------
        :class:`bool`
            A boolean indicating if the command is on cooldown.
        """

        if not self._buckets.valid:
            return False

        bucket = self._buckets.get_bucket(ctx.message)
        return bucket.get_tokens() == 0

    def reset_cooldown(self, ctx: Context) -> None:
        """Resets the cooldown on this command.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context to reset the cooldown under.
        """

        if self._buckets.valid:
            bucket = self._buckets.get_bucket(ctx.message)
            bucket.reset()

    async def invoke(self, ctx: Context) -> None:
        await self.prepare(ctx)

        ctx.invoked_subcommand = None
        injected = hooked_wrapped_callback(self, ctx, self.callback)
        await injected(*ctx.args, **ctx.kwargs)

    async def reinvoke(self, ctx: Context, *,
                       call_hooks: bool = False) -> None:
        ctx.command = self
        await self._parse_arguments(ctx)

        if call_hooks:
            await self.call_before_hooks()

        ctx.invoked_subcommand = None
        try:
            await self.callback(*ctx.args, **ctx.kwargs)
        except Exception:
            ctx.command_failed = True
            raise
        finally:
            if call_hooks:
                await self.call_after_hooks()

    def error(self, coro: Awaitable) -> Awaitable:
        """A decorator that registers a coroutine as a local error handler.

        A local error handler is an :func:`.event_command_error` event limited
        to a single command.

        Command error handlers are raised in a specific order. Returning
        ``False`` in any of them will invoke the next handler in the chain. If
        there are no handlers left to call, then the error is printed to
        stderr (console).

        The order goes as follows:
        1. The local command error handler is called. (Handler specified by
        this decorator.)
        2. The local cog command error handler is called.
        3. All :func:`.event_command_error()` handlers are called
        simultaneously. If any of them return False, then the error will
        be printed.

        Parameters
        ----------
        coro:
            The coroutine to register as the local error handler.

        Raises
        ------
        TypeError
            The coroutine passed is not actually a coroutine.
        """

        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Error handler must be a coroutine')

        self.error_handler = coro
        return coro

    def before_invoke(self, coro: Awaitable) -> Awaitable:
        """A decorator that registers a coroutine as a pre-invoke hook.

        A pre-invoke hook is called directly before the command is
        called. This makes it a useful function to set up database
        connections or any type of set up required.

        This pre-invoke hook takes a sole parameter, a :class:`.Context`.
        See :meth:`.Bot.before_invoke` for more info.

        Parameters
        -----------
        coro:
            The coroutine to register as the pre-invoke hook.

        Raises
        -------
        TypeError
            The coroutine passed is not actually a coroutine.
        """

        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Before invoke handler must be a coroutine')

        self._before_invoke = coro
        return coro

    def after_invoke(self, coro: Awaitable) -> Awaitable:
        """A decorator that registers a coroutine as a post-invoke hook.

        A post-invoke hook is called directly after the command is
        called. This makes it a useful function to clean-up database
        connections or any type of clean up required.

        This post-invoke hook takes a sole parameter, a :class:`.Context`.
        See :meth:`.Bot.after_invoke` for more info.

        Parameters
        -----------
        coro:
            The coroutine to register as the post-invoke hook.

        Raises
        -------
        TypeError
            The coroutine passed is not actually a coroutine.
        """

        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('After invoke handler must be a coroutine')

        self._after_invoke = coro
        return coro

    @property
    def cog_name(self) -> str:
        """:class:`str`: The name of the cog this command
        belongs to. ``None`` otherwise.
        """
        return type(self.cog).__cog_name__ if self.cog is not None else None

    @property
    def short_doc(self) -> str:
        """:class:`str`: Gets the "short" documentation of a command.

        By default, this is the :attr:`brief` attribute.
        If that lookup leads to an empty string then the first line of the
        :attr:`help` attribute is used instead.
        """
        if self.brief is not None:
            return self.brief

        if self.help is not None:
            return self.help.split('\n', 1)[0]

        return ''

    def _is_typing_optional(self, annotation: Any) -> bool:
        try:
            origin = annotation.__origin__
        except AttributeError:
            return False

        if origin is not Union:
            return False

        NoneType = type(None)
        return annotation.__args__[-1] is NoneType

    @property
    def signature(self) -> str:
        """:class:`str`: Returns a POSIX-like signature useful
        for help command output.
        """

        if self.usage is not None:
            return self.usage

        params = self.clean_params
        if not params:
            return ''

        result = []
        for name, param in params.items():
            greedy = isinstance(param.annotation, converters._Greedy)

            if param.default is not param.empty:
                if isinstance(param.default, str):
                    should_print = param.default
                else:
                    should_print = param.default is not None

                if should_print:
                    result.append(
                        '[%s=%s]' % (name, param.default) if not greedy else
                        '[%s=%s]...' % (name, param.default)
                    )
                    continue
                else:
                    result.append('[%s]' % name)

            elif param.kind == param.VAR_POSITIONAL:
                result.append('[%s...]' % name)
            elif greedy:
                result.append('[%s]...' % name)
            elif self._is_typing_optional(param.annotation):
                result.append('[%s]' % name)
            else:
                result.append('<%s>' % name)

        return ' '.join(result)

    async def can_run(self, ctx: Context) -> bool:
        """|coro|

        Checks if the command can be executed by checking all the predicates
        inside the :attr:`.checks` attribute. This also checks whether the
        command is disabled.

        Parameters
        -----------
        ctx: :class:`.Context`
            The ctx of the command currently being invoked.

        Raises
        -------
        :class:`CommandError`
            Any command error that was raised during a check call will be
            propagated by this function.

        Returns
        --------
        :class:`bool`
            A boolean indicating if the command can be invoked.
        """

        if not self.enabled:
            raise errors.DisabledCommand(
                '{0.name} command is disabled'.format(self)
            )

        original = ctx.command
        ctx.command = self

        try:
            if not await ctx.bot.can_run(ctx):
                raise errors.CheckFailure(
                    'The global check functions for command '
                    '{0.qualified_name} failed.'.format(self))

            cog = self.cog
            if cog is not None:
                local_check = Cog._get_overridden_method(cog.cog_check)
                if local_check is not None:
                    if asyncio.iscoroutinefunction(local_check):
                        ret = await local_check(ctx)
                    else:
                        ret = local_check(ctx)

                    if not ret:
                        return False

            predicates = self.checks
            if not predicates:
                return True

            for func in predicates:
                if asyncio.iscoroutinefunction(func):
                    res = await func(ctx)
                else:
                    res = func(ctx)

                if not res:
                    return False
            return res

        finally:
            ctx.command = original


class GroupMixin:
    """A mixin that implements common functionality for classes that behave
    similar to :class:`.Group` and are allowed to register commands.

    Attributes
    -----------
    all_commands: :class:`dict`
        A mapping of command name to :class:`.Command` or subclass
        objects.
    case_insensitive: Optional[:class:`bool`]
        The passed value telling if the commands should be case
        insensitive. Defaults to ``None``. Use
        :attr:`~.GroupMixin.qualified_case_insensitive` to check if the command
        truly is case insensitive.
    """

    def __init__(self, *args: list, **kwargs: dict) -> None:
        super().__init__(*args, **kwargs)
        case_ins = kwargs.get('case_insensitive')
        self.all_commands = _CaseInsensitiveDict() if case_ins else {}
        self.case_insensitive = case_ins

    @property
    def qualified_case_insensitive(self) -> Optional[bool]:
        """:class:`bool`: The qualified case insensitive. This means that the
        it will never return ``None`` as it checks inherited values. Could
        be ``None`` but only if the bot is not ultimately registered to the bot
        yet.
        """
        if self.case_insensitive is not None:
            return self.case_insensitive

        parent = getattr(self, 'parent', None)
        if parent is not None:
            return self.parent.case_insensitive
        return self.instance.case_insensitive

    @property
    def commands(self) -> Set[Command]:
        """Set[:class:`.Command`]: A unique set of commands without aliases
        that are registered.
        """
        return set(self.all_commands.values())

    def recursively_remove_all_commands(self) -> None:
        for command in self.all_commands.copy().values():
            if isinstance(command, GroupMixin):
                command.recursively_remove_all_commands()
            self.remove_command(command.name)

    def recursively_make_case_insensitive(self) -> None:
        new_commands = _CaseInsensitiveDict()
        to_make = []
        for key, value in self.all_commands.items():
            new_commands[key] = value

            if isinstance(value, GroupMixin):
                to_make.append(value)

        self.all_commands = new_commands
        for mixin in to_make:
            mixin.recursively_make_case_insensitive()

    def add_command(self, command: Command) -> None:
        """Adds a :class:`.Command` or its subclasses into the internal list
        of commands.

        This is usually not called, instead the :meth:`~.GroupMixin.command` or
        :meth:`~.GroupMixin.group` shortcut decorators are used instead.

        Parameters
        -----------
        command: :class:`Command`
            The command to add.

        Raises
        -------
        :exc:`.ClientException`
            If the command is already registered.
        TypeError
            If the command passed is not a subclass of :class:`.Command`.
        """
        if not isinstance(command, Command):
            raise TypeError(
                'Command passed must be a subclassed instance of Command'
            )

        if isinstance(self, Command):
            command.parent = self

        if command.name in self.all_commands:
            raise errors.CommandError(
                'Command {0.name} is already registered.'.format(command)
            )

        if isinstance(command, GroupMixin):
            if command.case_insensitive is None:
                if command.qualified_case_insensitive:
                    command.recursively_make_case_insensitive()

        self.all_commands[command.name] = command
        for alias in command.aliases:
            if alias in self.all_commands:
                raise errors.CommandError(
                    'The alias {} is already an existing command or '
                    'alias.'.format(alias)
                )

            self.all_commands[alias] = command

    def remove_command(self, name: str) -> Optional[Command]:
        """Remove a :class:`.Command` or subclasses from the internal list
        of commands.

        This could also be used as a way to remove aliases.

        Parameters
        ----------
        name: :class:`str`
            The name of the command to remove.

        Returns
        --------
        :class:`.Command` or subclass
            The command that was removed. If the name is not valid then
            `None` is returned instead.
        """

        command = self.all_commands.pop(name, None)

        if command is None:
            return None

        if name in command.aliases:
            return command

        for alias in command.aliases:
            self.all_commands.pop(alias, None)

        return command

    def walk_commands(self) -> Iterable:
        """An iterator that recursively walks through all commands
        and subcommands.
        """

        for command in self.commands:
            yield command

            if isinstance(command, GroupMixin):
                yield from command.walk_commands()

    def get_command(self, name: str) -> Optional[Command]:
        """Get a :class:`.Command` or subclasses from the internal list
        of commands.

        This could also be used as a way to get aliases.

        The name could be fully qualified (e.g. ``'foo bar'``) will get
        the subcommand ``bar`` of the group command ``foo``. If a
        subcommand is not found then ``None`` is returned just as usual.

        Parameters
        -----------
        name: :class:`str`
            The name of the command to get.

        Returns
        --------
        :class:`Command` or subclass
            The command that was requested. If not found, returns ``None``.
        """

        if ' ' not in name:
            return self.all_commands.get(name)

        names = name.split()
        obj = self.all_commands.get(names[0])
        if not isinstance(obj, GroupMixin):
            return obj

        for name in names[1:]:
            try:
                obj = obj.all_commands[name]
            except (AttributeError, KeyError):
                return None

        return obj

    def command(self, *args: list, **kwargs: dict) -> callable:
        """A shortcut decorator that invokes :func:`.command` and adds
        it to the internal command list via :meth:`~.GroupMixin.add_command`.
        """

        def decorator(func):
            kwargs.setdefault('parent', self)
            result = command(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator

    def group(self, *args: list, **kwargs: dict) -> callable:
        """A shortcut decorator that invokes :func:`.group` and adds it to
        the internal command list via :meth:`~.GroupMixin.add_command`.
        """

        def decorator(func):
            kwargs.setdefault('parent', self)
            result = group(*args, **kwargs)(func)
            self.add_command(result)
            return result

        return decorator


class Group(GroupMixin, Command):
    """A class that implements a grouping protocol for commands to be
    executed as subcommands.

    This class is a subclass of :class:`.Command` and thus all options
    valid in :class:`.Command` are valid in here as well.

    Attributes
    -----------
    invoke_without_command: Optional[:class:`bool`]
        Indicates if the group callback should begin parsing and
        invocation only if no subcommand was found. Useful for
        making it an error handling function to tell the user that
        no subcommand was found or to have different functionality
        in case no subcommand was found. If this is ``False``, then
        the group callback will always be invoked first. This means
        that the checks and the parsing dictated by its parameters
        will be executed. Defaults to ``False``.
    case_insensitive: Optional[:class:`bool`]
        Indicates if the group's commands should be case insensitive.
        Defaults to ``None`` which means it inherits the parents or bots
        value.
    """

    def __init__(self, *args: list, **attrs: dict) -> None:
        self.invoke_without_command = attrs.pop(
            'invoke_without_command',
            False
        )
        super().__init__(*args, **attrs)

    async def invoke(self, ctx: Context) -> None:
        ctx.invoked_subcommand = None
        early_invoke = not self.invoke_without_command
        if early_invoke:
            await self.prepare(ctx)

        view = ctx.view
        previous = view.index
        view.skip_ws()
        trigger = view.get_word()

        if trigger:
            ctx.subcommand_passed = trigger
            ctx.invoked_subcommand = self.all_commands.get(trigger, None)

        if early_invoke:
            injected = hooked_wrapped_callback(self, ctx, self.callback)
            await injected(*ctx.args, **ctx.kwargs)

        if trigger and ctx.invoked_subcommand:
            ctx.invoked_with = trigger
            await ctx.invoked_subcommand.invoke(ctx)
        elif not early_invoke:
            # undo the trigger parsing
            view.index = previous
            view.previous = previous
            await super().invoke(ctx)

    async def reinvoke(self, ctx: Context, *,
                       call_hooks: bool = False) -> None:
        ctx.invoked_subcommand = None
        early_invoke = not self.invoke_without_command
        if early_invoke:
            ctx.command = self
            await self._parse_arguments(ctx)

            if call_hooks:
                await self.call_before_hooks(ctx)

        view = ctx.view
        previous = view.index
        view.skip_ws()
        trigger = view.get_word()

        if trigger:
            ctx.subcommand_passed = trigger
            ctx.invoked_subcommand = self.all_commands.get(trigger, None)

        if early_invoke:
            try:
                await self.callback(*ctx.args, **ctx.kwargs)
            except Exception:
                ctx.command_failed = True
                raise
            finally:
                if call_hooks:
                    await self.call_after_hooks(ctx)

        if trigger and ctx.invoked_subcommand:
            ctx.invoked_with = trigger
            await ctx.invoked_subcommand.reinvoke(ctx, call_hooks=call_hooks)

        elif not early_invoke:
            view.index = previous
            view.previous = previous
            await super().reinvoke(ctx, call_hooks=call_hooks)


def command(name: Optional[str] = None,
            cls: Optional[Command] = None,
            **attrs: dict) -> callable:
    """A decorator that transforms a function into a :class:`.Command`
    or if called with :func:`.group`, :class:`.Group`.

    By default the ``help`` attribute is received automatically from the
    docstring of the function and is cleaned up with the use of
    ``inspect.cleandoc``. If the docstring is ``bytes``, then it is decoded
    into :class:`str` using utf-8 encoding.

    All checks added using the :func:`.check` & co. decorators are added into
    the function. There is no way to supply your own checks through this
    decorator.

    Parameters
    -----------
    name: :class:`str`
        The name to create the command with. By default this uses the
        function name unchanged.
    cls
        The class to construct with. By default this is :class:`.Command`.
        You usually do not change this.
    attrs
        Keyword arguments to pass into the construction of the class denoted
        by ``cls``.

    Raises
    -------
    TypeError
        If the function is not a coroutine or is already a command.
    """

    if cls is None:
        cls = Command

    def decorator(func):
        if isinstance(func, Command):
            raise TypeError('Callback is already a command.')
        return cls(func, name=name, **attrs)

    return decorator


def group(name: Optional[str] = None, **attrs: dict) -> callable:
    """A decorator that transforms a function into a :class:`.Group`.

    This is similar to the :func:`.command` decorator but the ``cls``
    parameter is set to :class:`Group` by default.
    """
    attrs.setdefault('cls', Group)
    return command(name=name, **attrs)


def check(predicate: callable) -> MaybeCoro:
    r"""A decorator that adds a check to the :class:`.Command` or its
    subclasses. These checks could be accessed via :attr:`.Command.checks`.

    These checks should be predicates that take in a single parameter taking
    a :class:`.Context`. If the check returns a ``False``\-like value then
    during invocation a :exc:`.CheckFailure` exception is raised and sent to
    the :func:`.event_command_error` event.

    If an exception should be thrown in the predicate then it should be a
    subclass of :exc:`.CommandError`. Any exception not subclassed from it
    will be propagated while those subclassed will be sent to
    :func:`.event_command_error`.

    A special attribute named ``predicate`` is bound to the value
    returned by this decorator to retrieve the predicate passed to the
    decorator.

    .. note::

        The function returned by ``predicate`` is **always** a coroutine,
        even if the original function was not a coroutine.

    Examples
    ---------

    Creating a basic check to see if the command invoker is you.

    .. code-block:: python3

        def check_if_it_is_me(ctx):
            return ctx.author.id == "8b6373cbbe7d452b8172b5ee67ad53fa"

        @bot.command()
        @commands.check(check_if_it_is_me)
        async def only_for_me(ctx):
            await ctx.send('I know you!')

    Transforming common checks into its own decorator:

    .. code-block:: python3

        def is_me():
            def predicate(ctx):
                return ctx.author.id == "8b6373cbbe7d452b8172b5ee67ad53fa"
            return commands.check(predicate)

        @bot.command()
        @is_me()
        async def only_me(ctx):
            await ctx.send('Only you!')

    Parameters
    -----------
    predicate: Callable[[:class:`Context`], :class:`bool`]
        The predicate to check if the command should be invoked.
    """  # noqa

    def decorator(func):
        if isinstance(func, Command):
            func.checks.append(predicate)
        else:
            if not hasattr(func, '__fnpy_commands_checks__'):
                func.__fnpy_commands_checks__ = []

            func.__fnpy_commands_checks__.append(predicate)

        return func

    if asyncio.iscoroutinefunction(predicate):
        decorator.predicate = predicate
    else:
        @functools.wraps(predicate)
        async def wrapper(ctx):
            return predicate(ctx)

        decorator.predicate = wrapper

    return decorator


def check_any(*checks: list) -> callable:
    r"""A :func:`check` that is added that checks if any of the checks passed
    will pass, i.e. using logical OR.

    If all checks fail then :exc:`.CheckAnyFailure` is raised to signal the
    failure. It inherits from :exc:`.CheckFailure`.

    .. note::

        The ``predicate`` attribute for this function **is** a coroutine.

    Parameters
    ------------
    \*checks: Callable[[:class:`Context`], :class:`bool`]
        An argument list of checks that have been decorated with
        the :func:`check` decorator.

    Raises
    -------
    TypeError
        A check passed has not been decorated with the :func:`check`
        decorator.

    Examples
    ---------

    Creating a basic check to see if it's the bot owner or
    the party leader:

    .. code-block:: python3

        def is_party_leader():
            def predicate(ctx):
                return ctx.party is not None and ctx.author.leader
            return commands.check(predicate)

        @bot.command()
        @commands.check_any(commands.is_owner(), is_party_leader())
        async def only_for_owners(ctx):
            await ctx.send('Hello mister owner!')
    """

    unwrapped = []
    for wrapped in checks:
        try:
            pred = wrapped.predicate
        except AttributeError:
            raise TypeError(
                '{0} must be wrapped by commands.check '
                'decorator'.format(wrapped)
            ) from None
        else:
            unwrapped.append(pred)

    async def predicate(ctx):
        errors = []
        for func in unwrapped:
            try:
                value = await func(ctx)
            except errors.CheckFailure as e:
                errors.append(e)
            else:
                if value:
                    return True

        raise errors.CheckAnyFailure(unwrapped, errors)

    return check(predicate)


def cooldown(rate: int,
             per: float,
             type: BucketType = BucketType.default) -> callable:
    """A decorator that adds a cooldown to a :class:`.Command`
    or its subclasses.

    A cooldown allows a command to only be used a specific amount
    of times in a specific time frame. These cooldowns can be based
    either on a per-user or global basis.
    Denoted by the third argument of ``type`` which must be of enum
    type :class:`.BucketType`.

    If a cooldown is triggered, then :exc:`.CommandOnCooldown` is triggered in
    :func:`.event_command_error` and the local error handler.

    A command can only have a single cooldown.

    Parameters
    ------------
    rate: :class:`int`
        The number of times a command can be used before triggering a cooldown.
    per: :class:`float`
        The amount of seconds to wait for a cooldown when it's been triggered.
    type: :class:`.BucketType`
        The type of cooldown to have.
    """

    def decorator(func):
        if isinstance(func, Command):
            func._buckets = CooldownMapping(Cooldown(rate, per, type))
        else:
            func.__fnpy_commands_cooldown__ = Cooldown(rate, per, type)
        return func
    return decorator


def max_concurrency(number: int, per: BucketType = BucketType.default, *,
                    wait: bool = False) -> callable:
    """A decorator that adds a maximum concurrency to a :class:`.Command` or
    its subclasses.

    This enables you to only allow a certain number of command invocations at
    the same time, for example if a command takes too long or if only one user
    can use it at a time. This differs from a cooldown in that there is no set
    waiting period or token bucket -- only a set number of people can run the
    command.

    Parameters
    ----------
    number: :class:`int`
        The maximum number of invocations of this command that can be running
        at the same time.
    per: :class:`.BucketType`
        The bucket that this concurrency is based on, e.g. ``BucketType.user``
        would allow it to be used up to ``number`` times per user.
    wait: :class:`bool`
        Whether the command should wait for the queue to be over. If this is
        set to ``False`` then instead of waiting until the command can run
        again, the command raises :exc:`.MaxConcurrencyReached` to its error
        handler. If this is set to ``True`` then the command waits until it
        can be executed.
    """

    def decorator(func):
        value = MaxConcurrency(number, per=per, wait=wait)
        if isinstance(func, Command):
            func._max_concurrency = value
        else:
            func.__fnpy_commands_max_concurrency__ = value
        return func
    return decorator


def before_invoke(coro: Awaitable) -> callable:
    """A decorator that registers a coroutine as a pre-invoke hook.

    This allows you to refer to one before invoke hook for several commands
    that do not have to be within the same cog.

    Example
    ---------

    .. code-block:: python3

        async def record_usage(ctx):
            print(ctx.author, 'used', ctx.command, 'at', ctx.message.created_at)

        @bot.command()
        @commands.before_invoke(record_usage)
        async def who(ctx): # Output: <User> used who at <Time>
            await ctx.send('i am a bot')

        class What(commands.Cog):

            @commands.before_invoke(record_usage)
            @commands.command()
            async def who(self, ctx): # Output: <User> used when at <Time>
                await ctx.send('and my name is {}'.format(ctx.bot.user.display_name))

            @commands.command()
            async def where(self, ctx): # Output: <Nothing>
                await ctx.send('on Fortnite')

            @commands.command()
            async def why(self, ctx): # Output: <Nothing>
                await ctx.send('because someone made me')

        bot.add_cog(What())
    """  # noqa

    def decorator(func):
        if isinstance(func, Command):
            func.before_invoke(coro)
        else:
            func.__fnpy_before_invoke__ = coro
        return func
    return decorator


def after_invoke(coro: Awaitable) -> callable:
    """A decorator that registers a coroutine as a post-invoke hook.

    This allows you to refer to one after invoke hook for several commands that
    do not have to be within the same cog.
    """

    def decorator(func):
        if isinstance(func, Command):
            func.after_invoke(coro)
        else:
            func.__fnpy_after_invoke__ = coro
        return func
    return decorator


def dm_only() -> callable:
    """A :func:`.check` that indicates this command must only be used in a
    DM context. Only private messages are allowed when
    using the command.

    This check raises a special exception, :exc:`.PrivateMessageOnly`
    that is inherited from :exc:`.CheckFailure`.
    """

    def predicate(ctx):
        if ctx.party is not None:
            raise errors.PrivateMessageOnly()
        return True

    return check(predicate)


def party_only() -> callable:
    """A :func:`.check` that indicates this command must only be used in a
    party context only. Basically, no private messages are allowed when
    using the command.

    This check raises a special exception, :exc:`.PartyMessageOnly`
    that is inherited from :exc:`.CheckFailure`.
    """

    def predicate(ctx):
        if ctx.party is None:
            raise errors.PartyMessageOnly()
        return True

    return check(predicate)


def is_owner() -> callable:
    """A :func:`.check` that checks if the person invoking this command is the
    owner of the bot.

    This is powered by :meth:`.Bot.is_owner`.

    This check raises a special exception, :exc:`.NotOwner` that is derived
    from :exc:`.CheckFailure`.
    """

    async def predicate(ctx):
        if not await ctx.bot.is_owner(ctx.author.id):
            raise errors.NotOwner('You do not own this bot.')
        return True

    return check(predicate)
