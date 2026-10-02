import os
import sys
import re
import math
import shutil
import uuid
import threading
import time
from typing import Dict, Any, List, Optional
import yt_dlp
import imageio_ffmpeg
from yt_dlp.cookies import extract_cookies_from_browser

# Determine directory paths based on whether frozen by PyInstaller or running directly
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

DOWNLOADS_DIR = os.path.join(APP_DIR, "downloads")
COOKIES_DIR = os.path.join(APP_DIR, "cookies")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
os.makedirs(COOKIES_DIR, exist_ok=True)

# Detect FFmpeg executable
bundled_ffmpeg = os.path.join(BUNDLE_DIR, "bin", "ffmpeg.exe")
local_ffmpeg = os.path.join(APP_DIR, "bin", "ffmpeg.exe")

if os.path.exists(bundled_ffmpeg):
    FFMPEG_PATH = bundled_ffmpeg
elif os.path.exists(local_ffmpeg):
    FFMPEG_PATH = local_ffmpeg
else:
    try:
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_PATH = "ffmpeg"

NODE_PATH = r"C:\Program Files\nodejs\node.exe"
OPERA_GX_PATH = os.path.expandvars(r"%APPDATA%\Opera Software\Opera GX Stable")

class DownloadCancelledException(Exception):
    """Raised when a download is cancelled by user."""
    pass

# In-memory download task tracker
tasks: Dict[str, Dict[str, Any]] = {}
tasks_lock = threading.Lock()

def get_installed_browsers_info() -> List[Dict[str, Any]]:
    """Detects browsers on the system and reports cookie availability."""
    browsers = [
        {"id": "opera_gx", "name": "Opera GX", "type": "opera", "path": OPERA_GX_PATH},
        {"id": "edge", "name": "Microsoft Edge", "type": "edge", "path": None},
        {"id": "chrome", "name": "Google Chrome", "type": "chrome", "path": None},
        {"id": "brave", "name": "Brave Browser", "type": "brave", "path": None},
        {"id": "firefox", "name": "Mozilla Firefox", "type": "firefox", "path": None},
    ]
    
    result = []
    for b in browsers:
        has_cookies = False
        yt_count = 0
        status_msg = "Not detected"
        try:
            if b['id'] == 'opera_gx':
                if os.path.exists(OPERA_GX_PATH):
                    cj = extract_cookies_from_browser('opera', profile=OPERA_GX_PATH)
                    yt_c = [c for c in cj if 'youtube.com' in c.domain]
                    has_cookies = len(yt_c) > 0
                    yt_count = len(yt_c)
                    status_msg = f"Ready ({yt_count} YouTube cookies found)"
                else:
                    status_msg = "Profile not found"
            else:
                cj = extract_cookies_from_browser(b['type'])
                yt_c = [c for c in cj if 'youtube.com' in c.domain]
                has_cookies = len(yt_c) > 0
                yt_count = len(yt_c)
                status_msg = f"Ready ({yt_count} YouTube cookies found)"
        except Exception as e:
            status_msg = f"Locked or unavailable ({type(e).__name__})"
            
        result.append({
            "id": b["id"],
            "name": b["name"],
            "has_cookies": has_cookies,
            "youtube_cookies": yt_count,
            "status": status_msg
        })
    return result

def get_base_ydl_opts(auth_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Builds base yt-dlp options. Default is Safe Anonymous Mode."""
    opts: Dict[str, Any] = {
        'ffmpeg_location': FFMPEG_PATH,
        'remote_components': ['ejs:github'],
        'quiet': True,
        'no_warnings': True,
        'ignoreconfig': True,  # 100% isolated: never loads external configs or ambient cookies
    }
    
    if os.path.exists(NODE_PATH):
        opts['js_runtimes'] = {'node': {}}
        
    if not auth_config:
        auth_config = {'mode': 'none'}
        
    mode = auth_config.get('mode', 'none')
    
    if mode == 'browser':
        browser = auth_config.get('browser', 'auto')
        if browser == 'opera_gx' or (browser == 'auto' and os.path.exists(OPERA_GX_PATH)):
            opts['cookiesfrombrowser'] = ('opera', OPERA_GX_PATH, None, None)
        elif browser in ['chrome', 'edge', 'firefox', 'brave', 'opera']:
            opts['cookiesfrombrowser'] = (browser, None, None, None)
    elif mode == 'file':
        cookie_file = auth_config.get('file_path')
        if cookie_file and os.path.exists(cookie_file):
            opts['cookiefile'] = cookie_file
    elif mode == 'text':
        cookie_text = auth_config.get('content', '')
        if cookie_text.strip():
            tmp_cookie = os.path.join(COOKIES_DIR, "active_cookies.txt")
            with open(tmp_cookie, "w", encoding="utf-8") as f:
                f.write(cookie_text)
            opts['cookiefile'] = tmp_cookie
            
    return opts

def format_bytes(bytes_val: Optional[float]) -> str:
    if not bytes_val or bytes_val <= 0:
        return "Unknown size"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(bytes_val, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_val / p, 1)
    return f"{s} {units[i]}"

def format_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "00:00"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def extract_video_info(url: str, auth_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extracts all video details, resolutions, and fps options."""
    ydl_opts = get_base_ydl_opts(auth_config)
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
    title = info.get('title', 'Unknown Title')
    duration = info.get('duration', 0)
    thumbnail = info.get('thumbnail')
    channel = info.get('uploader') or info.get('channel', 'Unknown Creator')
    view_count = info.get('view_count', 0)
    upload_date = info.get('upload_date', '')
    
    formats = info.get('formats', [])
    
    best_audio_size = 0
    best_audio_abr = 128
    audio_formats = []
    
    for f in formats:
        if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
            abr = f.get('abr') or 0
            size = f.get('filesize') or f.get('filesize_approx') or 0
            if size > best_audio_size:
                best_audio_size = size
            if abr > best_audio_abr:
                best_audio_abr = abr
                
            audio_formats.append({
                'format_id': f.get('format_id'),
                'ext': f.get('ext'),
                'abr': round(abr) if abr else 'Auto',
                'filesize': size,
                'filesize_str': format_bytes(size) if size else ('Estimated ~' + format_bytes((abr * 1000 / 8) * duration) if (abr and duration) else 'Unknown'),
                'acodec': f.get('acodec')
            })
            
    if best_audio_size == 0 and duration:
        best_audio_size = (128 * 1000 / 8) * duration
        
    video_formats = []
    seen_combinations = set()
    
    for f in formats:
        height = f.get('height')
        vcodec = f.get('vcodec')
        if not height or vcodec == 'none':
            continue
            
        fps = f.get('fps') or 30
        fps_int = round(fps)
        ext = f.get('ext', 'mp4')
        format_id = f.get('format_id')
        format_note = f.get('format_note', '')
        dynamic_range = f.get('dynamic_range', 'SDR')
        
        codec_name = "H.264"
        if "vp9" in vcodec.lower() or "vp09" in vcodec.lower():
            codec_name = "VP9"
        elif "av01" in vcodec.lower() or "av1" in vcodec.lower():
            codec_name = "AV1"
        elif "avc" in vcodec.lower() or "h264" in vcodec.lower():
            codec_name = "H.264"
            
        if height >= 4320:
            res_label = "8K Ultra HD"
        elif height >= 2160:
            res_label = "4K Ultra HD"
        elif height >= 1440:
            res_label = "2K Quad HD"
        elif height >= 1080:
            res_label = "1080p Full HD"
        elif height >= 720:
            res_label = "720p HD"
        elif height >= 480:
            res_label = "480p SD"
        elif height >= 360:
            res_label = "360p"
        elif height >= 240:
            res_label = "240p"
        else:
            res_label = f"{height}p"
            
        video_size = f.get('filesize') or f.get('filesize_approx') or 0
        total_size = (video_size + best_audio_size) if video_size > 0 else 0
        
        if total_size == 0 and duration:
            vbr = f.get('vbr') or f.get('tbr') or 0
            if vbr:
                total_size = ((vbr + best_audio_abr) * 1000 / 8) * duration
                
        combo_key = (height, fps_int, codec_name)
        if combo_key in seen_combinations:
            continue
        seen_combinations.add(combo_key)
        
        video_formats.append({
            'format_id': format_id,
            'height': height,
            'width': f.get('width'),
            'fps': fps_int,
            'is_high_fps': fps_int >= 50,
            'res_label': res_label,
            'codec': codec_name,
            'raw_vcodec': vcodec,
            'ext': 'mp4',
            'container': ext,
            'format_note': format_note,
            'dynamic_range': dynamic_range,
            'filesize': total_size,
            'filesize_str': format_bytes(total_size) if total_size > 0 else "Dynamic",
            'has_audio': f.get('acodec') != 'none'
        })
        
    def sort_key(item):
        codec_prio = 3 if item['codec'] == 'H.264' else (2 if item['codec'] == 'VP9' else 1)
        return (item['height'], item['fps'], codec_prio)
        
    video_formats.sort(key=sort_key, reverse=True)
    audio_formats.sort(key=lambda x: (x.get('abr') if isinstance(x.get('abr'), (int, float)) else 0), reverse=True)
    
    best_video = video_formats[0] if video_formats else None
    
    return {
        'id': info.get('id'),
        'url': url,
        'title': title,
        'channel': channel,
        'thumbnail': thumbnail,
        'duration': duration,
        'duration_str': format_duration(duration),
        'view_count': f"{view_count:,}" if view_count else "N/A",
        'upload_date': upload_date,
        'video_formats': video_formats,
        'audio_formats': audio_formats,
        'best_video': best_video,
        'total_video_options': len(video_formats),
    }

def clean_task_files(task_id: str):
    """Deletes any partial or temporary files associated with a task_id."""
    try:
        for fname in os.listdir(DOWNLOADS_DIR):
            if fname.startswith(task_id):
                file_to_del = os.path.join(DOWNLOADS_DIR, fname)
                try:
                    if os.path.isfile(file_to_del):
                        os.remove(file_to_del)
                except Exception:
                    pass
    except Exception:
        pass

def cancel_task(task_id: str) -> bool:
    """Cancels a running or queued download task and deletes partial files."""
    with tasks_lock:
        if task_id not in tasks:
            return False
        tasks[task_id]['cancelled'] = True
        tasks[task_id]['status'] = 'cancelled'
        tasks[task_id]['message'] = 'Download cancelled by user.'
        tasks[task_id]['speed'] = '0 KB/s'
        tasks[task_id]['eta'] = '--'
        
    threading.Thread(target=clean_task_files, args=(task_id,), daemon=True).start()
    return True

def _download_worker(task_id: str, url: str, download_type: str, format_id: str, audio_ext: str, auth_config: Optional[Dict[str, Any]]):
    with tasks_lock:
        tasks[task_id]['status'] = 'downloading'
        tasks[task_id]['progress'] = 0.0
        tasks[task_id]['message'] = 'Initializing download...'

    def progress_hook(d):
        with tasks_lock:
            if task_id not in tasks:
                return
            if tasks[task_id].get('cancelled'):
                raise DownloadCancelledException("Download cancelled by user.")
                
            status = d.get('status')
            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                
                if total > 0:
                    percent = round((downloaded / total) * 100, 1)
                else:
                    percent = 0.0
                    
                speed = d.get('speed')
                speed_str = format_bytes(speed) + "/s" if speed else "Calculating..."
                eta = d.get('eta')
                eta_str = f"{eta}s" if eta else "Calculating..."
                
                tasks[task_id]['progress'] = percent
                tasks[task_id]['downloaded_bytes'] = downloaded
                tasks[task_id]['total_bytes'] = total
                tasks[task_id]['speed'] = speed_str
                tasks[task_id]['eta'] = eta_str
                tasks[task_id]['message'] = f"Downloading: {percent}% at {speed_str} (ETA: {eta_str})"
                
            elif status == 'finished':
                tasks[task_id]['status'] = 'processing'
                tasks[task_id]['progress'] = 98.0
                tasks[task_id]['message'] = 'Merging video and audio with FFmpeg...'

    ydl_opts = get_base_ydl_opts(auth_config)
    ydl_opts['progress_hooks'] = [progress_hook]
    ydl_opts['quiet'] = False
    
    outtmpl = os.path.join(DOWNLOADS_DIR, f"{task_id}_%(title).100s.%(ext)s")
    ydl_opts['outtmpl'] = outtmpl

    if download_type == 'video':
        if format_id == 'best':
            ydl_opts['format'] = 'bestvideo+bestaudio/best'
        else:
            ydl_opts['format'] = f"{format_id}+bestaudio/best"
        ydl_opts['merge_output_format'] = 'mp4'
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }]
    elif download_type == 'audio':
        ydl_opts['format'] = format_id if (format_id and format_id != 'best') else 'bestaudio/best'
        if audio_ext == 'mp3':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '320',
            }]
        elif audio_ext == 'm4a':
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
                'preferredquality': '256',
            }]
    elif download_type == 'video_only':
        ydl_opts['format'] = format_id

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')

        with tasks_lock:
            if tasks[task_id].get('cancelled'):
                clean_task_files(task_id)
                return

        matched_file = None
        for filename in os.listdir(DOWNLOADS_DIR):
            if filename.startswith(task_id) and not filename.endswith('.part'):
                matched_file = os.path.join(DOWNLOADS_DIR, filename)
                break

        if matched_file and os.path.exists(matched_file):
            display_name = os.path.basename(matched_file).replace(f"{task_id}_", "")
            file_size = os.path.getsize(matched_file)
            with tasks_lock:
                tasks[task_id]['status'] = 'completed'
                tasks[task_id]['progress'] = 100.0
                tasks[task_id]['message'] = 'Ready for download!'
                tasks[task_id]['file_path'] = matched_file
                tasks[task_id]['filename'] = display_name
                tasks[task_id]['filesize'] = file_size
                tasks[task_id]['filesize_str'] = format_bytes(file_size)
        else:
            raise Exception("Output file was not found after processing.")

    except DownloadCancelledException:
        clean_task_files(task_id)
        with tasks_lock:
            tasks[task_id]['status'] = 'cancelled'
            tasks[task_id]['message'] = 'Download cancelled by user.'
    except Exception as e:
        with tasks_lock:
            if tasks[task_id].get('cancelled'):
                clean_task_files(task_id)
                return
        err_msg = str(e)
        if "Sign in to confirm" in err_msg or "confirm you're not a bot" in err_msg:
            err_msg = "YouTube anti-bot check triggered. You can enable Login under Settings to capture this video."
        with tasks_lock:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['message'] = err_msg
            tasks[task_id]['error'] = err_msg

def start_download_task(
    url: str,
    download_type: str = "video",
    format_id: str = "best",
    audio_ext: str = "mp3",
    auth_config: Optional[Dict[str, Any]] = None,
    quality_label: str = ""
) -> str:
    """Spawns an asynchronous download task and returns its task_id."""
    task_id = str(uuid.uuid4())[:8]
    with tasks_lock:
        tasks[task_id] = {
            'task_id': task_id,
            'url': url,
            'type': download_type,
            'format_id': format_id,
            'quality_label': quality_label,
            'status': 'queued',
            'progress': 0.0,
            'speed': '0 KB/s',
            'eta': '--',
            'message': 'Queued...',
            'error': None,
            'cancelled': False,
            'file_path': None,
            'filename': None,
            'filesize': 0,
            'filesize_str': '',
            'created_at': time.time()
        }

    t = threading.Thread(
        target=_download_worker,
        args=(task_id, url, download_type, format_id, audio_ext, auth_config),
        daemon=True
    )
    t.start()
    return task_id

def get_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    with tasks_lock:
        return tasks.get(task_id)

def unpack_paste_urls(input_url: str) -> List[str]:
    """
    Detects if the URL is a PrivateBin (e.g. paste.fitgirl-repacks.site) 
    or Pastebin paste, decrypts/fetches it, and returns the list of extracted URLs.
    """
    import urllib.parse
    # Match PrivateBin format: https://domain/?id#passphrase
    pb_match = re.search(r'(https?://[^/?#]+)/?\?([^#]+)#([A-Za-z0-9+/=_-]+)', input_url)
    if pb_match:
        try:
            from pbincli.api import PrivateBin
            from pbincli.format import Paste

            base_url = pb_match.group(1) + '/'
            paste_id = pb_match.group(2)
            passphrase = pb_match.group(3)

            api = PrivateBin({'server': base_url, 'proxy': None, 'verbose': False, 'debug': False})
            res = api.get(paste_id)
            p = Paste(debug=False)
            p.setVersion(res.get('v', 1))
            p.setHash(passphrase)
            p.loadJSON(res)
            p.decrypt()
            raw = p.getText()
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='replace')
            extracted = re.findall(r'https?://[^\s<>"\'\)]+', raw)
            if extracted:
                return extracted
        except Exception:
            pass

    return [input_url]

def _direct_file_worker(task_id: str, url: str, destination_dir: str, custom_filename: Optional[str] = None):
    import urllib.request
    import urllib.parse
    
    with tasks_lock:
        tasks[task_id]['status'] = 'downloading'
        tasks[task_id]['message'] = 'Connecting to server...'

    target_path = ""
    try:
        # Determine filename
        filename = custom_filename
        if not filename:
            parsed = urllib.parse.urlparse(url)
            if parsed.fragment:
                filename = parsed.fragment
            else:
                path = parsed.path
                filename = os.path.basename(path) or f"download_{task_id}.bin"

        # Sanitize filename
        filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
        os.makedirs(destination_dir, exist_ok=True)
        target_path = os.path.join(destination_dir, filename)

        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': '*/*'
        })

        with urllib.request.urlopen(req, timeout=15) as resp:
            total_size = resp.headers.get('Content-Length')
            total_bytes = int(total_size) if total_size and total_size.isdigit() else 0
            
            with tasks_lock:
                tasks[task_id]['total_bytes'] = total_bytes
                tasks[task_id]['filename'] = filename
                tasks[task_id]['file_path'] = target_path

            downloaded = 0
            start_time = time.time()
            last_time = start_time
            last_bytes = 0

            with open(target_path, 'wb') as f:
                while True:
                    with tasks_lock:
                        if tasks[task_id].get('cancelled'):
                            raise DownloadCancelledException("Cancelled by user.")

                    chunk = resp.read(65536) # 64 KB chunk
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_time >= 0.5:
                        chunk_time = now - last_time
                        chunk_bytes = downloaded - last_bytes
                        speed = chunk_bytes / chunk_time if chunk_time > 0 else 0
                        speed_str = format_bytes(speed) + "/s"

                        if total_bytes > 0:
                            percent = round((downloaded / total_bytes) * 100, 1)
                            rem_bytes = max(0, total_bytes - downloaded)
                            eta_sec = int(rem_bytes / speed) if speed > 0 else 0
                            eta_str = f"{eta_sec}s"
                        else:
                            percent = 50.0
                            eta_str = "--"

                        with tasks_lock:
                            tasks[task_id]['progress'] = percent
                            tasks[task_id]['downloaded_bytes'] = downloaded
                            tasks[task_id]['speed'] = speed_str
                            tasks[task_id]['eta'] = eta_str
                            tasks[task_id]['message'] = f"Downloading: {percent}% at {speed_str} (ETA: {eta_str})"

                        last_time = now
                        last_bytes = downloaded

        with tasks_lock:
            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100.0
            tasks[task_id]['speed'] = '0 KB/s'
            tasks[task_id]['eta'] = '0s'
            tasks[task_id]['message'] = '✓ Download completed!'

    except DownloadCancelledException:
        with tasks_lock:
            tasks[task_id]['status'] = 'cancelled'
            tasks[task_id]['message'] = 'Download cancelled.'
        try:
            if target_path and os.path.exists(target_path):
                os.remove(target_path)
        except Exception:
            pass
    except Exception as e:
        err_msg = str(e)
        if "403" in err_msg:
            err_msg = "HTTP 403 (Host protection / Cloudflare challenge triggered)."
        with tasks_lock:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = err_msg
            tasks[task_id]['message'] = f"Failed: {err_msg}"

def start_direct_download_task(
    url: str,
    destination_dir: str,
    custom_filename: Optional[str] = None,
    quality_label: str = "Direct Download"
) -> str:
    """Spawns an asynchronous direct file download task and returns its task_id."""
    task_id = str(uuid.uuid4())[:8]
    with tasks_lock:
        tasks[task_id] = {
            'task_id': task_id,
            'url': url,
            'type': 'direct_file',
            'custom_filename': custom_filename,
            'quality_label': quality_label,
            'status': 'queued',
            'progress': 0.0,
            'speed': '0 KB/s',
            'eta': '--',
            'message': 'Queued...',
            'error': None,
            'cancelled': False,
            'file_path': None,
            'filename': custom_filename,
            'filesize': 0,
            'filesize_str': '',
            'created_at': time.time()
        }
    t = threading.Thread(
        target=_direct_file_worker,
        args=(task_id, url, destination_dir, custom_filename),
        daemon=True
    )
    t.start()
    return task_id
