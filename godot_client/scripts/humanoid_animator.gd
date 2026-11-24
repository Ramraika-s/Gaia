# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/humanoid_animator.gd
# Universal Humanoid Animator for Gaia.
# Priority 1: Embedded AnimationPlayer clips (case-insensitive substring match + LOOP_LINEAR).
# Priority 2: Retargeted shared ual1_standard.glb clips (track paths remapped & filtered).
# Priority 3: Exact Skeleton3D-space rest-pose procedural fallback (zero zombie arms, zero T-pose).

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

const UAL1_PATH: String = "res://assets/mortals/animations/ual1_standard.glb"
const UAL_CLIP_WHITELIST: Array[String] = [
	"Idle",
	"Walk",
	"Jog_Fwd",
	"Sprint",
	"Crouch_Idle",
	"Jump",
	"Fixing_Kneeling",
	"Death01",
]
const IGNORED_CLIP_TOKENS: Array[String] = [
	"reset", "tpose", "a_tpose", "ref", "blink", "look",
	"aa", "ee", "ih", "oh", "ou", "neutral", "happy", "angry", "sad", "relaxed", "surprised",
]

static var _raw_ual_lib: AnimationLibrary = null
static var _remapped_ual_libs: Dictionary = {}  # skel_path_str -> AnimationLibrary

var current_state: AnimState = AnimState.IDLE
var anim_speed: float = 1.0
var move_velocity: Vector3 = Vector3.ZERO

var skeleton: Skeleton3D = null
var anim_player: AnimationPlayer = null
var is_vrm: bool = false
var has_clips: bool = false

var _clip_map: Dictionary = {}  # AnimState -> StringName

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

# Local & global rest rotations per bone_idx for exact Skeleton3D-space procedural poses
var _local_rest_q: Dictionary = {}
var _global_rest_q: Dictionary = {}
var _q_l_arm_down_skel: Quaternion = Quaternion.IDENTITY
var _q_r_arm_down_skel: Quaternion = Quaternion.IDENTITY
var _l_elbow_axis_rest: Vector3 = Vector3(1, 0, 0)
var _r_elbow_axis_rest: Vector3 = Vector3(1, 0, 0)
var _skel_fwd_z: float = -1.0  # -1.0 for -Z forward (VRM 0.0), +1.0 for +Z forward (VRM 1.0 / glTF)

# Phase accumulator & current smoothed Skeleton3D-space delta rotations
var _phase: float = 0.0
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


static func clear_static_caches() -> void:
	_raw_ual_lib = null
	_remapped_ual_libs.clear()


func _ready() -> void:
	if get_parent():
		bind_target(get_parent())


func bind_target(target_root: Node) -> void:
	# Reset state cleanly (important for pooled MortalActor mesh switching)
	has_clips = false
	is_vrm = false
	_clip_map.clear()
	_local_rest_q.clear()
	_global_rest_q.clear()
	_q_l_arm_down_skel = Quaternion.IDENTITY
	_q_r_arm_down_skel = Quaternion.IDENTITY
	_cur_l_arm = Quaternion.IDENTITY
	_cur_r_arm = Quaternion.IDENTITY
	_cur_l_forearm = Quaternion.IDENTITY
	_cur_r_forearm = Quaternion.IDENTITY
	_cur_l_thigh = Quaternion.IDENTITY
	_cur_r_thigh = Quaternion.IDENTITY
	_cur_l_knee = Quaternion.IDENTITY
	_cur_r_knee = Quaternion.IDENTITY
	_cur_spine = Quaternion.IDENTITY
	_cur_chest = Quaternion.IDENTITY
	_cur_head = Quaternion.IDENTITY

	skeleton = _find_skeleton(target_root)
	anim_player = _find_anim_player(target_root)

	if skeleton == null:
		push_warning("[HumanoidAnimator] No Skeleton3D found under: " + target_root.name)
		return

	_resolve_bones()

	# Detect VRM humanoid rigs (VRM 0.0 & VRM 1.0 have VRM expression clips, never body locomotion)
	var upper_arm_name: String = skeleton.get_bone_name(bone_l_upper_arm) if bone_l_upper_arm != -1 else ""
	var chest_name: String = skeleton.get_bone_name(bone_chest) if bone_chest != -1 else ""
	is_vrm = (upper_arm_name == "LeftUpperArm" or chest_name.begins_with("Chest") or "J_Bip_" in upper_arm_name)

	# Priority 1: Embedded locomotion animations (case-insensitive substring match)
	if not is_vrm and anim_player and anim_player.get_animation_list().size() > 0:
		_index_embedded_clips()

	# Priority 2: Properly retargeted UAL1 library for standard UAL humanoid rigs
	if not has_clips and not is_vrm and _has_ual_skeleton():
		_mount_shared_ual_library(target_root)

	# Priority 3: Precompute exact rest-pose arm-down transforms for procedural fallback
	_compute_rest_pose_calibration()

	if has_clips and anim_player:
		_play_clip_state()
	else:
		# Snap initial procedural pose immediately so frame 0 has zero T-pose flash
		_apply_procedural_pose(1.0)


func _has_ual_skeleton() -> bool:
	return skeleton != null and skeleton.find_bone("pelvis") != -1 and skeleton.find_bone("upperarm_l") != -1


func _is_ignored_clip(aname_lower: String) -> bool:
	for tok in IGNORED_CLIP_TOKENS:
		if aname_lower == tok or aname_lower.ends_with("|" + tok):
			return true
	return false


func _find_matching_clip(anims: PackedStringArray, exact_prefs: Array[String], sub_tokens: Array[String], excludes: Array[String] = []) -> String:
	for pref in exact_prefs:
		for a in anims:
			if a.to_lower() == pref.to_lower():
				return a
	for tok in sub_tokens:
		for a in anims:
			var al: String = a.to_lower()
			if _is_ignored_clip(al):
				continue
			var bad: bool = false
			for ex in excludes:
				if ex in al:
					bad = true
					break
			if not bad and tok in al:
				return a
	return ""


func _index_embedded_clips() -> void:
	if not anim_player:
		return
	var anims: PackedStringArray = anim_player.get_animation_list()
	if anims.is_empty():
		return

	var idle_clip := _find_matching_clip(anims, ["Idle_Loop", "Idle"], ["idle"], ["jump", "crouch", "sitting", "pistol", "zombie", "swim", "talking", "torch", "fold", "lantern", "rail", "shield"])
	var walk_clip := _find_matching_clip(anims, ["Walk_Loop", "Walk"], ["walk"], ["zombie", "formal", "carry"])
	var run_clip := _find_matching_clip(anims, ["Jog_Fwd_Loop", "Jog_Fwd", "Run", "Sprint_Loop", "Sprint"], ["jog", "run", "sprint"], [])
	var crouch_clip := _find_matching_clip(anims, ["Crouch_Idle_Loop", "Crouch_Idle", "Duck"], ["crouch_idle", "duck", "crouch"], [])
	var fly_clip := _find_matching_clip(anims, ["RedDragon_Armature|flightTest", "Jump_Loop", "Jump"], ["flighttest", "jump"], ["land", "start", "idle"])
	var pray_clip := _find_matching_clip(anims, ["Fixing_Kneeling", "Wave"], ["kneel", "wave"], [])

	if idle_clip == "" and walk_clip == "" and fly_clip == "":
		return

	var fallback_idle: String = idle_clip if idle_clip != "" else (walk_clip if walk_clip != "" else fly_clip)
	_clip_map[AnimState.IDLE] = StringName(fallback_idle)
	_clip_map[AnimState.WALK] = StringName(walk_clip if walk_clip != "" else fallback_idle)
	_clip_map[AnimState.RUN] = StringName(run_clip if run_clip != "" else _clip_map[AnimState.WALK])
	_clip_map[AnimState.CROUCH] = StringName(crouch_clip if crouch_clip != "" else fallback_idle)
	_clip_map[AnimState.JUMP] = StringName(fly_clip if fly_clip != "" else fallback_idle)
	_clip_map[AnimState.FLY] = StringName(fly_clip if fly_clip != "" else fallback_idle)
	_clip_map[AnimState.PRAY] = StringName(pray_clip if pray_clip != "" else fallback_idle)
	_clip_map[AnimState.DIVINE_HOVER] = StringName(fallback_idle)
	_clip_map[AnimState.CRY] = StringName(fallback_idle)

	for st in [AnimState.IDLE, AnimState.WALK, AnimState.RUN, AnimState.CROUCH, AnimState.FLY]:
		var cname: StringName = _clip_map[st]
		if anim_player.has_animation(cname):
			var anim: Animation = anim_player.get_animation(cname)
			if anim:
				anim.loop_mode = Animation.LOOP_LINEAR

	has_clips = true


func _ensure_raw_ual_lib() -> void:
	if _raw_ual_lib != null:
		return
	if not ResourceLoader.exists(UAL1_PATH):
		return
	var packed: PackedScene = load(UAL1_PATH) as PackedScene
	if not packed:
		return
	var ual_inst: Node = packed.instantiate()
	var src_player: AnimationPlayer = _find_anim_player(ual_inst)
	if src_player:
		var src_lib: AnimationLibrary = src_player.get_animation_library("")
		if src_lib:
			var curated := AnimationLibrary.new()
			for cname in UAL_CLIP_WHITELIST:
				if src_lib.has_animation(cname):
					var anim_copy: Animation = src_lib.get_animation(cname).duplicate(true) as Animation
					if anim_copy:
						curated.add_animation(cname, anim_copy)
			_raw_ual_lib = curated
	ual_inst.free()


func _mount_shared_ual_library(target_root: Node) -> void:
	_ensure_raw_ual_lib()
	if _raw_ual_lib == null or skeleton == null:
		return

	if not anim_player:
		anim_player = AnimationPlayer.new()
		anim_player.name = "HumanoidAnimationPlayer"
		anim_player.root_node = NodePath("..")
		target_root.add_child(anim_player)

	var root_ref: Node = anim_player.get_node_or_null(anim_player.root_node)
	if root_ref == null:
		root_ref = target_root
	var skel_path_str: String = String(root_ref.get_path_to(skeleton))

	var lib: AnimationLibrary = _remapped_ual_libs.get(skel_path_str, null) as AnimationLibrary
	if lib == null:
		lib = AnimationLibrary.new()
		for cname in _raw_ual_lib.get_animation_list():
			var anim: Animation = _raw_ual_lib.get_animation(cname).duplicate(true) as Animation
			if not anim:
				continue
			for t in range(anim.get_track_count() - 1, -1, -1):
				var orig_path: NodePath = anim.track_get_path(t)
				var bone_sub: String = String(orig_path.get_concatenated_subnames())
				if bone_sub == "" or skeleton.find_bone(bone_sub) == -1:
					anim.remove_track(t)
					continue
				if bone_sub == "root" and anim.track_get_type(t) == Animation.TYPE_POSITION_3D:
					anim.remove_track(t)
					continue
				anim.track_set_path(t, NodePath(skel_path_str + ":" + bone_sub))
			if cname in ["Idle", "Walk", "Jog_Fwd", "Sprint", "Crouch_Idle", "Jump", "Fixing_Kneeling"]:
				anim.loop_mode = Animation.LOOP_LINEAR
			lib.add_animation(cname, anim)
		_remapped_ual_libs[skel_path_str] = lib

	if not anim_player.has_animation_library(""):
		anim_player.add_animation_library("", lib)
	_index_embedded_clips()


func _resolve_bones() -> void:
	bone_hips = _find_best_bone(["Hips", "pelvis", "5.joint_HipMaster", "4.joint_HipMaster", "12.joint_HipMaster", "Waist", "Body", "Root"])
	bone_spine = _find_best_bone(["Spine", "spine_01", "12.joint_Torso", "10.joint_Torso", "42.joint_Torso", "Torso", "Abdomen"])
	bone_chest = _find_best_bone(["Chest", "UpperChest", "spine_03", "spine_02", "14.joint_Torso2", "11.joint_Torso2", "43.joint_Torso2"])
	bone_neck = _find_best_bone(["Neck", "neck_01"])
	bone_head = _find_best_bone(["Head", "head_01", "head"])

	bone_l_upper_arm = _find_best_bone(["LeftUpperArm", "upperarm_l", "UpperArm.L", "29.joint_LeftArm", "36.joint_LeftArm", "67.!joint_LeftArm", "J_Bip_L_UpperArm"])
	bone_r_upper_arm = _find_best_bone(["RightUpperArm", "upperarm_r", "UpperArm.R", "58.joint_RightArm", "18.joint_RightArm", "134.!joint_RightArm", "J_Bip_R_UpperArm"])

	bone_l_lower_arm = _find_best_bone(["LeftLowerArm", "lowerarm_l", "LowerArm.L", "33.joint_LeftElbow", "41.joint_LeftElbow", "74.joint_LeftElbow", "J_Bip_L_LowerArm"])
	bone_r_lower_arm = _find_best_bone(["RightLowerArm", "lowerarm_r", "LowerArm.R", "62.joint_RightElbow", "23.joint_RightElbow", "141.joint_RightElbow", "J_Bip_R_LowerArm"])

	bone_l_hand = _find_best_bone(["LeftHand", "hand_l", "Hand.L", "J_Bip_L_Hand"])
	bone_r_hand = _find_best_bone(["RightHand", "hand_r", "Hand.R", "J_Bip_R_Hand"])

	bone_l_upper_leg = _find_best_bone(["LeftUpperLeg", "thigh_l", "UpperLeg.L", "99.joint_LeftHipD", "70.joint_LeftHipD", "33.joint_LeftHip", "J_Bip_L_UpperLeg"])
	bone_r_upper_leg = _find_best_bone(["RightUpperLeg", "thigh_r", "UpperLeg.R", "103.joint_RightHipD", "66.joint_RightHipD", "38.joint_RightHip", "J_Bip_R_UpperLeg"])

	bone_l_lower_leg = _find_best_bone(["LeftLowerLeg", "calf_l", "LowerLeg.L", "J_Bip_L_LowerLeg"])
	bone_r_lower_leg = _find_best_bone(["RightLowerLeg", "calf_r", "LowerLeg.R", "J_Bip_R_LowerLeg"])

	bone_l_foot = _find_best_bone(["LeftFoot", "foot_l", "Foot.L", "101.joint_LeftFootD", "72.joint_LeftFootD", "35.joint_LeftFoot", "J_Bip_L_Foot"])
	bone_r_foot = _find_best_bone(["RightFoot", "foot_r", "Foot.R", "105.joint_RightFootD", "68.joint_RightFootD", "40.joint_RightFoot", "J_Bip_R_Foot"])

	var tracked: Array[int] = [
		bone_spine, bone_chest, bone_head,
		bone_l_upper_arm, bone_r_upper_arm, bone_l_lower_arm, bone_r_lower_arm,
		bone_l_upper_leg, bone_r_upper_leg, bone_l_lower_leg, bone_r_lower_leg,
	]
	if skeleton:
		for b in tracked:
			if b != -1:
				_local_rest_q[b] = skeleton.get_bone_rest(b).basis.get_rotation_quaternion().normalized()
				_global_rest_q[b] = skeleton.get_bone_global_rest(b).basis.get_rotation_quaternion().normalized()


func _compute_rest_pose_calibration() -> void:
	if not skeleton:
		return
	_skel_fwd_z = -1.0
	if bone_l_upper_arm != -1 and bone_l_lower_arm != -1:
		var v_l_rest: Vector3 = (skeleton.get_bone_global_rest(bone_l_lower_arm).origin - skeleton.get_bone_global_rest(bone_l_upper_arm).origin).normalized()
		if v_l_rest.length_squared() > 0.01:
			# Right-handed +Y up: Left arm points -X when facing -Z, and +X when facing +Z
			_skel_fwd_z = 1.0 if v_l_rest.x > 0.0 else -1.0
			var v_l_down: Vector3 = Vector3(signf(v_l_rest.x) * 0.14, -0.99, _skel_fwd_z * 0.03).normalized()
			_q_l_arm_down_skel = Quaternion(v_l_rest, v_l_down)
			_l_elbow_axis_rest = (_q_l_arm_down_skel.inverse() * Vector3(1.0, 0.0, 0.0)).normalized()

	if bone_r_upper_arm != -1 and bone_r_lower_arm != -1:
		var v_r_rest: Vector3 = (skeleton.get_bone_global_rest(bone_r_lower_arm).origin - skeleton.get_bone_global_rest(bone_r_upper_arm).origin).normalized()
		if v_r_rest.length_squared() > 0.01:
			var v_r_down: Vector3 = Vector3(signf(v_r_rest.x) * 0.14, -0.99, _skel_fwd_z * 0.03).normalized()
			_q_r_arm_down_skel = Quaternion(v_r_rest, v_r_down)
			_r_elbow_axis_rest = (_q_r_arm_down_skel.inverse() * Vector3(1.0, 0.0, 0.0)).normalized()


func _find_best_bone(candidate_names: Array) -> int:
	if not skeleton:
		return -1
	for cand in candidate_names:
		var idx: int = skeleton.find_bone(cand)
		if idx != -1:
			return idx
	for b in range(skeleton.get_bone_count()):
		var bname: String = skeleton.get_bone_name(b).to_lower()
		for cand in candidate_names:
			if String(cand).to_lower() in bname:
				return b
	return -1


func _apply_skel_space_delta(bone_idx: int, q_skel_delta: Quaternion) -> void:
	if bone_idx == -1 or not skeleton:
		return
	var q_loc: Quaternion = _local_rest_q.get(bone_idx, Quaternion.IDENTITY)
	var q_glb: Quaternion = _global_rest_q.get(bone_idx, Quaternion.IDENTITY)
	var pose_q: Quaternion = q_loc * (q_glb.inverse() * q_skel_delta * q_glb)
	skeleton.set_bone_pose_rotation(bone_idx, pose_q.normalized())


func set_state(new_state: AnimState) -> void:
	current_state = new_state


func set_velocity(vel: Vector3) -> void:
	move_velocity = vel


func _process(delta: float) -> void:
	step(delta)


func step(delta: float) -> void:
	if not skeleton:
		return
	if has_clips and anim_player:
		_play_clip_state()
		return
	_apply_procedural_pose(delta)


func _play_clip_state() -> void:
	if not anim_player:
		return
	var clip_name: StringName = _clip_map.get(current_state, _clip_map.get(AnimState.IDLE, &""))
	if clip_name != &"" and anim_player.has_animation(clip_name):
		if anim_player.current_animation != clip_name or not anim_player.is_playing():
			anim_player.play(clip_name, 0.2)
		anim_player.speed_scale = anim_speed


func _apply_procedural_pose(delta: float) -> void:
	var freq: float = 1.6
	if current_state == AnimState.RUN:
		freq = 10.5
	elif current_state == AnimState.WALK:
		freq = 6.5
	elif current_state in [AnimState.IDLE, AnimState.DIVINE_HOVER, AnimState.PRAY]:
		freq = 1.8

	_phase += delta * freq * anim_speed

	# Target rotations in Skeleton3D space
	var tgt_l_arm: Quaternion = _q_l_arm_down_skel
	var tgt_r_arm: Quaternion = _q_r_arm_down_skel
	var tgt_l_forearm: Quaternion = Quaternion.IDENTITY
	var tgt_r_forearm: Quaternion = Quaternion.IDENTITY
	var tgt_l_thigh: Quaternion = Quaternion.IDENTITY
	var tgt_r_thigh: Quaternion = Quaternion.IDENTITY
	var tgt_l_knee: Quaternion = Quaternion.IDENTITY
	var tgt_r_knee: Quaternion = Quaternion.IDENTITY
	var tgt_spine: Quaternion = Quaternion.IDENTITY
	var tgt_chest: Quaternion = Quaternion.IDENTITY
	var tgt_head: Quaternion = Quaternion.IDENTITY

	# Sagittal pitch sign: rotating downward -Y by (-_skel_fwd_z * theta) around +X swings FORWARD (+_skel_fwd_z)
	var fwd_pitch_sign: float = -_skel_fwd_z
	var breath: float = sin(_phase) * 0.025
	var sway: float = cos(_phase * 0.7) * 0.02

	match current_state:
		AnimState.IDLE, AnimState.DIVINE_HOVER:
			# Arms rest naturally downward alongside torso (dir.y ~ -0.99, |dir.z| ~ 0.03 -> zero zombie pose)
			var arm_breath: float = sin(_phase) * 0.02
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * arm_breath) * _q_l_arm_down_skel
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * arm_breath) * _q_r_arm_down_skel
			tgt_l_forearm = Quaternion(_l_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(10.0))
			tgt_r_forearm = Quaternion(_r_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(10.0))
			tgt_chest = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * breath)
			tgt_head = Quaternion(Vector3(0, 1, 0), sway)

		AnimState.PRAY:
			# Calm standing posture with softly bowed head and relaxed slightly-bent elbows
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(12.0)) * _q_l_arm_down_skel
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(12.0)) * _q_r_arm_down_skel
			tgt_l_forearm = Quaternion(_l_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(28.0))
			tgt_r_forearm = Quaternion(_r_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(28.0))
			tgt_head = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(10.0))

		AnimState.WALK, AnimState.RUN:
			var stride_amp: float = 0.42 if current_state == AnimState.WALK else 0.68
			var arm_amp: float = 0.28 if current_state == AnimState.WALK else 0.48
			var stride: float = sin(_phase)

			# Opposite-phase leg & arm swing in sagittal plane
			tgt_l_thigh = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * stride * stride_amp)
			tgt_r_thigh = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * (-stride) * stride_amp)

			# Knee bends backward (-fwd_pitch_sign) on trailing leg
			var l_knee_bend: float = maxf(0.0, -stride) * 0.58
			var r_knee_bend: float = maxf(0.0, stride) * 0.58
			tgt_l_knee = Quaternion(Vector3(1, 0, 0), -fwd_pitch_sign * l_knee_bend)
			tgt_r_knee = Quaternion(Vector3(1, 0, 0), -fwd_pitch_sign * r_knee_bend)

			tgt_l_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * (-stride) * arm_amp) * _q_l_arm_down_skel
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * stride * arm_amp) * _q_r_arm_down_skel
			tgt_l_forearm = Quaternion(_l_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(16.0))
			tgt_r_forearm = Quaternion(_r_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(16.0))
			tgt_spine = Quaternion(Vector3(0, 1, 0), stride * 0.04)
			tgt_chest = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(4.0))

		AnimState.CROUCH:
			tgt_spine = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(18.0))
			tgt_l_thigh = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(42.0))
			tgt_r_thigh = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(42.0))
			tgt_l_knee = Quaternion(Vector3(1, 0, 0), -fwd_pitch_sign * deg_to_rad(65.0))
			tgt_r_knee = Quaternion(Vector3(1, 0, 0), -fwd_pitch_sign * deg_to_rad(65.0))
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(12.0)) * _q_l_arm_down_skel
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(12.0)) * _q_r_arm_down_skel
			tgt_l_forearm = Quaternion(_l_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(25.0))
			tgt_r_forearm = Quaternion(_r_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(25.0))

		AnimState.JUMP, AnimState.FLY:
			tgt_l_thigh = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(12.0))
			tgt_r_thigh = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(4.0))
			tgt_l_knee = Quaternion(Vector3(1, 0, 0), -fwd_pitch_sign * deg_to_rad(26.0))
			tgt_r_knee = Quaternion(Vector3(1, 0, 0), -fwd_pitch_sign * deg_to_rad(18.0))
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(8.0)) * _q_l_arm_down_skel
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(8.0)) * _q_r_arm_down_skel
			tgt_l_forearm = Quaternion(_l_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(18.0))
			tgt_r_forearm = Quaternion(_r_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(18.0))
			tgt_spine = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(6.0))

		AnimState.CRY:
			var shake: float = sin(_phase * 12.0) * 0.03
			tgt_head = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(20.0))
			tgt_chest = Quaternion(Vector3(0, 1, 0), shake)
			tgt_l_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(22.0)) * _q_l_arm_down_skel
			tgt_r_arm = Quaternion(Vector3(1, 0, 0), fwd_pitch_sign * deg_to_rad(22.0)) * _q_r_arm_down_skel
			tgt_l_forearm = Quaternion(_l_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(48.0))
			tgt_r_forearm = Quaternion(_r_elbow_axis_rest, fwd_pitch_sign * deg_to_rad(48.0))

	var blend_rate: float = clampf(delta * 10.0, 0.0, 1.0)
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

	_apply_skel_space_delta(bone_l_upper_arm, _cur_l_arm)
	_apply_skel_space_delta(bone_r_upper_arm, _cur_r_arm)
	_apply_skel_space_delta(bone_l_lower_arm, _cur_l_forearm)
	_apply_skel_space_delta(bone_r_lower_arm, _cur_r_forearm)
	_apply_skel_space_delta(bone_l_upper_leg, _cur_l_thigh)
	_apply_skel_space_delta(bone_r_upper_leg, _cur_r_thigh)
	_apply_skel_space_delta(bone_l_lower_leg, _cur_l_knee)
	_apply_skel_space_delta(bone_r_lower_leg, _cur_r_knee)
	_apply_skel_space_delta(bone_spine, _cur_spine)
	_apply_skel_space_delta(bone_chest, _cur_chest)
	_apply_skel_space_delta(bone_head, _cur_head)


func _find_skeleton(node: Node) -> Skeleton3D:
	if node is Skeleton3D:
		return node as Skeleton3D
	for c in node.get_children():
		var found := _find_skeleton(c)
		if found:
			return found
	return null


func _find_anim_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for c in node.get_children():
		var found := _find_anim_player(c)
		if found:
			return found
	return null
