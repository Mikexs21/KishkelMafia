"""
Configuration file for Telegram Mafia Bot.
Production-ready version with validation and documentation.
"""

import os
from typing import Dict, List

# ====================================================
# BOT SETTINGS
# ====================================================
BOT_TOKEN = os.environ.get("MAFIA_BOT_TOKEN", "8597133472:AAHN387YGuvUDlZiUd4s4kqKjOSPoEh66B4")
# Get from @BotFather: https://t.me/BotFather

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

# Timer update interval (seconds)
# Higher = less spam, lower = more accurate countdown
TIMER_UPDATE_INTERVAL = 10

# ====================================================
# BUKOVEL MODE (Special game mode)
# ====================================================
BUKOVEL_ENABLED = True
BUKOVEL_CHANCE = 0.20  # 20% chance for Bukovel mode
POTATO_KILL_CHANCE = 0.5  # 50% chance potato kills target

# ====================================================
# FLOOD CONTROL
# ====================================================
MIN_MESSAGE_DELAY = 0.5  # Minimum delay between messages (seconds)
MAX_BATCH_MESSAGES = 5  # Max messages before batch delay
BATCH_DELAY = 2.0  # Delay between message batches (seconds)

# ====================================================
# VOTING SETTINGS
# ====================================================
# Minimum % of alive players needed to nominate candidate
NOMINATION_THRESHOLD_RATIO = 0.3  # 30% of players

# ====================================================
# EXECUTIONER SETTINGS
# ====================================================
EXECUTIONER_ROPE_BREAK_CHANCE = 0.5  # 50% for executioner
EXECUTIONER_REDUCES_BREAK_CHANCE_BY = 0.1  # -10% for others
NORMAL_ROPE_BREAK_CHANCE = 0.15  # 15% normally

# ====================================================
# MESSAGE DELETION
# ====================================================
DELETE_DEAD_MESSAGES = True  # Delete messages from dead players
DELETE_NIGHT_MESSAGES = True  # Delete all messages during night

# ====================================================
# ROLE DISTRIBUTION
# ====================================================
ROLE_DISTRIBUTION: Dict[int, List[str]] = {
    5: ["don", "doctor", "detective", "civilian", "civilian"],
    
    6: ["don", "mafia", "doctor", "detective", "civilian", "civilian"],
    
    7: ["don", "mafia", "doctor", "detective", "petrushka", 
        "civilian", "civilian"],
    
    8: ["don", "mafia", "doctor", "detective", "deputy", "petrushka",
        "civilian", "civilian"],
    
    9: ["don", "mafia", "doctor", "detective", "deputy", "mayor",
        "petrushka", "civilian", "civilian"],
    
    10: ["don", "mafia", "consigliere", "doctor", "detective", "deputy",
         "mayor", "petrushka", "civilian", "civilian"],
    
    11: ["don", "mafia", "consigliere", "doctor", "detective", "deputy",
         "mayor", "executioner", "petrushka", "civilian", "civilian"],
    
    12: ["don", "mafia", "mafia", "consigliere", "doctor", "detective",
         "deputy", "mayor", "executioner", "petrushka", "civilian", "civilian"],
    
    13: ["don", "mafia", "mafia", "consigliere", "doctor", "detective",
         "deputy", "mayor", "executioner", "petrushka", "civilian", 
         "civilian", "civilian"],
    
    14: ["don", "mafia", "mafia", "consigliere", "doctor", "detective",
         "deputy", "mayor", "executioner", "petrushka", "civilian",
         "civilian", "civilian", "civilian"],
    
    15: ["don", "mafia", "mafia", "consigliere", "doctor", "detective",
         "deputy", "mayor", "executioner", "petrushka", "civilian",
         "civilian", "civilian", "civilian", "civilian"],
}

# ====================================================
# PETRUSHKA SETTINGS
# ====================================================
ALLOW_PETRUSHKA = True  # Enable/disable Petrushka role

# ====================================================
# POINTS SYSTEM
# ====================================================
POINTS_WIN = 10  # Points for winning
POINTS_LOSS = 3  # Points for losing (participation award)
POINTS_KILL = 2  # Points per kill
POINTS_SAVE = 3  # Points per successful save
POINTS_CORRECT_CHECK = 1  # Points per check

# ====================================================
# SHOP SYSTEM
# ====================================================
LAST_WORDS_ENABLED = True  # Allow last words from dying players
LAST_WORDS_TIMEOUT = 20  # Seconds to write last words

ENABLE_SHOP = True  # Enable/disable shop

SHOP_ITEMS: Dict[str, Dict] = {
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
        "description": "Отримуєш х2 очки за наступні 5 ігор (тільки за перемоги)",
        "cost": 40,
        "buff_type": "DOUBLE_POINTS",
        "games": 5
    }
}

# ====================================================
# DATABASE SETTINGS
# ====================================================
DATABASE_FILE = os.environ.get("MAFIA_DB_FILE", "mafia_bot.db")

# ====================================================
# BOT AI SETTINGS
# ====================================================

# Kill target priorities (multipliers)
BOT_KILL_PRIORITY_DETECTIVE = 3.0  # Highest threat
BOT_KILL_PRIORITY_DOCTOR = 2.5  # High threat
BOT_KILL_PRIORITY_SPECIAL = 1.8  # Mayor, Deputy - medium threat
BOT_KILL_PRIORITY_HUMAN = 1.5  # Prefer killing humans
BOT_KILL_PRIORITY_ACCUSER = 2.0  # Kill those who accused us

# Heal target priorities (multipliers)
BOT_HEAL_PRIORITY_DETECTIVE = 2.5  # Protect detective
BOT_HEAL_PRIORITY_SPECIAL = 2.0  # Protect special roles
BOT_HEAL_PRIORITY_TRUSTED = 1.8  # Protect trusted players
BOT_HEAL_PRIORITY_HUMAN = 1.3  # Slightly prefer humans
BOT_HEAL_PRIORITY_DEFENDER = 2.2  # Protect those who defended us

# General AI settings
BOT_PRIORITY_RANDOM_MIN = 0.8  # Random factor min
BOT_PRIORITY_RANDOM_MAX = 1.2  # Random factor max
BOT_DOCTOR_SELF_HEAL_MIN_ROUND = 2  # Min round to self-heal

# Detective shoot settings
BOT_DETECTIVE_SHOOT_MIN_ROUND = 3  # Don't shoot before round 3
BOT_DETECTIVE_SHOOT_PROBABILITY_CONFIRMED = 0.8  # 80% if confirmed mafia
BOT_DETECTIVE_SHOOT_PROBABILITY_SUSPICIOUS = 0.4  # 40% if suspicious

# Voting behavior
BOT_FOLLOW_POPULAR_VOTE_PROBABILITY = 0.6  # 60% follow majority
BOT_MAFIA_TARGET_ACCUSER_PROBABILITY = 0.7  # 70% mafia targets accusers
BOT_MAFIA_VOTE_YES_PROBABILITY = 0.65  # 65% mafia votes yes to lynch

# Confirmation votes
BOT_CONFIRMATION_VERY_SUSPICIOUS_YES = 0.8  # 80% yes if very suspicious
BOT_CONFIRMATION_SUSPICIOUS_YES = 0.6  # 60% yes if suspicious
BOT_CONFIRMATION_TRUSTED_NO = 0.75  # 75% no if trusted

# ====================================================
# ADVANCED SETTINGS (usually don't need changing)
# ====================================================

# Memory cleanup interval (hours)
BOT_MEMORY_CLEANUP_HOURS = 24

# Maximum game duration (minutes) - auto-end if exceeded
MAX_GAME_DURATION_MINUTES = 120

# Debug mode
DEBUG_MODE = os.environ.get("MAFIA_DEBUG", "false").lower() == "true"

# ====================================================
# VALIDATION
# ====================================================

def validate_config() -> tuple[bool, list[str]]:
    """Validate configuration settings. Returns (is_valid, errors)."""
    errors = []
    
    # Bot token
    if not BOT_TOKEN or BOT_TOKEN == "PASTE_TOKEN_HERE":
        errors.append("BOT_TOKEN is not configured")
    
    # Player limits
    if MIN_PLAYERS < 4:
        errors.append(f"MIN_PLAYERS must be at least 4 (got {MIN_PLAYERS})")
    if MAX_PLAYERS < MIN_PLAYERS:
        errors.append(f"MAX_PLAYERS ({MAX_PLAYERS}) must be >= MIN_PLAYERS ({MIN_PLAYERS})")
    if MAX_BOTS < 0:
        errors.append(f"MAX_BOTS must be >= 0 (got {MAX_BOTS})")
    
    # Role distribution
    if not ROLE_DISTRIBUTION:
        errors.append("ROLE_DISTRIBUTION is empty")
    else:
        for player_count, roles in ROLE_DISTRIBUTION.items():
            if len(roles) != player_count:
                errors.append(f"ROLE_DISTRIBUTION[{player_count}]: expected {player_count} roles, got {len(roles)}")
            
            # Check for at least one mafia and one civilian team
            mafia_roles = sum(1 for r in roles if r in ["don", "mafia", "consigliere"])
            if mafia_roles == 0:
                errors.append(f"ROLE_DISTRIBUTION[{player_count}]: no mafia roles")
    
    # Probabilities
    if not 0 <= BUKOVEL_CHANCE <= 1:
        errors.append(f"BUKOVEL_CHANCE must be 0-1 (got {BUKOVEL_CHANCE})")
    if not 0 <= POTATO_KILL_CHANCE <= 1:
        errors.append(f"POTATO_KILL_CHANCE must be 0-1 (got {POTATO_KILL_CHANCE})")
    
    # Shop items
    if ENABLE_SHOP and SHOP_ITEMS:
        for item_id, item in SHOP_ITEMS.items():
            required_keys = ["name", "description", "cost", "buff_type", "games"]
            for key in required_keys:
                if key not in item:
                    errors.append(f"SHOP_ITEMS[{item_id}]: missing key '{key}'")
    
    return len(errors) == 0, errors


# Auto-validate on import (only in production)
if not DEBUG_MODE:
    _is_valid, _errors = validate_config()
    if not _is_valid:
        import sys
        print("❌ Configuration validation failed:")
        for error in _errors:
            print(f"  - {error}")
        print("\nFix these errors in config.py before running the bot.")
        sys.exit(1)