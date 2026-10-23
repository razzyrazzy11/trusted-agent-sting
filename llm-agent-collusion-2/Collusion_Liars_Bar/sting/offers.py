"""Offer delivery and the consent step.

The harness never asks the chosen partner to consent in live games (the invitation is built but
not sent). Here every offer is delivered to the target as a private message and the target's
reply is recorded verbatim, parsed strictly, and written into its private record whatever it
says (the agent remembers its own reply). Stage A uses exactly the same builders.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import texts
from .config import MAX_TOKENS_OFFER_REPLY, MAX_TOKENS_ZENG_A0Z
from .parsing import extract_partner, parse_accept_strict, parse_accept_zeng

BASE_RULES_PATH = texts.PROMPTS / "rule_vanilla.txt"


def base_rules() -> str:
    """The harness rules text exactly as Player._read_file returns it (stripped)."""
    return BASE_RULES_PATH.read_text(encoding="utf-8").strip()


def rules_with(suffix_keys) -> str:
    sfx = texts.rules_suffix(suffix_keys)
    return base_rules() + ("\n\n" + sfx if sfx else "")


def consent_messages(kind: str, *, target: str, sting: str, players: List[str], n_games: int, game: int,
                     suffix_keys=()) -> List[Dict[str, str]]:
    rules = rules_with(suffix_keys)
    if kind in texts.STING_OFFERS:
        content = texts.CONSENT_PROMPT.format(
            rules=rules, target=target, n_games=n_games, players=", ".join(players), game=game, sting=sting,
            offer_text=texts.STING_OFFERS[kind].format(target=target, sting=sting),
            reply_instruction=texts.STING_REPLY_INSTRUCTION.format(sting=sting))
    elif kind == "designer_direct":
        content = texts.DESIGNER_CONSENT_PROMPT.format(
            rules=rules, target=target, n_games=n_games, players=", ".join(players), game=game,
            designer_text=texts.DESIGNER_DIRECT.format(sting=sting),
            reply_instruction=texts.DESIGNER_REPLY_INSTRUCTION)
    elif kind == "designer_hint":
        content = texts.DESIGNER_CONSENT_PROMPT.format(
            rules=rules, target=target, n_games=n_games, players=", ".join(players), game=game,
            designer_text=texts.designer_hint_offer(sting), reply_instruction="").rstrip()
    else:
        raise ValueError(kind)
    return [{"role": "user", "content": content}]


def zeng_a0z_messages(*, target: str, players: List[str], suffix_keys=()) -> List[Dict[str, str]]:
    """Zeng & Rudzicz's acceptance-test structure (system rules, user context, user offer)."""
    lines = "\n".join(f"        - {p}" for p in players)
    return [
        {"role": "system", "content": rules_with(suffix_keys)},
        {"role": "user", "content": texts.ZENG_A0Z_CONTEXT.format(target=target, player_lines=lines)},
        {"role": "user", "content": texts.zeng_hint_offer_text()},
    ]


def offer_text_for_record(kind: str, *, target: str, sting: str) -> str:
    if kind in texts.STING_OFFERS:
        return texts.STING_OFFERS[kind].format(target=target, sting=sting)
    if kind == "designer_direct":
        return texts.DESIGNER_DIRECT.format(sting=sting)
    if kind == "designer_hint":
        return "designer hint tool paired with " + sting
    return ""


def run_offer(client, kind: str, *, target: str, sting: str, players: List[str], n_games: int, game: int,
              suffix_keys=(), meta: Optional[dict] = None) -> dict:
    """Deliver one offer to `target` through `client` and parse the reply."""
    if kind == "zeng_v0":
        messages = zeng_a0z_messages(target=target, players=players, suffix_keys=suffix_keys)
        max_tokens = MAX_TOKENS_ZENG_A0Z
    else:
        messages = consent_messages(kind, target=target, sting=sting, players=players, n_games=n_games,
                                    game=game, suffix_keys=suffix_keys)
        max_tokens = MAX_TOKENS_OFFER_REPLY
    with client.track("consent", kind=kind, target=target, **(meta or {})):
        reply, _ = client.chat(messages, model=client.model_key, max_new_tokens=max_tokens)
    strict = parse_accept_strict(reply)
    others = [p for p in players if p != target]
    return dict(kind=kind, target=target, sting=sting, suffix=list(suffix_keys), reply=reply,
                decision_strict=strict, decision_zeng=parse_accept_zeng(reply), accepted=(strict == "ACCEPT"),
                partner=extract_partner(reply, others) if kind == "zeng_v0" else sting,
                prompt=messages[-1]["content"], n_messages=len(messages))


def record_for_offer(offer: dict) -> str:
    """The private record the target carries after the consent step (any reply)."""
    kind = offer["kind"]
    if kind == "designer_hint":
        return texts.record_text("designer_hint", sting=offer["sting"], reply=offer["reply"],
                                 accepted=offer["accepted"])
    return texts.record_text(kind, sting=offer["sting"], target=offer["target"], reply=offer["reply"])
