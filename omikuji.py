import random

# Dictionary mapping fortune types to their corresponding colors (hex values)
fortune_colors = {
    "Great Blessing": 0xFFD700,  # Gold
    "Moderate Blessing": 0x00FF00,  # Green
    "Small Blessing": 0xADD8E6,  # Light Blue
    "Blessing": 0x1E90FF,    # Blue
    "Minor Blessing": 0xFFA500,  # Orange
    "Misfortune": 0xFF4500,    # Orange-Red
    "Great Misfortune": 0x8B0000   # Dark Red
}

# List of fortune entries, each containing various aspects and details
omikuji_fortunes = [
    {
        "Fortune": "Great Blessing",
        "Love": "Love will be as warm as a spring breeze—good news is on the way!",
        "Career": "Your career is soaring like the midday sun—promotion or a raise might be coming!",
        "Health": "Your body is full of energy—keep up your current condition!",
        "Suggested Action": "Today’s a good day to visit a shrine and give thanks for the blessings!",
        "Lucky Item": "Red and white shrine maiden outfit—wearing it will boost your confidence!"
    },
    {
        "Fortune": "Moderate Blessing",
        "Love": "Love progresses smoothly, but don’t forget to pay attention to the little details.",
        "Career": "Your career is stable with small achievements—don’t get too carried away!",
        "Health": "Health is decent—moderate exercise can boost your energy further.",
        "Suggested Action": "Relax with a cup of tea—your energy needs a break too.",
        "Lucky Item": "Paper wand—carry it with you to enhance your fortune!"
    },
    {
        "Fortune": "Small Blessing",
        "Love": "Love faces minor hiccups—patience will sort it out.",
        "Career": "Career hits a small snag—take it slow, no rush.",
        "Health": "You might feel tired occasionally—rest up a bit.",
        "Suggested Action": "Sweep the shrine grounds—you might just sweep away bad luck!",
        "Lucky Item": "Amulet—carrying it will give you some peace of mind."
    },
    {
        "Fortune": "Blessing",
        "Love": "Love is steady—maintaining the status quo is just fine.",
        "Career": "Career is stable—keep working hard, and you’ll see rewards.",
        "Health": "No major health issues—stay positive!",
        "Suggested Action": "Donate some money at the shrine—good fortune might favor you more.",
        "Lucky Item": "Sticky rice dumpling—eating one will lift your spirits!"
    },
    {
        "Fortune": "Minor Blessing",
        "Love": "Love feels a bit lukewarm—wait patiently for the right moment.",
        "Career": "Career progress is slow—don’t lose heart, take it step by step.",
        "Health": "Energy is a bit low—rest up and don’t overdo it.",
        "Suggested Action": "Help clean the shrine—your luck might improve!",
        "Lucky Item": "Bell—its sound can help you relax."
    },
    {
        "Fortune": "Misfortune",
        "Love": "Love might hit some trouble—communicate more to avoid misunderstandings.",
        "Career": "Career faces obstacles—seeking help could make things easier.",
        "Health": "You’re feeling a bit worn out—don’t push yourself, take a break.",
        "Suggested Action": "Visit the shrine to pray—this fortune isn’t looking great!",
        "Lucky Item": "Spell card—carry it to ward off misfortune."
    },
    {
        "Fortune": "Great Misfortune",
        "Love": "Love could face a crisis—handle it carefully and avoid rash moves.",
        "Career": "Career is at a low point—now’s not the time for big decisions.",
        "Health": "Health isn’t great—rest immediately and don’t strain yourself!",
        "Suggested Action": "Head to the shrine to pray right away—this fortune needs fixing!",
        "Lucky Item": "Protective charm—hold it tight, it’ll shield you."
    }
]

# Function to randomly draw a fortune and return its text and color
def draw_lots():
    fortune = random.choice(omikuji_fortunes)
    result_text = (
        f"**Fortune**: {fortune['Fortune']}\n"
        f"**Love**: {fortune['Love']}\n"
        f"**Career**: {fortune['Career']}\n"
        f"**Health**: {fortune['Health']}\n"
        f"**Suggested Action**: {fortune['Suggested Action']}\n"
        f"**Lucky Item**: {fortune['Lucky Item']}"
    )
    color = fortune_colors[fortune["Fortune"]]
    return result_text, color
