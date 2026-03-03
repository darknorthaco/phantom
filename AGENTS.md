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
