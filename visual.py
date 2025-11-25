"""
Visual layer: all Ukrainian text, keyboards, and formatting for Mafia Bot.
Dark humor, rural vibe style.
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Any, Optional, Tuple
import config


# ====================================================
# BOT NAMES
# ====================================================
BOT_NAMES = [
    "Іннокентій 🌾",
    "Пінченко ⚰️",
    "Іванов ДЦП 📜",
    "Баба Параска 🧹",
    "Кирило Яремче 🤪",
    "Степан Криворівня 🍺",
    "Петро Марусяк",
    "Тімченко Сечовий Міхур",
    "Ігор Рогальский",
    "Григорій Гребінський"
]


# ====================================================
# PERSISTENT KEYBOARD (для ЛС)
# ====================================================
def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Get persistent main menu keyboard for private chat."""
    keyboard = [
        [KeyboardButton("📊 Профіль"), KeyboardButton("🛒 Магазин")],
        [KeyboardButton("❓ Як грати"), KeyboardButton("📜 Правила")]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        persistent=True,
        one_time_keyboard=False,
        input_field_placeholder="Обери дію з меню 👇"
    )


# ====================================================
# ROLE NAMES & DESCRIPTIONS
# ====================================================
ROLE_NAMES = {
    "don": "Дон",
    "mafia": "Мафія",
    "doctor": "Лікар",
    "detective": "Детектив Кішкель",
    "civilian": "Мирний",
    "mayor": "Мер міста",
    "deputy": "Заступник детектива",
    "consigliere": "Консильєрі",
    "executioner": "Палач",
    "petrushka": "Петрушка"
}

ROLE_DESCRIPTIONS = {
    "don": "☠️ <b>Дон мафії</b>\n\nТи головний бандит у цьому селі. Кожної ночі обираєш жертву. Якщо тебе вб'ють, твої хлопці продовжать справу.",
    "mafia": "🔪 <b>Мафія</b>\n\nТи частина злочинної сім'ї. Допомагаєш Дону вбивати селян. Якщо Дон помре, ти станеш головним.",
    "doctor": "💉 <b>Лікар</b>\n\nТи рятуєш життя. Кожної ночі обираєш кого лікувати. Себе можеш лікувати тільки раз за гру.",
    "detective": "🔍 <b>Детектив Кішкель</b>\n\nТи шукаєш мафію. Можеш перевірити роль гравця АБО вистрілити в нього (один раз за гру).",
    "civilian": "👨‍🌾 <b>Мирний житель</b>\n\nТи звичайний лох, який чекає смерті. Твоя сила - у голосуванні та базіканні вдень.",
    "mayor": "🎩 <b>Мер міста</b>\n\nТи впливова особа. Під час голосування твій голос рахується за два. Ніхто про це не знає.",
    "deputy": "🔎 <b>Заступник детектива</b>\n\nТи можеш перевіряти ролі, як Детектив, але стріляти не вмієш.",
    "consigliere": "🎭 <b>Консильєрі</b>\n\nТи радник мафії. Перевіряєш ролі на користь своєї команди.",
    "executioner": "⚔️ <b>Палач</b>\n\nТи вмієш вішати. Якщо тебе намагаються повісити, мотузка може порватись. Коли ти живий, інші висять надійніше.",
    "petrushka": "🎪 <b>Петрушка</b>\n\nТи хаос! Раз за гру можеш змінити роль іншого гравця на випадкову. Формально ти за селян."
}


# ====================================================
# LOBBY TEXTS
# ====================================================
def format_lobby_message(game_id: int, humans: List[str], bots: List[str]) -> str:
    """Format lobby registration message."""
    text = f"🎲 <b>Гра #{game_id}</b>\n"
    text += f"📋 <b>Фаза:</b> Реєстрація\n\n"
    
    text += f"👥 <b>Люди ({len(humans)}):</b>\n"
    if humans:
        for h in humans:
            text += f"  • {h}\n"
    else:
        text += "  <i>Поки що нікого...</i>\n"
    
    text += f"\n🤖 <b>Боти ({len(bots)}):</b>\n"
    if bots:
        for b in bots:
            text += f"  • {b}\n"
    else:
        text += "  <i>Поки що нікого...</i>\n"
    
    text += f"\n<i>Мінімум {config.MIN_PLAYERS} учасників для старту</i>"
    
    return text


def get_lobby_keyboard() -> InlineKeyboardMarkup:
    """Get lobby keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Доєднатися в гру", callback_data="lobby_join")],
        [InlineKeyboardButton("Додати бота 🤖", callback_data="lobby_add_bot")],
        [InlineKeyboardButton("Почати гру", callback_data="lobby_start")]
    ])


# ====================================================
# GAME START TEXTS
# ====================================================
START_GAME_TEXT = """🎮 <b>Гра починається!</b>

Ролі роздані в особисті повідомлення.
Хтось сьогодні не доживе до ранку... 💀"""

BUKOVEL_ANNOUNCEMENT = """🏔 <b>УВАГА! РЕЖИМ БУКОВЕЛЬ!</b>

Це не звичайна гра. Це БУКОВЕЛЬ, сучка! 🥔

Мирні селяни отримали по картоплі.
Можете кинути в когось першої ночі.
50/50 - вб'єте або промахнетесь.

Використовуйте мудро. Або тупо. Вам вирішувати."""


# ====================================================
# NIGHT TEXTS
# ====================================================
NIGHT_START_TEXT = """🌙 <b>Село засинає...</b>

Темрява огортає вулиці. Хтось працює цієї ночі.
Сподіваюсь, не над тобою. 🔪"""

def format_timer_text(phase: str, seconds: int) -> str:
    """Format countdown timer."""
    emoji = {"night": "🌙", "day": "☀️", "voting": "🗳"}.get(phase, "⏳")
    phase_name = {"night": "Ніч", "day": "День", "voting": "Голосування"}.get(phase, "Таймер")
    return f"{emoji} <b>{phase_name}:</b> {seconds} с"


# ====================================================
# MORNING / DAY TEXTS
# ====================================================
MORNING_GIF_TEXT = "☀️ <b>Ранок у селі...</b>"

EVENT_MESSAGES = {
    "event_everyone_alive": """☀️ <b>Всі живі!</b>

Мабуть лікар добре попрацював, або мафія забухала вчора. 🍺
Або детектив точно вистрілив? Хто знає...""",
    
    "event_single_death": "⚰️ <b>{name}</b> не побачить сьогоднішнього заходу.\n\n{role_reveal}",
    
    "event_both_died": """⚰️⚰️ <b>Подвійна похоронна!</b>

<b>{name1}</b> та <b>{name2}</b> відправились на той світ.
Ритуальні послуги знижка 2+1! 🪦

{role_reveal}""",
    
    "doc_saved": """💚 <b>Лікар врятував чиюсь дупу!</b>

Хтось мав стати трупом, але медицина перемогла.
На цей раз.""",
    
    "don_dead_no_mafia": """👑 <b>Дона прибрали!</b>

Мафії більше немає в селі. Можна не замикати двері на ніч.
Ну, майже.""",
    
    "don_dead_mafia_alive": """👑 <b>Дон помер!</b>

Але його бізнес не вмирає. Справу продовжують "партнери".
Тепер без боса, але з тими ж ножами. 🔪""",
    
    "doc_dead": """💔 <b>Лікар помер!</b>

Тепер нікому клеїти ваші дірки. 
Сподіваюсь, у когось є бинти.""",
    
    "detective_dead": """🔍 <b>Детектива вбили!</b>

Єдиний розумний чоловік у селі тепер лежить в землі.
Залишились тільки дурні. Типу тебе.""",
    
    "civil_dead": """😔 <b>Звичайний селянин помер.</b>

Нічого особливого, просто ще один труп.
Життя продовжується. Для інших.""",
    
    "night_no_kick": """😴 <b>Всі дожили до ранку!</b>

Чи це означає що село безпечне?
Ні, це означає що вночі просто нікого не вбили. Поки що."""
}


def format_morning_report(events: List[str], details: Dict[str, Any]) -> str:
    """Format morning report with events."""
    parts = []
    
    for event_key in events:
        msg = EVENT_MESSAGES.get(event_key, "")
        if msg:
            parts.append(msg.format(**details))
    
    return "\n\n".join(parts)


def format_stats_block(alive_humans: List[str], alive_bots: List[str], 
                       dead_humans: List[str], dead_bots: List[str]) -> str:
    """Format statistics block."""
    text = "\n\n📊 <b>Статистика:</b>\n\n"
    
    text += f"✅ <b>Живі ({len(alive_humans) + len(alive_bots)}):</b>\n"
    if alive_humans or alive_bots:
        for h in alive_humans:
            text += f"  👥 {h}\n"
        for b in alive_bots:
            text += f"  🤖 {b}\n"
    else:
        text += "  <i>Нікого</i>\n"
    
    if dead_humans or dead_bots:
        text += f"\n💀 <b>Померли ({len(dead_humans) + len(dead_bots)}):</b>\n"
        for h in dead_humans:
            text += f"  👥 {h}\n"
        for b in dead_bots:
            text += f"  🤖 {b}\n"
    
    return text


# Додайте нову функцію для показу ролей в кінці гри:

def format_final_roles(players: Dict[str, Any]) -> str:
    """Format final roles reveal at game end."""
    text = "\n\n🎭 <b>Ролі гравців:</b>\n\n"
    
    for player in players.values():
        status_emoji = "✅" if player.is_alive else "💀"
        role_name = ROLE_NAMES.get(player.role, player.role)
        bot_indicator = " 🤖" if player.is_bot else ""
        text += f"{status_emoji} <b>{player.username}</b>{bot_indicator} - {role_name}\n"
    
    return text


# ====================================================
# VOTING TEXTS
# ====================================================
VOTING_START_TEXT = """🗳 <b>Час судити!</b>

Хто сьогодні заслуговує на мотузку? 
Може ти? Може твій сусід? Вирішуйте, селяне! 🪢"""

NOMINATION_PROMPT = "Обери підозрюваного на повіс:"
NOMINATION_LOGGED = "🔔 Хтось висунув підозрюваного..."

CANDIDATE_SELECTED = """🎯 <b>Народ обрав жертву:</b> {name}

Зараз будемо вирішувати його долю.
Спойлер: це буде не круїз на Карибах. ⚰️"""

CONFIRMATION_PROMPT = "Підтвердити повіс <b>{name}</b>?"

HANGING_SUCCESS = """⚰️ <b>{name}</b> більше не проблема!

Його повісили перед всім селом. Надіюсь, ви не помилились.

{role_reveal}

<i>Сімдесят відсотків часу селяни вішають своїх...</i>"""

HANGING_ROPE_BREAK = """😱 <b>МОТУЗКА ПОРВАЛАСЬ!</b>

<b>{name}</b> впав і тікає через город!
Хтось забув перевірити якість китайської мотузки. 

Може наступного разу спрацює... 🪢"""

NO_HANGING = """🤷 <b>Недостатньо голосів.</b>

Демократія не спрацювала. Ніхто сьогодні не висить.
Село розчароване, мотузка повернута до магазину."""

NO_CANDIDATE = "🤷 Не вистачило голосів для висунення кандидата."


def get_lynch_decision_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for lynch yes/no decision."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так, ріжемо!", callback_data="lynch_yes"),
            InlineKeyboardButton("Ні, всі круті", callback_data="lynch_no")
        ]
    ])


def get_lynch_decision_keyboard_with_count(yes_count: int, no_count: int, total: int) -> InlineKeyboardMarkup:
    """Get keyboard for lynch yes/no decision with vote counts."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"Так, ріжемо! ({yes_count}/{total})", callback_data="lynch_yes"),
            InlineKeyboardButton(f"Ні, всі круті ({no_count}/{total})", callback_data="lynch_no")
        ]
    ])


def get_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for final confirmation."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Так, вішати! 👍", callback_data="confirm_yes"),
            InlineKeyboardButton("Ні, помилка 👎", callback_data="confirm_no")
        ]
    ])


# ====================================================
# WIN/LOSE TEXTS
# ====================================================
MAFIA_WIN_TEXT = """🏴 <b>МАФІЯ ПЕРЕМОГЛА!</b>

Темні сили захопили село. Бандити тепер правлять.
Сподіваюсь, ви задоволені? Всі труби. 💀

GG WP, мафіозі! 🍾"""

CIVIL_WIN_TEXT = """✨ <b>СЕЛЯНИ ПЕРЕМОГЛИ!</b>

Мафію знищено! Село може спати спокійно.
Правда тепер вам нема на кого скидати всі проблеми...

Але перемога є перемога! 🎉"""


# ====================================================
# NIGHT ACTION KEYBOARDS
# ====================================================
def get_don_keyboard(targets: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """Get Don's target selection keyboard."""
    buttons = []
    for name, pid in targets:
        buttons.append([InlineKeyboardButton(name, callback_data=f"don_kill_{pid}")])
    return InlineKeyboardMarkup(buttons)


def get_doctor_keyboard(targets: List[Tuple[str, str]], can_heal_self: bool) -> InlineKeyboardMarkup:
    """Get Doctor's target selection keyboard."""
    buttons = []
    for name, pid in targets:
        buttons.append([InlineKeyboardButton(name, callback_data=f"doc_heal_{pid}")])
    return InlineKeyboardMarkup(buttons)


def get_detective_action_keyboard() -> InlineKeyboardMarkup:
    """Get Detective's action choice keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Перевірити гравця", callback_data="detective_check")],
        [InlineKeyboardButton("🔫 Вистрілити", callback_data="detective_shoot")]
    ])


def get_detective_target_keyboard(targets: List[Tuple[str, str]], action: str) -> InlineKeyboardMarkup:
    """Get Detective's target selection keyboard."""
    buttons = []
    prefix = "det_check_" if action == "check" else "det_shoot_"
    for name, pid in targets:
        buttons.append([InlineKeyboardButton(name, callback_data=f"{prefix}{pid}")])
    return InlineKeyboardMarkup(buttons)


def get_potato_keyboard(targets: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """Get potato throw target keyboard."""
    buttons = []
    for name, pid in targets:
        buttons.append([InlineKeyboardButton(name, callback_data=f"potato_{pid}")])
    buttons.append([InlineKeyboardButton("❌ Не кидати", callback_data="potato_skip")])
    return InlineKeyboardMarkup(buttons)


def get_petrushka_keyboard(targets: List[Tuple[str, str]]) -> InlineKeyboardMarkup:
    """Get Petrushka target keyboard."""
    buttons = []
    for name, pid in targets:
        buttons.append([InlineKeyboardButton(name, callback_data=f"petrushka_{pid}")])
    buttons.append([InlineKeyboardButton("❌ Не використовувати", callback_data="petrushka_skip")])
    return InlineKeyboardMarkup(buttons)


# ====================================================
# NIGHT ACTION PROMPTS
# ====================================================
NIGHT_ACTION_PROMPTS = {
    "don": "☠️ <b>Твоя ніч, Доне!</b>\n\nОбери жертву:",
    "mafia": "🔪 <b>Дон помер, тепер ти головний!</b>\n\nОбери жертву:",
    "doctor": "💉 <b>Час рятувати життя!</b>\n\nКого будеш лікувати цієї ночі?",
    "detective": "🔍 <b>Що робитимеш цієї ночі, Детективе?</b>",
    "deputy": "🔎 <b>Кого перевіримо цієї ночі?</b>",
    "consigliere": "🎭 <b>Кого перевіримо для мафії?</b>",
    "potato": "🥔 <b>У тебе є картопля!</b>\n\nТільки перша ніч! Кинься поганенько в когось:",
    "petrushka": "🎪 <b>Хочеш накоїти біди?</b>\n\nМожеш змінити роль одного гравця (раз за гру):"
}

ACTION_CONFIRMED = {
    "don": "☠️ Вибір зроблено. Жертва обрана...",
    "mafia": "🔪 Вибір зроблено. Жертва обрана...",
    "doctor": "💉 Побіг клеїти шви!",
    "detective_check": "🔍 Ідеш на слідство...",
    "detective_shoot": "🔫 Пістолет заряджено!",
    "deputy": "🔎 Ідеш збирати інформацію...",
    "consigliere": "🎭 Ідеш збирати інформацію для мафії...",
    "potato": "🥔 Картопля летить!",
    "potato_skip": "🥔 Зберіг картоплю в кишені.",
    "petrushka": "🎪 Магія активована!",
    "petrushka_skip": "🎪 Поки що не хочеш хаосу."
}

CHECK_RESULT = "🔍 <b>Результат перевірки:</b>\n\n<b>{name}</b> - {role}"

POTATO_RESULT_HIT = "🥔💥 <b>Хтось кинув картоплю в {name}...</b>\n\nВлучив!"
POTATO_RESULT_MISS = "🥔 <b>Хтось кинув картоплю в {name}...</b>\n\nПромах!"


# ====================================================
# GROUP ACTION LOGS
# ====================================================
ACTION_LOGS = {
    "don_chose": "☠️ Дон зробив свій вибір...",
    "mafia_chose": "🔪 Мафія обрала жертву...",
    "doctor_chose": "💉 Лікар вже комусь клеїть шви...",
    "detective_chose": "🔍 Детектив на слідстві...",
    "deputy_chose": "🔎 Заступник шукає відповіді...",
    "consigliere_chose": "🎭 Консильєрі збирає інформацію..."
}


# ====================================================
# ERRORS & WARNINGS
# ====================================================
ERROR_NOT_STARTED_BOT = "❌ Спочатку напиши /start боту в особисті повідомлення!"
ERROR_ALREADY_IN_GAME = "❌ Ти вже в грі!"
ERROR_TOO_FEW_PLAYERS = f"❌ Мало гравців! Потрібно мінімум {config.MIN_PLAYERS}."
ERROR_TOO_MANY_PLAYERS = f"❌ Забагато! Максимум {config.MAX_PLAYERS} учасників."
ERROR_TOO_MANY_BOTS = f"❌ Забагато ботів! Максимум {config.MAX_BOTS}."
ERROR_GAME_RUNNING = "❌ Гра вже йде!"
ERROR_NO_GAME = "❌ Зараз немає активної гри."
ERROR_NOT_ADMIN = "❌ Тільки адміни можуть це зробити."
ERROR_DELETE_PERMISSION = "⚠️ Немає прав видаляти повідомлення! Дай мені права адміністратора."


# ====================================================
# PROFILE & SHOP
# ====================================================
def format_profile(stats: Dict[str, Any], buffs: List[Dict[str, Any]]) -> str:
    """Format profile message."""
    text = f"👤 <b>Твій профіль</b>\n\n"
    text += f"💰 <b>Очки:</b> {stats.get('points', 0)}\n"
    text += f"🎮 <b>Ігор зіграно:</b> {stats.get('total_games', 0)}\n"
    text += f"✅ <b>Перемоги:</b> {stats.get('wins', 0)}\n"
    text += f"❌ <b>Поразки:</b> {stats.get('losses', 0)}\n"
    text += f"☠️ <b>Вбивств:</b> {stats.get('kills', 0)}\n"
    text += f"💚 <b>Врятувань:</b> {stats.get('saves', 0)}\n"
    
    if buffs:
        text += f"\n🎁 <b>Активні бафи:</b>\n"
        for buff in buffs:
            text += f"  • {buff['buff_type']}: {buff['remaining_games']} ігор\n"
    else:
        text += f"\n<i>Немає активних бафів</i>\n"
    
    return text


def format_shop() -> str:
    """Format shop message."""
    text = "🛒 <b>Магазин</b>\n\n"
    text += "Тут можна купити корисні штуки за очки:\n\n"
    
    for item_id, item in config.SHOP_ITEMS.items():
        text += f"<b>{item['name']}</b>\n"
        text += f"{item['description']}\n"
        text += f"💰 Ціна: {item['cost']} очок\n\n"
    
    return text


def get_shop_keyboard() -> InlineKeyboardMarkup:
    """Get shop keyboard."""
    buttons = []
    for item_id, item in config.SHOP_ITEMS.items():
        buttons.append([InlineKeyboardButton(
            f"{item['name']} - {item['cost']}💰",
            callback_data=f"shop_buy_{item_id}"
        )])
    return InlineKeyboardMarkup(buttons)


PURCHASE_SUCCESS = "✅ Куплено! Баф активовано."
PURCHASE_FAILED_POINTS = "❌ Недостатньо очок!"


# ====================================================
# CONSOLE LOG FORMATS
# ====================================================
def format_game_log(game_id: int, round_num: int, phase: str, message: str) -> str:
    """Format console log message."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    return f"[{timestamp}] 🎮 Гра #{game_id} | Раунд {round_num} | {phase.upper()} | {message}"


def format_action_log(game_id: int, round_num: int, player_name: str, 
                      role: str, action: str, target: str = "") -> str:
    """Format player action log."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    role_emoji = {
        "DON": "☠️",
        "MAFIA": "🔪",
        "DOCTOR": "💉",
        "DETECTIVE": "🔍",
        "DEPUTY": "🔎",
        "CONSIGLIERE": "🎭",
        "POTATO": "🥔",
        "PETRUSHKA": "🎪",
        "BOT": "🤖"
    }
    
    emoji = role_emoji.get(role.upper(), "👤")
    target_str = f" → {target}" if target else ""
    
    return f"[{timestamp}] {emoji} {player_name} ({role}) {action}{target_str}"

def format_final_roles(players: Dict[str, Any]) -> str:
    """Format final roles reveal at game end."""
    text = "\n\n🎭 <b>Ролі гравців:</b>\n\n"
    
    for player in players.values():
        status_emoji = "✅" if player.is_alive else "💀"
        role_name = ROLE_NAMES.get(player.role, player.role)
        bot_indicator = " 🤖" if player.is_bot else ""
        text += f"{status_emoji} <b>{player.username}</b>{bot_indicator} - {role_name}\n"
    
    return text