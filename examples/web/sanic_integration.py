"""This example showcases how to use fortnitepy with the asynchronous
web framework sanic. If captcha is enforced for the accounts, you will
only have to enter the authorization code the first time you run this script.

NOTE: This example uses AdvancedAuth and stores the details in a file.
It is important that this file is moved whenever the script itself is moved
because it relies on the stored details. However, if the file is nowhere to
be found, it will simply use email and password or prompt you to enter a
new authorization code to generate a new file.
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
        prompt_authorization_code=True,
        delete_existing_device_auths=True,
        **device_auth_details
    )
)

app = sanic.Sanic("bot")
server = None


@bot.event
async def event_device_auth_generate(details, email):
    store_device_auth_details(email, details)

@app.route('/members')
async def get_partymembers_handler(request):
    """
    Handles the HTTP GET request to retrieve party members.
    
    Parameters:
    - request: The request object containing HTTP request data.
    
    Returns:
    - A JSON response containing a list of party member IDs.
    
    Notes:
    - This function assumes the existence of the Sanic application ('app') and the 'bot' object with a 'party' attribute,
      representing the party system.
    - The function fetches member IDs from the 'bot.party.members' attribute and returns them as a JSON response.
    """
    members = [member.id for member in bot.party.members]
    return sanic.response.json(members)

@app.route('/friends', methods=['GET'])
    async def get_friends_handler(request):
    """
    Handles the HTTP GET request to retrieve friends.
    
    Parameters:
    - request: The request object containing HTTP request data.
    
    Returns:
    - A JSON response containing a list of friend IDs.
    
    Notes:
    - This function assumes the existence of the Sanic application ('app') and the 'bot' object with a 'friends' attribute,
      representing the friends system.
    - The function fetches friend IDs from the 'bot.friends' attribute and returns them as a JSON response.
    """
    friends = [friend.id for friend in bot.friends]
    return sanic.response.json(friends)

@bot.event
async def event_ready():
    global server

    print('----------------')
    print('Bot ready as')
    print(bot.user.display_name)
    print(bot.user.id)
    print('----------------')

    coro = app.create_server(
        host='0.0.0.0',
        port=8000,
        return_asyncio_server=True,
    )
    server = await coro

@bot.event
async def event_before_close():
    global server

    if server:
        await server.close()

@bot.event
async def event_friend_request(request):
    await request.accept()

@bot.command()
async def hello(ctx):
    await ctx.send('Hello!')

bot.run()
