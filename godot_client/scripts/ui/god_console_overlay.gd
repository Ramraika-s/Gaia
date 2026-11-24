# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ui/god_console_overlay.gd
# In-Game God Console Overlay: executes any Gaia CLI command over WebSocket.
# Toggleable with backtick (`) or F1, with command history and styled outputs.

extends CanvasLayer

signal console_opened
signal console_closed

@onready var panel: PanelContainer = $Panel
@onready var log_label: RichTextLabel = $Panel/VBox/LogText
@onready var cmd_input: LineEdit = $Panel/VBox/InputHBox/CmdInput
@onready var btn_send: Button = $Panel/VBox/InputHBox/BtnSend
@onready var btn_close: Button = $Panel/VBox/Header/BtnClose

var _history: Array[String] = []
var _history_idx: int = -1


func _ready() -> void:
	visible = false
	_connect_ui_signals()
	_connect_bridge_signals()

	log_label.text = "[color=#ffd24d]✦ GAIA DIVINE ENGINE CONSOLE ✦[/color]\nType [color=#55ddff]help[/color], [color=#55ddff]status[/color], [color=#55ddff]pop[/color], [color=#55ddff]speed 20x[/color], [color=#55ddff]save[/color], or any CLI command.\n"


func _connect_ui_signals() -> void:
	btn_send.pressed.connect(_on_submit_command)
	btn_close.pressed.connect(close_console)
	cmd_input.text_submitted.connect(func(_t): _on_submit_command())


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.god_command_result_received.connect(_on_command_result_received)


func is_modal_open() -> bool:
	return visible


func _input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return

	var key_ev: InputEventKey = event as InputEventKey
	var is_backtick: bool = (
		key_ev.keycode == KEY_QUOTELEFT
		or key_ev.physical_keycode == KEY_QUOTELEFT
		or key_ev.unicode == 96
	)
	var is_f1: bool = (key_ev.keycode == KEY_F1 or key_ev.physical_keycode == KEY_F1)
	if is_backtick or is_f1:
		if not visible and UiStateManager.instance:
			if UiStateManager.instance.is_blocking_modal_open() or UiStateManager.instance.is_text_input_focused():
				return
		toggle_console()
		get_viewport().set_input_as_handled()
	elif visible:
		var is_esc: bool = (key_ev.keycode == KEY_ESCAPE or key_ev.physical_keycode == KEY_ESCAPE)
		var is_up: bool = (key_ev.keycode == KEY_UP or key_ev.physical_keycode == KEY_UP)
		var is_down: bool = (key_ev.keycode == KEY_DOWN or key_ev.physical_keycode == KEY_DOWN)
		if is_esc:
			close_console()
			get_viewport().set_input_as_handled()
		elif is_up:
			_navigate_history(-1)
			get_viewport().set_input_as_handled()
		elif is_down:
			_navigate_history(1)
			get_viewport().set_input_as_handled()


func open_console() -> void:
	visible = true
	console_opened.emit()
	cmd_input.grab_focus()


func close_console() -> void:
	visible = false
	console_closed.emit()
	cmd_input.release_focus()


func close_modal() -> void:
	close_console()


func open_modal(_tab_idx: int = 0) -> void:
	open_console()


func toggle_console() -> void:
	if visible:
		close_console()
	else:
		open_console()


func _on_submit_command() -> void:
	var raw: String = cmd_input.text.strip_edges()
	if raw == "":
		return

	_history.append(raw)
	_history_idx = _history.size()
	cmd_input.text = ""

	log_label.append_text("\n[color=#77ee77]> %s[/color]\n" % raw)

	if raw == "clear" or raw == "cls":
		log_label.text = ""
		return

	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.is_bridge_connected():
		bridge.send_god_raw_command(raw)
	else:
		_execute_local_fallback(raw)


func _execute_local_fallback(cmd: String) -> void:
	var lower: String = cmd.to_lower()
	if lower == "help":
		log_label.append_text("[color=#aaaaaa]Available commands (Local & Live): status, pop, speed [Nx], pause, resume, name_deity, bless, curse, smite, save, clear[/color]\n")
	elif lower == "status":
		log_label.append_text("[color=#66ccff]Local Status: Godot 4.7.2 Forward+ MSAA 2x | Reality Bubble: 100 pooled mortals | MultiMesh: 10k capacity[/color]\n")
	else:
		log_label.append_text("[color=#ffaa55][Offline Mode] Command logged locally. Connect to Python bridge for full simulation execution.[/color]\n")


func _on_command_result_received(data: Dictionary) -> void:
	var output: String = data.get("output", "")
	if output == "":
		var details: Dictionary = data.get("details", {})
		if not details.is_empty():
			output = JSON.stringify(details, "  ")
		else:
			output = "Command executed: " + data.get("status", "SUCCESS")

	log_label.append_text("[color=#dddddd]%s[/color]\n" % output)


func _navigate_history(delta_idx: int) -> void:
	if _history.is_empty():
		return

	_history_idx = clampi(_history_idx + delta_idx, 0, _history.size() - 1)
	cmd_input.text = _history[_history_idx]
	cmd_input.caret_column = cmd_input.text.length()
