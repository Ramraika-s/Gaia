shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_disabled, diffuse_toon, specular_toon;

// Global uniform driven by SkyWeatherController and Python WORLD_TIME_WEATHER
global uniform float season_progress = 0.0;

uniform vec3 avatar_position = vec3(0.0);
uniform float wind_speed : hint_range(0.1, 5.0) = 1.4;
uniform float wind_strength : hint_range(0.0, 1.0) = 0.22;
uniform float trample_radius : hint_range(0.5, 6.0) = 2.4;
uniform float fade_start : hint_range(30.0, 100.0) = 68.0;
uniform float fade_end : hint_range(40.0, 120.0) = 85.0;

// Seasonal Grass Blade Palettes (Base / Tip)
const vec3 SPRING_BASE = vec3(0.18, 0.40, 0.14);
const vec3 SPRING_TIP = vec3(0.42, 0.68, 0.26);

const vec3 SUMMER_BASE = vec3(0.16, 0.36, 0.12);
const vec3 SUMMER_TIP = vec3(0.38, 0.62, 0.22);

const vec3 AUTUMN_BASE = vec3(0.48, 0.30, 0.10);
const vec3 AUTUMN_TIP = vec3(0.85, 0.58, 0.18);

const vec3 WINTER_BASE = vec3(0.42, 0.40, 0.35);
const vec3 WINTER_TIP = vec3(0.72, 0.70, 0.64);

varying vec3 v_world_pos;
varying float v_tip_factor;
varying float v_fade;

void vertex() {
	v_tip_factor = COLOR.r; // 0.0 at base, 1.0 at blade tip
	vec3 world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 instance_pos = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	v_world_pos = world_pos;

	// Distance fade calculation
	float dist_to_cam = length(instance_pos.xz - avatar_position.xz);
	v_fade = 1.0 - clamp((dist_to_cam - fade_start) / max(1.0, fade_end - fade_start), 0.0, 1.0);

	// Gentle wind sway (only affects upper half of blade)
	if (v_tip_factor > 0.05) {
		float sway_t = TIME * wind_speed;
		float w1 = sin(sway_t + instance_pos.x * 0.35 + instance_pos.z * 0.35);
		float w2 = cos(sway_t * 1.3 + instance_pos.x * 0.18) * 0.5;
		float total_wind = (w1 + w2) * wind_strength * v_tip_factor;

		VERTEX.x += total_wind;
		VERTEX.z += total_wind * 0.65;

		// Trample bend away from God Avatar
		vec2 to_avatar = instance_pos.xz - avatar_position.xz;
		float dist_avatar = length(to_avatar);
		if (dist_avatar < trample_radius && dist_avatar > 0.01) {
			float trample_push = (1.0 - (dist_avatar / trample_radius)) * v_tip_factor;
			vec2 push_dir = normalize(to_avatar);
			VERTEX.xz += push_dir * trample_push * 0.55;
			VERTEX.y -= trample_push * 0.20;
		}
	}
}

void fragment() {
	// Screen-door transparency dither for smooth distance fade
	if (v_fade < 0.99) {
		ivec2 screen_coord = ivec2(FRAGCOORD.xy);
		int dither_idx = (screen_coord.x % 4) * 4 + (screen_coord.y % 4);
		const float DITHER_TABLE[16] = float[16](
			0.0625, 0.5625, 0.1875, 0.6875,
			0.8125, 0.3125, 0.9375, 0.4375,
			0.2500, 0.7500, 0.1250, 0.6250,
			1.0000, 0.5000, 0.8750, 0.3750
		);
		if (v_fade < DITHER_TABLE[dither_idx]) {
			discard;
		}
	}

	// 4-Season Color Interpolation
	float prog = mod(season_progress, 4.0);
	vec3 base_col = SPRING_BASE;
	vec3 tip_col = SPRING_TIP;

	if (prog < 1.0) {
		base_col = mix(SPRING_BASE, SUMMER_BASE, prog);
		tip_col = mix(SPRING_TIP, SUMMER_TIP, prog);
	} else if (prog < 2.0) {
		base_col = mix(SUMMER_BASE, AUTUMN_BASE, prog - 1.0);
		tip_col = mix(SUMMER_TIP, AUTUMN_TIP, prog - 1.0);
	} else if (prog < 3.0) {
		base_col = mix(AUTUMN_BASE, WINTER_BASE, prog - 2.0);
		tip_col = mix(AUTUMN_TIP, WINTER_TIP, prog - 2.0);
	} else {
		base_col = mix(WINTER_BASE, SPRING_BASE, prog - 3.0);
		tip_col = mix(WINTER_TIP, SPRING_TIP, prog - 3.0);
	}

	vec3 blade_color = mix(base_col, tip_col, clamp(v_tip_factor, 0.0, 1.0));

	ALBEDO = blade_color;
	ROUGHNESS = 0.55;
	SPECULAR = 0.15;
}
