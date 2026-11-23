# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/humanoid_animator.gd
# Universal Humanoid Animator for Gaia.
# Ensures zero T-poses across all 7 VRoid deities, mortal races, and dragon/demon rigs.
# Supports both UAL/embedded AnimationPlayer clips and guaranteed procedural bone poses.

extends Node

class_name HumanoidAnimator

enum AnimState {
	IDLE,
	WALK,
	RUN,
	CROUCH,
	JUMP,
	FLY,
	PRAY,
	DIVINE_HOVER,
	CRY
}

var current_state: AnimState = AnimState.IDLE
var anim_speed: float = 1.0
var move_velocity: Vector3 = Vector3.ZERO

var skeleton: Skeleton3D = null
var anim_player: AnimationPlayer = null
var is_vrm: bool = false
var has_clips: bool = false

# Cached bone indices (-1 if not found)
var bone_hips: int = -1
var bone_spine: int = -1
var bone_chest: int = -1
var bone_neck: int = -1
var bone_head: int = -1
var bone_l_upper_arm: int = -1
var bone_r_upper_arm: int = -1
var bone_l_lower_arm: int = -1
var bone_r_lower_arm: int = -1
var bone_l_hand: int = -1
var bone_r_hand: int = -1
var bone_l_upper_leg: int = -1
var bone_r_upper_leg: int = -1
var bone_l_lower_leg: int = -1
var bone_r_lower_leg: int = -1
var bone_l_foot: int = -1
var bone_r_foot: int = -1

# Phase accumulator for procedural animation
var _phase: float = 0.0

# Current procedural rotations (for smooth blending)
var _cur_l_arm: Quaternion = Quaternion.IDENTITY
var _cur_r_arm: Quaternion = Quaternion.IDENTITY
var _cur_l_forearm: Quaternion = Quaternion.IDENTITY
var _cur_r_forearm: Quaternion = Quaternion.IDENTITY
var _cur_l_thigh: Quaternion = Quaternion.IDENTITY
var _cur_r_thigh: Quaternion = Quaternion.IDENTITY
var _cur_l_knee: Quaternion = Quaternion.IDENTITY
var _cur_r_knee: Quaternion = Quaternion.IDENTITY
var _cur_spine: Quaternion = Quaternion.IDENTITY
var _cur_chest: Quaternion = Quaternion.IDENTITY
var _cur_head: Quaternion = Quaternion.IDENTITY

# Skeleton bone rest rotations (essential baseline: Godot 4 set_bone_pose_rotation sets absolute local transform)
var _rest_l_upper_arm: Quaternion = Quaternion.IDENTITY
var _rest_r_upper_arm: Quaternion = Quaternion.IDENTITY
var _rest_l_lower_arm: Quaternion = Quaternion.IDENTITY
var _rest_r_lower_arm: Quaternion = Quaternion.IDENTITY
var _rest_l_upper_leg: Quaternion = Quaternion.IDENTITY
var _rest_r_upper_leg: Quaternion = Quaternion.IDENTITY
var _rest_l_lower_leg: Quaternion = Quaternion.IDENTITY
var _rest_r_lower_leg: Quaternion = Quaternion.IDENTITY
var _rest_spine: Quaternion = Quaternion.IDENTITY
var _rest_chest: Quaternion = Quaternion.IDENTITY
var _rest_head: Quaternion = Quaternion.IDENTITY


func _ready() -> void:
	# If attached as a child in a scene, auto-bind parent
	if get_parent():
		bind_target(get_parent())


func bind_target(target_root: Node) -> void:
	skeleton = _find_skeleton(target_root)
	anim_player = _find_anim_player(target_root)

	if skeleton == null:
		push_warning("[HumanoidAnimator] No Skeleton3D found under: " + target_root.name)
		return

	_resolve_bones()

	# Detect if target is a VRoid model
	is_vrm = (bone_chest != -1 and skeleton.get_bone_name(bone_chest).begins_with("Chest")) or \
			 (bone_l_upper_arm != -1 and skeleton.get_bone_name(bone_l_upper_arm) == "LeftUpperArm")

	# Check for embedded animation clips
	if anim_player and anim_player.get_animation_list().size() > 0:
		var anims = anim_player.get_animation_list()
		for a in anims:
			if a in ["Idle", "Walk", "Run", "RedDragon_Armature|flightTest", "RedDragon_Armature|flight_fire"]:
				has_clips = true
				break

	# Try mounting shared UAL library if standard mortal skeleton
	if not has_clips and not is_vrm and bone_spine != -1 and skeleton.get_bone_name(bone_spine).begins_with("spine_"):
		_mount_shared_ual_library(target_root)


func _resolve_bones() -> void:
	bone_hips = _find_best_bone(["Hips", "pelvis", "Waist", "Body", "Root", "root"])
	bone_spine = _find_best_bone(["Spine", "spine_01", "Torso", "Abdomen"])
	bone_chest = _find_best_bone(["Chest", "UpperChest", "spine_02", "spine_03", "Torso"])
	bone_neck = _find_best_bone(["Neck", "neck_01"])
	bone_head = _find_best_bone(["Head", "head_01", "head"])

	bone_l_upper_arm = _find_best_bone(["LeftUpperArm", "upperarm_l", "UpperArm.L", "left_upper_arm"])
	bone_r_upper_arm = _find_best_bone(["RightUpperArm", "upperarm_r", "UpperArm.R", "right_upper_arm"])

	bone_l_lower_arm = _find_best_bone(["LeftLowerArm", "lowerarm_l", "LowerArm.L", "left_lower_arm"])
	bone_r_lower_arm = _find_best_bone(["RightLowerArm", "lowerarm_r", "LowerArm.R", "right_lower_arm"])

	bone_l_hand = _find_best_bone(["LeftHand", "hand_l", "Hand.L", "joint_LeftHandTwist"])
	bone_r_hand = _find_best_bone(["RightHand", "hand_r", "Hand.R", "joint_RightHandTwist"])

	bone_l_upper_leg = _find_best_bone(["LeftUpperLeg", "thigh_l", "UpperLeg.L", "left_upper_leg"])
	bone_r_upper_leg = _find_best_bone(["RightUpperLeg", "thigh_r", "UpperLeg.R", "right_upper_leg"])

	bone_l_lower_leg = _find_best_bone(["LeftLowerLeg", "calf_l", "LowerLeg.L", "left_lower_leg"])
	bone_r_lower_leg = _find_best_bone(["RightLowerLeg", "calf_r", "LowerLeg.R", "right_lower_leg"])

	bone_l_foot = _find_best_bone(["LeftFoot", "foot_l", "Foot.L"])
	bone_r_foot = _find_best_bone(["RightFoot", "foot_r", "Foot.R"])

	# Cache rest rotations so procedural deltas multiply cleanly against the model's bind pose
	if skeleton:
		if bone_l_upper_arm != -1: _rest_l_upper_arm = skeleton.get_bone_rest(bone_l_upper_arm).basis.get_rotation_quaternion()
		if bone_r_upper_arm != -1: _rest_r_upper_arm = skeleton.get_bone_rest(bone_r_upper_arm).basis.get_rotation_quaternion()
		if bone_l_lower_arm != -1: _rest_l_lower_arm = skeleton.get_bone_rest(bone_l_lower_arm).basis.get_rotation_quaternion()
		if bone_r_lower_arm != -1: _rest_r_lower_arm = skeleton.get_bone_rest(bone_r_lower_arm).basis.get_rotation_quaternion()

		if bone_l_upper_leg != -1: _rest_l_upper_leg = skeleton.get_bone_rest(bone_l_upper_leg).basis.get_rotation_quaternion()
		if bone_r_upper_leg != -1: _rest_r_upper_leg = skeleton.get_bone_rest(bone_r_upper_leg).basis.get_rotation_quaternion()
		if bone_l_lower_leg != -1: _rest_l_lower_leg = skeleton.get_bone_rest(bone_l_lower_leg).basis.get_rotation_quaternion()
		if bone_r_lower_leg != -1: _rest_r_lower_leg = skeleton.get_bone_rest(bone_r_lower_leg).basis.get_rotation_quaternion()

		if bone_spine != -1: _rest_spine = skeleton.get_bone_rest(bone_spine).basis.get_rotation_quaternion()
		if bone_chest != -1: _rest_chest = skeleton.get_bone_rest(bone_chest).basis.get_rotation_quaternion()
		if bone_head != -1: _rest_head = skeleton.get_bone_rest(bone_head).basis.get_rotation_quaternion()


func _find_best_bone(candidate_names: Array) -> int:
	if not skeleton:
		return -1
	for cand in candidate_names:
		var idx = skeleton.find_bone(cand)
		if idx != -1:
			return idx
	# Fallback: case-insensitive contains search
	for b in range(skeleton.get_bone_count()):
		var bname = skeleton.get_bone_name(b).to_lower()
		for cand in candidate_names:
			if cand.to_lower() in bname:
				return b
	return -1


func _mount_shared_ual_library(target_root: Node) -> void:
	var ual_path = "res://assets/mortals/animations/ual1_standard.glb"
	if not ResourceLoader.exists(ual_path):
		return
	var ual = load(ual_path).instantiate()
	var src_player = _find_anim_player(ual)
	if src_player:
		if not anim_player:
			anim_player = AnimationPlayer.new()
			anim_player.name = "HumanoidAnimationPlayer"
			target_root.add_child(anim_player)
		var lib = src_player.get_animation_library("")
		if lib and not anim_player.has_animation_library(""):
			anim_player.add_animation_library("", lib)
			has_clips = true
	ual.queue_free()


func set_state(new_state: AnimState) -> void:
	current_state = new_state


func set_velocity(vel: Vector3) -> void:
	move_velocity = vel


func _process(delta: float) -> void:
	step(delta)


func step(delta: float) -> void:
	if not skeleton:
		return

	# Handle animation playback if clips exist
	if has_clips and anim_player:
		_play_clip_state()
		# For non-VRM with clips, clips handle the pose
		return

	# Otherwise, drive guaranteed procedural humanoid pose (ZERO T-POSE GUARANTEE)
	_apply_procedural_pose(delta)


func _play_clip_state() -> void:
	if not anim_player:
		return

	var clip_name: String = "Idle"
	match current_state:
		AnimState.IDLE:
			clip_name = "Idle"
		AnimState.WALK:
			clip_name = "Walk"
		AnimState.RUN:
			if anim_player.has_animation("Jog_Fwd"):
				clip_name = "Jog_Fwd"
			elif anim_player.has_animation("Run"):
				clip_name = "Run"
			elif anim_player.has_animation("Sprint"):
				clip_name = "Sprint"
			else:
				clip_name = "Walk"
		AnimState.CROUCH:
			if anim_player.has_animation("Crouch_Idle"):
				clip_name = "Crouch_Idle"
			elif anim_player.has_animation("Duck"):
				clip_name = "Duck"
			else:
				clip_name = "Idle"
		AnimState.JUMP, AnimState.FLY:
			if anim_player.has_animation("RedDragon_Armature|flightTest"):
				clip_name = "RedDragon_Armature|flightTest"
			elif anim_player.has_animation("Jump"):
				clip_name = "Jump"
			else:
				clip_name = "Idle"
		AnimState.PRAY, AnimState.DIVINE_HOVER:
			if anim_player.has_animation("Fixing_Kneeling"):
				clip_name = "Fixing_Kneeling"
			elif anim_player.has_animation("Wave"):
				clip_name = "Wave"
			else:
				clip_name = "Idle"
		AnimState.CRY:
			clip_name = "Idle"

	if anim_player.has_animation(clip_name):
		if anim_player.current_animation != clip_name:
			anim_player.play(clip_name)


func _apply_procedural_pose(delta: float) -> void:
	var h_speed: float = Vector2(move_velocity.x, move_velocity.z).length()
	var freq: float = 1.0
	if current_state == AnimState.RUN:
		freq = 11.0
	elif current_state == AnimState.WALK:
		freq = 7.0
	elif current_state in [AnimState.IDLE, AnimState.DIVINE_HOVER, AnimState.PRAY]:
		freq = 2.0

	_phase += delta * freq * anim_speed

	# Target rotations for procedural bones
	var tgt_l_arm: Quaternion = Quaternion.IDENTITY
	var tgt_r_arm: Quaternion = Quaternion.IDENTITY
	var tgt_l_forearm: Quaternion = Quaternion.IDENTITY
	var tgt_r_forearm: Quaternion = Quaternion.IDENTITY
	var tgt_l_thigh: Quaternion = Quaternion.IDENTITY
	var tgt_r_thigh: Quaternion = Quaternion.IDENTITY
	var tgt_l_knee: Quaternion = Quaternion.IDENTITY
	var tgt_r_knee: Quaternion = Quaternion.IDENTITY
	var tgt_spine: Quaternion = Quaternion.IDENTITY
	var tgt_chest: Quaternion = Quaternion.IDENTITY
	var tgt_head: Quaternion = Quaternion.IDENTITY

	# Base relaxed standing angles (68° down from T-pose on local X)
	var arm_down: float = deg_to_rad(-68.0)
	var breath: float = sin(_phase) * 0.03
	var sway: float = cos(_phase * 0.8) * 0.02

	match current_state:
		AnimState.IDLE:
			# Relaxed arms at sides, subtle breathing, slight elbow bend
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), arm_down) * Quaternion(Vector3(0, 1, 0), deg_to_rad(6.0))
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), arm_down) * Quaternion(Vector3(0, 1, 0), deg_to_rad(-6.0))
			tgt_l_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-16.0))
			tgt_r_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-16.0))
			tgt_chest = Quaternion(Vector3(1, 0, 0), breath)
			tgt_head = Quaternion(Vector3(0, 1, 0), sway)
			# Legs remain strictly at rest baseline in IDLE (standing straight on feet)
			tgt_l_thigh = Quaternion.IDENTITY
			tgt_r_thigh = Quaternion.IDENTITY
			tgt_l_knee = Quaternion.IDENTITY
			tgt_r_knee = Quaternion.IDENTITY

		AnimState.WALK, AnimState.RUN:
			var stride_amp: float = 0.40 if current_state == AnimState.WALK else 0.65
			var arm_amp: float = 0.35 if current_state == AnimState.WALK else 0.55
			var stride: float = sin(_phase)

			# Leg swings: negative X moves thigh forward, positive X moves thigh backward
			tgt_l_thigh = Quaternion(Vector3(1, 0, 0), -stride * stride_amp)
			tgt_r_thigh = Quaternion(Vector3(1, 0, 0), stride * stride_amp)

			# Knee bend on trailing leg (negative X bends knee backward)
			var l_knee_bend: float = -maxf(0.0, -stride) * 0.70
			var r_knee_bend: float = -maxf(0.0, stride) * 0.70
			tgt_l_knee = Quaternion(Vector3(1, 0, 0), l_knee_bend)
			tgt_r_knee = Quaternion(Vector3(1, 0, 0), r_knee_bend)

			# Counter-swinging arms: on left arm, +Z swings forward; on right arm, +Z swings backward
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), arm_down) * Quaternion(Vector3(0, 0, 1), stride * arm_amp)
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), arm_down) * Quaternion(Vector3(0, 0, 1), stride * arm_amp)
			tgt_l_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-20.0))
			tgt_r_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-20.0))

			# Torso sway
			tgt_spine = Quaternion(Vector3(0, 1, 0), stride * 0.05)
			tgt_chest = Quaternion(Vector3(1, 0, 0), deg_to_rad(5.0))

		AnimState.CROUCH:
			# Torso leans forward, knees bent backward, arms tucked
			tgt_spine = Quaternion(Vector3(1, 0, 0), deg_to_rad(22.0))
			tgt_l_thigh = Quaternion(Vector3(1, 0, 0), deg_to_rad(-40.0))
			tgt_r_thigh = Quaternion(Vector3(1, 0, 0), deg_to_rad(-40.0))
			tgt_l_knee = Quaternion(Vector3(1, 0, 0), deg_to_rad(-60.0))
			tgt_r_knee = Quaternion(Vector3(1, 0, 0), deg_to_rad(-60.0))
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-55.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(15.0))
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-55.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(-15.0))
			tgt_l_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-35.0))
			tgt_r_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-35.0))

		AnimState.JUMP, AnimState.FLY:
			# Legs trailing/tucked backward, arms balanced outward
			tgt_l_thigh = Quaternion(Vector3(1, 0, 0), deg_to_rad(-15.0))
			tgt_r_thigh = Quaternion(Vector3(1, 0, 0), deg_to_rad(-20.0))
			tgt_l_knee = Quaternion(Vector3(1, 0, 0), deg_to_rad(-30.0))
			tgt_r_knee = Quaternion(Vector3(1, 0, 0), deg_to_rad(-40.0))
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-50.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(-12.0))
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-50.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(12.0))
			tgt_l_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-25.0))
			tgt_r_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-25.0))
			tgt_spine = Quaternion(Vector3(1, 0, 0), deg_to_rad(8.0))

		AnimState.PRAY, AnimState.DIVINE_HOVER:
			# Serene floating sway, hands clasped/raised gracefully near chest
			var hover_tilt: float = sin(_phase * 1.5) * 0.04
			tgt_spine = Quaternion(Vector3(1, 0, 0), hover_tilt)
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-48.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(30.0))
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-48.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(-30.0))
			tgt_l_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-65.0))
			tgt_r_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-65.0))
			tgt_head = Quaternion(Vector3(1, 0, 0), deg_to_rad(-8.0))

		AnimState.CRY:
			# Head bowed, hands near face, shaking shoulders
			var shake: float = sin(_phase * 15.0) * 0.03
			tgt_head = Quaternion(Vector3(1, 0, 0), deg_to_rad(25.0))
			tgt_chest = Quaternion(Vector3(0, 1, 0), shake)
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-40.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(40.0))
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-40.0)) * Quaternion(Vector3(0, 0, 1), deg_to_rad(-40.0))
			tgt_l_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-60.0))
			tgt_r_forearm = Quaternion(Vector3(1, 0, 0), deg_to_rad(-60.0))

	# Smoothly blend current rotations toward target
	var blend_rate: float = clampf(delta * 12.0, 0.0, 1.0)
	_cur_l_arm = _cur_l_arm.slerp(tgt_l_arm, blend_rate)
	_cur_r_arm = _cur_r_arm.slerp(tgt_r_arm, blend_rate)
	_cur_l_forearm = _cur_l_forearm.slerp(tgt_l_forearm, blend_rate)
	_cur_r_forearm = _cur_r_forearm.slerp(tgt_r_forearm, blend_rate)
	_cur_l_thigh = _cur_l_thigh.slerp(tgt_l_thigh, blend_rate)
	_cur_r_thigh = _cur_r_thigh.slerp(tgt_r_thigh, blend_rate)
	_cur_l_knee = _cur_l_knee.slerp(tgt_l_knee, blend_rate)
	_cur_r_knee = _cur_r_knee.slerp(tgt_r_knee, blend_rate)
	_cur_spine = _cur_spine.slerp(tgt_spine, blend_rate)
	_cur_chest = _cur_chest.slerp(tgt_chest, blend_rate)
	_cur_head = _cur_head.slerp(tgt_head, blend_rate)

	# Apply to Skeleton3D multiplied by rest rotation baseline
	if bone_l_upper_arm != -1:
		skeleton.set_bone_pose_rotation(bone_l_upper_arm, _rest_l_upper_arm * _cur_l_arm)
	if bone_r_upper_arm != -1:
		skeleton.set_bone_pose_rotation(bone_r_upper_arm, _rest_r_upper_arm * _cur_r_arm)
	if bone_l_lower_arm != -1:
		skeleton.set_bone_pose_rotation(bone_l_lower_arm, _rest_l_lower_arm * _cur_l_forearm)
	if bone_r_lower_arm != -1:
		skeleton.set_bone_pose_rotation(bone_r_lower_arm, _rest_r_lower_arm * _cur_r_forearm)

	if bone_l_upper_leg != -1:
		skeleton.set_bone_pose_rotation(bone_l_upper_leg, _rest_l_upper_leg * _cur_l_thigh)
	if bone_r_upper_leg != -1:
		skeleton.set_bone_pose_rotation(bone_r_upper_leg, _rest_r_upper_leg * _cur_r_thigh)
	if bone_l_lower_leg != -1:
		skeleton.set_bone_pose_rotation(bone_l_lower_leg, _rest_l_lower_leg * _cur_l_knee)
	if bone_r_lower_leg != -1:
		skeleton.set_bone_pose_rotation(bone_r_lower_leg, _rest_r_lower_leg * _cur_r_knee)

	if bone_spine != -1:
		skeleton.set_bone_pose_rotation(bone_spine, _rest_spine * _cur_spine)
	if bone_chest != -1:
		skeleton.set_bone_pose_rotation(bone_chest, _rest_chest * _cur_chest)
	if bone_head != -1:
		skeleton.set_bone_pose_rotation(bone_head, _rest_head * _cur_head)


func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for c in node.get_children():
		var found = _find_skeleton(c)
		if found:
			return found
	return null


func _find_anim_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for c in node.get_children():
		var found = _find_anim_player(c)
		if found:
			return found
	return null
