Getting started
===============

Installation
------------

**Fortnitepy requires Python 3.5 or higher**

**Windows**

.. code:: sh

    py -3 -m pip install fortnitepy

**Linux**

.. code:: sh

    python3 -m pip install fortnitepy

Authentication
--------------

The get the bot working you must use one of several :ref:`authentication methods <authentication>`. If you do not know which one to use, you should stick with :class:`AdvancedAuth` which is used in all examples. :class:`AdvancedAuth` requires you to enter an authorization code upon the bots initial launch. When the bot has successfully authenticated, it will automatically generate credentials which can be used at a later point. That means you can launch your bot without any extra stuff needed after its first launch.

**How to get an authorization code:**

#. Log into an epic -games account of your choice `here <https://www.epicgames.com/id/logout?redirectUrl=https%3A//www.epicgames.com/id/login%3FredirectUrl%3Dhttps%253A%252F%252Fwww.epicgames.com%252Fid%252Fapi%252Fredirect%253FclientId%253D3446cd72694c4a4485d81b77adbb2141%2526responseType%253Dcode>`_.  
#. Copy the hex part from the url that shows up as showcased by the image below.

.. image:: https://raw.githubusercontent.com/Terbau/fortnitepy/dev/docs/resources/images/authorization_code.png

**Note:** An authorization code expires after 5 minutes.

Basic example
-------------

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
                    prompt_code_if_invalid=True,
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
