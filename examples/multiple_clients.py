# flake8: noqa

"""This example makes use of multiple accounts."""

import fortnitepy
import asyncio
import functools

# sub-account credentials
credentials = {
    "email1": "password1",
    "email2": "password2",
    "email3": "password3",
    "email4": "password4",
    "email5": "password5",
    "email6": "password6",
    "email7": "password7",
    "email8": "password8",
    "email9": "password9",
    "email10": "password10",
}

instances = {}

async def event_sub_ready(client):
    instances[client.user.id] = client
    print('{0.user.display_name} ready.'.format(client))

async def event_sub_friend_request(request):
    print('{0.client.user.display_name} received a friend request.'.format(request))
    await request.accept()

async def event_sub_party_member_join(member):
    print("{0.display_name} joined {0.client.user.display_name}'s party.".format(member))            

clients = []
for email, password in credentials.items():
    client = fortnitepy.Client(
        email=email,
        password=password,
        default_party_member_config=(
            functools.partial(fortnitepy.ClientPartyMember.set_outfit, 'CID_175_Athena_Commando_M_Celestial'), # galaxy skin
        )
    )

    # register events here
    client.add_event_handler('friend_request', event_sub_friend_request)
    client.add_event_handler('party_member_join', event_sub_party_member_join)

    clients.append(client)

fortnitepy.run_multiple(
    clients, 
    ready_callback=event_sub_ready,
    all_ready_callback=lambda: print('All clients ready')
)
