# import os
import discord
import pymongo
import asyncio
from keepalive import keep_alive
from dotenv import load_dotenv
from discord.ext import commands
from discord.utils import get

from googleapiclient.discovery import build

load_dotenv()
my_secret = os.getenv('token')
uri = os.getenv('uri')
key = os.getenv('key')

prefix = '$'
youtube = build('youtube', 'v3', developerKey=key)
client = commands.Bot(command_prefix="$")
message_here = ''
mention_role = ''
new_videos = []

cluster = pymongo.MongoClient(uri)
db = cluster["disc"]
channel_info = db["channel_info"]
videos = db["videos"]


async def get_channel_details(channel_id):
    request = youtube.channels().list(
        part="contentDetails",
        id = channel_id,
        access_token=key
    )
    response = request.execute()
    uploads = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
    await get_videos(uploads, channel_id)

async def get_videos(uploads, channel_id):
    request = youtube.playlistItems().list(
        part="snippet",
        maxResults=5,
        playlistId=uploads,
        access_token=key
    )
    response = request.execute()
    response = response['items']
    video_list = []
    for item in response:
        video_list.append(str(item['snippet']['resourceId']['videoId']))

    channelTitle = item['snippet']['channelTitle']
    post = {
        'channelTitle' : channelTitle,
        'channel_id' : channel_id,
        'uploads' : uploads,
        'videos' : video_list
    }
    videos.insert_one(post)

async def channel_exists(cd):
    flag = 0
    result = videos.find()
    temp_result = result
    for res in temp_result:
        x = res["channel_id"]
        if (x == cd):
            return 0
        else:
            flag = 1
    if (flag == 1):
        return 1

async def check_new_videos(ctx):    
    await client.wait_until_ready()
    while not client.is_closed():
        results = videos.find()
        print("checking")
        await message_here.send(f"{prefix}checking")
        await ctx.channel.purge(limit=1)
        for channel in results:
            uploads = channel['uploads']
            request = youtube.playlistItems().list(
                part="snippet",
                maxResults=5,
                playlistId= uploads,
                access_token=key
            )
            response = request.execute()
            response = response['items']
            for item in response:
                video = item['snippet']['resourceId']['videoId']
                if channel['videos'][0] == video:
                    break
                else:
                    channel['videos'].insert(0, video)
                    channel['videos'].pop(4)
                    videos.update_one({'channel_id' : response[0]['snippet']['channelId']}, {"$set":{'videos' : channel['videos']}})
                    await update_latest(video, item['snippet']['channelTitle'])
                    await message_here.send(f" {mention_role.mention} https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}")
                    break
        await asyncio.sleep(900)


async def update_latest(video, title):
    post = [title,video]
    new_videos.insert(0, post)
    if(len(new_videos) > 10):
        new_videos.pop(10)
    print(new_videos)


@client.event
async def on_ready():
    await client.change_presence(activity=discord.Game(name='Youtube'))
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.content.startswith('$checking'):
        await message.channel.purge(limit=1)

@client.command(aliases=["hello", "sup"], help="Prints hello!")
async def hi(ctx):
    await ctx.send(f"Hello! {ctx.author.mention}")

@client.command(help = "Adds channel to tracking list. [Provide channel id]")
async def follow(ctx, channel_id):
    if (await channel_exists(str(channel_id))):
        await get_channel_details(channel_id)
        await ctx.send(f"{ctx.author.mention} Started Following!!")
    else:
        await ctx.send(f"{ctx.author.mention} Already following!!")

@client.command(help = "Sets the channel in which bot will give latests uploads. [Provide text-channel id]")
async def set(ctx, id):
    global message_here
    global mention_role
    mention_role = get(ctx.guild.roles, name='Hermit')
    message_here = client.get_channel(int(id))
    # message_here = ctx
    await message_here.send(f"{ctx.author.mention} Channel set")   
    await client.loop.create_task(check_new_videos(ctx))

@client.command(help = "Lists the channels the bot is tracking.")
async def list(ctx):
    results = videos.find()
    embed = discord.Embed(title='List of channels', description =f"{ctx.author.mention} Here is a list of the channels the bot is tracking:-", color = discord.Colour.green())
    for channel in results:
        embed.add_field(name = channel['channelTitle'], value=channel['channel_id'], inline=False)
    await message_here.send(embed = embed)

@client.command(help = "Sets the prefix for using the bot.")
async def setPrefix(ctx, pref):
    global prefix
    global client
    prefix = str(pref)
    client = commands.Bot(command_prefix=str(pref))
    await message_here.send("Set prefix successfully.")

@client.command(help = "Purges the specified number if messages.")
async def purge(ctx, amount=0):
    await ctx.channel.purge(limit=int(amount)+1)

@client.command(help = "Gets the latest few videos.")
async def latest(ctx, count=5):
    flag = 0
    print(new_videos)
    x = len(new_videos)
    embed = discord.Embed(title='List of latest videos', description ='Here is a list of latest uploads:- ', color = discord.Colour.green())
    for i in range(int(count)):
        if (i < x):
            embed.add_field(name = new_videos[i][0], value=f"https://www.youtube.com/watch?v={new_videos[i][1]}", inline=False)
            flag = 1
        else:
            break
    if flag:
        await message_here.send(embed=embed)
    else:
        await message_here.send(f"{ctx.author.mention} No new videos.")
keep_alive()
client.run(my_secret)