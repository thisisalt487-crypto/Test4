import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import requests
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
DB_PATH = BASE_DIR / "jobs.json"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Private Seedance Omni Reference App")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def load_jobs() -> List[Dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    try:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_jobs(jobs: List[Dict[str, Any]]) -> None:
    DB_PATH.write_text(json.dumps(jobs, indent=2), encoding="utf-8")


def optimize_prompt_with_gpt6(user_prompt: str, reference_names: List[str]) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return user_prompt

    model = os.getenv("OPENAI_MODEL", "gpt-6")
    system = (
        "You are helping prepare a video generation prompt for an omni-reference model. "
        "Preserve the user's intent. Make the prompt more structured and specific. "
        "Mention subject, action, framing, style, motion, continuity, and reference usage. "
        "Return only the optimized prompt text."
    )
    input_text = (
        f"Original prompt:\n{user_prompt}\n\n"
        f"Available references: {', '.join(reference_names) if reference_names else 'None'}\n\n"
        "Write a clean production-ready prompt for a reference-driven video model."
    )

    try:
        resp = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": system}]},
                    {"role": "user", "content": [{"type": "input_text", "text": input_text}]},
                ],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"].strip()

        # Fallback parser for structured response payloads.
        outputs = data.get("output", [])
        texts = []
        for item in outputs:
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    texts.append(content["text"])
        joined = "\n".join(t.strip() for t in texts if t and t.strip())
        return joined or user_prompt
    except Exception:
        return user_prompt


def submit_seedance_job(payload: Dict[str, Any], file_paths: List[Path]) -> Dict[str, Any]:
    """
    Provider adapter.

    Set these env vars to connect a real provider:
      SEEDANCE_API_URL
      SEEDANCE_API_KEY
      SEEDANCE_API_AUTH_HEADER   (optional, defaults to Authorization)
      SEEDANCE_API_AUTH_PREFIX   (optional, defaults to Bearer)

    This starter keeps the provider contract in one place. Depending on where you
    access Seedance 2.5, you may need to change the request shape below.
    """
    api_url = os.getenv("SEEDANCE_API_URL")
    api_key = os.getenv("SEEDANCE_API_KEY")

    if not api_url or not api_key:
        return {
            "provider_mode": "mock",
            "status": "not_sent",
            "message": "No Seedance provider credentials are configured yet. Add SEEDANCE_API_URL and SEEDANCE_API_KEY to enable real generations.",
            "remote_job_id": None,
            "provider_response": None,
            "preview_url": None,
        }

    auth_header = os.getenv("SEEDANCE_API_AUTH_HEADER", "Authorization")
    auth_prefix = os.getenv("SEEDANCE_API_AUTH_PREFIX", "Bearer")

    headers = {auth_header: f"{auth_prefix} {api_key}".strip(), "Accept": "application/json"}
    data = {
        "prompt": payload["optimized_prompt"],
        "duration_seconds": str(payload["duration"]),
        "aspect_ratio": payload["aspect_ratio"],
        "resolution": payload["resolution"],
        "audio_enabled": str(payload["audio_enabled"]).lower(),
        "omni_reference_enabled": str(payload["omni_reference_enabled"]).lower(),
    }
    files = []
    handles = []
    try:
        for idx, fp in enumerate(file_paths):
            handle = open(fp, "rb")
            handles.append(handle)
            files.append(("references", (fp.name, handle, "application/octet-stream")))

        resp = requests.post(api_url, headers=headers, data=data, files=files, timeout=180)
        resp.raise_for_status()
        provider_json = resp.json()
        return {
            "provider_mode": "live",
            "status": provider_json.get("status", "submitted"),
            "message": provider_json.get("message", "Request submitted."),
            "remote_job_id": provider_json.get("id") or provider_json.get("job_id"),
            "provider_response": provider_json,
            "preview_url": provider_json.get("video_url") or provider_json.get("preview_url"),
        }
    finally:
        for h in handles:
            try:
                h.close()
            except Exception:
                pass


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/jobs")
def list_jobs():
    jobs = load_jobs()
    jobs.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return JSONResponse(jobs)


@app.post("/api/generate")
async def generate(
    prompt: str = Form(...),
    duration: int = Form(8),
    aspect_ratio: str = Form("16:9"),
    resolution: str = Form("720p"),
    audio_enabled: bool = Form(False),
    omni_reference_enabled: bool = Form(True),
    optimize_prompt: bool = Form(True),
    references: List[UploadFile] = File(default=[]),
):
    duration = max(4, min(duration, 30))
    job_id = str(uuid.uuid4())
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    saved_files: List[Path] = []
    reference_names: List[str] = []
    for ref in references:
        if not ref.filename:
            continue
        safe_name = ref.filename.replace("/", "_").replace("\\", "_")
        dest = job_dir / safe_name
        with dest.open("wb") as f:
            shutil.copyfileobj(ref.file, f)
        saved_files.append(dest)
        reference_names.append(safe_name)

    optimized = optimize_prompt_with_gpt6(prompt, reference_names) if optimize_prompt else prompt

    base_payload = {
        "job_id": job_id,
        "prompt": prompt,
        "optimized_prompt": optimized,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "audio_enabled": bool(audio_enabled),
        "omni_reference_enabled": bool(omni_reference_enabled),
    }

    provider = submit_seedance_job(base_payload, saved_files)

    record = {
        **base_payload,
        "provider_mode": provider["provider_mode"],
        "status": provider["status"],
        "message": provider["message"],
        "remote_job_id": provider["remote_job_id"],
        "provider_response": provider["provider_response"],
        "preview_url": provider["preview_url"],
        "reference_files": reference_names,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }

    jobs = load_jobs()
    jobs.append(record)
    save_jobs(jobs)

    return JSONResponse(record)
