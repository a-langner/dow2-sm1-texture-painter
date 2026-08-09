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

Texture roles and the current DoW2/SM1 filename suffixes are defined in
`src/texture_naming.py`. GUI and batch workflows must use its typed texture
kinds and naming profile instead of embedding suffix strings. The application
currently uses one profile, while the architecture allows future profiles to
be passed into the same workflows.

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
python -m mypy src/texture_set.py src/texture_renderer.py src/texture_naming.py src/render_settings.py src/constant.py src/action_state.py src/texture_loading_service.py src/image_process.py src/preview_controller.py src/batch_processing_service.py src/pattern_controller.py src/pattern_exchange.py src/color_pattern_handler.py
```

When using the repository's `.venv`, replace `python` with
`.\.venv\Scripts\python.exe`.

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
