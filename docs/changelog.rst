.. currentmodule:: fortnitepy

Changelog
=========

Detailed version changes.


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

