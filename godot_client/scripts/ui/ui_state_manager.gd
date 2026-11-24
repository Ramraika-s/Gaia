# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ui/ui_state_manager.gd
# Centralized modal, input focus, and cursor state manager.
# Enforces mutual exclusion among blocking modals, tracks text input focus,
# gates gameplay input, and acts as the single authoritative owner of Input.mouse_mode.

class_name UiStateManager
extends Node

signal blocking_state_changed(is_blocked: bool)

static var instance: UiStateManager = null

var blocking_modals: Array[CanvasLayer] = []
var non_blocking_inspectors: Array[CanvasLayer] = []

var _was_gameplay_blocked: bool = false
var _is_switching_modals: bool = false
var _is_avatar_mode: bool = true
var target_mouse_mode: Input.MouseMode = Input.MOUSE_MODE_VISIBLE


func _init() -> void:
	instance = self


func _enter_tree() -> void:
	instance = self


func _exit_tree() -> void:
	if instance == self:
		instance = null


static func get_instance() -> UiStateManager:
	return instance


static func is_input_blocked() -> bool:
	if instance != null and is_instance_valid(instance):
		return instance.is_gameplay_input_blocked()
	return false


static func is_gameplay_blocked() -> bool:
	return is_input_blocked()


func _process(_delta: float) -> void:
	var currently_blocked: bool = is_gameplay_input_blocked()
	if currently_blocked != _was_gameplay_blocked:
		_was_gameplay_blocked = currently_blocked
		blocking_state_changed.emit(currently_blocked)
		_apply_cursor_mode()


func register_blocking_modal(modal: CanvasLayer) -> void:
	if modal == null or blocking_modals.has(modal):
		return
	blocking_modals.append(modal)

	for sig_name in ["modal_opened", "dialogue_opened", "console_opened"]:
		if modal.has_signal(sig_name) and not modal.is_connected(sig_name, Callable(self, "_on_modal_opened")):
			modal.connect(sig_name, Callable(self, "_on_modal_opened").bind(modal))

	for sig_name in ["modal_closed", "dialogue_closed", "console_closed"]:
		if modal.has_signal(sig_name) and not modal.is_connected(sig_name, Callable(self, "_on_modal_closed")):
			modal.connect(sig_name, Callable(self, "_on_modal_closed").bind(modal))


func register_non_blocking_inspector(inspector: CanvasLayer) -> void:
	if inspector == null or non_blocking_inspectors.has(inspector):
		return
	non_blocking_inspectors.append(inspector)


func _on_modal_opened(modal: CanvasLayer) -> void:
	notify_modal_opened(modal)


func _on_modal_closed(modal: CanvasLayer) -> void:
	notify_modal_closed(modal)


func notify_modal_opened(modal: CanvasLayer) -> void:
	if _is_switching_modals:
		return
	_is_switching_modals = true

	# Cleanly close all other active blocking modals
	for m in blocking_modals:
		if m != modal and is_modal_active(m):
			_close_modal_instance(m)

	_is_switching_modals = false

	var blocked: bool = is_gameplay_input_blocked()
	if blocked != _was_gameplay_blocked:
		_was_gameplay_blocked = blocked
		blocking_state_changed.emit(blocked)
	_apply_cursor_mode()


func notify_modal_closed(_modal: CanvasLayer) -> void:
	if _is_switching_modals:
		return
	var blocked: bool = is_gameplay_input_blocked()
	if blocked != _was_gameplay_blocked:
		_was_gameplay_blocked = blocked
		blocking_state_changed.emit(blocked)
	_apply_cursor_mode()


func is_modal_active(modal: CanvasLayer) -> bool:
	if modal == null or not is_instance_valid(modal):
		return false
	if modal.has_method("is_modal_open"):
		return modal.is_modal_open()
	if "is_dialogue_open" in modal:
		return modal.is_dialogue_open
	return modal.visible


func _close_modal_instance(m: CanvasLayer) -> void:
	if m == null or not is_instance_valid(m):
		return
	if m.has_method("close_modal"):
		m.close_modal()
	elif m.has_method("close_dialogue"):
		m.close_dialogue()
	elif m.has_method("close_console"):
		m.close_console()
	elif m.has_method("close"):
		m.close()
	else:
		m.visible = false


func is_blocking_modal_open() -> bool:
	for m in blocking_modals:
		if is_modal_active(m):
			return true
	return false


func is_inspector_open() -> bool:
	for insp in non_blocking_inspectors:
		if insp != null and is_instance_valid(insp) and insp.visible:
			return true
	return false


func is_text_input_focused() -> bool:
	var vp: Viewport = get_viewport()
	if not vp:
		return false
	var focus_owner: Control = vp.gui_get_focus_owner()
	if not focus_owner or not focus_owner.is_visible_in_tree():
		return false
	return focus_owner is LineEdit or focus_owner is TextEdit or focus_owner is CodeEdit


func is_gameplay_input_blocked() -> bool:
	return is_blocking_modal_open() or is_text_input_focused()


func request_cursor_mode_refresh(is_avatar_mode: bool = true) -> void:
	_is_avatar_mode = is_avatar_mode
	_apply_cursor_mode()


func get_target_mouse_mode() -> Input.MouseMode:
	return target_mouse_mode


func _apply_cursor_mode() -> void:
	var should_show_cursor: bool = (
		is_blocking_modal_open()
		or is_inspector_open()
		or is_text_input_focused()
		or not _is_avatar_mode
		or Input.is_key_pressed(KEY_ALT)
	)
	if should_show_cursor:
		target_mouse_mode = Input.MOUSE_MODE_VISIBLE
		if Input.mouse_mode != Input.MOUSE_MODE_VISIBLE:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	else:
		target_mouse_mode = Input.MOUSE_MODE_CAPTURED
		if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

