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
    """This exception is raised when an error is received by Fortnite services."""
    pass
