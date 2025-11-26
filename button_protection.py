"""
🔥 УЛЬТИМАТИВНА СИСТЕМА ЗАХИСТУ V2 🔥

КРИТИЧНІ ЗМІНИ:
- Query ID tracking (Telegram native deduplication)
- User + Action + Game tracking
- Strict timestamp checks (<0.3s = block)
- Phase validation
- Processing flags
"""

import asyncio
import time
from typing import Dict, Set, Optional, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# ГЛОБАЛЬНА ДЕДУПЛІКАЦІЯ V2
# ============================================================================

class ButtonProtectionV2:
    """
    Посилена система захисту від дублікатів.
    
    НОВИЙ ПІДХІД:
    - Query ID + timestamp (0.3s cooldown)
    - User + Action + Game (prevent cross-game spam)
    - Processing flags per action type
    """
    
    def __init__(self):
        # Рівень 1: Query ID tracking
        self.processed_queries: Set[str] = set()
        self.query_times: Dict[str, float] = {}
        
        # Рівень 2: User + Action + Game
        # Key: f"{user_id}:{game_id}:{action}"
        self.user_game_actions: Dict[str, float] = {}
        
        # Рівень 3: Processing flags
        # Key: f"{game_id}:{action_type}"
        self.processing: Dict[str, bool] = {}
        
        # Cleanup
        self.last_cleanup = time.time()
    
    def check_and_register(self, query_id: str, user_id: int, 
                          game_id: int, action: str, 
                          cooldown: float = 0.3) -> bool:
        """
        Перевірити чи можна обробити запит.
        
        СТРОГІ ПРАВИЛА:
        - Query ID унікальний (Telegram guarantee)
        - Timestamp < 0.3s = BLOCK
        - User + Game + Action = ONE AT A TIME
        
        Returns:
            True - обробляти
            False - дублікат/спам, ігнорувати
        """
        current_time = time.time()
        
        # Cleanup кожні 30 секунд
        if current_time - self.last_cleanup > 30:
            self._cleanup(current_time)
        
        # ✅ CHECK 1: Query ID (найважливіше!)
        if query_id in self.processed_queries:
            logger.warning(f"🚫 DUPLICATE query_id: {query_id}")
            return False
        
        # ✅ CHECK 2: Query timestamp
        if query_id in self.query_times:
            time_since = current_time - self.query_times[query_id]
            if time_since < cooldown:
                logger.warning(f"🚫 SPAM query {query_id}: {time_since:.3f}s")
                return False
        
        # ✅ CHECK 3: User + Game + Action
        user_key = f"{user_id}:{game_id}:{action}"
        if user_key in self.user_game_actions:
            time_since = current_time - self.user_game_actions[user_key]
            if time_since < cooldown:
                logger.warning(f"🚫 SPAM user {user_id} action '{action}': {time_since:.3f}s")
                return False
        
        # ✅ REGISTER
        self.processed_queries.add(query_id)
        self.query_times[query_id] = current_time
        self.user_game_actions[user_key] = current_time
        
        logger.debug(f"✅ ALLOWED: query={query_id}, user={user_id}, game={game_id}, action={action}")
        return True
    
    def is_processing(self, game_id: int, action_type: str) -> bool:
        """Перевірити чи обробляється дія зараз."""
        key = f"{game_id}:{action_type}"
        return self.processing.get(key, False)
    
    def set_processing(self, game_id: int, action_type: str, value: bool):
        """Встановити статус обробки."""
        key = f"{game_id}:{action_type}"
        self.processing[key] = value
        if value:
            logger.debug(f"🔒 Processing START: {action_type} (game {game_id})")
        else:
            logger.debug(f"🔓 Processing END: {action_type} (game {game_id})")
    
    def _cleanup(self, current_time: float):
        """Очистити старі записи."""
        cutoff = current_time - 60  # 1 minute
        
        # Cleanup queries
        old_queries = [q for q, t in self.query_times.items() if t < cutoff]
        for q in old_queries:
            self.processed_queries.discard(q)
            self.query_times.pop(q, None)
        
        # Cleanup user actions
        old_actions = [k for k, t in self.user_game_actions.items() if t < cutoff]
        for k in old_actions:
            self.user_game_actions.pop(k, None)
        
        # Cleanup stuck processing flags
        stuck = [k for k, v in self.processing.items() if v]
        if stuck:
            logger.warning(f"⚠️ Clearing {len(stuck)} stuck processing flags")
            for k in stuck:
                self.processing[k] = False
        
        self.last_cleanup = current_time
        if old_queries or old_actions:
            logger.info(f"🧹 Cleanup: {len(old_queries)} queries, {len(old_actions)} actions")


# Глобальний інстанс V2
button_protection = ButtonProtectionV2()


# ============================================================================
# CALLBACK HANDLERS - ПОСИЛЕНА ВЕРСІЯ
# ============================================================================

async def voting_callback_v2(update, context) -> None:
    """
    Голосування - МАКСИМАЛЬНИЙ ЗАХИСТ.
    
    ПРОБЛЕМА: Люди спамлять кнопки Yes/No
    РІШЕННЯ: Query ID + timestamp + processing flag
    """
    query = update.callback_query
    
    # Безпечний answer (не чекаємо результату)
    asyncio.create_task(_safe_answer(query))
    
    user_id = query.from_user.id
    data = query.data
    
    if data not in ["lynch_yes", "lynch_no"]:
        return
    
    # Знайти гру
    from engine import game_manager, Phase
    
    game = None
    for g in game_manager.games.values():
        for p in g.players.values():
            if p.telegram_id == user_id:
                game = g
                break
        if game:
            break
    
    if not game or game.phase != Phase.VOTING:
        return
    
    # Знайти гравця
    player = None
    for p in game.players.values():
        if p.telegram_id == user_id:
            player = p
            break
    
    if not player or not player.is_alive:
        return
    
    # ✅ КРИТИЧНА ПЕРЕВІРКА - дедуплікація
    vote_action = f"lynch_vote_{data}"
    if not button_protection.check_and_register(
        query.id, user_id, game.game_id, vote_action, cooldown=0.3
    ):
        logger.warning(f"⛔ BLOCKED duplicate vote from {player.username}")
        return
    
    # ✅ ПЕРЕВІРКА PROCESSING
    if button_protection.is_processing(game.game_id, "lynch_decision"):
        logger.warning(f"⛔ BLOCKED vote during processing: {player.username}")
        return
    
    vote = "yes" if data == "lynch_yes" else "no"
    
    # Дозволити зміну голосу, але не дублікати
    if player.player_id in game.lynch_votes:
        if game.lynch_votes[player.player_id] == vote:
            logger.warning(f"⛔ Same vote from {player.username}, ignored")
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
    
    # Send message
    from engine import safe_send_message
    import visual
    
    mayor_indicator = " 🎩x2" if player.role == "mayor" else ""
    vote_emoji = "👍" if vote == "yes" else "👎"
    
    await safe_send_message(
        context,
        game.group_chat_id,
        f"{vote_emoji} <b>{player.username}</b>{mayor_indicator} проголосував\n\n"
        f"📊 Так: {yes_count}/{alive_count} | Ні: {no_count}/{alive_count}",
        parse_mode='HTML'
    )
    
    logger.info(f"✅ Vote registered: {player.username} -> {vote}")
    
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
        logger.info(f"🔔 All {alive_count} players voted!")
        from engine import handle_lynch_decision_complete
        await handle_lynch_decision_complete(game, context)


async def nomination_callback_v2(update, context) -> None:
    """
    Номінації - ПОСИЛЕНИЙ ЗАХИСТ.
    """
    query = update.callback_query
    asyncio.create_task(_safe_answer(query))
    
    user_id = query.from_user.id
    data = query.data
    
    if not data.startswith("nominate_"):
        return
    
    candidate_id = data.replace("nominate_", "")
    
    # Знайти гру
    from engine import game_manager, Phase
    
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
    
    if not game or game.phase != Phase.VOTING or not player or not player.is_alive:
        return
    
    # ✅ ДЕДУПЛІКАЦІЯ
    if not button_protection.check_and_register(
        query.id, user_id, game.game_id, "nomination", cooldown=0.5
    ):
        logger.warning(f"⛔ BLOCKED duplicate nomination from {player.username}")
        return
    
    # ✅ PROCESSING CHECK
    if button_protection.is_processing(game.game_id, "nominations"):
        logger.warning(f"⛔ BLOCKED nomination during processing: {player.username}")
        return
    
    # Перевірка чи вже номінував
    if player.player_id in game.nomination_votes:
        logger.warning(f"⛔ {player.username} already nominated")
        return
    
    game.nomination_votes[player.player_id] = candidate_id
    candidate = game.players[candidate_id]
    
    logger.info(f"✅ Nomination: {player.username} -> {candidate.username}")
    
    # Send to group
    from engine import safe_send_message
    await safe_send_message(
        context,
        game.group_chat_id,
        f"🗳 <b>{player.username}</b> висунув кандидата",
        parse_mode='HTML'
    )
    
    # Check if all nominated
    from engine import check_all_nominations_done
    await check_all_nominations_done(game, context)


async def confirmation_callback_v2(update, context) -> None:
    """
    Фінальне підтвердження - ПОСИЛЕНИЙ ЗАХИСТ.
    """
    query = update.callback_query
    asyncio.create_task(_safe_answer(query))
    
    user_id = query.from_user.id
    data = query.data
    
    if data not in ["confirm_yes", "confirm_no"]:
        return
    
    vote = "yes" if data == "confirm_yes" else "no"
    
    # Знайти гру
    from engine import game_manager, Phase
    
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
    
    if not game or game.phase != Phase.VOTING or not player or not player.is_alive:
        return
    
    if player.player_id == game.current_candidate:
        return
    
    # ✅ ДЕДУПЛІКАЦІЯ
    confirm_action = f"confirm_{vote}"
    if not button_protection.check_and_register(
        query.id, user_id, game.game_id, confirm_action, cooldown=0.3
    ):
        logger.warning(f"⛔ BLOCKED duplicate confirmation from {player.username}")
        return
    
    # Дозволити зміну, але не дублікати
    if player.player_id in game.confirmation_votes:
        if game.confirmation_votes[player.player_id] == vote:
            logger.warning(f"⛔ Same confirmation from {player.username}")
            return
    
    game.confirmation_votes[player.player_id] = vote
    
    # Calculate
    yes_count = 0
    no_count = 0
    for voter_id, v in game.confirmation_votes.items():
        voter = game.players[voter_id]
        weight = 2 if voter.role == "mayor" else 1
        if v == "yes":
            yes_count += weight
        else:
            no_count += weight
    
    candidate = game.players[game.current_candidate]
    alive_count = sum(1 for p in game.players.values() if p.is_alive) - 1
    
    vote_emoji = "👍" if vote == "yes" else "👎"
    mayor_indicator = " 🎩x2" if player.role == "mayor" else ""
    
    from engine import safe_send_message
    await safe_send_message(
        context,
        game.group_chat_id,
        f"{vote_emoji} <b>{player.username}</b>{mayor_indicator} проголосував\n\n"
        f"📊 За: {yes_count}/{alive_count} | Проти: {no_count}/{alive_count}",
        parse_mode='HTML'
    )
    
    logger.info(f"✅ Confirmation: {player.username} -> {vote} for {candidate.username}")


async def _safe_answer(query):
    """Безпечний answer без блокування."""
    try:
        await query.answer()
    except Exception as e:
        error_msg = str(e).lower()
        if "too old" not in error_msg and "expired" not in error_msg:
            logger.debug(f"Answer error (non-critical): {e}")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'button_protection',
    'voting_callback_v2',
    'nomination_callback_v2',
    'confirmation_callback_v2',
]