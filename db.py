"""
Database access layer for Mafia Bot using aiosqlite.
"""

import aiosqlite
import json
from typing import Optional, Dict, List, Any
from datetime import datetime
import config


_db: Optional[aiosqlite.Connection] = None


async def init_db() -> None:
    """Initialize database connection and create tables."""
    global _db
    _db = await aiosqlite.connect(config.DATABASE_FILE)  # ВИПРАВЛЕНО: DB_PATH -> DATABASE_FILE
    _db.row_factory = aiosqlite.Row
    await _create_tables()


async def close_db() -> None:
    """Close database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


async def _create_tables() -> None:
    """Create all necessary tables if they don't exist."""
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            username TEXT,
            first_seen_at TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            total_games INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            kills INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0,
            correct_checks INTEGER DEFAULT 0
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_chat_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            winner_side TEXT,
            total_rounds INTEGER DEFAULT 0,
            is_bukovel INTEGER DEFAULT 0
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS game_players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            user_id INTEGER,
            bot_name TEXT,
            role TEXT NOT NULL,
            is_bot INTEGER NOT NULL,
            is_alive INTEGER DEFAULT 1,
            kills INTEGER DEFAULT 0,
            heals INTEGER DEFAULT 0,
            checks INTEGER DEFAULT 0,
            FOREIGN KEY (game_id) REFERENCES games(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS user_buffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            buff_type TEXT NOT NULL,
            remaining_games INTEGER NOT NULL,
            payload TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    await _db.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_code TEXT NOT NULL,
            points_spent INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    
    await _db.commit()


async def get_or_create_user(telegram_id: int, username: Optional[str]) -> int:
    """Get existing user or create new one. Returns user_id."""
    cursor = await _db.execute(
        "SELECT id FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    row = await cursor.fetchone()
    
    if row:
        return row[0]
    
    now = datetime.now().isoformat()
    cursor = await _db.execute(
        "INSERT INTO users (telegram_id, username, first_seen_at) VALUES (?, ?, ?)",
        (telegram_id, username, now)
    )
    await _db.commit()
    return cursor.lastrowid


async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get user data by telegram_id."""
    cursor = await _db.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def update_user_points(user_id: int, delta: int) -> None:
    """Update user points by delta."""
    await _db.execute(
        "UPDATE users SET points = points + ? WHERE id = ?",
        (delta, user_id)
    )
    await _db.commit()


async def update_user_stats(user_id: int, **kwargs) -> None:
    """Update user statistics."""
    set_clauses = []
    values = []
    
    for key, value in kwargs.items():
        if key in ['total_games', 'wins', 'losses', 'kills', 'saves', 'correct_checks']:
            set_clauses.append(f"{key} = {key} + ?")
            values.append(value)
    
    if not set_clauses:
        return
    
    values.append(user_id)
    query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
    await _db.execute(query, values)
    await _db.commit()


async def get_user_stats(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Get user statistics."""
    cursor = await _db.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def add_game(group_chat_id: int, is_bukovel: bool = False) -> int:
    """Create new game. Returns game_id."""
    now = datetime.now().isoformat()
    cursor = await _db.execute(
        "INSERT INTO games (group_chat_id, started_at, is_bukovel) VALUES (?, ?, ?)",
        (group_chat_id, now, 1 if is_bukovel else 0)
    )
    await _db.commit()
    return cursor.lastrowid


async def end_game(game_id: int, winner_side: str, total_rounds: int) -> None:
    """Mark game as ended."""
    now = datetime.now().isoformat()
    await _db.execute(
        "UPDATE games SET ended_at = ?, winner_side = ?, total_rounds = ? WHERE id = ?",
        (now, winner_side, total_rounds, game_id)
    )
    await _db.commit()


async def add_game_player(
    game_id: int,
    role: str,
    is_bot: bool,
    user_id: Optional[int] = None,
    bot_name: Optional[str] = None
) -> int:
    """Add player to game. Returns player_id."""
    cursor = await _db.execute(
        "INSERT INTO game_players (game_id, user_id, bot_name, role, is_bot) VALUES (?, ?, ?, ?, ?)",
        (game_id, user_id, bot_name, role, 1 if is_bot else 0)
    )
    await _db.commit()
    return cursor.lastrowid


async def update_game_player_stats(player_id: int, **kwargs) -> None:
    """Update game player statistics."""
    set_clauses = []
    values = []
    
    for key, value in kwargs.items():
        if key in ['kills', 'heals', 'checks', 'is_alive']:
            set_clauses.append(f"{key} = ?")
            values.append(value)
    
    if not set_clauses:
        return
    
    values.append(player_id)
    query = f"UPDATE game_players SET {', '.join(set_clauses)} WHERE id = ?"
    await _db.execute(query, values)
    await _db.commit()


async def get_user_buffs(telegram_id: int) -> List[Dict[str, Any]]:
    """Get active buffs for user."""
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return []
    
    cursor = await _db.execute(
        "SELECT * FROM user_buffs WHERE user_id = ? AND remaining_games > 0",
        (user['id'],)
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def add_buff(telegram_id: int, buff_type: str, games: int, payload: Optional[Dict] = None) -> None:
    """Add buff to user."""
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return
    
    now = datetime.now().isoformat()
    payload_str = json.dumps(payload) if payload else None
    
    await _db.execute(
        "INSERT INTO user_buffs (user_id, buff_type, remaining_games, payload, created_at) VALUES (?, ?, ?, ?, ?)",
        (user['id'], buff_type, games, payload_str, now)
    )
    await _db.commit()


async def decrement_buff_games(telegram_id: int) -> None:
    """Decrement remaining_games for all user's buffs and delete expired ones."""
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return
    
    await _db.execute(
        "UPDATE user_buffs SET remaining_games = remaining_games - 1 WHERE user_id = ?",
        (user['id'],)
    )
    await _db.execute(
        "DELETE FROM user_buffs WHERE user_id = ? AND remaining_games <= 0",
        (user['id'],)
    )
    await _db.commit()


async def add_purchase(telegram_id: int, item_code: str, points_spent: int) -> None:
    """Record purchase."""
    user = await get_user_by_telegram_id(telegram_id)
    if not user:
        return
    
    now = datetime.now().isoformat()
    await _db.execute(
        "INSERT INTO purchases (user_id, item_code, points_spent, created_at) VALUES (?, ?, ?, ?)",
        (user['id'], item_code, points_spent, now)
    )
    await _db.commit()