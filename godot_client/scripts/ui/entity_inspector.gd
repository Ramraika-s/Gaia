# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ui/entity_inspector.gd
# Click-to-inspect panel for Reality Bubble mortals and Divine NPCs.
# Raycasts on left-click in 3D viewport, displays stats, and provides quick divine intervention buttons.

extends CanvasLayer

signal entity_inspected(info: Dictionary)

@onready var panel: PanelContainer = $InspectorPanel
@onready var title_label: Label = $InspectorPanel/VBox/TitleLabel
@onready var stats_label: Label = $InspectorPanel/VBox/StatsLabel
@onready var actions_hbox: HBoxContainer = $InspectorPanel/VBox/ActionsHBox
@onready var btn_bless: Button = $InspectorPanel/VBox/ActionsHBox/BtnBless
@onready var btn_smite: Button = $InspectorPanel/VBox/ActionsHBox/BtnSmite
@onready var btn_close: Button = $InspectorPanel/VBox/Header/BtnClose

var _current_target_id: String = ""
var _is_deity: bool = false


func _ready() -> void:
	visible = false
	btn_close.pressed.connect(close_inspector)
	btn_bless.pressed.connect(_on_bless_pressed)
	btn_smite.pressed.connect(_on_smite_pressed)


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		_perform_click_inspection(event.position)


func _perform_click_inspection(mouse_pos: Vector2) -> void:
	var viewport: Viewport = get_viewport()
	if viewport == null:
		return

	var cam: Camera3D = viewport.get_camera_3d()
	if cam == null:
		return

	var ray_origin: Vector3 = cam.project_ray_origin(mouse_pos)
	var ray_dir: Vector3 = cam.project_ray_normal(mouse_pos)

	# 1. Check Reality Bubble mortals
	var bubble: Node3D = get_tree().root.find_child("RealityBubbleContainer", true, false) as Node3D
	if bubble and bubble.has_method("get_pool"):
		var nearest_actor: Node3D = null
		var min_dist: float = 4.0  # Click tolerance in meters

		for actor in bubble.get_pool():
			if actor.is_pool_active and actor.visible:
				var actor_pos: Vector3 = actor.global_position + Vector3(0, 1.0, 0)
				# Distance from actor to ray line
				var v: Vector3 = actor_pos - ray_origin
				var proj: float = v.dot(ray_dir)
				if proj > 0:
					var nearest_point: Vector3 = ray_origin + ray_dir * proj
					var d: float = (actor_pos - nearest_point).length()
					if d < min_dist:
						min_dist = d
						nearest_actor = actor

		if nearest_actor != null:
			inspect_mortal_actor(nearest_actor)
			return

	# 2. Check Divine NPCs
	var deities: Node3D = get_tree().root.find_child("DivineNpcsManager", true, false) as Node3D
	if deities:
		var deity_ids: Array[String] = ["world_goddess", "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"]
		for did in deity_ids:
			var dnode: Node3D = deities.get_deity(did)
			if dnode:
				var dpos: Vector3 = dnode.global_position + Vector3(0, 1.5, 0)
				var v: Vector3 = dpos - ray_origin
				var proj: float = v.dot(ray_dir)
				if proj > 0:
					var nearest_pt: Vector3 = ray_origin + ray_dir * proj
					if (dpos - nearest_pt).length() < 6.0:
						inspect_deity_node(did, dnode)
						return


func inspect_mortal_actor(actor: Node3D) -> void:
	_is_deity = false
	_current_target_id = actor.agent_id

	var full_name: String = actor.full_name + " " + actor.dynasty
	if actor.is_oracle:
		full_name = "★ [ORACLE] " + full_name
	title_label.text = full_name

	var details: String = "Race: %s • Gender: %s • Stage: %s\n" % [actor.race, actor.gender, actor.stage]
	if actor.is_crying:
		details += "Status: 😭 Crying in Distress\n"
	else:
		details += "Status: Content & Peaceful\n"

	if actor.race == "DRAGON":
		details += "Dragon Form: %s\n" % actor.dragon_form

	details += "Position: (%.1f, %.1f, %.1f)" % [actor.global_position.x, actor.global_position.y, actor.global_position.z]
	stats_label.text = details

	actions_hbox.visible = true
	visible = true
	entity_inspected.emit({"type": "MORTAL", "id": actor.agent_id, "name": full_name})


func inspect_deity_node(did: String, dnode: Node3D) -> void:
	_is_deity = true
	_current_target_id = did

	var nameplate: Label3D = dnode.find_child("Nameplate", true, false) as Label3D
	var deity_text: String = nameplate.text if nameplate else did.capitalize()
	title_label.text = deity_text

	var details: String = "Deity Identifier: %s\n" % did
	details += "Domain: Divine Family of Gaia\n"
	details += "Authority: Sovereign / Sister Council\n"
	details += "Location: (%.1f, %.1f, %.1f)" % [dnode.global_position.x, dnode.global_position.y, dnode.global_position.z]
	stats_label.text = details

	actions_hbox.visible = false  # Mortals cannot smite or bless a God
	visible = true
	entity_inspected.emit({"type": "DEITY", "id": did, "name": deity_text})


func inspect_entity_data(data: Dictionary) -> void:
	_current_target_id = data.get("id", data.get("agent_id", ""))
	_is_deity = data.get("is_deity", false)

	title_label.text = data.get("name", "Unknown Entity")
	stats_label.text = data.get("details", "Inspected via Divine Radar")
	actions_hbox.visible = not _is_deity
	visible = true


func close_inspector() -> void:
	visible = false
	_current_target_id = ""


func _on_bless_pressed() -> void:
	if _current_target_id == "" or _is_deity:
		return
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_command("bless", {"agent_id": _current_target_id})
		stats_label.text += "\n[color=#44ff66]✦ BLESSED BY GOD ✦[/color]"


func _on_smite_pressed() -> void:
	if _current_target_id == "" or _is_deity:
		return
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_command("smite", {"agent_id": _current_target_id})
		stats_label.text += "\n[color=#ff4444]⚡ SMITTEN BY GOD ⚡[/color]"
		actions_hbox.visible = false
