# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/mortal_actor.gd
# Rigged mortal actor for the 60-120 Reality Bubble pool.
# Supports all 5 races, 2 genders, stage scaling, crying tears, Oracle aura, and Dragon morph.

extends Node3D

const STAGE_SCALES: Dictionary = {
	"INFANT": 0.45,
	"CHILD": 0.75,
	"ADULT": 1.00,
	"ELDER": 0.94,
}

const RACE_ADULT_MULTIPLIERS: Dictionary = {
	"HUMAN": 1.00,
	"ELF": 1.06,
	"DRAGON": 1.05,
	"BEASTHUMAN": 1.02,
	"DEMON": 1.08,
}

const RACE_ASSET_PATHS: Dictionary = {
	"HUMAN_GIRL": "res://assets/mortals/races/base_human_female.glb",
	"HUMAN_BOY": "res://assets/mortals/races/base_human_male.gltf",
	"ELF_BOY": "res://assets/mortals/races/base_elf_male.glb",
	"ELF_GIRL": "res://assets/mortals/races/base_elf_female.glb",
	"DRAGON_HUMANOID": "res://assets/mortals/races/base_dragon_humanoid.gltf",
	"DRAGON_TRUE": "res://assets/mortals/base_dragon_true.glb",
	"BEASTHUMAN_BOY": "res://assets/mortals/races/base_beasthuman_male.glb",
	"BEASTHUMAN_GIRL": "res://assets/mortals/races/base_beasthuman_female.glb",
	"DEMON_ALL": "res://assets/mortals/races/base_demon.gltf",
}

# Shared static scene cache to avoid redundant disk reads across pool
static var _scene_cache: Dictionary = {}

@onready var visual_root: Node3D = $VisualRoot
@onready var humanoid_mesh_node: Node3D = $VisualRoot/HumanoidMeshNode
@onready var true_dragon_mesh_node: Node3D = $VisualRoot/TrueDragonMeshNode
@onready var crying_particles: GPUParticles3D = $VisualRoot/CryingParticles
@onready var crying_audio: AudioStreamPlayer3D = $VisualRoot/CryingAudio
@onready var oracle_aura_particles: GPUParticles3D = $VisualRoot/OracleAuraParticles
@onready var fear_aura_ring: Node3D = $VisualRoot/FearAuraRing
@onready var nameplate_label: Label3D = $NameplateLabel
@onready var morph_controller: Node3D = $DragonMorphController

var agent_id: String = ""
var race: String = "HUMAN"
var gender: String = "GIRL"
var stage: String = "ADULT"
var full_name: String = "Citizen"
var dynasty: String = "Founder"
var is_crying: bool = false
var is_oracle: bool = false
var dragon_form: String = "HUMANOID_DRAGON"

var target_position: Vector3 = Vector3.ZERO
var target_rotation_y: float = 0.0
var is_pool_active: bool = false

var _current_active_key: String = ""
var _instanced_mesh_nodes: Dictionary = {}
var _walk_time: float = 0.0


func _ready() -> void:
	visible = false
	_preload_base_scenes()
	if morph_controller:
		morph_controller.humanoid_node = humanoid_mesh_node
		morph_controller.true_dragon_node = true_dragon_mesh_node
		morph_controller.fear_aura_ring = fear_aura_ring


func _preload_base_scenes() -> void:
	# Ensure scenes are cached
	for key in RACE_ASSET_PATHS:
		var path: String = RACE_ASSET_PATHS[key]
		if not _scene_cache.has(key) and ResourceLoader.exists(path):
			var res: Resource = load(path)
			if res is PackedScene:
				_scene_cache[key] = res


func bind_agent_data(data: Dictionary) -> void:
	agent_id = data.get("agent_id", "")
	race = data.get("race", "HUMAN").to_upper()
	gender = data.get("gender", "GIRL").to_upper()
	stage = data.get("stage", "ADULT").to_upper()
	full_name = data.get("name", "Citizen")
	dynasty = data.get("dynasty", "Founder")
	is_crying = data.get("crying", false)
	is_oracle = data.get("is_oracle", false)
	dragon_form = data.get("dragon_form", "HUMANOID_DRAGON")

	var px: float = float(data.get("x", global_position.x))
	var py: float = float(data.get("y", global_position.y))
	var pz: float = float(data.get("z", global_position.z))
	target_position = Vector3(px, py, pz)

	var rot: float = float(data.get("rotation_y", rotation.y))
	target_rotation_y = rot

	if not is_pool_active:
		global_position = target_position
		rotation.y = target_rotation_y
		is_pool_active = true
		visible = true

	_apply_visuals()


func release_to_pool() -> void:
	is_pool_active = false
	visible = false
	agent_id = ""
	if crying_particles:
		crying_particles.emitting = false
		crying_particles.visible = false
	if crying_audio and crying_audio.playing:
		crying_audio.stop()
	if oracle_aura_particles:
		oracle_aura_particles.emitting = false
		oracle_aura_particles.visible = false
	if fear_aura_ring:
		fear_aura_ring.visible = false
	if morph_controller:
		morph_controller.set_is_dragon(false)
		morph_controller.set_form("HUMANOID_DRAGON", false)


func _apply_visuals() -> void:
	var mesh_key: String = _resolve_mesh_key()
	_switch_mesh_node(mesh_key)

	# Life stage scale
	var stage_scale: float = STAGE_SCALES.get(stage, 1.0)
	var race_mult: float = RACE_ADULT_MULTIPLIERS.get(race, 1.0)
	var final_scale: float = stage_scale * (race_mult if stage != "INFANT" else 1.0)

	if race == "DRAGON" and dragon_form == "TRUE_DRAGON":
		visual_root.scale = Vector3.ONE  # True Dragon scaling handled inside TrueDragonMeshNode
	else:
		visual_root.scale = Vector3(final_scale, final_scale, final_scale)

	# Dragon morph controller
	if morph_controller:
		morph_controller.set_is_dragon(race == "DRAGON")
		if race == "DRAGON":
			morph_controller.set_form(dragon_form)

	# Crying state & audio
	if crying_particles:
		crying_particles.visible = is_crying
		crying_particles.emitting = is_crying

	if crying_audio:
		if is_crying and not crying_audio.playing:
			crying_audio.play()
		elif not is_crying and crying_audio.playing:
			crying_audio.stop()

	# Oracle Aura
	if oracle_aura_particles:
		oracle_aura_particles.visible = is_oracle
		oracle_aura_particles.emitting = is_oracle

	# Nameplate
	_update_nameplate(final_scale)


func _resolve_mesh_key() -> String:
	match race:
		"ELF":
			return "ELF_BOY" if gender == "BOY" else "ELF_GIRL"
		"DRAGON":
			return "DRAGON_HUMANOID"
		"BEASTHUMAN":
			return "BEASTHUMAN_BOY" if gender == "BOY" else "BEASTHUMAN_GIRL"
		"DEMON":
			return "DEMON_ALL"
		_:
			return "HUMAN_BOY" if gender == "BOY" else "HUMAN_GIRL"


func _switch_mesh_node(key: String) -> void:
	if key == _current_active_key:
		return

	# Hide previous
	for k in _instanced_mesh_nodes:
		var node: Node = _instanced_mesh_nodes[k]
		if is_instance_valid(node):
			node.visible = false

	_current_active_key = key

	# Check if already instanced under humanoid_mesh_node
	if _instanced_mesh_nodes.has(key):
		var node: Node = _instanced_mesh_nodes[key]
		if is_instance_valid(node):
			node.visible = true
			return

	# Instance from cached PackedScene
	if _scene_cache.has(key):
		var packed: PackedScene = _scene_cache[key]
		var inst: Node = packed.instantiate()
		inst.name = key
		humanoid_mesh_node.add_child(inst)
		_instanced_mesh_nodes[key] = inst
		inst.visible = true
	else:
		# Fallback primitive mesh if asset is unavailable
		var fallback: MeshInstance3D = MeshInstance3D.new()
		var capsule: CapsuleMesh = CapsuleMesh.new()
		capsule.radius = 0.35
		capsule.height = 1.7
		fallback.mesh = capsule
		fallback.name = key + "_fallback"
		humanoid_mesh_node.add_child(fallback)
		_instanced_mesh_nodes[key] = fallback
		fallback.visible = true


func _update_nameplate(current_scale: float) -> void:
	if nameplate_label == null:
		return

	var text: String = ""
	if is_oracle:
		text += "★ [DIVINE ORACLE] ★\n"
	text += "%s %s\n" % [full_name, dynasty]
	text += "[%s • %s]" % [race, stage]

	if is_crying:
		text += " 😭"

	nameplate_label.text = text

	var head_height: float = (1.8 if stage != "INFANT" else 0.9) * current_scale + 0.4
	nameplate_label.position.y = head_height


func _process(delta: float) -> void:
	if not is_pool_active or not visible:
		return

	# Smooth position & rotation interpolation
	global_position = global_position.lerp(target_position, delta * 10.0)
	rotation.y = lerp_angle(rotation.y, target_rotation_y, delta * 8.0)

	# Procedural walk bob
	var dist: float = (target_position - global_position).length()
	if dist > 0.08:
		_walk_time += delta * 12.0
		visual_root.position.y = abs(sin(_walk_time)) * 0.06
	else:
		_walk_time = 0.0
		visual_root.position.y = lerpf(visual_root.position.y, 0.0, delta * 6.0)
