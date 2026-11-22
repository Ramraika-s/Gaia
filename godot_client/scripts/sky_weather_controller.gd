# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/sky_weather_controller.gd
# Controls Sky3D day/night arc, 4-season global shader uniform, and weather particles.

extends Node3D

@export var sky_node_path: NodePath
@export var weather_particles_path: NodePath

var _sky_node: Node = null
var _weather_particles: GPUParticles3D = null

# Local simulation fallback when bridge is disconnected
var _local_time: float = 8.5  # 8:30 AM morning default
var _local_season_progress: float = 0.25  # Spring default
var _use_bridge_time: bool = false
var _last_bridge_packet_time: float = 0.0


func _ready() -> void:
	if not sky_node_path.is_empty():
		_sky_node = get_node_or_null(sky_node_path)
	if not weather_particles_path.is_empty():
		_weather_particles = get_node_or_null(weather_particles_path) as GPUParticles3D

	# Ensure soft ambient light floor in environment so nights are never pitch-black
	_configure_night_ambient_floor()

	# Connect to WebSocket bridge signals if available
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.has_signal("world_time_weather_received"):
		bridge.connect("world_time_weather_received", Callable(self, "_on_world_time_weather"))

	# Set initial global shader parameter
	_apply_season_progress(_local_season_progress)


func _process(delta: float) -> void:
	var now: float = Time.get_ticks_msec() / 1000.0
	if not _use_bridge_time or (now - _last_bridge_packet_time > 5.0):
		# Fallback local preview: 1 full day cycle every 180 seconds
		_local_time += (delta / 180.0) * 24.0
		if _local_time >= 24.0:
			_local_time -= 24.0
			_local_season_progress += 0.05
			if _local_season_progress >= 4.0:
				_local_season_progress -= 4.0
			_apply_season_progress(_local_season_progress)

		_apply_time_to_sky(_local_time)


func _configure_night_ambient_floor() -> void:
	if _sky_node and _sky_node is WorldEnvironment:
		var env: Environment = (_sky_node as WorldEnvironment).environment
		if env:
			env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
			env.ambient_light_color = Color(0.12, 0.15, 0.25, 1.0)
			env.ambient_light_energy = 0.40


func _on_world_time_weather(data: Dictionary) -> void:
	_use_bridge_time = true
	_last_bridge_packet_time = Time.get_ticks_msec() / 1000.0

	var time_of_day: float = float(data.get("time_of_day", 12.0))
	var season_prog: float = float(data.get("season_progress", 0.0))
	var weather_type: String = str(data.get("weather", "CLEAR"))

	_apply_time_to_sky(time_of_day)
	_apply_season_progress(season_prog)
	_apply_weather_vfx(weather_type, season_prog)


func _apply_time_to_sky(time_hours: float) -> void:
	if _sky_node and is_instance_valid(_sky_node):
		var tod: Node = _sky_node.get("tod")
		if tod and is_instance_valid(tod):
			tod.set("current_time", time_hours)


func _apply_season_progress(progress: float) -> void:
	# Set global shader uniform so all foliage and terrain shaders update atomically
	RenderingServer.global_shader_parameter_set("season_progress", progress)


func _apply_weather_vfx(weather: String, season_prog: float) -> void:
	if not _weather_particles:
		return

	var is_winter: bool = (season_prog >= 2.8 and season_prog <= 3.8)
	if weather == "SNOW" or (is_winter and weather != "CLEAR"):
		_weather_particles.emitting = true
		_weather_particles.amount = 400
	elif weather == "RAIN" or weather == "STORM":
		_weather_particles.emitting = true
		_weather_particles.amount = 600
	elif weather == "CLEAR":
		_weather_particles.emitting = false
	else:
		_weather_particles.emitting = false
