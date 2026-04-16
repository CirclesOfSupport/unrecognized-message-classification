from pathlib import Path
import logging
import yaml

from src.bucket import Bucket
from src.rules import Rule, KeywordRule, RegexRule


def load_yaml_file(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def rule_loader(bucket_data: dict) -> list[Rule]:
    rules: list[Rule] = []

    loaders = [
        ("keyword_rules", KeywordRule),
        ("regex_rules",   RegexRule),
    ]

    for key, cls in loaders:
        for rule_data in bucket_data.get(key, []):
            try:
                rules.append(cls.from_dict(rule_data))
            except Exception as e:
                logging.error(f"Error loading {key} rule '{rule_data.get('name', 'unknown')}': {e}")

    return rules


def bucket_loader(config_dir: str | Path) -> list[Bucket]:
    config_path = Path(config_dir)
    buckets: list[Bucket] = []

    for yaml_file in sorted(config_path.glob("*.y*ml")):
        try:
            data = load_yaml_file(yaml_file)
            name = data.get("bucket") or data.get("name")

            if not name:
                logging.warning(f"Skipping {yaml_file} — missing 'bucket' or 'name' field.")
                continue

            logging.info(f"Loading bucket '{name}' from {yaml_file}")
            buckets.append(Bucket(
                name=name,
                description=data.get("description", ""),
                rules=rule_loader(data),
                priority=data.get("priority", -1),
            ))

        except Exception as e:
            logging.error(f"Error loading bucket from {yaml_file}: {e}")

    # Sort: explicit priorities first (lowest number = highest priority), then -1 (no priority) last
    return sorted(buckets, key=lambda b: b.priority if b.priority != -1 else float("inf"))