# 3D Asset Catalog & Modular Architecture Dimensions Summary

This document provides exact local-space AABB measurements for all **565** 3D assets in the Gaia Engine Godot client.
Generated directly from mesh geometries via headless Godot 4.7.2 AST traversal (`godot_client/assets/ASSET_AABBS.json`).

## Modular Snapping Architecture Summary

- **Village Modular Grid:** Standard tile width is **2.000m**. Wall modules stand **3.123m** high with thickness **0.406m**. Floor tiles are **2.000m × 2.000m** with **0.020m** slab thickness (`min_y = -0.010m`). Balconies and half-tiles align to **1.000m** or **2.000m**. Roofs have standard spans of **2m**, **4m**, **6m**, and **8m**.
- **Dungeon Modular Grid:** Standard tile unit is **4.000m**. Wall pieces are **4.000m wide × 4.000m high × 1.000m deep** (`min_y = 0.000m`), with half-walls at **2.000m** width and corner units at **2.500m × 2.500m**. Large floor slabs are **4.000m × 4.000m**, and small slabs are **2.000m × 2.000m**.
- **Deities & Mortals:** Humanoid rigs stand between **1.60m** and **1.85m** tall (`min_y ≈ 0.00m` at ground pivot). True Dragon spans **3.602m wide × 2.476m high × 0.377m deep**.
- **Centering Convention:** An asset marked `Yes` is centered on both X and Z (`|center| < 0.05m`). `X-only` or `Z-only` indicates one axis is centered while the other is offset or flush. `No (corner)` indicates a corner pivot.

---

## Village Walls & Doors (38 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `corner_exterior_brick.gltf` | `0.531 × 3.016 × 0.576` | `-0.007` | No (corner) |
| `corner_exterior_top_down.gltf` | `0.093 × 2.467 × 0.093` | `0.650` | Yes |
| `corner_exterior_top_only.gltf` | `0.093 × 0.234 × 0.093` | `2.883` | Yes |
| `corner_exterior_wide_brick.gltf` | `0.712 × 3.043 × 0.756` | `-0.019` | No (corner) |
| `corner_exterior_wide_wood.gltf` | `0.290 × 3.000 × 0.331` | `0.000` | Yes |
| `corner_exterior_wood.gltf` | `0.210 × 3.000 × 0.240` | `0.000` | Yes |
| `corner_interior_big.gltf` | `0.333 × 3.000 × 0.368` | `0.000` | No (corner) |
| `corner_interior_small.gltf` | `0.210 × 3.000 × 0.240` | `0.000` | No (corner) |
| `door_1_flat.gltf` | `1.118 × 2.100 × 0.121` | `0.035` | Z-only |
| `door_1_round.gltf` | `1.120 × 2.318 × 0.121` | `0.033` | Z-only |
| `door_2_flat.gltf` | `1.114 × 2.100 × 0.261` | `0.040` | Z-only |
| `door_2_round.gltf` | `1.115 × 2.327 × 0.261` | `0.028` | Z-only |
| `door_4_flat.gltf` | `1.118 × 2.092 × 0.209` | `0.035` | Z-only |
| `door_4_round.gltf` | `1.115 × 2.323 × 0.209` | `0.033` | Z-only |
| `door_8_flat.gltf` | `1.118 × 2.099 × 0.199` | `0.035` | Z-only |
| `door_8_round.gltf` | `1.152 × 2.324 × 0.199` | `0.033` | Z-only |
| `door_frame_flat_brick.gltf` | `1.575 × 2.376 × 0.494` | `-0.002` | Yes |
| `door_frame_flat_wood_dark.gltf` | `1.574 × 2.312 × 0.388` | `-0.009` | Yes |
| `door_frame_round_brick.gltf` | `1.603 × 2.586 × 0.477` | `-0.002` | X-only |
| `door_frame_round_wood_dark.gltf` | `1.407 × 2.563 × 0.539` | `-0.009` | Yes |
| `overhang_plaster_corner.gltf` | `3.101 × 3.117 × 3.101` | `0.000` | No (corner) |
| `overhang_plaster_corner_front.gltf` | `3.118 × 3.140 × 3.118` | `-0.023` | No (corner) |
| `overhang_uneven_brick_corner.gltf` | `3.101 × 3.117 × 3.101` | `0.000` | No (corner) |
| `overhang_uneven_brick_corner_front.gltf` | `3.118 × 3.117 × 3.118` | `0.000` | No (corner) |
| `prop_exterior_border_corner.gltf` | `0.700 × 0.134 × 0.700` | `0.000` | No (corner) |
| `wall_arch.gltf` | `2.000 × 3.000 × 0.064` | `0.000` | Yes |
| `wall_bottom_cover.gltf` | `2.000 × 0.238 × 0.432` | `-0.117` | X-only |
| `wall_plaster_door_flat.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_plaster_door_round.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_plaster_door_round_inset.gltf` | `2.000 × 3.123 × 1.092` | `0.000` | X-only |
| `wall_plaster_straight.gltf` | `2.000 × 3.125 × 0.406` | `-0.002` | X-only |
| `wall_plaster_straight_base.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_plaster_straight_l.gltf` | `2.002 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_plaster_straight_r.gltf` | `2.002 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_plaster_wood_grid.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_uneven_brick_door_flat.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_uneven_brick_door_round.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_uneven_brick_straight.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |

## Village Windows & Shutters (21 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `wall_plaster_window_thin_round.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_plaster_window_wide_flat.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_plaster_window_wide_flat2.gltf` | `2.000 × 3.146 × 0.406` | `-0.023` | X-only |
| `wall_plaster_window_wide_round.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_uneven_brick_window_thin_round.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_uneven_brick_window_wide_flat.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `wall_uneven_brick_window_wide_round.gltf` | `2.000 × 3.123 × 0.406` | `0.000` | X-only |
| `window_roof_thin.gltf` | `0.852 × 1.177 × 1.179` | `1.338` | X-only |
| `window_roof_wide.gltf` | `1.416 × 1.181 × 1.179` | `1.338` | X-only |
| `window_shutters_thin_flat_closed.gltf` | `0.852 × 1.424 × 0.136` | `1.093` | X-only |
| `window_shutters_thin_flat_open.gltf` | `1.354 × 1.424 × 0.377` | `1.093` | X-only |
| `window_shutters_thin_round_closed.gltf` | `0.867 × 1.518 × 0.136` | `1.093` | X-only |
| `window_shutters_thin_round_open.gltf` | `1.606 × 1.518 × 0.376` | `1.093` | X-only |
| `window_shutters_wide_flat_closed.gltf` | `1.347 × 1.424 × 0.136` | `1.093` | X-only |
| `window_shutters_wide_flat_open.gltf` | `2.481 × 1.424 × 0.457` | `1.093` | X-only |
| `window_shutters_wide_round_closed.gltf` | `1.347 × 1.647 × 0.136` | `1.093` | X-only |
| `window_shutters_wide_round_open.gltf` | `2.303 × 1.647 × 0.472` | `1.093` | X-only |
| `window_thin_flat1.gltf` | `0.788 × 1.558 × 0.436` | `0.975` | Yes |
| `window_thin_round1.gltf` | `0.888 × 1.605 × 0.344` | `1.016` | X-only |
| `window_wide_flat1.gltf` | `1.608 × 1.580 × 0.683` | `0.944` | X-only |
| `window_wide_round1.gltf` | `1.365 × 1.726 × 0.530` | `1.016` | Yes |

## Village Roofs (45 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `overhang_roof_incline_plaster.gltf` | `2.000 × 0.266 × 1.430` | `-0.324` | X-only |
| `overhang_roof_incline_uneven_bricks.gltf` | `2.000 × 0.266 × 1.430` | `-0.324` | X-only |
| `overhang_roof_plaster.gltf` | `2.000 × 0.266 × 2.022` | `-0.324` | Yes |
| `overhang_roof_uneven_bricks.gltf` | `2.000 × 0.266 × 2.022` | `-0.324` | Yes |
| `prop_chimney.gltf` | `0.946 × 3.178 × 1.000` | `0.000` | Yes |
| `prop_chimney2.gltf` | `0.946 × 3.000 × 0.988` | `0.000` | Yes |
| `roof_2x4_round_tile.gltf` | `3.293 × 2.666 × 4.232` | `-0.342` | Yes |
| `roof_dormer_round_tile.gltf` | `1.966 × 2.673 × 2.439` | `0.030` | Z-only |
| `roof_front_brick2.gltf` | `2.607 × 1.775 × 0.751` | `-0.133` | Yes |
| `roof_front_brick4.gltf` | `4.400 × 3.069 × 1.129` | `-0.132` | X-only |
| `roof_front_brick4_half_l.gltf` | `2.410 × 3.197 × 0.490` | `-0.132` | No (corner) |
| `roof_front_brick4_half_r.gltf` | `2.416 × 3.197 × 0.490` | `-0.132` | No (corner) |
| `roof_front_brick6.gltf` | `6.694 × 4.516 × 1.129` | `-0.132` | X-only |
| `roof_front_brick6_half_l.gltf` | `3.414 × 4.516 × 0.490` | `-0.132` | No (corner) |
| `roof_front_brick6_half_r.gltf` | `3.400 × 4.516 × 0.490` | `-0.132` | No (corner) |
| `roof_front_brick8.gltf` | `8.511 × 5.446 × 1.129` | `-0.132` | X-only |
| `roof_front_brick8_half_l.gltf` | `4.327 × 5.446 × 0.490` | `-0.132` | No (corner) |
| `roof_front_brick8_half_r.gltf` | `4.349 × 5.446 × 0.490` | `-0.132` | No (corner) |
| `roof_front_supports.gltf` | `5.486 × 0.231 × 0.655` | `-0.118` | X-only |
| `roof_log.gltf` | `1.149 × 1.387 × 10.696` | `3.849` | Yes |
| `roof_modular_round_tiles.gltf` | `0.663 × 0.505 × 2.252` | `0.006` | X-only |
| `roof_round_tile_2x1.gltf` | `3.297 × 2.659 × 1.952` | `-0.342` | X-only |
| `roof_round_tile_2x1_long.gltf` | `4.347 × 3.325 × 1.952` | `-1.008` | X-only |
| `roof_round_tiles_4x4.gltf` | `5.513 × 4.249 × 5.561` | `-0.516` | Yes |
| `roof_round_tiles_4x6.gltf` | `5.513 × 4.234 × 7.572` | `-0.516` | Yes |
| `roof_round_tiles_4x8.gltf` | `5.513 × 4.229 × 9.683` | `-0.516` | Yes |
| `roof_round_tiles_6x10.gltf` | `8.250 × 5.672 × 11.852` | `-0.782` | Yes |
| `roof_round_tiles_6x12.gltf` | `8.250 × 5.672 × 13.658` | `-0.782` | Yes |
| `roof_round_tiles_6x14.gltf` | `8.250 × 5.672 × 15.706` | `-0.782` | Yes |
| `roof_round_tiles_6x4.gltf` | `8.250 × 5.672 × 4.992` | `-0.782` | X-only |
| `roof_round_tiles_6x6.gltf` | `8.250 × 5.672 × 8.032` | `-0.782` | X-only |
| `roof_round_tiles_6x8.gltf` | `8.250 × 5.672 × 9.683` | `-0.782` | Yes |
| `roof_round_tiles_8x10.gltf` | `9.952 × 6.781 × 11.859` | `-0.780` | X-only |
| `roof_round_tiles_8x12.gltf` | `9.952 × 6.781 × 14.132` | `-0.780` | X-only |
| `roof_round_tiles_8x14.gltf` | `9.952 × 6.781 × 15.706` | `-0.780` | Yes |
| `roof_round_tiles_8x8.gltf` | `9.952 × 6.781 × 10.332` | `-0.780` | X-only |
| `roof_support2.gltf` | `0.200 × 0.743 × 0.765` | `-0.677` | X-only |
| `roof_tower_round_tiles.gltf` | `5.651 × 7.361 × 5.427` | `-0.572` | Yes |
| `roof_wooden_2x1.gltf` | `2.258 × 1.248 × 1.560` | `-0.161` | X-only |
| `roof_wooden_2x1_center.gltf` | `2.000 × 1.208 × 1.499` | `-0.145` | X-only |
| `roof_wooden_2x1_center_mirror.gltf` | `2.000 × 1.208 × 1.499` | `-0.145` | X-only |
| `roof_wooden_2x1_corner.gltf` | `1.544 × 1.183 × 1.557` | `-0.169` | No (corner) |
| `roof_wooden_2x1_l.gltf` | `2.129 × 1.248 × 1.560` | `-0.161` | No (corner) |
| `roof_wooden_2x1_middle.gltf` | `2.000 × 0.138 × 2.000` | `0.924` | Yes |
| `roof_wooden_2x1_r.gltf` | `2.129 × 1.248 × 1.560` | `-0.161` | No (corner) |

## Village Floors & Stairs (36 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `balcony_cross_corner.gltf` | `2.104 × 1.230 × 2.104` | `-0.105` | No (corner) |
| `balcony_cross_straight.gltf` | `2.000 × 1.230 × 0.206` | `-0.105` | X-only |
| `balcony_simple_corner.gltf` | `2.104 × 1.230 × 2.104` | `-0.105` | No (corner) |
| `balcony_simple_straight.gltf` | `2.000 × 1.230 × 0.206` | `-0.105` | X-only |
| `floor_brick.gltf` | `2.000 × 0.020 × 2.000` | `-0.010` | Yes |
| `floor_red_brick.gltf` | `2.000 × 0.020 × 2.000` | `-0.010` | Yes |
| `floor_uneven_brick.gltf` | `2.000 × 0.020 × 2.000` | `-0.010` | Yes |
| `floor_wood_dark.gltf` | `2.000 × 0.020 × 2.000` | `-0.010` | Yes |
| `floor_wood_dark_half1.gltf` | `1.000 × 0.020 × 2.000` | `-0.010` | Z-only |
| `floor_wood_dark_half2.gltf` | `1.000 × 0.020 × 2.000` | `-0.010` | Z-only |
| `floor_wood_dark_half3.gltf` | `2.000 × 0.020 × 1.000` | `-0.010` | X-only |
| `floor_wood_dark_overhang_corner.gltf` | `1.000 × 0.020 × 1.756` | `-0.010` | No (corner) |
| `floor_wood_dark_overhang_corner2.gltf` | `0.957 × 0.020 × 1.750` | `-0.010` | No (corner) |
| `floor_wood_light.gltf` | `2.000 × 0.020 × 2.000` | `-0.010` | Yes |
| `floor_wood_light_overhang_corner.gltf` | `1.000 × 0.020 × 1.756` | `-0.010` | No (corner) |
| `floor_wood_light_overhang_corner2.gltf` | `0.957 × 0.020 × 1.750` | `-0.010` | No (corner) |
| `hole_cover_90_stairs.gltf` | `0.324 × 0.210 × 2.120` | `-0.105` | No (corner) |
| `stair_interior_rails.gltf` | `1.717 × 3.931 × 4.563` | `0.023` | X-only |
| `stair_interior_simple.gltf` | `1.676 × 3.035 × 4.620` | `-0.010` | X-only |
| `stair_interior_solid.gltf` | `1.769 × 3.046 × 4.710` | `-0.018` | X-only |
| `stair_interior_solid_extended.gltf` | `1.769 × 3.046 × 6.158` | `-0.018` | X-only |
| `stairs_exterior_no_first_step.gltf` | `2.000 × 1.000 × 2.077` | `0.000` | Yes |
| `stairs_exterior_platform.gltf` | `2.000 × 1.000 × 2.001` | `0.000` | Yes |
| `stairs_exterior_platform45.gltf` | `2.001 × 1.000 × 2.001` | `0.000` | Yes |
| `stairs_exterior_platform45_clean.gltf` | `2.000 × 1.000 × 2.001` | `0.000` | Yes |
| `stairs_exterior_platform_u.gltf` | `2.000 × 1.000 × 2.001` | `0.000` | Yes |
| `stairs_exterior_side_platform.gltf` | `2.000 × 1.000 × 2.001` | `0.000` | Yes |
| `stairs_exterior_sides.gltf` | `2.000 × 1.000 × 2.000` | `0.000` | Yes |
| `stairs_exterior_sides45.gltf` | `2.000 × 1.000 × 2.000` | `0.000` | Yes |
| `stairs_exterior_sides_u.gltf` | `2.000 × 1.000 × 2.000` | `0.000` | Yes |
| `stairs_exterior_single_side.gltf` | `0.200 × 1.000 × 2.000` | `0.000` | Z-only |
| `stairs_exterior_single_side_thick.gltf` | `0.400 × 1.000 × 2.000` | `0.000` | Yes |
| `stairs_exterior_straight.gltf` | `2.000 × 1.204 × 2.078` | `-0.204` | Yes |
| `stairs_exterior_straight_center.gltf` | `2.000 × 1.022 × 2.078` | `-0.204` | Yes |
| `stairs_exterior_straight_l.gltf` | `2.000 × 1.204 × 2.078` | `-0.204` | Yes |
| `stairs_exterior_straight_r.gltf` | `2.000 × 1.204 × 2.078` | `-0.204` | Yes |

## Village Exterior Props (36 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `hole_cover_90_angle.gltf` | `2.120 × 0.210 × 2.120` | `-0.105` | No (corner) |
| `hole_cover_90_half.gltf` | `1.120 × 0.210 × 1.120` | `-0.105` | No (corner) |
| `hole_cover_straight.gltf` | `2.000 × 0.210 × 0.240` | `-0.105` | X-only |
| `hole_cover_straight_half.gltf` | `1.000 × 0.210 × 0.240` | `-0.105` | X-only |
| `overhang_plaster_long.gltf` | `2.000 × 3.028 × 2.200` | `0.000` | X-only |
| `overhang_plaster_short.gltf` | `2.000 × 3.123 × 1.323` | `0.000` | X-only |
| `overhang_side_plaster_long_l.gltf` | `0.479 × 6.117 × 2.314` | `0.000` | No (corner) |
| `overhang_side_plaster_long_r.gltf` | `0.479 × 6.117 × 2.314` | `0.000` | No (corner) |
| `overhang_side_plaster_short_l.gltf` | `0.479 × 6.117 × 1.437` | `0.000` | No (corner) |
| `overhang_side_plaster_short_r.gltf` | `0.479 × 6.117 × 1.437` | `0.000` | No (corner) |
| `overhang_side_uneven_brick_long_l.gltf` | `0.479 × 6.117 × 2.314` | `0.000` | No (corner) |
| `overhang_side_uneven_brick_long_r.gltf` | `0.479 × 6.117 × 2.314` | `0.000` | No (corner) |
| `overhang_side_uneven_brick_short_l.gltf` | `0.479 × 6.117 × 1.437` | `0.000` | No (corner) |
| `overhang_side_uneven_brick_short_r.gltf` | `0.479 × 6.117 × 1.437` | `0.000` | No (corner) |
| `overhang_uneven_brick_long.gltf` | `2.000 × 3.028 × 2.200` | `0.000` | X-only |
| `overhang_uneven_brick_short.gltf` | `2.000 × 3.123 × 1.323` | `0.000` | X-only |
| `prop_brick1.gltf` | `0.346 × 0.208 × 0.250` | `-0.110` | Yes |
| `prop_brick2.gltf` | `0.395 × 0.245 × 0.217` | `-0.112` | Yes |
| `prop_brick3.gltf` | `0.381 × 0.250 × 0.216` | `-0.115` | Yes |
| `prop_brick4.gltf` | `0.257 × 0.250 × 0.216` | `-0.115` | Yes |
| `prop_crate.gltf` | `1.084 × 1.060 × 1.084` | `0.003` | Yes |
| `prop_exterior_border_straight1.gltf` | `2.000 × 0.134 × 0.700` | `0.000` | X-only |
| `prop_exterior_border_straight2.gltf` | `2.000 × 0.134 × 0.700` | `0.000` | X-only |
| `prop_metal_fence_ornament.gltf` | `1.952 × 2.852 × 0.156` | `0.000` | Yes |
| `prop_metal_fence_simple.gltf` | `1.949 × 2.868 × 0.156` | `0.000` | Yes |
| `prop_support.gltf` | `0.199 × 1.709 × 2.036` | `1.211` | X-only |
| `prop_vine1.gltf` | `1.536 × 2.603 × 0.219` | `-2.121` | X-only |
| `prop_vine2.gltf` | `1.386 × 2.603 × 0.214` | `-2.121` | No (corner) |
| `prop_vine4.gltf` | `1.017 × 1.588 × 0.150` | `-1.014` | Z-only |
| `prop_vine5.gltf` | `2.301 × 2.986 × 1.126` | `-1.955` | No (corner) |
| `prop_vine6.gltf` | `4.137 × 2.468 × 1.470` | `-1.072` | X-only |
| `prop_vine9.gltf` | `4.137 × 1.467 × 1.470` | `-0.633` | Yes |
| `prop_wagon.gltf` | `1.951 × 1.529 × 4.024` | `0.003` | X-only |
| `prop_wooden_fence_extension1.gltf` | `2.045 × 0.838 × 0.110` | `-0.028` | Yes |
| `prop_wooden_fence_extension2.gltf` | `2.027 × 0.838 × 0.110` | `-0.028` | Yes |
| `prop_wooden_fence_single.gltf` | `2.064 × 0.838 × 0.120` | `-0.028` | Yes |

## Dungeon Walls/Arches/Pillars/Stairs (128 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `barrel_large.gltf` | `1.800 × 2.000 × 1.800` | `0.000` | Yes |
| `barrel_large_decorated.gltf` | `1.938 × 2.556 × 1.855` | `-0.002` | Yes |
| `barrel_small.gltf` | `1.001 × 1.018 × 1.001` | `0.000` | Yes |
| `barrel_small_stack.gltf` | `1.850 × 1.770 × 1.000` | `0.000` | Yes |
| `barrier.gltf` | `4.000 × 1.100 × 0.500` | `0.000` | Yes |
| `barrier_colum_half.gltf` | `2.350 × 1.400 × 0.700` | `0.000` | Z-only |
| `barrier_column.gltf` | `4.000 × 1.400 × 0.700` | `0.000` | Yes |
| `barrier_corner.gltf` | `2.395 × 1.400 × 2.395` | `0.000` | No (corner) |
| `barrier_half.gltf` | `2.000 × 1.100 × 0.500` | `0.000` | Z-only |
| `bed_decorated.gltf` | `2.606 × 1.701 × 3.057` | `0.000` | Z-only |
| `bed_frame.gltf` | `1.500 × 1.063 × 3.000` | `0.000` | Yes |
| `bottle_a_brown.gltf` | `0.368 × 0.886 × 0.368` | `0.000` | Yes |
| `bottle_a_green.gltf` | `0.368 × 0.886 × 0.368` | `0.000` | Yes |
| `bottle_a_labeled_brown.gltf` | `0.368 × 0.886 × 0.368` | `0.000` | Yes |
| `bottle_a_labeled_green.gltf` | `0.368 × 0.886 × 0.368` | `0.000` | Yes |
| `bottle_b_brown.gltf` | `0.553 × 0.886 × 0.553` | `0.000` | Yes |
| `bottle_b_green.gltf` | `0.553 × 0.886 × 0.553` | `0.000` | Yes |
| `bottle_c_brown.gltf` | `0.737 × 0.906 × 0.737` | `0.000` | Yes |
| `bottle_c_green.gltf` | `0.737 × 0.906 × 0.737` | `0.000` | Yes |
| `box_large.gltf` | `1.500 × 1.500 × 1.500` | `0.000` | Yes |
| `box_small.gltf` | `1.000 × 1.000 × 1.000` | `0.000` | Yes |
| `box_small_decorated.gltf` | `1.490 × 1.483 × 1.487` | `0.000` | No (corner) |
| `box_stacked.gltf` | `3.475 × 3.309 × 3.635` | `0.000` | Yes |
| `candle.gltf` | `0.334 × 0.873 × 0.329` | `0.000` | Yes |
| `candle_lit.gltf` | `0.334 × 1.051 × 0.329` | `0.000` | Yes |
| `candle_melted.gltf` | `0.334 × 0.702 × 0.329` | `0.000` | Yes |
| `candle_thin.gltf` | `0.193 × 0.873 × 0.190` | `0.000` | Yes |
| `candle_thin_lit.gltf` | `0.193 × 1.051 × 0.190` | `0.000` | Yes |
| `candle_triple.gltf` | `0.501 × 0.873 × 0.390` | `0.000` | Z-only |
| `chair.gltf` | `0.750 × 1.227 × 0.750` | `0.000` | Yes |
| `chest.gltf` | `1.700 × 1.300 × 1.446` | `0.000` | Yes |
| `chest_gold.gltf` | `1.700 × 1.300 × 1.446` | `0.000` | Yes |
| `coin.gltf` | `0.360 × 0.125 × 0.360` | `-0.063` | Yes |
| `coin_stack_large.gltf` | `1.436 × 1.157 × 1.659` | `0.000` | Yes |
| `coin_stack_medium.gltf` | `0.993 × 0.641 × 1.034` | `0.000` | Z-only |
| `coin_stack_small.gltf` | `0.959 × 0.478 × 0.896` | `0.000` | Yes |
| `column.gltf` | `0.700 × 1.400 × 0.700` | `0.000` | Yes |
| `crates_stacked.gltf` | `2.089 × 2.142 × 2.249` | `0.000` | Yes |
| `keg.gltf` | `1.800 × 2.051 × 2.000` | `0.000` | Yes |
| `keg_decorated.gltf` | `3.519 × 2.051 × 2.000` | `0.000` | Z-only |
| `key.gltf` | `0.896 × 0.403 × 0.142` | `-0.201` | Z-only |
| `keyring.gltf` | `1.031 × 0.261 × 1.209` | `-0.020` | No (corner) |
| `keyring_hanging.gltf` | `0.680 × 1.220 × 0.383` | `-1.196` | Yes |
| `pillar.gltf` | `1.500 × 4.000 × 1.500` | `0.000` | Yes |
| `pillar_decorated.gltf` | `2.232 × 4.000 × 1.710` | `0.000` | X-only |
| `rubble_half.gltf` | `4.000 × 3.500 × 3.000` | `0.000` | Z-only |
| `rubble_large.gltf` | `8.129 × 3.496 × 3.183` | `0.000` | Yes |
| `shelf_large.gltf` | `2.000 × 0.450 × 0.500` | `-0.350` | X-only |
| `shelf_small.gltf` | `1.000 × 0.400 × 0.500` | `-0.300` | X-only |
| `shelf_small_candles.gltf` | `1.000 × 0.994 × 0.500` | `-0.300` | X-only |
| `shelves.gltf` | `2.000 × 1.950 × 0.500` | `0.750` | X-only |
| `stairs.gltf` | `5.000 × 5.100 × 4.000` | `0.000` | X-only |
| `stairs_long.gltf` | `5.000 × 5.100 × 8.000` | `0.000` | X-only |
| `stairs_long_modular_center.gltf` | `2.000 × 4.000 × 8.000` | `0.000` | X-only |
| `stairs_long_modular_left.gltf` | `1.500 × 5.100 × 8.000` | `0.000` | No (corner) |
| `stairs_long_modular_right.gltf` | `1.500 × 5.100 × 8.000` | `0.000` | No (corner) |
| `stairs_modular_center.gltf` | `2.000 × 4.000 × 4.000` | `0.000` | X-only |
| `stairs_modular_left.gltf` | `1.500 × 5.100 × 4.000` | `0.000` | No (corner) |
| `stairs_modular_right.gltf` | `1.500 × 5.100 × 4.000` | `0.000` | No (corner) |
| `stairs_narrow.gltf` | `4.000 × 5.100 × 4.000` | `0.000` | X-only |
| `stairs_wall_left.gltf` | `4.000 × 5.100 × 5.000` | `0.000` | X-only |
| `stairs_wall_right.gltf` | `4.000 × 5.100 × 5.000` | `0.000` | X-only |
| `stairs_walled.gltf` | `5.000 × 4.000 × 4.000` | `0.000` | X-only |
| `stairs_wide.gltf` | `7.000 × 5.100 × 4.000` | `0.000` | X-only |
| `stairs_wood.gltf` | `3.300 × 4.050 × 6.000` | `0.000` | X-only |
| `stairs_wood_decorated.gltf` | `3.300 × 4.050 × 6.000` | `0.000` | X-only |
| `stool.gltf` | `0.750 × 0.500 × 0.750` | `0.000` | Yes |
| `sword_shield.gltf` | `2.232 × 1.667 × 0.336` | `-0.815` | X-only |
| `sword_shield_broken.gltf` | `1.426 × 1.962 × 0.336` | `-0.793` | X-only |
| `sword_shield_gold.gltf` | `2.232 × 1.667 × 0.336` | `-0.815` | X-only |
| `table_long.gltf` | `2.000 × 1.000 × 4.000` | `0.000` | Yes |
| `table_long_broken.gltf` | `2.409 × 1.266 × 4.405` | `0.000` | Z-only |
| `table_long_decorated_a.gltf` | `2.059 × 1.886 × 4.000` | `0.000` | Yes |
| `table_long_decorated_c.gltf` | `2.000 × 2.768 × 4.025` | `0.000` | Yes |
| `table_long_tablecloth.gltf` | `2.000 × 1.000 × 4.000` | `0.000` | Yes |
| `table_long_tablecloth_decorated_a.gltf` | `2.059 × 1.886 × 4.000` | `0.000` | Yes |
| `table_medium.gltf` | `2.000 × 1.000 × 2.000` | `0.000` | Yes |
| `table_medium_broken.gltf` | `2.277 × 0.972 × 2.428` | `-0.002` | No (corner) |
| `table_medium_decorated_a.gltf` | `2.000 × 1.886 × 2.000` | `0.000` | Yes |
| `table_medium_tablecloth.gltf` | `2.000 × 1.000 × 2.000` | `0.000` | Yes |
| `table_medium_tablecloth_decorated_b.gltf` | `2.000 × 1.886 × 2.000` | `0.000` | Yes |
| `table_small.gltf` | `1.000 × 1.000 × 1.000` | `0.000` | Yes |
| `table_small_decorated_a.gltf` | `1.039 × 1.621 × 1.211` | `0.000` | Yes |
| `table_small_decorated_b.gltf` | `1.013 × 2.157 × 1.000` | `0.000` | Yes |
| `torch.gltf` | `0.550 × 1.042 × 0.550` | `-0.395` | Yes |
| `torch_lit.gltf` | `0.550 × 1.126 × 0.550` | `-0.395` | Yes |
| `torch_mounted.gltf` | `0.550 × 1.062 × 0.616` | `-0.381` | X-only |
| `trunk_large_a.gltf` | `1.500 × 1.000 × 1.300` | `0.000` | Yes |
| `trunk_large_b.gltf` | `1.500 × 1.000 × 1.300` | `0.000` | Yes |
| `trunk_large_c.gltf` | `1.500 × 1.000 × 1.300` | `0.000` | Yes |
| `trunk_medium_a.gltf` | `0.953 × 0.726 × 0.875` | `0.000` | Yes |
| `trunk_medium_b.gltf` | `0.953 × 0.726 × 0.875` | `0.000` | Yes |
| `trunk_medium_c.gltf` | `0.953 × 0.726 × 0.875` | `0.000` | Yes |
| `trunk_small_a.gltf` | `0.675 × 0.484 × 0.583` | `0.000` | Yes |
| `trunk_small_b.gltf` | `0.675 × 0.484 × 0.583` | `0.000` | Yes |
| `trunk_small_c.gltf` | `0.675 × 0.484 × 0.583` | `0.000` | Yes |
| `wall.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_arched.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_archedwindow_gated.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_archedwindow_gated_scaffold.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_archedwindow_open.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_broken.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_corner.gltf` | `2.500 × 4.000 × 2.500` | `0.000` | No (corner) |
| `wall_corner_gated.gltf` | `2.500 × 4.000 × 2.500` | `0.000` | No (corner) |
| `wall_corner_scaffold.gltf` | `2.500 × 4.000 × 2.500` | `0.000` | No (corner) |
| `wall_corner_small.gltf` | `1.500 × 4.000 × 1.500` | `0.000` | No (corner) |
| `wall_cracked.gltf` | `4.000 × 4.000 × 1.259` | `0.000` | Yes |
| `wall_crossing.gltf` | `4.000 × 4.000 × 4.000` | `0.000` | Yes |
| `wall_doorway.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_doorway_scaffold.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_doorway_sides.gltf` | `5.000 × 4.000 × 4.000` | `0.000` | Yes |
| `wall_doorway_tsplit.gltf` | `8.000 × 4.000 × 2.500` | `0.000` | X-only |
| `wall_endcap.gltf` | `1.067 × 4.000 × 1.000` | `0.000` | Z-only |
| `wall_gated.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_half.gltf` | `2.000 × 4.000 × 1.000` | `0.000` | Z-only |
| `wall_half_endcap.gltf` | `2.000 × 4.000 × 1.000` | `0.000` | Z-only |
| `wall_half_endcap_sloped.gltf` | `2.000 × 4.000 × 1.000` | `0.000` | Z-only |
| `wall_open_scaffold.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_pillar.gltf` | `4.000 × 4.000 × 1.500` | `0.000` | Yes |
| `wall_scaffold.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_shelves.gltf` | `4.000 × 4.000 × 1.368` | `0.000` | X-only |
| `wall_sloped.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_tsplit.gltf` | `4.000 × 4.000 × 2.500` | `0.000` | X-only |
| `wall_tsplit_sloped.gltf` | `4.000 × 4.000 × 2.500` | `0.000` | X-only |
| `wall_window_closed.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_window_closed_scaffold.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_window_open.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |
| `wall_window_open_scaffold.gltf` | `4.000 × 4.000 × 1.000` | `0.000` | Yes |

## Dungeon Floors & Banners (83 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `banner_blue.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_brown.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_green.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_a_blue.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_a_brown.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_a_green.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_a_red.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_a_white.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_a_yellow.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_b_blue.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_b_brown.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_b_green.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_b_red.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_b_white.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_b_yellow.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_c_blue.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_c_brown.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_c_green.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_c_red.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_c_white.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_pattern_c_yellow.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_red.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_shield_blue.gltf` | `2.232 × 3.196 × 0.374` | `0.531` | X-only |
| `banner_shield_brown.gltf` | `2.232 × 3.196 × 0.374` | `0.531` | X-only |
| `banner_shield_green.gltf` | `2.232 × 3.196 × 0.374` | `0.531` | X-only |
| `banner_shield_red.gltf` | `2.232 × 3.196 × 0.374` | `0.531` | X-only |
| `banner_shield_white.gltf` | `2.232 × 3.196 × 0.374` | `0.531` | X-only |
| `banner_shield_yellow.gltf` | `2.232 × 3.196 × 0.374` | `0.531` | X-only |
| `banner_thin_blue.gltf` | `1.100 × 3.171 × 0.362` | `0.556` | X-only |
| `banner_thin_brown.gltf` | `1.100 × 3.171 × 0.362` | `0.556` | X-only |
| `banner_thin_green.gltf` | `1.100 × 3.171 × 0.362` | `0.556` | X-only |
| `banner_thin_red.gltf` | `1.100 × 3.171 × 0.362` | `0.556` | X-only |
| `banner_thin_white.gltf` | `1.100 × 3.171 × 0.362` | `0.556` | X-only |
| `banner_thin_yellow.gltf` | `1.100 × 3.171 × 0.362` | `0.556` | X-only |
| `banner_triple_blue.gltf` | `3.700 × 3.196 × 0.362` | `0.531` | X-only |
| `banner_triple_brown.gltf` | `3.700 × 3.196 × 0.362` | `0.531` | X-only |
| `banner_triple_green.gltf` | `3.700 × 3.196 × 0.362` | `0.531` | X-only |
| `banner_triple_red.gltf` | `3.700 × 3.196 × 0.362` | `0.531` | X-only |
| `banner_triple_white.gltf` | `3.700 × 3.196 × 0.362` | `0.531` | X-only |
| `banner_triple_yellow.gltf` | `3.700 × 3.196 × 0.362` | `0.531` | X-only |
| `banner_white.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `banner_yellow.gltf` | `1.500 × 3.196 × 0.312` | `0.531` | X-only |
| `bed_floor.gltf` | `1.500 × 0.563 × 3.000` | `0.000` | Yes |
| `ceiling_tile.gltf` | `4.000 × 0.350 × 4.000` | `-0.250` | Yes |
| `floor_dirt_large.gltf` | `4.000 × 0.209 × 4.000` | `-0.100` | Yes |
| `floor_dirt_large_rocky.gltf` | `4.000 × 0.393 × 4.000` | `-0.100` | Yes |
| `floor_dirt_small_a.gltf` | `2.000 × 0.186 × 2.000` | `-0.100` | Yes |
| `floor_dirt_small_b.gltf` | `2.000 × 0.189 × 2.000` | `-0.100` | Yes |
| `floor_dirt_small_c.gltf` | `2.000 × 0.209 × 2.000` | `-0.100` | Yes |
| `floor_dirt_small_corner.gltf` | `2.000 × 0.154 × 2.000` | `-0.100` | Yes |
| `floor_dirt_small_d.gltf` | `2.000 × 0.138 × 2.000` | `-0.100` | Yes |
| `floor_dirt_small_weeds.gltf` | `2.000 × 0.295 × 2.000` | `-0.100` | Yes |
| `floor_foundation_allsides.gltf` | `2.200 × 2.000 × 2.200` | `0.000` | Yes |
| `floor_foundation_corner.gltf` | `2.100 × 2.000 × 2.100` | `0.000` | No (corner) |
| `floor_foundation_diagonal_corner.gltf` | `2.100 × 2.000 × 2.100` | `0.000` | No (corner) |
| `floor_foundation_front.gltf` | `2.000 × 2.000 × 2.100` | `0.000` | X-only |
| `floor_foundation_front_and_back.gltf` | `2.000 × 2.000 × 2.200` | `0.000` | Yes |
| `floor_foundation_front_and_sides.gltf` | `2.200 × 2.000 × 2.100` | `0.000` | X-only |
| `floor_tile_big_grate.gltf` | `4.000 × 1.050 × 4.000` | `-1.000` | Yes |
| `floor_tile_big_grate_open.gltf` | `4.000 × 1.050 × 4.000` | `-1.000` | Yes |
| `floor_tile_big_spikes.gltf` | `4.000 × 2.100 × 4.000` | `-0.100` | Yes |
| `floor_tile_extralarge_grates.gltf` | `8.000 × 1.130 × 8.000` | `-0.980` | Yes |
| `floor_tile_extralarge_grates_open.gltf` | `8.000 × 1.130 × 8.000` | `-0.980` | Yes |
| `floor_tile_grate.gltf` | `4.000 × 1.030 × 2.000` | `-0.980` | Yes |
| `floor_tile_grate_open.gltf` | `4.000 × 1.030 × 2.000` | `-0.980` | Yes |
| `floor_tile_large.gltf` | `4.000 × 0.150 × 4.000` | `-0.100` | Yes |
| `floor_tile_large_rocks.gltf` | `4.000 × 0.636 × 4.000` | `-0.100` | Yes |
| `floor_tile_small.gltf` | `2.000 × 0.150 × 2.000` | `-0.100` | Yes |
| `floor_tile_small_broken_a.gltf` | `2.000 × 0.150 × 2.000` | `-0.100` | Yes |
| `floor_tile_small_broken_b.gltf` | `2.000 × 0.150 × 2.000` | `-0.100` | Yes |
| `floor_tile_small_corner.gltf` | `2.000 × 0.150 × 2.000` | `-0.100` | Yes |
| `floor_tile_small_decorated.gltf` | `2.000 × 0.773 × 2.000` | `-0.100` | Yes |
| `floor_tile_small_weeds_a.gltf` | `2.000 × 0.295 × 2.000` | `-0.100` | Yes |
| `floor_tile_small_weeds_b.gltf` | `2.000 × 0.295 × 2.000` | `-0.100` | Yes |
| `floor_wood_large.gltf` | `4.000 × 0.150 × 4.000` | `-0.100` | Yes |
| `floor_wood_large_dark.gltf` | `4.000 × 0.150 × 4.000` | `-0.100` | Yes |
| `floor_wood_small.gltf` | `2.000 × 0.150 × 2.000` | `-0.100` | Yes |
| `floor_wood_small_dark.gltf` | `2.000 × 0.150 × 2.000` | `-0.100` | Yes |
| `plate.gltf` | `0.971 × 0.129 × 0.971` | `0.000` | Yes |
| `plate_food_a.gltf` | `1.025 × 0.788 × 0.971` | `0.000` | Yes |
| `plate_food_b.gltf` | `0.971 × 0.236 × 0.971` | `0.000` | Yes |
| `plate_small.gltf` | `0.485 × 0.129 × 0.485` | `0.000` | Yes |
| `plate_stack.gltf` | `0.997 × 0.564 × 1.002` | `0.000` | Yes |

## Interior & Street Props (94 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `anvil.gltf` | `1.082 × 0.556 × 0.402` | `0.003` | Z-only |
| `anvil_log.gltf` | `0.929 × 1.073 × 0.821` | `0.001` | No (corner) |
| `axe_bronze.gltf` | `0.294 × 0.827 × 0.046` | `-0.381` | Yes |
| `bag.gltf` | `0.655 × 0.799 × 0.544` | `0.002` | Yes |
| `banner_1.gltf` | `1.613 × 2.392 × 0.191` | `-1.549` | Z-only |
| `banner_1_cloth.gltf` | `0.810 × 2.246 × 0.057` | `-2.246` | Yes |
| `banner_2.gltf` | `1.613 × 2.077 × 0.191` | `-1.234` | Z-only |
| `banner_2_cloth.gltf` | `0.810 × 1.931 × 0.057` | `-1.931` | Yes |
| `barrel.gltf` | `0.698 × 0.898 × 0.698` | `0.003` | Yes |
| `barrel_apples.gltf` | `0.698 × 0.898 × 0.698` | `0.003` | Yes |
| `barrel_holder.gltf` | `1.359 × 1.257 × 0.741` | `-0.006` | Yes |
| `bed_twin1.gltf` | `1.876 × 0.805 × 2.412` | `0.000` | Yes |
| `bed_twin2.gltf` | `1.876 × 0.760 × 2.412` | `0.000` | Yes |
| `bench.gltf` | `2.777 × 0.533 × 0.534` | `-0.007` | Yes |
| `book_5.gltf` | `0.213 × 0.064 × 0.287` | `-0.032` | Yes |
| `book_7.gltf` | `0.247 × 0.068 × 0.333` | `-0.034` | Yes |
| `book_group_medium_1.gltf` | `1.063 × 0.298 × 0.247` | `-0.004` | Yes |
| `book_group_medium_2.gltf` | `1.105 × 0.295 × 0.247` | `0.000` | Yes |
| `book_group_medium_3.gltf` | `1.042 × 0.295 × 0.247` | `0.000` | Yes |
| `book_group_small_1.gltf` | `0.289 × 0.298 × 0.226` | `-0.005` | Yes |
| `book_group_small_2.gltf` | `0.228 × 0.283 × 0.237` | `-0.001` | Yes |
| `book_group_small_3.gltf` | `0.245 × 0.277 × 0.237` | `-0.001` | Yes |
| `book_simplified_single.gltf` | `0.065 × 0.268 × 0.210` | `-0.001` | Yes |
| `book_stack_1.gltf` | `0.285 × 0.214 × 0.226` | `0.001` | Yes |
| `book_stack_2.gltf` | `0.274 × 0.198 × 0.227` | `-0.001` | Yes |
| `book_stand.gltf` | `0.507 × 1.447 × 0.511` | `-0.002` | Yes |
| `bookcase_2.gltf` | `1.461 × 2.545 × 0.429` | `-0.017` | Yes |
| `bottle_1.gltf` | `0.113 × 0.365 × 0.113` | `0.002` | Yes |
| `bucket_metal.gltf` | `0.485 × 0.365 × 0.449` | `-0.005` | Yes |
| `bucket_wooden_1.gltf` | `0.434 × 0.293 × 0.383` | `0.001` | Yes |
| `cabinet.gltf` | `1.362 × 0.997 × 0.357` | `0.000` | Yes |
| `cage_small.gltf` | `0.855 × 0.805 × 0.884` | `-0.042` | Yes |
| `candle_1.gltf` | `0.094 × 0.132 × 0.108` | `0.001` | Yes |
| `candle_2.gltf` | `0.094 × 0.251 × 0.098` | `0.002` | Yes |
| `candle_stick.gltf` | `0.261 × 0.155 × 0.179` | `0.001` | Yes |
| `candle_stick_stand.gltf` | `0.732 × 1.313 × 0.731` | `-0.008` | Yes |
| `candle_stick_triple.gltf` | `0.442 × 0.463 × 0.136` | `-0.001` | Yes |
| `carrot.gltf` | `0.180 × 0.566 × 0.222` | `-0.238` | Yes |
| `cauldron.gltf` | `0.989 × 0.816 × 0.944` | `-0.003` | Yes |
| `chain_coil.gltf` | `1.070 × 0.087 × 0.908` | `0.005` | Yes |
| `chair_1.gltf` | `0.581 × 1.123 × 0.549` | `-0.003` | Yes |
| `chalice.gltf` | `0.118 × 0.257 × 0.125` | `-0.001` | Yes |
| `chandelier.gltf` | `1.303 × 1.458 × 1.303` | `-1.422` | Yes |
| `chest_wood.gltf` | `1.276 × 0.715 × 0.755` | `-0.023` | Yes |
| `coin.gltf` | `0.068 × 0.068 × 0.015` | `-0.034` | Yes |
| `coin_pile.gltf` | `0.197 × 0.073 × 0.154` | `-0.003` | Yes |
| `coin_pile_2.gltf` | `0.279 × 0.058 × 0.200` | `0.000` | Yes |
| `crate_metal.gltf` | `0.864 × 0.868 × 0.866` | `0.003` | Yes |
| `crate_wooden.gltf` | `0.842 × 0.931 × 0.908` | `-0.052` | Yes |
| `dummy.gltf` | `0.809 × 1.863 × 0.585` | `-0.003` | Yes |
| `farm_crate_apple.gltf` | `0.714 × 0.244 × 0.414` | `-0.016` | Yes |
| `farm_crate_carrot.gltf` | `0.714 × 0.411 × 0.567` | `-0.016` | X-only |
| `farm_crate_empty.gltf` | `0.714 × 0.244 × 0.414` | `-0.016` | Yes |
| `key_gold.gltf` | `0.058 × 0.012 × 0.122` | `-0.006` | Yes |
| `key_metal.gltf` | `0.048 × 0.012 × 0.111` | `-0.006` | Yes |
| `lantern_wall.gltf` | `0.357 × 1.337 × 1.302` | `0.082` | X-only |
| `mug.gltf` | `0.192 × 0.184 × 0.147` | `-0.005` | Yes |
| `nightstand_shelf.gltf` | `0.693 × 1.216 × 0.393` | `-0.006` | Yes |
| `peg_rack.gltf` | `1.184 × 0.348 × 0.096` | `-0.174` | Yes |
| `pickaxe_bronze.gltf` | `0.813 × 1.198 × 0.136` | `-0.494` | Yes |
| `pot_1.gltf` | `0.539 × 0.224 × 0.486` | `-0.023` | Yes |
| `pot_1_lid.gltf` | `0.539 × 0.280 × 0.486` | `-0.023` | Yes |
| `potion_1.gltf` | `0.114 × 0.140 × 0.114` | `0.000` | Yes |
| `potion_2.gltf` | `0.127 × 0.262 × 0.127` | `0.000` | Yes |
| `potion_4.gltf` | `0.148 × 0.201 × 0.148` | `0.000` | Yes |
| `pouch_large.gltf` | `0.225 × 0.159 × 0.120` | `0.001` | Yes |
| `rope_1.gltf` | `0.557 × 0.098 × 0.606` | `-0.027` | Yes |
| `rope_2.gltf` | `0.808 × 0.124 × 0.845` | `-0.003` | Yes |
| `rope_3.gltf` | `1.228 × 0.102 × 0.951` | `-0.027` | Z-only |
| `scroll_1.gltf` | `0.244 × 0.059 × 0.063` | `0.001` | Yes |
| `scroll_2.gltf` | `0.233 × 0.059 × 0.064` | `0.000` | Yes |
| `shelf_arch.gltf` | `1.245 × 1.589 × 0.312` | `-0.614` | X-only |
| `shelf_simple.gltf` | `1.184 × 0.309 × 0.292` | `-0.201` | X-only |
| `shelf_small_bottles.gltf` | `1.137 × 0.647 × 0.285` | `-0.019` | X-only |
| `shield_wooden.gltf` | `0.615 × 0.621 × 0.179` | `-0.310` | X-only |
| `small_bottle.gltf` | `0.060 × 0.119 × 0.049` | `0.000` | Yes |
| `small_bottles_1.gltf` | `0.215 × 0.145 × 0.056` | `0.001` | Yes |
| `stall_cart_empty.gltf` | `3.021 × 2.632 × 1.060` | `-0.004` | Z-only |
| `stall_empty.gltf` | `1.845 × 2.627 × 0.932` | `-0.005` | Yes |
| `stool.gltf` | `0.475 × 0.589 × 0.475` | `-0.006` | Yes |
| `sword_bronze.gltf` | `0.267 × 1.132 × 0.065` | `-0.208` | Yes |
| `table_fork.gltf` | `0.050 × 0.006 × 0.263` | `-0.003` | Yes |
| `table_knife.gltf` | `0.042 × 0.006 × 0.287` | `-0.003` | X-only |
| `table_large.gltf` | `2.848 × 0.813 × 1.097` | `0.001` | Yes |
| `table_plate.gltf` | `0.333 × 0.020 × 0.337` | `-0.001` | Yes |
| `table_spoon.gltf` | `0.046 × 0.018 × 0.272` | `-0.015` | X-only |
| `torch_metal.gltf` | `0.223 × 0.648 × 0.388` | `-0.278` | X-only |
| `vase_2.gltf` | `0.695 × 0.516 × 0.695` | `-0.001` | Yes |
| `vase_4.gltf` | `0.360 × 0.485 × 0.360` | `0.001` | Yes |
| `vase_rubble_medium.gltf` | `0.797 × 0.175 × 0.598` | `0.003` | Yes |
| `weapon_stand.gltf` | `1.386 × 1.109 × 0.983` | `-0.003` | Yes |
| `whetstone.gltf` | `1.141 × 1.170 × 0.902` | `0.003` | X-only |
| `workbench.gltf` | `2.019 × 0.895 × 1.024` | `0.000` | Yes |
| `workbench_drawers.gltf` | `0.423 × 0.242 × 0.299` | `0.884` | No (corner) |

## Nature Trees/Rocks/Foliage (68 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `bush_common.gltf` | `1.915 × 1.582 × 1.965` | `-0.235` | Yes |
| `bush_common_flowers.gltf` | `1.915 × 1.582 × 1.965` | `-0.235` | Yes |
| `clover_1.gltf` | `0.796 × 1.145 × 0.764` | `-0.013` | Z-only |
| `clover_2.gltf` | `0.851 × 1.264 × 0.837` | `-0.002` | No (corner) |
| `common_tree_1.gltf` | `4.311 × 7.265 × 4.578` | `-0.243` | X-only |
| `common_tree_2.gltf` | `4.464 × 7.643 × 4.276` | `-0.243` | X-only |
| `common_tree_3.gltf` | `4.063 × 9.425 × 4.241` | `-0.243` | X-only |
| `common_tree_4.gltf` | `3.826 × 9.438 × 3.755` | `-0.243` | No (corner) |
| `common_tree_5.gltf` | `3.671 × 7.006 × 4.220` | `-0.243` | No (corner) |
| `dead_tree_1.gltf` | `6.149 × 9.495 × 5.749` | `-0.336` | Z-only |
| `dead_tree_2.gltf` | `6.730 × 11.488 × 6.379` | `-0.336` | No (corner) |
| `dead_tree_3.gltf` | `6.388 × 13.280 × 6.430` | `-0.336` | No (corner) |
| `dead_tree_4.gltf` | `7.961 × 12.771 × 7.732` | `-0.336` | No (corner) |
| `dead_tree_5.gltf` | `8.356 × 16.437 × 8.413` | `-0.336` | No (corner) |
| `fern_1.gltf` | `2.827 × 0.840 × 2.652` | `-0.077` | Yes |
| `flower_3_group.gltf` | `1.488 × 2.055 × 1.591` | `-0.035` | Z-only |
| `flower_3_single.gltf` | `0.907 × 2.068 × 0.878` | `-0.018` | X-only |
| `flower_4_group.gltf` | `1.781 × 2.487 × 1.368` | `-0.057` | Yes |
| `flower_4_single.gltf` | `1.072 × 2.419 × 0.773` | `-0.030` | Yes |
| `grass_common_short.gltf` | `0.639 × 1.334 × 0.737` | `-0.022` | X-only |
| `grass_common_tall.gltf` | `0.895 × 1.873 × 0.993` | `-0.031` | Yes |
| `grass_wispy_short.gltf` | `1.322 × 1.072 × 1.210` | `-0.086` | Z-only |
| `grass_wispy_tall.gltf` | `1.540 × 1.672 × 1.594` | `-0.036` | Yes |
| `mushroom_common.gltf` | `0.564 × 0.463 × 0.779` | `-0.017` | No (corner) |
| `mushroom_laetiporus.gltf` | `1.366 × 0.767 × 1.103` | `-0.160` | X-only |
| `pebble_round_1.gltf` | `0.500 × 0.095 × 0.367` | `-0.008` | Yes |
| `pebble_round_2.gltf` | `0.449 × 0.094 × 0.411` | `-0.003` | Yes |
| `pebble_round_3.gltf` | `0.450 × 0.099 × 0.485` | `-0.002` | Yes |
| `pebble_round_4.gltf` | `0.406 × 0.099 × 0.452` | `-0.006` | Yes |
| `pebble_round_5.gltf` | `0.419 × 0.101 × 0.346` | `-0.004` | Yes |
| `pebble_square_1.gltf` | `0.435 × 0.130 × 0.440` | `-0.002` | Yes |
| `pebble_square_2.gltf` | `0.391 × 0.140 × 0.280` | `-0.005` | Yes |
| `pebble_square_3.gltf` | `0.373 × 0.159 × 0.319` | `-0.008` | Yes |
| `pebble_square_4.gltf` | `0.340 × 0.168 × 0.291` | `-0.003` | Yes |
| `pebble_square_5.gltf` | `0.352 × 0.152 × 0.450` | `-0.008` | Yes |
| `pebble_square_6.gltf` | `0.462 × 0.138 × 0.263` | `-0.010` | Yes |
| `petal_1.gltf` | `0.460 × 0.244 × 0.455` | `0.000` | Yes |
| `petal_2.gltf` | `0.673 × 0.236 × 0.631` | `0.000` | Yes |
| `petal_3.gltf` | `0.619 × 0.189 × 0.606` | `0.000` | Yes |
| `petal_4.gltf` | `0.329 × 0.252 × 0.244` | `0.000` | Yes |
| `petal_5.gltf` | `0.834 × 0.289 × 0.795` | `0.001` | Yes |
| `pine_1.gltf` | `4.945 × 7.317 × 4.538` | `-0.235` | X-only |
| `pine_2.gltf` | `5.728 × 7.376 × 5.221` | `-0.235` | X-only |
| `pine_3.gltf` | `3.611 × 7.392 × 3.996` | `-0.235` | No (corner) |
| `pine_4.gltf` | `5.802 × 10.236 × 5.371` | `-0.235` | X-only |
| `pine_5.gltf` | `6.420 × 8.724 × 6.222` | `-0.235` | No (corner) |
| `plant_1.gltf` | `1.273 × 1.014 × 1.386` | `-0.035` | No (corner) |
| `plant_1_big.gltf` | `1.807 × 2.348 × 1.954` | `-0.035` | X-only |
| `plant_7.gltf` | `1.048 × 0.250 × 0.962` | `0.079` | Z-only |
| `plant_7_big.gltf` | `1.311 × 0.253 × 1.362` | `0.050` | X-only |
| `rock_medium_1.gltf` | `3.225 × 2.260 × 2.989` | `-0.271` | No (corner) |
| `rock_medium_2.gltf` | `3.049 × 1.899 × 2.479` | `-0.051` | No (corner) |
| `rock_medium_3.gltf` | `3.420 × 2.316 × 3.476` | `-0.316` | No (corner) |
| `rock_path_round_small_1.gltf` | `1.057 × 0.113 × 1.476` | `-0.009` | Yes |
| `rock_path_round_small_2.gltf` | `1.140 × 0.105 × 1.354` | `-0.008` | X-only |
| `rock_path_round_small_3.gltf` | `1.179 × 0.109 × 1.290` | `-0.008` | Yes |
| `rock_path_round_thin.gltf` | `1.457 × 0.110 × 2.089` | `-0.009` | Yes |
| `rock_path_round_wide.gltf` | `2.111 × 0.113 × 2.129` | `-0.009` | X-only |
| `rock_path_square_small_1.gltf` | `1.019 × 0.150 × 0.974` | `-0.009` | Yes |
| `rock_path_square_small_2.gltf` | `0.993 × 0.149 × 0.966` | `-0.013` | Yes |
| `rock_path_square_small_3.gltf` | `0.836 × 0.174 × 1.076` | `-0.008` | Yes |
| `rock_path_square_thin.gltf` | `1.560 × 0.176 × 1.987` | `-0.010` | Yes |
| `rock_path_square_wide.gltf` | `2.052 × 0.176 × 1.987` | `-0.010` | Yes |
| `twisted_tree_1.gltf` | `13.516 × 16.725 × 11.549` | `-0.201` | No (corner) |
| `twisted_tree_2.gltf` | `10.563 × 18.949 × 9.203` | `-0.201` | No (corner) |
| `twisted_tree_3.gltf` | `11.357 × 16.073 × 11.506` | `-0.201` | No (corner) |
| `twisted_tree_4.gltf` | `10.381 × 18.738 × 11.293` | `-0.201` | No (corner) |
| `twisted_tree_5.gltf` | `9.495 × 15.662 × 9.387` | `-0.201` | No (corner) |

## Deities & Mortal Rigs (16 assets)

| Filename | W × H × D (m) | min_y | Centered? |
| :--- | :--- | :--- | :--- |
| `base_beasthuman_female.glb` | `1.504 × 1.747 × 0.508` | `-0.001` | X-only |
| `base_beasthuman_male.glb` | `1.864 × 1.848 × 0.411` | `-0.003` | Yes |
| `base_demon.gltf` | `4.656 × 3.120 × 2.320` | `-0.015` | X-only |
| `base_dragon_humanoid.gltf` | `4.649 × 3.226 × 1.919` | `-0.003` | X-only |
| `base_dragon_true.glb` | `3.602 × 2.476 × 0.377` | `-0.649` | X-only |
| `base_elf_female.glb` | `1.504 × 1.812 × 0.296` | `-0.001` | Yes |
| `base_elf_male.glb` | `1.864 × 1.895 × 0.375` | `-0.003` | Yes |
| `base_human_female.glb` | `1.762 × 1.806 × 0.309` | `0.002` | Yes |
| `base_human_male.gltf` | `1.799 × 1.563 × 0.352` | `-0.004` | Yes |
| `gm_beasthuman.vrm` | `1.389 × 1.690 × 0.790` | `0.000` | X-only |
| `gm_demon.vrm` | `2.891 × 2.419 × 2.077` | `0.000` | X-only |
| `gm_dragon.vrm` | `1.493 × 1.923 × 1.615` | `0.000` | X-only |
| `gm_elf.vrm` | `2.388 × 2.259 × 0.950` | `0.000` | No (corner) |
| `gm_human.vrm` | `1.159 × 1.430 × 0.482` | `-0.011` | X-only |
| `god_avatar.vrm` | `1.612 × 1.767 × 0.310` | `0.000` | Yes |
| `world_goddess.vrm` | `1.342 × 1.618 × 0.647` | `-0.002` | X-only |
