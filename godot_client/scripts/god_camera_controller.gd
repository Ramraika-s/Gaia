# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/god_camera_controller.gd
# Dual-Camera Controller: Orbital RTS God-View <-> 3rd-Person God Avatar Walk/Fly Mode.

extends Node3D

enum CameraMode {
	ORBITAL_RTS,
	THIRD_PERSON_AVATAR
}

const GOD_AVATAR_PATH: String = "res://assets/deities/god_avatar.vrm"
const ORBITAL_ALTITUDE_THRESHOLD: float = 250.0

@export var mode: CameraMode = CameraMode.ORBITAL_RTS
@export var move_speed: float = 30.0
@export var fast_move_multiplier: float = 3.5
@export var zoom_speed: float = 12.0
@export var min_zoom: float = 15.0
@export var max_zoom: float = 800.0

@onready var camera: Camera3D = $CameraPivot/Camera3D
@onready var camera_pivot: Node3D = $CameraPivot
@onready var avatar_root: Node3D = $AvatarRoot

var _target_pos: Vector3 = Vector3(0.0, 18.5, 0.0)
var _zoom_distance: float = 60.0
var _yaw: float = 0.0
var _pitch: float = -45.0
var _is_right_mouse_down: bool = false
var _is_flying: bool = false

var _god_avatar_instance: Node3D = null


func _ready() -> void:
	# Ensure input actions exist with sensible defaults
	_ensure_input_actions()

	# Instance God Avatar model
	_setup_god_avatar()

	# Set initial camera transform
	_update_camera_transform(true)


func _ensure_input_actions() -> void:
	if not InputMap.has_action("toggle_camera_mode"):
		InputMap.add_action("toggle_camera_mode")
		var ev: InputEventKey = InputEventKey.new()
		ev.keycode = KEY_TAB
		InputMap.action_add_event("toggle_camera_mode", ev)


func _setup_god_avatar() -> void:
	if ResourceLoader.exists(GOD_AVATAR_PATH):
		var scene: PackedScene = load(GOD_AVATAR_PATH) as PackedScene
		if scene:
			_god_avatar_instance = scene.instantiate() as Node3D
			if _god_avatar_instance:
				avatar_root.add_child(_god_avatar_instance)
				_god_avatar_instance.scale = Vector3(1.0, 1.0, 1.0)
				_god_avatar_instance.position = Vector3.ZERO

	if not _god_avatar_instance:
		# Fallback stylized golden deity marker
		var mesh_inst: MeshInstance3D = MeshInstance3D.new()
		var capsule: CapsuleMesh = CapsuleMesh.new()
		capsule.radius = 0.4
		capsule.height = 1.8
		mesh_inst.mesh = capsule
		var mat: StandardMaterial3D = StandardMaterial3D.new()
		mat.albedo_color = Color(1.0, 0.85, 0.3, 1.0)
		mat.emission_enabled = true
		mat.emission = Color(0.9, 0.7, 0.2, 1.0)
		mesh_inst.material_override = mat
		mesh_inst.position = Vector3(0.0, 0.9, 0.0)
		avatar_root.add_child(mesh_inst)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_camera_mode"):
		_toggle_mode()
		get_viewport().set_input_as_handled()
		return

	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_RIGHT:
			_is_right_mouse_down = mb.pressed
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			_zoom_distance = max(min_zoom, _zoom_distance - zoom_speed)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_zoom_distance = min(max_zoom, _zoom_distance + zoom_speed)

	elif event is InputEventMouseMotion and _is_right_mouse_down:
		var mm: InputEventMouseMotion = event as InputEventMouseMotion
		_yaw -= mm.relative.x * 0.25
		_pitch = clamp(_pitch - mm.relative.y * 0.25, -85.0, -10.0)


func _process(delta: float) -> void:
	var speed: float = move_speed
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= fast_move_multiplier

	var move_dir: Vector3 = Vector3.ZERO
	if Input.is_key_pressed(KEY_W):
		move_dir.z -= 1.0
	if Input.is_key_pressed(KEY_S):
		move_dir.z += 1.0
	if Input.is_key_pressed(KEY_A):
		move_dir.x -= 1.0
	if Input.is_key_pressed(KEY_D):
		move_dir.x += 1.0

	var yaw_rad: float = deg_to_rad(_yaw)
	var forward: Vector3 = Vector3(-sin(yaw_rad), 0.0, -cos(yaw_rad)).normalized()
	var right: Vector3 = Vector3(cos(yaw_rad), 0.0, -sin(yaw_rad)).normalized()

	var world_move: Vector3 = (right * move_dir.x + forward * move_dir.z).normalized()

	# Vertical fly / descend controls
	if Input.is_key_pressed(KEY_SPACE):
		world_move.y += 1.0
		_is_flying = true
	elif Input.is_key_pressed(KEY_CTRL) or Input.is_key_pressed(KEY_C):
		world_move.y -= 1.0

	_target_pos += world_move * speed * delta

	# Clamp world boundary limits
	_target_pos.x = clamp(_target_pos.x, -4900.0, 4900.0)
	_target_pos.z = clamp(_target_pos.z, -4900.0, 4900.0)

	# In avatar mode, keep avatar on ground or flying
	if mode == CameraMode.THIRD_PERSON_AVATAR:
		avatar_root.global_position = _target_pos
		if world_move.length_squared() > 0.001:
			var target_rot: float = atan2(-world_move.x, -world_move.z)
			avatar_root.rotation.y = lerp_angle(avatar_root.rotation.y, target_rot, 10.0 * delta)
		avatar_root.visible = true
	else:
		avatar_root.global_position = _target_pos
		avatar_root.visible = (_zoom_distance < 150.0)

	_update_camera_transform(false, delta)

	# Sync position with WebSocket bridge
	var is_orbital: bool = (_zoom_distance >= ORBITAL_ALTITUDE_THRESHOLD)
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.has_method("update_god_focus"):
		bridge.update_god_focus(_target_pos, is_orbital, _zoom_distance)


func _update_camera_transform(immediate: bool, delta: float = 0.0) -> void:
	camera_pivot.global_position = _target_pos

	var target_rot: Vector3 = Vector3(deg_to_rad(_pitch), deg_to_rad(_yaw), 0.0)
	if immediate:
		camera_pivot.rotation = target_rot
		camera.position = Vector3(0.0, 0.0, _zoom_distance)
	else:
		camera_pivot.rotation.x = lerp(camera_pivot.rotation.x, target_rot.x, 12.0 * delta)
		camera_pivot.rotation.y = lerp_angle(camera_pivot.rotation.y, target_rot.y, 12.0 * delta)
		camera.position.z = lerp(camera.position.z, _zoom_distance, 10.0 * delta)


func _toggle_mode() -> void:
	if mode == CameraMode.ORBITAL_RTS:
		mode = CameraMode.THIRD_PERSON_AVATAR
		_zoom_distance = 6.0
		_pitch = -15.0
	else:
		mode = CameraMode.ORBITAL_RTS
		_zoom_distance = 60.0
		_pitch = -45.0
