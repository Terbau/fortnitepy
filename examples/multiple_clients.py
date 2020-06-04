"""This example makes use of multiple accounts. If captcha is enforced for
the accounts, you will only have to enter the authorization code the first time
you run this script.

NOTE: This example uses AdvancedAuth and stores the details in a file.
It is important that this file is moved whenever the script itself is moved
because it relies on the stored details. However, if the file is nowhere to
be found, it will simply use email and password or prompt you to enter a
new authorization code to generate a new file.
"""

import fortnitepy
import asyncio
import functools
import os
import json

instances = {}
filename = 'device_auths.json'
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

def get_device_auth_details():
    if os.path.isfile(filename):
        with open(filename, 'r') as fp:
            return json.load(fp)
    return {}

def store_device_auth_details(email, details):
    existing = get_device_auth_details()
    existing[email] = details

    with open(filename, 'w') as fp:
        json.dump(existing, fp)

async def event_sub_device_auth_generate(details, email):
    store_device_auth_details(email, details)

async def event_sub_ready(client):
    instances[client.user.id] = client
    print('{0.user.display_name} ready.'.format(client))

async def event_sub_friend_request(request):
    print('{0.client.user.display_name} received a friend request.'.format(request))
    await request.accept()

async def event_sub_party_member_join(member):
    print("{0.display_name} joined {0.client.user.display_name}'s party.".format(member))            


clients = []
device_auths = get_device_auth_details()
for email, password in credentials.items():
    authentication = fortnitepy.AdvancedAuth(
        email=email,
        password=password,
        prompt_authorization_code=True,
        delete_existing_device_auths=True,
        **device_auths.get(email, {})
    )

    client = fortnitepy.Client(
        auth=authentication,
        default_party_member_config=fortnitepy.DefaultPartyMemberConfig(
            meta=(
                functools.partial(fortnitepy.ClientPartyMember.set_outfit, 'CID_175_Athena_Commando_M_Celestial'), # galaxy skin
            )
        )
    )

    # register events here
    client.add_event_handler('device_auth_generate', event_sub_device_auth_generate)
    client.add_event_handler('friend_request', event_sub_friend_request)
    client.add_event_handler('party_member_join', event_sub_party_member_join)

    clients.append(client)

fortnitepy.run_multiple(
    clients,
    ready_callback=event_sub_ready,
    all_ready_callback=lambda: print('All clients ready')
)
