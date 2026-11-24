# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/palace_dragon_guardian.gd
# Controls the Twin Guardian Dragons in the Grand Divine Palace.
# Animates continuous looping flight/idle clips at staggered phases and pulses brazier alerts.

extends Node3D

class_name PalaceDragonGuardian

@onready var dragon_left: Node3D = $DragonLeft
@onready var dragon_right: Node3D = $DragonRight

var _anim_left: AnimationPlayer = null
var _anim_right: AnimationPlayer = null
var _brazier_left_light: OmniLight3D = null
var _brazier_right_light: OmniLight3D = null
var _pulse_timer: float = 0.0


func _ready() -> void:
	_setup_dragon_animations()
	_setup_braziers()
	Callable(self, "_setup_braziers").call_deferred()
	_connect_bridge()


func _setup_dragon_animations() -> void:
	if dragon_left:
		_anim_left = _find_anim_player(dragon_left)
		_play_looping_clip(_anim_left, 0.0)

	if dragon_right:
		_anim_right = _find_anim_player(dragon_right)
		_play_looping_clip(_anim_right, 0.75)


func _find_anim_player(node: Node) -> AnimationPlayer:
	if node is AnimationPlayer:
		return node as AnimationPlayer
	for child in node.get_children():
		var found = _find_anim_player(child)
		if found:
			return found
	return null


func _play_looping_clip(player: AnimationPlayer, offset_sec: float) -> void:
	if not player:
		return

	var clip_to_play: String = ""
	var anim_list: PackedStringArray = player.get_animation_list()
	for anim_name in anim_list:
		if "flight" in anim_name.to_lower() or "idle" in anim_name.to_lower() or "wing" in anim_name.to_lower():
			clip_to_play = anim_name
			break

	if clip_to_play == "" and anim_list.size() > 0:
		clip_to_play = anim_list[0]

	if clip_to_play != "":
		var anim: Animation = player.get_animation(clip_to_play)
		if anim:
			anim.loop_mode = Animation.LOOP_LINEAR
		player.play(clip_to_play)
		if offset_sec > 0.0 and player.current_animation_length > 0.0:
			player.seek(fmod(offset_sec, player.current_animation_length), true)


func _setup_braziers() -> void:
	var brazier_l = get_node_or_null("../CourtyardDecor/BrazierLeft")
	if brazier_l:
		_brazier_left_light = _find_omni_light(brazier_l)

	var brazier_r = get_node_or_null("../CourtyardDecor/BrazierRight")
	if brazier_r:
		_brazier_right_light = _find_omni_light(brazier_r)


func _find_omni_light(node: Node) -> OmniLight3D:
	if node is OmniLight3D:
		return node as OmniLight3D
	for child in node.get_children():
		var found = _find_omni_light(child)
		if found:
			return found
	return null


func _connect_bridge() -> void:
	var bridge = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.has_signal("palace_entry_requested"):
		bridge.connect("palace_entry_requested", Callable(self, "_on_palace_entry_requested"))


func _on_palace_entry_requested(_payload: Dictionary = {}) -> void:
	pulse_alert()


func pulse_alert() -> void:
	if not _brazier_left_light or not _brazier_right_light:
		_setup_braziers()
	_pulse_timer = 1.5


func _process(delta: float) -> void:
	if not _brazier_left_light or not _brazier_right_light:
		_setup_braziers()
	if _pulse_timer > 0.0:
		_pulse_timer -= delta
		var pulse_glow: float = 3.0 + sin(_pulse_timer * 16.0) * 2.0
		if _brazier_left_light:
			_brazier_left_light.light_energy = pulse_glow
		if _brazier_right_light:
			_brazier_right_light.light_energy = pulse_glow
	else:
		if _brazier_left_light and _brazier_left_light.light_energy > 2.0:
			_brazier_left_light.light_energy = 2.0
		if _brazier_right_light and _brazier_right_light.light_energy > 2.0:
			_brazier_right_light.light_energy = 2.0
