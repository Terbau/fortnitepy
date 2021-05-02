"""This example makes use of discord integration with fortnitepy. If captcha
is enforced for the accounts, you will only have to enter the authorization code
the first time you run this script.

NOTE: This example uses AdvancedAuth and stores the details in a file.
It is important that this file is moved whenever the script itself is moved
because it relies on the stored details. However, if the file is nowhere to
be found, it will simply use email and password or prompt you to enter a
new authorization code to generate a new file.
"""

import fortnitepy
import json
import os

from fortnitepy.ext import commands as fortnite_commands
from discord.ext import commands as discord_commands

email = 'email@email.com'
password = 'password1'
discord_bot_token = ''  # the discord bots token
filename = 'device_auths.json'
description = 'My discord + fortnite bot!'


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


device_auth_details = get_device_auth_details().get(email, {})
fortnite_bot = fortnite_commands.Bot(
    command_prefix='!',
    description=description,
    auth=fortnitepy.AdvancedAuth(
        email=email,
        password=password,
        prompt_authorization_code=True,
        prompt_code_if_invalid=True,
        delete_existing_device_auths=True,
        **device_auth_details
    )
)

discord_bot = discord_commands.Bot(
    command_prefix='!',
    description=description,
    case_insensitive=True
)


@fortnite_bot.event
async def event_ready():
    print('Fortnite bot ready')
    await discord_bot.start(discord_bot_token)

@fortnite_bot.event
async def event_device_auth_generate(details, email):
    store_device_auth_details(email, details)

@fortnite_bot.event
async def event_before_close():
    await discord_bot.close()

@discord_bot.event
async def on_ready():
    print('Discord bot ready')

@discord_bot.event
async def on_message(message):
    if message.author.bot:
        return

    print('Received discord message from {0.author.display_name} | Content "{0.content}"'.format(message))
    await discord_bot.process_commands(message)

@fortnite_bot.event
async def event_friend_message(message):
    print('Received fortnite message from {0.author.display_name} | Content "{0.content}"'.format(message))

# discord command
@discord_bot.command()
async def mydiscordcommand(ctx):
    await ctx.send('Hello there discord!')

@fortnite_bot.command()
async def myfortnitecommand(ctx):
    await ctx.send('Hello there fortnite!')

fortnite_bot.run()
