shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

// Global uniform driven by SkyWeatherController and Python WORLD_TIME_WEATHER
global uniform float season_progress = 0.0;

uniform sampler2D heightmap_texture : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D biome_splat_texture : hint_default_black, filter_linear, repeat_disable;
uniform sampler2D road_mask_texture : hint_default_black, filter_linear, repeat_disable;

// Mipmapped PBR surface textures (bound by TerrainManager)
uniform sampler2D road_albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D road_normal_texture : hint_roughness_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D plaza_albedo_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D plaza_normal_texture : hint_roughness_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D cliff_rock_texture : source_color, hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;

uniform bool is_raw_float_meters = true;
uniform float max_height_meters = 180.0;
uniform float min_height_meters = -25.0;
uniform vec2 world_size = vec2(8000.0, 8000.0);

// Surface Color Palettes (true linear PBR range: matches sRGB textures without HDR blow-out)
// 1. Human Plains: lush sunlit emerald meadow & clover patches (seasonal)
const vec3 GRASS_BASE_SPRING = vec3(0.055, 0.165, 0.032);
const vec3 GRASS_HIGHLIGHT_SPRING = vec3(0.115, 0.275, 0.055);
const vec3 GRASS_DARK_SPRING = vec3(0.030, 0.105, 0.022);

const vec3 GRASS_BASE_SUMMER = vec3(0.050, 0.150, 0.028);
const vec3 GRASS_HIGHLIGHT_SUMMER = vec3(0.095, 0.240, 0.048);

const vec3 GRASS_BASE_AUTUMN = vec3(0.240, 0.125, 0.025);
const vec3 GRASS_HIGHLIGHT_AUTUMN = vec3(0.380, 0.210, 0.045);

const vec3 GRASS_BASE_WINTER = vec3(0.220, 0.205, 0.175);
const vec3 GRASS_HIGHLIGHT_WINTER = vec3(0.340, 0.320, 0.275);

const vec3 CLOVER_PATCH = vec3(0.040, 0.150, 0.065);

// 2. Roads & Plazas
const vec3 ROAD_DIRT = vec3(0.16, 0.11, 0.06);
const vec3 ROAD_DIRT_LIGHT = vec3(0.24, 0.17, 0.09);
const vec3 ROAD_STONE_TINT = vec3(0.86, 0.82, 0.76);
const vec3 PLAZA_STONE_TINT = vec3(0.84, 0.81, 0.75);

// 3. Sandy Shores & Riverbeds
const vec3 SAND_SHORE = vec3(0.36, 0.28, 0.14);
const vec3 SAND_WET = vec3(0.17, 0.13, 0.07);
const vec3 GRAVEL_RIVERBED = vec3(0.10, 0.09, 0.08);

// 4. Exposed Cliff Rock & Steep Slopes
const vec3 ROCK_CLIFF = vec3(0.16, 0.16, 0.18);
const vec3 ROCK_DARK = vec3(0.08, 0.08, 0.10);

// 5. Dragon Peaks: basalt ridges, ember vents, snowcaps
const vec3 DRAGON_OBSIDIAN = vec3(0.045, 0.040, 0.055);
const vec3 DRAGON_BASALT_LIGHT = vec3(0.12, 0.10, 0.12);
const vec3 DRAGON_FISSURE_GLOW = vec3(1.0, 0.38, 0.08);

// 6. Demon Ashlands: volcanic charcoal + violet-crimson fissures
const vec3 DEMON_ASHLAND = vec3(0.045, 0.038, 0.052);
const vec3 DEMON_FISSURE_VIOLET = vec3(0.75, 0.18, 0.95);
const vec3 DEMON_FISSURE_CRIMSON = vec3(0.95, 0.12, 0.30);

// 7. Elf Highlands: lush deep teal-emerald sylvan moss
const vec3 ELF_SYLVAN_MOSS = vec3(0.028, 0.155, 0.088);
const vec3 ELF_DEEP_TEAL = vec3(0.016, 0.095, 0.078);

// 8. Alpine Snowcaps & Winter Snow
const vec3 SNOW_COLOR = vec3(0.64, 0.70, 0.80);

// 9. Beasthuman Taiga: pine-olive steppe with slate outcrops
const vec3 BEAST_TAIGA_GROUND = vec3(0.075, 0.115, 0.055);
const vec3 BEAST_SLATE = vec3(0.13, 0.15, 0.19);

varying vec3 v_world_pos;
varying vec3 v_world_normal;
varying vec2 v_splat_uv;

// Precision-safe Dave Hoskins polynomial hashes (zero sin() precision drift at +-4000m)
vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return -1.0 + 2.0 * fract((p3.xx + p3.yz) * p3.zy);
}

// Tileable periodic gradient noise over integer period so mod(world_xz, 512.0) has zero seams
float gnoise_periodic(vec2 p, float period) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);

	vec2 i00 = mod(i, period);
	vec2 i10 = mod(i + vec2(1.0, 0.0), period);
	vec2 i01 = mod(i + vec2(0.0, 1.0), period);
	vec2 i11 = mod(i + vec2(1.0, 1.0), period);

	return mix(
		mix(dot(hash22(i00), f - vec2(0.0, 0.0)),
		    dot(hash22(i10), f - vec2(1.0, 0.0)), u.x),
		mix(dot(hash22(i01), f - vec2(0.0, 1.0)),
		    dot(hash22(i11), f - vec2(1.0, 1.0)), u.x),
		u.y
	);
}

// 2-octave smooth periodic fBM (base period is an exact divisor of 512m tile)
float fbm_periodic(vec2 p_norm, float base_period) {
	float f = 0.0;
	f += 0.65 * gnoise_periodic(p_norm * base_period, base_period);
	f += 0.35 * gnoise_periodic(p_norm * (base_period * 2.0), base_period * 2.0);
	return f;
}

float sample_height_meters(vec2 uv) {
	vec2 cuv = clamp(uv, vec2(0.0005), vec2(0.9995));
	float raw_val = texture(heightmap_texture, cuv).r;
	return is_raw_float_meters ? raw_val : (min_height_meters + raw_val * (max_height_meters - min_height_meters));
}

void vertex() {
	vec3 world_v = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec2 uv = clamp((world_v.xz + world_size * 0.5) / world_size, vec2(0.0), vec2(1.0));
	v_splat_uv = uv;

	// Exact Heightmap Displacement
	float h = sample_height_meters(uv);
	VERTEX.y = h;

	// Recompute true normal & orthonormal tangent frame from 1024x1024 heightmap gradient
	float texel_uv = 1.0 / 1024.0;
	float world_texel = world_size.x / 1024.0;

	float h_east = sample_height_meters(uv + vec2(texel_uv, 0.0));
	float h_west = sample_height_meters(uv - vec2(texel_uv, 0.0));
	float h_north = sample_height_meters(uv + vec2(0.0, texel_uv));
	float h_south = sample_height_meters(uv - vec2(0.0, texel_uv));

	vec3 normal = normalize(vec3(
		(h_west - h_east) / (2.0 * world_texel),
		1.0,
		(h_south - h_north) / (2.0 * world_texel)
	));
	vec3 tangent = normalize(vec3(1.0, (h_east - h_west) / (2.0 * world_texel), 0.0));
	vec3 binormal = normalize(cross(normal, tangent));
	tangent = normalize(cross(binormal, normal));

	NORMAL = normal;
	TANGENT = tangent;
	BINORMAL = binormal;
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(normal, 0.0)).xyz);
}

void fragment() {
	vec4 splat = texture(biome_splat_texture, v_splat_uv);
	float road_val = texture(road_mask_texture, v_splat_uv).r;
	float slope_y = clamp(v_world_normal.y, 0.0, 1.0);
	float h = v_world_pos.y;

	// Wrap world coordinates strictly inside [0, 512) -> zero precision loss anywhere on 8km map
	vec2 p = mod(v_world_pos.xz, 512.0);
	vec2 p_norm = p / 512.0;

	// Smooth distance attenuation for close-up detail (silky-smooth distant hills, zero moire)
	float cam_dist = length(VERTEX);
	float detail = smoothstep(180.0, 20.0, cam_dist);

	// 3-scale periodic fBM (exact integer harmonics over 512m -> zero tile seams)
	float n_macro = fbm_periodic(p_norm, 4.0);
	float n_mid = fbm_periodic(p_norm + vec2(0.13, 0.37), 16.0);
	float n_micro = fbm_periodic(p_norm + vec2(0.41, 0.19), 64.0) * detail;

	// 1. Seasonal Grass Palette
	float prog = mod(season_progress, 4.0);
	vec3 g_base = GRASS_BASE_SPRING;
	vec3 g_high = GRASS_HIGHLIGHT_SPRING;
	if (prog < 1.0) {
		g_base = mix(GRASS_BASE_SPRING, GRASS_BASE_SUMMER, prog);
		g_high = mix(GRASS_HIGHLIGHT_SPRING, GRASS_HIGHLIGHT_SUMMER, prog);
	} else if (prog < 2.0) {
		g_base = mix(GRASS_BASE_SUMMER, GRASS_BASE_AUTUMN, prog - 1.0);
		g_high = mix(GRASS_HIGHLIGHT_SUMMER, GRASS_HIGHLIGHT_AUTUMN, prog - 1.0);
	} else if (prog < 3.0) {
		g_base = mix(GRASS_BASE_AUTUMN, GRASS_BASE_WINTER, prog - 2.0);
		g_high = mix(GRASS_HIGHLIGHT_AUTUMN, GRASS_HIGHLIGHT_WINTER, prog - 2.0);
	} else {
		g_base = mix(GRASS_BASE_WINTER, GRASS_BASE_SPRING, prog - 3.0);
		g_high = mix(GRASS_HIGHLIGHT_WINTER, GRASS_HIGHLIGHT_SPRING, prog - 3.0);
	}

	vec3 grass_color = mix(g_base, g_high, clamp(n_macro * 0.85 + 0.5, 0.0, 1.0));
	grass_color = mix(grass_color, GRASS_DARK_SPRING, clamp(-n_macro * 0.65, 0.0, 1.0));
	grass_color = mix(grass_color, CLOVER_PATCH, smoothstep(0.05, 0.25, n_mid) * 0.42);
	grass_color *= 1.0 + n_micro * 0.12;

	// Sample mipmapped stylized rock texture at seamless periodic UVs
	vec3 rock_tex_a = texture(cliff_rock_texture, p_norm * 16.0).rgb;
	vec3 rock_tex_b = texture(cliff_rock_texture, p_norm.yx * 8.0 + vec2(0.35, 0.15)).rgb;
	vec3 rock_tex = mix(rock_tex_a, rock_tex_b, 0.45);

	// 2. Biome Blends
	// Beasthuman Taiga (Red): pine-olive steppe with slate stone outcrops
	vec3 taiga_surf = mix(BEAST_TAIGA_GROUND, BEAST_TAIGA_GROUND * 1.22, clamp(n_mid * 1.4 + 0.5, 0.0, 1.0));
	float outcrop = smoothstep(0.10, 0.28, n_micro + n_macro * 0.45);
	vec3 slate_rock = mix(BEAST_SLATE, rock_tex * 0.65, 0.35 * detail);
	taiga_surf = mix(taiga_surf, slate_rock, outcrop * 0.80);
	vec3 surface_color = mix(grass_color, taiga_surf, splat.r * 0.85);

	// Elf Highlands (Green): lush deep teal-emerald sylvan moss
	vec3 elf_surf = mix(ELF_SYLVAN_MOSS, ELF_DEEP_TEAL, clamp(n_mid * 1.8 + 0.5, 0.0, 1.0));
	elf_surf *= 1.0 + n_micro * 0.10;
	surface_color = mix(surface_color, elf_surf, splat.g * 0.90);

	// Dragon Peaks (Blue): basalt ridges & rocky strata
	float dragon_mask = splat.b;
	float ridge = clamp(1.0 - abs(n_mid * 2.6), 0.0, 1.0);
	vec3 dragon_surf = mix(DRAGON_OBSIDIAN, DRAGON_BASALT_LIGHT, ridge * ridge);
	dragon_surf = mix(dragon_surf, rock_tex * 0.40, 0.30 * detail);
	surface_color = mix(surface_color, dragon_surf, dragon_mask);

	// Demon Ashlands (Alpha): dark volcanic charcoal
	float demon_mask = splat.a;
	vec3 demon_surf = mix(DEMON_ASHLAND, ROCK_DARK * 0.65, clamp(n_macro * 0.7 + 0.4, 0.0, 1.0));
	surface_color = mix(surface_color, demon_surf, demon_mask);

	// Volcanic & Abyssal Fissure Glow (distance-stabilized)
	vec3 fissure_emission = vec3(0.0);
	float fissure_signal = smoothstep(0.30, 0.42, abs(n_mid + n_micro * 0.35)) * (0.4 + 0.6 * detail);
	if (dragon_mask > 0.35 && fissure_signal > 0.01) {
		float glow_intensity = (dragon_mask - 0.35) * fissure_signal * 1.25;
		surface_color = mix(surface_color, DRAGON_FISSURE_GLOW, clamp(glow_intensity, 0.0, 0.85));
		fissure_emission += DRAGON_FISSURE_GLOW * glow_intensity * 0.65;
	}
	if (demon_mask > 0.40 && fissure_signal > 0.01) {
		float glow_intensity = (demon_mask - 0.40) * fissure_signal * 1.25;
		vec3 fiss = mix(DEMON_FISSURE_VIOLET, DEMON_FISSURE_CRIMSON, clamp(n_macro * 2.0 + 0.5, 0.0, 1.0));
		surface_color = mix(surface_color, fiss, clamp(glow_intensity, 0.0, 0.85));
		fissure_emission += fiss * glow_intensity * 0.60;
	}

	// 3. Exposed Stone & Cliff Rock on Steep Slopes (NORMAL.y < 0.76)
	if (slope_y < 0.76) {
		float cliff_blend = smoothstep(0.76, 0.54, slope_y);
		vec3 cliff_base = mix(ROCK_CLIFF, ROCK_DARK, clamp(n_mid * 0.8 + 0.5, 0.0, 1.0));
		vec3 cliff_col = mix(cliff_base, rock_tex * 0.78, 0.45);
		surface_color = mix(surface_color, cliff_col, cliff_blend);
	}

	// 4. Coastal Sand (0m .. 4.5m) and Riverbed Gravel (y < 0.0m)
	if (h < 4.5) {
		if (h >= 0.0) {
			float sand_blend = smoothstep(4.5, 0.5, h);
			vec3 sand_color = mix(SAND_SHORE, SAND_WET, clamp(n_mid * 0.7 + 0.4, 0.0, 1.0));
			sand_color *= 1.0 + n_micro * 0.08;
			surface_color = mix(surface_color, sand_color, sand_blend * 0.95);
		} else {
			float gravel_blend = smoothstep(0.0, -3.0, h);
			vec3 wet_gravel = mix(SAND_WET, GRAVEL_RIVERBED, clamp(gravel_blend + n_mid * 0.3, 0.0, 1.0));
			surface_color = mix(surface_color, wet_gravel, 0.95);
		}
	}

	// 5. Real Mipmapped PBR Cobblestone Roads & Imperial Plaza Flagstones
	vec3 out_normal_map = vec3(0.5, 0.5, 1.0);
	float road_norm_weight = 0.0;
	float road_roughness_mix = 0.0;

	if (road_val > 0.02) {
		// Exact integer repeats across 512m tile (512 * 0.25 = 128 repeats -> zero seams)
		vec2 cobble_uv = p * 0.25;
		vec2 plaza_uv = p * 0.25;

		vec3 dirt_col = mix(ROAD_DIRT, ROAD_DIRT_LIGHT, clamp(n_mid * 1.2 + 0.5, 0.0, 1.0));
		dirt_col *= 1.0 + n_micro * 0.10;

		vec3 road_tex_alb = texture(road_albedo_texture, cobble_uv).rgb * ROAD_STONE_TINT;
		vec3 road_tex_nrm = texture(road_normal_texture, cobble_uv).rgb;

		vec3 plaza_tex_alb = texture(plaza_albedo_texture, plaza_uv).rgb * PLAZA_STONE_TINT;
		vec3 plaza_tex_nrm = texture(plaza_normal_texture, plaza_uv).rgb;

		float stone_mask = smoothstep(0.34, 0.52, road_val);
		float plaza_mask = smoothstep(0.86, 0.97, road_val);

		vec3 road_col = mix(dirt_col, road_tex_alb, stone_mask);
		road_col = mix(road_col, plaza_tex_alb, plaza_mask);

		vec3 stone_nrm = mix(road_tex_nrm, plaza_tex_nrm, plaza_mask);
		float road_alpha = smoothstep(0.02, 0.20, road_val);

		surface_color = mix(surface_color, road_col, road_alpha);
		road_norm_weight = stone_mask * road_alpha * detail;
		out_normal_map = normalize(mix(vec3(0.5, 0.5, 1.0), stone_nrm, road_norm_weight));
		road_roughness_mix = road_alpha * mix(0.25, 1.0, stone_mask);
	}

	// 6. Alpine Snowcaps (y > 85m)
	if (h > 85.0) {
		float snowcap_factor = smoothstep(85.0, 118.0, h);
		float snow_slope = smoothstep(0.50, 0.80, slope_y);
		surface_color = mix(surface_color, SNOW_COLOR, snowcap_factor * snow_slope * 0.92);
	}

	// 7. Winter Seasonal Snow Accumulation
	float winter_factor = 0.0;
	if (prog >= 2.5 && prog < 3.5) {
		winter_factor = clamp(1.0 - abs(prog - 3.0) * 2.0, 0.0, 1.0);
	}
	if (winter_factor > 0.01) {
		float top_facing = clamp(slope_y, 0.0, 1.0);
		float snow_cov = smoothstep(0.42, 0.72, top_facing) * winter_factor;
		snow_cov *= (1.0 - dragon_mask * 0.7) * (1.0 - demon_mask * 0.6);
		surface_color = mix(surface_color, SNOW_COLOR, snow_cov * 0.88);
	}

	ALBEDO = clamp(surface_color, vec3(0.0), vec3(1.0));
	NORMAL_MAP = out_normal_map;
	NORMAL_MAP_DEPTH = 0.85 * road_norm_weight;
	EMISSION = fissure_emission;
	ROUGHNESS = mix(0.90, 0.62, road_roughness_mix);
	SPECULAR = mix(0.10, 0.28, road_roughness_mix);
}
