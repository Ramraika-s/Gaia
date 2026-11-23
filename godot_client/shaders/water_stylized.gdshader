shader_type spatial;
render_mode blend_mix, depth_draw_always, cull_back, diffuse_toon, specular_toon;

uniform vec4 shallow_color : source_color = vec4(0.20, 0.76, 0.78, 0.85);
uniform vec4 deep_color : source_color = vec4(0.04, 0.18, 0.46, 0.95);
uniform vec4 foam_color : source_color = vec4(0.96, 0.98, 1.00, 1.00);

uniform float wave_speed : hint_range(0.0, 5.0) = 1.2;
uniform float wave_amplitude : hint_range(0.0, 1.0) = 0.20;
uniform float wave_frequency : hint_range(0.01, 1.0) = 0.06;
uniform float foam_thickness : hint_range(0.05, 3.0) = 0.75;
uniform float depth_distance : hint_range(0.5, 30.0) = 8.0;

uniform sampler2D depth_texture : hint_depth_texture, filter_linear_mipmap;

varying vec3 v_world_pos;
varying vec3 v_normal;

// Procedural wave normal calculation
vec3 get_wave_normal(vec2 p, float t) {
	float k = wave_frequency;
	float speed = wave_speed;
	float d1 = sin(p.x * k + t * speed) * cos(p.y * k * 0.8 + t * speed * 0.9);
	float d2 = cos(p.x * k * 1.3 - t * speed * 1.1) * sin(p.y * k * 1.2 + t * speed * 0.8);

	float dx = (d1 + d2) * wave_amplitude * 0.5;
	float dz = (d1 - d2) * wave_amplitude * 0.5;
	return normalize(vec3(-dx, 1.0, -dz));
}

void vertex() {
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float t = TIME * wave_speed;

	// Gentle animated surface wave
	float w1 = sin(v_world_pos.x * wave_frequency + t) * cos(v_world_pos.z * wave_frequency * 0.85 + t * 0.9);
	float w2 = cos(v_world_pos.x * wave_frequency * 1.4 - t * 0.7) * sin(v_world_pos.z * wave_frequency * 1.2 + t * 0.8);
	float displacement = (w1 + w2) * wave_amplitude;

	VERTEX.y += displacement;
	v_normal = get_wave_normal(v_world_pos.xz, t);
	NORMAL = normalize((MODEL_MATRIX * vec4(v_normal, 0.0)).xyz);
}

void fragment() {
	// Screen depth reconstruction for true depth-based tinting & shoreline foam
	float depth_raw = texture(depth_texture, SCREEN_UV).r;
	vec3 ndc = vec3(SCREEN_UV * 2.0 - 1.0, depth_raw);
	vec4 view_pos = INV_PROJECTION_MATRIX * vec4(ndc, 1.0);
	view_pos.xyz /= view_pos.w;
	float scene_depth = -view_pos.z;
	float surface_depth = -VERTEX.z;
	float water_depth = max(0.0, scene_depth - surface_depth);

	// Depth color gradient (shallow teal -> deep ocean blue)
	float depth_factor = clamp(water_depth / depth_distance, 0.0, 1.0);
	vec4 water_col = mix(shallow_color, deep_color, depth_factor);

	// Crisp stylized shoreline foam line
	float foam_mask = 0.0;
	if (water_depth < foam_thickness) {
		float foam_ramp = 1.0 - (water_depth / foam_thickness);
		float wave_edge = sin(v_world_pos.x * 0.4 + v_world_pos.z * 0.4 - TIME * 2.5) * 0.5 + 0.5;
		foam_mask = smoothstep(0.3, 0.7, foam_ramp + wave_edge * 0.35);
	}

	// Micro surface caustics / specular glint
	float caustic_wave = sin(v_world_pos.x * 0.25 + TIME * 1.8) * cos(v_world_pos.z * 0.25 - TIME * 1.4);
	float caustic_glint = smoothstep(0.75, 0.95, caustic_wave) * (1.0 - depth_factor * 0.7);

	vec3 final_color = mix(water_col.rgb, foam_color.rgb, foam_mask);
	final_color += vec3(caustic_glint * 0.25);

	ALBEDO = final_color;
	ALPHA = mix(water_col.a, 1.0, foam_mask);
	ROUGHNESS = mix(0.08, 0.60, foam_mask);
	SPECULAR = 0.55;
}
