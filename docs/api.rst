.. currentmodule:: fortnitepy

API Reference
=============

.. _authentication:

Authentication
--------------

As of v1.4.0, you now have to specify which authentication method you want to 
use for login. The one used up until this version was :class:`EmailAndPasswordAuth`. However,
after that authentication method recently has started to require captcha to login in quite a lot
of cases, this is no longer the preferred method in the long run.

The preferred method in the long run is now :class:`DeviceAuth`. To set up and handle this type
of auth, you should use :class:`AdvancedAuth`. `This example <https://github.com/Terbau/fortnitepy/blob/master/examples/basic_client.py>`_ demonstrates
how you can set up this auth with file storage for the preferred login which is :class:`DeviceAuth`.

.. autoclass:: EmailAndPasswordAuth

.. autoclass:: ExchangeCodeAuth

.. autoclass:: DeviceAuth

.. autoclass:: AdvancedAuth


Client
------

.. autoclass:: Client
    :members:


Utility Functions
-----------------

Utility functions provided by the package.

.. autofunction:: run_multiple

.. autofunction:: start_multiple
	
.. autofunction:: close_multiple


Enumerations
------------

.. class:: PartyPrivacy

	Specifies the privacy used in parties created by the client.

	.. attribute:: PUBLIC

		Sets privacy to completely public. This means everyone can join the party, even friends of friends.
	.. attribute:: FRIENDS_ALLOW_FRIENDS_OF_FRIENDS

		Sets privacy to only allow friends but friends of friends are able to join.
	.. attribute:: FRIENDS

		Sets privacy to friends only.
	.. attribute:: PRIVATE_ALLOW_FRIENDS_OF_FRIENDS

		Sets privacy to private but allows friends of friends.
	.. attribute:: PRIVATE

		Sets privacy to private without the possibility of friends of friends joining.

.. class:: V2Input

	An enumeration for valid input types used for stats.

	.. attribute:: KEYBOARDANDMOUSE

		Input type used for all users of keyboard and mouse. This is not only used
		for pc players but also other platforms where it's possible to use keyboard
		and mouse.
	.. attribute:: GAMEPAD

		Input type used for all players using a gamepad/controller. This is not only
		used for console players but also other platforms where it's possible to use
		a gamepad/controller.
	.. attribute:: TOUCH

		Input type used for all players using a touch display as controls. This is not
		only used for mobile players but also other platforms where it's possible to
		use a touch display as controls.

.. class:: Region

	An enumeration for all currently available Fortnite regions.

	.. attribute:: NAEAST

		The North America East region.
	.. attribute:: NAWEST

		The North America West region.
	.. attribute:: EUROPE

		The Europe region.
	.. attribute:: BRAZIL

		The Brazil region.
	.. attribute:: OCEANIA

		The Oceania region.
	.. attribute:: ASIA

		The Asia region.
	.. attribute:: MIDDLEEAST

		The Middle East region.

.. class:: Platform

	An enumeration for all currently available platforms.

	.. attribute:: WINDOWS
	.. attribute:: MAC
	.. attribute:: PLAYSTATION
	.. attribute:: XBOX
	.. attribute:: SWITCH
	.. attribute:: IOS
	.. attribute:: ANDROID

.. class:: ReadyState

	An enumeration for the available ready states.

	.. attribute:: READY
	.. attribute:: NOT_READY
	.. attribute:: SITTING_OUT


Event Reference
---------------

Events can be registered by the ``@client.event`` decorator. You do not need 
this decorator if you are in a subclass of :class:`Client`.

.. warning::

    All events must be registered as coroutines!

.. function:: event_ready()

    This event is called when the client has been successfully established and connected to all services.

	.. warning::

        This event is not called when the client starts in :class:`Client.logout()`.

.. function:: event_logout()

	This event is called when the client is beginning to log out. 

	.. warning::

        This event is not called when the client logs out in :class:`Client.logout()`.

	.. note::

		This event behaves differently from the other events. The logout of the account waits until the event handlers for this event is finished processing. This makes it so you are able to do heavy and/or time consuming operations before the client fully logs out. This unfortunately also means that this event is not compatible with :meth:`Client.wait_for()`.

.. function:: event_restart()

	This event is called when the client has successfully restarted.
	
.. function:: event_device_auth_generate(details, email)

	This event is called whenever new device authentication details are generated.

	:param details: A dictionary containing the keys ``device_id``, ``account_id`` and ``secret``.
	:type details: :class:`dict`
	:param email: Email of the account that just generated new device auth details.
	:type email: :class:`str`

.. function:: event_auth_refresh()

	This event is called when the clients authentication has been refreshed.

.. function:: event_friend_message(message)

    This event is called when :class:`ClientUser` receives a private message.
    
    :param message: Message object.
    :type message: :class:`FriendMessage`

.. function:: event_party_message(message)
	
	This event is called when :class:`ClientUser`'s party receives a message.
	
	:param message: Message object.
	:type message: :class:`PartyMessage`

.. function:: event_friend_add(friend)

	This event is called when a friend has been added.
	
	.. note::
		
		This event is called regardless of the direction. That means it will get called even if the client were to be the one to accept the user.
	
	:param friend: Friend that has been added.
	:type friend: :class:`Friend`

.. function:: event_friend_remove(friend)

	This event is called when a friend has been removed from the friendlist.
	
	.. note::
		
		This event is called regardless of the direction. That means it will get called even if the client were to be the one to remove the friend.
	
	:param friend: Friend that was removed.
	:type friend: :class:`Friend`

.. function:: event_friend_request(request)

	This event is called when the client receives a friend request.
	
	:param request: Request object.
	:type request: :class:`PendingFriend`

.. function:: event_friend_request_decline(friend)

	This event is called when a friend request is declined.

	:param request: Request object.
	:type request: :class:`PendingFriend`

.. function:: event_friend_request_abort(friend)

	This event is called when a friend request is aborted. Aborted means that the friend request was deleted before the receiving user managed to accept it.

	:param request: Request object.
	:type request: :class:`PendingFriend`

.. function:: event_friend_presence(presence)

	This event is valled when the client receives a presence from a friend.
	Presence is received when a user logs into fortnite, closes fortnite or
	when an user does an action when logged in e.g. joins into a game or joins
	a party.

	:param presence: Presence object.
	:type presence:	:class:`Presence`

.. function:: event_party_invite(invitation)

	This event is called when a party invitation is received.
	
	:param invitation: Invitation object.
	:type invitation: :class:`PartyInvitation`

.. function:: event_party_member_expire(member)

	This event is called when a partymember expires.
	
	:param member: Expired member.
	:type member: :class:`PartyMember`
	
.. function:: event_party_member_promote(old_leader, new_leader)

	This event is called when a new partyleader has been promoted.
	
	:param old_leader: Member that was previously leader.
	:type old_leader: :class:`PartyMember`
	:param new_leader: Member that was promoted.
	:type new_leader: :class:`PartyMember`
	
.. function:: event_party_member_kick(member)

	This event is called when a member has been kicked from the party.
	
	:param member: The member that was kicked.
	:type member: :class:`PartyMember`

.. function:: event_party_member_disconnect(member)

	This event is called when a member disconnects from the party.

	:param member: The member that disconnected.
	:type member: :class:`PartyMember`

.. function:: event_party_update(party)

	This event is called when :class:`ClientUser`'s partymeta is updated. An example of when this is called is when a new custom key has been set.

	:param party: The party that was updated.
	:type party: :class:`Party`

.. function:: event_party_member_update(member)

	This event is called when the meta of a member of :class:`ClientUser`'s party is updated. An example of when this might get called is when a member changes outfit.

	:param member: The member whos meta was updated.
	:type member: :class:`PartyMember`

.. function:: event_party_member_join(member)

	This event is called when a new member has joined :class:`ClientUser`'s party.

	:param member: The member who joined.
	:type member: :class:`PartyMember`

.. function:: event_party_member_leave(member)

	This event is called when a member leaves the party.
	
	:param member: The member who left the party.
	:type member: :class:`PartyMember`

.. function:: event_party_member_confirm(confirmation)

	This event is called when a member asks to join the party.

	.. warning::

		This event is automatically handled by the client which automatically always accepts the user. If you have this event referenced in your code the client won't automatically handle it anymore and you must handle it youself. 
	
	:param confirmation: Confirmation object with accessible confirmation methods.
	:type confirmation: :class:`PartyJoinConfirmation`

.. function:: event_party_member_chatban(member, reason)

	This event is called whenever a member of the party has been banned from the party chat.

	:param member: The member that was banned.
	:type member: :class:`PartyMember`
	:param reason: The reason for the ban if available.
	:type reason: Optional[:class:`str`]

.. function:: event_party_invite_cancel()

	This event is called when an invite has been cancelled.

.. function:: event_party_invite_decline()

	This event is called when an invite has been declined.

.. function:: event_party_playlist_change(party, before, after)

	This event is called when the playlist data has been changed.

	:param party: The party that changed.
	:type party: :class:`ClientParty`
	:param before: The previous playlist data. Same structure as .
	:type before: :class:`tuple`
	:param after: The current playlist data. Same structure as .
	:type after: :class:`tuple`

.. function:: event_party_squad_fill_change(party, before, after)

	This event is called when squad fill has been changed.

	:param party: The party that changed.
	:type party: :class:`ClientParty`
	:param before: The previous squad fill value.
	:type before: :class:`bool`
	:param after: The current squad fill value.
	:type after: :class:`bool`

.. function:: event_party_privacy_change(party, before, after)

	This event is called when the party privacy has been changed.

	:param party: The party that changed.
	:type party: :class:`ClientParty`
	:param before: The previous party privacy.
	:type before: :class:`Privacy`
	:param after: The current party privacy.
	:type after: :class:`Privacy`

.. function:: event_party_member_ready_change(member, before, after)

	This event is called when a members ready state has changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous ready state.
	:type before: :class:`ReadyState`
	:param after: The current ready status.
	:type after: :class:`ReadyState`

.. function:: event_party_member_input_change(member, before, after)

	This event is called when a members input has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous input.
	:type before: :class:`str`
	:param after: The current input.
	:type after: :class:`str`

.. function:: event_party_member_assisted_challenge_change(member, before, after)

	This event is called when a members assisted challenge has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous assisted challenge. ``None`` if no assisted challenge was previously set.
	:type before: :class:`str`
	:param after: The current assisted challenge. ``None`` if the assisted challenge was removed.
	:type after: :class:`str`

.. function:: event_party_member_outfit_change(member, before, after)

	This event is called when a members outfit has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous outfit cid.
	:type before: :class:`str`
	:param after: The current outfit cid.
	:type after: :class:`str`

.. function:: event_party_member_backpack_change(member, before, after)

	This event is called when a members backpack has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous backpack bid.
	:type before: :class:`str`
	:param after: The current backpack bid.
	:type after: :class:`str`

.. function:: event_party_member_pet_change(member, before, after)

	This event is called when a members pet has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous pet id.
	:type before: :class:`str`
	:param after: The current pet id.
	:type after: :class:`str`

.. function:: event_party_member_pickaxe_change(member, before, after)

	This event is called when a members pickaxe has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous pickaxe pid.
	:type before: :class:`str`
	:param after: The current pickaxe pid.
	:type after: :class:`str`

.. function:: event_party_member_contrail_change(member, before, after)

	This event is called when a members contrail has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous contrail id.
	:type before: :class:`str`
	:param after: The current contrail id.
	:type after: :class:`str`

.. function:: event_party_member_emote_change(member, before, after)

	This event is called when a members emote has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous emote eid. ``None`` if no emote was currently playing.
	:type before: :class:`str`
	:param after: The current emote eid. ``None`` if the emote was stopped.
	:type after: :class:`str`

.. function:: event_party_member_emoji_change(member, before, after)

	This event is called when a members emoji has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous emoji id. ``None`` if no emoji was currently playing.
	:type before: :class:`str`
	:param after: The current emoji id. ``None`` if the emoji was stopped.
	:type after: :class:`str`

.. function:: event_party_member_banner_change(member, before, after)

	This event is called when a members banner has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous banner data. Same structure as :attr:`PartyMember.banner`.
	:type before: :class:`tuple`
	:param after: The current banner data. Same structure as :attr:`PartyMember.banner`.
	:type after: :class:`tuple`

.. function:: event_party_member_battlepass_info_change(member, before, after)

	This event is called when a members battlepass info has been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous battlepass data. Same structure as :attr:`PartyMember.battlepass_info`.
	:type before: :class:`tuple`
	:param after: The current battlepass data. Same structure as :attr:`PartyMember.battlepass_info`.
	:type after: :class:`tuple`

.. function:: event_party_member_outfit_variants_change(member, before, after)

	This event is called when a members outfit variants been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous outfit variants. Same structure as :attr:`PartyMember.outfit_variants`.
	:type before: :class:`list`
	:param after: The current outfit variants. Same structure as :attr:`PartyMember.outfit_variants`.
	:type after: :class:`list`

.. function:: event_party_member_backpack_variants_change(member, before, after)

	This event is called when a members backpack variants been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous backpack variants. Same structure as :attr:`PartyMember.backpack_variants`.
	:type before: :class:`list`
	:param after: The current backpack variants. Same structure as :attr:`PartyMember.backpack_variants`.
	:type after: :class:`list`

.. function:: event_party_member_pickaxe_variants_change(member, before, after)

	This event is called when a members pickaxe variants been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous pickaxe variants. Same structure as :attr:`PartyMember.pickaxe_variants`.
	:type before: :class:`list`
	:param after: The current pickaxe variants. Same structure as :attr:`PartyMember.pickaxe_variants`.
	:type after: :class:`list`

.. function:: event_party_member_contrail_variants_change(member, before, after)

	This event is called when a members contrail variants been changed.

	:param member: The member that changed.
	:type member: :class:`PartyMember`
	:param before: The previous contrail variants. Same structure as :attr:`PartyMember.contrail_variants`.
	:type before: :class:`list`
	:param after: The current contrail variants. Same structure as :attr:`PartyMember.contrail_variants`.
	:type after: :class:`list`


Stats Reference
---------------

Gamemode names
~~~~~~~~~~~~~~

Since stats received from Fortnite's services changes all the time by adding 
new gamemodes and such, none of the gamemode names have been changed from the 
original response gotten from the request. Therefore, if you want to access a 
users solo stats, you must use the internal name for the solo gamemode:
``defaultsolo``.

There is no good, easy way of retrieving all these internal names. So for now
the best way you can do this is by fetching stats from someone that has played
a lot of different gamemode e.g. the user ``Dark`` (more known as Dakotaz) and
just write the gamemode names down.

Stats
~~~~~~~~~~~~~~~

**Default Solos Gamemode (defaultsolo)**

.. code-block:: python3

	{
	  'wins': int,
	  'placetop10': int,
	  'placetop25': int,
	  'kills': int,
	  'score': int,
	  'playersoutlives': int,
	  'minutesplayed': int,
	  'matchesplayed': int,
	  'lastmodified': datetime.datetime,
	}


**Default Duos Gamemode (defaultduo)**

.. code-block:: python3

	{
	  'wins': int,
	  'placetop5': int,
	  'placetop12': int,
	  'kills': int,
	  'score': int,
	  'playersoutlives': int,
	  'minutesplayed': int,
	  'matchesplayed': int,
	  'lastmodified': datetime.datetime,
	}

**Default Trios Gamemode (trios)**

.. code-block:: python3

	{
	  'wins': int,
	  'kills': int,
	  'score': int,
	  'playersoutlives': int,
	  'minutesplayed': int,
      'matchesplayed': int,
	  'lastmodified': datetime.datetime,
	}

**Default Squads Gamemode (defaultsquads)**

.. code-block:: python3

	{
	  'wins': int,
	  'placetop3': int,
	  'placetop6': int,
	  'kills': int,
	  'score': int,
	  'playersoutlives': int,
	  'minutesplayed': int,
	  'matchesplayed': int,
	  'lastmodified': datetime.datetime,
	}


Fortnite Models
---------------

.. danger::

	The classes below should never be created by users. These are classed representing data received from fortnite's services.

ClientUser
~~~~~~~~~~

.. autoclass:: ClientUser()
	:members:
	:inherited-members:

ExternalAuth
~~~~~~~~~~~~

.. autoclass:: ExternalAuth()
	:members:

User
~~~~

.. autoclass:: User()
	:members:
	:inherited-members:

BlockedUser
~~~~~~~~~~~

.. autoclass:: BlockedUser()
	:members:
	:inherited-members:

Friend
~~~~~~

.. autoclass:: Friend()
	:members:
	:inherited-members:

PendingFriend
~~~~~~~~~~~~~

.. autoclass:: PendingFriend()
	:members:
	:inherited-members:

FriendMessage
~~~~~~~~~~~~~

.. autoclass:: FriendMessage()
	:members:
	:inherited-members:

PartyMessage
~~~~~~~~~~~~

.. autoclass:: PartyMessage()
	:members:
	:inherited-members:

PartyMember
~~~~~~~~~~~

.. autoclass:: PartyMember()
	:members:
	:inherited-members:

ClientPartyMember
~~~~~~~~~~~~~~~~~

.. autoclass:: ClientPartyMember()
	:members:
	:inherited-members:

Party
~~~~~

.. autoclass:: Party()
	:members:
	:inherited-members:

ClientParty
~~~~~~~~~~~

.. autoclass:: ClientParty()
	:members:
	:inherited-members:

PartyInvitation
~~~~~~~~~~~~~~~

.. autoclass:: PartyInvitation()
	:members:

PartyJoinConfirmation
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: PartyJoinConfirmation()
	:members:

Presence
~~~~~~~~

.. autoclass:: Presence()
	:members:

PresenceParty
~~~~~~~~~~~~~

.. autoclass:: PresenceParty()
	:members:

PresenceGameplayStats
~~~~~~~~~~~~~~~~~~~~~

.. autoclass:: PresenceGameplayStats()
	:members:

StatsV2
~~~~~~~

.. autoclass:: StatsV2()
	:members:

BattleRoyaleNewsPost
~~~~~~~~~~~~~~~~~~~~

.. autoclass:: BattleRoyaleNewsPost()
	:members:

Store
~~~~~

.. autoclass:: Store()
	:members:

FeaturedStoreItem
~~~~~~~~~~~~~~~~~

.. autoclass:: FeaturedStoreItem()
	:members:
	:inherited-members:

DailyStoreItem
~~~~~~~~~~~~~~

.. autoclass:: DailyStoreItem()
	:members:
	:inherited-members:

Playlist
~~~~~~~~

.. autoclass:: Playlist()
	:members:


Exceptions
----------

.. autoexception:: FortniteException

.. autoexception:: AuthException

.. autoexception:: HTTPException

.. autoexception:: ValidationFailure

.. autoexception:: PurchaseException

.. autoexception:: EventError

.. autoexception:: XMPPError

.. autoexception:: PartyError

.. autoexception:: Forbidden

.. autoexception:: NotFound

