#!/usr/bin/env python3
"""
scripts/unpack_and_import_assets.py
Unpacks, filters, standardizes, and renames CC0 and VRM asset packs for Gaia
into godot_client/assets/ following v3.0 specs.
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_ASSETS = Path.home() / "Downloads" / "assets"
GODOT_ASSETS = REPO_ROOT / "godot_client" / "assets"


def to_snake_case(name: str) -> str:
    """Converts a filename or token to clean, lowercase snake_case."""
    base, ext = "", ""
    if "." in name:
        base, ext = name.rsplit(".", 1)
        ext = "." + ext.lower()
    else:
        base = name

    # Remove brackets, parentheses, quotes
    s = re.sub(r"[\(\)\[\]\']", "", base)
    # Replace spaces, hyphens, pluses with underscores
    s = re.sub(r"[\s\-+]+", "_", s)
    # Insert underscore before camelCase transitions
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", s)
    # Collapse multiple underscores
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s + ext


def copy_deities():
    """Copies 7 VRoid Divine Hero models and World Goddess portrait."""
    print("[*] Copying 7 Divine Hero VRM models...")
    deities_dir = GODOT_ASSETS / "deities"
    deities_dir.mkdir(parents=True, exist_ok=True)

    vrm_src = DOWNLOADS_ASSETS / "vrms"
    mappings = {
        "god.vrm": "god_avatar.vrm",
        "goddess.vrm": "world_goddess.vrm",
        "human_godmother.vrm": "gm_human.vrm",
        "elves_godmother.vrm": "gm_elf.vrm",
        "dragon_godmother.vrm": "gm_dragon.vrm",
        "beasthuman_godmother.vrm": "gm_beasthuman.vrm",
        "demon_godmother.vrm": "gm_demon.vrm",
    }

    for src_name, dst_name in mappings.items():
        src_path = vrm_src / src_name
        dst_path = deities_dir / dst_name
        if src_path.exists():
            shutil.copy2(src_path, dst_path)
            size_mb = dst_path.stat().st_size / (1024 * 1024)
            print(f"  [+] {dst_name} ({size_mb:.1f} MB)")
        else:
            print(f"  [!] Missing source: {src_path}")

    # Copy World Goddess portrait
    portrait_candidates = [
        DOWNLOADS_ASSETS / "vrms" / "goddess.png",
        DOWNLOADS_ASSETS / "goddess.png",
        Path.home() / ".local" / "share" / "Trash" / "files" / "goddess.png",
    ]
    portrait_dst = deities_dir / "world_goddess_portrait.png"
    for candidate in portrait_candidates:
        if candidate.exists():
            shutil.copy2(candidate, portrait_dst)
            print("  [+] world_goddess_portrait.png")
            break


def copy_true_dragon():
    """Copies True Dragon glb model."""
    print("[*] Copying True Dragon model...")
    mortals_dir = GODOT_ASSETS / "mortals"
    mortals_dir.mkdir(parents=True, exist_ok=True)

    src = DOWNLOADS_ASSETS / "red_dragon.glb"
    dst = mortals_dir / "base_dragon_true.glb"
    if src.exists():
        shutil.copy2(src, dst)
        size_mb = dst.stat().st_size / (1024 * 1024)
        print(f"  [+] base_dragon_true.glb ({size_mb:.1f} MB)")
    else:
        print(f"  [!] Missing True Dragon: {src}")


def fix_gltf_uris(gltf_path: Path, name_map: dict[str, str]):
    """Updates relative URIs inside a glTF JSON file to match renamed files."""
    try:
        with open(gltf_path, encoding="utf-8") as f:
            data = json.load(f)

        changed = False
        for buf in data.get("buffers", []):
            uri = buf.get("uri")
            if uri and not uri.startswith("data:"):
                orig_file = Path(uri).name
                if orig_file in name_map:
                    buf["uri"] = name_map[orig_file]
                    changed = True
                else:
                    new_uri = to_snake_case(orig_file)
                    buf["uri"] = new_uri
                    changed = True

        for img in data.get("images", []):
            uri = img.get("uri")
            if uri and not uri.startswith("data:"):
                orig_file = Path(uri).name
                if orig_file in name_map:
                    img["uri"] = name_map[orig_file]
                    changed = True
                else:
                    new_uri = to_snake_case(orig_file)
                    img["uri"] = new_uri
                    changed = True

        if changed:
            with open(gltf_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
    except Exception as e:
        print(f"  [!] Failed to update glTF URIs in {gltf_path}: {e}")


def unpack_zip_gltf_folder(
    zip_path: Path,
    source_prefix: str,
    target_dir: Path,
    include_exts: set[str] | None = None,
):
    """Unpacks a specific folder of glTF/GLB assets from a zip, renaming to snake_case."""
    if include_exts is None:
        include_exts = {".gltf", ".bin", ".png", ".glb"}
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = [
            m
            for m in zf.namelist()
            if m.startswith(source_prefix)
            and not m.endswith("/")
            and Path(m).suffix.lower() in include_exts
        ]

        # First pass: establish name mapping for files in this folder
        name_map = {}
        for m in members:
            orig_name = Path(m).name
            clean_name = to_snake_case(orig_name)
            name_map[orig_name] = clean_name

        # Extract and rename
        gltf_files = []
        for m in members:
            orig_name = Path(m).name
            clean_name = name_map[orig_name]
            dst_file = target_dir / clean_name
            with zf.open(m) as src_f, open(dst_file, "wb") as dst_f:
                shutil.copyfileobj(src_f, dst_f)
            if clean_name.endswith(".gltf"):
                gltf_files.append(dst_file)

        # Fix glTF JSON references
        for gf in gltf_files:
            fix_gltf_uris(gf, name_map)


def unpack_mortals_and_animations():
    """Unpacks mortal base rigs, outfits, animations, and monster models."""
    print("[*] Unpacking mortals, outfits, and animations...")
    races_dir = GODOT_ASSETS / "mortals" / "races"
    races_dir.mkdir(parents=True, exist_ok=True)
    outfits_dir = GODOT_ASSETS / "mortals" / "outfits"
    outfits_dir.mkdir(parents=True, exist_ok=True)
    anims_dir = GODOT_ASSETS / "mortals" / "animations"
    anims_dir.mkdir(parents=True, exist_ok=True)
    monsters_dir = GODOT_ASSETS / "mortals" / "monsters"
    monsters_dir.mkdir(parents=True, exist_ok=True)

    # 1. Fantasy Races Kit
    fr_zip = DOWNLOADS_ASSETS / "Characters - Fantasy Races Kit[Standard].zip"
    if fr_zip.exists():
        with zipfile.ZipFile(fr_zip, "r") as zf:
            prefix = "Characters - Fantasy Races Kit[Standard]/Exports/GLB (Godot-Unreal)/"
            race_map = {
                f"{prefix}Elf_Male.glb": "base_elf_male.glb",
                f"{prefix}Elf_Female.glb": "base_elf_female.glb",
                f"{prefix}Orc_Male.glb": "base_beasthuman_male.glb",
                f"{prefix}Orc_Female.glb": "base_beasthuman_female.glb",
            }
            for zpath, clean_name in race_map.items():
                if zpath in zf.namelist():
                    dst_path = races_dir / clean_name
                    with zf.open(zpath) as sf, open(dst_path, "wb") as df:
                        shutil.copyfileobj(sf, df)
                    print(f"  [+] races/{clean_name}")

    # 2. Universal Animation Library 1 & 2
    ual1_zip = DOWNLOADS_ASSETS / "Universal Animation Library[Standard].zip"
    if ual1_zip.exists():
        with zipfile.ZipFile(ual1_zip, "r") as zf:
            p1 = "Universal Animation Library[Standard]/Unreal-Godot/"
            ual1_map = {
                f"{p1}UAL1_Standard.glb": "ual1_standard.glb",
                f"{p1}UAL1_Standard_RM.glb": "ual1_standard_rm.glb",
            }
            for zpath, clean_name in ual1_map.items():
                if zpath in zf.namelist():
                    dst_path = anims_dir / clean_name
                    with zf.open(zpath) as sf, open(dst_path, "wb") as df:
                        shutil.copyfileobj(sf, df)
                    print(f"  [+] animations/{clean_name}")

    ual2_zip = DOWNLOADS_ASSETS / "Universal Animation Library 2[Standard].zip"
    if ual2_zip.exists():
        with zipfile.ZipFile(ual2_zip, "r") as zf:
            p2 = "Universal Animation Library 2[Standard]/"
            ual2_map = {
                f"{p2}Female Mannequin/Unreal-Godot/Mannequin_F.glb": (
                    races_dir / "base_human_female.glb"
                ),
                f"{p2}Unreal-Godot/UAL2_Standard.glb": (anims_dir / "ual2_standard.glb"),
                f"{p2}Unreal-Godot/UAL2_Standard_RM.glb": (anims_dir / "ual2_standard_rm.glb"),
            }
            for zpath, dst_path in ual2_map.items():
                if zpath in zf.namelist():
                    with zf.open(zpath) as sf, open(dst_path, "wb") as df:
                        shutil.copyfileobj(sf, df)
                    print(f"  [+] {dst_path.parent.name}/{dst_path.name}")

    # 3. Modular Character Outfits
    outfits_zip = DOWNLOADS_ASSETS / "Modular Character Outfits - Fantasy[Standard].zip"
    if outfits_zip.exists():
        outfits_pfx = "Modular Character Outfits - Fantasy[Standard]/Exports/glTF (Godot-Unreal)/"
        unpack_zip_gltf_folder(
            outfits_zip,
            f"{outfits_pfx}Outfits/",
            outfits_dir / "full",
        )
        unpack_zip_gltf_folder(
            outfits_zip,
            f"{outfits_pfx}Modular Parts/",
            outfits_dir / "parts",
        )
        # Extract base human male outfit as base_human_male
        male_peasant_gltf = outfits_dir / "full" / "male_peasant.gltf"
        male_peasant_bin = outfits_dir / "full" / "male_peasant.bin"
        if male_peasant_gltf.exists():
            shutil.copy2(male_peasant_gltf, races_dir / "base_human_male.gltf")
            if male_peasant_bin.exists():
                shutil.copy2(male_peasant_bin, races_dir / "male_peasant.bin")
            print("  [+] races/base_human_male.gltf")

    # 4. Ultimate Monsters (for Demon, Dino/Dragonborn, and monsters)
    monsters_zip = DOWNLOADS_ASSETS / "Ultimate Monsters-20261121T143740Z-1-001.zip"
    if monsters_zip.exists():
        with zipfile.ZipFile(monsters_zip, "r") as zf:
            for member in zf.namelist():
                if member.endswith(".gltf") or member.endswith(".png"):
                    clean_name = to_snake_case(Path(member).name)
                    # Extract to monsters dir
                    dst_path = monsters_dir / clean_name
                    with zf.open(member) as sf, open(dst_path, "wb") as df:
                        shutil.copyfileobj(sf, df)
                    # Map base_demon and base_dragon_humanoid to races dir
                    if member == "Ultimate Monsters/Big/glTF/Demon.gltf":
                        demon_dst = races_dir / "base_demon.gltf"
                        with zf.open(member) as sf, open(demon_dst, "wb") as df:
                            shutil.copyfileobj(sf, df)
                        print("  [+] races/base_demon.gltf")
                    if member == "Ultimate Monsters/Big/glTF/Dino.gltf":
                        dragon_dst = races_dir / "base_dragon_humanoid.gltf"
                        with zf.open(member) as sf, open(dragon_dst, "wb") as df:
                            shutil.copyfileobj(sf, df)
                        print("  [+] races/base_dragon_humanoid.gltf")


def unpack_buildings():
    """Unpacks medieval village, props, and dungeon kits."""
    print("[*] Unpacking buildings, props, and dungeons...")
    # 1. Medieval Village
    village_zip = DOWNLOADS_ASSETS / "Medieval Village MegaKit[Standard].zip"
    if village_zip.exists():
        unpack_zip_gltf_folder(
            village_zip,
            "Medieval Village MegaKit[Standard]/glTF/",
            GODOT_ASSETS / "buildings" / "village",
        )
        print("  [+] buildings/village/")

    # 2. Fantasy Props
    props_zip = DOWNLOADS_ASSETS / "Fantasy Props MegaKit[Standard].zip"
    if props_zip.exists():
        unpack_zip_gltf_folder(
            props_zip,
            "Exports/glTF/",
            GODOT_ASSETS / "buildings" / "props",
        )
        print("  [+] buildings/props/")

    # 3. KayKit Dungeon
    dungeon_zip = DOWNLOADS_ASSETS / "KayKit_Dungeon_Pack_1.1_FREE.zip"
    if dungeon_zip.exists():
        unpack_zip_gltf_folder(
            dungeon_zip,
            "KayKit_Dungeon_Pack_1.1_FREE/Assets/gltf/",
            GODOT_ASSETS / "buildings" / "dungeon",
        )
        print("  [+] buildings/dungeon/")


def unpack_nature():
    """Unpacks Stylized Nature kit."""
    print("[*] Unpacking nature assets...")
    nature_zip = DOWNLOADS_ASSETS / "Stylized Nature MegaKit[Standard].zip"
    if nature_zip.exists():
        unpack_zip_gltf_folder(
            nature_zip,
            "glTF/",
            GODOT_ASSETS / "nature" / "stylized",
        )
        print("  [+] nature/stylized/")


def unpack_vfx():
    """Unpacks particle sprites from Kenney Particle Pack."""
    print("[*] Unpacking VFX particles...")
    vfx_dir = GODOT_ASSETS / "vfx" / "particles"
    vfx_dir.mkdir(parents=True, exist_ok=True)

    vfx_zip = DOWNLOADS_ASSETS / "kenney_particle-pack.zip"
    if vfx_zip.exists():
        with zipfile.ZipFile(vfx_zip, "r") as zf:
            prefix = "PNG (Transparent)/"
            count = 0
            for m in zf.namelist():
                if m.startswith(prefix) and m.endswith(".png"):
                    clean_name = to_snake_case(Path(m).name)
                    dst = vfx_dir / clean_name
                    with zf.open(m) as sf, open(dst, "wb") as df:
                        shutil.copyfileobj(sf, df)
                    count += 1
            print(f"  [+] vfx/particles/ ({count} particle textures)")


def unpack_audio():
    """Unpacks audio SFX from Kenney audio packs."""
    print("[*] Unpacking audio SFX...")
    packs = [
        (DOWNLOADS_ASSETS / "kenney_rpg-audio.zip", GODOT_ASSETS / "audio" / "rpg"),
        (DOWNLOADS_ASSETS / "kenney_impact-sounds.zip", GODOT_ASSETS / "audio" / "impacts"),
        (DOWNLOADS_ASSETS / "kenney_ui-audio.zip", GODOT_ASSETS / "audio" / "ui"),
        (DOWNLOADS_ASSETS / "kenney_interface-sounds.zip", GODOT_ASSETS / "audio" / "ui"),
        (DOWNLOADS_ASSETS / "kenney_voiceover-pack-fighter.zip", GODOT_ASSETS / "audio" / "voice"),
    ]

    for zip_path, target_dir in packs:
        if zip_path.exists():
            target_dir.mkdir(parents=True, exist_ok=True)
            count = 0
            with zipfile.ZipFile(zip_path, "r") as zf:
                for m in zf.namelist():
                    if m.endswith(".ogg") or m.endswith(".wav"):
                        clean_name = to_snake_case(Path(m).name)
                        dst = target_dir / clean_name
                        with zf.open(m) as sf, open(dst, "wb") as df:
                            shutil.copyfileobj(sf, df)
                        count += 1
            print(f"  [+] audio/{target_dir.name}/ ({count} files)")


def generate_asset_manifest():
    """Generates godot_client/assets/ASSET_MANIFEST.json mapping logical roles to paths."""
    print("[*] Generating ASSET_MANIFEST.json...")
    manifest = {
        "version": "3.0.0",
        "description": "Master asset mapping for Gaia Civilization Engine Godot 4.7.2 client",
        "deities": {
            "god_avatar": "res://assets/deities/god_avatar.vrm",
            "world_goddess": "res://assets/deities/world_goddess.vrm",
            "world_goddess_portrait": "res://assets/deities/world_goddess_portrait.png",
            "gm_human": "res://assets/deities/gm_human.vrm",
            "gm_elf": "res://assets/deities/gm_elf.vrm",
            "gm_dragon": "res://assets/deities/gm_dragon.vrm",
            "gm_beasthuman": "res://assets/deities/gm_beasthuman.vrm",
            "gm_demon": "res://assets/deities/gm_demon.vrm",
        },
        "mortal_races": {
            "HUMAN": {
                "base_female": "res://assets/mortals/races/base_human_female.glb",
                "base_male": "res://assets/mortals/races/base_human_male.gltf",
            },
            "ELF": {
                "base_male": "res://assets/mortals/races/base_elf_male.glb",
                "base_female": "res://assets/mortals/races/base_elf_female.glb",
            },
            "DRAGON": {
                "humanoid_form": "res://assets/mortals/races/base_dragon_humanoid.gltf",
                "true_dragon_form": "res://assets/mortals/base_dragon_true.glb",
            },
            "BEASTHUMAN": {
                "base_male": "res://assets/mortals/races/base_beasthuman_male.glb",
                "base_female": "res://assets/mortals/races/base_beasthuman_female.glb",
            },
            "DEMON": {
                "base": "res://assets/mortals/races/base_demon.gltf",
            },
        },
        "animations": {
            "ual1_standard": "res://assets/mortals/animations/ual1_standard.glb",
            "ual1_standard_rm": "res://assets/mortals/animations/ual1_standard_rm.glb",
            "ual2_standard": "res://assets/mortals/animations/ual2_standard.glb",
            "ual2_standard_rm": "res://assets/mortals/animations/ual2_standard_rm.glb",
        },
        "directories": {
            "outfits": "res://assets/mortals/outfits/",
            "monsters": "res://assets/mortals/monsters/",
            "village_buildings": "res://assets/buildings/village/",
            "props": "res://assets/buildings/props/",
            "dungeon": "res://assets/buildings/dungeon/",
            "nature_stylized": "res://assets/nature/stylized/",
            "particles": "res://assets/vfx/particles/",
            "audio_rpg": "res://assets/audio/rpg/",
            "audio_impacts": "res://assets/audio/impacts/",
            "audio_ui": "res://assets/audio/ui/",
            "audio_voice": "res://assets/audio/voice/",
        },
    }

    manifest_path = GODOT_ASSETS / "ASSET_MANIFEST.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"  [+] Saved {manifest_path}")


def main():
    print("=" * 70)
    print("GAIA ASSET PACK UNPACKING, FILTERING & STANDARDIZED RENAMING")
    print(f"Source: {DOWNLOADS_ASSETS}")
    print(f"Target: {GODOT_ASSETS}")
    print("=" * 70)

    copy_deities()
    copy_true_dragon()
    unpack_mortals_and_animations()
    unpack_buildings()
    unpack_nature()
    unpack_vfx()
    unpack_audio()
    generate_asset_manifest()

    print("=" * 70)
    print("ALL ASSETS UNPACKED AND STANDARDIZED CLEANLY!")
    print("=" * 70)


if __name__ == "__main__":
    main()
