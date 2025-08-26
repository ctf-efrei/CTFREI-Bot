import requests
import discord
import json
import hashlib

# from main import AUTHOR_ICON

from datetime import datetime
from os import scandir


#generate md5 hash and keeps 8 char (used to have a unique ID on the Events to avoid dupplicates)
def generate_unique_id(CTFname: str):
    unique_id = (hashlib.md5(CTFname.encode()).hexdigest())[:8]
    return unique_id


def list_directory_contents(directory: str):
    try:
        contents = list(scandir(directory))
        return [item.name for item in contents]
    except FileNotFoundError:
        print(f"The directory '{directory}' was not found.")
        return []
    except PermissionError:
        print(f"You don't have permission to access the directory '{directory}'.")
        return []


#look inside the Json data files for match
async def search_ctf_data(filename: str, query: str, WEIGHT_RANGE: int):
    match = []  # array of match
    with open(filename) as json_file:
        events = json.load(json_file)

        if len(query) <= 2:  # set as 2 for weight search via INT
            try:
                # Attempt to convert the query to a float
                weight_query = float(query)
                # range can be set in the conf file
                min_weight = weight_query - WEIGHT_RANGE
                max_weight = weight_query + WEIGHT_RANGE

                if min_weight < 0:
                    min_weight = 0
                if max_weight > 100:
                    max_weight = 100

                for event in events:
                    event_weight = float(event['weight'])  # Convert event weight to float
                    if min_weight <= event_weight <= max_weight:
                        match.append({
                            # event info
                            "title": event['title'],
                            "weight": event['weight'],
                            "url": event['url'],
                            "ctftime_url": event['ctftime_url'],
                            "start": event['start'],
                            "finish": event['finish'],
                            "duration": event['duration'],
                            "format": event['format'],
                            "location": event['location'],
                            "logo": event['logo'],
                            "description": event['description'],
                            "onsite": event['onsite'],
                        })
            except ValueError:
                print(f"no result found: {query}")

        else:
            for event in events:
                if (query.lower() in event['title'].lower()):
                    match.append({
                        # event info
                        "title": event['title'],
                        "weight": event['weight'],
                        "url": event['url'],
                        "ctftime_url": event['ctftime_url'],
                        "start": event['start'],
                        "finish": event['finish'],
                        "duration": event['duration'],
                        "format": event['format'],
                        "location": event['location'],
                        "logo": event['logo'],
                        "description": event['description'],
                        "onsite": event['onsite'],
                    })

        return match


# Create a private text channel in the specified category for the role
async def create_private_channel(guild: discord.guild, category: discord.CategoryChannel, role: discord.Role):
    CTFREI_role = discord.utils.get(guild.roles,
                                    name="CTFREI")  # Get the CTFREI role to make sure the bot can access the channel

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),  # Deny access to everyone
        role: discord.PermissionOverwrite(read_messages=True),  # Grant access to users with the specified role
        CTFREI_role: discord.PermissionOverwrite(read_messages=True)  # Grant access to users with the CTFREI role
    }

    private_channel = await guild.create_text_channel(name=f"🚩-{role.name}", category=category, overwrites=overwrites)

    return private_channel


#retrieve a message by its id and reply to it with a given String
async def reply_message(ctx: discord.integrations, channel: discord.TextChannel, message_id: int, response: str):
    if channel is None:
        await ctx.send("Error finding the join channel")
        print("Channel not found.")
        return None
    try:
        message = await channel.fetch_message(message_id)
        await message.reply(response)
        return 1

    except discord.NotFound:
        await ctx.send("Error finding the actual message")
        return None
    except discord.Forbidden:
        await ctx.send("I don't have permission to fetch or reply to that message.")
        return None
    except discord.HTTPException:
        await ctx.send("Something went wrong while fetching the message.")
        return None


# Retrieve a discord.Category based on the settings' ID (to make sure channels are not created anywhere)
def get_category_by_id(guild: discord.Guild, category_id: int):
    for category in guild.categories:
        if category.id == category_id:
            return category
    return None


# Check if the channel name already exists (to make sure channels are not beeing doubled)
def get_channel_by_name(guild: discord.Guild, channelname: str):
    for channel in guild.channels:
        if channel.name == channelname:
            return channel
    return None


# retrieve the data of an event using the discord role associated to it (not case sensitive)
async def search_event_data_by_role(filename: str, role: str):
    with open(filename, 'r') as events_file:
        events_data = json.load(events_file)

    for event in events_data:
        for rolename in event:
            if rolename.lower() == role.lower():
                return event[role]  #returns the information about the CTF

    return None


# creates & returns an embedded message based on the event_info given (in the format of ctf_events.json), the integer is to differenciate the color/format.
async def send_event_info(event_info, id: int):
    # Retrieve start, finish, and duration from event_info
    start_time = datetime.fromisoformat(event_info['start'])
    end_time = datetime.fromisoformat(event_info['finish'])
    duration_days = event_info['duration'].get('days', 0)
    duration_hours = event_info['duration'].get('hours', 0)
    duration_str = f"{duration_days * 24 + duration_hours} hours"

    # Format the start and end time as 'days-month-year hrs:minutes'
    start = start_time.timestamp()
    end = end_time.timestamp()
    current = datetime.now().timestamp()

    # Calculate event status based on the current time
    if current < start:
        # Event hasn't started yet, shows the time before starts
        status_str = f"Start <t:{int(start)}:R>"

    elif start <= current < end:
        # Event has started, display relative time before ends
        status_str = f"Ends <t:{int(end)}:R>"

    else:
        # Event is over
        status_str = "Event is over"

    if id < 2:  # case 0 =  first message format (/quickadd for exempl), case 2 = /info format

        # Set up the embedded message
        color = discord.Color.dark_gold() if not id else discord.Color.blurple()  # if id 0 then dark_gold, else blurple()
        embeded_message = discord.Embed(
            title=f"__{event_info['title']}__",
            url=event_info['url'],
            description=f"Here are the information on **{event_info['title']}**.",
            color=color
        )

        # todo remplace par main.AUTHOR_ICON
        embeded_message.set_author(name="CTF INFORMATION (CTFTIME)", url=event_info['ctftime_url'],
                                   icon_url="https://ctfrei.fr/static-img/logo_red_alpha.png")
        embeded_message.add_field(name="Weight", value=f"**{event_info['weight']}**", inline=True)
        embeded_message.add_field(name="Onsite", value=f"{event_info['onsite']}", inline=True)
        embeded_message.add_field(name="Format", value=f"{event_info['format']}", inline=True)
        embeded_message.add_field(name="Start time", value=f"<t:{int(start)}:F>", inline=True)
        embeded_message.add_field(name="End time", value=f"<t:{int(end)}:F>", inline=True)
        embeded_message.add_field(name="Duration", value=f"{duration_str}", inline=True)
        embeded_message.add_field(name="Status", value=f"{status_str}", inline=True)
        embeded_message.add_field(name="URI", value=f"[CTFd]({event_info['url']})", inline=True)

        embeded_message.set_image(
            url="https://cdn.discordapp.com/attachments/1167256768087343256/1202189774836731934/CTFREI_Banniere_920_x_240_px_1.png?ex=67162479&is=6714d2f9&hm=c649d21b2152c0200b9466a29c09a04865387410258c1c228c8df58db111c539&")

        if event_info['logo']:
            embeded_message.set_thumbnail(url=event_info['logo'])

        return embeded_message


async def log(ctx: discord.integrations, FILE: str, logs: str):
    with open(FILE, 'a') as log:
        log.write(f"{ctx.guild.name}: user:{ctx.user.name} ({ctx.user.id}): {logs}")


# make an api call on a url and retrieves all the data, then put it in a file.
def api_call(url: str, filename: str):
    try:
        # url = "https://ctftime.org/api/v1/events/?limit=100"

        headers = {
            'User-Agent': 'curl/7.68.0'  # Mimicking a curl request
        }

        response = requests.get(url, headers=headers)

        # Check request's status code
        if response.status_code != 200:
            print(f"Failed to retrieve content: {response.status_code}")
            return None

        data = response.json()

        #print(data)
        with open(filename, 'w') as fp:
            json.dump(data, fp, indent=4)

        print(f"{url} data has been saved to {filename}")

        return data


    except Exception as e:
        print(f"An error occurred: {e}")
        return None
