# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2019-2021 Terbau

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from aiohttp import ClientResponse
from typing import Union


class FortniteException(Exception):
    """Base exception for fortnitepy.

    This could in theory be caught to handle all exceptions thrown by this
    library.
    """
    pass


class AuthException(FortniteException):
    """This exception is raised when auth fails by invalid credentials
    passed or some other misc failure.

    Attributes
    ----------
    original: :exc:`FortniteException`
        The original exception raised. The original error always inherits from
        :exc:`FortniteException`.
    """
    def __init__(self, message: str, original: Exception) -> None:
        super().__init__(message)
        self.original = original


class EventError(FortniteException):
    """This exception is raised when something regarding events fails."""
    pass


class XMPPError(FortniteException):
    """This exception is raised when something regarding the XMPP service
    fails.
    """
    pass


class PartyError(FortniteException):
    """This exception is raised when something regarding parties fails."""
    pass


class PartyIsFull(FortniteException):
    """This exception is raised when the bot attempts to join a full party."""


class Forbidden(FortniteException):
    """This exception is raised whenever you attempted a request that your
    account does not have permission to do.
    """
    pass


class NotFound(FortniteException):
    """This exception is raised when something was not found by fortnites
    services.
    """
    pass


class NoMoreItems(FortniteException):
    """This exception is raised whenever an iterator does not have any more
    items.
    """
    pass


class DuplicateFriendship(FortniteException):
    """This exception is raised whenever the client attempts to add a user as
    friend when the friendship already exists."""
    pass


class FriendshipRequestAlreadySent(FortniteException):
    """This exception is raised whenever the client attempts to send a friend
    request to a user that has already received a friend request from the
    client.
    """
    pass


class MaxFriendshipsExceeded(FortniteException):
    """This excepttion is raised if the client has hit the limit for
    friendships.
    """
    pass


class InviteeMaxFriendshipsExceeded(FortniteException):
    """This exception is raised if the user you attempted to add has
    hit the limit for friendships.
    """
    pass


class InviteeMaxFriendshipRequestsExceeded(FortniteException):
    """This exception is raised if the user you attempted to add has
    hit the limit for the amount of friendship requests a user can have
    at a time.
    """
    pass


class InvalidOffer(FortniteException):
    """This exception is raised when an invalid/outdated offer is
    passed. Only offers currently in the item shop are valid."""
    pass


class ValidationFailure(FortniteException):
    """Represents a validation failure returned.

    Attributes
    ----------
    field_name: :class:`str`
        Name of the field that was invalid.
    invalid_value: :class:`str`
        The invalid value.
    message: :class:`str`
        The message explaining why the field value was invalid.
    message_code: :class:`str`
        The raw error message code received.
    message_vars: Dict[:class:`str`, :class:`str`]
        The message variables received.
    """

    def __init__(self, data: dict) -> None:
        self.field_name = data['fieldName']
        self.invalid_value = data.get('invalidValue')
        self.message = data['errorMessage']
        self.message_code = data['errorCode']
        self.message_vars = data['messageVars']


class HTTPException(FortniteException):
    """This exception is raised when an error is received by Fortnite services.

    Attributes
    ----------
    response: :class:`aiohttp.ClientResponse`
        The response from the HTTP request.
    text: :class:`str`
        The error message.
    status: :class:`int`
        The status code of the HTTP request.
    route: Union[:class:`Route`, :class:`str`]
        The route or url used for this request.
    raw: Union[:class:`str`, :class:`dict`]
        The raw message/data received from Fortnite services.
    request_headers: :class:`dict`
        The headers used for the request.
    message: :class:`str`
        The raw error message received from Fortnite services.
    message_code: Optional[:class:`str`]
        The raw error message code received from Fortnite services.
    message_vars: List[:class:`str`]
        List containing arguments passed to the message.
    code: Optional[:class:`int`]
        The error code received from Fortnite services.
    originating_service: Optional[:class:`str`]
        The originating service this error was received from.
    intent: Optional[:class:`str`]
        The prod this error was received from.
    validation_failures: Optional[List[:exc:`ValidationFailure`]]
        A list containing information about the validation failures.
        ``None`` if the error was not raised a validation issue.
    """

    def __init__(self, response: ClientResponse,
                 route: Union['Route', str],
                 message: dict,
                 request_headers: dict) -> None:
        self.response = response
        self.status = response.status
        self.route = route
        self.raw = message
        self.request_headers = request_headers

        _err = message if isinstance(message, dict) else {}
        self.message = _err.get('errorMessage')
        self.message_code = _err.get('errorCode')
        self.message_vars = _err.get('messageVars', [])
        self.code = _err.get('numericErrorCode')
        self.originating_service = _err.get('originatingService')
        self.intent = _err.get('intent')

        validation_failures_data = _err.get('validationFailures')
        if validation_failures_data is not None:
            self.validation_failures = [
                ValidationFailure(d) for d in validation_failures_data.values()
            ]
        else:
            self.validation_failures = None

        if self.message_code is not None:
            fmt = self.message
        else:
            fmt = '{0} - {1}'.format(self.status, self.message)

        self.text = 'Code: "{0}" - {1}'.format(
            self.message_code,
            fmt
        )

        super().__init__(self.text)
