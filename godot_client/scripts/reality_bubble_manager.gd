# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/reality_bubble_manager.gd
# Manages the 60-120 pooled rigged mortal actors inside the 120-160m Reality Bubble.
# Guarantees zero runtime instantiate() or queue_free() calls during live camera flight.

extends Node3D

const POOL_SIZE: int = 100
const ACTOR_SCENE_PATH: String = "res://scenes/mortal_actor.tscn"

@export var auto_preview_offline: bool = true

var _actor_pool: Array[Node3D] = []
var _active_actors_by_id: Dictionary = {}
var _actor_scene: PackedScene = null


func _ready() -> void:
	_init_pool()
	_connect_bridge_signals()


func _init_pool() -> void:
	if ResourceLoader.exists(ACTOR_SCENE_PATH):
		_actor_scene = load(ACTOR_SCENE_PATH)
	else:
		push_error("[RealityBubbleManager] Actor scene missing: " + ACTOR_SCENE_PATH)
		return

	for i in range(POOL_SIZE):
		var actor: Node3D = _actor_scene.instantiate()
		actor.name = "MortalActor_%03d" % i
		actor.visible = false
		add_child(actor)
		_actor_pool.append(actor)

	print("[RealityBubbleManager] Pre-allocated %d pooled rigged mortal actors." % POOL_SIZE)


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.connect("bubble_sync_received", Callable(self, "_on_bubble_sync_received"))
		bridge.connect("connected_to_bridge", Callable(self, "_on_bridge_connected"))
		bridge.connect("disconnected_from_bridge", Callable(self, "_on_bridge_disconnected"))


func clear_all_actors() -> void:
	for actor in _actor_pool:
		if actor.is_pool_active or actor.visible:
			actor.release_to_pool()
	_active_actors_by_id.clear()


func _on_bridge_connected() -> void:
	print("[RealityBubbleManager] Bridge connected; clearing offline preview and switching to live bubble sync.")
	clear_all_actors()


func _on_bridge_disconnected() -> void:
	if auto_preview_offline and get_active_count() == 0:
		populate_offline_preview()


func _on_bubble_sync_received(data: Dictionary) -> void:
	var agent_list: Array = data.get("agents", [])
	sync_bubble_agents(agent_list)


func sync_bubble_agents(agent_list: Array) -> void:
	var count: int = min(agent_list.size(), POOL_SIZE)
	_active_actors_by_id.clear()

	for i in range(count):
		var agent_data: Dictionary = agent_list[i]
		var actor: Node3D = _actor_pool[i]
		actor.bind_agent_data(agent_data)
		var aid: String = agent_data.get("agent_id", "")
		if aid != "":
			_active_actors_by_id[aid] = actor

	# Release remaining pooled slots
	for i in range(count, POOL_SIZE):
		var actor: Node3D = _actor_pool[i]
		if actor.is_pool_active or actor.visible:
			actor.release_to_pool()


func get_active_count() -> int:
	var active: int = 0
	for actor in _actor_pool:
		if actor.is_pool_active and actor.visible:
			active += 1
	return active


func get_actor_by_id(aid: String) -> Node3D:
	return _active_actors_by_id.get(aid, null)


func get_pool() -> Array[Node3D]:
	return _actor_pool


func populate_offline_preview() -> void:
	# Spawns sample mortals across all 5 races + crying infant + Oracle + True Dragon in Central Basin
	var sample_agents: Array = [
		{
			"agent_id": "prev_human_01",
			"name": "Eldrin",
			"dynasty": "Pendelton",
			"race": "HUMAN",
			"gender": "BOY",
			"stage": "ADULT",
			"x": 12.0, "y": 18.2, "z": 8.0,
			"rotation_y": 0.4,
			"is_oracle": false,
			"crying": false,
		},
		{
			"agent_id": "prev_human_infant",
			"name": "Lily",
			"dynasty": "Pendelton",
			"race": "HUMAN",
			"gender": "GIRL",
			"stage": "INFANT",
			"x": 10.5, "y": 18.2, "z": 7.5,
			"rotation_y": 1.2,
			"is_oracle": false,
			"crying": true,  # Crying infant demonstration
		},
		{
			"agent_id": "prev_elf_01",
			"name": "Faerandil",
			"dynasty": "Moonwhisper",
			"race": "ELF",
			"gender": "BOY",
			"stage": "ADULT",
			"x": -14.0, "y": 18.2, "z": 12.0,
			"rotation_y": -1.1,
			"is_oracle": true,  # Oracle demonstration
			"crying": false,
		},
		{
			"agent_id": "prev_elf_female",
			"name": "Silvaria",
			"dynasty": "Moonwhisper",
			"race": "ELF",
			"gender": "GIRL",
			"stage": "ADULT",
			"x": -16.0, "y": 18.2, "z": 10.0,
			"rotation_y": 2.1,
			"is_oracle": false,
			"crying": false,
		},
		{
			"agent_id": "prev_dragon_humanoid",
			"name": "Ignis",
			"dynasty": "Drakon",
			"race": "DRAGON",
			"gender": "BOY",
			"stage": "ADULT",
			"x": 22.0, "y": 18.2, "z": -15.0,
			"rotation_y": 3.0,
			"dragon_form": "HUMANOID_DRAGON",
			"is_oracle": false,
			"crying": false,
		},
		{
			"agent_id": "prev_dragon_true",
			"name": "Vermithrax",
			"dynasty": "Draconia",
			"race": "DRAGON",
			"gender": "GIRL",
			"stage": "ADULT",
			"x": -35.0, "y": 18.2, "z": -25.0,
			"rotation_y": 0.8,
			"dragon_form": "TRUE_DRAGON",  # True Dragon demonstration
			"is_oracle": false,
			"crying": false,
		},
		{
			"agent_id": "prev_beasthuman_male",
			"name": "Karn",
			"dynasty": "Ironfang",
			"race": "BEASTHUMAN",
			"gender": "BOY",
			"stage": "ADULT",
			"x": 5.0, "y": 18.2, "z": -20.0,
			"rotation_y": -2.3,
			"is_oracle": false,
			"crying": false,
		},
		{
			"agent_id": "prev_beasthuman_female",
			"name": "Nara",
			"dynasty": "Ironfang",
			"race": "BEASTHUMAN",
			"gender": "GIRL",
			"stage": "CHILD",
			"x": 8.0, "y": 18.2, "z": -19.0,
			"rotation_y": 0.0,
			"is_oracle": false,
			"crying": false,
		},
		{
			"agent_id": "prev_demon_01",
			"name": "Malakor",
			"dynasty": "Shadowveil",
			"race": "DEMON",
			"gender": "BOY",
			"stage": "ADULT",
			"x": -25.0, "y": 18.2, "z": 22.0,
			"rotation_y": 1.5,
			"is_oracle": false,
			"crying": false,
		},
		{
			"agent_id": "prev_human_elder",
			"name": "Archibald",
			"dynasty": "Gildenfell",
			"race": "HUMAN",
			"gender": "BOY",
			"stage": "ELDER",
			"x": 0.0, "y": 18.2, "z": 24.0,
			"rotation_y": -0.5,
			"is_oracle": false,
			"crying": false,
		},
	]

	sync_bubble_agents(sample_agents)
	print("[RealityBubbleManager] Populated offline preview with %d sample mortals (all 5 races, crying infant, Oracle, True Dragon)." % sample_agents.size())
