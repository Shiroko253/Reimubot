import sqlite3
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
import asyncio
from dotenv import load_dotenv
import os
import openai # v0.28
import sys
import time
import logging
from omikuji import draw_lots
import json
import yaml
import random
import Hakurei_Shrine_Work as HSW

load_dotenv()

TOKEN = os.getenv('REIMU_TOKEN')  # My secret shrine token, don’t even think about peeking!
AUTHOR_ID = int(os.getenv('AUTHOR_ID', 0))  # Only the shrine’s master can use special commands!
API_URL = 'https://api.chatanywhere.org/v1/'  # The channel I use to chat with the outside world
api_keys = [
    {"key": os.getenv('CHATANYWHERE_API3'), "limit": 200, "remaining": 200}
]
current_api_index = 0

# Setting up logs to keep track of all the chaos I deal with at the shrine
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(filename='main-error.log', encoding='utf-8', mode='w'),
        logging.StreamHandler()
    ]
)

# My Discord permissions, so I can see everyone’s messages and keep tabs on shrine activity
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)  # My command prefix—shout “!” and I’ll show up!

def init_db():
    # Setting up the shrine’s database to store everyone’s messages and my epic backstory
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
    # Keeping track of what everyone says to me—don’t think I’ll forget!
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
    # Sweeping out old messages from the shrine—don’t want my database cluttered!
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
            print(f"Reimu swept {deleted_rows} old messages out of the shrine!")  # Reimu’s cleaning report
            return deleted_rows
    except sqlite3.Error as e:
        print(f"Ugh, something’s wrong with the database: {e}")  # Reimu’s grumbling when things go wrong
        return 0

def summarize_context(context):
    # Shortening long conversations—too much reading makes me dizzy!
    return context[:1500]

def generate_response(prompt, user_id):
    # Reimu crafts a response based on what you say, pulling from shrine records
    try:
        openai.api_base = API_URL
        openai.api_key = os.getenv('CHATANYWHERE_API3')

        conn = sqlite3.connect("example3.db")
        c = conn.cursor()
        c.execute("""
            SELECT message FROM UserMessages 
            WHERE user_id = ? OR user_id = 'system'
        """, (user_id,))
        context = "\n".join([f"{user_id} said to Reimu: {row[0]}" for row in c.fetchall()])  # Reimu organizing chat history
        conn.close()

        user_background_info = get_user_background_info("Hakurei Reimu")
        if not user_background_info:
            updated_background_info = (
                "I’m Hakurei Reimu, the shrine maiden of the Hakurei Shrine, solver of Gensokyo’s incidents!"
                "As the guardian, I wield spiritual powers and barriers. Troublesome youkai? One spell card and they’re done!"
                "Normally, I live a chill life, sipping tea and eating mochi, but the shrine’s donations are always low..."
                "Hey, if you visit the shrine, toss in some donation money—I’d be thrilled~"
            )
            conn = sqlite3.connect("example3.db")
            c = conn.cursor()
            c.execute("""
                INSERT INTO BackgroundInfo (user_id, info) VALUES (?, ?)
            """, ("Hakurei Reimu", updated_background_info))
            conn.commit()
            conn.close()
        else:
            updated_background_info = user_background_info

        if len(context.split()) > 3000:
            context = summarize_context(context)  # Reimu cuts down overly long chats!

        messages = [
            {"role": "system", "content": f"You are now Hakurei Reimu, shrine maiden of the Hakurei Shrine. Background: {updated_background_info}"},
            {"role": "user", "content": f"{user_id} said to Reimu: {prompt}"},
            {"role": "assistant", "content": f"Reimu’s background knowledge:\n{context}"}
        ]

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            request_timeout=600
        )

        return response['choices'][0]['message']['content'].strip()

    except Exception as e:
        print(f"My spiritual connection’s acting up: {str(e)}")  # Reimu’s complaint when the API fails
        return "Hey, Reimu’s busy dealing with an incident right now. Come back later~"

def get_user_background_info(user_id):
    # Reimu checks the shrine’s records for someone’s background info
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
    """General JSON file loading function"""
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Failed to load {file_name}: {e}")  # Reimu’s annoyed at file issues
        return default

def save_json(file_name, data):
    """General JSON file saving function"""
    with open(file_name, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

def load_yaml(file_name, default=None):
    if default is None:
        default = {}
    """General YAML file loading function"""
    try:
        with open(file_name, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or default
    except FileNotFoundError:
        print(f"{file_name} not found.")  # Reimu’s shrug when a file’s missing
        return default
    except yaml.YAMLError as e:
        print(f"Error loading {file_name}: {e}")  # Reimu’s grumble at YAML errors
        return default

def save_yaml(file_name, data):
    """General YAML file saving function"""
    with open(file_name, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)

def is_on_cooldown(user_id, cooldown_hours):
    # Checking if someone’s spamming my omikuji—give my spiritual powers a break!
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
    # Updating the cooldown so people don’t spam my shrine
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
    # Making sure people don’t flood the shrine with donations too fast
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
    # Recording donations—every coin helps keep the shrine running!
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
    # Converting big numbers into something easier to read, shrine-style
    units = [
        (10**20, "gai"),
        (10**16, "kyo"),
        (10**12, "cho"),
        (10**8, "oku"),
        (10**4, "man")
    ]
    for value, unit in units:
        if amount >= value:
            return f"{amount / value:.2f}{unit}"
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
        
    await bot.process_commands(message)
    
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")  # Reimu’s ready to run the shrine!
    
    try:
        await bot.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(type=discord.ActivityType.watching, name='Hakurei Shrine')
        )
        print("Set the bot’s status.")  # Reimu’s proud of her shrine’s vibe
    except Exception as e:
        print(f"Failed to set presence: {e}")  # Reimu’s annoyed at tech issues
        
    init_db()

@bot.slash_command(name="draw_lots", description="Ask Reimu to draw an omikuji for spiritual guidance!")
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
                f"Hey, slow down with the omikuji! My spiritual powers need a break. Come back in {remaining_time}, or I’ll charge extra donation money!",
                ephemeral=True
            )
            return
        elif repeat_count == 2:
            await interaction.response.send_message(
                f"You’re still at it?! I said my powers aren’t ready yet—wait {remaining_time}! Keep this up, and I’ll fine you 5000 donation money, got it?",
                ephemeral=True
            )
            return
        else:
            # Punishment time—deducting donation money!
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
                    f"You’ve tried {repeat_count} times, and I’m done! Deducted 5000 from your special donation money. You’ve got {reimu_balance_data[guild_id][user_id_str]} left!",
                    ephemeral=True
                )
                return
            elif normal_balance >= 5000:
                balance_data[guild_id][user_id_str] -= 5000
                save_json("balance.json", balance_data)
                user_data[guild_id][user_id_str]["repeat_count"] = 0
                save_json("Reimu_lots.json", user_data)
                await interaction.response.send_message(
                    f"You’ve tried {repeat_count} times, and I’m fed up! Deducted 5000 from your regular donation money. You’ve got {balance_data[guild_id][user_id_str]} left!",
                    ephemeral=True
                )
                return
            else:
                total = reimu_balance + normal_balance
                await interaction.response.send_message(
                    f"Hmph, you’ve tried {repeat_count} times, but your donation money’s too low (only {total})! I’ll let you off this time, but don’t push your luck!",
                    ephemeral=True
                )
                return
    
    await interaction.response.defer()
    
    result_text, color = draw_lots()
    
    embed = discord.Embed(
        title="🎋 Reimu’s Omikuji 🎋",
        description=(
            f"I’m Hakurei Reimu, shrine maiden of the Hakurei Shrine, here to draw your fortune!\n\n"
            f"{result_text}\n\n"
            "This is the result guided by my spiritual powers, so take it seriously~ If your luck’s bad, visit the shrine and donate some money!"
        ),
        color=color
    )
    
    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    fortune_type = result_text.split("\n")[0].split(":")[1].strip()
    good_fortunes = ["Great Blessing", "Moderate Blessing", "Blessing"]
    bad_fortunes = ["Curse", "Great Curse"]
    
    if fortune_type in good_fortunes:
        comments = [
            "Not bad, huh? Come thank me at the shrine—and don’t forget the donation money~",
            "Pretty good luck! Looks like my spiritual powers are on point today!",
            "Great Blessing? Perfect day to sip some tea and relax~",
            "Nice, nice! This fortune’s so good, I might draw one myself!",
            "My powers say you’re lucky today—don’t waste it!"
        ]
    elif fortune_type in bad_fortunes:
        comments = [
            "Oof, this fortune… Want me to blast that bad luck away with a spell card? It’ll cost you!",
            "Curse? Don’t blame me, the omikuji decided this—I’m just the maiden!",
            "Great Curse? Better come to the shrine for a blessing, or tomorrow might be rough!",
            "This fortune’s pretty bad. Hurry to the shrine—I’ll figure something out!",
            "My powers say your luck’s down. Stay safe and visit the shrine!"
        ]
    else:
        comments = [
            "Eh, it’s okay. A normal life’s fine, don’t sweat it~",
            "Small Blessing? Work hard, and it’ll probably get better. I believe in you!",
            "My powers say this is fair. Stop whining and go earn some donation money!",
            "Mediocre fortune? Play it safe and avoid risks!",
            "This omikuji says your luck’s average. A shrine visit could boost it!"
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

@bot.slash_command(name="donate", description="Donate money to Reimu to support the shrine!")
async def donate_command(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message(
            "Hey, donations can’t be zero or negative! Show some sincerity~",
            ephemeral=True
        )
        return

    user_id = interaction.user
    guild_id = str(user_id.guild.id)
    user_id_str = str(user_id.id)

    # Checking for donation cooldown
    on_cooldown, remaining_time = is_on_donation_cooldown(user_id, 1)
    if on_cooldown:
        await interaction.response.send_message(
            f"You just donated! I’m grateful, but wait {remaining_time} before donating again—the shrine’s gonna drown in your enthusiasm!",
            ephemeral=True
        )
        return

    # Load Reimu_balance.json (priority)
    reimu_balance_data = load_json("Reimu_balance.json", default={})
    if guild_id not in reimu_balance_data:
        reimu_balance_data[guild_id] = {}
    if user_id_str not in reimu_balance_data[guild_id]:
        reimu_balance_data[guild_id][user_id_str] = 0

    reimu_balance = reimu_balance_data[guild_id][user_id_str]

    # Load balance.json (secondary)
    balance_data = load_json("balance.json", default={})
    if guild_id not in balance_data:
        balance_data[guild_id] = {}
    if user_id_str not in balance_data[guild_id]:
        balance_data[guild_id][user_id_str] = 0

    user_balance = balance_data[guild_id][user_id_str]

    # Check if balance is enough
    total_balance = reimu_balance + user_balance
    if total_balance < amount:
        await interaction.response.send_message(
            f"You’ve only got {total_balance}, not enough for a {amount} donation! Go earn some more money~",
            ephemeral=True
        )
        return

    # Deduct donation
    if reimu_balance >= amount:
        reimu_balance_data[guild_id][user_id_str] -= amount
    else:
        balance_data[guild_id][user_id_str] -= (amount - reimu_balance)
        reimu_balance_data[guild_id][user_id_str] = 0

    save_json("Reimu_balance.json", reimu_balance_data)
    save_json("balance.json", balance_data)

    # Update omikuji data
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

    # Thank-you messages based on donation amount
    if amount < 1000:
        thanks_comments = [
            f"Thanks for donating {amount}! It’s not much, but I’ll take it~",
            f"Got {amount} donation money! The shrine can buy some tea leaves now, thanks!",
            f"Thanks for the {amount} donation! I’ll remember your kindness~"
        ]
    elif 1000 <= amount <= 5000:
        thanks_comments = [
            f"Wow, {amount} donation money! Thanks, the shrine can finally get some repairs!",
            f"You donated {amount}? I’m thrilled! Devotees like you make my day~",
            f"Thanks for {amount}! I’ll pray for your luck to turn around!"
        ]
    else:
        thanks_comments = [
            f"Whoa, {amount} donation money?! I’m touched—the shrine’s saved!",
            f"You gave {amount}? You’re the shrine’s biggest supporter! I’ll pray extra hard for you!",
            f"Thanks for {amount}! I’ll never forget this—it means the world to the shrine!"
        ]

    embed = discord.Embed(
        title="🎁 Thanks for Your Donation 🎁",
        description=(
            f"You donated **{amount}** to the Hakurei Shrine!\n"
            f"Your balance is now **{reimu_balance_data[guild_id][user_id_str]}**.\n\n"
            f"{random.choice(thanks_comments)}"
            + ("\n\n✨ Since you donated over 1000, your omikuji cooldown’s reduced by 1 hour!" if cooldown_reduced else "")
        ),
        color=discord.Color.gold()
    )
    embed.set_footer(text="Hakurei Reimu | Thanks for your support!")

    await interaction.response.send_message(embed=embed)

@bot.slash_command(name="work", description="Help out at the Hakurei Shrine and earn donation money!")
async def work_command(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    guild_id = str(interaction.guild.id)

    on_cooldown, remaining_time = HSW.is_on_work_cooldown(guild_id, user_id, cooldown_hours=1)
    if on_cooldown:
        embed = discord.Embed(
            title="🎋 Reimu’s Reminder",
            description=f"You just worked! You’re exhausted. Come back in **{remaining_time}**!",
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
            f"You completed the 【{task}】 task and earned **{reward}** donation money!\n"
            f"【Current Balance】: {balance_data[guild_id][user_id]} donation money"
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
    
@bot.slash_command(name="balance", description="Check your donation money balance!")
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
        title="✨ Hakurei Shrine · Donation Ledger ✨",
        description=(
            f"**👛 Special Donation Money**: {format_currency(reimu_balance)} yen\n"
            f"**🪙 Regular Donation Money**: {format_currency(normal_balance)} yen\n\n"
            f"**💰 Total**: {format_currency(total_balance)} yen"
        ),
        color=discord.Color.red()
    )

    if bot.user.avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    if total_balance >= 10**18:
        footer_text = "Σ( ° △ °|||) This donation money is insane!"
    else:
        footer_text = "Thanks for supporting the Hakurei Shrine. I’ll bless you! ✨"

    embed.set_footer(text=footer_text)

    await interaction.response.send_message(embed=embed)

@bot.slash_command(name="shutdown", description="Let Reimu shut down the bot, author only!")
async def shutdown(interaction: discord.Interaction):
    if interaction.user.id != AUTHOR_ID:
        embed = discord.Embed(
            title="🚫 No Permission",
            description="Hey, this is shrine business! Only my master can use this command~",
            color=discord.Color.red()
        )
        embed.set_footer(text="Hakurei Reimu | Go donate some money instead~")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="⛩️ Shutting Down...",
        description="I’m off to take a nap. Don’t bother me! The shrine’s closed for now—thanks for the donations~",
        color=discord.Color.orange()
    )
    embed.set_footer(text="Hakurei Reimu | Bye-bye~")
    await interaction.response.send_message(embed=embed, ephemeral=False)

    try:
        await bot.close()
    except Exception as e:
        logging.error(f"Failed to shut down bot: {e}")
        embed fibrinogen = discord.Embed(
            title="❌ Shutdown Failed",
            description=(
                f"Ugh, something went wrong during shutdown…\n"
                f"Error: {e}\n\n"
                "Maybe my spiritual powers are unstable. Check the logs (`main-error.log`) or try again later!"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Hakurei Reimu | Guess I gotta try harder…")
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.slash_command(name="restart", description="Let Reimu restart the bot, author only!")
async def restart(interaction: discord.Interaction):
    if interaction.user.id != AUTHOR_ID:
        embed = discord.Embed(
            title="🚫 No Permission",
            description="Hey, this is a big shrine deal! Only my master can use this command~",
            color=discord.Color.red()
        )
        embed.set_footer(text="Hakurei Reimu | Go donate some money instead~")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    embed = discord.Embed(
        title="⛩️ Restarting...",
        description="I’m tweaking my spiritual powers and will be back soon! Shrine’s closed for a bit—don’t worry, I’ll return quick~",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Hakurei Reimu | Hold on a sec!")
    await interaction.response.send_message(embed=embed, ephemeral=False)

    try:
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        logging.error(f"Failed to restart bot: {e}")
        embed = discord.Embed(
            title="❌ Restart Failed",
            description=(
                f"Ugh, something messed up during the restart…\n"
                f"Error: {e}\n\n"
                "Maybe some spiritual interference. Check the logs (`main-error.log`) or try again later!"
            ),
            color=discord.Color.red()
        )
        embed.set_footer(text="Hakurei Reimu | Guess I’ll try again…")
        await interaction.followup.send(embed=embed, ephemeral=True)

bot.run(TOKEN)
