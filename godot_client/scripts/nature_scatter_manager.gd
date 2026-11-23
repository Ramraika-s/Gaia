# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/nature_scatter_manager.gd
# High-performance 1-draw-call per mesh nature scatter system for Gaia 8km x 8km open world.
# Instantiates MultiMeshInstance3D nodes for stylized trees, pines, dead/twisted trees, rocks, and bushes
# distributed across Ring 2 wilderness and the 5 biomes with strict water, road, Acropolis, and city exclusion.
# Queries TerrainHeightSampler.get_height(x, z) and subtracts mesh local aabb.position.y
# to ensure zero floating assets across the entire world terrain.

extends Node3D

const ASSET_PATHS: Dictionary = {
	"common_tree": "res://assets/nature/stylized/common_tree_1.gltf",
	"pine_tree": "res://assets/nature/stylized/pine_1.gltf",
	"dead_tree": "res://assets/nature/stylized/dead_tree_1.gltf",
	"rock_1": "res://assets/nature/stylized/rock_medium_1.gltf",
	"rock_2": "res://assets/nature/stylized/rock_medium_2.gltf",
	"bush": "res://assets/nature/stylized/bush_common.gltf",
}

var _multimeshes: Dictionary = {}
var _transforms_by_type: Dictionary = {}
var _exclusion_cities: Array[Dictionary] = []


func _ready() -> void:
	_init_exclusions()
	_generate_scatter()


func _init_exclusions() -> void:
	TerrainHeightSampler.ensure_loaded()
	var meta: Dictionary = TerrainHeightSampler.get_metadata()
	var cities: Dictionary = meta.get("ring_1_cities", {})
	_exclusion_cities.clear()
	for key in cities:
		var c: Dictionary = cities[key]
		_exclusion_cities.append({
			"pos": Vector2(float(c.get("x", 0.0)), float(c.get("z", 0.0))),
			"radius": 300.0  # City pad exclusion r < 300m
		})


func _generate_scatter() -> void:
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 1337

	# Pre-extract meshes and cache their local AABB minimum Y
	var mesh_by_type: Dictionary = {}
	var min_y_by_type: Dictionary = {}
	for key in ASSET_PATHS:
		var m: Mesh = _extract_mesh(ASSET_PATHS[key])
		if m != null:
			mesh_by_type[key] = m
			min_y_by_type[key] = m.get_aabb().position.y
		else:
			min_y_by_type[key] = 0.0
			push_warning("[NatureScatter] Could not extract mesh for: " + key)

	# Collection of transforms per category
	var transforms_by_type: Dictionary = {
		"common_tree": [],
		"pine_tree": [],
		"dead_tree": [],
		"rock_1": [],
		"rock_2": [],
		"bush": [],
	}

	# 1. Inner Wilderness Ring (r = 450m .. 1050m)
	_scatter_cluster(
		transforms_by_type, min_y_by_type, rng,
		Vector2(0.0, 0.0), 450.0, 1050.0,
		{"common_tree": 220, "pine_tree": 150, "rock_1": 100, "rock_2": 80, "bush": 160}
	)

	# 2. Elf Sylvan Highlands (East)
	_scatter_cluster(
		transforms_by_type, min_y_by_type, rng,
		Vector2(2100.0, 600.0), 320.0, 1100.0,
		{"pine_tree": 240, "common_tree": 120, "rock_2": 80, "bush": 140}
	)

	# 3. Human Sunlit Plains & Frontier (South-East)
	_scatter_cluster(
		transforms_by_type, min_y_by_type, rng,
		Vector2(1200.0, 2000.0), 320.0, 1000.0,
		{"common_tree": 200, "rock_1": 60, "bush": 120}
	)

	# 4. Beasthuman Taiga & Steppes (South-West)
	_scatter_cluster(
		transforms_by_type, min_y_by_type, rng,
		Vector2(-2100.0, 1800.0), 320.0, 1100.0,
		{"pine_tree": 220, "rock_1": 90, "rock_2": 70, "bush": 110}
	)

	# 5. Demon Volcanic Ashlands (North-West)
	_scatter_cluster(
		transforms_by_type, min_y_by_type, rng,
		Vector2(-2400.0, -1650.0), 320.0, 1100.0,
		{"dead_tree": 180, "rock_1": 140, "rock_2": 110}
	)

	# 6. Dragon Obsidian Alpine Peaks (North-East)
	_scatter_cluster(
		transforms_by_type, min_y_by_type, rng,
		Vector2(2100.0, -2200.0), 320.0, 1100.0,
		{"rock_1": 150, "rock_2": 130, "pine_tree": 70}
	)

	# Build MultiMeshInstance3D for each category
	for key in ASSET_PATHS:
		var xforms: Array = transforms_by_type[key]
		if xforms.is_empty():
			continue

		var mesh: Mesh = mesh_by_type.get(key, null)
		if mesh == null:
			continue

		var mmi: MultiMeshInstance3D = MultiMeshInstance3D.new()
		mmi.name = "Scatter_" + key.capitalize()

		var mm: MultiMesh = MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = mesh
		mm.instance_count = xforms.size()

		for i in range(xforms.size()):
			mm.set_instance_transform(i, xforms[i])

		mmi.multimesh = mm
		mmi.set_meta("transforms", xforms)
		add_child(mmi)
		_multimeshes[key] = mmi

	_transforms_by_type = transforms_by_type

	var total_scatter: int = 0
	for k in transforms_by_type:
		total_scatter += transforms_by_type[k].size()
	print("[NatureScatter] Grounded %d nature assets flush with 8km x 8km terrain (zero floating, zero underwater)." % total_scatter)


func _scatter_cluster(
	targets: Dictionary,
	min_y_by_type: Dictionary,
	rng: RandomNumberGenerator,
	center: Vector2,
	min_r: float,
	max_r: float,
	counts: Dictionary
) -> void:
	for item_type in counts:
		var num: int = counts[item_type]
		var attempts: int = 0
		var placed: int = 0
		var min_y: float = min_y_by_type.get(item_type, 0.0)

		while placed < num and attempts < num * 5:
			attempts += 1
			var angle: float = rng.randf_range(0.0, TAU)
			var dist: float = rng.randf_range(min_r, max_r)
			var pos_2d: Vector2 = center + Vector2(cos(angle), sin(angle)) * dist

			# 1. Acropolis plaza exclusion (r <= 380m)
			var r_origin: float = pos_2d.length()
			if r_origin <= 380.0:
				continue

			# 2. Ring 1 City pads exclusion (r < 300m)
			var in_city: bool = false
			for city in _exclusion_cities:
				if pos_2d.distance_to(city["pos"]) < city["radius"]:
					in_city = true
					break
			if in_city:
				continue

			# 3. Ring Road exclusion (within 16m of r = 1150m)
			if abs(r_origin - 1150.0) < 16.0:
				continue

			# 4. Elevation & Ocean exclusion (strictly zero props on beaches/ocean y < 4.0m)
			var ground_y: float = TerrainHeightSampler.get_height(pos_2d.x, pos_2d.y)
			if ground_y < 4.0:
				continue

			# 5. Steep cliff exclusion
			var norm: Vector3 = TerrainHeightSampler.get_normal(pos_2d.x, pos_2d.y)
			if norm.y < 0.65:
				continue

			var scale_mult: float = rng.randf_range(0.85, 1.30)
			if item_type.begins_with("rock"):
				scale_mult = rng.randf_range(0.9, 1.6)

			var yaw: float = rng.randf_range(0.0, TAU)
			var basis: Basis = Basis(Vector3.UP, yaw)
			basis = basis.scaled(Vector3(scale_mult, scale_mult, scale_mult))

			# Query exact terrain elevation and subtract local mesh bottom offset
			var final_y: float = ground_y - (min_y * scale_mult)
			var pos_3d: Vector3 = Vector3(pos_2d.x, final_y, pos_2d.y)

			var xform: Transform3D = Transform3D(basis, pos_3d)
			targets[item_type].append(xform)
			placed += 1


func _extract_mesh(gltf_path: String) -> Mesh:
	if not ResourceLoader.exists(gltf_path):
		return null
	var packed: PackedScene = load(gltf_path)
	if not packed:
		return null
	var inst: Node = packed.instantiate()
	var found_mesh: Mesh = null
	for child in inst.get_children():
		if child is MeshInstance3D and child.mesh:
			found_mesh = child.mesh
			break
	inst.queue_free()
	return found_mesh
