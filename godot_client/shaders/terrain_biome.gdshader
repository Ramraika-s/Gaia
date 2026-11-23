shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_toon, specular_toon;

// Global uniform driven by SkyWeatherController and Python WORLD_TIME_WEATHER
global uniform float season_progress = 0.0;

uniform sampler2D heightmap_texture : hint_default_black, filter_linear;
uniform sampler2D biome_splat_texture : hint_default_black, filter_linear;
uniform sampler2D road_mask_texture : hint_default_black, filter_linear;
uniform bool is_raw_float_meters = true;
uniform float max_height_meters = 180.0;
uniform float min_height_meters = -25.0;
uniform vec2 world_size = vec2(8000.0, 8000.0);

// Cel Shading & Rim
uniform float cel_shadow_threshold : hint_range(0.0, 1.0) = 0.45;
uniform float cel_shadow_softness : hint_range(0.0, 0.5) = 0.05;
uniform vec4 shadow_tint : source_color = vec4(0.35, 0.38, 0.48, 1.0);
uniform float rim_threshold : hint_range(0.0, 1.0) = 0.65;
uniform float rim_softness : hint_range(0.0, 0.5) = 0.10;

// Surface Color Palettes
// 1. Plains / Basin Grass Layers
const vec3 GRASS_BASE_SPRING = vec3(0.24, 0.46, 0.18);
const vec3 GRASS_HIGHLIGHT_SPRING = vec3(0.38, 0.62, 0.24);
const vec3 GRASS_DARK_SPRING = vec3(0.15, 0.30, 0.12);

const vec3 GRASS_BASE_SUMMER = vec3(0.22, 0.42, 0.16);
const vec3 GRASS_HIGHLIGHT_SUMMER = vec3(0.34, 0.56, 0.22);

const vec3 GRASS_BASE_AUTUMN = vec3(0.65, 0.42, 0.15);
const vec3 GRASS_HIGHLIGHT_AUTUMN = vec3(0.82, 0.56, 0.20);

const vec3 GRASS_BASE_WINTER = vec3(0.55, 0.52, 0.45);
const vec3 GRASS_HIGHLIGHT_WINTER = vec3(0.68, 0.65, 0.58);

// 2. Roads & Plazas
const vec3 ROAD_PAVER = vec3(0.58, 0.54, 0.48);
const vec3 ROAD_DIRT = vec3(0.38, 0.32, 0.23);

// 3. Sandy Shores & Riverbeds
const vec3 SAND_SHORE = vec3(0.78, 0.71, 0.52);
const vec3 SAND_WET = vec3(0.48, 0.42, 0.30);
const vec3 GRAVEL_RIVERBED = vec3(0.32, 0.30, 0.28);

// 4. Exposed Cliff Rock & Steep Slopes
const vec3 ROCK_CLIFF = vec3(0.38, 0.38, 0.40);
const vec3 ROCK_DARK = vec3(0.24, 0.24, 0.26);

// 5. Dragon Volcanic Basalt & Glowing Magma
const vec3 DRAGON_OBSIDIAN = vec3(0.12, 0.10, 0.14);
const vec3 DRAGON_FISSURE_GLOW = vec3(1.0, 0.38, 0.08);

// 6. Demon Ash & Abyssal Purple Fissures
const vec3 DEMON_ASHLAND = vec3(0.14, 0.12, 0.16);
const vec3 DEMON_FISSURE_GLOW = vec3(0.75, 0.18, 0.95);

// 7. Elf Sylvan Highlands
const vec3 ELF_SYLVAN_MOSS = vec3(0.16, 0.48, 0.30);

// 8. Alpine Snowcaps & Winter Snow
const vec3 SNOW_COLOR = vec3(0.94, 0.97, 1.00);

varying vec3 v_world_pos;
varying vec3 v_world_normal;
varying vec2 v_splat_uv;

// Procedural Noise Functions
vec2 hash2(vec2 p) {
	p = vec2(dot(p, vec2(127.1, 311.7)), dot(p, vec2(269.5, 183.3)));
	return -1.0 + 2.0 * fract(sin(p) * 43758.5453123);
}

float gnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(
		mix(dot(hash2(i + vec2(0.0, 0.0)), f - vec2(0.0, 0.0)),
		    dot(hash2(i + vec2(1.0, 0.0)), f - vec2(1.0, 0.0)), u.x),
		mix(dot(hash2(i + vec2(0.0, 1.0)), f - vec2(0.0, 1.0)),
		    dot(hash2(i + vec2(1.0, 1.0)), f - vec2(1.0, 1.0)), u.x),
		u.y
	);
}

float fbm(vec2 p) {
	float f = 0.0;
	f += 0.5000 * gnoise(p); p *= 2.02;
	f += 0.2500 * gnoise(p); p *= 2.03;
	f += 0.1250 * gnoise(p);
	return f;
}

float sample_height_meters(vec2 uv) {
	float raw_val = texture(heightmap_texture, uv).r;
	return is_raw_float_meters ? raw_val : (min_height_meters + raw_val * (max_height_meters - min_height_meters));
}

void vertex() {
	vec2 uv = (vec2(VERTEX.x, VERTEX.z) + world_size * 0.5) / world_size;
	v_splat_uv = uv;

	// Exact Heightmap Displacement
	float h = sample_height_meters(uv);
	VERTEX.y = h;

	// Recompute true normal from 1024x1024 heightmap gradient
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

	NORMAL = normal;
	v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_world_normal = normalize((MODEL_MATRIX * vec4(normal, 0.0)).xyz);
}

void fragment() {
	vec4 splat = texture(biome_splat_texture, v_splat_uv);
	float road_val = texture(road_mask_texture, v_splat_uv).r;
	float slope_y = clamp(v_world_normal.y, 0.0, 1.0);
	vec2 p = v_world_pos.xz;
	float h = v_world_pos.y;

	// Multi-octave procedural noise for fine surface detail
	float n_macro = fbm(p * 0.008);
	float n_micro = fbm(p * 0.12);

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

	// Layered grass: blend highlight blades and dark hollows
	vec3 grass_color = mix(g_base, g_high, clamp(n_micro * 0.6 + 0.3, 0.0, 1.0));
	grass_color = mix(grass_color, GRASS_DARK_SPRING, clamp(-n_macro * 0.4, 0.0, 1.0));

	// 2. Biome Blends
	// Elf Sylvan Moss (Green channel)
	vec3 surface_color = mix(grass_color, ELF_SYLVAN_MOSS, splat.g * 0.85);

	// Dragon Obsidian (Blue channel)
	float dragon_mask = splat.b;
	vec3 dragon_surf = mix(DRAGON_OBSIDIAN, ROCK_DARK, n_micro * 0.5 + 0.5);
	surface_color = mix(surface_color, dragon_surf, dragon_mask);

	// Demon Ashland (Alpha channel)
	float demon_mask = splat.a;
	vec3 demon_surf = mix(DEMON_ASHLAND, ROCK_DARK, n_macro * 0.5 + 0.5);
	surface_color = mix(surface_color, demon_surf, demon_mask);

	// Fissure Glow (volcanic / abyssal cracks)
	vec3 fissure_emission = vec3(0.0);
	float crack = step(0.48, abs(n_micro));
	if (dragon_mask > 0.35 && crack > 0.5) {
		float glow_intensity = (dragon_mask - 0.35) * 1.5;
		surface_color = mix(surface_color, DRAGON_FISSURE_GLOW, glow_intensity);
		fissure_emission += DRAGON_FISSURE_GLOW * glow_intensity * 0.75;
	}
	if (demon_mask > 0.40 && crack > 0.5) {
		float glow_intensity = (demon_mask - 0.40) * 1.5;
		surface_color = mix(surface_color, DEMON_FISSURE_GLOW, glow_intensity);
		fissure_emission += DEMON_FISSURE_GLOW * glow_intensity * 0.65;
	}

	// 3. Exposed Stone & Cliff Rock on Steep Slopes (NORMAL.y < 0.75)
	if (slope_y < 0.75) {
		float cliff_blend = smoothstep(0.75, 0.55, slope_y);
		vec3 rock_color = mix(ROCK_CLIFF, ROCK_DARK, n_micro * 0.5 + 0.5);
		surface_color = mix(surface_color, rock_color, cliff_blend);
	}

	// 4. Coastal Sand (0m .. 4.5m) and Riverbed Gravel (y < 0.0m)
	if (h < 4.5) {
		if (h >= 0.0) {
			// Warm sandy beach
			float sand_blend = smoothstep(4.5, 0.5, h);
			vec3 sand_color = mix(SAND_SHORE, SAND_WET, clamp(n_micro * 0.5 + 0.5, 0.0, 1.0));
			surface_color = mix(surface_color, sand_color, sand_blend * 0.95);
		} else {
			// Submerged riverbed / seabed gravel
			float gravel_blend = smoothstep(0.0, -3.0, h);
			vec3 wet_gravel = mix(SAND_WET, GRAVEL_RIVERBED, clamp(gravel_blend + n_micro * 0.3, 0.0, 1.0));
			surface_color = mix(surface_color, wet_gravel, 0.95);
		}
	}

	// 5. Cobblestone Roads & Plazas (from road_mask_texture)
	if (road_val > 0.02) {
		float paver_tile = fbm(p * 0.45);
		vec3 road_color = mix(ROAD_DIRT, ROAD_PAVER, clamp(paver_tile * 0.7 + 0.3, 0.0, 1.0));
		surface_color = mix(surface_color, road_color, road_val);
	}

	// 6. Alpine Snowcaps (y > 95m)
	if (h > 95.0) {
		float snowcap_factor = smoothstep(95.0, 125.0, h);
		// Resist snow on vertical cliffs
		float snow_slope = smoothstep(0.50, 0.80, slope_y);
		surface_color = mix(surface_color, SNOW_COLOR, snowcap_factor * snow_slope * 0.95);
	}

	// 7. Winter Seasonal Snow Accumulation
	float winter_factor = 0.0;
	if (prog >= 2.5 && prog < 3.5) {
		winter_factor = 1.0 - abs(prog - 3.0) * 2.0;
		winter_factor = clamp(winter_factor, 0.0, 1.0);
	}
	if (winter_factor > 0.01) {
		float top_facing = clamp(slope_y, 0.0, 1.0);
		float snow_cov = smoothstep(0.42, 0.72, top_facing) * winter_factor;
		// Cliffs and magma fissures resist snow
		snow_cov *= (1.0 - dragon_mask * 0.7) * (1.0 - demon_mask * 0.6);
		surface_color = mix(surface_color, SNOW_COLOR, snow_cov * 0.90);
	}

	ALBEDO = surface_color;
	EMISSION = fissure_emission;
	ROUGHNESS = mix(0.85, 0.45, road_val);
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

	// Subtle rim light on edges
	float NdotV = 1.0 - dot(NORMAL, VIEW);
	float rim = smoothstep(
		rim_threshold - rim_softness,
		rim_threshold + rim_softness,
		NdotV * NdotL
	);
	vec3 rim_color = rim * LIGHT_COLOR * 0.20;

	DIFFUSE_LIGHT += ALBEDO * light_color + rim_color;
}
