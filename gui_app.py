import os
import sys
import threading
import time
import io
import re
import urllib.request
import urllib.parse
import webbrowser
from tkinter import filedialog
import customtkinter as ctk
from PIL import Image, ImageTk

# Base path handling for PyInstaller and source execution
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(APP_DIR)

import ytdlp_service

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class ModernYouTubeDownloader(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube Downloader Pro")
        self.geometry("1100x820")
        self.minsize(960, 680)
        self.configure(fg_color="#0b0f19")

        # Application State
        self.current_video_data = None
        self.active_task_id = None
        self.active_format_key = None
        self.format_states = {}
        self.tracking_active = False
        self.custom_cookie_file = None
        self.active_download_url = None
        self.download_destination = ytdlp_service.DOWNLOADS_DIR

        # Link Grabber State
        self.grabbed_links = []  # list of dicts: { url, name, type, size_str, size_bytes, status }

        self._build_ui()
        self.select_tab("single")

    def _build_ui(self):
        # Master Layout: Left Sidebar + Right Content Area
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0) # For persistent bottom download dock

        # ==========================================
        # LEFT SIDEBAR
        # ==========================================
        sidebar = ctk.CTkFrame(self, fg_color="#0f172a", width=220, corner_radius=0)
        sidebar.grid(row=0, column=0, sticky="nsew", rowspan=2)
        sidebar.grid_propagate(False)

        # Brand Header
        brand_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=18, pady=(22, 20))

        logo_lbl = ctk.CTkLabel(
            brand_frame,
            text="▶  YTDL Pro",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#ef4444"
        )
        logo_lbl.pack(anchor="w")

        sub_lbl = ctk.CTkLabel(
            brand_frame,
            text="All Qualities & Link Grabber",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Navigation Buttons
        self.nav_btns = {}

        nav_items = [
            ("single", "🎬  Single Downloader"),
            ("grabber", "🧲  Link Grabber (Bulk)"),
            ("settings", "⚙️  Settings & Privacy"),
        ]

        for tab_id, label in nav_items:
            btn = ctk.CTkButton(
                sidebar,
                text=label,
                height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent",
                text_color="#cbd5e1",
                hover_color="#1e293b",
                anchor="w",
                command=lambda t=tab_id: self.select_tab(t)
            )
            btn.pack(fill="x", padx=12, pady=4)
            self.nav_btns[tab_id] = btn

        # Bottom Sidebar Action
        sidebar_bottom = ctk.CTkFrame(sidebar, fg_color="transparent")
        sidebar_bottom.pack(side="bottom", fill="x", padx=12, pady=20)

        open_dir_btn = ctk.CTkButton(
            sidebar_bottom,
            text="📁  Open Downloads",
            height=36,
            corner_radius=8,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1e293b",
            hover_color="#334155",
            text_color="#e2e8f0",
            anchor="center",
            command=self.open_downloads_folder
        )
        open_dir_btn.pack(fill="x")

        # ==========================================
        # RIGHT CONTENT AREA (Frames for each tab)
        # ==========================================
        self.content_area = ctk.CTkFrame(self, fg_color="#0b0f19", corner_radius=0)
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        self.frames = {
            "single": self._build_single_downloader_frame(),
            "grabber": self._build_link_grabber_frame(),
            "settings": self._build_settings_frame()
        }

        # ==========================================
        # PERSISTENT BOTTOM DOWNLOAD DOCK
        # ==========================================
        self.bottom_dock = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=12, border_width=1, border_color="#334155")
        # Hidden initially; packed dynamically on download start

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
            text_color="#94a3b8"
        )
        self.dock_status_lbl.pack(side="left")

        self.dock_cancel_btn = ctk.CTkButton(
            dock_bottom,
            text="✕ Cancel",
            width=100,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#991b1b",
            hover_color="#7f1d1d",
            command=self.cancel_active_download
        )
        self.dock_cancel_btn.pack(side="right")

        self.dock_browser_btn = ctk.CTkButton(
            dock_bottom,
            text="🌐 Open Link in Browser",
            width=160,
            height=28,
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#b45309",
            hover_color="#d97706",
            command=self.open_active_in_browser
        )
        # Hidden by default; packed when Cloudflare challenge is triggered

    def open_active_in_browser(self):
        if self.active_download_url:
            webbrowser.open(self.active_download_url)

    def select_tab(self, tab_name):
        for t_id, frame in self.frames.items():
            frame.grid_forget()
            self.nav_btns[t_id].configure(fg_color="transparent", text_color="#cbd5e1")

        self.frames[tab_name].grid(row=0, column=0, sticky="nsew")
        self.nav_btns[tab_name].configure(fg_color="#ef4444", text_color="#ffffff")

    # ==========================================
    # TAB 1: SINGLE VIDEO DOWNLOADER
    # ==========================================
    def _build_single_downloader_frame(self):
        container = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")

        # Top Privacy Pill
        privacy_pill = ctk.CTkFrame(container, fg_color="#064e3b", corner_radius=8, height=34)
        privacy_pill.pack(fill="x", padx=16, pady=(14, 10))
        ctk.CTkLabel(
            privacy_pill,
            text="🛡️  Safe Anonymous Mode Active: Zero browser access, pure privacy.",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#6ee7b7"
        ).pack(side="left", padx=12, pady=6)

        # Input Card
        input_card = ctk.CTkFrame(container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")
        input_card.pack(fill="x", padx=16, pady=(0, 14), ipady=8)

        ctk.CTkLabel(
            input_card,
            text="Enter YouTube Video or Shorts Link",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            input_card,
            text="Paste any YouTube URL to extract all resolutions (8K, 4K, 1080p), 60 FPS streams, and pristine audio",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # URL Input Row
        input_row = ctk.CTkFrame(input_card, fg_color="transparent")
        input_row.pack(fill="x", padx=16, pady=(0, 8))

        self.url_entry = ctk.CTkEntry(
            input_row,
            placeholder_text="Paste YouTube link (e.g. https://www.youtube.com/watch?v=...)",
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

        # Quick Samples Row
        sample_row = ctk.CTkFrame(input_card, fg_color="transparent")
        sample_row.pack(fill="x", padx=16, pady=(0, 4))

        ctk.CTkLabel(
            sample_row,
            text="Quick Samples:",
            font=ctk.CTkFont(size=11),
            text_color="#64748b"
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

        self.status_lbl = ctk.CTkLabel(
            input_card,
            text="Ready. Paste a link or click a sample to fetch all available formats.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.status_lbl.pack(anchor="w", padx=16, pady=(4, 2))

        # Video Details Section (Populated dynamically)
        self.video_details_frame = ctk.CTkFrame(container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")

        self.video_header_frame = ctk.CTkFrame(self.video_details_frame, fg_color="transparent")
        self.video_header_frame.pack(fill="x", padx=16, pady=16)

        self.thumb_lbl = ctk.CTkLabel(self.video_header_frame, text="", width=200, height=112, fg_color="#030712", corner_radius=8)
        self.thumb_lbl.pack(side="left", padx=(0, 16))

        self.meta_frame = ctk.CTkFrame(self.video_header_frame, fg_color="transparent")
        self.meta_frame.pack(side="left", fill="both", expand=True)

        self.video_title_lbl = ctk.CTkLabel(
            self.meta_frame,
            text="Video Title",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ffffff",
            wraplength=580,
            justify="left"
        )
        self.video_title_lbl.pack(anchor="w", pady=(0, 4))

        self.video_sub_lbl = ctk.CTkLabel(
            self.meta_frame,
            text="Channel • Views • Duration",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.video_sub_lbl.pack(anchor="w", pady=(0, 10))

        self.quick_dl_btn = ctk.CTkButton(
            self.meta_frame,
            text="⚡ Download Highest Quality (Best MP4)",
            height=34,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c"
        )
        self.quick_dl_btn.pack(anchor="w")

        # Tabs for Formats
        self.tab_view = ctk.CTkTabview(self.video_details_frame, fg_color="#0b0f19")
        self.tab_view.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.tab_video = self.tab_view.add("🎬 Video (All Resolutions & 60 FPS)")
        self.tab_audio = self.tab_view.add("🎵 Audio Only (MP3 320k / M4A)")

        self.video_rows_frame = ctk.CTkFrame(self.tab_video, fg_color="transparent")
        self.video_rows_frame.pack(fill="both", expand=True, padx=4, pady=4)

        self.audio_rows_frame = ctk.CTkFrame(self.tab_audio, fg_color="transparent")
        self.audio_rows_frame.pack(fill="both", expand=True, padx=4, pady=4)

        return container

    # ==========================================
    # TAB 2: LINK GRABBER & BULK DOWNLOADER
    # ==========================================
    def _build_link_grabber_frame(self):
        container = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")

        card = ctk.CTkFrame(container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")
        card.pack(fill="x", padx=16, pady=16, ipady=8)

        ctk.CTkLabel(
            card,
            text="🧲  Link Grabber & Bulk Downloader",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            card,
            text="Paste multiple URLs (or a block of text containing links) for games, zip files, mods, and videos:",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # Text area for bulk URLs
        self.bulk_text = ctk.CTkTextbox(
            card,
            height=130,
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color="#030712",
            border_color="#374151",
            border_width=1
        )
        self.bulk_text.pack(fill="x", padx=16, pady=(0, 10))
        self.bulk_text.insert("1.0", "# Paste multiple links here (one per line or inside text):\nhttps://www.youtube.com/watch?v=dQw4w9WgXcQ\nhttps://www.youtube.com/watch?v=jNQXAC9IVRw\n")

        # Action Buttons
        btn_row = ctk.CTkFrame(card, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(0, 8))

        grab_btn = ctk.CTkButton(
            btn_row,
            text="🔍 Analyze & Grab Links",
            width=170,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#dc2626",
            hover_color="#b91c1c",
            command=self.parse_and_grab_links
        )
        grab_btn.pack(side="left", padx=(0, 10))

        clear_btn = ctk.CTkButton(
            btn_row,
            text="Clear Text",
            width=100,
            height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#1f2937",
            hover_color="#374151",
            command=lambda: self.bulk_text.delete("1.0", "end")
        )
        clear_btn.pack(side="left")

        self.grabber_status_lbl = ctk.CTkLabel(
            card,
            text="Ready to grab links.",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        )
        self.grabber_status_lbl.pack(anchor="w", padx=16, pady=(4, 2))

        # Grabbed Links Table Frame
        self.grabbed_table_card = ctk.CTkFrame(container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")
        self.grabbed_table_card.pack(fill="both", expand=True, padx=16, pady=(0, 20))

        tbl_header = ctk.CTkFrame(self.grabbed_table_card, fg_color="transparent")
        tbl_header.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            tbl_header,
            text="Grabbed Links Package",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff"
        ).pack(side="left")

        self.start_all_btn = ctk.CTkButton(
            tbl_header,
            text="⬇ Download All Items",
            width=160,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            command=self.start_all_grabbed_downloads
        )
        self.start_all_btn.pack(side="right", padx=(8, 0))

        self.open_all_btn = ctk.CTkButton(
            tbl_header,
            text="🌐 Open All in Browser",
            width=150,
            height=32,
            font=ctk.CTkFont(size=12),
            fg_color="#1f2937",
            hover_color="#374151",
            command=self.open_all_grabbed_in_browser
        )
        self.open_all_btn.pack(side="right")

        self.grabbed_items_frame = ctk.CTkFrame(self.grabbed_table_card, fg_color="transparent")
        self.grabbed_items_frame.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        return container

    # ==========================================
    # TAB 3: SETTINGS & PRIVACY
    # ==========================================
    def _build_settings_frame(self):
        container = ctk.CTkScrollableFrame(self.content_area, fg_color="transparent")

        # 1. Download Destination Card
        folder_card = ctk.CTkFrame(container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")
        folder_card.pack(fill="x", padx=16, pady=(14, 14), ipady=8)

        ctk.CTkLabel(
            folder_card,
            text="📂  Download Destination Directory",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            folder_card,
            text="Choose where all videos, audio files, and grabbed games/archives are saved:",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=16, pady=(0, 8))

        dest_row = ctk.CTkFrame(folder_card, fg_color="transparent")
        dest_row.pack(fill="x", padx=16, pady=(0, 8))

        self.dest_entry = ctk.CTkEntry(
            dest_row,
            height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#030712",
            border_color="#374151"
        )
        self.dest_entry.insert(0, self.download_destination)
        self.dest_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        browse_dest_btn = ctk.CTkButton(
            dest_row,
            text="Browse...",
            width=100,
            height=36,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#1f2937",
            hover_color="#374151",
            command=self.choose_download_directory
        )
        browse_dest_btn.pack(side="left")

        # 2. Authentication & Cookie Settings Card
        auth_card = ctk.CTkFrame(container, fg_color="#111827", corner_radius=12, border_width=1, border_color="#1f2937")
        auth_card.pack(fill="x", padx=16, pady=(0, 14), ipady=8)

        ctk.CTkLabel(
            auth_card,
            text="🔒  YouTube Authentication & Anti-Bot Bypass",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#ffffff"
        ).pack(anchor="w", padx=16, pady=(10, 2))

        ctk.CTkLabel(
            auth_card,
            text="Configure how age-restricted, private, or bot-blocked videos are handled:",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8"
        ).pack(anchor="w", padx=16, pady=(0, 10))

        self.auth_mode_var = ctk.StringVar(value="none")

        # Option 1: Safe Mode
        opt1_frame = ctk.CTkFrame(auth_card, fg_color="#030712", corner_radius=8)
        opt1_frame.pack(fill="x", padx=16, pady=4, ipady=4)

        ctk.CTkRadioButton(
            opt1_frame,
            text="Safe Mode (Anonymous, Zero Browser Access)",
            variable=self.auth_mode_var,
            value="none",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#34d399",
            fg_color="#10b981"
        ).pack(anchor="w", padx=12, pady=(6, 2))

        ctk.CTkLabel(
            opt1_frame,
            text="Recommended for privacy. Does not touch or inspect any browser files on your computer.",
            font=ctk.CTkFont(size=11),
            text_color="#64748b"
        ).pack(anchor="w", padx=36, pady=(0, 6))

        # Option 2: Browser Session
        opt2_frame = ctk.CTkFrame(auth_card, fg_color="#030712", corner_radius=8)
        opt2_frame.pack(fill="x", padx=16, pady=4, ipady=4)

        opt2_row = ctk.CTkFrame(opt2_frame, fg_color="transparent")
        opt2_row.pack(fill="x", padx=12, pady=(6, 2))

        ctk.CTkRadioButton(
            opt2_row,
            text="Use Local Browser Session:",
            variable=self.auth_mode_var,
            value="browser",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e2e8f0",
            fg_color="#ef4444"
        ).pack(side="left", padx=(0, 12))

        self.browser_dropdown = ctk.CTkComboBox(
            opt2_row,
            values=["Opera GX", "Microsoft Edge", "Google Chrome", "Mozilla Firefox"],
            width=160,
            height=30,
            font=ctk.CTkFont(size=11)
        )
        self.browser_dropdown.set("Opera GX")
        self.browser_dropdown.pack(side="left")

        ctk.CTkLabel(
            opt2_frame,
            text="Runs 100% locally on your PC to authenticate age-restricted or anti-bot checked videos.",
            font=ctk.CTkFont(size=11),
            text_color="#64748b"
        ).pack(anchor="w", padx=36, pady=(0, 6))

        # Option 3: Upload cookies.txt
        opt3_frame = ctk.CTkFrame(auth_card, fg_color="#030712", corner_radius=8)
        opt3_frame.pack(fill="x", padx=16, pady=4, ipady=4)

        opt3_row = ctk.CTkFrame(opt3_frame, fg_color="transparent")
        opt3_row.pack(fill="x", padx=12, pady=(6, 2))

        ctk.CTkRadioButton(
            opt3_row,
            text="Load Custom cookies.txt File:",
            variable=self.auth_mode_var,
            value="file",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e2e8f0",
            fg_color="#ef4444"
        ).pack(side="left", padx=(0, 12))

        self.cookie_browse_btn = ctk.CTkButton(
            opt3_row,
            text="Select File...",
            width=120,
            height=28,
            font=ctk.CTkFont(size=11),
            fg_color="#1f2937",
            hover_color="#374151",
            command=self.select_cookie_file
        )
        self.cookie_browse_btn.pack(side="left")

        self.cookie_path_lbl = ctk.CTkLabel(
            opt3_frame,
            text="No cookie file selected.",
            font=ctk.CTkFont(size=11),
            text_color="#64748b"
        )
        self.cookie_path_lbl.pack(anchor="w", padx=36, pady=(0, 6))

        return container

    # ==========================================
    # LOGIC: SETTINGS & DIRECTORY
    # ==========================================
    def choose_download_directory(self):
        folder = filedialog.askdirectory(title="Choose Downloads Folder", initialdir=self.download_destination)
        if folder:
            self.download_destination = folder
            self.dest_entry.delete(0, "end")
            self.dest_entry.insert(0, folder)
            ytdlp_service.DOWNLOADS_DIR = folder

    def select_cookie_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Exported cookies.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.custom_cookie_file = file_path
            self.auth_mode_var.set("file")
            fname = os.path.basename(file_path)
            self.cookie_browse_btn.configure(text="Loaded: " + fname[:10])
            self.cookie_path_lbl.configure(text=f"Selected: {file_path}", text_color="#34d399")

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

    def open_downloads_folder(self):
        try:
            os.startfile(self.download_destination)
        except Exception as e:
            pass

    # ==========================================
    # LOGIC: SINGLE VIDEO DOWNLOADER
    # ==========================================
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

    def fetch_video_info(self):
        url = self.url_entry.get().strip()
        if not url:
            self.status_lbl.configure(text="Please enter or paste a valid YouTube URL.", text_color="#f87171")
            return

        self.fetch_btn.configure(state="disabled", text="Analyzing...")
        self.status_lbl.configure(text="Extracting video formats, 60 FPS options, and audio streams...", text_color="#fbbf24")

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
            self.status_lbl.configure(text="YouTube anti-bot check triggered. Switch to 'Browser Session' (e.g. Opera GX) in Settings.", text_color="#f87171")
        else:
            self.status_lbl.configure(text=f"Error: {err_msg[:120]}", text_color="#f87171")

    def _on_info_fetched(self, data):
        self.fetch_btn.configure(state="normal", text="🔍 Fetch Qualities")
        self.status_lbl.configure(text=f"✓ Found {data.get('total_video_options', 0)} video quality and FPS options!", text_color="#34d399")
        self.current_video_data = data

        self.video_details_frame.pack(fill="both", expand=True, padx=16, pady=(0, 20))

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

            # Resolution Badge with color hierarchy
            h = f.get('height', 0)
            badge_bg = "#451a03" if h >= 2160 else ("#312e81" if h >= 1440 else ("#1e3a8a" if h >= 1080 else "#1e293b"))
            badge_txt = "#fbbf24" if h >= 2160 else ("#a5b4fc" if h >= 1440 else ("#93c5fd" if h >= 1080 else "#cbd5e1"))

            res_badge = ctk.CTkLabel(
                row,
                text=f" {f.get('height')}p ",
                font=ctk.CTkFont(size=12, weight="bold"),
                fg_color=badge_bg,
                text_color=badge_txt,
                corner_radius=6,
                width=65
            )
            res_badge.pack(side="left", padx=(10, 8), pady=8)

            # FPS Badge
            fps = f.get('fps', 30)
            fps_color = "#34d399" if fps >= 50 else "#94a3b8"
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

    # ==========================================
    # LOGIC: LINK GRABBER (BULK / GAMES / ZIP)
    # ==========================================
    def parse_and_grab_links(self):
        text = self.bulk_text.get("1.0", "end")
        raw_urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', text)
        raw_urls = list(dict.fromkeys(raw_urls))

        if not raw_urls:
            self.grabber_status_lbl.configure(text="No valid URLs found in text.", text_color="#f87171")
            return

        self.grabber_status_lbl.configure(text=f"Analyzing {len(raw_urls)} links & unpacking paste containers...", text_color="#fbbf24")
        threading.Thread(target=self._inspect_links_worker, args=(raw_urls,), daemon=True).start()

    def _inspect_links_worker(self, raw_urls):
        expanded_urls = []
        for u in raw_urls:
            # Check if this is a PrivateBin / FitGirl paste URL
            if "paste" in u or ("?" in u and "#" in u):
                unpacked = ytdlp_service.unpack_paste_urls(u)
                if unpacked and len(unpacked) > 1:
                    expanded_urls.extend(unpacked)
                    continue
            expanded_urls.append(u)

        expanded_urls = list(dict.fromkeys(expanded_urls))
        self.grabbed_links = []

        for u in expanded_urls:
            is_yt = "youtube.com" in u or "youtu.be" in u
            name = u
            size_str = "Checking..."

            # Extract clean filename from URL fragment (e.g. #Way_of_the_Hunter_...part01.rar)
            parsed_u = urllib.parse.urlparse(u)
            if parsed_u.fragment:
                name = urllib.parse.unquote(parsed_u.fragment)
            else:
                p_name = os.path.basename(parsed_u.path)
                if p_name and len(p_name) > 3:
                    name = urllib.parse.unquote(p_name)

            lower_name = name.lower()
            if is_yt:
                name = "YouTube Video Stream"
                size_str = "Adaptive"
                item_type = "🎬 Video"
            elif ".part" in lower_name and ".rar" in lower_name or lower_name.endswith(".rar"):
                item_type = "🧩 RAR Part"
            elif lower_name.endswith((".zip", ".7z", ".tar", ".gz")):
                item_type = "📦 Archive"
            elif lower_name.endswith((".iso", ".bin")):
                item_type = "💿 Disc ISO"
            elif lower_name.endswith((".exe", ".msi")):
                item_type = "💻 Installer"
            else:
                item_type = "📁 File / Host"

            if not is_yt and size_str == "Checking...":
                try:
                    req = urllib.request.Request(u, method="HEAD", headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=3) as resp:
                        cl = resp.headers.get('Content-Length')
                        cd = resp.headers.get('Content-Disposition')
                        if cd and 'filename=' in cd:
                            found = re.findall(r'filename="?([^";]+)"?', cd)
                            if found:
                                name = found[0]
                        if cl and cl.isdigit():
                            size_str = ytdlp_service.format_bytes(int(cl))
                        else:
                            size_str = "Direct Stream"
                except Exception:
                    size_str = "File Host"

            self.grabbed_links.append({
                'url': u,
                'name': name,
                'type': item_type,
                'size_str': size_str,
                'status': 'Ready',
                'task_id': None
            })

        self.after(0, self._render_grabbed_items)

    def _render_grabbed_items(self):
        for widget in self.grabbed_items_frame.winfo_children():
            widget.destroy()

        count = len(self.grabbed_links)
        self.grabber_status_lbl.configure(
            text=f"✓ Grabbed {count} items! You can download individual files or start the whole batch.",
            text_color="#34d399"
        )

        for idx, item in enumerate(self.grabbed_links):
            row = ctk.CTkFrame(self.grabbed_items_frame, fg_color="#030712", corner_radius=8, height=48)
            row.pack(fill="x", pady=2)
            row.pack_propagate(False)

            # Badge
            badge_color = "#38bdf8" if "Video" in item['type'] else ("#a78bfa" if "RAR" in item['type'] else "#34d399")
            ctk.CTkLabel(
                row,
                text=f"{item['type']}",
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#1e293b",
                text_color=badge_color,
                corner_radius=4,
                width=100
            ).pack(side="left", padx=(10, 8), pady=8)

            # File name
            name_display = item['name']
            if len(name_display) > 52:
                name_display = name_display[:50] + "..."
            ctk.CTkLabel(
                row,
                text=name_display,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#ffffff",
                anchor="w"
            ).pack(side="left", padx=(0, 10))

            # File size
            ctk.CTkLabel(
                row,
                text=f"Size: {item['size_str']}",
                font=ctk.CTkFont(size=11),
                text_color="#94a3b8"
            ).pack(side="left", padx=(0, 10))

            # Status label
            item_status = ctk.CTkLabel(
                row,
                text=item['status'],
                font=ctk.CTkFont(size=11),
                text_color="#34d399" if item['status'] == 'Completed' else ("#f87171" if 'Fail' in item['status'] else "#f59e0b")
            )
            item_status.pack(side="right", padx=(8, 12))
            item['status_lbl'] = item_status

            # Individual Download Button
            dl_btn = ctk.CTkButton(
                row,
                text="⬇ Download",
                width=100,
                height=28,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color="#dc2626",
                hover_color="#b91c1c",
                command=lambda i=idx: self.start_individual_grabbed_download(i)
            )
            dl_btn.pack(side="right", padx=(4, 6))
            item['dl_btn'] = dl_btn

            # Browser Open Button (handles Cloudflare/Turnstile hosts seamlessly)
            br_btn = ctk.CTkButton(
                row,
                text="🌐 Open",
                width=65,
                height=28,
                font=ctk.CTkFont(size=11),
                fg_color="#1f2937",
                hover_color="#374151",
                command=lambda u=item['url']: webbrowser.open(u)
            )
            br_btn.pack(side="right", padx=(4, 4))

    def open_all_grabbed_in_browser(self):
        if not self.grabbed_links:
            return
        for item in self.grabbed_links:
            try:
                webbrowser.open(item['url'])
                time.sleep(0.15)
            except Exception:
                pass

    def start_individual_grabbed_download(self, item_index):
        if item_index >= len(self.grabbed_links):
            return
        item = self.grabbed_links[item_index]
        u = item['url']
        is_yt = "youtube.com" in u or "youtu.be" in u

        # Show bottom dock
        self.active_download_url = u
        self.dock_browser_btn.pack_forget()
        self.bottom_dock.grid(row=1, column=1, sticky="ew", padx=16, pady=(4, 14))
        self.dock_title_lbl.configure(text=f"Downloading: {item['name'][:45]}")
        self.dock_status_lbl.configure(text="Connecting to download stream...")
        self.dock_percent_lbl.configure(text="0%")
        self.dock_progress.set(0.0)
        self.dock_cancel_btn.configure(text="✕ Cancel", state="normal")

        if 'dl_btn' in item and item['dl_btn']:
            item['dl_btn'].configure(text="Downloading...", state="disabled", fg_color="#78350f")

        if is_yt:
            t_id = ytdlp_service.start_download_task(
                url=u,
                download_type="video",
                format_id="best",
                auth_config=self._get_auth_config(),
                quality_label="Grabbed Video"
            )
        else:
            t_id = ytdlp_service.start_direct_download_task(
                url=u,
                destination_dir=self.download_destination,
                custom_filename=item['name'],
                quality_label="Grabbed File"
            )

        self.active_task_id = t_id
        self.tracking_active = True

        def monitor_worker():
            while self.tracking_active:
                t = ytdlp_service.get_task_status(t_id)
                if not t:
                    break
                st = t.get('status')
                pct = t.get('progress', 0.0)
                speed = t.get('speed', '--')
                eta = t.get('eta', '--')

                self.after(0, lambda s=st, p=pct, sp=speed: self._update_item_status(item, s, p, sp))
                self.after(0, lambda p=pct/100.0, pi=int(pct), sp=speed, e=eta, s=st: self._update_dock_ui(p, pi, sp, e, s))

                if st in ['completed', 'error', 'cancelled']:
                    self.tracking_active = False
                    if st == 'completed':
                        item['status'] = 'Completed'
                        self.after(0, lambda it=item: self._on_item_download_success(it))
                    elif st == 'error':
                        err = t.get('error', 'Error')
                        item['status'] = 'Failed'
                        self.after(0, lambda it=item, er=err: self._on_item_download_error(it, er))
                    break
                time.sleep(0.5)

        threading.Thread(target=monitor_worker, daemon=True).start()

    def start_all_grabbed_downloads(self):
        if not self.grabbed_links:
            return

        self.start_all_btn.configure(state="disabled", text="Downloading Batch...")
        # Note: Do NOT call self.select_tab("single") -- Stay on Link Grabber!
        self.bottom_dock.grid(row=1, column=1, sticky="ew", padx=16, pady=(4, 14))

        def batch_worker():
            total = len(self.grabbed_links)
            for idx, item in enumerate(self.grabbed_links):
                if item.get('status') == 'Completed':
                    continue

                u = item['url']
                is_yt = "youtube.com" in u or "youtu.be" in u

                self.after(0, lambda i=idx+1, tot=total, n=item['name']: (
                    self.start_all_btn.configure(text=f"Batch: {i}/{tot}"),
                    self.dock_title_lbl.configure(text=f"[{i}/{tot}] {n[:45]}")
                ))

                if is_yt:
                    t_id = ytdlp_service.start_download_task(
                        url=u,
                        download_type="video",
                        format_id="best",
                        auth_config=self._get_auth_config(),
                        quality_label=f"Batch {idx+1}/{total}"
                    )
                else:
                    t_id = ytdlp_service.start_direct_download_task(
                        url=u,
                        destination_dir=self.download_destination,
                        custom_filename=item['name'],
                        quality_label=f"Batch {idx+1}/{total}"
                    )

                self.active_task_id = t_id
                self.tracking_active = True

                while True:
                    t = ytdlp_service.get_task_status(t_id)
                    if not t:
                        break
                    st = t.get('status')
                    pct = t.get('progress', 0.0)
                    speed = t.get('speed', '--')
                    eta = t.get('eta', '--')

                    self.after(0, lambda s=st, p=pct, sp=speed, it=item: self._update_item_status(it, s, p, sp))
                    self.after(0, lambda p=pct/100.0, pi=int(pct), sp=speed, e=eta, s=st: self._update_dock_ui(p, pi, sp, e, s))

                    if st in ['completed', 'error', 'cancelled']:
                        if st == 'completed':
                            item['status'] = 'Completed'
                            self.after(0, lambda it=item: self._on_item_download_success(it))
                        elif st == 'error':
                            err = t.get('error', 'Error')
                            item['status'] = 'Failed'
                            self.after(0, lambda it=item, er=err: self._on_item_download_error(it, er))
                        break
                    time.sleep(0.5)

            self.after(0, lambda: self.start_all_btn.configure(state="normal", text="⬇ Download All Items"))
            self.after(0, self.open_downloads_folder)

        threading.Thread(target=batch_worker, daemon=True).start()

    def _update_item_status(self, item, status, pct, speed):
        lbl = item.get('status_lbl')
        if lbl:
            if status == 'downloading':
                lbl.configure(text=f"{int(pct)}% ({speed})", text_color="#38bdf8")
            elif status == 'completed':
                lbl.configure(text="✓ Done", text_color="#34d399")
            elif status == 'error':
                lbl.configure(text="Failed", text_color="#f87171")

    def _on_item_download_success(self, item):
        if 'dl_btn' in item and item['dl_btn']:
            item['dl_btn'].configure(text="✓ Done", state="disabled", fg_color="#064e3b")
        if 'status_lbl' in item and item['status_lbl']:
            item['status_lbl'].configure(text="✓ Saved", text_color="#34d399")
        self.dock_status_lbl.configure(text=f"✓ Downloaded: {item['name'][:40]}")

    def _on_item_download_error(self, item, err):
        is_cf = "403" in err or "Cloudflare" in err
        self.active_download_url = item.get('url')
        if 'status_lbl' in item and item['status_lbl']:
            if is_cf:
                item['status_lbl'].configure(text="Cloudflare Protected", text_color="#f87171")
            else:
                item['status_lbl'].configure(text=f"Failed: {err[:20]}", text_color="#f87171")
        if 'dl_btn' in item and item['dl_btn']:
            if is_cf:
                item['dl_btn'].configure(
                    text="🌐 Browser DL",
                    state="normal",
                    fg_color="#b45309",
                    command=lambda u=item['url']: webbrowser.open(u)
                )
            else:
                item['dl_btn'].configure(text="Retry", state="normal", fg_color="#1f2937")

        if is_cf:
            self.dock_status_lbl.configure(text="Cloudflare Turnstile verification required. Click 'Open in Browser' to download.")
            self.dock_browser_btn.pack(side="right", padx=(0, 8))
        else:
            self.dock_browser_btn.pack_forget()
            self.dock_status_lbl.configure(text=f"Error: {err}")

    # ==========================================
    # LOGIC: DOWNLOAD EXECUTION & PROGRESS
    # ==========================================
    def start_download(self, url, dl_type, format_id, ext, quality_label, format_key, btn=None):
        if self.format_states.get(format_key) == 'downloading':
            self.status_lbl.configure(text="This quality is already downloading! See active progress bar below.", text_color="#fbbf24")
            return

        if btn:
            btn.configure(text="Downloading...", state="disabled", fg_color="#78350f")

        self.format_states[format_key] = 'downloading'
        self.active_format_key = format_key

        # Show bottom dock
        self.bottom_dock.grid(row=1, column=1, sticky="ew", padx=16, pady=(4, 14))
        title = self.current_video_data.get('title', 'Video') if self.current_video_data else 'Media'
        self.dock_title_lbl.configure(text=f"Downloading: {title[:50]}... [{quality_label}]")
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

            self.after(3000, lambda: self.bottom_dock.grid_forget())

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

            self.after(0, lambda p=pct, pi=pct_int, s=speed, e=eta, st=status: self._update_dock_ui(p, pi, s, e, st))

            if status == 'completed':
                self.after(0, lambda: self._on_download_complete(format_key, btn))
                break
            elif status in ['error', 'cancelled']:
                self.after(0, lambda err=task.get('error', 'Failed'): self._on_download_error(format_key, btn, err))
                break

            time.sleep(0.5)

    def _update_dock_ui(self, pct, pct_int, speed, eta, status):
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
        self.status_lbl.configure(text="✓ Download complete! File saved in downloads folder.", text_color="#34d399")

        if btn:
            btn.configure(text="✓ Downloaded", state="normal", fg_color="#064e3b")

        self.open_downloads_folder()

    def _on_download_error(self, format_key, btn, err):
        self.tracking_active = False
        self.format_states[format_key] = 'idle'
        self.dock_status_lbl.configure(text=f"Error: {err}")
        self.status_lbl.configure(text=f"Download failed: {err}", text_color="#f87171")

        if btn:
            btn.configure(text="⬇ Download MP4", state="normal", fg_color="#1f2937")

if __name__ == "__main__":
    try:
        app = ModernYouTubeDownloader()
        app.mainloop()
    except Exception as e:
        with open(os.path.join(APP_DIR, "crash_log.txt"), "w") as f:
            import traceback
            traceback.print_exc(file=f)
