 # fortnitepy

[![Supported py versions](https://img.shields.io/pypi/pyversions/fortnitepy.svg)](https://pypi.org/project/fortnitepy/)
[![Current pypi version](https://img.shields.io/pypi/v/fortnitepy.svg)](https://pypi.org/project/fortnitepy/)

Asynchronous library for interacting with Fortnite and EpicGames' API and XMPP services.

**Note:** This library is still under developement so breaking changes might happen at any time.

**Some key features:**
- Full support for Friends.
- Support for XMPP events including friend and party messages + many more.
- Support for Parties.
- Support for Battle Royale stats.

# Documentation
https://fortnitepy.readthedocs.io/en/latest/

# Installing
```
# windows
py -3 -m pip install -U fortnitepy

# linux
python3 -m pip install -U fortnitepy
```

# Basic usage
```py
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
    print('Client ready as {0.user.display_name}'.format(client))


@client.event
async def event_friend_request(request):
    await request.accept()


@client.event
async def event_friend_message(message):
    print('Received message from {0.author.display_name} | Content: "{0.content}"'.format(message))
    await message.reply('Thanks for your message!')

client.run()
```

# Credit
Thanks to [Kysune](https://github.com/SzymonLisowiec), [iXyles](https://github.com/iXyles), [Vrekt](https://github.com/Vrekt) and [amrsatrio](https://github.com/Amrsatrio) for ideas and/or work that this library is built upon.

Also thanks to [discord.py](https:/github.com/Rapptz/discord.py) for much inspiration code-wise.

# Need help?
If you need more help feel free to join this [discord server](https://discord.gg/rnk869s).
