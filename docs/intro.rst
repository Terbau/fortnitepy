Introduction
============

Installation
------------

**Fortnitepy requires Python 3.5 or higher**

**Windows**

.. code:: sh

    py -3 -m pip install fortnitepy

**Linux**

.. code:: sh

    python3 -m pip install fortnitepy

Basic usage
-----------

.. code-block:: python3

    import fortnitepy
    import json
    import os

    email = 'email@email.com'
    password = 'password1'
    filename = 'device_auths.json'

    class MyClient(fortnitepy.Client):
        def __init__(self):
            device_auth_details = self.get_device_auth_details().get(email, {})
            super().__init__(
                auth=fortnitepy.AdvancedAuth(
                    email=email,
                    password=password,
                    prompt_authorization_code=True,
                    delete_existing_device_auths=True,
                    **device_auth_details
                )
            )

        def get_device_auth_details(self):
            if os.path.isfile(filename):
                with open(filename, 'r') as fp:
                    return json.load(fp)
            return {}

        def store_device_auth_details(self, email, details):
            existing = self.get_device_auth_details()
            existing[email] = details

            with open(filename, 'w') as fp:
                json.dump(existing, fp)

        async def event_device_auth_generate(self, details, email):
            self.store_device_auth_details(email, details)

        async def event_ready(self):
            print('----------------')
            print('Client ready as')
            print(self.user.display_name)
            print(self.user.id)
            print('----------------')

        async def event_friend_request(self, request):
            await request.accept()

        async def event_friend_message(self, message):
            print('Received message from {0.author.display_name} | Content: "{0.content}"'.format(message))
            await message.reply('Thanks for your message!')

    client = MyClient()
    client.run()
