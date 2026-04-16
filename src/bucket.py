from src.rules import Rule
from dataclasses import dataclass, field

@dataclass
class Bucket:
    name: str
    description: str
    rules: list[Rule] = field(default_factory=list)
    priority: int = -1  # Optional priority for ordering buckets, -1 means no priority

    def display_data(self) -> None:
        print(f"\nDisplaying data for bucket '{self.name}' ==============")
        print(f"\tName: {self.name}" \
                f"\n\tDescription: {self.description}" \
                f"\n\tPriority: {self.priority}")

        if not self.rules:
            print("\tRules: None")
            return

        print("\tRules:")
        for rule in self.rules:
            rule.display_data()