"""This example makes use of one main account and multiple sub-accounts."""

import fortnitepy
import asyncio

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

class MyClient(fortnitepy.Client):
    def __init__(self):
        super().__init__(
            email="email",
            password="password"
        )
        self.instances = {}

    async def event_sub_friend_request(self, request):
        print('{0.client.user.display_name} received a friend request.'.format(request))
        await request.accept()

    async def event_sub_party_member_join(self, member):
        print("{0.display_name} joined {0.client.user.display_name}'s party.".format(member))

        if member.id == member.client.user.id:
            # set outfit to galaxy
            await member.client.user.party.me.set_outfit('CID_175_Athena_Commando_M_Celestial')
    
    async def load_sub_account(self, email, password):
        client = fortnitepy.Client(
            email=email,
            password=password,
            loop=self.loop
        )

        # register events here with Client.add_event_handler()
        client.add_event_handler('friend_request', self.event_sub_friend_request)

        self.loop.create_task(client.start())
        await client.wait_until_ready()
        self.instances[client.user.id] = client

        # add code here that should be executed once this client is ready
        print('{0.user.display_name} ready.'.format(client))

    async def event_ready(self):
        print('Main client ready. Launching sub-accounts...')

        tasks = []
        for email, password in credentials.items():
            tasks.append(self.load_sub_account(email, password))
        
        await asyncio.wait(tasks)
        print('All clients ready')

    async def event_logout(self):
        tasks = []
        for client in self.instances.values():
            tasks.append(client.logout())

        await asyncio.wait(tasks)
        print('Successfully logged out of all sub accounts.')

    async def event_friend_request(self, request):
        await request.accept()
    
client = MyClient()
client.run()

