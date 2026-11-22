# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ui/two_book_modal.gd
# Two-Book Governance Modal: World Library (scholarship) + Divine Codex (decrees & live parameter overrides).
# Zero direct SQLite access: all reads/writes pass through WsBridgeClient over WebSocket.

extends CanvasLayer

signal modal_opened
signal modal_closed

@onready var modal_panel: PanelContainer = $Center/ModalPanel
@onready var btn_close: Button = $Center/ModalPanel/VBox/Header/BtnClose
@onready var tab_container: TabContainer = $Center/ModalPanel/VBox/TabContainer

# Tab 1: World Library
@onready var lib_item_list: ItemList = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/ListVBox/ItemList
@onready var lib_detail_title: Label = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/DetailVBox/TitleLabel
@onready var lib_detail_author: Label = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/DetailVBox/AuthorLabel
@onready var lib_detail_text: TextEdit = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/DetailVBox/ContentText
@onready var lib_input_topic: LineEdit = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/DetailVBox/EditForm/TopicInput
@onready var lib_input_title: LineEdit = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/DetailVBox/EditForm/TitleInput
@onready var lib_input_content: TextEdit = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/DetailVBox/EditForm/BodyInput
@onready var lib_btn_commit: Button = $Center/ModalPanel/VBox/TabContainer/WorldLibrary/HBox/DetailVBox/EditForm/BtnCommit

# Tab 2: Divine Codex
@onready var codex_item_list: ItemList = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/ListVBox/ItemList
@onready var codex_detail_title: Label = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/TitleLabel
@onready var codex_detail_author: Label = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/AuthorLabel
@onready var codex_detail_text: TextEdit = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/ContentText
@onready var codex_approval_hbox: HBoxContainer = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/ApprovalHBox
@onready var codex_btn_approve: Button = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/ApprovalHBox/BtnApprove
@onready var codex_btn_reject: Button = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/ApprovalHBox/BtnReject
@onready var codex_input_decree_id: LineEdit = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/DecreeForm/DecreeIdInput
@onready var codex_input_param_key: LineEdit = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/DecreeForm/ParamKeyInput
@onready var codex_input_param_val: LineEdit = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/DecreeForm/ParamValInput
@onready var codex_input_decree_text: TextEdit = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/DecreeForm/DecreeBodyInput
@onready var codex_btn_promulgate: Button = $Center/ModalPanel/VBox/TabContainer/DivineCodex/HBox/DetailVBox/DecreeForm/BtnPromulgate

var _library_entries: Array = []
var _library_proposals: Array = []
var _codex_entries: Array = []
var _codex_proposals: Array = []
var _selected_codex_proposal_id: String = ""


func _ready() -> void:
	visible = false
	_connect_ui_signals()
	_connect_bridge_signals()


func _connect_ui_signals() -> void:
	btn_close.pressed.connect(close_modal)

	lib_item_list.item_selected.connect(_on_library_item_selected)
	lib_btn_commit.pressed.connect(_on_library_commit_pressed)

	codex_item_list.item_selected.connect(_on_codex_item_selected)
	codex_btn_approve.pressed.connect(_on_codex_approve_pressed)
	codex_btn_reject.pressed.connect(_on_codex_reject_pressed)
	codex_btn_promulgate.pressed.connect(_on_codex_promulgate_pressed)


func _connect_bridge_signals() -> void:
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.book_state_sync_received.connect(_on_book_state_sync_received)
		bridge.god_library_edit_response_received.connect(_on_library_edit_response)
		bridge.god_codex_approve_response_received.connect(_on_codex_approve_response)
		bridge.god_codex_reject_response_received.connect(_on_codex_reject_response)
		bridge.god_codex_edit_response_received.connect(_on_codex_edit_response)


var is_near_lectern: bool = false


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_L:
			toggle_modal()
		elif event.keycode == KEY_E and is_near_lectern and not visible:
			open_modal(0)
		elif event.keycode == KEY_ESCAPE and visible:
			close_modal()


func set_near_lectern(near: bool) -> void:
	is_near_lectern = near


func open_modal(tab_idx: int = 0) -> void:
	visible = true
	tab_container.current_tab = tab_idx
	modal_opened.emit()

	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge and bridge.is_bridge_connected():
		bridge.request_book_state_sync()
	else:
		_populate_offline_sample_data()


func close_modal() -> void:
	visible = false
	modal_closed.emit()


func toggle_modal() -> void:
	if visible:
		close_modal()
	else:
		open_modal()


func _on_book_state_sync_received(data: Dictionary) -> void:
	_library_entries = data.get("library_entries", [])
	_library_proposals = data.get("library_proposals", [])
	_codex_entries = data.get("codex_entries", [])
	_codex_proposals = data.get("codex_proposals", [])

	_refresh_library_list()
	_refresh_codex_list()


func _refresh_library_list() -> void:
	lib_item_list.clear()

	# Add committed entries
	for e in _library_entries:
		var topic: String = e.get("topic", "UNKNOWN")
		var title: String = e.get("title", "Volume")
		lib_item_list.add_item("📖 [%s] %s" % [topic, title])

	# Add pending proposals
	for p in _library_proposals:
		var status: String = p.get("status", "PENDING")
		var title: String = p.get("title", "Proposal")
		lib_item_list.add_item("⏳ [%s] %s" % [status, title])


func _on_library_item_selected(index: int) -> void:
	if index < _library_entries.size():
		var e: Dictionary = _library_entries[index]
		lib_detail_title.text = e.get("title", "Canonical Volume")
		lib_detail_author.text = "Author: %s (Proficiency: %.2f) • Created Tick: %s" % [
			e.get("author_id", "Unknown"),
			float(e.get("author_proficiency", 1.0)),
			str(e.get("created_tick", 0))
		]
		lib_detail_text.text = e.get("summary", "")
	else:
		var p_idx: int = index - _library_entries.size()
		if p_idx < _library_proposals.size():
			var p: Dictionary = _library_proposals[p_idx]
			lib_detail_title.text = "[PROPOSAL] " + p.get("title", "Proposal")
			lib_detail_author.text = "Author: %s • Status: %s" % [
				p.get("author_id", "Unknown"),
				p.get("status", "PENDING")
			]
			lib_detail_text.text = p.get("summary", "")


func _on_library_commit_pressed() -> void:
	var topic: String = lib_input_topic.text.strip_edges()
	var title: String = lib_input_title.text.strip_edges()
	var body: String = lib_input_content.text.strip_edges()

	if topic == "" or title == "" or body == "":
		return

	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_library_edit(topic, title, body, "GOD")
		lib_input_topic.text = ""
		lib_input_title.text = ""
		lib_input_content.text = ""


func _on_library_edit_response(data: Dictionary) -> void:
	print("[TwoBookModal] Library edit response: ", data.get("status", ""), " - ", data.get("reason", ""))
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.request_book_state_sync()


func _refresh_codex_list() -> void:
	codex_item_list.clear()

	# Add active decrees / overrides
	for e in _codex_entries:
		var cat: String = e.get("category", "DECREE")
		var title: String = e.get("title", "Decree")
		codex_item_list.add_item("⚖ [%s] %s" % [cat, title])

	# Add pending codex proposals
	for p in _codex_proposals:
		var title: String = p.get("title", "Proposal")
		codex_item_list.add_item("⚡ [PENDING GOD] %s" % title)


func _on_codex_item_selected(index: int) -> void:
	codex_approval_hbox.visible = false
	_selected_codex_proposal_id = ""

	if index < _codex_entries.size():
		var e: Dictionary = _codex_entries[index]
		codex_detail_title.text = e.get("title", "Divine Decree")
		var author: String = e.get("author_slot", "GOD")
		var cat: String = e.get("category", "DECREE")
		var pkey: Variant = e.get("parameter_key")
		var pval: Variant = e.get("parameter_value_json")

		var desc: String = "Category: %s • Author: %s" % [cat, author]
		if pkey != null and str(pkey) != "":
			desc += "\nEngine Override: %s = %s" % [str(pkey), str(pval)]
		codex_detail_author.text = desc
		codex_detail_text.text = e.get("text", "")
	else:
		var p_idx: int = index - _codex_entries.size()
		if p_idx < _codex_proposals.size():
			var p: Dictionary = _codex_proposals[p_idx]
			_selected_codex_proposal_id = p.get("proposal_id", "")
			codex_detail_title.text = "[PENDING APPEAL] " + p.get("title", "Proposal")
			codex_detail_author.text = "Proposer: %s • Param Key: %s • Param Value: %s" % [
				p.get("proposer_slot", "world_goddess"),
				p.get("parameter_key", ""),
				str(p.get("parameter_value_json", ""))
			]
			codex_detail_text.text = p.get("text", "")
			codex_approval_hbox.visible = (p.get("status", "") == "PENDING_GOD")


func _on_codex_approve_pressed() -> void:
	if _selected_codex_proposal_id == "":
		return
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_codex_approve(_selected_codex_proposal_id)
		codex_approval_hbox.visible = false


func _on_codex_reject_pressed() -> void:
	if _selected_codex_proposal_id == "":
		return
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_codex_reject(_selected_codex_proposal_id)
		codex_approval_hbox.visible = false


func _on_codex_promulgate_pressed() -> void:
	var did: String = codex_input_decree_id.text.strip_edges()
	var body: String = codex_input_decree_text.text.strip_edges()
	var pkey: String = codex_input_param_key.text.strip_edges()
	var pval_raw: String = codex_input_param_val.text.strip_edges()

	if did == "" or body == "":
		return

	var pval: Variant = null
	if pval_raw != "":
		pval = pval_raw.to_float() if pval_raw.is_valid_float() else pval_raw

	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.send_god_codex_edit(did, body, pkey, pval)
		codex_input_decree_id.text = ""
		codex_input_decree_text.text = ""
		codex_input_param_key.text = ""
		codex_input_param_val.text = ""


func _on_codex_approve_response(data: Dictionary) -> void:
	print("[TwoBookModal] Codex approve response: ", data)
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.request_book_state_sync()


func _on_codex_reject_response(data: Dictionary) -> void:
	print("[TwoBookModal] Codex reject response: ", data)
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.request_book_state_sync()


func _on_codex_edit_response(data: Dictionary) -> void:
	print("[TwoBookModal] Codex edit response: ", data)
	var bridge: Node = get_node_or_null("/root/WsBridgeClient")
	if bridge:
		bridge.request_book_state_sync()


func _populate_offline_sample_data() -> void:
	_library_entries = [
		{
			"topic": "DIVINE_PHYSICS",
			"title": "Celestial Harmonics Vol I",
			"author_id": "GOD",
			"author_proficiency": 1.0,
			"created_tick": 0,
			"summary": "Gravitational curvature and physical parameters are sustained by divine harmonics and atomic two-phase commit verification.",
		},
		{
			"topic": "AGRICULTURE",
			"title": "Four-Season Harvests",
			"author_id": "Eldrin the Farmer",
			"author_proficiency": 0.85,
			"created_tick": 120,
			"summary": "Grain stores must be hoarded before winter frost. Winter crop multipliers reduce baseline yields by 70%.",
		},
	]
	_codex_entries = [
		{
			"title": "COVENANT_OF_NON_AGGRESSION",
			"category": "COVENANT_LAW",
			"author_slot": "GOD",
			"parameter_key": "NON_AGGRESSION_COVENANT",
			"parameter_value_json": "true",
			"text": "Racial God-Mothers shall not directly smite civilians of rival lineages without an active war declaration.",
		},
	]
	_refresh_library_list()
	_refresh_codex_list()
