import os
import sys
import threading
import time
import io
import urllib.request
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk

# Determine application directory
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(APP_DIR)

import ytdlp_service

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class YouTubeDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader Pro")
        self.geometry("1020x820")
        self.minsize(880, 650)
        self.configure(fg_color="#0b0f19")

        # State
        self.current_video_data = None
        self.active_task_id = None
        self.active_format_key = None
        self.format_states = {}
        self.tracking_active = False
        self.custom_cookie_file = None

        self._build_ui()

    def _build_ui(self):
        # 1. Top Navigation Bar
        header = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=0, height=62)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(fill="both", expand=True, padx=22, pady=10)

        title_lbl = ctk.CTkLabel(
            header_content,
            text="▶  YouTube Downloader Pro",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff"
        )
        title_lbl.pack(side="left")

        badge_lbl = ctk.CTkLabel(
            header_content,
            text=" All Qualities & 60 FPS ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#371b1d",
            text_color="#f87171",
            corner_radius=6
        )
        badge_lbl.pack(side="left", padx=12)

        open_folder_btn = ctk.CTkButton(
            header_content,
            text="📁 Open Downloads Folder",
            width=180,
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#e2e8f0",
            command=self.open_downloads_folder
        )
        open_folder_btn.pack(side="right")

        # 2. Main Scrollable Container
        self.main_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=(12, 5))

        # 3. Privacy & Auth Settings Card (Always visible with toggle options)
        auth_card = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=10, border_width=1, border_color="#1f2937")
        auth_card.pack(fill="x", pady=(0, 12), padx=2, ipady=4)

        auth_top = ctk.CTkFrame(auth_card, fg_color="transparent")
        auth_top.pack(fill="x", padx=14, pady=(8, 4))

        ctk.CTkLabel(
            auth_top,
            text="🔒 YouTube Authentication & Login Settings:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e2e8f0"
        ).pack(side="left")

        self.auth_mode_var = ctk.StringVar(value="none")

        # Radio Options
        radio_row = ctk.CTkFrame(auth_card, fg_color="transparent")
        radio_row.pack(fill="x", padx=14, pady=(0, 8))

        self.r_safe = ctk.CTkRadioButton(
            radio_row,
            text="Safe Mode (Anonymous, Zero browser access)",
            variable=self.auth_mode_var,
            value="none",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#34d399",
            fg_color="#10b981",
            command=self._on_auth_mode_change
        )
        self.r_safe.pack(side="left", padx=(0, 15))

        self.r_browser = ctk.CTkRadioButton(
            radio_row,
            text="Use Browser Session:",
            variable=self.auth_mode_var,
            value="browser",
            font=ctk.CTkFont(size=11),
            text_color="#cbd5e1",
            fg_color="#ef4444",
            command=self._on_auth_mode_change
        )
        self.r_browser.pack(side="left", padx=(0, 6))

        self.browser_dropdown = ctk.CTkComboBox(
            radio_row,
            values=["Opera GX", "Microsoft Edge", "Google Chrome", "Mozilla Firefox"],
            width=140,
            height=26,
            font=ctk.CTkFont(size=11),
            command=self._on_browser_selected
        )
        self.browser_dropdown.set("Opera GX")
        self.browser_dropdown.pack(side="left", padx=(0, 15))

        self.r_file = ctk.CTkRadioButton(
            radio_row,
            text="Upload cookies.txt",
            variable=self.auth_mode_var,
            value="file",
            font=ctk.CTkFont(size=11),
            text_color="#cbd5e1",
            fg_color="#ef4444",
            command=self._on_auth_mode_change
        )
        self.r_file.pack(side="left", padx=(0, 6))

        self.upload_cookie_btn = ctk.CTkButton(
            radio_row,
            text="Browse...",
            width=70,
            height=26,
            font=ctk.CTkFont(size=10),
            fg_color="#1f2937",
            hover_color="#374151",
            command=self.select_cookie_file
        )
        self.upload_cookie_btn.pack(side="left")

        # 4. Input Card
        input_card = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")
        input_card.pack(fill="x", pady=(0, 14), padx=2, ipady=8)

        ctk.CTkLabel(
            input_card,
            text="Enter YouTube Video Link",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=16, pady=(8, 2))

        ctk.CTkLabel(
            input_card,
            text="Supports regular videos, YouTube Shorts, 4K/8K, 60 FPS, music, and podcasts",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # URL Input Row
        input_row = ctk.CTkFrame(input_card, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(0, 8))

        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Paste YouTube URL here (e.g. https://www.youtube.com/watch?v=...)",
            height=42,
            font=ctk.CTkFont(size=13),
            fg_color="#030712",
            border_color="#374151"
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.url_entry.bind("<Return>", lambda e: self.fetch_video_info())

        paste_btn = ctk.CTkButton(
            input_row,
            text="📋 Paste",
            width=80,
            height=42,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1f2937",
            hover_color="#374151",
            command=self.paste_from_clipboard
        )
        paste_btn.pack(side="left", padx=(0, 8))

        self.fetch_btn = ctk.CTkButton(
            input_row,
            text="🔍 Fetch Qualities",
            width=150,
            height=42,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=self.fetch_video_info
        )
        self.fetch_btn.pack(side="left")

        # Quick sample links row
        sample_row = ctk.CTkFrame(input_card, fg_color="transparent")
        sample_row.pack(fill="x", padx=16, pady=(0, 6))

        ctk.CTkLabel(
            sample_row,
            text="Quick Samples:",
            font=ctk.CTkFont(size=11),
            text_color="#6b7280"
        ).pack(side="left", padx=(0, 8))

        s1_btn = ctk.CTkButton(
            sample_row,
            text="Rick Astley (4K 60FPS)",
            width=150,
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="#1f2937",
            hover_color="#374151",
            command=lambda: self._load_sample("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        )
        s1_btn.pack(side="left", padx=(0, 6))

        s2_btn = ctk.CTkButton(
            sample_row,
            text="Me at the zoo (Short)",
            width=140,
            height=24,
            font=ctk.CTkFont(size=10),
            fg_color="#1f2937",
            hover_color="#374151",
            command=lambda: self._load_sample("https://www.youtube.com/watch?v=jNQXAC9IVRw")
        )
        s2_btn.pack(side="left")

        # Status Label
        self.status_lbl = ctk.CTkLabel(
            input_card,
            text="Ready. Paste a link or click a sample to fetch all available qualities.",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af"
        )
        self.status_lbl.pack(anchor="w", padx=16, pady=(2, 4))

        # 5. Video Details Section (Populates dynamically)
        self.video_details_frame = ctk.CTkFrame(self.main_container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")

        # Top Video Overview inside card
        self.video_header_frame = ctk.CTkFrame(self.video_details_frame, fg_color="transparent")
        self.video_header_frame.pack(fill="x", padx=16, pady=16)

        # Thumbnail Label
        self.thumb_lbl = ctk.CTkLabel(self.video_header_frame, text="", width=200, height=112, fg_color="#030712", corner_radius=8)
        self.thumb_lbl.pack(side="left", padx=(0, 16))

        # Metadata
        self.meta_frame = ctk.CTkFrame(self.video_header_frame, fg_color="transparent")
        self.meta_frame.pack(side="left", fill="both", expand=True)

        self.video_title_lbl = ctk.CTkLabel(
            self.meta_frame,
            text="Video Title",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff",
            wraplength=620,
            justify="left"
        )
        self.video_title_lbl.pack(anchor="w", pady=(0, 4))

        self.video_sub_lbl = ctk.CTkLabel(
            self.meta_frame,
            text="Channel • Views • Duration",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af"
        )
        self.video_sub_lbl.pack(anchor="w", pady=(0, 10))

        # Quick Best Download Button
        self.quick_dl_btn = ctk.CTkButton(
            self.meta_frame,
            text="⚡ Download Highest Quality Available (Best MP4)",
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#b91c1c",
            hover_color="#991b1b"
        )
        self.quick_dl_btn.pack(anchor="w")

        # 6. Formats Tabs (Video Qualities & Audio Only)
        self.tab_view = ctk.CTkTabview(self.video_details_frame, fg_color="#0b0f19")
        self.tab_view.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.tab_video = self.tab_view.add("🎬 Video (All Resolutions & 60 FPS)")
        self.tab_audio = self.tab_view.add("🎵 Audio Only (MP3 320k / M4A)")

        # Scrollable rows inside tabs
        self.video_rows_frame = ctk.CTkFrame(self.tab_video, fg_color="transparent")
        self.video_rows_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.audio_rows_frame = ctk.CTkFrame(self.tab_audio, fg_color="transparent")
        self.audio_rows_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # 7. Persistent Bottom Download Dock
        self.bottom_dock = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#374151")
        
        dock_content = ctk.CTkFrame(self.bottom_dock, fg_color="transparent")
        dock_content.pack(fill="both", expand=True, padx=16, pady=10)

        dock_top = ctk.CTkFrame(dock_content, fg_color="transparent")
        dock_top.pack(fill="x", pady=(0, 6))

        self.dock_title_lbl = ctk.CTkLabel(
            dock_top,
            text="Downloading video...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffffff"
        )
        self.dock_title_lbl.pack(side="left")

        self.dock_percent_lbl = ctk.CTkLabel(
            dock_top,
            text="0%",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f59e0b"
        )
        self.dock_percent_lbl.pack(side="right")

        self.dock_progress = ctk.CTkProgressBar(dock_content, height=10, progress_color="#ef4444")
        self.dock_progress.set(0.0)
        self.dock_progress.pack(fill="x", pady=(0, 6))

        dock_bottom = ctk.CTkFrame(dock_content, fg_color="transparent")
        dock_bottom.pack(fill="x")

        self.dock_status_lbl = ctk.CTkLabel(
            dock_bottom,
            text="Initializing download...",
            font=ctk.CTkFont(size=11),
            text_color="#9ca3af"
        )
        self.dock_status_lbl.pack(side="left")

        self.dock_cancel_btn = ctk.CTkButton(
            dock_bottom,
            text="✕ Cancel Download",
            width=130,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#991b1b",
            hover_color="#7f1d1d",
            command=self.cancel_active_download
        )
        self.dock_cancel_btn.pack(side="right")

    def _on_auth_mode_change(self):
        mode = self.auth_mode_var.get()
        if mode == "browser":
            self.set_status("Browser cookies mode enabled. Runs 100% locally on your PC.", "#fbbf24")
        elif mode == "none":
            self.set_status("Safe Anonymous Mode: Zero browser access, pure privacy.", "#34d399")

    def _on_browser_selected(self, choice):
        self.auth_mode_var.set("browser")

    def select_cookie_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Exported cookies.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.custom_cookie_file = file_path
            self.auth_mode_var.set("file")
            fname = os.path.basename(file_path)
            self.upload_cookie_btn.configure(text=fname[:12] + "...")
            self.set_status(f"Loaded cookie file: {fname}", "#34d399")

    def _load_sample(self, url):
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        self.fetch_video_info()

    def paste_from_clipboard(self):
        try:
            text = self.clipboard_get()
            if text:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, text.strip())
                self.fetch_video_info()
        except Exception:
            pass

    def open_downloads_folder(self):
        try:
            os.startfile(ytdlp_service.DOWNLOADS_DIR)
        except Exception as e:
            self.set_status(f"Could not open folder: {e}", "#f87171")

    def set_status(self, msg, color="#9ca3af"):
        self.status_lbl.configure(text=msg, text_color=color)

    def _get_auth_config(self):
        mode = self.auth_mode_var.get()
        browser_choice = self.browser_dropdown.get().lower()
        browser_map = {
            "opera gx": "opera_gx",
            "microsoft edge": "edge",
            "google chrome": "chrome",
            "mozilla firefox": "firefox"
        }
        b_key = browser_map.get(browser_choice, "opera_gx")

        auth_config = {'mode': mode, 'browser': b_key}
        if mode == 'file' and self.custom_cookie_file:
            auth_config['file_path'] = self.custom_cookie_file
        return auth_config

    def fetch_video_info(self):
        url = self.url_entry.get().strip()
        if not url:
            self.set_status("Please enter or paste a valid YouTube URL.", "#f87171")
            return

        self.fetch_btn.configure(state="disabled", text="Analyzing...")
        self.set_status("Extracting all available resolutions and 60 FPS streams...", "#fbbf24")

        auth_config = self._get_auth_config()

        def worker():
            try:
                data = ytdlp_service.extract_video_info(url, auth_config)
                self.after(0, lambda: self._on_info_fetched(data))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: self._on_info_error(err_msg))

        threading.Thread(target=worker, daemon=True).start()

    def _on_info_error(self, err_msg):
        self.fetch_btn.configure(state="normal", text="🔍 Fetch Qualities")
        if "Sign in to confirm" in err_msg or "bot" in err_msg:
            self.set_status("YouTube anti-bot check triggered. Switch to 'Browser Session' (e.g. Opera GX) or cookies.txt.", "#f87171")
        else:
            self.set_status(f"Error: {err_msg[:120]}", "#f87171")

    def _on_info_fetched(self, data):
        self.fetch_btn.configure(state="normal", text="🔍 Fetch Qualities")
        self.set_status(f"✓ Found {data.get('total_video_options', 0)} video quality and FPS options!", "#34d399")
        self.current_video_data = data

        self.video_details_frame.pack(fill="both", expand=True, pady=(0, 20))

        self.video_title_lbl.configure(text=data.get('title', 'Unknown Title'))
        self.video_sub_lbl.configure(
            text=f"Channel: {data.get('channel')}   •   Views: {data.get('view_count')}   •   Duration: {data.get('duration_str')}"
        )

        best_v = data.get('best_video')
        if best_v:
            lbl = f"⚡ Download Highest Quality: {best_v.get('res_label')} ({best_v.get('fps')}fps, {best_v.get('filesize_str')})"
            self.quick_dl_btn.configure(
                text=lbl,
                command=lambda: self.start_download(
                    data.get('url'),
                    'video',
                    best_v.get('format_id'),
                    'mp4',
                    f"{best_v.get('res_label')} {best_v.get('fps')}fps",
                    f"quick_{best_v.get('format_id')}"
                )
            )

        thumb_url = data.get('thumbnail')
        if thumb_url:
            threading.Thread(target=self._load_thumbnail, args=(thumb_url,), daemon=True).start()

        self._render_video_formats(data.get('video_formats', []))
        self._render_audio_formats(data.get('audio_formats', []))

    def _load_thumbnail(self, thumb_url):
        try:
            req = urllib.request.Request(thumb_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read()
            pil_img = Image.open(io.BytesIO(data))
            pil_img.thumbnail((200, 112))
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
            self.after(0, lambda: self.thumb_lbl.configure(image=ctk_img, text=""))
        except Exception:
            pass

    def _render_video_formats(self, formats):
        for widget in self.video_rows_frame.winfo_children():
            widget.destroy()

        if not formats:
            ctk.CTkLabel(self.video_rows_frame, text="No video formats available.", text_color="#9ca3af").pack(pady=10)
            return

        for f in formats:
            format_key = f"video_{f.get('format_id')}"
            row = ctk.CTkFrame(self.video_rows_frame, fg_color="#030712", corner_radius=8, height=48)
            row.pack(fill="x", pady=3)
            row.pack_propagate(False)

            # Resolution Badge
            res_badge = ctk.CTkLabel(
                row,
                text=f" {f.get('height')}p ",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color="#1e293b",
                text_color="#38bdf8",
                corner_radius=6,
                width=65
            )
            res_badge.pack(side="left", padx=(10, 8), pady=8)

            # FPS Badge
            fps = f.get('fps', 30)
            fps_color = "#34d399" if fps >= 50 else "#9ca3af"
            fps_bg = "#064e3b" if fps >= 50 else "#111827"
            
            fps_badge = ctk.CTkLabel(
                row,
                text=f" {fps} FPS ",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=fps_bg,
                text_color=fps_color,
                corner_radius=4
            )
            fps_badge.pack(side="left", padx=(0, 10))

            hdr_str = " [HDR]" if f.get('dynamic_range') == 'HDR' else ""
            info_str = f"{f.get('res_label')}{hdr_str}   •   Codec: {f.get('codec')}   •   Size: {f.get('filesize_str')}   •   🔊 Audio Merged"
            detail_lbl = ctk.CTkLabel(
                row,
                text=info_str,
                font=ctk.CTkFont(size=11),
                text_color="#e2e8f0"
            )
            detail_lbl.pack(side="left")

            dl_btn = ctk.CTkButton(
                row,
                text="⬇ Download MP4",
                width=130,
                height=30,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#1f2937",
                hover_color="#dc2626"
            )
            dl_btn.pack(side="right", padx=10, pady=8)

            def make_cmd(fid=f.get('format_id'), qlbl=f"{f.get('res_label')} {f.get('fps')}fps", fk=format_key, b=dl_btn):
                return lambda: self.start_download(self.current_video_data['url'], 'video', fid, 'mp4', qlbl, fk, b)

            dl_btn.configure(command=make_cmd())

    def _render_audio_formats(self, formats):
        for widget in self.audio_rows_frame.winfo_children():
            widget.destroy()

        presets = [
            ("MP3 Audio (High Quality 320kbps)", "mp3", "bestaudio", "Universally compatible with all phones, computers and car audio systems"),
            ("M4A Audio (Original AAC Quality)", "m4a", "bestaudio[ext=m4a]/bestaudio", "Pristine studio AAC audio directly from YouTube")
        ]

        for title, ext, fid, note in presets:
            row = ctk.CTkFrame(self.audio_rows_frame, fg_color="#030712", corner_radius=8, height=52)
            row.pack(fill="x", pady=4)
            row.pack_propagate(False)

            ctk.CTkLabel(
                row,
                text=f" 🎵 {ext.upper()} ",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#450a0a",
                text_color="#f87171",
                corner_radius=6,
                width=65
            ).pack(side="left", padx=(10, 8), pady=8)

            ctk.CTkLabel(
                row,
                text=f"{title}   •   {note}",
                font=ctk.CTkFont(size=11),
                text_color="#e2e8f0"
            ).pack(side="left")

            dl_btn = ctk.CTkButton(
                row,
                text=f"⬇ Download .{ext.upper()}",
                width=140,
                height=30,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#1f2937",
                hover_color="#dc2626"
            )
            dl_btn.pack(side="right", padx=10, pady=8)

            def make_audio_cmd(fid=fid, ext=ext, title=title):
                return lambda: self.start_download(self.current_video_data['url'], 'audio', fid, ext, title, f"audio_{ext}", dl_btn)

            dl_btn.configure(command=make_audio_cmd())

    def start_download(self, url, dl_type, format_id, ext, quality_label, format_key, btn=None):
        if self.format_states.get(format_key) == 'downloading':
            self.set_status("This quality is already downloading! See active progress bar below.", "#fbbf24")
            return

        if btn:
            btn.configure(text="Downloading...", state="disabled", fg_color="#78350f")

        self.format_states[format_key] = 'downloading'
        self.active_format_key = format_key

        self.bottom_dock.pack(fill="x", side="bottom", padx=20, pady=(5, 15))
        self.dock_title_lbl.configure(text=f"Downloading: {self.current_video_data.get('title', 'Video')[:50]}... [{quality_label}]")
        self.dock_status_lbl.configure(text="Initializing download with FFmpeg...")
        self.dock_percent_lbl.configure(text="0%")
        self.dock_progress.set(0.0)
        self.dock_cancel_btn.configure(state="normal", text="✕ Cancel Download")

        auth_config = self._get_auth_config()

        task_id = ytdlp_service.start_download_task(
            url=url,
            download_type=dl_type,
            format_id=format_id,
            audio_ext=ext,
            auth_config=auth_config,
            quality_label=quality_label
        )
        self.active_task_id = task_id
        self.tracking_active = True

        threading.Thread(target=self._track_progress, args=(task_id, format_key, btn), daemon=True).start()

    def cancel_active_download(self):
        if self.active_task_id:
            ytdlp_service.cancel_task(self.active_task_id)
            self.dock_status_lbl.configure(text="Download cancelled by user.")
            self.dock_cancel_btn.configure(state="disabled")
            self.dock_progress.set(0.0)
            self.tracking_active = False

            if self.active_format_key:
                self.format_states[self.active_format_key] = 'idle'

            self.after(3000, lambda: self.bottom_dock.pack_forget())

    def _track_progress(self, task_id, format_key, btn):
        while self.tracking_active:
            task = ytdlp_service.get_task_status(task_id)
            if not task:
                break

            status = task.get('status')
            pct = task.get('progress', 0.0) / 100.0
            pct_int = int(task.get('progress', 0.0))
            speed = task.get('speed', '')
            eta = task.get('eta', '')

            self.after(0, lambda p=pct, pi=pct_int, s=speed, e=eta, st=status, m=task.get('message', ''): self._update_dock_ui(p, pi, s, e, st, m))

            if status == 'completed':
                self.after(0, lambda: self._on_download_complete(format_key, btn))
                break
            elif status in ['error', 'cancelled']:
                self.after(0, lambda err=task.get('error', 'Failed'): self._on_download_error(format_key, btn, err))
                break

            time.sleep(0.5)

    def _update_dock_ui(self, pct, pct_int, speed, eta, status, msg):
        self.dock_progress.set(pct)
        self.dock_percent_lbl.configure(text=f"{pct_int}%")

        if status == 'downloading':
            self.dock_status_lbl.configure(text=f"Downloading at {speed}   •   ETA: {eta}")
        elif status == 'processing':
            self.dock_status_lbl.configure(text="Merging video and audio with FFmpeg...")
        elif status == 'completed':
            self.dock_status_lbl.configure(text="✓ Download complete! Saved to downloads folder.")

    def _on_download_complete(self, format_key, btn):
        self.tracking_active = False
        self.format_states[format_key] = 'completed'
        self.dock_cancel_btn.configure(text="✓ Completed", state="disabled")
        self.set_status("✓ Download complete! File saved in downloads folder.", "#34d399")

        if btn:
            btn.configure(text="✓ Downloaded", state="normal", fg_color="#064e3b")

        self.open_downloads_folder()

    def _on_download_error(self, format_key, btn, err):
        self.tracking_active = False
        self.format_states[format_key] = 'idle'
        self.dock_status_lbl.configure(text=f"Error: {err}")
        self.set_status(f"Download failed: {err}", "#f87171")

        if btn:
            btn.configure(text="⬇ Download MP4", state="normal", fg_color="#1f2937")

if __name__ == "__main__":
    try:
        app = YouTubeDownloaderApp()
        app.mainloop()
    except Exception as e:
        with open(os.path.join(APP_DIR, "crash_log.txt"), "w") as f:
            import traceback
            traceback.print_exc(file=f)
