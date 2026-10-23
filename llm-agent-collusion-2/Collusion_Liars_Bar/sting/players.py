"""Players for the study.

TrackedPlayer: the harness's Player (src/agents/player.py) unchanged in prompts, parsing,
retries and fallbacks, plus (1) an optional suffix to the shared rules text (integrity
notice, fairness reminder, planted persona), (2) per-decision call tracking so the game can
log attempts, raw replies and fallbacks, (3) a true shots-fired counter, and (4) a
single-target reflection step so reflections can run in parallel with identical semantics.

StingPlayer: the scripted confederate S. Its card plays and challenge decisions come from
seeded streams (identical across arms for a given seed); only its visible "behavior" text
is written by an LLM -- the same model as the rest of the table -- so it reads like the
other players.
"""
from __future__ import annotations

import json
import re
from typing import Dict, List, Optional, Tuple

from src.agents.player import Player, RULE_BASE_PATH, REFLECT_PROMPT_TEMPLATE_PATH

from . import texts
from .config import StingPolicy, MAX_TOKENS_BEHAVIOR


def _fresh_secret_channel_memory() -> dict:
    return {"enabled": False, "partner_name": None, "communication_history": [],
            "game_history": [], "alliance_established_game": None}


class TrackedPlayer(Player):
    def __init__(self, name: str, model_key: str, role: str, client, rules_suffix: str = ""):
        # Same attributes as Player.__init__, without constructing the harness's LLMClient
        # (the study injects its recording client). Bullet position is set by the game from
        # a seeded stream.
        self.name = name
        self.hand: List[str] = []
        self.alive = True
        self.bullet_position = 0
        self.current_bullet_position = 1
        self.opinions: Dict[str, str] = {}
        self.series_memory = ""
        self.secret_channel_memory = _fresh_secret_channel_memory()
        self.llm_client = client
        self.model_name = model_key
        # study additions
        self.role = role
        self.rules_suffix = rules_suffix
        self.shots_fired = 0
        self.last_decision: dict = {}

    # The harness reads the rules file inside every prompt builder; append the suffix here.
    def _read_file(self, filepath: str) -> str:
        content = super()._read_file(filepath)
        if filepath == RULE_BASE_PATH and self.rules_suffix:
            content = content + "\n\n" + self.rules_suffix
        return content

    def rules_text(self) -> str:
        return self._read_file(RULE_BASE_PATH)

    def choose_cards_to_play(self, round_base_info, round_action_info, play_decision_info):
        with self.llm_client.track("play", player=self.name, role=self.role) as tr:
            result, reasoning = super().choose_cards_to_play(round_base_info, round_action_info, play_decision_info)
        s = tr.summary()
        self.last_decision = {"tracker": s, "attempts": s["n_calls"],
                              "fallback": str(result.get("play_reason", "")).startswith("fallback:")}
        return result, reasoning

    def decide_challenge(self, round_base_info, round_action_info, challenge_decision_info,
                         challenging_player_performance, extra_hint):
        with self.llm_client.track("challenge", player=self.name, role=self.role) as tr:
            result, reasoning = super().decide_challenge(round_base_info, round_action_info, challenge_decision_info,
                                                         challenging_player_performance, extra_hint)
        s = tr.summary()
        self.last_decision = {"tracker": s, "attempts": s["n_calls"],
                              "fallback": str(result.get("challenge_reason", "")).startswith("fallback:")}
        return result, reasoning

    def reflect_one(self, player_name: str, round_base_info: str, round_action_info: str, round_result: str) -> None:
        """One iteration of Player.reflect's loop body (same template, memory and update rule)."""
        template = self._read_file(REFLECT_PROMPT_TEMPLATE_PATH)
        rules = self._read_file(RULE_BASE_PATH)
        previous_opinion = self.opinions.get(player_name, "Doesn't know well about this player yet")
        memory_section = ""
        if self.series_memory:
            memory_section = f"\n\n=== CROSS-GAME MEMORY ===\n{self.series_memory}\n=== END MEMORY ===\n"
        prompt = template.format(rules=rules, self_name=self.name, round_base_info=round_base_info,
                                 round_action_info=round_action_info, round_result=round_result,
                                 player=player_name, previous_opinion=previous_opinion) + memory_section
        try:
            with self.llm_client.track("reflect", player=self.name, role=self.role, about=player_name):
                content, _ = self.llm_client.chat([{"role": "user", "content": prompt}], model=self.model_name)
            self.opinions[player_name] = content.strip()
        except Exception as e:  # mirrors the harness: keep the previous opinion
            print(f"Error while reflecting {player_name} : {str(e)}")

    def reflect(self, alive_players, round_base_info, round_action_info, round_result) -> None:
        for player_name in alive_players:
            if player_name != self.name:
                self.reflect_one(player_name, round_base_info, round_action_info, round_result)

    def process_penalty(self) -> bool:
        alive = super().process_penalty()
        self.shots_fired += 1
        return alive


class StingPlayer(TrackedPlayer):
    """Scripted confederate. Never calls the harness's decision methods."""

    def __init__(self, name: str, model_key: str, client, policy: StingPolicy, rules_suffix: str = ""):
        super().__init__(name, model_key, "S", client, rules_suffix=rules_suffix)
        self.policy = policy

    def choose_cards_to_play(self, *a, **k):          # pragma: no cover - guarded by StingGame
        raise RuntimeError("StingPlayer decisions are scripted; StingGame must call scripted_play()")

    def decide_challenge(self, *a, **k):              # pragma: no cover
        raise RuntimeError("StingPlayer decisions are scripted; StingGame must call scripted_challenge()")

    def reflect(self, *a, **k) -> None:
        return None                                    # S's opinions are never shown to anyone

    def reflect_one(self, *a, **k) -> None:
        return None

    def n_cards(self, rng) -> int:
        r, acc = rng.random(), 0.0
        for n, p in sorted(self.policy.cards_per_play.items()):
            acc += p
            if r <= acc:
                return max(1, min(n, len(self.hand)))
        return max(1, min(max(self.policy.cards_per_play), len(self.hand)))

    def scripted_play(self, *, target: str, round_base_info: str, round_action_info: str,
                      play_decision_info: str, rng) -> Tuple[dict, dict]:
        n = self.n_cards(rng)
        hand_before = list(self.hand)
        cards = self.hand[:n]                          # hand order was shuffled by the seeded deal
        self.hand = self.hand[n:]
        behavior, voice = self._voice(target=target, cards=cards, hand=hand_before,
                                      round_base_info=round_base_info, round_action_info=round_action_info,
                                      play_decision_info=play_decision_info, rng=rng)
        result = {"played_cards": cards, "behavior": behavior, "play_reason": "[sting: scripted play]"}
        return result, {"attempts": voice["n_calls"], "fallback": False, "voice_fallback": voice["fallback"],
                        "tracker": voice}

    def scripted_challenge(self, p: float, rng) -> bool:
        return rng.random() < p

    def _voice(self, *, target, cards, hand, round_base_info, round_action_info, play_decision_info, rng):
        prompt = texts.STING_BEHAVIOR_PROMPT.format(
            rules=self.rules_text(), sting=self.name, round_base_info=round_base_info,
            round_action_info=round_action_info, play_decision_info=play_decision_info,
            hand=", ".join(hand), n=len(cards), cards=", ".join(cards), target=target)
        raw_responses = []
        for _ in range(2):
            with self.llm_client.track("sting_behavior", player=self.name, role="S"):
                content, _ = self.llm_client.chat([{"role": "user", "content": prompt}], model=self.model_name,
                                                  max_new_tokens=MAX_TOKENS_BEHAVIOR)
            raw_responses.append(content)
            text = _extract_behavior(content)
            if text:
                return text, {"n_calls": len(raw_responses), "fallback": False, "raw_responses": raw_responses,
                              "first_prompt": prompt}
        fallback = texts.STING_BEHAVIOR_FALLBACKS[rng.randrange(len(texts.STING_BEHAVIOR_FALLBACKS))]
        return fallback, {"n_calls": len(raw_responses), "fallback": True, "raw_responses": raw_responses,
                          "first_prompt": prompt}


def _extract_behavior(content: str) -> Optional[str]:
    try:
        m = re.search(r"({[\s\S]*})", content or "")
        if m:
            value = json.loads(m.group(1)).get("behavior")
            if isinstance(value, str) and value.strip():
                return " ".join(value.split())[:300]
    except Exception:
        pass
    return None
