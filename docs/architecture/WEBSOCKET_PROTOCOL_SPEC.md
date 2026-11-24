# WEBSOCKET_PROTOCOL_SPEC.md — High-Frequency Binary & JSON WebSocket Bridge Protocol

## 1. Network Architecture & Connection Parameters
The Python simulation core acts as the authoritative WebSocket server, streaming live agent kinematics, macro world states, and divine control events to the Godot 4.7.2 client (`godot_client/scripts/ws_client.gd`).

- **Endpoint:** `ws://127.0.0.1:8765`
- **Default Port:** `8765` (tunable via CLI `--port <int>`)
- **Transport Mode:** Multiplexed dual-stream over a single TCP socket:
  1. **Binary Stream (`PackedFloat32Array`):** High-frequency orbital agent state (6 float32 values per agent = 24 bytes).
  2. **Text Frames (JSON UTF-8):** Low-frequency discrete world events, UI modals, governance decrees, and 3D Reality Bubble synchronization.
- **Maximum JSON Frame Size:** 65,536 bytes (64 KB). Frames exceeding this limit are rejected with an `ERROR` response.

---

## 2. High-Frequency Binary Frame Format (Orbital God Map)

For high-altitude orbital viewing ($> 250\text{m}$), Python packs every active agent into a contiguous binary buffer evaluated directly by Godot's `OrbitalMultiMeshRenderer.gd` in a single draw call (`MultiMeshInstance3D`):

### 2.1 Stride & Layout (24 Bytes per Agent)
Each agent occupies exactly **6 contiguous 32-bit floats** (little-endian `<f4`):

| Offset (Bytes) | Float Index | Field | Data Type | Description / Range |
| :--- | :--- | :--- | :--- | :--- |
| `0..3` | `0` | `pos_x` | `float32` | World $X$ coordinate in meters ($[-4000.0, 4000.0]$). |
| `4..7` | `1` | `pos_y` | `float32` | Elevation $Y$ coordinate in meters (synced to heightmap). |
| `8..11` | `2` | `pos_z` | `float32` | World $Z$ coordinate in meters ($[-4000.0, 4000.0]$). |
| `12..15` | `3` | `race_float` | `float32` | `0.0` = `HUMAN`, `1.0` = `ELF`, `2.0` = `DRAGON`, `3.0` = `BEASTHUMAN`, `4.0` = `DEMON`. |
| `16..19` | `4` | `stage_float` | `float32` | `0.0` = `INFANT`, `1.0` = `CHILD`, `2.0` = `ADULT`, `3.0` = `ELDER`. |
| `20..23` | `5` | `flags_float` | `float32` | Bitmask packed as a float (see bit flags below). |

### 2.2 Flags Bitmask Encoding (`flags_float`)
The 6th float encodes boolean status bits for visualization:
- `Bit 0` (`1`): `FLAG_CRYING` — Infant is in root-cause distress (`distress >= 0.45`).
- `Bit 1` (`2`): `FLAG_IS_ORACLE` — Mortal Oracle/Champion of a Racial God-Mother.
- `Bit 2` (`4`): `FLAG_TRUE_DRAGON` — Dragon transformed into apex True Dragon form.
- `Bit 3` (`8`): `FLAG_INJURED` — Agent has active physical injury (`injured > 0.1`).
- `Bit 4` (`16`): `FLAG_ILLNESS` — Agent is ill from winter exposure/starvation (`illness > 0.1`).
- `Bit 5` (`32`): `FLAG_IN_COMBAT` — Engaged in active combat.
- `Bit 6` (`64`): `FLAG_PRAYING` — Performing prayer or attending an altar.

---

## 3. Server $\rightarrow$ Client JSON Messages (Python $\rightarrow$ Godot)

### 3.1 `HANDSHAKE_ACK`
Emitted immediately upon client connection:
```json
{
  "type": "HANDSHAKE_ACK",
  "status": "CONNECTED",
  "protocol_version": "4.0.0",
  "world_size": 8000.0,
  "sea_level": 0.0,
  "server_day": 14,
  "server_tick": 4200
}
```

### 3.2 `BUBBLE_SYNC` (Reality Bubble In-World Agents)
Streams the 60–120 nearest agents within God's Reality Bubble ($120\text{m}..160\text{m}$) for full skeletal animation and visual sockets:
```json
{
  "type": "BUBBLE_SYNC",
  "agents": [
    {
      "agent_id": "agt_01h8x",
      "slot_idx": 42,
      "display_name": "Aldric Ironhand",
      "dynasty": "Ironhand",
      "race": "HUMAN",
      "stage": "ADULT",
      "gender": "BOY",
      "x": 355.2,
      "y": 18.0,
      "z": 1092.4,
      "yaw": 1.57,
      "speed": 1.2,
      "current_action": "MINE_STONE_OR_ORE",
      "crying": false,
      "speech_text": "Good iron in this vein.",
      "equipped_gear": ["BLACKSMITH_HAMMER", "LEATHER_BACKPACK", "PEASANT_TUNIC"]
    }
  ]
}
```

### 3.3 `DEITY_SYNC` (Divine Beings Telemetry)
Transmits live coordinates and activities for the World Goddess and 5 Racial God-Mothers:
```json
{
  "type": "DEITY_SYNC",
  "deities": [
    {
      "id": "world_goddess",
      "name": "Celestia",
      "title": "Wife of God & World Goddess",
      "race": "DIVINE",
      "x": 0.0,
      "y": 32.0,
      "z": 12.5,
      "yaw": 3.14,
      "speed": 0.0,
      "activity": "MEDITATING",
      "speech_text": "The mortal realm rests in balance today."
    }
  ]
}
```

### 3.4 `BUILDING_SYNC` & `BUILDING_UPDATE`
Full baseline sync and dynamic updates when structures are built or upgraded:
```json
{
  "type": "BUILDING_SYNC",
  "buildings": [
    {
      "building_id": "bld_aur_001",
      "city_id": "city_aurelia",
      "building_type": "HOUSE_T2_TOWNHOUSE",
      "racial_style": "HUMAN",
      "x": 360.0,
      "y": 18.0,
      "z": 1100.0,
      "rotation_y": 0.0,
      "parcel_x": 22,
      "parcel_z": 68,
      "owner_id": "agt_01h8x",
      "owner_name": "Aldric Ironhand",
      "for_sale": false,
      "sale_price": 0.0,
      "is_frontier": false
    }
  ]
}
```

### 3.5 `BOOK_STATE_SYNC`
Synchronizes the contents of the World Library and Divine Codex for the in-game lectern modal:
```json
{
  "type": "BOOK_STATE_SYNC",
  "entries": [
    {
      "entry_id": "book_arch_01",
      "topic": "architecture_and_engineering",
      "title": "Principles of Arch Vaulting",
      "summary": "Methods for supporting stone weight across wide spans.",
      "author_id": "agt_scholar_01",
      "author_type": "MORTAL",
      "subject": "architecture_and_engineering",
      "fact_key": "arch-vaulting-basics",
      "tags": ["masonry", "engineering"],
      "mechanical_effects": {"structural_integrity_bonus": 0.15}
    }
  ],
  "proposals": [],
  "codex_entries": [],
  "codex_proposals": []
}
```

### 3.6 `WORLD_TIME_WEATHER`
Transmits continuous planetary time and macro weather cell states:
```json
{
  "type": "WORLD_TIME_WEATHER",
  "day": 14,
  "tick": 4200,
  "season": "AUTUMN",
  "time_of_day": 14200.0,
  "season_progress": 0.45,
  "weather_cells": [
    {"cell_id": "NE_HIGHLANDS", "condition": "OVERCAST", "rain": 0.2, "snow": 0.0, "fog": 0.4},
    {"cell_id": "NW_ASHLAND", "condition": "ASH_FALL", "rain": 0.0, "snow": 0.0, "fog": 0.6}
  ]
}
```

### 3.7 `SIGN_UPDATE` (WTC Market Boards)
Updates 3D hanging wooden market signs in city squares:
```json
{
  "type": "SIGN_UPDATE",
  "sign_id": "wtc_aurelia_board",
  "cpi": 1.08,
  "prices": {
    "food": 12.5,
    "wood": 8.0,
    "stone": 15.0,
    "iron": 45.0,
    "tools": 60.0
  }
}
```

### 3.8 `ALTAR_BEACON` (Prayer Pillar VFX)
Triggers skyward light pillars when $\ge 3$ mortals form a congregational prayer:
```json
{
  "type": "ALTAR_BEACON",
  "parcel_id": "22_68",
  "pos": {"x": 355.0, "y": 18.0, "z": 1090.0},
  "deity_slot": "gm_human",
  "participants_count": 42
}
```

### 3.9 `DIVINE_HUD_MESSAGE`
Direct notification to God's screen overlay:
```json
{
  "type": "DIVINE_HUD_MESSAGE",
  "speaker": "Celestia",
  "category": "WORLD_GODDESS_SUMMARY",
  "message": "Population reached 2,418. All five capitals report full granaries.",
  "realtime": true
}
```

### 3.10 `PALACE_ENTRY_REQUEST`
Alerts God of a petitioner at the Grand Divine Palace Gate:
```json
{
  "type": "PALACE_ENTRY_REQUEST",
  "request": {
    "request_id": "req_pal_001",
    "agent_id": "agt_01h8x",
    "name": "Aldric Ironhand",
    "race": "HUMAN",
    "title": "Guildmaster",
    "criminal_count": 0,
    "faith_devotion": 0.85,
    "reason": "Seeking Divine Truce ratification.",
    "status": "PENDING"
  }
}
```

### 3.11 `DIALOGUE_RESPONSE`
Returns asynchronous conversational replies from deities or mortals:
```json
{
  "type": "DIALOGUE_RESPONSE",
  "target_id": "world_goddess",
  "target_name": "Celestia",
  "title": "World Goddess",
  "race": "DIVINE",
  "mood": "calm",
  "spoken_reply": "Husband, the borders remain tranquil, though Drakonis Spire watches the eastern pass closely.",
  "action_taken": "NONE",
  "llm_backend": "QWEN3.5_4B_LLAMA_CPP"
}
```

---

## 4. Client $\rightarrow$ Server JSON Messages (Godot $\rightarrow$ Python)

### 4.1 `CLIENT_HANDSHAKE`
Initiates connection and declares client capabilities:
```json
{
  "type": "CLIENT_HANDSHAKE",
  "client": "GODOT_CLIENT",
  "version": "4.7.2",
  "include_deities": true
}
```

### 4.2 `GOD_STATE` (God Avatar Movement & Reality Bubble)
Transmits God's current 3D position and orientation:
```json
{
  "type": "GOD_STATE",
  "pos": {"x": 0.0, "y": 32.0, "z": 10.0},
  "yaw": 0.0,
  "is_god": true,
  "reality_bubble_radius": 160.0
}
```

### 4.3 `GOD_PALACE_DECISION`
God grants or denies entry to a petitioner at the palace gate:
```json
{
  "type": "GOD_PALACE_DECISION",
  "request_id": "req_pal_001",
  "decision": "GRANT"
}
```

### 4.4 `DIALOGUE_REQUEST`
Initiates conversation with a deity or mortal in the 3D world:
```json
{
  "type": "DIALOGUE_REQUEST",
  "dialogue_id": "diag_001",
  "target_type": "DEITY",
  "target_id": "world_goddess",
  "message": "Report on the state of the harvest and the 5 capitals.",
  "order": ""
}
```

### 4.5 `GOD_LIBRARY_EDIT`
Direct write/update of a World Library book by God (`bypass_god_check=True`):
```json
{
  "type": "GOD_LIBRARY_EDIT",
  "entry_id": "book_divine_01",
  "topic": "divine_theology_and_history",
  "title": "On the Balance of the Five Realms",
  "summary": "Canonical treatise on inter-sister harmony.",
  "body": "Full manuscript text...",
  "subject": "divine_theology_and_history",
  "section": "Theology",
  "fact_key": "realm-balance-treatise",
  "tags": ["doctrine", "divine"]
}
```

### 4.6 `GOD_CODEX_EDIT`, `GOD_CODEX_APPROVE`, `GOD_CODEX_REJECT`
Direct administration of the Divine Codex and live engine parameter overrides:
```json
{
  "type": "GOD_CODEX_EDIT",
  "title": "Decree of Celestial Sanctuary",
  "text": "Attacking pilgrims within 50 meters of an altar is strictly forbidden.",
  "category": "DECREE",
  "parameter_key": null,
  "parameter_value_json": null
}
```
```json
{
  "type": "GOD_CODEX_APPROVE",
  "proposal_id": "prop_codex_002"
}
```

### 4.7 `GOD_COMMAND`
Executes God Console commands directly from the Godot in-game terminal or UI modals (e.g., `speed`, `bless`, `curse`, `rewind`, `freeze_wtc`):
```json
{
  "type": "GOD_COMMAND",
  "command": "speed",
  "args": ["5.0"]
}
```
Or applying divine intervention directly from `EntityInspector`:
```json
{
  "type": "GOD_COMMAND",
  "command": "curse",
  "args": ["agt_01h8x", "SLOTH"]
}
```
Response:
```json
{
  "type": "GOD_COMMAND_RESULT",
  "command": "curse",
  "status": "SUCCESS",
  "message": "Cursed agt_01h8x with SLOTH."
}
```
