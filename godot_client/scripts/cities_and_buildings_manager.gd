# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/cities_and_buildings_manager.gd
# Spawns and manages 5 Equidistant Gated Ring 1 Cities, God-Mother Palaces,
# modular walk-in housing & shops, live BUILDING_SYNC, masonry curtain walls + watchtowers,
# texture-preserving racial theming, deterministic exterior variety, and distance-streamed LOD.

extends Node3D

const PREFAB_MAP: Dictionary = {
	"GODMOTHER_PALACE": "res://scenes/buildings/godmother_palace.tscn",
	"CITY_GATE": "res://scenes/buildings/city_gate_and_wall.tscn",
	"HOUSE_T1_COTTAGE": "res://scenes/buildings/house_tier1_cottage.tscn",
	"HOUSE_T2_TOWNHOUSE": "res://scenes/buildings/house_tier2_townhouse.tscn",
	"HOUSE_T3_MANOR": "res://scenes/buildings/house_tier3_manor.tscn",
	"SHOP_MARKET": "res://scenes/buildings/shop_commercial.tscn",
	"SHOP_BLACKSMITH": "res://scenes/buildings/shop_commercial.tscn",
	"SHOP_TAVERN": "res://scenes/buildings/shop_commercial.tscn",
}

const RACIAL_THEMES: Dictionary = {
	"ELF": {
		"accent": Color(0.18, 0.78, 0.44, 1.0),
		"secondary": Color(0.82, 0.88, 0.92, 1.0),
		"window_glow": Color(0.58, 0.98, 0.72, 1.0),
		"brazier_light": Color(0.55, 1.0, 0.68, 1.0),
		"title_prefix": "Sylvanor",
	},
	"HUMAN": {
		"accent": Color(0.96, 0.78, 0.26, 1.0),
		"secondary": Color(0.24, 0.46, 0.82, 1.0),
		"window_glow": Color(1.0, 0.84, 0.46, 1.0),
		"brazier_light": Color(1.0, 0.76, 0.34, 1.0),
		"title_prefix": "Aurelia",
	},
	"BEASTHUMAN": {
		"accent": Color(0.90, 0.54, 0.18, 1.0),
		"secondary": Color(0.56, 0.36, 0.20, 1.0),
		"window_glow": Color(1.0, 0.68, 0.28, 1.0),
		"brazier_light": Color(1.0, 0.60, 0.22, 1.0),
		"title_prefix": "Fenris Hold",
	},
	"DEMON": {
		"accent": Color(0.86, 0.14, 0.20, 1.0),
		"secondary": Color(0.38, 0.20, 0.48, 1.0),
		"window_glow": Color(0.95, 0.30, 0.68, 1.0),
		"brazier_light": Color(0.95, 0.28, 0.58, 1.0),
		"title_prefix": "Malakor",
	},
	"DRAGON": {
		"accent": Color(1.0, 0.72, 0.18, 1.0),
		"secondary": Color(0.76, 0.18, 0.16, 1.0),
		"window_glow": Color(1.0, 0.54, 0.20, 1.0),
		"brazier_light": Color(1.0, 0.50, 0.16, 1.0),
		"title_prefix": "Drakonis Spire",
	},
}

const WATCHTOWER_GLTF_PATHS: Dictionary = {
	"wall": "res://assets/buildings/dungeon/wall.gltf",
	"window": "res://assets/buildings/dungeon/wall_archedwindow_gated.gltf",
	"pillar": "res://assets/buildings/dungeon/pillar.gltf",
	"barrier": "res://assets/buildings/dungeon/barrier_column.gltf",
	"roof": "res://assets/buildings/village/roof_tower_round_tiles.gltf",
	"banner": "res://assets/buildings/dungeon/banner_white.gltf",
	"torch": "res://assets/buildings/dungeon/torch_lit.gltf",
}

# Distance-based streaming: houses and detailed stalls stream in within 580m; Orbital proxies beyond 580m
const HOUSE_STREAMING_DIST_SQ: float = 580.0 * 580.0
const LIGHT_CULL_DIST_SQ: float = 180.0 * 180.0
const CHECK_INTERVAL: float = 0.2  # 5 Hz throttle
const FAR_PROXY_SHADER_PATH: String = "res://shaders/far_building_proxy.gdshader"
const PARKED_PROXY_XF: Transform3D = Transform3D(Basis(Vector3.ZERO, Vector3.ZERO, Vector3.ZERO), Vector3(0.0, -5000.0, 0.0))

signal buildings_populated

var _buildings_by_id: Dictionary = {}         # bld_id -> Node3D instance
var _building_records: Dictionary = {}        # bld_id -> Dictionary
var _streamable_houses: Array[Node3D] = []     # List of houses subject to distance culling
var _building_lights: Array[OmniLight3D] = []  # Cached OmniLight3Ds for 180m culling
var _far_proxy_records: Array[Dictionary] = [] # Far Orbital MultiMesh proxy records
var _far_walls_mmi: MultiMeshInstance3D = null
var _far_roofs_mmi: MultiMeshInstance3D = null
var _far_wall_mesh: Mesh = null
var _far_roof_mesh: Mesh = null
var _perimeter_walls_node: Node3D = null
var _check_timer: float = 0.0
var _camera_node: Camera3D = null
var _sky_controller: Node = null
var _current_night_factor: float = 0.0
var _tex_cache: Dictionary = {}
var _packed_cache: Dictionary = {}


func _ready() -> void:
	_connect_bridge()
	_connect_sky_controller()
	_find_camera()


func _process(delta: float) -> void:
	_check_timer += delta
	if _check_timer >= CHECK_INTERVAL:
		_check_timer = 0.0
		_update_distance_streaming()


func _find_camera() -> void:
	var vp = get_viewport()
	if vp:
		_camera_node = vp.get_camera_3d()


func _connect_sky_controller() -> void:
	var root = get_tree().root
	_sky_controller = root.find_child("SkyWeatherController", true, false)
	if _sky_controller and _sky_controller.has_signal("night_factor_changed"):
		_sky_controller.connect("night_factor_changed", Callable(self, "_on_night_factor_changed"))
		if _sky_controller.has_method("get_night_factor"):
			_current_night_factor = _sky_controller.get_night_factor()


func _connect_bridge() -> void:
	var bridge = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.connect("building_sync_received", Callable(self, "_on_building_sync_received"))
		bridge.connect("building_updated", Callable(self, "_on_building_updated"))


func _on_building_sync_received(buildings: Array, cities: Array) -> void:
	print("[CitiesManager] BUILDING_SYNC received: %d buildings across %d cities." % [buildings.size(), cities.size()])
	_spawn_buildings(buildings)


func _on_building_updated(bld_data: Dictionary) -> void:
	var bid: String = bld_data.get("building_id", "")
	if bid == "":
		return

	var old_bld: Dictionary = _building_records.get(bid, {})
	var old_type: String = old_bld.get("building_type", "")
	var new_type: String = bld_data.get("building_type", "")
	_building_records[bid] = bld_data

	if bid in _buildings_by_id:
		var node: Node3D = _buildings_by_id[bid]
		if old_type != "" and new_type != "" and old_type != new_type:
			# Tier upgrade: replace node with upgraded prefab
			if is_instance_valid(node):
				if node in _streamable_houses:
					_streamable_houses.erase(node)
				node.queue_free()
			_buildings_by_id.erase(bid)
			_remove_far_proxy_record(bid)
			_spawn_single_building(bld_data)
			_rebuild_far_proxies()
			_update_distance_streaming()
			buildings_populated.emit()
		else:
			_update_plaque(node, bld_data)
	else:
		# Incrementally spawn newly constructed / frontier building
		_spawn_single_building(bld_data)
		_rebuild_far_proxies()
		_update_distance_streaming()
		buildings_populated.emit()


func _on_night_factor_changed(nf: float) -> void:
	_current_night_factor = nf
	for bid in _buildings_by_id:
		var node: Node3D = _buildings_by_id[bid]
		if is_instance_valid(node):
			_apply_building_night_lighting(node, nf)
	if _perimeter_walls_node and is_instance_valid(_perimeter_walls_node):
		_apply_building_night_lighting(_perimeter_walls_node, nf)


func _spawn_buildings(buildings: Array) -> void:
	TerrainHeightSampler.ensure_loaded()
	# Clear previous instances if any
	for bid in _buildings_by_id:
		var n: Node3D = _buildings_by_id[bid]
		if is_instance_valid(n):
			n.queue_free()

	_buildings_by_id.clear()
	_building_records.clear()
	_streamable_houses.clear()
	_building_lights.clear()
	_far_proxy_records.clear()
	if _far_walls_mmi and is_instance_valid(_far_walls_mmi):
		_far_walls_mmi.queue_free()
	_far_walls_mmi = null
	if _far_roofs_mmi and is_instance_valid(_far_roofs_mmi):
		_far_roofs_mmi.queue_free()
	_far_roofs_mmi = null

	for bld_data in buildings:
		_spawn_single_building(bld_data)

	_build_perimeter_walls()
	_rebuild_far_proxies()
	_update_distance_streaming()
	print("[CitiesManager] Successfully materialized %d city buildings and landmarks (%d far proxies)." % [_buildings_by_id.size(), _far_proxy_records.size()])
	buildings_populated.emit()


func _spawn_single_building(bld: Dictionary) -> void:
	TerrainHeightSampler.ensure_loaded()
	var bid: String = bld.get("building_id", "")
	var btype: String = bld.get("building_type", "HOUSE_T1_COTTAGE")
	var style: String = bld.get("racial_style", "HUMAN")

	if bid == "" or not (btype in PREFAB_MAP):
		return

	var prefab_path: String = PREFAB_MAP[btype]
	if not ResourceLoader.exists(prefab_path):
		return

	var scene_res: PackedScene = load(prefab_path)
	if not scene_res:
		return

	var inst: Node3D = scene_res.instantiate()
	inst.name = bid

	var bx: float = float(bld.get("x", 0.0))
	var bz: float = float(bld.get("z", 0.0))
	var ground_y: float = TerrainHeightSampler.get_height(bx, bz)
	var rot_y: float = float(bld.get("rotation_y", 0.0))

	# Snap flush on terrain elevation
	inst.position = Vector3(bx, ground_y, bz)
	inst.rotation.y = rot_y

	# Apply non-destructive racial accent colors (preserving glTF PBR textures)
	_apply_racial_theming(inst, style, btype)

	# Apply deterministic per-building architectural variety on modular houses/shops
	_apply_exterior_variation(inst, bid, style, btype)

	# Update property plaque
	_update_plaque(inst, bld)

	add_child(inst)
	_buildings_by_id[bid] = inst
	_building_records[bid] = bld

	# Collect OmniLight3D nodes for distance culling
	_collect_building_lights(inst)

	# Apply night lighting state
	_apply_building_night_lighting(inst, _current_night_factor)

	# Categorize for distance streaming: Palaces and Gates stay visible as landmarks; houses stream
	if btype not in ["GODMOTHER_PALACE", "CITY_GATE"]:
		_streamable_houses.append(inst)
		var proxy_spec := _compute_far_proxy_spec(btype, style, bx, ground_y, bz, rot_y)
		proxy_spec["node"] = inst
		proxy_spec["bid"] = bid
		proxy_spec["state"] = -1
		_far_proxy_records.append(proxy_spec)


func get_building_footprints() -> Array[Dictionary]:
	var fps: Array[Dictionary] = []
	for bid in _building_records:
		var b: Dictionary = _building_records[bid]
		fps.append({
			"building_id": bid,
			"city_id": b.get("city_id", ""),
			"building_type": b.get("building_type", ""),
			"x": float(b.get("x", 0.0)),
			"z": float(b.get("z", 0.0)),
			"rotation_y": float(b.get("rotation_y", 0.0)),
			"radius": float(b.get("footprint_radius", _default_footprint_radius(str(b.get("building_type", ""))))),
		})
	return fps


func _default_footprint_radius(btype: String) -> float:
	if btype == "GODMOTHER_PALACE":
		return 32.0
	if btype == "CITY_GATE":
		return 16.0
	if "COTTAGE" in btype:
		return 8.0
	if "TOWNHOUSE" in btype:
		return 11.0
	return 14.0


func _remove_far_proxy_record(bid: String) -> void:
	for i in range(_far_proxy_records.size() - 1, -1, -1):
		if str(_far_proxy_records[i].get("bid", "")) == bid:
			_far_proxy_records.remove_at(i)


func _compute_far_proxy_spec(btype: String, style: String, bx: float, gy: float, bz: float, rot_y: float) -> Dictionary:
	var w: float = 8.4
	var wh: float = 4.5
	var d: float = 7.2
	var rh: float = 3.2
	if btype == "HOUSE_T1_COTTAGE":
		w = 8.0; wh = 4.2; d = 7.0; rh = 3.2
	elif btype == "HOUSE_T2_TOWNHOUSE":
		w = 10.2; wh = 6.8; d = 8.8; rh = 3.8
	elif btype == "HOUSE_T3_MANOR":
		w = 14.2; wh = 7.8; d = 11.0; rh = 4.4
	elif btype == "SHOP_MARKET":
		w = 9.4; wh = 3.6; d = 7.4; rh = 2.8
	elif btype == "SHOP_BLACKSMITH":
		w = 10.0; wh = 4.8; d = 8.4; rh = 3.4
	elif btype == "SHOP_TAVERN":
		w = 11.8; wh = 6.2; d = 9.4; rh = 4.0

	var wall_col := Color(0.93, 0.88, 0.78, 1.0)
	var roof_col := Color(0.71, 0.29, 0.20, 1.0)
	if style == "ELF":
		wall_col = Color(0.89, 0.92, 0.85, 1.0)
		roof_col = Color(0.18, 0.43, 0.31, 1.0)
	elif style == "BEASTHUMAN":
		wall_col = Color(0.78, 0.71, 0.61, 1.0)
		roof_col = Color(0.36, 0.42, 0.49, 1.0)
	elif style == "DEMON":
		wall_col = Color(0.37, 0.33, 0.35, 1.0)
		roof_col = Color(0.56, 0.14, 0.14, 1.0)
	elif style == "DRAGON":
		wall_col = Color(0.56, 0.60, 0.65, 1.0)
		roof_col = Color(0.21, 0.31, 0.45, 1.0)

	var rot_basis := Basis(Vector3.UP, rot_y)
	var wall_xf := Transform3D(rot_basis.scaled_local(Vector3(w, wh, d)), Vector3(bx, gy, bz))
	var roof_xf := Transform3D(rot_basis.scaled_local(Vector3(w, rh, d)), Vector3(bx, gy + wh, bz))
	return {
		"wall_xf": wall_xf,
		"roof_xf": roof_xf,
		"wall_col": wall_col,
		"roof_col": roof_col,
	}


func _ensure_far_proxy_meshes() -> void:
	if _far_wall_mesh != null and _far_roof_mesh != null:
		return
	var wall_mat: Material = null
	var roof_mat: Material = null
	if ResourceLoader.exists(FAR_PROXY_SHADER_PATH):
		var sh: Shader = load(FAR_PROXY_SHADER_PATH)
		var wm := ShaderMaterial.new()
		wm.shader = sh
		wm.set_shader_parameter("is_roof", false)
		wm.set_shader_parameter("roughness_val", 0.85)
		wall_mat = wm
		var rm := ShaderMaterial.new()
		rm.shader = sh
		rm.set_shader_parameter("is_roof", true)
		rm.set_shader_parameter("roughness_val", 0.72)
		roof_mat = rm
	else:
		var sm_w := StandardMaterial3D.new()
		sm_w.vertex_color_use_as_albedo = true
		wall_mat = sm_w
		var sm_r := StandardMaterial3D.new()
		sm_r.vertex_color_use_as_albedo = true
		roof_mat = sm_r

	# 1. Unit Wall Cube: X,Z in [-0.5, 0.5], Y in [0.0, 1.0]
	var st_w := SurfaceTool.new()
	st_w.begin(Mesh.PRIMITIVE_TRIANGLES)
	var p000 := Vector3(-0.5, 0.0, -0.5)
	var p001 := Vector3(-0.5, 0.0,  0.5)
	var p010 := Vector3(-0.5, 1.0, -0.5)
	var p011 := Vector3(-0.5, 1.0,  0.5)
	var p100 := Vector3( 0.5, 0.0, -0.5)
	var p101 := Vector3( 0.5, 0.0,  0.5)
	var p110 := Vector3( 0.5, 1.0, -0.5)
	var p111 := Vector3( 0.5, 1.0,  0.5)
	var add_quad := func(st: SurfaceTool, a: Vector3, b: Vector3, d: Vector3, e: Vector3, n: Vector3) -> void:
		st.set_normal(n)
		st.add_vertex(a); st.add_vertex(e); st.add_vertex(d)
		st.add_vertex(a); st.add_vertex(d); st.add_vertex(b)
	add_quad.call(st_w, p001, p101, p111, p011, Vector3(0, 0, 1))
	add_quad.call(st_w, p100, p000, p010, p110, Vector3(0, 0, -1))
	add_quad.call(st_w, p101, p100, p110, p111, Vector3(1, 0, 0))
	add_quad.call(st_w, p000, p001, p011, p010, Vector3(-1, 0, 0))
	add_quad.call(st_w, p011, p111, p110, p010, Vector3(0, 1, 0))
	st_w.set_material(wall_mat)
	_far_wall_mesh = st_w.commit()

	# 2. Unit Pitched Gable Roof: eaves [-0.55, 0.55] at y=0, ridge along X at y=1, z=0
	var st_r := SurfaceTool.new()
	st_r.begin(Mesh.PRIMITIVE_TRIANGLES)
	var r00 := Vector3(-0.55, 0.0,  0.55)
	var r10 := Vector3( 0.55, 0.0,  0.55)
	var r01 := Vector3(-0.55, 0.0, -0.55)
	var r11 := Vector3( 0.55, 0.0, -0.55)
	var rg0 := Vector3(-0.55, 1.0,  0.0)
	var rg1 := Vector3( 0.55, 1.0,  0.0)
	var n_front := Vector3(0.0, 0.55, 1.0).normalized()
	var n_back := Vector3(0.0, 0.55, -1.0).normalized()
	add_quad.call(st_r, r00, r10, rg1, rg0, n_front)
	add_quad.call(st_r, r11, r01, rg0, rg1, n_back)
	# Gable ends (-X and +X), CW when viewed from outside
	st_r.set_normal(Vector3(-1, 0, 0))
	st_r.add_vertex(r01); st_r.add_vertex(rg0); st_r.add_vertex(r00)
	st_r.set_normal(Vector3(1, 0, 0))
	st_r.add_vertex(r10); st_r.add_vertex(rg1); st_r.add_vertex(r11)
	# Bottom cap (-Y), CW from below
	add_quad.call(st_r, r01, r11, r10, r00, Vector3(0, -1, 0))
	st_r.set_material(roof_mat)
	_far_roof_mesh = st_r.commit()


func _rebuild_far_proxies() -> void:
	if _far_walls_mmi and is_instance_valid(_far_walls_mmi):
		_far_walls_mmi.queue_free()
	_far_walls_mmi = null
	if _far_roofs_mmi and is_instance_valid(_far_roofs_mmi):
		_far_roofs_mmi.queue_free()
	_far_roofs_mmi = null

	if _far_proxy_records.is_empty():
		return

	_ensure_far_proxy_meshes()
	var count: int = _far_proxy_records.size()

	var mm_w := MultiMesh.new()
	mm_w.transform_format = MultiMesh.TRANSFORM_3D
	mm_w.use_colors = true
	mm_w.mesh = _far_wall_mesh
	mm_w.instance_count = count

	var mm_r := MultiMesh.new()
	mm_r.transform_format = MultiMesh.TRANSFORM_3D
	mm_r.use_colors = true
	mm_r.mesh = _far_roof_mesh
	mm_r.instance_count = count

	for i in range(count):
		var rec: Dictionary = _far_proxy_records[i]
		rec["state"] = -1
		mm_w.set_instance_transform(i, PARKED_PROXY_XF)
		mm_w.set_instance_color(i, rec["wall_col"])
		mm_r.set_instance_transform(i, PARKED_PROXY_XF)
		mm_r.set_instance_color(i, rec["roof_col"])

	_far_walls_mmi = MultiMeshInstance3D.new()
	_far_walls_mmi.name = "FarBuildingWallsMultiMesh"
	_far_walls_mmi.multimesh = mm_w
	_far_walls_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_far_walls_mmi)

	_far_roofs_mmi = MultiMeshInstance3D.new()
	_far_roofs_mmi.name = "FarBuildingRoofsMultiMesh"
	_far_roofs_mmi.multimesh = mm_r
	_far_roofs_mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_far_roofs_mmi)


func _collect_building_lights(node: Node) -> void:
	if node is OmniLight3D:
		var light: OmniLight3D = node as OmniLight3D
		if not light.has_meta("base_energy"):
			light.set_meta("base_energy", light.light_energy)
		_building_lights.append(light)
	for child in node.get_children():
		_collect_building_lights(child)


func _apply_building_night_lighting(node: Node, nf: float) -> void:
	if node is OmniLight3D:
		var light: OmniLight3D = node as OmniLight3D
		if not light.has_meta("base_energy"):
			light.set_meta("base_energy", light.light_energy)
		var base: float = float(light.get_meta("base_energy"))
		light.light_energy = base * nf
		light.visible = (nf > 0.02)
	elif node is MeshInstance3D:
		var mi: MeshInstance3D = node as MeshInstance3D
		var mname: String = mi.name.to_lower()
		# Strictly glow emissive glass panes, lantern bulbs, and brazier flames (never glTF wall meshes containing "window"!)
		if mname.begins_with("windowglass") or mname.begins_with("lanternglow") or mname == "flame":
			var mat: Material = mi.material_override
			if not mat and mi.get_surface_override_material_count() > 0:
				mat = mi.get_surface_override_material(0)
			if not mat and mi.mesh and mi.mesh.get_surface_count() > 0:
				mat = mi.mesh.surface_get_material(0)
			if mat is StandardMaterial3D:
				var smat: StandardMaterial3D = mat as StandardMaterial3D
				if not smat.has_meta("_shared_cloned"):
					smat = smat.duplicate() as StandardMaterial3D
					smat.set_meta("_shared_cloned", true)
					mi.material_override = smat
				smat.emission_enabled = (nf > 0.05)
				if not smat.has_meta("_racial_emission_color"):
					smat.emission = Color(1.0, 0.82, 0.45)
				smat.emission_energy_multiplier = 1.6 * nf

	for child in node.get_children():
		_apply_building_night_lighting(child, nf)


func _apply_racial_theming(node: Node3D, style: String, btype: String) -> void:
	if not (style in RACIAL_THEMES):
		return

	var theme: Dictionary = RACIAL_THEMES[style]
	var accent_col: Color = theme["accent"]
	var secondary_col: Color = theme.get("secondary", accent_col)
	var glow_col: Color = theme.get("window_glow", Color(1.0, 0.82, 0.42))
	var brazier_col: Color = theme.get("brazier_light", Color(1.0, 0.72, 0.30))

	# Tint banners while preserving fabric weaving / trim textures
	var banners = node.get_node_or_null("Banners")
	if banners:
		for b in banners.get_children():
			_tint_preserving_textures(b, accent_col, true)

	for bname in ["BannerL", "BannerR", "TradeBanner"]:
		var b_node = node.get_node_or_null(bname)
		if b_node:
			_tint_preserving_textures(b_node, accent_col, true)

	# Tint roof trim / trim accents with racial secondary palette (muted on timber ridge caps, richer on monuments)
	var trim_col: Color = secondary_col if btype in ["GODMOTHER_PALACE", "CITY_GATE"] else Color(0.32, 0.25, 0.19, 1.0).lerp(secondary_col, 0.35)
	var roof_trim = node.get_node_or_null("RoofTrim")
	if roof_trim:
		_tint_preserving_textures(roof_trim, trim_col, true)
	var trim_mesh = node.get_node_or_null("TrimMesh")
	if trim_mesh:
		_tint_preserving_textures(trim_mesh, trim_col, true)

	# Show Elf ivy vines only for ELF settlement style
	var sylvan_vines = node.get_node_or_null("SylvanVines")
	if sylvan_vines:
		sylvan_vines.visible = (style == "ELF")

	# For Palaces & Gates, give stained glass & braziers distinctive racial ambiance
	if btype in ["GODMOTHER_PALACE", "CITY_GATE"]:
		_apply_monument_glow_palette(node, glow_col, brazier_col)


func _apply_monument_glow_palette(node: Node, glow_col: Color, brazier_col: Color) -> void:
	if node is OmniLight3D:
		(node as OmniLight3D).light_color = brazier_col
	elif node is MeshInstance3D:
		var mi: MeshInstance3D = node as MeshInstance3D
		var lname: String = mi.name.to_lower()
		if "windowglass" in lname or "flame" in lname:
			var smat: Material = _get_active_surface_material(mi, 0)
			if smat is ShaderMaterial:
				var sh: ShaderMaterial = smat.duplicate() as ShaderMaterial
				sh.set_shader_parameter("night_glow_color", glow_col if "window" in lname else brazier_col)
				mi.material_override = sh
			elif smat is StandardMaterial3D:
				var st: StandardMaterial3D = smat.duplicate() as StandardMaterial3D
				st.emission = glow_col if "window" in lname else brazier_col
				st.set_meta("_racial_emission_color", true)
				st.set_meta("_shared_cloned", true)
				mi.material_override = st

	for child in node.get_children():
		_apply_monument_glow_palette(child, glow_col, brazier_col)


func _apply_exterior_variation(node: Node3D, bid: String, style: String, btype: String) -> void:
	if btype in ["GODMOTHER_PALACE", "CITY_GATE"]:
		return

	var h: int = abs(bid.hash())

	# 1. Subtle +/-6% warm/cool plaster hue shift without clobbering plaster textures
	var plaster_group = node.get_node_or_null("PlasterWalls")
	if plaster_group:
		var hue_shift: float = (float(h % 13) - 6.0) * 0.01  # -0.06 .. +0.06
		var mod_col: Color = Color(
			clampf(1.0 + hue_shift, 0.88, 1.06),
			clampf(1.0 + hue_shift * 0.5, 0.88, 1.05),
			clampf(1.0 - hue_shift, 0.88, 1.06),
			1.0
		)
		_tint_preserving_textures(plaster_group, mod_col, true)

	# 2. Optional vines, barrels, crates, fences & specialized shop props
	var props_root = node.get_node_or_null("ExteriorProps")
	if props_root:
		var vines = props_root.get_node_or_null("PropVines")
		if vines:
			vines.visible = (style == "ELF") or ((h % 3) == 0)
		var barrel = props_root.get_node_or_null("PropBarrel")
		if barrel:
			barrel.visible = ((h / 3) % 2) == 0
		var crate = props_root.get_node_or_null("PropCrate")
		if crate:
			crate.visible = ((h / 5) % 2) == 0
		var fence = props_root.get_node_or_null("PropFence")
		if fence:
			fence.visible = ((h / 7) % 2) == 0

		# Shop archetype prop specialization (Market vs Blacksmith vs Tavern)
		var market_props = props_root.get_node_or_null("MarketProps")
		var smith_props = props_root.get_node_or_null("BlacksmithProps")
		var tavern_props = props_root.get_node_or_null("TavernProps")
		if market_props:
			market_props.visible = (btype == "SHOP_MARKET")
		if smith_props:
			smith_props.visible = (btype == "SHOP_BLACKSMITH")
		if tavern_props:
			tavern_props.visible = (btype == "SHOP_TAVERN")


func _get_active_surface_material(mi: MeshInstance3D, surf_idx: int) -> Material:
	if mi.material_override:
		return mi.material_override
	var override_mat: Material = mi.get_surface_override_material(surf_idx)
	if override_mat:
		return override_mat
	if mi.mesh and surf_idx < mi.mesh.get_surface_count():
		return mi.mesh.surface_get_material(surf_idx)
	return null


func _tint_preserving_textures(node: Node, tint_color: Color, multiply_mode: bool = true) -> void:
	"""Modulates existing textured materials without stripping albedo/normal/roughness maps."""
	if node is MeshInstance3D and (node as MeshInstance3D).mesh:
		var mi: MeshInstance3D = node as MeshInstance3D
		var surf_count: int = mi.mesh.get_surface_count()
		for s in range(surf_count):
			var base_mat: Material = _get_active_surface_material(mi, s)
			if base_mat is BaseMaterial3D:
				var dup: BaseMaterial3D = base_mat.duplicate() as BaseMaterial3D
				if multiply_mode and dup.albedo_texture != null:
					# Preserve texture map detail cleanly while shifting color
					dup.albedo_color = Color(
						dup.albedo_color.r * tint_color.r,
						dup.albedo_color.g * tint_color.g,
						dup.albedo_color.b * tint_color.b,
						dup.albedo_color.a
					)
				elif multiply_mode and dup.albedo_color != Color(1, 1, 1, 1):
					dup.albedo_color = dup.albedo_color.lerp(tint_color, 0.72)
				else:
					dup.albedo_color = tint_color
				mi.set_surface_override_material(s, dup)

	for child in node.get_children():
		_tint_preserving_textures(child, tint_color, multiply_mode)


func _load_mipmapped_texture(res_path: String, force_srgb: bool = true) -> Texture2D:
	if _tex_cache.has(res_path):
		return _tex_cache[res_path]
	if not ResourceLoader.exists(res_path):
		return null
	var raw_res: Resource = load(res_path)
	if raw_res is Texture2D:
		var raw_img: Image = (raw_res as Texture2D).get_image()
		if raw_img != null and not raw_img.is_empty():
			var img: Image = raw_img.duplicate() as Image
			if img.is_compressed():
				img.decompress()
			if force_srgb:
				img.srgb_to_linear()
			img.generate_mipmaps()
			var tex: ImageTexture = ImageTexture.create_from_image(img)
			_tex_cache[res_path] = tex
			return tex
	return raw_res as Texture2D


func _load_cached_scene(res_path: String) -> PackedScene:
	if _packed_cache.has(res_path):
		return _packed_cache[res_path]
	if not ResourceLoader.exists(res_path):
		return null
	var ps: PackedScene = load(res_path) as PackedScene
	if ps:
		_packed_cache[res_path] = ps
	return ps


func _build_crenellated_wall_mesh() -> ArrayMesh:
	"""
	Builds a unit-width (X in [-0.5, +0.5]) 2-surface fortified battlement segment:
	- Surface 0: Deep stone/brick wall body (y = -2.5..5.2, battered z = +-1.15 -> +-0.95) + 3 merlons.
	- Surface 1: Cut stone parapet coping (y = 5.15..5.55) + walkway + merlon capstones.
	"""
	var mesh := ArrayMesh.new()

	var brick_albedo: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_brick_base_color.png", false)
	var brick_normal: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_brick_normal.png", false)
	var brick_rough: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_brick_roughness.png", false)

	var trim_albedo: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_rock_trim_base_color.png", false)
	var trim_normal: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_rock_trim_normal.png", false)

	var wall_mat := StandardMaterial3D.new()
	wall_mat.albedo_color = Color(0.84, 0.81, 0.77, 1.0)
	wall_mat.roughness = 0.82
	wall_mat.metallic = 0.04
	wall_mat.uv1_scale = Vector3(3.2, 2.2, 1.0)
	if brick_albedo:
		wall_mat.albedo_texture = brick_albedo
	if brick_normal:
		wall_mat.normal_enabled = true
		wall_mat.normal_texture = brick_normal
		wall_mat.normal_scale = 0.8
	if brick_rough:
		wall_mat.roughness_texture = brick_rough

	var trim_mat := StandardMaterial3D.new()
	trim_mat.albedo_color = Color(0.76, 0.74, 0.70, 1.0)
	trim_mat.roughness = 0.68
	trim_mat.metallic = 0.05
	trim_mat.uv1_scale = Vector3(3.0, 1.0, 1.0)
	if trim_albedo:
		trim_mat.albedo_texture = trim_albedo
	if trim_normal:
		trim_mat.normal_enabled = true
		trim_mat.normal_texture = trim_normal
		trim_mat.normal_scale = 0.6

	var add_box := func(st: SurfaceTool, c: Vector3, s: Vector3, u_mult: float = 1.0, v_mult: float = 1.0) -> void:
		var hx: float = s.x * 0.5
		var hy: float = s.y * 0.5
		var hz: float = s.z * 0.5
		var p000 := c + Vector3(-hx, -hy, -hz)
		var p001 := c + Vector3(-hx, -hy,  hz)
		var p010 := c + Vector3(-hx,  hy, -hz)
		var p011 := c + Vector3(-hx,  hy,  hz)
		var p100 := c + Vector3( hx, -hy, -hz)
		var p101 := c + Vector3( hx, -hy,  hz)
		var p110 := c + Vector3( hx,  hy, -hz)
		var p111 := c + Vector3( hx,  hy,  hz)
		# Godot front-face is CW when viewed from outside: (a -> e -> d) and (a -> d -> b)
		var add_quad := func(a: Vector3, b: Vector3, d: Vector3, e: Vector3, n: Vector3) -> void:
			st.set_normal(n)
			st.set_uv(Vector2(0.0, v_mult)); st.add_vertex(a)
			st.set_uv(Vector2(0.0, 0.0)); st.add_vertex(e)
			st.set_uv(Vector2(u_mult, 0.0)); st.add_vertex(d)
			st.set_uv(Vector2(0.0, v_mult)); st.add_vertex(a)
			st.set_uv(Vector2(u_mult, 0.0)); st.add_vertex(d)
			st.set_uv(Vector2(u_mult, v_mult)); st.add_vertex(b)
		# +Z front, -Z back, +X right, -X left, +Y top
		add_quad.call(p001, p101, p111, p011, Vector3(0, 0, 1))
		add_quad.call(p100, p000, p010, p110, Vector3(0, 0, -1))
		add_quad.call(p101, p100, p110, p111, Vector3(1, 0, 0))
		add_quad.call(p000, p001, p011, p010, Vector3(-1, 0, 0))
		add_quad.call(p011, p111, p110, p010, Vector3(0, 1, 0))

	# Surface 0: Main stone body + battered plinth + 3 exterior merlons + rear parapet wall
	var st0 := SurfaceTool.new()
	st0.begin(Mesh.PRIMITIVE_TRIANGLES)
	add_box.call(st0, Vector3(0.0, -1.25, 0.0), Vector3(1.02, 2.5, 2.4), 1.0, 0.4)
	add_box.call(st0, Vector3(0.0, 2.6, 0.0), Vector3(1.01, 5.2, 1.9), 1.0, 1.0)
	add_box.call(st0, Vector3(0.0, 5.8, -0.78), Vector3(1.01, 0.7, 0.36), 1.0, 0.25)
	for mx in [-0.33, 0.0, 0.33]:
		add_box.call(st0, Vector3(mx, 5.95, 0.80), Vector3(0.18, 0.9, 0.42), 0.22, 0.3)
	st0.set_material(wall_mat)
	st0.commit(mesh)

	# Surface 1: Stone parapet corbel, walkway slab, and merlon capstones
	var st1 := SurfaceTool.new()
	st1.begin(Mesh.PRIMITIVE_TRIANGLES)
	add_box.call(st1, Vector3(0.0, 5.35, 0.0), Vector3(1.02, 0.36, 2.18), 1.0, 0.25)
	for mx in [-0.33, 0.0, 0.33]:
		add_box.call(st1, Vector3(mx, 6.46, 0.80), Vector3(0.20, 0.14, 0.48), 0.25, 0.15)
	st1.set_material(trim_mat)
	st1.commit(mesh)

	return mesh


func _create_watchtower_node(tname: String, pos: Vector3, rot_y: float, style: String, theme: Dictionary, plinth_mat: StandardMaterial3D) -> Node3D:
	var tower := Node3D.new()
	tower.name = tname
	tower.position = pos
	tower.rotation.y = rot_y

	# Grounded stone foundation skirt (prevents floating on any slope)
	var plinth_body := StaticBody3D.new()
	plinth_body.name = "TowerPhysics"
	var plinth_col := CollisionShape3D.new()
	var col_box := BoxShape3D.new()
	col_box.size = Vector3(4.6, 12.0, 4.6)
	plinth_col.shape = col_box
	plinth_col.position = Vector3(0.0, 4.75, 0.0)
	plinth_body.add_child(plinth_col)

	var plinth_mi := MeshInstance3D.new()
	var plinth_mesh := BoxMesh.new()
	plinth_mesh.size = Vector3(4.8, 2.6, 4.8)
	plinth_mesh.material = plinth_mat
	plinth_mi.mesh = plinth_mesh
	plinth_mi.position = Vector3(0.0, -1.2, 0.0)
	plinth_body.add_child(plinth_mi)
	tower.add_child(plinth_body)

	var wall_ps := _load_cached_scene(WATCHTOWER_GLTF_PATHS["wall"])
	var win_ps := _load_cached_scene(WATCHTOWER_GLTF_PATHS["window"])
	var pillar_ps := _load_cached_scene(WATCHTOWER_GLTF_PATHS["pillar"])
	var bar_ps := _load_cached_scene(WATCHTOWER_GLTF_PATHS["barrier"])
	var roof_ps := _load_cached_scene(WATCHTOWER_GLTF_PATHS["roof"])
	var banner_ps := _load_cached_scene(WATCHTOWER_GLTF_PATHS["banner"])
	var torch_ps := _load_cached_scene(WATCHTOWER_GLTF_PATHS["torch"])

	# Ground floor + Upper floor 4m x 4m masonry tower shaft
	for story_y in [0.0, 4.0]:
		var wall_rot_specs: Array = [
			[Vector3(0.0, story_y, 1.8), 0.0, win_ps if story_y > 1.0 else wall_ps],
			[Vector3(0.0, story_y, -1.8), PI, win_ps if story_y > 1.0 else wall_ps],
			[Vector3(1.8, story_y, 0.0), PI * 0.5, win_ps],
			[Vector3(-1.8, story_y, 0.0), -PI * 0.5, win_ps],
		]
		for spec in wall_rot_specs:
			var ps: PackedScene = spec[2]
			if ps:
				var w := ps.instantiate() as Node3D
				w.position = spec[0]
				w.rotation.y = spec[1]
				tower.add_child(w)
		if pillar_ps:
			for cpos in [Vector3(-1.95, story_y, 1.95), Vector3(1.95, story_y, 1.95), Vector3(-1.95, story_y, -1.95), Vector3(1.95, story_y, -1.95)]:
				var p := pillar_ps.instantiate() as Node3D
				p.position = cpos
				tower.add_child(p)

	# Crenellated battlement gallery at y = 8.0m
	if bar_ps:
		for bspec in [
			[Vector3(0.0, 8.0, 2.05), 0.0],
			[Vector3(0.0, 8.0, -2.05), PI],
			[Vector3(2.05, 8.0, 0.0), PI * 0.5],
			[Vector3(-2.05, 8.0, 0.0), -PI * 0.5],
		]:
			var b := bar_ps.instantiate() as Node3D
			b.position = bspec[0]
			b.rotation.y = bspec[1]
			tower.add_child(b)

	# Conical Village round-tile tower roof
	if roof_ps:
		var roof := roof_ps.instantiate() as Node3D
		roof.position = Vector3(0.0, 9.25, 0.0)
		roof.scale = Vector3(1.06, 1.0, 1.06)
		tower.add_child(roof)

	# Outward racial banner & watchtorch
	if banner_ps:
		var ban := banner_ps.instantiate() as Node3D
		ban.name = "BannerTower"
		ban.position = Vector3(0.0, 3.6, 2.0)
		ban.scale = Vector3(1.15, 1.15, 1.15)
		_tint_preserving_textures(ban, theme.get("accent", Color.WHITE), true)
		tower.add_child(ban)

	if torch_ps:
		var torch := torch_ps.instantiate() as Node3D
		torch.position = Vector3(0.0, 5.4, 2.45)
		tower.add_child(torch)

	var tlight := OmniLight3D.new()
	tlight.name = "WatchtowerLight"
	tlight.position = Vector3(0.0, 6.2, 2.9)
	tlight.light_color = theme.get("brazier_light", Color(1.0, 0.72, 0.30))
	tlight.light_energy = 2.0
	tlight.omni_range = 13.0
	tlight.set_meta("base_energy", 2.0)
	tlight.visible = (_current_night_factor > 0.02)
	tower.add_child(tlight)
	_building_lights.append(tlight)

	return tower


func _build_perimeter_walls() -> void:
	if not _perimeter_walls_node:
		_perimeter_walls_node = Node3D.new()
		_perimeter_walls_node.name = "PerimeterWalls"
		add_child(_perimeter_walls_node)
	else:
		for child in _perimeter_walls_node.get_children():
			child.queue_free()

	TerrainHeightSampler.ensure_loaded()
	var meta: Dictionary = TerrainHeightSampler.get_metadata()
	var cities: Dictionary = meta.get("ring_1_cities", {})
	if cities.is_empty():
		return

	var wall_unit_mesh: ArrayMesh = _build_crenellated_wall_mesh()
	var wall_transforms: Array[Transform3D] = []

	var plinth_albedo: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_rock_trim_base_color.png", false)
	var plinth_normal: Texture2D = _load_mipmapped_texture("res://assets/buildings/village/t_rock_trim_normal.png", false)
	var plinth_mat := StandardMaterial3D.new()
	plinth_mat.albedo_color = Color(0.72, 0.70, 0.66, 1.0)
	plinth_mat.roughness = 0.76
	plinth_mat.uv1_scale = Vector3(2.0, 1.0, 2.0)
	if plinth_albedo:
		plinth_mat.albedo_texture = plinth_albedo
	if plinth_normal:
		plinth_mat.normal_enabled = true
		plinth_mat.normal_texture = plinth_normal

	# Clear angular buffer around each Gatehouse (+-20m -> 0.083 rad) and Watchtower (+-2.4m -> 0.011 rad)
	const GATE_CLR_RAD: float = 0.082
	const TOWER_CLR_RAD: float = 0.011

	for ckey in cities:
		var c: Dictionary = cities[ckey]
		var cx: float = float(c.get("x", 0.0))
		var cz: float = float(c.get("z", 0.0))
		var style: String = str(c.get("racial_style", "HUMAN"))
		var theme: Dictionary = RACIAL_THEMES.get(style, RACIAL_THEMES["HUMAN"])
		var main_angle: float = atan2(-cz, -cx)

		for g_idx in range(4):
			var gate_a0: float = main_angle + float(g_idx) * PI * 0.5
			var gate_a1: float = gate_a0 + PI * 0.5
			var wt1_a: float = gate_a0 + (PI / 6.0)   # +30 deg intermediate watchtower
			var wt2_a: float = gate_a0 + (PI / 3.0)   # +60 deg intermediate watchtower

			# Spawn 2 intermediate fortified Watchtowers per quadrant = 8 per city (30°, 60°, 120°, ...)
			for wt_idx in range(2):
				var wt_a: float = wt1_a if wt_idx == 0 else wt2_a
				var wx: float = cx + 240.0 * cos(wt_a)
				var wz: float = cz + 240.0 * sin(wt_a)
				var wy: float = TerrainHeightSampler.get_height(wx, wz)
				var tower := _create_watchtower_node(
					"Watchtower_%s_q%d_t%d" % [ckey, g_idx, wt_idx],
					Vector3(wx, wy, wz),
					PI * 0.5 - wt_a,
					style,
					theme,
					plinth_mat
				)
				_perimeter_walls_node.add_child(tower)

			# 3 continuous sub-arcs of crenellated masonry wall connecting gates <-> watchtowers
			var sub_arcs: Array = [
				[gate_a0 + GATE_CLR_RAD, wt1_a - TOWER_CLR_RAD, 9],
				[wt1_a + TOWER_CLR_RAD, wt2_a - TOWER_CLR_RAD, 10],
				[wt2_a + TOWER_CLR_RAD, gate_a1 - GATE_CLR_RAD, 9],
			]
			for arc_idx in range(sub_arcs.size()):
				var a0: float = float(sub_arcs[arc_idx][0])
				var a1: float = float(sub_arcs[arc_idx][1])
				var seg_count: int = int(sub_arcs[arc_idx][2])
				var d_ang: float = (a1 - a0) / float(seg_count)

				# 2 collision boxes per sub-arc (~50m arc each, minimal overhead)
				var col_groups: int = 2
				var col_d_ang: float = (a1 - a0) / float(col_groups)
				for cg in range(col_groups):
					var ca0: float = a0 + float(cg) * col_d_ang
					var ca1: float = ca0 + col_d_ang
					var cp0: Vector2 = Vector2(cx + 240.0 * cos(ca0), cz + 240.0 * sin(ca0))
					var cp1: Vector2 = Vector2(cx + 240.0 * cos(ca1), cz + 240.0 * sin(ca1))
					var cmid: Vector2 = (cp0 + cp1) * 0.5
					var c_ang: float = (ca0 + ca1) * 0.5
					var cgy: float = TerrainHeightSampler.get_height(cmid.x, cmid.y)
					var w_body := StaticBody3D.new()
					w_body.name = "WallCol_%s_g%d_a%d_%d" % [ckey, g_idx, arc_idx, cg]
					w_body.position = Vector3(cmid.x, cgy + 3.0, cmid.y)
					w_body.rotation.y = PI * 0.5 - c_ang
					var cshape := CollisionShape3D.new()
					var box := BoxShape3D.new()
					box.size = Vector3(cp0.distance_to(cp1) + 0.4, 6.2, 2.2)
					cshape.shape = box
					w_body.add_child(cshape)
					_perimeter_walls_node.add_child(w_body)

				# Individual curved battlement visual segments pushed into 1 shared MultiMesh
				for s in range(seg_count):
					var sa0: float = a0 + float(s) * d_ang
					var sa1: float = sa0 + d_ang
					var p0: Vector2 = Vector2(cx + 240.0 * cos(sa0), cz + 240.0 * sin(sa0))
					var p1: Vector2 = Vector2(cx + 240.0 * cos(sa1), cz + 240.0 * sin(sa1))
					var mid: Vector2 = (p0 + p1) * 0.5
					var seg_len: float = p0.distance_to(p1)
					var mid_a: float = (sa0 + sa1) * 0.5
					var gy: float = TerrainHeightSampler.get_height(mid.x, mid.y)
					# Tangent basis: Local +Z points radially outward, scaled_local stretches strictly along Local X tangent chord
					var basis_x := Basis(Vector3.UP, PI * 0.5 - mid_a).scaled_local(Vector3(seg_len, 1.0, 1.0))
					wall_transforms.append(Transform3D(basis_x, Vector3(mid.x, gy, mid.y)))

	# Single-draw-call MultiMeshInstance3D for all 5 cities' masonry curtain walls
	if not wall_transforms.is_empty():
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = wall_unit_mesh
		mm.instance_count = wall_transforms.size()
		for i in range(wall_transforms.size()):
			mm.set_instance_transform(i, wall_transforms[i])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "CurvedCurtainWallsMultiMesh"
		mmi.multimesh = mm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		_perimeter_walls_node.add_child(mmi)


func _update_plaque(node: Node3D, bld: Dictionary) -> void:
	var plaque: Label3D = node.get_node_or_null("PropertyPlaque")
	if not plaque:
		plaque = node.get_node_or_null("PalacePlaque")
		if not plaque:
			plaque = node.get_node_or_null("GatePlaque")

	if not plaque:
		return

	var for_sale: bool = bool(bld.get("for_sale", false))
	var price: float = float(bld.get("sale_price", 0.0))
	var owner_name: String = str(bld.get("owner_name", ""))
	var btype: String = bld.get("building_type", "")

	if btype == "GODMOTHER_PALACE":
		var style: String = bld.get("racial_style", "DIVINE")
		plaque.text = "%s PALACE" % style
		plaque.modulate = Color(1.0, 0.9, 0.35, 1.0)
	elif btype == "CITY_GATE":
		plaque.text = owner_name if owner_name != "" else "CITY GATE"
		plaque.modulate = Color(1.0, 0.85, 0.4, 1.0)
	elif for_sale:
		plaque.text = "FOR SALE: %d cr" % int(price)
		plaque.modulate = Color(1.0, 0.82, 0.25, 1.0)
	else:
		var label_str = owner_name if owner_name != "" else "Private Residence"
		plaque.text = "Owner: %s" % label_str
		plaque.modulate = Color(0.8, 0.95, 0.8, 1.0)


func _update_distance_streaming() -> void:
	var vp = get_viewport()
	if vp:
		var active_cam := vp.get_camera_3d()
		if active_cam and is_instance_valid(active_cam):
			_camera_node = active_cam
	if not _camera_node or not is_instance_valid(_camera_node):
		_find_camera()
		if not _camera_node:
			return

	var cam_pos: Vector3 = _camera_node.global_position
	var has_far: bool = (
		_far_walls_mmi != null and is_instance_valid(_far_walls_mmi)
		and _far_roofs_mmi != null and is_instance_valid(_far_roofs_mmi)
	)
	var mm_w: MultiMesh = _far_walls_mmi.multimesh if has_far else null
	var mm_r: MultiMesh = _far_roofs_mmi.multimesh if has_far else null

	# Mutually exclusive handoff: near (<580m) shows modular glTF .tscn; far (>=580m) shows 2-draw-call Orbital MultiMesh
	for i in range(_far_proxy_records.size()):
		var rec: Dictionary = _far_proxy_records[i]
		var house: Node3D = rec.get("node", null)
		if not is_instance_valid(house):
			continue
		var dist_sq: float = cam_pos.distance_squared_to(house.global_position)
		var new_state: int = 1 if (dist_sq <= HOUSE_STREAMING_DIST_SQ) else 0
		if new_state != int(rec.get("state", -1)):
			rec["state"] = new_state
			house.visible = (new_state == 1)
			if mm_w != null and mm_r != null:
				if new_state == 1:
					mm_w.set_instance_transform(i, PARKED_PROXY_XF)
					mm_r.set_instance_transform(i, PARKED_PROXY_XF)
				else:
					mm_w.set_instance_transform(i, rec["wall_xf"])
					mm_r.set_instance_transform(i, rec["roof_xf"])

	# Distance-cull building OmniLight3D nodes strictly within 180m of camera AND night_factor > 0.02
	for light in _building_lights:
		if is_instance_valid(light):
			var dist_sq: float = cam_pos.distance_squared_to(light.global_position)
			light.visible = (_current_night_factor > 0.02) and (dist_sq <= LIGHT_CULL_DIST_SQ)


func populate_offline_preview() -> void:
	"""Populates the 5 cities with offline layout preview when bridge is not running."""
	var mock_cities = [
		{"city_id": "sylvanor", "name": "Sylvanor", "racial_style": "ELF", "x": 1150.0, "z": 0.0},
		{"city_id": "aurelia", "name": "Aurelia", "racial_style": "HUMAN", "x": 355.37, "z": 1093.71},
		{"city_id": "fenris_hold", "name": "Fenris Hold", "racial_style": "BEASTHUMAN", "x": -930.37, "z": 675.95},
		{"city_id": "malakor", "name": "Malakor", "racial_style": "DEMON", "x": -930.37, "z": -675.95},
		{"city_id": "drakonis_spire", "name": "Drakonis Spire", "racial_style": "DRAGON", "x": 355.37, "z": -1093.71},
	]

	var mock_buildings: Array = []
	for c in mock_cities:
		var cid: String = c["city_id"]
		var style: String = c["racial_style"]
		var cx: float = float(c["x"])
		var cz: float = float(c["z"])

		# Palace
		mock_buildings.append({
			"building_id": "bld_%s_palace" % cid,
			"city_id": cid,
			"building_type": "GODMOTHER_PALACE",
			"racial_style": style,
			"x": cx,
			"z": cz,
			"rotation_y": 0.0,
			"for_sale": false,
		})

		# 4 Gates (Local +Z outward along radial, Local X flush tangent along r = 240m wall)
		var main_angle = atan2(-cz, -cx)
		for g_idx in range(4):
			var a = main_angle + (g_idx * PI * 0.5)
			mock_buildings.append({
				"building_id": "bld_%s_gate_%d" % [cid, g_idx],
				"city_id": cid,
				"building_type": "CITY_GATE",
				"racial_style": style,
				"x": cx + 240.0 * cos(a),
				"z": cz + 240.0 * sin(a),
				"rotation_y": PI * 0.5 - a,
				"for_sale": false,
				"owner_name": "%s Gate %d" % [c["name"], g_idx + 1],
			})

		# 44 Non-Overlapping Quadrant Buildings (matches sim_core/world/city_layout.py 1-to-1)
		var quad_slots_even: Array = [
			[68.0, 24.0, "inward", "SHOP_MARKET", 420.0, false],
			[86.0, 45.0, "inward", "SHOP_TAVERN", 480.0, false],
			[68.0, 66.0, "inward", "HOUSE_T2_TOWNHOUSE", 320.0, false],
			[116.0, 20.0, "boulevard_ccw", "HOUSE_T1_COTTAGE", 180.0, false],
			[132.0, 37.0, "outward", "HOUSE_T2_TOWNHOUSE", 330.0, true],
			[132.0, 53.0, "outward", "HOUSE_T1_COTTAGE", 190.0, true],
			[116.0, 70.0, "boulevard_cw", "SHOP_BLACKSMITH", 440.0, false],
			[174.0, 20.0, "inward", "HOUSE_T1_COTTAGE", 175.0, false],
			[196.0, 37.0, "inward", "HOUSE_T3_MANOR", 590.0, false],
			[196.0, 53.0, "inward", "HOUSE_T1_COTTAGE", 185.0, true],
			[174.0, 70.0, "inward", "HOUSE_T2_TOWNHOUSE", 315.0, false],
		]
		var quad_slots_odd: Array = [
			[68.0, 24.0, "inward", "SHOP_MARKET", 420.0, false],
			[86.0, 45.0, "inward", "SHOP_BLACKSMITH", 450.0, true],
			[68.0, 66.0, "inward", "HOUSE_T2_TOWNHOUSE", 320.0, false],
			[116.0, 20.0, "boulevard_ccw", "HOUSE_T1_COTTAGE", 180.0, false],
			[132.0, 37.0, "outward", "HOUSE_T2_TOWNHOUSE", 330.0, true],
			[132.0, 53.0, "outward", "HOUSE_T1_COTTAGE", 190.0, true],
			[116.0, 70.0, "boulevard_cw", "HOUSE_T2_TOWNHOUSE", 340.0, false],
			[174.0, 20.0, "inward", "HOUSE_T1_COTTAGE", 175.0, false],
			[196.0, 37.0, "inward", "HOUSE_T3_MANOR", 590.0, false],
			[196.0, 53.0, "inward", "HOUSE_T1_COTTAGE", 185.0, true],
			[174.0, 70.0, "inward", "HOUSE_T2_TOWNHOUSE", 315.0, false],
		]
		var h_idx: int = 0
		for q in range(4):
			var quad_base_angle: float = main_angle + float(q) * (PI * 0.5)
			var slots: Array = quad_slots_even if (q % 2 == 0) else quad_slots_odd
			for slot_i in range(slots.size()):
				var s: Array = slots[slot_i]
				h_idx += 1
				var radius: float = float(s[0])
				var deg_off: float = float(s[1])
				var face_mode: String = str(s[2])
				var btype: String = str(s[3])
				var price: float = float(s[4])
				var is_sale: bool = bool(s[5])
				if q == 3 and slot_i == 8:
					is_sale = true
					price = 620.0
				var ang: float = fposmod(quad_base_angle + deg_to_rad(deg_off), TAU)
				var face_angle: float = ang
				if face_mode == "inward":
					face_angle = ang + PI
				elif face_mode == "boulevard_ccw":
					face_angle = quad_base_angle - (PI * 0.5)
				elif face_mode == "boulevard_cw":
					face_angle = quad_base_angle + PI
				var fp_rad: float = 8.0 if "COTTAGE" in btype else (11.0 if "TOWNHOUSE" in btype else 14.0)
				mock_buildings.append({
					"building_id": "bld_%s_seed_%02d" % [cid, h_idx],
					"city_id": cid,
					"building_type": btype,
					"racial_style": style,
					"x": cx + radius * cos(ang),
					"z": cz + radius * sin(ang),
					"rotation_y": fposmod((PI * 0.5) - face_angle, TAU),
					"footprint_radius": fp_rad,
					"for_sale": is_sale,
					"sale_price": price,
					"owner_name": "Citizen %d" % h_idx if not is_sale else "",
				})

	_spawn_buildings(mock_buildings)
