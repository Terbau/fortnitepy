.. currentmodule:: fortnitepy

API Reference
=============

Client
------

.. autoclass:: Client
    :members:

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

.. class:: V2Inputs

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

.. class:: Regions

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
	.. attribute:: NA

		The North America region.
	.. attribute:: CHINA
		
		The China region.


Event Reference
---------------

Events can be registered by the ``@client.event`` decorator. You do not need 
this decorator if you are in a subclass of :class:`Client`.

.. warning::

    All event must be registered as coroutines!

.. function:: event_ready()

    This event is called when the client has been successfully established and connected to all services.

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
	
.. function:: event_party_member_promote(member)

	This event is called when a new partyleader has been promoted.
	
	:param member: Member that was promoted.
	:type member: :class:`PartyMember`
	
.. function:: event_party_member_kicked(member)

	This event is called when a member has been kicked from the party.
	
	:param member: The member that was kicked.
	:type member: :class:`PartyMember`

.. function:: event_party_member_disconnected(member)

	This event is called when a member disconnects from the party.

	:param member: The member that disconnected.
	:type member: :class:`PartyMember`

.. function:: event_party_updated(party)

	This event is called when :class:`ClientUser`'s partymeta is updated. An example of when this is called is when a new custom key has been set.

	:param party: The party that was updated.
	:type party: :class:`Party`

.. function:: event_party_member_updated(member)

	This event is called when the meta of a member of :class:`ClientUser`'s party is updated. An example of when this might get called is when a member changes outfit.

	:param member: The member whos meta was updated.
	:type member: :class:`PartyMember`

.. function:: event_party_member_join(member)

	This event is called when a new member has joined :class:`ClientUser`'s party.

	:param member: The member who joined.
	:type member: :class:`PartyMember`

.. function:: event_party_member_confirmation(confirmation)

	This event is called when a member asks to join the party.

	.. warning::

		This event is automatically handled by the client which automatically always accepts the user. If you have this event referenced in your code the client won't automatically handle it anymore and you must handle it youself. 
	
	:param confirmation: Confirmation object with accessible confirmation methods.
	:type confirmation: :class:`PartyJoinConfirmation`

.. function:: event_party_invite_cancelled()

	This event is called when an invite has been cancelled.

.. function:: event_party_invite_declined()

	This event is called when an invite has been declined.


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

User
~~~~

.. autoclass:: User()
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

Party
~~~~~

.. autoclass:: Party()
	:members:

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

.. autoexception:: EventError

.. autoexception:: XMPPError

.. autoexception:: PartyError

.. autoexception:: PartyPermissionError



