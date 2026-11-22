# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/landmarks_manager.gd
# Instantiates and manages walk-in institutional landmarks in Central Basin.
# Dynamically routes sign_update_received to WTC & Courthouse 3D boards,
# and altar_beacon_received to Grand Cathedral prayer pillars.

extends Node3D

signal library_lectern_entered
signal library_lectern_exited

const LANDMARK_SCENES: Dictionary = {
	"sanctum": "res://scenes/landmarks/world_goddess_sanctum.tscn",
	"library": "res://scenes/landmarks/world_library.tscn",
	"wtc": "res://scenes/landmarks/wtc_market.tscn",
	"courthouse": "res://scenes/landmarks/courthouse.tscn",
	"cathedral": "res://scenes/landmarks/grand_cathedral.tscn",
}

const LANDMARK_POSITIONS: Dictionary = {
	"sanctum": Vector3(0.0, 18.5, 0.0),
	"library": Vector3(100.0, 18.0, 100.0),
	"wtc": Vector3(-100.0, 18.0, 100.0),
	"courthouse": Vector3(-100.0, 18.0, -100.0),
	"cathedral": Vector3(100.0, 18.0, -100.0),
}

var _landmarks: Dictionary = {}
var price_board_label: Label3D = null
var docket_board_label: Label3D = null
var altar_beacon_node: Node3D = null
var altar_beacon_label: Label3D = null


func _ready() -> void:
	_assemble_landmarks()
	_connect_bridge_signals()


func _assemble_landmarks() -> void:
	for key in LANDMARK_SCENES:
		var path: String = LANDMARK_SCENES[key]
		if not ResourceLoader.exists(path):
			push_warning("[LandmarksManager] Landmark scene missing: " + path)
			continue

		var packed: PackedScene = load(path)
		if packed:
			var inst: Node3D = packed.instantiate()
			inst.name = key.capitalize()
			inst.position = LANDMARK_POSITIONS[key]
			add_child(inst)
			_landmarks[key] = inst

	_bind_subnodes()
	print("[LandmarksManager] Assembled 5 walk-in institutional landmarks.")


func _bind_subnodes() -> void:
	if _landmarks.has("wtc"):
		price_board_label = _landmarks["wtc"].find_child("PriceBoardLabel", true, false) as Label3D

	if _landmarks.has("courthouse"):
		docket_board_label = _landmarks["courthouse"].find_child("DocketBoardLabel", true, false) as Label3D

	if _landmarks.has("cathedral"):
		altar_beacon_node = _landmarks["cathedral"].find_child("AltarPrayerBeacon", true, false) as Node3D
		if altar_beacon_node:
			altar_beacon_label = altar_beacon_node.find_child("BeaconLabel", true, false) as Label3D

	if _landmarks.has("library"):
		var area: Area3D = _landmarks["library"].find_child("LecternTriggerArea", true, false) as Area3D
		if area:
			area.connect("body_entered", Callable(self, "_on_lectern_body_entered"))
			area.connect("body_exited", Callable(self, "_on_lectern_body_exited"))


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.connect("sign_update_received", Callable(self, "_on_sign_update_received"))
		bridge.connect("altar_beacon_received", Callable(self, "_on_altar_beacon_received"))


func _on_sign_update_received(data: Dictionary) -> void:
	var board_type: String = data.get("board", data.get("type", data.get("board_type", ""))).to_upper()

	if board_type == "WTC" or data.has("cpi"):
		update_wtc_board(data)
	elif board_type == "COURTHOUSE" or data.has("cases"):
		update_courthouse_board(data)


func update_wtc_board(data: Dictionary) -> void:
	if price_board_label == null:
		return

	var cpi: float = float(data.get("cpi", 1.0))
	var money_supply: float = float(data.get("money_supply", data.get("circulating_credits", 1000000.0)))
	var commodities: Dictionary = data.get("commodities", data.get("prices", {}))

	var grain: float = float(commodities.get("grain", 10.0 * cpi))
	var timber: float = float(commodities.get("timber", 15.0 * cpi))
	var stone: float = float(commodities.get("stone", 12.0 * cpi))
	var iron: float = float(commodities.get("iron", 25.0 * cpi))
	var herbs: float = float(commodities.get("herbs", 18.0 * cpi))
	var meat: float = float(commodities.get("meat", 20.0 * cpi))

	var text: String = "=== WORLD TRADE CENTRE (WTC) ===\n"
	text += "CPI Inflation Index: %.3f | Money Supply: %s c\n" % [cpi, String.num(money_supply, 0)]
	text += "Grain: %.1fc  •  Timber: %.1fc  •  Stone: %.1fc\n" % [grain, timber, stone]
	text += "Iron:  %.1fc  •  Herbs:  %.1fc  •  Meat:  %.1fc\n" % [iron, herbs, meat]
	text += "Reserve: 100% Closed-Loop Solvency (World Bank)"

	price_board_label.text = text


func update_courthouse_board(data: Dictionary) -> void:
	if docket_board_label == null:
		return

	var status: String = data.get("status", "Court in Order")
	var active_cases: int = int(data.get("active_cases", data.get("cases_count", 0)))
	var convictions: int = int(data.get("convictions", data.get("resolved_count", 0)))
	var polities: int = int(data.get("polities_count", 5))

	var text: String = "=== HIGH COURTHOUSE OF GAIA ===\n"
	text += "Judiciary Status: %s\n" % status
	text += "Active Cases: %d  •  Convictions: %d\n" % [active_cases, convictions]
	text += "Criminal Records: Persistent SQLite Docket\n"
	text += "Jurisdiction: %d Bordered Sovereign Polities" % polities

	docket_board_label.text = text


func _on_altar_beacon_received(data: Dictionary) -> void:
	var active: bool = data.get("active", true)
	var prayer_head: String = data.get("prayer_head", "Elder Priest")
	var faith_name: String = data.get("faith_name", "Divine Sisterhood")
	var attendees: int = int(data.get("attendees", 10))

	set_altar_beacon_active(active, prayer_head, faith_name, attendees)


func set_altar_beacon_active(active: bool, prayer_head: String = "Prayer Head", faith: String = "Faith", attendees: int = 10) -> void:
	if altar_beacon_node == null:
		return

	altar_beacon_node.visible = active
	if active and altar_beacon_label:
		altar_beacon_label.text = "✦ PRAYER BEACON ACTIVE ✦\n%s • Head: %s (%d worshippers)" % [faith, prayer_head, attendees]


func _on_lectern_body_entered(body: Node) -> void:
	print("[LandmarksManager] Mortal or God approached Library Lectern: ", body.name)
	library_lectern_entered.emit()


func _on_lectern_body_exited(body: Node) -> void:
	library_lectern_exited.emit()


func get_landmark(key: String) -> Node3D:
	return _landmarks.get(key, null)
