import discord
from discord import channel
from discord import member
import discord.ext.commands
import json
import time
import math
import random
import threading

# Bot permissions: 16780288
# On breakout command: Find all rooms that start with "Breakout", divide the
# number of people by the number of rooms and move people randomly into the
# breakout rooms

# Format
# {
#   server: {
#     initiator's user id: {
#       "return_channel": channel_name
#       "breakout_channels": ["Breakout1", "Breakout2"]
#     }
#   }
# }
state = {}

BREAKOUT_ROOM_PREFIX = "Breakout"

intents = discord.Intents.default()
# Without this we can't see the members of channels
intents.members = True
bot = discord.ext.commands.Bot(command_prefix="!br ", pm_help=True, intents=intents)

@bot.command(name="start")
async def breakout(ctx, persons_per_room_str = None):
    server_state = state.setdefault(ctx.message.guild.name, {})
    initiator_id = ctx.message.author.id
    initiator_channel = ctx.message.author.voice.channel
    if initiator_id in server_state:
        print("Author with active session is attempting to create a new one. Aborting.")
        await ctx.send("Breakout session already active, stop it with !stop first")
        return

    channel_members = initiator_channel.members
    print(f"initiator_channel: {initiator_channel}; initiator_channel.members: {channel_members}")

    attendees = {}
    for member in channel_members:
        attendees[member.id] = storage["users"].get(str(member.id), {"number_of_people": 1}).copy()
        attendees[member.id]["user"] = member

    print(f"attendees: {attendees}")

    abomination = sorted([(user["number_of_people"], user["user"]) for user in attendees.values()], key=lambda x:x[0], reverse=True)
    potential_breakout_session = [room for room in ctx.message.guild.voice_channels if room.name.startswith(BREAKOUT_ROOM_PREFIX)]    
    number_of_people = sum(i for i, _ in abomination)

    print(f"abomination: {abomination}; potential_breakout_session: {potential_breakout_session}; number_of_people: {number_of_people}")

    if persons_per_room_str is None:
        persons_per_room = max(math.floor(number_of_people / len(potential_breakout_session)), 2)
    else:
        try:
            persons_per_room = int(persons_per_room_str)
        except Exception as e:
            print(f"Number conversion error: {e}")
            await ctx.send("Could not convert input into number, please try again")
            return
        if (persons_per_room * len(potential_breakout_session)) < number_of_people:
            print("Insufficient amount of breakout channels. Aborting.")
            await ctx.send("Please create more breakout rooms")
            return

    number_of_rooms_used = math.floor(number_of_people / persons_per_room)
    print(f"number_of_rooms_used: {number_of_rooms_used}")

    server_state[initiator_id] = {
        "return_channel": ctx.message.author.voice.channel,
        "breakout_channels": potential_breakout_session[:number_of_rooms_used]
    }

    crazy_channels = [{"room": room, "persons_in_room": 0} for room in server_state[initiator_id]["breakout_channels"]]
    current_channel_index = 0
    persons_moved = 0
    for persons, user in abomination:
        print(f"crazy_channels: {crazy_channels}; current_channel_index: {current_channel_index}; persons_moved: {persons_moved}")
        if current_channel_index == 0:
            random.shuffle(crazy_channels)

        if crazy_channels[current_channel_index]["persons_in_room"] >= persons_per_room and persons_moved < persons_per_room * number_of_rooms_used:
            continue

        print(f"Moving {user} to {crazy_channels[current_channel_index]['room']}")
        await user.move_to(crazy_channels[current_channel_index]["room"])
        persons_moved += persons
        crazy_channels[current_channel_index]["persons_in_room"] += persons
        
        current_channel_index = (current_channel_index + 1) % number_of_rooms_used

    print("Done moving people")
    await ctx.send("Breakout session started")
        
@bot.command(name="stop")
async def breakin(ctx, seconds_str = None):
    if seconds_str is None:
        seconds = 0
    else:
        try:
            seconds = int(seconds_str)
        except Exception as e:
            print(f"Number conversion error: {e}")
            await ctx.send("Could not convert input into number, please try again")
            return
    
    server_name = ctx.message.guild.name
    author_id = ctx.message.author.id
    if server_name not in state or author_id not in state[server_name]:
        print(f"No active breakout sessions for server {server_name} and user {author_id}")
        await ctx.send("No active breakout session found, did you start one?")
        return

    session = state[server_name][author_id]
    return_channel = session["return_channel"]

    await ctx.send(f"Stopping breakout channels in {seconds} seconds")
    time.sleep(seconds)
    for room in session["breakout_channels"]:
        for member in room.members:
            print(f"Moving {member} to {return_channel}")
            await member.move_to(return_channel)
    print("Done moving people back!")

    del state[server_name][author_id]
    if not state[server_name]:
        del state[server_name]

    await ctx.send("Breakout session finished")

@bot.command(name="weare")
async def store_number_of_people_for_user(ctx, num_str = None):
    print(f"{ctx.message.author.id}: {num_str}")
    await store_members_for_user_id(ctx, num_str, ctx.message.author.id)

@bot.command(name="theyare")
async def store_number_of_people_for_different_user(ctx, member_id = None, num_str = None):
    print(f"{ctx.message.author.id} set number of people for {member_id} to {num_str}")
    await store_members_for_user_id(ctx, num_str, member_id)

@bot.command(name="howmany")
async def get_number_of_people_for_user(ctx, member_id_str = None):
    author_id = ctx.message.author.id
    if member_id_str is None:
        member_id_str = str(author_id)
    print(f"{author_id} requested how many they are for {member_id_str}")
    user_storage = storage["users"].get(member_id_str, {"number_of_people": 1})
    await ctx.send(f"{ctx.message.guild.get_member(int(member_id_str)).display_name} are {user_storage['number_of_people']}")

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')

async def store_members_for_user_id(ctx, num_str, user_id_str):
    try:
        num = int(num_str)
    except Exception as e:
        print(f"Number conversion error: {e}")
        await ctx.send("Could not convert input into number, please try again")
        return
    if num <= 0:
        print("Someone tried to be less than 1 person")
        await ctx.send(f"You are more than that to me <3")
        return

    user_storage = storage["users"].setdefault(user_id_str, {})
    user_storage["number_of_people"] = num
    save_storage()
    await ctx.send(f"Set {ctx.message.guild.get_member(int(user_id_str)).display_name} to {num} people :)")

    

def save_storage():
    print(f"Saving storage: {storage}")
    with storage_lock:
        with open("storage.json", "w") as f:
            json.dump(storage, f)

def main():
    with open(".secrets.json", "r") as f:
        secrets = json.load(f)

    # Format
    # {
    #   "users": {
    #     user_id: {
    #       "number_of_people": 42
    #     }
    #   }
    # }
    with open("storage.json", "r") as f:
        global storage
        storage = json.load(f)

    global storage_lock
    storage_lock = threading.Lock()

    bot.run(secrets["token"])

if __name__ == "__main__":
    main()