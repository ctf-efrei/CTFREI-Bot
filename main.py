import asyncio
import hmac

import requests as req
import time as t
import uvicorn

from bot_functions import *
from settings import *
from discord.ext import commands, tasks
from discord.ui import Button, View
from discord.utils import get
from datetime import *
from os import path as p
from os import mkdir, rename
from typing import Literal


"""CONFIGURATION LOADING"""

CTFREI = "__GOATS__"

"""INTERACTIONS' RELATED"""

INTERACTION_SAVE_FILE = conf['INTERACTION_SAVE_FILE']
def load_persistent_data():
    try:
        with open(INTERACTION_SAVE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Interaction save file not found.")
        return {}

def save_persistent_data(data):
    with open(INTERACTION_SAVE_FILE, "w") as f:
        json.dump(data, f)

persistent_data = load_persistent_data()

class PersistentView(View):
    def __init__(self, role):
        super().__init__(timeout=None)
        self.add_item(RoleButton(role))

class RoleButton(Button):
    def __init__(self, role):
        super().__init__(label="🚩 Rejoindre ce CTF!", style=discord.ButtonStyle.success)
        self.role = role

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if self.role not in user.roles:
            await user.add_roles(self.role)
            await interaction.response.send_message(f"Vous avez récupéré le rôle {self.role.name} !", ephemeral=True)
        else:
            await interaction.response.send_message(f"Vous avez déjà le rôle {self.role.name}.", ephemeral=True)




"""ROLE DETECTION"""
# @bot.event
# async def on_member_update(before: discord.Member, after: discord.Member):
@bot.tree.command(name="memberize", description="Fais de l'utilisateur spécifié un membre (sur CTFd aussi).", guild=discord.Object(id=DISCORD_GUILD_ID))
@commands.has_permissions(manage_roles=True)
async def memberize(ctx: discord.Interaction, user: discord.Member):
    # before_roles = set(before.roles)
    # after_roles = set(after.roles)
    # removed = before_roles - after_roles
    # if removed:
    #     for role in removed:
    #         if role.name == "Membre":
    #             payload["new_state"] = False
    #             print("Revoking", end=" ")

    guild = ctx.guild
    role = discord.utils.get(guild.roles, name="Membre")
    if role is None:
        await ctx.response.send_message("Pas de role 'Membre' !")
        return

    await user.add_roles(role, reason=f"membrisé par {ctx.user.name}")

    payload = {
        "new_state": True
    }
    print(f"Giving membership for {user.name}", end=" ")
    req.patch(
        f"http://ctfd-ctfd-1:8000/plugins/ctfrei_registration/update_role/{user.name}",
        headers={
            "X-Signature": hmac.new(
                WEBHOOK_SECRET.encode(),
                json.dumps(payload).encode("utf-8"),
                hashlib.sha256
            ).hexdigest()
        },
        json=payload
    )

    await ctx.response.send_message(f"{user.name} est maintenant membre.", ephemeral=True)


"""CTFTIME COMMANDS (CTFTIME API): FILE MODIFICATION"""

@bot.tree.command(name="quickadd", description="Ajoute un évènement au serveur (CTFTIME only).", guild=discord.Object(id=DISCORD_GUILD_ID))
async def add_reaction_and_channel(ctx: discord.Interaction, role_name: str, ctf_name: str):
    """add an event to the current events on a server, needs a role name (str) and a ctf name (that can be checked using /search)"""

    """RETRIEVE ALL THE DATA HERE"""

    # tries to find the ctf, if not found it'll stop the program
    CTF_EVENT = await search_ctf_data(filename=UPCOMING_CTFTIME_FILE, query=ctf_name, WEIGHT_RANGE=WEIGHT_RANGE_GENERAL)
    if not CTF_EVENT:
        await ctx.response.send_message("Erreur: Aucun CTF ne correspond. Utilise /search pour vérifier le nom de ton CTF.", ephemeral=True)
        return None
    elif len(CTF_EVENT) > 1:
        await ctx.response.send_message("Erreur: Plus d'un CTF correspond à ce nom. Utilise /search pour t'assurer que tu n'ajoutes qu'un seul CTF.", ephemeral=True)
        return None

    try:
        category = get_category_by_id(guild=ctx.guild, category_id=CTF_CHANNEL_CATEGORY_ID[ctx.guild.name])
        join_channel = await ctx.guild.fetch_channel(CTF_JOIN_CHANNEL[ctx.guild.name])
        current_events = list_directory_contents(f"{CURRENT_CTF_DIR}{ctx.guild.id}")
        role = get(ctx.guild.roles, name=role_name)
        ctfChannel = get_channel_by_name(ctx.guild, f"🚩-{role_name}")
        end_time = datetime.fromisoformat(CTF_EVENT[0]["finish"]).timestamp()
        current = datetime.now().timestamp()
        timeout_timer = end_time - current  # Calculate time remaining until end for interaction
    except ValueError:
        await ctx.response.send_message('Erreur pendant la récupération des données. Si cela continue, contacte un administrateur.', ephemeral=True)
        return 1


    """CHECK FOR ALREADY EXISTING DATA (if there is, stop function and return error)"""


    try:
        event_id = generate_unique_id(str(CTF_EVENT[0]['title']))  # To avoid duplicates with different roles
        for event in current_events:
            if event_id in event:
                await ctx.response.send_message("L'évènement semble déjà être enregistré sur ce serveur, verifie avec /listevents.", ephemeral=True)
                return None

        CTF_EVENT = CTF_EVENT[0]  # Select the data of the event

        if role:
            await ctx.response.send_message("Le role existe déjà.", ephemeral=True)
            return None

        if ctfChannel:
            await ctx.response.send_message(f"Il existe déjà un salon avec ce nom ici {ctfChannel.mention}", ephemeral=True)
            return None
    except ValueError:
        await ctx.response.send_message('Erreur pendant la récupération des données.', ephemeral=True)
        return 1


    """Check if event is over (for interaction mostly)"""

    if timeout_timer < 0:
        await ctx.response.send_message(f"L'évènement semble déjà être terminé ({CTF_EVENT['finish'][:10:]})", ephemeral=True)
        return None

    """ALL THE CHECKS PASSED: CREATING ALL THE ROLES AND CHANNELS"""

    try:
        role = await ctx.guild.create_role(name=role_name)
        private_channel = await create_private_channel(ctx.guild, category, role)
        # Create the button and view after the role is created
        button = RoleButton(role)
        view = View(timeout=timeout_timer)
        view.add_item(button)
    except ValueError:
        await ctx.response.send_message("Erreur pendant la création du bouton.", ephemeral=True)
        return 1

    # Send the message with the button
    try:
        join_message = await join_channel.send(f"{CTF_EVENT['title']} à été ajouter aux évènements ici {private_channel.mention}", view=view)
        message_link = f"https://discord.com/channels/{ctx.guild.id}/{CTF_JOIN_CHANNEL[ctx.guild.name]}/{join_message.id}" # will be linked in the response

        persistent_data[str(join_message.id)] = {"role_id": role.id, "finish": CTF_EVENT['finish']} # to keep the interaction going
        save_persistent_data(persistent_data) # add the interaction to the save file

    except ValueError:
        await ctx.response.send_message("Erreur lors de la création du message pour rejoindre.", ephemeral=True)
        return 1

    """SAVING ALL THE DATA"""

    try:
        # Save the event data to a file
        event_info = {
            "title": CTF_EVENT['title'],
            "weight": CTF_EVENT['weight'],
            "url": CTF_EVENT['url'],
            "ctftime_url": CTF_EVENT['ctftime_url'],
            "start": CTF_EVENT['start'],
            "finish": CTF_EVENT['finish'],
            "duration": CTF_EVENT['duration'],
            "format": CTF_EVENT['format'],
            "location": CTF_EVENT['location'],
            "logo": CTF_EVENT['logo'],
            "description": CTF_EVENT['description'],
            "onsite": CTF_EVENT['onsite'],
            "role_name": role.name,
            "role_id": role.id,
            "event_id": event_id,
            "users_vote": {},
            "channelID": private_channel.id,
            "join_message_id": join_message.id
        }
        event_file_name = f"{role.name}-{event_id}-{private_channel.id}"
        complete_event_file_path = f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file_name}"
        with open(complete_event_file_path, 'x') as file:
            json.dump(event_info, file, indent=4)
    except ValueError:
        await ctx.response.send_message("Erreur lors de la sauvegarde des données.", ephemeral=True)
        return 1


    """SEND THE ANNOUNCEMENT"""
    announce_data = CTF_ANNOUNCE_CHANNEL[ctx.guild.name]
    announce_channel = await ctx.guild.fetch_channel(announce_data['channel_id'])
    announce_role = discord.utils.get(ctx.guild.roles, id=announce_data["role_id"])
    duration = (int(event_info['duration']['days'])*24) + (event_info['duration']['hours'])

    # Set up the embedded message
    color = discord.Color.red()
    embeded_message = discord.Embed(
        title=f"__{event_info['title']}__",
        description=f"Salut {announce_role.mention} ! <:xxxxxxd:1312187847217909770>\n **{event_info['title']}** à été ajouté sur le serveur ! \n\nRécupérez le rôle {role.mention} pour avoir accès au salon dédié.", # french version (cocorico)
        color=color
    )

    embeded_message.set_author(name="CTFREI BOT",icon_url="https://www.efrei.fr/wp-content/uploads/2024/07/ctefrei.png")

    embeded_message.add_field(name="**Informations:**", value=f":date: Du <t:{int((datetime.fromisoformat(event_info['start'])).timestamp())}:F> au <t:{int((datetime.fromisoformat(event_info['finish'])).timestamp())}:F>\n:alarm_clock: dure {duration} heures au total\n:man_lifting_weights: Weight estimé {event_info['weight'] if int(event_info['weight']) != 0 else 'inconnu'}", inline=True)

    embeded_message.add_field(name="**URI links:**", value=f"<:ctftime:1320354001287647264> [CTFTIME]({event_info['ctftime_url']})\n<:site:1320352422056693821> [CTFd]({event_info['url']})\n", inline=False)

    embeded_message.add_field(name="**Channel & role:**", value=f"<:logo_ctfrei:1167954970889441300> {message_link}", inline=False)

    embeded_message.set_image(url="https://cdn.discordapp.com/attachments/1167256768087343256/1202189774836731934/CTFREI_Banniere_920_x_240_px_1.png?ex=67162479&is=6714d2f9&hm=c649d21b2152c0200b9466a29c09a04865387410258c1c228c8df58db111c539&")

    if event_info['logo']:
        embeded_message.set_thumbnail(url=event_info['logo'])

    announce_message = await announce_channel.send(f"||{announce_role.mention}||",embed=embeded_message, view=view) # send the announce message with the button (view)

    persistent_data[str(announce_message.id)] = {"role_id": role.id, "finish": CTF_EVENT['finish']} # create the entry for the interaction (persistence post restart)
    save_persistent_data(persistent_data) # save it


    """OTHER: SEND THE EVENT DATA TO THE NEW CHANNEL"""

    await log(ctx, EVENT_LOG_FILE, f"EDIT: added a new CTF ({CTF_EVENT['title']}) as {role.name}\n")
    await private_channel.send(embed=(await send_event_info(event_info=event_info, id=0)))
    await ctx.response.send_message(f"l'évènement à été ajouter avec succès ici : {message_link}", ephemeral=True)
    return None

@bot.tree.command(name="refresh", description="Une commande pour rafraichir la liste des CTFs de CTFTIME.", guild=discord.Object(id=DISCORD_GUILD_ID))
async def refresh_data(ctx: discord.Interaction):
    """refresh the list of upcoming CTFs (using CTFtime API's, reload up to 100 events)"""
    try:
        data = api_call("https://ctftime.org/api/v1/events/?limit=100", UPCOMING_CTFTIME_FILE)
        last = str(data[-1]['finish'])[:10:]
        if not data:
            await ctx.response.send_message(f"Erreur.", ephemeral=True)
        await log(ctx, EVENT_LOG_FILE, f"REQ: Refreshed the event file\n")
        await ctx.response.send_message(f"liste mise à jour jusqu'au : {last}", ephemeral=True)
        return None
    except ValueError:
        ctx.response.send_message("Erreur lors de la mise à jour des évènements.", ephemeral=True)
        return 1










"""SEARCHING COMMANDS (GENERAL): NO FILE MODIFICATION"""

@bot.tree.command(name="upcoming", description="Liste les prochains CTF à venir.", guild=discord.Object(id=DISCORD_GUILD_ID))
async def upcoming_ctf(ctx: discord.Interaction, max_events: int = MAX_EVENT_LIMIT):
    """List X number of the upcoming CTFs based on the UPCOMING file's content"""

    """Retrieve data from UPCOMING file"""
    if max_events and ((max_events > 25) or (max_events < 1)):
        max_events = 25 # set a limit to 25, above the response will crash.

    try:
        with open(UPCOMING_CTFTIME_FILE) as data_file:
            events = json.load(data_file)
    except ValueError:
        await ctx.response.send_message("Erreur lors de la lecture de la liste d'évènement à venir.", ephemeral=True)
        return 1

    embeded_message = discord.Embed(
            title="Les CTF à venir",  # Title of the embed
            description="Voici la liste des CTF à venir de CTFTIME",  # Description of the embed
            color=discord.Color.blue()  # Color of the side bar (you can change the color)
        )

    try:
        count = 0 # variable to limit the amount of output per message (discord limits)
        for event in events:
            if event['location'] == '':

                event_info = f"Weight: {event['weight']} | {event['format']} | starts : <t:{int((datetime.fromisoformat(event['start'])).timestamp())}:R>" # format for the output of the CTF upcoming lists for each event
                embeded_message.add_field(name=event['title'], value=event_info, inline=False)

                count += 1

            if count >= max_events:
                break
    except ValueError:
        ctx.response.send_message("Erreur lors de la lecture de la liste des évènements.", ephemeral=True)
        return 1
    embeded_message.set_author(name="CTFTIME API DATA", url="https://ctftime.org/event/list/upcoming", icon_url=AUTHOR_ICON)
    embeded_message.set_footer(text="Pour plus d'évènement utiliser /upcoming {number}\nVous pouvez également en apprendre plus sur un évènement avec la commande /search {nom de l'évènement}", icon_url=FOOTER_ICON)

    embeded_message.set_thumbnail(url=optional_thumbnail)

    await ctx.response.send_message(embed=embeded_message, ephemeral=True)
    return None

@bot.tree.command(name="listevents", description="Liste tout les CTFs actifs sur le serveur.", guild=discord.Object(id=DISCORD_GUILD_ID))
async def list_registered_events(ctx: discord.Integration):
    """list all the files in the current events directory and prints some info"""
    try:
        current_events = list_directory_contents(f"{CURRENT_CTF_DIR}{ctx.guild.id}")
        if not current_events:
            await ctx.response.send_message("Aucun évènement n'a été trouvé.", ephemeral=True)
            return 1

        events_data = []
        for individual_event in current_events:
            with open(f"{CURRENT_CTF_DIR}{ctx.guild.id}/{individual_event}") as individual_event_file:
                temp = json.load(individual_event_file)
                full_data = [temp['title'], temp['weight'], temp['start'][:10:], temp['url'], temp['channelID'], temp['join_message_id'], temp['role_name'], temp['event_id'], temp['logo']]
                events_data.append(full_data)
    except ValueError:
        await ctx.response.send_message('Erreur lors de la récupération des données.', ephemeral=True)
        return 1


    embeded_message = discord.Embed(
            title="Évènement CTF en cours",
            description="Voici la liste des CTFs actuellement en cours sur le serveur.",
            color=discord.Color.dark_grey()  # Color of the side bar (you can change the color)
        )

    try:
        for individual_event in events_data:
            event_chan = ctx.guild.get_channel(individual_event[4])
            message_link = f"https://discord.com/channels/{ctx.guild.id}/{CTF_JOIN_CHANNEL[ctx.guild.name]}/{individual_event[5]}"
            event_info = f"Weight: {individual_event[1]} | commence: <t:{int((datetime.fromisoformat(individual_event[2])).timestamp())}:F> | Event ID: `{individual_event[7]}` | channel: {event_chan.mention} | {message_link}" # format for the output of the Currently registered CTF
            embeded_message.add_field(name=individual_event[0], value=event_info, inline=False)
    except ValueError:
        await ctx.response.send_message("Erreur lors de l'utilisation de la données.", ephemeral=True)
        return 1

    embeded_message.set_footer(text="Vous pouvez en apprendre plus sur un certain évènement en cours en utilisant /registered_search {eventID}", icon_url=FOOTER_ICON)

    await ctx.response.send_message(embed=embeded_message, ephemeral=True)
    return None

@bot.tree.command(name="search", description="Cherche à travers les CTFs à venir, peut chercher par nom (string) ou par difficulté (int).", guild=discord.Object(id=DISCORD_GUILD_ID))
async def search_json(ctx: discord.Interaction, query: str = None):
    """search the upcoming file for matches, can use integer for weight search, for strings for name/tag search"""

    if query is None:
        await ctx.response.send_message(f"S'il vous plait ajouter une entrer: \n- **string** => cherche un évènement par nom/tag\n- **integer** => cherche un niveau de difficulté (marge de {WEIGHT_RANGE_GENERAL})", ephemeral=True)
        return None

    try:
        matches = await search_ctf_data(UPCOMING_CTFTIME_FILE, query, WEIGHT_RANGE_GENERAL)
        if not matches:
            await ctx.response.send_message("Aucun évènement n'a pu être trouvé, vérifier si l'évènement n'est pas déjà enregistré avec /listevents, sinon vous pouvez utiliser /refresh pour raffraichir la liste ou /upcoming pour voir les prochains CTFs à venir.", ephemeral=True)
            return None
    except ValueError:
        await ctx.response.send_message("Erreur pendant la recherche.", ephemeral=True)
        return 1





    if len(matches) == 1:
        matches = matches[0]  # if only one match, use the first element directly
        # prepare the embeded message for discord limiting to NUMBER_OF_RECOMMENDATIONS
        embeded_message = discord.Embed(
            title=f"__**{matches['title']}**__",
            description=f"CTF de type {matches['format']} - Onsite: {matches['onsite']} - Location: {matches['location'] if matches['location'] else 'ONLINE'}",
            color=discord.Color.dark_orange()
        )

        if matches['logo']:
            embeded_message.set_thumbnail(url=matches['logo'])

        embeded_message.add_field(name=f"**Informations :**", value=f":stopwatch: durée du CTF : {(int(matches['duration']['days'])*24) + (matches['duration']['hours'])} heures\n:man_lifting_weights: Weight estimé {matches['weight'] if int(matches['weight']) != 0 else 'inconnu'}", inline=True)

        embeded_message.add_field(name="**URI links:**", value=f"<:ctftime:1320354001287647264> [CTFTIME]({matches['ctftime_url']})\n<:site:1320352422056693821> [CTFd]({matches['url']})\n", inline=True)

        embeded_message.add_field(name="# **Dates:**", value=f":date: Du <t:{int((datetime.fromisoformat(matches['start'])).timestamp())}:F> au <t:{int((datetime.fromisoformat(matches['finish'])).timestamp())}:F>", inline=False)

        embeded_message.add_field(name="**Description:**", value=f"{matches['description'][:1200:]}", inline=False)

        embeded_message.set_author(name="CTFTIME API DATA", url="https://ctftime.org/event/list/upcoming", icon_url=AUTHOR_ICON)

    else:
        embeded_message = discord.Embed(
            title="CTFs trouvés",
            description="Voici la liste des CTFs trouvés avec votre recherche.",
            color=discord.Color.greyple()  # Color of the side bar (you can change the color)
        )
        try :
            count = 0 # to limit output (avoid discord limit related crashes)
            for event in matches:
                if count < 12:
                    event_info = f"Weight: {event['weight']} | {event['format']} | Starts: <t:{int((datetime.fromisoformat(event['start'])).timestamp())}:F> => [CTFTIME]({event['ctftime_url']})\n"
                    count += 1
                    embeded_message.add_field(name=f"**__{event['title']}__**", value=event_info, inline=False)
                else:
                    continue
        except ValueError:
            await ctx.response.send_message("Erreur lors de la création de la réponse.", ephemeral=True)
            return 1

        embeded_message.set_author(name="CTFTIME API DATA", url="https://ctftime.org/event/list/upcoming", icon_url=AUTHOR_ICON)
        embeded_message.set_footer(text="Vous pouvez en apprendre plus sur un certain évènement en utilisant /search {name of the event}", icon_url=FOOTER_ICON)


    await log(ctx, EVENT_LOG_FILE, f"GET: searched for {query}\n")
    await ctx.response.send_message(embed=embeded_message, ephemeral=True)
    return None

@bot.tree.command(name="registered_search", description="Cherche dans la liste des évènements déjà enregistrés avec son ID.", guild=discord.Object(id=DISCORD_GUILD_ID))
async def search_registered_events(ctx: discord.Integration, event_id: str):
    """search the directory for current events using its ID or associated role name"""

    current_events = list_directory_contents(f"{CURRENT_CTF_DIR}{ctx.guild.id}")

    full_data = []
    for event_file in current_events:
        if event_id in event_file:
            with open(f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file}") as individual_event_file:
                full_data = json.load(individual_event_file)

    if not full_data:
        await ctx.response.send_message(f"Aucun évènement avec l'ID {event_id} n'a pu être trouvé. Vous pouvez utiliser /listevents pour voir tout les évènements et leur ID.", ephemeral=True)
        return None

    event_chan = ctx.guild.get_channel(CTF_JOIN_CHANNEL[ctx.guild.name])

    message_link = f"https://discord.com/channels/{ctx.guild.id}/{event_chan.id}/{full_data['join_message_id']}"

    # Set up the embedded message
    color = discord.Color.dark_teal()
    embeded_message = discord.Embed(
        title=f"__{full_data['title']}__",
        url=full_data['url'],
        description=f"Voici les informations CTFTIME sur {full_data['title']}.",
        color=color
    )

    embeded_message.set_author(name="CTF INFORMATION", url=full_data['url'], icon_url=AUTHOR_ICON)
    embeded_message.add_field(name="Weight", value=f"**{full_data['weight']}**", inline=True)
    embeded_message.add_field(name="Rejoindre ici:", value=f"{message_link}", inline=True)
    embeded_message.add_field(name="Commence:", value=f"<t:{int((datetime.fromisoformat(full_data['start'])).timestamp())}:F>", inline=False)
    embeded_message.add_field(name="Fini:", value=f"<t:{int((datetime.fromisoformat(full_data['finish'])).timestamp())}:F>", inline=True)
    embeded_message.add_field(name="Liens CTF:", value=f"[CTFd]({full_data['url']})\n[CTFTIME]({full_data['ctftime_url']})", inline=False)


    ctfrei_logo = "https://cdn.discordapp.com/attachments/1167256768087343256/1202189774836731934/CTFREI_Banniere_920_x_240_px_1.png?ex=67162479&is=6714d2f9&hm=c649d21b2152c0200b9466a29c09a04865387410258c1c228c8df58db111c539&"

    embeded_message.set_thumbnail(url=full_data['logo']) if full_data['logo'] else embeded_message.set_thumbnail(url=ctfrei_logo)

    embeded_message.set_image(url=ctfrei_logo)

    await ctx.response.send_message(embed=embeded_message, ephemeral=True)

    return None










"""SEARCHING COMMANDS (CTFs channel): NO FILE MODIFICATION"""

@bot.tree.command(name="info", description="Affiche les informations sur le CTF lié au channel actuel.", guild=discord.Object(id=DISCORD_GUILD_ID))
async def get_info(ctx: discord.Interaction):
    """displays info on current channel's CTF"""
    try:
        channel_id = ctx.channel.id # used for search
        event_data = {}
        event_list = list_directory_contents(f"{CURRENT_CTF_DIR}{ctx.guild.id}")
        for event_file in event_list:
            if str(channel_id) in event_file:
                with open(f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file}", 'r') as data:
                    event_data = json.load(data)

        if not event_data:
            await ctx.response.send_message(f"Aucun évènement n'a pu être trouvé pour ce channel. Assurer vous que vous utilisez cette commande dans un salon dédié à un CTF. (/listevents)", ephemeral=True)
            return 1

        print(event_data)
        embeded_message = await send_event_info(event_info=event_data, id=1)
    except ValueError:
        await ctx.response.send_message("Erreur lors de la récupération de l'information.", ephemeral=True)
        return 1
    await log(ctx, EVENT_LOG_FILE, f"GET: Event info for {event_data['title']}\n")
    await ctx.response.send_message(embed=embeded_message, ephemeral=True)
    return None

@bot.tree.command(name="description", description="Affiche la description de l'évènement en cours (CTFTIME).", guild=discord.Object(id=DISCORD_GUILD_ID))
async def get_description(ctx: discord.integrations):
    """displays the description of the current channel's CTF"""
    try:
        channel_id = ctx.channel.id # used for search
        event_data = []
        event_list = list_directory_contents(f"{CURRENT_CTF_DIR}{ctx.guild.id}")
        for event_file in event_list:
            if str(channel_id) in event_file:
                with open(f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file}", 'r') as data:
                    event_data = json.load(data)
        if not event_data:
            await ctx.response.send_message(f"Aucun évènement n'a pu être trouvé pour ce channel. Assurer vous que vous utilisez cette commande dans un salon dédié à un CTF. (/listevents)", ephemeral=True)
            return 1
    except ValueError:
        await ctx.response.send_message("Erreur lors de la récupération de l'information.", ephemeral=True)
        return 1
    await log(ctx, EVENT_LOG_FILE, f"GET: Event description for {event_data['title']}\n")
    await ctx.response.send_message(f"Voici la description de **{event_data['title']}**:\n{event_data['description']}", ephemeral=True)
    return None


@bot.tree.command(name="end", description="Termine et archive le CTF actuelle (uniquement quand il est terminé sur CTFTIME).", guild=discord.Object(id=DISCORD_GUILD_ID))
async def end_event(ctx: discord.integrations):
    """Moves the CTF file and channel to the archive, effectively stopping it from beeing seen as currently running"""

    """retrieve the data"""
    try:
        full_file_path = "" # keep or will crash if no file found
        ARCHIVE_CATEGORY = conf['ARCHIVE_CATEGORY'][ctx.guild.name]
        channel_id = ctx.channel.id # used for search
        event_list = list_directory_contents(f"{CURRENT_CTF_DIR}{ctx.guild.id}")
        for event_file in event_list:
            if str(channel_id) in event_file:
                full_file_path= f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file}"

                with open(f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file}", 'r') as data:
                    data = json.load(data)

                break
        if not full_file_path:
            await ctx.response.send_message(f"Aucun évènement n'a pu être trouvé pour ce channel. Assurer vous que vous utilisez cette commande dans un salon dédié à un CTF (/listevents) et que le CTF n'a pas déjà été terminé.  ", ephemeral=True)
            return 1

        """Check if the event is actually over"""

        end_time = datetime.fromisoformat(data['finish']).timestamp()
        current = datetime.now().timestamp()

        if end_time > current: # event is not over
            await ctx.response.send_message(f"L'évènement n'est pas encore terminé selon les informations CTFTIME récupérées.", ephemeral=True)
            return 1

        """Move the file to PAST and move discord channel to the archive (optionnal)"""

        rename(full_file_path, f"{PAST_CTF_DIR}{ctx.guild.id}/{event_file}_{int(t.time())}")

        archive_category = get(ctx.guild.categories, id=ARCHIVE_CATEGORY)
        await ctx.channel.edit(category=archive_category, sync_permissions=True)
        role = ctx.guild.get_role(data['role_id'])
        if role:
            await role.delete()
        await log(ctx, EVENT_LOG_FILE, f"EDIT: Ended event for {data['title']}\n")
        await ctx.response.send_message("Le CTF à été archivé avec succès.")
        return None
    except ValueError:
        await ctx.response.send_message("Erreur lors de la récupération d'information.", ephemeral=True)
        return 1






""" TRASH COMMAND TO BE REBUILT LATER"""
"""
@bot.tree.command(name="vote", description="start the vote on current channel's CTF. (only if over)", guild=discord.Object(id=DISCORD_GUILD_ID))
async def event_democracy(ctx: discord.integrations, grade: Literal["Absolute Trash", "Not Worth", "OK tier", "Banger"]):
    #Allow users to give a grade to an event between 4 different possibilities


    #retrieve the CTF data (and users_vote if existing)
    try:
        data = {} # keep or will crash if no file found
        channel_id = ctx.channel.id # used for search
        event_list = list_directory_contents(f"{CURRENT_CTF_DIR}{ctx.guild.id}")
        for event_file in event_list:
            if str(channel_id) in event_file:
                with open(f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file}", 'r') as data:
                    data = json.load(data)
                    users_vote = data['users_vote']
                    break
        if not data:
            await ctx.response.send_message(f"No event could be found for this channel. please make sure you use this command in a CTF channel. (/listevents) (you cannot vote for a CTF that was ended)", ephemeral=True)
            return 1
    except ValueError:
        await ctx.response.send_message("Error retrieving the info.", ephemeral=True)
        return 1

    #Set the users vote as grade's value
    try:
        users_vote[ctx.user.id] = grade
        data['users_vote'] = users_vote
        with open(f"{CURRENT_CTF_DIR}{ctx.guild.id}/{event_file}", 'w') as file:
            json.dump(data, file, indent=4)
        await ctx.response.send_message(f"Your vote has been registered ! ({grade})")
        return None
    except ValueError:
        await ctx.response.send_message("Error during the voting process.", ephemeral=True)
        return 1



idée 1 :
faire en sorte qu'il envoie un message privé à chaque personne avec le bon role et propose de voter par emoji, message ou intéraction,

idée 2 :
lance un message embedded dans le salon avec des émojis ou des bouttons pour voter et enregistre le vote par l'id discord avec un overwrite si la personne vote à nouveau

"""






"""HELP"""
@bot.tree.command(name="help", description="Help command.", guild=discord.Object(id=DISCORD_GUILD_ID))
async def event_summary(ctx: discord.Interaction, commands: Literal["memberize", "listevents", "upcoming", "refresh", "search", "registered_search", "quickadd", "info, description, vote, end"]):


    error_server="Si la commande ne répond pas il s'agit surement d'une erreur serveur.\nSVP contacter un admin pour qu'il puisse vérifier."

    if commands == "memberize":
        com = "Memberize"
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} transforme l'utilisateur spécifié en membre.\nCela lui donne le role de membre sur le serveur Discord et le CTFd.",
            color=discord.Color.pink()
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/{com} [user]`"
        usage_exemple = f"`/{com}`"
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande ", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)
    elif commands == "listevents":
        com="Listevents"
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} est une commande pour afficher les évènements actuellement disponible sur le serveur.\nelle informe l'utilisateur :\n- le weight (difficulter de l'évènement selon CTFTIME de 0 à 100)\n- Quand l'évènement commence\n- Son ID (spécifique au Bot CTFREI pour /registered_search)\n- Le salon d'évènement et le lien du message pour rejoindre si jamais vous n'avez pas accès au salon.",
            color=discord.Color.pink()  # Color of the side bar (you can change the color)
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/{com} [aucun argument]`"
        usage_exemple = f"`/{com}`"
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande ", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)

    elif commands == "upcoming":
        com="Upcoming"
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} est une commande pour afficher les X (par défaut {MAX_EVENT_LIMIT}) prochains évènements CTFs à venir selon CTFTIME .\nIl récupère les informations à partir d'un fichier cache qui est mis à jour toutes les 24h (ou à chaque /refresh), et donne à l'utilisateur :\n- Le nom de l'évènement\n- Le Weight (difficulter de l'évènement selon CTFTIME de 0 à 100)\n- Le format de l'évènement\n- La date à laquelle le CTF commence.",
            color=discord.Color.pink()  # Color of the side bar (you can change the color)
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/{com} [Nombre (OPTIONNEL)->INT]`"
        usage_exemple = f"`/{com}`\n`/{com} 15`"
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)
        embeded_message.add_field(name=f"**{com}** Description des Options ", value=f"Cette valeur défini le nombre totale d'évènement à afficher.\nLa valeur par défaut est {MAX_EVENT_LIMIT} et le maximum est 25.", inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)

    elif commands == "refresh":
        com="Refresh"
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} est une commande qui permet de raffraichir le fichier cache contenant tout les CTFs de CTFTIME.\nCette function est lancé automatiquement toute les 24h mais vous pouvez toujours la lancer si besoin.",
            color=discord.Color.pink()  # Color of the side bar (you can change the color)
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/{com} [aucun argument]`"
        usage_exemple = f"`/{com}`"
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)

    elif commands == "search":
        com="Search"
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} est une commande pour récupérer les informations sur les __PROCHAINS__ CTFs.\nCette commande prend 2 forme de queries, elle peut chercher à partir d'un nom/mot, ou utiliser un chiffre pour chercher par difficulté (la marge est de {WEIGHT_RANGE_GENERAL}), Le resultat est sous forme de liste.",
            color=discord.Color.pink()  # Color of the side bar (you can change the color)
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/{com} [query: INT ou query: STR]`"
        usage_exemple = f"`/{com} HTB`\n`/{com} 20`\n`/{com} LakeCTF Quals 24-25`"
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)
        embeded_message.add_field(name=f"**{com}** Description des Options", value=f"La **recherche par nom/mots** est une simple recherche par string (non case sensitive).\n\nLa **recherche par weight** utiliser une portée de recherche comme marge (par défaut {WEIGHT_RANGE_GENERAL}) ce qui permet de lister les prochains évènements à travers un éventail de difficulté, par exemple si vous chercher avec le weight \"20\" vous obtiendrez une liste d'évènement entre {0 if (16-WEIGHT_RANGE_GENERAL<0) else (16-WEIGHT_RANGE_GENERAL)} and {100 if (16+WEIGHT_RANGE_GENERAL>=100) else (16+WEIGHT_RANGE_GENERAL)}.", inline=False)
        embeded_message.add_field(name=f"**{com}** Information des Options", value="Pour la recherche par nom/mot le string doit être d'au moins 3 charactères de long.\nPour la recherche par weight, le nom doit être au maximum de 2 unités (0-99) et ne doit pas être un float.", inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)

    elif commands == "registered_search":
        com="Registered_search"
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} est une commande pour récupérer plus d'information sur des CTFs __en cours__ et enregistrés sur le serveur\nElle peut prendre en entrer l'ID de l'évènement (/listevents pour les voir), vous pouvez aussi lui donner le nom du role associé à l'évènement.",
            color=discord.Color.pink()  # Color of the side bar (you can change the color)
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/{com} [id: STR ou role: STR]`"
        usage_exemple = f"`/{com} d62cd16c`\n`/{com} exemple_quals_2024`"
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)

    elif commands == "quickadd":
        com="Quickadd"
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} est la commande pour ajouter des évènements au serveur à partir des informations CTFTIME.\nPour enregistrer un nouvelle évènement vous aurez besoin de :\n- Donner le nom du CTF comme il est écrit sur CTFTIME, comme c'est montré dans la sortie de `/upcoming`.\n- de créer un nom pour le role qui sera utilisé.",
            color=discord.Color.pink()  # Color of the side bar (you can change the color)
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/{com} [rolename: STR] [ctfname: STR]`"
        usage_exemple = f"`/{com} htb_uni_2024 HTB University CTF 2024`\n`/{com} saarCTF_2024 saarCTF 2024`"
        restrictions = ("Ils existent différentes restrictions pour que cette commande aboutisse."
                        "\nCes restrictions sont :"
                        "\n- Si aucun évènement n'a été trouvé,"
                        " ou si plus d'un évènement a été trouvé lors de la recherche."
                        "\n- Le CTF est déjà présent sur le serveur (`/listevents`)."
                        "\n- le nom du rôle existe déjà sur le serveur."
                        "\n- un salon avec ce nom (celui du rôle) existe déjà sur le serveur."
                        "\n- l'évènement est déjà fini (dans le cas ou le fichier cache n'aurait pas été mis à jour).")
        search_info = "**Note**: la fonction de recherche est exactement la meme que pour `/search`\nPour que la commande `/quickadd` fonctionne avec le nom de CTF que vous donnez vous devez vous assurez que `/search` fonctionne avec votre query."
        # role_format=""
        # role_warning=""
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)
        embeded_message.add_field(name=f"**{com}** Restrictions de Commande", value=restrictions, inline=False)
        embeded_message.add_field(name=f"**{com}** Mécanisme de recherche", value=search_info, inline=False)
        # embeded_message.add_field(name=f"**{com}** Format de nom de role", value=role_format, inline=False)
        # embeded_message.add_field(name=f"**{com}** Avertissement de Nom de Role", value=role_warning, inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)

    elif commands == "info, description, vote, end":
        com='"info", "description", ~~"vote"~~ and "end" commands'
        embeded_message = discord.Embed(
            title=f"__{com}__",
            description=f"{com} sont des commandes utilisées pour voir et gérer des salons CTF dédiés (ceux créés par le Bot), ces commandes peuvent **uniquement** être lancer à l'intérieur de salon CTF en cours, ces salons sont listés dans /listevents.",
            color=discord.Color.pink()  # Color of the side bar (you can change the color)
        )
        embeded_message.set_author(
            name="CTFREI HELP",
            url="https://github.com/ctf-efrei/ctfrei-web-front",
            icon_url=AUTHOR_ICON
        )

        format = f"`/info [no arguments]`\n`/description [no arguments]`\n`/vote [value: Litteral]`\n`/end [no arguments]`"
        usage_exemple = f"`/info`\n`/description`\n`/vote Banger`\n`/end`"
        embeded_message.set_footer(text=error_server, icon_url=FOOTER_ICON)
        embeded_message.add_field(name=f"**{com}** Format de Commande ", value=format, inline=False)
        embeded_message.add_field(name=f"**{com}** Exemple de Commande", value=usage_exemple, inline=False)
        embeded_message.add_field(name=f"**{com}** Information Importante", value="Ces commandes marche uniquement pour les évènement encore en cours, créés par le Bot et qui n'ont pas été archivés avec la commande /end", inline=False)

        await ctx.response.send_message(embed=embeded_message, ephemeral=True)
    else:
        await ctx.response.send_message("Utilise cette commande pour en apprendre plus sur les différentes commandes du Bot.", ephemeral=True)










"""BOT INITIAL SETUP, RESTART, SYNC, AND LOOP FUNCTIONS"""

@bot.command(name="setup-ctfrei") # run /setup-ctfrei first time the bot is on a server (will setup file directories for said server)
async def setup_dir(ctx: discord.integrations):
    """setup command for each server to setup the file system (does not appear as an actual command on servers)"""
    if not p.isdir(f"{CURRENT_CTF_DIR}{ctx.guild.id}"): # create server's dedicated dir in current
        mkdir(f"{CURRENT_CTF_DIR}{ctx.guild.id}")
        print(f"Discord CTF dir ({CURRENT_CTF_DIR}{ctx.guild.id}) has been created ")

    if not p.isdir(f"{PAST_CTF_DIR}{ctx.guild.id}"): # create server's dedicated dir in past
        mkdir(f"{PAST_CTF_DIR}{ctx.guild.id}")
        print(f"Discord CTF dir ({PAST_CTF_DIR}{ctx.guild.id}) has been created ")

    print(f"\nSERVER INFORMATIONS:\n\nServer: {ctx.guild.name}\nServer ID: {ctx.guild.id}\nCurrent Channel: {ctx.channel.id}\nCurrent Category: {ctx.channel.category.id}")


    if p.isdir(f"{CURRENT_CTF_DIR}{ctx.guild.id}") and p.isdir(f"{PAST_CTF_DIR}{ctx.guild.id}") and p.isfile(UPCOMING_CTFTIME_FILE):
        return 0
    else:
        print("something went wrong during the setup")
        return 1

@bot.tree.command(name="sync", description="commande pour sync les commandes (dev only)")
async def sync(ctx: discord.Interaction):
    """sync commands with the given DISCORD_GUILD_ID"""
    await ctx.response.defer(ephemeral=True)
    await log(ctx, EVENT_LOG_FILE, f"REQ: Synced the Bot\n")
    await bot.tree.sync(guild=discord.Object(id=DISCORD_GUILD_ID))
    await refresh_interactions(ctx.guild.id, CTF_JOIN_CHANNEL[ctx.guild.name])
    await ctx.edit_original_response(content="Commands & interactions synced successfully!")

async def refresh_interactions(discord_guild_id, Channels_id):
    """function to refresh the interactions that are not expired post restart"""
    if persistent_data:
        found= [] # To keep track of messages that were found
        not_found = []  # To keep track of messages that were not found
        for channel_id in Channels_id:
            guild = bot.get_guild(discord_guild_id)  # The server to refresh
            channel = guild.get_channel(channel_id)  # The channel to refresh

            if channel:
                print(f"Refreshing interactions in channel: {channel.name} ({channel.id})")

                for message_id, data in list(persistent_data.items()):  # Iterate through a copy to allow modification
                    finish_date = data["finish"]  # Retrieve finish date
                    end_time = datetime.fromisoformat(finish_date).timestamp()
                    current = datetime.now().timestamp()
                    timeout_timer = end_time - current  # Calculate time remaining

                    try :
                        message = await channel.fetch_message(int(message_id))

                    except discord.NotFound:
                        print(f"Le message {message_id} n'a pas été trouvé dans {channel.name}.")
                        not_found.append(message_id)  # Keep track of not found messages
                        continue


                    # Check if the timeout has expired
                    if timeout_timer < 0:
                        # Delete the expired message's button and remove its record
                        # await message.delete() # this delete the whole message
                        await message.edit(view=None) # this delete the button from the message
                        print(f"Le bouton de {message_id} à été supprimé car le CTF est terminé.")
                        del persistent_data[message_id]
                        save_persistent_data(persistent_data)
                        continue  # Skip further processing for this message if timer's out

                    else: # the timer is still running
                        # Refresh the message with the new timeout
                        role = discord.utils.get(channel.guild.roles, id=data["role_id"])
                        if role:
                            view = PersistentView(role)
                            view.timeout = timeout_timer  # Set the remaining timeout
                            await message.edit(view=view)  # Re-attach the view
                            print(f"Vue raffraichi pour {message_id} avec un timeout de {timeout_timer} secondes.")
                            found.append(message_id)  # Keep track of found messages
                        else:
                            print(f"Le rôle {data['role_id']} n'a pas été trouvé dans le serveur {channel.guild.name} pour le message {message_id}.")
                            not_found.append(message_id)
            else:
                print(f"le salon avec l'id {channel_id} n'a pas été trouvé.")


        # Remove any messages that were not found from persistent_data
        if not_found:
            to_remove = set(not_found) - set(found)
            for message_id in to_remove:
                if message_id in persistent_data:
                    del persistent_data[message_id]
                    print(f"Le message {message_id} à été supprimé des intéractions.")
            if to_remove:
                save_persistent_data(persistent_data)
    else:
        print("Aucune interaction à raffraichir n'a été trouvé.")

"""refresh every 24h of event cache"""
@tasks.loop(hours=24)
async def automatic_refresh():
    try:
        api_call("https://ctftime.org/api/v1/events/?limit=100", UPCOMING_CTFTIME_FILE)
    except Exception as e:
        print(f"Refresh now: {e}")

def loops_check(message):
    with open("./loops.log", "w") as file:
        file.write(message)


@tasks.loop(hours=12, minutes=1)  # Runs every Wednesday at 12:00 UTC
async def weekly_refresh():
    """look at the list of upcoming CTFs and sends a message with 5 CTFs where the difficulty is within 20 to 40"""

    loops_check("loop started")

    if datetime.today().isoweekday() != DAY_OF_WEEK_RECOMMENDATION :  # Check if today is monday
        return

    data = await search_ctf_data(UPCOMING_CTFTIME_FILE, str(WEIGHT_START_RECOMMENDATION), int(WEIGHT_RANGE_RECOMMENDATION))

    # check if any are coming in the next X weeks
    now = datetime.now(timezone.utc)
    x_weeks_later = now + timedelta(weeks=WEEKS_RANGE_RECOMMENDATION)
    data = [
        event for event in data
        if datetime.fromisoformat(event['start']).replace(tzinfo=timezone.utc) <= x_weeks_later
    ]
    if not data:
        print(f"Aucun CTFs n'ont pu être trouvés entre {0 if (WEIGHT_START_RECOMMENDATION - WEIGHT_RANGE_RECOMMENDATION) < 0 else (WEIGHT_START_RECOMMENDATION - WEIGHT_RANGE_RECOMMENDATION)} et {100 if (WEIGHT_START_RECOMMENDATION + WEIGHT_RANGE_RECOMMENDATION) > 100 else (WEIGHT_START_RECOMMENDATION + WEIGHT_RANGE_RECOMMENDATION)} de weight dans les {WEEKS_RANGE_RECOMMENDATION} prochaines semaines.", ephemeral=True)
        return None


    if DISABLE_ZERO_WEIGHT_RECOMMENDATION:
        data = [event for event in data if event['weight'] > 0]

    #orders data by date
    data.sort(key=lambda x: datetime.fromisoformat(x['start']).replace(tzinfo=timezone.utc))
    print(f"Data sorted by date: {len(data)} events found.")

    # get the discord server by ID
    guild = bot.get_guild(DISCORD_GUILD_ID)
    join_channelid = CTF_JOIN_CHANNEL[guild.name]
    join_channel = guild.get_channel(join_channelid)


    # prepare the embeded message for discord limiting to NUMBER_OF_RECOMMENDATIONS
    embeded_message = discord.Embed(
        title="Recommendations de CTFs à venir",
        description=f"Voici les CTFs qui correspondent aux critères suivant : Weight de `{0 if (WEIGHT_START_RECOMMENDATION - WEIGHT_RANGE_RECOMMENDATION) < 0 else (WEIGHT_START_RECOMMENDATION - WEIGHT_RANGE_RECOMMENDATION)} à {100 if (WEIGHT_START_RECOMMENDATION + WEIGHT_RANGE_RECOMMENDATION) > 100 else (WEIGHT_START_RECOMMENDATION + WEIGHT_RANGE_RECOMMENDATION)}` dans les `{WEEKS_RANGE_RECOMMENDATION}` prochaines semaines:",
        color=discord.Color.dark_gold()
    )

    await join_channel.send(embed=embeded_message)

    for CTF in data[:NUMBER_OF_RECOMMENDATIONS]:

        # prepare the embeded message for discord limiting to NUMBER_OF_RECOMMENDATIONS
        embeded_message = discord.Embed(
            title=f"__**{CTF['title']}**__",
            description=f"CTF de type {CTF['format']} - Onsite: {CTF['onsite']} - Location: {CTF['location'] if CTF['location'] else 'ONLINE'}",
            color=discord.Color.gold()
        )

        embeded_message.set_author(name="CTFREI RECOMMENDATION AUTOMATIQUE",icon_url="https://www.efrei.fr/wp-content/uploads/2024/07/ctefrei.png")

        if CTF['logo']:
            embeded_message.set_thumbnail(url=CTF['logo'])

        embeded_message.add_field(name=f"**Informations :**", value=f":stopwatch: durée du CTF : {(int(CTF['duration']['days'])*24) + (CTF['duration']['hours'])} heures\n:man_lifting_weights: Weight estimé {CTF['weight'] if int(CTF['weight']) != 0 else 'inconnu'}", inline=True)

        embeded_message.add_field(name="**URI links:**", value=f"<:ctftime:1320354001287647264> [CTFTIME]({CTF['ctftime_url']})\n<:site:1320352422056693821> [CTFd]({CTF['url']})\n", inline=True)

        embeded_message.add_field(name="# **Dates:**", value=f":date: Du <t:{int((datetime.fromisoformat(CTF['start'])).timestamp())}:F> au <t:{int((datetime.fromisoformat(CTF['finish'])).timestamp())}:F>", inline=False)

        embeded_message.add_field(name="**Description:**", value=f"{CTF['description'][:1200:]}", inline=False)

        await join_channel.send(embed=embeded_message)










#"""DEV COMMANDS (DELETE/COMMENT BEFORE PRODUCTION)"""

#@bot.tree.command(name="test", description="dev testing command", guild=discord.Object(id=DISCORD_GUILD_ID))
#async def testing_command(ctx, cmd: str):

#    print("test")









"""BOT STARTING AND CHECKING"""

async def basic_setup():
    """minimum necessary to start the bot, is checked as startup"""
    try:
        if not p.isdir('log'):
            mkdir('log')
            print(f"Current CTF dir ('/log') has been created.")

        if not p.isdir(CURRENT_CTF_DIR): # check for current CTF dir
            mkdir(CURRENT_CTF_DIR)
            print(f"Current CTF dir ({CURRENT_CTF_DIR}) has been created ")

        if not p.isdir(PAST_CTF_DIR): # check for past CTF dir
            mkdir(PAST_CTF_DIR)
            print(f"Past CTF dir ({PAST_CTF_DIR}) has been created ")

        if not p.isfile(UPCOMING_CTFTIME_FILE):
            temp = {}
            with open(UPCOMING_CTFTIME_FILE, 'x') as filecreation:
                json.dump(temp, filecreation)

        if not p.isfile(EVENT_LOG_FILE):
            with open(EVENT_LOG_FILE, 'x') as filecreation:
                filecreation.write("Here starts the log file for the CTFREI bot.\n")

        if not p.isfile(INTERACTION_SAVE_FILE):
            with open(INTERACTION_SAVE_FILE, 'x') as filecreation:
                filecreation.write('{}')

        print('SETUP HAS BEEN CHECKED')
        return None
    except ValueError:
        print("Error during SETUP CHECKING")
        return 1

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await guild.chunk()

    if "testing_command" in globals(): # make sure the testing command is not running in production
        print("#"*20, "\n\nIMPORTANT : THE TESTING COMMAND IS ON (line ~892), PLEASE REMOVE IT BEFORE PRODUCTION.\n\n", "#"*20)

    if "sync" in globals():
        print("#"*20, "\n\nNote : THE SYNC COMMAND IS ON (line ~780).\n\n", "#"*20)

    """bot startup routine"""
    await basic_setup()
    await bot.tree.sync()
    await refresh_interactions(DISCORD_GUILD_ID, [CTF_JOIN_CHANNEL['CTFREI'], CTF_ANNOUNCE_CHANNEL['CTFREI']['channel_id']]) # refresh all current interactions, and delete old join interactions
    automatic_refresh.start()
    weekly_refresh.start()
    print(f'Logged in as {bot.user}')
    loops_check("bot restarted")

async def start_bot():
    await bot.start(TOKEN)

async def main():
    from registering import app
    # bot_task = asyncio.create_task(start_bot())
    server = uvicorn.Server(config=uvicorn.Config(app, host="0.0.0.0", port=5000, log_level="info"))
    api_task = asyncio.create_task(server.serve())

    print("Serving...")

    await asyncio.gather(api_task)


if CTFREI == '__GOATS__': # FACT
    asyncio.run(main())
    bot.run(TOKEN)
