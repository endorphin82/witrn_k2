"""FastAPI Web Server for WITRN K2 Telemetry Streaming and Analysis."""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime
import json
import logging
from pathlib import Path
import sqlite3
import time
from typing import Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..core import (
    AutoStopRule,
    LinuxHidrawTransport,
    Recorder,
    Sample,
    SimulatorTransport,
    calculate_statistics,
    decode_report,
    export_json,
    export_official_csv,
    export_standard_csv,
    find_k2_device,
    import_official_csv,
    open_transport,
)
from ..core.exporter import read_sqlite_samples

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("witrn_k2_web")

STORAGE_DIR = Path(__file__).parent.parent.parent / "recordings"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


class ConnectionManager:
    """Manages active WebSocket clients for telemetry broadcast."""
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        msg_text = json.dumps(message)
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(msg_text)
            except Exception:
                dead.append(connection)
        for d in dead:
            self.disconnect(d)


manager = ConnectionManager()
recorder = Recorder(STORAGE_DIR)

# State
device_state = {
    "connected": False,
    "info": None,
    "error": None,
    "mode": "hardware",  # "hardware" or "simulator"
}

# In-memory circular buffer for recent samples (for live graphs)
RECENT_BUFFER_MAX = 3600  # ~1 hour at 1 Hz or 36s at 100 Hz
recent_samples = deque(maxlen=RECENT_BUFFER_MAX)
background_task: Optional[asyncio.Task] = None
shutdown_event = asyncio.Event()


def try_connect_device(mode: str = "hardware"):
    global device_state
    try:
        if mode == "simulator":
            trans, info = open_transport(force_simulator=True)
            device_state["connected"] = True
            device_state["info"] = info
            device_state["error"] = None
            device_state["mode"] = "simulator"
            return trans
        else:
            trans, info = open_transport(force_simulator=False)
            device_state["connected"] = True
            device_state["info"] = info
            device_state["error"] = None
            device_state["mode"] = "hardware"
            return trans
    except Exception as exc:
        device_state["connected"] = False
        device_state["info"] = find_k2_device()
        device_state["error"] = str(exc)
        device_state["mode"] = mode
        logger.warning(f"Device connection failed: {exc}")
        return None


async def telemetry_worker():
    """Background loop polling transport and streaming to WebSockets & Recorder."""
    global device_state
    trans = try_connect_device(device_state["mode"])

    last_broadcast = time.monotonic()
    pending_samples = []
    started_time = time.monotonic()

    while not shutdown_event.is_set():
        if trans is None:
            # Reconnect attempt every 2 seconds
            await asyncio.sleep(2.0)
            trans = try_connect_device(device_state["mode"])
            if trans:
                started_time = time.monotonic()
            continue

        try:
            # Non-blocking read in executor to keep asyncio responsive
            raw = await asyncio.get_event_loop().run_in_executor(None, trans.read, 20)
            now = time.monotonic()

            if raw:
                sample = decode_report(raw, now - started_time)
                if sample:
                    auto_stopped = recorder.feed(sample)
                    recent_samples.append(sample.dictionary())
                    pending_samples.append(sample.dictionary())

                    if auto_stopped:
                        await manager.broadcast({
                            "type": "event",
                            "event": "auto_stop",
                            "message": "Запис автоматично зупинено за заданою умовою",
                        })

            # Broadcast at up to ~25 Hz or if buffer exceeds 10 items
            if now - last_broadcast >= 0.04 and pending_samples:
                latest = pending_samples[-1]
                await manager.broadcast({
                    "type": "telemetry",
                    "latest": latest,
                    "batch": pending_samples if len(pending_samples) > 1 else None,
                    "recorder": recorder.get_status(),
                })
                pending_samples.clear()
                last_broadcast = now

            await asyncio.sleep(0.002)

        except Exception as exc:
            logger.error(f"Error in telemetry worker: {exc}")
            if trans:
                try:
                    trans.close()
                except Exception:
                    pass
            trans = None
            device_state["connected"] = False
            device_state["error"] = str(exc)
            await asyncio.sleep(1.0)

    if trans:
        trans.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global background_task
    shutdown_event.clear()
    background_task = asyncio.create_task(telemetry_worker())
    logger.info("WITRN K2 telemetry service started")
    yield
    shutdown_event.set()
    if background_task:
        await background_task
    recorder.stop()
    logger.info("WITRN K2 telemetry service stopped")


app = FastAPI(title="WITRN K2 Analysis Suite", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Models
class RecordStartRequest(BaseModel):
    session_name: Optional[str] = None
    rate: int = 10
    auto_stop_enabled: bool = False
    auto_stop_kind: str = "current"
    auto_stop_threshold: float = 0.05
    auto_stop_duration: float = 10.0


class ConnectRequest(BaseModel):
    mode: str = "hardware"  # "hardware" or "simulator"


@app.get("/api/status")
def get_status():
    hw_info = find_k2_device()
    return {
        "device": {
            **device_state,
            "detected_device": hw_info,
        },
        "recorder": recorder.get_status(),
        "recent_count": len(recent_samples),
    }


@app.post("/api/connect")
def connect_device(req: ConnectRequest):
    global device_state, background_task
    device_state["mode"] = req.mode
    # Cancel and restart background task to re-open transport
    if background_task:
        background_task.cancel()
    background_task = asyncio.create_task(telemetry_worker())
    return {"status": "ok", "mode": req.mode}


@app.post("/api/record/start")
def start_recording(req: RecordStartRequest):
    try:
        auto_rule = AutoStopRule(
            enabled=req.auto_stop_enabled,
            kind=req.auto_stop_kind,
            threshold=req.auto_stop_threshold,
            duration=req.auto_stop_duration,
        )
        file_path = recorder.start(
            session_name=req.session_name,
            rate=req.rate,
            auto_rule=auto_rule,
        )
        return {
            "status": "recording_started",
            "file": str(file_path.name),
            "rate": req.rate,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/record/pause")
def pause_recording():
    recorder.pause()
    return {"status": "paused"}


@app.post("/api/record/resume")
def resume_recording():
    recorder.resume()
    return {"status": "resumed"}


@app.post("/api/record/stop")
def stop_recording():
    path = recorder.stop()
    return {
        "status": "stopped",
        "file": str(path.name) if path else None,
    }


@app.get("/api/history")
def get_recent_history():
    """Return recently captured in-memory samples for quick graph initialization."""
    return {
        "samples": list(recent_samples),
    }


@app.get("/api/sessions")
def list_sessions():
    """List saved SQLite recording files."""
    files = sorted(STORAGE_DIR.glob("*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True)
    sessions = []
    for f in files:
        st = f.stat()
        meta = {}
        sample_count = 0
        try:
            conn = sqlite3.connect(f"file:{f.resolve()}?mode=ro", uri=True)
            for k, v in conn.execute("SELECT key, value FROM metadata"):
                meta[k] = v
            c = conn.execute("SELECT COUNT(*) FROM samples").fetchone()
            sample_count = c[0] if c else 0
            conn.close()
        except Exception:
            pass

        sessions.append({
            "id": f.stem,
            "filename": f.name,
            "size_bytes": st.st_size,
            "modified_at": datetime.fromtimestamp(st.st_mtime).isoformat(),
            "sample_count": sample_count,
            "metadata": meta,
        })
    return {"sessions": sessions}


@app.get("/api/sessions/{session_id}")
def get_session_details(session_id: str, max_points: Optional[int] = Query(2000)):
    """Retrieve full details, statistics, and optionally thinned samples for an existing session."""
    db_path = STORAGE_DIR / f"{session_id}.sqlite"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    samples = list(read_sqlite_samples(db_path, max_points=max_points))
    stats = calculate_statistics(samples)

    # Read metadata
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    meta = {k: v for k, v in conn.execute("SELECT key, value FROM metadata")}
    conn.close()

    return {
        "session_id": session_id,
        "metadata": meta,
        "statistics": stats,
        "samples": [s.dictionary() for s in samples],
    }


@app.get("/api/sessions/{session_id}/export")
def export_session(session_id: str, format: str = Query("witrn_csv", pattern="^(witrn_csv|standard_csv|json|sqlite)$")):
    """Export a recorded session in the requested format."""
    db_path = STORAGE_DIR / f"{session_id}.sqlite"
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="Session not found")

    if format == "sqlite":
        return FileResponse(db_path, media_type="application/x-sqlite3", filename=f"{session_id}.sqlite")

    samples = list(read_sqlite_samples(db_path))

    if format == "witrn_csv":
        export_file = STORAGE_DIR / f"{session_id}_witrn.csv"
        export_official_csv(samples, export_file, metadata={"session_id": session_id})
        return FileResponse(export_file, media_type="text/csv", filename=f"{session_id}_witrn.csv")

    elif format == "standard_csv":
        export_file = STORAGE_DIR / f"{session_id}_std.csv"
        export_standard_csv(samples, export_file)
        return FileResponse(export_file, media_type="text/csv", filename=f"{session_id}.csv")

    elif format == "json":
        export_file = STORAGE_DIR / f"{session_id}.json"
        export_json(samples, export_file, metadata={"session_id": session_id})
        return FileResponse(export_file, media_type="application/json", filename=f"{session_id}.json")


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: str):
    db_path = STORAGE_DIR / f"{session_id}.sqlite"
    if db_path.exists():
        db_path.unlink()
        for suffix in ("-wal", "-shm"):
            extra = STORAGE_DIR / f"{session_id}.sqlite{suffix}"
            if extra.exists():
                extra.unlink()
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Session not found")


@app.post("/api/import")
async def import_csv(file: UploadFile = File(...)):
    """Upload and import an official WITRN CSV file into a new SQLite session."""
    temp_path = STORAGE_DIR / f"temp_import_{file.filename}"
    try:
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)

        samples = import_official_csv(temp_path)
        if not samples:
            raise HTTPException(status_code=400, detail="No valid samples found in CSV")

        session_id = f"imported_{Path(file.filename).stem}"
        new_db = STORAGE_DIR / f"{session_id}.sqlite"
        from ..core.recorder import RecordingSession
        sess = RecordingSession(new_db, rate=0, metadata={"source": file.filename, "imported": "1"})
        for s in samples:
            sess.append(s)
        sess.close(completed=True)

        return {
            "status": "imported",
            "session_id": session_id,
            "sample_count": len(samples),
        }
    finally:
        if temp_path.exists():
            temp_path.unlink()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        # Send current status upon connection
        await websocket.send_text(json.dumps({
            "type": "init",
            "device": device_state,
            "recorder": recorder.get_status(),
        }))
        while True:
            # Client heartbeat or commands
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Mount static directory for frontend
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
