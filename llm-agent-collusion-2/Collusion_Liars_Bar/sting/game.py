"""StingGame: the harness's base Liar's Bar game (src/game/game.py) with the study's controls.

Rules, prompts, turn order and scoring are the harness's. Differences (all logged in
DEVIATIONS.md):
  1. Seating is set by the sequence (arrangement A or B) instead of config order; the first
     player of each game, the target card, the deal, bullet positions and round restarts come
     from seeded streams (common random numbers across arms) instead of global `random`.
  2. The scripted sting confederate's plays and challenges are scripted (StingPlayer).
  3. Every play and challenge decision is logged with the ACTUAL challenger (the next living
     player who still has cards, which is not always the next seat), the claimant, cards,
     bluff truth, attempts, raw replies and whether the harness fell back to a default.
  4. Bug fixes in the study game only: (a) the second-last-survivor bonus (+2) went to the
     third-last player because survivors were counted after the elimination; (b) the decision
     prompts showed "You have fired N shot(s)" with N = pulls + 1 (the chamber counter starts
     at 1); the study shows true shots fired. The base game has no double reset (that bug is in
     the secret-tool variants and is fixed there separately).
  5. Reflections run in parallel (each reflection is an independent call on the same inputs as
     the harness's sequential loop); the scripted sting does not reflect.
  6. A safety cap on rounds per game (flagged, never silent).
"""
from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional

from src.game.game import Game
from src.game.game_record import GameRecord, PlayerInitialState

from .config import ROLES, StingPolicy
from .parsing import is_bluff
from .rng import stream
from .texts import MEMORY_WRAP


class StudyGameRecord(GameRecord):
    """GameRecord that saves into the sequence directory (no shared default folder)."""

    def __init__(self, save_dir: Path, game_id: str):  # noqa: D401 - mirrors GameRecord fields
        self.game_id = game_id
        self.player_names: List[str] = []
        self.rounds = []
        self.winner = None
        self.final_scores: Dict[str, int] = {}
        self.communication_enabled = False
        self.communication_history = []
        self.communication_rounds = 1
        self.secret_channel_config = {}
        self.secret_channel_events = []
        self.secret_channel_communications = []
        self.save_directory = str(save_dir)
        os.makedirs(self.save_directory, exist_ok=True)


def split_memory(prompt: str) -> (str, str):
    """Split a harness decision prompt into (base, memory_section)."""
    marker = "\n\n=== CROSS-GAME MEMORY ===\n"
    i = prompt.find(marker)
    return (prompt, "") if i < 0 else (prompt[:i], prompt[i:])


class StingGame(Game):
    def __init__(self, seat_players: List, *, seed: int, game_no: int, period: str, arrangement: str,
                 policy: StingPolicy, logger, records_dir: Path, context: dict,
                 max_rounds: int = 60, reflect_workers: int = 6, log_prompts_for=("T",)):
        # Mirrors Game.__init__ (players are built by the sequence, not from configs).
        self.players = list(seat_players)
        for p in self.players:
            p.init_opinions(self.players)
        self.scores = {p.name: 0 for p in self.players}
        self.deck: List[str] = []
        self.target_card: Optional[str] = None
        self.seed, self.game_no, self.period, self.arrangement = seed, game_no, period, arrangement
        self.current_player_idx: int = stream("first_player", seed, game_no).randrange(len(self.players))
        self.last_shooter_name: Optional[str] = None
        self.game_over = False
        self.game_record = StudyGameRecord(records_dir, f"game_{game_no:02d}")
        self.game_record.start_game([p.name for p in self.players])
        self.round_count = 0
        # study state
        self.policy = policy
        self.log = logger
        self.context = dict(context)
        self.max_rounds = max_rounds
        self.reflect_workers = reflect_workers
        self.log_prompts_for = set(log_prompts_for)
        self.by_role = {p.role: p for p in self.players}
        self.role_of = {p.name: p.role for p in self.players}
        self.sting = self.by_role["S"]
        self.turn_count = 0
        self.capped = False
        self.elimination_order: List[str] = []
        self.shots: List[dict] = []
        self._victory_logged = False

    # ------------------------------------------------------------------ randomness
    def choose_target_card(self) -> None:
        r = self.round_count + 1                       # the round about to be recorded
        self.target_card = stream("target", self.seed, self.game_no, r).choice(["Q", "K", "A"])

    def deal_cards(self) -> None:
        """Harness's standardized hand (2 target, 2 other, 1 Joker), dealt per ROLE from a seeded
        deck; dead roles' cards are still drawn so living roles get the same hands across arms."""
        r = self.round_count + 1
        rng = stream("deal", self.seed, self.game_no, r)
        if self.target_card is None:
            self.choose_target_card()
        deck = ["Q"] * 8 + ["K"] * 8 + ["A"] * 8 + ["Joker"] * 4
        rng.shuffle(deck)
        target_cards = [c for c in deck if c == self.target_card]
        other_cards = [c for c in deck if c in ("Q", "K", "A") and c != self.target_card]
        jokers = [c for c in deck if c == "Joker"]
        for p in self.players:
            if p.alive:
                p.hand.clear()
        for role in ROLES:
            hand = [target_cards.pop(), target_cards.pop(), other_cards.pop(), other_cards.pop(), jokers.pop()]
            rng.shuffle(hand)
            player = self.by_role[role]
            if player.alive:
                player.hand = hand

    def start_round_record(self) -> None:
        self.round_count += 1
        starting_player = self.players[self.current_player_idx].name
        states = [PlayerInitialState(player_name=p.name, bullet_position=p.bullet_position,
                                     current_gun_position=p.shots_fired,   # fix: true shots fired
                                     initial_hand=p.hand.copy())
                  for p in self.players if p.alive]
        opinions = {p.name: dict(p.opinions) for p in self.players}
        self.game_record.start_round(round_id=self.round_count, target_card=self.target_card,
                                     round_players=[p.name for p in self.players if p.alive],
                                     starting_player=starting_player, player_initial_states=states,
                                     player_opinions=opinions, player_scores=self.scores.copy())
        self.log.event(dict(self.context, event="round_start", game=self.game_no, round=self.round_count,
                            target_card=self.target_card, starting_player=starting_player,
                            starting_role=self.role_of[starting_player],
                            alive=[p.role for p in self.players if p.alive],
                            hands={p.role: p.hand.copy() for p in self.players if p.alive}))

    # ------------------------------------------------------------------ penalties / rounds
    def perform_penalty(self, player, was_unsuccessful_challenge: bool = False) -> None:
        n_alive_before = sum(1 for p in self.players if p.alive)
        still_alive = player.process_penalty()
        self.last_shooter_name = player.name
        if not still_alive:
            if n_alive_before == 2:                    # fix: the eliminated player is second-last
                self.scores[player.name] += 2
            self.scores[player.name] -= 2
            for p in self.players:
                if p.alive and p.name != player.name:
                    self.scores[p.name] += 1
            self.elimination_order.append(player.name)
        elif was_unsuccessful_challenge:
            self.scores[player.name] -= 1
        shot = dict(game=self.game_no, round=self.round_count, shooter=player.name,
                    shooter_role=player.role, hit=not still_alive, shots_fired=player.shots_fired,
                    unsuccessful_challenge=was_unsuccessful_challenge)
        self.shots.append(shot)
        self.log.event(dict(self.context, event="shot", **shot))
        self.game_record.update_scores(self.scores)
        self.game_record.record_shooting(shooter_name=player.name, bullet_hit=not still_alive)
        if not self.check_victory():
            self.reset_round(record_shooter=True)

    def reset_round(self, record_shooter: bool) -> None:
        alive_players = self.handle_reflection()
        self.choose_target_card()
        self.deal_cards()
        if record_shooter and self.last_shooter_name:
            shooter_idx = next((i for i, p in enumerate(self.players) if p.name == self.last_shooter_name), None)
            if shooter_idx is not None and self.players[shooter_idx].alive:
                self.current_player_idx = shooter_idx
            else:
                self.current_player_idx = self.find_next_player_with_cards(shooter_idx or 0)
        else:
            self.last_shooter_name = None
            rng = stream("restart", self.seed, self.game_no, self.round_count)
            self.current_player_idx = self.players.index(rng.choice(alive_players))
        self.start_round_record()

    def check_victory(self) -> bool:
        if self.game_over:
            return True
        alive = [p for p in self.players if p.alive]
        if len(alive) == 1:
            self.scores[alive[0].name] += 3
            self.game_record.update_scores(self.scores)
            winner = max(self.scores.items(), key=lambda x: x[1])[0]
            self.game_record.finish_game(winner, self.scores)
            self.game_over = True
            self._log_game_end(last_survivor=alive[0].name, winner=winner)
            return True
        return False

    def _log_game_end(self, last_survivor: Optional[str], winner: Optional[str]) -> None:
        if self._victory_logged:
            return
        self._victory_logged = True
        self.log.event(dict(self.context, event="game_end", game=self.game_no, rounds=self.round_count,
                            turns=self.turn_count, capped=self.capped, last_survivor=last_survivor,
                            last_survivor_role=self.role_of.get(last_survivor), winner=winner,
                            winner_role=self.role_of.get(winner), scores=dict(self.scores),
                            scores_by_role={self.role_of[n]: s for n, s in self.scores.items()},
                            elimination_order=[self.role_of[n] for n in self.elimination_order]))

    def handle_reflection(self):
        alive = [p for p in self.players if p.alive]
        names = [p.name for p in alive]
        rbi = self.game_record.get_latest_round_info()
        tasks = []
        for p in alive:
            if p is self.sting:
                continue
            rai = self.game_record.get_latest_round_actions(p.name, include_latest=True) + "\n" + f"Current scores: {self.scores}"
            rr = self.game_record.get_latest_round_result(p.name)
            for other in names:
                if other != p.name:
                    tasks.append((p, other, rbi, rai, rr))
        if self.reflect_workers and self.reflect_workers > 1 and len(tasks) > 1:
            with ThreadPoolExecutor(max_workers=self.reflect_workers) as ex:
                list(ex.map(lambda t: t[0].reflect_one(t[1], t[2], t[3], t[4]), tasks))
        else:
            for t in tasks:
                t[0].reflect_one(t[1], t[2], t[3], t[4])
        return alive

    # ------------------------------------------------------------------ turns
    def _seat_next(self, idx: int):
        return self.players[(idx + 1) % len(self.players)]

    def handle_play_cards(self, current_player, next_player) -> List[str]:
        round_base_info = self.game_record.get_latest_round_info()
        round_action_info = self.game_record.get_latest_round_actions(current_player.name, include_latest=True)
        play_decision_info = self.game_record.get_play_decision_info(current_player.name, next_player.name)
        play_decision_info += f"\nCurrent scores: {self.scores}"
        hand_before = list(current_player.hand)
        if current_player is self.sting:
            rng = stream("sting_play", self.seed, self.game_no, self.round_count, self.turn_count)
            play_result, info = self.sting.scripted_play(target=self.target_card, round_base_info=round_base_info,
                                                         round_action_info=round_action_info,
                                                         play_decision_info=play_decision_info, rng=rng)
            reasoning = ""
        else:
            play_result, reasoning = current_player.choose_cards_to_play(round_base_info, round_action_info,
                                                                         play_decision_info)
            info = current_player.last_decision
        self.game_record.record_play(player_name=current_player.name,
                                     played_cards=play_result["played_cards"].copy(),
                                     remaining_cards=current_player.hand.copy(),
                                     play_reason=play_result["play_reason"], behavior=play_result["behavior"],
                                     next_player=next_player.name, play_thinking=reasoning)
        cards = play_result["played_cards"]
        self._log_decision("play", actor=current_player, counterpart=next_player, info=info,
                           extra=dict(hand_before=hand_before, played_cards=list(cards), n_cards=len(cards),
                                      bluffed=is_bluff(cards, self.target_card),
                                      behavior=play_result["behavior"], reason=play_result["play_reason"],
                                      hand_after=list(current_player.hand)))
        return cards

    def handle_challenge(self, current_player, next_player, played_cards):
        """Harness logic and scoring, with the sting's decision scripted and every decision logged."""
        round_base_info = self.game_record.get_latest_round_info()
        round_action_info = self.game_record.get_latest_round_actions(next_player.name, include_latest=False)
        challenge_decision_info = self.game_record.get_challenge_decision_info(next_player.name, current_player.name)
        challenge_decision_info += f"\nCurrent scores: {self.scores}"
        challenging_player_behavior = self.game_record.get_latest_play_behavior()
        extra_hint = ("Attention, All other players have emptied thier hands."
                      if self.check_other_players_no_cards(next_player) else "")
        if next_player is self.sting:
            p = self._sting_challenge_prob(current_player)
            rng = stream("sting_challenge", self.seed, self.game_no, self.round_count, self.turn_count)
            decided = self.sting.scripted_challenge(p, rng)
            challenge_result = {"was_challenged": decided, "challenge_reason": "[sting: scripted challenge decision]"}
            reasoning, info = "", {"attempts": 0, "fallback": False, "p_challenge": p}
        else:
            challenge_result, reasoning = next_player.decide_challenge(round_base_info, round_action_info,
                                                                       challenge_decision_info,
                                                                       challenging_player_behavior, extra_hint)
            info = next_player.last_decision
        bluff = is_bluff(played_cards, self.target_card)
        is_valid = not bluff
        if challenge_result["was_challenged"]:
            self.game_record.record_challenge(was_challenged=True, reason=challenge_result["challenge_reason"],
                                              result=not is_valid, challenge_thinking=reasoning)
            if not is_valid:
                self.scores[next_player.name] += 2
            outcome = (next_player, is_valid) if is_valid else (current_player, False)
        else:
            self.game_record.record_challenge(was_challenged=False, reason=challenge_result["challenge_reason"],
                                              result=None, challenge_thinking=reasoning)
            if is_valid:
                self.scores[next_player.name] += 2
            if not current_player.hand:
                self.scores[current_player.name] += 2
            outcome = (None, False)
        self._log_decision("challenge", actor=next_player, counterpart=current_player, info=info,
                           extra=dict(played_cards=list(played_cards), claimed_n=len(played_cards),
                                      claim_was_bluff=bluff, challenged=bool(challenge_result["was_challenged"]),
                                      reason=challenge_result["challenge_reason"],
                                      extra_hint=bool(extra_hint)))
        return outcome

    def _sting_challenge_prob(self, claimant) -> float:
        if self.period == "pre":
            return self.policy.p_challenge_pre
        return self.policy.p_challenge_post_T if claimant.role == "T" else self.policy.p_challenge_post_other

    def handle_system_challenge(self, current_player) -> None:
        self.log.event(dict(self.context, event="system_challenge", game=self.game_no, round=self.round_count,
                            player_role=current_player.role, cards=list(current_player.hand),
                            bluff=is_bluff(current_player.hand, self.target_card)))
        super().handle_system_challenge(current_player)

    def play_round(self) -> None:
        current_player = self.players[self.current_player_idx]
        if self.check_other_players_no_cards(current_player):
            self.handle_system_challenge(current_player)
            return
        self.turn_count += 1
        next_idx = self.find_next_player_with_cards(self.current_player_idx)
        next_player = self.players[next_idx]
        self._turn_seat_next = self._seat_next(self.current_player_idx)
        played_cards = self.handle_play_cards(current_player, next_player)
        if next_player != current_player:
            player_to_penalize, was_unsuccessful_challenge = self.handle_challenge(current_player, next_player,
                                                                                   played_cards)
            if player_to_penalize is not None:
                self.perform_penalty(player_to_penalize, was_unsuccessful_challenge)
                return
        self.current_player_idx = next_idx

    def start_game(self) -> None:
        self.choose_target_card()
        self.deal_cards()
        self.start_round_record()
        while not self.game_over:
            if self.round_count > self.max_rounds:
                self.capped = True
                self.game_over = True
                winner = max(self.scores.items(), key=lambda x: x[1])[0]
                self.game_record.finish_game(winner, self.scores)
                self._log_game_end(last_survivor=None, winner=winner)
                break
            self.play_round()

    # ------------------------------------------------------------------ logging
    def _log_decision(self, dtype: str, *, actor, counterpart, info: dict, extra: dict) -> None:
        tracker = (info or {}).get("tracker") or {}
        prompt = tracker.get("first_prompt", "") or ""
        base, memory = split_memory(prompt)
        seat_next = getattr(self, "_turn_seat_next", None)
        rec = dict(self.context)
        rec.update(
            decision_type=dtype, game=self.game_no, period=self.period, arrangement=self.arrangement,
            round=self.round_count, turn=self.turn_count, target_card=self.target_card,
            actor=actor.name, actor_role=actor.role, counterpart=counterpart.name, counterpart_role=counterpart.role,
            seat_next_role=(seat_next.role if (seat_next is not None and dtype == "play") else None),
            challenger_skipped_seat=(bool(seat_next is not None and dtype == "play" and seat_next is not counterpart)),
            alive=[p.role for p in self.players if p.alive],
            cards_left={p.role: len(p.hand) for p in self.players if p.alive},
            shots_fired={p.role: p.shots_fired for p in self.players},
            scores_by_role={p.role: self.scores[p.name] for p in self.players},
            attempts=(info or {}).get("attempts"), fallback=bool((info or {}).get("fallback")),
            voice_fallback=(info or {}).get("voice_fallback"), p_challenge=(info or {}).get("p_challenge"),
            empty_responses=tracker.get("empty_responses"), errors=tracker.get("errors"),
            raw_responses=tracker.get("raw_responses"),
            has_memory=bool(memory), memory_hash=hashlib.sha1(memory.encode()).hexdigest()[:10] if memory else None,
            prompt_hash=hashlib.sha1(base.encode()).hexdigest()[:12] if base else None,
        )
        if actor.role in self.log_prompts_for and base:
            rec["prompt_base"] = base
        rec.update(extra)
        self.log.decision(rec)
