import time
import asyncio

from enum import Enum
from collections import deque
from typing import Any, Optional

from .typedefs import Message
from .errors import MaxConcurrencyReached

__all__ = (
    'BucketType',
    'Cooldown',
    'CooldownMapping',
    'MaxConcurrency',
)


class BucketType(Enum):
    default = 0
    user = 1

    def get_key(self, msg: Message) -> Any:
        if self is BucketType.user:
            return msg.author.id


class Cooldown:
    __slots__ = ('rate', 'per', 'type', '_window', '_tokens', '_last')

    def __init__(self, rate: int, per: float, type: BucketType) -> None:
        self.rate = int(rate)
        self.per = float(per)
        self.type = type
        self._window = 0.0
        self._tokens = self.rate
        self._last = 0.0

        if not isinstance(self.type, BucketType):
            raise TypeError('Cooldown type must be a BucketType')

    def get_tokens(self, current: Optional[float] = None) -> int:
        if not current:
            current = time.time()

        tokens = self._tokens

        if current > self._window + self.per:
            tokens = self.rate
        return tokens

    def update_rate_limit(self,
                          current: Optional[float] = None) -> Optional[float]:
        current = current or time.time()
        self._last = current

        self._tokens = self.get_tokens(current)

        # first token used means that we start a new rate limit window
        if self._tokens == self.rate:
            self._window = current

        # check if we are rate limited
        if self._tokens == 0:
            return self.per - (current - self._window)

        # we're not so decrement our tokens
        self._tokens -= 1

        # see if we got rate limited due to this token change, and if
        # so update the window to point to our current time frame
        if self._tokens == 0:
            self._window = current

    def reset(self) -> None:
        self._tokens = self.rate
        self._last = 0.0

    def copy(self) -> 'Cooldown':
        return Cooldown(self.rate, self.per, self.type)

    def __repr__(self) -> str:
        return ('<Cooldown rate: {0.rate} per: {0.per} window: {0._window} '
                'tokens: {0._tokens}>'.format(self))


class CooldownMapping:
    def __init__(self, original: Cooldown) -> None:
        self._cache = {}
        self._cooldown = original

    def copy(self) -> 'CooldownMapping':
        ret = CooldownMapping(self._cooldown)
        ret._cache = self._cache.copy()
        return ret

    @property
    def valid(self) -> bool:
        return self._cooldown is not None

    @classmethod
    def from_cooldown(cls, rate: int,
                      per: float,
                      type: BucketType) -> 'CooldownMapping':
        return cls(Cooldown(rate, per, type))

    def _bucket_key(self, msg: Message) -> Any:
        return self._cooldown.type.get_key(msg)

    def _verify_cache_integrity(self, current: Optional[float] = None) -> None:
        # we want to delete all cache objects that haven't been used
        # in a cooldown window. e.g. if we have a  command that has a
        # cooldown of 60s and it has not been used in 60s then that key should
        # be deleted
        current = current or time.time()
        dead_keys = [k for k, v in self._cache.items()
                     if current > v._last + v.per]
        for k in dead_keys:
            del self._cache[k]

    def get_bucket(self, message: Message,
                   current: Optional[float] = None) -> Cooldown:
        if self._cooldown.type is BucketType.default:
            return self._cooldown

        self._verify_cache_integrity(current)
        key = self._bucket_key(message)
        if key not in self._cache:
            bucket = self._cooldown.copy()
            self._cache[key] = bucket
        else:
            bucket = self._cache[key]

        return bucket

    def update_rate_limit(self, message: Message,
                          current: Optional[float] = None) -> Optional[float]:
        bucket = self.get_bucket(message, current)
        return bucket.update_rate_limit(current)


class _Semaphore:
    __slots__ = ('value', 'loop', '_waiters')

    def __init__(self, number: int) -> None:
        self.value = number
        self.loop = asyncio.get_event_loop()
        self._waiters = deque()

    def __repr__(self) -> str:
        return ('<_Semaphore value={0.value} waiters={1}>'
                ''.format(self, len(self._waiters)))

    def locked(self) -> bool:
        return self.value == 0

    def is_active(self) -> bool:
        return len(self._waiters) > 0

    def wake_up(self) -> None:
        while self._waiters:
            future = self._waiters.popleft()
            if not future.done():
                future.set_result(None)
                return

    async def acquire(self, *, wait: bool = False) -> bool:
        if not wait and self.value <= 0:
            # signal that we're not acquiring
            return False

        while self.value <= 0:
            future = self.loop.create_future()
            self._waiters.append(future)
            try:
                await future
            except Exception:
                future.cancel()
                if self.value > 0 and not future.cancelled():
                    self.wake_up()
                raise

        self.value -= 1
        return True

    def release(self) -> None:
        self.value += 1
        self.wake_up()


class MaxConcurrency:
    __slots__ = ('number', 'per', 'wait', '_mapping')

    def __init__(self, number: int, *, per: BucketType, wait: bool) -> None:
        self._mapping = {}
        self.per = per
        self.number = number
        self.wait = wait

        if number <= 0:
            raise ValueError('max_concurrency \'number\' cannot be less '
                             'than 1')

        if not isinstance(per, BucketType):
            raise TypeError('max_concurrency \'per\' must be of type '
                            'BucketType not %r' % type(per))

    def copy(self) -> 'MaxConcurrency':
        return self.__class__(self.number, per=self.per, wait=self.wait)

    def __repr__(self) -> str:
        return ('<MaxConcurrency per={0.per!r} number={0.number} '
                'wait={0.wait}>'.format(self))

    def get_key(self, message: Message) -> Any:
        return self.per.get_key(message)

    async def acquire(self, message: Message) -> None:
        key = self.get_key(message)

        try:
            sem = self._mapping[key]
        except KeyError:
            self._mapping[key] = sem = _Semaphore(self.number)

        acquired = await sem.acquire(wait=self.wait)
        if not acquired:
            raise MaxConcurrencyReached(self.number, self.per)

    async def release(self, message: Message) -> None:
        # Technically there's no reason for this function to be async
        # But it might be more useful in the future
        key = self.get_key(message)

        try:
            sem = self._mapping[key]
        except KeyError:
            # ...? peculiar
            return
        else:
            sem.release()

        if sem.value >= self.number and not sem.is_active():
            del self._mapping[key]
