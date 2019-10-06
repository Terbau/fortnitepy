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

    class MyClient(fortnitepy.Client):
        def __init__(self):
            super().__init__(
                email='example@email.com',
                password='password123'
            )
        
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
