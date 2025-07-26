import sqlite3
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import openai
import sys
import logging
from omikuji import draw_lots
import json
import yaml
import random
import Hakurei_Shrine_Work as HSW
import asyncio
import yt_dlp

load_dotenv()

TOKEN = os.getenv('REIMU_TOKEN')
AUTHOR_ID = int(os.getenv('AUTHOR_ID', 0))
API_URL = 'https://api.chatanywhere.org/v1/'
api_keys = [
    {"key": os.getenv('CHATANYWHERE_API3'), "limit": 200, "remaining": 200}
]
current_api_index = 0

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename='reimu-error.log', encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ]
)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

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
            logging.info(f"Deleted {deleted_rows} old messages")
            return deleted_rows
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
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
        context = "\n".join([f"{user_id} says {row[0]}" for row in c.fetchall()])
        conn.close()

        user_background_info = get_user_background_info("Reimu Hakurei")
        if not user_background_info:
            updated_background_info = (
                "I am Reimu Hakurei, the shrine maiden of the Hakurei Shrine, and the resolver of incidents in Gensokyo. "
                "As the guardian of Gensokyo, I possess the ability to manipulate spiritual power and barriers, "
                "defeating troublesome youkai with my spell cards. "
                "I usually lead a relaxed life, enjoying tea and rice dumplings, "
                "but the shrine's offerings are scarce, so I'm always worried about donation money. "
                "Oh, if you visit the shrine, please donate some offering money; I'll be very happy~"
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
            {"role": "system", "content": f"You are now Reimu Hakurei, the shrine maiden of the Hakurei Shrine. Background info: {updated_background_info}"},
            {"role": "user", "content": f"{user_id} says {prompt}"},
            {"role": "assistant", "content": f"Known context: \n{context}"}
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            request_timeout=600
        )

        return response['choices'][0]['message']['content'].strip()

    except Exception as e:
        logging.error(f"API error: {str(e)}")
        return "Reimu is a bit busy right now, come back later~♪"

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
    """Load JSON file"""
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading {file_name}: {e}")
        return default

def save_json(file_name, data):
    """Save JSON file"""
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_yaml(file_name, default=None):
    if default is None:
        default = {}
    """Load YAML file"""
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or default
    except FileNotFoundError:
        logging.error(f"{file_name} file not found")
        return default
    except yaml.YAMLError as e:
        logging.error(f"Error loading {file_name}: {e}")
        return default

def save_yaml(file_name, data):
    """Save YAML file"""
    with open(file_name, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)

def is_on_cooldown(user_id, cooldown_hours):
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

def format_currency(amount):
    units = [
        (10**20, "gai"),
        (10**16, "kyo"),
        (10**12, "cho"),
        (10**8, "oku"),
        (10**4, "man")
    ]
    for value, unit in units:
        if amount >= value:
            return f"{amount / value:.2f} {unit}"
    return str(amount)

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
        
    if message.content.startswith('shut down bot'):
        if message.author.id == AUTHOR_ID:
            await message.channel.send("Shutting down...")
            await asyncio.sleep(5)
            await bot.close()
        else:
            await message.channel.send("You don't have permission to shut me down >_<")
        
    await bot.process_commands(message)
    
@bot.event
async def on_ready():
    logging.info(f"Logged in as {bot.user}")
    
    try:
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(type=discord.ActivityType.watching, name='Hakurei Shrine')
        )
        logging.info("Successfully set bot presence")
    except Exception as e:
        logging.error(f"Failed to set presence: {e}")
        
    init_db()

@bot.slash_command(name="draw_lots", description="Ask Reimu Hakurei to draw a fortune for you, seeking spiritual guidance!")
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
                f"Hey, don't rush to draw lots! My spiritual power isn't ready yet. Come back in {remaining_time}, or I'll charge you extra donation money!",
                ephemeral=True
            )
            return
        elif repeat_count == 2:
            await interaction.response.send_message(
                f"You're still trying to draw?! I said my spiritual power isn't ready. Come back in {remaining_time}! Keep this up, and I'll charge you 5000 donation money!",
                ephemeral=True
            )
            return
        else:
            # Penalty deduction
            reimu_balance_data = load_json("Reimu_balance.json", default={})
            balance_data = load_json("balance.json", default={})
            
            if guild_id not in reimu_balance_data:
                reimu_balance_data[guild_id] = {}
            if user_id_str not in reimu_balance_data[guild_id]:
                reimu_balance_data[guild_id][user_id_str] = 0

            if guild_id not in balance_data:
                balance_data[guild_id] = {}
            if user_id_str not in balance_data[guild_id]:
                balance_data[guild_id][user_id_str] = 0

            reimu_balance = reimu_balance_data[guild_id][user_id_str]
            normal_balance = balance_data[guild_id][user_id_str]

            if reimu_balance >= 5000:
                reimu_balance_data[guild_id][user_id_str] -= 5000
                save_json("Reimu_balance.json", reimu_balance_data)
                user_data[guild_id][user_id_str]["repeat_count"] = 0
                save_json("Reimu_lots.json", user_data)
                await interaction.response.send_message(
                    f"You've tried {repeat_count} times, and I'm fed up! Deducted 5000 from your special donation money. Remaining: {reimu_balance_data[guild_id][user_id_str]}!",
                    ephemeral=True
                )
                return
            elif normal_balance >= 5000:
                balance_data[guild_id][user_id_str] -= 5000
                save_json("balance.json", balance_data)
                user_data[guild_id][user_id_str]["repeat_count"] = 0
                save_json("Reimu_lots.json", user_data)
                await interaction.response.send_message(
                    f"You've tried {repeat_count} times, and I'm fed up! Deducted 5000 from your regular donation money. Remaining: {balance_data[guild_id][user_id_str]}!",
                    ephemeral=True
                )
                return
            else:
                total = reimu_balance + normal_balance
                await interaction.response.send_message(
                    f"Hmph, you've tried {repeat_count} times, but your donation money isn't enough (total: {total})! I'll let you off this time, but don't expect it next time!",
                    ephemeral=True
                )
                return
    
    await interaction.response.defer()
    
    result_text, color = draw_lots()
    
    embed = discord.Embed(
        title="🎋 Reimu Hakurei's Fortune 🎋",
        description=(
            f"I am Reimu Hakurei, the shrine maiden of the Hakurei Shrine, now drawing a fortune for you!\n\n"
            f"{result_text}\n\n"
            "This is a result guided by spiritual power, so accept it graciously~ If your luck is bad, visit the shrine more often and donate some money!"
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
            "Hmm, this fortune is pretty good. Come back to the shrine to thank me, and don't forget the donation money!",
            "Nice luck! Looks like my spiritual power is reliable as always!",
            "Great Blessing, huh? Perfect day to relax with some tea~",
            "Not bad, this fortune makes me want to draw a few more myself!",
            "My spiritual power says you're lucky today. Don't waste it!"
        ]
    elif fortune_type in bad_fortunes:
        comments = [
            "Ouch, this luck... Want me to blast away the bad fortune with my spell cards? It'll cost you, of course!",
            "Misfortune? Don't blame me, the fortune decides itself. I'm just the shrine maiden~",
            "Great Misfortune? Better come to the shrine for a blessing, or I can't guarantee tomorrow!",
            "This luck is rough. Hurry to the shrine, and I'll figure out a way to help!",
            "My spiritual power says your luck is bad. Play it safe and visit the shrine for a blessing!"
        ]
    else:
        comments = [
            "It's alright, a calm life is true happiness. Don't worry too much~",
            "Small Blessing? Work hard, and things will improve. I believe in you!",
            "My spiritual power says this is a fair result. Stop complaining and go earn some donation money!",
            "Average luck? Play it steady and avoid risks!",
            "This fortune says your luck is ordinary. A shrine visit could boost it!"
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

@bot.slash_command(name="donate", description="Donate offering money to Reimu Hakurei to support the shrine!")
async def donate_command_chinese(interaction: discord.Interaction, amount: int):
    try:
        # Defer the response to avoid 3-second timeout
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.InteractionResponded:
            logging.warning(f"[Donate] Interaction already responded: {interaction.user.id}")
        except Exception as e:
            logging.warning(f"[Donate] Error during defer: {e}")

        if amount <= 0:
            await interaction.followup.send(
                "Hey, donation money can't be negative or zero! Show some sincerity~",
                ephemeral=True
            )
            logging.info(f"[Donate] {interaction.user.id} attempted to donate non-positive amount: {amount}")
            return

        user_id = interaction.user
        guild_id = str(interaction.guild.id)
        user_id_str = str(user_id.id)

        logging.info(f"[Donate] {user_id_str} in guild {guild_id} attempting to donate {amount} offering money")

        # Check cooldown
        on_cooldown, remaining_time = is_on_donation_cooldown(user_id, 1)
        if on_cooldown:
            await interaction.followup.send(
                f"You just donated! Reimu is grateful, but wait {remaining_time} before donating again, or the shrine will be overwhelmed by your enthusiasm!",
                ephemeral=True
            )
            logging.info(f"[Donate] {user_id_str} is on cooldown, remaining time: {remaining_time}")
            return

        # Load data with defaults
        reimu_balance_data = load_json("Reimu_balance.json", default={})
        reimu_balance_data.setdefault(guild_id, {}).setdefault(user_id_str, 0)
        reimu_balance = reimu_balance_data[guild_id][user_id_str]

        balance_data = load_json("balance.json", default={})
        balance_data.setdefault(guild_id, {}).setdefault(user_id_str, 0)
        user_balance = balance_data[guild_id][user_id_str]

        total_balance = reimu_balance + user_balance
        if total_balance < amount:
            await interaction.followup.send(
                f"Your balance is only {total_balance}, not enough to donate {amount}! Go earn some more offering money~",
                ephemeral=True
            )
            logging.info(f"[Donate] {user_id_str} insufficient balance: {total_balance} < {amount}")
            return

        # Deduct balance
        if reimu_balance >= amount:
            reimu_balance_data[guild_id][user_id_str] -= amount
        else:
            balance_data[guild_id][user_id_str] -= (amount - reimu_balance)
            reimu_balance_data[guild_id][user_id_str] = 0

        save_json("Reimu_balance.json", reimu_balance_data)
        save_json("balance.json", balance_data)

        # Update lots data
        lots_data = load_json("Reimu_lots.json", default={})
        lots_data.setdefault(guild_id, {}).setdefault(user_id_str, {
            "draw_cooldown": None,
            "repeat_count": 0,
            "donation_cooldown": None,
            "donation_count": 0,
            "total_donated": 0
        })

        user_lots = lots_data[guild_id][user_id_str]
        # Ensure all required keys exist
        user_lots.setdefault("donation_count", 0)
        user_lots.setdefault("total_donated", 0)
        user_lots.setdefault("donation_cooldown", None)
        user_lots.setdefault("draw_cooldown", None)
        user_lots.setdefault("repeat_count", 0)

        user_lots["donation_count"] += 1
        user_lots["total_donated"] += amount
        user_lots["donation_cooldown"] = (datetime.now() + timedelta(minutes=1)).isoformat()

        cooldown_reduced = False
        draw_cd_str = user_lots.get("draw_cooldown")
        if amount >= 1000 and draw_cd_str and isinstance(draw_cd_str, str):
            try:
                current_cooldown = datetime.fromisoformat(draw_cd_str)
                if current_cooldown > datetime.now():
                    new_cooldown = current_cooldown - timedelta(hours=1)
                    user_lots["draw_cooldown"] = None if new_cooldown <= datetime.now() else new_cooldown.isoformat()
                    cooldown_reduced = True
            except ValueError as e:
                logging.warning(f"[Donate] Error parsing draw_cooldown: {draw_cd_str} ({e})")

        save_json("Reimu_lots.json", lots_data)

        # Prepare thank-you message
        if amount < 1000:
            thanks_comments = [
                f"Thanks for donating {amount} offering money! It’s not much, but Reimu appreciates it~",
                f"Got your {amount} offering money! The shrine can buy some tea leaves now. Thanks!",
                f"Thank you for donating {amount} offering money! Reimu will remember your kindness~"
            ]
        elif 1000 <= amount <= 5000:
            thanks_comments = [
                f"Wow, {amount} offering money! Thanks, the shrine can finally get some repairs!",
                f"You donated {amount} offering money! Reimu is thrilled to have such a great supporter~",
                f"Thanks for the {amount} offering money! Reimu will pray for your good fortune!"
            ]
        else:
            thanks_comments = [
                f"Whoa, {amount} offering money?! Reimu is touched; the shrine is saved!",
                f"You donated {amount} offering money?! You're the biggest contributor, and Reimu will pray extra hard for you!",
                f"Thank you for {amount} offering money! Reimu will never forget you; this means a lot to the shrine!"
            ]

        embed = discord.Embed(
            title="🎁 Thank You for Your Donation 🎁",
            description=(
                f"You donated **{amount}** offering money to the Hakurei Shrine!\n"
                f"Your current balance is **{reimu_balance_data[guild_id][user_id_str]}**.\n\n"
                f"{random.choice(thanks_comments)}"
                + ("\n\n✨ Since you donated over 1000, your fortune-drawing cooldown is reduced by 1 hour!" if cooldown_reduced else "")
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Reimu Hakurei | Thank you for your support!")

        try:
            await interaction.followup.send(embed=embed)
            logging.info(f"[Donate] {user_id_str} successfully donated {amount}, cooldown reduced: {cooldown_reduced}")
        except discord.errors.HTTPException as e:
            logging.error(f"[Donate] Failed to send followup message: {e}")
            # Optionally, send a DM to the user
            try:
                await user_id.send("Reimu thanks you for your donation, but due to technical issues, the result couldn't be shown in the channel. Please try again later!")
            except Exception as dm_error:
                logging.error(f"[Donate] Failed to send DM to {user_id_str}: {dm_error}")

    except Exception as e:
        logging.exception(f"[Donate] Unexpected error: {e}")
        try:
            await interaction.followup.send(
                "Something went wrong, and Reimu is working on fixing it. Please try again later!",
                ephemeral=True
            )
        except Exception as nested:
            logging.error(f"[Donate] Failed to send error response: {nested}")
            # Optionally, send a DM to the user
            try:
                await user_id.send("Reimu ran into an issue processing your donation. Please try again later!")
            except Exception as dm_error:
                logging.error(f"[Donate] Failed to send DM to {user_id_str}: {dm_error}")

@bot.slash_command(name="work", description="Work at the Hakurei Shrine to earn offering money!")
async def work_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    on_cooldown, remaining_time = HSW.is_on_work_cooldown(guild_id, user_id, cooldown_hours=1)
    if on_cooldown:
        embed = discord.Embed(
            title="🎋 Reimu's Reminder",
            description=f"Reimu says you've just worked and are too tired! Come back in **{remaining_time}**!",
            color=0xDC143C
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    selected_work, task, reward = HSW.do_work(guild_id, user_id)

    balance_data = HSW.load_json("Reimu_balance.json")
    balance_data.setdefault(guild_id, {})
    balance_data[guild_id].setdefault(user_id, 0)

    balance_data[guild_id][user_id] += reward
    HSW.save_json("Reimu_balance.json", balance_data)

    embed = discord.Embed(
        title="🎋 Hakurei Shrine Work",
        description=(
            f"You completed the **{task}** task and earned **{reward}** offering money!\n"
            f"**Current Balance**: {balance_data[guild_id][user_id]} offering money"
        ),
        color=0xDC143C
    )
    await interaction.response.send_message(embed=embed)

@bot.slash_command(name="work_progress", description="Check your work progress at the Hakurei Shrine!")
async def work_progress(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    progress = HSW.get_user_progress(guild_id, user_id)

    embed = discord.Embed(
        title="📋 Your Work Progress",
        description=(
            f"**Basic Tasks**: {progress['basic']} times\n"
            f"**Normal Tasks**: {progress['normal']} times\n"
            f"**Hard Tasks**: {progress['hard']} times"
        ),
        color=0xDC143C
    )
    await interaction.response.send_message(embed=embed)
    
@bot.slash_command(name="balance", description="Check your offering money balance!")
async def balance_command(interaction: discord.Interaction):
    user_id = interaction.user
    guild_id = str(user_id.guild.id)
    user_id_str = str(user_id.id)

    reimu_balance_data = load_json("Reimu_balance.json", default={})
    balance_data = load_json("balance.json", default={})

    reimu_balance = 0
    normal_balance = 0

    if guild_id in reimu_balance_data and user_id_str in reimu_balance_data[guild_id]:
        reimu_balance = reimu_balance_data[guild_id][user_id_str]

    if guild_id in balance_data and user_id_str in balance_data[guild_id]:
        normal_balance = balance_data[guild_id][user_id_str]

    total_balance = reimu_balance + normal_balance

    embed = discord.Embed(
        title="✨ Hakurei Shrine · Offering Money Ledger ✨",
        description=(
            f"**👛 Special Offering Money**: {format_currency(reimu_balance)} yen\n"
            f"**🪙 Regular Offering Money**: {format_currency(normal_balance)} yen\n\n"
            f"**💰 Total**: {format_currency(total_balance)} yen"
        ),
        color=discord.Color.red()
    )

    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    if total_balance >= 10**18:
        footer_text = "Σ( ° △ °|||) This amount of offering money is insane?!"
    else:
        footer_text = "Thank you for supporting the Hakurei Shrine. Reimu will bless you! ✨"

    embed.set_footer(text=footer_text)

    await interaction.response.send_message(embed=embed)

@bot.slash_command(name="shutdown", description="Have Reimu Hakurei shut down the bot, author only")
async def shutdown(interaction: discord.Interaction):
    if interaction.user.id != AUTHOR_ID:
        embed = discord.Embed(
            title="🚫 Insufficient Permissions",
            description="Hey, this is a sensitive shrine operation! Only my master can use this command~",
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Go donate some offering money instead~")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="⛩️ Shutting Down...",
        description="I'm off to rest. Don't disturb me! The shrine is temporarily closed. Thanks for your donations~",
        color=discord.Color.orange()
    )
    embed.set_footer(text="Reimu Hakurei | Bye-bye~")
    await interaction.response.send_message(embed=embed, ephemeral=False)

    try:
        await bot.close()
    except Exception as e:
        logging.error(f"Failed to shutdown bot: {e}")
        embed = discord.Embed(
            title="❌ Shutdown Failed",
            description=(
                f"Oops, something went wrong during shutdown...\n"
                f"Error message: {e}\n\n"
                "Maybe the spiritual power isn't stable. Check the log (`reimu-error.log`) or try again later!"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Guess I need to try harder...")
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.slash_command(name="restart", description="Have Reimu Hakurei restart the bot, author only")
async def restart(interaction: discord.Interaction):
    if interaction.user.id != AUTHOR_ID:
        embed = discord.Embed(
            title="🚫 Insufficient Permissions",
            description="Hey, this is a big shrine matter! Only my master can use this command~",
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Go donate some offering money instead~")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="⛩️ Restarting...",
        description="I'm adjusting my spiritual power and will be back soon! The shrine is temporarily closed, but don't worry, I'll return quickly~",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Reimu Hakurei | Wait for me!")
    await interaction.response.send_message(embed=embed, ephemeral=False)

    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logging.error(f"Failed to restart bot: {e}")
        embed = discord.Embed(
            title="❌ Restart Failed",
            description=(
                f"Oops, something went wrong during restart...\n"
                f"Error message: {e}\n\n"
                "Maybe some spiritual interference. Check the log (`reimu-error.log`) or try again later!"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Reimu Hakurei | Looks like I need to try again...")
        await interaction.followup.send(embed=embed, ephemeral=True)

bot.run(TOKEN)
