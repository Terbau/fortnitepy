"""This example makes use of one main account and multiple sub-accounts.
If captcha is enforced for the accounts, you will only have to enter the
authorization code the first time you run this script.

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

filename = 'device_auths.json'

# main account credentials
email = ''
password = ''

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

class MyClient(fortnitepy.Client):
    def __init__(self):
        device_auths = get_device_auth_details()
        super().__init__(
            auth=fortnitepy.AdvancedAuth(
                email=email,
                password=password,
                authorization=True,
                delete_existing_device_auths=True,
                **device_auths.get(email, {})
            )
        )
        self.instances = {}

    async def event_sub_device_auth_generate(self, details, email):
        store_device_auth_details(email, details)

    async def event_sub_ready(self, client):
        self.instances[client.user.id] = client
        print('Sub client {0.user.display_name} ready.'.format(client))

    async def event_sub_friend_request(self, request):
        print('Sub client {0.client.user.display_name} received a friend request.'.format(request))
        await request.accept()

    async def event_sub_party_member_join(self, member):
        print("{0.display_name} joined sub client {0.client.user.display_name}'s party.".format(member))            

    async def event_device_auth_generate(self, details, email):
        store_device_auth_details(email, details)

    async def event_ready(self):
        print('Main client ready. Launching sub-accounts...')

        clients = []
        device_auths = get_device_auth_details()
        for email, password in credentials.items():
            client = fortnitepy.Client(
                auth=fortnitepy.AdvancedAuth(
                    email=email,
                    password=password,
                    prompt_authorization_code=True,
                    delete_existing_device_auths=True,
                    **device_auths.get(email, {})
                ),
                default_party_member_config=fortnitepy.DefaultPartyMemberConfig(
                    meta=(
                        functools.partial(fortnitepy.ClientPartyMember.set_outfit, 'CID_175_Athena_Commando_M_Celestial'), # galaxy skin
                    )
                )
            )

            # register events here
            client.add_event_handler('device_auth_generate', self.event_sub_device_auth_generate)
            client.add_event_handler('friend_request', self.event_sub_friend_request)
            client.add_event_handler('party_member_join', self.event_sub_party_member_join)

            clients.append(client)

        try:
            await fortnitepy.start_multiple(
                clients,
                ready_callback=self.event_sub_ready,
                all_ready_callback=lambda: print('All sub clients ready')
            )
        except fortnitepy.AuthException:
            print('An error occured while starting sub clients. Closing gracefully.')
            await self.close()

    async def event_close(self):
        await fortnitepy.close_multiple(list(self.instances.values()))
        print('Successfully logged out of all sub accounts.')

    async def event_friend_request(self, request):
        await request.accept()

client = MyClient()
client.run()
