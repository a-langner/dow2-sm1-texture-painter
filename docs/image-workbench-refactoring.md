# Rendering architecture

The `ImageWorkbench` decomposition is complete. Rendering now has three focused
domain values—`TextureSet`, `RenderSettings`, and `TextureRenderer`—with
`ArmyPainter` acting as the GUI composition root.

## Dependency flow

```text
TextureLoadingService
        |
        v
   TextureSet ----------------------+
        |                           |
        v                           v
PreviewController             full-resolution Save As
        |                           |
        +-------------+-------------+
                      |
                      v
               TextureRenderer
                      ^
                      |
               RenderSettings

BatchProcessingService
        +---- loads an isolated TextureSet per item
        +---- receives one immutable RenderSettings snapshot
        +---- reuses TextureRenderer
```

`TextureRenderer` is the single authoritative rendering implementation.

## TextureSet

`TextureSet` contains source images only:

- required RGBA diffuse image;
- optional RGB/RGBA team-colour image;
- optional RGBA dirt image;
- optional RGBA specular image.

`None` consistently represents an absent companion. The model contains no GUI,
path, Pattern, settings, persistence, preview, or rendered-output state.
Pillow images are retained by reference, and all exposed source references and
pixels are treated as read-only. `copy_for_render()` creates a shallow container
snapshot rather than copying full-resolution pixel buffers.

## RenderSettings

`RenderSettings` is a frozen value containing every pixel-affecting parameter
exactly once: four colours in canonical channel order, brightness, contrast,
alpha, dirt, specular, colour operation, and selected team-colour channels.
Validation occurs at construction. `ArmyPainter` replaces this immutable value
when GUI controls change; preview, Save As, and batch each receive a snapshot.

## TextureRenderer

`TextureRenderer` is stateless. It receives a `TextureSet` and
`RenderSettings`, returns caller-owned Pillow images, and never mutates source
pixels. It has no GUI, filesystem, filename, Pattern, settings-persistence, or
output-cache responsibility.

The preserved rendering order is team-colour application, contrast then
brightness per colour layer, black-background flattening, optional alpha, dirt,
then specular. Team-colour masks are applied once. The historical commented
soft-mask implementation remains beside the corrected algorithm for reference.

## Active texture and loading

`ImageWorkbench` is retired. No compatibility wrapper remains.

`ArmyPainter.active_texture_set` is the one authoritative interactive source
reference. `None` means no diffuse is loaded. UI placeholder images belong only
to Tk labels and are never placed in a `TextureSet`.

`TextureLoadingService` validates and decodes files, discovers companions, and
returns a complete replacement `TextureSet`. Separate channel loading also
returns a new container retaining the existing diffuse and optional companions.
The composition root swaps its active reference only after a successful load.
Closing releases the active reference, invalidates preview work, and restores
UI placeholders without changing Patterns, render settings, or geometry.

## Preview flow and thread safety

The Tk thread captures a shallow `TextureSet` container snapshot plus an
immutable `RenderSettings` value. `PreviewController` owns debounce,
cancellation, stale-generation rejection, and UI-thread result delivery. A
worker may finish using source references from an older set, but replacement or
close increments the preview generation so its result cannot update the UI.
Workers never touch Tk objects.

No full-resolution source buffers are copied for each preview. Renderer results
are owned only by requests/callers and are released when those references leave
scope. The shared renderer has no mutable request or result fields.

## Save As flow

Save As requires an active texture, synchronizes current GUI settings, renders
the active full-resolution `TextureSet` directly, and passes the explicit result
to the output helper. It does not depend on preview size, preview completion, or
cached output. Render and write failures remain separately logged and presented.

## Batch flow

`BatchProcessingService` discovers the same canonical inputs and companions,
creates one isolated `TextureSet` per item, reuses the stateless renderer, and
uses the request's immutable settings snapshot. Each item releases its images
before the next item. Output naming, overwrite behavior, atomic writes,
cancellation, progress, warnings, and structured per-item failures remain at
the batch boundary. Interactive texture state is never read or mutated.

## Dependency and behavioral guarantees

- Core rendering modules do not import Tkinter or `frame_main`.
- `TextureRenderer` does not import Pattern or settings persistence.
- Preview and batch depend on `TextureRenderer`, not GUI widgets.
- Pixel baselines cover diffuse, each/all colours, operation modes,
  brightness/contrast, alpha, dirt, specular, and the representative pipeline.
- Preview, Save As, and batch parity tests require exact pixel equality.
- Mutation and concurrency tests cover source reuse, independent settings,
  stale previews, shutdown, and renderer reuse.

## Next phase

The next planned architecture phase is:

```text
Improve typing of the newly separated core modules.
```

That phase is intentionally outside this refactoring.
