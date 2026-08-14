from __future__ import annotations

import json
from pathlib import Path


class Localization:
    """Loads user-editable UI translations from languages.json."""

    def __init__(self, default_language: str = "en") -> None:
        self.path = Path(__file__).resolve().with_name("languages.json")
        with self.path.open("r", encoding="utf-8") as language_file:
            self.languages: dict[str, dict[str, str]] = json.load(language_file)
        if not self.languages:
            raise ValueError("languages.json must contain at least one language")
        self.current = (
            default_language if default_language in self.languages else next(iter(self.languages))
        )

    def text(self, key: str) -> str:
        current_text = self.languages[self.current]
        if key in current_text:
            return current_text[key]
        return self.languages[next(iter(self.languages))].get(key, key)

    def choices(self) -> list[str]:
        return [values.get("language_name", code) for code, values in self.languages.items()]

    def select_by_name(self, language_name: str) -> None:
        for code, values in self.languages.items():
            if values.get("language_name", code) == language_name:
                self.current = code
                return
