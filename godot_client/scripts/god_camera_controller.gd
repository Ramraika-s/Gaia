# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/god_camera_controller.gd
# Dual-Mode Camera Controller & Real CharacterBody3D God Avatar with Mouse-Look.
# - 3rd-Person Avatar Mode: CharacterBody3D with CapsuleShape3D collision, real gravity,
#   move_and_slide(), WASD sprint/crouch, space jump, F flight toggle, SpringArm3D collision,
#   mouse capture (Alt / UI release), surface footsteps, and jump landing dust VFX.
# - Orbital RTS Mode: Unconstrained RTS map pan, right-click orbit, scroll zoom.

extends Node3D

enum CameraMode {
	ORBITAL_RTS,
	THIRD_PERSON_AVATAR
}

const GOD_AVATAR_PATH: String = "res://assets/deities/god_avatar.vrm"
const ORBITAL_ALTITUDE_THRESHOLD: float = 250.0

@export var mode: CameraMode = CameraMode.THIRD_PERSON_AVATAR
@export var walk_speed: float = 8.0
@export var sprint_speed: float = 18.0
@export var crouch_speed: float = 3.5
@export var flight_speed: float = 32.0
@export var jump_velocity: float = 8.5
@export var gravity: float = 22.0
@export var mouse_sensitivity: float = 0.22

# Orbital RTS parameters
@export var orbital_pan_speed: float = 65.0
@export var orbital_zoom_speed: float = 15.0
@export var orbital_min_zoom: float = 20.0
@export var orbital_max_zoom: float = 800.0

# Node references
var avatar_body: CharacterBody3D = null
var avatar_collider: CollisionShape3D = null
var avatar_capsule: CapsuleShape3D = null
var avatar_visual_root: Node3D = null
var dust_particles: GPUParticles3D = null
var footstep_audio: AudioStreamPlayer3D = null
var avatar_animator: HumanoidAnimator = null

var camera_pivot: Node3D = null
var spring_arm: SpringArm3D = null
var camera: Camera3D = null

# Controller State
var _yaw: float = 0.0
var _pitch: float = -20.0
var _target_zoom: float = 6.0
var _orbital_target_pos: Vector3 = Vector3(0.0, 18.5, 0.0)

var _is_flying: bool = false
var _is_crouching: bool = false
var _was_on_floor: bool = true
var _standing_capsule_height: float = 1.8
var _crouch_capsule_height: float = 1.1
var _capsule_radius: float = 0.4

var _step_distance_accum: float = 0.0
var _is_right_mouse_down: bool = false

# Cached footstep sounds
var _sfx_grass: Array[AudioStream] = []
var _sfx_concrete: Array[AudioStream] = []
var _sfx_snow: Array[AudioStream] = []
var _sfx_impact: AudioStream = null


func _ready() -> void:
	_ensure_input_actions()
	_preload_audio()
	_setup_nodes()
	_update_camera_mode(true)


func _ensure_input_actions() -> void:
	if not InputMap.has_action("toggle_camera_mode"):
		InputMap.add_action("toggle_camera_mode")
		var ev: InputEventKey = InputEventKey.new()
		ev.keycode = KEY_TAB
		InputMap.action_add_event("toggle_camera_mode", ev)


func _preload_audio() -> void:
	for i in range(5):
		var p_grass = "res://assets/audio/impacts/footstep_grass_%03d.ogg" % i
		if ResourceLoader.exists(p_grass):
			_sfx_grass.append(load(p_grass) as AudioStream)

		var p_conc = "res://assets/audio/impacts/footstep_concrete_%03d.ogg" % i
		if ResourceLoader.exists(p_conc):
			_sfx_concrete.append(load(p_conc) as AudioStream)

		var p_snow = "res://assets/audio/impacts/footstep_snow_%03d.ogg" % i
		if ResourceLoader.exists(p_snow):
			_sfx_snow.append(load(p_snow) as AudioStream)

	var p_imp = "res://assets/audio/impacts/impact_soft_heavy_000.ogg"
	if ResourceLoader.exists(p_imp):
		_sfx_impact = load(p_imp) as AudioStream


func _setup_nodes() -> void:
	# 1. Setup or retrieve CharacterBody3D GodAvatar
	avatar_body = get_node_or_null("GodAvatar") as CharacterBody3D
	if not avatar_body:
		avatar_body = CharacterBody3D.new()
		avatar_body.name = "GodAvatar"
		add_child(avatar_body)

	avatar_body.collision_layer = 2  # God layer
	avatar_body.collision_mask = 1   # Collides with environment & terrain

	# Set initial position flush with ground
	TerrainHeightSampler.ensure_loaded()
	var ground_h: float = TerrainHeightSampler.get_height(0.0, 0.0)
	avatar_body.global_position = Vector3(0.0, ground_h, 0.0)

	# 2. Collider setup
	avatar_collider = avatar_body.get_node_or_null("CollisionShape3D") as CollisionShape3D
	if not avatar_collider:
		avatar_collider = CollisionShape3D.new()
		avatar_collider.name = "CollisionShape3D"
		avatar_body.add_child(avatar_collider)

	avatar_capsule = CapsuleShape3D.new()
	avatar_capsule.radius = _capsule_radius
	avatar_capsule.height = _standing_capsule_height
	avatar_collider.shape = avatar_capsule
	avatar_collider.position = Vector3(0.0, _standing_capsule_height * 0.5, 0.0)

	# 3. Visual Root
	avatar_visual_root = avatar_body.get_node_or_null("VisualRoot") as Node3D
	if not avatar_visual_root:
		avatar_visual_root = Node3D.new()
		avatar_visual_root.name = "VisualRoot"
		avatar_body.add_child(avatar_visual_root)

	_instance_god_visuals()

	# 4. Landing Dust VFX
	dust_particles = avatar_body.get_node_or_null("DustParticles") as GPUParticles3D
	if not dust_particles:
		dust_particles = GPUParticles3D.new()
		dust_particles.name = "DustParticles"
		avatar_body.add_child(dust_particles)
		_configure_dust_particles(dust_particles)

	# 5. Footstep & Impact Audio
	footstep_audio = avatar_body.get_node_or_null("FootstepAudio") as AudioStreamPlayer3D
	if not footstep_audio:
		footstep_audio = AudioStreamPlayer3D.new()
		footstep_audio.name = "FootstepAudio"
		footstep_audio.max_distance = 25.0
		avatar_body.add_child(footstep_audio)

	# 6. Camera Pivot, SpringArm3D & Camera3D
	camera_pivot = get_node_or_null("CameraPivot") as Node3D
	if not camera_pivot:
		camera_pivot = Node3D.new()
		camera_pivot.name = "CameraPivot"
		add_child(camera_pivot)

	spring_arm = camera_pivot.get_node_or_null("SpringArm3D") as SpringArm3D
	if not spring_arm:
		spring_arm = SpringArm3D.new()
		spring_arm.name = "SpringArm3D"
		spring_arm.margin = 0.25
		spring_arm.collision_mask = 1  # Collide with terrain/walls so camera never clips
		camera_pivot.add_child(spring_arm)

	camera = spring_arm.get_node_or_null("Camera3D") as Camera3D
	if not camera:
		# Check if an existing Camera3D was attached under CameraPivot
		var old_cam: Camera3D = camera_pivot.get_node_or_null("Camera3D") as Camera3D
		if old_cam:
			old_cam.reparent(spring_arm)
			camera = old_cam
		else:
			camera = Camera3D.new()
			camera.name = "Camera3D"
			spring_arm.add_child(camera)

	camera.current = true
	camera.fov = 65.0
	camera.far = 5000.0
	camera.position = Vector3.ZERO


func _instance_god_visuals() -> void:
	var model_inst: Node = null
	if ResourceLoader.exists(GOD_AVATAR_PATH):
		var scene: PackedScene = load(GOD_AVATAR_PATH) as PackedScene
		if scene:
			model_inst = scene.instantiate()
			avatar_visual_root.add_child(model_inst)
			avatar_animator = HumanoidAnimator.new()
			avatar_animator.name = "GodAvatarAnimator"
			avatar_body.add_child(avatar_animator)
			avatar_animator.bind_target(model_inst)

	if not model_inst:
		# Fallback stylized golden deity avatar
		var mesh_inst: MeshInstance3D = MeshInstance3D.new()
		var capsule: CapsuleMesh = CapsuleMesh.new()
		capsule.radius = _capsule_radius
		capsule.height = _standing_capsule_height
		mesh_inst.mesh = capsule
		var mat: StandardMaterial3D = StandardMaterial3D.new()
		mat.albedo_color = Color(1.0, 0.88, 0.35, 1.0)
		mat.emission_enabled = true
		mat.emission = Color(0.95, 0.75, 0.2, 1.0)
		mesh_inst.material_override = mat
		mesh_inst.position = Vector3(0.0, _standing_capsule_height * 0.5, 0.0)
		avatar_visual_root.add_child(mesh_inst)


func _configure_dust_particles(particles: GPUParticles3D) -> void:
	particles.emitting = false
	particles.one_shot = true
	particles.explosiveness = 1.0
	particles.amount = 14
	particles.lifetime = 0.45

	var mat: ParticleProcessMaterial = ParticleProcessMaterial.new()
	mat.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_RING
	mat.emission_ring_radius = 0.5
	mat.direction = Vector3(0.0, 1.0, 0.0)
	mat.spread = 50.0
	mat.initial_velocity_min = 1.5
	mat.initial_velocity_max = 3.2
	mat.gravity = Vector3(0.0, -5.0, 0.0)
	mat.color = Color(0.85, 0.82, 0.72, 0.55)

	particles.process_material = mat

	var quad: QuadMesh = QuadMesh.new()
	quad.size = Vector2(0.25, 0.25)
	var qmat: StandardMaterial3D = StandardMaterial3D.new()
	qmat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	qmat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	qmat.vertex_color_use_as_albedo = true
	qmat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	quad.material = qmat

	particles.draw_pass_1 = quad


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("toggle_camera_mode"):
		_toggle_mode()
		get_viewport().set_input_as_handled()
		return

	# Flight toggle with F
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_F and mode == CameraMode.THIRD_PERSON_AVATAR:
			_is_flying = !_is_flying
			if _is_flying:
				_is_crouching = false
				if avatar_body:
					avatar_body.velocity.y = 4.0
			print("[GodCameraController] Divine Flight mode: ", _is_flying)
			get_viewport().set_input_as_handled()
			return
		elif (event.keycode == KEY_CTRL or event.keycode == KEY_C) and mode == CameraMode.THIRD_PERSON_AVATAR:
			if not _is_flying:
				_is_crouching = !_is_crouching
			get_viewport().set_input_as_handled()
			return

	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_RIGHT:
			_is_right_mouse_down = mb.pressed
		elif mb.button_index == MOUSE_BUTTON_LEFT and mb.pressed:
			# Click into viewport recaptures mouse if in avatar mode
			if mode == CameraMode.THIRD_PERSON_AVATAR and not _is_any_ui_open() and not Input.is_key_pressed(KEY_ALT):
				Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP:
			if mode == CameraMode.ORBITAL_RTS:
				_target_zoom = maxf(orbital_min_zoom, _target_zoom - orbital_zoom_speed)
			else:
				_target_zoom = clampf(_target_zoom - 1.0, 2.5, 15.0)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			if mode == CameraMode.ORBITAL_RTS:
				_target_zoom = minf(orbital_max_zoom, _target_zoom + orbital_zoom_speed)
			else:
				_target_zoom = clampf(_target_zoom + 1.0, 2.5, 15.0)

	elif event is InputEventMouseMotion:
		var mm: InputEventMouseMotion = event as InputEventMouseMotion
		if mode == CameraMode.THIRD_PERSON_AVATAR and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			_yaw -= mm.relative.x * mouse_sensitivity
			_pitch = clampf(_pitch - mm.relative.y * mouse_sensitivity, -80.0, 60.0)
		elif mode == CameraMode.ORBITAL_RTS and _is_right_mouse_down:
			_yaw -= mm.relative.x * 0.25
			_pitch = clampf(_pitch - mm.relative.y * 0.25, -85.0, -10.0)


func _physics_process(delta: float) -> void:
	_update_mouse_capture()

	if mode == CameraMode.THIRD_PERSON_AVATAR:
		_process_avatar_physics(delta)
	else:
		_process_orbital_pan(delta)

	_update_camera_transform(delta)


func _update_mouse_capture() -> void:
	var is_ui_open: bool = _is_any_ui_open()
	if mode == CameraMode.THIRD_PERSON_AVATAR and not is_ui_open and not Input.is_key_pressed(KEY_ALT):
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	else:
		if Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _is_any_ui_open() -> bool:
	var tree = get_tree()
	if not tree:
		return false
	var root = tree.root
	for path in [
		"MainWorld/TwoBookModal",
		"MainWorld/GodConsoleOverlay",
		"MainWorld/EntityInspector"
	]:
		var node = root.get_node_or_null(path)
		if node and node is CanvasLayer and node.visible:
			return true
	return false


func _process_avatar_physics(delta: float) -> void:
	if not avatar_body:
		return

	# 1. Movement input relative to camera yaw (W=forward, S=backward, D=right, A=left)
	var forward_input: float = 0.0
	var right_input: float = 0.0
	if Input.is_key_pressed(KEY_W):
		forward_input += 1.0
	if Input.is_key_pressed(KEY_S):
		forward_input -= 1.0
	if Input.is_key_pressed(KEY_A):
		right_input -= 1.0
	if Input.is_key_pressed(KEY_D):
		right_input += 1.0

	var yaw_rad: float = deg_to_rad(_yaw)
	var forward: Vector3 = Vector3(-sin(yaw_rad), 0.0, -cos(yaw_rad)).normalized()
	var right: Vector3 = Vector3(cos(yaw_rad), 0.0, -sin(yaw_rad)).normalized()

	var move_vec: Vector3 = forward * forward_input + right * right_input
	var move_dir: Vector3 = move_vec.normalized() if move_vec.length_squared() > 0.001 else Vector3.ZERO

	# Determine speed
	var current_speed: float = walk_speed
	if _is_crouching:
		current_speed = crouch_speed
	elif Input.is_key_pressed(KEY_SHIFT):
		current_speed = sprint_speed

	var target_vel_h: Vector3 = move_dir * current_speed
	avatar_body.velocity.x = lerpf(avatar_body.velocity.x, target_vel_h.x, delta * 14.0)
	avatar_body.velocity.z = lerpf(avatar_body.velocity.z, target_vel_h.z, delta * 14.0)

	# 3. Flight or Ground physics
	if _is_flying:
		# Flying vertical controls
		var v_dir: float = 0.0
		if Input.is_key_pressed(KEY_SPACE):
			v_dir += 1.0
		if Input.is_key_pressed(KEY_CTRL) or Input.is_key_pressed(KEY_C):
			v_dir -= 1.0

		avatar_body.velocity.y = lerpf(avatar_body.velocity.y, v_dir * flight_speed, delta * 8.0)

		# Clamp above terrain
		var min_terrain_y: float = TerrainHeightSampler.get_height(avatar_body.global_position.x, avatar_body.global_position.z) + 0.5
		if avatar_body.global_position.y < min_terrain_y:
			avatar_body.global_position.y = min_terrain_y
			if avatar_body.velocity.y < 0.0:
				avatar_body.velocity.y = 0.0
	else:
		# Gravity
		if not avatar_body.is_on_floor():
			avatar_body.velocity.y -= gravity * delta
		else:
			# Jump when grounded (or stand up if crouched)
			if Input.is_key_pressed(KEY_SPACE):
				if _is_crouching:
					_is_crouching = false
				else:
					avatar_body.velocity.y = jump_velocity

	# 4. Smooth Capsule Crouch scaling
	var target_capsule_h: float = _crouch_capsule_height if _is_crouching else _standing_capsule_height
	avatar_capsule.height = lerpf(avatar_capsule.height, target_capsule_h, delta * 10.0)
	avatar_collider.position.y = avatar_capsule.height * 0.5

	# 5. Execute move_and_slide()
	avatar_body.move_and_slide()

	# Landing detection
	var is_floor_now: bool = avatar_body.is_on_floor()
	if is_floor_now and not _was_on_floor:
		_trigger_landing_effects()
	_was_on_floor = is_floor_now

	# 6. Smooth Facing Rotation toward movement direction or camera yaw
	if move_dir.length_squared() > 0.01:
		var target_angle: float = atan2(-move_dir.x, -move_dir.z)
		avatar_visual_root.rotation.y = lerp_angle(avatar_visual_root.rotation.y, target_angle, delta * 12.0)
	else:
		# When idle in 3rd person mode, face toward camera yaw
		var target_angle: float = deg_to_rad(_yaw)
		avatar_visual_root.rotation.y = lerp_angle(avatar_visual_root.rotation.y, target_angle, delta * 8.0)

	# 7. Update HumanoidAnimator state
	if avatar_animator:
		avatar_animator.set_velocity(avatar_body.velocity)
		if _is_flying:
			avatar_animator.set_state(HumanoidAnimator.AnimState.FLY)
		elif not is_floor_now:
			avatar_animator.set_state(HumanoidAnimator.AnimState.JUMP)
		elif _is_crouching:
			avatar_animator.set_state(HumanoidAnimator.AnimState.CROUCH)
		else:
			var h_vel: float = Vector2(avatar_body.velocity.x, avatar_body.velocity.z).length()
			if h_vel > 6.0:
				avatar_animator.set_state(HumanoidAnimator.AnimState.RUN)
			elif h_vel > 0.4:
				avatar_animator.set_state(HumanoidAnimator.AnimState.WALK)
			else:
				avatar_animator.set_state(HumanoidAnimator.AnimState.IDLE)

	# 7. Footstep Audio
	if is_floor_now and not _is_flying:
		var h_speed: float = Vector2(avatar_body.velocity.x, avatar_body.velocity.z).length()
		if h_speed > 0.5:
			_step_distance_accum += h_speed * delta
			var step_dist_needed: float = 1.8 if not Input.is_key_pressed(KEY_SHIFT) else 2.6
			if _step_distance_accum >= step_dist_needed:
				_step_distance_accum = 0.0
				_play_footstep_sound()
		else:
			_step_distance_accum = 0.0

	# Sync position with WebSocket bridge
	_sync_bridge_position(avatar_body.global_position, false, _target_zoom)


func _trigger_landing_effects() -> void:
	if dust_particles:
		dust_particles.restart()
		dust_particles.emitting = true

	if footstep_audio and _sfx_impact:
		footstep_audio.stream = _sfx_impact
		footstep_audio.pitch_scale = randf_range(0.92, 1.08)
		footstep_audio.play()


func _play_footstep_sound() -> void:
	if not footstep_audio:
		return

	var pos: Vector3 = avatar_body.global_position
	var is_near_sanctum: bool = pos.distance_to(Vector3.ZERO) < 120.0
	var pool: Array[AudioStream] = _sfx_grass

	if is_near_sanctum:
		pool = _sfx_concrete
	elif pos.z < -1500.0 and pos.x < -1500.0: # Beasthuman Taiga / Snow
		pool = _sfx_snow

	if pool.is_empty():
		return

	var sfx: AudioStream = pool[randi() % pool.size()]
	footstep_audio.stream = sfx
	footstep_audio.pitch_scale = randf_range(0.90, 1.12)
	footstep_audio.play()


func _process_orbital_pan(delta: float) -> void:
	var speed: float = orbital_pan_speed
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= 2.5

	var move_dir: Vector3 = Vector3.ZERO
	if Input.is_key_pressed(KEY_W):
		move_dir.z -= 1.0
	if Input.is_key_pressed(KEY_S):
		move_dir.z += 1.0
	if Input.is_key_pressed(KEY_A):
		move_dir.x -= 1.0
	if Input.is_key_pressed(KEY_D):
		move_dir.x += 1.0

	var yaw_rad: float = deg_to_rad(_yaw)
	var forward: Vector3 = Vector3(-sin(yaw_rad), 0.0, -cos(yaw_rad)).normalized()
	var right: Vector3 = Vector3(cos(yaw_rad), 0.0, -sin(yaw_rad)).normalized()

	var world_move: Vector3 = (right * move_dir.x + forward * move_dir.z).normalized()
	_orbital_target_pos += world_move * speed * delta

	# Clamp world boundary limits
	_orbital_target_pos.x = clampf(_orbital_target_pos.x, -4900.0, 4900.0)
	_orbital_target_pos.z = clampf(_orbital_target_pos.z, -4900.0, 4900.0)

	var ground_h: float = TerrainHeightSampler.get_height(_orbital_target_pos.x, _orbital_target_pos.z)
	_orbital_target_pos.y = ground_h

	_sync_bridge_position(_orbital_target_pos, true, _target_zoom)


func _update_camera_transform(delta: float) -> void:
	var target_eye_h: float = (_crouch_capsule_height * 0.8) if _is_crouching else (_standing_capsule_height * 0.9)

	if mode == CameraMode.THIRD_PERSON_AVATAR and avatar_body:
		var target_pivot_pos: Vector3 = avatar_body.global_position + Vector3(0.0, target_eye_h, 0.0)
		camera_pivot.global_position = camera_pivot.global_position.lerp(target_pivot_pos, delta * 16.0)
		avatar_body.visible = true
	else:
		var target_pivot_pos: Vector3 = _orbital_target_pos + Vector3(0.0, 1.5, 0.0)
		camera_pivot.global_position = camera_pivot.global_position.lerp(target_pivot_pos, delta * 12.0)
		if avatar_body:
			avatar_body.visible = (_target_zoom < 150.0)

	var target_rot: Vector3 = Vector3(deg_to_rad(_pitch), deg_to_rad(_yaw), 0.0)
	camera_pivot.rotation.x = lerp_angle(camera_pivot.rotation.x, target_rot.x, delta * 14.0)
	camera_pivot.rotation.y = lerp_angle(camera_pivot.rotation.y, target_rot.y, delta * 14.0)

	spring_arm.spring_length = lerpf(spring_arm.spring_length, _target_zoom, delta * 10.0)


func _toggle_mode() -> void:
	if mode == CameraMode.ORBITAL_RTS:
		mode = CameraMode.THIRD_PERSON_AVATAR
		_target_zoom = 6.0
		_pitch = -20.0
		if avatar_body:
			camera_pivot.global_position = avatar_body.global_position + Vector3(0.0, 1.5, 0.0)
	else:
		mode = CameraMode.ORBITAL_RTS
		_target_zoom = 65.0
		_pitch = -45.0
		if avatar_body:
			_orbital_target_pos = avatar_body.global_position
			camera_pivot.global_position = _orbital_target_pos + Vector3(0.0, 1.5, 0.0)

	_update_camera_mode(false)


func _update_camera_mode(immediate: bool) -> void:
	if mode == CameraMode.THIRD_PERSON_AVATAR:
		_target_zoom = 6.0
		_pitch = -20.0
	else:
		_target_zoom = 65.0
		_pitch = -45.0

	if immediate:
		spring_arm.spring_length = _target_zoom
		camera_pivot.rotation = Vector3(deg_to_rad(_pitch), deg_to_rad(_yaw), 0.0)


func _sync_bridge_position(pos: Vector3, is_orbital: bool, zoom: float) -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.has_method("update_god_focus"):
		bridge.update_god_focus(pos, is_orbital, zoom)
