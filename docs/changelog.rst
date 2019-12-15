.. currentmodule:: fortnitepy

Changelog
=========

Detailed version changes.


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

