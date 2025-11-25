"""
ФІХ #8: Оптимізовані налаштування для production
Замінити відповідні значення в config.py
"""

# ====================================================
# GAME SETTINGS (ОПТИМІЗОВАНО)
# ====================================================
MIN_PLAYERS = 5
MAX_PLAYERS = 15
MAX_BOTS = 10

# Phase durations (seconds) - ЗБАЛАНСОВАНО
NIGHT_DURATION = 45  # Було 40, тепер 45 (більше часу для 10+ людей)
DAY_DURATION = 80    # Було 70, тепер 80 (більше часу на обговорення)
VOTING_DURATION = 25  # Було 20, тепер 25
FINAL_CONFIRMATION_DURATION = 25  # Було 20, тепер 25

# Timer update interval - ОПТИМІЗОВАНО
TIMER_UPDATE_INTERVAL = 10  # Було 15, тепер 10 (краще UX)

# ====================================================
# FLOOD CONTROL SETTINGS (НОВИЙ РОЗДІЛ)
# ====================================================
# Максимальна кількість повідомлень на секунду в чат
MAX_MESSAGES_PER_SECOND = 8  # Підвищено для груп з 10+ людей

# Максимальна кількість дій користувача на секунду
MAX_USER_ACTIONS_PER_SECOND = 3

# Затримка між повідомленнями (секунди)
MIN_MESSAGE_DELAY = 0.3  # Було 0.5, тепер 0.3

# Максимум повідомлень в batch
MAX_BATCH_MESSAGES = 8  # Було 5, тепер 8

# Затримка між batch повідомленнями
BATCH_DELAY = 1.5  # Було 2.0, тепер 1.5

# ====================================================
# BUKOVEL MODE
# ====================================================
BUKOVEL_ENABLED = True
BUKOVEL_CHANCE = 0.20  # 20% шанс
POTATO_KILL_CHANCE = 0.5  # 50% вбити

# ====================================================
# VOTING SETTINGS
# ====================================================
NOMINATION_THRESHOLD_RATIO = 0.3  # 30% від живих для номінації

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
# LAST WORDS (ПОКРАЩЕНО)
# ====================================================
LAST_WORDS_ENABLED = True
LAST_WORDS_TIMEOUT = 20  # Секунди на написання останніх слів
LAST_WORDS_MAX_LENGTH = 200  # Максимум символів

# ====================================================
# SHOP SYSTEM
# ====================================================
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
        "description": "Отримуєш х2 очки за перемоги наступні 5 ігор",
        "cost": 40,
        "buff_type": "DOUBLE_POINTS",
        "games": 5
    }
}

# ====================================================
# POINTS SYSTEM
# ====================================================
POINTS_WIN = 10
POINTS_LOSS = 3
POINTS_KILL = 2
POINTS_SAVE = 3
POINTS_CORRECT_CHECK = 1

# ====================================================
# BOT AI SETTINGS (ЗБАЛАНСОВАНО)
# ====================================================
# Kill priorities
BOT_KILL_PRIORITY_DETECTIVE = 3.0
BOT_KILL_PRIORITY_DOCTOR = 2.5
BOT_KILL_PRIORITY_SPECIAL = 1.8
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

# ====================================================
# LOGGING SETTINGS (НОВИЙ РОЗДІЛ)
# ====================================================
# Рівень логування для production
PRODUCTION_LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

# Логувати performance метрики
LOG_PERFORMANCE = False  # True для дебагу

# Логувати всі дії ботів
LOG_BOT_ACTIONS = True

# Зберігати лог у файл
SAVE_LOG_TO_FILE = False  # True якщо потрібно
LOG_FILE_PATH = "mafia_bot.log"

DATABASE_FILE = "mafia_bot.db"

# ====================================================
# ROLE DISTRIBUTION (КРИТИЧНО!)
# ====================================================
ALLOW_PETRUSHKA = True

ROLE_DISTRIBUTION = {
    5: ["don", "doctor", "detective", "civilian", "civilian"],
    6: ["don", "mafia", "doctor", "detective", "civilian", "civilian"],
    7: ["don", "mafia", "doctor", "detective", "mayor", "civilian", "civilian"],
    8: ["don", "mafia", "doctor", "detective", "deputy", "mayor", "civilian", "civilian"],
    9: ["don", "mafia", "doctor", "detective", "deputy", "mayor", "civilian", "civilian", "civilian"],
    10: ["don", "mafia", "mafia", "doctor", "detective", "deputy", "consigliere", "mayor", "civilian", "civilian"],
    11: ["don", "mafia", "mafia", "doctor", "detective", "deputy", "consigliere", "mayor", "executioner", "civilian", "civilian"],
    12: ["don", "mafia", "mafia", "doctor", "detective", "deputy", "consigliere", "mayor", "executioner", "petrushka", "civilian", "civilian"],
    13: ["don", "mafia", "mafia", "doctor", "detective", "deputy", "consigliere", "mayor", "executioner", "petrushka", "civilian", "civilian", "civilian"],
    14: ["don", "mafia", "mafia", "mafia", "doctor", "detective", "deputy", "consigliere", "mayor", "executioner", "petrushka", "civilian", "civilian", "civilian"],
    15: ["don", "mafia", "mafia", "mafia", "doctor", "detective", "deputy", "consigliere", "mayor", "executioner", "petrushka", "civilian", "civilian", "civilian", "civilian"]
}