shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_toon, specular_toon;

// Global uniform driven by SkyWeatherController and Python WORLD_TIME_WEATHER
global uniform float season_progress = 0.0;

uniform sampler2D albedo_texture : source_color, filter_linear_mipmap, repeat_enable;
uniform vec4 base_color : source_color = vec4(1.0, 1.0, 1.0, 1.0);
uniform bool is_foliage = false;
uniform float cel_shadow_threshold : hint_range(0.0, 1.0) = 0.45;
uniform float cel_shadow_softness : hint_range(0.0, 0.5) = 0.05;
uniform vec4 shadow_tint : source_color = vec4(0.40, 0.45, 0.55, 1.0);
uniform float rim_threshold : hint_range(0.0, 1.0) = 0.65;
uniform float rim_softness : hint_range(0.0, 0.5) = 0.10;

// 4-Season Foliage & Environment Colors
const vec3 SPRING_TINT = vec3(0.32, 0.58, 0.32);
const vec3 SUMMER_TINT = vec3(0.26, 0.50, 0.22);
const vec3 AUTUMN_TINT = vec3(0.85, 0.45, 0.16);
const vec3 WINTER_TINT = vec3(0.85, 0.90, 0.95);
const vec3 SNOW_COLOR  = vec3(0.92, 0.95, 1.00);

varying vec3 v_world_normal;
varying vec3 v_world_pos;

void vertex() {
	v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

void fragment() {
	vec4 tex_color = texture(albedo_texture, UV) * base_color;
	vec3 final_albedo = tex_color.rgb;

	// 1. Foliage seasonal tint transitions
	if (is_foliage) {
		float progress = mod(season_progress, 4.0);
		vec3 season_tint = SPRING_TINT;
		if (progress < 1.0) {
			season_tint = mix(SPRING_TINT, SUMMER_TINT, progress);
		} else if (progress < 2.0) {
			season_tint = mix(SUMMER_TINT, AUTUMN_TINT, progress - 1.0);
		} else if (progress < 3.0) {
			season_tint = mix(AUTUMN_TINT, WINTER_TINT, progress - 2.0);
		} else {
			season_tint = mix(WINTER_TINT, SPRING_TINT, progress - 3.0);
		}
		final_albedo *= season_tint;
	}

	// 2. Winter top-facing snow accumulation
	float prog = mod(season_progress, 4.0);
	float winter_factor = 0.0;
	if (prog >= 2.5 && prog < 3.5) {
		winter_factor = 1.0 - abs(prog - 3.0) * 2.0;
		winter_factor = clamp(winter_factor, 0.0, 1.0);
	}
	float top_facing = clamp(dot(v_world_normal, vec3(0.0, 1.0, 0.0)), 0.0, 1.0);
	float snow_coverage = smoothstep(0.40, 0.70, top_facing) * winter_factor;
	final_albedo = mix(final_albedo, SNOW_COLOR, snow_coverage * 0.85);

	ALBEDO = final_albedo;
	ROUGHNESS = 0.85;
	SPECULAR = 0.15;
}

void light() {
	// Crisp 2-band stylized cel shading
	float NdotL = dot(NORMAL, LIGHT);
	float light_intensity = smoothstep(
		cel_shadow_threshold - cel_shadow_softness,
		cel_shadow_threshold + cel_shadow_softness,
		NdotL
	);
	vec3 light_color = mix(shadow_tint.rgb, vec3(1.0), light_intensity) * LIGHT_COLOR * ATTENUATION;

	// Subtle rim light
	float NdotV = 1.0 - dot(NORMAL, VIEW);
	float rim = smoothstep(
		rim_threshold - rim_softness,
		rim_threshold + rim_softness,
		NdotV * NdotL
	);
	vec3 rim_color = rim * LIGHT_COLOR * 0.25;

	DIFFUSE_LIGHT += ALBEDO * light_color + rim_color;
}
