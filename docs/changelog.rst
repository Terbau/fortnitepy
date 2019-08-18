.. currentmodule:: fortnitepy

Changelog
=========

Detailed version changes.


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

