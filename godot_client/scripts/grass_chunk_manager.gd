# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/grass_chunk_manager.gd
# Camera-centered 3D grass streaming system for Gaia civilization simulation.
# Maintains a dynamic ring of MultiMeshInstance3D chunks (~85m radius around camera/God Avatar).
# Evaluates terrain elevation, slope, water level (y >= 3.5m), and road/caldera exclusion zones.

extends Node3D

class_name GrassChunkManager

const CHUNK_SIZE: float = 16.0
const STREAM_RADIUS: float = 85.0
const BLADES_PER_CHUNK: int = 140

@export var avatar_path: NodePath = NodePath("../GodCameraController/GodAvatar")

var _avatar_node: Node3D = null
var _grass_material: ShaderMaterial = null
var _grass_mesh: Mesh = null

# Active chunks: Vector2i(chunk_x, chunk_z) -> MultiMeshInstance3D
var _active_chunks: Dictionary = {}
var _chunk_pool: Array[MultiMeshInstance3D] = []
var _last_chunk_coord: Vector2i = Vector2i(999999, 999999)

# Exclusion zones cache
var _exclusion_cities: Array[Dictionary] = []


func _ready() -> void:
	TerrainHeightSampler.ensure_loaded()
	_init_exclusion_zones()
	_create_grass_resources()

	if not avatar_path.is_empty():
		_avatar_node = get_node_or_null(avatar_path) as Node3D

	_update_chunks(true)


func _init_exclusion_zones() -> void:
	var meta: Dictionary = TerrainHeightSampler.get_metadata()
	var cities: Dictionary = meta.get("ring_1_cities", {})
	_exclusion_cities.clear()
	for key in cities:
		var c: Dictionary = cities[key]
		_exclusion_cities.append({
			"pos": Vector2(float(c.get("x", 0.0)), float(c.get("z", 0.0))),
			"radius": float(c.get("radius", 280.0))
		})


func _create_grass_resources() -> void:
	# 1. Create grass sway shader material
	var shader: Shader = load("res://shaders/grass_sway.gdshader") as Shader
	if shader:
		_grass_material = ShaderMaterial.new()
		_grass_material.shader = shader
		_grass_material.set_shader_parameter("wind_speed", 1.4)
		_grass_material.set_shader_parameter("wind_strength", 0.22)
		_grass_material.set_shader_parameter("trample_radius", 2.5)
		_grass_material.set_shader_parameter("fade_start", 65.0)
		_grass_material.set_shader_parameter("fade_end", 85.0)

	# 2. Procedural crossed-quad stylized grass tuft mesh with tip vertex colors
	var st: SurfaceTool = SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)

	# 2 crossed vertical quads
	var hw: float = 0.22  # Half width
	var h: float = 0.65   # Height

	# Quad 1: Along X axis
	# Vertices: 0:(-hw, 0, 0), 1:(hw, 0, 0), 2:(hw, h, 0), 3:(-hw, h, 0)
	st.set_color(Color(0, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(-hw, 0, 0))

	st.set_color(Color(0, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(hw, 0, 0))

	st.set_color(Color(1, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(hw, h, 0))

	st.set_color(Color(1, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(-hw, h, 0))

	# Quad 2: Along Z axis
	st.set_color(Color(0, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(0, 0, -hw))

	st.set_color(Color(0, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(0, 0, hw))

	st.set_color(Color(1, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(0, h, hw))

	st.set_color(Color(1, 0, 0, 1))
	st.set_normal(Vector3(0, 1, 0))
	st.add_vertex(Vector3(0, h, -hw))

	# Indices for Quad 1 (double sided)
	st.add_index(0); st.add_index(1); st.add_index(2)
	st.add_index(0); st.add_index(2); st.add_index(3)
	st.add_index(0); st.add_index(2); st.add_index(1)
	st.add_index(0); st.add_index(3); st.add_index(2)

	# Indices for Quad 2 (double sided)
	st.add_index(4); st.add_index(5); st.add_index(6)
	st.add_index(4); st.add_index(6); st.add_index(7)
	st.add_index(4); st.add_index(6); st.add_index(5)
	st.add_index(4); st.add_index(7); st.add_index(6)

	_grass_mesh = st.commit()


var custom_focus_pos: Vector3 = Vector3.ZERO
var use_custom_focus: bool = false


func _get_avatar_pos() -> Vector3:
	if use_custom_focus:
		return custom_focus_pos
	if _avatar_node and is_instance_valid(_avatar_node):
		return _avatar_node.global_position
	if get_viewport() and get_viewport().get_camera_3d():
		return get_viewport().get_camera_3d().global_position
	return custom_focus_pos


func set_custom_focus(pos: Vector3) -> void:
	custom_focus_pos = pos
	use_custom_focus = true
	_update_chunks(true)


func _process(_delta: float) -> void:
	var avatar_pos: Vector3 = _get_avatar_pos()

	if _grass_material:
		_grass_material.set_shader_parameter("avatar_position", avatar_pos)

	var cur_chunk: Vector2i = Vector2i(
		int(floor(avatar_pos.x / CHUNK_SIZE)),
		int(floor(avatar_pos.z / CHUNK_SIZE))
	)

	if cur_chunk != _last_chunk_coord:
		_last_chunk_coord = cur_chunk
		_update_chunks(false)


func _update_chunks(force: bool) -> void:
	var avatar_pos: Vector3 = _get_avatar_pos()

	var center_chunk_x: int = int(floor(avatar_pos.x / CHUNK_SIZE))
	var center_chunk_z: int = int(floor(avatar_pos.z / CHUNK_SIZE))
	var chunk_radius: int = int(ceil(STREAM_RADIUS / CHUNK_SIZE))

	var needed_coords: Dictionary = {}
	for cx in range(center_chunk_x - chunk_radius, center_chunk_x + chunk_radius + 1):
		for cz in range(center_chunk_z - chunk_radius, center_chunk_z + chunk_radius + 1):
			var world_center_x: float = (float(cx) + 0.5) * CHUNK_SIZE
			var world_center_z: float = (float(cz) + 0.5) * CHUNK_SIZE
			var dist: float = Vector2(world_center_x - avatar_pos.x, world_center_z - avatar_pos.z).length()
			if dist <= STREAM_RADIUS:
				needed_coords[Vector2i(cx, cz)] = true

	# Recycle out-of-range chunks
	var to_remove: Array[Vector2i] = []
	for coord in _active_chunks:
		if not needed_coords.has(coord) or force:
			var mmi: MultiMeshInstance3D = _active_chunks[coord]
			mmi.visible = false
			_chunk_pool.append(mmi)
			to_remove.append(coord)

	for coord in to_remove:
		_active_chunks.erase(coord)

	# Populate newly entered chunks
	for coord in needed_coords:
		if not _active_chunks.has(coord):
			var mmi: MultiMeshInstance3D = _get_or_create_chunk_instance()
			_populate_chunk(mmi, coord.x, coord.y)
			_active_chunks[coord] = mmi


func _get_or_create_chunk_instance() -> MultiMeshInstance3D:
	if not _chunk_pool.is_empty():
		var mmi: MultiMeshInstance3D = _chunk_pool.pop_back()
		mmi.visible = true
		return mmi

	var new_mmi: MultiMeshInstance3D = MultiMeshInstance3D.new()
	var mm: MultiMesh = MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = _grass_mesh
	mm.instance_count = BLADES_PER_CHUNK
	new_mmi.multimesh = mm
	new_mmi.material_override = _grass_material
	new_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(new_mmi)
	return new_mmi


func _populate_chunk(mmi: MultiMeshInstance3D, cx: int, cz: int) -> void:
	var mm: MultiMesh = mmi.multimesh
	var origin_x: float = float(cx) * CHUNK_SIZE
	var origin_z: float = float(cz) * CHUNK_SIZE

	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	# Deterministic seed per chunk coordinate
	var seed_val: int = int((cx * 73856093) ^ (cz * 19349663)) & 0x7FFFFFFF
	rng.seed = seed_val

	var valid_count: int = 0
	for _i in range(BLADES_PER_CHUNK):
		var lx: float = rng.randf_range(0.0, CHUNK_SIZE)
		var lz: float = rng.randf_range(0.0, CHUNK_SIZE)
		var gx: float = origin_x + lx
		var gz: float = origin_z + lz

		# 1. Height and water exclusion (strictly zero blades underwater or on shoreline)
		var h: float = TerrainHeightSampler.get_height(gx, gz)
		if h < 3.5:
			continue

		# 2. Steep cliff rock exclusion
		var norm: Vector3 = TerrainHeightSampler.get_normal(gx, gz)
		if norm.y < 0.75:
			continue

		# 3. Ring 0 Acropolis plaza exclusion (r <= 360m)
		var r_origin: float = sqrt(gx * gx + gz * gz)
		if r_origin <= 360.0:
			continue

		# 4. Ring 1 City pads exclusion (r <= 280m)
		var in_city: bool = false
		for city in _exclusion_cities:
			if Vector2(gx, gz).distance_to(city["pos"]) <= city["radius"]:
				in_city = true
				break
		if in_city:
			continue

		# 5. Volcanic ashlands / Demon caldera exclusion
		if gx < -1500.0 and gz < -800.0:
			continue

		# 6. Radial Highway and Ring Road exclusion
		var d_ring: float = abs(r_origin - 1150.0)
		if d_ring < 8.0:
			continue

		# Valid blade instance
		var scale_factor: float = rng.randf_range(0.85, 1.30)
		var yaw: float = rng.randf_range(0.0, TAU)
		var basis: Basis = Basis(Vector3.UP, yaw).scaled(Vector3(scale_factor, scale_factor, scale_factor))
		var xform: Transform3D = Transform3D(basis, Vector3(gx, h, gz))

		mm.set_instance_transform(valid_count, xform)
		valid_count += 1

	mmi.set_meta("placed_blades", valid_count)

	# Collapse remaining instances to below world so they are invisible
	var collapsed: Transform3D = Transform3D(Basis(), Vector3(0.0, -999.0, 0.0))
	for j in range(valid_count, BLADES_PER_CHUNK):
		mm.set_instance_transform(j, collapsed)


func get_active_chunk_count() -> int:
	return _active_chunks.size()


func get_total_visible_blades() -> int:
	return _active_chunks.size() * BLADES_PER_CHUNK


func get_total_placed_blades() -> int:
	var total: int = 0
	for mmi in _active_chunks.values():
		total += int(mmi.get_meta("placed_blades", 0))
	return total
