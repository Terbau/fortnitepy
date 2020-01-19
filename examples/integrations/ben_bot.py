import aiohttp
import fortnitepy
import asyncio

BEN_BOT_BASE = 'http://benbotfn.tk:8080'


class MyClient(fortnitepy.Client):
    def __init__(self):
        super().__init__(
            email='',
            password=''
        )
        self.session_event = asyncio.Event(loop=self.loop)

    async def event_ready(self):
        print('Client is ready as {0.user.display_name}.'.format(self))
        self.session = aiohttp.ClientSession(loop=self.loop)
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

            await self.user.party.me.set_outfit(
                asset=cid
            )

        # runs the emote specified for 10 seconds
        elif command == '!setemote':
            data = await self.fetch_cosmetic_id(' '.join(args))
            eid = data.get('id')
            if eid is None or data['type'] != 'Emote':
                return await message.reply('Could not find the requested emote.')

            await self.user.party.me.set_emote(
                asset=eid,
                run_for=10
            )

c = MyClient()
c.run()
