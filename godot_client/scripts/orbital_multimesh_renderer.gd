# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/orbital_multimesh_renderer.gd
# 1-draw-call 10,000+ agent Orbital MultiMesh renderer for Gaia civilization simulation.
# Tuned for AMD Radeon 780M iGPU with Forward+ renderer and zero runtime node allocations.

extends Node3D

const DEFAULT_CAPACITY: int = 16384
const BUBBLE_EXCLUSION_RADIUS: float = 140.0
const BUBBLE_EXCLUSION_RADIUS_SQ: float = BUBBLE_EXCLUSION_RADIUS * BUBBLE_EXCLUSION_RADIUS

signal population_counts_updated(h: int, e: int, d: int, b: int, dem: int)

# Race color palette (5 distinct races)
const RACE_COLORS: Array[Color] = [
	Color(0.25, 0.65, 1.00, 1.0),  # 0: HUMAN (Cyan/Blue)
	Color(0.20, 0.90, 0.35, 1.0),  # 1: ELF (Emerald Green)
	Color(1.00, 0.25, 0.20, 1.0),  # 2: DRAGON (Crimson Red)
	Color(1.00, 0.65, 0.15, 1.0),  # 3: BEASTHUMAN (Amber Orange)
	Color(0.75, 0.20, 0.95, 1.0),  # 4: DEMON (Violet Purple)
]

# Life stage scale multipliers
const STAGE_SCALES: Array[float] = [
	0.45,  # 0: INFANT
	0.75,  # 1: CHILD
	1.00,  # 2: ADULT
	0.94,  # 3: ELDER
]

# Flag bitmasks (matching sim_core/bridge/godot_ws_bridge.py)
const FLAG_CRYING: int = 1 << 0       # 1
const FLAG_IS_ORACLE: int = 1 << 1    # 2
const FLAG_TRUE_DRAGON: int = 1 << 2  # 4
const FLAG_INJURED: int = 1 << 3      # 8
const FLAG_ILLNESS: int = 1 << 4      # 16
const FLAG_IN_COMBAT: int = 1 << 5    # 32
const FLAG_PRAYING: int = 1 << 6      # 64
const FLAG_IN_BUBBLE: int = 1 << 7    # 128

@export var multimesh_capacity: int = DEFAULT_CAPACITY
@export var marker_base_size: float = 1.4

var multimesh_instance: MultiMeshInstance3D = null
var current_god_focus: Vector3 = Vector3(0.0, 18.5, 0.0)
var last_update_duration_ms: float = 0.0
var active_agent_count: int = 0


func _ready() -> void:
	_init_multimesh()
	_connect_bridge_signals()


func _init_multimesh() -> void:
	if multimesh_instance == null:
		multimesh_instance = MultiMeshInstance3D.new()
		multimesh_instance.name = "OrbitalMultiMesh"
		add_child(multimesh_instance)

	var mm: MultiMesh = MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.instance_count = multimesh_capacity
	mm.visible_instance_count = 0

	# Lightweight low-poly upright cone marker
	var cone_mesh: CylinderMesh = CylinderMesh.new()
	cone_mesh.top_radius = 0.0
	cone_mesh.bottom_radius = 0.8
	cone_mesh.height = 2.2
	cone_mesh.radial_segments = 6
	cone_mesh.rings = 1

	# Unshaded vertex-colored material for fast 1-draw-call rendering
	var mat: StandardMaterial3D = StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.vertex_color_use_as_albedo = true
	cone_mesh.material = mat

	mm.mesh = cone_mesh
	multimesh_instance.multimesh = mm


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.connect("orbital_positions_received", Callable(self, "_on_orbital_positions_received"))
		bridge.connect("god_focus_changed", Callable(self, "_on_god_focus_changed"))


func _on_god_focus_changed(pos: Vector3, _is_orbital: bool) -> void:
	current_god_focus = pos


func _on_orbital_positions_received(buffer: PackedByteArray, agent_count: int) -> void:
	update_from_buffer(buffer, agent_count)


func update_from_buffer(buffer: PackedByteArray, agent_count: int) -> float:
	if multimesh_instance == null:
		_init_multimesh()

	var start_time: int = Time.get_ticks_usec()
	var mm: MultiMesh = multimesh_instance.multimesh
	if mm == null:
		return 0.0

	# Ensure capacity
	if agent_count > mm.instance_count:
		var new_capacity: int = max(agent_count, mm.instance_count * 2)
		mm.instance_count = new_capacity

	var focus_x: float = current_god_focus.x
	var focus_z: float = current_god_focus.z
	var visible_count: int = 0
	var total_to_process: int = min(agent_count, mm.instance_count)
	var race_counts: Array[int] = [0, 0, 0, 0, 0]

	var hidden_xform: Transform3D = Transform3D(Basis().scaled(Vector3.ZERO), Vector3(0.0, -999.0, 0.0))

	for i in range(total_to_process):
		var offset: int = i * 24
		var x: float = buffer.decode_float(offset)
		var y: float = buffer.decode_float(offset + 4)
		var z: float = buffer.decode_float(offset + 8)
		var race_idx: int = clampi(roundi(buffer.decode_float(offset + 12)), 0, 4)
		var stage_idx: int = clampi(roundi(buffer.decode_float(offset + 16)), 0, 3)
		var flags: int = roundi(buffer.decode_float(offset + 20))
		race_counts[race_idx] += 1

		# Reality Bubble exclusion: avoid double-rendering actors near God
		var dx: float = x - focus_x
		var dz: float = z - focus_z
		var dist_sq: float = dx * dx + dz * dz
		var in_bubble: bool = (flags & FLAG_IN_BUBBLE) != 0 or dist_sq < BUBBLE_EXCLUSION_RADIUS_SQ

		if in_bubble:
			mm.set_instance_transform(i, hidden_xform)
			continue

		var scale_factor: float = marker_base_size * STAGE_SCALES[stage_idx]
		if (flags & FLAG_TRUE_DRAGON) != 0:
			scale_factor *= 2.5

		var basis: Basis = Basis().scaled(Vector3(scale_factor, scale_factor, scale_factor))
		var xform: Transform3D = Transform3D(basis, Vector3(x, y + 1.2, z))
		mm.set_instance_transform(i, xform)

		var col: Color = RACE_COLORS[race_idx]
		if (flags & FLAG_IS_ORACLE) != 0:
			col = col.lerp(Color(1.0, 0.9, 0.3, 1.0), 0.4)
		mm.set_instance_color(i, col)
		visible_count += 1

	mm.visible_instance_count = total_to_process
	active_agent_count = total_to_process
	population_counts_updated.emit(race_counts[0], race_counts[1], race_counts[2], race_counts[3], race_counts[4])

	var end_time: int = Time.get_ticks_usec()
	last_update_duration_ms = (end_time - start_time) / 1000.0
	return last_update_duration_ms


func populate_offline_preview(count: int = 2500) -> void:
	# Generates deterministic synthetic buffer distributed across the 5 biomes
	var buf: PackedByteArray = PackedByteArray()
	buf.resize(count * 24)

	var biome_centers: Array[Vector2] = [
		Vector2(-1800.0, 2000.0),  # Human plains
		Vector2(2200.0, 2000.0),   # Elf highlands
		Vector2(2500.0, -2500.0),  # Dragon peaks
		Vector2(-2500.0, -2500.0), # Beasthuman taiga
		Vector2(-3500.0, 500.0),   # Demon crags
	]

	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 42

	for i in range(count):
		var race_id: int = i % 5
		var center: Vector2 = biome_centers[race_id]
		var angle: float = rng.randf_range(0.0, TAU)
		var dist: float = rng.randf_range(50.0, 900.0)
		var x: float = center.x + cos(angle) * dist
		var z: float = center.y + sin(angle) * dist
		var y: float = 18.0 + (race_id * 5.0) + sin(dist * 0.05) * 4.0
		var stage_id: int = rng.randi_range(0, 3)
		var flags: int = 0
		if race_id == 2 and rng.randf() < 0.15:
			flags |= FLAG_TRUE_DRAGON
		if rng.randf() < 0.03:
			flags |= FLAG_IS_ORACLE

		var offset: int = i * 24
		buf.encode_float(offset, x)
		buf.encode_float(offset + 4, y)
		buf.encode_float(offset + 8, z)
		buf.encode_float(offset + 12, float(race_id))
		buf.encode_float(offset + 16, float(stage_id))
		buf.encode_float(offset + 20, float(flags))

	update_from_buffer(buf, count)
	print("[OrbitalMultiMesh] Populated offline preview with %d agents across 5 races (unpack: %.2f ms)" % [count, last_update_duration_ms])
