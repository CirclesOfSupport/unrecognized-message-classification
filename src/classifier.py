import re

from src.models import ClassificationResult
from src.normalize import NormalizedText
from src.bucket import Bucket
from src.rules import KeywordRule, RegexRule


class KeywordClassifier:
    layer_name = "keyword"

    def classify(self, text: NormalizedText, bucket: Bucket) -> ClassificationResult:
        matched_rules = []

        for rule in bucket.rules:
            if not isinstance(rule, KeywordRule):
                continue

            input_text = self._get_text_for_rule(text, rule)
            tokens = input_text.split()

            matched_keywords = self._find_matches(input_text, tokens, rule)
            if matched_keywords:
                matched_rules.append({
                    "rule_name": rule.name,
                    "description": rule.description,
                    "match_mode": rule.match_mode,
                    "matched_keywords": matched_keywords,
                })

        if not matched_rules:
            return self._no_match(bucket.name)

        return ClassificationResult(
            bucket=bucket.name,
            matched=True,
            source_layer=self.layer_name,
            rule_name=matched_rules[0]["rule_name"],
            confidence=1.0,
            details={
                "bucket_description": bucket.description,
                "matched_rules": matched_rules,
            },
        )

    def _find_matches(self, input_text: str, tokens: list[str], rule: KeywordRule) -> list[dict]:
        matched_keywords = []

        for keyword in rule.keywords:
            pattern = keyword.strip().casefold()
            if not pattern:
                continue

            if rule.match_mode == "phrase":
                if pattern in input_text:
                    matched_keywords.append({
                        "keyword_pattern": pattern,
                        "matched_value": pattern,
                        "match_type": "phrase",
                    })

            elif rule.match_mode == "token":
                for token in tokens:
                    match_type = self._token_match_type(token, pattern)
                    if match_type:
                        matched_keywords.append({
                            "keyword_pattern": pattern,
                            "matched_value": token,
                            "match_type": match_type,
                        })
                        break

            elif rule.match_mode == "exact":
                if input_text == pattern:
                    matched_keywords.append({
                        "keyword_pattern": pattern,
                        "matched_value": input_text,
                        "match_type": "exact",
                    })

            else:
                raise ValueError(f"Unsupported match_mode: {rule.match_mode}")

        return matched_keywords

    def _token_match_type(self, token: str, pattern: str) -> str | None:
        has_leading = pattern.startswith("*")
        has_trailing = pattern.endswith("*")

        if has_leading and has_trailing and len(pattern) > 2:
            return "contains" if pattern[1:-1] in token else None
        if has_leading and len(pattern) > 1:
            return "suffix" if token.endswith(pattern[1:]) else None
        if has_trailing and len(pattern) > 1:
            return "prefix" if token.startswith(pattern[:-1]) else None
        return "exact" if token == pattern else None

    def _no_match(self, bucket_name: str, details: dict | None = None) -> ClassificationResult:
        return ClassificationResult(
            bucket=bucket_name,
            matched=False,
            source_layer=self.layer_name,
            details=details or {},
        )

    def _get_text_for_rule(self, text: NormalizedText, rule: KeywordRule) -> str:
        text_input_type = getattr(rule, "text_input_type", "normalized_text")

        if text_input_type == "raw_text":
            return text.raw_text.casefold()
        if text_input_type == "emoji_normalized_text":
            return text.emoji_normalized_text.casefold()
        return text.normalized_text.casefold()


class RegexClassifier:
    layer_name = "regex"

    def classify(self, text: NormalizedText, bucket: Bucket) -> ClassificationResult:
        include_matches = []
        exclude_matches = []

        for rule in bucket.rules:
            if not isinstance(rule, RegexRule) or not rule.pattern:
                continue

            input_text = self._get_text_for_rule(text, rule)
            match = re.search(rule.pattern, input_text)

            if not match:
                continue

            match_info = {
                "rule_name": rule.name,
                "description": rule.description,
                "match_mode": rule.match_mode,
                "pattern": rule.pattern,
                "matched_value": match.group(0),
                "span": [match.start(), match.end()],
            }

            mode = getattr(rule, "match_mode", "include")
            if rule.match_mode == "exclude":
                exclude_matches.append(match_info)
            elif rule.match_mode == "include":
                include_matches.append(match_info)
            else:
                raise ValueError(f"Unsupported regex match_mode: {rule.match_mode}")

        # An exclude match means this bucket is disqualified — stop here.
        if exclude_matches:
            return self._no_match(
                bucket.name,
                details={
                    "bucket_description": bucket.description,
                    "excluded": True,
                    "exclude_matches": exclude_matches,
                    "include_matches": include_matches,
                },
            )

        if not include_matches:
            return self._no_match(bucket.name)

        return ClassificationResult(
            bucket=bucket.name,
            matched=True,
            source_layer=self.layer_name,
            rule_name=include_matches[0]["rule_name"],
            confidence=1.0,
            details={
                "bucket_description": bucket.description,
                "matched_rules": include_matches,
            },
        )
    
    def _get_text_for_rule(self, text: NormalizedText, rule: RegexRule) -> str:
        if rule.text_input_type == "raw_text":
            return text.raw_text
        if rule.text_input_type == "emoji_normalized_text":
            return text.emoji_normalized_text
        return text.normalized_text

    def _no_match(self, bucket_name: str, details: dict | None = None) -> ClassificationResult:
        return ClassificationResult(
            bucket=bucket_name,
            matched=False,
            source_layer=self.layer_name,
            details=details or {},
        )