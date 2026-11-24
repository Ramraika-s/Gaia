# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/sky_weather_controller.gd
# Controls Sky3D day/night arc, 4-season global shader uniform, and regional weather cross-fades.
# Smoothly interpolates fog density, sky tint, rain/snow/ash particles, and wind strength.

extends Node3D

signal night_factor_changed(night_factor: float)

@export var sky_node_path: NodePath
@export var weather_particles_path: NodePath
@export var sun_light_path: NodePath = NodePath("../SunLight")

var _sky_node: Node = null
var _weather_particles: GPUParticles3D = null
var _sun_light: DirectionalLight3D = null
var _environment: Environment = null
var _sky_material: ProceduralSkyMaterial = null

# Night lighting interpolation
var _current_night_factor: float = 0.0

# ---------------------------------------------------------------------------
# 4 diurnal keyframes (AA stylized sky). Sun/moon light and ambient follow the same keys.
# ---------------------------------------------------------------------------
const KEY_NIGHT: int = 0
const KEY_DAWN: int = 1
const KEY_DAY: int = 2
const KEY_DUSK: int = 3

const SKY_KEYS: Array[Dictionary] = [
	{  # Starry Night (19:30-05:30): deep midnight indigo, readable slate horizon, silver-blue moonlight
		"top": Color(0.03, 0.05, 0.12),
		"horizon": Color(0.08, 0.12, 0.22),
		"ground_horizon": Color(0.08, 0.12, 0.22),
		"ground_bottom": Color(0.02, 0.03, 0.07),
		"fog": Color(0.10, 0.14, 0.26),
		"light_color": Color(0.55, 0.66, 0.96),
		"light_energy": 0.28,
		"ambient": 0.80,
	},
	{  # Dawn (05:30-07:30): soft lavender zenith, warm peach/gold horizon
		"top": Color(0.46, 0.40, 0.70),
		"horizon": Color(0.99, 0.72, 0.48),
		"ground_horizon": Color(0.85, 0.62, 0.50),
		"ground_bottom": Color(0.30, 0.28, 0.34),
		"fog": Color(0.95, 0.76, 0.62),
		"light_color": Color(1.0, 0.76, 0.52),
		"light_energy": 0.95,
		"ambient": 0.55,
	},
	{  # Day (07:30-16:30): vibrant anime-fantasy blue, luminous pale cyan horizon
		"top": Color(0.18, 0.46, 0.88),
		"horizon": Color(0.66, 0.84, 0.98),
		"ground_horizon": Color(0.66, 0.82, 0.92),
		"ground_bottom": Color(0.28, 0.36, 0.30),
		"fog": Color(0.68, 0.80, 0.94),
		"light_color": Color(1.0, 0.97, 0.90),
		"light_energy": 1.35,
		"ambient": 0.55,
	},
	{  # Golden Hour / Dusk (16:30-19:30): royal blue zenith, amber/coral horizon
		"top": Color(0.08, 0.12, 0.42),
		"horizon": Color(0.95, 0.50, 0.28),
		"ground_horizon": Color(0.80, 0.42, 0.30),
		"ground_bottom": Color(0.18, 0.14, 0.22),
		"fog": Color(0.88, 0.58, 0.44),
		"light_color": Color(1.0, 0.58, 0.32),
		"light_energy": 0.90,
		"ambient": 0.50,
	},
]

# [hour, key] anchors; adjacent anchors cross-fade with smoothstep (night wraps around midnight).
const KEY_SCHEDULE: Array = [
	[0.0, 0], [5.5, 0], [6.5, 1], [7.5, 2], [16.5, 2], [18.0, 3], [19.5, 0], [24.0, 0],
]

const CLEAR_FOG_DENSITY: float = 0.00022
const MAX_WEATHER_FOG_DENSITY: float = 0.0030

# Weather smoothing targets (fog density here is the exponential aerial-perspective density)
var _target_fog_density: float = CLEAR_FOG_DENSITY
var _current_fog_density: float = CLEAR_FOG_DENSITY
var _target_sky_tint: Color = Color(0.48, 0.65, 0.88, 1.0)
var _current_sky_tint: Color = Color(0.48, 0.65, 0.88, 1.0)
var _target_weather_blend: float = 0.0
var _current_weather_blend: float = 0.0
var _target_wind: float = 0.15
var _current_wind: float = 0.15
var _current_weather: String = "CLEAR"
var _time_hours: float = 8.5

# Local simulation fallback when bridge is disconnected
var _local_time: float = 8.5  # 8:30 AM golden morning default
var _local_season_progress: float = 0.25  # Spring default
var _use_bridge_time: bool = false
var _last_bridge_packet_time: float = 0.0


func _ready() -> void:
	if not sky_node_path.is_empty():
		_sky_node = get_node_or_null(sky_node_path)
	if not weather_particles_path.is_empty():
		_weather_particles = get_node_or_null(weather_particles_path) as GPUParticles3D
	if not sun_light_path.is_empty():
		_sun_light = get_node_or_null(sun_light_path) as DirectionalLight3D

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
	_current_weather_blend = lerpf(_current_weather_blend, _target_weather_blend, lerp_t)
	_current_wind = lerpf(_current_wind, _target_wind, lerp_t)

	_apply_environmental_blend()


func _get_environment() -> Environment:
	if _environment == null and _sky_node and _sky_node is WorldEnvironment:
		_environment = (_sky_node as WorldEnvironment).environment
	return _environment


func _get_sky_material() -> ProceduralSkyMaterial:
	"""Returns the ProceduralSkyMaterial, creating a BG_SKY dome if the scene lacks one."""
	if _sky_material != null:
		return _sky_material
	var env: Environment = _get_environment()
	if env == null:
		return null
	if env.sky == null or not (env.sky.sky_material is ProceduralSkyMaterial):
		var sky: Sky = Sky.new()
		sky.sky_material = ProceduralSkyMaterial.new()
		env.sky = sky
	env.background_mode = Environment.BG_SKY
	_sky_material = env.sky.sky_material as ProceduralSkyMaterial
	return _sky_material


func _configure_night_ambient_floor() -> void:
	# Sky-sourced ambient with a bluish colour floor so nights stay readable; clear-weather
	# volumetric fog stays OFF (crisp painterly distance haze comes from aerial-perspective fog).
	var env: Environment = _get_environment()
	if env:
		_get_sky_material()
		env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
		env.ambient_light_color = Color(0.22, 0.28, 0.42, 1.0)
		env.volumetric_fog_enabled = false
		env.fog_enabled = true


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
		var raw_fog: float = float(details.get("fog_density", 0.0006))
		var excess: float = maxf(raw_fog - 0.0006, 0.0)
		_target_fog_density = clampf(CLEAR_FOG_DENSITY + excess * 0.25, CLEAR_FOG_DENSITY, MAX_WEATHER_FOG_DENSITY)
		_target_weather_blend = clampf(excess / 0.006, 0.0, 0.85)
		var tint_array: Array = details.get("sky_tint", [0.48, 0.65, 0.88])
		if tint_array.size() >= 3:
			_target_sky_tint = Color(float(tint_array[0]), float(tint_array[1]), float(tint_array[2]), 1.0)
		_target_wind = float(details.get("wind_strength", 0.15))
	else:
		_set_default_weather_targets(weather_type)

	_apply_weather_vfx(weather_type, season_prog)


func _set_default_weather_targets(weather: String) -> void:
	if weather == "ASH":
		_target_fog_density = 0.0030
		_target_weather_blend = 0.80
		_target_sky_tint = Color(0.42, 0.35, 0.30, 1.0)
		_target_wind = 0.45
	elif weather == "STORM":
		_target_fog_density = 0.0024
		_target_weather_blend = 0.85
		_target_sky_tint = Color(0.28, 0.32, 0.40, 1.0)
		_target_wind = 0.60
	elif weather == "SNOW":
		_target_fog_density = 0.0016
		_target_weather_blend = 0.55
		_target_sky_tint = Color(0.72, 0.78, 0.88, 1.0)
		_target_wind = 0.30
	elif weather == "RAIN":
		_target_fog_density = 0.0012
		_target_weather_blend = 0.60
		_target_sky_tint = Color(0.48, 0.55, 0.65, 1.0)
		_target_wind = 0.35
	elif weather == "OVERCAST":
		_target_fog_density = 0.0007
		_target_weather_blend = 0.40
		_target_sky_tint = Color(0.65, 0.70, 0.76, 1.0)
		_target_wind = 0.20
	else:  # CLEAR
		_target_fog_density = CLEAR_FOG_DENSITY
		_target_weather_blend = 0.0
		_target_sky_tint = Color(0.48, 0.65, 0.88, 1.0)
		_target_wind = 0.12


func sample_diurnal_keyframe(time_hours: float) -> Dictionary:
	"""Cross-fades the 4 diurnal keyframes (night/dawn/day/dusk) at the given hour (0..24)."""
	var t: float = fposmod(time_hours, 24.0)
	var lo: Array = KEY_SCHEDULE[0]
	var hi: Array = KEY_SCHEDULE[KEY_SCHEDULE.size() - 1]
	for i in range(KEY_SCHEDULE.size() - 1):
		if t >= float(KEY_SCHEDULE[i][0]) and t <= float(KEY_SCHEDULE[i + 1][0]):
			lo = KEY_SCHEDULE[i]
			hi = KEY_SCHEDULE[i + 1]
			break
	var span: float = float(hi[0]) - float(lo[0])
	var w: float = 0.0 if span <= 0.0 else smoothstep(0.0, 1.0, (t - float(lo[0])) / span)
	var ka: Dictionary = SKY_KEYS[int(lo[1])]
	var kb: Dictionary = SKY_KEYS[int(hi[1])]
	return {
		"top": (ka["top"] as Color).lerp(kb["top"], w),
		"horizon": (ka["horizon"] as Color).lerp(kb["horizon"], w),
		"ground_horizon": (ka["ground_horizon"] as Color).lerp(kb["ground_horizon"], w),
		"ground_bottom": (ka["ground_bottom"] as Color).lerp(kb["ground_bottom"], w),
		"fog": (ka["fog"] as Color).lerp(kb["fog"], w),
		"light_color": (ka["light_color"] as Color).lerp(kb["light_color"], w),
		"light_energy": lerpf(float(ka["light_energy"]), float(kb["light_energy"]), w),
		"ambient": lerpf(float(ka["ambient"]), float(kb["ambient"]), w),
	}


func _apply_environmental_blend() -> void:
	var env: Environment = _get_environment()
	if env == null:
		return
	var mat: ProceduralSkyMaterial = _get_sky_material()
	var key: Dictionary = sample_diurnal_keyframe(_time_hours)

	# Weather (Rain/Storm/Snow/Ash) tints sky + haze, darkened at night; BG_SKY is never replaced.
	var wb: float = _current_weather_blend
	var tint_lum: float = lerpf(1.0, 0.16, _current_night_factor)
	var weather_col: Color = _current_sky_tint * tint_lum
	weather_col.a = 1.0
	var top_col: Color = (key["top"] as Color).lerp(weather_col * 0.78, wb * 0.75)
	var horizon_col: Color = (key["horizon"] as Color).lerp(weather_col, wb)
	var ground_h_col: Color = (key["ground_horizon"] as Color).lerp(weather_col * 0.9, wb)
	var fog_col: Color = (key["fog"] as Color).lerp(weather_col, wb * 0.9)

	if mat:
		mat.sky_top_color = top_col
		mat.sky_horizon_color = horizon_col
		mat.ground_horizon_color = ground_h_col
		mat.ground_bottom_color = key["ground_bottom"]

	env.background_mode = Environment.BG_SKY
	env.fog_enabled = true
	env.volumetric_fog_enabled = false
	env.fog_light_color = fog_col
	env.fog_density = _current_fog_density
	env.ambient_light_energy = float(key["ambient"]) * lerpf(1.0, 0.8, wb)
	env.ambient_light_sky_contribution = lerpf(0.75, 0.45, _current_night_factor)


func get_night_factor() -> float:
	return _current_night_factor


func set_time_of_day(hour: float) -> void:
	_local_time = fposmod(hour, 24.0)
	_time_hours = _local_time
	_apply_time_to_sky(_local_time)
	_apply_environmental_blend()


func calculate_night_factor(time_hours: float) -> float:
	# 06:00 - 18:00 is daytime (nf = 0.0)
	# 18:00 - 19:30 dusk transition (nf 0.0 -> 1.0)
	# 19:30 - 04:30 night (nf = 1.0)
	# 04:30 - 06:00 dawn transition (nf 1.0 -> 0.0)
	if time_hours >= 18.0 and time_hours < 19.5:
		return (time_hours - 18.0) / 1.5
	elif (time_hours >= 19.5 and time_hours <= 24.0) or (time_hours >= 0.0 and time_hours < 4.5):
		return 1.0
	elif time_hours >= 4.5 and time_hours < 6.0:
		return 1.0 - (time_hours - 4.5) / 1.5
	else:
		return 0.0


func _apply_time_to_sky(time_hours: float) -> void:
	_time_hours = fposmod(time_hours, 24.0)
	if _sky_node and is_instance_valid(_sky_node):
		var tod: Node = _sky_node.get("tod")
		if tod and is_instance_valid(tod):
			tod.set("current_time", time_hours)

	var nf: float = calculate_night_factor(time_hours)
	RenderingServer.global_shader_parameter_set("night_factor", nf)
	if abs(nf - _current_night_factor) > 0.002:
		_current_night_factor = nf
		night_factor_changed.emit(nf)

	_apply_sun_light(time_hours, nf)
	_apply_environmental_blend()


func get_sun_elevation_degrees(time_hours: float) -> float:
	"""Sun arc 05:30-19:30 (rising golden sun, high noon, low amber sunset); moon arc otherwise."""
	var t: float = fposmod(time_hours, 24.0)
	if t >= 5.5 and t <= 19.5:
		var u: float = (t - 5.5) / 14.0
		return 2.0 + 68.0 * pow(sin(u * PI), 1.25)
	var nt: float = t - 19.5 if t > 19.5 else t + 4.5
	return 18.0 + 40.0 * sin(clampf(nt / 10.0, 0.0, 1.0) * PI)


func _apply_sun_light(time_hours: float, _nf: float) -> void:
	if not _sun_light or not is_instance_valid(_sun_light):
		if not sun_light_path.is_empty():
			_sun_light = get_node_or_null(sun_light_path) as DirectionalLight3D
		if not _sun_light:
			return

	var t: float = fposmod(time_hours, 24.0)
	var key: Dictionary = sample_diurnal_keyframe(t)
	var elevation: float = get_sun_elevation_degrees(t)

	# Azimuth sweeps east -> west over the day arc; the moon continues the sweep at night.
	var yaw_deg: float
	if t >= 5.5 and t <= 19.5:
		yaw_deg = lerpf(-100.0, 100.0, (t - 5.5) / 14.0)
	else:
		var nt: float = t - 19.5 if t > 19.5 else t + 4.5
		yaw_deg = lerpf(100.0, 260.0, clampf(nt / 10.0, 0.0, 1.0))

	var energy: float = float(key["light_energy"]) * lerpf(1.0, 0.55, _current_weather_blend)
	_sun_light.rotation_degrees = Vector3(-elevation, yaw_deg, 0.0)
	_sun_light.light_color = key["light_color"]
	_sun_light.light_energy = energy


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
