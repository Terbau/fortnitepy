"""This example showcases how to use fortnitepy. If captcha is enforced for
the account, you will only have to enter the exchange code the first time
you run this script.

NOTE: This example uses AdvancedAuth and stores the details in a file.
It is important that this file is moved whenever the script itself is moved
because it relies on the stored details. However, if the file is nowhere to
be found, it will simply use email and password or prompt you to enter a
new exchange code to generate a new file.
"""

import fortnitepy
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


device_auth_details = get_device_auth_details().get(email, {})
client = fortnitepy.Client(
    auth=fortnitepy.AdvancedAuth(
        email=email,
        password=password,
        prompt_exchange_code=True,
        delete_existing_device_auths=True,
        **device_auth_details
    )
)

@client.event
async def event_device_auth_generate(details, email):
    store_device_auth_details(email, details)

@client.event
async def event_ready():
    print('----------------')
    print('Client ready as')
    print(client.user.display_name)
    print(client.user.id)
    print('----------------')

@client.event
async def event_friend_request(request):
    await request.accept()

@client.event
async def event_friend_message(message):
    print('Received message from {0.author.display_name} | Content: "{0.content}"'.format(message))
    await message.reply('Thanks for your message!')

client.run()