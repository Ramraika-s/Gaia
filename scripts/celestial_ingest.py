#!/usr/bin/env python3
"""
scripts/celestial_ingest.py
Sandboxed Celestial Lore Harvester & Ingestion CLI for Gaia v4.0.

Distills raw reference text/lore into clean Knowledge Foundry JSON packs:
- Strictly offline-safe with optional local llama.cpp acceleration
- Enforces fantasy tone and strips/rejects modern anachronisms
- Applies 3-stage cascaded deduplication before saving
- Formats valid KnowledgePack JSON ready for review and atomic merge

Follows Gaia v4.0 Sprint 6 Specification.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sim_core.knowledge.dedupe import DeduplicationEngine  # noqa: E402
from sim_core.knowledge.schema import (  # noqa: E402
    CANONICAL_SUBJECTS,
    KnowledgeEntry,
    KnowledgePack,
    SubjectLiteral,
    validate_anachronisms,
)

SUBJECT_DEFAULT_EFFECTS: dict[str, dict[str, float]] = {
    "tactics_and_warfare": {"defense_bonus": 0.08, "combat_power_multiplier": 0.06},
    "craft_and_metallurgy": {"craft_speed_bonus": 0.10, "tool_durability_bonus": 0.12},
    "architecture_and_engineering": {
        "structural_integrity_bonus": 0.15,
        "construction_cost_reduction": 0.05,
    },
    "agriculture_and_botany": {"crop_yield_bonus": 0.10, "winter_hardiness": 0.08},
    "medicine_and_biology": {"healing_rate_bonus": 0.12, "infection_resistance": 0.15},
    "economics_and_trade": {"trade_fee_reduction": 0.05, "market_clearing_efficiency": 0.08},
    "law_and_governance": {"civil_stability_bonus": 0.10, "judicial_accuracy": 0.08},
    "philosophy_and_culture": {"reputation_bonus": 0.08, "civil_stability_bonus": 0.05},
    "natural_history_and_geography": {"patrol_efficiency": 0.10, "attrition_reduction": 0.06},
    "divine_theology_and_history": {"faith_devotion_bonus": 0.12, "divine_favor_generation": 0.10},
}


def sanitize_snake_id(text: str, max_len: int = 48) -> str:
    """Converts arbitrary text into a clean snake_case identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    cleaned = re.sub(r"_+", "_", cleaned)
    if len(cleaned) < 4:
        cleaned = f"entry_{cleaned}".strip("_")
    return cleaned[:max_len]


def cleanse_modern_anachronisms(text: str) -> str:
    """Replaces modern terms with archaic fantasy equivalents if found."""
    replacements = {
        "internet": "astral weave",
        "computer": "arithmetic abacus",
        "computing": "reckoning",
        "electricity": "celestial lightning",
        "electrical": "lightning-attuned",
        "nuclear": "abyssal core",
        "atomic": "elemental particle",
        "steam engine": "fire-water apparatus",
        "plastic": "molded resin",
        "plastics": "molded resins",
        "wifi": "whisper spirit",
        "wi-fi": "whisper spirit",
        "smartphone": "scrying mirror",
        "cellphone": "scrying stone",
        "machine learning": "eldritch lorecraft",
        "neural network": "astral soul tapestry",
        "robotics": "clockwork golemcraft",
        "satellite": "orbital luminary",
        "diesel": "naphtha fuel",
        "gasoline": "refined alchemical oil",
        "petrol": "rock oil",
        "laser": "focused sunbeam",
        "wikipedia": "World Library",
    }
    cleansed = text
    for modern, archaic in replacements.items():
        pattern = re.compile(rf"\b{re.escape(modern)}\b", re.IGNORECASE)
        cleansed = pattern.sub(archaic, cleansed)
    return cleansed


def extract_offline_heuristic(
    raw_text: str,
    subject: SubjectLiteral,
    author: str,
    era_tier: int,
    max_entries: int,
) -> list[KnowledgeEntry]:
    """Heuristic extraction splitting headers or paragraphs into clean KnowledgeEntries."""
    entries: list[KnowledgeEntry] = []
    paragraphs = [p.strip() for p in raw_text.split("\n\n") if len(p.strip()) > 40]

    if not paragraphs:
        paragraphs = [p.strip() for p in raw_text.split("\n") if len(p.strip()) > 40]

    base_effects = SUBJECT_DEFAULT_EFFECTS.get(subject, {"civil_stability_bonus": 0.05})

    for idx, para in enumerate(paragraphs[:max_entries]):
        cleansed_para = cleanse_modern_anachronisms(para)

        # Derive title
        lines = cleansed_para.splitlines()
        first_line = lines[0].strip("# ").strip()
        if 4 <= len(first_line) <= 80:
            title = first_line
        else:
            title = f"{subject.replace('_', ' ').title()} Discourse {idx + 1}"
        title = re.sub(r"[^\w\s\-,]", "", title)[:110]

        summary = cleansed_para[:250].replace("\n", " ").strip()
        if len(summary) < 20:
            summary = f"Scholarly treatise on {title.lower()} within the mortal realms."

        body = cleansed_para
        if len(body) < 50:
            body = (
                f"{cleansed_para}\n\nRecorded by {author} for preservation in the World Library. "
                f"This knowledge strengthens mortal understanding of {subject.replace('_', ' ')}."
            )

        # Build valid identifiers
        entry_slug = sanitize_snake_id(title, 36)
        entry_id = f"{subject[:4]}_{entry_slug}"[:48]
        if len(entry_id) < 4:
            entry_id = f"lore_{idx + 1:04d}"

        subtopic = sanitize_snake_id(subject.split("_")[0], 16)
        concept = sanitize_snake_id(entry_slug, 16)
        fact_key = f"{subject}.{subtopic}.{concept}"

        # Clean tags
        raw_words = re.findall(r"\b[a-z]{3,16}\b", title.lower())
        tags = [w for w in raw_words if not validate_anachronisms(w)][:5]
        if not tags:
            tags = [subtopic]

        # Verify no residual anachronisms
        if (
            validate_anachronisms(title)
            or validate_anachronisms(summary)
            or validate_anachronisms(body)
        ):
            continue

        try:
            entry = KnowledgeEntry(
                entry_id=entry_id,
                subject=subject,
                target_section=f"Section {subject.title()}",
                fact_key=fact_key,
                title=title,
                summary=summary,
                body=body,
                author=author,
                author_type="MORTAL",
                era_tier=era_tier,
                tags=tags,
                mechanical_effects=dict(base_effects),
            )
            entries.append(entry)
        except Exception:
            continue

    return entries


def extract_with_llm(
    raw_text: str,
    subject: SubjectLiteral,
    author: str,
    era_tier: int,
    max_entries: int,
    llm_url: str,
) -> list[KnowledgeEntry]:
    """Attempts structured LLM distillation via local llama.cpp server; falls back to heuristic."""
    prompt = (
        f"You are the Celestial Scribe of Gaia. Distill the following reference lore into at most "
        f"{max_entries} entries for the subject '{subject}'.\n"
        f"STRICT RULES:\n"
        f"1. Tone MUST be high anime-fantasy, mythological, or classical scholarly.\n"
        f"2. ZERO modern technology words (no internet, computer, electricity, nuclear, plastic).\n"
        f"3. Return ONLY a valid JSON array of objects with keys: title, summary, body, tags.\n\n"
        f"REFERENCE TEXT:\n{raw_text[:3500]}"
    )

    req_payload = {
        "model": "local-model",
        "messages": [
            {
                "role": "system",
                "content": "You are a fantasy lore knowledge extractor. Output JSON only.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.4,
        "max_tokens": 1200,
        "chat_template_kwargs": {"enable_thinking": False},
    }

    try:
        url = f"{llm_url.rstrip('/')}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(req_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            # Extract JSON array
            match = re.search(r"\[\s*\{.*\}\s*\]", content, re.DOTALL)
            if match:
                items = json.loads(match.group(0))
                entries: list[KnowledgeEntry] = []
                base_effects = SUBJECT_DEFAULT_EFFECTS.get(subject, {"civil_stability_bonus": 0.05})
                for item in items[:max_entries]:
                    title = cleanse_modern_anachronisms(str(item.get("title", "")))[:110]
                    summary = cleanse_modern_anachronisms(str(item.get("summary", "")))[:550]
                    body = cleanse_modern_anachronisms(str(item.get("body", "")))[:4000]

                    if len(title) < 4 or len(summary) < 20 or len(body) < 50:
                        continue

                    entry_slug = sanitize_snake_id(title, 36)
                    entry_id = f"{subject[:4]}_{entry_slug}"[:48]
                    subtopic = sanitize_snake_id(subject.split("_")[0], 16)
                    concept = sanitize_snake_id(entry_slug, 16)
                    fact_key = f"{subject}.{subtopic}.{concept}"
                    raw_item_tags = item.get("tags", [subtopic])
                    tags = [
                        sanitize_snake_id(t, 16)
                        for t in raw_item_tags
                        if 2 <= len(t) <= 16
                    ][:5]

                    entry = KnowledgeEntry(
                        entry_id=entry_id,
                        subject=subject,
                        target_section=f"Section {subject.title()}",
                        fact_key=fact_key,
                        title=title,
                        summary=summary,
                        body=body,
                        author=author,
                        author_type="MORTAL",
                        era_tier=era_tier,
                        tags=tags,
                        mechanical_effects=dict(base_effects),
                    )
                    entries.append(entry)
                if entries:
                    return entries
    except Exception:
        # Fall back gracefully to heuristic extractor
        pass

    return extract_offline_heuristic(raw_text, subject, author, era_tier, max_entries)


def run_ingest(
    input_path: Path,
    subject: SubjectLiteral,
    output_path: Path,
    use_llm: bool = False,
    llm_url: str = "http://127.0.0.1:8080/v1",
    max_entries: int = 15,
    era_tier: int = 1,
    author: str = "Celestial Scribe",
) -> KnowledgePack:
    """Executes celestial lore harvest, deduplication, and JSON pack generation."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if subject not in CANONICAL_SUBJECTS:
        raise ValueError(f"Invalid subject '{subject}'. Must be one of: {CANONICAL_SUBJECTS}")

    with open(input_path, encoding="utf-8") as f:
        raw_text = f.read()

    # Extract raw candidates
    if use_llm:
        candidates = extract_with_llm(raw_text, subject, author, era_tier, max_entries, llm_url)
    else:
        candidates = extract_offline_heuristic(raw_text, subject, author, era_tier, max_entries)

    if not candidates:
        raise RuntimeError("No valid knowledge entries could be extracted from input text.")

    # Deduplication and audit
    dedupe_engine = DeduplicationEngine()
    accepted_entries: list[KnowledgeEntry] = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()

    for entry in candidates:
        if entry.entry_id in seen_ids or entry.fact_key in seen_keys:
            continue

        # Audit against already accepted entries
        is_dup = False
        for existing in accepted_entries:
            sim = dedupe_engine.compute_lexical_similarity(entry, existing)
            if sim >= 0.82:
                is_dup = True
                break

        if not is_dup:
            accepted_entries.append(entry)
            seen_ids.add(entry.entry_id)
            seen_keys.add(entry.fact_key)

    pack_name = f"pack_{subject}_{sanitize_snake_id(input_path.stem, 24)}"
    pack = KnowledgePack(
        pack_id=pack_name,
        entries=accepted_entries[:30],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pack.model_dump(), f, indent=2)

    return pack


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gaia v4.0 Celestial Lore Harvester (Sprint 6).",
    )
    parser.add_argument(
        "--input", "-i", type=Path, required=True, help="Input lore text/markdown path"
    )
    parser.add_argument(
        "--subject", "-s", type=str, required=True,
        choices=CANONICAL_SUBJECTS,
        help="Canonical subject category",
    )
    parser.add_argument(
        "--output", "-o", type=Path, default=None,
        help="Output JSON pack path (default: data/knowledge/staged/<pack_name>.json)",
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Use local llama.cpp server for extraction",
    )
    parser.add_argument(
        "--llm-url",
        type=str,
        default="http://127.0.0.1:8080/v1",
        help="Local LLM endpoint",
    )
    parser.add_argument(
        "--max-entries",
        type=int,
        default=15,
        help="Max entries to generate (1..30)",
    )
    parser.add_argument("--era-tier", type=int, default=1, help="Era tier (1..5)")
    parser.add_argument(
        "--author", type=str, default="Celestial Scribe", help="Author attribution"
    )

    args = parser.parse_args()

    out_file = args.output
    if not out_file:
        out_file = (
            REPO_ROOT
            / "data"
            / "knowledge"
            / "staged"
            / f"pack_{args.subject}_{args.input.stem}.json"
        )

    pack = run_ingest(
        input_path=args.input,
        subject=cast(SubjectLiteral, args.subject),
        output_path=out_file,
        use_llm=args.use_llm,
        llm_url=args.llm_url,
        max_entries=args.max_entries,
        era_tier=args.era_tier,
        author=args.author,
    )

    print(
        f"\n[Celestial Lore Harvester] Successfully generated pack '{pack.pack_id}' "
        f"with {len(pack.entries)} entries."
    )
    print(f"Saved to: {out_file}")
    print("\nNext Review & Merge Steps:")
    print(f"  1. Review: uv run python scripts/knowledge_review.py --pack {out_file}")
    print(f"  2. Commit: uv run python scripts/knowledge_merge.py --pack {out_file} --commit\n")


if __name__ == "__main__":
    main()
