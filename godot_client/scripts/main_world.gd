# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/main_world.gd
# Root scene controller for Gaia Civilization Engine Godot 4.7.2 3D client.
# Coordinates Camera, Sky/Weather, Parcels, 10k Orbital MultiMesh, Reality Bubble, Landmarks & Deities.

extends Node3D

const GodCamera = preload("res://scripts/god_camera_controller.gd")

const DEITY_TALK_RADIUS_AVATAR: float = 6.5
const DEITY_TALK_RADIUS_ORBITAL: float = 18.0
const ORBITAL_TALK_MAX_ZOOM: float = 120.0

@onready var god_camera: Node3D = $GodCameraController
@onready var sky_weather: Node3D = $SkyWeatherController
@onready var parcel_overlay: Node3D = $ParcelBorderOverlay
@onready var reality_bubble_manager: Node3D = $RealityBubbleContainer
@onready var landmarks_manager: Node3D = $LandmarksContainer
@onready var orbital_multimesh: Node3D = $OrbitalMultiMeshRenderer
@onready var divine_npcs: Node3D = $DivineNpcsManager
@onready var divine_hud: CanvasLayer = $DivineHud
@onready var two_book_modal: CanvasLayer = $TwoBookModal
@onready var god_console_overlay: CanvasLayer = $GodConsoleOverlay
@onready var entity_inspector: CanvasLayer = $EntityInspector
@onready var cities_manager: Node3D = $CitiesAndBuildingsManager
@onready var dialogue_modal: CanvasLayer = $DialogueModal
@onready var ui_state_manager: UiStateManager = $UiStateManager


func _ready() -> void:
	print("============================================================")
	print("GAIA CIVILIZATION ENGINE: 3D WORLD CLIENT INITIALIZED")
	print("Renderer: Forward+ (MSAA 2x, 2048px Shadow Atlas)")
	print("Vertical Slice C: Divine HUD, Two-Book Modals, God Console, Entity Inspector & Live Bridge Sync")
	print("Sprint 3: 5 Equidistant Gated Cities, God-Mother Palaces & Modular Housing Active")
	print("============================================================")

	# Wire Centralized UI State Manager
	if ui_state_manager:
		if two_book_modal:
			ui_state_manager.register_blocking_modal(two_book_modal)
		if dialogue_modal:
			ui_state_manager.register_blocking_modal(dialogue_modal)
		if god_console_overlay:
			ui_state_manager.register_blocking_modal(god_console_overlay)
		if entity_inspector:
			ui_state_manager.register_non_blocking_inspector(entity_inspector)

	# Wire Vertical Slice C UI interactions
	if landmarks_manager and two_book_modal:
		landmarks_manager.library_lectern_entered.connect(func(): two_book_modal.set_near_lectern(true))
		landmarks_manager.library_lectern_exited.connect(func(): two_book_modal.set_near_lectern(false))

	if divine_hud and two_book_modal:
		divine_hud.open_two_book_modal_requested.connect(func(): two_book_modal.open_modal(0))

	if divine_hud and god_console_overlay:
		divine_hud.toggle_console_requested.connect(god_console_overlay.toggle_console)

	if orbital_multimesh and divine_hud:
		orbital_multimesh.population_counts_updated.connect(divine_hud.update_population_counts)

	# Connect bridge connection signals if available
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.connect("connected_to_bridge", Callable(self, "_on_bridge_connected"))
		bridge.connect("disconnected_from_bridge", Callable(self, "_on_bridge_disconnected"))

		# If already connected, wait for live bridge sync; otherwise populate offline preview
		if not bridge.is_bridge_connected():
			_init_offline_preview()
	else:
		_init_offline_preview()


func _init_offline_preview() -> void:
	if orbital_multimesh and orbital_multimesh.has_method("populate_offline_preview"):
		orbital_multimesh.populate_offline_preview(1500)

	if reality_bubble_manager and reality_bubble_manager.has_method("populate_offline_preview"):
		reality_bubble_manager.populate_offline_preview()

	if cities_manager and cities_manager.has_method("populate_offline_preview"):
		cities_manager.populate_offline_preview()


func _on_bridge_connected() -> void:
	print("[+] WebSocket Bridge connected to Python core (ws://127.0.0.1:8765)")


func _on_bridge_disconnected() -> void:
	print("[!] WebSocket Bridge disconnected; maintaining local visual state")


func _process(_delta: float) -> void:
	if not dialogue_modal or not dialogue_modal.has_method("clear_interaction_target"):
		return
	# `is_dialogue_open` is a member variable (not a method): read it via get().
	if dialogue_modal.get("is_dialogue_open") == true:
		return
	if not god_camera:
		dialogue_modal.clear_interaction_target()
		return

	# Determine check position & radius:
	# - 3rd-person: God avatar body within 6.5m
	# - Orbital RTS (zoomed below 120m): orbital focus point within 18m
	var check_pos: Vector3 = Vector3.ZERO
	var check_radius: float = DEITY_TALK_RADIUS_AVATAR
	var cam_mode = god_camera.get("mode")
	var in_orbital: bool = (cam_mode != null and int(cam_mode) == GodCamera.CameraMode.ORBITAL_RTS)

	if in_orbital:
		var target_zoom = god_camera.get("_target_zoom")
		var orb_pos = god_camera.get("_orbital_target_pos")
		if target_zoom == null or orb_pos == null or float(target_zoom) >= ORBITAL_TALK_MAX_ZOOM:
			dialogue_modal.clear_interaction_target()
			return
		check_pos = orb_pos
		check_radius = DEITY_TALK_RADIUS_ORBITAL
	else:
		if not god_camera.avatar_body:
			dialogue_modal.clear_interaction_target()
			return
		check_pos = god_camera.avatar_body.global_position

	# 1. Nearby Deity always takes priority over the Library Lectern
	if divine_npcs and divine_npcs.has_method("get_nearest_deity"):
		var nearest_deity: Dictionary = divine_npcs.get_nearest_deity(check_pos, check_radius)
		if not nearest_deity.is_empty():
			dialogue_modal.set_interaction_target(
				"DEITY",
				nearest_deity["id"],
				nearest_deity["name"],
				nearest_deity["title"],
				nearest_deity["race"],
				nearest_deity["mood"]
			)
			return

	# 2. Near the library lectern (and no deity nearby): lectern owns [E] ([L] opens books anywhere)
	if two_book_modal and two_book_modal.get("is_near_lectern") == true:
		dialogue_modal.clear_interaction_target()
		return

	# 3. Nearest Mortal within check radius
	if reality_bubble_manager and reality_bubble_manager.has_method("get_pool"):
		var pool: Array = reality_bubble_manager.get_pool()
		var best_mortal: Node3D = null
		var best_dist_sq: float = check_radius * check_radius

		for actor in pool:
			if actor and actor.visible and actor.is_pool_active:
				var dist_sq: float = actor.global_position.distance_squared_to(check_pos)
				if dist_sq < best_dist_sq:
					best_dist_sq = dist_sq
					best_mortal = actor

		if best_mortal:
			dialogue_modal.set_interaction_target(
				"MORTAL",
				best_mortal.agent_id,
				best_mortal.full_name,
				best_mortal.role,
				best_mortal.race,
				"calm"
			)
			return

	dialogue_modal.clear_interaction_target()
