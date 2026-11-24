shader_type spatial;
render_mode blend_add, depth_draw_never, unshaded, cull_disabled;

global uniform float night_factor;

void fragment() {
	vec2 d = UV * 2.0 - 1.0;
	float dist = length(d);
	float nf = smoothstep(0.05, 0.45, night_factor);
	float falloff = exp(-dist * dist * 4.0) * smoothstep(1.0, 0.25, dist);
	float intensity = nf * falloff;
	ALBEDO = vec3(1.0, 0.50, 0.10) * 1.15;
	ALPHA = intensity * 0.62;
}
