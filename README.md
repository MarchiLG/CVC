# Computer Vision Central

Python application for monitoring multiple IP cameras with computer
vision: object detection and tracking (YOLO, with detection/OBB/
segmentation/pose/classification support), employee face recognition,
item counting, PPE compliance checks, missing-product detection, car
identification (trademark/color/plate), 3D-print failure monitoring,
notifications (log, desktop and/or database), condition → action
triggers that drive external IO devices (MQTT, Modbus TCP, HTTP
webhook), and natural-language summaries produced by a local LLM
through Ollama.

There are **two interfaces** on top of the same backend, and you pick
which one to use when you start it:

| Interface | How to run | What it is |
|---|---|---|
| **Desktop** | `./run.sh` | Native GUI in PySide6 (Qt), no browser |
| **Web** | `./run-html.sh` | UI in HTML/CSS/JS opened in the browser, served by a local server (FastAPI) |

Both show the same cameras and the same alerts, and edit the same
configuration files — only the presentation layer differs. Neither
replaces the other.

The interface is available in **English (the default) and
Portuguese** — see [Language](#language).

## Contents

- [Architecture](#architecture)
- [Installation](#installation)
- [Configuration](#configuration)
- [Camera credentials & encryption](#camera-credentials--encryption)
- [Language](#language)
- [Running](#running)
- [Using the interface](#using-the-interface)
- [Web interface](#web-interface)
- [Available vision tasks](#available-vision-tasks)
- [Triggers](#triggers)
- [Optional features](#optional-features)
- [Tests](#tests)
- [Where the files live](#where-the-files-live)
- [Resetting the application](#resetting-the-application)
- [Troubleshooting](#troubleshooting)

## Architecture

```
src/
├── main.py            # entry point of the desktop GUI (PySide6)
├── main_web.py        # entry point of the web interface (FastAPI + browser)
├── bootstrap.py       # assembles and starts the backend — shared by BOTH interfaces
├── i18n.py            # the single translation catalog, shared by BOTH interfaces
├── camera/
│   ├── camera_stream.py    # continuous capture of ONE camera on its own thread (OpenCV)
│   └── camera_manager.py   # loads cameras.yaml and orchestrates one CameraStream per camera
├── config/
│   ├── schema.py            # configuration dataclasses (cameras, tasks, app.yaml)
│   ├── loader.py            # reading/parsing cameras.yaml, tasks.yaml and app.yaml
│   ├── writer.py            # writing tasks.yaml preserving comments (ruamel.yaml)
│   └── calibration.py       # line/zone rules, shared by both interfaces
├── vision/
│   ├── detector.py          # runs the YOLO model (ultralytics) over a frame
│   ├── tracker.py           # object tracking across frames
│   ├── device.py            # automatic device resolution (cuda/cpu) and default model
│   ├── model_registry.py    # cache of loaded YOLO instances, per (model, device)
│   ├── overlay.py           # draws the boxes onto the frame, used by both interfaces
│   └── face/recognizer.py   # face recognition (InsightFace)
├── pipeline/
│   ├── builder.py            # assembles one CameraPipeline (Detector + Tracker) per camera
│   ├── camera_pipeline.py    # runs the tasks assigned to a camera over each frame
│   ├── inference_engine.py   # single inference thread iterating over every camera
│   └── results_store.py      # last inference result per camera, for the interfaces
├── tasks/
│   ├── base.py               # TaskAnalyzer interface
│   ├── registry.py           # maps "type" (tasks.yaml) -> TaskAnalyzer class
│   ├── treadmill_counter.py  # the "item_counting" task
│   ├── ppe_compliance.py     # the "ppe_compliance" task
│   ├── missing_product.py    # the "missing_product" task
│   └── face_id.py            # the "face_id" task (optional, needs insightface/onnxruntime)
├── notify/
│   ├── flag.py, flag_manager.py   # events ("Flags") raised by the tasks
│   └── notifiers/                  # notification channels: log, desktop, database
├── db/
│   ├── models.py       # SQLAlchemy: employees, face embeddings, event/narration logs
│   ├── session.py       # database initialization (SQLite)
│   └── repository.py    # queries (employees, embedding similarity search, etc.)
├── llm/
│   ├── ollama_client.py # client for the local Ollama service
│   └── narrator.py      # produces periodic summaries of recent alerts
├── gui_qt/                      # INTERFACE 1: native desktop GUI (./run.sh)
│   ├── app.py, main_window.py
│   └── widgets/
│       ├── camera_grid.py, camera_tile.py   # live video grid
│       ├── calibration_view.py               # drawing lines/zones over a frozen frame
│       ├── settings_panel.py                 # editing tasks per camera
│       ├── employee_enrollment.py            # employee enrollment (face recognition)
│       └── alerts_panel.py                   # alerts table + narrator summary
└── web/                         # INTERFACE 2: web UI (./run-html.sh)
    ├── server.py         # FastAPI app: serves the static files and the routes
    ├── api.py            # REST routes (cameras, tasks, calibration, employees)
    ├── streaming.py      # live MJPEG video and JPEG snapshots
    ├── errors.py         # API errors carrying a translation code
    ├── deps.py           # reference to the live backend, injected into the routes
    └── static/           # THE INTERFACE ITSELF — edit here to change the looks
        ├── index.html            # structure of every screen
        ├── css/
        │   ├── theme.css         # colors, spacing, fonts (start here)
        │   ├── base.css          # reset + the three-column layout
        │   └── components.css    # buttons, cards, tables, alerts, toasts
        └── js/
            ├── api.js            # the only layer that talks to the backend
            ├── i18n.js           # translation + the language picker
            ├── ui.js             # DOM helpers, toasts, formatting
            ├── app.js            # navigation between screens + polling
            └── views/            # one file per screen
                ├── live.js, calibration.js, settings.js, employees.js
```

General flow: the `CameraManager` keeps one capture thread
(`CameraStream`) per registered camera, always holding only the most
recent frame. A single `InferenceEngine` walks the cameras that have
tasks assigned, runs each one's `CameraPipeline` (YOLO detection +
tracking + the configured `TaskAnalyzer`s) and publishes the result
into the `ResultsStore`. Tasks that trigger a condition produce a
`Flag`, which the `FlagManager` routes to the enabled notification
channels (log, desktop notification and/or the `event_log` table in
SQLite).

All of that is assembled by `bootstrap.AppRuntime`, which **knows
nothing about interfaces**. Each entry point only does
`runtime = AppRuntime.create(); runtime.start()` and then reads the
`ResultsStore` and the `FlagManager` the way its presentation layer
wants: `MainWindow` (PySide6) draws into Qt widgets; the web server
exposes the same data as JSON and the video as MJPEG, and the browser
draws the rest. Changes to the backend apply to both interfaces
automatically.

Cameras that use the same YOLO model share the same loaded instance
(`ModelRegistry`), avoiding reloading weights and duplicating memory.

## Installation

Requires Python 3 and, optionally, an NVIDIA GPU with CUDA for better
performance — the application also works on CPU.

Recommended path — the `run.sh` (desktop) and `run-html.sh` (web)
scripts take care of everything on the first run (they create the
`.venv`, install the dependencies from `requirements.txt` and copy
`.env.example` to `.env`). Both use the SAME `.venv`, so installing
through one covers the other:

```bash
./run.sh        # desktop GUI
./run-html.sh   # web interface
```

The initial dependency download (torch + ultralytics + insightface
together) is over 1 GB, so the first run may take several minutes.
Later runs just start the application.

The very first time either interface actually **starts** (after `.env`
has real credentials in it), it asks you to **choose a password**: that
password encrypts `.env` into `.env.enc` and the plaintext `.env` is
deleted. Every run after that asks for the same password to unlock it.
**Where** it asks depends on the interface — the desktop GUI (`./run.sh`)
still asks on the terminal, but the web interface (`./run-html.sh`) asks
**in the browser itself**, specifically so `./run-html.sh` can be
double-clicked from a file manager with no terminal involved at all. See
[Camera credentials & encryption](#camera-credentials--encryption).

To force reinstalling the dependencies (for example after editing
`requirements.txt`):

```bash
./run.sh --reinstall        # or ./run-html.sh --reinstall
```

Manual alternative:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env

python src/main.py          # desktop GUI
python src/main_web.py      # web interface
```

`python src/main.py` prompts for the credential-store password on the
terminal before the window opens. `python src/main_web.py` does NOT —
it starts the server immediately and the password is entered on the
lock screen in the browser instead (see below).

The web interface adds three lightweight packages (`fastapi`,
`uvicorn`, `python-multipart`) — nothing compiled, a few seconds of
download. In exchange, it **does not need PySide6**: on a headless
server you can drop `PySide6` from `requirements.txt` and run the web
version alone.

### GPU (optional)

By default, `requirements.txt` installs the CPU variants of `torch` and
`onnxruntime`. To use an NVIDIA GPU:

1. Install the CUDA variant of `torch` **before** the rest of
   `requirements.txt`, following
   https://pytorch.org/get-started/locally/ (the exact command depends
   on the installed CUDA version).
2. Replace `onnxruntime` with `onnxruntime-gpu` (`pip install
   onnxruntime-gpu`) — the two packages are mutually exclusive, install
   only one.

Device detection at runtime (`vision/device.py`) is automatic; the
correct wheel for the GPU still has to be installed per machine.

On Arch/CachyOS, skip the pip CUDA wheels for `torch`/`torchvision`/
`onnxruntime` entirely — install `python-pytorch-cuda`,
`python-torchvision-cuda` and `python-onnxruntime-cuda` via `pacman`
instead (they track the driver's CUDA version and avoid pip/pacman
conflicts), and create `.venv` with `python3 -m venv
--system-site-packages .venv` so it can see them. `pip install -r
requirements.txt` then leaves those three alone ("Requirement already
satisfied") instead of pulling CPU wheels on top.

**Adding `easyocr` (for `car_identification`) on that same setup**: a
plain `pip install easyocr` resolves its own `torch`/`torchvision`
requirement and can try to replace the pacman-installed CUDA build
with a CPU wheel inside the `--system-site-packages` venv — exactly the
kind of conflict a stuck `pacman -Syu` transaction involving
`python-torchvision-cuda` can also surface (e.g. a build tool like
`python-maturin` insisting on a CPU package to satisfy a version
constraint). Avoid it by installing `easyocr` without letting pip touch
torch:

```bash
.venv/bin/pip install --no-deps easyocr
.venv/bin/pip install python-bidi scikit-image Shapely pyclipper ninja Pillow
```

Then confirm CUDA is still intact before relying on it:

```bash
.venv/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

If pip did overwrite the CUDA build, reinstall it — `sudo pacman -S
python-pytorch-cuda python-torchvision-cuda` — from your own terminal
(not run non-interactively), since it needs your `sudo` password.

## Configuration

There are four configuration sources:

| File | Contents |
|---|---|
| `.env` → `.env.enc` | camera credentials, encrypted after the first run (never committed) — see [Camera credentials & encryption](#camera-credentials--encryption) |
| `config/cameras.yaml` | which cameras exist, name, URL and the `enabled` flag |
| `config/tasks.yaml` | what each camera is monitoring (vision tasks) |
| `config/app.yaml` | global settings: language, device, database, LLM narrator, desktop notifications |

`config/tasks.yaml` can also be edited live from either interface
(the **Settings** and **Calibration** tabs) — those edits preserve the
YAML's comments and formatting.

### Cameras (`.env` + `config/cameras.yaml`)

The easiest way is the web interface: open the **Live** tab and click
**+ Add camera**, which asks for the connection type (RTSP, HTTP/MJPEG,
HTTPS/MJPEG), host, port, path and credentials and writes both files
for you — see [Managing cameras from the Live
tab](#managing-cameras-from-the-live-tab). What follows is the manual,
by-hand equivalent of what that button does.

Edit `.env` with the real credentials of each camera (on the very next
start of the application, this file gets encrypted into `.env.enc` and
removed — see the next section):

```
CAM1_URL=rtsp://user:password@192.168.1.3:554/...
CAM2_URL=rtsp://user:password@192.168.1.4:554/...
```

And `config/cameras.yaml` with the id, name and URL of each registered
camera — the `url` field references an environment variable
(`${CAM1_URL}`) and is expanded at load time; it accepts an RTSP or
HTTP/MJPEG stream:

```yaml
cameras:
  - id: "cam1"
    name: "C1"
    url: "${CAM1_URL}"
    enabled: true
```

### Tasks per camera (`config/tasks.yaml`)

Each camera can have zero or more tasks assigned (see the types under
[Available vision tasks](#available-vision-tasks)). Cameras without any
task generate no inference pipeline. The most practical way to define
counting lines and zones is the **Calibration** tab, rather than typing
pixel coordinates by hand.

A task that requires geometry (`item_counting`, `ppe_compliance`,
`missing_product`) and has **not been calibrated** does not run: the
camera goes without a pipeline and the reason appears in the log. The
Settings screen of the web interface flags this on the task's own card.

Every task has a `flags` list controlling what actually gets notified:

```yaml
flags:
  - id: missing_ppe
    enabled: true
    severity: warning        # info | warning | critical
    notify: [log, desktop]   # any combination of: log, desktop, db
```

`notify: [db]` only has an effect when `db.enabled: true` in
`app.yaml`.

### Global settings (`config/app.yaml`)

```yaml
ui:
  language: en          # en | pt (see the Language section)

vision:
  device: auto          # auto | cpu | cuda
  # model_size_override: yolov8m.pt   # default YOLO model when a task does not set "model:"

db:
  enabled: false         # true persists Flags into event_log, on top of the console log
  url: sqlite:///data/app.db

llm:
  enabled: false          # requires Ollama installed and running
  model: qwen2.5:1.5b
  interval_seconds: 60
  max_flags_per_summary: 20

notify:
  desktop:
    enabled: true
```

With `device: cuda` on a machine without a GPU, the application logs a
warning and falls back to CPU automatically — it does not crash.

### Models

Every Ultralytics checkpoint lives under `models/<kind>/` at the
project root, one folder per model kind: `models/detection/`,
`models/obb/`, `models/segmentation/`, `models/pose/`,
`models/classification/`. Which kind a task needs is fixed by its type
(`src/tasks/model_kinds.py`) — `item_counting`/`ppe_compliance`/
`missing_product`/`car_identification` need `detection`,
`print_monitor` needs `segmentation`, `face_id` manages its own model
and needs none. The web UI's Settings screen offers a model picker
scoped to the right folder for each task; picking one (or leaving it on
"device default") writes the `model:` field in `config/tasks.yaml`.
Placing a checkpoint whose actual kind doesn't match what the task
expects (e.g. a segmentation model under a `detection`-kind task) makes
that camera's pipeline fail to build, logged with the mismatch —
it does not crash the application.

There are three independent models, each configured in one place:

1. **Object detection (YOLO)** — used by `item_counting`,
   `ppe_compliance`, `missing_product` and `car_identification`:
   - Per-task override: the `model:` field in `config/tasks.yaml`
     (e.g. `model: models/detection/yolov8s.pt`).
   - Global default: `vision.model_size_override` in `config/app.yaml`.
   - If neither is set, the application automatically picks
     `models/detection/yolov8s.pt` on CUDA or `models/detection/yolov8n.pt` on CPU.
   - `ppe_compliance` needs a model actually trained on PPE classes —
     the default YOLO model (COCO) does not recognize a helmet or a
     vest, so point `model:` at a checkpoint trained for that before
     enabling the task.

2. **Device (CPU vs. GPU)**, for YOLO and face recognition:
   `vision.device` in `config/app.yaml` (`auto | cpu | cuda`).

3. **Face recognition** — used by `face_id`:
   - Per-task override, inside the `face_id` task's `params`:
     `model_pack: buffalo_l` (or `buffalo_s`) and, optionally,
     `device:` (overrides `vision.device` for that task alone).
   - If unset, it follows the same device resolution as YOLO:
     `buffalo_l` on CUDA, `buffalo_s` (lighter) on CPU.

4. **LLM narrator** (summarizes recent alerts in natural language):
   `llm.model` in `config/app.yaml` — it must be a model already pulled
   through Ollama (see [LLM narrator](#llm-narrator-optional)).

## Camera credentials & encryption

Camera credentials never sit on disk in plain text for long. The
encryption logic lives in `src/security/env_vault.py`; **where** it asks
for the password differs by interface:

- **Desktop GUI** (`src/main.py`) — asks on the terminal, before the
  window even opens, since a terminal is guaranteed to be there.
- **Web interface** (`src/main_web.py`) — asks **in the browser**, on a
  lock screen (`GET /api/lock` + `POST /api/unlock` in `src/web/api.py`).
  The server itself starts immediately, with no prompt and no backend
  yet (no cameras, no AppRuntime) — that is deliberate: it is what lets
  `./run-html.sh` be **double-clicked** from a file manager with no
  visible terminal at all. The browser opens automatically, shows the
  lock screen, and only builds/starts the real backend once you submit
  the password there.

Both paths share the same underlying behavior:

- **First run** — if `.env` exists and `.env.enc` does not, you are
  asked to **choose a password** (twice, to confirm). It then encrypts
  `.env`'s contents into `.env.enc` (AES via `cryptography`'s Fernet,
  key derived with PBKDF2-HMAC-SHA256) and **deletes the plaintext
  `.env`**.
- **Every run after that** — you are asked for that same password to
  unlock `.env.enc`. Get it wrong five times and the application shuts
  itself down (on the web interface, this also stops the server — the
  lock screen shows this happened, it does not just hang).
- **The password itself is never written anywhere** — not to disk, not
  to a config file, not logged. Only the key derived from it is kept,
  in that process's memory, for as long as it keeps running. Restarting
  the application means entering the password again.
- That in-memory key is what lets the **Live** tab's *Add camera* panel
  and each camera's cog-button settings menu (see [Managing cameras
  from the Live tab](#managing-cameras-from-the-live-tab)) write new or
  changed credentials into `.env.enc` **without asking for the password
  again mid-session** — it only re-encrypts with the key already
  unlocked at startup.
- Losing the password means losing access to whatever is in
  `.env.enc` — there is no recovery. Keep it somewhere safe (a password
  manager), separate from the project.

`.env.enc` is gitignored, same as `.env` used to be — it should never
be committed.

### Stopping the application

Since `.env.enc`'s decrypted contents only ever live in memory (never
written back to disk), simply killing the process loses nothing —
**but** don't rely on that as your normal way to stop it: the desktop
GUI closes normally through its window, and the web interface has an
**Exit application** button at the bottom of the sidebar (`POST
/api/shutdown` in `src/web/api.py`) specifically for when there is no
terminal to `Ctrl+C` — again, the double-click case. It stops the
camera/inference threads first, then the process itself, and is
guaranteed to actually exit within a few seconds even if a camera is
stuck reconnecting (a hard fallback forces the exit if the graceful
shutdown takes too long).

## Language

The interface is available in **English (the default) and
Portuguese**. Both are driven by a single catalog, `src/i18n.py`, which
the desktop GUI imports directly and the web interface fetches through
`GET /api/i18n` — so wording is edited in exactly one place and never
drifts between the two.

**Web interface:** a picker in the sidebar footer switches language
instantly, with no reload. The choice is stored in that browser
(`localStorage`), so it survives a refresh and applies only to whoever
made it.

**Desktop GUI:** it follows `ui.language` in `config/app.yaml` and
applies it when the widgets are created, so changing it means
restarting the application. There is no picker there.

```yaml
ui:
  language: en    # en | pt
```

`ui.language` also sets:

- the language the web interface starts in, for a browser that has not
  chosen yet (a saved choice always wins);
- the language of the LLM narrator's summaries, since those are
  generated on the server, once, for everyone.

An unrecognized value falls back to English instead of breaking
startup.

Alert texts are translated too: the analyzers emit a translation key
alongside the rendered English message, so the panel shows the alert in
the chosen language while the log, the `event_log` table and the LLM
prompt stay in English.

### Adding or changing wording

Everything lives in `CATALOG` in `src/i18n.py`, grouped by area
(`nav.*`, `settings.*`, `flag.*`, `api.*`, ...). To adjust wording,
edit the value; both interfaces pick it up.

To add a third language, add its code to `LANGUAGES` and a dictionary
with the same keys to `CATALOG` — the web picker is built from
`LANGUAGES`, so it shows up on its own. `tests/test_i18n.py` fails if a
language is missing a key or if the `{placeholders}` do not match
between languages.

## Running

**Desktop GUI** (PySide6, no browser):

```bash
./run.sh
# or, with the virtualenv already active:
python src/main.py
```

**Web interface** (opens the browser at `http://localhost:8000`):

```bash
./run-html.sh
# or, with the virtualenv already active:
python src/main_web.py
```

`./run-html.sh` needs no terminal interaction at all — after the first
install, **double-clicking it from a file manager works**: it opens the
browser, which shows the lock screen (password entry — see [Camera
credentials & encryption](#camera-credentials--encryption)) instead of
anything appearing on a terminal.

Options for `run-html.sh` (any argument is passed through to
`src/main_web.py`):

| Option | Effect |
|---|---|
| `--port 9000` | listen on another port (default: 8000) |
| `--host 0.0.0.0` | expose on the local network, to reach it from another device |
| `--no-browser` | do not open the browser automatically |
| `--reinstall` | force reinstalling the dependencies |

> **Careful with `--host 0.0.0.0`:** there is no authentication at all
> once unlocked. The startup password (see [Camera credentials &
> encryption](#camera-credentials--encryption)) protects `.env.enc`
> itself — with `--host 0.0.0.0`, the lock screen (and its 5-attempt
> guess limit) is also reachable from the network before that, but once
> someone gets past it, or once you unlock it yourself, anyone who can
> reach the port sees the live cameras and can add/edit/delete them,
> same as sitting at the keyboard. Use it only on a trusted network (or
> keep the default `127.0.0.1`, which accepts connections from this
> machine only).

Both interfaces can run at the same time, but each opens **its own**
set of connections to the cameras (they are separate processes) — on a
modest machine, prefer one at a time.

To stop the web interface, use its **Exit application** button (sidebar
footer) rather than closing the terminal or killing the process — see
[Stopping the application](#stopping-the-application).

## Using the interface

The same four screens exist in both interfaces:

| Tab | Purpose |
|---|---|
| **Live** | Grid with every configured camera, with detection boxes drawn according to the task assigned to each one |
| **Calibration** | Freezes a live frame from a camera so you can draw, by clicking, a counting line or a zone polygon for one of its tasks — saved straight into `tasks.yaml` |
| **Settings** | List of tasks per camera: add/remove tasks, edit `detect_fps` and `required_ppe`, and enable/edit flags |
| **Employees** | Employee enrollment for `face_id` (capture from a camera or upload a photo + name); lists who is already enrolled |
| **Alerts** (side panel) | Live table of recent flags, with the latest narrator summary at the top (when enabled) |

Differences between the two:

| | Desktop (`./run.sh`) | Web (`./run-html.sh`) |
|---|---|---|
| Saving a task | writes to `tasks.yaml`; takes effect on the **next run** | writes and **reloads the pipelines immediately** (*Apply now* button) |
| Live | a fixed grid | adjustable columns and quality; click to expand a camera; add/edit/delete cameras in place (see below) |
| Calibration | points drawn on a `QGraphicsScene` | numbered points on a `<canvas>`, with the already-saved geometry dashed underneath |
| Language | follows `app.yaml`, needs a restart | picker in the sidebar, switches instantly |
| Remote access | no | yes, with `--host 0.0.0.0` (no authentication — see the warning under [Running](#running)) |

## Web interface

Everything the web interface renders in HTML/CSS/JS lives in
`src/web/static/` — that is the part meant to be edited without
touching Python:

| File | What it changes |
|---|---|
| `css/theme.css` | **start here**: colors, spacing, radii, fonts. All the rest of the CSS only references these variables, so changing a color here changes the whole interface |
| `css/base.css` | reset, typography and the three-column layout (sidebar, main area, alerts panel) |
| `css/components.css` | the looks of each piece: buttons, camera cards, task cards, alerts, toasts |
| `index.html` | the structure of the screens. All of them exist in the HTML at once; the JS only toggles which is visible |
| `js/views/*.js` | the behavior of each screen, one file per screen |
| `js/api.js` | the only layer that talks to the backend — if you change a route in `src/web/api.py`, it is the only JS file that has to follow |
| `js/i18n.js` | translation and the language picker; the wording itself lives in `src/i18n.py` |

There is no build step, no bundler and no CDN dependency: it is native
ES modules and plain CSS. Editing a file and reloading the page (F5)
already shows the result — the server reads the static files from disk
on every request, with no restart needed.

Note that user-visible text in `index.html` uses `data-i18n="key"`
attributes instead of literal text, and JavaScript builds strings
through `t('key')`. That is what lets the language picker work without
a reload; text typed directly into the markup would simply never
translate.

### Managing cameras from the Live tab

Each camera card's header shows its host/IPv4 next to the name, as a
deliberately understated link (no "link blue", underline only on
hover) that opens `http://<host>` in a new tab — the camera's own
manufacturer web UI, for when you need its native configuration page
rather than this application's.

**+ Add camera**, above the grid, opens a form for the connection type
(RTSP, HTTP/MJPEG or HTTPS/MJPEG), host, port, path and credentials.
Submitting it (`POST /api/cameras`) builds the connection string on the
server, writes the credential into `.env.enc` and the camera into
`config/cameras.yaml`, and starts streaming it immediately — no
restart.

The **⚙ cog button** on each card opens that camera's settings, prefilled
from `.env.enc` (name, connection type, host, port, path, username,
password, enabled). There is no separate login for this panel: it
lives behind the same startup password as the rest of the application
(see [Camera credentials & encryption](#camera-credentials--encryption)).
**Save** rewrites both `cameras.yaml` and `.env.enc` and reopens the
camera's stream with the new details; **Delete camera** removes it from
`cameras.yaml`, stops its stream, and removes its credential from
`.env.enc`.

### How the video reaches the browser

Each camera is an `<img>` pointing at `/api/cameras/<id>/stream`, which
returns **MJPEG** (`multipart/x-mixed-replace`): the server keeps the
connection open and sends one JPEG per frame, a format the browser
understands on its own. No WebSocket, WebRTC or video player is
involved.

The detection boxes are drawn **on the server**
(`src/vision/overlay.py`, the same module the Qt GUI uses), not in the
browser — which is why both interfaces show exactly the same overlay.

The rest of the screen (camera status, alerts, narrator summary) is
refreshed by *polling*: one request per second to `/api/state`, the
same pattern as the desktop GUI's `QTimer`.

### API routes

With the server running, interactive documentation lives at
`http://localhost:8000/api/docs` (generated by FastAPI; every route can
be tried from the browser). The main ones:

| Route | Purpose |
|---|---|
| `GET /api/lock` | whether the credential vault is locked, and whether this is a first run — polled once before anything else |
| `POST /api/unlock` | the lock screen's password submission; builds and starts the real backend on success |
| `POST /api/shutdown` | the "Exit application" button — stops the backend and terminates the process |
| `GET /api/state` | cameras + alerts + summary, in one request (this is what the UI polls) |
| `GET /api/system` | device, notification channels, counts |
| `GET /api/i18n` | translation catalog + available languages |
| `GET /api/cameras/<id>/stream` | live MJPEG video (`?width=&quality=&fps=&overlay=`) |
| `GET /api/cameras/<id>/snapshot` | a single JPEG frame (calibration uses `?width=0&overlay=false`) |
| `GET/POST/PATCH/DELETE /api/cameras[/<id>]` | reading and editing `cameras.yaml` + the `.env.enc` vault — powers the Live tab's *Add camera* panel and per-camera settings (cog button) |
| `GET/POST/PATCH/DELETE /api/cameras/<id>/tasks[...]` | reading and editing `tasks.yaml` |
| `POST /api/cameras/<id>/tasks/<i>/geometry` | saves the line/zone drawn during calibration |
| `POST /api/reload` | rebuilds the pipelines with the current `tasks.yaml`, no restart |
| `GET/POST /api/employees` | lists and enrolls employees (face recognition) |

Errors answer with `{"detail": "<english text>", "code": "<key>"}` —
the browser translates `code` and falls back to `detail` when it does
not recognize it. Every route except `/api/lock`, `/api/unlock`,
`/api/shutdown` and `/api/i18n` answers `423` (`api.locked`) until
`POST /api/unlock` succeeds — there is no `AppRuntime` before that.

## Available vision tasks

Types registered in `tasks/registry.py` (auto-registered when the
`tasks` package is imported):

- **`item_counting`** (`tasks/treadmill_counter.py`) — counts objects
  crossing a line.
  Parameters: `counting_line` (`p1`, `p2`), `direction`,
  `target_classes`, `min_count_per_window`, `window_seconds`.

- **`missing_product`** (`tasks/missing_product.py`) — flags an empty
  zone that should contain an object.
  Parameters: `zones` (each with a name, polygon and `expected_class`),
  `absence_dwell_seconds`.

- **`ppe_compliance`** (`tasks/ppe_compliance.py`) — flags a person
  without the required protective equipment.
  Parameters: `required_ppe`, `zones`, `missing_ppe_dwell_seconds`.
  Requires a YOLO model trained on the PPE classes (see
  [Models](#models)).

- **`face_id`** (`tasks/face_id.py`, optional) — flags unrecognized
  faces. Parameters: `match_threshold`, `log_unknown`, `device`,
  `model_pack`. Available only when `insightface` and `onnxruntime` are
  installed; with no employee enrolled, every face is treated as
  unknown (see [Employee enrollment](#employee-enrollment)).

- **`print_monitor`** (`tasks/print_monitor.py`) — segmentation-based
  "spaghetti detection" heuristic for 3D printing: masks the current
  print each frame and flags an abrupt area/shape deviation from its
  own rolling history as a possible failed print. Needs a
  **segmentation**-kind model (see [Models](#models)) — there is no
  default one shipped, so `model:` must be set explicitly in
  `tasks.yaml`. Parameters: `print_class`, `window_size`,
  `area_growth_threshold`, `shape_irregularity_threshold`,
  `min_history_before_flagging`. Comparing against the actual STL/3MF
  file is a documented future phase, not implemented yet — it would
  need a camera-calibration step this application doesn't have.

- **`car_identification`** (`tasks/car_identification.py`, optional) —
  for each tracked car, crops it and returns an ordered
  `[trademark, color, plate_text]`: trademark comes from a
  **classification**-kind model you provide (`trademark_model`
  parameter, required), color is computed directly from the crop's
  pixels (not a model — more robust than a trained classifier under
  varying lighting), and the plate is read with OCR
  ([EasyOCR](https://github.com/JaidedAI/EasyOCR)). Parameters:
  `car_class`, `trademark_model`, `ocr_languages`, `min_confidence`,
  `cooldown_seconds`, `device`. Available only when `easyocr` is
  installed (see [Installation](#installation) for a CUDA-friendly way
  to add it without disturbing a pacman-installed torch).

## Triggers

Condition → action rules that react to any Flag (from any task above)
and drive external IO — the **Triggers** screen in the web interface
(bolt icon in the sidebar), backed by `config/Triggers.yaml`.

A global toggle picks how matched actions run:

- **Ask for permission** (default) — a matched action is queued for
  manual approval/denial in the same screen, instead of firing
  immediately.
- **Auto mode** — matched actions fire right away.

Each rule has a condition (`task_type`, `flag_id`, `camera_id`,
`severity` — an empty field matches anything) and one or more actions.
Three protocol backends ship today, registered in
`triggers/actions/registry.py`:

| Action type | Needs | Target fields |
|---|---|---|
| `http_webhook` | nothing extra — always available | `url`, `timeout_seconds` (optional) |
| `mqtt` | `paho-mqtt` | `host`, `port` (optional, default 1883), `topic`, `qos` (optional) |
| `modbus_tcp` | `pymodbus` | `host`, `port` (optional, default 502), `register`, `value` |

`mqtt`/`modbus_tcp` simply don't appear in the action-type picker when
their package isn't installed — the rest of the application keeps
working. Adding another protocol (EtherNet/IP, OPC-UA, ...) is a new
file in `triggers/actions/` plus one import line, following the same
pattern.

## Optional features

### Desktop notifications

Enabled by default. Controlled by `config/app.yaml` ->
`notify.desktop.enabled`.

### Event log in SQLite

Disabled by default. `config/app.yaml` -> `db.enabled: true` persists
every flag into the `event_log` table of `data/app.db`, on top of the
console log.

### Employee enrollment

Always active, with no toggle — a SQLite file at `data/app.db`, created
automatically on the first run. Enroll people through the
**Employees** tab (present in both interfaces): capture from a camera
or upload a photo, type a name and click Enroll. Both write to the same
database, so an enrollment made in one shows up in the other.

Only the face *embedding* is stored — the photo itself is not saved.

### LLM narrator (optional)

Disabled by default. Requires the [Ollama](https://ollama.com/download)
service installed separately (it is not a pip package):

1. Install Ollama.
2. Start the service: `ollama serve`
3. Pull a small model: `ollama pull qwen2.5:1.5b` (or `llama3.2:1b` —
   any model light enough to run on CPU; it is only a text summarizer,
   not the vision model).
4. In `config/app.yaml`, set `llm.enabled: true` and `llm.model` to
   match the model you pulled.

Summaries are written in the language set by `ui.language` (see
[Language](#language)).

If Ollama is not running, the narrator logs a warning on every cycle
and the "Summary (AI)" panel simply stays empty — the rest of the
application keeps working normally. With `llm.enabled: false`, the web
interface does not even show the summary panel.

## Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

Every test runs without needing real cameras, a browser or a running
Ollama instance. The web interface tests (`test_web_api.py`) use
FastAPI's `TestClient` with a fake backend — no camera is opened and no
model is loaded. `test_i18n.py` checks that both languages define the
same keys with matching placeholders, so a half-translated string fails
the suite instead of reaching the screen. One test
(`test_vision_integration.py`) downloads `models/detection/yolov8n.pt` and another
(`test_face_recognizer_integration.py`) downloads the `buffalo_s` face
model on the first run, when they are not cached yet.

## Where the files live

| Location | Contents |
|---|---|
| `data/app.db` | SQLite: employees, face embeddings, event log, narration log (gitignored) |
| `.env.enc` | Encrypted camera credentials (gitignored) — see [Camera credentials & encryption](#camera-credentials--encryption) |
| `~/.insightface/models/` | Downloaded face recognition models (`buffalo_s`/`buffalo_l`), cached between runs |
| `models/<kind>/*.pt` | Downloaded YOLO weights, one folder per model kind (`detection`/`obb`/`segmentation`/`pose`/`classification`), cached between runs (gitignored) |
| `src/web/static/` | HTML, CSS and JS of the web interface — this is where you edit the looks |
| `src/i18n.py` | Wording of both interfaces, in English and Portuguese |

## Resetting the application

```bash
./reset.sh                 # asks for confirmation, then resets
./reset.sh --yes           # skips the confirmation prompt
./reset.sh --purge-config  # ALSO deletes cameras.yaml/tasks.yaml/app.yaml
./reset.sh --purge-models  # ALSO deletes downloaded *.pt / *.onnx weights
```

Wipes `.venv/`, every `__pycache__/`/`.pytest_cache/`, `data/*.db` and
the camera credentials (`.env`/`.env.enc`) — everything generated or
local that `./run.sh`/`./run-html.sh` will recreate on the next start.
`config/cameras.yaml`, `config/tasks.yaml`, `config/app.yaml` and the
downloaded model weights are kept unless you pass `--purge-config` /
`--purge-models`, since redoing those is expensive.

**The camera credentials are not recoverable after this** — there is no
backup of the password or of `.env.enc`'s contents. Note down your
camera URLs/credentials first if you have not saved them elsewhere.

## Troubleshooting

**`vision.device='cuda' requested but CUDA is not available`**
Expected and harmless when the machine has no NVIDIA GPU — it only
means `device: cuda` in `app.yaml` fell back to CPU automatically. Set
`device: auto` or `device: cpu` to stop seeing the warning.

**`Failed to call Ollama` every ~60s**
Expected when `llm.enabled: true` but Ollama is not installed/running.
Start Ollama (see [LLM narrator](#llm-narrator-optional)) or set
`llm.enabled: false`.

**torch/onnxruntime install is CPU-only by default**
`requirements.txt` installs the CPU wheels. For a machine with an
NVIDIA GPU, install the CUDA build of torch first (see
[GPU (optional)](#gpu-optional)) and swap `onnxruntime` for
`onnxruntime-gpu` — the two are mutually exclusive, install only one.

**A camera never connects / the interface shows "waiting for connection..."**
Check the RTSP URL and the credentials (edit them from the cog button
on the camera's card, or in `.env`/`.env.enc`), and whether the camera
is reachable on the network (e.g. `nc -zv <ip> 554`).

**"Wrong password" at startup / forgot the credential-store password**
There is no recovery — see [Camera credentials &
encryption](#camera-credentials--encryption). Five wrong attempts shut
the application down (on the web interface, the lock screen shows this
and the server stops); run `./run.sh`/`./run-html.sh` again to retry.
If the password is truly lost, `./reset.sh` (see [Resetting the
application](#resetting-the-application)) removes `.env.enc` so you can
start over, but the credentials in it are gone for good.

**The web interface is stuck on the lock screen / never shows the dashboard**
Check that `POST /api/unlock` is actually succeeding — open the
browser's dev tools (Network tab) and retry. A `423` on other routes
before that is expected (see [API routes](#api-routes)): there is no
backend at all until the vault unlocks, by design — that's what lets
the process start with no terminal prompt in the first place.

**Clicking "Exit application" doesn't seem to do anything**
It does — the button disables itself and the page switches to a
"Shutting down…" screen, but there is no toast because the connection
that would show one drops as the process exits. Give it a few seconds:
`POST /api/shutdown` stops the server gracefully and, if a camera is
stuck reconnecting and that takes too long, force-exits shortly after
as a fallback either way (see [Stopping the
application](#stopping-the-application)).

**`Credential store is locked` from the API**
The vault in `src/security/env_vault.py` was never unlocked — normal
while the web interface's lock screen is still showing (see above).
Outside of that, it can happen if `web.server.create_web_app()` is
imported and run some other way without ever calling `POST
/api/unlock` or `security.env_vault.unlock_interactive()`. Restart
through the normal entry points.

**`Camera 'camX' has no pipeline: ...` in the log**
That camera's task requires geometry and has not been calibrated yet
(or some parameter is missing in `tasks.yaml`). Draw the line/zone in
the **Calibration** tab. The application keeps running normally; only
that camera goes without detection.

**`Address already in use` when running `./run-html.sh`**
Port 8000 is already taken (most likely by another instance). Run
`./run-html.sh --port 9000` or stop the previous instance.

**Video does not show in the web interface, but the cameras are connected**
Each open camera holds one HTTP connection. Many browser tabs open at
once can exhaust the per-server connection limit. Close the extra tabs,
or lower the quality in the **Live** tab's selector (which also cuts
CPU and bandwidth).

**The web interface opens, but the sidebar says "no connection to the backend"**
The server went down or is restarting — check the terminal where
`./run-html.sh` is running. The page recovers on its own as soon as the
backend answers again.

**The web interface shows raw keys like `nav.live` instead of text**
The translation catalog failed to load (`GET /api/i18n`). Reload the
page; if it persists, check the server terminal for an error in
`src/i18n.py`.
