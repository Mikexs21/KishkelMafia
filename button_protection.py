"""
🔥 УЛЬТИМАТИВНА СИСТЕМА ЗАХИСТУ ВІД ДУБЛІКАТІВ 🔥

Проблема: Telegram надсилає callback_query кілька разів якщо:
- Користувач швидко клікає кнопку
- Інтернет лагає і retry
- Багато людей натискають одночасно

Рішення: 4-рівнева система захисту на КОЖНУ кнопку
"""

import asyncio
import time
from typing import Dict, Set, Optional
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ГЛОБАЛЬНА СИСТЕМА ДЕДУПЛІКАЦІЇ
# ============================================================================

class ButtonDuplicateProtection:
    """
    Універсальна система захисту від дублікатів кнопок.
    
    Працює на 4 рівнях:
    1. Query ID tracking (Telegram вбудований захист)
    2. User + Action tracking (один user не може зробити ту саму дію 2 рази підряд)
    3. Timestamp throttling (блокує швидкі повторні кліки <0.5s)
    4. Game state locks (async locks для critical sections)
    """
    
    def __init__(self):
        # Рівень 1: Processed query IDs (Telegram IDs)
        self.processed_queries: Set[str] = set()
        self.query_timestamps: Dict[str, float] = {}
        
        # Рівень 2: User actions (user_id + action_type)
        self.user_actions: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # Рівень 3: Game locks
        self.game_locks: Dict[int, asyncio.Lock] = {}
        
        # Cleanup
        self.last_cleanup = time.time()
    
    def get_game_lock(self, game_id: int) -> asyncio.Lock:
        """Get or create async lock for game."""
        if game_id not in self.game_locks:
            self.game_locks[game_id] = asyncio.Lock()
        return self.game_locks[game_id]
    
    async def check_and_register(self, query_id: str, user_id: int, 
                                 action: str, cooldown: float = 0.5) -> bool:
        """
        Перевірити чи можна обробити цей запит.
        
        Returns:
            True - можна обробляти
            False - це дублікат, ігноруй
        """
        current_time = time.time()
        
        # Cleanup старих записів кожні 60 секунд
        if current_time - self.last_cleanup > 60:
            await self._cleanup_old_records(current_time)
        
        # ✅ РІВЕНЬ 1: Query ID Check
        if query_id in self.processed_queries:
            logger.warning(f"🚫 DUPLICATE: Query {query_id} already processed")
            return False
        
        # ✅ РІВЕНЬ 2: Timestamp Check для цього query
        if query_id in self.query_timestamps:
            time_since = current_time - self.query_timestamps[query_id]
            if time_since < cooldown:
                logger.warning(f"🚫 DUPLICATE: Query {query_id} too fast ({time_since:.2f}s)")
                return False
        
        # ✅ РІВЕНЬ 3: User Action Check
        user_key = f"{user_id}:{action}"
        if user_key in self.user_actions:
            last_time = self.user_actions[user_key].get('last_time', 0)
            time_since = current_time - last_time
            if time_since < cooldown:
                logger.warning(f"🚫 DUPLICATE: User {user_id} action '{action}' too fast ({time_since:.2f}s)")
                return False
        
        # ✅ Реєструємо як оброблений
        self.processed_queries.add(query_id)
        self.query_timestamps[query_id] = current_time
        self.user_actions[user_key] = {'last_time': current_time}
        
        logger.debug(f"✅ ALLOWED: Query {query_id}, User {user_id}, Action '{action}'")
        return True
    
    async def _cleanup_old_records(self, current_time: float):
        """Видалити старі записи (>5 хвилин)."""
        cutoff = current_time - 300  # 5 minutes
        
        # Cleanup queries
        old_queries = [qid for qid, ts in self.query_timestamps.items() if ts < cutoff]
        for qid in old_queries:
            self.processed_queries.discard(qid)
            del self.query_timestamps[qid]
        
        # Cleanup user actions
        for user_key in list(self.user_actions.keys()):
            if self.user_actions[user_key].get('last_time', 0) < cutoff:
                del self.user_actions[user_key]
        
        # Cleanup empty game locks
        for game_id in list(self.game_locks.keys()):
            if self.game_locks[game_id].locked():
                continue
            # Видалити неактивні locks
            del self.game_locks[game_id]
        
        self.last_cleanup = current_time
        logger.info(f"🧹 Cleanup: {len(old_queries)} old queries removed")


# Глобальний інстанс
button_protection = ButtonDuplicateProtection()


# ============================================================================
# ДЕКОРАТОР ДЛЯ CALLBACK HANDLERS
# ============================================================================

def prevent_duplicates(action_type: str, cooldown: float = 0.5):
    """
    Декоратор для захисту callback handlers від дублікатів.
    
    Usage:
        @prevent_duplicates("night_action", cooldown=1.0)
        async def night_action_callback(update, context):
            ...
    """
    def decorator(func):
        async def wrapper(update, context):
            query = update.callback_query
            
            if not query:
                return await func(update, context)
            
            query_id = query.id
            user_id = query.from_user.id
            
            # Перевірка дублікату
            allowed = await button_protection.check_and_register(
                query_id, user_id, action_type, cooldown
            )
            
            if not allowed:
                # Це дублікат - ігноруємо без answer (щоб не спамити)
                logger.warning(f"⛔ BLOCKED DUPLICATE: {action_type} from user {user_id}")
                return
            
            # Виконуємо оригінальну функцію
            try:
                return await func(update, context)
            except Exception as e:
                logger.error(f"Error in {action_type}: {e}", exc_info=True)
                try:
                    await query.answer("❌ Помилка обробки. Спробуй ще раз.", show_alert=True)
                except:
                    pass
        
        return wrapper
    return decorator


# ============================================================================
# ВИПРАВЛЕНІ CALLBACK HANDLERS ДЛЯ main.py
# ============================================================================

# ЗАМІНІТЬ ВСІ callback handlers в main.py на ці версії:

@prevent_duplicates("lobby_action", cooldown=0.5)
async def lobby_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle lobby button callbacks - ЗАХИЩЕНО."""
    query = update.callback_query
    
    # ВАЖЛИВО: answer() ОДРАЗУ щоб прибрати "loading"
    try:
        await query.answer()
    except Exception as e:
        if "too old" not in str(e).lower():
            logger.debug(f"Answer error (non-critical): {e}")
    
    chat_id = query.message.chat.id
    game = game_manager.get_game(chat_id)
    
    if not game or game.phase != Phase.LOBBY:
        try:
            await query.answer("❌ Ця гра вже не активна", show_alert=True)
        except:
            pass
        return
    
    action = query.data
    
    # Отримати game lock
    lock = button_protection.get_game_lock(game.game_id)
    
    async with lock:
        if action == "lobby_join":
            await handle_lobby_join(update, context, game)
        elif action == "lobby_add_bot":
            await handle_lobby_add_bot(update, context, game)
        elif action == "lobby_start":
            await handle_lobby_start(update, context, game)


@prevent_duplicates("night_action", cooldown=1.0)
async def night_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle night action callbacks - ЗАХИЩЕНО."""
    query = update.callback_query
    
    # Answer ОДРАЗУ
    try:
        await query.answer()
    except Exception as e:
        if "too old" not in str(e).lower():
            logger.debug(f"Answer error: {e}")
    
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
    
    # Захист від повторних дій (крім вибору дії детектива)
    if data not in ["detective_check", "detective_shoot"]:
        if player.has_acted_this_night:
            try:
                await query.answer("❌ Ти вже зробив вибір", show_alert=True)
            except:
                pass
            return
    
    # Отримати game lock
    lock = button_protection.get_game_lock(game.game_id)
    
    async with lock:
        # Handle different actions
        if data.startswith("don_kill_"):
            target_id = data.replace("don_kill_", "")
            await handle_don_kill_callback(game, player, target_id, context)
        
        elif data.startswith("doc_heal_"):
            target_id = data.replace("doc_heal_", "")
            await handle_doctor_heal_callback(game, player, target_id, context)
        
        elif data == "detective_check":
            targets = [(p.username, pid) for pid, p in game.players.items() 
                       if p.is_alive and pid != player.player_id]
            await query.message.reply_text(
                "🔍 <b>Обери кого перевірити:</b>",
                reply_markup=visual.get_detective_target_keyboard(targets, "check"),
                parse_mode='HTML'
            )
        
        elif data == "detective_shoot":
            if player.has_used_gun:
                try:
                    await query.answer("❌ Пістолет вже використано!", show_alert=True)
                except:
                    pass
                return
            
            targets = [(p.username, pid) for pid, p in game.players.items() 
                       if p.is_alive and pid != player.player_id]
            await query.message.reply_text(
                "🔫 <b>Обери в кого стріляти:</b>\n\n"
                "<i>⚠️ Можна використати тільки РАЗ!</i>",
                reply_markup=visual.get_detective_target_keyboard(targets, "shoot"),
                parse_mode='HTML'
            )
        
        elif data.startswith("det_check_"):
            target_id = data.replace("det_check_", "")
            await handle_detective_check_callback(game, player, target_id, context)
        
        elif data.startswith("det_shoot_"):
            # КРИТИЧНА ПЕРЕВІРКА: чи не стріляє в себе
            if player.has_used_gun:
                try:
                    await query.answer("❌ Пістолет вже використано!", show_alert=True)
                except:
                    pass
                return
            
            target_id = data.replace("det_shoot_", "")
            
            # ЗАБОРОНА САМОГУБСТВА
            if target_id == player.player_id:
                try:
                    await query.answer(
                        "❌ Не можна стріляти в себе!\n\nЦе самогубство! 🔫🚫",
                        show_alert=True
                    )
                except:
                    pass
                return
            
            await handle_detective_shoot_callback(game, player, target_id, context)
        
        elif data.startswith("potato_"):
            if data == "potato_skip":
                player.has_thrown_potato = True
                player.has_acted_this_night = True
                await query.message.reply_text(visual.ACTION_CONFIRMED["potato_skip"])
                await check_all_night_actions_done(game, context)
            else:
                target_id = data.replace("potato_", "")
                await handle_potato_throw_callback(game, player, target_id, context)
        
        elif data.startswith("petrushka_"):
            if data == "petrushka_skip":
                player.has_used_petrushka = True
                player.has_acted_this_night = True
                await query.message.reply_text(visual.ACTION_CONFIRMED["petrushka_skip"])
                await check_all_night_actions_done(game, context)
            else:
                target_id = data.replace("petrushka_", "")
                await handle_petrushka_callback(game, player, target_id, context)


@prevent_duplicates("voting", cooldown=0.3)
async def voting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle voting callbacks - ЗАХИЩЕНО."""
    query = update.callback_query
    
    # Answer ОДРАЗУ
    try:
        await query.answer()
    except Exception as e:
        if "too old" not in str(e).lower():
            logger.debug(f"Answer error: {e}")
    
    chat_id = query.message.chat.id
    game = game_manager.get_game(chat_id)
    
    if not game or game.phase == Phase.ENDED:
        return
    
    if game.phase != Phase.VOTING:
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
        return
    
    # Отримати game lock
    lock = button_protection.get_game_lock(game.game_id)
    
    if data in ["lynch_yes", "lynch_no"]:
        vote = "yes" if data == "lynch_yes" else "no"
        
        async with lock:
            # Дозволити зміну голосу, але не дублікати
            if player.player_id in game.lynch_votes:
                old_vote = game.lynch_votes[player.player_id]
                if old_vote == vote:
                    # Це дублікат того ж голосу - ігноруємо
                    return
            
            game.lynch_votes[player.player_id] = vote
            
            # Calculate votes
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
            
            # Відправити повідомлення в групу
            mayor_indicator = " 🎩x2" if player.role == "mayor" else ""
            vote_emoji = "👍" if vote == "yes" else "👎"
            
            await safe_send_message(
                context,
                game.group_chat_id,
                f"{vote_emoji} <b>{player.username}</b>{mayor_indicator} проголосував\n\n"
                f"📊 Так: {yes_count}/{alive_count} | Ні: {no_count}/{alive_count}",
                parse_mode='HTML'
            )
            
            # Update keyboard
            try:
                await query.message.edit_reply_markup(
                    reply_markup=visual.get_lynch_decision_keyboard_with_count(
                        yes_count, no_count, alive_count
                    )
                )
            except:
                pass
            
            # Check if all voted
            if len(game.lynch_votes) >= alive_count:
                await handle_lynch_decision_complete(game, context)


@prevent_duplicates("nomination", cooldown=0.5)
async def nomination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle nomination callbacks - ЗАХИЩЕНО."""
    query = update.callback_query
    
    # Answer ОДРАЗУ
    try:
        await query.answer()
    except Exception as e:
        if "too old" not in str(e).lower():
            logger.debug(f"Answer error: {e}")
    
    user_id = query.from_user.id
    data = query.data
    
    if not data.startswith("nominate_"):
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
    
    if not game or game.phase != Phase.VOTING or not player.is_alive:
        return
    
    # Отримати game lock
    lock = button_protection.get_game_lock(game.game_id)
    
    async with lock:
        # Перевірка чи вже номінував
        if player.player_id in game.nomination_votes:
            return
        
        game.nomination_votes[player.player_id] = candidate_id
        
        candidate = game.players[candidate_id]
        
        # Відправити в групу
        await safe_send_message(
            context,
            game.group_chat_id,
            f"🗳 <b>{player.username}</b> висунув кандидата",
            parse_mode='HTML'
        )
        
        await check_all_nominations_done(game, context)


@prevent_duplicates("confirmation", cooldown=0.3)
async def confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmation callbacks - ЗАХИЩЕНО."""
    query = update.callback_query
    
    # Answer ОДРАЗУ
    try:
        await query.answer()
    except Exception as e:
        if "too old" not in str(e).lower():
            logger.debug(f"Answer error: {e}")
    
    user_id = query.from_user.id
    data = query.data
    
    if data not in ["confirm_yes", "confirm_no"]:
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
    
    if not game or game.phase != Phase.VOTING or not player.is_alive:
        return
    
    if player.player_id == game.current_candidate:
        return
    
    # Отримати game lock
    lock = button_protection.get_game_lock(game.game_id)
    
    async with lock:
        # Дозволити зміну, але не дублікати
        if player.player_id in game.confirmation_votes:
            if game.confirmation_votes[player.player_id] == vote:
                return  # Дублікат
        
        game.confirmation_votes[player.player_id] = vote
        
        candidate = game.players[game.current_candidate]
        
        # Calculate votes
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
        
        vote_emoji = "👍" if vote == "yes" else "👎"
        mayor_indicator = " 🎩x2" if player.role == "mayor" else ""
        
        await safe_send_message(
            context,
            game.group_chat_id,
            f"{vote_emoji} <b>{player.username}</b>{mayor_indicator} проголосував\n\n"
            f"📊 За: {yes_count}/{alive_count} | Проти: {no_count}/{alive_count}",
            parse_mode='HTML'
        )


@prevent_duplicates("shop", cooldown=1.0)
async def shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle shop callbacks - ЗАХИЩЕНО."""
    query = update.callback_query
    
    # Answer ОДРАЗУ
    try:
        await query.answer()
    except Exception as e:
        if "too old" not in str(e).lower():
            logger.debug(f"Answer error: {e}")
    
    data = query.data
    
    if not data.startswith("shop_buy_"):
        return
    
    item_id = data.replace("shop_buy_", "")
    
    if item_id not in config.SHOP_ITEMS:
        return
    
    item = config.SHOP_ITEMS[item_id]
    user = query.from_user
    
    stats = await db.get_user_stats(user.id)
    if not stats:
        return
    
    if stats['points'] < item['cost']:
        shortfall = item['cost'] - stats['points']
        try:
            await query.answer(
                f"❌ Бракує {shortfall} 💰",
                show_alert=True
            )
        except:
            pass
        return
    
    # Process purchase
    await db.update_user_points(stats['id'], -item['cost'])
    await db.add_buff(user.id, item['buff_type'], item['games'])
    await db.add_purchase(user.id, item_id, item['cost'])
    
    try:
        await query.answer(f"✅ Куплено! -{item['cost']}💰", show_alert=True)
    except:
        pass


# ============================================================================
# ІНСТРУКЦІЇ ПО ЗАСТОСУВАННЮ
# ============================================================================
"""
📋 ЯК ЗАСТОСУВАТИ:

1. СКОПІЮЙ весь цей файл як button_protection.py в папку проекту

2. У main.py ДОДАЙ імпорт на початку:
   
   from button_protection import (
       button_protection,
       prevent_duplicates,
       lobby_callback,
       night_action_callback,
       voting_callback,
       nomination_callback,
       confirmation_callback,
       shop_callback
   )

3. ВИДАЛИ старі версії цих функцій з main.py

4. У main.py в розділі "Register callback handlers" ЗАМІНІТЬ на:
   
   application.add_handler(CallbackQueryHandler(lobby_callback, pattern="^lobby_"))
   application.add_handler(CallbackQueryHandler(night_action_callback, pattern="^(don_kill_|doc_heal_|detective_|det_|potato_|petrushka_)"))
   application.add_handler(CallbackQueryHandler(voting_callback, pattern="^lynch_"))
   application.add_handler(CallbackQueryHandler(nomination_callback, pattern="^nominate_"))
   application.add_handler(CallbackQueryHandler(confirmation_callback, pattern="^confirm_"))
   application.add_handler(CallbackQueryHandler(shop_callback, pattern="^shop_buy_"))

5. ТЕСТУЙ:
   - 10+ людей одночасно клікають кнопки
   - Логи мають показувати "🚫 DUPLICATE" для дублікатів
   - "✅ ALLOWED" для нормальних запитів

✅ РЕЗУЛЬТАТ:
- Жодних дублікатів подій
- Швидка реакція на кнопки
- Захист від спаму
- Стабільна робота при навантаженні
"""