import os
import shutil
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import ytdlp_service

app = FastAPI(title="YouTube Video & Audio Downloader", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    APP_DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DATA_DIR = BASE_DIR

STATIC_DIR = os.path.join(BASE_DIR, "static")
COOKIES_DIR = os.path.join(APP_DATA_DIR, "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)


class ExtractRequest(BaseModel):
    url: str
    auth_mode: Optional[str] = "none"  # Default is 'none' (Safe Anonymous Mode)
    browser: Optional[str] = "opera_gx"
    cookie_text: Optional[str] = None

class DownloadRequest(BaseModel):
    url: str
    download_type: Optional[str] = "video"
    format_id: Optional[str] = "best"
    audio_ext: Optional[str] = "mp3"
    auth_mode: Optional[str] = "none"
    browser: Optional[str] = "opera_gx"
    cookie_text: Optional[str] = None
    quality_label: Optional[str] = ""

def build_auth_config(auth_mode: Optional[str], browser: Optional[str], cookie_text: Optional[str]):
    mode = auth_mode or 'none'
    auth_config = {'mode': mode, 'browser': browser or 'auto'}
    if mode == 'text' and cookie_text:
        auth_config['content'] = cookie_text
    elif mode == 'file':
        uploaded = os.path.join(COOKIES_DIR, "uploaded_cookies.txt")
        if os.path.exists(uploaded):
            auth_config['file_path'] = uploaded
    return auth_config

@app.get("/api/browsers")
async def list_browsers():
    """Returns detected system browsers and their cookie status."""
    return {"browsers": ytdlp_service.get_installed_browsers_info()}

@app.post("/api/extract")
async def extract_info(req: ExtractRequest):
    """Extracts video metadata, all available resolutions, and FPS options."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Please provide a valid YouTube URL.")
    
    url = req.url.strip()
    auth_config = build_auth_config(req.auth_mode, req.browser, req.cookie_text)
    
    try:
        data = ytdlp_service.extract_video_info(url, auth_config)
        return data
    except Exception as e:
        err = str(e)
        if "Sign in to confirm" in err or "confirm you're not a bot" in err:
            raise HTTPException(
                status_code=403, 
                detail="YouTube anti-bot check triggered. Switch to 'Browser Session' (e.g. Opera GX) or upload a cookies.txt in Login Settings to access this video."
            )
        raise HTTPException(status_code=400, detail=f"Failed to fetch video details: {err}")

@app.post("/api/download")
async def start_download(req: DownloadRequest):
    """Queues a download task for the chosen format and returns task_id."""
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="Missing YouTube URL.")
        
    auth_config = build_auth_config(req.auth_mode, req.browser, req.cookie_text)
    task_id = ytdlp_service.start_download_task(
        url=req.url.strip(),
        download_type=req.download_type or "video",
        format_id=req.format_id or "best",
        audio_ext=req.audio_ext or "mp3",
        auth_config=auth_config,
        quality_label=req.quality_label or ""
    )
    return {"task_id": task_id, "status": "queued"}

@app.post("/api/cancel/{task_id}")
async def cancel_download(task_id: str):
    """Cancels a running or queued download and purges temp files."""
    success = ytdlp_service.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already finished.")
    return {"status": "cancelled", "task_id": task_id}

@app.get("/api/status/{task_id}")
async def get_status(task_id: str):
    """Polls real-time download and processing status."""
    task = ytdlp_service.get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Download task not found.")
    return task

@app.get("/api/file/{task_id}")
async def download_file(task_id: str):
    """Streams the completed video/audio file to the user's browser."""
    task = ytdlp_service.get_task_status(task_id)
    if not task or task.get('status') != 'completed':
        raise HTTPException(status_code=400, detail="File is not ready yet.")
        
    filepath = task.get('file_path')
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found on server.")
        
    filename = task.get('filename') or os.path.basename(filepath)
    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.post("/api/upload-cookies")
async def upload_cookies(file: UploadFile = File(...)):
    """Saves an uploaded cookies.txt file safely."""
    save_path = os.path.join(COOKIES_DIR, "uploaded_cookies.txt")
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"status": "success", "message": f"Saved {file.filename} successfully."}

@app.post("/api/open-folder")
async def open_downloads_folder():
    """Opens the Windows Downloads folder in Explorer."""
    try:
        os.startfile(ytdlp_service.DOWNLOADS_DIR)
        return {"status": "success", "path": ytdlp_service.DOWNLOADS_DIR}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
