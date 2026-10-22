# Apex Rig & Motion 1.1.0

An advanced human **control rig + animation toolkit** for **Blender 5.2 LTS**, packaged as a
native Blender **extension** (`apex_rig-1.0.0.zip`).

![Apex rig fitted to a character, mid-walk](out/apex_fitted.png)

---

## 1. Install

1. Blender **5.2.0 – 5.2.x** (the manifest refuses anything outside that range).
2. `Edit ▸ Preferences ▸ Get Extensions ▸ ⌄ ▸ Install from Disk…` → pick `dist/apex_rig-1.0.0.zip`.
3. Press `N` in the 3D View and open the **Apex** tab.

Headless install (what the test suite does):

```bash
blender --command extension install-file -r user_default -e dist/apex_rig-1.0.0.zip
blender -b --python-expr "import bpy; bpy.ops.preferences.addon_enable(module='bl_ext.user_default.apex_rig')"
```

---

## 2. Rigging the character you already have

The **Apex ▸ My Character** panel puts the rig on an existing mesh instead of at the world origin.

1. Select your character mesh (any object transform, any rotation, scaled, multiple parts).
2. Press **Analyze** — the add-on reports height, floor, facing, A-pose angle and leg length.
3. Press **Rig My Character** — it builds a rig *fitted* to that character and skins it.

<table>
<tr><td width="50%">

**If the mesh is already rigged** (Mixamo / UE5 / Unity / VRM / Rigify / any skeleton with
recognisable hips, feet, head, shoulders):

* joint positions are read from that skeleton,
* a coordinate-descent solver (best-of-candidates per parameter, 5 passes, ~0.03 s) fits
  `height, leg_len, arm_len, shoulder, hip, head_scale, arm_angle` so the Apex skeleton lands on
  the real joints,
* measured on a 2.25 m heroic character rotated −25° and scaled 1.15×:
  **RMS 0.8 cm, max joint error 1.39 cm** across all 16 matched joints.

</td><td>

**If the mesh is not rigged**, everything is measured from evaluated geometry, in *character
space* (facing found first, then the point cloud is rotated):

* height/floor from the bounds, body axis from the hip band,
* facing from the feet (2-means leg split → per-foot fore-aft PCA → heel-to-toe sign),
  axis-snapped only when within 12°, otherwise kept as a free angle,
* A-pose from the outer-arm silhouette slope, crotch from the leg-gap test.

Same character translated, rotated 120° and scaled 0.85×: **max landmark error 2.8 cm**,
**20/22 joints inside** the mesh.

</td></tr>
</table>

Extras in the same panel: **Check** (how many joints are inside the mesh, bone-to-surface
distance, which bones and fingers are outside) and **Refit Existing Rig** (move / rotate / scale
an Apex rig you already built onto a moved or rescaled character — deformation keeps working,
verified after a 35° re-rotation and 1.1× rescale).

An existing Apex rig in the scene is replaced automatically; a *foreign* skeleton is left in place
(the rig is simply separated from it). If the character's chest does not fit the generic profile,
the mesh-level weights still work — only the joint placement comes from the skeleton.

## 3. What the rig gives you

| Feature | Detail |
|---|---|
| Skeleton | 64 bones: root → cog → pelvis/spine_01/spine_02/chest/neck/head, clavicle → upper_arm → forearm → hand, 5 fingers × 3 phalanges, thigh → shin → foot → toe |
| Proportions | 8 presets (Female, Male, Heavy, Slim, Heroic, Child, Stylized, Custom); height, girth/build, head scale, shoulder/chest/waist/hip width, arm & leg length, A-pose angle, finger count |
| IK limbs | 2-bone IK on arms and legs, `chain_count=2`, **pole targets** auto-calibrated per side, anatomically limited hinges (X limits) with soft Y/Z stiffness |
| IK ⇄ FK | `ik_arm.L/R`, `ik_leg.L/R` props blend continuously; `Snap IK ▸ FK` / `Snap FK ▸ IK` keep the silhouette to **0.0000 m** |
| Twists | Optional upper-arm / forearm twist bones driven by the hand |
| Fingers | `finger_curl`, `finger_spread`, `thumb_curl` props drive all 30 phalanges with per-joint falloff |
| Stretch | `ik_stretch` prop; over-extension error 0.0761 m → **0.0000 m** when enabled |
| Controls | Colour-coded bone collections (Controls / Torso / Arms / Legs / Twists), custom shapes, viewport-independent widgets |
| Extras | Mirror pose, reset pose, one-click control keying, weight validation, engine bone renaming (UE5 / Mixamo / Unity / VRM) |

Rest-pose accuracy (measured through the evaluated depsgraph):
`cog, pelvis, spine_02, chest, neck, head, hand.L, foot.L` all **0.0000 m** off their rest
positions with every constraint and driver live; limbs stay at their rest targets when the hips
move.

## 4. Skinning

* **Apex Adaptive Weights** (default) – deterministic capsule-distance weights restricted to
  hierarchically adjacent bones (max 2 hops, same side only), edge-aware Laplacian smoothing,
  pruned to 4 influences and normalised. Works on non-manifold, multi-shell and hard-surface
  meshes where bone-heat fails, and a rescue pass guarantees that **every deform bone owns
  geometry** — no finger tip, toe or clavicle is ever left without weights.
* **Bone Heat** and **Bone Envelopes** – Blender's solvers with automatic 4-influence cleanup and
  normalisation.
* **Realistic Body (MakeHuman)** – the only body source in the add-on. Builds an adult CC0 body
  (male, female, athletic, heavier, or custom gender / muscle / weight), fits the Apex rig to it,
  and skins it. The procedural mannequin has been removed.

### 4.1 Deformation toolkit (new)

The `Deforming` panel fixes the classic "some parts of the body don't move" problem and polishes
the result:

| Tool | What it does |
|---|---|
| **Deform Check** | Puts the rig through a stress pose, measures every bone's actual vertex displacement and lists **bones that do not move their verts** (`0` on a healthy rig) and *weakest movers*. With `Check Animation` it also samples the active action frame-by-frame and reports bones that never move in the clip. |
| **Preserve Volume** | Toggles dual-quaternion skinning on every armature modifier — stops knees, elbows and shoulders collapsing at extreme angles. |
| **Corrective Smooth** | Adds a corrective-smooth modifier driven after the armature (factor/iterations adjustable) to remove candy-wrapper pinching. |
| **Smooth / Symmetrize / Clean / Heatmap / Restore** | Weight editing without leaving the panel: Laplacian weight smoothing, L→R or R→L symmetrisation (46 bone pairs), 4-influence clean-up, a 45-colour weight heatmap written to a vertex-colour attribute, and one-click restore to the generated weights. |
| **Ensure Coverage** | Re-runs the rescue pass: any deform bone with no (or negligible) influence gets its nearest vertices so it always deforms something. |

Measured on the built-in rig: **52 / 52 deform bones covered**, deform check `0 empty / 0 stalled`,
max vertex displacement 0.31 m in the stress pose, **52 / 52 bones moving across a walk clip**.

## 5. Animation

Procedural motions are authored as **editable control keys**, not baked deform data: Bezier
interpolation, quaternion hemisphere fix-up, loop boundary keys and a `CYCLES` modifier so any
loop runs forever in the timeline/NLA.

| Motion | Frames | Notes |
|---|---|---|
| Breathing | 96 | chest/neck/shoulder respiration + subtle vertical float |
| Weight Shift | 144 | hip sway with counter-rotated spine and head |
| Idle Sway | 180 | layered sine noise for organic hold |
| Look Around | 168 | keyed glances with holds |
| Finger Fidget | 120 | keeps finger drivers alive |
| Settle / Overshoot | 32 | one-shot damped settle |
| Walk / Run / Sneak | 32 / 24 / 40 | full locomotion cycles: heel strike → flat → toe-off, hip yaw/roll/sway, counter-rotating torso, arm swing, head stabilisation, **automatic gait crouch derived from leg reach** |

Measured: walk cycle foot IK error **0.0001 m**, 0.071 m foot lift, 33 keys/curve, cyclic.
Motions land on their own NLA tracks (auto-placed after existing tracks) so several clips can be
stacked and exported together.

Also included: **Bake Controls**, **Bake Action** (visual keying of the whole pose), and
**Mirror Action** (creates the opposite-side clip, including mirrored rig properties).

## 6. Mocap / retargeting

The retargeter is name-first, position-fallback:

1. Alias tables for **Mixamo, UE5, Unity, VRM, Rigify/BVH** plus substring heuristics
   (`LeftArm`, `mixamorig:LeftArm`, `upperarm_l`, …), and finger index detection.
2. Unmatched bones fall back to a rest-pose position match.
3. Rotation **deltas** are transferred in world space and re-applied to the Apex rest skeleton, so
   differing bone rolls and lengths are handled correctly; hip translation is height-scaled
   (female 1.65 m ← male 1.77 m ⇒ scale 0.933).
4. The result is a plain editable action (IK props keyed to FK), 53 bones / 25 frames.

`Rename Rig Bones` bakes the rig itself into UE5 / Mixamo / Unity / VRM naming (vertex groups are
renamed too, and constraints/drivers follow).

## 7. Pose library (new)

Ten ready poses that work on any Apex rig regardless of proportions: **A-Pose, T-Pose, Relaxed,
Combat Guard, Deep Crouch, Jump, Wave, Hero Landing, Sit, Look Back**. Each pose is written with
posing primitives (`aim_bone`, `rotate_bone`, `move_bone`, `place_bone_head`) and keeps the feet
planted with IK; `Key Pose` turns any of them into a keyed action.

## 8. Export

`glTF 2.0 (.glb / .gltf)` and `FBX (UE5 / Unity / Generic)` with deform-bone-only skins, 4
influences, all actions stashed on NLA tracks and baked. Export options are filtered against the
live RNA, so renamed exporter properties never break the add-on.

Verified output of a 6 056-vert character with 5 clips:

```
apex_character.glb  290 660 B   skins:1 (52 joints)  animations:5  meshes:1
  Apex_Walk          156 channels  rotation/translation/scale  time max 1.333 s
  Apex_Run           156 channels                              time max 1.0 s
```

## 9. UI

Eight N-panel sub-panels under **Apex**: `My Character` (fit to an existing mesh),
`Body Presets`, `Poses`, `Controls`, `Skinning`, `Animation`, `Mocap / Retarget`, `Export`.
All build settings are live scene settings with descriptions, slider ranges and soft limits.

**Picture-based selection.** Presets, poses, motions and skinning methods are chosen from
thumbnail grids instead of dropdowns — 31 rendered previews ship inside the extension
(`previews/preset_*.png`, `pose_*.png`, `motion_*.png`, `skin_*.png`). The images are loaded
through `bpy.utils.previews`; in a normal (GL) Blender session each tile is a clickable picture,
and in background/headless mode the same grid degrades automatically to labelled buttons, so the
UI never breaks.

Regenerate the thumbnails after changing proportions or the body:

```bash
blender -b --factory-startup --python scripts/make_previews.py   # ~40 s, Cycles CPU
```

## 9.1 Highlights in this build

* **Fixed**: `reset pose` used to restore a stale knee/elbow pole angle and twisted both legs by
  ~90°, which is what made crouches, sits and some clips look melted. Pole angles are now treated
  as rig-specific and preserved (poses measure thigh rotation `-60°` clean, feet planted at z 0.081).
* **Fixed**: hip joint width was anatomically too wide; the legs now sit under the pelvis and the
  "skirt" silhouette at the hips is gone.
* New: pose library, deformation toolkit, animation coverage report, picture UI, previews.

## 10. Verification

Run against Blender 5.2.1 LTS (headless):

```bash
blender -b --factory-startup --python tests/test_acceptance.py   # 12 PASS
blender -b --factory-startup --python tests/test_suite.py        # build→skin→motion→retarget→export
blender -b --factory-startup --python tests/test_extension.py    # installed-extension path
blender -b --factory-startup --python tests/test_fit.py          # fit to a plain character mesh
blender -b --factory-startup --python tests/test_fit_skeleton.py # fit to a rigged character
blender -b --factory-startup --python tests/test_fit_ops.py      # the panel's operators
blender -b --factory-startup --python tests/test_deform.py       # weights + deformation tools
blender -b --factory-startup --python tests/test_v2.py           # coverage, animation audit, poses, UI
blender -b --factory-startup --python tests/test_ext_v2.py       # installed extension, full v2 stack
```

Fitting results (all against Blender 5.2.1 headless):

```
rigged character, 120° rotation, 0.85× scale   max landmark error 0.0277 m, 20/22 joints inside
rigged character, -25° rotation, 1.15× scale   RMS 0.8 cm, max joint error 1.39 cm, 20/22 inside
installed extension, 65° rotation, 1.05× scale 22/22 joints inside, walk IK error 0.0001 m
```

`tests/test_acceptance.py` output:

```
1 rest pose ............................ PASS  (all bones 0.0000 m)
2 ik_stretch over-reach ................ PASS  (0.0761 → 0.0000 m)
3 finger curl / spread / pole angle .... PASS  (0.1297 / 0.0168 / 0.1106 m)
4 FK→IK / IK→FK snapping ............... PASS  (0.0000 m both ways)
5 mirror pose .......................... PASS
6 walk cycle IK error .................. PASS  (0.0001 m)
7 pelvis stable during limb IK ......... PASS  (0.0 m)
8 extension manifest / no bl_info ...... PASS
```

Note: an IK limb cannot reach targets beyond its rest chain length — that is expected behaviour;
raise `ik_stretch` (or move `cog`) to extend it.

---

## 11. Files

```
apex_rig/
  __init__.py        extension entry point (register/unregister, no bl_info)
  blender_manifest.toml
  const.py           presets, palettes, property table, motion catalogue
  proportions.py     anthropometric skeleton generator (BoneSpec list)
  rig.py             rig builder, IK/pole calibration, drivers, Rig runtime API
  widgets.py         procedural custom-shape meshes
  skin.py            capsule / bone-heat / envelope skinning + validation
  fit.py             character measurement, proportion solver, placement
  animation.py       motion library, bake, mirror, NLA helpers
  poses.py           posing primitives + 10-pose library
  deform.py          deformation toolkit, coverage + animation audit
  ui_icons.py        preview-thumbnail cache and picture buttons
  mocap.py           naming tables, retargeter, file import
  export.py          glTF / FBX exporters
  operators.py       38 operators
  properties.py      scene settings PropertyGroup
  panels.py          8 N-panel sub-panels (picture grids)
  previews/          31 thumbnail PNGs shipped with the extension
scripts/
  make_previews.py   headless thumbnail renderer (Cycles CPU, ~40 s)
  render_showcase.py six-pose beauty render (out/apex_showcase.png)
dist/apex_rig-1.1.0.zip   built with `blender --command extension build`
out/                 demo .blend, .glb, .fbx, preview and showcase renders
tests/               acceptance, deform, fit, extension and v2 regression scripts
```
