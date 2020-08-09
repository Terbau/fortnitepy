.. currentmodule:: fortnitepy

Changelog
=========

Detailed version changes.


v3.0.0
------

This major update focuses on stability but also introduces lots of additions and changes.

Changed
~~~~~~~

- (**Breaking**) Renamed ``ProfileSearchPlatform`` -> :class:`UserSearchPlatform`.
- (**Breaking**) Renamed ``ProfileSearchEntryUser`` -> :class:`UserSearchEntry`.
- (**Breaking**) The access attribute for caches now return a copied list of the caches values. This affects these attributes:
    - :attr:`Client.friends`
    - :attr:`Client.pending_friends`
    - :attr:`Client.blocked_users`
    - :attr:`Client.presences`
    - :attr:`Party.members`
- (**Breaking**) Renamed ``Client.join_to_party()`` -> :meth:`Client.join_party()`.
- (**Breaking**) Renamed ``Client.set_status()`` -> :meth:`Client.set_presence()`.
- (**Breaking**) Renamed ``Client.send_status()`` -> :meth:`Client.send_presence()`.
- (**Breaking**) Renamed ``event_party_member_disconnect()`` -> :func:`event_party_member_zombie()`.
- Renamed multiple fetch methods. All of the renamed methods are still aliased to their previous names so this should break anything.
    - ``Client.fetch_profile_by_display_name()`` -> :meth:`Client.fetch_user_by_display_name()`.
    - ``Client.fetch_profiles_by_display_name()`` -> :meth:`Client.fetch_users_by_display_name()`.
    - ``Client.fetch_profile()`` -> :meth:`Client.fetch_user()`.
    - ``Client.fetch_profiles()`` -> :meth:`Client.fetch_users()`.
    - ``Client.fetch_profile_by_email()`` -> :meth:`Client.fetch_user_by_email()`.
    - ``Client.search_profiles()`` -> :meth:`Client.search_users()`.
- Removed usage of the loop parameter internally since asyncio is deprecating it soon.
- The client now logs out and returns the start call (:meth:`Client.start()` or :meth:`Client.run()`) when too many reauth attempts has been tried. This happens even if the client has previously successfully logged in and emitted :func:`event_ready()`.

Added
~~~~~

- Added parameter ``error_callback`` to :func:`start_multiple()` and :func:`run_multiple()`.
- Added parameter ``away`` to :class:`Client` to set the clients presence :class:`AwayStatus`.
- Added proper ratelimit and retry handling for http requests.
- Added parameter ``http_retry_config`` to :class:`Client` which controls how http ratelimits and retries are handled. Check out its new dataclass :class:`HTTPRetryConfig` to see the options you can set.
- Added :attr:`Client.incoming_pending_friends` to get a list of the clients incoming pending friends.
- Added :attr:`Client.outgoing_pending_friends` to get a list of the clients outgoing pending friends.
- Added :meth:`Client.get_incoming_pending_friend()` to get an incoming pending friend by their id.
- Added :meth:`Client.get_outgoing_pending_friend()` to get an outgoing pending friend by their id.
- Added :meth:`Client.wait_until_closed()`.
- Added :meth:`Client.fetch_party()` to fetch a party by its id.
- Added parameter ``away`` to :meth:`Client.set_presence()` and :meth:`Client.send_presence()`.
- Added :attr:`HTTPException.request_headers` to access the headers of the request that failed.
- Added alias ``inbound`` for attribute ``incoming`` to :class:`IncomingPendingFriend` and :class:`OutgoingPendingFriend`.
- Added alias ``outbound`` for attribute ``outgoing`` to :class:`IncomingPendingFriend` and :class:`OutgoingPendingFriend`.
- Added parameter ``offline_ttl`` to :class:`DefaultPartyMemberConfig`.
- Added :attr:`PartyMember.offline_ttl` to check a members time to live seconds before leaving the party when its connection is lost.
- Added :meth:`PartyMember.is_zombie()` to check if the members connection is currently lost and therefore not responding.
- Added :attr:`PartyMember.zombie_since` to check when a member lost its connection.
- Added :meth:`Party.join()`.
- Added :meth:`ClientParty.set_max_size()` to set the max size of the party while in it.
- Added :func:`event_invalid_party_invite()`.
- Added :func:`event_party_member_reconnect()`.
- Added :func:`event_xmpp_session_establish()`.
- Added :func:`event_xmpp_session_lost()`.
- Added :func:`event_xmpp_session_close()`.
- Added compare magic methods (``__eq__`` and ``__ne__``) to:
    - :class:`Avatar`
    - :class:`Party`
    - :class:`ClientParty`
    - :class:`ReceivedPartyInvitation`
    - :class:`SentPartyInvitation`
    - :class:`PartyJoinConfirmation`
    - :class:`Playlist`
    - :class:`ExternalAuth`
    - :class:`User`
    - :class:`BlockedUser`
    - :class:`UserSearchEntry`
    - :class:`SacSearchEntryUser`
    - :class:`User`
    - :class:`Friend`
    - :class:`IncomingPendingFriend`
    - :class:`OutgoingPendingFriend`
    - :class:`PartyMember`

Removed
~~~~~~~

- Removed parameter ``check_private`` from :meth:`Client.join_party()`.

Bug Fixes
~~~~~~~~~

- Reworked the invalid access token reauth strategy to fix multiple issues that caused stuff to break down completely.
- Fixed an issue regarding joining a bots party when the bot was party leader but not the original creator.
- Fixed party config patching.
- Fixed an issue where bots were not able to join any new lobbies in some rare circumstances.
- Fixed an issue that caused other users to not be able to rejoin or lookup the bots private party even when the user had already been a part of the party before.
- Fixed an issue where :exc:`HTTPException` would sometimes fail at initializing because of a missing required value.
- Fixed multiple issues regarding graphql error responses that was not correctly catched to raise an :exc:`HTTPException` and would raise an ugly error.
- HTTP retries are now attempted for even more errors.
- Fixed an issue where :attr:`PartyMember.connection` wasn't always updated to use the latest connection.
- Improved the clients knowledge of which member is actually the party leader.
- Fixed and improved lots of stuff regarding sudden connection loss including recovering and dispatching events, automatic party reconnect if the criterias is met and more.
- Fixed an issue where a member was removed from the party internally if their connection was lost but not expired.
- Lowered the deadtime hard limit values for the xmpp connection before reconnecting.
- Fixed a window where :attr:`ClientParty.me` could be ``None``.


v2.3.1
------

Stability improvements.

Changed
~~~~~~~

- Dropped the underlying launcher session since it's not longer used for anything.
- Authentication now attempts to reauthenticate on startup in some cases.
- Reauthentication on sudden access token invalid has been improved.

Bug Fixes
~~~~~~~~~

- Fixed some issues with incorrect handling of websocket disconnects that resulted in the xmpp connection to eventually time out.
- A graceful close is now attempted even if the client is not ready.
- Processing of messages now handles some race conditions that some times resulted in :attr:`FriendMessage.author` being ``None``.


v2.3.0
------

Huge performance improvements and lots of bug fixes.

Changed
~~~~~~~

- Internal parsing of xmpp stanzas like presences and messages are now processed by a custom processor which bypasses aioxmpp's slow processing whenever possible. This is more noticable on accounts with lots of online friends. Internal tests are showing performance speeds to be more than three times faster than before.

Added
~~~~~

- Added missing docs for ``connector`` keyword argument in :class:`Client.`
- Added keyword argument ``ws_connector`` to :class:`Client`.
- Added ``__slots__`` to :class:`Avatar`.

Removed
~~~~~~~

- Removed two undocumented attributes related to presences to reduce memory footprint:
    - ``Presence.raw_properties``
    - ``PresenceParty.raw``

Bug Fixes
~~~~~~~~~

- Fixed lots of issues regarding the xmpp over websocket solution. The most noticable one is that xmpp will auto reconnect on errors and unexpected closings.
- Fixed invalid refresh token sometimes crashing the bot while refreshing the session. NOTE: This only works when using :class:`DeviceAuth` or :class:`AdvancedAuth`.
- Fixed an issue where stored meta changes from :attr:`DefaultPartyConfig.meta` wasn't always applied correctly when creating a new party.
- Fixed an issue where some meta props wasn't always updated when using :meth:`ClientParty.edit()` or :meth:`ClientPartyMember.edit()`.
- :class:`aiohttp.BaseConnector`'s passed to :class:`Client` will no longer be closed when the client is closed.
- Fixed :attr:`PartyMember.external_auths` always being empty when the member was a part of :class:`ClientParty`.
- Fixed an issue that caused the client to sometimes leave the party some seconds after joining due to an event not being fired.
- The client will no longer send out its presence two times on startup. Sowwy epic :(


v2.2.1
------

Fixes an issue that caused some accounts with lots of friends to crash on startup.


v2.2.0
------

Changed
~~~~~~~

- (**Breaking**) Split `PendingFriend` into two separate objects :class:`IncomingPendingFriend` and :class:`OutgoingPendingFriend` depending on the direction of the request. Keep in mind that :attr:`Client.pending_friends` can include instances of both classes.
- (**Breaking**) :func:`event_friend_presence()` now takes two arguments ``before`` and ``after``.
- (**Breaking**) ``PendingFriendBase.inbound`` has been renamed to ``PendingFriendBase.incoming``.
- Made some small visual improvements to the documentation.

Added
~~~~~

- Added :attr:`SeasonEndTimestamp.SEASON_12` and :attr:`SeasonStartTimestamp.SEASON_13`.
- You can now cancel outgoing friend requests with :meth:`OutgoingPendingFriend.cancel()`.
- Added :attr:`Store.special_featured_items`.
- Added :attr:`Store.special_daily_items`.
- Added missing documentation to various attributes, methods and functions. The most relevant is the addition of ``meta`` keyword-arg to :class:`DefaultPartyConfig` which was already implemented but not documented.
- Added missing type hinting to various methods.

Removed
~~~~~~~

- Removed API KEY usage from the Fortnite-API example. Thanks (cup#9125).
- Removed some piece of code which auto claimed the fortnite entitlement. This has not been actively used for some updates.
- ``beautifulsoup4`` and ``websockets`` have been removed from requirements because they're no longer used.

Bug Fixes
~~~~~~~~~

- Fixed various bugs regarding the xmpp over websocket solution introduced in the last minor update. The library now uses aiohttp for websockets instead of the websockets library.
- Fixed a rare issue regarding last_online that sometimes crashed the client on startup.
- Fixed an issue that caused voice chat to not work for regular users in the clients party.
- Fixed a rare error that was sometimes raised in :meth:`PartyJoinConfirmation.confirm()` and :meth:`PartyJoinConfirmation.reject()`
- Silenced an error in processing of :func:`event_party_invite()`.




v2.1.1
------

Fixes an issue where :attr:`Friend.last_logout` would sometimes be a string after v2.1.0.


v2.1.0
------

This update fixes the new xmpp authentication issue + some other bugs.

Bug Fixes
~~~~~~~~~

- Fixed xmpp authentication by running xmpp over a custom xmpp over websocket connector.
- You can now use ``ProactorEventLoop`` with fortnitepy.
- Fixed an issue where a bot would not be able to start in some scenarios because of a friend missing the ``last_online`` property.
- Fixed an issue where a party was not created after refreshing the session. This was the cause of ``error code -93`` after refreshes.
- Fixed an issue that caused :meth:`Client.restart()` to not work.
- Silenced an error in processing of :func:`party_team_member_swap`.


v2.0.7
------

Fixes bugs introduced in fortnite v13.00 + fixes other bugs and adds some other changes.

Changes
~~~~~~~

- :meth:`Client.add_friend()` and other methods to add/accept friends now raises more specific exceptions.
- A RuntimeError with more info is now raised if a running ProactorEventLoop is found when importing fortnitepy.

Added
~~~~~

- :exc:`DuplicateFriendship`
- :exc:`FriendshipRequestAlreadySent`

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused no party meta related stuff to work after fortnite v13.00 (Invisible players fix).
- Fixed an issue where presence initialization failed because of a missing property.
- Removed ``party`` from :class:`ClientUser`.
- Fixed an issue where the xmpp stream would timeout in some cases. (Fixes `issue #67 <https://github.com/Terbau/fortnitepy/issues/67>`_)
- :class:`SentPartyInvitation` has now been added to the docs.
- :func:`event_command_error()`, :func:`event_command()` and :func:`event_command_completion()` are now properly named in the documentation.


v2.0.6
------

Various bug fixes

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused :class:`EmailAndPasswordAuth` to not work in some cases.
- Fixed errors not being raised correctly in newer versions when using :func:`start_multiple()` or :func:`run_multiple()`.
- Unnecessary errors are not longer raised when closing the client before it has started.
- Fixed an issue that caused :func:`event_party_member_in_match_change()` to not work.

Other
~~~~~

- Added documentation to :meth:`ClientPartyMember.set_in_match()` and :meth:`ClientPartyMember.clear_in_match()`.
- Edited docstrings in all examples to be up to date with recent changes.


v2.0.5
------

Changes
~~~~~~~

- Added :class:`AuthorizationCodeAuth` as an auth method.
- Added optional parameter ``authorization_code`` to :class:`AdvancedAuth`.
- Added optional parameter ``prompt_authorization_code`` to :class:`AdvancedAuth`.
- (**Breaking**) Renamed optional parameter ``prompt_exchange_code_if_invalid`` -> `prompt_code_if_invalid` for :class:`AdvancedAuth`.
- (**Breaking**) Renamed optional parameter ``prompt_exchange_code_if_throttled`` -> `prompt_code_if_throttled` for :class:`AdvancedAuth`.
- (**Breaking**) Renamed parameter ``exchange_code`` -> ``code`` for :class:`ExchangeCodeAuth`.
- Updated all examples to use ``prompt_authorization_code`` since thats now the easiest method.


v2.0.4
------

Small update which introduces some serious memory optimizations for accounts with many friends + exchange code fix.

Changes
~~~~~~~

- Added keyword argument ``prompt_exchange_code_if_invalid`` to :class:`AdvancedAuth`.
- Exchange code prompt messages now includes the cause for exchange code being needed.
- Added :attr:`AuthException.original` which can be used to retrieve the original error object.
- Made some serious changes to optimize memory usage.
- Corrected the endpoint used for retrieving an exchange code in :class:`EmailAndPasswordAuth`.
- Fixed an issue that caused invalid party team position swap requests to not be handled correctly.
- Fixed an issue where constructing presences would fail in some cases due to an unexpected type.


v2.0.1 - v2.0.3
---------------

Hotpatches to fix some overlooked major bugs.


v2.0.0
------

Big update which adds a commands extension and other huge changes.

Changes
~~~~~~~

- The main way to access the clients party has been moved from :class:`ClientUser` to :class:`Client`. ``client.user.party`` -> ``client.party``.
- :class:`Client`'s keyword arg ``default_party_config`` has been completely reworked. Read more about it on :class:`Client`'s page.
- :class:`Client`'s keyword arg ``default_party_member_config`` has been completely reworked. Read more about it on :class:`Client`'s page.
- Renamed ``Client.logout()`` -> :meth:`Client.close()`.
- Renamed ``event_logout()`` -> :func:`event_close()`.
- Renamed ``PartyInvitation`` -> :class:`ReceivedPartyInvitation`.
- :attr:`Presence.avatar` now returns :class:`Avatar`.

Added
~~~~~

- Ext.commands has been ported from discord.py to work with fortnitepy. All changes are wayyyy to big to mention in this changelog. You can read more about it here :ref:`here <fortnitepy_ext_commands>`.
- Added :meth:`Client.search_profiles()` to search up to 100 users by a name prefix.
- Added :class:`ProfileSearchEntryUser`.
- Added enum :class:`ProfileSeachPlatform`.
- Added enum :class:`ProfileSearchMatchType`.
- Added :meth:`Client.search_sac_by_slug()` to search for support a creator code owners by a slug.
- Added :class:`SacSearchEntryUser`.
- Added :class:`Avatar`. This can be passed to :class:`Client` on initialization to set an avatar for the bot.
- Added enum :class:`KairosBackgroundColorPreset` which offers color presets for :class:`Avatar`.
- Added :meth:`Client.set_avatar()` to set a new avatar while the client is running.
- Added :meth:`Friend.fetch_mutual_friends()` to fetch friends the client and this friend have in common.
- Added event :func:`event_party_team_swap()`.
- Added event :func:`event_party_member_in_match_change()`.
- Added event :func:`event_party_member_match_players_left_change()`.
- Added new example for integration with the web server Sanic.
- Added an ios session that is kept alive at all times. This means that you finally can use internal device auth methods after launch.
- Added :meth:`Client.remove_all_friends()`.
- Added enums :class:`SeasonStartTimestamp` and :class:`SeasonEndTimestamp` to help with passing season start and ends to stats methods.
- Added ``start_time`` and ``end_time`` kwargs to all battlepass level fetch methods. This can be used to fetch levels from past chapter 2 seasons.
- Added enum :class:`AwayStatus`.
- Added :class:`JustChattingClientPartyMember` that can be passed to :class:`DefaultPartyMemberConfig` for the client to 
- Added :class:`DefaultPartyConfig`.
- Added :class:`DefaultPartyMemberConfig`.
- Added enum :class:`PartyDiscoverability`.
- Added enum :class:`PartyJoinability`.
- Added :class:`SentPartyInvitation` which represents a sent party invite and offers functionality like resending the invite and cancelling it.
- Added :meth:`ClientParty.edit()`.
- Added :meth:`ClientParty.edit_and_keep()`.
- Added :attr:`PartyMember.position` to get a members position in a party.
- Added :attr:`PartyMember.will_yield_leadership`.
- Added :meth:`PartyMember.is_just_chatting()`.
- Added :meth:`PartyMember.in_match()`.
- Added :meth:`ClientPartyMember.set_in_match()`.
- Added :meth:`ClientPartyMember.clear_in_match()`.
- Added :attr:`PartyMember.match_started_at`.
- Added :attr:`PartyMember.match_players_left`.
- Added :meth:`PartyMember.swap_position()`.
- Added keyword ``enlightenment`` to :meth:`ClientPartyMember.set_backpack()`.
- Added :meth:`Party.get_member()`.
- Added :meth:`ClientParty.fetch_invites()`.
- Added :attr:`Presence.away`.
- Added :attr:`Presence.in_kairos`.

Removed
~~~~~~~

- Removed ``Client.update_net_cl()``.
- Removed ``Friend.fetch_mutual_friend_count``. You can now use the new :meth:`Friend.fetch_mutual_friends()`.
- Removed ``ClientPartyMember.set_shout()``.
- Removed ``Presence.avatar_colors``.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused party methods and sometimes party to be ``None`` whenever a new party was being created.
- Fixed an issue that caused sessions to not be correctly killed when closing.
- Fixed an issue where it was not possible to register more than one of each event.
- Fixed an issue that caused :func:`event_party_member_confirm()` to not always work.
- :meth:`Client.to_iso()` now only has floating point precision of three like fortnite expects.
- :meth:`Client.run()` and other utility run functions now works correctly in docker environments.
- Fixed an issue that caused display name cache lookups in profile fetch methods to not work.
- :meth:`Client.event()` can now also correctly be used on staticmethods.
- Fixed an issue that caused ``start_time`` and ``end_time`` in all stats fetch methods to not work.
- :meth:`Client.fetch_multiple_br_stats()` now accepts more than 51 owners.
- Fixed an issue where :exc:`HTTPException`'s were incomplete when raised from a graphql request.
- Fixed an issue that caused some meta values to be incorrect in some instances because of a parsing error.
- Fixed an issue where :attr:`PartyMember.platform` could be ``None`` in some rare cases.
- Fixed an issue that crashed the client on startup if the clients display name contained arabic or other letters that are read in the other direction.

Miscellanious
~~~~~~~~~~~~~

- Updated the build version.
- Removed documentation for old client kwarg ``engine_build``.
- Fixed some documentation issues.


v1.7.0
------

Update to fix some issues regarding auth and overall control over the application + some more.

Changes
~~~~~~~

- The ``exchange_code`` argument in :class:`ExchangeCodeAuth` and keyword argument in :class:`AdvancedAuth` now also accepts a callable or awaitable that must return an exchange code in form of a :class:`str`.

Added
~~~~~

- Added :meth:`Client.fetch_profile_by_email()` to fetch a :class:`User` by their email.
- Added :class:`RefreshTokenAuth` which can be used to authenticate by a launcher refresh token.
- Added keyword argument ``gap_timeout`` to :func:`start_multiple()` and :func:`run_multiple()`. The value passed decides how long it should sleep between starting the clients to avoid throttling.
- Added :attr:`PartyMember.enlightenments` to check the members enlightenment values.
- Added keyword argument ``enlightenment`` to :meth:`ClientPartyMember.set_outfit()`. Read more about it in the docs.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused :meth:`Client.restart()` not to work with all of the available auth methods.
- Fixed an issue where the wrong refresh_token was refreshed which resulted in no active launcher access token to be valid after the first auth refresh (~8 hours).
- Fixed :func:`run_multiple()` not shutting down correctly in environments that depend on signals to shut down the process.
- The client now ignores ghost pings (invites).


v1.6.2
------

Fixes :exc:`HTTPException` not being raised and changes some stuff related to :exc:`AuthException`.

Changes
~~~~~~~

- :exc:`AuthException` is now only raised when invalid credentials (email/password, device auth, exchange code or 2fa code) are passed and some other misc failures. It will no longer eat all errors raised.
- Removed ``HTTPException.reraise()``.

Added
~~~~~

- Added parameter ``prompt_exchange_code_if_throttled`` to :class:`AuthException`. If set to ``True`` it will prompt exchange code if the account is throttled.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused no :exc:`HTTPException`'s to be raised. This caused other errors which often looked weird.


v1.6.1
------

Hotpatch to fix bots not being able to start.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused json payloads sometimes not being decoded.


v1.6.0
------

This update fixes device authentication and adds some new methods to play around with.

Added
~~~~~

- Added :meth:`ClientPartyMember.set_shout()` to set a shout (Unreleased feature which plays small audio clips).  
- Added a parameter ``run_for`` to :meth:`ClientPartyMember.set_emoji()`.
- Added :meth:`ClientPartyMember.clear_backpack()`.
- Added :meth:`ClientPartyMember.clear_pet()`.
- Added :meth:`ClientPartyMember.clear_contrail()`.
- Added :meth:`ClientPartyMember.clear_assisted_challenge()`.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused device auth to not work with newly generated details.
- Fixed an issue that caused :meth:`Client.fetch_profile_by_display_name()` to not work if the account requested had linked external platforms to their account.


v1.5.5
------

Update to fix a breaking issue and also change some other necessary stuff.

Changes
~~~~~~~

- :attr:`Friend.last_logout` now always is ``None`` when the friend is added while the client is running.

Added
~~~~~

- Added :meth:`Friend.fetch_last_logout()` to fetch the last logout of a friend.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused some events not to work correctly due to an unknown payload being received.
- Fixed an issue that caused the client to attempt to join two or more parties at a time.
- Fixed an issue that in rare cases caused cache initialization to fail on startup and therefore break.
- Fixed a race condition between two events that very rarely broke the clients party.
- Readded detailed stack traces for :exc:`HTTPException` in most cases.


v1.5.4
------

Another hotpatch to fix a breaking auth refreshing issue.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused stuff to break after auth refresh.
- Fixed an issue that caused the ``cache`` keyword to be ignored in :meth:`Client.fetch_profile()` and similar fetch profile functions.
- (Docs) Fixed an issue causing :class:`ExternalAuth`'s section to be empty.


v1.5.3
------

Hotpatch to fix auth refreshing.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused auth refreshing not to work.
- Silenced an unecessary error raised sometimes when the bot left a party.


v1.5.2
------

Another update add some changes and fix a big issue introduced in v1.5.0.

Changes
~~~~~~~

- :attr:`PartyMember.ready` now is a value of the enum :class:`ReadyState` instead of an Optional[:class:`bool`].
- :meth:`ClientPartyMember.set_ready()`'s only parameter was renamed to ``state`` and now takes a value of :class:`ReadyState` instead of an Optional[:class:`bool`]
- :func:`event_party_member_ready_change()`'s arguments ``before`` and ``after`` now is a value of the enum :class:`ReadyState` instead of a :class:`str`.
- :attr:`Friend.platform` now is a value of the enum :class:`Platform` instead of a :class:`str`.
- :attr:`Presence.platform` now is a value of the enum :class:`Platform` instead of a :class:`str`.
- :attr:`PresenceParty.platform` now is a value of the enum :class:`Platform` instead of a :class:`str`.
- :attr:`PartyMember.platform` now is a value of the enum :class:`Platform` instead of a :class:`str`.

Added
~~~~~

- Added enumeration :class:`ReadyState`.
- Added method :meth:`PartyMember.is_ready()` to check if a member is ready or not.
- Added method :meth:`Client.is_closed()` to check if the client is logged out and closed.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused members of a party not to load correctly when the client was the leader of the party.
- Fixed an issue that caused an incorrect member to be marked as the leader of the party.
- The client will no longer try to promote itself when promoting a random member when changing ready state to :attr:`ReadyState.SITTING_OUT`.


v1.5.1
------

Quick hotpatch to fix Python 3.5 & 3.6 compatibility.

Bug Fixes
~~~~~~~~~

- Fixed Python 3.5 & 3.6 compatibility.


v1.5.0
------

This update fixes some important bugs and introduces functionality to ban members in party chat.

Removed
~~~~~~~

- Removed ``get_event_loop()`` since it's no longer needed. Use :func:`asyncio.get_event_loop()`.

Added
~~~~~

- Added :attr:`Friend.platform` to get the currently used platform by the friend if online.
- Added :attr:`Presence.platform` to get the platform the presence was sent from.
- Added :meth:`PartyMember.chatban()` to chatban a member.
- Added :meth:`PartyMember.is_chatbanned()` to check if a member is chatbanned.
- Added :attr:`ClientParty.chatbanned_members` to get a mapping of all chatbanned members.
- Added event :func:`event_party_member_chatban()` which emits when a party member was chatbanned.

Bug Fixes
~~~~~~~~~

- Fixed compatibility with Python 3.8 on windows specifically by setting the event loop policy to :class:`asyncio.WindowsSelectorEventLoopPolicy`.
- The email passed in :func:`event_device_auth_generate()` is now never ``None`` and always the correct email.
- Fixed an issue that caused party members of a party you joined to have the default meta values.
- Fixed an issue that caused :func:`event_party_invite()` to not emit.
- Fixed an issue that caused an internal method to never be run.
- Fixed :attr:`ClientPartyMember.leader`.
- Fixed an issue that caused an error to be raised when a message from a non-party member was sometimes received.


v1.4.0
------

Very breaking update introducing new methods to authenticate, type hinting and more.

Changes
~~~~~~~

- You no longer pass an email and a password directly when initializing :class:`Client`. ``auth`` is the new parameter taking one of the new authentication methods. Read more about them here :ref:`here <authentication>`.
- Also moved parameters ``two_factor_code``, ``launcher_token``, ``fortnite_token`` and ``device_id`` to the auth object.
- :meth:`Friend.join()` now returns the new :class:`ClientParty` the client just joined.

Bug Fixes
~~~~~~~~~

- Fixed :meth:`ClientPartyMember.set_assisted_challenge()`.
- Fixed an issue that caused :meth:`Client.fetch_profile_by_display_name()` to return a :class:`User` with missing external auths.


v1.3.1
------

Fixes some issues from the last update.

Added
~~~~~

- :meth:`Client.get_blocked_user()` to get a blocked user from the internal cache.
- :meth:`Client.is_blocked()` to check if a user is blocked.

Bug Fixes
~~~~~~~~~

- Fixed an issue that broke startup of accounts with a large amount of friends.
- Optimized startup speed of accounts with a large amount of friends.
- Fixed an issue that caused the internal blocked users cache to not get initialized correctly.
- Fixed another breaking issue that would break cache initializations.
- :attr:`Friend.nickname` and :attr:`Friend.note` now correctly is ``None`` if not set.
- Fixed an issue causing :meth:`Client.has_friend()` to return the wrong value (even though technically it did work).
- Fixed an issue where some dataclasses inheriting from :class:`User` was missing external auths at some times.


v1.3.0
------

Introduces some much awaited utility functions for starting multiple accounts at once and more stability in general.

Changes
~~~~~~~

- [**Breaking**] Member meta attributes ``assisted_challenge``, ``outfit``, ``backpack``, ``pickaxe``, ``contrail`` and ``emote`` now returns the asset path instead of just the id.
- [**Breaking**] :attr:`User.external_auths` has been changed and fully utilized.
- Optimized the auth flow and general startup speeds by ~1 second.
- Lookup methods now also searches for non-epic accounts.
- :attr:`User.display_name` now uses an external display name if the account is not linked to an epic account.
- :meth:`Client.fetch_br_stats()` now raises :exc:`Forbidden` if the account requested has private stats.
- Changed some examples to reflect some of this updates changes.

Added
~~~~~

- Added a parameter ``cache_users`` to :class:`Client` and can be used to turn off the users cache and therefore in some cases save some memory but sacrificing a little speed on some user lookups.
- Added utility functions :func:`run_multiple()`, :func:`start_multiple()` and :func:`close_multiple()` to help with controlling multiple clients at once.
- Added support for pets with :meth:`ClientPartyMember.set_pet()`, :attr:`ClientPartyMember.pet` and the event :func:`event_party_member_pet_change`.
- Added support for emojis with :meth:`ClientPartyMember.set_emoji()`, :attr:`ClientPartyMember.emoji` and the event :func:`event_party_member_emoji_change`.
- Added :attr:`HTTPException.validation_failures`.
- Added :attr:`User.epicgames_account` to check if an account is an epicgames account.
- Added an example for usage with the api https://fortnite-api.com/.

Bug Fixes
~~~~~~~~~

- Fixed an issue that caused :meth:`Client.start()` to return whenever :meth:`Client.restart()` was returned.
- :meth:`Client.restart()` now correctly returns errors.
- Fixed an issue that in some rare cases caused task cancelling on shutdown to break.
- Fixed an issue that caused :meth:`Client.fetch_profiles()` to break in some cases where you looked up an id and a display name.
- Some annoyingly long error stack traces should now be a little smaller (without losing any context).
- Fixed an issue that caused buying fortnite on accounts that did not already own it to fail.
- Fixed an issue that caused :meth:`ClientPartyMember.set_assisted_challenge()` to break if no asset was passed.
- Fixed a rare issue that caused some presences to break.
- Fixed a trailing issue from last update that caused some events regarding pending friend requests to not work properly.


v1.2.2
------

Fixes the login flow and another breaking login bug.

Changes
~~~~~~~

- [**BREAKING**] Attribute ``favorite`` removed from :class:`PendingFriend`.

Bug Fixes
~~~~~~~~~

- Fixed the login flow (you can now actually log in to an account).
- Fixed an issue where login would break because of a missing parameter in a payload.


v1.2.1
------

Fixes small mistakes introduced in v1.2.0.

Bug Fixes
~~~~~~~~~

- The client no longer sends a party message every time a new member joins (oops).
- Using :meth:`ClientPartyMember.clear_emote()` now cancels current clear tasks created by ``run_for``.
- Fixed some docs issues as well as a logging issue.


v1.2.0
------

This update adds a lot of new stuff and also increases stability.

[**ALL BREAKING**] Changes
~~~~~~~

- :func:`event_logout()` is no longer called when the client is logged out via :meth:`Client.restart()`.
- :meth:`PartyMember.create_variants()` is now a staticmethod.
- [**RENAME**] ``Client.get_blocklist()`` -> :meth:`Client.fetch_blocklist()`
- [**RENAME**] ``DefaultCharacters`` -> :class:`DefaultCharactersChapter1`

Added
~~~~~

- When setting the clients status, you can now use two placeholders ``{party_size}`` and ``{party_max_size}`` which is replaced automatically when status is sent.
- Added :class:`BlockedUser` with a single unique method being :meth:`BlockedUser.unblock()`.
- Added a cache for blocked users.
- Added :attr:`Client.blocked_users`.
- Added :meth:`User.block()`.
- Added :attr:`PartyMember.contrail` and :attr:`ClientPartyMember.contrail`.
- Added :attr:`PartyMember.contrail_variants` and :attr:`ClientPartyMember.contrail_variants`.
- Added :meth:`ClientPartyMember.set_contrail()`.
- Added event :func:`event_party_member_contrail_change()`.
- Added event :func:`event_party_member_contrail_variants_change()`.
- Added :class:`DefaultCharactersChapter2`. A random skin for :class:`ClientPartyMember` is now chosen from this enum.
- Added kwarg ``profile_banner`` to :meth:`PartyMember.create_variants()`.
- Added :attr:`Region.MIDDLEEAST` and removed :attr:`Region.CHINA`.
- Added :attr:`PresenceGameplayStats.friend`.
- Added magic methods to some classes where it made sense:
    - :class:`Friend` (``__repr__``, ``__str__``)
    - :class:`PendingFriend` (``__repr__``, ``__str__``)
    - :class:`ClientUser` (``__repr__``, ``__str__``)
    - :class:`User` (``__repr__``, ``__str__``)
    - :class:`BlockedUser` (``__repr__``, ``__str__``)
    - :class:`PartyMember` (``__repr__``, ``__str__``)
    - :class:`ClientPartyMember` (``__repr__``, ``__str__``)
    - :class:`Party` (``__repr__``, ``__str__``)
    - :class:`ClientParty` (``__repr__``, ``__str__``)
    - :class:`PartyInvitation` (``__repr__``)
    - :class:`PartyJoinConfirmation` (``__repr__``)
    - :class:`FriendMessage` (``__repr__``)
    - :class:`PartyMessage` (``__repr__``)
    - :class:`BattleRoyaleNewsPost` (``__repr__``, ``__str__``)
    - :class:`Playlist` (``__repr__``, ``__str__``)
    - :class:`PresenceGameplayStats` (``__repr__``)
    - :class:`PresenceParty` (``__repr__``)
    - :class:`Presence` (``__repr__``)
    - :class:`StatsV2` (``__repr__``)
    - :class:`Store` (``__repr__``)
    - :class:`FeaturedStoreItem` (``__repr__``, ``__str__``)
    - :class:`DailyStoreItem` (``__repr__``, ``__str__``)

Bug Fixes
~~~~~~~~~

- Fixed two factor authentication.
- Fixed an issue that caused :func:`event_party_member_confirm()` to not work when defined in a subclass of :class:`Client`.
- Fixed an issue that caused :meth:`Client.fetch_blocklist()` to not work.
- The HTTP client now attempts to resend a request if ``server_error`` or ``concurrent_modifaction_error`` is received.
- Fixed an issue that caused :meth:`PartyMember.kick()` to raise an incorrect error.
- Calling :meth:`ClientPartyMember.set_emote()` with the ``run_for`` keyword argument will now cancel any existing emote cancelling tasks created by ``run_for`` before.
- Fixed an issue where an error would be raised if the client was friends with someone that had never entered fortnite before.
- Fixed two rare errors raised because of missing attributes in xmpp event payloads.
- Fixed an noisy issue where the client sometimes attempted to remove a missing pending friend from the cache.
- Fixed an issue that caused the processing of variant changes from other party members to fail.
- Fixed a noisy issue that was raised on startup of some clients (bIsPlaying).
- Fixed an issue that caused :meth:`PartyInvitation.decline()` to raise an error.


v1.1.0
------

This update adds some much awaited edit functions to ClientPartyMember as well as some important bug fixes.

Added
~~~~~

- Added :meth:`ClientPartyMember.edit()` which patches multiple meta changes at once.
- Added :meth:`ClientPartyMember.edit_and_keep()` which patches multiple meta changes at once and then keeps the changes so they are automatically equipped when joining new parties.
- Added keyword ``default_party_member_config`` to :class:`Client` which takes a list of meta changes and automatically equips them when joining new parties.

Bug Fixes
~~~~~~~~~

- Fixed :meth:`Friend.remove()`.
- Fixed an issue where :attr:`PartyMember.outfit` would sometimes raise an error.
- Fixed an issue causing an error to sometimes be raised when a new member joined the party.
- Fixed an issue causing an error to sometimes be raised when a message was received from party chat.


v1.0.3
------

Another hotpatch to fix a silly issue from the last one .-.

Bug Fixes
~~~~~~~~~

- Fixed :meth:`Client.from_iso()`.


v1.0.2
------

Another hotpatch.

Changes
~~~~~~~

- Fixed an issue where :func:`event_party_member_kick()` would not emit if the member was kicked by the client.
- Fixed a bug that caused an error to be raised when converting a string to a datetime object internally.
- :meth:`Client.join_to_party()` now waits until the client has joined the party before returning.
- :meth:`PresenceParty.join()` now returns the :class:`ClientParty` that was just joined.


v1.0.1
------

Quick update to fix some issues brought along with v1.0.0.

Added
~~~~~

- Added :func:`event_friend_request_decline()` which emits when a friend request in either direction is declined.

Renamed
~~~~~~~

- :meth:`Client.get_user()`'s only parameter has been renamed from ``id`` to ``user_id``.
- :meth:`Client.get_friend()`'s only parameter has been renamed from ``id`` to ``user_id``.
- :meth:`Client.get_presence()`'s only parameter has been renamed from ``id`` to ``user_id``.
- :meth:`Client.get_pending_friend()`'s only parameter has been renamed from ``id`` to ``user_id``.
- :meth:`Client.has_friend()`'s only parameter has been renamed from ``id`` to ``user_id``.
- :meth:`Client.is_pending()`'s only parameter has been renamed from ``id`` to ``user_id``.
- :meth:`Client.block_user()`'s only parameter has been renamed from ``id`` to ``user_id``.
- :meth:`Client.unblock_user()`'s only parameter has been renamed from ``id`` to ``user_id``.

Bug Fixes
~~~~~~~~~

- Unavailable presences now work as expected again.
- Fixed an issue where an error was raised when when removing a friend in some special cases.
- Fixed an issue that caused :meth:`Client.remove_or_decline_friend()` to not work.


v1.0.0
------

| **BREAKING UPDATE**
| Massive code overhaul and lots of new stuff / bugs fixes. Keep in mind that this is a very big update so issues and bugs might appear. If so, report them either on the issue tracker or on discord.

Added
~~~~~

- Added :meth:`Client.restart()` which restarts the client completely.
- Added :meth:`Client.accept_friend()` which accepts a friend and then returns the :class:`Friend` object of the friend you added.
- Added :attr:`Friend.nickname` which returns the currently set nickname for a friend.
- Added :attr:`Friend.note` which returns the currently set note for a friend.
- Added :attr:`Friend.last_logout` which returns the time of a friends last logout.
- Added :meth:`Friend.fetch_mutual_friends_count()` which returns the number of mutual friends the friend and the client have.
- Added :meth:`Friend.set_nickname()` to set a friends nickname.
- Added :meth:`Friend.remove_nickname()` to remove the friends nickname.
- Added :meth:`Friend.set_note()` to pin a note to a friend.
- Added :meth:`Friend.remove_note()` to remove the note pinned to a friend.
- Added :attr:`ClientUser.email_verified`.
- Added :attr:`ClientUser.minor_verified`.
- Added :attr:`ClientUser.minor_expected`.
- Added :attr:`ClientUser.minor_status`.
- Added event :func:`event_restart()` which emits when the client has successfully restarted.
- Added event :func:`event_auth_refresh()` which emits when the clients authentication has been successfully refreshed.
- Added event :func:`event_party_playlist_change()` which emits when the playlist of the clients current party is changed.
- Added event :func:`event_party_squad_fill_change()` which emits when the squad fill value is changed.
- Added event :func:`event_party_privacy_change()` which emits when the party privacy is changed.
- Added event :func:`event_party_member_ready_change()` which emits when a members ready state is changed.
- Added event :func:`event_party_member_input_change()` which emits when a members input is changed.
- Added event :func:`event_party_member_assisted_challenge_change()` which emits when a members assisted challenge is changed.
- Added event :func:`event_party_member_outfit_change()` which emits when a members outfit is changed.
- Added event :func:`event_party_member_backpack_change()` which emits when a members backpack is changed.
- Added event :func:`event_party_member_pickaxe_change()` which emits when a members pickaxe is changed.
- Added event :func:`event_party_member_emote_change()` which emits when a members emote is changed.
- Added event :func:`event_party_member_banner_change()` which emits when a members banner is changed.
- Added event :func:`event_party_member_battlepass_info_change()` which emits when a members battlepass info is changed.
- Added event :func:`event_party_member_outfit_variants_change()` which emits when a members outfit variants is changed.
- Added event :func:`event_party_member_backpack_variants_change()` which emits when a members backpack variants is changed.
- Added event :func:`event_party_member_pickaxe_variants_change()` which emits when a members pickaxe variants is changed.

[**ALL BREAKING**] Renamed
~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``event_party_updated()`` -> :func:`event_party_update()`
- ``Client.remove_friend`` -> :meth:`Client.remove_or_decline_friend()`
- ``PartyMember.is_leader`` -> :attr:`PartyMember.leader`
- ``ClientPartyMember.is_leader`` -> :attr:`ClientPartyMember.leader`
- ``Party.squad_fill_enabled`` -> :attr:`Party.squad_fill`
- ``ClientParty.squad_fill_enabled`` -> :attr:`ClientParty.squad_fill`
- ``PartyInvitation.author`` -> :attr:`PartyInvitation.sender`
- ``PresenceParty.is_private`` -> :attr:`PresenceParty.private`
- ``Presence.is_available`` -> :attr:`Presence.available`
- ``Presence.is_playing`` -> :attr:`Presence.playing`
- ``Presence.is_joinable`` -> :attr:`Presence.joinable`

Changes
~~~~~~~

- :meth:`Client.start()` now takes an optional parameter ``dispatch_ready`` which determines if the :func:`event_ready()` should be dispatched when the client is ready.
- :meth:`Client.logout()` now takes an optional parameter ``close_http`` which determines if the clients :class:`aiohttp.ClientSession` should be closed when logged out.
- The decorator :meth:`Client.event()` can now be used by being called. Read more about it on its page.
- [**BREAKING**] :meth:`Friend.is_online()` is now a method instead of an attribute.
- :meth:`PendingFriend.accept()` now returns the friend object of the friend you just accepted.
- :meth:`ClientPartyMember.set_ready()` now promotes a random member to leader when changing to sitting out.
- [**BREAKING**] :func:`event_party_member_promote()` now has an additional parameter which represents the previous leader.
- :meth:`ClientPartyMember.set_outfit()`'s parameter ``asset`` is now optional.
- :meth:`ClientPartyMember.set_backpack()`'s parameter ``asset`` is now optional.
- :meth:`ClientPartyMember.set_pickaxe()`'s parameter ``asset`` is now optional.

Bug Fixes
~~~~~~~~~

- Fixed an issue causing the :func:`event_party_member_confirm()` event to not work.
- Fixed an issue that caused :meth:`Client.fetch_br_stats()` to not work when passing a starttime and an endtime.
- Fixed an issue that caused ``party_not_found`` to be raised when the bot was leaving its current party.
- Fixed an issue that caused :attr:`Friend.favorite` to return an incorrect value.
- Swapped some unintentional f-strings (oops) for the python 3.5 supported format method.
- Attempted to fix an issue where an error would be raised saying the clients oauth token was invalid.
- Fixed an issue introduced in fortnite v11.30 that caused adding/removing friends to not work.
- Fixed an issue introduced in fortnite v11.30 that caused inviting and joining parties to not work.
- Fixed an issue that caused :meth:`Client.fetch_br_stats()`, :meth:`Client.fetch_multiple_br_stats()` and :meth:`Client.fetch_leaderboard()` to not work.
- Fixed an issue that caused :attr:`Presence.playing`, :attr:`Presence.joinable` and :attr:`Presence.has_voice_support` to return incorrect values.
- :attr:`StatsV2.start_time` and :attr:`StatsV2.end_time` now returns an UTC timestamp instead of a local timestamp (oops).
- Fixed an issue that caused :meth:`Client.fetch_item_shop()` to emit an error.
- Fixed an issue where :attr:`Presence.friend` would be ``None``.
- Fixed an issue where changing variants with :meth:`ClientPartyMember.set_outfit()`, :meth:`ClientPartyMember.set_backpack()` and :meth:`ClientPartyMember.set_pickaxe()` would sometimes not work properly.
- Fixed an issue where :meth:`Client.fetch_active_ltms()` would sometimes fail and raise an error.


v0.9.0
------

| **BREAKING UPDATE**
| This update adds windows support for python 3.8, removes the need for setting a net_cl and fixes multiple important bugs.

Breaking Changes
~~~~~~~~~~~~~~~~

- :exc:`Forbidden` has been renamed from ``PartyPermissionError``.
- Reworked and added documentation for :meth:`Client.join_to_party()`. The function no longer takes ``party`` as a keyword and a new kwarg ``check_private`` has been added.

Changes
~~~~~~~

- You no longer need to worry about net_cl, ever.
- Added :func:`get_event_loop()` to get a working event loop on Windows. It isn't necessary to use this function as long as fortnitepy is imported before the event loop is created.
- Added :meth:`HTTPException.reraise()` which reraises the exception.
- Added :meth:`Friend.invite()` which invites the friend to your party.
- :meth:`ClientPartyMember.set_banner()` and :meth:`ClientParty.set_playlist()`
- The loading time between accepting and joining a party with 2+ users has been significantly decreased.
- :meth:`PartyInvitation.accept()` now raises :exc:`Forbidden` if you attempted to join a private party you have already been a member of before.

Bug Fixes
~~~~~~~~~

- Fixed multiple internal issues related to party chat.
- Fixed an issue where that caused invites sent by the client to its private party to not work.
- Fixed an issue where :func:`event_party_member_join()` would dispatch before party chat was ready.
- Fixed an issue that caused aioxmpp logger to not work.


v0.8.0
------

| **BREAKING UPDATE**
| This update reworks and adds a couple of stats functions, adds some new features that came with Fortnite 2 season 1 and fixes some important bugs.

Breaking Changes
~~~~~~~~~~~~~~~~

- Most functions with keyword arguments now uses strict kwargs. This means you must specify the argument as a keyword. If you've used keyword arguments correctly before, this will not be an issue.
- The new correct way to get stats from the object :class:`StatsV2` is now with the :meth:`StatsV2.get_stats()` method. Up until this version the way to get the stats from the object was to call ``StatsV2.stats``.
- :meth:`Client.fetch_br_stats()` now returns ``None`` if the user was not found. An empty :class:`StatsV2` is still returned if a valid user doesn't have any recorded stats.
- :meth:`Client.fetch_multiple_br_stats()` now returns ``None`` mapped to the passed userid if the user was not found. An empty :class:`StatsV2` is still returned if a valid user doesn't have any recorded stats for the stats you requested.
- The cache keyword argument in :meth:`Client.fetch_profile`, :meth:`Client.fetch_profiles` and :meth:`Client.fetch_profile_by_display_name` now defaults to ``False`` which means the client will not attempt to get any of the requested users from the cache.
- :attr:`Playlist.violator` was renamed from `violater` because of the typo.
- :attr:`PresenceGameplayStats.players_alive` was moved from :class:`Presence` to :class:`PresenceGameplayStats`.

Added
~~~~~

- Added a new event :func:`event_friend_request_abort` which emits when a sent friend request is aborted before the receiving user has accepted it.
- Added :meth:`Client.update_net_cl()` which updated the current net_cl and party_build_id while the client is running.
- Added :meth:`Client.fetch_multiple_battleapss_levels` which fetches multiple userids battlepass levels at once.
- Added :meth:`Client.fetch_battlepass_level` which fetches a userid's battlepass level.
- You can now pass ``None`` to :meth:`ClientPartyMember.set_ready()` to make the client go into the Sitting Out state.
- Added :attr:`PartyInvitation.net_cl` which returnes the net_cl that was sent with a party invitation.
- Added :attr:`Presence.avatar` to get the cid of the friends Kairos avatar.
- Added :attr:`Presence.avatar_colors` to get the background colors of the friends Kairos avatar.
- Added :meth:`StatsV2.get_stats()` which is now the correct approach to getting the users stats mapped to platforms and gamemodes from the object. 
- Added :meth:`StatsV2.get_combined_stats()` to get the users combined stats mapped to platforms. There is also an option to combine stats across all platforms.
- Added :meth:`User.fetch_br_stats()` to get a users stats directly from the object. (Function exists for :class:`Friend` too since it inherits from :class:`User`)
- Added :meth:`User.fetch_battlepass_levels()` to get a users battlepass level directly from the object. (Function exists for :class:`Friend` too since it inherits from :class:`User`)
- Updated net_cl and build info.

Bug Fixes
~~~~~~~~~

- :attr:`StatsV2.start_time` and :attr:`StatsV2.end_time` now actually works.
- Removed the new stat ``s11_social_bp_level`` from :class:`StatsV2`.
- Moved the check invalid net_cl check to method :meth:`PartyInvitation.accept()` so it is possible to catch the exception.
- Renamed :attr:`Playlist.violator` from ``violater`` because of the typo.
- Waiting for the 2fa code to be entered into console is no longer blocking.
- :class:`Playlist` now uses __slots__ to reduce its memory footprint.
- Fixed another issue that lead to ``Incompatible net_cl`` being incorrectly raised.
- Attempted to fix `issue #38 <https://github.com/Terbau/fortnitepy/issues/38>`_.
- Fixed some issues in the docs.


v0.7.0
------

| **BREAKING UPDATE**
| Lots of small bug fixes and some added functionality as well.

Breaking Changes
~~~~~~~~~~~~~~~~

- :class:`Client`'s keyword argument ``platform`` now accepts the new enumerator :class:`Platform` instead of :class:`str`.
- :meth:`ClientParty.set_playlist()` keyword argument ``region`` now accepts the enumerator :class:`Region` instead of :class:`str`.
- Renamed :func:`event_friend_remove` from ``event_friend_removed``.
- Renamed :func:`event_party_member_kick` from ``event_party_member_kicked``.
- Renamed :func:`event_party_member_disconnect` from ``event_party_member_disconnected``.
- Renamed :func:`event_party_member_update` from ``event_party_member_updated``.
- Renamed :func:`event_party_member_confirm` from ``event_party_member_confirmation``.
- Renamed :func:`event_party_member_cancel` from ``event_party_member_cancelled``.
- Renamed :func:`event_party_member_decline` from ``event_party_member_declined``.
- Renamed :class:`V2Input` from ``V2Inputs``.
- Renamed :class:`Region` from ``Regions``.
- Removed attribute ``engine_build`` from :class:`Client` since it was not being used.

Added
~~~~~

- Added :func:`event_logout()` which is called just before the client is about to log out.
- Fortnite is now automatically bought for free on startup if the account does not already own it.
- Added an example to showcase how you can have multiple clients running at the same time.
- Added enumeration :class:`Platform`.
- Added :attr:`Client.os`. You shouldnt ever need to change this but you could do it by passing a different value with the ``os`` keyword when initialising :class:`Client`.
- Added :attr:`PartyMember.outfit_variants` to get the raw outfit variants of this member.
- Added :attr:`PartyMember.backpack_variants` to get the raw backpack variants of this member.
- Added :attr:`PartyMember.pickaxe_variants` to get the raw pickaxe variants of this member.
- Added keyword ``variants`` to :meth:`ClientPartyMember.set_backpack()`.
- Added keyword ``variants`` to :meth:`ClientPartyMember.set_pickaxe()`.
- Added :attr:`PresenceParty.net_cl` to get the net_cl received with this presence.
- Updated net_cl and build info.

Bug Fixes
~~~~

- Fixed and silenced multiple noisy errors like the OpenSSL error printed on shutdown.
- The default user-agent used internally is now correctly built by :attr:`Client.build` and :attr:`Client.os`.
- Removed the annoying message printed to console every time a friend was added or removed.
- :class:`Client` now successfully shuts down if an error occurs in the login process.
- You can now try except :meth:`Client.run()`.
- Outgoing presences now correctly uses :attr:`Client.party_build_id` instead of :attr:`Client.net_cl`.
- Display names of friends should now always have a value if exists.
- Fixed an issue where a presence would not be sent if a member was promoted to leader of the party.
- Fixed an issue where :attr:`Presence.friend` would sometimes be ``None``.
- Fixed an issue where the platform set would not be visibly changed in-game.
- Fixed an issue where party chat would sometimes not work.


v0.6.4
------

Little update to push out a better authentication flow.

Added
~~~~~

- Added a more stable, faster and more reliable authentication flow. Thanks iXyles and Bad_Mate_Pat.


v0.6.3
------

| **HIGHLY IMPORTANT UPDATE**
| Fixed authentication to work with the newest changes fortnite made to their services.

Updated
~~~~~~~

- Updated net_cl.

Bug Fixes
~~~~~~~~~

- Fixed authentication.


v0.6.1
------

Hotpatch to make all datetime objects represented in the UTC timezone. 

Changed
~~~~~~~

- All datetime objects are now represented in the UTC timezone.

Bug Fixes
~~~~~~~~~

- Fixed an issue where token refresh would happen at the wrong time.


v0.6.0
------

| **BREAKING UPDATE**
| Reworked parties and added some new stuff. This rework has been in my mind for some time but was recently accelerated because of some breaking bugs that required this rework.

Reworked
~~~~~~~~

- :class:`ClientParty` is the new object for parties the client is a part of.
- :class:`Party` is now only used for parties the client is not a part of. 
- :class:`ClientPartyMember` is the new object that represents the client as a partymember.
- :class:`PartyMember` represents party members like usual but is now mostly read-only with exceptions for some methods.

.. note::

    You can get the :class:`ClientPartyMember` object from :attr:`ClientParty.me`.

Additions
~~~~~~~~~

- Added attr ``member_count`` to :class:`Party` and :class:`ClientParty` to get the member count of the party.
- Added attr ``inbound`` and ``outgoing`` to :class:`Friend` and :class:`PendingFriend`.
- Added :attr:`Client.friends` to get a mapping of all friends.
- Added :attr:`Client.pending_friends` to get a mapping of all pending friends.
- Added :attr:`Client.presences` to get a mapping of friends latest presence received.

Bug Fixes
~~~~~~~~~

- Fixed an issue where :attr:`PartyMember.direction` and :attr:`PartyMember.favorite` would be ``None`` in events.
- Fixed an issue where parties would sometimes break down completely when receiving an invite.


v0.5.2
------

Internal changes 99% of you wont ever notice + some small bug fixes.

Refactored
~~~~~~~~~~

- Reworked :meth:`Client.run()` to use :meth:`asyncio.AbstractEventLoop.run_forever()` and implemented better task cleanup heavily based of discord.py's cleanup method.
- Reworked :meth:`Client.start()` and :meth:`Client.logout()` a work better together when logging out while running.
- Changed some internal data body values related to parties to match fortnite's values.
- The clients XMPP jid will now use a unique id in its resource part.

Bug Fixes
~~~~~~~~~

- Fixed an issue with :meth:`Client.fetch_profiles()` where if ``raw`` was ``True`` and some of the profiles were gotten from cache they would not be returned raw.
- Fixed an issue with :meth:`Client.fetch_profiles()` where if no profiles was retrieved an error would be raised.


v5.0.1
------

Quick update fixing some small bugs.

Bug Fixes
~~~~~~~~~

- Fixed :meth:`PartyMember.set_emote()` raising an error if ``run_for`` keyword argument was ``None``.
- Fixed an internal error where the party chatroom was not overwritten correctly when leaving a party.


v0.5.0
------

Breaking update removing ``Party.leave()`` and adding many new meta related party features + important bug fixes.

Breaking Changes
~~~~~~~~~~~~~~~~

- Removed ``Party.leave()``. Use :meth:`PartyMember.leave()` instead.

New Features
~~~~~~~~~~~~

- Added :attr:`PartyMember.ready` which returns the state of a members readiness.
- Added :attr:`PartyMember.input` to check what input a party member is using.
- Added :attr:`PartyMember.assisted_challenge` to get a members currently set party-assisted challenge.
- Added :attr:`PartyMember.outfit` to get the CID of the current outfit a member has equipped.
- Added :attr:`PartyMember.outfit_variants` to get the raw variants of the current outfit a member has equipped.
- Added :attr:`PartyMember.backpack` to get the BID of a members currently equipped backpack.
- Added :attr:`PartyMember.pickaxe` to get a members currently set pickaxe.
- Added :attr:`PartyMember.emote` to get a members currently playing emote.
- Added :attr:`PartyMember.banner` to get a tuple consisting of the members currently set banner.
- Added :attr:`PartyMember.battlepass_info` to get a tuple consisting of the members battlepass info.
- Added :attr:`PartyMember.platform` to get a members platform.
- Added :attr:`Party.playlist_info` to get a tuple consisting of information about the currently set playlist.
- Added :attr:`Party.squad_fill_allowed` which returns the state of squad fill.
- Added :attr:`Party.privacy` to get the partys privacy.
- Added keyword-argument ``run_for`` to :meth:`PartyMember.set_emote()` for setting how long an emote should be playing for in seconds.

Updated
~~~~~~~

- Updated :attr:`Client.net_cl` to match the value from the Fortnite v10.10 update.
- Updated :attr:`Client.build` to match the value from the Fortnite v10.10 update.
- Updated :attr:`Client.engine_build` to match the value from the Fortnite v10.10 update.

Bug Fixes
~~~~~~~~~

- Fixed the naming of :func:`event_member_updated` not matching the docs.
- Fixed :meth:`Client.has_friend()` returning the opposite of the correct value.
- Fixed :meth:`PartyMember.create_variants()` not working like intended in some situations.
- Fixed an issue where you would get an error if you tried to initialize the client with a different default party privacy.
- Fixed an issue where :meth:`Party.set_privacy()` would raise an error causing the function to fail.
- Fixed an issue where an error were sometimes raised due to attempting to create a new party while already in a another.
- Fixed :meth:`PartyMember.set_assisted_challenge()` only taking a full path for the quest argument.
- Fixed an issue where members of a party the client is joining would not have updated metas.
- Fixed an issue where an unecessary error would be raised when sending a message to a party chat.

Miscellanious
~~~~~~~~~~~~~

- Added missing :func:`event_party_member_leave` to the event reference.
- Added "How can I fix the Incompatible net_cl error" to the faq.
- Updated the faq answer regarding two factor auhentication usage.
- Updated arena docs example for :meth:`Party.set_privacy()` to match the new arena playlist information introduced in Fortnite v10.


v0.4.1
------

Small update which adds some basic functionality and fixes some important bugs like invites not working.

New Features
~~~~~~~~~~~~

- Added :meth:`Client.is_ready()` which checks if the internal state of the client is ready.
- Added :meth:`Client.wait_until_ready()` which waits for the clients internal state to get ready.

Updated
~~~~~~~

- Updated :attr:`Client.net_cl` to match the value from the Fortnite v10 update.
- Updated :attr:`Client.build` to match the value from the Fortnite v10 update.
- Updated :attr:`Client.engine_build` to match the value from the Fortnite v10 update.

Bug Fixes
~~~~~~~~~

- Fixed party invites not emitting the :func:`event_party_invite` event.
- Fixed an issue where :func:`event_friend_add` would in some cases return the clients user instead of the player added.


v0.4.0
------

This is a small feature update I'm releasing before I go on a small vacation. I have a couple more features planned that I wished I had time to add to this update that unfortunately didn't make it in. They will be included in the next update.

New Features
~~~~~~~~~~~~

- :func:`event_friend_presence` is now also emitted when a user goes offline on Fortnite.
- Added :attr:`Presence.is_available` to show if the user that emitted this presence is online or went offline.
- Added :attr:`Friend.is_online` to show if a friend is currently online on Fortnite.
- Added support for two factor auhentication. If you do not pass a 2fa code when initializing the client, you will be asked to enter it into console when that time comes.
- You can now pass :attr:`Client.two_factor_code` and :attr:`Client.device_id` to client when initializing.
- Added :attr:`HTTPException.raw` to get the raw error received from Fornite services.

Bug Fixes
~~~~~~~~~

- :meth:`Client.fetch_profile_by_display_name` and :meth:`Client.fetch_profile` now correctly returns ``None`` when the user was not found.
- Fixed an issue where the fetching of friends on startup did not work as intended.
- Fixed an issue where the client would fail to automatically recreate a party in some situations.
- Fixed an issue where party presences was processed as a user presence.

Miscellanious
~~~~~~~~~~~~~

- Added missing documentation to some functions.
- The ``Incompatible build id`` error message will now say ``Incompatible net_cl`` to avoid some confusion around what the problem really is.


v0.3.1
------

Minor release to update build info to match the new values changed in v9.41.

Updated
~~~~~~~

- Updated :attr:`Client.net_cl`.
- Updated :attr:`Client.build`.
- Updated :attr:`Client.engine_build`.


v0.3.0
------

This update fixes some of the big issues and bugs with this library making it much more stable. It also introduces a couple of missing methods and attributes.

New Features
~~~~~~~~~~~~

- Added :meth:`PartyMember.leave` for leaving a party and creating a new one.
- Reworked :exc:`HTTPException` to include more data of the request and exception gotten from Fortnite services.
- Added attributes ``display_names`` and ``violator`` to :class:`FeaturedStoreItem` and :class:`DailyStoreItem`.

Bug Fixes
~~~~~~~~~

- Fixed XMPP service timing out after a while due to pinging not being handled well enough.
- Fixed :exc:`asyncio.TimeoutError` sometimes occurring when a new party was being made (mainly noticed on startup) which completely shut down the clients party services.
- Fixed ``stale_revision`` sometimes occurring when party related request happened making the request completely fail.
- Fixed ``error code -93`` sometimes occurring when trying to join the clients party.


v0.2.0
------

This is the first major update for fortnitepy. This update includes a fix for an issue with invites not working after the Fortnite v9.40 as well as a couple of new features.

Thanks to `amrsatrio <https://github.com/Amrsatrio>`_ and `Luc1412 <https://github.com/Luc1412>`_ for suggestions and help with this update.

New Features
~~~~~~~~~~~~

- Added :meth:`Client.fetch_lightswitch_status` for checking Fortnite's status.
- Added :meth:`Client.fetch_item_shop` for fetching the current item shop.
- Added :meth:`Client.fetch_br_news` for fetching the current Battle Royale news.
- Added :meth:`Client.fetch_multiple_br_stats` for fetching a list of stats for multiple users at the same time.
- Added :meth:`Client.fetch_leaderboard` for fetching the leaderboard for a stat.
- Added the enum :class:`V2Inputs` for better access to the different input types.
- Added :meth:`StatsV2.create_stat` for easier and more understandable interaction with V2 stats.
- Added :meth:`Client.fetch_br_playlists` for fetching all known playlists registered on Fortnite. 
- Added :meth:`Client.fetch_active_ltms` for fetching the active Limited Time Gamemodes for a specific region.
- Added the enum :class:`Regions` for better access to the regions used by Fortnite services.
- Added :meth:`PartyMember.create_variants` for easier building of variants used for outfits. The variants system used by Fortnite follows little logic and therefore this function is probably a little confusing. Expect a guide on outfit variants in not too long.

Bug Fixes
~~~~~~~~~

- Fixed an issue introduced with the Fortnite v9.40 update that made party invites not work.
- Fixed an issue where the client would not make a new party if the client expires from an earlier party. (fix for fortnite ``error code -93`` upon attempting to join the clients party.)

Miscellanious
~~~~~~~~~~~~~

- Added some enums and functions to make ready for StatsV1 support coming in a later update.


v0.1.3
------

Quick update to update new build info that came with the Fortnite v9.40 update.

Updates
~~~~~~~

- Updated net_cl.
- Updated engine_build.
- Updated build.

