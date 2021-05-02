import aiohttp
import fortnitepy
import asyncio
import random
import json
import os

FORTNITE_API_BASE = 'https://fortnite-api.com'
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

    async def event_friend_request(self, request):
        await request.accept()

    async def fetch_cosmetic(self, type_, name):
        async with self.session.get(
            FORTNITE_API_BASE + '/cosmetics/br/search',
            params={'type': type_, 'name': name}
        ) as r:
            if r.status == 404:
                return None
            return await r.json()

    def build_random_variants(self, type_, data):
        types = {
            'outfit': 'AthenaCharacter',
            'backpack': 'AthenaBackpack',
            'pickaxe': 'AthenaPickaxe'
        }

        variants = []
        for variant in data:
            variants.append({
                'item': types[type_],
                'channel': variant['channel'],
                'variant': random.choice(variant['options'])['tag']
            })

        return variants

    async def event_party_message(self, message):
        # wait until session is set
        await self.session_event.wait()

        split = message.content.split()
        command = split[0].lower()
        args = split[1:]
        joined_args = ' '.join(args)

        # sets the current outfit
        if command == '!setoutfit':
            data = await self.fetch_cosmetic('outfit', joined_args)
            if data is None:
                return await message.reply('Could not find the requested outfit.')

            outfit_data = data['data']
            await self.party.me.set_outfit(
                asset=outfit_data['id'],
                variants=self.build_random_variants('outfit', outfit_data.get('variants', []))
            )

        # runs the emote specified for 10 seconds
        elif command == '!setemote':
            data = await self.fetch_cosmetic('emote', joined_args)
            if data is None:
                return await message.reply('Could not find the requested emote.')

            emote_data = data['data']
            await self.party.me.set_emote(
                asset=emote_data['id'],
                run_for=10
            )


c = MyClient()
c.run()
