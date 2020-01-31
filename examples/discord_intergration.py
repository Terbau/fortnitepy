"""This example makes use of discord integration with fortnitepy. If captcha is enforced for
the accounts, you will only have to enter the exchange code the first time
you run this script.

NOTE: This example uses AdvancedAuth and stores the details in a file.
It is important that this file is moved whenever the script itself is moved
because it relies on the stored details. However, if the file is nowhere to
be found, it will simply use email and password or prompt you to enter a
new exchange code to generate a new file.
"""

import fortnitepy
from discord.ext import commands
import json
import os

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

discord_bot = commands.Bot(
    command_prefix='!',
    description='My discord + fortnite bot!',
    case_insensitive=True
)

device_auth_details = get_device_auth_details().get(email, {})
fortnite_client = fortnitepy.Client(
    auth=fortnitepy.AdvancedAuth(
        email=email,
        password=password,
        prompt_exchange_code=True,
        delete_existing_device_auths=True,
        **device_auth_details
    ),
    loop=discord_bot.loop
)

@discord_bot.event
async def on_ready():
    print('Discord bot ready')
    await fortnite_client.start()

@fortnite_client.event
async def event_device_auth_generate(details, email):
    store_device_auth_details(email, details)
    
@fortnite_client.event
async def event_ready():
    print('Fortnite client ready')

@discord_bot.event
async def on_message(message):
    print('Received message from {0.author.display_name} | Content "{0.content}"'.format(message))

@fortnite_client.event
async def event_friend_message(message):
    print('Received message from {0.author.display_name} | Content "{0.content}"'.format(message))

# discord command
@commands.command()
async def mycommand(ctx):
    await ctx.send('Hello there!')

discord_bot.run('DISCORD TOKEN')
