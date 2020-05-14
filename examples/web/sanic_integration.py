"""This example showcases how to use fortnitepy within a subclass. If captcha
is enforced for the accounts, you will only have to enter the exchange code
the first time you run this script.

NOTE: This example uses AdvancedAuth and stores the details in a file.
It is important that this file is moved whenever the script itself is moved
because it relies on the stored details. However, if the file is nowhere to
be found, it will simply use email and password or prompt you to enter a
new exchange code to generate a new file.
"""

import fortnitepy
import json
import os
import sanic

from fortnitepy.ext import commands


email = 'email@email.com'
password = 'password1'
filename = 'device_auths.json'
description = 'My awesome fortnite bot / sanic app!'

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
bot = commands.Bot(
    command_prefix='!',
    auth=fortnitepy.AdvancedAuth(
        email=email,
        password=password,
        prompt_exchange_code=True,
        delete_existing_device_auths=True,
        **device_auth_details
    )
)

sanic_app = sanic.Sanic(__name__)
server = None


@bot.event
async def event_device_auth_generate(details, email):
    store_device_auth_details(email, details)

@sanic_app.route('/friends', methods=['GET'])
async def get_friends_handler(request):
    friends = [friend.id for friend in bot.friends.values()]
    return sanic.response.json(friends)

@bot.event
async def event_ready():
    global server

    print('----------------')
    print('Bot ready as')
    print(bot.user.display_name)
    print(bot.user.id)
    print('----------------')

    coro = sanic_app.create_server(
        host='0.0.0.0',
        port=8000,
        return_asyncio_server=True,
    )
    server = await coro

@bot.event
async def event_close():
    global server

    if server is not None:
        await server.close()

@bot.event
async def event_friend_request(request):
    await request.accept()

@bot.command()
async def hello(ctx):
    await ctx.send('Hello!')

bot.run()
