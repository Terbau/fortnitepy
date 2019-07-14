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
        print(f'Received message from {message.author.display_name} | Content: "{message.content}"')
        await message.reply('Thanks for your message!')
    
client = MyClient()
client.run()