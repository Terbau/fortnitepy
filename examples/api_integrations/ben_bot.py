import aiohttp
import fortnitepy
import asyncio
import json
import os

BEN_BOT_BASE = 'http://benbotfn.tk:8080'
email = 'email@email.com'
password = 'password1'
filename = 'device_auths.json'

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
        device_auth_details = get_device_auth_details().get(email, {})
        super().__init__(
            auth=fortnitepy.AdvancedAuth(
                email=email,
                password=password,
                prompt_authorization_code=True,
                prompt_code_if_invalid=True,
                delete_existing_device_auths=True,
                **device_auth_details
            )
        )
        self.session_event = asyncio.Event()
        
    async def event_device_auth_generate(self, details, email):
        store_device_auth_details(email, details)

    async def event_ready(self):
        print('Client is ready as {0.user.display_name}.'.format(self))
        self.session = aiohttp.ClientSession()
        self.session_event.set()

    async def fetch_cosmetic_id(self, display_name):
        async with self.session.get(
            BEN_BOT_BASE + '/api/cosmetics/search', 
            params={'displayName': display_name}
        ) as r:
            data = await r.json()
            return data

    async def event_party_message(self, message):
        # wait until session is set
        await self.session_event.wait()

        split = message.content.split()
        command = split[0].lower()
        args = split[1:]
        joined_args = ' '.join(args)

        # sets the current outfit
        if command == '!setoutfit':
            data = await self.fetch_cosmetic_id(joined_args)
            cid = data.get('id')
            if cid is None or data['type'] != 'Outfit':
                return await message.reply('Could not find the requested outfit.')

            await self.party.me.set_outfit(
                asset=cid
            )

        # runs the emote specified for 10 seconds
        elif command == '!setemote':
            data = await self.fetch_cosmetic_id(' '.join(args))
            eid = data.get('id')
            if eid is None or data['type'] != 'Emote':
                return await message.reply('Could not find the requested emote.')

            await self.party.me.set_emote(
                asset=eid,
                run_for=10
            )

c = MyClient()
c.run()
