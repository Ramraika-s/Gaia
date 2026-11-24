# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/terrain_manager.gd
# Manages 8x8 frustum-cullable chunked terrain grid (64 tiles), mipmapped PBR textures,
# material uniforms, and exact 1024x1024 physics collision shape for Gaia.

extends Node3D

class_name TerrainManager

const CHUNKS_X: int = 8
const CHUNKS_Z: int = 8
const CHUNK_SUBDIVISIONS: int = 64

@onready var static_body: StaticBody3D = $TerrainCollision
@onready var collision_shape: CollisionShape3D = $TerrainCollision/HeightMapCollider

var _height_tex: ImageTexture = null
var _road_tex: Texture2D = null
var _detail_textures: Array[Texture2D] = []
var _shared_material: ShaderMaterial = null
var chunks: Array[MeshInstance3D] = []


func _ready() -> void:
	_setup_terrain_physics()
	_setup_terrain_chunks()


func _load_mipmapped_texture(res_path: String) -> Texture2D:
	"""Loads a texture and ensures GPU mipmaps exist to prevent distance moiré flicker."""
	if not ResourceLoader.exists(res_path):
		return null
	var raw_tex: Texture2D = load(res_path) as Texture2D
	if raw_tex == null:
		return null
	var img: Image = raw_tex.get_image()
	if img == null:
		_detail_textures.append(raw_tex)
		return raw_tex
	if not img.has_mipmaps():
		img = img.duplicate() as Image
		img.generate_mipmaps()
		var mip_tex: ImageTexture = ImageTexture.create_from_image(img)
		_detail_textures.append(mip_tex)
		return mip_tex
	_detail_textures.append(raw_tex)
	return raw_tex


func _setup_terrain_physics() -> void:
	TerrainHeightSampler.ensure_loaded()
	if not collision_shape:
		push_error("[TerrainManager] CollisionShape3D missing under TerrainCollision!")
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
	if static_body:
		static_body.position = Vector3.ZERO
	print("[TerrainManager] Collision HeightMapShape3D initialized: %dx%d scaled to %.0fx%.0fm." % [
		cols, rows, size_x, size_z
	])


func _setup_terrain_chunks() -> void:
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

	# Remove any legacy un-chunked GroundPlane if present in scene
	var legacy_ground: Node = get_node_or_null("GroundPlane")
	if legacy_ground:
		legacy_ground.queue_free()

	# Create / configure shared ShaderMaterial
	var shader: Shader = load("res://shaders/terrain_biome.gdshader") as Shader
	if not shader:
		push_error("[TerrainManager] Failed to load res://shaders/terrain_biome.gdshader!")
		return

	_shared_material = ShaderMaterial.new()
	_shared_material.shader = shader
	_detail_textures.clear()

	var bin_path: String = "res://assets/terrain/world_heightmap.bin"
	if FileAccess.file_exists(bin_path):
		var f: FileAccess = FileAccess.open(bin_path, FileAccess.READ)
		if f:
			var raw_bytes: PackedByteArray = f.get_buffer(cols * rows * 4)
			var img: Image = Image.create_from_data(cols, rows, false, Image.FORMAT_RF, raw_bytes)
			_height_tex = ImageTexture.create_from_image(img)
			_shared_material.set_shader_parameter("heightmap_texture", _height_tex)
			_shared_material.set_shader_parameter("is_raw_float_meters", true)
	elif ResourceLoader.exists("res://assets/terrain/world_heightmap.png"):
		var png_tex: Texture2D = load("res://assets/terrain/world_heightmap.png") as Texture2D
		_shared_material.set_shader_parameter("heightmap_texture", png_tex)
		_shared_material.set_shader_parameter("is_raw_float_meters", false)

	var splat_path: String = "res://assets/terrain/world_biome_splat.png"
	if FileAccess.file_exists(splat_path):
		var splat_img: Image = Image.load_from_file(ProjectSettings.globalize_path(splat_path))
		if splat_img and not splat_img.is_empty():
			_shared_material.set_shader_parameter("biome_splat_texture", ImageTexture.create_from_image(splat_img))
	elif ResourceLoader.exists(splat_path):
		var splat_tex: Texture2D = load(splat_path) as Texture2D
		_shared_material.set_shader_parameter("biome_splat_texture", splat_tex)

	var road_path: String = "res://assets/terrain/world_road_mask.png"
	if FileAccess.file_exists(road_path):
		var road_img: Image = Image.load_from_file(ProjectSettings.globalize_path(road_path))
		if road_img and not road_img.is_empty():
			_road_tex = ImageTexture.create_from_image(road_img)
			_shared_material.set_shader_parameter("road_mask_texture", _road_tex)
	elif ResourceLoader.exists(road_path):
		_road_tex = load(road_path) as Texture2D
		_shared_material.set_shader_parameter("road_mask_texture", _road_tex)

	# Bind real mipmapped PBR surface textures for roads, plazas, and cliff rock
	var road_alb: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_uneven_brick_base_color.png")
	var road_nrm: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_uneven_brick_normal.png")
	var plaza_alb: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_brick_base_color.png")
	var plaza_nrm: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_brick_normal.png")
	var rock_alb: Texture2D = _load_mipmapped_texture("res://assets/nature/stylized/rocks_diffuse.png")

	if road_alb:
		_shared_material.set_shader_parameter("road_albedo_texture", road_alb)
	if road_nrm:
		_shared_material.set_shader_parameter("road_normal_texture", road_nrm)
	if plaza_alb:
		_shared_material.set_shader_parameter("plaza_albedo_texture", plaza_alb)
	if plaza_nrm:
		_shared_material.set_shader_parameter("plaza_normal_texture", plaza_nrm)
	if rock_alb:
		_shared_material.set_shader_parameter("cliff_rock_texture", rock_alb)

	_shared_material.set_shader_parameter("world_size", Vector2(size_x, size_z))
	_shared_material.set_shader_parameter("max_height_meters", max_h)
	_shared_material.set_shader_parameter("min_height_meters", min_h)

	# Build 8x8 Grid of Frustum-Cullable Terrain Chunks
	chunks.clear()
	var chunk_w: float = size_x / float(CHUNKS_X)
	var chunk_d: float = size_z / float(CHUNKS_Z)

	for iz in range(CHUNKS_Z):
		for ix in range(CHUNKS_X):
			var c_min_x: float = min_x + float(ix) * chunk_w
			var c_min_z: float = min_z + float(iz) * chunk_d
			var center_x: float = c_min_x + chunk_w * 0.5
			var center_z: float = c_min_z + chunk_d * 0.5

			# Sample dense 17x17 elevation grid across this chunk for safe frustum AABB
			var chunk_min_y: float = 9999.0
			var chunk_max_y: float = -9999.0
			for sy in range(17):
				for sx in range(17):
					var sample_x: float = c_min_x + (float(sx) / 16.0) * chunk_w
					var sample_z: float = c_min_z + (float(sy) / 16.0) * chunk_d
					var h: float = TerrainHeightSampler.get_height(sample_x, sample_z)
					chunk_min_y = minf(chunk_min_y, h)
					chunk_max_y = maxf(chunk_max_y, h)

			var pm: PlaneMesh = PlaneMesh.new()
			pm.size = Vector2(chunk_w, chunk_d)
			pm.subdivide_width = CHUNK_SUBDIVISIONS
			pm.subdivide_depth = CHUNK_SUBDIVISIONS

			var chunk_mi: MeshInstance3D = MeshInstance3D.new()
			chunk_mi.name = "Chunk_%d_%d" % [ix, iz]
			chunk_mi.mesh = pm
			chunk_mi.material_override = _shared_material
			chunk_mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			chunk_mi.position = Vector3(center_x, 0.0, center_z)

			# Generous custom AABB padding (+/- 15m) prevents tilt-popping on steep ridges
			var aabb_y_min: float = chunk_min_y - 15.0
			var aabb_y_max: float = chunk_max_y + 15.0
			var aabb_height: float = maxf(1.0, aabb_y_max - aabb_y_min)
			chunk_mi.custom_aabb = AABB(
				Vector3(-chunk_w * 0.5, aabb_y_min, -chunk_d * 0.5),
				Vector3(chunk_w, aabb_height, chunk_d)
			)

			add_child(chunk_mi)
			chunks.append(chunk_mi)

	var total_tris: int = chunks.size() * (CHUNK_SUBDIVISIONS + 1) * (CHUNK_SUBDIVISIONS + 1) * 2
	print("[TerrainManager] Built %d terrain chunks (8x8 grid). Total terrain tris: %d (~80-130k visible)." % [
		chunks.size(), total_tris
	])


func get_chunks() -> Array[MeshInstance3D]:
	return chunks


func get_shared_material() -> ShaderMaterial:
	return _shared_material
