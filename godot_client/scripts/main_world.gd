# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/main_world.gd
# Root scene controller for Gaia Civilization Engine Godot 4.7.2 3D client.
# Coordinates Camera, Sky/Weather, Parcels, 10k Orbital MultiMesh, Reality Bubble, Landmarks & Deities.

extends Node3D

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


func _ready() -> void:
	print("============================================================")
	print("GAIA CIVILIZATION ENGINE: 3D WORLD CLIENT INITIALIZED")
	print("Renderer: Forward+ (MSAA 2x, 2048px Shadow Atlas)")
	print("Vertical Slice C: Divine HUD, Two-Book Modals, God Console, Entity Inspector & Live Bridge Sync")
	print("============================================================")

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


func _on_bridge_connected() -> void:
	print("[+] WebSocket Bridge connected to Python core (ws://127.0.0.1:8765)")


func _on_bridge_disconnected() -> void:
	print("[!] WebSocket Bridge disconnected; maintaining local visual state")
