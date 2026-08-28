# Developing

Create a virtual environment and install the runtime requirements, development
requirements, and project in editable mode.

On Windows PowerShell, from the repository root:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m src.frame_main
```

On Linux or macOS:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m src.frame_main
```

On Unix-like systems, `make setup-dev` performs the environment creation and
installation without requiring activation. Afterward, `make run-dev` starts the
application through that environment.

### Widget callback rule

Widgets receive behavior through explicit `on_...` callbacks and must not reach
upward to the application root to invoke controller methods. Callbacks should
carry domain values, such as color or slider values, rather than Tk widgets.

### Texture naming profiles

Texture roles and the Dawn of War II and Space Marine 1 filename profiles are
defined in `src/texture_naming.py`. Each profile has a stable internal ID, a
display name, and suffixes for diffuse, team-colour, dirt, and specular maps.
GUI and batch workflows must use its typed texture kinds and naming profiles
instead of embedding suffix strings. The application currently selects the
DoW2 profile by default. The Game menu selects either supported profile and
persists its stable ID in `settings.json` for the next application start.

Normal maps are intentionally outside the renderer and profile model. The
existing `_drt` dirt-map workflow remains distinct and unchanged.

### Texture files, channels, and batch scope

Interactive loading accepts DDS, PNG, JPEG, BMP, TGA, TIFF, and BLP images.
Image export supports PNG, JPEG, BMP, and TGA. Companion discovery searches
exact sibling stems and permits the DIF and its TEM/PNT, DRT, and SPC files to
use different supported extensions. Optional missing companions are treated as
absent; explicitly selected invalid files are errors.

The four positional Color Slots map to the mask's red, green, blue, and alpha
channels in that order. RGB masks receive an empty alpha channel. NRM, EMI, and
OCL files are not inputs to the recolouring renderer.

Batch Edit discovers matching DIF files only in the selected source directory;
it does not recurse into subdirectories. The legacy Batch Convert path accepts
four previously extracted Dawn of War I mask images whose stems end in
`_Primary`, `_Secondary`, `_Trim`, and `_Weapon`, then writes one team-colour
mask using the currently selected naming profile. This converter does not make
Dawn of War I a supported interactive recolouring profile.

### Pattern persistence

`src/color_pattern_handler.py` owns Pattern validation and persistent storage,
`src/pattern_exchange.py` owns exchange validation and atomic import/export, and
`src/pattern_controller.py` coordinates those operations for the GUI.

Built-in Patterns are ordered, read-only package data in
`src/resources/army_pattern.json`. User Patterns retain insertion/manual order
and are stored outside the executable in `user_patterns.json` under the
`DOW2-SM1 Texture Painter` platform data directory:

- Windows: `%LOCALAPPDATA%\DOW2-SM1 Texture Painter\user_patterns.json`
- Linux: `$XDG_DATA_HOME/DOW2-SM1 Texture Painter/user_patterns.json`, or
  `~/.local/share/DOW2-SM1 Texture Painter/user_patterns.json` by default
- macOS: `~/Library/Application Support/DOW2-SM1 Texture Painter/user_patterns.json`

The current persistence wrapper uses format
`dow2-sm1-texture-painter-user-patterns`, version `1`, and an ordered `patterns`
object. Writes use a flushed temporary file followed by `os.replace`. The
loader also accepts the legacy unwrapped Pattern mapping for backward
compatibility. Replacing the application executable does not normally affect
this per-user file.

Each stored Pattern has four required `#RRGGBB` fields in stable order:

```json
{
  "primary_colour_name": "#112233",
  "secondary_colour_name": "#445566",
  "tint_colour_name": "#778899",
  "extra_colour_name": "#aabbcc"
}
```

A complete current Pattern may additionally contain:

- `processing_mode`: `global` or `per_color`
- `global_processing`: blend mode, brightness, contrast, opacity, and saturation
- `per_color_processing`: the same fields for `color_1` through `color_4`
- `marker_color`: `yellow`, `red`, `green`, `blue`, or `purple`; missing,
  `default`, and unknown values resolve to Default
- `custom_favorite_identities`: four optional `{id, name}` entries aligned with
  the Color Slots

Legacy colour-only Patterns and the earlier flat blend/brightness/contrast
shape remain supported. Missing opacity or saturation resolves to `100`.
Pattern data deliberately excludes active TEM/PNT variant identity and DRT/SPC
state.

The Pattern panel marks a selected Pattern as `Modified` when current workspace
state differs from its stored state. Save New creates a User Pattern from the
current workspace; Update, Rename, Delete, marker changes, and manual reorder
apply only to User Patterns. Built-ins cannot be modified, overwritten, or
given marker metadata.

### Pattern exchange formats

Single Pattern exchange uses `.pattern.json`, format
`dow2-sm1-texture-painter-pattern`, version `1`. Both built-in and User Patterns
can be exported. A minimal valid colour-only document is:

```json
{
  "format": "dow2-sm1-texture-painter-pattern",
  "version": 1,
  "name": "Example Pattern",
  "colors": {
    "primary_colour_name": "#112233",
    "secondary_colour_name": "#445566",
    "tint_colour_name": "#778899",
    "extra_colour_name": "#aabbcc"
  }
}
```

The optional current processing, marker, and Custom Favorite identity fields
listed above are preserved during single exchange. Imports validate the entire
document before persistence. A built-in name cannot be overwritten; a User
Pattern conflict can be renamed, overwritten, or cancelled through the UI.
Imported files are copied into application-owned persistence rather than used
as live external sources.

Pattern Collection exchange uses `.pattern-collection.json`, format
`dow2-sm1-texture-painter-pattern-collection`, version `1`:

```json
{
  "format": "dow2-sm1-texture-painter-pattern-collection",
  "version": 1,
  "name": "My Patterns",
  "patterns": [
    {
      "name": "Example Pattern",
      "colors": {
        "primary_colour_name": "#112233",
        "secondary_colour_name": "#445566",
        "tint_colour_name": "#778899",
        "extra_colour_name": "#aabbcc"
      }
    }
  ]
}
```

Collections contain User Patterns only and preserve deterministic/manual order.
The collection name is informational and is not prefixed to Pattern names. The
whole document, including duplicate names and every Pattern entry, is validated
before changes are applied. Built-in conflicts are always skipped. User
conflicts default to skip and may be overwritten only when explicitly chosen.
A confirmed collection import is committed through one atomic replacement, and
stale conflict analysis is rejected rather than overwriting newer state.

### Running tests

The project uses Python's built-in `unittest` runner. On Unix-like systems,
run the complete suite with:

```text
make test
```

GNU Make is not normally installed with Windows. Run the equivalent command
directly in PowerShell instead:

```powershell
py -m unittest discover -s tests
```

When using the repository's `.venv`, you can run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

### Static typing

Static typing is enforced incrementally. Core domain and processing modules are
type-checked first; the Tkinter presentation layer remains intentionally less
strict until its interfaces are stable. Targeted core modules must pass mypy,
new core modules should be fully annotated, and `Any` should be explicit when
it is genuinely unavoidable.

On Unix-like systems, run the current target set with:

```text
make typecheck
```

GNU Make is not normally installed with Windows. Run the equivalent command
directly in PowerShell instead:

```powershell
python -m mypy
```

When using the repository's `.venv`, replace `python` with
`.\.venv\Scripts\python.exe`.

The canonical module scope is configured once in `mypy.ini`. It covers the core
domain, rendering, loading, preview, batch, Pattern, settings, and persistence
layers. Complex Tkinter presentation and custom-dialog implementations remain
outside the enforced scope while their interfaces are migrated incrementally.
New core code must not introduce untyped public interfaces.

GitHub Actions runs the complete test suite on both Linux and Windows and runs
the canonical mypy command on Linux. The Windows job also performs a PyInstaller
packaging smoke test that verifies the executable and bundled resources; it does
not automate the graphical interface.

### Building the application

The checked-in `texture-painter.spec` is the authoritative PyInstaller
configuration. It includes the bundled, read-only resources under
`src/resources`; user Patterns, settings, and logs remain outside the bundle.

On Windows PowerShell, build the default one-folder application with:

```powershell
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm texture-painter.spec
```

For a single-file executable:

```powershell
$env:TEXTURE_PAINTER_ONEFILE = "1"
.\.venv\Scripts\python.exe -m PyInstaller --clean --noconfirm texture-painter.spec
Remove-Item Env:TEXTURE_PAINTER_ONEFILE
```

On Linux or macOS, use `make build` for a one-folder bundle or
`make build-onefile` for a single-file executable. Build output is written to
`dist/`, with temporary files under `build/`. Use `make build-clean` to remove
both output directories.
