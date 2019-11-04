import aiohttp
import fortnitepy
import asyncio
import random

class MyClient(fortnitepy.Client):
    TERAX_API_BASE = 'https://fnserver.terax235.com/'

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

    async def fetch_cosmetic(self, type, query):
        async with self.session.get(
            self.TERAX_API_BASE + '/api/v1.2/cosmetics/search',
            headers={'type': type, 'query': query},
        ) as r:
            if r.status == 404:
                return None
            return await r.json()

    def build_random_variants(self, type, data):
        types = {
            'skin': 'AthenaCharacter',
            'backpack': 'AthenaBackpack',
            'pickaxe': 'AthenaPickaxe'
        }

        variants = []
        for variant in data:
            variants.append({
                'item': types[type],
                'channel': variant['channel'],
                'variant': random.choice(variant['tags'])['tag']
            })

        return variants

    async def event_party_message(self, message):
        # wait until session is set
        await self.session_event.wait()

        split = message.content.split()
        command = split[0].lower()
        args = split[1:]

        # sets the current outfit
        if command == '!setoutfit':
            data = await self.fetch_cosmetic('skin', ' '.join(args))
            if data is None:
                return await message.reply('Could not find the requested outfit.')

            outfit_data = data['data']
            await self.user.party.me.set_outfit(
                asset=outfit_data['id'],
                variants=self.build_random_variants('skin', outfit_data['variants'])
            )

        # sets the current emote (emotes are infinite)
        elif command == '!setemote':
            data = await self.fetch_cosmetic('emote', ' '.join(args))
            if data is None:
                return await message.reply('Could not find the requested emote.')

            emote_data = data['data']
            await self.user.party.me.set_emote(
                asset=emote_data['id']
            )

        # clears/stops the current emote
        elif command == '!clearemote':
            await self.user.party.me.clear_emote()


c = MyClient()
c.run()
