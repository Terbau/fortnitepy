import aiohttp
import fortnitepy
import asyncio
import random

FORTNITE_API_BASE = 'https://fortnite-api.com'
API_KEY = '' # get your api key from https://fortnite-api.com/


class MyClient(fortnitepy.Client):
    def __init__(self):
        super().__init__(
            email='',
            password=''
        )
        self.session_event = asyncio.Event()

    async def event_ready(self):
        print('Client is ready as {0.user.display_name}.'.format(self))
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.session_event.set()

    async def event_friend_request(self, request):
        await request.accept()

    async def fetch_cosmetic(self, type_, name):
        async with self.session.get(
            FORTNITE_API_BASE + '/cosmetics/br/search',
            headers={'x-api-key': API_KEY},
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
            await self.user.party.me.set_outfit(
                asset=outfit_data['id'],
                variants=self.build_random_variants('outfit', outfit_data.get('variants', []))
            )

        # runs the emote specified for 10 seconds
        elif command == '!setemote':
            data = await self.fetch_cosmetic('emote', joined_args)
            if data is None:
                return await message.reply('Could not find the requested emote.')

            emote_data = data['data']
            await self.user.party.me.set_emote(
                asset=emote_data['id'],
                run_for=10
            )


c = MyClient()
c.run()
