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
	"KNIGHT_BOY": "res://assets/mortals/outfits/full/male_ranger.gltf",
	"KNIGHT_GIRL": "res://assets/mortals/outfits/full/female_ranger.gltf",
}

const GEAR_PROPS_PATHS: Dictionary = {
	"SWORD": "res://assets/buildings/props/sword_bronze.gltf",
	"HOE": "res://assets/buildings/props/axe_bronze.gltf",
	"PICKAXE": "res://assets/buildings/props/pickaxe_bronze.gltf",
	"HAMMER": "res://assets/buildings/props/axe_bronze.gltf",
	"TOME": "res://assets/buildings/props/book_simplified_single.gltf",
	"HOOD": "res://assets/mortals/outfits/parts/female_ranger_head_hood.gltf",
	"PAULDRONS": "res://assets/mortals/outfits/parts/female_ranger_acc_pauldrons.gltf",
	"LANTERN": "res://assets/buildings/props/lantern_wall.gltf",
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
@onready var speech_bubble_label: Label3D = $SpeechBubbleLabel
@onready var morph_controller: Node3D = $DragonMorphController

var agent_id: String = ""
var race: String = "HUMAN"
var gender: String = "GIRL"
var stage: String = "ADULT"
var full_name: String = "Citizen"
var dynasty: String = "Founder"
var role: String = "CITIZEN"
var is_crying: bool = false
var is_oracle: bool = false
var dragon_form: String = "HUMANOID_DRAGON"
var equipped_gear: Array = []

var target_position: Vector3 = Vector3.ZERO
var target_rotation_y: float = 0.0
var is_pool_active: bool = false

var _current_active_key: String = ""
var _instanced_mesh_nodes: Dictionary = {}
var _gear_container: Node3D = null
var _lantern_light: OmniLight3D = null
var _instanced_gear_nodes: Dictionary = {}
var _walk_time: float = 0.0
var _base_y_offset: float = 0.0
var humanoid_animator: HumanoidAnimator = null


func _ensure_references() -> void:
	if not visual_root:
		visual_root = get_node_or_null("VisualRoot")
	if not humanoid_mesh_node and visual_root:
		humanoid_mesh_node = visual_root.get_node_or_null("HumanoidMeshNode")
	if not true_dragon_mesh_node and visual_root:
		true_dragon_mesh_node = visual_root.get_node_or_null("TrueDragonMeshNode")
	if not nameplate_label:
		nameplate_label = get_node_or_null("NameplateLabel")
	if not speech_bubble_label:
		speech_bubble_label = get_node_or_null("SpeechBubbleLabel")
	if not crying_particles and visual_root:
		crying_particles = visual_root.get_node_or_null("CryingParticles")
	if not crying_audio and visual_root:
		crying_audio = visual_root.get_node_or_null("CryingAudio")
	if not oracle_aura_particles and visual_root:
		oracle_aura_particles = visual_root.get_node_or_null("OracleAuraParticles")
	if not fear_aura_ring and visual_root:
		fear_aura_ring = visual_root.get_node_or_null("FearAuraRing")
	if not morph_controller:
		morph_controller = get_node_or_null("DragonMorphController")
	if not _gear_container and visual_root:
		_gear_container = visual_root.get_node_or_null("GearContainer")
		if not _gear_container:
			_gear_container = Node3D.new()
			_gear_container.name = "GearContainer"
			visual_root.add_child(_gear_container)


func _ready() -> void:
	visible = false
	_ensure_references()
	if not humanoid_animator:
		humanoid_animator = HumanoidAnimator.new()
		humanoid_animator.name = "HumanoidAnimator"
		add_child(humanoid_animator)

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
	_ensure_references()
	agent_id = data.get("agent_id", "")
	race = data.get("race", "HUMAN").to_upper()
	gender = data.get("gender", "GIRL").to_upper()
	stage = data.get("stage", "ADULT").to_upper()
	full_name = data.get("name", "Citizen")
	dynasty = data.get("dynasty", "Founder")
	role = data.get("role", "CITIZEN").to_upper()
	is_crying = data.get("crying", false)
	is_oracle = data.get("is_oracle", false)
	dragon_form = data.get("dragon_form", "HUMANOID_DRAGON")
	equipped_gear = data.get("equipped_gear", [])

	var px: float = float(data.get("x", global_position.x))
	var py: float = float(data.get("y", global_position.y))
	var pz: float = float(data.get("z", global_position.z))
	target_position = Vector3(px, py, pz)

	var rot: float = float(data.get("rotation_y", rotation.y))
	target_rotation_y = rot

	var speech: String = str(data.get("speech_text", ""))
	if speech_bubble_label:
		if speech != "":
			speech_bubble_label.text = "“%s”" % speech
			speech_bubble_label.visible = true
		else:
			speech_bubble_label.visible = false

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
	equipped_gear.clear()
	if _lantern_light:
		_lantern_light.visible = false
	for k in _instanced_gear_nodes:
		var n: Node = _instanced_gear_nodes[k]
		if is_instance_valid(n):
			n.visible = false
	if speech_bubble_label:
		speech_bubble_label.visible = false
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
		visual_root.position.y = 0.0
	else:
		visual_root.scale = Vector3(final_scale, final_scale, final_scale)
		var active_mesh_node: Node = _instanced_mesh_nodes.get(mesh_key, null)
		var min_y: float = _get_min_mesh_y(active_mesh_node)
		_base_y_offset = -min_y * final_scale
		visual_root.position.y = _base_y_offset

	# Dragon morph controller
	if morph_controller:
		morph_controller.set_is_dragon(race == "DRAGON")
		if race == "DRAGON":
			morph_controller.set_form(dragon_form)

	# Modular gear props & carried items
	_update_gear_props()

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


func _update_gear_props() -> void:
	if not _gear_container:
		return

	# Hide all existing gear props initially
	for k in _instanced_gear_nodes:
		var n: Node = _instanced_gear_nodes[k]
		if is_instance_valid(n):
			n.visible = false

	if _lantern_light:
		_lantern_light.visible = false

	if race == "DRAGON" and dragon_form == "TRUE_DRAGON":
		return

	for item in equipped_gear:
		var item_str: String = str(item).to_upper()
		if item_str == "LANTERN":
			_ensure_lantern()
			if _lantern_light:
				_lantern_light.visible = true
			if _instanced_gear_nodes.has("LANTERN"):
				_instanced_gear_nodes["LANTERN"].visible = true
		elif item_str in GEAR_PROPS_PATHS:
			_attach_gear_prop(item_str)


func _ensure_lantern() -> void:
	if not _lantern_light:
		_lantern_light = OmniLight3D.new()
		_lantern_light.name = "LanternLight"
		_lantern_light.light_color = Color(1.0, 0.78, 0.42, 1.0)
		_lantern_light.light_energy = 1.2
		_lantern_light.omni_range = 5.0
		_lantern_light.shadow_enabled = false
		_lantern_light.position = Vector3(0.35, 0.85, 0.25)
		_gear_container.add_child(_lantern_light)

	if not _instanced_gear_nodes.has("LANTERN") and ResourceLoader.exists(GEAR_PROPS_PATHS["LANTERN"]):
		var scene: PackedScene = load(GEAR_PROPS_PATHS["LANTERN"])
		if scene:
			var inst: Node3D = scene.instantiate() as Node3D
			inst.name = "LanternMesh"
			inst.position = Vector3(0.35, 0.85, 0.25)
			inst.scale = Vector3(0.35, 0.35, 0.35)
			_gear_container.add_child(inst)
			_instanced_gear_nodes["LANTERN"] = inst


func _attach_gear_prop(item_id: String) -> void:
	if _instanced_gear_nodes.has(item_id):
		var node: Node = _instanced_gear_nodes[item_id]
		if is_instance_valid(node):
			node.visible = true
			return

	var path: String = GEAR_PROPS_PATHS.get(item_id, "")
	if path == "" or not ResourceLoader.exists(path):
		return

	var scene: PackedScene = load(path)
	if not scene:
		return

	var inst: Node3D = scene.instantiate() as Node3D
	inst.name = "Prop_" + item_id

	if item_id in ["SWORD", "HOE", "PICKAXE", "HAMMER", "TOME"]:
		inst.position = Vector3(0.38, 0.85, 0.15)
		inst.scale = Vector3(0.45, 0.45, 0.45)
	elif item_id == "HOOD":
		inst.position = Vector3(0.0, 1.45, 0.0)
		inst.scale = Vector3(0.95, 0.95, 0.95)
	elif item_id == "PAULDRONS":
		inst.position = Vector3(0.0, 1.25, 0.0)
		inst.scale = Vector3(0.9, 0.9, 0.9)

	_gear_container.add_child(inst)
	_instanced_gear_nodes[item_id] = inst
	inst.visible = true


func _resolve_mesh_key() -> String:
	if role == "PALACE_KNIGHT":
		return "KNIGHT_BOY" if gender == "BOY" else "KNIGHT_GIRL"

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
			if humanoid_animator:
				humanoid_animator.bind_target(node)
			return

	# Instance from cached PackedScene
	if _scene_cache.has(key):
		var packed: PackedScene = _scene_cache[key]
		var inst: Node = packed.instantiate()
		inst.name = key
		humanoid_mesh_node.add_child(inst)
		_instanced_mesh_nodes[key] = inst
		inst.visible = true
		if humanoid_animator:
			humanoid_animator.bind_target(inst)
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
		if humanoid_animator:
			humanoid_animator.bind_target(fallback)


func _update_nameplate(current_scale: float) -> void:
	if nameplate_label == null:
		return

	var text: String = ""
	if role == "PALACE_KNIGHT":
		text += "⚔ [PALACE KNIGHT] ⚔\n"
	elif is_oracle:
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
	var bob: float = 0.0
	if dist > 0.08:
		_walk_time += delta * 12.0
		bob = abs(sin(_walk_time)) * 0.06
	else:
		_walk_time = 0.0
	visual_root.position.y = lerpf(visual_root.position.y, _base_y_offset + bob, delta * 10.0)

	# Update HumanoidAnimator
	if humanoid_animator and humanoid_mesh_node.visible:
		var speed: float = dist / maxf(delta, 0.001)
		humanoid_animator.set_velocity((target_position - global_position) / maxf(delta, 0.001))
		if is_crying:
			humanoid_animator.set_state(HumanoidAnimator.AnimState.CRY)
		elif is_oracle:
			humanoid_animator.set_state(HumanoidAnimator.AnimState.PRAY)
		elif speed > 4.5:
			humanoid_animator.set_state(HumanoidAnimator.AnimState.RUN)
		elif speed > 0.4:
			humanoid_animator.set_state(HumanoidAnimator.AnimState.WALK)
		else:
			humanoid_animator.set_state(HumanoidAnimator.AnimState.IDLE)

	# Ensure True Dragon animation plays when transformed
	if true_dragon_mesh_node and true_dragon_mesh_node.visible:
		var dragon_ap: AnimationPlayer = true_dragon_mesh_node.find_child("AnimationPlayer", true, false) as AnimationPlayer
		if dragon_ap and dragon_ap.has_animation("RedDragon_Armature|flightTest") and dragon_ap.current_animation != "RedDragon_Armature|flightTest":
			dragon_ap.play("RedDragon_Armature|flightTest")

	# Update Lantern glow based on night factor
	if _lantern_light and _lantern_light.visible:
		var nf_param = RenderingServer.global_shader_parameter_get("night_factor")
		var nf: float = float(nf_param) if nf_param != null else 0.0
		_lantern_light.light_energy = 0.2 + (1.2 * nf)


func _get_min_mesh_y(node: Node, parent_y: float = 0.0) -> float:
	if node == null:
		return 0.0
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
