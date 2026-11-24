shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_toon, specular_toon;

// Global uniform driven by SkyWeatherController
global uniform float night_factor;

uniform vec4 day_glass_color : source_color = vec4(0.12, 0.16, 0.22, 1.0);
uniform vec4 night_glow_color : source_color = vec4(1.0, 0.82, 0.42, 1.0);
uniform float day_roughness : hint_range(0.0, 1.0) = 0.15;
uniform float night_roughness : hint_range(0.0, 1.0) = 0.45;
uniform float max_emission_energy : hint_range(0.0, 8.0) = 2.4;

void fragment() {
	float nf = clamp(night_factor, 0.0, 1.0);
	ALBEDO = mix(day_glass_color.rgb, night_glow_color.rgb, nf * 0.75);
	ROUGHNESS = mix(day_roughness, night_roughness, nf);
	METALLIC = mix(0.85, 0.10, nf);
	SPECULAR = 0.5;

	// Warm glowing amber emission at night
	if (nf > 0.01) {
		EMISSION = night_glow_color.rgb * (nf * max_emission_energy);
	} else {
		EMISSION = vec3(0.0);
	}
}
