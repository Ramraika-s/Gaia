# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/terrain_height_sampler.gd
# Shared terrain elevation and slope sampling engine for Gaia.
# Computes exact O(1) bilinear interpolation matching Python's sim_core/spatial/heightmap.py.

extends Node

class_name TerrainHeightSampler

const HEIGHTMAP_PNG_PATH: String = "res://assets/terrain/world_heightmap.png"
const HEIGHTMAP_BIN_PATH: String = "res://assets/terrain/world_heightmap.bin"
const ROAD_MASK_PNG_PATH: String = "res://assets/terrain/world_road_mask.png"
const METADATA_PATH: String = "res://assets/terrain/terrain_metadata.json"

static var _is_initialized: bool = false
static var _min_x: float = -4000.0
static var _max_x: float = 4000.0
static var _min_z: float = -4000.0
static var _max_z: float = 4000.0
static var _cols: int = 1024
static var _rows: int = 1024
static var _max_height_meters: float = 180.0
static var _min_height_meters: float = -25.0
static var _scale_x: float = 1023.0 / 8000.0
static var _scale_z: float = 1023.0 / 8000.0

static var _float_data: PackedFloat32Array = PackedFloat32Array()
static var _image_data: Image = null
static var _road_mask_image: Image = null
static var _metadata: Dictionary = {}


func _enter_tree() -> void:
	ensure_loaded()


func _ready() -> void:
	ensure_loaded()


static func ensure_loaded() -> void:
	if _is_initialized:
		return

	# 1. Load Metadata
	if ResourceLoader.exists(METADATA_PATH):
		var file: FileAccess = FileAccess.open(METADATA_PATH, FileAccess.READ)
		if file:
			var json_str: String = file.get_as_text()
			var json_parser: JSON = JSON.new()
			if json_parser.parse(json_str) == OK and json_parser.data is Dictionary:
				_metadata = json_parser.data
				var bounds: Dictionary = _metadata.get("world_bounds", {})
				_min_x = float(bounds.get("min_x", -4000.0))
				_max_x = float(bounds.get("max_x", 4000.0))
				_min_z = float(bounds.get("min_z", -4000.0))
				_max_z = float(bounds.get("max_z", 4000.0))
				_cols = int(_metadata.get("resolution", 1024))
				_rows = _cols
				_max_height_meters = float(_metadata.get("max_height_meters", 180.0))
				_min_height_meters = float(_metadata.get("min_height_meters", -25.0))

	var size_x: float = _max_x - _min_x
	var size_z: float = _max_z - _min_z
	_scale_x = float(_cols - 1) / size_x if size_x > 0.0 else 1.0
	_scale_z = float(_rows - 1) / size_z if size_z > 0.0 else 1.0

	# 2. Try loading binary float32 elevation array (bit-for-bit identical to Python)
	if FileAccess.file_exists(HEIGHTMAP_BIN_PATH):
		var bf: FileAccess = FileAccess.open(HEIGHTMAP_BIN_PATH, FileAccess.READ)
		if bf:
			var bytes: PackedByteArray = bf.get_buffer(_cols * _rows * 4)
			_float_data = bytes.to_float32_array()

	# 3. Fallback / supplementary loading from world_heightmap.png
	if _float_data.size() != _cols * _rows and ResourceLoader.exists(HEIGHTMAP_PNG_PATH):
		_image_data = Image.load_from_file(HEIGHTMAP_PNG_PATH)
		if _image_data:
			_cols = _image_data.get_width()
			_rows = _image_data.get_height()
			_scale_x = float(_cols - 1) / size_x if size_x > 0.0 else 1.0
			_scale_z = float(_rows - 1) / size_z if size_z > 0.0 else 1.0

	# 4. Load Road Mask
	if ResourceLoader.exists(ROAD_MASK_PNG_PATH):
		var tex: Resource = load(ROAD_MASK_PNG_PATH)
		if tex is Texture2D:
			_road_mask_image = (tex as Texture2D).get_image()
	if _road_mask_image == null and FileAccess.file_exists(ROAD_MASK_PNG_PATH):
		_road_mask_image = Image.load_from_file(ROAD_MASK_PNG_PATH)

	_is_initialized = true
	print("[TerrainHeightSampler] Initialized: bounds=[%s..%s, %s..%s], res=%dx%d, max_h=%.1fm, float_cache=%d" % [
		_min_x, _max_x, _min_z, _max_z, _cols, _rows, _max_height_meters, _float_data.size()
	])


static func _get_raw(col: int, row: int) -> float:
	if _float_data.size() == _cols * _rows:
		return _float_data[row * _cols + col]
	if _image_data:
		return _min_height_meters + _image_data.get_pixel(col, row).r * (_max_height_meters - _min_height_meters)
	return 24.0


static func get_height(x: float, z: float) -> float:
	ensure_loaded()
	var clamped_x: float = clampf(x, _min_x, _max_x)
	var clamped_z: float = clampf(z, _min_z, _max_z)

	var col: float = (clamped_x - _min_x) * _scale_x
	var row: float = (clamped_z - _min_z) * _scale_z

	var c0: int = int(floor(col))
	var r0: int = int(floor(row))
	var c1: int = mini(c0 + 1, _cols - 1)
	var r1: int = mini(r0 + 1, _rows - 1)

	var frac_c: float = col - float(c0)
	var frac_r: float = row - float(r0)

	var h00: float = _get_raw(c0, r0)
	var h10: float = _get_raw(c1, r0)
	var h01: float = _get_raw(c0, r1)
	var h11: float = _get_raw(c1, r1)

	var h_top: float = h00 * (1.0 - frac_c) + h10 * frac_c
	var h_bot: float = h01 * (1.0 - frac_c) + h11 * frac_c
	return h_top * (1.0 - frac_r) + h_bot * frac_r


static func get_slope(x: float, z: float, step: float = 2.0) -> float:
	var h_east: float = get_height(x + step, z)
	var h_west: float = get_height(x - step, z)
	var h_north: float = get_height(x, z + step)
	var h_south: float = get_height(x, z - step)

	var dx: float = (h_east - h_west) / (2.0 * step)
	var dz: float = (h_north - h_south) / (2.0 * step)
	return sqrt(dx * dx + dz * dz)


static func get_normal(x: float, z: float, step: float = 2.0) -> Vector3:
	var h_east: float = get_height(x + step, z)
	var h_west: float = get_height(x - step, z)
	var h_north: float = get_height(x, z + step)
	var h_south: float = get_height(x, z - step)

	var dx: float = (h_east - h_west) / (2.0 * step)
	var dz: float = (h_north - h_south) / (2.0 * step)
	return Vector3(-dx, 1.0, -dz).normalized()


static func get_height_array() -> PackedFloat32Array:
	ensure_loaded()
	if _float_data.size() == _cols * _rows:
		return _float_data

	var result: PackedFloat32Array = PackedFloat32Array()
	result.resize(_cols * _rows)
	for r in range(_rows):
		for c in range(_cols):
			result[r * _cols + c] = _get_raw(c, r)
	return result


static func create_collision_shape() -> HeightMapShape3D:
	ensure_loaded()
	var shape: HeightMapShape3D = HeightMapShape3D.new()
	shape.map_width = _cols
	shape.map_depth = _rows
	shape.map_data = get_height_array()
	return shape


static func get_road_weight(x: float, z: float) -> float:
	ensure_loaded()
	if _road_mask_image == null:
		return 0.0

	var clamped_x: float = clampf(x, _min_x, _max_x)
	var clamped_z: float = clampf(z, _min_z, _max_z)

	var w: int = _road_mask_image.get_width()
	var h: int = _road_mask_image.get_height()
	if w <= 0 or h <= 0:
		return 0.0

	var col: float = (clamped_x - _min_x) / (_max_x - _min_x) * float(w - 1)
	var row: float = (clamped_z - _min_z) / (_max_z - _min_z) * float(h - 1)

	var c0: int = clampi(int(floor(col)), 0, w - 1)
	var r0: int = clampi(int(floor(row)), 0, h - 1)
	var c1: int = mini(c0 + 1, w - 1)
	var r1: int = mini(r0 + 1, h - 1)

	var frac_c: float = col - float(c0)
	var frac_r: float = row - float(r0)

	var v00: float = _road_mask_image.get_pixel(c0, r0).r
	var v10: float = _road_mask_image.get_pixel(c1, r0).r
	var v01: float = _road_mask_image.get_pixel(c0, r1).r
	var v11: float = _road_mask_image.get_pixel(c1, r1).r

	var v_top: float = v00 * (1.0 - frac_c) + v10 * frac_c
	var v_bot: float = v01 * (1.0 - frac_c) + v11 * frac_c
	return v_top * (1.0 - frac_r) + v_bot * frac_r


static func get_landmark_pad(key: String) -> Dictionary:
	ensure_loaded()
	var pads: Dictionary = _metadata.get("ring_0_acropolis", {}).get("pads", {})
	return pads.get(key, {})


static func get_metadata() -> Dictionary:
	ensure_loaded()
	return _metadata
