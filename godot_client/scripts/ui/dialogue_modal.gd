# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ui/dialogue_modal.gd
# Interactive [E] Dialogue UI Modal for Deities & Mortals.
# Zero direct SQLite access: all dialogue requests pass through WsBridgeClient over WebSocket.

extends CanvasLayer

signal dialogue_opened
signal dialogue_closed

@onready var prompt_panel: PanelContainer = $PromptPanel
@onready var prompt_label: Label = $PromptPanel/PromptLabel

@onready var dialogue_panel: PanelContainer = $DialoguePanel
@onready var portrait_rect: TextureRect = $DialoguePanel/HBox/LeftCol/Portrait
@onready var name_label: Label = $DialoguePanel/HBox/LeftCol/NameLabel
@onready var title_label: Label = $DialoguePanel/HBox/LeftCol/TitleLabel
@onready var race_mood_label: Label = $DialoguePanel/HBox/LeftCol/RaceMoodLabel

@onready var log_label: RichTextLabel = $DialoguePanel/HBox/RightCol/ChatLog
@onready var input_edit: LineEdit = $DialoguePanel/HBox/RightCol/InputRow/ChatInput
@onready var btn_send: Button = $DialoguePanel/HBox/RightCol/InputRow/BtnSend
@onready var btn_close: Button = $DialoguePanel/HBox/RightCol/InputRow/BtnClose

# Quick action buttons
@onready var btn_world_report: Button = $DialoguePanel/HBox/RightCol/ActionRow/BtnWorldReport
@onready var btn_books_council: Button = $DialoguePanel/HBox/RightCol/ActionRow/BtnBooksCouncil
@onready var btn_follow: Button = $DialoguePanel/HBox/RightCol/ActionRow/BtnFollow
@onready var btn_council: Button = $DialoguePanel/HBox/RightCol/ActionRow/BtnCouncil
@onready var btn_return_palace: Button = $DialoguePanel/HBox/RightCol/ActionRow/BtnReturnPalace

const PORTRAIT_GODDESS: String = "res://assets/ui/portraits/world_goddess_portrait.png"

var current_target_type: String = "DEITY"  # "DEITY" or "MORTAL"
var current_target_id: String = ""
var current_target_name: String = ""
var current_target_title: String = ""
var current_target_race: String = ""
var current_target_mood: String = "calm"
var is_near_target: bool = false
var is_dialogue_open: bool = false


func _ready() -> void:
	prompt_panel.visible = false
	dialogue_panel.visible = false
	_connect_ui_signals()
	_connect_bridge_signals()


func _connect_ui_signals() -> void:
	btn_send.pressed.connect(_on_send_pressed)
	btn_close.pressed.connect(close_dialogue)
	input_edit.text_submitted.connect(func(_txt): _on_send_pressed())

	btn_world_report.pressed.connect(func(): _send_quick_action("Give me a full report on the state of the world.", ""))
	btn_books_council.pressed.connect(func(): _send_quick_action("What is the status of the library books and sister council?", ""))
	btn_follow.pressed.connect(func(): _send_quick_action("Accompany me through the realm.", "FOLLOW_GOD"))
	btn_council.pressed.connect(func(): _send_quick_action("I decree that the 5-Sister Council shall assemble immediately.", "CONVENE_COUNCIL"))
	btn_return_palace.pressed.connect(func(): _send_quick_action("Return to your divine palace seat.", "RETURN_PALACE"))


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		if bridge.has_signal("dialogue_response_received"):
			bridge.connect("dialogue_response_received", Callable(self, "_on_dialogue_response_received"))


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_E:
			if is_near_target and not is_dialogue_open:
				open_dialogue()
				get_viewport().set_input_as_handled()
		elif event.keycode == KEY_ESCAPE:
			if is_dialogue_open:
				close_dialogue()
				get_viewport().set_input_as_handled()


func set_interaction_target(
	target_type: String,
	tid: String,
	tname: String,
	title: String = "",
	race: String = "",
	mood: String = "calm"
) -> void:
	current_target_type = target_type
	current_target_id = tid
	current_target_name = tname
	current_target_title = title
	current_target_race = race
	current_target_mood = mood
	is_near_target = (tid != "")

	if is_near_target and not is_dialogue_open:
		prompt_label.text = "[E] Speak with %s" % tname
		prompt_panel.visible = true
	else:
		prompt_panel.visible = false


func clear_interaction_target() -> void:
	is_near_target = false
	prompt_panel.visible = false


func open_dialogue(
	target_type: String = "",
	tid: String = "",
	tname: String = "",
	title: String = "",
	race: String = "",
	mood: String = "calm"
) -> void:
	if tid != "":
		set_interaction_target(target_type, tid, tname, title, race, mood)
	is_dialogue_open = true
	prompt_panel.visible = false
	dialogue_panel.visible = true

	# Release mouse cursor
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE

	# Update header info
	name_label.text = current_target_name
	title_label.text = current_target_title
	race_mood_label.text = "[%s • %s]" % [current_target_race, current_target_mood.to_upper()]

	# Load portrait if World Goddess
	if current_target_id == "world_goddess":
		if ResourceLoader.exists(PORTRAIT_GODDESS):
			var res = load(PORTRAIT_GODDESS)
			if res is Texture2D:
				portrait_rect.texture = res
		if portrait_rect.texture == null and FileAccess.file_exists(PORTRAIT_GODDESS):
			var img: Image = Image.load_from_file(PORTRAIT_GODDESS)
			if img:
				portrait_rect.texture = ImageTexture.create_from_image(img)
		portrait_rect.visible = (portrait_rect.texture != null)
	else:
		portrait_rect.visible = (portrait_rect.texture != null)

	# Adjust buttons depending on whether target is Deity or Mortal
	var is_deity: bool = (current_target_type == "DEITY")
	btn_world_report.visible = is_deity
	btn_books_council.visible = is_deity
	btn_follow.visible = is_deity
	btn_council.visible = is_deity
	btn_return_palace.visible = is_deity

	# Initial welcome in log
	log_label.clear()
	log_label.append_text("[color=#88ccff]✦ You stand before %s. Press Enter or Send to speak. ✦[/color]\n\n" % current_target_name)
	input_edit.grab_focus()

	dialogue_opened.emit()


func close_dialogue() -> void:
	is_dialogue_open = false
	dialogue_panel.visible = false

	# Re-capture mouse
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED

	if is_near_target:
		prompt_panel.visible = true

	dialogue_closed.emit()


func _on_send_pressed() -> void:
	var text: String = input_edit.text.strip_edges()
	if text == "":
		return
	input_edit.clear()

	# Append God's message
	log_label.append_text("[b][color=#ffd700]God Avatar:[/color][/b] %s\n" % text)

	_dispatch_request(text, "")


func _send_quick_action(message: String, order: String) -> void:
	log_label.append_text("[b][color=#ffd700]God Avatar:[/color][/b] %s\n" % message)
	_dispatch_request(message, order)


func _dispatch_request(message: String, order: String) -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.has_method("send_dialogue_request"):
		bridge.send_dialogue_request(current_target_type, current_target_id, message, order)
	else:
		# Offline local mock response
		call_deferred("_mock_local_response", message, order)


func _mock_local_response(message: String, order: String) -> void:
	var reply: String = "I hear Your divine words, My Lord."
	if order == "CONVENE_COUNCIL":
		reply = "The Great Bell tolls. The 5-Sister Council is convened at the Grand Palace Courtyard!"
	elif order == "FOLLOW_GOD":
		reply = "I follow Your divine steps."
	elif "report" in message.to_lower():
		reply = "The realm is peaceful. All five races prosper under the celestial vault."

	_on_dialogue_response_received({
		"target_name": current_target_name,
		"spoken_reply": reply,
		"action_taken": ("Executed order: " + order) if order != "" else ""
	})


func _on_dialogue_response_received(data: Dictionary) -> void:
	var speaker: String = data.get("target_name", current_target_name)
	var reply: String = data.get("spoken_reply", "")
	var action: String = data.get("action_taken", "")
	var backend: String = data.get("llm_backend", "")

	log_label.append_text("[b][color=#aaccff]%s:[/color][/b] %s\n" % [speaker, reply])
	if action != "":
		log_label.append_text("[color=#ffcc66]<i>✦ %s</i>[/color]\n" % action)
	if backend != "":
		log_label.append_text("[color=#778899][font_size=12]<i>[%s]</i>[/font_size][/color]\n" % backend)
	log_label.append_text("\n")
