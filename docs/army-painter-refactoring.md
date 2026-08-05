# ArmyPainter refactoring map

This document records the current responsibilities in `src/frame_main.py` and
the intended boundaries for their incremental extraction. It describes the
architecture before extraction; it does not change application behavior.

## Current responsibility inventory

| Responsibility | Current methods and free functions | Important state | Current kind | Proposed long-term owner |
| --- | --- | --- | --- | --- |
| Tk root and main-window lifecycle | `ArmyPainter.__init__()`, `main()`, `on_exit()` | `closing`, window protocol, icon | Tkinter presentation | `ArmyPainter` as composition root and top-level owner |
| Widget creation and layout | `define_frame_workspace_tool()`, `define_frame_workspace()`, `open_batch_edit_tools()`, `close_batch_edit_tools()` | `frame_img_tools`, `frame_img`, `frame_color_chooser`, `frame_color_op_option`, `frame_channel_select`, `frame_sliders`, `frame_army_pattern`, `frame_batch_tools`, image labels | Tkinter presentation | `ArmyPainter`; existing focused widget classes remain widgets |
| Menu creation and action state | `define_menu()`, `activate_pattern_panel_callbacks()`, `update_pattern_action_states()`, `is_selected_pattern_dirty()`; `pattern_action_states()` in the Pattern policy module | `pattern_menu`, `apply_dirt`, `apply_spec`, current Pattern selection and colors | Tkinter presentation plus application orchestration and pure policy | `ArmyPainter` renders menus; an `ActionStateCoordinator` coordinates state; pure policy stays in the Pattern policy module |
| File-dialog presentation | `save()`, `load_file()`, `open_diffuse()`, `open_channel()`, Pattern and Collection import/export methods, Pattern save/rename/duplicate methods | Tk parent, file filters, suggested filenames | Tkinter presentation | Narrow Tk-specific `DialogGateway` |
| Remembered import/export directories | `open_diffuse()`, `import_pattern()`, `export_selected_pattern()`, `import_pattern_collection()`, `export_all_user_patterns()` | `settings`; selected source/destination paths | Application orchestration plus persistence | `SettingsHandler` owns persistence; a `FileSelectionService` coordinates selection and success-only updates |
| Diffuse and channel loading | `load_file()`, `load_channel_packed_file()`, `load_dirt_file()`, `load_spec_file()`, `open_diffuse()`, `open_channel()` | `img_wbench`, `og_filename`, `texture_naming_profile` | Application orchestration plus filesystem/domain work | `TextureLoadingService`, with `ArmyPainter` retaining user interaction and post-load UI actions |
| Automatic companion discovery | free function `find_companion_texture()` and calls in `load_file()` | `texture_naming_profile`, diffuse path | Pure filesystem policy | `TextureLoadingService`, using `TextureNamingProfile` helpers |
| Texture validation and error presentation | `_check_diffuse_format()`, `load_file()`, `open_diffuse()`, `open_channel()` and `ImageWorkbench` load methods | supported file types, current workbench state | Domain validation mixed with Tkinter presentation | validation/loading in `TextureLoadingService`; messages through `ArmyPainter` and `DialogGateway` |
| Preview scheduling and debounce | `refresh_workspace()`, `schedule_preview_refresh()`, `start_preview_refresh()` | `preview_after_id`, `preview_generation`, `closing` | Application orchestration | `PreviewController` using injected Tk scheduling callbacks |
| Background preview execution | `start_preview_refresh()` and free function `render_preview()` | `preview_executor`, `preview_futures`, workbench render snapshots | Background execution | `PreviewController`; `render_preview()` remains a stateless worker |
| Preview-result delivery to Tk | `poll_preview_result()` | `preview_generation`, `preview_futures`, `img_wbench.img_workspace`, `img_dif`, `img_tem`, preview labels | Background coordination plus Tkinter presentation | `PreviewController` validates/delivers results through an injected `ArmyPainter` presentation callback |
| Pattern creation, editing, deletion, import, and export | `save_pattern()`, `get_current_pattern_colors()`, `update_selected_pattern()`, `reset_to_selected_pattern()`, `rename_selected_pattern()`, `duplicate_selected_pattern()`, `delete_pattern()`, `import_pattern()`, `_show_pattern_import_error()`, `_choose_pattern_import_conflict()`, `_request_pattern_import_name()`, `_report_invalid_pattern_import_name()`, `export_selected_pattern()`, `apply_selected_pattern_colors()`; free functions `suggested_pattern_filename()`, `single_import_selection_policy()`, `resolve_pattern_import_conflicts()` | Pattern widget selection, color boxes, `settings`, `pattern_menu` | Tkinter presentation, orchestration, persistence, and pure policy | `PatternController`; persistence and policy remain in focused Pattern modules; dialogs remain in GUI boundary |
| Pattern Collection import and export | `import_pattern_collection()`, `export_all_user_patterns()`; free functions `suggested_pattern_collection_filename()`, `format_collection_import_result()`, `collection_selection_was_overwritten()` | current selection/colors, `settings`, Pattern list and menu state | Tkinter presentation, orchestration, persistence, and pure policy | `PatternController`, reusing existing Collection domain and persistence APIs |
| Batch recoloring | `open_batch_edit_tools()`, `close_batch_edit_tools()`, `_check_batch_path()`, `_check_diffuse_format()`, `get_batch_edit_input()`, `start_batch_job()`, `cancel_batch()`, `poll_batch_job()`, `batch_edit()`; free functions `prepare_batch_workbench()`, `save_processed_image()`, `batch_edit_worker()` | `frame_batch_tools`, `batch_executor`, `batch_future`, `batch_cancel`, `batch_events`, current Pattern colors and render settings | Tkinter presentation, filesystem processing, and background execution | `BatchProcessingService`; `ArmyPainter` owns the batch window and presents progress/results |
| Dawn of War 1 conversion | `batch_convert()` and free function `batch_convert_worker()` | batch window values, `batch_executor`, cancellation and event queue, `texture_naming_profile` | Application orchestration, filesystem processing, and background execution | `Dow1ConversionService` or focused existing converter functions coordinated by `BatchProcessingService` |
| Window sizing and positioning | `__init__()`, `resize_for_diffuse()`; free functions `calculate_initial_window_size()`, `calculate_diffuse_window_size()`, `clamp_window_position()`, `is_window_maximized()` | minimum dimensions, screen dimensions, current geometry/window state | Tkinter presentation plus pure policy | `ArmyPainter` applies geometry; stateless geometry helpers remain module-level policy functions |
| Logging and unexpected-error presentation | `show_user_pattern_load_warning()`, `open_log_folder()`, `report_callback_exception()`; free functions `appears_to_run_from_pyinstaller_bundle()`, `log_application_startup()`, `main()` | `application_log_path`, `_handling_callback_exception`, `user_pattern_warning_shown` | Application lifecycle plus Tkinter presentation | startup logging stays at the composition boundary; `ArmyPainter` retains Tk callback handling; dialogs use `DialogGateway` |
| Shutdown and executor cleanup | `close_batch_edit_tools()`, `cancel_batch()`, `on_exit()` | `closing`, both executors, futures, scheduled callback identifier, cancellation event | Application orchestration and background execution | `ArmyPainter` initiates shutdown; preview and batch owners expose deterministic cancellation/close methods |

The free filename and geometry helpers are already appropriate candidates for
stateless policy. Worker functions are also useful process boundaries, but the
submission, cancellation, polling, and Tk delivery around them are still owned
by `ArmyPainter`.

## Target ownership map

| Responsibility | Proposed owner |
| --- | --- |
| Tk widget construction and top-level lifecycle | `ArmyPainter` |
| Application composition and dependency wiring | `ArmyPainter` |
| File dialogs and simple prompts | `DialogGateway` |
| Initial-directory selection and success-only remembering | `FileSelectionService` plus `SettingsHandler` |
| Texture validation, loading, and companion discovery | `TextureLoadingService` |
| Preview debounce, generations, executor, and result coordination | `PreviewController` |
| Pattern and Collection workflow orchestration | `PatternController` |
| Pattern persistence, validation, and conflict policy | Existing focused Pattern modules |
| Batch processing and conversion execution | `BatchProcessingService`, delegating conversion domain work to the existing converter module |
| Menu and button state coordination | `ActionStateCoordinator`, using existing pure Pattern action policy |
| Window geometry application | `ArmyPainter` |
| Window geometry calculations | Existing stateless helpers |
| Image state and rendering during this series | Existing `ImageWorkbench` |

Not every row implies a class. Geometry, filename, selection, and result-format
policies should remain focused functions where they do not need lifecycle or
mutable state.

## Dependency direction

The allowed direction is:

```text
Widgets -> callbacks only
ArmyPainter -> controllers/services
Controllers -> domain and persistence APIs
Services -> filesystem/domain helpers
Domain modules -> no Tkinter imports
```

Additional rules:

- `ArmyPainter` remains the composition root and owns the Tk root, widgets,
  menus, and application-level presentation callbacks.
- Controllers and services must not import or discover `ArmyPainter`.
- Non-GUI services must not import Tkinter or display message boxes.
- Controllers may request presentation through injected callbacks or a narrow
  dialog interface; specialized multi-action dialogs may remain in the GUI
  layer.
- Widgets communicate outward only through their explicit callback contracts.
- Persistence and domain modules return values or raise domain-specific
  exceptions instead of presenting errors.
- `ImageWorkbench` remains unchanged during this job series except for a small
  compatibility call if an extraction cannot otherwise preserve behavior.
- A later TextureSet/Renderer refactor is a separate phase and must not be
  pulled into these extractions.

## High-risk coupling before extraction

- `sync_render_settings()` reads colors, slider values, and channel selection
  from three widget groups and writes them into shared `ImageWorkbench` state.
  Preview, Pattern-dirty detection, batch setup, and saves all depend on that
  state being synchronized at the correct time.
- `load_file()` mutates the workbench, discovers and loads three companion
  types, may open a channel dialog, shows validation errors, refreshes the
  preview, and resizes the window. Failure after diffuse loading can therefore
  leave partially changed texture state.
- `open_diffuse()` couples a dialog, format validation, texture mutation,
  filename state, remembered-directory persistence, error presentation, and
  diffuse-specific geometry.
- `schedule_preview_refresh()`, `start_preview_refresh()`, and
  `poll_preview_result()` share generation counters and futures while crossing
  from widget reads to worker execution and back to Tk image objects. They must
  preserve Tk-thread ownership and ignore stale results during extraction.
- `start_batch_job()` and `poll_batch_job()` similarly combine worker
  submission, cancellation, queue processing, batch-window updates, dialogs,
  and window lifetime checks.
- Pattern mutation methods combine selection lookup, multiple color-widget
  reads, confirmation/name dialogs, persistence, list refresh, preview refresh,
  and menu/button state. Their tests commonly need a substantial
  `ArmyPainter`-shaped object.
- `import_pattern()` and `import_pattern_collection()` combine filesystem
  parsing, detailed exception mapping, conflict dialogs, persistence,
  remembered directories, selection restoration, color application, and state
  synchronization.
- `update_pattern_action_states()` depends simultaneously on Treeview
  selection, current color widgets, Pattern persistence, button state, and menu
  entries. It is called during construction and list refresh, making callback
  timing particularly sensitive.
- `img_wbench`, Pattern selection, current color widgets, and preview generation
  form implicit shared state: changing a Pattern or texture can schedule work
  based on values owned by several different UI components.
- Shutdown spans Tk timers, preview futures, a batch future, an event queue,
  cancellation flags, and two executors; extracted owners must have an explicit
  shutdown order and must not schedule Tk callbacks after destruction.

## Recommended extraction order

1. Introduce the narrow Tk-specific `DialogGateway`. This removes module-level
   dialog patching from workflow tests without moving orchestration.
2. Extract file-selection and remembered-directory coordination, preserving
   the existing success-only update points.
3. Extract texture loading and companion discovery behind structured results,
   while leaving preview scheduling and geometry in `ArmyPainter`.
4. Extract preview scheduling, executor ownership, stale-result policy, and
   shutdown into `PreviewController` with injected Tk scheduling and delivery
   callbacks.
5. Extract Pattern and Pattern Collection orchestration after dialog and file
   selection dependencies are narrow and injectable.
6. Extract menu/button synchronization into `ActionStateCoordinator` once the
   Pattern controller exposes a stable selection and dirty-state view.
7. Extract batch recoloring and Dawn of War 1 conversion execution, reusing the
   preview/render policy rather than coupling services to widgets.
8. Finish lifecycle wiring and executor cleanup in the composition root, then
   verify development and packaged startup.

At every step, keep the extraction behavior-preserving and leave Tk widget
construction, top-level ownership, and geometry application in `ArmyPainter`.
