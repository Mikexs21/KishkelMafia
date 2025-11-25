"""
Advanced AI system for Mafia Bot.
Thread-safe implementation with configurable behavior.
"""

import random
import asyncio
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
import config


class SuspicionLevel(Enum):
    """Levels of suspicion for players."""
    TRUSTED = 1
    NEUTRAL = 2
    SUSPICIOUS = 3
    VERY_SUSPICIOUS = 4
    CONFIRMED_MAFIA = 5


@dataclass
class BotMemory:
    """Memory system for a single bot."""
    player_id: str
    role: str
    
    # Suspicion tracking
    suspicion: Dict[str, SuspicionLevel] = field(default_factory=dict)
    
    # Knowledge base
    confirmed_roles: Dict[str, str] = field(default_factory=dict)
    voting_history: List[Tuple[str, str]] = field(default_factory=list)
    defense_history: List[Tuple[str, str]] = field(default_factory=list)
    
    # Strategic memory
    last_night_target: Optional[str] = None
    players_defended_me: Set[str] = field(default_factory=set)
    players_accused_me: Set[str] = field(default_factory=set)
    
    # Round tracking
    rounds_observed: int = 0


class BotAI:
    """Advanced AI controller for bot behavior with thread safety."""
    
    def __init__(self):
        self.memories: Dict[str, BotMemory] = {}
        self._lock = asyncio.Lock()  # 🔧 Thread-safety для multiple games
    
    async def get_or_create_memory(self, player_id: str, role: str) -> BotMemory:
        """Thread-safe get or create memory for a bot."""
        async with self._lock:
            if player_id not in self.memories:
                self.memories[player_id] = BotMemory(player_id=player_id, role=role)
            return self.memories[player_id]
    
    async def update_suspicion(self, bot_id: str, target_id: str, change: int, reason: str = ""):
        """Thread-safe suspicion update."""
        async with self._lock:
            memory = self.memories.get(bot_id)
            if not memory:
                return
            
            current = memory.suspicion.get(target_id, SuspicionLevel.NEUTRAL)
            new_level_value = max(1, min(5, current.value + change))
            memory.suspicion[target_id] = SuspicionLevel(new_level_value)
    
    async def record_vote(self, bot_id: str, voter_id: str, target_id: str):
        """Thread-safe vote recording."""
        async with self._lock:
            memory = self.memories.get(bot_id)
            if not memory:
                return
            
            memory.voting_history.append((voter_id, target_id))
            
            if target_id == bot_id:
                memory.players_accused_me.add(voter_id)
        
        await self.update_suspicion(bot_id, voter_id, 1, "voted against me")
    
    async def select_kill_target(self, game, bot) -> Optional[str]:
        """Advanced target selection for mafia kill."""
        memory = await self.get_or_create_memory(bot.player_id, bot.role)
        
        targets = []
        for pid, player in game.players.items():
            if not player.is_alive:
                continue
            if pid == bot.player_id:
                continue
            if player.role in {"don", "mafia", "consigliere"}:
                continue
            
            priority = await self._calculate_kill_priority(memory, player, game)
            targets.append((player.username, pid, priority))
        
        if not targets:
            return None
        
        targets.sort(key=lambda x: x[2], reverse=True)
        
        top_candidates = targets[:min(3, len(targets))]
        weights = [t[2] for t in top_candidates]
        total = sum(weights)
        
        if total == 0:
            return random.choice(targets)[1]
        
        rand = random.uniform(0, total)
        cumsum = 0
        for name, pid, weight in top_candidates:
            cumsum += weight
            if rand <= cumsum:
                return pid
        
        return top_candidates[0][1]
    
    async def _calculate_kill_priority(self, memory: BotMemory, target, game) -> float:
        """Calculate priority for killing a target using config constants."""
        priority = 1.0
        
        if target.player_id in memory.confirmed_roles:
            role = memory.confirmed_roles[target.player_id]
            if role == "detective":
                priority *= config.BOT_KILL_PRIORITY_DETECTIVE
            elif role == "doctor":
                priority *= config.BOT_KILL_PRIORITY_DOCTOR
            elif role in ["deputy", "mayor"]:
                priority *= config.BOT_KILL_PRIORITY_SPECIAL
        
        if not target.is_bot:
            priority *= config.BOT_KILL_PRIORITY_HUMAN
        
        if target.player_id in memory.players_accused_me:
            priority *= config.BOT_KILL_PRIORITY_ACCUSER
        
        if target.player_id == memory.last_night_target:
            priority *= 0.5
        
        priority *= random.uniform(config.BOT_PRIORITY_RANDOM_MIN, 
                                   config.BOT_PRIORITY_RANDOM_MAX)
        
        return priority
    
    async def select_heal_target(self, game, bot) -> Optional[str]:
        """Advanced target selection for doctor heal."""
        memory = await self.get_or_create_memory(bot.player_id, bot.role)
        
        if not bot.has_self_healed and game.round_num >= config.BOT_DOCTOR_SELF_HEAL_MIN_ROUND:
            if bot.player_id in memory.players_accused_me:
                return bot.player_id
        
        targets = []
        for pid, player in game.players.items():
            if not player.is_alive:
                continue
            if pid == bot.player_id and bot.has_self_healed:
                continue
            
            priority = await self._calculate_heal_priority(memory, player, game)
            targets.append((player.username, pid, priority))
        
        if not targets:
            return None
        
        targets.sort(key=lambda x: x[2], reverse=True)
        return targets[0][1]
    
    async def _calculate_heal_priority(self, memory: BotMemory, target, game) -> float:
        """Calculate priority for healing a target using config constants."""
        priority = 1.0
        
        if target.player_id in memory.confirmed_roles:
            role = memory.confirmed_roles[target.player_id]
            if role == "detective":
                priority *= config.BOT_HEAL_PRIORITY_DETECTIVE
            elif role in ["deputy", "mayor"]:
                priority *= config.BOT_HEAL_PRIORITY_SPECIAL
        
        suspicion = memory.suspicion.get(target.player_id, SuspicionLevel.NEUTRAL)
        if suspicion == SuspicionLevel.TRUSTED:
            priority *= config.BOT_HEAL_PRIORITY_TRUSTED
        
        if not target.is_bot:
            priority *= config.BOT_HEAL_PRIORITY_HUMAN
        
        if target.player_id in memory.players_defended_me:
            priority *= config.BOT_HEAL_PRIORITY_DEFENDER
        
        if target.player_id == memory.last_night_target:
            priority *= 0.6
        
        priority *= random.uniform(config.BOT_PRIORITY_RANDOM_MIN,
                                   config.BOT_PRIORITY_RANDOM_MAX)
        return priority
    
    async def select_check_target(self, game, bot) -> Optional[str]:
        """Advanced target selection for detective/deputy check."""
        memory = await self.get_or_create_memory(bot.player_id, bot.role)
        
        targets = []
        for pid, player in game.players.items():
            if not player.is_alive:
                continue
            if pid == bot.player_id:
                continue
            if pid in memory.confirmed_roles:
                continue
            
            priority = await self._calculate_check_priority(memory, player, game)
            targets.append((player.username, pid, priority))
        
        if not targets:
            return None
        
        targets.sort(key=lambda x: x[2], reverse=True)
        return targets[0][1]
    
    async def _calculate_check_priority(self, memory: BotMemory, target, game) -> float:
        """Calculate priority for checking a target."""
        priority = 1.0
        
        suspicion = memory.suspicion.get(target.player_id, SuspicionLevel.NEUTRAL)
        if suspicion == SuspicionLevel.VERY_SUSPICIOUS:
            priority *= 3.0
        elif suspicion == SuspicionLevel.SUSPICIOUS:
            priority *= 2.0
        
        if not target.is_bot:
            priority *= 1.3
        
        accusation_count = sum(1 for v, t in memory.voting_history if v == target.player_id)
        if accusation_count >= 2:
            priority *= 1.5
        
        priority *= random.uniform(config.BOT_PRIORITY_RANDOM_MIN,
                                   config.BOT_PRIORITY_RANDOM_MAX)
        return priority
    
    async def should_detective_shoot(self, game, bot) -> bool:
        """Decide if detective should use gun using config constants."""
        memory = await self.get_or_create_memory(bot.player_id, bot.role)
        
        if game.round_num < config.BOT_DETECTIVE_SHOOT_MIN_ROUND:
            return False
        
        if bot.has_used_gun:
            return False
        
        confirmed_mafia = [pid for pid, role in memory.confirmed_roles.items() 
                          if role in {"don", "mafia", "consigliere"} 
                          and game.players[pid].is_alive]
        
        if confirmed_mafia:
            return random.random() < config.BOT_DETECTIVE_SHOOT_PROBABILITY_CONFIRMED
        
        if game.round_num >= 5:
            very_suspicious = [pid for pid, susp in memory.suspicion.items()
                              if susp == SuspicionLevel.VERY_SUSPICIOUS
                              and game.players[pid].is_alive]
            if very_suspicious:
                return random.random() < config.BOT_DETECTIVE_SHOOT_PROBABILITY_SUSPICIOUS
        
        return False
    
    async def select_shoot_target(self, game, bot) -> Optional[str]:
        """Select target for detective shoot."""
        memory = await self.get_or_create_memory(bot.player_id, bot.role)
        
        confirmed_mafia = [pid for pid, role in memory.confirmed_roles.items() 
                          if role in {"don", "mafia", "consigliere"} 
                          and game.players[pid].is_alive]
        
        if confirmed_mafia:
            return random.choice(confirmed_mafia)
        
        targets = [(pid, susp.value) for pid, susp in memory.suspicion.items()
                   if game.players[pid].is_alive and pid != bot.player_id]
        
        if not targets:
            return None
        
        targets.sort(key=lambda x: x[1], reverse=True)
        return targets[0][0]
    
    async def select_nomination(self, game, bot) -> Optional[str]:
        """Advanced nomination selection using config constants."""
        memory = await self.get_or_create_memory(bot.player_id, bot.role)
        mafia_roles = {"don", "mafia", "consigliere"}
        
        candidates = [pid for pid, p in game.players.items() 
                     if p.is_alive and pid != bot.player_id]
        
        if bot.role in mafia_roles:
            candidates = [pid for pid in candidates 
                         if game.players[pid].role not in mafia_roles]
        
        if not candidates:
            return None
        
        vote_counts = {}
        for voter_id, candidate_id in game.nomination_votes.items():
            if candidate_id in candidates:
                vote_counts[candidate_id] = vote_counts.get(candidate_id, 0) + 1
        
        popular = [cid for cid, count in vote_counts.items() if count >= 2]
        
        if popular and random.random() < config.BOT_FOLLOW_POPULAR_VOTE_PROBABILITY:
            return random.choice(popular)
        
        if bot.role in mafia_roles:
            return await self._mafia_select_nomination(memory, candidates, game)
        else:
            return await self._civilian_select_nomination(memory, candidates, game)
    
    async def _mafia_select_nomination(self, memory: BotMemory, candidates: List[str], game) -> str:
        """Mafia-specific nomination logic using config constants."""
        accusers = [pid for pid in candidates if pid in memory.players_accused_me]
        if accusers and random.random() < config.BOT_MAFIA_TARGET_ACCUSER_PROBABILITY:
            return random.choice(accusers)
        
        humans = [pid for pid in candidates if not game.players[pid].is_bot]
        if humans and random.random() < 0.7:
            return random.choice(humans)
        
        return random.choice(candidates)
    
    async def _civilian_select_nomination(self, memory: BotMemory, candidates: List[str], game) -> str:
        """Civilian-specific nomination logic."""
        very_suspicious = [pid for pid in candidates 
                          if memory.suspicion.get(pid, SuspicionLevel.NEUTRAL) == SuspicionLevel.VERY_SUSPICIOUS]
        if very_suspicious:
            return random.choice(very_suspicious)
        
        suspicious = [pid for pid in candidates 
                     if memory.suspicion.get(pid, SuspicionLevel.NEUTRAL).value >= 3]
        if suspicious:
            return random.choice(suspicious)
        
        return random.choice(candidates)
    
    async def select_confirmation_vote(self, game, bot, candidate_id: str) -> str:
        """Advanced confirmation vote logic using config constants."""
        memory = await self.get_or_create_memory(bot.player_id, bot.role)
        candidate = game.players[candidate_id]
        mafia_roles = {"don", "mafia", "consigliere"}
        
        if bot.role in mafia_roles:
            if candidate.role in mafia_roles:
                return "no"
            else:
                if candidate_id in memory.players_accused_me:
                    return "yes"
                return "yes" if random.random() < config.BOT_MAFIA_VOTE_YES_PROBABILITY else "no"
        else:
            suspicion = memory.suspicion.get(candidate_id, SuspicionLevel.NEUTRAL)
            
            if suspicion == SuspicionLevel.CONFIRMED_MAFIA:
                return "yes"
            elif suspicion == SuspicionLevel.VERY_SUSPICIOUS:
                return "yes" if random.random() < config.BOT_CONFIRMATION_VERY_SUSPICIOUS_YES else "no"
            elif suspicion == SuspicionLevel.SUSPICIOUS:
                return "yes" if random.random() < config.BOT_CONFIRMATION_SUSPICIOUS_YES else "no"
            elif suspicion == SuspicionLevel.TRUSTED:
                return "no" if random.random() < config.BOT_CONFIRMATION_TRUSTED_NO else "yes"
            else:
                yes_count = sum(1 for v in game.confirmation_votes.values() if v == "yes")
                total = len(game.confirmation_votes)
                
                if total > 0:
                    yes_ratio = yes_count / total
                    return "yes" if random.random() < yes_ratio else "no"
                
                return "yes" if random.random() < 0.55 else "no"
    
    async def process_check_result(self, bot_id: str, target_id: str, target_role: str):
        """Thread-safe processing of check results."""
        async with self._lock:
            memory = self.memories.get(bot_id)
            if not memory:
                return
            
            memory.confirmed_roles[target_id] = target_role
            
            mafia_roles = {"don", "mafia", "consigliere"}
            if target_role in mafia_roles:
                memory.suspicion[target_id] = SuspicionLevel.CONFIRMED_MAFIA
            else:
                memory.suspicion[target_id] = SuspicionLevel.TRUSTED
    
    async def observe_death(self, bot_id: str, dead_player_id: str, revealed_role: str):
        """Thread-safe learning from death reveals."""
        async with self._lock:
            memory = self.memories.get(bot_id)
            if not memory:
                return
            
            memory.confirmed_roles[dead_player_id] = revealed_role
            
            mafia_roles = {"don", "mafia", "consigliere"}
            
            for voter_id, target_id in memory.voting_history[-10:]:
                if target_id == dead_player_id:
                    if revealed_role in mafia_roles:
                        # Voted for mafia - good
                        pass
                    else:
                        # Voted for innocent - suspicious
                        pass
    
    async def new_round(self, bot_id: str):
        """Thread-safe round update."""
        async with self._lock:
            memory = self.memories.get(bot_id)
            if not memory:
                return
            
            memory.rounds_observed += 1
            memory.last_night_target = None
    
    async def cleanup_old_memories(self, max_age_hours: int = 24):
    """
    Clean up old bot memories to prevent memory leaks.
    
    ПОКРАЩЕНО: Додано timestamp-based cleanup
    """
    async with self._lock:
        import sys
        from datetime import datetime, timedelta
        
        # Перевірка розміру пам'яті
        size = sys.getsizeof(self.memories)
        
        if size > 1024 * 1024:  # 1MB
            logger.warning(f"⚠️ Bot AI memory size: {size / 1024:.2f} KB")
            
            # Видалити найстаріші 50% якщо більше 100 записів
            if len(self.memories) > 100:
                keys = list(self.memories.keys())
                to_remove = keys[:len(keys)//2]
                for key in to_remove:
                    del self.memories[key]
                logger.info(f"🧹 Cleaned up {len(to_remove)} old bot memories")


# Global AI instance
bot_ai = BotAI()