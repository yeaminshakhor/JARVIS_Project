"""FastAPI server exposing JARVIS automation command endpoints."""

from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.Assistant import EnhancedProfessionalAIAutomation

app = FastAPI(title="JARVIS Automation API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jarvis = EnhancedProfessionalAIAutomation()


class CommandRequest(BaseModel):
    command: str | None = None
    text: str | None = None


def _status_from_result(result: Any) -> str:
    text = str(result or "")
    lowered = text.lower()
    if "failed" in lowered or "unknown command" in lowered or "denied" in lowered:
        return "error"
    return "success"


@app.post("/command")
def process_command(req: CommandRequest) -> Dict[str, Any]:
    raw_text = str(req.text or req.command or "").strip()
    parsed = jarvis.parse_natural_command(raw_text)

    results = []
    for cmd in parsed:
        action = str(cmd.get("action") or "unknown")
        params = {k: v for k, v in cmd.items() if k != "action"}
        if action == "unknown":
            # Reuse existing process path to include AI fallback + suggestion behavior.
            unknown_text = str(cmd.get("command") or "").strip() or raw_text
            results.append(str(jarvis.process_command(unknown_text)))
            continue
        results.append(str(jarvis.execute_command(action, **params)))

    result_text = "\n".join([r for r in results if str(r).strip()]).strip()
    if not result_text:
        result_text = jarvis.process_command(raw_text)

    return {
        "input": raw_text,
        "parsed": parsed,
        "commands": parsed,
        "results": results,
        "result": result_text,
        "status": _status_from_result(result_text),
    }


@app.get("/status")
def get_status() -> Dict[str, Any]:
    return {
        "system": jarvis.get_system_info(),
        "bluetooth": jarvis.get_bluetooth_info(),
    }


@app.get("/logs")
def get_logs() -> Dict[str, Any]:
    return {"logs": jarvis.logs[-50:]}
