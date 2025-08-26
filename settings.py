import os

import discord
import json

from discord.ext import commands

with open('conf.json') as conf_file:
    conf = json.load(conf_file)

TOKEN = conf['DISCORD_TOKEN'] # discord token
DISCORD_GUILD_ID = conf['DISCORD_GUILD_ID'] # discord Guild ID (useless for now)

UPCOMING_CTFTIME_FILE = conf['UPCOMING_CTFTIME_FILE'] # file to save all Events Data (CTFTIME)
EVENT_LOG_FILE = conf['EVENT_LOG_FILE'] # to be removed when new file system complete
CURRENT_CTF_DIR = conf['CURRENT_CTF_DIR'] # directory for the current CTF's
PAST_CTF_DIR = conf['PAST_CTF_DIR'] # directory for the past CTF's

WEIGHT_RANGE_GENERAL = conf['WEIGHT_RANGE_GENERAL'] # the spread for the research by weight
WEIGHT_START_RECOMMENDATION = conf['WEIGHT_START_RECOMMENDATION'] # the starting weight to start recommending CTFs (used with the RANGE)
WEEKS_RANGE_RECOMMENDATION = conf['WEEKS_RANGE_RECOMMENDATION']
WEIGHT_RANGE_RECOMMENDATION = conf['WEIGHT_RANGE_RECOMMENDATION'] # the spread for the recommendation by weight
DAY_OF_WEEK_RECOMMENDATION = conf['DAY_OF_WEEK_RECOMMENDATION']
DISABLE_ZERO_WEIGHT_RECOMMENDATION = conf['DISABLE_ZERO_WEIGHT_RECOMMENDATION'] # if 0 than CTFs with 0 weight will be skipped for recommendations
NUMBER_OF_RECOMMENDATIONS = conf['NUMBER_OF_RECOMMENDATIONS'] # number of CTFs to recommend at once (every wednesday)

MAX_EVENT_LIMIT = max(conf['MAX_EVENT_LIMIT'] - 1, 0) # limit the maximum amount of event to be printed out by the bot in a single message (mostly to avoid crashing)
CTF_CHANNEL_CATEGORY_ID = conf['CTF_CHANNEL_CATEGORY_ID']# the list of all the categories the bot can modify (one per server)
CTF_JOIN_CHANNEL = conf['CTF_JOIN_CHANNEL'] # channel to send msg
CTF_ANNOUNCE_CHANNEL = conf['CTF_ANNOUNCE_CHANNEL'] # channel to send the announce

AUTHOR_ICON = "https://ctfrei.fr/static-img/logo_red_alpha.png"
FOOTER_ICON = "https://play-lh.googleusercontent.com/WOWsciDNUp-ilSYTtZ_MtkhZrhXBFp_y5KNGK0x7h2OnaqSe6JdRgQgbvBEUbNhuKxrW"

WEBHOOK_SECRET = os.getenv("DISCORD_SHARED_KEY")

if not WEBHOOK_SECRET:
    raise ValueError("DISCORD_SHARED_KEY environment variable is not set")

optional_thumbnail="https://cdn.discordapp.com/attachments/1167256768087343256/1202189272707502080/CFTREI_Story.png?ex=67517782&is=67502602&hm=308d0f9c1577dfad2a898dd262ad1e526127c115cf165a193d02ea5585ada2a3&"


intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)