import fortnitepy

client = fortnitepy.Client(
    email='example@email.com',
    password='password123'
)

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
    print(f'Received message from {message.author.display_name} | Content: "{message.content}"')
    await message.reply('Thanks for your message!')

client.run()