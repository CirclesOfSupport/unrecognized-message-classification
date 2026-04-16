import emoji
import re
from dataclasses import dataclass


@dataclass
class NormalizedText:
    raw_text: str
    normalized_text: str
    emoji_normalized_text: str
    emoji_placeholder: str = "__EMOJI__"

    def __init__(self, raw_text: str):
        self.raw_text = raw_text if isinstance(raw_text, str) else ""
        self.normalized_text = self._normalize_text(raw_text)
        self.emoji_normalized_text = self._normalize_with_emoji(self.raw_text)

    def _normalize_text(self, text: str) -> str:
        if not isinstance(text, str):
            return ""

        normalized = text.casefold().strip()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized)

        return normalized.strip()

    def _normalize_with_emoji(self, text: str) -> str:
        if not isinstance(text, str):
            return ""

        # Replace emojis with placeholder
        text = emoji.replace_emoji(text, replace=f" {self.emoji_placeholder} ")
        text = re.sub(r"�+", f" {self.emoji_placeholder} ", text)
        text = text.casefold().strip()

        # preserve underscores so __EMOJI__ survives
        text = re.sub(r"[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text)
        text = text.replace(self.emoji_placeholder.lower(), self.emoji_placeholder)
        text = re.sub(rf"({re.escape(self.emoji_placeholder)}\s*)+", self.emoji_placeholder + " ", text)

        return text.strip()