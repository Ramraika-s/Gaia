# ECONOMY_HOUSING_AND_GEAR_SPEC.md — Closed-Loop Double-Entry Economy, Housing Market & Gear Synchronization

## 1. Executive Summary & Financial Invariants
Gaia v4.0 implements a strictly closed-loop, macro-financially conservative economy where **zero credits are created or destroyed out of thin air**:
1. **The World Bank is the Sole Currency Issuer:** All currency originates from the World Bank's initial reserve pool. Subsystems, governments, and deities cannot spawn fiat credits.
2. **Strict Double-Entry Bookkeeping:** Every transaction—from a parent handing an allowance to an infant, to a merchant buying iron at the WTC, to a pioneer purchasing a deed—executes as:
   $$\text{debit}(\text{sender}, \text{amount}) \quad\text{and}\quad \text{credit}(\text{receiver}, \text{amount})$$
   Transactions fail atomically if $\text{sender.credits} < \text{amount}$.
3. **Zero Credit Drift Verification:** Multi-thousand-agent soak tests verify that total circulating credits plus bank reserves remain perfectly invariant over hundreds of game days ($0.000000$ drift).

```text
┌────────────────────────────────────────────────────────────────────────┐
│                      WORLD BANK (Sole Issuer)                          │
│               Reserve Credits + Active Loans Portfolio                 │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Double-Entry Transfers
                                    ▼
┌───────────────────┬───────────────────┬───────────────────┬────────────┐
│   WTC Exchange    │  Property Market  │  Housing Market   │Gear Economy│
│Order-Book Clearing│  16x16m Deed Sales│   T1 -> T2 -> T3  │Outfits and │
│  Fisher CPI Index │     and Leases    │ Upgrades & Probate│Tools Sync  │
└───────────────────┴───────────────────┴───────────────────┴────────────┘
```

---

## 2. The World Bank & Double-Entry Credit Mechanics (`sim_core/society/economy.py`)

### 2.1 Currency Creation & Reserve Management
- At world inception, the World Bank holds the civilization's master monetary base $M_0$ (default $1,000,000.0$ credits).
- Circulating credits are injected through verified loans issued to municipal treasuries or qualified adult citizens, and recollected through principal repayments and interest.

### 2.2 Credit Scoring & Loan Underwriting
- **Credit Score Range:** $300$ to $850$ (baseline initial score: $650$).
- **Score Dynamics:**
  - $+10$ points for every loan payment completed on time.
  - $-35$ points for a delinquent window.
  - $-100$ points upon formal loan default.
- **Underwriting Thresholds:**
  - Mortals with $\text{credit\_score} < 580$ are rejected by `WorldGoddessCritic` for new loans.
  - Maximum borrowing limit:
    $$\text{Max Principal} = \min\left(\text{World Bank Reserve}, \text{credits} \times 4.0 \times \frac{\text{credit\_score}}{650}\right)$$
- **Default & Collateral Seizure:**
  - If a borrower misses 3 consecutive payment windows, the loan enters `DEFAULTED` status.
  - The World Bank executes immediate collateral seizure: frozen accounts, forfeiture of owned $16\text{m} \times 16\text{m}$ parcels to the bank, and a `DEBT_DEFAULT` case opened in the Judiciary.

### 2.3 Strict Double-Entry Conservation Invariant
- **Zero-Drift Invariant:** The World Bank is the sole monetary issuer. Every single transfer—whether purchasing goods, paying allowances, transferring rent, buying buildings, or settling probate—is an atomic debit from `sender` and credit to `receiver`.
- **System-Wide Balance Check:**
  $$\text{Total Money Supply} = \text{World Bank Reserves} + \sum_{i} \text{Agent}_i.\text{credits} + \sum_{s} \text{Treasury}_s.\text{credits} \equiv M_0$$
  This balance is verified at every civic tick and daily commit with exact **0.000000 drift tolerance**. Any discrepancy instantly aborts the commit and triggers `ErrorHealer` transaction rollback.

---

## 3. World Trade Centre (WTC) & Real Inflation (`sim_core/society/wtc_market.py`)

The WTC operates as a decentralized, order-book commodity exchange clearing bids and asks once per civic tick:

### 3.1 Traded Commodities & Volatility Clamping
- **Core Goods:** `food`, `wood`, `stone`, `iron`, `tools`, and `land_deeds`.
- **Price Volatility Guard:** Clearing prices are clamped to $\pm 15\%$ per tick relative to the previous clearing price to prevent runaway market panics.
- **3D Market Boards:** Live prices and CPI indicators stream to Godot over WebSocket, updating `UPDATE_ONCE` hanging wooden and marble signs in city squares.

### 3.2 Racial Comparative Advantage Matrix
Natural skill proficiencies create organic economic interdependence:
- **Dwarves (`BEASTHUMAN`):** Massive bonuses in mining and smithing; net exporters of `iron`, `stone`, and `tools`.
- **Elves (`ELF`):** High botanical yields; net exporters of `food` and rare medicinal herbs, especially vital during winter crop failures.
- **Humans (`HUMAN`):** Highest commercial velocity and banking aptitude; net exporters of financial services, logistics, and manufactured consumer wares.
- **Demons (`DEMON`):** Masters of volcanic smelting and dark enchanting; net exporters of high-durability weapons and basalt building blocks.
- **Dragons (`DRAGON`):** Possess vast mountain mineral deposits; trade high-grade gems and ancient lore during peaceful interludes.

### 3.3 Fisher CPI & Monetary Pressure
Inflation is computed endogenously using Fisher's Equation of Exchange:
$$\text{CPI}_t = \frac{\sum_k w_k P_k(t)}{\sum_k w_k P_k(0)}, \qquad \text{Monetary Pressure} = \frac{M_t / Q_t}{M_0 / Q_0}$$
- Where $M_t$ is circulating credit volume, and $Q_t$ is trailing aggregate physical commodity production.
- High wartime debt borrowing or severe winter famine reduces $Q_t$, driving up $\text{CPI}_t$ and eroding real wages.

---

## 4. Property Ownership & $16\text{m} \times 16\text{m}$ Parcels (`sim_core/society/property.py`)

- **Spatial Representation:** The world is partitioned into a uniform grid of $16\text{m} \times 16\text{m}$ parcels identified by `parcel_id = f"{cx}_{cz}"`.
- **Ownership Types:** `AGENT`, `SETTLEMENT`, `NATION`, `CHURCH`, or `UNCLAIMED`.
- **Zoning & Improvements:** Each parcel tracks improvements (`has_altar`, `has_library`, building footprints), assessed valuation, and active tenants.
- **Leasing & Rental:** Tenants pay recurring rental debits directly to the owner each civic tick. Failure to pay triggers eviction via the local Judiciary.

---

## 5. Housing Market Engine & Frontier Pioneering (`sim_core/society/housing_market.py`)

### 5.1 Autonomous Home Purchasing
- Unhoused mortal adults evaluate listed homes in their home settlement or regional capital.
- Starter cottage (`HOUSE_T1_COTTAGE`) base price is $60.0$ credits.
- Purchase executes via `WorldGoddessCritic` as an atomic double-entry debit from the buyer and credit to the seller (or settlement treasury if escheat property).

### 5.2 In-Place Tier Upgrades
Homeowners upgrade their dwellings as their family wealth and dynasty prestige expand:
1. `HOUSE_T1_COTTAGE` $\rightarrow$ `HOUSE_T2_TOWNHOUSE` ($120.0$ credits):
   - Expands household sleeping capacity from 2 to 5 agents.
   - Raises owner's civic reputation and unlocks artisan workshop placement.
2. `HOUSE_T2_TOWNHOUSE` $\rightarrow$ `HOUSE_T3_MANOR` ($250.0$ credits):
   - Expands capacity to 10 agents; adds courtyards and private storage.
   - Required for appointment to High Councils or royal candidacy.

### 5.3 Probate & Escheatment Cascade
When a property owner dies, `property.execute_probate(agent_id)` executes:
1. **Direct Heirs:** Equal fractional division among living spouse and children.
2. **Extended Kin:** Parents or siblings if no direct descendants exist.
3. **Settlement Escheatment:** If zero heirs exist and the parcel lies within a settlement border, ownership escheats to the **Settlement Treasury**, which re-lists it for sale on the WTC.
4. **Wilderness Abandonment:** If outside all borders, the property flips to **`UNCLAIMED` (Nameless)**, allowing squatters or frontiersmen to claim it freely.

### 5.4 Frontier Pioneering in Ring 2
- Ambitious adults migrate beyond the Ring 1 walls into the Ring 2 Frontier Wilderness ($1,500\text{m} \le r \le 3,300\text{m}$).
- Pioneers clear plots, gather local timber, and construct pioneer cottages (`is_frontier = true`).
- **Emergent Village Clustering:** When $\ge 5$ pioneer cottages cluster within $120\text{m}$, the inhabitants petition the World Goddess for recognition as a formal **`VILLAGE`** polity.

---

## 6. Gear Economy & 3D Reality Bubble Sync (`sim_core/society/gear_economy.py`)

Mortal visual status and vocational efficacy are reinforced by an equipment ecosystem:

### 6.1 Catalog & Item Classifications
- **Clothing (`CLOTHING`):**
  - `PEASANT_TUNIC` ($20$ cr): Agrarian work attire.
  - `RANGER_CLOAK` ($55$ cr): Camouflage cloak for woodland scouts and hunters.
  - `MAGE_ROBE` ($120$ cr): Embroidered robe for scholars and clerics.
- **Accessories (`ACCESSORY`):**
  - `LEATHER_BACKPACK` ($35$ cr): Increases personal inventory carrying capacity.
  - `SCHOLAR_AMULET` ($40$ cr): Accelerates World Library study speed.
  - `WARRIOR_HELMET` ($85$ cr): Reduces combat head injury risk.
- **Tools & Weapons (`TOOL_WEAPON`):**
  - `WOODCUTTER_AXE` ($30$ cr): Enhances timber harvesting efficiency.
  - `BLACKSMITH_HAMMER` ($45$ cr): Required for tool forging and repairs.
  - `IRON_SWORD` ($75$ cr): Standard sidearm for City Guards and infantry.
  - `DIVINE_STAFF` ($180$ cr): Sacred focus item for Oracles and High Clerics.

### 6.2 Profession-Driven Purchasing
- Agents evaluate gear based on profession requirements and surplus credits.
- Purchases transfer credits directly to local Blacksmith and Merchant shopkeepers via `WorldBank` double-entry transfers.

### 6.3 Reality Bubble Synchronization (`equipped_gear`)
- Python streams each visible mortal's `equipped_gear: list[str]` inside the `BUBBLE_SYNC` WebSocket frame.
- Godot's `HumanoidAnimator.gd` reads the item identifiers and dynamically attaches corresponding 3D GLTF meshes to skeletal bone sockets:
  - Weapons / Tools $\rightarrow$ `Hand_R` or `Hand_L` socket.
  - Backpacks / Quivers $\rightarrow$ `Spine` socket.
  - Helmets / Circlets $\rightarrow$ `Head` socket.
- Ensures distinct visual diversity among visible citizens without breaking the forward-pass batched draw call budget.
