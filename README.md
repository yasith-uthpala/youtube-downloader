# 🎬 YouTube Downloader Pro

A modern, fast, and feature-rich YouTube Video & Audio Downloader available as both a **100% Native Desktop Software GUI** and a **Web Application**.

Built with **Python**, **CustomTkinter**, **yt-dlp**, and **FFmpeg**.

---

## ✨ Features

- **📺 All Resolutions Supported:**
  - 8K Ultra HD (4320p)
  - 4K Ultra HD (2160p)
  - 2K Quad HD (1440p)
  - 1080p Full HD
  - 720p HD, 480p, 360p, 240p, 144p
- **⚡ High Framerate (FPS) Detection:**
  - Automatically identifies and highlights **60 FPS** and **50 FPS** streams with dedicated badges.
  - Standard 30 FPS / 24 FPS streams also available.
- **🔊 Automatic Video & Audio Merging:**
  - YouTube serves 1080p, 4K, and 8K videos as separate adaptive video and audio streams. This software uses **FFmpeg** to merge them into complete, high-quality **MP4** files automatically.
- **🎵 Studio Audio Extraction:**
  - **MP3 (High Quality 320kbps)**: Universally compatible with all devices, phones, and car audio systems.
  - **M4A (Original AAC Quality)**: Original studio audio track directly from YouTube with zero quality loss.
- **🛡️ Privacy-First Authentication & Anti-Bot Bypass:**
  - **Safe Anonymous Mode (Default)**: Zero browser access, no personal data touched. 95%+ of videos download anonymously.
  - **Optional Browser Session**: Optional 1-click bypass for age-restricted or private videos using your local browser cookies (**Opera GX**, **Microsoft Edge**, **Google Chrome**, **Mozilla Firefox**).
  - **Custom cookies.txt Upload**: Supports manual export files.
- **⏱️ Real-Time Download Tracking & Cancellation:**
  - Live progress bar (`0%` to `100%`).
  - Real-time download speed (`MB/s`) and remaining `ETA`.
  - **Explicit `✕ Cancel` Button**: Stops downloading immediately and clears partial files to save disk space.
  - **Duplicate Download Prevention**: Buttons disable during active download to prevent accidental double-clicks.
- **📁 One-Click "Open Downloads Folder":**
  - Quickly opens your local download destination in Windows File Explorer.

---

## 🖥️ Two Ways to Run

### Option 1: Native Desktop Software (Recommended)
Runs directly as a pure Windows software window (no browser required, no `127.0.0.1`, no connection errors):

* **Double-click:** `YouTube Downloader (Desktop App).vbs` or `Launch Desktop App.bat`
* **Or via Terminal:**
  ```powershell
  python gui_app.py
  ```

### Option 2: Web Browser Interface
Runs as a local FastAPI web application with a modern Tailwind CSS glassmorphic interface:

* **Double-click:** `run.bat`
* **Or via Terminal:**
  ```powershell
  python app.py
  ```
  Then visit: `http://localhost:8000`

---

## 🚀 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yasith-uthpala/youtube-downloader.git
   cd youtube-downloader
   ```

2. **Install required dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch the app:**
   ```bash
   python gui_app.py
   ```

---

## 📦 Packaging as a Standalone `.exe` (Optional)

You can compile the entire application into a standalone Windows `.exe` that runs on any PC without installing Python:

```bash
python -m PyInstaller --noconsole --onedir --add-data "bin;bin" --collect-all "customtkinter" --name "YouTubeDownloaderPro" gui_app.py --noconfirm
```

The compiled standalone executable will be located in:
`dist/YouTubeDownloaderPro/YouTubeDownloaderPro.exe`

---

## 🔒 Security & Privacy

* This repository does **NOT** track, store, or upload any user cookies or downloaded files (`cookies/` and `downloads/` folders are blocked via `.gitignore`).
* All video downloading and audio processing happens **100% locally** on your computer.

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
