import re

from typing import Any, Optional
from fortnitepy.user import User
from fortnitepy.party import PartyMember
from fortnitepy.friend import Friend

from .errors import BadArgument
from .context import Context


__all__ = (
    'Converter',
    'IDConverter',
    'UserConverter',
    'PartyMemberConverter',
    'FriendConverter',
    'IDConverter',
    'Greedy',
)


class Converter:
    """The base class of custom converters that require the :class:`.Context`
    to be passed to be useful.

    This allows you to implement converters that function similar to the
    special cased ``fortnitepy`` classes.

    Classes that derive from this should override the
    :meth:`~.Converter.convert` method to do its conversion logic. This method
    must be a coroutine.
    """

    async def convert(self, ctx: 'Context', argument: str) -> Any:
        """|coro|

        The method to override to do conversion logic.

        If an error is found while converting, it is recommended to
        raise a :exc:`.CommandError` derived exception as it will
        properly propagate to the error handlers.

        Parameters
        -----------
        ctx: :class:`.Context`
            The invocation context that the argument is being used in.
        argument: :class:`str`
            The argument that is being converted.
        """
        raise NotImplementedError('Derived classes need to implement this.')


class IDConverter(Converter):
    def __init__(self) -> None:
        self._id_regex = re.compile(r'([0-9a-fA-F]{32})$')

    def _get_id_match(self, argument: str) -> Any:
        return self._id_regex.match(argument)


class UserConverter(IDConverter):
    """Converts to a :class:`~fortnitepy.User`.

    The lookup strategy is as follows (in order):
    1. Cache lookup by ID.
    2. Cache lookup by display name.
    3. API Request to fetch the user by id/display name.
    """

    async def convert(self, ctx: Context, argument: str) -> User:
        bot = ctx.bot
        match = self._get_id_match(argument)

        if match is not None:
            to_lookup = match.group(1).lower()
        else:
            to_lookup = argument

        result = await bot.fetch_profile(to_lookup, cache=True)

        if result is None:
            raise BadArgument('User "{}" not found'.format(argument))

        return result


class PartyMemberConverter(IDConverter):
    """Converts to a :class:`~fortnitepy.PartyMember`.

    All lookups are done via the bots party member cache.

    The lookup strategy is as follows (in order):
    1. Lookup by ID.
    2. Lookup by display name.
    """

    async def convert(self, ctx: Context, argument: str) -> PartyMember:
        bot = ctx.bot
        match = self._get_id_match(argument)
        party = ctx.party or bot.party

        result = None
        if match is None:
            for member in party.members.values():
                if member.display_name.casefold() == argument.casefold():
                    result = member
                    break
        else:
            user_id = match.group(1).lower()
            result = party.get_member(user_id)

        if result is None:
            raise BadArgument('Party member "{}" not found'.format(argument))

        return result


class FriendConverter(IDConverter):
    """Converts to a :class:`~fortnitepy.Friend`.

    All lookups are via the friend cache.

    The lookup strategy is as follows (in order):
    1. Lookup by ID.
    2. Lookup by display name.
    """

    async def convert(self, ctx: Context, argument: str) -> Friend:
        bot = ctx.bot
        match = self._get_id_match(argument)

        result = None
        if match is not None:
            user_id = match.group(1).lower()
            result = bot.get_friend(user_id)
        else:
            for friend in bot.friends.values():
                if friend.display_name.casefold() == argument.casefold():
                    result = friend
                    break

        if result is None:
            raise BadArgument('Friend "{}" not found'.format(argument))

        return result


class _Greedy:
    __slots__ = ('converter',)

    def __init__(self, *, converter: Optional[Converter] = None) -> None:
        self.converter = converter

    def __getitem__(self, params):
        if not isinstance(params, tuple):
            params = (params,)
        if len(params) != 1:
            raise TypeError('Greedy[...] only takes a single argument')

        converter = params[0]

        if not (callable(converter) or isinstance(converter, Converter)
                or hasattr(converter, '__origin__')):
            raise TypeError('Greedy[...] expects a type or a Converter '
                            'instance.')

        NoneType = type(None)
        if converter is str or converter is NoneType or converter is _Greedy:
            raise TypeError('Greedy[%s] is invalid.' % converter.__name__)

        return self.__class__(converter=converter)


Greedy = _Greedy()
