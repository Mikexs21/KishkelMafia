import asyncio
import logging
import random
import os
import signal
import sys
from datetime import datetime  # ← ДОДАНО для log функцій
from engine import safe_send_message, safe_send_animation
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import RetryAfter
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

import config
import db
import visual

from engine import (
    game_manager,
    Phase,
    start_game,
    start_voting,
    handle_group_message,
    handle_don_kill_callback,
    handle_doctor_heal_callback,
    handle_detective_check_callback,
    handle_detective_shoot_callback,
    check_all_nominations_done,
    handle_potato_throw_callback,
    handle_petrushka_callback,
    handle_lynch_decision_complete
)


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

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

# Замінити базове налаштування логування на:
Path("logs").mkdir(exist_ok=True)

# Console handler з кольорами
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(ColoredFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
))

# File handler без кольорів
file_handler = logging.FileHandler('logs/mafia_bot.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))

# Налаштувати root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler]
)

# Приглушити сторонні бібліотеки
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ====================================================
# ЛОГУВАННЯ (ВИПРАВЛЕНО)
# ====================================================

def log_game_event(game_id: int, round_num: int, event_type: str, message: str):
    """Log game event with enhanced formatting."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    emoji_map = {
        "NIGHT": "🌙",
        "DAY": "☀️",
        "VOTING": "🗳",
        "ENDED": "🏁",
        "START": "🎮",
        "KILL": "☠️",
        "HEAL": "💚",
        "CHECK": "🔍",
        "SHOOT": "🔫",
        "LYNCH": "⚰️",
        "WIN": "🏆"
    }
    emoji = emoji_map.get(event_type, "📌")
    logger.info(f"{emoji} Гра #{game_id} | Раунд {round_num} | {event_type} | {message}")


def log_player_action(game_id: int, round_num: int, player_name: str, 
                      role: str, action: str, target: str = ""):
    """Log player action with role emoji."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    role_emoji = {
        "don": "☠️",
        "mafia": "🔪",
        "doctor": "💉",
        "detective": "🔍",
        "deputy": "🔎",
        "consigliere": "🎭",
        "petrushka": "🎪",
        "civilian": "👨‍🌾",
        "mayor": "🎩",
        "executioner": "⚔️",
        "bot": "🤖"
    }
    emoji = role_emoji.get(role.lower(), "👤")
    target_str = f" → {target}" if target else ""
    logger.info(f"{emoji} {player_name} ({role}) {action}{target_str}")


# ====================================================
# COMMAND HANDLERS
# ====================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command in DM and group."""
    user = update.effective_user
    
    # Register user in database
    await db.get_or_create_user(user.id, user.username or user.first_name)
    
    if update.effective_chat.type == 'private':
        # Private chat - show full menu
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Мій профіль", callback_data="menu_profile")],
            [InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop")],
            [InlineKeyboardButton("❓ Як грати", callback_data="menu_help")],
            [InlineKeyboardButton("📜 Правила", callback_data="menu_rules")]
        ])
        
        welcome_text = """👋 <b>Привіт! Я Детектив Кішкель</b>

Бот для гри в Мафію в Telegram групах.

🎮 <b>Щоб почати гру:</b>
1. Додай мене в групу
2. Хтось пише /newgame
3. Гравці приєднуються
4. Гра автоматично починається!

<b>Обери дію нижче:</b>"""
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    else:
        # Group chat - show detailed info
        group_welcome = f"""👋 <b>Привіт! Я бот для гри в Мафію!</b>

✅ {user.first_name}, тепер можеш грати!

📋 <b>Доступні команди:</b>
/newgame - Створити нову гру
/cancelgame - Скасувати гру (тільки адміни)
/status - Статус поточної гри
/profile - Твій профіль (в особистих повідомленнях)
/shop - Магазин бафів (в особистих повідомленнях)

🎮 <b>Як почати:</b>
1. Напиши /newgame в цій групі
2. Гравці натискають кнопку "Приєднатися"
3. Коли зібралось 5+ учасників - жми "Почати гру"
4. Отримайте ролі та грайте!

💡 <b>Додаткова інфо:</b>
Напиши мені /start в особистих повідомленнях щоб побачити свій профіль, правила гри та магазин бафів!"""
        
        await update.message.reply_text(
            group_welcome,
            parse_mode='HTML'
        )


async def handle_mafia_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle mafia chat messages in DM during night."""
    if update.effective_chat.type != 'private':
        return
    
    if not update.message or not update.message.text:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Find game and player
    game = None
    player = None
    
    for g in game_manager.games.values():
        if g.phase != Phase.NIGHT:
            continue
        for p in g.players.values():
            if p.telegram_id == user_id:
                game = g
                player = p
                break
        if game:
            break
    
    if not game or not player:
        return
    
    # Check if mafia member
    mafia_roles = {"don", "mafia", "consigliere"}
    if player.role not in mafia_roles:
        return
    
    # Перевірка чи гравець живий
    if not player.is_alive:
        try:
            await context.bot.delete_message(
                update.effective_chat.id, 
                update.message.message_id
            )
        except Exception as e:
            logger.debug(f"Не вдалося видалити повідомлення мертвого: {e}")
        return
    
    # Check if already sent
    if player.player_id in game.mafia_message_sent:
        await update.message.reply_text(
            "❌ Ти вже відправив повідомлення команді цієї ночі!\n\n"
            "Можна відправити тільки ОДНЕ повідомлення за ніч."
        )
        return
    
    # Check length
    if len(message_text) > 200:
        await update.message.reply_text(
            f"❌ Повідомлення занадто довге! Максимум 200 символів.\n\n"
            f"Зараз: {len(message_text)} символів"
        )
        return
    
    # Save message
    game.mafia_messages.append((player.username, message_text))
    game.mafia_message_sent.add(player.player_id)
    
    await update.message.reply_text(
        "✅ <b>Повідомлення надіслано команді!</b>\n\n"
        f"Твоє повідомлення: \"{message_text[:50]}{'...' if len(message_text) > 50 else ''}\"",
        parse_mode='HTML'
    )
    
    logger.info(f"💬 Мафія-чат від {player.username}: {message_text[:50]}...")
    
    # Send to all mafia members
    for p in game.players.values():
        if p.role in mafia_roles and p.player_id != player.player_id:
            if not p.is_bot and p.telegram_id:
                try:
                    await context.bot.send_message(
                        p.telegram_id,
                        f"💬 <b>{player.username}:</b>\n{message_text}",
                        parse_mode='HTML'
                    )
                    logger.info(f"💬 Мафія-чат доставлено до {p.username}")
                except Exception as e:
                    logger.error(f"Помилка надсилання мафія-чату до {p.username}: {e}")


async def handle_last_words_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle last words from dying players - ВИПРАВЛЕНА ВЕРСІЯ."""
    if update.effective_chat.type != 'private':
        return
    
    if not update.message:
        return
    
    # Дозволяємо ТІЛЬКИ текст
    if not update.message.text:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Find game and player
    game = None
    player = None
    
    for g in game_manager.games.values():
        for p in g.players.values():
            if p.telegram_id == user_id and p.player_id in g.awaiting_last_words:
                game = g
                player = p
                break
        if game:
            break
    
    if not game or not player:
        # Не знайдено гравця який очікує на останні слова
        return
    
    # 🔧 ВИПРАВЛЕНО: Перевірка чи не надіслав вже
    if player.player_id in game.last_words:
        await update.message.reply_text(
            "ℹ️ Ти вже надіслав свої останні слова!",
            parse_mode='HTML'
        )
        return
    
    # Check length
    if len(message_text) > 200:
        await update.message.reply_text(
            "❌ Занадто довго! Максимум 200 символів.\n\n"
            f"Зараз: {len(message_text)} символів",
            parse_mode='HTML'
        )
        return
    
    # Save last words
    game.last_words[player.player_id] = message_text
    game.awaiting_last_words.remove(player.player_id)
    
    await update.message.reply_text(
        "✅ <b>Твої останні слова записані!</b>\n\n"
        "Всі гравці побачать їх вранці.\n\n"
        f"<i>Твоє повідомлення: \"{message_text[:50]}{'...' if len(message_text) > 50 else ''}\"</i>",
        parse_mode='HTML'
    )
    
    logger.info(f"💬 Останні слова від {player.username}: {message_text[:50]}...")

async def handle_last_words_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle last words from dying players - ВИПРАВЛЕНА ВЕРСІЯ."""
    if update.effective_chat.type != 'private':
        return
    
    if not update.message:
        return
    
    # Дозволяємо ТІЛЬКИ текст
    if not update.message.text:
        return
    
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # Find game and player
    game = None
    player = None
    
    for g in game_manager.games.values():
        for p in g.players.values():
            if p.telegram_id == user_id and p.player_id in g.awaiting_last_words:
                game = g
                player = p
                break
        if game:
            break
    
    if not game or not player:
        # Не знайдено гравця який очікує на останні слова
        return
    
    # Перевірка чи не надіслав вже
    if player.player_id in game.last_words:
        await update.message.reply_text(
            "ℹ️ Ти вже надіслав свої останні слова!",
            parse_mode='HTML'
        )
        return
    
    # Check length
    if len(message_text) > 200:
        await update.message.reply_text(
            "❌ Занадто довго! Максимум 200 символів.\n\n"
            f"Зараз: {len(message_text)} символів",
            parse_mode='HTML'
        )
        return
    
    # Save last words
    game.last_words[player.player_id] = message_text
    game.awaiting_last_words.remove(player.player_id)
    
    await update.message.reply_text(
        "✅ <b>Твої останні слова записані!</b>\n\n"
        "Всі гравці побачать їх вранці.\n\n"
        f"<i>Твоє повідомлення: \"{message_text[:50]}{'...' if len(message_text) > 50 else ''}\"</i>",
        parse_mode='HTML'
    )
    
    logger.info(f"💬 Останні слова від {player.username}: {message_text[:50]}...")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command in DM and group."""
    user = update.effective_user
    
    # If in group, send link to DM
    if update.effective_chat.type != 'private':
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"📊 Переходь у особисті повідомлення з ботом для перегляду профілю:\n"
            f"👉 @{bot_username}",
            parse_mode='HTML'
        )
        return
    
    stats = await db.get_user_stats(user.id)
    
    if not stats:
        await update.message.reply_text("❌ Спочатку напиши /start")
        return
    
    buffs = await db.get_user_buffs(user.id)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop")],
        [InlineKeyboardButton("« Головне меню", callback_data="menu_back")]
    ])
    
    await update.message.reply_text(
        visual.format_profile(stats, buffs),
        reply_markup=keyboard,
        parse_mode='HTML'
    )


async def shop_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /shop command in DM and group."""
    # If in group, send link to DM
    if update.effective_chat.type != 'private':
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(
            f"🛒 Переходь у особисті повідомлення з ботом для перегляду магазину:\n"
            f"👉 @{bot_username}",
            parse_mode='HTML'
        )
        return
    
    if not config.ENABLE_SHOP:
        await update.message.reply_text("🛒 Магазин тимчасово закритий.")
        return
    
    keyboard = visual.get_shop_keyboard()
    keyboard.inline_keyboard.append([InlineKeyboardButton("« Головне меню", callback_data="menu_back")])
    
    await update.message.reply_text(
        visual.format_shop(),
        reply_markup=keyboard,
        parse_mode='HTML'
    )

async def check_bot_permissions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if bot has required permissions in the group."""
    chat_id = update.effective_chat.id
    bot = await context.bot.get_me()
    
    try:
        bot_member = await context.bot.get_chat_member(chat_id, bot.id)
        
        # Check if bot is admin
        if bot_member.status not in ['administrator']:
            await update.message.reply_text(
                "⚠️ <b>УВАГА!</b>\n\n"
                "Бот повинен бути <b>адміністратором</b> групи!\n\n"
                "📋 <b>Необхідні права:</b>\n"
                "  • Видалення повідомлень\n\n"
                "Додай бота в адміни групи і спробуй знову.",
                parse_mode='HTML'
            )
            return False
        
        # Check delete messages permission
        if not bot_member.can_delete_messages:
            await update.message.reply_text(
                "⚠️ <b>УВАГА!</b>\n\n"
                "Бот є адміном, але йому потрібне право <b>видаляти повідомлення</b>!\n\n"
                "📋 <b>Як виправити:</b>\n"
                "1. Налаштування групи → Адміністратори\n"
                "2. Знайди бота в списку\n"
                "3. Увімкни 'Видалення повідомлень'\n\n"
                "Це потрібно щоб мертві гравці не могли писати в чат.",
                parse_mode='HTML'
            )
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking bot permissions: {e}")
        return True  # Allow game to start anyway

async def newgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /newgame command in group."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ Цю команду можна використовувати тільки в групах!")
        return
    
    chat_id = update.effective_chat.id
    
    # Check if game already exists
    game = game_manager.get_game(chat_id)
    if game:
        await update.message.reply_text(visual.ERROR_GAME_RUNNING, parse_mode='HTML')
        return
    
    # Create new game
    game = game_manager.create_game(chat_id)
    
    # Determine if Bukovel mode
    if config.BUKOVEL_ENABLED and random.random() < config.BUKOVEL_CHANCE:
        game.is_bukovel = True
    
    # Send lobby message
    lobby_msg = await update.message.reply_text(
        visual.format_lobby_message(game.game_id, [], []),
        reply_markup=visual.get_lobby_keyboard(),
        parse_mode='HTML'
    )
    
    # Store lobby message ID
    context.chat_data['lobby_message_id'] = lobby_msg.message_id
    
    logger.info(f"New game {game.game_id} created in chat {chat_id}")


async def cancelgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /cancelgame command in group."""
    if update.effective_chat.type == 'private':
        return
    
    chat_id = update.effective_chat.id
    
    # Check admin
    member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    if member.status not in ['creator', 'administrator']:
        await update.message.reply_text(visual.ERROR_NOT_ADMIN, parse_mode='HTML')
        return
    
    game = game_manager.get_game(chat_id)
    if not game:
        await update.message.reply_text(visual.ERROR_NO_GAME, parse_mode='HTML')
        return
    
    # Cancel timer if exists
    if game.timer_task:
        game.timer_task.cancel()
    
    game_manager.remove_game(chat_id)
    
    await update.message.reply_text("✅ Гру скасовано.", parse_mode='HTML')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /status command in group."""
    if update.effective_chat.type == 'private':
        return
    
    chat_id = update.effective_chat.id
    game = game_manager.get_game(chat_id)
    
    if not game:
        await update.message.reply_text(visual.ERROR_NO_GAME, parse_mode='HTML')
        return
    
    # Build status message
    text = f"🎮 <b>Статус гри #{game.game_id}</b>\n\n"
    text += f"📍 <b>Фаза:</b> {game.phase.value}\n"
    text += f"🔄 <b>Раунд:</b> {game.round_num}\n\n"
    
    alive_count = sum(1 for p in game.players.values() if p.is_alive)
    dead_count = len(game.players) - alive_count
    
    text += f"✅ <b>Живих:</b> {alive_count}\n"
    text += f"💀 <b>Мертвих:</b> {dead_count}\n"
    
    await update.message.reply_text(text, parse_mode='HTML')


# ====================================================
# CALLBACK QUERY HANDLERS
# ====================================================

async def lobby_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle lobby button callbacks."""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat.id
    game = game_manager.get_game(chat_id)
    
    if not game or game.phase != Phase.LOBBY:
        await query.answer("❌ Ця гра вже не активна", show_alert=True)
        return
    
    action = query.data
    
    if action == "lobby_join":
        await handle_lobby_join(update, context, game)
    elif action == "lobby_add_bot":
        await handle_lobby_add_bot(update, context, game)
    elif action == "lobby_start":
        await handle_lobby_start(update, context, game)


async def handle_lobby_join(update: Update, context: ContextTypes.DEFAULT_TYPE, game) -> None:
    """Handle player joining lobby."""
    user = update.callback_query.from_user
    
    # Check if already in game
    for player in game.players.values():
        if player.telegram_id == user.id:
            await update.callback_query.answer("❌ Ти вже в грі!", show_alert=True)
            return
    
    # Auto-register user
    user_data = await db.get_user_by_telegram_id(user.id)
    if not user_data:
        await db.get_or_create_user(user.id, user.username or user.first_name)
        logger.info(f"Auto-registered user {user.id} ({user.first_name}) on game join")
    
    # Check max players
    if len(game.players) >= config.MAX_PLAYERS:
        await update.callback_query.answer(visual.ERROR_TOO_MANY_PLAYERS, show_alert=True)
        return
    
    # Add player
    player_id = game_manager.generate_player_id()
    from engine import PlayerState
    
    player = PlayerState(
        player_id=player_id,
        telegram_id=user.id,
        username=user.first_name or user.username or f"User{user.id}",
        is_bot=False,
        role=""
    )
    
    game.players[player_id] = player
    game.player_order.append(player_id)
    
    logger.info(f"Player {player.username} (ID: {user.id}) joined game {game.game_id}")
    
    # Update lobby message
    await update_lobby_message(update.callback_query.message, game)
    
    await update.callback_query.answer("✅ Ти в грі!")


async def handle_lobby_add_bot(update: Update, context: ContextTypes.DEFAULT_TYPE, game) -> None:
    """Handle adding bot to lobby."""
    # Count bots
    bot_count = sum(1 for p in game.players.values() if p.is_bot)
    
    if bot_count >= config.MAX_BOTS:
        await update.callback_query.answer(visual.ERROR_TOO_MANY_BOTS, show_alert=True)
        return
    
    if len(game.players) >= config.MAX_PLAYERS:
        await update.callback_query.answer(visual.ERROR_TOO_MANY_PLAYERS, show_alert=True)
        return
    
    # Add bot
    player_id = game_manager.generate_player_id()
    from engine import PlayerState
    
    # Get used bot names
    used_names = [p.username for p in game.players.values() if p.is_bot]
    
    # Find available name
    available_names = [name for name in visual.BOT_NAMES if name not in used_names]
    
    if not available_names:
        await update.callback_query.answer("❌ Всі імена ботів вже використані!", show_alert=True)
        return
    
    bot_name = random.choice(available_names)
    
    player = PlayerState(
        player_id=player_id,
        telegram_id=None,
        username=bot_name,
        is_bot=True,
        role=""
    )
    
    game.players[player_id] = player
    game.player_order.append(player_id)
    
    logger.info(f"Bot {bot_name} added to game {game.game_id}")
    
    # Update lobby message
    await update_lobby_message(update.callback_query.message, game)
    
    await update.callback_query.answer(f"✅ Додано бота: {bot_name}")


async def handle_lobby_start(update: Update, context: ContextTypes.DEFAULT_TYPE, game) -> None:
    """Handle starting game from lobby."""
    if len(game.players) < config.MIN_PLAYERS:
        await update.callback_query.answer(visual.ERROR_TOO_FEW_PLAYERS, show_alert=True)
        return
    
    await update.callback_query.answer("🎮 Гра починається!")
    
    # Delete lobby message keyboard
    try:
        await update.callback_query.message.edit_reply_markup(reply_markup=None)
    except:
        pass
    
    # Start game
    await start_game(game, context)


async def update_lobby_message(message, game) -> None:
    """Update lobby message with current players."""
    humans = [p.username for p in game.players.values() if not p.is_bot]
    bots = [p.username for p in game.players.values() if p.is_bot]
    
    logger.info(f"Updating lobby: {len(humans)} humans, {len(bots)} bots")
    
    try:
        await message.edit_text(
            visual.format_lobby_message(game.game_id, humans, bots),
            reply_markup=visual.get_lobby_keyboard(),
            parse_mode='HTML'
        )
        logger.info("Lobby message updated successfully")
    except Exception as e:
        logger.error(f"Failed to update lobby message: {e}")


async def night_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle night action callbacks with enhanced protection."""
    query = update.callback_query
    
    user_id = query.from_user.id
    data = query.data
    
    # Find game and player
    game = None
    player = None
    
    for g in game_manager.games.values():
        for p in g.players.values():
            if p.telegram_id == user_id:
                game = g
                player = p
                break
        if game:
            break
    
    if not game or not player:
        try:
            await query.answer("❌ Гра не знайдена", show_alert=True)
        except:
            pass
        return
    
    if game.phase != Phase.NIGHT:
        try:
            await query.answer("❌ Зараз не ніч", show_alert=True)
        except:
            pass
        return
    
    if not player.is_alive:
        try:
            await query.answer("❌ Ти мертвий", show_alert=True)
        except:
            pass
        return
    
    # 🔧 ВИПРАВЛЕНО: Захист від повторних кліків (крім вибору дії детектива)
    if data not in ["detective_check", "detective_shoot"]:
        if player.has_acted_this_night:
            try:
                await query.answer("❌ Ти вже зробив вибір цієї ночі", show_alert=True)
                logger.warning(f"⚠️ {player.username} спробував діяти двічі (заблоковано)")
            except:
                pass
            return
    
    # Безпечний answer
    try:
        await query.answer()
    except Exception as e:
        error_msg = str(e).lower()
        if "too old" not in error_msg and "expired" not in error_msg:
            logger.warning(f"Query answer помилка (некритично): {e}")
    
    # Handle action
    if data.startswith("don_kill_"):
        target_id = data.replace("don_kill_", "")
        logger.info(f"☠️ {player.username} обирає жертву: {game.players[target_id].username}")
        await handle_don_kill_callback(game, player, target_id, context)
    
    elif data.startswith("doc_heal_"):
        target_id = data.replace("doc_heal_", "")
        logger.info(f"💉 {player.username} лікує: {game.players[target_id].username}")
        await handle_doctor_heal_callback(game, player, target_id, context)
    
    elif data == "detective_check":
        logger.info(f"🔍 {player.username} обрав перевірку")
        targets = [(p.username, pid) for pid, p in game.players.items() 
                   if p.is_alive and pid != player.player_id]
        await query.message.reply_text(
            "🔍 <b>Обери кого перевірити:</b>",
            reply_markup=visual.get_detective_target_keyboard(targets, "check"),
            parse_mode='HTML'
        )
    
    elif data == "detective_shoot":
        # 🔧 ВИПРАВЛЕНО: СТРОГА перевірка has_used_gun
        if player.has_used_gun:
            try:
                await query.answer(
                    "❌ Ти вже використав пістолет раніше!\n\n"
                    "Можеш тільки перевіряти ролі.",
                    show_alert=True
                )
                logger.warning(f"⚠️ {player.username} спробував стріляти ЗНОВУ (заблоковано в callback)")
            except:
                pass
            return
        
        logger.info(f"🔫 {player.username} обрав постріл")
        targets = [(p.username, pid) for pid, p in game.players.items() 
                   if p.is_alive and pid != player.player_id]
        await query.message.reply_text(
            "🔫 <b>Обери в кого стріляти:</b>\n\n"
            "<i>⚠️ Пістолет можна використати тільки РАЗ за гру!</i>",
            reply_markup=visual.get_detective_target_keyboard(targets, "shoot"),
            parse_mode='HTML'
        )
    
    elif data.startswith("det_check_"):
        target_id = data.replace("det_check_", "")
        logger.info(f"🔍 {player.username} перевіряє: {game.players[target_id].username}")
        await handle_detective_check_callback(game, player, target_id, context)
    
    elif data.startswith("det_shoot_"):
        # 🔧 ВИПРАВЛЕНО: Додаткова перевірка перед пострілом
        if player.has_used_gun:
            try:
                await query.answer("❌ Ти вже використав пістолет!", show_alert=True)
                logger.warning(f"⚠️ {player.username} спробував стріляти ЗНОВУ (заблоковано в det_shoot_)")
            except:
                pass
            return
        
        target_id = data.replace("det_shoot_", "")
        logger.info(f"🔫 {player.username} СТРІЛЯЄ у: {game.players[target_id].username}")
        await handle_detective_shoot_callback(game, player, target_id, context)
    
    elif data.startswith("potato_"):
        if data == "potato_skip":
            player.has_thrown_potato = True
            player.has_acted_this_night = True
            logger.info(f"🥔 {player.username} пропустив картоплю")
            await query.message.reply_text(visual.ACTION_CONFIRMED["potato_skip"])
            await check_all_night_actions_done(game, context)
        else:
            target_id = data.replace("potato_", "")
            logger.info(f"🥔 {player.username} кидає картоплю в: {game.players[target_id].username}")
            await handle_potato_throw_callback(game, player, target_id, context)
    
    elif data.startswith("petrushka_"):
        if data == "petrushka_skip":
            player.has_used_petrushka = True
            player.has_acted_this_night = True
            logger.info(f"🎪 {player.username} пропустив Петрушку")
            await query.message.reply_text(visual.ACTION_CONFIRMED["petrushka_skip"])
            await check_all_night_actions_done(game, context)
        else:
            target_id = data.replace("petrushka_", "")
            logger.info(f"🎪 {player.username} використовує Петрушку на: {game.players[target_id].username}")
            await handle_petrushka_callback(game, player, target_id, context)


async def voting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
        
        # 🔧 ВИПРАВЛЕНО: Дедуплікація - дозволити зміну, але не дублювати
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

async def nomination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle nomination callbacks in DM."""
    query = update.callback_query
    
    user_id = query.from_user.id
    data = query.data
    
    if not data.startswith("nominate_"):
        try:
            await query.answer()
        except:
            pass
        return
    
    candidate_id = data.replace("nominate_", "")
    
    # Find game and player
    game = None
    player = None
    
    for g in game_manager.games.values():
        for p in g.players.values():
            if p.telegram_id == user_id:
                game = g
                player = p
                break
        if game:
            break
    
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
    
    if not player.is_alive:
        try:
            await query.answer("❌ Ти мертвий", show_alert=True)
        except:
            pass
        return
    
    if player.player_id in game.nomination_votes:
        try:
            await query.answer("❌ Ти вже висунув кандидата!", show_alert=True)
        except:
            pass
        return
    
    if hasattr(game, '_processing_nominations') and game._processing_nominations:
        try:
            await query.answer("⏳ Голосування вже обробляється...", show_alert=True)
        except:
            pass
        return
    
    game.nomination_votes[player.player_id] = candidate_id
    
    candidate = game.players[candidate_id]
    
    try:
        await query.answer(f"✅ Ти висунув: {candidate.username}")
    except Exception as e:
        error_msg = str(e).lower()
        if "too old" not in error_msg and "expired" not in error_msg:
            logger.error(f"Nomination answer error: {e}")
    
    # 🔧 ДОДАНО: Повідомлення в чат
    await safe_send_message(
        context,
        game.group_chat_id,
        f"🗳 <b>{player.username}</b> висунув кандидата",
        parse_mode='HTML'
    )
    
    await check_all_nominations_done(game, context)


async def confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation callbacks with flood control."""
    query = update.callback_query
    
    user_id = query.from_user.id
    data = query.data
    
    if data not in ["confirm_yes", "confirm_no"]:
        try:
            await query.answer()
        except:
            pass
        return
    
    vote = "yes" if data == "confirm_yes" else "no"
    
    # Find game and player
    game = None
    player = None
    
    for g in game_manager.games.values():
        for p in g.players.values():
            if p.telegram_id == user_id:
                game = g
                player = p
                break
        if game:
            break
    
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
    
    if not player.is_alive:
        try:
            await query.answer("❌ Ти мертвий", show_alert=True)
        except:
            pass
        return
    
    if player.player_id == game.current_candidate:
        try:
            await query.answer("❌ Ти кандидат, не можеш голосувати", show_alert=True)
        except:
            pass
        return
    
    # Check duplicate
    if player.player_id in game.confirmation_votes:
        old_vote = game.confirmation_votes[player.player_id]
        if old_vote == vote:
            try:
                await query.answer("❌ Ти вже проголосував!", show_alert=True)
            except:
                pass
            return
    
    game.confirmation_votes[player.player_id] = vote
    
    try:
        await query.answer(f"✅ Твій голос: {'Так' if vote == 'yes' else 'Ні'}")
    except Exception as e:
        error_msg = str(e).lower()
        if "too old" not in error_msg and "expired" not in error_msg:
            logger.error(f"Confirmation answer error: {e}")
    
    candidate = game.players[game.current_candidate]
    vote_emoji = "👍" if vote == "yes" else "👎"
    
    # Calculate with mayor
    yes_count = 0
    no_count = 0
    for voter_id, v in game.confirmation_votes.items():
        voter = game.players[voter_id]
        weight = 2 if voter.role == "mayor" else 1
        if v == "yes":
            yes_count += weight
        else:
            no_count += weight
    
    alive_count = sum(1 for p in game.players.values() if p.is_alive) - 1
    
    mayor_indicator = " 👑x2" if player.role == "mayor" else ""
    
    # ✅ Use safe_send with delay
    await asyncio.sleep(0.5)
    await safe_send_message(
        context,
        game.group_chat_id,
        f"{vote_emoji} <b>{player.username}</b>{mayor_indicator} проголосував за долю {candidate.username}\n\n"
        f"📊 За повіс: {yes_count}/{alive_count} | Проти: {no_count}/{alive_count}",
        parse_mode='HTML'
    )
    
    logger.info(visual.format_action_log(
        game.game_id, game.round_num, player.username,
        "CONFIRM", f"{vote.upper()} for {candidate.username}"
    ))

async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shop purchase callbacks."""
    query = update.callback_query
    
    data = query.data
    
    if not data.startswith("shop_buy_"):
        await query.answer()
        return
    
    item_id = data.replace("shop_buy_", "")
    
    if item_id not in config.SHOP_ITEMS:
        await query.answer("❌ Товар не знайдено", show_alert=True)
        return
    
    item = config.SHOP_ITEMS[item_id]
    user = query.from_user
    
    # Get user stats
    stats = await db.get_user_stats(user.id)
    if not stats:
        await query.answer("❌ Спочатку напиши /start", show_alert=True)
        return
    
    # Check money
    if stats['points'] < item['cost']:
        shortfall = item['cost'] - stats['points']
        await query.answer(
            f"❌ Недостатньо очок!\n\n"
            f"У тебе: {stats['points']} 💰\n"
            f"Потрібно: {item['cost']} 💰\n"
            f"Бракує: {shortfall} 💰",
            show_alert=True
        )
        return
    
    # Process purchase
    await db.update_user_points(stats['id'], -item['cost'])
    await db.add_buff(user.id, item['buff_type'], item['games'])
    await db.add_purchase(user.id, item_id, item['cost'])
    
    await query.answer(f"✅ Куплено!\n\nВитрачено {item['cost']} 💰", show_alert=True)
    
    # Refresh profile
    updated_stats = await db.get_user_stats(user.id)
    buffs = await db.get_user_buffs(user.id)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop")],
        [InlineKeyboardButton("« Назад", callback_data="menu_back")]
    ])
    
    try:
        await query.message.edit_text(
            visual.format_profile(updated_stats, buffs),
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Failed to update profile after purchase: {e}")

async def newgame_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /newgame command in group."""
    if update.effective_chat.type == 'private':
        await update.message.reply_text("❌ Цю команду можна використовувати тільки в групах!")
        return
    
    # НОВИЙ КОД: Перевірка прав бота
    if not await check_bot_permissions(update, context):
        return
    
    chat_id = update.effective_chat.id
    
    # Check if game already exists
    game = game_manager.get_game(chat_id)
    if game:
        await update.message.reply_text(visual.ERROR_GAME_RUNNING, parse_mode='HTML')
        return
    
    # Create new game
    game = game_manager.create_game(chat_id)
    
    # Determine if Bukovel mode
    if config.BUKOVEL_ENABLED and random.random() < config.BUKOVEL_CHANCE:
        game.is_bukovel = True
    
    # Send lobby message
    lobby_msg = await update.message.reply_text(
        visual.format_lobby_message(game.game_id, [], []),
        reply_markup=visual.get_lobby_keyboard(),
        parse_mode='HTML'
    )
    
    # Store lobby message ID
    context.chat_data['lobby_message_id'] = lobby_msg.message_id
    
    logger.info(f"New game {game.game_id} created in chat {chat_id}")


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle main menu callbacks."""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "menu_profile":
        stats = await db.get_user_stats(user.id)
        if not stats:
            await query.answer("❌ Помилка завантаження профілю", show_alert=True)
            return
        
        buffs = await db.get_user_buffs(user.id)
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Назад", callback_data="menu_back")]
        ])
        
        await query.message.edit_text(
            visual.format_profile(stats, buffs),
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    elif data == "menu_shop":
        if not config.ENABLE_SHOP:
            await query.answer("🛒 Магазин тимчасово закритий.", show_alert=True)
            return
        
        keyboard_markup = visual.get_shop_keyboard()
        
        buttons = list(keyboard_markup.inline_keyboard)
        buttons.append([InlineKeyboardButton("« Назад", callback_data="menu_back")])
        
        new_keyboard = InlineKeyboardMarkup(buttons)
        
        await query.message.edit_text(
            visual.format_shop(),
            reply_markup=new_keyboard,
            parse_mode='HTML'
        )
    
    elif data == "menu_help":
        help_text = """❓ <b>Як грати в Мафію</b>

<b>📝 Підготовка:</b>
1. Напиши /start боту в особистих повідомленнях
2. Додай бота в свою групу
3. Напиши /newgame в групі

<b>🎮 Процес гри:</b>
- Гравці приєднуються натиснувши кнопку
- Можна додати AI ботів
- Коли зібралось мінімум 5 учасників - стартуйте!

<b>🌙 Ніч:</b>
Активні ролі (Дон, Лікар, Детектив) отримають DM з вибором дій

<b>☀️ День:</b>
Обговорення того, хто помер

<b>🗳 Голосування:</b>
Вирішуйте кого повісити (якщо хочете)

<b>🏆 Перемога:</b>
- Мафія виграє якщо їх більшість
- Селяни виграють якщо вбили всю мафію"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Назад", callback_data="menu_back")]
        ])
        
        await query.message.edit_text(
            help_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    elif data == "menu_rules":
        rules_text = """📜 <b>Ролі в грі</b>

☠️ <b>Дон</b> - Вбиває вночі
🔪 <b>Мафія</b> - Помічник Дона
💉 <b>Лікар</b> - Рятує від смерті
🔍 <b>Детектив</b> - Перевіряє або стріляє
👨‍🌾 <b>Мирний</b> - Голосує і обговорює
🎩 <b>Мер</b> - Голос х2 (таємно)
🔎 <b>Заступник</b> - Перевіряє ролі
🎭 <b>Консильєрі</b> - Шпигун мафії
⚔️ <b>Палач</b> - Важко повісити
🎪 <b>Петрушка</b> - Змінює ролі

<b>🥔 Режим Буковель:</b>
Випадковий режим де мирні мають картоплю на першу ніч (50% вбити когось)

<b>💰 Очки:</b>
Заробляй очки за перемоги та дії, купуй бафи в магазині!"""

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("« Назад", callback_data="menu_back")]
        ])
        
        await query.message.edit_text(
            rules_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    
    elif data == "menu_back":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Мій профіль", callback_data="menu_profile")],
            [InlineKeyboardButton("🛒 Магазин", callback_data="menu_shop")],
            [InlineKeyboardButton("❓ Як грати", callback_data="menu_help")],
            [InlineKeyboardButton("📜 Правила", callback_data="menu_rules")]
        ])
        
        welcome_text = """👋 <b>Головне меню</b>

Обери дію:"""
        
        await query.message.edit_text(
            welcome_text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )

# ====================================================
# FLOOD CONTROL WRAPPER
# ====================================================

async def safe_send_message(context, chat_id: int, text: str, **kwargs):
    """Send message with smart flood control."""
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # Wait only if needed for this specific chat
            await _flood_controller.wait_if_needed(chat_id)
            
            return await context.bot.send_message(chat_id, text, **kwargs)
            
        except RetryAfter as e:
            if attempt < max_retries - 1:
                wait_time = e.retry_after + 0.5
                logger.warning(f"Flood control hit (chat {chat_id}), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"Failed after {max_retries} retries due to flood control")
                return None
        except Exception as e:
            logger.error(f"Send message error: {e}")
            return None


async def safe_send_animation(context, chat_id: int, animation, **kwargs):
    """Send animation with smart flood control."""
    max_retries = 2
    
    for attempt in range(max_retries):
        try:
            # Wait only if needed for this specific chat
            await _flood_controller.wait_if_needed(chat_id)
            
            return await context.bot.send_animation(chat_id, animation, **kwargs)
            
        except RetryAfter as e:
            if attempt < max_retries - 1:
                wait_time = e.retry_after + 0.5
                logger.warning(f"Flood on animation (chat {chat_id}), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                logger.warning("Failed to send animation after retries, falling back to text")
                caption = kwargs.get('caption', '')
                if caption:
                    return await safe_send_message(
                        context, chat_id, caption, 
                        parse_mode=kwargs.get('parse_mode')
                    )
                return None
        except Exception as e:
            logger.error(f"Animation send error: {e}, falling back to text")
            caption = kwargs.get('caption', '')
            if caption:
                return await safe_send_message(
                    context, chat_id, caption,
                    parse_mode=kwargs.get('parse_mode')
                )
            return None


# ====================================================
# MAIN
# ====================================================

async def post_init(application: Application) -> None:
    """Initialize database after application startup."""
    await db.init_db()
    logger.info("Database initialized")


async def post_shutdown(application: Application) -> None:
    """Cleanup on shutdown."""
    await db.close_db()
    logger.info("Database closed")

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
    
    # 🔧 ВИПРАВЛЕНО: Видаляти ВСЕ від мертвих (текст, гіфки, стікери, фото)
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

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for unhandled exceptions."""
    logger.error(f"Exception while handling an update:", exc_info=context.error)
    
    # Спробувати повідомити користувача
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "😵 <b>Щось пішло не так...</b>\n\n"
                "Спробуй ще раз або напиши /start",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")

# Додайте це в кінець main.py, замініть існуючу функцію main()

def main() -> None:
    """Start the bot with proper error handling."""
    
    print("="*60)
    print("🎮 Mafia Bot Starting...")
    print("="*60)
    
    # Перевірка токена
    if not hasattr(config, 'BOT_TOKEN') or not config.BOT_TOKEN:
        print("❌ ERROR: BOT_TOKEN not found in config.py")
        print("Please set BOT_TOKEN in config.py or environment variables")
        return
    
    if config.BOT_TOKEN == "PASTE_TOKEN_HERE":
        print("❌ ERROR: Please replace BOT_TOKEN in config.py with your actual token")
        return
    
    print(f"✅ Bot token configured: {config.BOT_TOKEN[:20]}...")
    
    # Перевірка критичних констант
    if not hasattr(config, 'DATABASE_FILE'):
        print("❌ ERROR: DATABASE_FILE not found in config.py")
        print("Add: DATABASE_FILE = 'mafia_bot.db'")
        return
    
    if not hasattr(config, 'ROLE_DISTRIBUTION'):
        print("❌ ERROR: ROLE_DISTRIBUTION not found in config.py")
        print("Please add ROLE_DISTRIBUTION dictionary")
        return
    
    print(f"✅ Database file: {config.DATABASE_FILE}")
    print(f"✅ Role distributions: {len(config.ROLE_DISTRIBUTION)} configurations")
    
    # Створити необхідні директорії
    Path("logs").mkdir(exist_ok=True)
    Path("gifs").mkdir(exist_ok=True)
    
    print("✅ Directories created/verified")
    
    # Перевірити наявність GIF файлів
    required_gifs = ["night.gif", "morning.gif", "vote.gif", "dead.gif", "lost_civil.gif", "lost_mafia.gif"]
    missing_gifs = [gif for gif in required_gifs if not Path(f"gifs/{gif}").exists()]
    
    if missing_gifs:
        print(f"⚠️  WARNING: Missing GIF files: {', '.join(missing_gifs)}")
        print("Bot will work but will use text fallbacks instead of animations")
    else:
        print("✅ All GIF files present")
    
    print("\n" + "="*60)
    print("🚀 Starting Telegram Bot...")
    print("="*60 + "\n")
    
    try:
        application = (
            Application.builder()
            .token(config.BOT_TOKEN)
            .post_init(post_init)
            .post_shutdown(post_shutdown)
            .build()
        )
        
        # Register command handlers
        print("📝 Registering handlers...")
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("profile", profile_command))
        application.add_handler(CommandHandler("shop", shop_command))
        application.add_handler(CommandHandler("newgame", newgame_command))
        application.add_handler(CommandHandler("cancelgame", cancelgame_command))
        application.add_handler(CommandHandler("status", status_command))
        
        # Register callback handlers
        application.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))
        application.add_handler(CallbackQueryHandler(lobby_callback, pattern="^lobby_"))
        application.add_handler(CallbackQueryHandler(night_action_callback, pattern="^(don_kill_|doc_heal_|detective_|det_|potato_|petrushka_)"))
        application.add_handler(CallbackQueryHandler(voting_callback, pattern="^lynch_"))
        application.add_handler(CallbackQueryHandler(nomination_callback, pattern="^nominate_"))
        application.add_handler(CallbackQueryHandler(confirmation_callback, pattern="^confirm_"))
        application.add_handler(CallbackQueryHandler(shop_callback, pattern="^shop_buy_"))
        
        # Message handlers
        application.add_handler(MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            handle_last_words_message
        ))
        
        application.add_handler(MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND,
            handle_mafia_chat_message
        ))
        
        application.add_handler(MessageHandler(
            filters.ChatType.GROUPS & ~filters.COMMAND,
            handle_group_message
        ))
        
        # Global error handler
        application.add_error_handler(error_handler)
        
        print("✅ All handlers registered")
        print("\n" + "="*60)
        print("✅ BOT IS RUNNING!")
        print("="*60)
        print("Press Ctrl+C to stop")
        print("="*60 + "\n")
        
        # Start polling
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()