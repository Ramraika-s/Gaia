# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/sky_weather_controller.gd
# Controls Sky3D day/night arc, 4-season global shader uniform, and regional weather cross-fades.
# Smoothly interpolates fog density, sky tint, rain/snow/ash particles, and wind strength.

extends Node3D

signal night_factor_changed(night_factor: float)

@export var sky_node_path: NodePath
@export var weather_particles_path: NodePath

var _sky_node: Node = null
var _weather_particles: GPUParticles3D = null

# Night lighting interpolation
var _current_night_factor: float = 0.0

# Weather smoothing targets
var _target_fog_density: float = 0.0006
var _current_fog_density: float = 0.0006
var _target_sky_tint: Color = Color(0.48, 0.65, 0.88, 1.0)
var _current_sky_tint: Color = Color(0.48, 0.65, 0.88, 1.0)
var _target_wind: float = 0.15
var _current_wind: float = 0.15
var _current_weather: String = "CLEAR"

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

	# Smooth exponential cross-fade of environmental parameters
	var lerp_t: float = clamp(delta * 1.8, 0.0, 1.0)
	_current_fog_density = lerpf(_current_fog_density, _target_fog_density, lerp_t)
	_current_sky_tint = _current_sky_tint.lerp(_target_sky_tint, lerp_t)
	_current_wind = lerpf(_current_wind, _target_wind, lerp_t)

	_apply_environmental_blend()


func _configure_night_ambient_floor() -> void:
	if _sky_node and _sky_node is WorldEnvironment:
		var env: Environment = (_sky_node as WorldEnvironment).environment
		if env:
			env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
			env.ambient_light_color = Color(0.12, 0.15, 0.25, 1.0)
			env.ambient_light_energy = 0.40
			env.volumetric_fog_enabled = true
			env.volumetric_fog_density = _current_fog_density


func _on_world_time_weather(data: Dictionary) -> void:
	_use_bridge_time = true
	_last_bridge_packet_time = Time.get_ticks_msec() / 1000.0

	var time_of_day: float = float(data.get("time_of_day", 12.0))
	var season_prog: float = float(data.get("season_progress", 0.0))
	var weather_type: String = str(data.get("weather", "CLEAR"))
	var details: Dictionary = data.get("weather_details", {})

	_apply_time_to_sky(time_of_day)
	_apply_season_progress(season_prog)

	# Target environmental values from regional weather details
	if not details.is_empty():
		_target_fog_density = float(details.get("fog_density", 0.0006))
		var tint_array: Array = details.get("sky_tint", [0.48, 0.65, 0.88])
		if tint_array.size() >= 3:
			_target_sky_tint = Color(float(tint_array[0]), float(tint_array[1]), float(tint_array[2]), 1.0)
		_target_wind = float(details.get("wind_strength", 0.15))
	else:
		_set_default_weather_targets(weather_type)

	_apply_weather_vfx(weather_type, season_prog)


func _set_default_weather_targets(weather: String) -> void:
	if weather == "ASH":
		_target_fog_density = 0.0150
		_target_sky_tint = Color(0.42, 0.35, 0.30, 1.0)
		_target_wind = 0.45
	elif weather == "STORM":
		_target_fog_density = 0.0120
		_target_sky_tint = Color(0.28, 0.32, 0.40, 1.0)
		_target_wind = 0.60
	elif weather == "SNOW":
		_target_fog_density = 0.0080
		_target_sky_tint = Color(0.72, 0.78, 0.88, 1.0)
		_target_wind = 0.30
	elif weather == "RAIN":
		_target_fog_density = 0.0060
		_target_sky_tint = Color(0.48, 0.55, 0.65, 1.0)
		_target_wind = 0.35
	elif weather == "OVERCAST":
		_target_fog_density = 0.0028
		_target_sky_tint = Color(0.65, 0.70, 0.76, 1.0)
		_target_wind = 0.20
	else: # CLEAR
		_target_fog_density = 0.0006
		_target_sky_tint = Color(0.48, 0.65, 0.88, 1.0)
		_target_wind = 0.12


func _apply_environmental_blend() -> void:
	if _sky_node and _sky_node is WorldEnvironment:
		var env: Environment = (_sky_node as WorldEnvironment).environment
		if env:
			env.volumetric_fog_density = _current_fog_density
			env.background_color = _current_sky_tint


func get_night_factor() -> float:
	return _current_night_factor


func calculate_night_factor(time_hours: float) -> float:
	# Smooth transition: 19:00 - 20:30 dusk ramp, 20:30 - 04:30 deep night, 04:30 - 06:00 dawn
	if time_hours >= 19.0 and time_hours < 20.5:
		return (time_hours - 19.0) / 1.5
	elif (time_hours >= 20.5 and time_hours <= 24.0) or (time_hours >= 0.0 and time_hours <= 4.5):
		return 1.0
	elif time_hours > 4.5 and time_hours <= 6.0:
		return 1.0 - (time_hours - 4.5) / 1.5
	else:
		return 0.0


func _apply_time_to_sky(time_hours: float) -> void:
	if _sky_node and is_instance_valid(_sky_node):
		var tod: Node = _sky_node.get("tod")
		if tod and is_instance_valid(tod):
			tod.set("current_time", time_hours)

	var nf: float = calculate_night_factor(time_hours)
	RenderingServer.global_shader_parameter_set("night_factor", nf)
	if abs(nf - _current_night_factor) > 0.005:
		_current_night_factor = nf
		night_factor_changed.emit(nf)


func _apply_season_progress(progress: float) -> void:
	RenderingServer.global_shader_parameter_set("season_progress", progress)


func _apply_weather_vfx(weather: String, season_prog: float) -> void:
	_current_weather = weather
	if not _weather_particles:
		return

	var is_winter: bool = (season_prog >= 2.8 and season_prog <= 3.8)
	var mat: ParticleProcessMaterial = _weather_particles.process_material as ParticleProcessMaterial

	if weather == "ASH":
		_weather_particles.emitting = true
		_weather_particles.amount = 350
		if mat:
			mat.gravity = Vector3(0.0, -1.8, 0.0)
			mat.color = Color(0.25, 0.20, 0.18, 0.85)
	elif weather == "SNOW" or (is_winter and weather != "CLEAR"):
		_weather_particles.emitting = true
		_weather_particles.amount = 450
		if mat:
			mat.gravity = Vector3(0.0, -2.5, 0.0)
			mat.color = Color(0.95, 0.98, 1.0, 0.85)
	elif weather == "RAIN" or weather == "STORM":
		_weather_particles.emitting = true
		_weather_particles.amount = 650 if weather == "STORM" else 450
		if mat:
			mat.gravity = Vector3(0.0, -14.0, 0.0)
			mat.color = Color(0.70, 0.80, 0.95, 0.70)
	elif weather == "CLEAR":
		_weather_particles.emitting = false
	else:
		_weather_particles.emitting = false
