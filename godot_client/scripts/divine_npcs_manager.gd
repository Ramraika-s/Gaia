# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/divine_npcs_manager.gd
# Spawns and manages the 6 Divine Hero NPC models in the world:
# World Goddess (Sanctum) + 5 Racial God-Mothers (Human, Elf, Dragon, Beasthuman, Demon).
# Features floating idle animations, divine aura VFX, and diegetic nameplates.

extends Node3D

const PARTICLE_TEX: String = "res://assets/vfx/particles/circle_05.png"

const DEITY_CONFIGS: Array[Dictionary] = [
	{
		"id": "world_goddess",
		"title": "World Goddess",
		"epithet": "Cosmic Matriarch & Global Adjudicator",
		"vrm_path": "res://assets/deities/world_goddess.vrm",
		"position": Vector3(0.0, 32.0, -15.0),
		"scale": 1.15,
		"aura_color": Color(1.0, 0.95, 0.75, 0.85),
		"dais_offset": 1.2,
	},
	{
		"id": "gm_human",
		"title": "Human God-Mother",
		"epithet": "Protector of Mankind & Balance",
		"vrm_path": "res://assets/deities/gm_human.vrm",
		"position": Vector3(355.37, 18.0, 1091.71),
		"scale": 1.0,
		"aura_color": Color(0.3, 0.7, 1.0, 0.85),
		"dais_offset": 3.2,
	},
	{
		"id": "gm_elf",
		"title": "Elf God-Mother",
		"epithet": "Sylvan Matron & Living Harmony",
		"vrm_path": "res://assets/deities/gm_elf.vrm",
		"position": Vector3(1150.0, 28.0, -2.0),
		"scale": 1.02,
		"aura_color": Color(0.3, 1.0, 0.5, 0.85),
		"dais_offset": 3.2,
	},
	{
		"id": "gm_dragon",
		"title": "Dragon God-Mother",
		"epithet": "Draconic Empress & Primordial Flame",
		"vrm_path": "res://assets/deities/gm_dragon.vrm",
		"position": Vector3(355.37, 68.0, -1095.71),
		"scale": 1.05,
		"aura_color": Color(1.0, 0.35, 0.25, 0.85),
		"dais_offset": 3.2,
	},
	{
		"id": "gm_beasthuman",
		"title": "Beasthuman God-Mother",
		"epithet": "Wild Pack Guardian & Primal Strength",
		"vrm_path": "res://assets/deities/gm_beasthuman.vrm",
		"position": Vector3(-930.36, 24.0, 673.95),
		"scale": 1.0,
		"aura_color": Color(1.0, 0.75, 0.2, 0.85),
		"dais_offset": 3.2,
	},
	{
		"id": "gm_demon",
		"title": "Demon God-Mother",
		"epithet": "Infernal Sovereign & Abyssal Mistress",
		"vrm_path": "res://assets/deities/gm_demon.vrm",
		"position": Vector3(-930.36, 42.0, -677.95),
		"scale": 1.04,
		"aura_color": Color(0.85, 0.25, 1.0, 0.85),
		"dais_offset": 3.2,
	},
]


var _spawned_deities: Dictionary = {}
var _deity_targets: Dictionary = {}  # did -> {pos: Vector3, yaw: float, speed: float, speech: String, activity: String}
var _float_time: float = 0.0


func _ready() -> void:
	_spawn_all_deities()
	_connect_bridge_signals()


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.has_signal("deity_sync_received"):
		bridge.connect("deity_sync_received", Callable(self, "_on_deity_sync_received"))


func _on_deity_sync_received(deities: Array) -> void:
	TerrainHeightSampler.ensure_loaded()
	for d in deities:
		if typeof(d) != TYPE_DICTIONARY:
			continue
		var did: String = d.get("id", "")
		if did == "" or not _spawned_deities.has(did):
			continue

		var px: float = float(d.get("x", 0.0))
		var pz: float = float(d.get("z", 0.0))
		var py: float = float(d.get("y", 0.0))
		# Use heightmap if py is not explicit or ground height
		var ground_y: float = TerrainHeightSampler.get_height(px, pz)
		var dais: float = 1.2 if did == "world_goddess" else 3.2
		var final_y: float = max(py, ground_y + dais)

		var yaw: float = float(d.get("yaw", 0.0))
		var spd: float = float(d.get("speed", 0.0))
		var speech: String = str(d.get("speech_text", ""))
		var activity: String = str(d.get("activity", "IDLE"))

		_deity_targets[did] = {
			"pos": Vector3(px, final_y, pz),
			"yaw": yaw,
			"speed": spd,
			"speech": speech,
			"activity": activity,
		}


func _spawn_all_deities() -> void:
	for cfg in DEITY_CONFIGS:
		_spawn_deity(cfg)
	print("[DivineNpcsManager] Spawned all 6 Divine Hero NPCs in world.")


func _spawn_deity(cfg: Dictionary) -> void:
	TerrainHeightSampler.ensure_loaded()
	var did: String = cfg["id"]
	var root: Node3D = Node3D.new()
	root.name = "Deity_" + did

	var pos_cfg: Vector3 = cfg["position"]
	var ground_y: float = TerrainHeightSampler.get_height(pos_cfg.x, pos_cfg.z)

	var s: float = cfg["scale"]
	var model_container: Node3D = Node3D.new()
	model_container.name = "ModelContainer"
	model_container.scale = Vector3(s, s, s)
	root.add_child(model_container)

	# Load VRM model (with safe stylized fallback)
	var vrm_path: String = cfg["vrm_path"]
	var model_inst: Node = null
	if ResourceLoader.exists(vrm_path):
		var res: Resource = load(vrm_path)
		if res is PackedScene:
			model_inst = res.instantiate()
			model_container.add_child(model_inst)
			var anim: HumanoidAnimator = HumanoidAnimator.new()
			anim.name = "HumanoidAnimator"
			root.add_child(anim)
			anim.bind_target(model_inst)
			anim.set_state(HumanoidAnimator.AnimState.DIVINE_HOVER)

	if model_inst == null:
		# Elegant stylized celestial spire fallback
		var mesh_inst: MeshInstance3D = MeshInstance3D.new()
		var prism: PrismMesh = PrismMesh.new()
		prism.size = Vector3(0.9, 2.4, 0.9)
		mesh_inst.mesh = prism

		var mat: StandardMaterial3D = StandardMaterial3D.new()
		mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mat.albedo_color = cfg["aura_color"]
		mesh_inst.material_override = mat

		model_container.add_child(mesh_inst)

	var min_y: float = _get_min_mesh_y(model_container)
	var dais_offset: float = float(cfg.get("dais_offset", 0.0))
	root.position = Vector3(pos_cfg.x, ground_y + dais_offset - min_y, pos_cfg.z)
	add_child(root)

	# Floating Divine Aura Particles
	var aura: GPUParticles3D = _create_divine_aura(cfg["aura_color"])
	root.add_child(aura)

	# Floating Nameplate Label
	var label: Label3D = Label3D.new()
	label.name = "Nameplate"
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.outline_render_priority = 1
	label.outline_size = 6
	label.font_size = 22
	label.text = "✦ %s ✦\n[%s]" % [cfg["title"], cfg["epithet"]]
	label.modulate = Color(1.0, 1.0, 0.9, 1.0)
	label.outline_modulate = Color(0.1, 0.08, 0.15, 0.9)
	label.position.y = 2.6 * s + 0.3
	root.add_child(label)

	# Floating 3D Overhead Speech Bubble
	var speech_label: Label3D = Label3D.new()
	speech_label.name = "SpeechBubble"
	speech_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	speech_label.outline_render_priority = 2
	speech_label.outline_size = 8
	speech_label.font_size = 24
	speech_label.modulate = Color(1.0, 0.95, 0.7, 1.0)
	speech_label.outline_modulate = Color(0.05, 0.05, 0.1, 0.95)
	speech_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	speech_label.width = 450.0
	speech_label.position.y = 3.6 * s
	speech_label.visible = false
	root.add_child(speech_label)

	_spawned_deities[did] = root
	_deity_targets[did] = {
		"pos": root.position,
		"yaw": root.rotation.y,
		"speed": 0.0,
		"speech": "",
		"activity": "IDLE",
	}


func _create_divine_aura(color: Color) -> GPUParticles3D:
	var particles: GPUParticles3D = GPUParticles3D.new()
	particles.name = "DivineAura"
	particles.amount = 24
	particles.lifetime = 2.0
	particles.visibility_aabb = AABB(Vector3(-2, 0, -2), Vector3(4, 5, 4))

	var pmat: ParticleProcessMaterial = ParticleProcessMaterial.new()
	pmat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	pmat.emission_ring_radius = 1.2
	pmat.emission_ring_inner_radius = 0.4
	pmat.emission_ring_height = 0.2
	pmat.direction = Vector3(0, 1, 0)
	pmat.spread = 10.0
	pmat.initial_velocity_min = 0.6
	pmat.initial_velocity_max = 1.4
	pmat.gravity = Vector3(0, 0.2, 0)
	pmat.color = color
	pmat.scale_min = 0.15
	pmat.scale_max = 0.4
	particles.process_material = pmat

	var draw_mesh: QuadMesh = QuadMesh.new()
	draw_mesh.size = Vector2(0.3, 0.3)
	var dmat: StandardMaterial3D = StandardMaterial3D.new()
	dmat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	dmat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	dmat.vertex_color_use_as_albedo = true
	dmat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	if ResourceLoader.exists(PARTICLE_TEX):
		dmat.albedo_texture = load(PARTICLE_TEX)
	draw_mesh.material = dmat
	particles.draw_pass_1 = draw_mesh

	return particles


func _process(delta: float) -> void:
	_float_time += delta * 1.5
	var hover_offset: float = sin(_float_time) * 0.22

	for did in _spawned_deities:
		var deity: Node3D = _spawned_deities[did]
		var model: Node3D = deity.get_node_or_null("ModelContainer")
		var anim: HumanoidAnimator = deity.get_node_or_null("HumanoidAnimator")
		var speech_bubble: Label3D = deity.get_node_or_null("SpeechBubble")

		var target_info: Dictionary = _deity_targets.get(did, {})
		if not target_info.is_empty():
			var t_pos: Vector3 = target_info.get("pos", deity.position)
			var t_yaw: float = float(target_info.get("yaw", deity.rotation.y))
			var spd: float = float(target_info.get("speed", 0.0))
			var speech: String = str(target_info.get("speech", ""))

			# Smooth movement interpolation
			var prev_pos: Vector3 = deity.position
			deity.position = deity.position.lerp(t_pos, clampf(delta * 4.0, 0.0, 1.0))
			deity.rotation.y = lerp_angle(deity.rotation.y, t_yaw, clampf(delta * 5.0, 0.0, 1.0))

			var actual_spd: float = Vector2(deity.position.x - prev_pos.x, deity.position.z - prev_pos.z).length() / max(0.001, delta)
			var is_moving: bool = (actual_spd > 0.25 or spd > 0.25)

			# Animator state
			if anim:
				if is_moving:
					if anim.current_state != HumanoidAnimator.AnimState.WALK:
						anim.set_state(HumanoidAnimator.AnimState.WALK)
					anim.anim_speed = 1.0
				else:
					if anim.current_state != HumanoidAnimator.AnimState.DIVINE_HOVER:
						anim.set_state(HumanoidAnimator.AnimState.DIVINE_HOVER)

			# Subtle hover bobbing when stationary
			if model and not is_moving:
				model.position.y = hover_offset
				model.rotation.y = sin(_float_time * 0.3) * 0.06
			elif model and is_moving:
				model.position.y = 0.0
				model.rotation.y = 0.0

			# Speech Bubble display
			if speech_bubble:
				if speech != "":
					speech_bubble.text = "“%s”" % speech
					speech_bubble.visible = true
				else:
					speech_bubble.visible = false
		else:
			if model:
				model.position.y = hover_offset
				model.rotation.y = sin(_float_time * 0.3) * 0.08


func get_deity(did: String) -> Node3D:
	return _spawned_deities.get(did, null)


func get_all_deities() -> Dictionary:
	return _spawned_deities


func get_nearest_deity(avatar_pos: Vector3, max_dist: float = 6.0) -> Dictionary:
	"""Returns the nearest deity to avatar_pos within max_dist, or empty dict if none."""
	var best_dist_sq: float = max_dist * max_dist
	var best_result: Dictionary = {}

	for cfg in DEITY_CONFIGS:
		var did: String = cfg["id"]
		var deity_node: Node3D = _spawned_deities.get(did, null)
		if not deity_node:
			continue

		var dist_sq: float = deity_node.global_position.distance_squared_to(avatar_pos)
		if dist_sq < best_dist_sq:
			best_dist_sq = dist_sq
			var target_info: Dictionary = _deity_targets.get(did, {})
			best_result = {
				"type": "DEITY",
				"id": did,
				"deity_id": did,
				"name": cfg["title"],
				"title": cfg["epithet"],
				"race": "DIVINE",
				"mood": "calm",
				"distance": sqrt(dist_sq),
				"node": deity_node,
			}

	return best_result


func _get_min_mesh_y(node: Node, parent_y: float = 0.0) -> float:
	var min_val: float = 0.0
	var found: bool = false

	if node is MeshInstance3D and (node as MeshInstance3D).mesh:
		var aabb: AABB = (node as MeshInstance3D).mesh.get_aabb()
		var y: float = parent_y + aabb.position.y * (node as MeshInstance3D).scale.y
		min_val = y
		found = true

	for child in node.get_children():
		var child_offset: float = parent_y
		if child is Node3D:
			child_offset += (child as Node3D).position.y
		var child_min: float = _get_min_mesh_y(child, child_offset)
		if not found:
			min_val = child_min
			found = true
		else:
			min_val = minf(min_val, child_min)

	return min_val if found else 0.0
