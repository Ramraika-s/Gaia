# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/parcel_border_overlay.gd
# Renders 16x16m chunk parcel grid and color-coded polity borders projected on terrain.

extends Node3D

const PARCEL_SIZE: float = 16.0
const GRID_RADIUS_CHUNKS: int = 14  # 29x29 chunk grid = ~464m x 464m area around God camera

@export var overlay_color: Color = Color(1.0, 1.0, 1.0, 0.22)
@export var neutral_color: Color = Color(0.2, 0.85, 0.95, 0.65)
@export var human_color: Color = Color(0.25, 0.55, 0.95, 0.65)
@export var elf_color: Color = Color(0.25, 0.85, 0.35, 0.65)
@export var dragon_color: Color = Color(0.95, 0.25, 0.25, 0.65)
@export var beast_color: Color = Color(0.95, 0.65, 0.20, 0.65)
@export var demon_color: Color = Color(0.75, 0.20, 0.90, 0.65)

var _mesh_instance: MeshInstance3D = null
var _immediate_mesh: ImmediateMesh = null
var _material: StandardMaterial3D = null
var _last_chunk_x: int = -99999
var _last_chunk_z: int = -99999

# parcel_id ("cx_cz") -> polity_type
var territory_claims: Dictionary = {}


func _ready() -> void:
	_ensure_input_action()
	_setup_mesh()
	visible = false


func _ensure_input_action() -> void:
	if not InputMap.has_action("toggle_parcel_borders"):
		InputMap.add_action("toggle_parcel_borders")
		var ev: InputEventKey = InputEventKey.new()
		ev.keycode = KEY_B
		InputMap.action_add_event("toggle_parcel_borders", ev)


func _setup_mesh() -> void:
	_immediate_mesh = ImmediateMesh.new()
	_mesh_instance = MeshInstance3D.new()
	_mesh_instance.mesh = _immediate_mesh

	_material = StandardMaterial3D.new()
	_material.shading_mode = StandardMaterial3D.SHADING_MODE_UNSHADED
	_material.vertex_color_use_as_albedo = true
	_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	_material.no_depth_test = false

	_mesh_instance.material_override = _material
	add_child(_mesh_instance)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_parcel_borders"):
		visible = not visible
		get_viewport().set_input_as_handled()


func _process(_delta: float) -> void:
	if not visible:
		return

	var cam: Camera3D = get_viewport().get_camera_3d()
	if not cam:
		return

	var cam_pos: Vector3 = cam.global_position
	var center_cx: int = int(floor(cam_pos.x / PARCEL_SIZE))
	var center_cz: int = int(floor(cam_pos.z / PARCEL_SIZE))

	if center_cx != _last_chunk_x or center_cz != _last_chunk_z:
		_last_chunk_x = center_cx
		_last_chunk_z = center_cz
		_rebuild_grid(center_cx, center_cz)


func _rebuild_grid(center_cx: int, center_cz: int) -> void:
	_immediate_mesh.clear_surfaces()
	_immediate_mesh.surface_begin(Mesh.PRIMITIVE_LINES)

	var min_cx: int = center_cx - GRID_RADIUS_CHUNKS
	var max_cx: int = center_cx + GRID_RADIUS_CHUNKS
	var min_cz: int = center_cz - GRID_RADIUS_CHUNKS
	var max_cz: int = center_cz + GRID_RADIUS_CHUNKS

	var y_offset: float = 0.25  # Slight offset above ground

	# Draw lines along X and Z
	for cx in range(min_cx, max_cx + 1):
		for cz in range(min_cz, max_cz + 1):
			var parcel_id: String = "%d_%d" % [cx, cz]
			var line_col: Color = _get_parcel_color(parcel_id)

			var x0: float = float(cx) * PARCEL_SIZE
			var x1: float = x0 + PARCEL_SIZE
			var z0: float = float(cz) * PARCEL_SIZE
			var z1: float = z0 + PARCEL_SIZE

			var y_approx: float = _sample_terrain_y(x0, z0) + y_offset

			_immediate_mesh.surface_set_color(line_col)
			_immediate_mesh.surface_add_vertex(Vector3(x0, y_approx, z0))
			_immediate_mesh.surface_add_vertex(Vector3(x1, y_approx, z0))

			_immediate_mesh.surface_set_color(line_col)
			_immediate_mesh.surface_add_vertex(Vector3(x0, y_approx, z0))
			_immediate_mesh.surface_add_vertex(Vector3(x0, y_approx, z1))

	_immediate_mesh.surface_end()


func _sample_terrain_y(x: float, z: float) -> float:
	# Central basin default is ~18.5m; smooth heuristic based on distance from center
	var dist: float = sqrt(x * x + z * z)
	if dist < 800.0:
		return 18.2
	return 18.0 + clamp((dist - 800.0) * 0.015, 0.0, 80.0)


func _get_parcel_color(parcel_id: String) -> Color:
	if territory_claims.has(parcel_id):
		var claim_type: String = str(territory_claims[parcel_id])
		match claim_type:
			"NEUTRAL_FREE_CITY": return neutral_color
			"HUMAN": return human_color
			"ELF": return elf_color
			"DRAGON": return dragon_color
			"BEASTHUMAN": return beast_color
			"DEMON": return demon_color
	return overlay_color
