import fortnitepy
import FortniteAPIAsync # you will need to install using pip install FortniteAPIAsync

from fortnitepy.ext import commands


bot = commands.Bot(
    command_prefix='!',
    auth=fortnitepy.AuthorizationCodeAuth(
        code=input('Enter authorization code: ')
    )
)

@bot.command()
async def skin(
    ctx,
    *, 
    content: str
):
    try:
        cosmetic = await FortniteAPIAsync.get_cosmetic(
            matchMethod="contains",
            name=content,
            backendType="AthenaCharacter"
        )
        await ctx.send(f'Skin set to {cosmetic.id}.')
        print(f"Set skin to: {cosmetic.id}.")
        await client.party.me.set_outfit(asset=cosmetic.id)

    except FortniteAPIAsync.exceptions.NotFound:
        await ctx.send(f"Failed to find a skin with the name: {content}.")
        print(f"Failed to find a skin with the name: {content}.")

@bot.command()
async def emote(
    ctx,
    *, 
    content: str
):
    try:
        cosmetic = await FortniteAPIAsync.get_cosmetic(
            matchMethod="contains",
            name=content,
            backendType="AthenaDance"
        )
        await ctx.send(f'Skin set to {cosmetic.id}.')
        print(f"Set skin to: {cosmetic.id}.")
        await client.party.me.set_emote(asset=cosmetic.id)

    except FortniteAPIAsync.exceptions.NotFound:
        await ctx.send(f"Failed to find a emote with the name: {content}.")
        print(f"Failed to find a emote with the name: {content}.")


bot.run()
