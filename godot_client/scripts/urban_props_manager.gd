# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/urban_props_manager.gd
# 1-draw-call GPU-instanced urban streetscapes, streetlamps, market clutter,
# racial boulevard foliage, and Acropolis Knight Avenue ceremonial colonnades.

extends Node3D

const ASSET_PATHS: Dictionary = {
	"pillar": "res://assets/buildings/dungeon/pillar_decorated.gltf",
	"banner": "res://assets/buildings/dungeon/banner_pattern_a_yellow.gltf",
	"brazier": "res://assets/buildings/props/candle_stick_stand.gltf",
	"stall": "res://assets/buildings/props/stall_empty.gltf",
	"stall_cart": "res://assets/buildings/props/stall_cart_empty.gltf",
	"wagon": "res://assets/buildings/village/prop_wagon.gltf",
	"barrel": "res://assets/buildings/props/barrel_apples.gltf",
	"crates": "res://assets/buildings/dungeon/crates_stacked.gltf",
	"bench": "res://assets/buildings/props/bench.gltf",
	"common_tree": "res://assets/nature/stylized/common_tree_1.gltf",
	"pine_tree": "res://assets/nature/stylized/pine_1.gltf",
	"dead_tree": "res://assets/nature/stylized/dead_tree_1.gltf",
	"rock_obelisk": "res://assets/nature/stylized/rock_medium_1.gltf",
}

const GLOW_SHADER_PATH: String = "res://shaders/emissive_window.gdshader"
const POOL_SHADER_PATH: String = "res://shaders/lantern_light_pool.gdshader"

var _cities_mgr: Node = null
var _props_root: Node3D = null
var _mesh_cache: Dictionary = {}
var _min_y_cache: Dictionary = {}
var _lantern_post_mesh: Mesh = null
var _lantern_bulb_mesh: Mesh = null
var _lantern_pool_mesh: Mesh = null
var _flame_orb_mesh: Mesh = null


func _ready() -> void:
	TerrainHeightSampler.ensure_loaded()
	_props_root = Node3D.new()
	_props_root.name = "UrbanPropsRoot"
	add_child(_props_root)

	_prepare_custom_meshes()
	_cities_mgr = get_parent().get_node_or_null("CitiesAndBuildingsManager")
	if _cities_mgr and _cities_mgr.has_signal("buildings_populated"):
		_cities_mgr.connect("buildings_populated", Callable(self, "rebuild_urban_props"))

	call_deferred("_initial_build_if_ready")


func _initial_build_if_ready() -> void:
	if _props_root and _props_root.get_child_count() == 0:
		rebuild_urban_props()


func rebuild_urban_props() -> void:
	if not _props_root:
		return
	for child in _props_root.get_children():
		child.queue_free()

	TerrainHeightSampler.ensure_loaded()
	var footprints: Array[Dictionary] = []
	if _cities_mgr and _cities_mgr.has_method("get_building_footprints"):
		footprints = _cities_mgr.get_building_footprints()

	var meta: Dictionary = TerrainHeightSampler.get_metadata()
	var cities: Dictionary = meta.get("ring_1_cities", {})

	var xforms: Dictionary = {
		"lantern_post": [],
		"lantern_bulb": [],
		"lantern_pool": [],
		"pillar": [],
		"banner": [],
		"brazier": [],
		"flame": [],
		"stall": [],
		"stall_cart": [],
		"wagon": [],
		"barrel": [],
		"crates": [],
		"bench": [],
		"common_tree": [],
		"pine_tree": [],
		"dead_tree": [],
		"rock_obelisk": [],
	}

	_populate_acropolis_avenues(xforms, cities, footprints)
	_populate_radial_highways(xforms, cities)
	_populate_ring1_cities(xforms, cities, footprints)

	# Build 1-draw-call MultiMeshInstance3D nodes
	_spawn_mm("StreetLanternPostsMultiMesh", _lantern_post_mesh, xforms["lantern_post"], false, 950.0)
	_spawn_mm("StreetLanternBulbsMultiMesh", _lantern_bulb_mesh, xforms["lantern_bulb"], false, 1100.0)
	_spawn_mm("StreetLanternLightPoolsMultiMesh", _lantern_pool_mesh, xforms["lantern_pool"], false, 0.0)
	_spawn_mm("AcropolisPillarsMultiMesh", _get_gltf_mesh("pillar"), xforms["pillar"], true, 1200.0)
	_spawn_mm("AcropolisBannersMultiMesh", _get_gltf_mesh("banner"), xforms["banner"], true, 1000.0)
	_spawn_mm("AcropolisBraziersMultiMesh", _get_gltf_mesh("brazier"), xforms["brazier"], false, 800.0)
	_spawn_mm("AcropolisFlamesMultiMesh", _flame_orb_mesh, xforms["flame"], false, 950.0)

	_spawn_mm("MarketStallsMultiMesh", _get_gltf_mesh("stall"), xforms["stall"], true, 750.0)
	_spawn_mm("MarketCartsMultiMesh", _get_gltf_mesh("stall_cart"), xforms["stall_cart"], true, 750.0)
	_spawn_mm("MarketWagonsMultiMesh", _get_gltf_mesh("wagon"), xforms["wagon"], true, 800.0)
	_spawn_mm("MarketBarrelsMultiMesh", _get_gltf_mesh("barrel"), xforms["barrel"], false, 650.0)
	_spawn_mm("MarketCratesMultiMesh", _get_gltf_mesh("crates"), xforms["crates"], true, 650.0)
	_spawn_mm("CityBenchesMultiMesh", _get_gltf_mesh("bench"), xforms["bench"], false, 650.0)

	_spawn_mm("AureliaTreesMultiMesh", _get_gltf_mesh("common_tree"), xforms["common_tree"], true, 1600.0)
	_spawn_mm("SylvanFenrisPinesMultiMesh", _get_gltf_mesh("pine_tree"), xforms["pine_tree"], true, 1600.0)
	_spawn_mm("MalakorDeadTreesMultiMesh", _get_gltf_mesh("dead_tree"), xforms["dead_tree"], true, 1600.0)
	_spawn_mm("DrakonisObelisksMultiMesh", _get_gltf_mesh("rock_obelisk"), xforms["rock_obelisk"], true, 1600.0)


func _populate_acropolis_avenues(xforms: Dictionary, cities: Dictionary, footprints: Array[Dictionary]) -> void:
	# 1. South Knight Avenue (z = 116..340m, step 32m, flanked ±10.5m)
	var pillar_min_y: float = _get_gltf_min_y("pillar")
	var banner_min_y: float = _get_gltf_min_y("banner")
	var brazier_min_y: float = _get_gltf_min_y("brazier")

	var z_pos: float = 116.0
	while z_pos <= 340.0:
		for side in [-1.0, 1.0]:
			var px: float = side * 10.5
			var pz: float = z_pos
			if not _is_blocked(px, pz, 2.0, footprints):
				var gy: float = TerrainHeightSampler.get_height(px, pz)
				var face_yaw: float = (-PI * 0.5) if side > 0.0 else (PI * 0.5)
				var p_scale: float = 1.15
				var p_basis: Basis = Basis(Vector3.UP, face_yaw).scaled_local(Vector3(p_scale, p_scale, p_scale))
				xforms["pillar"].append(Transform3D(p_basis, Vector3(px, gy - pillar_min_y * p_scale, pz)))

				# Banner hanging on inward face of pillar
				var bx: float = px - side * 1.15
				var b_basis: Basis = Basis(Vector3.UP, face_yaw).scaled_local(Vector3(1.1, 1.1, 1.1))
				xforms["banner"].append(Transform3D(b_basis, Vector3(bx, gy + 1.0 - banner_min_y * 1.1, pz)))

				# Brazier beside pillar toward street
				var brx: float = px - side * 2.2
				var brz: float = pz
				var br_gy: float = TerrainHeightSampler.get_height(brx, brz)
				var br_scale: float = 1.2
				xforms["brazier"].append(Transform3D(Basis(Vector3.UP, face_yaw).scaled_local(Vector3(br_scale, br_scale, br_scale)), Vector3(brx, br_gy - brazier_min_y * br_scale, brz)))
				xforms["flame"].append(Transform3D(Basis(), Vector3(brx, br_gy - brazier_min_y * br_scale + 1.48 * br_scale, brz)))

				# Alternating streetlamps midway along Knight Avenue
				if int(z_pos) % 64 == 52:
					_add_lantern(xforms, px - side * 1.5, pz + 16.0, face_yaw)
		z_pos += 32.0

	# 2. Acropolis 4 Institutional Plaza Avenues & Outer Ring Lamps
	var inst_targets: Array[Vector2] = [
		Vector2(180.0, 180.0),
		Vector2(-180.0, 180.0),
		Vector2(-180.0, -180.0),
		Vector2(180.0, -180.0),
	]
	for t in inst_targets:
		var dir: Vector2 = t.normalized()
		var perp: Vector2 = Vector2(-dir.y, dir.x)
		var d_along: float = 110.0
		while d_along <= 220.0:
			for s in [-1.0, 1.0]:
				var pos: Vector2 = dir * d_along + perp * (s * 8.5)
				var yaw: float = PI * 0.5 - atan2(-perp.y * s, -perp.x * s)
				_add_lantern(xforms, pos.x, pos.y, yaw)
			d_along += 55.0

	# 3. Acropolis Rim Pylons at r = 355m flanking all 5 Radial Highways
	for key in cities:
		var c: Dictionary = cities[key]
		var cx: float = float(c.get("x", 0.0))
		var cz: float = float(c.get("z", 0.0))
		var ang: float = atan2(cz, cx)
		var radial: Vector2 = Vector2(cos(ang), sin(ang))
		var tang: Vector2 = Vector2(-radial.y, radial.x)
		for s in [-1.0, 1.0]:
			var rp: Vector2 = radial * 355.0 + tang * (s * 9.5)
			var gy: float = TerrainHeightSampler.get_height(rp.x, rp.y)
			var yaw: float = PI * 0.5 - atan2(-tang.y * s, -tang.x * s)
			xforms["pillar"].append(Transform3D(Basis(Vector3.UP, yaw).scaled_local(Vector3(1.3, 1.35, 1.3)), Vector3(rp.x, gy - pillar_min_y * 1.35, rp.y)))
			xforms["flame"].append(Transform3D(Basis(), Vector3(rp.x, gy + 5.55, rp.y)))

	# 4. Acropolis Promenade Ring Lamps (r = 240m)
	for deg_step in range(12):
		var a: float = deg_step * (TAU / 12.0) + 0.15
		var lp: Vector2 = Vector2(cos(a), sin(a)) * 231.0
		_add_lantern(xforms, lp.x, lp.y, PI * 0.5 - a)


func _populate_radial_highways(xforms: Dictionary, cities: Dictionary) -> void:
	for key in cities:
		var c: Dictionary = cities[key]
		var cx: float = float(c.get("x", 0.0))
		var cz: float = float(c.get("z", 0.0))
		var ang: float = atan2(cz, cx)
		var dir: Vector2 = Vector2(cos(ang), sin(ang))
		var perp: Vector2 = Vector2(-dir.y, dir.x)
		var r_pos: float = 420.0
		while r_pos <= 860.0:
			for s in [-1.0, 1.0]:
				var pos: Vector2 = dir * r_pos + perp * (s * 8.5)
				var gy: float = TerrainHeightSampler.get_height(pos.x, pos.y)
				if gy > 2.5:
					var yaw: float = PI * 0.5 - atan2(-perp.y * s, -perp.x * s)
					_add_lantern(xforms, pos.x, pos.y, yaw)
			r_pos += 88.0


func _populate_ring1_cities(xforms: Dictionary, cities: Dictionary, footprints: Array[Dictionary]) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20263
	var stall_min_y: float = _get_gltf_min_y("stall")
	var cart_min_y: float = _get_gltf_min_y("stall_cart")
	var wagon_min_y: float = _get_gltf_min_y("wagon")
	var barrel_min_y: float = _get_gltf_min_y("barrel")
	var crates_min_y: float = _get_gltf_min_y("crates")
	var bench_min_y: float = _get_gltf_min_y("bench")

	for cid in cities:
		var c: Dictionary = cities[cid]
		var cx: float = float(c.get("x", 0.0))
		var cz: float = float(c.get("z", 0.0))
		var race: String = str(c.get("race", "HUMAN"))
		var main_angle: float = atan2(-cz, -cx)

		# A. Cross-Axis Boulevard Lamps (all 4 axes, r = 64..208m, step 36m)
		for q in range(4):
			var axis_a: float = main_angle + q * (PI * 0.5)
			var dir: Vector2 = Vector2(cos(axis_a), sin(axis_a))
			var perp: Vector2 = Vector2(-dir.y, dir.x)
			var r_step: float = 64.0
			while r_step <= 208.0:
				for s in [-1.0, 1.0]:
					var lp: Vector2 = Vector2(cx, cz) + dir * r_step + perp * (s * 8.2)
					if not _is_blocked(lp.x, lp.y, 1.5, footprints):
						var yaw: float = PI * 0.5 - atan2(-perp.y * s, -perp.x * s)
						_add_lantern(xforms, lp.x, lp.y, yaw)
				r_step += 36.0

		# B. Inner Plaza Ring Benches & Lanterns (r = 49m at quadrant mid-angles)
		for q in range(4):
			var mid_a: float = main_angle + q * (PI * 0.5) + PI * 0.25
			for off_deg in [-14.0, 14.0]:
				var ba: float = mid_a + deg_to_rad(off_deg)
				var bp: Vector2 = Vector2(cx + 47.0 * cos(ba), cz + 47.0 * sin(ba))
				if not _is_blocked(bp.x, bp.y, 2.2, footprints):
					var gy: float = TerrainHeightSampler.get_height(bp.x, bp.y)
					var bench_yaw: float = PI * 0.5 - (ba + PI)
					xforms["bench"].append(Transform3D(Basis(Vector3.UP, bench_yaw), Vector3(bp.x, gy - bench_min_y, bp.y)))

			# Boulevard Wagons parked neatly on shoulder midway between 100m and 136m streetlamps
			var axis_a2: float = main_angle + q * (PI * 0.5)
			var dir2: Vector2 = Vector2(cos(axis_a2), sin(axis_a2))
			var perp2: Vector2 = Vector2(-dir2.y, dir2.x)
			var wp: Vector2 = Vector2(cx, cz) + dir2 * 118.0 + perp2 * (9.8 if (q % 2 == 0) else -9.8)
			if not _is_blocked(wp.x, wp.y, 2.8, footprints):
				var wgy: float = TerrainHeightSampler.get_height(wp.x, wp.y)
				var wyaw: float = PI * 0.5 - axis_a2
				xforms["wagon"].append(Transform3D(Basis(Vector3.UP, wyaw), Vector3(wp.x, wgy - wagon_min_y, wp.y)))

		# C. Market & Shop Front Clutter around this city's shops
		for fp in footprints:
			if str(fp.get("city_id", "")) != cid:
				continue
			var btype: String = str(fp.get("building_type", ""))
			var bx: float = float(fp.get("x", 0.0))
			var bz: float = float(fp.get("z", 0.0))
			var brad: float = float(fp.get("radius", 10.0))
			var rot_y: float = float(fp.get("rotation_y", 0.0))
			var fwd: Vector2 = Vector2(sin(rot_y), cos(rot_y))
			var right: Vector2 = Vector2(fwd.y, -fwd.x)

			if btype == "SHOP_MARKET":
				# 2 stalls + barrels/crates neatly outside the market footprint edge
				for side in [-1.0, 1.0]:
					var sp: Vector2 = Vector2(bx, bz) + fwd * (brad + 2.2) + right * (side * 3.8)
					if not _is_blocked(sp.x, sp.y, 1.5, footprints):
						var sgy: float = TerrainHeightSampler.get_height(sp.x, sp.y)
						var key_stall: String = "stall" if side < 0.0 else "stall_cart"
						var my: float = stall_min_y if side < 0.0 else cart_min_y
						xforms[key_stall].append(Transform3D(Basis(Vector3.UP, rot_y), Vector3(sp.x, sgy - my, sp.y)))
				var brp: Vector2 = Vector2(bx, bz) + fwd * (brad + 1.8) + right * 6.2
				if not _is_blocked(brp.x, brp.y, 1.0, footprints):
					var bgy: float = TerrainHeightSampler.get_height(brp.x, brp.y)
					xforms["barrel"].append(Transform3D(Basis(Vector3.UP, rot_y), Vector3(brp.x, bgy - barrel_min_y, brp.y)))
			elif btype == "SHOP_BLACKSMITH" or btype == "SHOP_TAVERN":
				var cp: Vector2 = Vector2(bx, bz) + fwd * (brad + 1.6) + right * 3.2
				if not _is_blocked(cp.x, cp.y, 1.4, footprints):
					var cgy: float = TerrainHeightSampler.get_height(cp.x, cp.y)
					xforms["crates"].append(Transform3D(Basis(Vector3.UP, rot_y + 0.35), Vector3(cp.x, cgy - crates_min_y, cp.y)))
				var bp2: Vector2 = Vector2(bx, bz) + fwd * (brad + 1.4) - right * 2.8
				if not _is_blocked(bp2.x, bp2.y, 1.0, footprints):
					var bgy2: float = TerrainHeightSampler.get_height(bp2.x, bp2.y)
					xforms["barrel"].append(Transform3D(Basis(Vector3.UP, rot_y), Vector3(bp2.x, bgy2 - barrel_min_y, bp2.y)))

		# D. Racial Courtyard & Boulevard Foliage / Landmarks (strictly off roads & buildings!)
		var flora_key: String = "common_tree"
		if race == "ELF" or race == "BEASTHUMAN":
			flora_key = "pine_tree"
		elif race == "DEMON":
			flora_key = "dead_tree"
		elif race == "DRAGON":
			flora_key = "rock_obelisk"
		var flora_min_y: float = _get_gltf_min_y(flora_key)

		var tree_spots: Array[Dictionary] = [
			{"r": 96.0, "deg": 24.0},
			{"r": 96.0, "deg": 66.0},
			{"r": 160.0, "deg": 28.0},
			{"r": 160.0, "deg": 62.0},
			{"r": 212.0, "deg": 45.0},
		]
		for q in range(4):
			var qbase: float = main_angle + q * (PI * 0.5)
			for spot in tree_spots:
				var ta: float = qbase + deg_to_rad(float(spot["deg"]))
				var tx: float = cx + float(spot["r"]) * cos(ta)
				var tz: float = cz + float(spot["r"]) * sin(ta)
				if _is_blocked(tx, tz, 3.6, footprints):
					continue
				if TerrainHeightSampler.get_road_weight(tx, tz) > 0.30:
					continue
				var tgy: float = TerrainHeightSampler.get_height(tx, tz)
				var tscale: float = rng.randf_range(0.82, 1.12)
				var tyaw: float = rng.randf_range(0.0, TAU)
				var basis := Basis(Vector3.UP, tyaw).scaled(Vector3(tscale, tscale, tscale))
				xforms[flora_key].append(Transform3D(basis, Vector3(tx, tgy - flora_min_y * tscale, tz)))


func _add_lantern(xforms: Dictionary, lx: float, lz: float, yaw: float) -> void:
	var gy: float = TerrainHeightSampler.get_height(lx, lz)
	var xf := Transform3D(Basis(Vector3.UP, yaw), Vector3(lx, gy, lz))
	xforms["lantern_post"].append(xf)
	var bulb_offset: Vector3 = Basis(Vector3.UP, yaw) * Vector3(0.0, 4.18, 0.52)
	xforms["lantern_bulb"].append(Transform3D(Basis(Vector3.UP, yaw), Vector3(lx, gy, lz) + bulb_offset))
	var pool_offset: Vector3 = Basis(Vector3.UP, yaw) * Vector3(0.0, 0.22, 0.52)
	xforms["lantern_pool"].append(Transform3D(Basis(), Vector3(lx, gy, lz) + pool_offset))


func _is_blocked(px: float, pz: float, clearance: float, footprints: Array[Dictionary]) -> bool:
	var p2 := Vector2(px, pz)
	for fp in footprints:
		var rad: float = float(fp.get("radius", 10.0)) + clearance
		var c2 := Vector2(float(fp.get("x", 0.0)), float(fp.get("z", 0.0)))
		if p2.distance_squared_to(c2) < rad * rad:
			return true
	return false


func _get_gltf_mesh(key: String) -> Mesh:
	if key in _mesh_cache:
		return _mesh_cache[key]
	var path: String = ASSET_PATHS.get(key, "")
	if path == "" or not ResourceLoader.exists(path):
		return null
	var packed: PackedScene = load(path)
	if not packed:
		return null
	var inst: Node = packed.instantiate()
	var found: Mesh = _find_first_mesh(inst)
	inst.queue_free()
	if found:
		_mesh_cache[key] = found
		_min_y_cache[key] = found.get_aabb().position.y
	return found


func _get_gltf_min_y(key: String) -> float:
	if key not in _min_y_cache:
		_get_gltf_mesh(key)
	return float(_min_y_cache.get(key, 0.0))


func _find_first_mesh(node: Node) -> Mesh:
	if node is MeshInstance3D and node.mesh:
		return node.mesh
	for ch in node.get_children():
		var m := _find_first_mesh(ch)
		if m:
			return m
	return null


func _spawn_mm(node_name: String, mesh: Mesh, transforms: Array, cast_shadows: bool, _vis_end: float) -> void:
	if mesh == null or transforms.is_empty():
		return
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = transforms.size()
	for i in range(transforms.size()):
		mm.set_instance_transform(i, transforms[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.name = node_name
	mmi.multimesh = mm
	mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if cast_shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# Never whole-node cull MultiMeshes centered at world (0,0,0) (would drop Ring 1 props at r=1150m!)
	mmi.visibility_range_end = 0.0
	mmi.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
	_props_root.add_child(mmi)


func _prepare_custom_meshes() -> void:
	# 1. Procedural Wrought-Iron Streetlamp Post
	var iron_mat := StandardMaterial3D.new()
	iron_mat.albedo_color = Color(0.16, 0.17, 0.20, 1.0)
	iron_mat.metallic = 0.72
	iron_mat.roughness = 0.42

	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	st.set_material(iron_mat)
	# Plinth base
	_add_st_box(st, Vector3(0.0, 0.25, 0.0), Vector3(0.46, 0.50, 0.46))
	# Post shaft
	_add_st_box(st, Vector3(0.0, 2.35, 0.0), Vector3(0.24, 4.10, 0.24))
	# Cantilever arm (+Z forward)
	_add_st_box(st, Vector3(0.0, 4.42, 0.30), Vector3(0.16, 0.16, 0.80))
	# Lantern cap, hanger stem, and bottom cradle
	_add_st_box(st, Vector3(0.0, 4.38, 0.52), Vector3(0.42, 0.12, 0.42))
	_add_st_box(st, Vector3(0.0, 4.35, 0.52), Vector3(0.10, 0.16, 0.10))
	_add_st_box(st, Vector3(0.0, 3.98, 0.52), Vector3(0.30, 0.07, 0.30))
	_lantern_post_mesh = st.commit()

	# 2. Emissive Streetlamp Bulb & Brazier Flame Orb (ShaderMaterial, zero OmniLight3D overhead)
	var glow_mat: Material = null
	if ResourceLoader.exists(GLOW_SHADER_PATH):
		var sh: Shader = load(GLOW_SHADER_PATH)
		var sm := ShaderMaterial.new()
		sm.shader = sh
		sm.set_shader_parameter("day_glass_color", Color(0.96, 0.84, 0.50, 1.0))
		sm.set_shader_parameter("night_glow_color", Color(1.0, 0.52, 0.12, 1.0))
		sm.set_shader_parameter("day_roughness", 0.24)
		sm.set_shader_parameter("max_emission_energy", 4.2)
		glow_mat = sm
	else:
		var m := StandardMaterial3D.new()
		m.albedo_color = Color(1.0, 0.82, 0.4, 1.0)
		m.emission_enabled = true
		m.emission = Color(1.0, 0.52, 0.12, 1.0)
		m.emission_energy_multiplier = 3.2
		glow_mat = m

	var bulb := BoxMesh.new()
	bulb.size = Vector3(0.28, 0.34, 0.28)
	bulb.material = glow_mat
	_lantern_bulb_mesh = bulb

	# 3. 1-Draw-Call Golden Night Light-Pool Disc (zero OmniLight3D overhead, zero daytime alpha)
	var pool_plane := PlaneMesh.new()
	pool_plane.size = Vector2(11.0, 11.0)
	if ResourceLoader.exists(POOL_SHADER_PATH):
		var pm := ShaderMaterial.new()
		pm.shader = load(POOL_SHADER_PATH)
		pool_plane.material = pm
	else:
		var pm_fb := StandardMaterial3D.new()
		pm_fb.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		pm_fb.albedo_color = Color(1.0, 0.55, 0.15, 0.0)
		pool_plane.material = pm_fb
	_lantern_pool_mesh = pool_plane

	var flame := SphereMesh.new()
	flame.radius = 0.22
	flame.height = 0.48
	flame.radial_segments = 8
	flame.rings = 4
	flame.material = glow_mat
	_flame_orb_mesh = flame


func _add_st_box(st: SurfaceTool, center: Vector3, sz: Vector3) -> void:
	var hx: float = sz.x * 0.5
	var hy: float = sz.y * 0.5
	var hz: float = sz.z * 0.5
	var cx: float = center.x
	var cy: float = center.y
	var cz: float = center.z

	var p000 := Vector3(cx - hx, cy - hy, cz - hz)
	var p100 := Vector3(cx + hx, cy - hy, cz - hz)
	var p110 := Vector3(cx + hx, cy + hy, cz - hz)
	var p010 := Vector3(cx - hx, cy + hy, cz - hz)
	var p001 := Vector3(cx - hx, cy - hy, cz + hz)
	var p101 := Vector3(cx + hx, cy - hy, cz + hz)
	var p111 := Vector3(cx + hx, cy + hy, cz + hz)
	var p011 := Vector3(cx - hx, cy + hy, cz + hz)

	# +Z front, -Z back, +X right, -X left, +Y top, -Y bottom (CW outward winding + crisp normals)
	_st_quad_n(st, p001, p101, p111, p011, Vector3(0, 0, 1))
	_st_quad_n(st, p100, p000, p010, p110, Vector3(0, 0, -1))
	_st_quad_n(st, p101, p100, p110, p111, Vector3(1, 0, 0))
	_st_quad_n(st, p000, p001, p011, p010, Vector3(-1, 0, 0))
	_st_quad_n(st, p011, p111, p110, p010, Vector3(0, 1, 0))
	_st_quad_n(st, p000, p100, p101, p001, Vector3(0, -1, 0))


func _st_quad_n(st: SurfaceTool, a: Vector3, b: Vector3, d: Vector3, e: Vector3, n: Vector3) -> void:
	st.set_normal(n)
	st.add_vertex(a)
	st.add_vertex(e)
	st.add_vertex(d)
	st.add_vertex(a)
	st.add_vertex(d)
	st.add_vertex(b)
