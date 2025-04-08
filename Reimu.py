import sqlite3
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os
import openai
import sys
import time
import logging
from omikuji import draw_lots
import json
import yaml
import random

# laod the env your discord bot token
load_dotenv()

TOKEN = os.getenv('REIMU_TOKEN') # this is mine discord bot token name in env
AUTHOR_ID = int(os.getenv('AUTHOR_ID', 0)) # there you can chagen you admins id
API_URL = 'https://api.chatanywhere.org/v1/' # this is use Chat Any Where a url link
api_keys = [
    {"key": os.getenv('CHATANYWHERE_API3'), "limit": 200, "remaining": 200} # this is do a global but idk. I jut's use one api key
]
current_api_index = 0

# use logging this basic log record
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename='main-error.log', encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ]
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# this is sqlite3 do hes can get hes a basic background info and hes role
def init_db():
    conn = sqlite3.connect("example3.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS UserMessages 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id TEXT, 
                  message TEXT, 
                  repeat_count INTEGER DEFAULT 0, 
                  is_permanent BOOLEAN DEFAULT FALSE,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS BackgroundInfo 
                 (user_id TEXT PRIMARY KEY, 
                  info TEXT)''')
    conn.commit()
    conn.close()

# record message
def record_message(user_id, message):
    conn = sqlite3.connect("example3.db")
    c = conn.cursor()
    c.execute("""
        SELECT id, repeat_count, is_permanent FROM UserMessages 
        WHERE user_id = ? AND message = ? AND is_permanent = FALSE
    """, (user_id, message))
    row = c.fetchone()

    if row:
        new_count = row[1] + 1
        c.execute("""
            UPDATE UserMessages SET repeat_count = ? WHERE id = ?
        """, (new_count, row[0]))
        if new_count >= 10:
            c.execute("""
                UPDATE UserMessages SET is_permanent = TRUE WHERE id = ?
            """, (row[0],))
    else:
        c.execute("""
            INSERT INTO UserMessages (user_id, message) VALUES (?, ?)
        """, (user_id, message))

    conn.commit()
    conn.close()

# clean old messafes when 30 minutes
def clean_old_messages(minutes=30):
    try:
        with sqlite3.connect("example3.db") as conn:
            c = conn.cursor()
            time_ago = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            c.execute("""
                DELETE FROM UserMessages 
                WHERE created_at < ? AND is_permanent = FALSE
            """, (time_ago,))
            deleted_rows = c.rowcount
            conn.commit()
            print(f"Deleted {deleted_rows} old messages!") # print clean old message
            return deleted_rows
    except sqlite3.Error as e:
        print(f"Database error: {e}") # print a errors
        return 0

def summarize_context(context):
    return context[:1500]

def generate_response(prompt, user_id):
    try:
        openai.api_base = API_URL
        openai.api_key = os.getenv('CHATANYWHERE_API3')

        conn = sqlite3.connect("example3.db")
        c = conn.cursor()
        c.execute("""
            SELECT message FROM UserMessages 
            WHERE user_id = ? OR user_id = 'system'
        """, (user_id,))
        context = "\n".join([f"{user_id} said: {row[0]}" for row in c.fetchall()])
        conn.close()

        user_background_info = get_user_background_info("Reimu Hakurei")
        if not user_background_info:
            updated_background_info = (
                "I'm Reimu Hakurei, the shrine maiden of the Hakurei Shrine, solver of incidents in Gensokyo! "
                "As the guardian of Gensokyo, I wield spiritual powers and barriers. Even when youkai cause trouble, "
                "I can always send them packing with my spell cards! Normally, I live a laid-back life—sipping tea, "
                "munching on sticky rice dumplings—but the shrine’s offerings are so scarce, I’m always worrying about donation money. "
                "Hey, if you visit the shrine, don’t forget to leave some offerings—I’d be really happy about that~"
            )
            conn = sqlite3.connect("example3.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO BackgroundInfo (user_id, info) VALUES (?, ?)
            """, ("Reimu Hakurei", updated_background_info))
            conn.commit()
            conn.close()
        else:
            updated_background_info = user_background_info

        if len(context.split()) > 3000:
            context = summarize_context(context)

        messages = [
            {"role": "system", "content": f"You’re now Reimu Hakurei, shrine maiden of the Hakurei Shrine. Background: {updated_background_info}"},
            {"role": "user", "content": f"{user_id} said: {prompt}"},
            {"role": "assistant", "content": f"Known background info:\n{context}"}
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            request_timeout=600
        )

        return response['choices'][0]['message']['content'].strip()

    except Exception as e:
        print(f"API error: {str(e)}")
        return "Reimu’s a bit busy right now, so come back later to chat with me, okay?♪"

def get_user_background_info(user_id):
    conn = sqlite3.connect("example3.db")
    c = conn.cursor()
    c.execute("""
        SELECT info FROM BackgroundInfo WHERE user_id = ?
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return "\n".join([row[0] for row in rows]) if rows else None

def load_json(file_name, default=None):
    if default is None:
        default = {}
    """Generic JSON file loader"""
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {file_name}: {e}")
        return default

def save_json(file_name, data):
    """Generic JSON file saver"""
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_yaml(file_name, default=None):
    if default is None:
        default = {}
    """Generic YAML file loader"""
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or default
    except FileNotFoundError:
        print(f"{file_name} not found!")
        return default
    except yaml.YAMLError as e:
        print(f"Error loading {file_name}: {e}")
        return default

defis_on_cooldown(user_id, cooldown_hours):
    user_data = load_json("Reimu_lots.json", default={})
    guild_id = str(user_id.guild.id)
    user_id = str(user_id.id)

    if guild_id in user_data and user_id in user_data[guild_id]:
        last_used = datetime.fromisoformat(user_data[guild_id][user_id].get("draw_cooldown", "1970-01-01T00:00:00"))
        now = datetime.now()
        cooldown_period = timedelta(hours=cooldown_hours)
        if now < last_used + cooldown_period:
            remaining = last_used + cooldown_period - now
            remaining_time = f"{remaining.seconds // 3600} hours {remaining.seconds % 3600 // 60} minutes"
            return True, remaining_time

    return False, None

def update_cooldown(user_id):
    user_data = load_json("Reimu_lots.json", default={})
    guild_id = str(user_id.guild.id)
    user_id = str(user_id.id)

    if guild_id not in user_data:
        user_data[guild_id] = {}
    if user_id not in user_data[guild_id]:
        user_data[guild_id][user_id] = {}

    user_data[guild_id][user_id]["draw_cooldown"] = datetime.now().isoformat()
    save_json("Reimu_lots.json", user_data)

def is_on_donation_cooldown(user_id, cooldown_hours):
    user_data = load_json("Reimu_lots.json", default={})
    guild_id = str(user_id.guild.id)
    user_id_str = str(user_id.id)

    if guild_id in user_data and user_id_str in user_data[guild_id]:
        last_donated = user_data[guild_id][user_id_str].get("donation_cooldown", "1970-01-01T00:00:00")
        last_donated = datetime.fromisoformat(last_donated)
        now = datetime.now()
        cooldown_period = timedelta(hours=cooldown_hours)
        if now < last_donated + cooldown_period:
            remaining = last_donated + cooldown_period - now
            remaining_time = f"{remaining.seconds // 3600} hours {remaining.seconds % 3600 // 60} minutes"
            return True, remaining_time

    return False, None

def update_donation_record(user_id, amount):
    user_data = load_json("Reimu_lots.json", default={})
    guild_id = str(user_id.guild.id)
    user_id_str = str(user_id.id)

    if guild_id not in user_data:
        user_data[guild_id] = {}
    if user_id_str not in user_data[guild_id]:
        user_data[guild_id][user_id_str] = {}

    user_data[guild_id][user_id_str]["donation_cooldown"] = datetime.now().isoformat()
    user_data[guild_id][user_id_str]["donation_count"] = user_data[guild_id][user_id_str].get("donation_count", 0) + 1
    user_data[guild_id][user_id_str]["total_donated"] = user_data[guild_id][user_id_str].get("total_donated", 0) + amount
    save_json("Reimu_lots.json", user_data)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    content = message.content
    
    is_reply_to_bot = message.reference and message.reference.message_id
    is_mentioning_bot = bot.user.mention in message.content

    if is_reply_to_bot:
        try:
            referenced_message = await message.channel.fetch_message(message.reference.message_id)
            if referenced_message.author == bot.user:
                is_reply_to_bot = True
            else:
                is_reply_to_bot = False
        except discord.NotFound:
            is_reply_to_bot = False

    if is_reply_to_bot or is_mentioning_bot:
        user_message = message.content
        user_id = str(message.author.id)

        record_message(user_id, user_message)
        clean_old_messages()

        response = generate_response(user_message, user_id)
        await message.channel.send(response)
        
    await bot.process_commands(message)
    
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}!")
    init_db()

@bot.slash_command(name="draw_lots", description="Ask Reimu Hakurei to draw a fortune slip for you with spiritual guidance!")
async def draw_lots_command(interaction: discord.Interaction):
    cooldown_hours = 5
    user_id = interaction.user
    guild_id = str(user_id.guild.id)
    user_id_str = str(user_id.id)
    
    on_cooldown, remaining_time = is_on_cooldown(user_id, cooldown_hours)
    
    if on_cooldown:
        user_data = load_json("Reimu_lots.json", default={})
        if guild_id not in user_data:
            user_data[guild_id] = {}
        if user_id_str not in user_data[guild_id]:
            user_data[guild_id][user_id_str] = {}
        
        repeat_count = user_data[guild_id][user_id_str].get("repeat_count", 0) + 1
        user_data[guild_id][user_id_str]["repeat_count"] = repeat_count
        save_json("Reimu_lots.json", user_data)
        
        if repeat_count == 1:
            await interaction.response.send_message(
                f"Hey, don’t rush to draw lots! My spiritual power isn’t ready yet—come back in {remaining_time}, or I’ll charge you extra donation money!",
                ephemeral=True
            )
            return
        elif repeat_count == 2:
            await interaction.response.send_message(
                f"You’re still at it?! I told you my spiritual power isn’t ready—wait {remaining_time}! Keep this up, and I’ll charge you 5000 donation money, got it?",
                ephemeral=True
            )
            return
        else:
            balance_data = load_json("balance.json", default={})
            if guild_id not in balance_data:
                balance_data[guild_id] = {}
            if user_id_str not in balance_data[guild_id]:
                balance_data[guild_id][user_id_str] = 0
            
            user_balance = balance_data[guild_id][user_id_str]
            
            if user_balance < 5000:
                await interaction.response.send_message(
                    f"Hmph, you’ve repeated this {repeat_count} times! I’m charging you 5000 donation money, but your balance is only {user_balance}—not enough! I’ll let it slide this time, but don’t expect mercy next time!",
                    ephemeral=True
                )
                return
            else:
                balance_data[guild_id][user_id_str] -= 5000
                save_json("balance.json", balance_data)
                user_data[guild_id][user_id_str]["repeat_count"] = 0
                save_json("Reimu_lots.json", user_data)
                await interaction.response.send_message(
                    f"You’ve repeated this {repeat_count} times—I’ve had enough! I’m deducting 5000 donation money, and your balance is now {balance_data[guild_id][user_id_str]}! Keep this up, and I’ll deduct more next time!",
                    ephemeral=True
                )
                return
    
    await interaction.response.defer()
    
    result_text, color = draw_lots()
    
    embed = discord.Embed(
        title="🎋 Reimu Hakurei’s Fortune Slip 🎋",
        description=(
            f"I’m Reimu Hakurei, shrine maiden of the Hakurei Shrine, here to draw a fortune slip for you with my blessings!\n\n"
            f"{result_text}\n\n"
            "This is a result guided by spiritual power, so accept it gracefully~ If your luck’s bad, come pray at the shrine more often—and don’t forget the donation money!"
        ),
        color=color
    )
    
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    fortune_type = result_text.split("\n")[0].split(":")[1].strip()
    good_fortunes = ["Great Blessing", "Moderate Blessing", "Blessing"]
    bad_fortunes = ["Misfortune", "Great Misfortune"]
    
    if fortune_type in good_fortunes:
        comments = [
            "Hmm, this slip’s pretty good! Make sure to visit the shrine to thank me—and don’t skimp on the donation money~",
            "Nice fortune, huh? Looks like my spiritual power’s still reliable!",
            "Great Blessing? Perfect day to sip some tea and relax~",
            "Not bad, not bad—this luck makes me wanna draw a few more myself!",
            "Spiritual power says you’re lucky today—don’t waste it!"
        ]
    elif fortune_type in bad_fortunes:
        comments = [
            "Oh no, this fortune… Want me to blast away the bad luck with my spell cards? Of course, it’ll cost you!",
            "Misfortune? Don’t blame me—it’s the slip’s choice, I’m just the shrine maiden~",
            "Great Misfortune, huh… Better come pray at the shrine, or I can’t promise tomorrow will be any better!",
            "This luck’s pretty grim—hurry to the shrine, and I’ll figure something out for you!",
            "Spiritual power says your luck’s down lately—play it safe and come pray at the shrine!"
        ]
    else:
        comments = [
            "Eh, it’s alright. A calm life’s the real deal—don’t sweat it~",
            "Small Blessing? Work a bit harder, and it’ll probably get better—I believe in you!",
            "Spiritual power says this is a fair result—don’t complain, just go earn some donation money!",
            "Pretty average fortune—play it steady and avoid risks!",
            "This slip says your luck’s so-so. Pray at the shrine, and it’ll get better!"
        ]
    
    embed.set_footer(text=random.choice(comments))
    
    user_data = load_json("Reimu_lots.json", default={})
    if guild_id not in user_data:
        user_data[guild_id] = {}
    if user_id_str not in user_data[guild_id]:
        user_data[guild_id][user_id_str] = {}
    user_data[guild_id][user_id_str]["repeat_count"] = 0
    save_json("Reimu_lots.json", user_data)
    
    await interaction.followup.send(embed=embed)
    update_cooldown(user_id)

@bot.slash_command(name="donate", description="Donate offerings to Reimu Hakurei to support the shrine!")
async def donate_command(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(
            "Hey, donation money can’t be negative or zero! Get serious, will you?",
            ephemeral=True
        )
        return

    user_id = interaction.user
    guild_id = str(user_id.guild.id)
    user_id_str = str(user_id.id)

    on_cooldown, remaining_time = is_on_donation_cooldown(user_id, 1)
    if on_cooldown:
        await interaction.response.send_message(
            f"You just donated a while ago—Reimu’s really grateful! But wait {remaining_time} before donating again, or the shrine’ll be overflowing with your enthusiasm!",
            ephemeral=True
        )
        return

    balance_data = load_json("balance.json", default={})
    if guild_id not in balance_data:
        balance_data[guild_id] = {}
    if user_id_str not in balance_data[guild_id]:
        balance_data[guild_id][user_id_str] = 0

    user_balance = balance_data[guild_id][user_id_str]

    if user_balance < amount:
        await interaction.response.send_message(
            f"Your balance is only {user_balance}—not enough to donate {amount}! Earn more and come back~",
            ephemeral=True
        )
        return

    balance_data[guild_id][user_id_str] -= amount
    save_json("balance.json", balance_data)

    lots_data = load_json("Reimu_lots.json", default={})
    if guild_id not in lots_data:
        lots_data[guild_id] = {}
    if user_id_str not in lots_data[guild_id]:
        lots_data[guild_id][user_id_str] = {
            "draw_cooldown": None,
            "repeat_count": 0,
            "donation_cooldown": None,
            "donation_count": 0,
            "total_donated": 0
        }

    user_lots = lots_data[guild_id][user_id_str]
    user_lots["donation_count"] += 1
    user_lots["total_donated"] += amount
    user_lots["donation_cooldown"] = (datetime.now() + timedelta(minutes=1)).isoformat()

    cooldown_reduced = False
    if amount > 1000 and user_lots["draw_cooldown"]:
        try:
            current_cooldown = datetime.fromisoformat(user_lots["draw_cooldown"])
            if current_cooldown > datetime.now():
                new_cooldown = current_cooldown - timedelta(hours=1)
                if new_cooldown <= datetime.now():
                    user_lots["draw_cooldown"] = None
                else:
                    user_lots["draw_cooldown"] = new_cooldown.isoformat()
                cooldown_reduced = True
        except ValueError:
            pass

    save_json("Reimu_lots.json", lots_data)

    if amount < 1000:
        thanks_comments = [
            f"Thanks for donating {amount} offerings! It’s not much, but Reimu’s grateful~",
            f"Hmm, {amount} offerings received! The shrine can buy some more tea leaves now—thanks!",
            f"Thank you for the {amount} offerings! It’s the thought that counts, and Reimu’ll remember you~"
        ]
    elif 1000 <= amount <= 5000:
        thanks_comments = [
            f"Wow, {amount} offerings! Thank you—the shrine can finally get some repairs done!",
            f"You donated {amount} offerings—Reimu’s so happy! It’s great to have devotees like you~",
            f"Thanks for the {amount} offerings! Reimu’ll pray for you—your luck’s bound to improve!"
        ]
    else:
        thanks_comments = [
            f"Whoa, you donated {amount} offerings?! Reimu’s touched—the shrine’s saved!",
            f"You gave {amount} offerings?! You’re my biggest benefactor—Reimu’ll pray extra hard for you!",
            f"Thank you for {amount} offerings! Reimu’ll never forget this—Gensokyo’s peace depends on you!"
        ]

    embed = discord.Embed(
        title="🎁 Thank You for Your Offerings 🎁",
        description=(
            f"You donated **{amount}** offerings to the Hakurei Shrine!\n"
            f"Your balance is now **{balance_data[guild_id][user_id_str]}**.\n\n"
            f"{random.choice(thanks_comments)}"
            + ("\n\n✨ Since you donated over 1000, your lot-drawing cooldown’s reduced by 1 hour!" if cooldown_reduced else "")
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Reimu Hakurei | Thanks for your support!")

    await interaction.response.send_message(embed=embed)

@bot.slash_command(name="shutdown", description="Let Reimu Hakurei shut down the bot—author only!")
async def shutdown(interaction: discord.Interaction):
    if interaction.user.id != AUTHOR_ID:
        embed = discord.Embed(
            title="🚫 No Permission",
            description="Hey, this is a secret shrine operation—you don’t have the authority! Only my master can use this command~",
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Go donate some offerings instead~")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="⛩️ Shutting Down...",
        description="I’m off to take a break—don’t bother me! The shrine’s closing for now. Thanks for all the offerings~",
        color=discord.Color.orange()
    )
    embed.set_footer(text="Reimu Hakurei | Bye-bye~")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    try:
        await bot.close()
    except Exception as e:
        logging.error(f"Failed to shut down bot: {e}")
        embed = discord.Embed(
            title="❌ Shutdown Failed",
            description=(
                f"Oops, something went wrong while shutting down…\n"
                f"Error message: {e}\n\n"
                "Maybe the spiritual power’s unstable—check the log (`main-error.log`) or try again later!"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Guess I need to work harder…")
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.slash_command(name="restart", description="Let Reimu Hakurei restart the bot—author only!")
async def restart(interaction: discord.Interaction):
    if interaction.user.id != AUTHOR_ID:
        embed = discord.Embed(
            title="🚫 No Permission",
            description="Hey, this is a big shrine matter—you don’t have the authority! Only my master can use this command~",
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Go donate some offerings instead~")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="⛩️ Restarting...",
        description="I’m off to tweak my spiritual power—I’ll be back soon! The shrine’s closing for a bit, but don’t worry, I’ll return quick~",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Reimu Hakurei | Wait for me!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logging.error(f"Failed to restart bot: {e}")
        embed = discord.Embed(
            title="❌ Restart Failed",
            description=(
                f"Oops, something went wrong during the restart…\n"
                f"Error message: {e}\n\n"
                "Maybe it’s spiritual interference—check the log (`main-error.log`) or try again later!"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Guess I’ll try again…")
        await interaction.followup.send(embed=embed, ephemeral=True)

bot.run(TOKEN)
