from datetime import datetime
from typing import Union, Awaitable, Callable


MaybeCoro = Union[Awaitable, Callable]
StrOrMaybeCoro = Union[str, MaybeCoro]
ListOrTuple = Union[list, tuple]
StrOrInt = Union[str, int]
DatetimeOrTimestamp = Union[datetime, int]
