shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 shallow_color : source_color = vec4(0.06, 0.42, 0.48, 0.80);
uniform vec4 deep_color : source_color = vec4(0.015, 0.085, 0.26, 0.95);
uniform vec4 foam_color : source_color = vec4(0.82, 0.90, 0.96, 1.00);

uniform float wave_speed : hint_range(0.0, 5.0) = 1.2;
uniform float wave_amplitude : hint_range(0.0, 1.0) = 0.20;
uniform float wave_frequency : hint_range(0.01, 1.0) = 0.06;
uniform float foam_thickness : hint_range(0.05, 3.0) = 0.75;
uniform float depth_distance : hint_range(0.5, 30.0) = 8.0;

uniform sampler2D depth_texture : hint_depth_texture, repeat_disable, filter_nearest;

varying vec3 v_world_pos;

// Exact integer harmonics of 512m domain -> 100% seamless across 8km map (zero 512m tile seams)
const float K1X = 6.28318530718 * 8.0 / 512.0;
const float K1Z = 6.28318530718 * 7.0 / 512.0;
const float K2X = 6.28318530718 * 11.0 / 512.0;
const float K2Z = 6.28318530718 * 13.0 / 512.0;
const float K3X = 6.28318530718 * 10.0 / 512.0;
const float K3Z = 6.28318530718 * 12.0 / 512.0;
const float K_FOAM = 6.28318530718 * 28.0 / 512.0;

vec3 get_wave_normal(vec2 wp, float t) {
	float d1 = sin(wp.x * K1X + t) * cos(wp.y * K1Z + t * 0.9);
	float d2 = cos(wp.x * K2X - t * 1.1) * sin(wp.y * K2Z + t * 0.8);
	float d3 = sin(wp.x * K3X + wp.y * K3Z + t * 1.35) * 0.35;

	float dx = (d1 + d2 + d3) * wave_amplitude * 0.38;
	float dz = (d1 - d2 + d3 * 0.8) * wave_amplitude * 0.38;
	return normalize(vec3(-dx, 1.0, -dz));
}

void vertex() {
	vec3 world_v = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec2 wp = mod(world_v.xz, 512.0);
	float t = TIME * wave_speed;

	// Gentle surface displacement (kept low so large triangles never Z-fight flat beaches)
	float w1 = sin(wp.x * K1X + t) * cos(wp.y * K1Z + t * 0.9);
	float w2 = cos(wp.x * K2X - t * 0.7) * sin(wp.y * K2Z + t * 0.8);
	float displacement = (w1 + w2) * wave_amplitude * 0.25;

	VERTEX.y += displacement;
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 w_nrm = get_wave_normal(wp, t);
	NORMAL = normalize((MODEL_MATRIX * vec4(w_nrm, 0.0)).xyz);
}

void fragment() {
	// Reverse-Z Vulkan Forward+ screen depth reconstruction
	float depth_raw = texture(depth_texture, SCREEN_UV).r;
	float water_depth = depth_distance;
	if (depth_raw > 0.00001) {
		vec3 ndc = vec3(SCREEN_UV * 2.0 - 1.0, depth_raw);
		vec4 view_pos = INV_PROJECTION_MATRIX * vec4(ndc, 1.0);
		view_pos.xyz /= max(abs(view_pos.w), 0.000001);
		float scene_depth = -view_pos.z;
		float surface_depth = -VERTEX.z;
		water_depth = max(0.0, scene_depth - surface_depth);
	}

	// Smooth shoreline alpha feathering (prevents hard polygon edges and beach Z-fighting)
	float shore_fade = smoothstep(0.0, 0.45, water_depth);

	// Depth color gradient (shallow turquoise -> deep ocean blue)
	float depth_factor = clamp(water_depth / depth_distance, 0.0, 1.0);
	vec4 water_col = mix(shallow_color, deep_color, depth_factor);

	// Wrapped coordinates for seamless wave normals across 8km
	vec2 wp = mod(v_world_pos.xz, 512.0);
	float t = TIME * wave_speed;
	vec3 wave_n = get_wave_normal(wp, t);
	vec3 view_n = normalize((VIEW_MATRIX * vec4(wave_n, 0.0)).xyz);
	NORMAL = view_n;

	// Organic Fresnel sky reflection + subtle directional wave-crest shimmer (no grid blobs)
	float fresnel = pow(1.0 - clamp(dot(view_n, normalize(VIEW)), 0.0, 1.0), 3.0);
	float crest = pow(clamp(dot(wave_n, normalize(vec3(0.24, 0.94, 0.24))), 0.0, 1.0), 18.0);
	float ripple_shimmer = smoothstep(0.55, 0.92, crest);

	// Soft animated shoreline foam band
	float foam_mask = 0.0;
	if (water_depth < foam_thickness) {
		float foam_ramp = 1.0 - (water_depth / foam_thickness);
		float wave_edge = sin((wp.x + wp.y) * K_FOAM - t * 2.0) * 0.5 + 0.5;
		float inner_fade = smoothstep(0.03, 0.18, water_depth);
		foam_mask = smoothstep(0.38, 0.80, foam_ramp + wave_edge * 0.22) * inner_fade;
	}

	vec3 sky_reflect_col = vec3(0.28, 0.52, 0.78);
	vec3 final_color = mix(water_col.rgb, sky_reflect_col, fresnel * 0.35);
	final_color += vec3(0.08, 0.14, 0.18) * ripple_shimmer * (1.0 - depth_factor * 0.5) * shore_fade;
	final_color = mix(final_color, foam_color.rgb, foam_mask);

	ALBEDO = clamp(final_color, vec3(0.0), vec3(1.0));
	ALPHA = mix(water_col.a, 0.92, foam_mask) * shore_fade;
	ROUGHNESS = mix(0.08, 0.52, foam_mask);
	SPECULAR = 0.65;
}
