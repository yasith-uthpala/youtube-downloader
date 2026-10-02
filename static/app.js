// YouTube Downloader Frontend Logic v1.1.0

let currentVideoData = null;
let activeTasks = {}; // taskId -> { intervalId, formatKey, title, ext }
let formatStates = {}; // formatKey -> { status: 'idle'|'downloading'|'completed', taskId }
let currentFloatingTaskId = null;

document.addEventListener('DOMContentLoaded', () => {
  lucide.createIcons();
  initAuthSettings();
  initEventListeners();
  initFloatingBarEvents();
});

// Toast notification helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  const colors = {
    info: 'bg-gray-900 border-gray-700 text-white',
    success: 'bg-emerald-950 border-emerald-700 text-emerald-200',
    warning: 'bg-amber-950 border-amber-700 text-amber-200',
    error: 'bg-red-950 border-red-700 text-red-200'
  };
  
  toast.className = `pointer-events-auto px-4 py-2.5 rounded-xl border shadow-xl text-xs font-medium flex items-center gap-2 transform transition-all duration-300 translate-y-2 opacity-0 ${colors[type] || colors.info}`;
  toast.innerHTML = `
    <span>${escapeHtml(message)}</span>
  `;

  container.appendChild(toast);
  requestAnimationFrame(() => {
    toast.classList.remove('translate-y-2', 'opacity-0');
  });

  setTimeout(() => {
    toast.classList.add('opacity-0', 'translate-y-2');
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Auth Settings Handling (Safe Mode is default)
function initAuthSettings() {
  const toggleAuthBtn = document.getElementById('toggleAuthBtn');
  const authSettingsPanel = document.getElementById('authSettingsPanel');
  const browserSelect = document.getElementById('browserSelect');
  const cookieFileInput = document.getElementById('cookieFileInput');
  const cookieUploadStatus = document.getElementById('cookieUploadStatus');

  toggleAuthBtn.addEventListener('click', () => {
    authSettingsPanel.classList.toggle('hidden');
  });

  document.querySelectorAll('input[name="authMode"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
      if (e.target.value === 'browser') {
        showToast("Browser cookies mode enabled. Runs 100% locally on your machine.", 'warning');
      } else if (e.target.value === 'none') {
        showToast("Safe Anonymous Mode enabled. Zero browser access.", 'success');
      }
    });
  });

  cookieFileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    cookieUploadStatus.textContent = "Uploading cookies...";
    cookieUploadStatus.className = "text-[10px] text-yellow-400 mt-1";

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload-cookies', {
        method: 'POST',
        body: formData
      });
      if (res.ok) {
        cookieUploadStatus.textContent = `✓ Uploaded: ${file.name}`;
        cookieUploadStatus.className = "text-[10px] text-emerald-400 font-semibold mt-1";
        document.querySelector('input[name="authMode"][value="file"]').checked = true;
        showToast("Cookies file loaded successfully.", 'success');
      } else {
        cookieUploadStatus.textContent = "Failed to upload cookies.";
        cookieUploadStatus.className = "text-[10px] text-red-400 mt-1";
      }
    } catch (err) {
      cookieUploadStatus.textContent = "Error uploading cookie file.";
      cookieUploadStatus.className = "text-[10px] text-red-400 mt-1";
    }
  });
}

function getSelectedAuth() {
  const modeRadio = document.querySelector('input[name="authMode"]:checked');
  const mode = modeRadio ? modeRadio.value : 'none';
  const browser = document.getElementById('browserSelect').value;
  return {
    auth_mode: mode,
    browser: browser
  };
}

// Event Listeners
function initEventListeners() {
  const urlInput = document.getElementById('urlInput');
  const fetchBtn = document.getElementById('fetchBtn');
  const pasteBtn = document.getElementById('pasteBtn');
  const openFolderBtn = document.getElementById('openFolderBtn');
  const dismissErrorBtn = document.getElementById('dismissErrorBtn');
  const tabVideo = document.getElementById('tabVideo');
  const tabAudio = document.getElementById('tabAudio');
  const videoFormatsTab = document.getElementById('videoFormatsTab');
  const audioFormatsTab = document.getElementById('audioFormatsTab');
  const headerDownloadsBtn = document.getElementById('headerDownloadsBtn');

  headerDownloadsBtn.addEventListener('click', () => {
    const dlSection = document.getElementById('activeDownloadsContainer');
    dlSection.classList.remove('hidden');
    dlSection.scrollIntoView({ behavior: 'smooth' });
  });

  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        fetchVideoInfo();
      }
    } catch (e) {
      urlInput.focus();
    }
  });

  urlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      fetchVideoInfo();
    }
  });

  fetchBtn.addEventListener('click', fetchVideoInfo);

  document.querySelectorAll('.sample-link').forEach(link => {
    link.addEventListener('click', () => {
      urlInput.value = link.getAttribute('data-url');
      fetchVideoInfo();
    });
  });

  openFolderBtn.addEventListener('click', async () => {
    try {
      await fetch('/api/open-folder', { method: 'POST' });
      showToast("Opened Downloads folder in File Explorer", 'info');
    } catch (e) {
      console.error(e);
    }
  });

  dismissErrorBtn.addEventListener('click', () => {
    document.getElementById('errorAlert').classList.add('hidden');
  });

  tabVideo.addEventListener('click', () => {
    tabVideo.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-red-600/20 text-red-400 border border-red-500/30 flex items-center gap-1.5 transition";
    tabAudio.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-800/60 text-gray-400 hover:text-gray-200 border border-gray-700/50 flex items-center gap-1.5 transition";
    videoFormatsTab.classList.remove('hidden');
    audioFormatsTab.classList.add('hidden');
  });

  tabAudio.addEventListener('click', () => {
    tabAudio.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-red-600/20 text-red-400 border border-red-500/30 flex items-center gap-1.5 transition";
    tabVideo.className = "px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-gray-800/60 text-gray-400 hover:text-gray-200 border border-gray-700/50 flex items-center gap-1.5 transition";
    audioFormatsTab.classList.remove('hidden');
    videoFormatsTab.classList.add('hidden');
  });
}

function initFloatingBarEvents() {
  const dismissBtn = document.getElementById('floatingDismissBtn');
  const cancelBtn = document.getElementById('floatingCancelBtn');

  dismissBtn.addEventListener('click', () => {
    document.getElementById('floatingDownloadBar').classList.add('hidden');
  });

  cancelBtn.addEventListener('click', () => {
    if (currentFloatingTaskId) {
      cancelDownload(currentFloatingTaskId);
    }
  });
}

// Fetch Video Info & Formats
async function fetchVideoInfo() {
  const urlInput = document.getElementById('urlInput');
  const fetchBtn = document.getElementById('fetchBtn');
  const loadingState = document.getElementById('loadingState');
  const errorAlert = document.getElementById('errorAlert');
  const videoDetailsCard = document.getElementById('videoDetailsCard');

  const url = urlInput.value.trim();
  if (!url) {
    showError("Please enter or paste a valid YouTube URL.");
    return;
  }

  errorAlert.classList.add('hidden');
  videoDetailsCard.classList.add('hidden');
  loadingState.classList.remove('hidden');
  fetchBtn.disabled = true;

  const auth = getSelectedAuth();

  try {
    const res = await fetch('/api/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        auth_mode: auth.auth_mode,
        browser: auth.browser
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to fetch video information.");
    }

    currentVideoData = data;
    renderVideoDetails(data);
    loadingState.classList.add('hidden');
    videoDetailsCard.classList.remove('hidden');
    lucide.createIcons();

  } catch (err) {
    loadingState.classList.add('hidden');
    showError(err.message);
  } finally {
    fetchBtn.disabled = false;
  }
}

function showError(msg) {
  const errorAlert = document.getElementById('errorAlert');
  const errorMessage = document.getElementById('errorMessage');
  errorMessage.textContent = msg;
  errorAlert.classList.remove('hidden');
}

// Render Video Details
function renderVideoDetails(data) {
  document.getElementById('videoThumbnail').src = data.thumbnail || '';
  document.getElementById('videoDuration').textContent = data.duration_str || '00:00';
  document.getElementById('videoTitle').textContent = data.title || 'Unknown Title';
  document.getElementById('videoChannel').innerHTML = `<i data-lucide="user" class="w-3.5 h-3.5 text-gray-500"></i> ${escapeHtml(data.channel)}`;
  document.getElementById('videoViews').innerHTML = `<i data-lucide="eye" class="w-3.5 h-3.5 text-gray-500"></i> ${data.view_count} views`;
  document.getElementById('videoQualityCount').textContent = `${data.total_video_options} Qualities & FPS Options`;

  // Quick download button
  const quickBtn = document.getElementById('quickDownloadBtn');
  const quickText = document.getElementById('quickDownloadText');
  if (data.best_video) {
    const fpsBadge = data.best_video.fps ? `${data.best_video.fps}fps` : '';
    quickText.textContent = `Download Highest Quality: ${data.best_video.res_label} ${fpsBadge} (${data.best_video.filesize_str})`;
    quickBtn.onclick = () => handleDownloadRequest(data.url, 'video', data.best_video.format_id, 'mp4', `${data.title} (${data.best_video.res_label})`, `quick-${data.best_video.format_id}`, quickBtn);
  } else {
    quickText.textContent = `Download Best MP4`;
    quickBtn.onclick = () => handleDownloadRequest(data.url, 'video', 'best', 'mp4', data.title, 'quick-best', quickBtn);
  }

  renderVideoFormats(data.video_formats, data.url, data.title);
  renderAudioFormats(data.audio_formats, data.url, data.title);
}

function renderVideoFormats(formats, videoUrl, videoTitle) {
  const container = document.getElementById('videoFormatsList');
  container.innerHTML = '';

  if (!formats || formats.length === 0) {
    container.innerHTML = `<p class="text-xs text-gray-400 p-4 text-center">No video formats detected.</p>`;
    return;
  }

  formats.forEach(f => {
    const card = document.createElement('div');
    card.className = "flex items-center justify-between p-3.5 rounded-xl bg-gray-950/70 border border-gray-800/80 hover:border-gray-700 hover:bg-gray-950 transition duration-150";

    const formatKey = `video_${f.format_id}`;

    let fpsHtml = '';
    if (f.fps >= 60) {
      fpsHtml = `<span class="px-2 py-0.5 rounded-md text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center gap-1 badge-60fps">
        <i data-lucide="sparkles" class="w-3 h-3"></i> ${f.fps} FPS
      </span>`;
    } else if (f.fps >= 50) {
      fpsHtml = `<span class="px-2 py-0.5 rounded-md text-[11px] font-bold bg-teal-500/20 text-teal-400 border border-teal-500/30">
        ${f.fps} FPS
      </span>`;
    } else {
      fpsHtml = `<span class="px-2 py-0.5 rounded-md text-[11px] font-medium bg-gray-800 text-gray-300">
        ${f.fps} FPS
      </span>`;
    }

    let resBadgeClass = "bg-gray-800 text-gray-300 border-gray-700";
    if (f.height >= 2160) {
      resBadgeClass = "bg-amber-500/20 text-amber-400 border-amber-500/40 font-bold";
    } else if (f.height >= 1440) {
      resBadgeClass = "bg-indigo-500/20 text-indigo-400 border-indigo-500/40 font-bold";
    } else if (f.height >= 1080) {
      resBadgeClass = "bg-blue-500/20 text-blue-400 border-blue-500/40 font-bold";
    } else if (f.height >= 720) {
      resBadgeClass = "bg-purple-500/20 text-purple-400 border-purple-500/40 font-bold";
    }

    const state = formatStates[formatKey];
    let btnText = 'Download MP4';
    let btnDisabled = '';
    let btnClass = 'bg-gray-800 hover:bg-red-600 text-gray-200 hover:text-white border-gray-700 hover:border-red-500';

    if (state && state.status === 'downloading') {
      btnText = 'Downloading...';
      btnDisabled = 'disabled';
      btnClass = 'bg-yellow-950/60 text-yellow-300 border-yellow-700 cursor-not-allowed';
    } else if (state && state.status === 'completed') {
      btnText = '✓ Downloaded (Save Again)';
      btnClass = 'bg-emerald-950/60 text-emerald-300 border-emerald-700 hover:bg-emerald-900';
    }

    card.innerHTML = `
      <div class="flex items-center gap-3">
        <span class="px-2.5 py-1 rounded-lg text-xs border ${resBadgeClass} min-w-[70px] text-center">
          ${f.height}p
        </span>

        <div class="space-y-0.5">
          <div class="flex items-center gap-2">
            <span class="text-xs font-bold text-white">${f.res_label}</span>
            ${fpsHtml}
            ${f.dynamic_range === 'HDR' ? '<span class="px-1.5 py-0.2 rounded text-[10px] bg-yellow-500/20 text-yellow-300 font-bold border border-yellow-500/30">HDR</span>' : ''}
          </div>
          <div class="flex items-center gap-2 text-[11px] text-gray-400">
            <span>Codec: ${f.codec}</span>
            <span>•</span>
            <span class="text-gray-300 font-medium">Est. Size: ${f.filesize_str}</span>
            <span>•</span>
            <span class="text-emerald-400/90 flex items-center gap-1 font-medium">
              <i data-lucide="volume-2" class="w-3 h-3"></i> Audio Merged
            </span>
          </div>
        </div>
      </div>

      <button 
        id="btn-${formatKey}"
        class="dl-btn px-4 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 border transition duration-150 shadow-sm ${btnClass}"
        ${btnDisabled}
      >
        <i data-lucide="download" class="w-3.5 h-3.5"></i>
        <span id="btn-text-${formatKey}">${btnText}</span>
      </button>
    `;

    const btn = card.querySelector(`#btn-${formatKey}`);
    btn.addEventListener('click', () => {
      handleDownloadRequest(
        videoUrl, 
        'video', 
        f.format_id, 
        'mp4', 
        `${videoTitle} (${f.res_label} ${f.fps}fps)`,
        formatKey,
        btn,
        `${f.res_label} ${f.fps}fps`
      );
    });

    container.appendChild(card);
  });
}

function renderAudioFormats(formats, videoUrl, videoTitle) {
  const container = document.getElementById('audioFormatsList');
  container.innerHTML = '';

  const presets = [
    { id: "mp3_320", name: "MP3 Audio (High Quality 320kbps)", ext: "mp3", note: "Universally compatible with all devices and cars", format_id: "bestaudio" },
    { id: "m4a_orig", name: "M4A Audio (Original AAC Quality)", ext: "m4a", note: "Original AAC track from YouTube with zero quality loss", format_id: "bestaudio[ext=m4a]/bestaudio" },
  ];

  presets.forEach(p => {
    const formatKey = `audio_${p.id}`;
    const card = document.createElement('div');
    card.className = "p-4 rounded-xl bg-gray-950/70 border border-gray-800 hover:border-gray-700 flex flex-col justify-between space-y-3";
    
    card.innerHTML = `
      <div>
        <div class="flex items-center justify-between mb-1">
          <span class="text-xs font-bold text-white flex items-center gap-1.5">
            <i data-lucide="headphones" class="w-4 h-4 text-red-400"></i> ${p.name}
          </span>
          <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-red-500/20 text-red-400 uppercase">${p.ext}</span>
        </div>
        <p class="text-[11px] text-gray-400">${p.note}</p>
      </div>
      <button 
        id="btn-${formatKey}"
        class="w-full py-2 bg-gray-800 hover:bg-red-600 text-gray-200 hover:text-white rounded-lg text-xs font-medium flex items-center justify-center gap-1.5 transition"
      >
        <i data-lucide="download" class="w-3.5 h-3.5"></i>
        <span id="btn-text-${formatKey}">Download .${p.ext.toUpperCase()}</span>
      </button>
    `;

    const btn = card.querySelector(`#btn-${formatKey}`);
    btn.addEventListener('click', () => {
      handleDownloadRequest(
        videoUrl, 
        'audio', 
        p.format_id, 
        p.ext, 
        `${videoTitle} [Audio]`,
        formatKey,
        btn,
        `Audio .${p.ext.toUpperCase()}`
      );
    });

    container.appendChild(card);
  });
}

// Handle Download Request with Duplicate Prevention
async function handleDownloadRequest(url, type, formatId, ext, title, formatKey, btnElement, badgeText = "") {
  // Prevent duplicate simultaneous downloads of the exact same quality
  if (formatStates[formatKey] && formatStates[formatKey].status === 'downloading') {
    showToast("This quality is already downloading! See active progress bar below.", 'warning');
    showFloatingBarForTask(formatStates[formatKey].taskId);
    return;
  }

  // If already completed, just re-download the generated file directly
  if (formatStates[formatKey] && formatStates[formatKey].status === 'completed') {
    const existingTaskId = formatStates[formatKey].taskId;
    showToast("Opening already downloaded file...", 'success');
    triggerBrowserFileSave(existingTaskId);
    return;
  }

  // Update button UI immediately to show user something happened
  if (btnElement) {
    btnElement.disabled = true;
    btnElement.className = "px-4 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 border bg-yellow-950/60 text-yellow-300 border-yellow-700 transition cursor-not-allowed";
    const textSpan = btnElement.querySelector('span');
    if (textSpan) textSpan.textContent = "Starting...";
  }

  formatStates[formatKey] = { status: 'downloading', taskId: null };

  const auth = getSelectedAuth();

  try {
    const res = await fetch('/api/download', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: url,
        download_type: type,
        format_id: formatId,
        audio_ext: ext,
        auth_mode: auth.auth_mode,
        browser: auth.browser,
        quality_label: badgeText
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || "Failed to start download.");
    }

    const taskId = data.task_id;
    formatStates[formatKey].taskId = taskId;

    // Show floating bar immediately (HIGHLY NOTICEABLE & NEVER MISSED)
    showFloatingBar(taskId, title, badgeText);

    // Also add to in-page downloads section
    const activeDownloadsContainer = document.getElementById('activeDownloadsContainer');
    activeDownloadsContainer.classList.remove('hidden');
    createInPageDownloadCard(taskId, title, ext, formatKey, badgeText);

    // Show toast notification
    showToast(`⬇ Started downloading: ${badgeText || title}`, 'info');

    // Update header downloads pill
    updateHeaderDownloadsCount();

    // Start background polling
    startTrackingTask(taskId, formatKey, title);

  } catch (err) {
    formatStates[formatKey] = { status: 'idle', taskId: null };
    if (btnElement) {
      btnElement.disabled = false;
      btnElement.className = "dl-btn px-4 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 border bg-gray-800 hover:bg-red-600 text-gray-200 hover:text-white border-gray-700 hover:border-red-500 transition duration-150 shadow-sm";
      const textSpan = btnElement.querySelector('span');
      if (textSpan) textSpan.textContent = "Download MP4";
    }
    showToast("Download failed: " + err.message, 'error');
  }
}

// Cancel a download
async function cancelDownload(taskId) {
  const taskInfo = activeTasks[taskId];
  const formatKey = taskInfo ? taskInfo.formatKey : null;

  try {
    await fetch(`/api/cancel/${taskId}`, { method: 'POST' });
    showToast("Download cancelled.", 'warning');

    if (taskInfo && taskInfo.intervalId) {
      clearInterval(taskInfo.intervalId);
    }
    delete activeTasks[taskId];

    // Reset button on format card
    if (formatKey) {
      formatStates[formatKey] = { status: 'idle', taskId: null };
      const btn = document.getElementById(`btn-${formatKey}`);
      if (btn) {
        btn.disabled = false;
        btn.className = "dl-btn px-4 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 border bg-gray-800 hover:bg-red-600 text-gray-200 hover:text-white border-gray-700 hover:border-red-500 transition duration-150 shadow-sm";
        const textSpan = document.getElementById(`btn-text-${formatKey}`);
        if (textSpan) textSpan.textContent = "Download MP4";
      }
    }

    // Update in-page card
    const cardStatus = document.getElementById(`task-status-text-${taskId}`);
    if (cardStatus) {
      cardStatus.textContent = "Cancelled by user";
      cardStatus.className = "text-red-400 font-semibold";
    }
    const cancelBtn = document.getElementById(`task-cancel-btn-${taskId}`);
    if (cancelBtn) cancelBtn.remove();

    // Update floating bar
    if (currentFloatingTaskId === taskId) {
      document.getElementById('floatingStatus').textContent = "Cancelled";
      document.getElementById('floatingStatus').className = "text-red-400 font-semibold";
      document.getElementById('floatingCancelBtn').classList.add('hidden');
      setTimeout(() => {
        document.getElementById('floatingDownloadBar').classList.add('hidden');
      }, 3000);
    }

    updateHeaderDownloadsCount();

  } catch (err) {
    showToast("Failed to cancel: " + err.message, 'error');
  }
}

// Floating Bottom Download Bar Management
function showFloatingBar(taskId, title, badgeText) {
  currentFloatingTaskId = taskId;
  const bar = document.getElementById('floatingDownloadBar');
  bar.classList.remove('hidden');

  document.getElementById('floatingTitle').textContent = title || 'Downloading video';
  document.getElementById('floatingBadge').textContent = badgeText || 'Video';
  document.getElementById('floatingStatus').textContent = 'Starting download...';
  document.getElementById('floatingStatus').className = 'text-amber-400 font-semibold';
  document.getElementById('floatingSpeed').textContent = '0 KB/s';
  document.getElementById('floatingEta').textContent = 'ETA: --';
  document.getElementById('floatingPercent').textContent = '0%';
  document.getElementById('floatingProgressBar').style.width = '0%';

  document.getElementById('floatingCancelBtn').classList.remove('hidden');
  document.getElementById('floatingSaveBtn').classList.add('hidden');

  lucide.createIcons();
}

function showFloatingBarForTask(taskId) {
  const taskInfo = activeTasks[taskId];
  if (taskInfo) {
    showFloatingBar(taskId, taskInfo.title, "");
  }
}

function updateFloatingBar(taskId, task) {
  if (currentFloatingTaskId !== taskId) return;

  const pct = Math.max(0, Math.min(100, task.progress || 0));
  document.getElementById('floatingProgressBar').style.width = `${pct}%`;
  document.getElementById('floatingPercent').textContent = `${pct}%`;

  if (task.status === 'downloading') {
    document.getElementById('floatingStatus').textContent = `Downloading (${pct}%)`;
    document.getElementById('floatingStatus').className = "text-amber-400 font-semibold";
    document.getElementById('floatingSpeed').textContent = task.speed || 'Calculating...';
    document.getElementById('floatingEta').textContent = `ETA: ${task.eta || '--'}`;
  } else if (task.status === 'processing') {
    document.getElementById('floatingStatus').textContent = "Merging with FFmpeg...";
    document.getElementById('floatingStatus').className = "text-blue-400 font-semibold animate-pulse";
    document.getElementById('floatingSpeed').textContent = "Merging";
    document.getElementById('floatingEta').textContent = "Almost ready";
  } else if (task.status === 'completed') {
    document.getElementById('floatingProgressBar').style.width = '100%';
    document.getElementById('floatingPercent').textContent = '100%';
    document.getElementById('floatingStatus').textContent = `Finished (${task.filesize_str || ''})`;
    document.getElementById('floatingStatus').className = "text-emerald-400 font-bold";
    document.getElementById('floatingSpeed').textContent = "Done";
    document.getElementById('floatingEta').textContent = "0s";

    document.getElementById('floatingCancelBtn').classList.add('hidden');
    const saveBtn = document.getElementById('floatingSaveBtn');
    saveBtn.classList.remove('hidden');
    saveBtn.href = `/api/file/${taskId}`;
  } else if (task.status === 'error') {
    document.getElementById('floatingStatus').textContent = `Error: ${task.message || 'Failed'}`;
    document.getElementById('floatingStatus').className = "text-red-400 font-semibold";
    document.getElementById('floatingCancelBtn').classList.add('hidden');
  }
}

// In-Page Download Card Creation
function createInPageDownloadCard(taskId, title, ext, formatKey, badgeText) {
  const container = document.getElementById('downloadsList');
  const card = document.createElement('div');
  card.id = `task-card-${taskId}`;
  card.className = "bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3 shadow-lg";

  card.innerHTML = `
    <div class="flex items-start justify-between gap-3">
      <div class="space-y-0.5 flex-1 min-w-0">
        <div class="flex items-center gap-2">
          <h4 class="text-xs font-bold text-white truncate">${escapeHtml(title)}</h4>
          ${badgeText ? `<span class="text-[10px] font-bold px-1.5 py-0.2 rounded bg-red-500/20 text-red-400 border border-red-500/30">${escapeHtml(badgeText)}</span>` : ''}
        </div>
        <div class="flex items-center gap-2 text-[11px] text-gray-400">
          <span id="task-status-text-${taskId}" class="text-amber-400 font-medium">Starting download...</span>
          <span>•</span>
          <span id="task-speed-${taskId}">0 KB/s</span>
          <span>•</span>
          <span id="task-eta-${taskId}">ETA: --</span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <span class="text-xs font-bold text-white px-2 py-0.5 rounded bg-gray-800 border border-gray-700" id="task-percent-badge-${taskId}">0%</span>
        <!-- Cancel button on in-page card -->
        <button id="task-cancel-btn-${taskId}" class="px-2.5 py-1 rounded-lg text-xs font-semibold bg-red-600/20 hover:bg-red-600 text-red-400 hover:text-white border border-red-500/40 flex items-center gap-1 transition">
          <i data-lucide="x" class="w-3 h-3"></i> Cancel
        </button>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="w-full bg-gray-950 rounded-full h-2 overflow-hidden border border-gray-800">
      <div id="task-progress-bar-${taskId}" class="bg-gradient-to-r from-red-600 via-amber-500 to-emerald-500 h-2 rounded-full transition-all duration-300 w-0"></div>
    </div>

    <!-- Action row when completed -->
    <div id="task-actions-${taskId}" class="hidden pt-2 border-t border-gray-800/80 flex items-center justify-between">
      <span class="text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
        <i data-lucide="check-circle" class="w-4 h-4"></i> Ready! File saved.
      </span>
      <div class="flex items-center gap-2">
        <a 
          id="task-file-link-${taskId}"
          href="/api/file/${taskId}"
          download
          class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg text-xs font-medium flex items-center gap-1.5 shadow transition"
        >
          <i data-lucide="download" class="w-3.5 h-3.5"></i> Save File to PC
        </a>
      </div>
    </div>
  `;

  card.querySelector(`#task-cancel-btn-${taskId}`).addEventListener('click', () => {
    cancelDownload(taskId);
  });

  container.prepend(card);
  lucide.createIcons();
}

// Background Tracking
function startTrackingTask(taskId, formatKey, title) {
  const intervalId = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${taskId}`);
      if (!res.ok) return;

      const data = await res.json();
      updateTaskUI(taskId, data, formatKey);
      updateFloatingBar(taskId, data);

      if (data.status === 'completed' || data.status === 'error' || data.status === 'cancelled') {
        clearInterval(intervalId);
        delete activeTasks[taskId];
        updateHeaderDownloadsCount();

        if (data.status === 'completed') {
          formatStates[formatKey] = { status: 'completed', taskId: taskId };
          showToast(`✓ Download Complete: ${title}`, 'success');
          // Automatically trigger browser save
          triggerBrowserFileSave(taskId);
          // Update button state on format card
          updateButtonCompleted(formatKey);
        } else if (data.status === 'error') {
          formatStates[formatKey] = { status: 'idle', taskId: null };
          showToast(`Download error: ${data.message || 'Failed'}`, 'error');
          resetButton(formatKey);
        }
      }
    } catch (e) {
      console.error("Tracking error:", e);
    }
  }, 1000);

  activeTasks[taskId] = { intervalId, formatKey, title };
}

function updateTaskUI(taskId, task, formatKey) {
  const progressBar = document.getElementById(`task-progress-bar-${taskId}`);
  const percentBadge = document.getElementById(`task-percent-badge-${taskId}`);
  const statusText = document.getElementById(`task-status-text-${taskId}`);
  const speedText = document.getElementById(`task-speed-${taskId}`);
  const etaText = document.getElementById(`task-eta-${taskId}`);
  const actionsRow = document.getElementById(`task-actions-${taskId}`);
  const cancelBtn = document.getElementById(`task-cancel-btn-${taskId}`);

  if (!progressBar) return;

  const pct = Math.max(0, Math.min(100, task.progress || 0));
  progressBar.style.width = `${pct}%`;
  percentBadge.textContent = `${pct}%`;

  // Update button on format card with live %
  if (formatKey) {
    const btnText = document.getElementById(`btn-text-${formatKey}`);
    if (btnText && task.status === 'downloading') {
      btnText.textContent = `Downloading... (${pct}%)`;
    }
  }

  if (task.status === 'downloading') {
    statusText.textContent = `Downloading (${pct}%)`;
    statusText.className = "text-amber-400 font-medium";
    speedText.textContent = task.speed || 'Calculating...';
    etaText.textContent = `ETA: ${task.eta || '--'}`;
  } else if (task.status === 'processing') {
    statusText.textContent = "Merging Video & Audio (FFmpeg)...";
    statusText.className = "text-blue-400 font-medium animate-pulse";
    speedText.textContent = "Processing";
    etaText.textContent = "Almost done";
  } else if (task.status === 'completed') {
    progressBar.style.width = '100%';
    percentBadge.textContent = '100%';
    statusText.textContent = `Completed (${task.filesize_str || ''})`;
    statusText.className = "text-emerald-400 font-bold";
    speedText.textContent = "Finished";
    etaText.textContent = "0s";
    if (cancelBtn) cancelBtn.remove();
    if (actionsRow) {
      actionsRow.classList.remove('hidden');
      lucide.createIcons();
    }
  } else if (task.status === 'error') {
    statusText.textContent = `Error: ${task.message || 'Download failed'}`;
    statusText.className = "text-red-400 font-semibold";
    if (cancelBtn) cancelBtn.remove();
  }
}

function updateButtonCompleted(formatKey) {
  const btn = document.getElementById(`btn-${formatKey}`);
  if (btn) {
    btn.disabled = false;
    btn.className = "dl-btn px-4 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 border bg-emerald-950/60 text-emerald-300 border-emerald-700 hover:bg-emerald-900 transition duration-150 shadow-sm";
    const textSpan = document.getElementById(`btn-text-${formatKey}`);
    if (textSpan) textSpan.textContent = "✓ Downloaded (Save Again)";
  }
}

function resetButton(formatKey) {
  const btn = document.getElementById(`btn-${formatKey}`);
  if (btn) {
    btn.disabled = false;
    btn.className = "dl-btn px-4 py-2 rounded-xl text-xs font-medium flex items-center gap-1.5 border bg-gray-800 hover:bg-red-600 text-gray-200 hover:text-white border-gray-700 hover:border-red-500 transition duration-150 shadow-sm";
    const textSpan = document.getElementById(`btn-text-${formatKey}`);
    if (textSpan) textSpan.textContent = "Download MP4";
  }
}

function updateHeaderDownloadsCount() {
  const count = Object.keys(activeTasks).length;
  const headerBtn = document.getElementById('headerDownloadsBtn');
  const headerText = document.getElementById('headerDownloadsText');

  if (count > 0) {
    headerBtn.classList.remove('hidden');
    headerText.textContent = `${count} Downloading`;
  } else {
    headerBtn.classList.add('hidden');
  }
}

function triggerBrowserFileSave(taskId) {
  const a = document.createElement('a');
  a.href = `/api/file/${taskId}`;
  a.download = '';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
