"""
sim_core/knowledge
Standalone Knowledge Foundry & Deduplication Package for Gaia v4.0.
"""

from sim_core.knowledge.dedupe import (
    AuditReport,
    DeduplicationEngine,
    audit_single_entry,
)
from sim_core.knowledge.schema import (
    CANONICAL_SUBJECTS,
    FORBIDDEN_ANACHRONISMS,
    KnowledgeEntry,
    KnowledgePack,
    validate_anachronisms,
)

__all__ = [
    "CANONICAL_SUBJECTS",
    "FORBIDDEN_ANACHRONISMS",
    "KnowledgeEntry",
    "KnowledgePack",
    "validate_anachronisms",
    "AuditReport",
    "DeduplicationEngine",
    "audit_single_entry",
]
