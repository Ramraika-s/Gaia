# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/dragon_morph_controller.gd
# Zero-stutter Dragon metamorphosis controller (< 0.1 ms form swap).
# Toggles HUMANOID_DRAGON <-> TRUE_DRAGON, fires particle bursts, and controls 40m fear aura ring.

extends Node3D

signal form_changed(new_form: String)

const FORM_HUMANOID: String = "HUMANOID_DRAGON"
const FORM_TRUE_DRAGON: String = "TRUE_DRAGON"
const TRUE_DRAGON_SCALE: Vector3 = Vector3(3.8, 3.8, 3.8)

@export var humanoid_node: Node3D = null
@export var true_dragon_node: Node3D = null
@export var burst_particles: GPUParticles3D = null
@export var fear_aura_ring: Node3D = null

var current_form: String = FORM_HUMANOID
var is_dragon_race: bool = false


func _ready() -> void:
	_apply_form(current_form, true)


func set_is_dragon(is_dragon: bool) -> void:
	is_dragon_race = is_dragon
	if not is_dragon_race:
		if true_dragon_node:
			true_dragon_node.visible = false
		if fear_aura_ring:
			fear_aura_ring.visible = false
		current_form = FORM_HUMANOID


func set_form(new_form: String, trigger_vfx: bool = true) -> void:
	if not is_dragon_race:
		return

	var target_form: String = FORM_TRUE_DRAGON if new_form == FORM_TRUE_DRAGON else FORM_HUMANOID
	if target_form == current_form:
		return

	current_form = target_form
	_apply_form(current_form, false, trigger_vfx)
	form_changed.emit(current_form)


func _apply_form(form: String, initial_setup: bool = false, trigger_vfx: bool = true) -> void:
	var is_true: bool = (form == FORM_TRUE_DRAGON)

	if trigger_vfx and not initial_setup and burst_particles:
		burst_particles.restart()
		burst_particles.emitting = true

	if humanoid_node:
		humanoid_node.visible = not is_true

	if true_dragon_node:
		true_dragon_node.visible = is_true
		if is_true:
			true_dragon_node.scale = TRUE_DRAGON_SCALE

	if fear_aura_ring:
		fear_aura_ring.visible = is_true


func is_true_dragon() -> bool:
	return is_dragon_race and current_form == FORM_TRUE_DRAGON
