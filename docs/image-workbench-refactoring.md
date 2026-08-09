# ImageWorkbench refactoring inventory

This document records the pre-decomposition responsibilities of
`src.image_process.ImageWorkbench`. It is the baseline for introducing
`TextureSet`, consolidating `RenderSettings`, and extracting `TextureRenderer`.
The inventory describes the implementation before those migrations; Job 1 makes
no rendering or user-visible changes.

## TextureSet transition

Job 3 introduced `src.texture_set.TextureSet` as the single authoritative
container for diffuse, team-colour, dirt, and specular Pillow images.
`ImageWorkbench` owns one mutable `TextureSet` and exposes its historical image
field names as compatibility properties; there is no duplicate source-image
state. The container retains incoming image references directly to avoid large
copies. Rendering treats those images as read-only.

The container is deliberately mutable during loading so a complete image
reference can be replaced. `copy_for_render()` creates a separate container but
retains the same read-only Pillow image references. Consequently later source
reference replacement cannot alter an outstanding preview's texture selection,
while snapshot creation does not copy texture pixel buffers. File paths,
validation policy, derived channels, settings, rendered output, and GUI state
remain outside `TextureSet`. `dimensions` reports the required diffuse size;
format, mode, companion-size, and filesystem validation remain at the loading
boundary.

## RenderSettings transition

Job 4 made `src.render_settings.RenderSettings` the complete immutable settings
value. `ImageWorkbench.render_settings` is authoritative; the historical
`colors`, brightness/contrast, operation, toggle, and selected-channel
attributes are compatibility properties that create a replacement settings
value. `get_render_settings()` returns the immutable value directly,
`apply_render_settings()` replaces it, and a preview snapshot safely retains the
value that existed when the request started.

The pixel-affecting fields, in canonical order, are:

1. `primary_color`, `secondary_color`, `tint_color`, and `extra_color` as
   validated `#RRGGBB` strings;
2. `brightness` in the GUI range 0–150, defaulting to 75;
3. `contrast` in the GUI range 0–200, defaulting to 100;
4. `apply_alpha` and the immutable `tem_selected` channel-index tuple used to
   construct its mask;
5. `apply_dirt`;
6. `apply_spec`;
7. `color_op` as the existing `ColorOps` enum, defaulting to overlay.

There are no dirt or specular strength values in the current renderer. Preview
size, paths, Pattern identity, GUI selection objects, and save destinations do
not affect rendered pixels and are not settings. Colours are validated without
normalizing their case. Brightness and contrast are rejected outside their GUI
ranges rather than silently clamped. GUI strings cross the compatibility
boundary through explicit conversion to `ColorOps`; unsupported values are
rejected instead of selecting the renderer's historical fallback branch.

## TextureRenderer transition

Job 5 introduced the stateless `src.texture_renderer.TextureRenderer`. Its
primary operation is now the sole authoritative pixel pipeline:

```text
TextureSet + RenderSettings -> Pillow Image
```

It derives the RGB/RGBA team-colour bands locally, applies the four colours in
canonical order, preserves contrast-before-brightness processing, flattens over
black, applies the inverted selected-channel alpha when enabled, then
alpha-composites dirt before specular. All render state and intermediate images
are local to a call, and source Pillow images are treated as read-only.

`ImageWorkbench` remains the compatibility facade for preview, normal save, and
batch callers in this job. Its `process_coloring()`, `refresh_workspace()`, and
`refresh_team_colour_img()` methods delegate to one reusable renderer instance;
the old independent algorithm has been removed. No caller outside the facade
has been migrated yet. The renderer has no Tkinter, filesystem, persistence,
filename, output-path, preview-size, or `ImageWorkbench` dependency.

## Current state ownership

`ImageWorkbench` initializes some fields directly and creates the remaining
image fields through `set_placeholder_img()`.

| Field | Current meaning | Category | Target owner |
| --- | --- | --- | --- |
| `img_og_dif` | Required diffuse image, always held as RGBA after a real load; initially an RGBA placeholder | Source texture data | `TextureSet.diffuse` |
| `img_og_tem` | Original team-colour image (RGBA for a real RGB/RGBA load), or an L-mode placeholder/default mask | Source texture data and compatibility state | `TextureSet.team_color`; the compatibility facade may temporarily expose the old name |
| `tem_channels` | L-mode channel images split from `img_og_tem`; empty until a team-colour texture is loaded | Derived/source-preparation data | Derived once during `TextureSet` construction/loading, then supplied to `TextureRenderer` without GUI ownership |
| `img_dirt` | Optional RGBA dirt image, resized to diffuse dimensions during loading | Source texture data plus source preparation | `TextureSet.dirt`; preparation remains at the loading boundary |
| `img_spec` | Optional RGBA specular image, resized to diffuse dimensions during loading | Source texture data plus source preparation | `TextureSet.specular`; preparation remains at the loading boundary |
| `colors` | Ordered colour strings zipped with team-colour channels | Render settings | `RenderSettings` |
| `brightness` | Per-coloured-layer Pillow brightness factor expressed as a percentage; default 75 | Render settings | `RenderSettings` |
| `contrast` | Per-coloured-layer Pillow contrast factor expressed as a percentage; default 100 | Render settings | `RenderSettings` |
| `apply_alpha` | Whether the inverse selected-channel mask replaces final alpha | Render settings | `RenderSettings` |
| `apply_dirt` | Whether a present dirt image is alpha-composited | Render settings | `RenderSettings` |
| `apply_spec` | Whether a present specular image is alpha-composited | Render settings | `RenderSettings` |
| `color_op` | String value selecting overlay, multiply, or the fallback screen operation | Render settings and compatibility state | A validated field of `RenderSettings` |
| `tem_selected` | Indices used to build the alpha/team-colour preview mask; supplied by the GUI listbox | Render settings mixed with GUI-derived selection state | `RenderSettings`, represented as an immutable tuple |
| `img_workspace` | Most recently rendered image, or a diffuse/placeholder copy during initialization/reset | Transient render output and compatibility state | Return/result object owned by the preview or save caller |

There are no stored source file paths, save paths, preview-sized Pillow images,
explicit cached dimensions, cached source modes, dirt/specular strengths, or
other cached processing intermediates. `TextureLoadResult` and
`ChannelLoadResult` own paths and reported dimensions. `ArmyPainter` owns the
`ImageTk.PhotoImage` preview objects (`img_dif` and `img_tem`). Local variables
such as `gray_img`, `color_img`, `new_img`, `background`, and `tmp` exist only
during a render and are not cached.

The current `RenderSettings` frozen dataclass is a snapshot/transfer object for
the eight settings fields above. It contains no images, paths, widgets, or
rendered output, but its annotations and validation are deliberately still
minimal at this stage.

## Current method ownership

| Method | Primary classification | Current responsibilities and target |
| --- | --- | --- |
| `__init__()` | Mixes multiple responsibilities | Establishes mutable settings defaults, optional-source state, and placeholder/output state. During migration it should initialize delegated models and facade compatibility only. |
| `set_placeholder_img()` | Mutates source data; mixes responsibilities | Replaces diffuse/team sources with generated placeholders, resets channels and optional sources, and creates workspace output. Placeholder/GUI empty-state policy ultimately belongs outside the renderer. |
| `get_render_settings()` | Exposes compatibility state | Copies mutable workbench settings into an immutable `RenderSettings`. Retain temporarily, then replace with direct settings ownership/collection. |
| `apply_render_settings()` | Changes rendering settings | Copies a settings snapshot back into mutable fields, converting colours to a list and selected indices to a tuple. Retain only as a facade adapter during migration. |
| `render_snapshot()` | Prepares a preview; exposes compatibility state | Creates an uninitialized `ImageWorkbench`, shares source image/channel references, and copies settings into it. Replace with explicit `TextureSet` plus immutable `RenderSettings` arguments. |
| `process_coloring()` | Renders output | Copies diffuse into `img_workspace`, renders each non-grey colour/channel layer, and pastes it through its channel. Move unchanged to `TextureRenderer`. |
| `refresh_workspace()` | Renders output; mixes responsibilities | Runs colouring, flattens against black, optionally replaces alpha, composites dirt then specular, stores and returns output. Move the algorithm to `TextureRenderer`; callers own the result. |
| `refresh_team_colour_img()` | Prepares a preview; renders derived output | Builds the selected-channel image used for alpha and the team-colour preview. Rendering-related mask construction belongs with renderer/domain logic; preview ownership belongs to the caller/result. |
| `load_diffuse_file()` | Loads and mutates source data | Opens/validates/converts diffuse, creates a default L mask, and clears companions. File validation/loading belongs to `TextureLoadingService`; loaded images belong to `TextureSet`. |
| `load_team_colour_file()` | Loads source data; performs validation and preparation | Opens the file, enforces diffuse dimensions and RGB/RGBA mode, adds a zero alpha channel to RGB, and derives four L channels. Loading/format validation stays at the loading boundary; data belongs to `TextureSet`. |
| `_prepare_optional_map()` | Loads source data; performs validation and preparation | Opens an optional image, validates aspect ratio, resizes it to diffuse dimensions with LANCZOS, and converts it to RGBA. Loading/preparation belongs to `TextureLoadingService` or a focused loader. |
| `load_dirt_file()` | Loads and mutates source data | Delegates optional-map preparation and replaces `img_dirt`. Target is the loader plus `TextureSet.dirt`. |
| `load_specular_file()` | Loads and mutates source data | Delegates optional-map preparation and replaces `img_spec`. Target is the loader plus `TextureSet.specular`. |
| `save()` | Saves output | Saves current workspace directly, converting `.jpg` (case-sensitive today) to RGB. Move to a save/export service or caller consuming an explicit renderer result. |

Module helpers are adjacent responsibilities rather than workbench methods:
`_open_texture()` decodes, validates dimensions, loads, and copies an image away
from its file handle; `_validate_dimensions()` enforces positive dimensions and
the 16K limit; `_same_aspect_ratio()` supports optional-map validation;
`create_placeholder_img()` creates GUI empty-state imagery. `almostEquals()` is
not used by the current workbench pipeline.

## Caller inventory

### Production callers

| Caller | Current coupling |
| --- | --- |
| `TextureLoadingService` | Calls all four public load methods; reads diffuse/team image sizes; directly snapshots and restores `img_og_dif`, `img_og_tem`, `tem_channels`, `img_dirt`, and `img_spec` to make companion discovery transactional. |
| `PreviewController` | Calls `render_snapshot()` on the Tk thread, then submits `refresh_workspace()` and `refresh_team_colour_img()` on that snapshot to its worker executor. It returns both images in `PreviewResult`. |
| `ArmyPainter` normal save | Calls `ImageWorkbench.save()` after choosing a destination. The saved value is the latest `img_workspace`, normally installed from an accepted preview result. |
| `BatchProcessingService` | Creates one isolated `ImageWorkbench` per item, calls the four loaders, applies a captured `RenderSettings`, calls `refresh_workspace()`, then passes the returned image to atomic `save_processed_image()`. |
| `ArmyPainter` initialization/display | Constructs the workbench and reads its diffuse/team placeholder images to create Tk preview objects. |
| `ArmyPainter` settings callbacks | Directly writes `colors`, `brightness`, `contrast`, `tem_selected`, `color_op`, `apply_alpha`, `apply_dirt`, and `apply_spec`; `sync_render_settings()` repeats several writes before preview and batch capture. |
| `ArmyPainter` preview completion | Directly replaces `img_workspace` with an accepted background-render result, then creates Tk images from the result. |
| `ArmyPainter.close()` / reset | Calls `set_placeholder_img()`, clears channels redundantly, or assigns diffuse directly to `img_workspace` before scheduling another preview. |
| `ArmyPainter.batch_edit()` | Captures settings through `get_render_settings()` and places the immutable snapshot in `BatchProcessingRequest`. |

No production widget calls `ImageWorkbench` directly; widgets communicate
through callbacks owned by `ArmyPainter`.

### Tests

- `tests/test_texture_loading_service.py` uses a real workbench and asserts
  source loading, channel derivation, optional-map resizing/clearing, validation,
  and transactional restoration of all five source fields.
- `tests/test_batch_processing_service.py` obtains settings from a real
  workbench and compares batch output with a separately prepared workbench render.
- `tests/test_batch_texture_naming.py` patches the batch workbench and verifies
  companion lookup/loading calls.
- `tests/test_preview_controller.py` uses a workbench fake exposing
  `render_snapshot()` and verifies scheduling, stale-result rejection,
  cancellation, worker errors, and delivery.
- `tests/test_composition_root.py` patches construction to verify composition-root
  wiring.
- `tests/test_preview_geometry.py` observes installation of `img_workspace` from
  a preview result.
- `tests/test_widget_callbacks.py` observes direct settings writes and preview
  requests through an `ArmyPainter` fake.
- Several Pattern GUI tests provide small workbench/application fakes with
  `refresh_workspace()`; they exercise the GUI compatibility boundary rather
  than the renderer itself.

There is not yet a dedicated pixel-characterization test module for
`ImageWorkbench`; that is intentionally the next job.

## Exact current rendering order

The order below is normative for the decomposition. Brightness and contrast do
not currently apply to the whole finished image; they apply independently to
each non-grey team-colour layer before that layer is pasted.

1. Copy `img_og_dif` into `img_workspace`.
2. Zip `colors` with `tem_channels`; extra values on either side are ignored.
3. Parse each colour with `ImageColor.getrgb()` and skip exactly
   `(128, 128, 128)`.
4. For every remaining pair, copy the original diffuse to `gray_img`.
5. Create a solid RGBA `color_img` at diffuse dimensions.
6. Combine `gray_img` and `color_img` using overlay, multiply, or screen. Any
   `color_op` other than the overlay and multiply values currently falls back to
   screen.
7. Apply Pillow contrast enhancement to that combined layer using
   `contrast / 100`.
8. Apply Pillow brightness enhancement to the contrasted layer using
   `brightness / 100`.
9. Paste the layer into `img_workspace` using the corresponding L channel once
   as the paste mask.
10. Create an opaque black RGBA background and alpha-composite the coloured
    workspace over it. This discards the diffuse's original transparency before
    optional team-colour alpha is applied.
11. If `apply_alpha` is true, build the selected-team-channel image: create a
    black L image, then for each index in `tem_selected`, paste that channel into
    it using the same channel as mask. If there are no derived channels, return
    `img_og_tem` instead. Invert the returned image and install it as workspace
    alpha with `putalpha()`.
12. If `apply_dirt` is true and `img_dirt` exists, alpha-composite dirt over the
    workspace.
13. If `apply_spec` is true and `img_spec` exists, alpha-composite specular over
    the current workspace.
14. Store and return the resulting Pillow image without a final mode conversion.
    Normal JPEG saving later converts it to RGB; other saves preserve its mode.

The team-colour preview independently calls the selected-channel construction
described in step 11 and returns that image without inversion. The apparent
double use of a channel in that preview/mask construction is existing behavior
and must not be silently changed while extracting the renderer.

## Pillow mutation and reuse

- `Image.copy()`, `Image.new()`, `ImageChops.overlay/multiply/screen/invert()`,
  `ImageEnhance.*.enhance()`, `Image.alpha_composite()`, `convert()`, `resize()`,
  `split()`, and `Image.merge()` produce distinct images in the ways used here.
- `img_workspace.paste(...)` mutates the workspace copy in place for every
  colour layer.
- `new_img.paste(...)` mutates the newly created L selected-channel image in
  place. It does not mutate the channel used as its mask.
- `img_workspace.putalpha(...)` mutates the current workspace in place.
- Pillow `save()` writes external data but does not intentionally mutate the
  image; JPEG conversion creates a separate RGB image first.
- Loading retains copies independent of open file handles. Optional-map resize
  and conversion replace local references rather than modifying the decoded
  image in place.
- The diffuse, original team-colour image, derived channel images, dirt image,
  and specular image must remain reusable and must be treated as read-only by
  rendering. Current rendering does not intentionally mutate them.
- `refresh_team_colour_img()` returns the actual `img_og_tem` reference when
  there are no channels. Consumers therefore must not mutate that result.
- `img_workspace` is deliberately mutable/transient and is overwritten on each
  render or accepted preview. Normal save currently relies on that shared field
  containing the desired latest output.

## Threading and snapshot risks

`ArmyPainter` owns a one-worker preview executor. On the Tk thread,
`PreviewController` debounces requests and calls `render_snapshot()`. The worker
then renders only the snapshot. Result polling and `ImageTk` creation occur on
the Tk thread. Request IDs reject stale results, and invalidation attempts to
cancel futures that have not started.

The snapshot copies setting containers/values: colours become a fresh list and
selected indices become a tuple. Later GUI settings writes therefore do not
change an outstanding render's settings. It does **not** copy Pillow source
images or channel images; it shares their references in accordance with the
current read-only rendering convention. The worker writes only a new snapshot
`img_workspace`.

Loading replaces whole source references rather than editing the old sources,
so an already-running snapshot can finish against the old texture set. Diffuse
loading then invalidates the controller, causing that result to be rejected.
The invalidation currently occurs after synchronous loading completes, leaving
a narrow interval in which an old request can finish, although Tk-thread result
delivery cannot interleave inside the synchronous load callback. Explicit
`TextureSet` snapshots will make this ownership clearer.

Risks to preserve or eliminate deliberately during migration are:

- public mutable source/settings fields allow callers to create inconsistent
  combinations without validation;
- source images are shared across threads and safety depends on every renderer
  and caller treating them as read-only;
- normal saving consumes shared `img_workspace`, not an explicit render result;
- `TextureLoadingService` knows and restores the workbench's internal field
  tuple transactionally;
- `refresh_team_colour_img()` can return `None` for an out-of-range selected
  channel after partially building its local image;
- `tem_selected` is inconsistently initialized as a list and later stored as a
  tuple, while other settings also have mutable facade forms;
- batch rendering is isolated per item, but preview and GUI share the primary
  workbench facade.

## Target ownership and dependency direction

| Current responsibility | Target owner |
| --- | --- |
| Diffuse/team/dirt/specular images | `TextureSet` |
| Prepared team-colour channels | `TextureSet` or a renderer-facing prepared source representation, with one authoritative source state |
| Render parameter values | Immutable `RenderSettings` |
| Rendering algorithm | `TextureRenderer` |
| Rendered preview/output | Caller/result object |
| Image saving | Save/export service or caller |
| Texture discovery, decoding, validation, and companion preparation | `TextureLoadingService` and focused non-GUI loading helpers |
| GUI control and preview image state | `ArmyPainter` and widgets |

The intended dependency direction is:

```text
TextureSet
    no GUI dependencies

RenderSettings
    no GUI dependencies

TextureRenderer
    depends on TextureSet + RenderSettings
    no Tkinter dependencies
    no persistence dependencies

PreviewController
    uses TextureRenderer

BatchProcessingService
    uses TextureRenderer

GUI/save workflows
    consume renderer results
```

Pattern persistence and texture naming remain outside this decomposition.

## Migration path and compatibility facade

`ImageWorkbench` should remain temporarily as a compatibility facade. It can
first delegate source ownership to one `TextureSet`, then hold one authoritative
immutable `RenderSettings`, and finally delegate rendering to
`TextureRenderer`. Compatibility properties and methods should translate old
callers without creating duplicate mutable image or setting state.

A safe staged path is:

1. Add pixel-regression and non-mutation characterization tests for the exact
   pipeline above.
2. Introduce `TextureSet` as the single source-image owner and adapt the facade
   without migrating preview, save, or batch callers yet.
3. Complete and harden immutable `RenderSettings`; facade setters replace the
   settings value instead of maintaining a second authority.
4. Extract the characterized operations, in their current order, to a
   non-GUI/non-persistence `TextureRenderer` returning explicit result images.
5. Migrate preview and batch to pass `TextureSet` plus `RenderSettings` directly.
6. Make normal save consume an explicit accepted/rendered result through a save
   boundary, and remove loading/save responsibilities from the facade.
7. Reduce or remove `ImageWorkbench` only after all production callers and
   compatibility tests have migrated.

Pixel identity includes channel ordering and single-mask colour application;
the skip for neutral grey; operation fallback behavior; contrast-before-
brightness on each layer; black flattening before optional alpha; selected-mask
construction and inversion; dirt-before-specular composition; optional-map
LANCZOS resizing and RGBA conversion; and final image modes. None of these are
assumed interchangeable during the refactor.
