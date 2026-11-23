# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ui/divine_hud.gd
# In-Godot Divine Family HUD, live clock, speed controls, population breakdown,
# and real-time 5-Sister Council feed with Codex approval buttons.

extends CanvasLayer

signal open_two_book_modal_requested
signal toggle_console_requested

@onready var day_label: Label = $TopBar/HBox/DayLabel
@onready var ws_badge: Label = $TopBar/HBox/WsBadge
@onready var cpi_label: Label = $TopBar/HBox/CpiLabel
@onready var pop_human: Label = $TopBar/HBox/PopHuman
@onready var pop_elf: Label = $TopBar/HBox/PopElf
@onready var pop_dragon: Label = $TopBar/HBox/PopDragon
@onready var pop_beast: Label = $TopBar/HBox/PopBeast
@onready var pop_demon: Label = $TopBar/HBox/PopDemon

@onready var btn_pause: Button = $TopBar/HBox/SpeedGroup/BtnPause
@onready var btn_1x: Button = $TopBar/HBox/SpeedGroup/Btn1x
@onready var btn_5x: Button = $TopBar/HBox/SpeedGroup/Btn5x
@onready var btn_20x: Button = $TopBar/HBox/SpeedGroup/Btn20x
@onready var btn_60x: Button = $TopBar/HBox/SpeedGroup/Btn60x

@onready var council_drawer: PanelContainer = $CouncilDrawer
@onready var message_container: VBoxContainer = $CouncilDrawer/VBox/Scroll/MessageContainer
@onready var btn_toggle_feed: Button = $TopBar/HBox/BtnToggleFeed

var _current_speed: float = 1.0
var _is_paused: bool = false
var _speed_buttons: Array[Button] = []


func _ready() -> void:
	_speed_buttons = [btn_pause, btn_1x, btn_5x, btn_20x, btn_60x]
	_connect_ui_signals()
	_connect_bridge_signals()
	_update_speed_button_states()


func _connect_ui_signals() -> void:
	btn_pause.pressed.connect(func(): _set_speed(0.0))
	btn_1x.pressed.connect(func(): _set_speed(1.0))
	btn_5x.pressed.connect(func(): _set_speed(5.0))
	btn_20x.pressed.connect(func(): _set_speed(20.0))
	btn_60x.pressed.connect(func(): _set_speed(60.0))

	btn_toggle_feed.pressed.connect(_on_toggle_feed_pressed)


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.connected_to_bridge.connect(_on_bridge_connected)
		bridge.disconnected_from_bridge.connect(_on_bridge_disconnected)
		bridge.world_time_weather_received.connect(_on_time_weather_received)
		bridge.divine_hud_message_received.connect(_on_divine_hud_message_received)
		bridge.sign_update_received.connect(_on_sign_update_received)
		bridge.palace_entry_requested.connect(_on_palace_entry_requested)

		if bridge.is_bridge_connected():
			_on_bridge_connected()
		else:
			_on_bridge_disconnected()


func _on_bridge_connected() -> void:
	if ws_badge:
		ws_badge.text = "● LIVE (ws://127.0.0.1:8765)"
		ws_badge.modulate = Color(0.3, 1.0, 0.4, 1.0)


func _on_bridge_disconnected() -> void:
	if ws_badge:
		ws_badge.text = "○ STANDALONE (Local)"
		ws_badge.modulate = Color(1.0, 0.7, 0.2, 1.0)


func _set_speed(speed: float) -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if speed == 0.0:
		_is_paused = true
		if bridge:
			bridge.send_god_command("pause")
	else:
		_is_paused = false
		_current_speed = speed
		if bridge:
			bridge.send_god_command("speed", {"speed": speed})
			bridge.send_god_command("resume")

	_update_speed_button_states()


func _update_speed_button_states() -> void:
	btn_pause.button_pressed = _is_paused
	btn_1x.button_pressed = (not _is_paused and is_equal_approx(_current_speed, 1.0))
	btn_5x.button_pressed = (not _is_paused and is_equal_approx(_current_speed, 5.0))
	btn_20x.button_pressed = (not _is_paused and is_equal_approx(_current_speed, 20.0))
	btn_60x.button_pressed = (not _is_paused and is_equal_approx(_current_speed, 60.0))


func _on_time_weather_received(data: Dictionary) -> void:
	var day: int = int(data.get("day", 1))
	var tod: float = float(data.get("time_of_day", 0.5))
	var season_progress: float = float(data.get("season_progress", 0.0))
	var season_str: String = _get_season_name(season_progress)

	var hours: int = int(tod * 24.0) % 24
	var mins: int = int((tod * 24.0 - hours) * 60.0)
	var time_str: String = "%02d:%02d" % [hours, mins]

	if day_label:
		day_label.text = "Day %d • %s • %s" % [day, season_str, time_str]


func _get_season_name(progress: float) -> String:
	var p: float = fmod(progress, 1.0)
	if p < 0.25:
		return "Spring"
	elif p < 0.50:
		return "Summer"
	elif p < 0.75:
		return "Autumn"
	else:
		return "Winter"


func _on_sign_update_received(data: Dictionary) -> void:
	if data.has("cpi") and cpi_label:
		cpi_label.text = "CPI: %.3f" % float(data.get("cpi", 1.0))


func update_population_counts(h: int, e: int, d: int, b: int, dem: int) -> void:
	if pop_human: pop_human.text = "HUM: %d" % h
	if pop_elf: pop_elf.text = "ELF: %d" % e
	if pop_dragon: pop_dragon.text = "DRG: %d" % d
	if pop_beast: pop_beast.text = "BST: %d" % b
	if pop_demon: pop_demon.text = "DEM: %d" % dem


func _on_toggle_feed_pressed() -> void:
	council_drawer.visible = not council_drawer.visible
	btn_toggle_feed.text = "Council Feed ▲" if council_drawer.visible else "Council Feed ▼"


func _on_divine_hud_message_received(data: Dictionary) -> void:
	add_feed_message(data)


func add_feed_message(data: Dictionary) -> void:
	if message_container == null:
		return

	var speaker: String = data.get("speaker", data.get("speaker_name", "Divine Voice"))
	var text: String = data.get("message", data.get("text", ""))
	var category: String = data.get("category", "COUNCIL")
	var proposal_id: String = data.get("proposal_id", "")

	var item: PanelContainer = PanelContainer.new()
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.12, 0.14, 0.22, 0.92)
	style.set_corner_radius_all(6)
	style.content_margin_left = 8
	style.content_margin_top = 6
	style.content_margin_right = 8
	style.content_margin_bottom = 6
	item.add_theme_stylebox_override("panel", style)

	var vbox: VBoxContainer = VBoxContainer.new()
	item.add_child(vbox)

	var title_lbl: Label = Label.new()
	title_lbl.text = "✦ %s [%s]" % [speaker, category]
	title_lbl.modulate = Color(1.0, 0.88, 0.45, 1.0)
	vbox.add_child(title_lbl)

	var body_lbl: Label = Label.new()
	body_lbl.text = text
	body_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(body_lbl)

	# If pending proposal, add interactive one-click decision buttons
	if proposal_id != "":
		var hbox_btn: HBoxContainer = HBoxContainer.new()
		vbox.add_child(hbox_btn)

		var btn_app: Button = Button.new()
		btn_app.text = "✔ Approve & Apply"
		btn_app.modulate = Color(0.4, 1.0, 0.5, 1.0)
		btn_app.pressed.connect(func():
			var bridge: Node = get_node_or_null("/root/WsBridgeClient")
			if bridge:
				bridge.send_god_codex_approve(proposal_id)
			btn_app.disabled = true
			btn_app.text = "Approved"
		)
		hbox_btn.add_child(btn_app)

		var btn_rej: Button = Button.new()
		btn_rej.text = "✖ Reject"
		btn_rej.modulate = Color(1.0, 0.4, 0.4, 1.0)
		btn_rej.pressed.connect(func():
			var bridge: Node = get_node_or_null("/root/WsBridgeClient")
			if bridge:
				bridge.send_god_codex_reject(proposal_id)
			btn_rej.disabled = true
			btn_rej.text = "Rejected"
		)
		hbox_btn.add_child(btn_rej)

	# Keep feed to max 25 items
	message_container.add_child(item)
	while message_container.get_child_count() > 25:
		var oldest: Node = message_container.get_child(0)
		message_container.remove_child(oldest)
		oldest.queue_free()


func _on_palace_entry_requested(data: Dictionary) -> void:
	if message_container == null:
		return

	var req_id: String = data.get("request_id", "")
	var agent_name: String = data.get("name", "Unknown Mortal")
	var race_name: String = data.get("race", "HUMAN")
	var title_str: String = data.get("title", "Citizen")
	var crimes: int = int(data.get("criminal_count", 0))
	var devotion: float = float(data.get("faith_devotion", 0.5))
	var reason: String = data.get("reason", "Petitioning Audience")

	var item: PanelContainer = PanelContainer.new()
	var style: StyleBoxFlat = StyleBoxFlat.new()
	style.bg_color = Color(0.18, 0.08, 0.12, 0.95)
	style.border_color = Color(1.0, 0.45, 0.2, 1.0)
	style.set_border_width_all(2)
	style.set_corner_radius_all(6)
	style.content_margin_left = 10
	style.content_margin_top = 8
	style.content_margin_right = 10
	style.content_margin_bottom = 8
	item.add_theme_stylebox_override("panel", style)

	var vbox: VBoxContainer = VBoxContainer.new()
	item.add_child(vbox)

	var header: Label = Label.new()
	header.text = "🐉 TWIN DRAGON GATE: PALACE ENTRY PETITION"
	header.modulate = Color(1.0, 0.75, 0.3, 1.0)
	vbox.add_child(header)

	var info: Label = Label.new()
	info.text = "Petitioner: %s [%s • %s]\nDevotion: %.2f | Prior Crimes: %d\nReason: %s" % [
		agent_name, race_name, title_str, devotion, crimes, reason
	]
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(info)

	var hbox: HBoxContainer = HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 8)
	vbox.add_child(hbox)

	var btn_grant: Button = Button.new()
	btn_grant.text = "✔ Grant Entry"
	btn_grant.modulate = Color(0.3, 1.0, 0.5, 1.0)
	btn_grant.pressed.connect(func():
		var bridge: Node = get_node_or_null("/root/WsBridgeClient")
		if bridge and bridge.has_method("send_palace_decision"):
			bridge.send_palace_decision(req_id, "GRANT")
		btn_grant.disabled = true
		btn_grant.text = "Granted"
		for c in hbox.get_children():
			if c != btn_grant and c is Button:
				c.disabled = true
	)
	hbox.add_child(btn_grant)

	var btn_deny: Button = Button.new()
	btn_deny.text = "✖ Deny"
	btn_deny.modulate = Color(1.0, 0.4, 0.4, 1.0)
	btn_deny.pressed.connect(func():
		var bridge: Node = get_node_or_null("/root/WsBridgeClient")
		if bridge and bridge.has_method("send_palace_decision"):
			bridge.send_palace_decision(req_id, "DENY")
		btn_deny.disabled = true
		btn_deny.text = "Denied"
		for c in hbox.get_children():
			if c != btn_deny and c is Button:
				c.disabled = true
	)
	hbox.add_child(btn_deny)

	var btn_escort: Button = Button.new()
	btn_escort.text = "⚔ Escort Out"
	btn_escort.modulate = Color(1.0, 0.8, 0.2, 1.0)
	btn_escort.pressed.connect(func():
		var bridge: Node = get_node_or_null("/root/WsBridgeClient")
		if bridge and bridge.has_method("send_palace_decision"):
			bridge.send_palace_decision(req_id, "ESCORT")
		btn_escort.disabled = true
		btn_escort.text = "Escorted"
		for c in hbox.get_children():
			if c != btn_escort and c is Button:
				c.disabled = true
	)
	hbox.add_child(btn_escort)

	# Insert at top of feed
	message_container.add_child(item)
	message_container.move_child(item, 0)
	if council_drawer and not council_drawer.visible:
		council_drawer.visible = true

