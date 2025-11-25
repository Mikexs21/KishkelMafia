"""
Configuration file for Telegram Mafia Bot.
"""

# ====================================================
# BOT SETTINGS
# ====================================================
BOT_TOKEN = "8597133472:AAHN387YGuvUDlZiUd4s4kqKjOSPoEh66B4"

# ====================================================
# GAME SETTINGS
# ====================================================
MIN_PLAYERS = 5
MAX_PLAYERS = 15
MAX_BOTS = 10

# Phase durations (seconds)
NIGHT_DURATION = 40
DAY_DURATION = 70
VOTING_DURATION = 20  
FINAL_CONFIRMATION_DURATION = 20  

# Timer update interval
TIMER_UPDATE_INTERVAL = 15  # ВИПРАВЛЕНО: 5 -> 10 секунд (менше навантаження)

# ====================================================
# BUKOVEL MODE
# ====================================================
BUKOVEL_ENABLED = True
BUKOVEL_CHANCE = 0.20
POTATO_KILL_CHANCE = 0.5

# ✅ НОВИЙ: Мінімальна затримка між повідомленнями
MIN_MESSAGE_DELAY = 0.5  # секунди

# ✅ НОВИЙ: Максимум повідомлень в batch
MAX_BATCH_MESSAGES = 5

# ✅ НОВИЙ: Затримка між batch повідомленнями
BATCH_DELAY = 2.0  # секунди

# ====================================================
# VOTING SETTINGS
# ====================================================
NOMINATION_THRESHOLD_RATIO = 0.3

# ====================================================
# EXECUTIONER SETTINGS
# ====================================================
EXECUTIONER_ROPE_BREAK_CHANCE = 0.5
EXECUTIONER_REDUCES_BREAK_CHANCE_BY = 0.1
NORMAL_ROPE_BREAK_CHANCE = 0.15

# ====================================================
# MESSAGE DELETION
# ====================================================
DELETE_DEAD_MESSAGES = True
DELETE_NIGHT_MESSAGES = True

# ====================================================
# ROLE DISTRIBUTION
# ====================================================
ROLE_DISTRIBUTION = {
    5: ["don", "doctor", "detective", "civilian", "civilian"],
    6: ["don", "mafia", "doctor", "detective", "civilian", "civilian"],
    7: ["don", "mafia", "doctor", "detective", "petrushka", "civilian", "civilian"],
    8: ["don", "mafia", "doctor", "detective", "deputy", "petrushka", "civilian", "civilian"],
    9: ["don", "mafia", "doctor", "detective", "deputy", "mayor", "petrushka", "civilian", "civilian"],
    10: ["don", "mafia", "consigliere", "doctor", "detective", "deputy", "mayor", "petrushka", "civilian", "civilian"],
    11: ["don", "mafia", "consigliere", "doctor", "detective", "deputy", "mayor", "executioner", "petrushka", "civilian", "civilian"],
    12: ["don", "mafia", "mafia", "consigliere", "doctor", "detective", "deputy", "mayor", "executioner", "petrushka", "civilian", "civilian"],
    13: ["don", "mafia", "mafia", "consigliere", "doctor", "detective", "deputy", "mayor", "executioner", "petrushka", "civilian", "civilian", "civilian"],
    14: ["don", "mafia", "mafia", "consigliere", "doctor", "detective", "deputy", "mayor", "executioner", "petrushka", "civilian", "civilian", "civilian", "civilian"],
    15: ["don", "mafia", "mafia", "consigliere", "doctor", "detective", "deputy", "mayor", "executioner", "petrushka", "civilian", "civilian", "civilian", "civilian", "civilian"],
}

# ====================================================
# PETRUSHKA SETTINGS
# ====================================================
ALLOW_PETRUSHKA = True

# ====================================================
# POINTS SYSTEM
# ====================================================
POINTS_WIN = 10
POINTS_LOSS = 3
POINTS_KILL = 2
POINTS_SAVE = 3
POINTS_CORRECT_CHECK = 1

# ====================================================
# SHOP SYSTEM
# ====================================================
LAST_WORDS_ENABLED = True
LAST_WORDS_TIMEOUT = 20

ENABLE_SHOP = True

SHOP_ITEMS = {
    "force_detective": {
        "name": "🔍 Роль Детектива",
        "description": "Гарантовано отримаєш роль Детектива наступну гру",
        "cost": 50,
        "buff_type": "FORCE_DETECTIVE",
        "games": 1
    },
    "active_role": {
        "name": "⭐ Активна роль",
        "description": "Гарантовано отримаєш активну роль (не мирний) наступні 3 гри",
        "cost": 30,
        "buff_type": "ACTIVE_ROLE",
        "games": 3
    },
    "double_points": {
        "name": "💎 Подвійні очки",
        "description": "Отримуєш х2 очки за наступні 5 ігор",
        "cost": 40,
        "buff_type": "DOUBLE_POINTS",
        "games": 5
    }
}

# ====================================================
# DATABASE SETTINGS
# ====================================================
DATABASE_FILE = "mafia_bot.db"


# ====================================================
# BOT AI SETTINGS
# ====================================================
# Kill priorities
BOT_KILL_PRIORITY_DETECTIVE = 3.0
BOT_KILL_PRIORITY_DOCTOR = 2.5
BOT_KILL_PRIORITY_SPECIAL = 1.8  # mayor, deputy
BOT_KILL_PRIORITY_HUMAN = 1.5
BOT_KILL_PRIORITY_ACCUSER = 2.0

# Heal priorities
BOT_HEAL_PRIORITY_DETECTIVE = 2.5
BOT_HEAL_PRIORITY_SPECIAL = 2.0
BOT_HEAL_PRIORITY_TRUSTED = 1.8
BOT_HEAL_PRIORITY_HUMAN = 1.3
BOT_HEAL_PRIORITY_DEFENDER = 2.2

# General settings
BOT_PRIORITY_RANDOM_MIN = 0.8
BOT_PRIORITY_RANDOM_MAX = 1.2
BOT_DOCTOR_SELF_HEAL_MIN_ROUND = 2

# Detective shoot settings
BOT_DETECTIVE_SHOOT_MIN_ROUND = 3
BOT_DETECTIVE_SHOOT_PROBABILITY_CONFIRMED = 0.8
BOT_DETECTIVE_SHOOT_PROBABILITY_SUSPICIOUS = 0.4

# Voting behavior
BOT_FOLLOW_POPULAR_VOTE_PROBABILITY = 0.6
BOT_MAFIA_TARGET_ACCUSER_PROBABILITY = 0.7
BOT_MAFIA_VOTE_YES_PROBABILITY = 0.65

# Confirmation votes
BOT_CONFIRMATION_VERY_SUSPICIOUS_YES = 0.8
BOT_CONFIRMATION_SUSPICIOUS_YES = 0.6
BOT_CONFIRMATION_TRUSTED_NO = 0.75