from dataclasses import dataclass, field


@dataclass
class Rule:
    name: str
    description: str
    rule_type: str  # "keyword" | "regex"

    def display_data(self) -> None:
        print(f"\t[{self.rule_type}] '{self.name}': {self.description}")


@dataclass
class KeywordRule(Rule):
    keywords: list[str]
    match_mode: str  # "phrase" | "token" | "exact"
    text_input_type: str = "normalized_text"  # "normalized" | "emoji_normalized"

    @classmethod
    def from_dict(cls, data: dict) -> "KeywordRule":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            rule_type="keyword",
            keywords=data.get("keywords", []),
            match_mode=data.get("match_mode", "token"),
            text_input_type=data.get("text_input_type", "normalized_text"),
        )


@dataclass
class RegexRule(Rule):
    pattern: str
    match_mode: str  # "include" | "exclude"
    text_input_type: str = "normalized_text"  # "normalized" | "emoji_normalized"

    @classmethod
    def from_dict(cls, data: dict) -> "RegexRule":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            rule_type="regex",
            pattern=data.get("pattern", ""),
            match_mode=data.get("match_mode", "include"),
            text_input_type=data.get("text_input_type", "normalized_text"),
        )