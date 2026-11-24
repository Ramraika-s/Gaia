# Copyright (c) 2026 Gaia Project Contributors
# godot_client/scripts/ws_bridge_client.gd
# Non-blocking WebSocket client connecting Godot 4.7.2 client to Python core on ws://127.0.0.1:8765.

extends Node

signal connected_to_bridge
signal disconnected_from_bridge
signal world_time_weather_received(data: Dictionary)
signal bubble_sync_received(data: Dictionary)
signal sign_update_received(data: Dictionary)
signal altar_beacon_received(data: Dictionary)
signal divine_hud_message_received(data: Dictionary)
signal orbital_positions_received(buffer: PackedByteArray, agent_count: int)
signal god_focus_changed(pos: Vector3, is_orbital: bool)

signal book_state_sync_received(data: Dictionary)
signal god_command_result_received(data: Dictionary)
signal god_library_edit_response_received(data: Dictionary)
signal god_codex_approve_response_received(data: Dictionary)
signal god_codex_reject_response_received(data: Dictionary)
signal god_codex_edit_response_received(data: Dictionary)
signal palace_entry_requested(payload: Dictionary)
signal palace_decision_announced(payload: Dictionary)
signal building_sync_received(buildings: Array, cities: Array)
signal building_updated(building: Dictionary)
signal deity_sync_received(deities: Array)
signal dialogue_response_received(data: Dictionary)

const BRIDGE_URL: String = "ws://127.0.0.1:8765"
const RECONNECT_DELAY: float = 2.0
const STATE_SEND_INTERVAL: float = 0.1  # 10 Hz

var _ws: WebSocketPeer = WebSocketPeer.new()
var _connected: bool = false
var _reconnect_timer: float = 0.0
var _send_timer: float = 0.0

var current_god_pos: Vector3 = Vector3(0.0, 18.5, 0.0)
var is_orbital_view: bool = false
var camera_altitude: float = 35.0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_connect_to_bridge()


func _process(delta: float) -> void:
	_poll_websocket()

	if not _connected:
		_reconnect_timer += delta
		if _reconnect_timer >= RECONNECT_DELAY:
			_reconnect_timer = 0.0
			_connect_to_bridge()
	else:
		_send_timer += delta
		if _send_timer >= STATE_SEND_INTERVAL:
			_send_timer = 0.0
			_send_god_state()


func _connect_to_bridge() -> void:
	_ws = WebSocketPeer.new()
	_ws.inbound_buffer_size = 4 * 1024 * 1024
	_ws.outbound_buffer_size = 1024 * 1024
	_ws.max_queued_packets = 4096
	var err: Error = _ws.connect_to_url(BRIDGE_URL)
	if err != OK:
		# Will retry automatically on next interval
		return


func _poll_websocket() -> void:
	_ws.poll()
	var state: WebSocketPeer.State = _ws.get_ready_state()

	if state == WebSocketPeer.STATE_OPEN:
		if not _connected:
			_connected = true
			connected_to_bridge.emit()
			# Send initial handshake identifying as Godot God Avatar client
			var handshake: Dictionary = {
				"type": "CLIENT_HANDSHAKE",
				"client": "GODOT_CLIENT",
				"version": "4.0.0",
				"is_god": true,
			}
			send_json(handshake)

		while _ws.get_available_packet_count() > 0:
			_handle_packet()

	elif state == WebSocketPeer.STATE_CLOSED or state == WebSocketPeer.STATE_CLOSING:
		if _connected:
			_connected = false
			disconnected_from_bridge.emit()


func _handle_packet() -> void:
	var raw_bytes: PackedByteArray = _ws.get_packet()
	if _ws.was_string_packet():
		var text: String = raw_bytes.get_string_from_utf8()
		var json_result: Variant = JSON.parse_string(text)
		if typeof(json_result) == TYPE_DICTIONARY:
			_dispatch_json_event(json_result as Dictionary)
	else:
		# Binary packet: PackedFloat32Array bulk agent positions (24 bytes per agent)
		var agent_count: int = raw_bytes.size() / 24
		if agent_count > 0:
			orbital_positions_received.emit(raw_bytes, agent_count)


func _dispatch_json_event(dict: Dictionary) -> void:
	var msg_type: String = dict.get("type", "")
	match msg_type:
		"WORLD_TIME_WEATHER":
			world_time_weather_received.emit(dict)
		"BUBBLE_SYNC":
			bubble_sync_received.emit(dict)
		"SIGN_UPDATE":
			sign_update_received.emit(dict)
		"ALTAR_BEACON":
			altar_beacon_received.emit(dict)
		"DIVINE_HUD_MESSAGE":
			divine_hud_message_received.emit(dict)
		"BOOK_STATE_SYNC":
			book_state_sync_received.emit(dict)
		"GOD_COMMAND_RESULT":
			god_command_result_received.emit(dict)
		"GOD_COMMAND_RESPONSE":
			god_command_result_received.emit(dict)
		"GOD_LIBRARY_EDIT_RESPONSE":
			god_library_edit_response_received.emit(dict)
		"GOD_CODEX_APPROVE_RESPONSE":
			god_codex_approve_response_received.emit(dict)
		"GOD_CODEX_REJECT_RESPONSE":
			god_codex_reject_response_received.emit(dict)
		"GOD_CODEX_EDIT_RESPONSE":
			god_codex_edit_response_received.emit(dict)
		"PALACE_ENTRY_REQUEST":
			palace_entry_requested.emit(dict)
		"PALACE_DECISION_ANNOUNCED":
			palace_decision_announced.emit(dict)
		"BUILDING_SYNC":
			building_sync_received.emit(dict.get("buildings", []), dict.get("cities", []))
		"BUILDING_UPDATE":
			building_updated.emit(dict.get("building", {}))
		"DEITY_SYNC":
			deity_sync_received.emit(dict.get("deities", []))
		"DIALOGUE_RESPONSE":
			dialogue_response_received.emit(dict)


func _send_god_state() -> void:
	var payload: Dictionary = {
		"type": "GOD_STATE",
		"x": current_god_pos.x,
		"y": current_god_pos.y,
		"z": current_god_pos.z,
		"is_orbital": is_orbital_view,
		"altitude": camera_altitude,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func update_god_focus(pos: Vector3, orbital: bool, alt: float) -> void:
	current_god_pos = pos
	is_orbital_view = orbital
	camera_altitude = alt
	god_focus_changed.emit(pos, orbital)


func send_json(dict: Dictionary) -> void:
	if _connected and _ws.get_ready_state() == WebSocketPeer.STATE_OPEN:
		var json_text: String = JSON.stringify(dict)
		_ws.put_packet(json_text.to_utf8_buffer())


func send_god_command(command: String, args: Dictionary = {}) -> void:
	var payload: Dictionary = {
		"type": "GOD_COMMAND",
		"command": command,
		"args": args,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func send_god_raw_command(raw_cmd: String) -> void:
	var payload: Dictionary = {
		"type": "GOD_COMMAND",
		"raw_command": raw_cmd,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func send_god_library_edit(topic: String, volume_title: String, text_content: String, author_id: String = "GOD") -> void:
	var payload: Dictionary = {
		"type": "GOD_LIBRARY_EDIT",
		"topic": topic,
		"volume_title": volume_title,
		"text_content": text_content,
		"author_id": author_id,
		"bypass_god_check": true,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func send_god_codex_edit(decree_id: String, text_decree: String, param_key: String = "", param_val: Variant = null) -> void:
	var payload: Dictionary = {
		"type": "GOD_CODEX_EDIT",
		"decree_id": decree_id,
		"text_decree": text_decree,
		"bypass_god_check": true,
		"timestamp": Time.get_unix_time_from_system(),
	}
	if param_key != "":
		payload["parameter_key"] = param_key
		payload["parameter_val"] = param_val
	send_json(payload)


func send_god_codex_approve(proposal_id: String) -> void:
	var payload: Dictionary = {
		"type": "GOD_CODEX_APPROVE",
		"proposal_id": proposal_id,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func send_god_codex_reject(proposal_id: String) -> void:
	var payload: Dictionary = {
		"type": "GOD_CODEX_REJECT",
		"proposal_id": proposal_id,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func request_book_state_sync() -> void:
	var payload: Dictionary = {
		"type": "REQUEST_BOOK_STATE_SYNC",
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func is_bridge_connected() -> bool:
	return _connected


func send_palace_decision(request_id: String, decision: String, duration: int = 600) -> void:
	var payload: Dictionary = {
		"type": "GOD_PALACE_DECISION",
		"request_id": request_id,
		"decision": decision,
		"duration": duration,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)


func send_dialogue_request(target_type: String, target_id: String, message: String, order: String = "") -> void:
	var payload: Dictionary = {
		"type": "DIALOGUE_REQUEST",
		"target_type": target_type,
		"target_id": target_id,
		"message": message,
		"order": order,
		"timestamp": Time.get_unix_time_from_system(),
	}
	send_json(payload)
