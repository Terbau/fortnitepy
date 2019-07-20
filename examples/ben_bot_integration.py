import aiohttp
import fortnitepy

class MyClient(fortnitepy.Client):

    BEN_BOT_BASE = 'http://benbotfn.tk:8080/api/cosmetics/search'

    def __init__(self):
        super().__init__(
            email='',
            password=''
        )
        self.session = aiohttp.ClientSession(loop=self.loop)

    async def event_ready(self):
        print('Client is ready as {0.user.display_name}.'.format(self))

    async def fetch_cosmetic_id(self, display_name):
        async with self.session.get(self.BEN_BOT_BASE, params={'displayName': display_name}) as r:
            data = await r.json()
            return data.get('id')

    async def event_party_message(self, message):
        split = message.content.split()
        command = split[0].lower()
        args = split[1:]

        # sets the current outfit
        if command == '!setoutfit':
            cid = await self.fetch_cosmetic_id(' '.join(args))
            if cid is None:
                return await message.reply('Could not find the requested outfit.')

            await self.user.party.me.set_outfit(
                asset=cid
            )

        # sets the current emote (since emotes are infinite)
        elif command == '!setemote':
            eid = await self.fetch_cosmetic_id(' '.join(args))
            if eid is None:
                return await message.reply('Could not find the requested emote.')

            await self.user.party.me.set_emote(
                asset=eid
            )

        # clears/stops the current emote
        elif command == '!clearemote':
            await self.user.party.me.clear_emote()

c = MyClient()
c.run()
