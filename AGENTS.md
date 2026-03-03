# AGENTS.md

## Cursor Cloud specific instructions

### Overview

Phantom is a Python-based distributed computing platform. The main service is the **Controller API** (FastAPI), located in `phantom_core/`. No external databases, message queues, or cloud services are required.

### Running the Controller

```bash
export PHANTOM_STATE_DIR=/tmp/phantom/state
cd phantom_core
python3 run.py --host 127.0.0.1 --port 8080 --security disabled
```

The `PHANTOM_STATE_DIR` environment variable **must** be set to a writable path (e.g. `/tmp/phantom/state`). The default (`/var/lib/phantom/state`) requires root and will cause a `PermissionError` on startup.

For the integrated system (Controller + Socket Infrastructure):

```bash
export PHANTOM_STATE_DIR=/tmp/phantom/state
cd phantom_core
python3 run_integrated_phantom.py --host 127.0.0.1 --port 8080 --security disabled
```

### Linting and Testing

- **Lint:** `python3 -m black --check phantom_core/` and `python3 -m flake8 --max-line-length=88 --extend-ignore=E203,W503 phantom_core/phantom_core/`
- **Tests:** `cd phantom_core && python3 -m pytest tests/ -v`
- Config: `phantom_core/pytest.ini` sets `asyncio_mode = auto`
- GPU/gRPC tests are auto-skipped when hardware or optional dependencies are absent

### Dependencies

Core Python deps are in `phantom_core/requirements.txt`. GPU packages (`pynvml`, `py3nvml`, `gpustat`) and AI/ML packages (`torch`, `transformers`, `accelerate`) are optional and will not install without GPU hardware. Install core deps with:

```bash
pip install fastapi 'uvicorn[standard]' pydantic httpx requests websockets psutil numpy pyyaml cryptography pyjwt pytest pytest-asyncio black flake8
```

### Key API Endpoints

See `phantom_core/README.md` for full API reference. Key endpoints on `http://127.0.0.1:8080`:
- `GET /health` — health check
- `GET /workers` — list workers
- `POST /workers/register` — register a worker
- `POST /tasks/submit` — submit a task
- `GET /stats` — system statistics

### Web UI

The RedBlue Matrix Web UI at `ui/redblue_matrix/matrix-web-ui/` is static HTML/CSS/JS with no build step. It can be served with any HTTP server (e.g. `python3 -m http.server 3000`).

### Phantom Application (Tauri Desktop App)

The `phantom_app/` directory contains a Tauri v2 application — the "stone home" for Phantom. It wraps the engine without modifying it.

**Prerequisites:** Rust 1.85+, Node.js 18+, system packages `libwebkit2gtk-4.1-dev libssl-dev libayatana-appindicator3-dev librsvg2-dev`.

**Build & run:**
```bash
cd phantom_app
npm install
npm run tauri dev       # development mode (requires display)
npm run tauri build     # release build (outputs .deb, .rpm, .AppImage)
```

**Frontend-only dev server** (no Tauri/display required):
```bash
cd phantom_app && npx vite --host 0.0.0.0 --port 1420
```
The frontend auto-detects the controller on port 8080. When running the frontend outside Tauri, set `PHANTOM_CORS_ORIGINS` to include the Vite port:
```bash
export PHANTOM_CORS_ORIGINS="http://localhost:8080,http://127.0.0.1:8080,http://localhost:1420,http://127.0.0.1:1420"
```

**Architecture:** Rust backend (`src-tauri/src/`) handles deployment, LAN scanning, and OS service management. React/TypeScript frontend (`src/`) provides the TOC interface. The app communicates with Phantom's controller API via HTTP — it never modifies Phantom's core.
