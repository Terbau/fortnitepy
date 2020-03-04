# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2019-2020 Terbau

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


class FortniteException(Exception):
    """Base exception for fortnitepy.

    This could in theory be caught to handle all exceptions thrown by this
    library.
    """
    pass


class PurchaseException(FortniteException):
    """This exception is raised if the game could not be purchased on
    launch.
    """


class AuthException(FortniteException):
    """This exception is raised when auth fails by invalid credentials
    passed or some other misc failure."""
    pass


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

    def __init__(self, data: dict):
        self.field_name = data['fieldName']
        self.invalid_value = data['invalidValue']
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
    raw: Union[:class:`str`, :class:`dict`]
        The raw message/data received from Fortnite services.
    message: :class:`str`
        The raw error message received from Fortnite services.
    message_code: :class:`str`
        The raw error message code received from Fortnite services.
    message_vars: List[:class:`str`]
        List containing arguments passed to the message.
    code: :class:`int`
        The error code received from Fortnite services.
    originating_service: :class:`str`
        The originating service this error was received from.
    intent: :class:`str`
        The prod this error was received from.
    validation_failures: List[:exc:`ValidationFailure`]
        A list containing information about the validation failures.
        ``None`` if the error was not raised a validation issue.
    """

    def __init__(self, response: ClientResponse, message: dict) -> None:
        self.response = response
        self.status = response.status
        self.raw = message

        _err = message if isinstance(message, dict) else {}
        self.message = _err.get('errorMessage')
        self.message_code = _err.get('errorCode')
        self.message_vars = _err.get('messageVars')
        self.code = _err.get('numericErrorCode')
        self.originating_service = _err.get('originatingService')
        self.intent = _err.get('intent')

        validation_failures_data = _err.get('validationFailures')
        if validation_failures_data is not None:
            self.validation_failures = [ValidationFailure(d) for d
                                        in validation_failures_data.values()]
        else:
            self.validation_failures = None

        self.text = 'Code: "{0}" - {1}'.format(
            self.message_code,
            self.message
        )

        super().__init__(self.text)
