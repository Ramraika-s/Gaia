# Economics and Trade (`economics_and_trade`) — Authoring Guide

## 1. Scope & Domain Definition
The `economics_and_trade` domain encompasses market mechanics, double-entry bookkeeping, currency velocity, order-book price clearing at the World Trade Centre (WTC), credit issuance by the closed-loop World Bank, cargo transport tariffs, promissory notes, and property deeds.

---

## 2. Subtopics & `fact_key` Conventions
Prefix: `economics_and_trade.<subtopic>.<concept>`

Allowed `<subtopic>` categories:
- `accounting`: Double-entry ledgers, debit-credit balance, audit reconciliation.
- `market`: Order-book bid/ask matching, price clearing, bulk auction mechanics.
- `banking`: Collateralized loans, interest accrual, reserve ratios, promissory bills.
- `logistics`: Caravan routes, toll plazas, shipping insurance, warehouse storage fees.
- `property`: Land deed registration, probate appraisal, escheatment transfers.

---

## 3. Tone & Voice
- **Tone:** Analytical, prudent, mercantile, quantitative.
- **Style:** Merchant guild statutes, banker handbooks, commercial treaties, customs edicts.
- **Racial Considerations:**
  - *Dwarf:* Precise ledger balancing, gold/silver assay marks, vault security.
  - *Human:* Dynamic market clearing, risk-pooling joint ventures, trade fairs.
  - *Beasthuman:* Barter valuation protocols, seasonal migratory fur fairs, meat trade.
  - *Elf:* Long-term resource treaties, botanical commodity grading, silent trading.
  - *Demon:* High-value rare gem contracts, strict punitive default clauses, mining futures.

---

## 4. Profession Hooks & Rigs
- Primary professions: Merchant, Banker, Clerk, Caravan Master, Toll Collector, Appraiser.
- Rig integration: Abacus counting, coin weighing scales, ledger writing with quill.

---

## 5. Mechanical Effect Bounds
- `trade_fee_reduction`: `[0.00, +0.25]`
- `market_clearing_efficiency`: `[0.00, +0.30]`
- `credit_default_reduction`: `[0.00, +0.30]`
- `civil_stability_bonus`: `[0.00, +0.20]`

---

## 6. Example Entries

```json
[
  {
    "entry_id": "econ_trade_vol001_double_entry_ledger_system",
    "subject": "economics_and_trade",
    "target_section": "commerce_and_banking",
    "fact_key": "economics_and_trade.accounting.double_entry_bookkeeping",
    "title": "Double-Entry Bookkeeping and Closed-Loop Ledgering",
    "summary": "Mandating balanced debits and credits across all merchant transactions to eliminate unrecorded credit leakage and fraudulent overdrafts.",
    "body": "Primitive tally sticks fail when credit chains extend across multiple towns. The double-entry method records every transaction as an equal debit to one account and credit to another. By requiring day-end sum totals to balance to zero, merchant houses and the World Bank instantly identify embezzlement and prevent phantom credit expansion.",
    "author": "Banker Malakor",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["accounting", "bookkeeping", "ledger", "banking", "finance"],
    "prerequisites": [],
    "mechanical_effects": {
      "credit_default_reduction": 0.22,
      "market_clearing_efficiency": 0.12
    },
    "supersedes": [],
    "distinct_from": []
  },
  {
    "entry_id": "econ_trade_vol001_sealed_grain_warrants",
    "subject": "economics_and_trade",
    "target_section": "commerce_and_banking",
    "fact_key": "economics_and_trade.market.sealed_depository_warrants",
    "title": "Sealed Depository Warrants for Bulk Commodity Clearing",
    "summary": "Transferring standardized paper warehouse receipts rather than carting tons of physical grain to the central trade floor, drastically lowering exchange friction.",
    "body": "Hauling thousands of bushels of rye and barley to the World Trade Centre floor creates massive street congestion and cargo spillage. Depositing grain into certified guild elevators in exchange for wax-sealed bearer warrants allows merchants to buy and sell title instantaneously. Physical grain moves only once, directly from the elevator to the final baker's cart.",
    "author": "Guild Master Corvus",
    "author_type": "MORTAL",
    "era_tier": 1,
    "tags": ["market", "wtc", "commodities", "warrants", "trade"],
    "prerequisites": ["economics_and_trade.accounting.double_entry_bookkeeping"],
    "mechanical_effects": {
      "trade_fee_reduction": 0.15,
      "market_clearing_efficiency": 0.18
    },
    "supersedes": [],
    "distinct_from": []
  }
]
```
