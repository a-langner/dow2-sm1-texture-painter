


https://user-images.githubusercontent.com/7768858/124058067-f3dfa780-da28-11eb-8335-7c35456467c7.mov

# Dawn of War 2 texture painter

This is a GUI desktop application that allows the user to recolor Dawn of War 2 grayscale diffuse texture using the default army color pattern from the game.

Dawn of War 2 engine uses shader & pre-defined color pattern to colorize their texture. Those textures are grayscaled by default.

The goal is to reproduce the engine coloring to export those textures with their color pattern.

Users can also make their custom army pattern and save it. Batch editing is supported, you can set a pattern to apply it to every texture in a folder.


![](https://i.imgur.com/VXFjzkh.jpg)
_dow2 texture painter application loaded with the hormagaunt grayscale diffuse texture._

## How to use

This tool was made to precisely work with Dawn of War 2 textures to reduce
editing time.

Dawn of War 2 unit textures are composed of the following files:
* {unit_name}_dif.dds -> diffuse
* {unit_name}_tem.dds -> team color mask
* {unit_name}_drt.dds -> dirt
* {unit_name}_spc.dds -> specular
* {unit_name}_emi.dds -> emissive
* {unit_name}_ocl.dds -> oclusion
* {unit_name}_nrm.dds -> normal map

This tool assumes that the textures are located in the unit folder, e.g a folder
named "space marine" contains all textures for a space marine model.
Emissive, oclusion and normal map textures are not useful to color the diffuse texture.

Click on `File -> Open` and select a diffuse texture, it will load the
{unit_name}_tem.dds texture located in the same folder, the team color file
contains RGBA color masks which are necessary for mapping the colored part of the
diffuse texture. Can open following format: DDS, PNG, JPG, BMP, TGA and BLP.

Click on the top left boxes to pick a color that correspond to the following mask of the
team color texture:
* Color 1 -> red mask
* Color 2 -> green mask
* Color 3 -> blue mask
* Color 4 -> alpha mask

![dow2-texture-mask](https://user-images.githubusercontent.com/7768858/124062661-5fc60e00-da31-11eb-97f7-2e8f04c45974.png)
_Using red, green and white for the coloring._


Once you're done, you can save your edit by clicking on `File -> Save`, can save
with the following format: PNG, JPG, BMP and TGA.

The application loads the default color pattern from Dawn of War 2, you can
select them on the list located bottom right.

### Saved color patterns

Built-in patterns are bundled with the application and are read-only. Custom
patterns are stored persistently outside the executable and are marked with
`★` in the pattern list.

The custom-pattern file is stored at:

* Windows: `%LOCALAPPDATA%\SM1-DOW2 Texture Painter\user_patterns.json`
* Linux: `$XDG_DATA_HOME/SM1-DOW2 Texture Painter/user_patterns.json`, or
  `~/.local/share/SM1-DOW2 Texture Painter/user_patterns.json` by default
* macOS: `~/Library/Application Support/SM1-DOW2 Texture Painter/user_patterns.json`

Updating or replacing the application executable does not normally remove
custom patterns because this file is stored separately.

### Editing color patterns

The Pattern panel uses a 2×2 button layout: `Save New`, `Update`, `Rename`, and
`Delete`.

* `Save New` creates a custom Pattern from the colors currently shown, whether
  a built-in or custom Pattern is selected.
* `Update` replaces the stored colors of the selected custom Pattern.
* `Rename` changes only the selected custom Pattern's name.
* `Delete` permanently removes the selected custom Pattern.

Only custom, user-created Patterns can be updated, renamed, or deleted.
Built-in Patterns remain read-only. Editing operations are stored persistently
and remain available after restarting the application.

`Modified` appears when the current colors differ from the selected Pattern's
stored colors. Color changes are not saved automatically: use `Update` to keep
them, or `Edit -> Reset to Selected Pattern` to discard them. To create a new
custom Pattern from any selected Pattern's stored colors, use
`Edit -> Duplicate Selected Pattern…`.

Pattern import and export behavior is unchanged.

### Importing and exporting patterns

The `Patterns` menu contains commands for single patterns and Pattern
Collections:

* `Import Pattern…`
* `Export Selected Pattern…`
* `Import Pattern Collection…`
* `Export All User Patterns…`

For single-pattern exchange, both built-in and custom patterns can be exported.
Pattern exchange files use the `.pattern.json` suffix and contain versioned
JSON, for example:

```json
{
  "format": "sm1-dow2-texture-painter-pattern",
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

Imported patterns become custom, user-created patterns and receive the `★`
marker in the pattern list. They are copied into persistent user storage, so
deleting the original `.pattern.json` file later does not delete the imported
pattern.

Built-in patterns cannot be overwritten. If an imported name matches an
existing custom pattern, the application asks whether to rename the import,
overwrite the existing pattern, or cancel. Nothing is overwritten without
confirmation.

### Pattern Collections

`Export All User Patterns…` saves all custom, user-created patterns in one
versioned JSON file with the `.pattern-collection.json` suffix. Built-in
patterns are never included. The Collection name is informational and is not
added to the names of its patterns.

```json
{
  "format": "sm1-dow2-texture-painter-pattern-collection",
  "version": 1,
  "name": "My Space Marine Patterns",
  "patterns": [
    {
      "name": "Blood Ravens Veteran",
      "colors": {
        "primary_colour_name": "#7f1919",
        "secondary_colour_name": "#d1b989",
        "tint_colour_name": "#242424",
        "extra_colour_name": "#ffffff"
      }
    }
  ]
}
```

`Import Pattern Collection…` validates the entire Collection before saving
anything. If one pattern is invalid, or if names are duplicated within the
Collection, the whole Collection is rejected. A confirmed import is atomic, so
it is saved as one operation rather than as a series of partial imports.

Names that conflict with built-in patterns are always skipped because built-in
patterns cannot be overwritten. For names that conflict with existing custom
patterns, you can skip or overwrite them; **Skip existing user patterns** is the
default. Collection import does not automatically rename conflicting patterns.

Single-pattern import and export remain available separately through
`Import Pattern…` and `Export Selected Pattern…`.

You can apply dirt & specular texture by clicking on `Edit -> Apply dirt/specular`,
those textures must be in the same folder as the diffuse ones and their filenames must
follow the following pattern.
* {unit_name}_drt.dds -> dirt
* {unit_name}_spc.dds -> specular

You can replace color by transparency with selecting the color mask in the list
and checking the  `Apply alpha` box.

You can color multiple diffuse textures by using the batch edit tool, select the source
directory where your textures are located, input format, output format and the
destination directory, the name of the colored files will be the same as the
original one, if input & output file have the same format, the output will overwrite
the original diffuse texture. Batch edit tool does not process subfolder.
Batch edit only works for diffuse texture ending with "_dif", such as {unit_name}_dif.dds,
because it's the name format for Dawn of War 2 diffuse texture.

## Dawn of War 1 Texture
Dawn of War 1 uses a different format to store their tem textures, the 4 masks are
separated into individual file stored in a RTX file, once you extract them with a third party tool, you can merge
them into a single file using the batch tool editor. The converted texture can then
be used to color Dawn of War 1 diffuse grayscale texture.

This tool is experimental and only process files from a folder in a "batch" manner.

Click `Tools` -> `Batch Edit Tools` -> `Process Batch Convert` to convert Dawn of War 1
tem textures to Dawn of War 2 tem format.

![example4](https://user-images.githubusercontent.com/7768858/148760310-08c01d18-182b-4680-a092-9e7689f4cb93.jpg)

Dawn of War 1 Trim 2 & Eye coloring aren't handled yet.

## Developing

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

GitHub Actions runs the complete test suite on both Linux and Windows. The
Windows job also performs a PyInstaller packaging smoke test that verifies the
executable and bundled resources; it does not automate the graphical interface.

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
