# Block 4 Job 1: Post-Block-3 processing inspection

This is an inspection-only record of the state before Global/Per Color
processing is introduced. No runtime behaviour or persisted schema is changed
by Job 1.

## Runtime ownership and UI writes

- `ArmyPainter.render_settings` is initialized from the immutable
  `DEFAULT_RENDER_SETTINGS` in `frame_main.py`. It is the authoritative runtime
  snapshot for interactive rendering and contains four colour strings plus one
  global `color_op`, `brightness`, and `contrast` value. It also contains alpha,
  DRT/SPC, and selected TEM/PNT-channel state.
- The four current colours are also held presentation-first in
  `FrameColorChooser.color_boxes`: four separate Tk Canvas `bg` values in a
  list. They are not four structured colour-slot domain objects.
- `FrameSlider` owns the two Tk Scale values. A slider callback requests a
  preview; `ArmyPainter.sync_render_settings()` then reads both controls and
  replaces the global brightness and contrast in `render_settings`.
- `FrameColorOps` owns a display-name `StringVar` and a read-only selector built
  from `IMPLEMENTED_BLEND_MODES`. Its callback emits a stable blend ID;
  `ArmyPainter.color_operation_update()` parses it and replaces the single
  global blend mode in `render_settings`.
- A confirmed Color Picker result writes the selected Canvas background. The
  application later copies all four Canvas values into the four named colour
  fields of `RenderSettings` during synchronization.
- The selected Pattern is Treeview selection state exposed as a
  `PatternSelection`; there is no separate active-Pattern domain field in
  `ArmyPainter`.

## Rendering and preview reads

- `ArmyPainter.create_preview_request()` snapshots the active `TextureSet` and
  the current immutable `RenderSettings`. `PreviewController` debounces work,
  rejects stale results, and calls the stateless `TextureRenderer` off the Tk
  thread.
- `TextureRenderer._apply_team_colors()` zips the four colours with the RGBA
  mask channels, but applies the same `settings.color_op`, brightness, and
  contrast to every channel. This loop is the key per-colour integration point.
- The Block 3 blend implementations are centralized in that loop. Contrast and
  brightness are applied to each generated colour image before the channel is
  pasted exactly once.
- After team colouring, `TextureRenderer.render()` preserves the existing order:
  flatten over black, optional alpha, optional dirt/DRT composite, then optional
  specular composite. TEM/PNT variant selection replaces only the team-mask
  image in the active `TextureSet`; its selected RGBA channels remain in
  `RenderSettings.tem_selected` and are independent of Pattern persistence.
- Save As calls the same renderer after synchronizing controls. Batch processing
  captures the same `RenderSettings` in `BatchProcessingRequest` and renders
  every discovered DIF through the same renderer and naming-profile pipeline.

## Pattern storage and loading

- Pattern colours use four established flat keys:
  `primary_colour_name`, `secondary_colour_name`, `tint_colour_name`, and
  `extra_colour_name`.
- Optional global processing uses three additional flat keys: `blend_mode`,
  `brightness`, and `contrast`. `PatternProcessing` is a `NamedTuple` containing
  precisely those global values. Save New, Update, Duplicate, dirty-state
  comparison, and Pattern application pass through `PatternController` and
  `color_pattern_handler`.
- User Pattern persistence is a version-1, atomically replaced JSON document.
  Its validator currently accepts either exactly the four colour keys or those
  four followed by all three global processing keys. Stable blend IDs are stored.
- Patterns without processing keys, including all packaged built-ins, resolve
  through `get_pattern_processing()` to Overlay / 75 / 100. Invalid stored
  processing also falls back safely to those defaults. Applying a Pattern writes
  its colours to the four Canvases and its global processing to
  `render_settings`, the blend selector, and both sliders before refreshing.
- Single and collection Pattern exchange formats currently serialize colours
  only. Import therefore creates colour-only Patterns which receive default
  global processing when selected. This is a separate schema surface that Job
  12/14 must deliberately extend or explicitly preserve for compatibility.
- Application settings do not persist the active Pattern, current colours, or
  processing controls. There is no general undo/redo or command-history system.
  Pattern Reset reloads stored values, while dirty state is derived by comparing
  current GUI colours/global processing with the selected stored Pattern.

## Limitations relevant to per-colour processing

1. `RenderSettings` mixes four colour values with only one processing triple;
   the renderer cannot select processing by channel without a new reusable
   per-context model.
2. The same logical processing state is mirrored across `render_settings` and
   three Tk widget values. Slider values become authoritative during sync, while
   blend callbacks update `render_settings` immediately. This split ownership
   needs a single runtime model before controls can switch editing context.
3. Colour slots are Canvas widgets plus positional list indexes, not structured
   objects, and clicking a Canvas immediately opens the picker. There is no
   active-slot state independent of colour editing.
4. `PatternProcessing`, validation, persistence, dirty comparison, duplication,
   reset/application, and exchange all assume at most one global triple. All
   must be evolved together to avoid silently dropping per-colour values.
5. Programmatic Pattern application sets the combobox and sliders. Tk Scale
   callbacks can request intermediate previews, so later context refreshes need
   a guard against treating programmatic control updates as user edits.
6. Preview, Save As, and batch already share one immutable settings snapshot.
   Extending that snapshot is preferable to adding GUI-aware renderer state and
   is necessary to retain pixel parity.

## Preservation boundaries for subsequent jobs

- Keep stable Block 3 blend IDs, presentation ordering, and blend mathematics.
- Keep RGBA-to-Color 1-4 positional mapping and single mask application.
- Keep TEM/PNT variants asset-scoped and outside Pattern data.
- Keep DRT discovery/loading and post-team-colour compositing unchanged.
- Keep DoW2 and SM1 on the shared renderer and keep NRM ignored.
