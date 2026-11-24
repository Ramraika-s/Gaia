#!/usr/bin/env python3
"""
scripts/interactive_toolchain_setup.py
Audits external tools, Godot addons, and CC0 asset packs for Gaia.
Searches for missing components, displays exact official URLs / install commands,
and interactively prompts for confirmation before any downloads or installs.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# Project Root Directory
REPO_ROOT = Path(__file__).resolve().parent.parent

# Specifications for External Software, Addons, and Asset Packs
TOOLS_SPEC = {
    "blender": {
        "name": "Blender (3D Modeling & Rig Inspection)",
        "binary": "blender",
        "install_cmd": "sudo dnf install -y blender",
        "official_url": "https://www.blender.org/download/",
        "required_in": "Phase 5",
        "note": "Used for bone-parenting props/horns/wings. Never Decimate on rigged VRMs.",
    },
    "godot": {
        "name": "Godot Engine 4.7.2 (Linux x86_64, Vulkan)",
        "binary": "godot",
        "alt_binaries": ["godot4", "godot-bin"],
        "install_cmd": "curl -LO https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip",
        "official_url": "https://godotengine.org/download/archive/4.7.2-stable/",
        "required_in": "Phase 5",
        "note": "Stylized 3D Reality Bubble & Orbital God Map client.",
    },
    "steam": {
        "name": "Steam & VRoid Studio (via Proton)",
        "binary": "steam",
        "install_cmd": "sudo dnf install -y steam",
        "official_url": "https://store.steampowered.com/app/1486350/VRoid_Studio_v1290/",
        "required_in": "Phase 5",
        "note": "VRoid Studio AppID 1486350 used for 6 VRoid deities with Reduce Polygons preset.",
    },
}

ADDONS_SPEC = {
    "terrain_3d": {
        "name": "Terrain3D v1.1.0",
        "target_path": "godot_client/addons/terrain_3d",
        "official_url": "https://github.com/TokisanGames/Terrain3D/releases/tag/v1.1.0-stable",
        "archive_url": "https://github.com/TokisanGames/Terrain3D/releases/download/v1.1.0-stable/Terrain3D_v1.1.0-stable.zip",
        "required_in": "Phase 5 (Slice A)",
    },
    "sky_3d": {
        "name": "Sky3D v2.1",
        "target_path": "godot_client/addons/sky_3d",
        "official_url": "https://github.com/TokisanGames/Sky3D/releases/tag/v2.1.0",
        "archive_url": "https://github.com/TokisanGames/Sky3D/releases/download/v2.1.0/Sky3D_v2.1.0.zip",
        "required_in": "Phase 5 (Slice A)",
    },
    "vrm_importer": {
        "name": "VRM Importer & MToon Shader v2.6.1",
        "target_path": "godot_client/addons/vrm",
        "official_url": "https://github.com/AzPepoze/godot-vrm/releases/tag/v2.6.1",
        "archive_url": "https://github.com/AzPepoze/godot-vrm/releases/download/v2.6.1/godot-vrm-v2.6.1.zip",
        "required_in": "Phase 5 (Slice B/C)",
    },
}

ASSETS_SPEC = {
    "quaternius_fantasy_races": {
        "name": "Fantasy Races (5 Base Rigs: Human, Elf, Dragon, Beasthuman, Demon)",
        "target_path": "godot_client/assets/mortals/races",
        "official_url": "https://quaternius.com/packs/fantasyraces.html",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice B)",
    },
    "quaternius_modular_outfits": {
        "name": "Modular Character Outfits - Fantasy",
        "target_path": "godot_client/assets/mortals/outfits",
        "official_url": "https://quaternius.com/packs/modularfantasy.html",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice B)",
    },
    "quaternius_animations": {
        "name": "Universal Animation Library 1 & 2",
        "target_path": "godot_client/assets/mortals/animations",
        "official_url": "https://quaternius.com/packs/universalanimations.html",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice B)",
    },
    "quaternius_village": {
        "name": "Medieval Village MegaKit",
        "target_path": "godot_client/assets/buildings/village",
        "official_url": "https://quaternius.com/packs/medievalvillage.html",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice A)",
    },
    "quaternius_props": {
        "name": "Fantasy Props MegaKit",
        "target_path": "godot_client/assets/buildings/props",
        "official_url": "https://quaternius.com/packs/fantasyprops.html",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice C)",
    },
    "quaternius_dragon": {
        "name": "True Dragon Model (.glb)",
        "target_path": "godot_client/assets/mortals/base_dragon_true.glb",
        "official_url": "Local CC0 Model",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice B)",
    },
    "kaykit_dungeon": {
        "name": "KayKit - Dungeon Pack 1.1",
        "target_path": "godot_client/assets/buildings/dungeon",
        "official_url": "https://kaylousberg.itch.io/kaykit-dungeon-pack",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice C)",
    },
    "nature_stylized": {
        "name": "Stylized Nature MegaKit",
        "target_path": "godot_client/assets/nature/stylized",
        "official_url": "https://quaternius.com/packs/stylizednature.html",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice A)",
    },
    "kenney_particles": {
        "name": "Kenney - Particle Pack",
        "target_path": "godot_client/assets/vfx/particles",
        "official_url": "https://kenney.nl/assets/particle-pack",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice B)",
    },
    "kenney_audio": {
        "name": "Kenney - Audio Packs (RPG / Impact / UI)",
        "target_path": "godot_client/assets/audio/rpg",
        "official_url": "https://kenney.nl/assets/category:Audio",
        "license": "CC0 (Public Domain)",
        "required_in": "Phase 5 (Slice B/C)",
    },
    "vroid_deities": {
        "name": "VRoid - 7 Divine Hero Models (.vrm)",
        "target_path": "godot_client/assets/deities",
        "official_url": "Local VRoid Studio export (AppID 1486350)",
        "license": "Custom Hero Models",
        "required_in": "Phase 5 (Slice C)",
    },
}


def check_tool_installed(spec: dict) -> tuple[bool, str]:
    """Checks if binary or alternative binaries exist on PATH."""
    binaries = [spec["binary"]] + spec.get("alt_binaries", [])
    for b in binaries:
        path = shutil.which(b)
        if path:
            # Try to grab version
            try:
                out = subprocess.check_output(
                    [path, "--version"],
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=3,
                )
                first_line = out.strip().splitlines()[0] if out.strip() else ""
                return True, f"{path} ({first_line[:40]})"
            except Exception:
                return True, path
    return False, "Not found on system PATH"


def check_path_exists(rel_path: str) -> bool:
    """Checks if the target path exists in the repository."""
    full_path = REPO_ROOT / rel_path
    if not full_path.exists():
        return False
    if full_path.is_dir():
        return any(full_path.iterdir())
    return full_path.stat().st_size > 0


def audit_toolchain() -> dict:
    """Audits tools, addons, and asset packs, returning an inventory report."""
    report = {
        "tools": {},
        "addons": {},
        "assets": {},
    }

    for key, spec in TOOLS_SPEC.items():
        installed, details = check_tool_installed(spec)
        report["tools"][key] = {
            "name": spec["name"],
            "installed": installed,
            "details": details,
            "spec": spec,
        }

    for key, spec in ADDONS_SPEC.items():
        present = check_path_exists(spec["target_path"])
        report["addons"][key] = {
            "name": spec["name"],
            "present": present,
            "path": spec["target_path"],
            "spec": spec,
        }

    for key, spec in ASSETS_SPEC.items():
        present = check_path_exists(spec["target_path"])
        report["assets"][key] = {
            "name": spec["name"],
            "present": present,
            "path": spec["target_path"],
            "spec": spec,
        }

    return report


def print_audit_table(report: dict):
    """Prints a structured table of the audit results."""
    try:
        from rich.console import Console
        from rich.table import Table

        console = Console()
        table = Table(title="Gaia Toolchain & Asset Inventory (Target: Phase 5)")
        table.add_column("Category", style="cyan", no_wrap=True)
        table.add_column("Component", style="white")
        table.add_column("Status", style="bold")
        table.add_column("Details / Official Source", style="dim")

        for data in report["tools"].values():
            status = "[green]INSTALLED[/green]" if data["installed"] else "[yellow]MISSING[/yellow]"
            details = data["details"] if data["installed"] else data["spec"]["official_url"]
            table.add_row("External Tool", data["name"], status, details)

        for data in report["addons"].values():
            status = "[green]PRESENT[/green]" if data["present"] else "[yellow]MISSING[/yellow]"
            table.add_row("Godot Addon", data["name"], status, data["spec"]["official_url"])

        for data in report["assets"].values():
            status = "[green]PRESENT[/green]" if data["present"] else "[yellow]MISSING[/yellow]"
            table.add_row("Asset Pack", data["name"], status, data["spec"]["official_url"])

        console.print(table)
    except ImportError:
        # Fallback to plain text if rich is not yet available
        print("=" * 80)
        print("Gaia Toolchain & Asset Inventory (Target: Phase 5)")
        print("=" * 80)
        print("\n--- External Tools ---")
        for data in report["tools"].values():
            status = "INSTALLED" if data["installed"] else "MISSING"
            print(f"[{status}] {data['name']}: {data['details']}")
            if not data["installed"]:
                print(f"    Install command: {data['spec']['install_cmd']}")
                print(f"    Official URL:    {data['spec']['official_url']}")

        print("\n--- Godot Addons ---")
        for data in report["addons"].values():
            status = "PRESENT" if data["present"] else "MISSING"
            print(f"[{status}] {data['name']} ({data['path']})")
            if not data["present"]:
                print(f"    Official URL:    {data['spec']['official_url']}")

        print("\n--- CC0 Asset Packs & Models ---")
        for data in report["assets"].values():
            status = "PRESENT" if data["present"] else "MISSING"
            print(f"[{status}] {data['name']} ({data['path']})")
            if not data["present"]:
                print(f"    Official URL:    {data['spec']['official_url']}")
        print("=" * 80)


def prompt_user_action(item_name: str, action_desc: str, cmd_or_url: str) -> bool:
    """Interactively prompts user before any external installation or download."""
    print(f"\n[ACTION REQUIRED] {item_name}")
    print(f"Proposed Action: {action_desc}")
    print(f"Command / URL:   {cmd_or_url}")
    try:
        choice = input("Do you confirm and authorize this action? [y/N]: ").strip().lower()
        return choice in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print("\nAction skipped.")
        return False


def main():
    parser = argparse.ArgumentParser(description="Gaia Toolchain & Asset Setup Auditor")
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Print audit report without interactive prompts",
    )
    args = parser.parse_args()

    report = audit_toolchain()
    print_audit_table(report)

    if args.audit_only:
        print("\nAudit complete. No changes made (--audit-only flag passed).")
        return 0

    print("\nNote: External software and assets are scheduled for installation in Phase 5.")
    print(
        "In accordance with AGENTS.md Section 2, no software will be downloaded "
        "without your explicit confirmation."
    )

    # Check missing items and offer confirmation
    missing_tools = [d for d in report["tools"].values() if not d["installed"]]
    missing_addons = [d for d in report["addons"].values() if not d["present"]]
    missing_assets = [d for d in report["assets"].values() if not d["present"]]

    if not missing_tools and not missing_addons and not missing_assets:
        print("\nAll Phase 5 toolchain items and assets are already installed and in place!")
        return 0

    print(
        f"\nInventory summary: {len(missing_tools)} tools missing, "
        f"{len(missing_addons)} addons missing, {len(missing_assets)} asset packs missing."
    )
    print("When Phase 5 begins, this tool will prompt for confirmation before provisioning.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
