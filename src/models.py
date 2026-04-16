from dataclasses import dataclass, field
from typing import Any

@dataclass
class ClassificationResult:
    bucket: str
    matched: bool
    source_layer: str
    rule_name: str | None = None
    confidence: float | None = None
    details: dict[str, Any] = field(default_factory=dict)