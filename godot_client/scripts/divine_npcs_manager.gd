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
		"position": Vector3(0.0, 18.5, 0.0),
		"scale": 1.15,
		"aura_color": Color(1.0, 0.95, 0.75, 0.85),
	},
	{
		"id": "gm_human",
		"title": "Human God-Mother",
		"epithet": "Protector of Mankind & Balance",
		"vrm_path": "res://assets/deities/gm_human.vrm",
		"position": Vector3(-1800.0, 24.0, 2000.0),
		"scale": 1.0,
		"aura_color": Color(0.3, 0.7, 1.0, 0.85),
	},
	{
		"id": "gm_elf",
		"title": "Elf God-Mother",
		"epithet": "Sylvan Matron & Living Harmony",
		"vrm_path": "res://assets/deities/gm_elf.vrm",
		"position": Vector3(2200.0, 45.0, 2000.0),
		"scale": 1.02,
		"aura_color": Color(0.3, 1.0, 0.5, 0.85),
	},
	{
		"id": "gm_dragon",
		"title": "Dragon God-Mother",
		"epithet": "Draconic Empress & Primordial Flame",
		"vrm_path": "res://assets/deities/gm_dragon.vrm",
		"position": Vector3(2500.0, 85.0, -2500.0),
		"scale": 1.05,
		"aura_color": Color(1.0, 0.35, 0.25, 0.85),
	},
	{
		"id": "gm_beasthuman",
		"title": "Beasthuman God-Mother",
		"epithet": "Wild Pack Guardian & Primal Strength",
		"vrm_path": "res://assets/deities/gm_beasthuman.vrm",
		"position": Vector3(-2500.0, 35.0, -2500.0),
		"scale": 1.0,
		"aura_color": Color(1.0, 0.75, 0.2, 0.85),
	},
	{
		"id": "gm_demon",
		"title": "Demon God-Mother",
		"epithet": "Infernal Sovereign & Abyssal Mistress",
		"vrm_path": "res://assets/deities/gm_demon.vrm",
		"position": Vector3(-3500.0, 60.0, 500.0),
		"scale": 1.04,
		"aura_color": Color(0.85, 0.25, 1.0, 0.85),
	},
]

var _spawned_deities: Dictionary = {}
var _float_time: float = 0.0


func _ready() -> void:
	_spawn_all_deities()


func _spawn_all_deities() -> void:
	for cfg in DEITY_CONFIGS:
		_spawn_deity(cfg)
	print("[DivineNpcsManager] Spawned all 6 Divine Hero NPCs in world.")


func _spawn_deity(cfg: Dictionary) -> void:
	var did: String = cfg["id"]
	var root: Node3D = Node3D.new()
	root.name = "Deity_" + did
	root.position = cfg["position"]
	add_child(root)

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

	_spawned_deities[did] = root


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
		if model:
			model.position.y = hover_offset
			model.rotation.y = sin(_float_time * 0.3) * 0.08


func get_deity(did: String) -> Node3D:
	return _spawned_deities.get(did, null)
