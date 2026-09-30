"""Restore exact known Kavach placeholders in a pasted response."""

import re
from dataclasses import dataclass

_TOKEN_LIKE = re.compile(
    r"\[\[KAVACH:(?:(?!\[\[KAVACH:)[^\r\n])*?(?:\]\]|(?=\[\[KAVACH:)|$)"
)


@dataclass(frozen=True)
class RestorationResult:
    restored_text: str
    restored_count: int
    unresolved_tokens: list[str]


def restore_tokens(text: str, token_map: dict[str, str]) -> RestorationResult:
    restored_count = 0
    unresolved: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        nonlocal restored_count
        token = match.group(0)
        original = token_map.get(token)
        if original is None:
            unresolved.add(token)
            return token
        restored_count += 1
        return original

    restored_text = _TOKEN_LIKE.sub(replace, text)
    return RestorationResult(
        restored_text=restored_text,
        restored_count=restored_count,
        unresolved_tokens=sorted(unresolved),
    )
