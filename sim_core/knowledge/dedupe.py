"""
sim_core/knowledge/dedupe.py
Fast 3-Stage Cascaded Deduplication & Conflict Detection Engine for Gaia v4.0.

Stages:
- Stage 0: Schema validation & modern anachronism guardrails (HARD_FAIL)
- Stage 1: Exact & Normalized SHA-256 hash + ID/fact_key collision (HARD_DUPLICATE)
- Stage 2: Lexical Fuzzy & Shingles (word 3-gram + token-set ratio >= 0.82)
           (LEXICAL_DUPLICATE)
- Stage 3: Semantic Vector Similarity (NumPy cosine >= 0.88 SEMANTIC_DUPLICATE,

           0.78-0.87 NEAR_DUPLICATE_REVIEW, and opposing mechanical effects CONFLICT)
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

import numpy as np

try:
    from rapidfuzz import fuzz

    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    fuzz = None

from sim_core.knowledge.schema import (
    KnowledgeEntry,
    KnowledgePack,
    validate_anachronisms,
)

CACHE_DIR = Path(".cache")
EMBEDDINGS_CACHE_PATH = CACHE_DIR / "knowledge_embeddings.npz"


def normalize_text(text: str) -> str:
    """Lowercases, strips punctuation, and normalizes whitespace."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(cleaned.split())


def compute_normalized_hash(title: str, summary: str, body: str) -> str:
    """Computes SHA-256 of normalized core textual content."""
    combined = f"{normalize_text(title)} {normalize_text(summary)} {normalize_text(body)}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def compute_word_3grams(text: str) -> set[tuple[str, str, str]]:
    """Extracts sliding word 3-grams from normalized text."""
    words = re.findall(r"\b[a-z0-9]+\b", text.lower())
    if len(words) < 3:
        return set()
    return {(words[i], words[i + 1], words[i + 2]) for i in range(len(words) - 2)}


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Computes Jaccard similarity between two sets."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def token_set_similarity(text_a: str, text_b: str) -> float:
    """Computes token set ratio similarity (0.0 to 1.0)."""
    if HAS_RAPIDFUZZ and fuzz is not None:
        return float(fuzz.token_set_ratio(text_a, text_b)) / 100.0
    words_a = set(re.findall(r"\b[a-z0-9]+\b", text_a.lower()))
    words_b = set(re.findall(r"\b[a-z0-9]+\b", text_b.lower()))
    return jaccard_similarity(words_a, words_b)


# =============================================================================
# Stage 3: Offline Deterministic Dense Vector Embedder & Cache
# =============================================================================


class DeterministicTextEmbedder:
    """
    100% offline, deterministic dense vector embedder using feature hashing and
    fixed orthogonal random projection to produce 64-dimensional unit-norm vectors.
    Runs in milliseconds on CPU with zero external network downloads.
    """

    def __init__(self, n_features: int = 1024, n_components: int = 64, seed: int = 42):
        self.n_features = n_features
        self.n_components = n_components
        rng = np.random.RandomState(seed)
        # Random projection matrix Gaussian distribution
        raw_proj = rng.randn(n_features, n_components)
        # QR decomposition for orthonormal columns
        q, _ = np.linalg.qr(raw_proj)
        self.proj_matrix = q.astype(np.float32)

    def _hash_token(self, token: str) -> int:
        h = hashlib.md5(token.encode("utf-8")).digest()
        return int.from_bytes(h[:4], "little") % self.n_features

    def embed_text(self, text: str) -> np.ndarray:
        """Converts text into a 64-dim unit-normalized dense vector."""
        words = re.findall(r"\b[a-z0-9]+\b", text.lower())
        char_3grams = [text[i : i + 3].lower() for i in range(len(text) - 2)]

        counts = np.zeros(self.n_features, dtype=np.float32)
        for w in words:
            counts[self._hash_token(w)] += 1.0
        # Word bigrams
        for i in range(len(words) - 1):
            bg = f"{words[i]}_{words[i + 1]}"
            counts[self._hash_token(bg)] += 1.5
        # Character trigrams for morphological robustness
        for c3 in char_3grams:
            counts[self._hash_token(c3)] += 0.3

        # Sublinear term frequency
        counts = np.log1p(counts)

        # Dense projection
        dense = np.dot(counts, self.proj_matrix)
        norm = np.linalg.norm(dense)
        if norm > 1e-8:
            dense = dense / norm
        return dense


_GLOBAL_EMBEDDER = DeterministicTextEmbedder()


def load_vector_cache() -> dict[str, np.ndarray]:
    """Loads cached embeddings from .cache/knowledge_embeddings.npz."""
    if not EMBEDDINGS_CACHE_PATH.exists():
        return {}
    try:
        data = np.load(EMBEDDINGS_CACHE_PATH)
        return {k: data[k] for k in data.files}
    except Exception:
        return {}


def save_vector_cache(cache: dict[str, np.ndarray]) -> None:
    """Saves embedding cache atomically to .cache/knowledge_embeddings.npz."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = CACHE_DIR / ".knowledge_embeddings.tmp.npz"
    try:
        np.savez_compressed(str(tmp_path), **cast(dict[str, Any], cache))
        tmp_path.replace(EMBEDDINGS_CACHE_PATH)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()


def get_embedding(text: str, cache: dict[str, np.ndarray] | None = None) -> tuple[np.ndarray, str]:
    """Gets or computes 64-dim unit-norm embedding for text, tracking content hash."""
    content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if cache is not None and content_hash in cache:
        return cache[content_hash], content_hash
    vec = _GLOBAL_EMBEDDER.embed_text(text)
    if cache is not None:
        cache[content_hash] = vec
    return vec, content_hash


# =============================================================================
# Diagnostic Data Structures & Audit Engine
# =============================================================================


@dataclass
class AuditReport:
    total_packs: int = 0
    total_entries: int = 0
    hard_fails: list[dict[str, Any]] = field(default_factory=list)
    hard_duplicates: list[dict[str, Any]] = field(default_factory=list)
    lexical_duplicates: list[dict[str, Any]] = field(default_factory=list)
    semantic_duplicates: list[dict[str, Any]] = field(default_factory=list)
    near_duplicates: list[dict[str, Any]] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    passed_entries: int = 0
    duration_ms: float = 0.0

    @property
    def is_clean(self) -> bool:
        """True if there are zero hard blocking issues."""
        return (
            len(self.hard_fails) == 0
            and len(self.hard_duplicates) == 0
            and len(self.lexical_duplicates) == 0
            and len(self.semantic_duplicates) == 0
        )


class DeduplicationEngine:
    """
    3-Stage Cascaded Deduplication Engine.
    Audits staged packs against each other and against existing world_library entries.
    """

    def __init__(self, existing_library_entries: list[Any] | None = None):
        self.existing_entries: list[dict[str, Any]] = []
        self.vector_cache: dict[str, np.ndarray] = load_vector_cache()

        if existing_library_entries:
            for item in existing_library_entries:
                self._register_existing(item)

    def _register_existing(self, item: Any) -> None:
        """Normalizes an existing world_library entry or dict."""
        if hasattr(item, "entry_id"):
            entry_id = item.entry_id
            subject = getattr(item, "subject", "unknown")
            fact_key = getattr(item, "fact_key", getattr(item, "topic", "unknown.unknown.unknown"))
            title = getattr(item, "title", "")
            summary = getattr(item, "summary", "")
            body = getattr(item, "body", summary)
            tags = getattr(item, "tags", [])
            effects = getattr(item, "mechanical_effects", {})
            supersedes = getattr(item, "supersedes", [])
            distinct_from = getattr(item, "distinct_from", [])
        elif isinstance(item, dict):
            entry_id = item.get("entry_id", "")
            subject = item.get("subject", "unknown")
            fact_key = item.get("fact_key", item.get("topic", "unknown.unknown.unknown"))
            title = item.get("title", "")
            summary = item.get("summary", "")
            body = item.get("body", summary)
            tags = item.get("tags", [])
            effects = item.get("mechanical_effects", {})
            supersedes = item.get("supersedes", [])
            distinct_from = item.get("distinct_from", [])
        else:
            return

        combined_text = f"{title}\n{summary}\n{body}"
        vec, _ = get_embedding(combined_text, self.vector_cache)

        self.existing_entries.append(
            {
                "entry_id": entry_id,
                "subject": subject,
                "fact_key": fact_key,
                "title": title,
                "summary": summary,
                "body": body,
                "tags": tags,
                "mechanical_effects": effects,
                "supersedes": supersedes,
                "distinct_from": distinct_from,
                "norm_hash": compute_normalized_hash(title, summary, body),
                "words_3gram": compute_word_3grams(f"{title} {summary} {body}"),
                "combined_text": combined_text,
                "vector": vec,
                "source": "world_library",
            }
        )

    def compute_lexical_similarity(
        self,
        entry_a: KnowledgeEntry | dict[str, Any],
        entry_b: KnowledgeEntry | dict[str, Any],
    ) -> float:
        """Computes lexical similarity (max of 3-gram Jaccard and token-set ratio)."""
        is_dict_a = isinstance(entry_a, dict)
        title_a = entry_a.get("title", "") if is_dict_a else getattr(entry_a, "title", "")
        summary_a = entry_a.get("summary", "") if is_dict_a else getattr(entry_a, "summary", "")
        body_a = entry_a.get("body", "") if is_dict_a else getattr(entry_a, "body", "")

        is_dict_b = isinstance(entry_b, dict)
        title_b = entry_b.get("title", "") if is_dict_b else getattr(entry_b, "title", "")
        summary_b = entry_b.get("summary", "") if is_dict_b else getattr(entry_b, "summary", "")
        body_b = entry_b.get("body", "") if is_dict_b else getattr(entry_b, "body", "")

        text_a = f"{title_a} {summary_a} {body_a}"
        text_b = f"{title_b} {summary_b} {body_b}"

        grams_a = compute_word_3grams(text_a)
        grams_b = compute_word_3grams(text_b)
        jaccard = jaccard_similarity(grams_a, grams_b)

        comb_a = f"{title_a}\n{summary_a}\n{body_a}"
        comb_b = f"{title_b}\n{summary_b}\n{body_b}"
        token_ratio = token_set_similarity(comb_a, comb_b)

        return float(max(jaccard, token_ratio))

    def audit_packs(
        self,
        pack_files: list[Path],
        strict_near_dupes: bool = False,
    ) -> AuditReport:
        """Audits a collection of JSON knowledge pack files."""
        t_start = time.perf_counter()
        report = AuditReport(total_packs=len(pack_files))

        staged_items: list[dict[str, Any]] = []

        # ---------------------------------------------------------------------
        # STAGE 0: Schema Validation & Guardrails
        # ---------------------------------------------------------------------
        for pack_path in pack_files:
            try:
                with open(pack_path, encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as ex:
                report.hard_fails.append(
                    {
                        "file": str(pack_path),
                        "entry_id": None,
                        "stage": 0,
                        "reason": f"JSON decode error: {ex}",
                    }
                )
                continue

            try:
                pack = KnowledgePack.model_validate(raw_data)
            except Exception as ex:
                report.hard_fails.append(
                    {
                        "file": str(pack_path),
                        "entry_id": None,
                        "stage": 0,
                        "reason": f"Schema validation error: {ex}",
                    }
                )
                continue

            for entry in pack.entries:
                report.total_entries += 1
                combined_text = f"{entry.title}\n{entry.summary}\n{entry.body}"
                vec, _ = get_embedding(combined_text, self.vector_cache)

                staged_items.append(
                    {
                        "entry": entry,
                        "file": str(pack_path),
                        "entry_id": entry.entry_id,
                        "subject": entry.subject,
                        "fact_key": entry.fact_key,
                        "title": entry.title,
                        "summary": entry.summary,
                        "body": entry.body,
                        "tags": entry.tags,
                        "mechanical_effects": entry.mechanical_effects,
                        "supersedes": set(entry.supersedes),
                        "distinct_from": set(entry.distinct_from),
                        "norm_hash": compute_normalized_hash(
                            entry.title, entry.summary, entry.body
                        ),
                        "words_3gram": compute_word_3grams(
                            f"{entry.title} {entry.summary} {entry.body}"
                        ),
                        "combined_text": combined_text,
                        "vector": vec,
                        "source": str(pack_path),
                    }
                )

        # Compare staged against all reference entries (existing + other staged)
        all_references = list(self.existing_entries)

        for i, item in enumerate(staged_items):
            entry_id = item["entry_id"]
            fact_key = item["fact_key"]
            norm_hash = item["norm_hash"]
            words_3gram = item["words_3gram"]
            vec_a = item["vector"]
            supersedes = item["supersedes"]
            distinct_from = item["distinct_from"]

            # Current pool of prior references to compare against:
            # 1. All existing library entries
            # 2. All prior staged items in this run
            compare_pool = all_references + staged_items[:i]

            entry_has_hard_issue = False

            for ref in compare_pool:
                ref_id = ref["entry_id"]
                ref_key = ref["fact_key"]

                # If entry explicitly supersedes the target, collisions/similarities are allowed
                is_superseded = (ref_id in supersedes) or (ref_key in supersedes)
                is_distinct = (ref_id in distinct_from) or (ref_key in distinct_from)

                # -------------------------------------------------------------
                # STAGE 1: Exact Hash & Identifier Collisions
                # -------------------------------------------------------------
                if entry_id == ref_id and not is_superseded:
                    report.hard_duplicates.append(
                        {
                            "file": item["file"],
                            "entry_id": entry_id,
                            "conflict_with": ref_id,
                            "conflict_source": ref["source"],
                            "stage": 1,
                            "reason": f"Exact entry_id collision '{entry_id}'",
                        }
                    )
                    entry_has_hard_issue = True

                if fact_key == ref_key and not is_superseded:
                    report.hard_duplicates.append(
                        {
                            "file": item["file"],
                            "entry_id": entry_id,
                            "conflict_with": ref_id,
                            "conflict_source": ref["source"],
                            "stage": 1,
                            "reason": f"Exact fact_key collision '{fact_key}'",
                        }
                    )
                    entry_has_hard_issue = True

                if norm_hash == ref["norm_hash"] and not is_superseded:
                    report.hard_duplicates.append(
                        {
                            "file": item["file"],
                            "entry_id": entry_id,
                            "conflict_with": ref_id,
                            "conflict_source": ref["source"],
                            "stage": 1,
                            "reason": "Identical normalized content hash (duplicate text)",
                        }
                    )
                    entry_has_hard_issue = True

                if entry_has_hard_issue:
                    break

                # -------------------------------------------------------------
                # STAGE 2: Lexical Fuzzy & Shingles (>= 0.82)
                # -------------------------------------------------------------
                jaccard = jaccard_similarity(words_3gram, ref["words_3gram"])
                token_ratio = token_set_similarity(item["combined_text"], ref["combined_text"])
                lexical_score = max(jaccard, token_ratio)

                # -------------------------------------------------------------
                # STAGE 3: Semantic Vector Similarity & Conflict Detection
                # -------------------------------------------------------------
                cosine = float(np.dot(vec_a, ref["vector"]))

                # Conflict Check: same subject + overlapping tags + similarity >= 0.72
                if (
                    item["subject"] == ref["subject"]
                    and cosine >= 0.72
                    and not is_superseded
                    and not is_distinct
                ):
                    common_tags = set(item["tags"]) & set(ref["tags"])
                    if common_tags:
                        eff_a = item["mechanical_effects"]
                        eff_b = ref["mechanical_effects"]
                        for eff_k, val_a in eff_a.items():
                            if eff_k in eff_b:
                                val_b = eff_b[eff_k]
                                # Check opposing direction (one positive, one negative)
                                if (val_a > 0.02 and val_b < -0.02) or (
                                    val_a < -0.02 and val_b > 0.02
                                ):
                                    report.conflicts.append(
                                        {
                                            "file": item["file"],
                                            "entry_id": entry_id,
                                            "conflict_with": ref_id,
                                            "similarity": round(cosine, 3),
                                            "effect_key": eff_k,
                                            "val_a": val_a,
                                            "val_b": val_b,
                                            "stage": 3,
                                            "reason": (
                                                f"Opposing effect on '{eff_k}' ({val_a} vs {val_b})"
                                            ),
                                        }
                                    )

                if lexical_score >= 0.82 and not is_superseded and not is_distinct:
                    report.lexical_duplicates.append(
                        {
                            "file": item["file"],
                            "entry_id": entry_id,
                            "conflict_with": ref_id,
                            "conflict_source": ref["source"],
                            "similarity": round(lexical_score, 3),
                            "stage": 2,
                            "reason": f"High lexical/shingle similarity ({lexical_score:.1%})",
                        }
                    )
                    entry_has_hard_issue = True
                    break

                if cosine >= 0.88 and not is_superseded and not is_distinct:
                    report.semantic_duplicates.append(
                        {
                            "file": item["file"],
                            "entry_id": entry_id,
                            "conflict_with": ref_id,
                            "conflict_source": ref["source"],
                            "similarity": round(cosine, 3),
                            "stage": 3,
                            "reason": f"High semantic vector similarity ({cosine:.1%})",
                        }
                    )
                    entry_has_hard_issue = True
                    break

                elif 0.78 <= cosine < 0.88 and not is_superseded and not is_distinct:
                    report.near_duplicates.append(
                        {
                            "file": item["file"],
                            "entry_id": entry_id,
                            "conflict_with": ref_id,
                            "conflict_source": ref["source"],
                            "similarity": round(cosine, 3),
                            "title_a": item["title"],
                            "title_b": ref["title"],
                            "stage": 3,
                        }
                    )
                    if strict_near_dupes:
                        entry_has_hard_issue = True
                        break

            if not entry_has_hard_issue:
                report.passed_entries += 1

        # Persist vector cache updates
        save_vector_cache(self.vector_cache)

        report.duration_ms = (time.perf_counter() - t_start) * 1000.0
        return report


def audit_single_entry(
    entry_data: dict[str, Any] | KnowledgeEntry,
    existing_entries: list[Any],
) -> tuple[bool, str, dict[str, Any] | None]:
    """
    Evaluates a single proposed entry against existing entries through Stages 0-3.
    Used by Mortal Book Petitions to reject duplicates automatically.
    Returns: (is_valid, reason_code, details_or_conflict)
    """
    # Stage 0: Schema & Anachronisms
    if isinstance(entry_data, dict):
        try:
            entry = KnowledgeEntry.model_validate(entry_data)
        except Exception as ex:
            return False, f"HARD_FAIL: Schema error: {ex}", None
    else:
        entry = entry_data

    # Check anachronisms
    for field_val in (entry.title, entry.summary, entry.body):
        term = validate_anachronisms(field_val)
        if term:
            return False, f"HARD_FAIL: Anachronism '{term}' forbidden", None

    norm_hash = compute_normalized_hash(entry.title, entry.summary, entry.body)
    words_3gram = compute_word_3grams(f"{entry.title} {entry.summary} {entry.body}")
    combined_text = f"{entry.title}\n{entry.summary}\n{entry.body}"
    vec, _ = get_embedding(combined_text)

    supersedes = set(entry.supersedes)
    distinct_from = set(entry.distinct_from)

    for item in existing_entries:
        if hasattr(item, "entry_id"):
            ref_id = item.entry_id
            ref_key = getattr(item, "fact_key", getattr(item, "topic", ""))
            ref_title = getattr(item, "title", "")
            ref_summary = getattr(item, "summary", "")
            ref_body = getattr(item, "body", ref_summary)
            ref_effects = getattr(item, "mechanical_effects", {})
            ref_subject = getattr(item, "subject", "")
            ref_tags = getattr(item, "tags", [])
        elif isinstance(item, dict):
            ref_id = item.get("entry_id", "")
            ref_key = item.get("fact_key", item.get("topic", ""))
            ref_title = item.get("title", "")
            ref_summary = item.get("summary", "")
            ref_body = item.get("body", ref_summary)
            ref_effects = item.get("mechanical_effects", {})
            ref_subject = item.get("subject", "")
            ref_tags = item.get("tags", [])
        else:
            continue

        is_superseded = (ref_id in supersedes) or (ref_key in supersedes)
        is_distinct = (ref_id in distinct_from) or (ref_key in distinct_from)

        # Stage 1
        if entry.entry_id == ref_id and not is_superseded:
            return False, f"HARD_DUPLICATE: ID collision '{ref_id}'", {"conflict_id": ref_id}
        if entry.fact_key == ref_key and not is_superseded:
            return False, f"HARD_DUPLICATE: fact_key collision '{ref_key}'", {"conflict_id": ref_id}
        ref_norm_hash = compute_normalized_hash(ref_title, ref_summary, ref_body)
        if norm_hash == ref_norm_hash and not is_superseded:
            return False, "HARD_DUPLICATE: Identical normalized text hash", {"conflict_id": ref_id}

        # Stage 2
        ref_3grams = compute_word_3grams(f"{ref_title} {ref_summary} {ref_body}")
        ref_combined = f"{ref_title}\n{ref_summary}\n{ref_body}"
        jaccard = jaccard_similarity(words_3gram, ref_3grams)
        token_ratio = token_set_similarity(combined_text, ref_combined)
        lexical_score = max(jaccard, token_ratio)
        if lexical_score >= 0.82 and not is_superseded and not is_distinct:
            return (
                False,
                f"LEXICAL_DUPLICATE: score {lexical_score:.1%}",
                {"conflict_id": ref_id, "score": lexical_score},
            )

        # Stage 3
        ref_vec, _ = get_embedding(ref_combined)
        cosine = float(np.dot(vec, ref_vec))
        if cosine >= 0.88 and not is_superseded and not is_distinct:
            return (
                False,
                f"SEMANTIC_DUPLICATE: cosine {cosine:.1%}",
                {"conflict_id": ref_id, "score": cosine},
            )

        # Conflict check
        if (
            entry.subject == ref_subject
            and cosine >= 0.72
            and not is_superseded
            and not is_distinct
        ):
            common_tags = set(entry.tags) & set(ref_tags)
            if common_tags:
                for eff_k, val_a in entry.mechanical_effects.items():
                    if eff_k in ref_effects:
                        val_b = ref_effects[eff_k]
                        if (val_a > 0.02 and val_b < -0.02) or (val_a < -0.02 and val_b > 0.02):
                            return (
                                False,
                                f"CONFLICT: opposing effect on '{eff_k}' ({val_a} vs {val_b})",
                                {"conflict_id": ref_id},
                            )

    return True, "VALID", None
