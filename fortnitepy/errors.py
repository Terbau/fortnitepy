# -*- coding: utf-8 -*-

"""
MIT License

Copyright (c) 2019 Terbau

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

class FortniteException(Exception):
    """Base exception for fortnitepy.
    
    This could in theory be caught to handle all exceptions thrown by this library.
    """
    pass

class AuthException(FortniteException):
    """This exception is raised when auth fails."""
    pass

class EventError(FortniteException):
    """This exception is raised when something regarding events fails."""
    pass

class XMPPError(FortniteException):
    """This exception is raised when something regarding the XMPP service fails."""
    pass

class PartyError(FortniteException):
    """This exception is raised when something regarding parties fails."""
    pass

class PartyPermissionError(FortniteException):
    """This exception is raised when you dont have permission to do something in a party
    or a party you are trying to join is private.
    """
    pass

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
    """
    
    def __init__(self, response, message):
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

        self.text = 'Code: "{0}" - {1}'.format(
            self.message_code,
            self.message
        )

        super().__init__(self.text)
