# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ui/entity_inspector.gd
# Click-to-inspect panel for Reality Bubble mortals and Divine NPCs.
# Raycasts on left-click in 3D viewport, displays stats, and provides quick divine intervention buttons.
# Strictly non-blocking UI inspector.

extends CanvasLayer

signal entity_inspected(info: Dictionary)

@onready var panel: PanelContainer = $InspectorPanel
@onready var title_label: Label = $InspectorPanel/VBox/TitleLabel
@onready var stats_label: RichTextLabel = $InspectorPanel/VBox/StatsLabel
@onready var btn_speak: Button = $InspectorPanel/VBox/BtnSpeak
@onready var actions_hbox: HBoxContainer = $InspectorPanel/VBox/ActionsHBox
@onready var btn_bless: Button = $InspectorPanel/VBox/ActionsHBox/BtnBless
@onready var btn_curse: Button = $InspectorPanel/VBox/ActionsHBox/BtnCurse
@onready var btn_smite: Button = $InspectorPanel/VBox/ActionsHBox/BtnSmite
@onready var btn_close: Button = $InspectorPanel/VBox/Header/BtnClose

const DEITY_IDS: Array[String] = ["world_goddess", "gm_human", "gm_elf", "gm_dragon", "gm_beasthuman", "gm_demon"]
const DEITY_BASE_TOLERANCE: float = 2.0
const DEITY_MAX_TOLERANCE: float = 12.0
const ORBITAL_ALTITUDE_M: float = 60.0

var _current_target_id: String = ""
var _is_deity: bool = false
var _current_name: String = ""
var _current_title: String = ""
var _current_race: String = ""


func _ready() -> void:
	visible = false
	btn_close.pressed.connect(close_inspector)
	btn_speak.pressed.connect(_on_speak_pressed)
	btn_bless.pressed.connect(_on_bless_pressed)
	btn_curse.pressed.connect(_on_curse_pressed)
	btn_smite.pressed.connect(_on_smite_pressed)


func is_inspector_open() -> bool:
	return visible


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var key_ev: InputEventKey = event as InputEventKey
		var is_esc: bool = (key_ev.keycode == KEY_ESCAPE or key_ev.physical_keycode == KEY_ESCAPE)
		if is_esc and visible:
			close_inspector()
			get_viewport().set_input_as_handled()
			return

	if event is InputEventMouseButton and event.pressed and event.button_index == MOUSE_BUTTON_LEFT:
		if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			return
		if UiStateManager.instance and UiStateManager.instance.is_blocking_modal_open():
			return
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

	var best_target_type: String = ""
	var best_actor: Node3D = null
	var best_deity_id: String = ""
	var best_deity_node: Node3D = null
	var min_proj: float = INF

	# 1. Check Reality Bubble mortals (tolerance 1.2m)
	var bubble: Node3D = get_tree().root.find_child("RealityBubbleContainer", true, false) as Node3D
	if bubble and bubble.has_method("get_pool"):
		for actor in bubble.get_pool():
			if actor != null and is_instance_valid(actor) and actor.is_pool_active and actor.visible:
				var actor_pos: Vector3 = actor.global_position + Vector3(0, 0.9, 0)
				var v: Vector3 = actor_pos - ray_origin
				var proj: float = v.dot(ray_dir)
				if proj > 0.0 and proj < min_proj:
					var nearest_point: Vector3 = ray_origin + ray_dir * proj
					var d: float = (actor_pos - nearest_point).length()
					if d <= 1.2:
						min_proj = proj
						best_target_type = "MORTAL"
						best_actor = actor

	# 2. Check Divine NPCs (tolerance 2.0m; widens with camera distance up to 12.0m above 60m altitude)
	var deities: Node3D = get_tree().root.find_child("DivineNpcsManager", true, false) as Node3D
	if deities:
		var high_altitude: bool = cam.global_position.y > ORBITAL_ALTITUDE_M
		for did in DEITY_IDS:
			var dnode: Node3D = deities.get_deity(did)
			if dnode and dnode.visible:
				var dpos: Vector3 = dnode.global_position + Vector3(0, 1.2, 0)
				var v: Vector3 = dpos - ray_origin
				var proj: float = v.dot(ray_dir)
				if proj > 0.0 and proj < min_proj:
					var nearest_pt: Vector3 = ray_origin + ray_dir * proj
					var d: float = (dpos - nearest_pt).length()
					var tol: float = DEITY_BASE_TOLERANCE
					if high_altitude:
						tol = clampf(v.length() * 0.06, DEITY_BASE_TOLERANCE, DEITY_MAX_TOLERANCE)
					if d <= tol:
						min_proj = proj
						best_target_type = "DEITY"
						best_deity_id = did
						best_deity_node = dnode

	if best_target_type == "MORTAL" and best_actor != null:
		inspect_mortal_actor(best_actor)
	elif best_target_type == "DEITY" and best_deity_node != null:
		inspect_deity_node(best_deity_id, best_deity_node)


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

	_current_name = actor.full_name + " " + actor.dynasty
	_current_title = actor.role
	_current_race = actor.race
	btn_speak.visible = true
	actions_hbox.visible = true
	visible = true
	if UiStateManager.instance:
		UiStateManager.instance.request_cursor_mode_refresh()
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

	var info: Dictionary = {}
	var npc_mgr: Node = get_tree().root.find_child("DivineNpcsManager", true, false)
	if npc_mgr and npc_mgr.has_method("get_deity_info"):
		info = npc_mgr.get_deity_info(did)
	_current_name = str(info.get("name", did.replace("_", " ").capitalize()))
	_current_title = str(info.get("title", "Patron Deity"))
	_current_race = str(info.get("race", "DIVINE"))

	btn_speak.visible = true  # Deities and mortals are always speakable
	actions_hbox.visible = false  # Mortals cannot smite or bless a God
	visible = true
	if UiStateManager.instance:
		UiStateManager.instance.request_cursor_mode_refresh()
	entity_inspected.emit({"type": "DEITY", "id": did, "name": deity_text})


func inspect_entity_data(data: Dictionary) -> void:
	_current_target_id = data.get("id", data.get("agent_id", ""))
	_is_deity = data.get("is_deity", false)

	title_label.text = data.get("name", "Unknown Entity")
	stats_label.text = data.get("details", "Inspected via Divine Radar")
	_current_name = str(data.get("name", "Unknown Entity"))
	_current_title = str(data.get("title", ""))
	_current_race = str(data.get("race", "DIVINE" if _is_deity else "HUMAN"))
	btn_speak.visible = _current_target_id != ""
	actions_hbox.visible = not _is_deity
	visible = true
	if UiStateManager.instance:
		UiStateManager.instance.request_cursor_mode_refresh()


func close_inspector() -> void:
	visible = false
	_current_target_id = ""
	if UiStateManager.instance:
		UiStateManager.instance.request_cursor_mode_refresh()


func _find_dialogue_modal() -> Node:
	var parent: Node = get_parent()
	if parent:
		var sibling: Node = parent.get_node_or_null("DialogueModal")
		if sibling:
			return sibling
	return get_tree().root.find_child("DialogueModal", true, false)


func _on_speak_pressed() -> void:
	if _current_target_id == "":
		return
	var modal: Node = _find_dialogue_modal()
	if modal == null or not modal.has_method("open_dialogue"):
		return
	var target_type: String = "DEITY" if _is_deity else "MORTAL"
	var tid: String = _current_target_id
	var tname: String = _current_name
	var ttitle: String = _current_title
	var trace: String = _current_race
	close_inspector()
	modal.open_dialogue(target_type, tid, tname, ttitle, trace, "calm")


func _on_bless_pressed() -> void:
	if _current_target_id == "" or _is_deity:
		return
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_command("bless", {"agent_id": _current_target_id})
		stats_label.append_text("\n[color=#44ff66]✦ BLESSED BY GOD ✦[/color]")


func _on_curse_pressed() -> void:
	if _current_target_id == "" or _is_deity:
		return
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_command("curse", {"agent_id": _current_target_id})
		stats_label.append_text("\n[color=#bf66ff]☠ CURSED BY GOD ☠[/color]")


func _on_smite_pressed() -> void:
	if _current_target_id == "" or _is_deity:
		return
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_command("smite", {"agent_id": _current_target_id})
		stats_label.append_text("\n[color=#ff4444]⚡ SMITTEN BY GOD ⚡[/color]")
		actions_hbox.visible = false
