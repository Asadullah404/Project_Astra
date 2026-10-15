/**
 * Film Studio - Frontend Application Logic
 * Pure vanilla JavaScript with xterm.js integration, WebSockets, and live monitoring.
 */

(function () {
  'use strict';

  // --- Global State ---
  let startupToken = null;
  let term = null;
  let fitAddon = null;
  let wsTerminal = null;
  let wsMonitor = null;
  let activeJobId = null;
  let activeJobPath = null;
  let lastMonitorData = null;
  let saveSettingsTimeout = null;

  // --- DOM Elements ---
  const studioLayout = document.getElementById('studioLayout');
  const colSettings = document.getElementById('colSettings');
  const colTerminal = document.getElementById('colTerminal');
  const colMonitor = document.getElementById('colMonitor');
  const resizerLeft = document.getElementById('resizerLeft');
  const resizerRight = document.getElementById('resizerRight');
  const btnCollapseLeft = document.getElementById('btnCollapseLeft');
  const btnCollapseRight = document.getElementById('btnCollapseRight');
  const btnRestoreLeft = document.getElementById('btnRestoreLeft');
  const btnRestoreRight = document.getElementById('btnRestoreRight');
  const btnToggleSettingsTop = document.getElementById('btnToggleSettingsTop');
  const btnToggleMonitorTop = document.getElementById('btnToggleMonitorTop');

  const globalStatusPill = document.getElementById('globalStatusPill');
  const globalStateDot = document.getElementById('globalStateDot');
  const globalStateText = document.getElementById('globalStateText');

  // Left Form
  const inputTitle = document.getElementById('inputTitle');
  const inputStory = document.getElementById('inputStory');
  const inputStyle = document.getElementById('inputStyle');
  const inputDuration = document.getElementById('inputDuration');
  const inputSecPerClip = document.getElementById('inputSecPerClip');
  const selectAspect = document.getElementById('selectAspect');
  const selectResolution = document.getElementById('selectResolution');
  const charactersContainer = document.getElementById('charactersContainer');
  const btnAddCharacter = document.getElementById('btnAddCharacter');
  const toggleNarration = document.getElementById('toggleNarration');
  const groupVoiceSelect = document.getElementById('groupVoiceSelect');
  const selectVoice = document.getElementById('selectVoice');
  const toggleMusic = document.getElementById('toggleMusic');
  const toggleKeepAudioLow = document.getElementById('toggleKeepAudioLow');
  const inputBudget = document.getElementById('inputBudget');
  const toggleApproval = document.getElementById('toggleApproval');
  const warningNoApproval = document.getElementById('warningNoApproval');
  const inputOutputRoot = document.getElementById('inputOutputRoot');
  const btnRunJob = document.getElementById('btnRunJob');
  const btnCheckGflow = document.getElementById('btnCheckGflow');
  const btnOpenJobsFolder = document.getElementById('btnOpenJobsFolder');

  // Center Terminal
  const termDot = document.getElementById('termDot');
  const termStateText = document.getElementById('termStateText');
  const termVersionText = document.getElementById('termVersionText');
  const btnStartSession = document.getElementById('btnStartSession');
  const btnStopSession = document.getElementById('btnStopSession');
  const btnRestartSession = document.getElementById('btnRestartSession');
  const btnClearTerminal = document.getElementById('btnClearTerminal');
  const terminalContainer = document.getElementById('terminalContainer');

  // Right Monitor
  const btnOpenCurrentJobFolder = document.getElementById('btnOpenCurrentJobFolder');
  const btnResendPrompt = document.getElementById('btnResendPrompt');
  const monJobTitle = document.getElementById('monJobTitle');
  const monTimer = document.getElementById('monTimer');
  const monJobPath = document.getElementById('monJobPath');
  const monClipsCount = document.getElementById('monClipsCount');
  const monStateBadge = document.getElementById('monStateBadge');
  const monProgressBar = document.getElementById('monProgressBar');
  const sceneGrid = document.getElementById('sceneGrid');
  const monFinalFilename = document.getElementById('monFinalFilename');
  const monFinalBadge = document.getElementById('monFinalBadge');
  const finalPreviewContainer = document.getElementById('finalPreviewContainer');
  const finalVideoPlayer = document.getElementById('finalVideoPlayer');
  const monFinalDuration = document.getElementById('monFinalDuration');
  const monFinalSize = document.getElementById('monFinalSize');
  const pillScenesJson = document.getElementById('pillScenesJson');
  const statusScenesJson = document.getElementById('statusScenesJson');
  const pillStoryMd = document.getElementById('pillStoryMd');
  const statusStoryMd = document.getElementById('statusStoryMd');
  const countNarrationAudio = document.getElementById('countNarrationAudio');
  const logTailContainer = document.getElementById('logTailContainer');
  const jobHistoryList = document.getElementById('jobHistoryList');
  const btnRefreshHistory = document.getElementById('btnRefreshHistory');

  // Modals
  const modalGflow = document.getElementById('modalGflow');
  const gflowModalContent = document.getElementById('gflowModalContent');
  const btnCloseGflowModal = document.getElementById('btnCloseGflowModal');
  const btnCloseGflowModalBtn = document.getElementById('btnCloseGflowModalBtn');
  const btnCopyGflowResult = document.getElementById('btnCopyGflowResult');

  const modalConfirm = document.getElementById('modalConfirm');
  const btnCancelConfirm = document.getElementById('btnCancelConfirm');
  const btnDismissConfirm = document.getElementById('btnDismissConfirm');
  const btnProceedConfirm = document.getElementById('btnProceedConfirm');

  const modalClipPreview = document.getElementById('modalClipPreview');
  const clipPreviewTitle = document.getElementById('clipPreviewTitle');
  const clipModalPlayer = document.getElementById('clipModalPlayer');
  const btnCloseClipModal = document.getElementById('btnCloseClipModal');
  const btnCloseClipModalBtn = document.getElementById('btnCloseClipModalBtn');

  // --- Initialization ---
  async function init() {
    // 1. Resolve startup token
    const urlParams = new URLSearchParams(window.location.search);
    startupToken = urlParams.get('token');
    if (!startupToken) {
      try {
        const resp = await fetch('/api/token');
        const data = await resp.json();
        startupToken = data.token;
      } catch (e) {
        console.error('Failed to obtain startup token:', e);
      }
    }

    // 2. Setup xterm.js
    initTerminal();

    // 2b. Setup Closeable & Resizable Sidebars
    initSidebarResizing();

    // 3. Connect WebSockets
    connectTerminalWebSocket();
    connectMonitorWebSocket();

    // 4. Load saved settings
    await loadSettings();

    // 5. Load job history
    await loadJobHistory();

    // 6. Bind Event Listeners
    bindEvents();
  }

  // --- Sidebar Collapse & Resize Management ---
  function initSidebarResizing() {
    // Restore saved widths from localStorage
    const savedLeftWidth = localStorage.getItem('film_studio_left_width');
    const savedRightWidth = localStorage.getItem('film_studio_right_width');
    if (savedLeftWidth && colSettings) {
      colSettings.style.width = `${Math.max(240, Math.min(700, parseInt(savedLeftWidth, 10)))}px`;
    }
    if (savedRightWidth && colMonitor) {
      colMonitor.style.width = `${Math.max(240, Math.min(700, parseInt(savedRightWidth, 10)))}px`;
    }

    // Left Resizer Dragging
    if (resizerLeft && colSettings) {
      resizerLeft.addEventListener('mousedown', (e) => {
        e.preventDefault();
        studioLayout.classList.add('is-resizing');
        resizerLeft.classList.add('is-dragging');
        const startX = e.clientX;
        const startWidth = colSettings.getBoundingClientRect().width;

        function onMouseMove(ev) {
          const delta = ev.clientX - startX;
          const newWidth = Math.max(240, Math.min(700, startWidth + delta));
          colSettings.style.width = `${newWidth}px`;
          if (fitAddon) fitAddon.fit();
        }

        function onMouseUp(ev) {
          studioLayout.classList.remove('is-resizing');
          resizerLeft.classList.remove('is-dragging');
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
          const finalWidth = colSettings.getBoundingClientRect().width;
          localStorage.setItem('film_studio_left_width', Math.round(finalWidth));
          if (fitAddon) fitAddon.fit();
          sendTerminalResize();
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    }

    // Right Resizer Dragging
    if (resizerRight && colMonitor) {
      resizerRight.addEventListener('mousedown', (e) => {
        e.preventDefault();
        studioLayout.classList.add('is-resizing');
        resizerRight.classList.add('is-dragging');
        const startX = e.clientX;
        const startWidth = colMonitor.getBoundingClientRect().width;

        function onMouseMove(ev) {
          const delta = startX - ev.clientX; // dragging left expands right sidebar
          const newWidth = Math.max(240, Math.min(700, startWidth + delta));
          colMonitor.style.width = `${newWidth}px`;
          if (fitAddon) fitAddon.fit();
        }

        function onMouseUp(ev) {
          studioLayout.classList.remove('is-resizing');
          resizerRight.classList.remove('is-dragging');
          document.removeEventListener('mousemove', onMouseMove);
          document.removeEventListener('mouseup', onMouseUp);
          const finalWidth = colMonitor.getBoundingClientRect().width;
          localStorage.setItem('film_studio_right_width', Math.round(finalWidth));
          if (fitAddon) fitAddon.fit();
          sendTerminalResize();
        }

        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
      });
    }
  }

  function toggleLeftSidebar(forceState) {
    if (!colSettings) return;
    const isCurrentlyCollapsed = colSettings.classList.contains('collapsed');
    const shouldCollapse = forceState !== undefined ? forceState : !isCurrentlyCollapsed;

    if (shouldCollapse) {
      colSettings.classList.add('collapsed');
      if (resizerLeft) resizerLeft.classList.add('collapsed');
      if (btnRestoreLeft) btnRestoreLeft.classList.remove('hidden');
    } else {
      colSettings.classList.remove('collapsed');
      if (resizerLeft) resizerLeft.classList.remove('collapsed');
      if (btnRestoreLeft) btnRestoreLeft.classList.add('hidden');
    }

    setTimeout(() => {
      if (fitAddon) fitAddon.fit();
      sendTerminalResize();
    }, 180);
  }

  function toggleRightSidebar(forceState) {
    if (!colMonitor) return;
    const isCurrentlyCollapsed = colMonitor.classList.contains('collapsed');
    const shouldCollapse = forceState !== undefined ? forceState : !isCurrentlyCollapsed;

    if (shouldCollapse) {
      colMonitor.classList.add('collapsed');
      if (resizerRight) resizerRight.classList.add('collapsed');
      if (btnRestoreRight) btnRestoreRight.classList.remove('hidden');
    } else {
      colMonitor.classList.remove('collapsed');
      if (resizerRight) resizerRight.classList.remove('collapsed');
      if (btnRestoreRight) btnRestoreRight.classList.add('hidden');
    }

    setTimeout(() => {
      if (fitAddon) fitAddon.fit();
      sendTerminalResize();
    }, 180);
  }

  // --- Terminal Setup ---
  function initTerminal() {
    if (!window.Terminal) {
      terminalContainer.innerHTML = '<div style="color:red;padding:20px;">xterm.js failed to load.</div>';
      return;
    }

    term = new window.Terminal({
      theme: {
        background: '#080a0c',
        foreground: '#f1f2f6',
        cursor: '#00e5b7',
        cursorAccent: '#080a0c',
        selectionBackground: 'rgba(0, 229, 183, 0.3)',
        black: '#1e252b',
        red: '#ff4757',
        green: '#2ed573',
        yellow: '#ffa502',
        blue: '#1e90ff',
        magenta: '#ff6b81',
        cyan: '#00e5b7',
        white: '#ffffff',
        brightBlack: '#576574',
        brightRed: '#ff6b81',
        brightGreen: '#7bed9f',
        brightYellow: '#eccc68',
        brightBlue: '#70a1ff',
        brightMagenta: '#ff78c4',
        brightCyan: '#70ebd3',
        brightWhite: '#ffffff',
      },
      fontFamily: '"JetBrains Mono", Consolas, "Courier New", monospace',
      fontSize: 13,
      lineHeight: 1.25,
      cursorBlink: true,
      convertEol: true,
      allowTransparency: true
    });

    if (window.FitAddon && window.FitAddon.FitAddon) {
      fitAddon = new window.FitAddon.FitAddon();
      term.loadAddon(fitAddon);
    }

    term.open(terminalContainer);

    // Initial fit
    setTimeout(() => {
      if (fitAddon) {
        fitAddon.fit();
        sendTerminalResize();
      }
    }, 150);

    // Resize observer on terminal container
    window.addEventListener('resize', () => {
      if (fitAddon) {
        fitAddon.fit();
        sendTerminalResize();
      }
    });

    // Keystrokes sent directly to live agy PTY
    term.onData(data => {
      if (wsTerminal && wsTerminal.readyState === WebSocket.OPEN) {
        wsTerminal.send(JSON.stringify({ type: 'input', data }));
      }
    });
  }

  function sendTerminalResize() {
    if (term && wsTerminal && wsTerminal.readyState === WebSocket.OPEN) {
      if (term.cols > 5 && term.rows > 2 && isFinite(term.cols) && isFinite(term.rows)) {
        wsTerminal.send(JSON.stringify({
          type: 'resize',
          cols: term.cols,
          rows: term.rows
        }));
      }
    }
  }

  // --- WebSockets ---
  function connectTerminalWebSocket() {
    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${loc.host}/ws/terminal?token=${encodeURIComponent(startupToken || '')}`;

    wsTerminal = new WebSocket(wsUrl);

    wsTerminal.onopen = () => {
      console.log('Terminal WebSocket connected');
      sendTerminalResize();
    };

    wsTerminal.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'output' && term) {
          term.write(msg.data);
        } else if (msg.type === 'status') {
          updateTerminalStatusUI(msg.data);
        }
      } catch (e) {
        console.error('Terminal ws message parse error:', e);
      }
    };

    wsTerminal.onclose = () => {
      console.log('Terminal WebSocket disconnected, retrying in 2s...');
      setTimeout(connectTerminalWebSocket, 2000);
    };
  }

  function updateTerminalStatusUI(status) {
    if (!status) return;
    const state = status.state || 'stopped';
    termStateText.textContent = state.toUpperCase();
    termVersionText.textContent = status.version ? `agy ${status.version}` : 'agy';

    termDot.className = 'pulsing-dot dot-sm';
    if (state === 'running') {
      termDot.classList.add('dot-running');
    } else if (state === 'starting') {
      termDot.classList.add('dot-writing');
    } else {
      termDot.classList.add('dot-idle');
    }
  }

  function connectMonitorWebSocket() {
    const loc = window.location;
    const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${loc.host}/ws/monitor?token=${encodeURIComponent(startupToken || '')}`;

    wsMonitor = new WebSocket(wsUrl);

    wsMonitor.onopen = () => {
      console.log('Monitor WebSocket connected');
    };

    wsMonitor.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'monitor') {
          renderMonitorUpdate(msg.data);
        }
      } catch (e) {
        console.error('Monitor ws message parse error:', e);
      }
    };

    wsMonitor.onclose = () => {
      console.log('Monitor WebSocket disconnected, retrying in 2s...');
      setTimeout(connectMonitorWebSocket, 2000);
    };
  }

  // --- Live Monitor Rendering ---
  function renderMonitorUpdate(data) {
    if (!data) return;
    lastMonitorData = data;

    activeJobPath = data.job_dir;
    activeJobId = data.job_name;

    // Header & Info
    monJobTitle.textContent = data.job_name || 'No Active Job';
    monJobPath.textContent = data.job_dir || '-';
    monJobPath.title = data.job_dir || '';

    // Timer
    const elapsed = data.elapsed_seconds || 0;
    const m = Math.floor(elapsed / 60);
    const s = elapsed % 60;
    monTimer.textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;

    // Overall State Badge
    const state = data.state_badge || 'Waiting for agy';
    monStateBadge.textContent = state;
    globalStateText.textContent = state;

    globalStateDot.className = 'pulsing-dot';
    if (state === 'Done') {
      globalStateDot.classList.add('dot-done');
      monStateBadge.style.color = 'var(--emerald-success)';
      monStateBadge.style.borderColor = 'var(--emerald-success)';
      // Job is complete - re-enable Run Job button
      btnRunJob.disabled = false;
      btnRunJob.classList.remove('is-running', 'is-launching');
      btnRunJob.innerHTML = '<span class="btn-icon">⚡</span> Run Job';
    } else if (state === 'Generating' || state === 'Stitching') {
      globalStateDot.classList.add('dot-running');
      monStateBadge.style.color = 'var(--teal-primary)';
      monStateBadge.style.borderColor = 'rgba(0, 229, 183, 0.4)';
      // Job is running - keep Run Job button disabled and greyed out
      btnRunJob.disabled = true;
      btnRunJob.classList.add('is-running');
      btnRunJob.innerHTML = `<span class="spinner"></span> ${state}...`;
    } else {
      globalStateDot.classList.add('dot-idle');
      monStateBadge.style.color = 'var(--text-muted)';
      monStateBadge.style.borderColor = 'var(--border-subtle)';
      // Idle - enable Run Job button if not currently launching
      if (!btnRunJob.classList.contains('is-launching') && !btnRunJob.classList.contains('is-running')) {
        btnRunJob.disabled = false;
        btnRunJob.classList.remove('is-running', 'is-launching');
        btnRunJob.innerHTML = '<span class="btn-icon">⚡</span> Run Job';
      }
    }

    // Clips Progress
    const found = data.clips_found || 0;
    const expected = data.expected_clips || 1;
    monClipsCount.textContent = `${found} / ${expected} found`;
    const percent = Math.min(100, Math.round((found / expected) * 100));
    monProgressBar.style.width = `${percent}%`;

    // Scene Tiles Grid
    renderSceneGrid(data.scenes || [], data.job_name);

    // Final Video Card
    const final = data.final_video || {};
    if (final.found) {
      monFinalBadge.textContent = 'FOUND';
      monFinalBadge.className = 'badge badge-final found';
      finalPreviewContainer.classList.remove('hidden');
      monFinalDuration.textContent = final.duration_formatted ? `⏱ ${final.duration_formatted}` : '';
      monFinalSize.textContent = final.size_mb ? `💾 ${final.size_mb} MB` : '';

      const mediaUrl = `/api/media/${encodeURIComponent(data.job_name)}/final/final_film.mp4`;
      if (!finalVideoPlayer.src.includes(mediaUrl)) {
        finalVideoPlayer.src = mediaUrl;
      }
    } else {
      monFinalBadge.textContent = 'NOT FOUND';
      monFinalBadge.className = 'badge badge-final';
      finalPreviewContainer.classList.add('hidden');
    }

    // Pipeline Assets
    statusScenesJson.textContent = data.script_scenes ? 'Found' : 'Missing';
    statusScenesJson.style.color = data.script_scenes ? 'var(--emerald-success)' : 'var(--text-subtle)';

    statusStoryMd.textContent = data.script_story ? 'Found' : 'Missing';
    statusStoryMd.style.color = data.script_story ? 'var(--emerald-success)' : 'var(--text-subtle)';

    countNarrationAudio.textContent = data.narration_count || 0;

    // Progress Log Tail
    const lines = data.log_tail || [];
    if (lines.length > 0) {
      logTailContainer.innerHTML = lines.map(line => `<div>${escapeHtml(line)}</div>`).join('');
      logTailContainer.scrollTop = logTailContainer.scrollHeight;
    } else {
      logTailContainer.innerHTML = '<span class="log-empty">No log entries yet.</span>';
    }
  }

  function renderSceneGrid(scenes, jobId) {
    sceneGrid.innerHTML = '';
    scenes.forEach(scene => {
      const tile = document.createElement('div');
      tile.className = `scene-tile status-${scene.status}`;
      
      const numSpan = document.createElement('span');
      numSpan.className = 'tile-num';
      numSpan.textContent = `sc_${String(scene.index).padStart(3, '0')}`;

      const durSpan = document.createElement('span');
      durSpan.className = 'tile-dur';
      durSpan.textContent = scene.duration_formatted || (scene.status === 'writing' ? '...' : '--:--');

      tile.appendChild(numSpan);
      tile.appendChild(durSpan);

      // Click to preview found scenes
      if (scene.status === 'found' && jobId) {
        tile.title = `Click to preview ${scene.name} (${scene.size_kb} KB)`;
        tile.addEventListener('click', () => {
          openClipPreview(jobId, scene.name);
        });
      }

      sceneGrid.appendChild(tile);
    });
  }

  function openClipPreview(jobId, sceneName) {
    clipPreviewTitle.textContent = `Preview: ${sceneName}`;
    const clipUrl = `/api/media/${encodeURIComponent(jobId)}/clips/${encodeURIComponent(sceneName)}`;
    clipModalPlayer.src = clipUrl;
    modalClipPreview.classList.remove('hidden');
    clipModalPlayer.play().catch(() => {});
  }

  // --- Settings Persistence & Form Handling ---
  async function loadSettings() {
    try {
      const res = await fetch('/api/settings');
      if (!res.ok) return;
      const s = await res.json();

      inputTitle.value = s.title || '';
      inputStory.value = s.story || '';
      inputStyle.value = s.style || '';
      inputDuration.value = s.duration_minutes || 1.0;
      inputSecPerClip.value = s.seconds_per_clip || 8;
      selectAspect.value = s.aspect || '16:9';
      selectResolution.value = s.resolution || '1080p';

      toggleNarration.checked = s.narration !== false;
      selectVoice.value = s.voice || 'en-US-ChristopherNeural';
      toggleMusic.checked = s.background_music !== false;
      toggleKeepAudioLow.checked = s.keep_clip_audio_low !== false;

      inputBudget.value = s.budget || 50;
      toggleApproval.checked = s.approval_mode !== false;
      inputOutputRoot.value = s.output_root || './jobs';

      // Update approval warning
      updateApprovalWarning();
      updateVoiceVisibility();

      // Render characters
      charactersContainer.innerHTML = '';
      const chars = s.characters || [];
      if (chars.length === 0) {
        addCharacterRow('Kira', 'Young woman with cybernetic teal eyes, sleek black jacket, silver braided hair.');
      } else {
        chars.forEach(c => addCharacterRow(c.name, c.description));
      }
    } catch (e) {
      console.error('Error loading settings:', e);
    }
  }

  function getFormSettings() {
    const chars = [];
    const rows = charactersContainer.querySelectorAll('.character-card');
    rows.forEach(r => {
      const name = r.querySelector('.char-name-input').value.trim();
      const desc = r.querySelector('.char-desc-input').value.trim();
      if (name || desc) {
        chars.push({ name, description: desc });
      }
    });

    return {
      title: inputTitle.value.trim() || 'Untitled Film',
      story: inputStory.value.trim(),
      style: inputStyle.value.trim(),
      duration_minutes: parseFloat(inputDuration.value) || 1.0,
      seconds_per_clip: parseFloat(inputSecPerClip.value) || 8.0,
      aspect: selectAspect.value,
      resolution: selectResolution.value,
      characters: chars,
      narration: toggleNarration.checked,
      voice: selectVoice.value,
      background_music: toggleMusic.checked,
      keep_clip_audio_low: toggleKeepAudioLow.checked,
      budget: parseInt(inputBudget.value, 10) || 50,
      approval_mode: toggleApproval.checked,
      output_root: inputOutputRoot.value.trim() || './jobs'
    };
  }

  function triggerAutoSave() {
    clearTimeout(saveSettingsTimeout);
    saveSettingsTimeout = setTimeout(async () => {
      const settings = getFormSettings();
      try {
        await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(settings)
        });
      } catch (e) {
        console.error('Failed to auto-save settings:', e);
      }
    }, 600);
  }

  function addCharacterRow(name = '', description = '') {
    const card = document.createElement('div');
    card.className = 'character-card';

    const topRow = document.createElement('div');
    topRow.className = 'char-row-top';

    const nameInput = document.createElement('input');
    nameInput.type = 'text';
    nameInput.className = 'form-input char-name-input';
    nameInput.placeholder = 'Character Name (e.g. Kira)';
    nameInput.value = name;
    nameInput.addEventListener('input', triggerAutoSave);

    const btnRemove = document.createElement('button');
    btnRemove.type = 'button';
    btnRemove.className = 'btn-remove-char';
    btnRemove.innerHTML = '&times;';
    btnRemove.title = 'Remove character';
    btnRemove.addEventListener('click', () => {
      card.remove();
      triggerAutoSave();
    });

    topRow.appendChild(nameInput);
    topRow.appendChild(btnRemove);

    const descInput = document.createElement('textarea');
    descInput.className = 'form-textarea char-desc-input';
    descInput.rows = 2;
    descInput.placeholder = 'Full visual description (clothes, facial features, lighting, hair, cybernetics)...';
    descInput.value = description;
    descInput.addEventListener('input', triggerAutoSave);

    card.appendChild(topRow);
    card.appendChild(descInput);
    charactersContainer.appendChild(card);
  }

  function updateApprovalWarning() {
    if (toggleApproval.checked) {
      warningNoApproval.classList.add('hidden');
    } else {
      warningNoApproval.classList.remove('hidden');
    }
  }

  function updateVoiceVisibility() {
    if (toggleNarration.checked) {
      groupVoiceSelect.classList.remove('hidden');
    } else {
      groupVoiceSelect.classList.add('hidden');
    }
  }

  // --- Job Execution & History ---
  async function runJob(force = false) {
    const settings = getFormSettings();

    btnRunJob.disabled = true;
    btnRunJob.classList.add('is-running', 'is-launching');
    btnRunJob.innerHTML = '<span class="spinner"></span> Launching Job...';

    try {
      const resp = await fetch('/api/job/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ settings, force })
      });

      if (resp.status === 409) {
        // Active job confirmation required
        const data = await resp.json();
        document.getElementById('confirmMessageText').textContent = data.message || 'A job is still running.';
        modalConfirm.classList.remove('hidden');
        btnRunJob.disabled = false;
        btnRunJob.classList.remove('is-running', 'is-launching');
        btnRunJob.innerHTML = '<span class="btn-icon">⚡</span> Run Job';
        return;
      }

      if (!resp.ok) {
        throw new Error(`Server returned error ${resp.status}`);
      }

      const resData = await resp.json();
      console.log('Job started:', resData);

      // Keep button greyed out and showing in-progress status while job runs
      btnRunJob.disabled = true;
      btnRunJob.classList.remove('is-launching');
      btnRunJob.classList.add('is-running');
      btnRunJob.innerHTML = '<span class="spinner"></span> Job in Progress...';

      // Refresh job history
      await loadJobHistory();
    } catch (e) {
      alert(`Failed to start job: ${e.message}`);
      btnRunJob.disabled = false;
      btnRunJob.classList.remove('is-running', 'is-launching');
      btnRunJob.innerHTML = '<span class="btn-icon">⚡</span> Run Job';
    }
  }

  async function loadJobHistory() {
    try {
      const resp = await fetch('/api/jobs');
      if (!resp.ok) return;
      const data = await resp.json();
      const jobs = data.jobs || [];

      jobHistoryList.innerHTML = '';
      if (jobs.length === 0) {
        jobHistoryList.innerHTML = '<span class="log-empty">No previous jobs found.</span>';
        return;
      }

      jobs.forEach(job => {
        const item = document.createElement('div');
        item.className = 'history-item';
        if (job.id === activeJobId) {
          item.classList.add('active');
        }

        const leftDiv = document.createElement('div');
        const titleSpan = document.createElement('span');
        titleSpan.className = 'hist-title';
        titleSpan.textContent = job.title || job.id;

        const dateSpan = document.createElement('span');
        dateSpan.className = 'hist-date';
        dateSpan.textContent = `${job.id} • ${formatDate(job.created_at)}`;

        leftDiv.appendChild(titleSpan);
        leftDiv.appendChild(dateSpan);

        const actionsDiv = document.createElement('div');
        actionsDiv.className = 'hist-actions';

        const btnOpen = document.createElement('button');
        btnOpen.className = 'btn btn-ghost btn-xs';
        btnOpen.textContent = '📁';
        btnOpen.title = 'Open Folder';
        btnOpen.addEventListener('click', (e) => {
          e.stopPropagation();
          openFolder(job.path);
        });

        const btnResend = document.createElement('button');
        btnResend.className = 'btn btn-ghost btn-xs';
        btnResend.textContent = '🔁';
        btnResend.title = 'Re-send prompt to agy';
        btnResend.addEventListener('click', (e) => {
          e.stopPropagation();
          resendPrompt(job.path);
        });

        actionsDiv.appendChild(btnOpen);
        actionsDiv.appendChild(btnResend);

        item.appendChild(leftDiv);
        item.appendChild(actionsDiv);

        // Click to switch monitor to this job
        item.addEventListener('click', () => {
          selectJob(job.path);
        });

        jobHistoryList.appendChild(item);
      });
    } catch (e) {
      console.error('Error loading job history:', e);
    }
  }

  async function selectJob(jobPath) {
    try {
      await fetch('/api/job/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: jobPath })
      });
      loadJobHistory();
    } catch (e) {
      console.error('Error selecting job:', e);
    }
  }

  async function resendPrompt(jobPath) {
    try {
      const resp = await fetch('/api/job/resend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: jobPath })
      });
      const data = await resp.json();
      if (data.status === 'ok') {
        alert('Prompt re-sent to agy terminal session.');
      }
    } catch (e) {
      alert(`Error resending prompt: ${e.message}`);
    }
  }

  async function openFolder(path) {
    try {
      await fetch('/api/job/open-folder', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path || activeJobPath })
      });
    } catch (e) {
      console.error('Error opening folder:', e);
    }
  }

  async function executeTerminalAction(action) {
    try {
      const resp = await fetch('/api/terminal/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action })
      });
      const data = await resp.json();
      updateTerminalStatusUI(data.terminal_status);
    } catch (e) {
      console.error(`Terminal action ${action} failed:`, e);
    }
  }

  // --- Diagnostics Check: gflow ---
  async function runGflowCheck() {
    modalGflow.classList.remove('hidden');
    gflowModalContent.innerHTML = '<div class="spinner"></div> Probing gflow session and balance (read-only)...';

    try {
      const resp = await fetch('/api/gflow/check', { method: 'POST' });
      const data = await resp.json();

      let html = `<div style="font-family: var(--font-mono); font-size: 0.78rem;">`;
      
      // Auth status
      const auth = data.auth || {};
      const authOk = auth.status === 'ok';
      html += `<div style="margin-bottom: 12px; padding: 10px; background: var(--bg-input); border-radius: 6px;">
        <strong>1. Auth Status:</strong> <span style="color: ${authOk ? 'var(--emerald-success)' : 'var(--amber-warning)'};">${auth.status.toUpperCase()}</span>
        <pre style="margin-top: 6px; white-space: pre-wrap; color: #a4b0be;">${escapeHtml(auth.output || 'No output')}</pre>
      </div>`;

      // Credits status
      const cred = data.credits || {};
      html += `<div style="padding: 10px; background: var(--bg-input); border-radius: 6px;">
        <strong>2. Credits Status:</strong> <span style="color: ${cred.status === 'ok' ? 'var(--emerald-success)' : 'var(--amber-warning)'};">${cred.status.toUpperCase()}</span>
        <pre style="margin-top: 6px; white-space: pre-wrap; color: #a4b0be;">${escapeHtml(cred.output || 'No output')}</pre>
      </div>`;

      html += `</div>`;
      gflowModalContent.innerHTML = html;
    } catch (e) {
      gflowModalContent.innerHTML = `<div style="color: var(--red-danger);">Failed to check gflow: ${escapeHtml(e.message)}</div>`;
    }
  }

  // --- Event Bindings ---
  function bindEvents() {
    // Form Inputs auto-save
    [inputTitle, inputStory, inputStyle, inputDuration, inputSecPerClip, selectAspect, selectResolution, selectVoice, inputBudget, inputOutputRoot].forEach(el => {
      el.addEventListener('input', triggerAutoSave);
      el.addEventListener('change', triggerAutoSave);
    });

    btnAddCharacter.addEventListener('click', () => {
      addCharacterRow();
      triggerAutoSave();
    });

    toggleNarration.addEventListener('change', () => {
      updateVoiceVisibility();
      triggerAutoSave();
    });

    toggleMusic.addEventListener('change', triggerAutoSave);
    toggleKeepAudioLow.addEventListener('change', triggerAutoSave);

    toggleApproval.addEventListener('change', () => {
      updateApprovalWarning();
      triggerAutoSave();
    });

    // Big Buttons
    btnRunJob.addEventListener('click', () => runJob(false));

    btnCheckGflow.addEventListener('click', runGflowCheck);
    btnOpenJobsFolder.addEventListener('click', () => openFolder(inputOutputRoot.value.trim()));

    // Terminal Controls
    btnStartSession.addEventListener('click', () => executeTerminalAction('start'));
    btnStopSession.addEventListener('click', () => executeTerminalAction('stop'));
    btnRestartSession.addEventListener('click', () => executeTerminalAction('restart'));
    btnClearTerminal.addEventListener('click', () => {
      if (term) term.clear();
      executeTerminalAction('clear');
    });

    // Monitor Controls
    btnOpenCurrentJobFolder.addEventListener('click', () => openFolder(activeJobPath));
    btnResendPrompt.addEventListener('click', () => {
      if (activeJobPath) resendPrompt(activeJobPath);
    });
    btnRefreshHistory.addEventListener('click', loadJobHistory);

    // Modals
    btnCloseGflowModal.addEventListener('click', () => modalGflow.classList.add('hidden'));
    btnCloseGflowModalBtn.addEventListener('click', () => modalGflow.classList.add('hidden'));
    btnCopyGflowResult.addEventListener('click', () => {
      navigator.clipboard.writeText(gflowModalContent.innerText).then(() => {
        alert('Diagnostics copied to clipboard!');
      });
    });

    btnCancelConfirm.addEventListener('click', () => modalConfirm.classList.add('hidden'));
    btnDismissConfirm.addEventListener('click', () => modalConfirm.classList.add('hidden'));
    btnProceedConfirm.addEventListener('click', () => {
      modalConfirm.classList.add('hidden');
      runJob(true);
    });

    btnCloseClipModal.addEventListener('click', () => {
      clipModalPlayer.pause();
      modalClipPreview.classList.add('hidden');
    });
    btnCloseClipModalBtn.addEventListener('click', () => {
      clipModalPlayer.pause();
      modalClipPreview.classList.add('hidden');
    });

    // Sidebar Collapse and Toggle Buttons
    if (btnCollapseLeft) btnCollapseLeft.addEventListener('click', () => toggleLeftSidebar(true));
    if (btnRestoreLeft) btnRestoreLeft.addEventListener('click', () => toggleLeftSidebar(false));
    if (btnToggleSettingsTop) btnToggleSettingsTop.addEventListener('click', () => toggleLeftSidebar());

    if (btnCollapseRight) btnCollapseRight.addEventListener('click', () => toggleRightSidebar(true));
    if (btnRestoreRight) btnRestoreRight.addEventListener('click', () => toggleRightSidebar(false));
    if (btnToggleMonitorTop) btnToggleMonitorTop.addEventListener('click', () => toggleRightSidebar());

    // Focus terminal when clicking inside terminal container
    if (terminalContainer) {
      terminalContainer.addEventListener('click', () => {
        if (term) term.focus();
      });
    }
  }

  // --- Helpers ---
  function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function formatDate(isoStr) {
    if (!isoStr) return '';
    try {
      const d = new Date(isoStr);
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return isoStr;
    }
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
