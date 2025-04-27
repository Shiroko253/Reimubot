import random
import json
import os
import threading
from datetime import datetime, timedelta

file_lock = threading.Lock()  # A lock to keep my shrine’s records safe from chaos!

def load_json(filename, default=None):
    # Reimu’s way of grabbing JSON files—don’t mess up my shrine’s records!
    try:
        if not os.path.exists(filename):
            return default if default is not None else {}
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Ugh, failed to load {filename}: {e}")  # Reimu’s annoyed at file troubles
        return default if default is not None else {}

def save_json(filename, data):
    # Saving the shrine’s precious data—don’t let it get lost!
    try:
        with file_lock:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Hey, something went wrong saving {filename}: {e}")  # Reimu’s grumble when saving fails

def get_user_work_data(guild_id, user_id):
    # Fetching work records from the shrine’s dusty archive
    data = load_json("Hakurei_work.json")
    data.setdefault(guild_id, {})
    data[guild_id].setdefault(user_id, {
        "basic": 0,
        "normal": 0,
        "hard": 0,
        "last_work": None  # Setting up cooldown for shrine chores
    })
    return data

def save_user_work_data(data):
    # Stashing work records back in the shrine’s storage
    save_json("Hakurei_work.json", data)

def is_on_work_cooldown(guild_id, user_id, cooldown_hours=1):
    # Checking if you’re slacking or spamming shrine work—give me a break!
    data = load_json("Hakurei_work.json")
    user_data = data.get(guild_id, {}).get(user_id, {})
    last_work = user_data.get("last_work")

    if not last_work:
        return False, "0 hours 0 minutes"  # No work done? You’re free to help!

    try:
        last_work_time = datetime.fromisoformat(last_work)
        cooldown_end = last_work_time + timedelta(hours=cooldown_hours)
        now = datetime.utcnow()

        if now < cooldown_end:
            remaining = cooldown_end - now
            hours = remaining.seconds // 3600
            minutes = (remaining.seconds % 3600) // 60
            return True, f"{hours} hours {minutes} minutes"  # Reimu’s telling you to chill
        return False, "0 hours 0 minutes"
    except ValueError:
        return False, "0 hours 0 minutes"  # Something’s off, but I’ll let you work

def do_work(guild_id, user_id):
    # Assigning chores at the shrine—don’t expect me to do all the work!
    data = get_user_work_data(guild_id, user_id)
    user_data = data[guild_id][user_id]

    # Picking tasks based on how much you’ve helped out
    available_works = ["basic"]  # Basic chores are always open
    if user_data["basic"] >= 10:
        available_works.append("normal")  # You’ve earned some tougher jobs
    if user_data["normal"] >= 25:
        available_works.append("hard")  # Ready for the big leagues, huh?

    selected_work = random.choice(available_works)

    # Choosing a task and reward based on the job type
    if selected_work == "basic":
        task = random.choice([
            "Sweeping the grounds",
            "Polishing the stone lions",
            "Clearing fallen leaves",
            "Organizing the ema boards",
            "Cleaning the shrine’s backyard"
        ])
        reward = random.randint(100, 500)  # A small tip for small jobs
    elif selected_work == "normal":
        task = random.choice([
            "Chasing off pesky fairies",
            "Handling a minor incident",
            "Rescuing a lost animal",
            "Cleaning the festival grounds",
            "Carrying offerings"
        ])
        reward = random.randint(1200, 3000)  # Decent pay for decent work
    else:  # hard
        task = random.choice([
            "Resolving a major incident",
            "Taking down a nasty youkai",
            "Fixing a broken barrier",
            "Driving off intruders",
            "Calming a rogue nature spirit"
        ])
        reward = random.randint(50000, 1000000)  # Big bucks for saving Gensokyo!

    # Updating your work progress and setting a cooldown
    user_data[selected_work] += 1
    user_data["last_work"] = datetime.utcnow().isoformat()
    save_user_work_data(data)

    return selected_work, task, reward

def get_user_progress(guild_id, user_id):
    # Checking how much you’ve helped at the shrine—impress me!
    data = load_json("Hakurei_work.json")
    return data.get(guild_id, {}).get(user_id, {"basic": 0, "normal": 0, "hard": 0, "last_work": None})
