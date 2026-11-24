shader_type spatial;
render_mode cull_back, diffuse_burley, specular_schlick_ggx;

global uniform float night_factor;

uniform bool is_roof = false;
uniform float roughness_val = 0.84;

varying vec3 v_color;
varying vec3 v_local_pos;
varying vec3 v_world_nrm;

void vertex() {
	v_color = COLOR.rgb;
	v_local_pos = VERTEX;
	v_world_nrm = (MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz;
}

void fragment() {
	vec3 base_col = v_color;
	float wall_win_mask = 0.0;
	float roof_dormer_mask = 0.0;

	if (!is_roof && abs(v_world_nrm.y) < 0.45) {
		float u = abs(v_world_nrm.x) > abs(v_world_nrm.z) ? (v_local_pos.z + 0.5) : (v_local_pos.x + 0.5);
		float v = v_local_pos.y;
		if (u > 0.10 && u < 0.90 && v > 0.16 && v < 0.88) {
			vec2 cell = fract(vec2(u * 3.0, v * 2.5));
			float in_x = step(0.22, cell.x) * step(cell.x, 0.78);
			float in_y = step(0.20, cell.y) * step(cell.y, 0.76);
			wall_win_mask = in_x * in_y;
		}
		base_col = mix(base_col, base_col * 0.48 + vec3(0.06, 0.08, 0.11), wall_win_mask * (1.0 - night_factor));
	} else if (is_roof && v_local_pos.y > 0.18 && v_local_pos.y < 0.62) {
		// Subtle warm dormer / skylight stipples visible from high Orbital RTS angles at night
		if (abs(abs(v_local_pos.x) - 0.24) < 0.08) {
			roof_dormer_mask = 1.0;
		}
	}

	ALBEDO = base_col;
	ROUGHNESS = roughness_val;
	METALLIC = 0.04;

	float glow_strength = smoothstep(0.05, 0.42, night_factor);
	vec3 wall_glow = vec3(1.0, 0.48, 0.08) * (3.2 + 1.8 * night_factor) * wall_win_mask;
	vec3 dormer_glow = vec3(1.0, 0.45, 0.08) * 2.4 * roof_dormer_mask;
	EMISSION = (wall_glow + dormer_glow) * glow_strength;
}
