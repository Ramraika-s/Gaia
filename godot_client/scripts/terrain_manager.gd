# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/terrain_manager.gd
# Manages displaced 1024x1024 8km x 8km terrain mesh, material uniforms, and matching physics collider.

extends Node3D

@onready var ground_plane: MeshInstance3D = $GroundPlane
@onready var static_body: StaticBody3D = $TerrainCollision
@onready var collision_shape: CollisionShape3D = $TerrainCollision/HeightMapCollider

var _height_tex: ImageTexture = null
var _road_tex: Texture2D = null


func _ready() -> void:
	_setup_terrain_physics()
	_setup_terrain_material()


func _setup_terrain_physics() -> void:
	TerrainHeightSampler.ensure_loaded()
	if not collision_shape:
		return

	var meta: Dictionary = TerrainHeightSampler.get_metadata()
	var bounds: Dictionary = meta.get("world_bounds", {})
	var min_x: float = float(bounds.get("min_x", -4000.0))
	var max_x: float = float(bounds.get("max_x", 4000.0))
	var min_z: float = float(bounds.get("min_z", -4000.0))
	var max_z: float = float(bounds.get("max_z", 4000.0))
	var cols: int = int(meta.get("resolution", 1024))
	var rows: int = cols

	var size_x: float = max_x - min_x
	var size_z: float = max_z - min_z

	var shape: HeightMapShape3D = TerrainHeightSampler.create_collision_shape()
	collision_shape.shape = shape
	var sx: float = size_x / float(cols - 1)
	var sz: float = size_z / float(rows - 1)
	collision_shape.scale = Vector3(sx, 1.0, sz)
	collision_shape.position = Vector3.ZERO
	static_body.position = Vector3.ZERO
	print("[TerrainManager] Collision HeightMapShape3D initialized: %dx%d scaled to %.0fx%.0fm." % [
		cols, rows, size_x, size_z
	])


func _setup_terrain_material() -> void:
	if not ground_plane:
		return

	TerrainHeightSampler.ensure_loaded()
	var meta: Dictionary = TerrainHeightSampler.get_metadata()
	var bounds: Dictionary = meta.get("world_bounds", {})
	var min_x: float = float(bounds.get("min_x", -4000.0))
	var max_x: float = float(bounds.get("max_x", 4000.0))
	var min_z: float = float(bounds.get("min_z", -4000.0))
	var max_z: float = float(bounds.get("max_z", 4000.0))
	var cols: int = int(meta.get("resolution", 1024))
	var rows: int = cols
	var max_h: float = float(meta.get("max_height_meters", 180.0))
	var min_h: float = float(meta.get("min_height_meters", -25.0))

	var size_x: float = max_x - min_x
	var size_z: float = max_z - min_z

	# Ensure custom AABB covers full terrain vertical bounds so peaks/oceans are never frustum-culled
	ground_plane.custom_aabb = AABB(Vector3(min_x, -50.0, min_z), Vector3(size_x, 250.0, size_z))
	ground_plane.position = Vector3.ZERO

	# Update plane mesh size if plane mesh is used
	if ground_plane.mesh and ground_plane.mesh is PlaneMesh:
		var pm: PlaneMesh = ground_plane.mesh as PlaneMesh
		pm.size = Vector2(size_x, size_z)
		pm.subdivide_width = cols - 1
		pm.subdivide_depth = rows - 1

	var mat: ShaderMaterial = null
	if ground_plane.material_override is ShaderMaterial:
		mat = ground_plane.material_override as ShaderMaterial
	elif ground_plane.mesh and ground_plane.mesh.material is ShaderMaterial:
		mat = ground_plane.mesh.material as ShaderMaterial

	if mat == null:
		var shader: Shader = load("res://shaders/terrain_biome.gdshader") as Shader
		if shader:
			mat = ShaderMaterial.new()
			mat.shader = shader
			ground_plane.material_override = mat

	if mat == null:
		return

	var bin_path: String = "res://assets/terrain/world_heightmap.bin"
	if FileAccess.file_exists(bin_path):
		var f: FileAccess = FileAccess.open(bin_path, FileAccess.READ)
		if f:
			var raw_bytes: PackedByteArray = f.get_buffer(cols * rows * 4)
			var img: Image = Image.create_from_data(cols, rows, false, Image.FORMAT_RF, raw_bytes)
			_height_tex = ImageTexture.create_from_image(img)
			mat.set_shader_parameter("heightmap_texture", _height_tex)
			mat.set_shader_parameter("is_raw_float_meters", true)
	else:
		if ResourceLoader.exists("res://assets/terrain/world_heightmap.png"):
			var png_tex: Texture2D = load("res://assets/terrain/world_heightmap.png") as Texture2D
			mat.set_shader_parameter("heightmap_texture", png_tex)
			mat.set_shader_parameter("is_raw_float_meters", false)

	if ResourceLoader.exists("res://assets/terrain/world_biome_splat.png"):
		var splat_tex: Texture2D = load("res://assets/terrain/world_biome_splat.png") as Texture2D
		mat.set_shader_parameter("biome_splat_texture", splat_tex)

	if ResourceLoader.exists("res://assets/terrain/world_road_mask.png"):
		_road_tex = load("res://assets/terrain/world_road_mask.png") as Texture2D
		mat.set_shader_parameter("road_mask_texture", _road_tex)

	mat.set_shader_parameter("world_size", Vector2(size_x, size_z))
	mat.set_shader_parameter("max_height_meters", max_h)
	mat.set_shader_parameter("min_height_meters", min_h)
	print("[TerrainManager] Terrain material uniforms bound: size=%.0fx%.0fm, res=%dx%d." % [
		size_x, size_z, cols, rows
	])
