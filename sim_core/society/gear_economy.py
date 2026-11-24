"""
sim_core/society/gear_economy.py
Modular Outfits, Accessories, and Tools/Weapons Economy.
Manages closed-loop crafting, merchant retail inventory, profession-driven purchasing,
and equipped gear synchronization for the Reality Bubble.
Follows SOCIETY_AND_GOVERNANCE_SPEC.md and Gaia v4.0 Sprint 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sim_core.schemas import AgentRecord
from sim_core.society.economy import WorldBank

GearCategory = Literal["CLOTHING", "ACCESSORY", "TOOL_WEAPON"]


@dataclass(frozen=True)
class GearItemSpec:
    item_id: str
    name: str
    category: GearCategory
    price: float
    durability: float = 100.0
    crafter_profession: str = "BLACKSMITH"  # or MERCHANT / ARTISAN
    description: str = ""


GEAR_CATALOG: dict[str, GearItemSpec] = {
    # Clothing
    "PEASANT_TUNIC": GearItemSpec(
        item_id="PEASANT_TUNIC",
        name="Peasant Tunic",
        category="CLOTHING",
        price=20.0,
        crafter_profession="MERCHANT",
        description="Durable homespun cotton tunic for agrarian labour.",
    ),
    "RANGER_CLOAK": GearItemSpec(
        item_id="RANGER_CLOAK",
        name="Ranger Cloak",
        category="CLOTHING",
        price=55.0,
        crafter_profession="MERCHANT",
        description="Weather-resistant hooded travel cloak for frontier exploration.",
    ),
    "NOBLE_GARB": GearItemSpec(
        item_id="NOBLE_GARB",
        name="Noble Garb",
        category="CLOTHING",
        price=120.0,
        crafter_profession="MERCHANT",
        description="Fine dyed silk vestments with silver threading.",
    ),
    "KNIGHT_PLATE": GearItemSpec(
        item_id="KNIGHT_PLATE",
        name="Knight Plate",
        category="CLOTHING",
        price=180.0,
        crafter_profession="BLACKSMITH",
        description="Polished steel harness crafted for palace guards and knights.",
    ),
    # Accessories
    "HOOD": GearItemSpec(
        item_id="HOOD",
        name="Leather Hood",
        category="ACCESSORY",
        price=15.0,
        crafter_profession="MERCHANT",
        description="Cured leather cowl offering warmth against mountain winds.",
    ),
    "PAULDRONS": GearItemSpec(
        item_id="PAULDRONS",
        name="Steel Pauldrons",
        category="ACCESSORY",
        price=45.0,
        crafter_profession="BLACKSMITH",
        description="Articulated shoulder armor plates.",
    ),
    "AMULET": GearItemSpec(
        item_id="AMULET",
        name="Blessed Amulet",
        category="ACCESSORY",
        price=60.0,
        crafter_profession="MERCHANT",
        description="Engraved silver talisman dedicated to the God-Mothers.",
    ),
    "LANTERN": GearItemSpec(
        item_id="LANTERN",
        name="Brass Oil Lantern",
        category="ACCESSORY",
        price=25.0,
        crafter_profession="BLACKSMITH",
        description="Enclosed brass lantern casting warm light on night roads.",
    ),
    # Tools & Weapons
    "HOE": GearItemSpec(
        item_id="HOE",
        name="Iron Farm Hoe",
        category="TOOL_WEAPON",
        price=30.0,
        crafter_profession="BLACKSMITH",
        description="Sturdy forged hoe for cultivating farmland parcels.",
    ),
    "PICKAXE": GearItemSpec(
        item_id="PICKAXE",
        name="Mining Pickaxe",
        category="TOOL_WEAPON",
        price=35.0,
        crafter_profession="BLACKSMITH",
        description="Hardened iron pick for stone and metal quarrying.",
    ),
    "HAMMER": GearItemSpec(
        item_id="HAMMER",
        name="Craftsman Hammer",
        category="TOOL_WEAPON",
        price=35.0,
        crafter_profession="BLACKSMITH",
        description="Balanced forge and construction hammer.",
    ),
    "SWORD": GearItemSpec(
        item_id="SWORD",
        name="Steel Arming Sword",
        category="TOOL_WEAPON",
        price=80.0,
        crafter_profession="BLACKSMITH",
        description="Double-edged steel blade carried by guards and knights.",
    ),
    "TOME": GearItemSpec(
        item_id="TOME",
        name="Scholarly Tome",
        category="TOOL_WEAPON",
        price=75.0,
        crafter_profession="MERCHANT",
        description="Bound vellum volume of World Library records.",
    ),
}

# Preferred gear sets by profession
PROFESSION_GEAR_PREFERENCES: dict[str, list[str]] = {
    "FARMER": ["PEASANT_TUNIC", "HOE", "LANTERN"],
    "HUNTER": ["RANGER_CLOAK", "HOOD", "LANTERN"],
    "BLACKSMITH": ["PEASANT_TUNIC", "HAMMER"],
    "BUILDER": ["PEASANT_TUNIC", "HAMMER"],
    "KNIGHT": ["KNIGHT_PLATE", "SWORD", "PAULDRONS"],
    "PALACE_KNIGHT": ["KNIGHT_PLATE", "SWORD", "PAULDRONS"],
    "CITY_GUARD": ["KNIGHT_PLATE", "SWORD", "LANTERN"],
    "SCHOLAR": ["NOBLE_GARB", "TOME", "AMULET"],
    "CLERIC": ["NOBLE_GARB", "TOME", "AMULET", "LANTERN"],
    "MERCHANT": ["NOBLE_GARB", "AMULET"],
    "CITIZEN": ["PEASANT_TUNIC", "HOOD"],
}


@dataclass
class ShopInventory:
    shop_id: str
    owner_id: str
    city_id: str
    stock: dict[str, int] = field(default_factory=dict)
    treasury_credits: float = 200.0


class GearEconomyEngine:
    """
    Manages crafting, shop retail stock, and autonomous purchasing of modular gear.
    All transactions conserve credits strictly via WorldBank double-entry transfers.
    """

    def __init__(self, engine: Any = None) -> None:
        self.engine = engine
        self.shops: dict[str, ShopInventory] = {}
        self.total_crafted_items: int = 0
        self.total_retail_sales: int = 0

    def craft_item(
        self,
        crafter: AgentRecord,
        item_id: str,
        bank: WorldBank,
    ) -> bool:
        """
        Crafter (Blacksmith or Merchant) invests material costs to forge/tailor gear.
        Materials cost is 40% of retail price, transferred to Bank.
        """
        if item_id not in GEAR_CATALOG:
            return False

        spec = GEAR_CATALOG[item_id]
        materials_cost = round(spec.price * 0.40, 2)

        ok, _ = bank.transfer_credits(
            sender=crafter,
            receiver=bank,
            amount=materials_cost,
            memo=f"CRAFT_MATERIALS_{item_id}",
        )
        if not ok:
            return False

        # Add to crafter's shop or personal inventory
        shop_id = f"shop_{crafter.agent_id}"
        if shop_id not in self.shops:
            self.shops[shop_id] = ShopInventory(
                shop_id=shop_id,
                owner_id=crafter.agent_id,
                city_id=getattr(crafter, "settlement_id", "aurelia") or "aurelia",
            )

        shop = self.shops[shop_id]
        shop.stock[item_id] = shop.stock.get(item_id, 0) + 1
        self.total_crafted_items += 1
        return True

    def purchase_and_equip(
        self,
        buyer: AgentRecord,
        item_id: str,
        seller: Any,
        bank: WorldBank,
    ) -> bool:
        """
        Autonomous purchase of gear item with strict double-entry credit transfer.
        Equips onto buyer with slot conflict replacement.
        """
        if item_id not in GEAR_CATALOG:
            return False

        spec = GEAR_CATALOG[item_id]
        price = spec.price

        ok, _ = bank.transfer_credits(
            sender=buyer,
            receiver=seller,
            amount=price,
            memo=f"BUY_GEAR_{item_id}",
        )
        if not ok:
            return False

        self._equip_item_to_agent(buyer, item_id)
        self.total_retail_sales += 1
        return True

    def _equip_item_to_agent(self, agent: AgentRecord, item_id: str) -> None:
        """Equips an item onto an agent, resolving slot category limits."""
        if item_id not in GEAR_CATALOG:
            return

        spec = GEAR_CATALOG[item_id]
        equipped = list(getattr(agent, "equipped_gear", []))

        # Check existing items in the same slot
        if spec.category == "CLOTHING":
            # Max 1 clothing: remove any existing clothing
            equipped = [
                i for i in equipped if i in GEAR_CATALOG and GEAR_CATALOG[i].category != "CLOTHING"
            ]
            equipped.append(item_id)
        elif spec.category == "TOOL_WEAPON":
            # Max 1 tool/weapon: remove existing tool/weapon
            equipped = [
                i
                for i in equipped
                if i in GEAR_CATALOG and GEAR_CATALOG[i].category != "TOOL_WEAPON"
            ]
            equipped.append(item_id)
        elif spec.category == "ACCESSORY":
            # Max 2 accessories
            accessories = [
                i for i in equipped if i in GEAR_CATALOG and GEAR_CATALOG[i].category == "ACCESSORY"
            ]
            if len(accessories) >= 2 and item_id not in accessories:
                # Replace oldest accessory
                oldest = accessories[0]
                equipped.remove(oldest)
            if item_id not in equipped:
                equipped.append(item_id)

        agent.equipped_gear = equipped

    def step_gear_economy(
        self,
        agents: dict[str, AgentRecord],
        bank: WorldBank,
        current_tick: int,
    ) -> list[dict[str, Any]]:
        """
        Steps the gear economy during civic ticks:
        1. Craftsmen forge/tailor stock when low.
        2. Mortals inspect needs matching profession and wealth, purchasing gear.
        3. Night travelers acquire lanterns.
        """
        events: list[dict[str, Any]] = []

        # 1. Craftsmen Stocking
        for agent in agents.values():
            if not agent.alive or agent.stage != "ADULT":
                continue
            role = getattr(agent, "role", "CITIZEN").upper()

            if role in ("BLACKSMITH", "MERCHANT") and agent.credits >= 60.0:
                # Determine what to craft
                target_items = (
                    ["SWORD", "HAMMER", "HOE", "KNIGHT_PLATE", "LANTERN", "PAULDRONS"]
                    if role == "BLACKSMITH"
                    else [
                        "PEASANT_TUNIC",
                        "RANGER_CLOAK",
                        "NOBLE_GARB",
                        "TOME",
                        "AMULET",
                        "HOOD",
                        "SWORD",
                        "HOE",
                        "KNIGHT_PLATE",
                        "LANTERN",
                    ]
                )
                for item_id in target_items:
                    shop_id = f"shop_{agent.agent_id}"
                    shop = self.shops.get(shop_id, ShopInventory(shop_id, agent.agent_id, "city"))
                    curr_stock = shop.stock.get(item_id, 0)
                    if curr_stock < 2:
                        self.craft_item(agent, item_id, bank)
                        break

        # 2. Mortals Purchasing Gear matching Profession & Wealth
        for agent in agents.values():
            if not agent.alive or agent.stage not in ("ADULT", "ELDER"):
                continue

            role = getattr(agent, "role", "CITIZEN").upper()
            default_pref = PROFESSION_GEAR_PREFERENCES["CITIZEN"]
            prefs = list(PROFESSION_GEAR_PREFERENCES.get(role, default_pref))

            # Wealthy citizens upgrade to NOBLE_GARB
            if agent.credits >= 250.0 and "NOBLE_GARB" not in prefs:
                prefs.append("NOBLE_GARB")

            current_gear = set(getattr(agent, "equipped_gear", []))

            for item_id in prefs:
                if item_id in current_gear:
                    continue

                spec = GEAR_CATALOG[item_id]
                # Only buy if agent can comfortably afford it (keep 30 cr savings)
                if agent.credits >= spec.price + 30.0:
                    # Find a seller shop or World Bank escrow
                    seller: Any = bank
                    for shop in self.shops.values():
                        if shop.stock.get(item_id, 0) > 0:
                            if shop.owner_id in agents and agents[shop.owner_id].alive:
                                seller = agents[shop.owner_id]
                                shop.stock[item_id] -= 1
                                break

                    ok = self.purchase_and_equip(agent, item_id, seller, bank)
                    if ok:
                        events.append(
                            {
                                "type": "GEAR_PURCHASED",
                                "agent_id": agent.agent_id,
                                "item_id": item_id,
                                "price": spec.price,
                                "tick": current_tick,
                            }
                        )
                    break  # One gear purchase per tick

        return events
