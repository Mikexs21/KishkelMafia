

import asyncio
import random
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from telegram import Update, Message, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import RetryAfter
import math
import logging
from datetime import datetime

import config
import visual
import db
from bot_ai import bot_ai, BotAI

logger = logging.getLogger(__name__)


# ====================================================
# OPTIMIZED FLOOD CONTROL
# ====================================================

class ColoredFormatter(logging.Formatter):
    """Colored log formatter for better readability."""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

class FloodController:
    """Enhanced flood control - витримує 10+ користувачів одночасно."""
    
    def __init__(self):
        self.chat_message_times = defaultdict(list)
        self.user_action_times = defaultdict(lambda: defaultdict(list))
        
        # Збільшено ліміти для груп
        self.max_messages_per_second = 8  # Було 3, тепер 8
        self.max_user_actions_per_second = 3  # Per-user throttling
        
        self.cleanup_interval = 60
        self.last_cleanup = time.time()
        self._lock = asyncio.Lock()
    
    async def wait_if_needed(self, chat_id: int, user_id: Optional[int] = None) -> None:
        """Wait only if we're sending too fast to this specific chat."""
        async with self._lock:
            current_time = time.time()
            
            # Cleanup old records
            if current_time - self.last_cleanup > self.cleanup_interval:
                self._cleanup_old_records(current_time)
                self.last_cleanup = current_time
            
            # Per-user throttling (якщо є user_id)
            if user_id:
                user_times = self.user_action_times[chat_id][user_id]
                cutoff = current_time - 1.0
                user_times = [t for t in user_times if t > cutoff]
                self.user_action_times[chat_id][user_id] = user_times
                
                if len(user_times) >= self.max_user_actions_per_second:
                    wait_time = 1.0 - (current_time - user_times[0]) + 0.1
                    logger.debug(f"⏳ User {user_id} throttled, waiting {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                
                self.user_action_times[chat_id][user_id].append(time.time())
            
            # Per-chat throttling
            recent_messages = self.chat_message_times[chat_id]
            cutoff_time = current_time - 1.0
            recent_messages = [t for t in recent_messages if t > cutoff_time]
            self.chat_message_times[chat_id] = recent_messages
            
            if len(recent_messages) >= self.max_messages_per_second:
                wait_time = 1.0 - (current_time - recent_messages[0]) + 0.1
                logger.debug(f"⏳ Chat {chat_id} throttled, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
            
            self.chat_message_times[chat_id].append(time.time())
    
    def _cleanup_old_records(self, current_time: float) -> None:
        """Remove old message records to prevent memory leak."""
        cutoff = current_time - 10.0
        
        # Clean chat times
        for chat_id in list(self.chat_message_times.keys()):
            self.chat_message_times[chat_id] = [
                t for t in self.chat_message_times[chat_id] if t > cutoff
            ]
            if not self.chat_message_times[chat_id]:
                del self.chat_message_times[chat_id]
        
        # Clean user times
        for chat_id in list(self.user_action_times.keys()):
            for user_id in list(self.user_action_times[chat_id].keys()):
                self.user_action_times[chat_id][user_id] = [
                    t for t in self.user_action_times[chat_id][user_id] if t > cutoff
                ]
                if not self.user_action_times[chat_id][user_id]:
                    del self.user_action_times[chat_id][user_id]
            
            if not self.user_action_times[chat_id]:
                del self.user_action_times[chat_id]


# Global flood controller
_flood_controller = FloodController()


# ====================================================
# SAFE MESSAGE SENDING
# ====================================================

async def safe_send_message(context, chat_id: int, text: str, user_id: Optional[int] = None, **kwargs):
    """Send message with enhanced flood control."""
    max_retries = 3  # Збільшено з 2
    
    for attempt in range(max_retries):
        try:
            await _flood_controller.wait_if_needed(chat_id, user_id)
            return await context.bot.send_message(chat_id, text, **kwargs)
            
        except RetryAfter as e:
            if attempt < max_retries - 1:
                wait_time = e.retry_after + 0.5
                logger.warning(f"⚠️ Flood control hit (chat {chat_id}), чекаємо {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"❌ Не вдалося надіслати після {max_retries} спроб (flood)")
                return None
        except Exception as e:
            logger.error(f"❌ Помилка надсилання: {e}")
            return None


async def safe_send_animation(context, chat_id: int, animation, user_id: Optional[int] = None, **kwargs):
    """Send animation with enhanced flood control."""
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            await _flood_controller.wait_if_needed(chat_id, user_id)
            return await context.bot.send_animation(chat_id, animation, **kwargs)
            
        except RetryAfter as e:
            if attempt < max_retries - 1:
                wait_time = e.retry_after + 0.5
                logger.warning(f"⚠️ Flood на анімації (chat {chat_id}), чекаємо {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.warning("⚠️ Не вдалося надіслати анімацію, fallback на текст")
                caption = kwargs.get('caption', '')
                if caption:
                    return await safe_send_message(
                        context, chat_id, caption, user_id,
                        parse_mode=kwargs.get('parse_mode')
                    )
                return None
        except Exception as e:
            logger.error(f"❌ Помилка анімації: {e}, fallback на текст")
            caption = kwargs.get('caption', '')
            if caption:
                return await safe_send_message(
                    context, chat_id, caption, user_id,
                    parse_mode=kwargs.get('parse_mode')
                )
            return None


async def safe_edit_message(context, chat_id: int, message_id: int, text: str, **kwargs):
    """Edit message with flood control."""
    try:
        await _flood_controller.wait_if_needed(chat_id)
        return await context.bot.edit_message_text(
            text,
            chat_id=chat_id,
            message_id=message_id,
            **kwargs
        )
    except Exception as e:
        error_msg = str(e).lower()
        if "message is not modified" not in error_msg:
            logger.debug(f"Помилка редагування: {e}")
        return None


async def cancel_timer_safely(task: Optional[asyncio.Task]) -> None:
    """Cancel timer with proper cleanup."""
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error during timer cancellation: {e}")


# ====================================================
# GAME STATE CLASSES
# ====================================================

class Phase(Enum):
    LOBBY = "lobby"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    ENDED = "ended"


@dataclass
class PlayerState:
    """State of a single player."""
    player_id: str
    telegram_id: Optional[int]
    username: str
    is_bot: bool
    role: str
    is_alive: bool = True
    
    # Action tracking
    has_acted_this_night: bool = False
    night_target: Optional[str] = None
    night_action: Optional[str] = None
    
    # Role-specific state
    has_self_healed: bool = False
    has_used_gun: bool = False
    has_used_petrushka: bool = False
    has_used_executioner_immunity: bool = False
    has_thrown_potato: bool = False
    
    # Stats
    db_player_id: Optional[int] = None
    kills: int = 0
    heals: int = 0
    checks: int = 0


@dataclass
class GameState:
    """State of a single game."""
    game_id: int
    group_chat_id: int
    phase: Phase
    round_num: int = 1
    
    # Players
    players: Dict[str, PlayerState] = field(default_factory=dict)
    player_order: List[str] = field(default_factory=list)
    
    # Game settings
    is_bukovel: bool = False
    
    # Timer
    timer_task: Optional[asyncio.Task] = None
    timer_message_id: Optional[int] = None
    nomination_timer: Optional[asyncio.Task] = None

    last_words: Dict[str, str] = field(default_factory=dict)  # player_id -> message
    awaiting_last_words: Set[str] = field(default_factory=set)
    
    # Voting state
    lynch_votes: Dict[str, str] = field(default_factory=dict)
    nomination_votes: Dict[str, str] = field(default_factory=dict)
    current_candidate: Optional[str] = None
    confirmation_votes: Dict[str, str] = field(default_factory=dict)
    
    # Night resolution
    don_target: Optional[str] = None
    doctor_target: Optional[str] = None
    detective_shoot_target: Optional[str] = None
    potato_actions: List[Tuple[str, str]] = field(default_factory=list)
    check_results: Dict[str, Tuple[str, str]] = field(default_factory=dict)
    
    # Mafia chat
    mafia_messages: List[Tuple[str, str]] = field(default_factory=list)
    mafia_message_sent: Set[str] = field(default_factory=set)
    
    # DB reference
    db_game_id: Optional[int] = None
    
    # Message deletion
    messages_to_delete: Set[int] = field(default_factory=set)


class GameManager:
    """Manages all active games."""
    
    def __init__(self):
        self.games: Dict[int, GameState] = {}
        self._next_game_id = 1
        self._next_player_id = 1
    
    def create_game(self, group_chat_id: int) -> GameState:
        """Create new game for group."""
        game = GameState(
            game_id=self._next_game_id,
            group_chat_id=group_chat_id,
            phase=Phase.LOBBY
        )
        self._next_game_id += 1
        self.games[group_chat_id] = game
        return game
    
    def get_game(self, group_chat_id: int) -> Optional[GameState]:
        """Get game for group."""
        return self.games.get(group_chat_id)
    
    def remove_game(self, group_chat_id: int) -> None:
        """Remove game."""
        if group_chat_id in self.games:
            del self.games[group_chat_id]
    
    def generate_player_id(self) -> str:
        """Generate unique player ID."""
        pid = f"p{self._next_player_id}"
        self._next_player_id += 1
        return pid


# Global game manager
game_manager = GameManager()


# ====================================================
# GAME FLOW - START
# ====================================================


# ====================================================
# GAME FLOW - START
# ====================================================

async def start_game(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start game after lobby."""
    # Store game in DB
    game.db_game_id = await db.add_game(game.group_chat_id, game.is_bukovel)
    
    # Distribute roles
    await distribute_roles(game)
    
    # Save players to DB
    for pid in game.player_order:
        player = game.players[pid]
        db_player_id = await db.add_game_player(
            game.db_game_id,
            player.role,
            player.is_bot,
            user_id=await db.get_or_create_user(player.telegram_id, player.username) if not player.is_bot else None,
            bot_name=player.username if player.is_bot else None
        )
        player.db_player_id = db_player_id
    
    # Initialize bot AI memories
    for pid in game.player_order:
        player = game.players[pid]
        if player.is_bot:
            await bot_ai.get_or_create_memory(player.player_id, player.role)
    
    # Send start message
    await context.bot.send_message(
        game.group_chat_id,
        visual.START_GAME_TEXT,
        parse_mode='HTML'
    )
    
    # Bukovel announcement
    if game.is_bukovel:
        await context.bot.send_message(
            game.group_chat_id,
            visual.BUKOVEL_ANNOUNCEMENT,
            parse_mode='HTML'
        )
    
    # Send role DMs
    for pid in game.player_order:
        player = game.players[pid]
        if not player.is_bot and player.telegram_id:
            try:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.ROLE_DESCRIPTIONS[player.role],
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to send role DM to {player.username}: {e}")
    
    # Notify mafia team
    await notify_mafia_team(game, context)
    
    # Start night
    await start_night(game, context)


async def notify_mafia_team(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Notify mafia members about their team and setup mafia chat."""
    mafia_roles = {"don", "mafia", "consigliere"}
    mafia_members = [p for p in game.players.values() if p.role in mafia_roles]
    
    if len(mafia_members) <= 1:
        return
    
    # Form team list
    team_list = []
    for member in mafia_members:
        role_name = visual.ROLE_NAMES.get(member.role, member.role)
        team_list.append(f"{member.username} ({role_name})")
    
    team_text = "\n".join([f"  • {m}" for m in team_list])
    
    message = f"""🤝 <b>Твоя команда мафії:</b>

{team_text}

💬 <b>Мафійський чат:</b>
Ти можеш надіслати одне повідомлення своїй команді цієї ночі.
Просто напиши мені текст (до 200 символів)."""
    
    # Send to each mafia member
    for member in mafia_members:
        if not member.is_bot and member.telegram_id:
            try:
                await context.bot.send_message(
                    member.telegram_id,
                    message,
                    parse_mode='HTML'
                )
            except Exception as e:
                logger.error(f"Failed to send mafia team info to {member.username}: {e}")


# Виправлення для engine.py, лінія 453
# Змініть цей рядок:

# НЕПРАВИЛЬНО:
# aasync def distribute_roles(game: GameState) -> None:

# ПРАВИЛЬНО:
async def distribute_roles(game: GameState) -> None:
    """Distribute roles to players with proper validation."""
    player_count = len(game.players)
    
    # Перевірка наявності конфігурації
    if not hasattr(config, 'ROLE_DISTRIBUTION'):
        logger.error("ROLE_DISTRIBUTION not found in config!")
        # Fallback на базовий розподіл
        roles = ["don", "doctor", "detective"] + ["civilian"] * (player_count - 3)
    elif player_count in config.ROLE_DISTRIBUTION:
        roles = config.ROLE_DISTRIBUTION[player_count].copy()
    else:
        logger.warning(f"No role distribution for {player_count} players, using fallback")
        # Fallback логіка для нестандартної кількості
        roles = ["don", "mafia", "doctor", "detective"] + ["civilian"] * max(0, player_count - 4)
    
    # Check for Petrushka
    if not config.ALLOW_PETRUSHKA:
        roles = [r if r != "petrushka" else "civilian" for r in roles]
    
    # Перевірка кількості ролей
    if len(roles) != player_count:
        logger.error(f"Role count mismatch: {len(roles)} roles for {player_count} players")
        # Додати або видалити civilian для вирівнювання
        while len(roles) < player_count:
            roles.append("civilian")
        while len(roles) > player_count:
            if "civilian" in roles:
                roles.remove("civilian")
            else:
                roles.pop()
    
    # Shuffle players
    player_ids = list(game.players.keys())
    random.shuffle(player_ids)
    
    detective_assigned = False
    
    # Спочатку обробляємо FORCE_DETECTIVE для людей
    for pid in player_ids:
        player = game.players[pid]
        if player.is_bot:
            continue
        
        try:
            buffs = await db.get_user_buffs(player.telegram_id)
            for buff in buffs:
                if buff['buff_type'] == 'FORCE_DETECTIVE' and not detective_assigned:
                    if "detective" in roles:
                        player.role = "detective"
                        roles.remove("detective")
                        detective_assigned = True
                        logger.info(f"✅ Assigned Detective to {player.username} (FORCE_DETECTIVE buff)")
                        break
        except Exception as e:
            logger.error(f"Error checking buffs for {player.username}: {e}")
    
    # Потім обробляємо ACTIVE_ROLE для людей
    for pid in player_ids:
        player = game.players[pid]
        if player.is_bot or player.role:
            continue
        
        try:
            buffs = await db.get_user_buffs(player.telegram_id)
            for buff in buffs:
                if buff['buff_type'] == 'ACTIVE_ROLE':
                    active_roles = [r for r in roles if r not in ['civilian', 'petrushka', 'detective']]
                    if active_roles:
                        role = random.choice(active_roles)
                        player.role = role
                        roles.remove(role)
                        logger.info(f"✅ Assigned {role} to {player.username} (ACTIVE_ROLE buff)")
                        break
        except Exception as e:
            logger.error(f"Error checking buffs for {player.username}: {e}")
    
    # Shuffle remaining roles
    random.shuffle(roles)
    
    # Assign remaining roles
    for pid in player_ids:
        player = game.players[pid]
        if player.role:
            continue
        
        if not roles:
            player.role = "civilian"
            logger.warning(f"No roles left, assigned civilian to {player.username}")
            continue
        
        if player.is_bot:
            # Боти не можуть бути детективом
            available = [r for r in roles if r != "detective"]
            if available:
                role = random.choice(available)
                player.role = role
                roles.remove(role)
            else:
                # Якщо залишився тільки detective - даємо civilian
                player.role = "civilian"
                if "detective" in roles:
                    roles.remove("detective")
                    roles.append("civilian")
        else:
            # Люди можуть бути будь-ким
            role = random.choice(roles)
            player.role = role
            roles.remove(role)
        
        logger.info(f"Assigned {player.role} to {player.username}")
    
    game.player_order = player_ids


# ====================================================
# NIGHT PHASE
# ====================================================

async def start_night(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start night phase with flood control."""
    game.phase = Phase.NIGHT
    
    # Reset night actions
    for player in game.players.values():
        player.has_acted_this_night = False
        player.night_target = None
        player.night_action = None
    
    game.don_target = None
    game.doctor_target = None
    game.detective_shoot_target = None
    game.potato_actions = []
    game.check_results = {}
    game.mafia_messages = []
    game.mafia_message_sent = set()
    
    # Initialize critical flags
    game._resolving_night = False
    game._action_log_batch = []
    game._action_log_task = None
    
    # Update bot AI round tracking
    for pid in game.player_order:
        player = game.players[pid]
        if player.is_bot and player.is_alive:
            await bot_ai.new_round(player.player_id)
    
    logger.info(visual.format_game_log(game.game_id, game.round_num, "NIGHT", "Night started"))
    
    # Send night GIF
    try:
        with open("gifs/night.gif", "rb") as gif_file:
            await safe_send_animation(
                context,
                game.group_chat_id,
                animation=gif_file,
                caption=visual.NIGHT_START_TEXT,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.warning(f"Failed to load night GIF: {e}")
        await safe_send_message(
            context,
            game.group_chat_id,
            visual.NIGHT_START_TEXT,
            parse_mode='HTML'
        )
    
    # Delay before action prompts
    await asyncio.sleep(1.5)
    
    # Send night action prompts
    await send_night_action_prompts(game, context)
    
    # Delay before timer
    await asyncio.sleep(1)
    
    # Start timer
    await start_timer(game, context, config.NIGHT_DURATION, "night")


async def send_night_action_prompts(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send DM prompts for night actions with delays."""
    delay_between_prompts = 0.3
    
    for pid in game.player_order:
        player = game.players[pid]
        if not player.is_alive:
            continue
        
        if player.is_bot:
            asyncio.create_task(execute_bot_night_action(game, player, context))
        else:
            await send_player_night_prompt(game, player, context)
            await asyncio.sleep(delay_between_prompts)


async def send_player_night_prompt(game: GameState, player: PlayerState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send night action prompt to human player."""
    if not player.telegram_id:
        return
    
    try:
        if player.role == "don":
            targets = get_available_targets(game, player, exclude_mafia=True)
            if targets:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["don"],
                    reply_markup=visual.get_don_keyboard(targets),
                    parse_mode='HTML'
                )
        
        elif player.role == "mafia" and is_mafia_acting_don(game):
            targets = get_available_targets(game, player, exclude_mafia=True)
            if targets:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["mafia"],
                    reply_markup=visual.get_don_keyboard(targets),
                    parse_mode='HTML'
                )
        
        elif player.role == "doctor":
            targets = get_available_targets(game, player, include_self=not player.has_self_healed)
            if targets:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["doctor"],
                    reply_markup=visual.get_doctor_keyboard(targets, not player.has_self_healed),
                    parse_mode='HTML'
                )
        
        elif player.role == "detective":
            # 🔧 ВИПРАВЛЕНО: Строга перевірка пістолета
            if player.has_used_gun:
                # Якщо вже стріляв - ТІЛЬКИ перевірка
                targets = get_available_targets(game, player, include_self=False)
                if targets:
                    await context.bot.send_message(
                        player.telegram_id,
                        "🔍 <b>Пістолет вже використано!</b>\n\n"
                        "Тепер можеш тільки перевіряти ролі гравців.\n\n"
                        "Обери кого перевірити:",
                        reply_markup=visual.get_detective_target_keyboard(targets, "check"),
                        parse_mode='HTML'
                    )
                logger.info(f"🔫 {player.username} вже використав пістолет, тільки перевірка")
            else:
                # Повний вибір дій
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["detective"],
                    reply_markup=visual.get_detective_action_keyboard(),
                    parse_mode='HTML'
                )
        
        elif player.role == "deputy":
            targets = get_available_targets(game, player, include_self=False)
            if targets:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["deputy"],
                    reply_markup=visual.get_detective_target_keyboard(targets, "check"),
                    parse_mode='HTML'
                )
        
        elif player.role == "consigliere":
            targets = get_available_targets(game, player, include_self=False)
            if targets:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["consigliere"],
                    reply_markup=visual.get_detective_target_keyboard(targets, "check"),
                    parse_mode='HTML'
                )
        
        elif player.role == "civilian" and game.is_bukovel and game.round_num == 1 and not player.has_thrown_potato:
            targets = get_available_targets(game, player, include_self=False)
            if targets:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["potato"],
                    reply_markup=visual.get_potato_keyboard(targets),
                    parse_mode='HTML'
                )
        
        elif player.role == "petrushka" and not player.has_used_petrushka:
            targets = get_available_targets(game, player, include_self=False)
            if targets:
                await context.bot.send_message(
                    player.telegram_id,
                    visual.NIGHT_ACTION_PROMPTS["petrushka"],
                    reply_markup=visual.get_petrushka_keyboard(targets),
                    parse_mode='HTML'
                )
    
    except Exception as e:
        logger.error(f"Помилка надсилання нічного промпту до {player.username}: {e}")


async def execute_bot_night_action(game: GameState, bot: PlayerState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute bot's night action automatically using advanced AI."""
    await asyncio.sleep(random.uniform(2, 8))
    
    if not bot.is_alive:
        return
    
    if bot.role == "don":
        target_id = await bot_ai.select_kill_target(game, bot)
        if target_id:
            game.don_target = target_id
            bot.has_acted_this_night = True
            target_name = game.players[target_id].username
            logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "DON", "KILL", target_name))
            await log_action_in_group(game, context, "don_chose")
    
    elif bot.role == "mafia" and is_mafia_acting_don(game):
        target_id = await bot_ai.select_kill_target(game, bot)
        if target_id:
            game.don_target = target_id
            bot.has_acted_this_night = True
            target_name = game.players[target_id].username
            logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "MAFIA", "KILL", target_name))
            await log_action_in_group(game, context, "mafia_chose")
    
    elif bot.role == "doctor":
        target_id = await bot_ai.select_heal_target(game, bot)
        if target_id:
            game.doctor_target = target_id
            if target_id == bot.player_id:
                bot.has_self_healed = True
            bot.has_acted_this_night = True
            target_name = game.players[target_id].username
            logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "DOCTOR", "HEAL", target_name))
            await log_action_in_group(game, context, "doctor_chose")
    
    elif bot.role == "detective":
        if await bot_ai.should_detective_shoot(game, bot):
            target_id = await bot_ai.select_shoot_target(game, bot)
            if target_id:
                game.detective_shoot_target = target_id
                bot.has_used_gun = True
                bot.has_acted_this_night = True
                target_name = game.players[target_id].username
                logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "DETECTIVE", "SHOOT", target_name))
                await log_action_in_group(game, context, "detective_chose")
        else:
            target_id = await bot_ai.select_check_target(game, bot)
            if target_id:
                target = game.players[target_id]
                game.check_results[bot.player_id] = (target_id, target.role)
                bot.has_acted_this_night = True
                bot.checks += 1
                
                await bot_ai.process_check_result(bot.player_id, target_id, target.role)
                
                logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "DETECTIVE", "CHECK", target.username))
                await log_action_in_group(game, context, "detective_chose")
    
    elif bot.role == "deputy":
        target_id = await bot_ai.select_check_target(game, bot)
        if target_id:
            target = game.players[target_id]
            game.check_results[bot.player_id] = (target_id, target.role)
            bot.has_acted_this_night = True
            bot.checks += 1
            
            await bot_ai.process_check_result(bot.player_id, target_id, target.role)
            
            logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "DEPUTY", "CHECK", target.username))
            await log_action_in_group(game, context, "deputy_chose")
    
    elif bot.role == "consigliere":
        target_id = await bot_ai.select_check_target(game, bot)
        if target_id:
            target = game.players[target_id]
            game.check_results[bot.player_id] = (target_id, target.role)
            bot.has_acted_this_night = True
            bot.checks += 1
            
            await bot_ai.process_check_result(bot.player_id, target_id, target.role)
            
            # 🔧 ВИПРАВЛЕНО: Надіслати результат усій команді мафії
            mafia_roles = {"don", "mafia", "consigliere"}
            for p in game.players.values():
                if p.role in mafia_roles and p.is_alive and not p.is_bot and p.telegram_id:
                    try:
                        await context.bot.send_message(
                            p.telegram_id,
                            f"🎭 <b>Консильєрі дізнався:</b>\n\n"
                            f"<b>{target.username}</b> - {visual.ROLE_NAMES[target.role]}",
                            parse_mode='HTML'
                        )
                    except Exception as e:
                        logger.error(f"Failed to send consigliere result to {p.username}: {e}")
            
            logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "CONSIGLIERE", "CHECK", target.username))
            await log_action_in_group(game, context, "consigliere_chose")
    
    elif bot.role == "civilian" and game.is_bukovel and game.round_num == 1 and not bot.has_thrown_potato:
        if random.random() < 0.5:
            targets = get_available_targets(game, bot, include_self=False)
            if targets:
                target_name, target_id = random.choice(targets)
                game.potato_actions.append((bot.player_id, target_id))
                bot.has_thrown_potato = True
                bot.has_acted_this_night = True
                logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "POTATO", "THROW", target_name))
    
    elif bot.role == "petrushka" and not bot.has_used_petrushka:
        if random.random() < 0.3 and game.round_num >= 2:
            targets = get_available_targets(game, bot, include_self=False)
            if targets:
                target_name, target_id = random.choice(targets)
                # Використовуємо callback для правильної логіки
                await handle_petrushka_callback(game, bot, target_id, context)
    
    await check_all_night_actions_done(game, context)

async def handle_voting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voting callbacks with flood control."""
    query = update.callback_query
    
    chat_id = query.message.chat.id
    game = game_manager.get_game(chat_id)
    
    if not game or game.phase == Phase.ENDED:
        try:
            await query.answer("❌ Гра завершена", show_alert=True)
        except:
            pass
        return
    
    if game.phase != Phase.VOTING:
        try:
            await query.answer("❌ Зараз не голосування", show_alert=True)
        except:
            pass
        return
    
    user_id = query.from_user.id
    data = query.data
    
    # Find player
    player = None
    for p in game.players.values():
        if p.telegram_id == user_id:
            player = p
            break
    
    if not player or not player.is_alive:
        try:
            await query.answer("❌ Ти не можеш голосувати", show_alert=True)
        except:
            pass
        return
    
    if data in ["lynch_yes", "lynch_no"]:
        vote = "yes" if data == "lynch_yes" else "no"
        
        # Check duplicate vote
        if player.player_id in game.lynch_votes:
            old_vote = game.lynch_votes[player.player_id]
            if old_vote == vote:
                try:
                    await query.answer("❌ Ти вже проголосував!", show_alert=True)
                except:
                    pass
                return
            else:
                try:
                    await query.answer(f"🔄 Змінено голос на: {'Так' if vote == 'yes' else 'Ні'}")
                except:
                    pass
        else:
            try:
                await query.answer(f"✅ Твій голос: {'Так' if vote == 'yes' else 'Ні'}")
            except Exception as e:
                error_msg = str(e).lower()
                if "too old" not in error_msg and "expired" not in error_msg:
                    logger.error(f"Vote answer error: {e}")
        
        game.lynch_votes[player.player_id] = vote
        
        # Calculate with mayor weight
        yes_count = 0
        no_count = 0
        
        for voter_id, v in game.lynch_votes.items():
            voter = game.players[voter_id]
            weight = 2 if voter.role == "mayor" else 1
            if v == "yes":
                yes_count += weight
            else:
                no_count += weight
        
        alive_count = sum(1 for p in game.players.values() if p.is_alive)
        
        mayor_indicator = " 🎩x2" if player.role == "mayor" else ""
        vote_emoji = "👍" if vote == "yes" else "👎"
        
        await asyncio.sleep(0.5)
        await safe_send_message(
            context,
            game.group_chat_id,
            f"{vote_emoji} <b>{player.username}</b>{mayor_indicator} проголосував\n\n"
            f"📊 Так: {yes_count}/{alive_count} | Ні: {no_count}/{alive_count}",
            parse_mode='HTML'
        )
        
        logger.info(visual.format_action_log(
            game.game_id, game.round_num, player.username,
            "VOTE", f"LYNCH_{vote.upper()}"
        ))
        
        # Update keyboard
        try:
            await query.message.edit_reply_markup(
                reply_markup=visual.get_lynch_decision_keyboard_with_count(yes_count, no_count, alive_count)
            )
        except:
            pass
        
        # Check if all voted
        if len(game.lynch_votes) >= alive_count:
            logger.info("All players voted on lynch decision")
            await handle_lynch_decision_complete(game, context)

async def log_action_in_group(game: GameState, context: ContextTypes.DEFAULT_TYPE, action_key: str) -> None:
    """Log action in group with unique messages for each role."""
    
    # Унікальне повідомлення для кожної ролі
    message = None
    
    if action_key == "don_chose":
        message = "☠️ Дон зробив свій вибір..."
    elif action_key == "mafia_chose":
        message = "🔪 Мафія обрала жертву..."
    elif action_key == "doctor_chose":
        message = "💉 Лікар вже комусь клеїть шви..."
    elif action_key == "detective_chose":
        message = "🔍 Детектив на слідстві..."
    elif action_key == "deputy_chose":
        message = "🔎 Заступник шукає відповіді..."
    elif action_key == "consigliere_chose":
        message = "🎭 Консильєрі збирає інформацію..."
    
    if message:
        await safe_send_message(
            context,
            game.group_chat_id,
            message,
            parse_mode='HTML'
        )
        
        game._action_log_batch = []
    


def get_available_targets(game: GameState, player: PlayerState, 
                          exclude_mafia: bool = False,
                          include_self: bool = False) -> List[Tuple[str, str]]:
    """Get list of available targets for player."""
    targets = []
    mafia_roles = {"don", "mafia", "consigliere"}
    
    for pid in game.player_order:
        target = game.players[pid]
        if not target.is_alive:
            continue
        if pid == player.player_id and not include_self:
            continue
        if exclude_mafia and target.role in mafia_roles:
            continue
        
        targets.append((target.username, pid))
    
    return targets


def is_mafia_acting_don(game: GameState) -> bool:
    """Check if mafia should act as don (don is dead)."""
    don_alive = any(p.is_alive and p.role == "don" for p in game.players.values())
    return not don_alive


async def check_all_night_actions_done(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Check if all players have acted and resolve night early.
    
    ✅ ЗАХИСТ:
    - Lock
    - Processing flag
    - Phase check
    """
    
    if game.phase != Phase.NIGHT:
        return
    
    if not hasattr(game, '_night_resolution_lock'):
        game._night_resolution_lock = asyncio.Lock()
    
    # Не блокувати якщо вже обробляється
    if game._night_resolution_lock.locked():
        logger.debug("Night resolution busy, пропускаємо")
        return
    
    async with game._night_resolution_lock:
        # Processing flag
        if hasattr(game, '_resolving_night') and game._resolving_night:
            logger.debug("Night вже розв'язується, пропускаємо")
            return
        
        # Перевірити чи всі зробили дії
        for player in game.players.values():
            if not player.is_alive:
                continue
            
            # Skip civilians (unless bukovel potato)
            if player.role == "civilian":
                if game.is_bukovel and game.round_num == 1 and not player.has_thrown_potato:
                    if not player.has_acted_this_night:
                        return
                continue
            
            # Skip used petrushka
            if player.role == "petrushka" and player.has_used_petrushka:
                continue
            
            # Active roles must act
            if player.role in ["don", "doctor", "detective", "deputy", "consigliere"]:
                if not player.has_acted_this_night:
                    return
            
            # Mafia acts if don dead
            if player.role == "mafia" and is_mafia_acting_don(game):
                if not player.has_acted_this_night:
                    return
        
        # All done!
        logger.info("✅ Всі дії завершені, розв'язуємо ніч достроково")
        game._resolving_night = True
        
        # Cancel timer
        if game.timer_task and not game.timer_task.done():
            game.timer_task.cancel()
            try:
                await game.timer_task
                logger.info("Timer скасовано (early resolution)")
            except asyncio.CancelledError:
                pass
        
        await resolve_night(game, context)

async def request_last_words(game: GameState, context: ContextTypes.DEFAULT_TYPE, 
                             dead_player_ids: List[str]) -> None:
    """Request last words from dying players."""
    if not config.LAST_WORDS_ENABLED:
        return
    
    for pid in dead_player_ids:
        player = game.players[pid]
        
        # Skip bots
        if player.is_bot or not player.telegram_id:
            continue
        
        # Mark as awaiting
        game.awaiting_last_words.add(pid)
        
        try:
            await context.bot.send_message(
                player.telegram_id,
                f"💀 <b>Тебе вбили!</b>\n\n"
                f"У тебе є {config.LAST_WORDS_TIMEOUT} секунд написати свої останні слова.\n"
                f"Просто надішли мені повідомлення - воно буде передане всім гравцям.\n\n"
                f"<i>Можна писати що завгодно (до 200 символів)</i>",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to send last words request to {player.username}: {e}")
    
    # Wait for responses
    if game.awaiting_last_words:
        await asyncio.sleep(config.LAST_WORDS_TIMEOUT)


async def broadcast_last_words(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast collected last words to the group."""
    if not game.last_words:
        return
    
    for pid, message in game.last_words.items():
        player = game.players[pid]
        
        await safe_send_message(
            context,
            game.group_chat_id,
            f"💬 <b>Останні слова {player.username}:</b>\n\n"
            f"<i>\"{message}\"</i>",
            parse_mode='HTML'
        )
        await asyncio.sleep(0.5)
    
    # Clear
    game.last_words.clear()
    game.awaiting_last_words.clear()

"""
ФІХ #1: Останні слова тепер показуються ПРАВИЛЬНО
Замінити функції resolve_night() і start_day() в engine.py
"""

async def resolve_night(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Resolve all night actions.
    
    ✅ ВИПРАВЛЕНА ЛОГІКА:
    1. Збираємо потенційні смерті
    2. Застосовуємо лікаря
    3. Повідомляємо жертв (врятовані/помираючі)
    4. Чекаємо останні слова ТІЛЬКИ від помираючих
    5. Показуємо результати
    """
    
    logger.info(visual.format_game_log(game.game_id, game.round_num, "NIGHT", "🌙 Розв'язуємо ніч"))
    
    # КРОК 1: Збираємо потенційні смерті
    potential_deaths = set()
    
    if game.don_target:
        potential_deaths.add(game.don_target)
        logger.info(f"🔪 Дон → {game.players[game.don_target].username}")
    
    if game.detective_shoot_target:
        potential_deaths.add(game.detective_shoot_target)
        logger.info(f"🔫 Детектив → {game.players[game.detective_shoot_target].username}")
    
    # Potato kills
    for thrower_id, target_id in game.potato_actions:
        if random.random() < config.POTATO_KILL_CHANCE:
            potential_deaths.add(target_id)
            thrower = game.players[thrower_id]
            target = game.players[target_id]
            logger.info(f"🥔💥 {thrower.username} → {target.username}")
            await safe_send_message(
                context,
                game.group_chat_id,
                visual.POTATO_RESULT_HIT.format(name=target.username),
                parse_mode='HTML'
            )
            await asyncio.sleep(0.5)
        else:
            target = game.players[target_id]
            logger.info(f"🥔 Промах → {target.username}")
            await safe_send_message(
                context,
                game.group_chat_id,
                visual.POTATO_RESULT_MISS.format(name=target.username),
                parse_mode='HTML'
            )
            await asyncio.sleep(0.5)
    
    # КРОК 2: Застосовуємо лікаря
    saved_player_id = None
    
    if game.doctor_target and game.doctor_target in potential_deaths:
        potential_deaths.remove(game.doctor_target)
        saved_player_id = game.doctor_target
        logger.info(f"💚 Лікар врятував: {game.players[saved_player_id].username}")
        
        # Award heal
        for p in game.players.values():
            if p.role == "doctor" and p.is_alive:
                p.heals += 1
                if not p.is_bot:
                    await db.update_user_stats(
                        await db.get_or_create_user(p.telegram_id, p.username),
                        saves=1
                    )
    
    # КРОК 3: Повідомляємо жертв про замахи
    attempted_targets = []
    if game.don_target:
        attempted_targets.append(game.don_target)
    if game.detective_shoot_target:
        attempted_targets.append(game.detective_shoot_target)
    
    for target_id in set(attempted_targets):
        target = game.players[target_id]
        
        if target.is_bot or not target.telegram_id:
            continue
        
        was_saved = target_id == saved_player_id
        will_die = target_id in potential_deaths
        
        try:
            if was_saved:
                # 🎉 ВРЯТУВАЛИ
                await context.bot.send_message(
                    target.telegram_id,
                    "🚑 <b>ТЕБЕ ВРЯТУВАЛИ!</b>\n\n"
                    "На тебе скоїли замах, але лікар прибіг вчасно!\n\n"
                    "✨ <b>От і вдача!</b> Ти живий!",
                    parse_mode='HTML'
                )
                logger.info(f"💚 {target.username} врятовано - повідомлено")
            
            elif will_die:
                # 💀 ПОМРЕШ
                await context.bot.send_message(
                    target.telegram_id,
                    f"⚠️ <b>НА ТЕБЕ СКОЇЛИ ЗАМАХ!</b>\n\n"
                    f"Лікар не встиг... Це кінець.\n\n"
                    f"У тебе <b>{config.LAST_WORDS_TIMEOUT}с</b> написати останні слова.\n\n"
                    f"<i>Надішли текст (до 200 символів)</i>",
                    parse_mode='HTML'
                )
                game.awaiting_last_words.add(target_id)
                logger.info(f"💀 {target.username} помирає - запит останніх слів")
        
        except Exception as e:
            logger.error(f"Помилка повідомлення {target.username}: {e}")
    
    # КРОК 4: Чекаємо останні слова
    if game.awaiting_last_words and config.LAST_WORDS_ENABLED:
        logger.info(f"⏳ Чекаємо {config.LAST_WORDS_TIMEOUT}с на останні слова")
        await asyncio.sleep(config.LAST_WORDS_TIMEOUT)
        logger.info(f"✅ Отримано {len(game.last_words)} останніх слів")
    
    # КРОК 5: Застосовуємо смерті
    deaths = list(potential_deaths)
    
    for pid in deaths:
        player = game.players[pid]
        player.is_alive = False
        logger.info(f"💀 {player.username} помер ({player.role})")
        
        if player.db_player_id:
            await db.update_game_player_stats(player.db_player_id, is_alive=0)
        
        # Bot AI learns
        from bot_ai import bot_ai
        for bot_pid in game.player_order:
            bot = game.players[bot_pid]
            if bot.is_bot and bot.is_alive:
                await bot_ai.observe_death(bot.player_id, pid, player.role)
        
        # Award kills
        if game.don_target == pid:
            for p in game.players.values():
                if p.role in ["don", "mafia"] and p.is_alive:
                    p.kills += 1
                    if not p.is_bot:
                        await db.update_user_stats(
                            await db.get_or_create_user(p.telegram_id, p.username),
                            kills=1
                        )
    
    # КРОК 6: Надіслати результати перевірок
    for checker_id, (target_id, target_role) in game.check_results.items():
        checker = game.players[checker_id]
        target = game.players[target_id]
        
        if not checker.is_bot and checker.telegram_id:
            try:
                await context.bot.send_message(
                    checker.telegram_id,
                    visual.CHECK_RESULT.format(
                        name=target.username,
                        role=visual.ROLE_NAMES[target_role]
                    ),
                    parse_mode='HTML'
                )
                logger.info(f"🔍 {checker.username} → {target.username}: {target_role}")
            except Exception as e:
                logger.error(f"Помилка перевірки: {e}")
    
    # КРОК 7: Надіслати повідомлення про дії
    await send_night_notifications(game, context, deaths, saved_player_id)
    
    # КРОК 8: Визначити події
    events = []
    if len(deaths) == 0:
        if saved_player_id:
            events.append("doc_saved")
        else:
            events.append("event_everyone_alive")
    elif len(deaths) == 1:
        events.append("event_single_death")
        
        dead_player = game.players[deaths[0]]
        if dead_player.role == "don":
            if any(p.is_alive and p.role == "mafia" for p in game.players.values()):
                events.append("don_dead_mafia_alive")
            else:
                events.append("don_dead_no_mafia")
        elif dead_player.role == "doctor":
            events.append("doc_dead")
        elif dead_player.role == "detective":
            events.append("detective_dead")
        elif dead_player.role == "civilian":
            events.append("civil_dead")
    else:
        events.append("event_both_died")
    
    # КРОК 9: Перехід до дня
    if hasattr(game, '_day_started') and game._day_started:
        logger.warning("⚠️ День вже почався")
        return
    
    game._day_started = True
    game._resolving_night = False
    
    await asyncio.sleep(2)
    
    await start_day(game, context, events, deaths)

async def send_night_notifications(game: GameState, context: ContextTypes.DEFAULT_TYPE,
                                   deaths: List[str], saved_player_id: Optional[str]) -> None:
    """Send notifications to players about night results."""
    
    # Notify mafia
    if game.don_target:
        target = game.players[game.don_target]
        killed = game.don_target in deaths
        
        mafia_roles = {"don", "mafia", "consigliere"}
        for p in game.players.values():
            if p.role in mafia_roles and p.is_alive and not p.is_bot and p.telegram_id:
                try:
                    if killed:
                        await context.bot.send_message(
                            p.telegram_id,
                            f"☠️ <b>Місія виконана!</b>\n\n"
                            f"{target.username} більше не проблема.",
                            parse_mode='HTML'
                        )
                    else:
                        await context.bot.send_message(
                            p.telegram_id,
                            f"💔 <b>Невдача!</b>\n\n"
                            f"{target.username} вижив...",
                            parse_mode='HTML'
                        )
                except Exception as e:
                    logger.error(f"Помилка мафія-нотіфікації: {e}")
    
    # Notify doctor
    if game.doctor_target:
        for p in game.players.values():
            if p.role == "doctor" and p.is_alive and not p.is_bot and p.telegram_id:
                target = game.players[game.doctor_target]
                saved = game.doctor_target == saved_player_id
                
                try:
                    if saved:
                        await context.bot.send_message(
                            p.telegram_id,
                            f"💚 <b>Врятував!</b>\n\n"
                            f"Ти врятував {target.username}!",
                            parse_mode='HTML'
                        )
                    else:
                        await context.bot.send_message(
                            p.telegram_id,
                            f"😔 <b>Нікого не атакували...</b>\n\n"
                            f"{target.username} був у безпеці.",
                            parse_mode='HTML'
                        )
                except Exception as e:
                    logger.error(f"Помилка доктор-нотіфікації: {e}")
    
    # Notify detective about shoot
    if game.detective_shoot_target:
        for p in game.players.values():
            if p.role == "detective" and p.is_alive and not p.is_bot and p.telegram_id:
                target = game.players[game.detective_shoot_target]
                killed = game.detective_shoot_target in deaths
                
                try:
                    if killed:
                        await context.bot.send_message(
                            p.telegram_id,
                            f"🔫 <b>Влучив!</b>\n\n"
                            f"{target.username} більше не загроза.",
                            parse_mode='HTML'
                        )
                    else:
                        await context.bot.send_message(
                            p.telegram_id,
                            f"😬 <b>Промах...</b>\n\n"
                            f"{target.username} вижив.",
                            parse_mode='HTML'
                        )
                except Exception as e:
                    logger.error(f"Помилка детектив-нотіфікації: {e}")

async def start_day(game: GameState, context: ContextTypes.DEFAULT_TYPE,
                    events: List[str], deaths: List[str]) -> None:
    """Start day phase with flood control."""
    
    # Скидаємо прапорець для наступного раунду
    game._day_started = False
    
    game.phase = Phase.DAY
    
    logger.info(visual.format_game_log(game.game_id, game.round_num, "DAY", "☀️ День почався"))
    
    # Send morning GIF
    try:
        with open("gifs/morning.gif", "rb") as gif_file:
            await safe_send_animation(
                context,
                game.group_chat_id,
                animation=gif_file,
                caption=visual.MORNING_GIF_TEXT,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.warning(f"Не вдалося надіслати GIF ранку: {e}")
        await safe_send_message(
            context,
            game.group_chat_id,
            visual.MORNING_GIF_TEXT,
            parse_mode='HTML'
        )
    
    await asyncio.sleep(1.5)
    
    # 🔧 ВИПРАВЛЕНО: Показуємо останні слова ТІЛЬКИ ТУТ
    if game.last_words:
        logger.info(f"💬 Показуємо останні слова від {len(game.last_words)} гравців")
        await broadcast_last_words(game, context)
        await asyncio.sleep(1)
    
    # Build event details
    details = {}
    if deaths:
        if len(deaths) == 1:
            dead = game.players[deaths[0]]
            details['name'] = dead.username
            details['role_reveal'] = f"Це був {visual.ROLE_NAMES[dead.role]}."
        elif len(deaths) >= 2:
            dead1 = game.players[deaths[0]]
            dead2 = game.players[deaths[1]]
            details['name1'] = dead1.username
            details['name2'] = dead2.username
            details['role_reveal'] = f"{dead1.username} - {visual.ROLE_NAMES[dead1.role]}, {dead2.username} - {visual.ROLE_NAMES[dead2.role]}."
    
    # Send morning report
    report = visual.format_morning_report(events, details)
    
    # Add stats
    alive_humans = [p.username for p in game.players.values() if p.is_alive and not p.is_bot]
    alive_bots = [p.username for p in game.players.values() if p.is_alive and p.is_bot]
    dead_humans = [p.username for p in game.players.values() if not p.is_alive and not p.is_bot]
    dead_bots = [p.username for p in game.players.values() if not p.is_alive and p.is_bot]
    
    stats = visual.format_stats_block(alive_humans, alive_bots, dead_humans, dead_bots)
    
    await safe_send_message(
        context,
        game.group_chat_id,
        report + stats,
        parse_mode='HTML'
    )
    
    # Check win conditions
    if await check_win_condition(game, context):
        return
    
    await asyncio.sleep(1)
    
    # Start timer
    await start_timer(game, context, config.DAY_DURATION, "day")


async def request_last_words(game: GameState, context: ContextTypes.DEFAULT_TYPE, 
                             dead_player_ids: List[str]) -> None:
    """Request last words from dying players."""
    if not config.LAST_WORDS_ENABLED:
        return
    
    human_deaths = []
    
    for pid in dead_player_ids:
        player = game.players[pid]
        
        # Skip bots
        if player.is_bot or not player.telegram_id:
            continue
        
        human_deaths.append(pid)
        
        # Mark as awaiting
        game.awaiting_last_words.add(pid)
        
        try:
            await context.bot.send_message(
                player.telegram_id,
                f"💀 <b>Тебе вбили!</b>\n\n"
                f"У тебе є {config.LAST_WORDS_TIMEOUT} секунд написати свої останні слова.\n"
                f"Просто надішли мені повідомлення - воно буде передане всім гравцям.\n\n"
                f"<i>Можна писати що завгодно (до 200 символів)</i>",
                parse_mode='HTML'
            )
            logger.info(f"💬 Запит останніх слів надіслано: {player.username}")
        except Exception as e:
            logger.error(f"Помилка надсилання запиту останніх слів до {player.username}: {e}")
    
    # Wait for responses
    if human_deaths:
        logger.info(f"⏳ Чекаємо {config.LAST_WORDS_TIMEOUT}с на останні слова від {len(human_deaths)} гравців")
        await asyncio.sleep(config.LAST_WORDS_TIMEOUT)
        logger.info(f"✅ Отримано {len(game.last_words)}/{len(human_deaths)} останніх слів")


async def broadcast_last_words(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Broadcast collected last words to the group."""
    if not game.last_words:
        logger.info("ℹ️ Немає останніх слів для показу")
        return
    
    logger.info(f"📢 Показуємо {len(game.last_words)} останніх слів у групі")
    
    for pid, message in game.last_words.items():
        player = game.players[pid]
        
        await safe_send_message(
            context,
            game.group_chat_id,
            f"💬 <b>Останні слова {player.username}:</b>\n\n"
            f"<i>\"{message}\"</i>",
            parse_mode='HTML'
        )
        logger.info(f"💬 Показано останні слова від {player.username}")
        await asyncio.sleep(0.7)
    
    # Clear
    game.last_words.clear()
    game.awaiting_last_words.clear()
    logger.info("🧹 Останні слова очищено")

# ====================================================
# DAY PHASE
# ====================================================

async def start_day(game: GameState, context: ContextTypes.DEFAULT_TYPE,
                    events: List[str], deaths: List[str]) -> None:
    """Start day phase with flood control."""
    
    # Скидаємо прапорець для наступного раунду
    game._day_started = False
    
    game.phase = Phase.DAY
    
    logger.info(visual.format_game_log(game.game_id, game.round_num, "DAY", "Day started"))
    
    # Send morning GIF
    try:
        with open("gifs/morning.gif", "rb") as gif_file:
            await safe_send_animation(
                context,
                game.group_chat_id,
                animation=gif_file,
                caption=visual.MORNING_GIF_TEXT,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.warning(f"Failed to send morning GIF: {e}")
        await safe_send_message(
            context,
            game.group_chat_id,
            visual.MORNING_GIF_TEXT,
            parse_mode='HTML'
        )
    
    await asyncio.sleep(1.5)
    
    # 🆕 НОВИЙ КОД: Показати останні слова
    if game.last_words:
        await broadcast_last_words(game, context)
        await asyncio.sleep(1)
    
    # Build event details
    details = {}
    if deaths:
        if len(deaths) == 1:
            dead = game.players[deaths[0]]
            details['name'] = dead.username
            details['role_reveal'] = f"Це був {visual.ROLE_NAMES[dead.role]}."
        elif len(deaths) >= 2:
            dead1 = game.players[deaths[0]]
            dead2 = game.players[deaths[1]]
            details['name1'] = dead1.username
            details['name2'] = dead2.username
            details['role_reveal'] = f"{dead1.username} - {visual.ROLE_NAMES[dead1.role]}, {dead2.username} - {visual.ROLE_NAMES[dead2.role]}."
    
    # Send morning report
    report = visual.format_morning_report(events, details)
    
    # Add stats
    alive_humans = [p.username for p in game.players.values() if p.is_alive and not p.is_bot]
    alive_bots = [p.username for p in game.players.values() if p.is_alive and p.is_bot]
    dead_humans = [p.username for p in game.players.values() if not p.is_alive and not p.is_bot]
    dead_bots = [p.username for p in game.players.values() if not p.is_alive and p.is_bot]
    
    stats = visual.format_stats_block(alive_humans, alive_bots, dead_humans, dead_bots)
    
    await safe_send_message(
        context,
        game.group_chat_id,
        report + stats,
        parse_mode='HTML'
    )
    
    # Check win conditions
    if await check_win_condition(game, context):
        return
    
    await asyncio.sleep(1)
    
    # Start timer
    await start_timer(game, context, config.DAY_DURATION, "day")


# ====================================================
# VOTING PHASE
# ====================================================

async def start_voting(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start voting phase."""
    game.phase = Phase.VOTING
    game.lynch_votes = {}
    game.nomination_votes = {}
    game.current_candidate = None
    game.confirmation_votes = {}
    
    logger.info(visual.format_game_log(game.game_id, game.round_num, "VOTING", "Voting started"))
    
    # Send voting message
    try:
        with open("gifs/vote.gif", "rb") as gif_file:
            await context.bot.send_animation(
                game.group_chat_id,
                animation=gif_file,
                caption=visual.VOTING_START_TEXT,
                parse_mode='HTML'
            )
    except Exception as e:
        logger.warning(f"Failed to send voting GIF: {e}")
        await context.bot.send_message(
            game.group_chat_id,
            visual.VOTING_START_TEXT,
            parse_mode='HTML'
        )
    
    # Ask if want to lynch
    alive_count = sum(1 for p in game.players.values() if p.is_alive)
    await context.bot.send_message(
        game.group_chat_id,
        "Ріжемо когось?",
        reply_markup=visual.get_lynch_decision_keyboard_with_count(0, 0, alive_count),
        parse_mode='HTML'
    )
    
    # Bots vote on lynch decision
    for pid in game.player_order:
        player = game.players[pid]
        if player.is_bot and player.is_alive:
            await execute_bot_lynch_vote(game, player)
    
    # Start timer
    await start_timer(game, context, config.VOTING_DURATION, "voting")


async def execute_bot_lynch_vote(game: GameState, bot: PlayerState) -> None:
    """Execute bot's lynch decision vote."""
    await asyncio.sleep(random.uniform(1, 5))
    
    mafia_roles = {"don", "mafia", "consigliere"}
    if bot.role in mafia_roles:
        vote = "yes" if random.random() < 0.75 else "no"
    else:
        vote = "yes" if random.random() < 0.6 else "no"
    
    game.lynch_votes[bot.player_id] = vote
    logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "BOT", f"LYNCH_{vote.upper()}", ""))



async def handle_lynch_decision_complete(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle completed lynch decision voting.
    
    ✅ ЗАХИСТ:
    - Async lock (тільки один виклик одночасно)
    - Processing flag
    - Timestamp check
    """
    
    # Створити lock якщо немає
    if not hasattr(game, '_lynch_lock'):
        game._lynch_lock = asyncio.Lock()
    
    # Спробувати отримати lock (не блокуючи якщо вже зайнято)
    if game._lynch_lock.locked():
        logger.warning("⚠️ Lynch decision вже обробляється (lock busy), пропускаємо")
        return
    
    async with game._lynch_lock:
        # Додаткова перевірка processing flag
        if hasattr(game, '_processing_lynch') and game._processing_lynch:
            logger.warning("⚠️ Lynch decision flag=True, пропускаємо")
            return
        
        # Timestamp check
        current_time = time.time()
        if hasattr(game, '_last_lynch_time'):
            time_diff = current_time - game._last_lynch_time
            if time_diff < 1.0:
                logger.warning(f"⚠️ Lynch decision занадто швидко ({time_diff:.2f}s), блокуємо")
                return
        
        # Встановити прапорці
        game._last_lynch_time = current_time
        game._processing_lynch = True
        
        try:
            alive_count = sum(1 for p in game.players.values() if p.is_alive)
            
            yes_count = 0
            no_count = 0
            
            for voter_id, vote in game.lynch_votes.items():
                voter = game.players[voter_id]
                weight = 2 if voter.role == "mayor" else 1
                
                if vote == "yes":
                    yes_count += weight
                else:
                    no_count += weight
            
            logger.info(f"📊 Lynch: ТАК={yes_count}, НІ={no_count}, ВСЬОГО={alive_count}")
            
            # Потрібна більшість
            if yes_count > alive_count / 2:
                logger.info(f"✅ Переходимо до номінацій")
                await start_nominations(game, context)
            else:
                logger.info(f"❌ Недостатньо голосів")
                await safe_send_message(
                    context,
                    game.group_chat_id,
                    visual.NO_HANGING,
                    parse_mode='HTML'
                )
                
                game.round_num += 1
                await start_night(game, context)
        
        finally:
            game._processing_lynch = False

# ====================================================
# ВИПРАВЛЕННЯ №1: Таймер з правильним оновленням
# ====================================================

async def run_timer(game: GameState, context: ContextTypes.DEFAULT_TYPE, 
                   duration: int, phase_name: str) -> None:
    """Run countdown timer with fixed updates."""
    
    # Send initial timer message
    try:
        msg = await context.bot.send_message(
            game.group_chat_id,
            visual.format_timer_text(phase_name, duration),
            parse_mode='HTML'
        )
        game.timer_message_id = msg.message_id
        logger.info(f"Timer started: {phase_name} for {duration}s")
    except Exception as e:
        logger.error(f"Failed to send initial timer: {e}")
        await asyncio.sleep(duration)
        await on_phase_timeout(game, context, phase_name)
        return
    
    try:
        elapsed = 0
        update_interval = config.TIMER_UPDATE_INTERVAL
        last_update_time = 0
        
        while elapsed < duration:
            await asyncio.sleep(1)  # Sleep 1 second at a time
            elapsed += 1
            remaining = duration - elapsed
            
            # Update display every TIMER_UPDATE_INTERVAL seconds
            if elapsed - last_update_time >= update_interval or remaining == 0:
                try:
                    await context.bot.edit_message_text(
                        visual.format_timer_text(phase_name, remaining),
                        chat_id=game.group_chat_id,
                        message_id=game.timer_message_id,
                        parse_mode='HTML'
                    )
                    last_update_time = elapsed
                    logger.debug(f"Timer updated: {phase_name} - {remaining}s remaining")
                except Exception as e:
                    error_msg = str(e).lower()
                    if "message is not modified" not in error_msg:
                        logger.debug(f"Timer update error: {e}")
        
        logger.info(f"Timer finished: {phase_name}")
        await on_phase_timeout(game, context, phase_name)
        
    except asyncio.CancelledError:
        logger.info(f"Timer cancelled for {phase_name}")
        raise


# ====================================================
# ВИПРАВЛЕННЯ №2: Перевірка перемоги з детальним логом
# ====================================================

async def check_win_condition(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Check if game has ended with detailed logging.
    
    КРИТИЧНО: Мафія виграє при ПАРИТЕТІ (>=), а не при більшості (>)
    """
    mafia_roles = {"don", "mafia", "consigliere"}
    
    # Count with detailed logging
    mafia_list = []
    civilian_list = []
    
    for p in game.players.values():
        if p.is_alive:
            if p.role in mafia_roles:
                mafia_list.append(f"{p.username}({p.role})")
            else:
                civilian_list.append(f"{p.username}({p.role})")
    
    mafia_alive = len(mafia_list)
    civilian_alive = len(civilian_list)
    
    logger.info(f"🔍 Win check - Game #{game.game_id}, Round {game.round_num}:")
    logger.info(f"  🔴 Mafia ({mafia_alive}): {', '.join(mafia_list) if mafia_list else 'None'}")
    logger.info(f"  🔵 Civilians ({civilian_alive}): {', '.join(civilian_list) if civilian_list else 'None'}")
    
    # Мафія виграє якщо >= мирних (ПАРИТЕТ!)
    if mafia_alive > 0 and mafia_alive >= civilian_alive:
        logger.info(f"🏴 MAFIA WINS by parity control! ({mafia_alive} >= {civilian_alive})")
        await end_game(game, context, "mafia")
        return True
    
    # Мирні виграють якщо мафії немає
    if mafia_alive == 0:
        logger.info(f"✨ CIVILIANS WIN! No mafia left")
        await end_game(game, context, "civilians")
        return True
    
    logger.info(f"⏳ Game continues: {mafia_alive} mafia vs {civilian_alive} civilians")
    return False


# ====================================================
# ВИПРАВЛЕННЯ №3: Номінації з повідомленням в чат
# ====================================================

async def execute_bot_nomination(game: GameState, bot: PlayerState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute bot nomination with chat notification."""
    await asyncio.sleep(random.uniform(2, 10))
    
    candidate_id = await bot_ai.select_nomination(game, bot)
    if candidate_id:
        game.nomination_votes[bot.player_id] = candidate_id
        candidate = game.players[candidate_id]
        logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "BOT", "NOMINATE", candidate.username))
        
        await bot_ai.record_vote(bot.player_id, bot.player_id, candidate_id)
        
        # 🔧 ДОДАНО: Повідомлення в чат
        await safe_send_message(
            context,
            game.group_chat_id,
            f"🗳 <b>{bot.username}</b> висунув кандидата",
            parse_mode='HTML'
        )
        
        if hasattr(game, '_voting_context') and game._voting_context:
            await check_all_nominations_done(game, game._voting_context)


async def start_nominations(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start nomination process with context passing."""
    game.nomination_votes = {}
    
    if not hasattr(game, '_nominations_lock'):
        game._nominations_lock = asyncio.Lock()
    
    game._processing_nominations = False
    game._nominations_processed = False
    game._voting_context = context
    
    await safe_send_message(
        context,
        game.group_chat_id,
        "📢 <b>Час висувати кандидатів на страту!</b>\n\nКожен гравець зараз отримає приватне повідомлення для вибору.",
        parse_mode='HTML'
    )
    
    await asyncio.sleep(1)
    
    # Send nomination DMs with context
    for pid in game.player_order:
        player = game.players[pid]
        if not player.is_alive:
            continue
        
        if player.is_bot:
            asyncio.create_task(execute_bot_nomination(game, player, context))  # ← Передаємо context
        else:
            await send_nomination_dm(game, player, context)
            await asyncio.sleep(0.3)
    
    # Start timer
    game.nomination_timer = asyncio.create_task(
        nomination_timer(game, context, config.VOTING_DURATION)
    )


async def send_nomination_dm(game: GameState, player: PlayerState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send nomination DM to player."""
    if not player.telegram_id:
        return
    
    targets = [(p.username, pid) for pid, p in game.players.items() 
               if p.is_alive and pid != player.player_id]
    
    if not targets:
        return
    
    buttons = []
    for name, pid in targets:
        buttons.append([InlineKeyboardButton(name, callback_data=f"nominate_{pid}")])
    
    try:
        await context.bot.send_message(
            player.telegram_id,
            visual.NOMINATION_PROMPT,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to send nomination DM to {player.username}: {e}")


async def execute_bot_nomination(game: GameState, bot: PlayerState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Execute bot nomination with chat notification."""
    await asyncio.sleep(random.uniform(2, 10))
    
    candidate_id = await bot_ai.select_nomination(game, bot)
    if candidate_id:
        game.nomination_votes[bot.player_id] = candidate_id
        candidate = game.players[candidate_id]
        logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "BOT", "NOMINATE", candidate.username))
        
        await bot_ai.record_vote(bot.player_id, bot.player_id, candidate_id)
        
        # 🔧 ДОДАНО: Повідомлення в чат
        await safe_send_message(
            context,
            game.group_chat_id,
            f"🗳 <b>{bot.username}</b> висунув кандидата",
            parse_mode='HTML'
        )
        
        if hasattr(game, '_voting_context') and game._voting_context:
            await check_all_nominations_done(game, game._voting_context)


async def check_all_nominations_done(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Check if all alive players nominated.
    
    ✅ ЗАХИСТ:
    - Lock per game
    - Processing flag
    - Count verification
    """
    
    if game.phase != Phase.VOTING:
        return
    
    if not hasattr(game, '_nominations_lock'):
        game._nominations_lock = asyncio.Lock()
    
    # Не блокувати якщо вже обробляється
    if game._nominations_lock.locked():
        logger.debug("Nominations lock busy, пропускаємо")
        return
    
    async with game._nominations_lock:
        # Processing flag check
        if hasattr(game, '_nominations_processed') and game._nominations_processed:
            logger.debug("Nominations вже оброблені, пропускаємо")
            return
        
        alive_count = sum(1 for p in game.players.values() if p.is_alive)
        
        if len(game.nomination_votes) >= alive_count:
            logger.info(f"✅ Всі номінували ({len(game.nomination_votes)}/{alive_count})")
            
            game._nominations_processed = True
            
            # Cancel timer if exists
            if hasattr(game, 'nomination_timer') and game.nomination_timer:
                if not game.nomination_timer.done():
                    game.nomination_timer.cancel()
                    try:
                        await game.nomination_timer
                    except asyncio.CancelledError:
                        pass
            
            await process_nominations(game, context)



async def nomination_timer(game: GameState, context: ContextTypes.DEFAULT_TYPE, duration: int) -> None:
    """Timer for nominations."""
    try:
        await asyncio.sleep(duration)
        await process_nominations(game, context)
    except asyncio.CancelledError:
        logger.info("Nomination timer cancelled (all voted early)")


async def process_nominations(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Process nominations and select candidate.
    
    ✅ ЗАХИСТ:
    - Lock
    - Processing flag
    - Timestamp
    """
    
    if not hasattr(game, '_process_nominations_lock'):
        game._process_nominations_lock = asyncio.Lock()
    
    if game._process_nominations_lock.locked():
        logger.warning("⚠️ process_nominations вже виконується, пропускаємо")
        return
    
    async with game._process_nominations_lock:
        # Processing flag
        if hasattr(game, '_processing_nominations_now') and game._processing_nominations_now:
            logger.warning("⚠️ Nominations flag=True, пропускаємо")
            return
        
        # Timestamp check
        current_time = time.time()
        if hasattr(game, '_last_process_nominations_time'):
            time_diff = current_time - game._last_process_nominations_time
            if time_diff < 1.0:
                logger.warning(f"⚠️ process_nominations занадто швидко ({time_diff:.2f}s)")
                return
        
        game._last_process_nominations_time = current_time
        game._processing_nominations_now = True
        
        try:
            if not game.nomination_votes:
                await safe_send_message(
                    context,
                    game.group_chat_id,
                    visual.NO_CANDIDATE,
                    parse_mode='HTML'
                )
                
                # Скинути прапорці
                if hasattr(game, '_nominations_processed'):
                    game._nominations_processed = False
                
                game.round_num += 1
                await start_night(game, context)
                return
            
            # Count votes with mayor weight
            vote_counts = {}
            for voter_id, candidate_id in game.nomination_votes.items():
                if game.players[candidate_id].is_alive:
                    voter = game.players[voter_id]
                    weight = 2 if voter.role == "mayor" else 1
                    vote_counts[candidate_id] = vote_counts.get(candidate_id, 0) + weight
            
            if not vote_counts:
                await safe_send_message(
                    context,
                    game.group_chat_id,
                    visual.NO_CANDIDATE,
                    parse_mode='HTML'
                )
                
                if hasattr(game, '_nominations_processed'):
                    game._nominations_processed = False
                
                game.round_num += 1
                await start_night(game, context)
                return
            
            # Find top candidate
            alive_count = sum(1 for p in game.players.values() if p.is_alive)
            threshold = math.ceil(alive_count * config.NOMINATION_THRESHOLD_RATIO)
            
            max_votes = max(vote_counts.values())
            
            logger.info(f"📊 Номінації: {vote_counts}, поріг={threshold}")
            
            if max_votes < threshold:
                logger.info(f"❌ Недостатньо голосів ({max_votes} < {threshold})")
                await safe_send_message(
                    context,
                    game.group_chat_id,
                    visual.NO_CANDIDATE,
                    parse_mode='HTML'
                )
                
                if hasattr(game, '_nominations_processed'):
                    game._nominations_processed = False
                
                game.round_num += 1
                await start_night(game, context)
                return
            
            # Select candidate
            candidates_with_max = [cid for cid, count in vote_counts.items() if count == max_votes]
            game.current_candidate = random.choice(candidates_with_max)
            
            candidate = game.players[game.current_candidate]
            
            logger.info(f"🎯 Кандидат: {candidate.username} ({max_votes} голосів)")
            
            await safe_send_message(
                context,
                game.group_chat_id,
                visual.CANDIDATE_SELECTED.format(name=candidate.username),
                parse_mode='HTML'
            )
            
            await asyncio.sleep(1)
            
            await start_confirmation(game, context)
        
        finally:
            game._processing_nominations_now = False


async def start_confirmation(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start final confirmation voting."""
    game.confirmation_votes = {}
    
    candidate = game.players[game.current_candidate]
    
    # Send confirmation DMs
    for pid in game.player_order:
        player = game.players[pid]
        if not player.is_alive:
            continue
        if pid == game.current_candidate:
            continue
        
        if player.is_bot:
            asyncio.create_task(execute_bot_confirmation(game, player))
        else:
            await send_confirmation_dm(game, player, candidate, context)
            await asyncio.sleep(0.3)
    
    # Wait then process
    await asyncio.sleep(config.FINAL_CONFIRMATION_DURATION)
    await process_confirmation(game, context)


async def send_confirmation_dm(game: GameState, player: PlayerState, 
                               candidate: PlayerState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send confirmation DM."""
    if not player.telegram_id:
        return
    
    try:
        await context.bot.send_message(
            player.telegram_id,
            visual.CONFIRMATION_PROMPT.format(name=candidate.username),
            reply_markup=visual.get_confirmation_keyboard(),
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to send confirmation DM to {player.username}: {e}")


async def execute_bot_confirmation(game: GameState, bot: PlayerState) -> None:
    """Execute bot confirmation vote using AI."""
    await asyncio.sleep(random.uniform(1, 8))
    
    vote = await bot_ai.select_confirmation_vote(game, bot, game.current_candidate)
    game.confirmation_votes[bot.player_id] = vote
    
    candidate = game.players[game.current_candidate]
    logger.info(visual.format_action_log(game.game_id, game.round_num, bot.username, "BOT", f"CONFIRM_{vote.upper()}", candidate.username))
    
    await bot_ai.record_vote(bot.player_id, bot.player_id, game.current_candidate)


async def process_confirmation(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process confirmation votes and execute hanging."""
    candidate = game.players[game.current_candidate]
    
    # Calculate votes with mayor bonus
    yes_count = 0
    no_count = 0
    
    for voter_id, vote in game.confirmation_votes.items():
        voter = game.players[voter_id]
        vote_weight = 2 if voter.role == "mayor" else 1
        
        if vote == "yes":
            yes_count += vote_weight
        else:
            no_count += vote_weight
    
    alive_count = sum(1 for p in game.players.values() if p.is_alive) - 1
    
    if yes_count <= alive_count // 2:
        await safe_send_message(
            context,
            game.group_chat_id,
            visual.NO_HANGING,
            parse_mode='HTML'
        )
        await asyncio.sleep(1.5)
        game.round_num += 1
        await start_night(game, context)
        return
    
    # Execute hanging
    rope_breaks = False
    
    if candidate.role == "executioner" and not candidate.has_used_executioner_immunity:
        if random.random() < config.EXECUTIONER_ROPE_BREAK_CHANCE:
            rope_breaks = True
            candidate.has_used_executioner_immunity = True
    else:
        executioner_alive = any(p.is_alive and p.role == "executioner" 
                               for p in game.players.values())
        
        break_chance = config.NORMAL_ROPE_BREAK_CHANCE
        if executioner_alive:
            break_chance -= config.EXECUTIONER_REDUCES_BREAK_CHANCE_BY
            break_chance = max(0, break_chance)
        
        if random.random() < break_chance:
            rope_breaks = True
    
    if rope_breaks:
        await safe_send_message(
            context,
            game.group_chat_id,
            visual.HANGING_ROPE_BREAK.format(name=candidate.username),
            parse_mode='HTML'
        )
    else:
        candidate.is_alive = False
        
        if candidate.db_player_id:
            await db.update_game_player_stats(candidate.db_player_id, is_alive=0)
        
        # Bot AI learns
        for bot_pid in game.player_order:
            bot = game.players[bot_pid]
            if bot.is_bot and bot.is_alive:
                await bot_ai.observe_death(bot.player_id, game.current_candidate, candidate.role)
        
        # Send hanging GIF
        try:
            with open("gifs/dead.gif", "rb") as gif_file:
                await safe_send_animation(
                    context,
                    game.group_chat_id,
                    animation=gif_file,
                    caption=visual.HANGING_SUCCESS.format(
                        name=candidate.username,
                        role_reveal=f"Це був {visual.ROLE_NAMES[candidate.role]}."
                    ),
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.warning(f"Failed to send hanging GIF: {e}")
            await safe_send_message(
                context,
                game.group_chat_id,
                visual.HANGING_SUCCESS.format(
                    name=candidate.username,
                    role_reveal=f"Це був {visual.ROLE_NAMES[candidate.role]}."
                ),
                parse_mode='HTML'
            )
        
        logger.info(visual.format_game_log(game.game_id, game.round_num, "VOTING", f"{candidate.username} hanged"))
    
    # Check win condition
    if await check_win_condition(game, context):
        return
    
    await asyncio.sleep(2)
    
    # Next round
    game.round_num += 1
    await start_night(game, context)


# ====================================================
# WIN CONDITION & GAME END
# ====================================================

async def check_win_condition(game: GameState, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if game has ended with detailed logging."""
    mafia_roles = {"don", "mafia", "consigliere"}
    
    # Count with detailed logging
    mafia_list = []
    civilian_list = []
    
    for p in game.players.values():
        if p.is_alive:
            if p.role in mafia_roles:
                mafia_list.append(f"{p.username}({p.role})")
            else:
                civilian_list.append(f"{p.username}({p.role})")
    
    mafia_alive = len(mafia_list)
    civilian_alive = len(civilian_list)
    
    logger.info(f"🔍 Win check:")
    logger.info(f"  🔴 Mafia ({mafia_alive}): {', '.join(mafia_list) if mafia_list else 'None'}")
    logger.info(f"  🔵 Civilians ({civilian_alive}): {', '.join(civilian_list) if civilian_list else 'None'}")
    
    # Mafia wins if >= civilians (parity control)
    if mafia_alive > 0 and mafia_alive >= civilian_alive:
        logger.info(f"🏴 MAFIA WINS by parity!")
        await end_game(game, context, "mafia")
        return True
    
    # Civilians win if no mafia
    if mafia_alive == 0:
        logger.info(f"✨ CIVILIANS WIN!")
        await end_game(game, context, "civilians")
        return True
    
    logger.info(f"⏳ Game continues: {mafia_alive} mafia vs {civilian_alive} civilians")
    return False


async def end_game(game: GameState, context: ContextTypes.DEFAULT_TYPE, winner: str) -> None:
    """End game and award points."""
    game.phase = Phase.ENDED
    
    logger.info(visual.format_game_log(game.game_id, game.round_num, "END", f"{winner} won"))
    
    await cancel_timer_safely(game.timer_task)
    
    # Send win message
    if winner == "mafia":
        win_text = visual.MAFIA_WIN_TEXT
        try:
            with open("gifs/lost_civil.gif", "rb") as gif_file:
                await context.bot.send_animation(
                    game.group_chat_id,
                    animation=gif_file,
                    caption=win_text,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.warning(f"Failed to send mafia win GIF: {e}")
            await context.bot.send_message(
                game.group_chat_id,
                win_text,
                parse_mode='HTML'
            )
    else:
        win_text = visual.CIVIL_WIN_TEXT
        try:
            with open("gifs/lost_mafia.gif", "rb") as gif_file:
                await context.bot.send_animation(
                    game.group_chat_id,
                    animation=gif_file,
                    caption=win_text,
                    parse_mode='HTML'
                )
        except Exception as e:
            logger.warning(f"Failed to send civil win GIF: {e}")
            await context.bot.send_message(
                game.group_chat_id,
                win_text,
                parse_mode='HTML'
            )
    
    # Show all roles
    await context.bot.send_message(
        game.group_chat_id,
        visual.format_final_roles(game.players),
        parse_mode='HTML'
    )
    
    # Update DB
    if game.db_game_id:
        await db.end_game(game.db_game_id, winner, game.round_num)
    
    # Award points
    mafia_roles = {"don", "mafia", "consigliere"}
    
    for player in game.players.values():
        if player.is_bot:
            continue
        
        user_id = await db.get_or_create_user(player.telegram_id, player.username)
        
        won = (winner == "mafia" and player.role in mafia_roles) or \
              (winner == "civilians" and player.role not in mafia_roles)
        
        points = config.POINTS_WIN if won else config.POINTS_LOSS
        points += player.kills * config.POINTS_KILL
        points += player.heals * config.POINTS_SAVE
        points += player.checks * config.POINTS_CORRECT_CHECK
        
        # 🔧 ВИПРАВЛЕНО: DOUBLE_POINTS тільки на перемогах
        buffs = await db.get_user_buffs(player.telegram_id)
        for buff in buffs:
            if buff['buff_type'] == 'DOUBLE_POINTS' and won:  # ← Додано "and won"
                points *= 2
                logger.info(f"💎 {player.username} got x2 points (DOUBLE_POINTS buff)")
                break
        
        await db.update_user_points(user_id, points)
        await db.update_user_stats(user_id, total_games=1, wins=1 if won else 0, losses=0 if won else 1)
        
        # 🔧 ВИПРАВЛЕНО: Декремент бафів тільки для переможців
        if won:
            await db.decrement_buff_games(player.telegram_id)
        else:
            logger.info(f"🔄 {player.username} lost - buffs NOT decremented")
    
    # Remove game
    game_manager.remove_game(game.group_chat_id)


# ====================================================
# TIMER MANAGEMENT
# ====================================================

async def start_timer(game: GameState, context: ContextTypes.DEFAULT_TYPE, 
                     duration: int, phase_name: str) -> None:
    """Start phase timer with countdown."""
    if game.timer_task:
        game.timer_task.cancel()
    
    game.timer_task = asyncio.create_task(
        run_timer(game, context, duration, phase_name)
    )


async def run_timer(game: GameState, context: ContextTypes.DEFAULT_TYPE, 
                   duration: int, phase_name: str) -> None:
    """Run countdown timer with fixed updates."""
    
    # Send initial timer message
    try:
        msg = await context.bot.send_message(
            game.group_chat_id,
            visual.format_timer_text(phase_name, duration),
            parse_mode='HTML'
        )
        game.timer_message_id = msg.message_id
        logger.info(f"Timer started: {phase_name} for {duration}s")
    except Exception as e:
        logger.error(f"Failed to send initial timer: {e}")
        await asyncio.sleep(duration)
        await on_phase_timeout(game, context, phase_name)
        return
    
    try:
        elapsed = 0
        update_interval = config.TIMER_UPDATE_INTERVAL
        
        while elapsed < duration:
            await asyncio.sleep(update_interval)
            elapsed += update_interval
            remaining = max(0, duration - elapsed)
            
            # Update timer display
            try:
                await context.bot.edit_message_text(
                    visual.format_timer_text(phase_name, remaining),
                    chat_id=game.group_chat_id,
                    message_id=game.timer_message_id,
                    parse_mode='HTML'
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "message is not modified" not in error_msg:
                    logger.debug(f"Timer update error: {e}")
        
        logger.info(f"Timer finished: {phase_name}")
        await on_phase_timeout(game, context, phase_name)
        
    except asyncio.CancelledError:
        logger.info(f"Timer cancelled for {phase_name}")
        raise


async def on_phase_timeout(game: GameState, context: ContextTypes.DEFAULT_TYPE, phase_name: str) -> None:
    """Handle phase timeout."""
    if phase_name == "night":
        if hasattr(game, '_resolving_night') and game._resolving_night:
            logger.info("Night already resolving, skipping timeout handler")
            return
        await resolve_night(game, context)
    
    elif phase_name == "day":
        await start_voting(game, context)
    
    elif phase_name == "voting":
        if game.lynch_votes:
            await handle_lynch_decision_complete(game, context)
        else:
            await context.bot.send_message(
                game.group_chat_id,
                visual.NO_HANGING,
                parse_mode='HTML'
            )
            game.round_num += 1
            await start_night(game, context)


# ====================================================
# NIGHT ACTION CALLBACKS
# ====================================================

async def handle_don_kill_callback(game: GameState, player: PlayerState, 
                                   target_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Don's kill choice."""
    game.don_target = target_id
    player.has_acted_this_night = True
    
    target = game.players[target_id]
    logger.info(visual.format_action_log(game.game_id, game.round_num, player.username, "DON", "KILL", target.username))
    
    await context.bot.send_message(
        player.telegram_id,
        visual.ACTION_CONFIRMED["don"],
        parse_mode='HTML'
    )
    
    await log_action_in_group(game, context, "don_chose")
    await check_all_night_actions_done(game, context)


async def handle_doctor_heal_callback(game: GameState, player: PlayerState, 
                                      target_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Doctor's heal choice."""
    game.doctor_target = target_id
    player.has_acted_this_night = True
    
    if target_id == player.player_id:
        player.has_self_healed = True
    
    target = game.players[target_id]
    logger.info(visual.format_action_log(game.game_id, game.round_num, player.username, "DOCTOR", "HEAL", target.username))
    
    await context.bot.send_message(
        player.telegram_id,
        visual.ACTION_CONFIRMED["doctor"],
        parse_mode='HTML'
    )
    
    await log_action_in_group(game, context, "doctor_chose")
    await check_all_night_actions_done(game, context)


async def handle_detective_check_callback(game: GameState, player: PlayerState, 
                                          target_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Detective's check choice."""
    player.has_acted_this_night = True
    player.checks += 1
    
    target = game.players[target_id]
    game.check_results[player.player_id] = (target_id, target.role)
    
    logger.info(visual.format_action_log(game.game_id, game.round_num, player.username, "DETECTIVE", "CHECK", target.username))
    
    await context.bot.send_message(
        player.telegram_id,
        visual.ACTION_CONFIRMED["detective_check"],
        parse_mode='HTML'
    )
    
    if not player.is_bot:
        await db.update_user_stats(await db.get_or_create_user(player.telegram_id, player.username), correct_checks=1)
    
    await log_action_in_group(game, context, "detective_chose")
    await check_all_night_actions_done(game, context)


async def handle_detective_shoot_callback(game: GameState, player: PlayerState, 
                                          target_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle Detective's shoot choice with STRICT validation.
    """
    
    # ✅ FIX #1: LOCK для запобігання race condition
    if not hasattr(game, '_detective_shoot_lock'):
        game._detective_shoot_lock = asyncio.Lock()
    
    # ✅ FIX #2: Спробувати отримати lock
    if game._detective_shoot_lock.locked():
        logger.warning(f"⚠️ {player.username} спробував стріляти під час іншого пострілу")
        try:
            await context.bot.send_message(
                player.telegram_id,
                "❌ Зачекай, постріл вже обробляється!",
                parse_mode='HTML'
            )
        except:
            pass
        return
    
    async with game._detective_shoot_lock:
        # ✅ FIX #3: СТРОГА перевірка на початку (під lock)
        if player.has_used_gun:
            logger.warning(f"⚠️ {player.username} спробував стріляти ЗНОВУ (заблоковано)")
            try:
                await context.bot.send_message(
                    player.telegram_id,
                    "❌ <b>Помилка!</b>\n\n"
                    "Ти вже використав пістолет раніше!\n\n"
                    "Можеш тільки перевіряти ролі.",
                    parse_mode='HTML'
                )
            except:
                pass
            return
        
        # Перевірка фази
        if game.phase != Phase.NIGHT:
            logger.warning(f"⚠️ {player.username} спробував стріляти не вночі")
            return
        
        # Перевірка що гравець живий
        if not player.is_alive:
            logger.warning(f"⚠️ {player.username} спробував стріляти будучи мертвим")
            return
        
        # Перевірка що ціль існує
        if target_id not in game.players:
            logger.error(f"⚠️ {player.username} обрав неіснуючу ціль: {target_id}")
            return
        
        # ✅ FIX #4: ЗАБОРОНА САМОГУБСТВА
        if target_id == player.player_id:
            try:
                await context.bot.send_message(
                    player.telegram_id,
                    "❌ Не можна стріляти в себе!\n\nЦе самогубство! 🔫🚫",
                    parse_mode='HTML'
                )
            except:
                pass
            return
        
        # ✅ FIX #5: Виконуємо постріл ТА ОДРАЗУ ВСТАНОВЛЮЄМО ПРАПОРЕЦЬ
        player.has_used_gun = True  # ← КРИТИЧНО: ДО присвоєння target
        game.detective_shoot_target = target_id
        player.has_acted_this_night = True
        
        target = game.players[target_id]
        logger.info(f"🔫 {player.username} ВИСТРІЛИВ у {target.username} (пістолет використано)")
        
        try:
            await context.bot.send_message(
                player.telegram_id,
                "🔫 <b>Постріл здійснено!</b>\n\n"
                "Пістолет тепер порожній. Вранці дізнаєшся результат.\n\n"
                "<i>Більше стріляти не зможеш.</i>",
                parse_mode='HTML'
            )
        except Exception as e:
            logger.error(f"Failed to send shoot confirmation: {e}")
        
        from engine import log_action_in_group, check_all_night_actions_done
        await log_action_in_group(game, context, "detective_chose")
        await check_all_night_actions_done(game, context)

async def handle_potato_throw_callback(game: GameState, player: PlayerState, 
                                       target_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle potato throw."""
    game.potato_actions.append((player.player_id, target_id))
    player.has_thrown_potato = True
    player.has_acted_this_night = True
    
    target = game.players[target_id]
    logger.info(visual.format_action_log(game.game_id, game.round_num, player.username, "POTATO", "THROW", target.username))
    
    await context.bot.send_message(
        player.telegram_id,
        visual.ACTION_CONFIRMED["potato"],
        parse_mode='HTML'
    )
    
    await check_all_night_actions_done(game, context)


async def handle_petrushka_callback(game: GameState, player: PlayerState, 
                                    target_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle Petrushka role change."""
    player.has_used_petrushka = True
    player.has_acted_this_night = True
    
    target = game.players[target_id]
    old_role = target.role
    
    # 🔧 ВИПРАВЛЕНО: Виключаємо критичні ролі з можливих замін
    # Не можна міняти на don/mafia якщо це порушить баланс гри
    mafia_roles = {"don", "mafia", "consigliere"}
    
    # Рахуємо живих мафіозі
    mafia_count = sum(1 for p in game.players.values() 
                     if p.is_alive and p.role in mafia_roles)
    
    # Якщо ціль - мафія, і це остання мафія - НЕ ДОЗВОЛЯТИ зміну
    if old_role in mafia_roles and mafia_count <= 1:
        await context.bot.send_message(
            player.telegram_id,
            "❌ <b>Магія не спрацювала!</b>\n\nЩось пішло не так... Спробуй іншу ціль.",
            parse_mode='HTML'
        )
        player.has_used_petrushka = False
        player.has_acted_this_night = False
        return
    
    # Визначаємо доступні ролі для заміни
    available_roles = []
    
    if old_role in mafia_roles:
        # Якщо ціль - мафія, може стати тільки мирною роллю
        available_roles = ["civilian", "doctor", "mayor", "deputy", "executioner"]
    else:
        # Якщо ціль - мирний, може стати будь-ким окрім don
        available_roles = ["mafia", "doctor", "civilian", "mayor", 
                          "deputy", "consigliere", "executioner"]
    
    # Виключаємо поточну роль
    if old_role in available_roles:
        available_roles.remove(old_role)
    
    if not available_roles:
        await context.bot.send_message(
            player.telegram_id,
            "❌ Немає доступних ролей для заміни!",
            parse_mode='HTML'
        )
        player.has_used_petrushka = False
        player.has_acted_this_night = False
        return
    
    new_role = random.choice(available_roles)
    target.role = new_role
    
    # 🔧 ВИПРАВЛЕНО: Скидаємо статуси цілі
    if new_role == "doctor":
        target.has_self_healed = False
    elif new_role == "detective":
        target.has_used_gun = False
    
    logger.info(visual.format_action_log(game.game_id, game.round_num, player.username, "PETRUSHKA", 
                                   f"CHANGE {target.username} {old_role}->{new_role}", ""))
    
    await context.bot.send_message(
        player.telegram_id,
        visual.ACTION_CONFIRMED["petrushka"],
        parse_mode='HTML'
    )
    
    # Notify target
    if not target.is_bot and target.telegram_id:
        try:
            await context.bot.send_message(
                target.telegram_id,
                f"⚠️ Щось пішло не так з твоєю долею...\n\n{visual.ROLE_DESCRIPTIONS[new_role]}",
                parse_mode='HTML'
            )
        except:
            pass
    
    # 🔧 ВИПРАВЛЕНО: Перевірка win condition після зміни ролі
    await asyncio.sleep(0.5)
    await check_all_night_actions_done(game, context)



# ====================================================
# MESSAGE DELETION
# ====================================================

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle messages in group and delete if needed."""
    if not update.message or not update.message.chat:
        return
    
    chat_id = update.message.chat.id
    game = game_manager.get_game(chat_id)
    
    if not game or game.phase == Phase.LOBBY:
        return
    
    sender_id = update.message.from_user.id
    message_id = update.message.message_id
    
    # Find player
    player = None
    for p in game.players.values():
        if p.telegram_id == sender_id:
            player = p
            break
    
    should_delete = False
    reason = ""
    
    # Delete dead player messages
    if player and not player.is_alive:
        should_delete = True
        reason = f"dead player {player.username}"
    
    # Delete all messages during night
    elif game.phase == Phase.NIGHT and config.DELETE_NIGHT_MESSAGES:
        should_delete = True
        reason = "night phase"
    
    if should_delete:
        try:
            await context.bot.delete_message(chat_id, message_id)
            logger.info(f"Deleted message from {reason} in chat {chat_id}")
        except Exception as e:
            error_msg = str(e).lower()
            
            if "can't be deleted" in error_msg or "message to delete not found" in error_msg:
                logger.debug(f"Message {message_id} already deleted or too old")
                return
            
            if "not enough rights" in error_msg or "no rights" in error_msg:
                if not hasattr(context.bot_data, 'warned_chats'):
                    context.bot_data.warned_chats = set()
                
                if chat_id not in context.bot_data.warned_chats:
                    context.bot_data.warned_chats.add(chat_id)
                    
                    try:
                        await context.bot.send_message(
                            chat_id,
                            visual.ERROR_DELETE_PERMISSION,
                            parse_mode='HTML'
                        )
                    except:
                        pass
                    logger.warning(f"Missing delete permissions in chat {chat_id}")
            else:
                logger.error(f"Failed to delete message: {e}")