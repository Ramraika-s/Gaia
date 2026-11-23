# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/cities_and_buildings_manager.gd
# Spawns and manages 5 Equidistant Gated Ring 1 Cities, God-Mother Palaces,
# modular walk-in housing & shops, live BUILDING_SYNC, and distance-streamed LOD for 60 FPS.

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
		"accent": Color(0.2, 0.85, 0.45, 1.0),
		"secondary": Color(0.85, 0.88, 0.92, 1.0),
		"title_prefix": "Sylvanor",
	},
	"HUMAN": {
		"accent": Color(1.0, 0.85, 0.35, 1.0),
		"secondary": Color(0.82, 0.45, 0.28, 1.0),
		"title_prefix": "Aurelia",
	},
	"BEASTHUMAN": {
		"accent": Color(0.95, 0.65, 0.15, 1.0),
		"secondary": Color(0.42, 0.28, 0.16, 1.0),
		"title_prefix": "Fenris Hold",
	},
	"DEMON": {
		"accent": Color(0.88, 0.15, 0.2, 1.0),
		"secondary": Color(0.18, 0.15, 0.22, 1.0),
		"title_prefix": "Malakor",
	},
	"DRAGON": {
		"accent": Color(1.0, 0.75, 0.2, 1.0),
		"secondary": Color(0.24, 0.26, 0.3, 1.0),
		"title_prefix": "Drakonis Spire",
	},
}

# Distance-based streaming: houses and detailed stalls cull beyond 650m
const HOUSE_STREAMING_DIST_SQ: float = 650.0 * 650.0
const CHECK_INTERVAL: float = 0.2  # 5 Hz throttle

var _buildings_by_id: Dictionary = {}        # bld_id -> Node3D instance
var _building_records: Dictionary = {}       # bld_id -> Dictionary
var _streamable_houses: Array[Node3D] = []    # List of houses subject to distance culling
var _check_timer: float = 0.0
var _camera_node: Camera3D = null
var _sky_controller: Node = null
var _current_night_factor: float = 0.0


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
			_spawn_single_building(bld_data)
		else:
			_update_plaque(node, bld_data)
	else:
		# Incrementally spawn newly constructed / frontier building
		_spawn_single_building(bld_data)


func _on_night_factor_changed(nf: float) -> void:
	_current_night_factor = nf
	for bid in _buildings_by_id:
		var node: Node3D = _buildings_by_id[bid]
		if is_instance_valid(node):
			_apply_building_night_lighting(node, nf)


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

	for bld_data in buildings:
		_spawn_single_building(bld_data)

	print("[CitiesManager] Successfully materialized %d city buildings and landmarks." % _buildings_by_id.size())


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

	# Apply racial accent colors
	_apply_racial_theming(inst, style, btype)

	# Update property plaque
	_update_plaque(inst, bld)

	add_child(inst)
	_buildings_by_id[bid] = inst
	_building_records[bid] = bld

	# Apply night lighting state
	_apply_building_night_lighting(inst, _current_night_factor)

	# Categorize for distance streaming: Palaces and Gates stay visible as landmarks; houses stream
	if btype not in ["GODMOTHER_PALACE", "CITY_GATE"]:
		_streamable_houses.append(inst)


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
		if "window" in mname or "glass" in mname or "lantern" in mname or "brazier" in mname or "light" in mname:
			var mat: Material = mi.material_override
			if not mat and mi.get_surface_override_material_count() > 0:
				mat = mi.get_surface_override_material(0)
			if mat is StandardMaterial3D:
				var smat: StandardMaterial3D = mat as StandardMaterial3D
				smat.emission_enabled = (nf > 0.05)
				smat.emission = Color(1.0, 0.82, 0.45)
				smat.emission_energy_multiplier = 1.6 * nf

	for child in node.get_children():
		_apply_building_night_lighting(child, nf)


func _apply_racial_theming(node: Node3D, style: String, btype: String) -> void:
	if not (style in RACIAL_THEMES):
		return

	var theme: Dictionary = RACIAL_THEMES[style]
	var accent_col: Color = theme["accent"]

	# Tint banners if present
	var banners = node.get_node_or_null("Banners")
	if banners:
		for b in banners.get_children():
			_tint_mesh_nodes(b, accent_col)

	var b1 = node.get_node_or_null("BannerL")
	if b1:
		_tint_mesh_nodes(b1, accent_col)
	var b2 = node.get_node_or_null("BannerR")
	if b2:
		_tint_mesh_nodes(b2, accent_col)


func _tint_mesh_nodes(node: Node, color: Color) -> void:
	if node is MeshInstance3D and (node as MeshInstance3D).mesh:
		var mi: MeshInstance3D = node as MeshInstance3D
		var mat = StandardMaterial3D.new()
		mat.albedo_color = color
		mat.roughness = 0.4
		mi.material_override = mat

	for child in node.get_children():
		_tint_mesh_nodes(child, color)


func _update_plaque(node: Node3D, bld: Dictionary) -> void:
	var plaque: Label3D = node.get_node_or_null("PropertyPlaque")
	if not plaque:
		# Check for palace/gate plaques
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
	if not _camera_node or not is_instance_valid(_camera_node):
		_find_camera()
		if not _camera_node:
			return

	var cam_pos: Vector3 = _camera_node.global_position

	# Streaming distance: toggle visibility for modular houses/shops outside 650m
	for house in _streamable_houses:
		if not is_instance_valid(house):
			continue
		var dist_sq: float = cam_pos.distance_squared_to(house.global_position)
		house.visible = (dist_sq <= HOUSE_STREAMING_DIST_SQ)


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

		# 4 Gates
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
				"rotation_y": a,
				"for_sale": false,
				"owner_name": "Gate Watch %d" % (g_idx + 1),
			})

		# 12 Sample Houses & Shops
		var archetypes = ["HOUSE_T1_COTTAGE", "HOUSE_T2_TOWNHOUSE", "HOUSE_T3_MANOR", "SHOP_MARKET"]
		for h in range(12):
			var dist = 80.0 + (h % 3) * 45.0
			var ang = main_angle + 0.4 + (h * 0.45)
			var btype = archetypes[h % archetypes.size()]
			var is_sale = (h % 3 == 0)
			mock_buildings.append({
				"building_id": "bld_%s_h_%02d" % [cid, h + 1],
				"city_id": cid,
				"building_type": btype,
				"racial_style": style,
				"x": cx + dist * cos(ang),
				"z": cz + dist * sin(ang),
				"rotation_y": ang + PI,
				"for_sale": is_sale,
				"sale_price": 200.0 + (h * 40.0),
				"owner_name": "Citizen %d" % (h + 1) if not is_sale else "",
			})

	_spawn_buildings(mock_buildings)
