"""
evaluate.py — Batch classifier evaluation against a labeled CSV.

Usage:
    python evaluate.py \
        --input data/alc_data.csv \
        --output results/evaluation.csv \
        --config config/ \
        [--old-rules data/old_rules.csv] \
        [--message-col input] \
        [--label-col triage_determination]

Input CSV must have at minimum:
    - A message column (default: "input")
    - A label column   (default: "triage_determination")

Old rules file (optional) — CSV format with columns: rule,bucket
    Each row has a regex pattern and the bucket name it maps to.
    The first matching rule (in order) wins. Unmatched rows → "other".
    The input text is lowercased before matching against old rules.

Output CSV columns:
    input | triage_determination | new_classification | old_classification

Number of times when new script classifies a response as ("definitely triage" or "other) when old script classified the response as "do not triage"
Number of times when new script classifies a response as "do not triage" when (old script classified the response as as ["definitely triage" or "other] AND counselor marked response as != "Not relevant") (Low, moderate, High)
"""

import argparse
import csv
import logging
import re
import sys
from pathlib import Path

from src.normalize import NormalizedText
from src.classifier import KeywordClassifier, RegexClassifier
from src.utils import bucket_loader

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

TRIAGE_CATEGORIES = ["definitely_triage", "other"]
TRIAGE_DETERMINATIONS = ["moderateconcern", "highconcern"]

# TP = TRIAGE_CATEGORY and LOW, MODERATE, HIGH
# TN = NOT A TRIAGE_CATEGORY and NOTRELEVANT
# FN = NOT A TRIAGE_CATEGORY and LOW, MODERATE, HIGH
# FP = TRIAGE_CATEGORIES and NOTRELEVANT


# ──────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ──────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch evaluate classifier against labeled CSV.")
    p.add_argument("--input",       "-i", required=True,  help="Path to input CSV file.")
    p.add_argument("--output",      "-o", required=True,  help="Path for output CSV file.")
    p.add_argument("--config",      "-c", default="config", help="Path to bucket config dir (default: config/).")
    p.add_argument("--old-rules",         default=None,   help="Path to old regex rules CSV (optional).")
    p.add_argument("--old-triage-keywords", default=None,  help="Path to old triage keywords txt file (optional, used with --old-rules).")
    p.add_argument("--message-col",       default="input",                help="CSV column name for message text.")
    p.add_argument("--label-col",         default="triage_determination", help="CSV column name for ground-truth label.")
    return p.parse_args()


# ──────────────────────────────────────────────────────────────────────────────
# New classifier (wraps your existing src/ stack)
# ──────────────────────────────────────────────────────────────────────────────

def load_new_classifier(config_dir: str):
    """
    Import your existing classifier stack and return a callable:
        classify(raw_text: str) -> str   (bucket name or "other")
    """
    buckets = bucket_loader(Path(config_dir))
    if not buckets:
        log.warning("No buckets loaded from '%s' — all rows will be classified as 'other'.", config_dir)

    classifiers = [KeywordClassifier(), RegexClassifier()]

    def classify(raw_text: str) -> str:
        normalized = NormalizedText(raw_text)
        for bucket in buckets:
            for clf in classifiers:
                result = clf.classify(normalized, bucket)
                if result.matched:
                    return bucket.name
        return "other"

    return classify


# ──────────────────────────────────────────────────────────────────────────────
# Old regex classifier
# ──────────────────────────────────────────────────────────────────────────────

def _load_triage_keywords(keywords_path: str) -> list[str]:
    """Load triage keywords from a text file (one keyword per line)."""
    path = Path(keywords_path)
    if not path.exists():
        log.error("Triage keywords file not found: %s", path)
        sys.exit(1)

    keywords = [
        line.strip().lower()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    log.info("Old triage keywords: loaded %d keywords from %s.", len(keywords), keywords_path)
    return keywords


def load_old_classifier(rules_path: str, triage_keywords_path: str | None = None):
    """
    Load old regex rules from a CSV file and return a callable:
        classify(raw_text: str) -> str   (bucket name or "other")

    Expected CSV format (columns: rule, bucket):
        rule,bucket
        "\\bbye\\b",end_conversation
        "\\bok\\b",okay

    The input text is lowercased before matching.
    If triage_keywords_path is provided, any message containing one of those
    keywords is classified as "definitely_triage" before regex rules are checked.
    """
    path = Path(rules_path)
    if not path.exists():
        log.error("Old rules file not found: %s", path)
        sys.exit(1)

    triage_keywords: list[str] = []
    if triage_keywords_path:
        triage_keywords = _load_triage_keywords(triage_keywords_path)

    compiled: list[tuple[re.Pattern, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pattern_str = row.get("rule", "").strip()
            bucket_name = row.get("bucket", "").strip()
            if not pattern_str or not bucket_name:
                continue
            try:
                compiled.append((re.compile(pattern_str, re.UNICODE), bucket_name))
            except re.error as e:
                log.warning("Skipping invalid regex in old rules: %s — %s", pattern_str, e)

    log.info("Old rules: loaded %d patterns from %s.", len(compiled), rules_path)

    def classify(raw_text: str) -> str:
        lowered = raw_text.lower()
        for kw in triage_keywords:
            if kw in lowered:
                return "definitely_triage"
        for pattern, bucket_name in compiled:
            if pattern.search(lowered):
                return bucket_name
        return "other"

    return classify


# ──────────────────────────────────────────────────────────────────────────────
# CSV processing
# ──────────────────────────────────────────────────────────────────────────────

def run_evaluation(
    input_path: str,
    output_path: str,
    message_col: str,
    label_col: str,
    new_classify,
    old_classify,
) -> None:
    input_file  = Path(input_path)
    output_file = Path(output_path)

    if not input_file.exists():
        log.error("Input file not found: %s", input_file)
        sys.exit(1)

    output_file.parent.mkdir(parents=True, exist_ok=True)

    out_cols = ["input", "triage_determination", "new_classification", "old_classification"]

    total = matched_new = matched_old = agreement = 0
    not_relevant_total = not_relevant_other_new = not_relevant_other_old = 0
    relevant_total = relevant_new = relevant_old = 0

    # (new, old)
    true_positives = [0, 0]
    true_negatives = [0, 0]
    false_positives = [0, 0]
    false_negatives = [0, 0]

    new_triage_old_notriage = 0
    new_notriage_old_triage = 0
    new_notriage_old_triage_nr = 0

    with (
        input_file.open("r", encoding="utf-8", newline="") as infile,
        output_file.open("w", encoding="utf-8", newline="") as outfile,
    ):
        reader = csv.DictReader(infile)

        if message_col not in (reader.fieldnames or []):
            log.error(
                "Message column '%s' not found in CSV. Available columns: %s",
                message_col, reader.fieldnames,
            )
            sys.exit(1)

        if label_col not in (reader.fieldnames or []):
            log.warning(
                "Label column '%s' not found in CSV — triage_determination will be empty.", label_col
            )

        writer = csv.DictWriter(outfile, fieldnames=out_cols, extrasaction="ignore")
        writer.writeheader()

        for i, row in enumerate(reader, start=1):
            raw_text = row.get(message_col, "").strip()
            label    = row.get(label_col, "").strip()

            if raw_text == "":
                continue

            new_result = new_classify(raw_text)
            old_result = old_classify(raw_text) if old_classify else "n/a"

            writer.writerow({
                "input":               raw_text,
                "triage_determination": label,
                "new_classification":  new_result,
                "old_classification":  old_result,
            })

            total += 1

            if label.lower() in TRIAGE_DETERMINATIONS:
                if new_result in TRIAGE_CATEGORIES:
                    true_positives[0] += 1
                else:
                    false_negatives[0] += 1

                if old_result in TRIAGE_CATEGORIES:
                    true_positives[1] += 1
                else:
                    false_negatives[1] += 1
            else:
                if new_result in TRIAGE_CATEGORIES:
                    false_positives[0] += 1
                else:
                    true_negatives[0] += 1
                
                if old_result in TRIAGE_CATEGORIES:
                    false_positives[1] += 1
                else:
                    true_negatives[1] += 1
            
            normalized = NormalizedText(raw_text)
            
            if new_result in TRIAGE_CATEGORIES and old_result not in TRIAGE_CATEGORIES:
                new_triage_old_notriage += 1
                print(f"Message: {raw_text}, New: {new_result}, Old: {old_result}, Emoji Normalized: {normalized.emoji_normalized_text}")
            elif new_result not in TRIAGE_CATEGORIES and old_result in TRIAGE_CATEGORIES and label.lower() not in ["notrelevant", "lowconcern"]:
                new_notriage_old_triage += 1
            
                
                print(f"CHECK HERE XXXXXXXXXXXXXXXXX Message: {raw_text}, New: {new_result}, Old: {old_result}, Label: {label}, Emoji Normalized: {normalized.emoji_normalized_text}")
            elif new_result not in TRIAGE_CATEGORIES and old_result in TRIAGE_CATEGORIES and label.lower()=="notrelevant":
                new_notriage_old_triage_nr += 1



            if new_result != "other":
                matched_new += 1
            if old_result not in ("other", "n/a"):
                matched_old += 1
            if new_result == old_result and new_result != "other":
                agreement += 1
            if label.lower() == "notrelevant":
                not_relevant_total += 1
                if new_result == "other":
                    not_relevant_other_new += 1
                if old_result == "other":
                    not_relevant_other_old += 1
            else:
                relevant_total+=1


            if i % 500 == 0:
                log.info("Processed %d rows...", i)

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 50)
    print("  Evaluation complete")
    print("=" * 50)
    print(f"  Total rows processed  : {total}")
    print(f"  New classifier matches (anything not categorized as 'Other'): {matched_new:>6}  ({matched_new/total*100:.1f}%)" if total else "")
    if old_classify:
        print(f"  Old classifier matches (anything not categorized as 'Other'): {matched_old:>6}  ({matched_old/total*100:.1f}%)" if total else "")
        print(f"  Classifier agreement (when things are not categorized as 'Other') : {agreement:>6}  ({agreement/total*100:.1f}%)" if total else "")
    if not_relevant_total:
        pct_new = not_relevant_other_new / not_relevant_total * 100
        print(f"  NotRelevant → other (new): {not_relevant_other_new:>6}/{not_relevant_total}  ({pct_new:.1f}%)")
        if old_classify:
            pct_old = not_relevant_other_old / not_relevant_total * 100
            print(f"  NotRelevant → other (old): {not_relevant_other_old:>6}/{not_relevant_total}  ({pct_old:.1f}%)")
    print(f"  Output written to     : {output_file}")
    print("=" * 50)


    tp = true_positives[0]
    fp = false_positives[0]
    fn = false_negatives[0]
    tn = true_negatives[0]

    print("\nConfusion Matrix for New Script:")
    print("                     Predicted")
    print("                 |   Pos        Neg")
    print(f"Actual  Pos      | TP: {tp:<5} FN: {fn:<5}")
    print(f"        Neg      | FP: {fp:<5} TN: {tn:<5}\n")

    print("=" * 50)


    tp = true_positives[1]
    fp = false_positives[1]
    fn = false_negatives[1]
    tn = true_negatives[1]

    print("\nConfusion Matrix for Old Script:")
    print("                     Predicted")
    print("                 |   Pos        Neg")
    print(f"Actual  Pos      | TP: {tp:<5} FN: {fn:<5}")
    print(f"        Neg      | FP: {fp:<5} TN: {tn:<5}")


    print(f"\nNew script classified {new_triage_old_notriage} responses as 'Send to Triage'" \
            " while old script classified the same responses as 'Do Not Triage'.")
    print(f"\nNew script classified {new_notriage_old_triage} responses as 'Do Not Triage'" \
            " when old script classified the same responses as 'Send to Triage'" \
            " AND a counselor marked the response as Moderate or High concern.")
    print(f"\nNew script classified {new_notriage_old_triage_nr} responses as 'Do Not Triage'" \
            " when old script classified the same responses as 'Send to Triage'" \
            " AND a counselor marked the response as NotRelevant.")


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    log.info("Loading new classifier from config dir: %s", args.config)
    new_classify = load_new_classifier(args.config)

    old_classify = None
    if args.old_rules:
        log.info("Loading old regex classifier from: %s", args.old_rules)
        old_classify = load_old_classifier(args.old_rules, args.old_triage_keywords)
    else:
        log.info("No --old-rules provided — old_classification column will be 'n/a'.")

    run_evaluation(
        input_path=args.input,
        output_path=args.output,
        message_col=args.message_col,
        label_col=args.label_col,
        new_classify=new_classify,
        old_classify=old_classify,
    )


if __name__ == "__main__":
    main()