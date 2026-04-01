const hud = document.getElementById("hud");
const centerBody = document.querySelector(".center-body");
console.log("main.js loaded successfully");

document.addEventListener("DOMContentLoaded", () => {
  console.log("DOM fully loaded");
  const ramEl = document.getElementById("ramValue");
  console.log("RAM element found:", ramEl ? "Yes" : "No");
});

if (typeof qt === "undefined") {
  console.warn("QtWebChannel not loaded - running in fallback mode");
} else {
  console.log("QtWebChannel loaded");
  document.documentElement.classList.add("qt-embed");
}

const IS_QT_EMBED = document.documentElement.classList.contains("qt-embed");
const PREFERS_REDUCED_MOTION = Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
const LOW_POWER_MODE = IS_QT_EMBED || PREFERS_REDUCED_MOTION;

const systemState = document.getElementById("systemState");
const clockValue = document.getElementById("clockValue");
const ramValue = document.getElementById("ramValue");
const ramFill = document.getElementById("ramFill");
const wifiValue = document.getElementById("wifiValue");
const downValue = document.getElementById("downValue");
const upValue = document.getElementById("upValue");
const dateDay = document.getElementById("dateDay");
const dateMonth = document.getElementById("dateMonth");
const avatarButton = document.getElementById("avatarButton");
const avatarInput = document.getElementById("avatarInput");
const playPause = document.getElementById("playPause");
const prevTrack = document.getElementById("prevTrack");
const nextTrack = document.getElementById("nextTrack");
const shutdownBtn = document.getElementById("shutdownBtn");
const restartBtn = document.getElementById("restartBtn");
const mediaCurrent = document.getElementById("mediaCurrent");
const mediaTotal = document.getElementById("mediaTotal");
const mediaProgressFill = document.getElementById("mediaProgressFill");
const reactorCoreBtn = document.getElementById("reactorCoreBtn");
const reactorFxCanvas = document.getElementById("reactorFxCanvas");
const chatPanel = document.getElementById("chatPanel");
const chatCloseBtn = document.getElementById("chatCloseBtn");
const workflowPanel = document.getElementById("workflowPanel");
const workflowCloseBtn = document.getElementById("workflowCloseBtn");
const aiAgentBtn = document.getElementById("aiAgentBtn");
const mapPanel = document.getElementById("mapPanel");
const mapCloseBtn = document.getElementById("mapCloseBtn");
const mapRoadBtn = document.getElementById("mapRoadBtn");
const mapSatelliteBtn = document.getElementById("mapSatelliteBtn");
const cameraPanel = document.getElementById("cameraPanel");
const cameraCloseBtn = document.getElementById("cameraCloseBtn");
const cameraFeed = document.getElementById("cameraFeed");
const authPanel = document.getElementById("authPanel");
const authNotice = document.getElementById("authNotice");
const authFaceManualUnlockBtn = document.getElementById("authFaceManualUnlockBtn");
const profileAuthSettings = document.getElementById("profileAuthSettings");
const profileAuthSetupBtn = document.getElementById("profileAuthSetupBtn");
const profileFaceUnlockBtn = document.getElementById("profileFaceUnlockBtn");
const profileFaceAddBtn = document.getElementById("profileFaceAddBtn");
const profileFaceRemoveBtn = document.getElementById("profileFaceRemoveBtn");
const orbitalCameraBtn = document.getElementById("orbitalCameraBtn");
const gpsMapFrame = document.getElementById("gpsMapFrame");
const map3dCanvas = document.getElementById("map3dCanvas");
const gpsStatus = document.getElementById("gpsStatus");
const gpsLat = document.getElementById("gpsLat");
const gpsLon = document.getElementById("gpsLon");
const gpsAcc = document.getElementById("gpsAcc");
const chatLog = document.getElementById("chatLog");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");
const commandFeed = document.getElementById("commandFeed");
const parsedCommandList = document.getElementById("parsedCommandList");
const liveNewsTicker = document.getElementById("liveNewsTicker");
const liveWeatherValue = document.getElementById("liveWeatherValue");
const liveSuggestionsList = document.getElementById("liveSuggestionsList");
const quickImageBtn = document.getElementById("quickImageBtn");
const quickSearchBtn = document.getElementById("quickSearchBtn");
const quickClassifyBtn = document.getElementById("quickClassifyBtn");
const searchPanel = document.getElementById("searchPanel");
const searchProgress = document.getElementById("searchProgress");
const searchResults = document.getElementById("searchResults");
const imageGenPanel = document.getElementById("imageGenPanel");
const imageGrid = document.getElementById("imageGrid");
const genStatus = document.getElementById("genStatus");
const micToggleBtn = document.getElementById("micToggleBtn");
const voiceMuteBtn = document.getElementById("voiceMuteBtn");
const micStatus = document.getElementById("micStatus");
const orbitLayer = document.getElementById("orbitLayer");
const notifList = document.getElementById("notifList");
const activeNotifBar = document.getElementById("activeNotifBar");
const anbIcon = document.getElementById("anbIcon");
const anbTag = document.getElementById("anbTag");
const anbTitle = document.getElementById("anbTitle");
const anbBody = document.getElementById("anbBody");

if (chatPanel) {
  chatPanel.hidden = true;
}

if (workflowPanel) {
  workflowPanel.hidden = true;
}

if (cameraPanel) {
  cameraPanel.hidden = true;
}

let isOnline = true;
let ramLevel = 24;
let trackIndex = 0;
let isPlaying = false;
let elapsedSeconds = 0;
let avatarImageUrl;
let jarvisBridge = null;
let micEnabled = false;
let speechRecognition = null;
let speechListening = false;
let backendMicPollTimer = null;
let backendSttInFlight = false;
let liveAssistantPartial = "";
let liveAssistantNode = null;
let micLiveState = "idle";
let lastBackendFinalTranscript = "";
let lastBackendSttError = "";
let lastBackendSttErrorAt = 0;
let reactorState = "idle";
let reactorStateTimer = null;
let reactorSpeedMultiplier = 1;
let voiceMuted = false;
let audioCtx = null;
let humOscA = null;
let humOscB = null;
let humGainNode = null;
let humStarted = false;
let reactorFxCtx = null;
let reactorFxBurstSeed = 0;
let reactorFxBursts = [];
let reactorFxLoopId = null;
let gpsWatchId = null;
let cameraStream = null;
let mapMode = "road";
let map3d = null;
let mapConfig = null;
let mapConfigRequested = false;
const AVATAR_STORAGE_KEY = "jarvis.avatar.dataurl";
let authLocked = true;
let authSetupRequired = false;
let authInProgress = false;
let authHasFace = false;
let authFaceFailed = false;
let authProgressPollTimer = null;
let autoFaceUnlockInFlight = false;
let autoFaceLastAttemptMs = 0;
let authRefreshInFlight = false;
let systemStatsInFlight = false;
let perfMonitor = null;
let notificationIndex = 0;

const NOTIF_SEVERITY_ORDER = {
  info: 1,
  success: 2,
  important: 3,
  critical: 4,
};

const normalizeSeverity = (raw, item = null) => {
  const key = String(raw || item?.severity || item?.priority || item?.level || "").trim().toLowerCase();
  if (["critical", "error", "alert", "fatal", "high"].includes(key)) {
    return "critical";
  }
  if (["important", "warning", "warn", "medium"].includes(key)) {
    return "important";
  }
  if (["success", "ok", "done", "completed"].includes(key)) {
    return "success";
  }
  if (item?.urgent) {
    return "critical";
  }
  const text = `${item?.title || ""} ${item?.message || ""} ${item?.body || ""} ${item?.tag || ""}`.toLowerCase();
  if (["failed", "denied", "security", "error", "critical"].some((kw) => text.includes(kw))) {
    return "critical";
  }
  if (["reminder", "pending", "warning", "soon"].some((kw) => text.includes(kw))) {
    return "important";
  }
  if (["sent", "completed", "success", "done"].some((kw) => text.includes(kw))) {
    return "success";
  }
  return "info";
};

const maxSeverity = (a, b) => (NOTIF_SEVERITY_ORDER[a] >= NOTIF_SEVERITY_ORDER[b] ? a : b);

const severityLabel = (severity) => {
  if (severity === "critical") {
    return "CRITICAL";
  }
  if (severity === "important") {
    return "IMPORTANT";
  }
  if (severity === "success") {
    return "SUCCESS";
  }
  return "INFO";
};

const {
  EventManager,
  registerInterval,
  registerTimeout,
  clearManagedTimers,
} = window.JarvisRuntimeUtils;

const lazyLoadModules = {
  map: null,
  reactor: null,
  camera: null,
};

const AUTH_PROGRESS_POLL_MS = LOW_POWER_MODE ? 2500 : 2000;
const AUTH_BOOT_POLL_MS = LOW_POWER_MODE ? 1200 : 600;
const SYSTEM_STATS_POLL_MS = 3000;
const MEDIA_TICK_MS = 1000;
const BACKEND_STT_POLL_MS = LOW_POWER_MODE ? 1000 : 900;
const AUTO_FACE_UNLOCK_ENABLED = false;
const AUTO_CAMERA_PREVIEW_ON_LOCK = false;
let lastGpsPosition = {
  latitude: 23.8103,
  longitude: 90.4125,
};

const toastHost = document.createElement("div");
toastHost.className = "toast-host";
document.body.appendChild(toastHost);

const buttonCommands = {
  photoshop: "open gimp",
  premiere: "open youtube",
  terminal: "open terminal",
  "vs code": "open vscode",
  discord: "open discord",
  libreoffice: "open libreoffice",
  chrome: "open chrome",
  steam: "open steam",
  spotify: "open spotify",
  "epic games": "open epic games",
  firefox: "open firefox web",
  downloads: "open downloads",
  documents: "open documents",
  pictures: "open pictures",
  music: "open music",
  videos: "open videos",
  mail: "open mail",
  google: "open google",
  openai: "open openai",
  deepseek: "open deepseek",
  grok: "open grok",
  wikipedia: "open wikipedia",
  "google calendar": "open google calendar",
  reminder: "open reminders",
  notes: "open notes",
  "google drive": "open google drive",
  "x (twitter)": "open twitter",
  outlook: "open outlook",
  instagram: "open instagram",
  linkedin: "open linkedin",
  facebook: "open facebook",
};

const tracks = [
  { duration: 168 },
  { duration: 202 },
  { duration: 194 },
];

const NEWS_BRIEFINGS = [
  "AI market update: edge copilots adopted across enterprise support desks.",
  "Security advisory: keep browser and GPU drivers patched this week.",
  "Productivity tip: chain commands with 'and then' for multi-action runs.",
  "System status: automation plugins loaded and ready.",
];

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = String(seconds % 60).padStart(2, "0");
  return `${mins}:${secs}`;
};

const renderTrackUi = () => {
  if (!mediaCurrent || !mediaTotal || !mediaProgressFill || !playPause) {
    return;
  }

  const duration = tracks[trackIndex].duration;
  const progress = Math.min(100, (elapsedSeconds / duration) * 100);

  mediaCurrent.textContent = formatTime(elapsedSeconds);
  mediaTotal.textContent = formatTime(duration);
  mediaProgressFill.style.width = `${progress}%`;
  playPause.innerHTML = isPlaying ? "&#10074;&#10074;" : "&#9654;";
  playPause.setAttribute("aria-label", isPlaying ? "Pause" : "Play");
};

const changeTrack = (direction) => {
  trackIndex = (trackIndex + direction + tracks.length) % tracks.length;
  elapsedSeconds = 0;
  renderTrackUi();
};

const togglePlayback = () => {
  isPlaying = !isPlaying;
  renderTrackUi();
};

const showToast = (message, kind = "info") => {
  if (!message) {
    return;
  }
  const normalizedKind = normalizeSeverity(kind);
  const toast = document.createElement("div");
  toast.className = `toast toast-${normalizedKind}`;
  toast.textContent = String(message);
  toastHost.appendChild(toast);
  setTimeout(() => toast.classList.add("show"), 20);
  setTimeout(() => {
    toast.classList.remove("show");
    setTimeout(() => toast.remove(), 220);
  }, 2400);
};

const ensureAudioContext = () => {
  const AudioCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtor) {
    return null;
  }
  if (!audioCtx) {
    audioCtx = new AudioCtor();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume().catch(() => {});
  }
  return audioCtx;
};

const startReactorHum = () => {
  const ctx = ensureAudioContext();
  if (!ctx || humStarted) {
    return;
  }

  humGainNode = ctx.createGain();
  humGainNode.gain.value = 0.008;
  humGainNode.connect(ctx.destination);

  humOscA = ctx.createOscillator();
  humOscA.type = "sine";
  humOscA.frequency.value = 46;
  humOscA.connect(humGainNode);

  humOscB = ctx.createOscillator();
  humOscB.type = "triangle";
  humOscB.frequency.value = 92;
  humOscB.connect(humGainNode);

  humOscA.start();
  humOscB.start();
  humStarted = true;
};

const playTone = (frequency, durationMs, type = "sine", gain = 0.04) => {
  const ctx = ensureAudioContext();
  if (!ctx) {
    return;
  }
  const osc = ctx.createOscillator();
  const gainNode = ctx.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(frequency, ctx.currentTime);
  gainNode.gain.setValueAtTime(gain, ctx.currentTime);
  gainNode.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + durationMs / 1000);
  osc.connect(gainNode);
  gainNode.connect(ctx.destination);
  osc.start();
  osc.stop(ctx.currentTime + durationMs / 1000);
};

const playUiSound = (name) => {
  if (voiceMuted) {
    return;
  }
  if (name === "click") {
    playTone(780, 70, "triangle", 0.02);
    return;
  }
  if (name === "listen") {
    playTone(560, 90, "sine", 0.035);
    setTimeout(() => playTone(760, 110, "sine", 0.03), 70);
    return;
  }
  if (name === "success") {
    playTone(660, 100, "sine", 0.035);
    setTimeout(() => playTone(880, 140, "triangle", 0.04), 100);
    return;
  }
  if (name === "error") {
    playTone(180, 120, "sawtooth", 0.045);
    setTimeout(() => playTone(140, 160, "square", 0.04), 80);
  }
};

const addClickRipple = (event) => {
  const target = event.currentTarget;
  if (!(target instanceof HTMLElement)) {
    return;
  }
  target.classList.add("ripple-host");
  const rect = target.getBoundingClientRect();
  const ripple = document.createElement("span");
  ripple.className = "click-ripple";
  ripple.style.left = `${event.clientX - rect.left}px`;
  ripple.style.top = `${event.clientY - rect.top}px`;
  target.appendChild(ripple);
  setTimeout(() => ripple.remove(), 500);
};

const resizeReactorFxCanvas = () => {
  if (!reactorFxCanvas) {
    return;
  }
  const rect = reactorFxCanvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  reactorFxCanvas.width = Math.max(1, Math.floor(rect.width * dpr));
  reactorFxCanvas.height = Math.max(1, Math.floor(rect.height * dpr));
  if (reactorFxCtx) {
    reactorFxCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
};

const emitReactorBurst = (intensity = 1, color = "cyan") => {
  reactorFxBurstSeed += 1;
  reactorFxBursts.push({
    id: reactorFxBurstSeed,
    radius: 0,
    speed: 3.5 + Math.random() * 3.1 * Math.max(0.6, intensity),
    alpha: Math.min(1, 0.35 + 0.4 * intensity),
    color,
  });
  if (reactorFxBursts.length > 16) {
    reactorFxBursts = reactorFxBursts.slice(-16);
  }
};

const _fxColor = (name, alpha = 0.4) => {
  if (name === "error") {
    return `rgba(255,77,77,${alpha})`;
  }
  if (name === "success") {
    return `rgba(0,255,136,${alpha})`;
  }
  if (name === "amber") {
    return `rgba(245,156,35,${alpha})`;
  }
  return `rgba(29,227,255,${alpha})`;
};

const startReactorFxLoop = () => {
  if (!reactorFxCanvas) {
    return;
  }
  if (!reactorFxCtx) {
    reactorFxCtx = reactorFxCanvas.getContext("2d");
    resizeReactorFxCanvas();
  }
  if (!reactorFxCtx || reactorFxLoopId) {
    return;
  }

  const tick = () => {
    if (!reactorFxCtx || !reactorFxCanvas) {
      reactorFxLoopId = null;
      return;
    }

    const w = reactorFxCanvas.clientWidth;
    const h = reactorFxCanvas.clientHeight;
    const cx = w / 2;
    const cy = h / 2;
    const maxR = Math.min(w, h) * 0.5;
    const t = performance.now() * 0.002;

    reactorFxCtx.clearRect(0, 0, w, h);

    if (reactorState === "executing") {
      const rays = 22;
      for (let i = 0; i < rays; i += 1) {
        const angle = (Math.PI * 2 * i) / rays + t;
        const inner = maxR * 0.2;
        const outer = maxR * (0.45 + 0.35 * Math.abs(Math.sin(t * 1.7 + i)));
        const x1 = cx + Math.cos(angle) * inner;
        const y1 = cy + Math.sin(angle) * inner;
        const x2 = cx + Math.cos(angle) * outer;
        const y2 = cy + Math.sin(angle) * outer;
        const grad = reactorFxCtx.createLinearGradient(x1, y1, x2, y2);
        grad.addColorStop(0, _fxColor("cyan", 0.03));
        grad.addColorStop(1, _fxColor("cyan", 0.42));
        reactorFxCtx.strokeStyle = grad;
        reactorFxCtx.lineWidth = 1 + 1.5 * Math.abs(Math.sin(t * 2 + i));
        reactorFxCtx.beginPath();
        reactorFxCtx.moveTo(x1, y1);
        reactorFxCtx.lineTo(x2, y2);
        reactorFxCtx.stroke();
      }
    }

    reactorFxBursts = reactorFxBursts.filter((b) => b.radius < maxR * 1.1 && b.alpha > 0.01);
    reactorFxBursts.forEach((burst) => {
      burst.radius += burst.speed;
      burst.alpha *= 0.965;
      reactorFxCtx.strokeStyle = _fxColor(burst.color, burst.alpha);
      reactorFxCtx.lineWidth = 1.6;
      reactorFxCtx.beginPath();
      reactorFxCtx.arc(cx, cy, burst.radius, 0, Math.PI * 2);
      reactorFxCtx.stroke();
    });

    reactorFxLoopId = requestAnimationFrame(tick);
  };

  reactorFxLoopId = requestAnimationFrame(tick);
};

const setReactorState = (state) => {
  const target = String(state || "idle").toLowerCase();
  const reactor = document.getElementById("reactorSystem");
  if (!reactor) {
    return;
  }

  reactor.classList.remove("state-idle", "state-listening", "state-processing", "state-thinking", "state-executing", "state-success", "state-error");
  reactor.classList.add(`state-${target}`);
  reactorState = target;

  const speedMap = {
    idle: 1,
    listening: 1.35,
    thinking: 2.2,
    executing: 2.9,
    processing: 2.35,
    success: 1.15,
    error: 0.8,
  };
  reactorSpeedMultiplier = speedMap[target] || 1;

  if (target === "listening") {
    emitReactorBurst(0.8, "cyan");
  } else if (target === "thinking") {
    emitReactorBurst(0.9, "amber");
  } else if (target === "executing") {
    emitReactorBurst(1.2, "cyan");
  } else if (target === "success") {
    emitReactorBurst(1.4, "success");
  } else if (target === "error") {
    emitReactorBurst(1.5, "error");
  }

  if (reactorStateTimer) {
    clearTimeout(reactorStateTimer);
    reactorStateTimer = null;
  }
  if (target === "success" || target === "error") {
    reactorStateTimer = setTimeout(() => {
      setReactorState("idle");
    }, 1000);
  }
};

const pushFeedEntry = (text, level = "info") => {
  if (!commandFeed) {
    return;
  }
  const entry = document.createElement("div");
  const style = ["pending", "success", "error"].includes(level) ? level : "";
  entry.className = `feed-entry${style ? ` ${style}` : ""}`;
  entry.textContent = String(text || "");
  commandFeed.appendChild(entry);
  commandFeed.scrollTop = commandFeed.scrollHeight;
};

const renderParsedCommands = (parsedPayload) => {
  if (!parsedCommandList) {
    return;
  }
  parsedCommandList.innerHTML = "";

  const parsed = parsedPayload && typeof parsedPayload === "object" ? parsedPayload : {};
  const commands = parsed.action === "multi" && Array.isArray(parsed.commands)
    ? parsed.commands
    : [parsed];

  if (!commands.length || !commands[0]?.action) {
    const row = document.createElement("li");
    row.textContent = "No command parsed yet.";
    parsedCommandList.appendChild(row);
    return;
  }

  commands.forEach((cmd, index) => {
    const action = String(cmd?.action || "unknown").replace(/_/g, " ");
    const target = String(
      cmd?.app_name
      || cmd?.website
      || cmd?.query
      || cmd?.url
      || cmd?.text
      || cmd?.keys
      || cmd?.command
      || ""
    );
    const row = document.createElement("li");
    row.textContent = `${index + 1}. ${action.replace(/\b\w/g, (c) => c.toUpperCase())}${target ? ` -> ${target}` : ""}`;
    parsedCommandList.appendChild(row);
  });
};

const updateLiveSuggestions = (parsedPayload) => {
  if (!liveSuggestionsList) {
    return;
  }

  const parsed = parsedPayload && typeof parsedPayload === "object" ? parsedPayload : {};
  const commands = parsed.action === "multi" && Array.isArray(parsed.commands)
    ? parsed.commands
    : [parsed];

  const suggestions = [];
  const nowHour = new Date().getHours();
  let historicalHint = "";

  try {
    const raw = window.localStorage.getItem("jarvis.command.patterns") || "{}";
    const patterns = JSON.parse(raw);
    const hourBucket = patterns?.[String(nowHour)] || {};
    let topAction = "";
    let topCount = 0;
    Object.entries(hourBucket).forEach(([key, count]) => {
      const numeric = Number(count) || 0;
      if (numeric > topCount) {
        topCount = numeric;
        topAction = key;
      }
    });
    if (topAction) {
      historicalHint = `You usually open ${topAction} at this time`;
    }
  } catch (_error) {
  }

  commands.forEach((cmd) => {
    const action = String(cmd?.action || "");
    if (action === "open_app") {
      suggestions.push("Try follow-up: open it again");
    }
    if (action === "search_web") {
      suggestions.push("Try follow-up: find latest headlines");
    }
    if (action === "unknown") {
      suggestions.push("Try: open browser example.com");
      suggestions.push("Try: list apps");
    }
  });

  if (!suggestions.length) {
    suggestions.push("Try: open chrome and search AI news");
    suggestions.push("Try: turn on bluetooth");
  }

  if (historicalHint) {
    suggestions.unshift(historicalHint);
  }

  liveSuggestionsList.innerHTML = "";
  suggestions.slice(0, 3).forEach((item) => {
    const row = document.createElement("li");
    row.textContent = item;
    liveSuggestionsList.appendChild(row);
  });
};

const rememberCommandPattern = (parsedPayload) => {
  const parsed = parsedPayload && typeof parsedPayload === "object" ? parsedPayload : {};
  const commands = parsed.action === "multi" && Array.isArray(parsed.commands)
    ? parsed.commands
    : [parsed];
  const hour = String(new Date().getHours());

  try {
    const raw = window.localStorage.getItem("jarvis.command.patterns") || "{}";
    const store = JSON.parse(raw);
    if (!store[hour]) {
      store[hour] = {};
    }
    commands.forEach((cmd) => {
      if (String(cmd?.action || "") !== "open_app") {
        return;
      }
      const app = String(cmd?.app_name || "").trim().toLowerCase();
      if (!app) {
        return;
      }
      store[hour][app] = (Number(store[hour][app]) || 0) + 1;
    });
    window.localStorage.setItem("jarvis.command.patterns", JSON.stringify(store));
  } catch (_error) {
  }
};

const JarvisUI = {
  reactor_state(state) {
    setReactorState(state);
  },

  show_parsed(parsed) {
    renderParsedCommands(parsed);
    updateLiveSuggestions(parsed);
  },

  show_result(result) {
    const output = String(result || "").trim();
    if (!output) {
      return;
    }
    output.split("\n").filter(Boolean).forEach((line) => {
      const lower = line.toLowerCase();
      const level = lower.includes("failed") || lower.includes("unknown") ? "error" : "success";
      pushFeedEntry(` ${line}`, level);
    });
  },

  add_to_feed(text) {
    pushFeedEntry(text, "pending");
  },

  play_sound(name) {
    playUiSound(name);
  },
};

const startTypingIndicator = () => {
  if (!commandFeed) {
    return () => {};
  }
  const entry = document.createElement("div");
  entry.className = "feed-entry pending";
  entry.textContent = "Understanding";
  commandFeed.appendChild(entry);
  commandFeed.scrollTop = commandFeed.scrollHeight;
  let tick = 0;
  const interval = setInterval(() => {
    tick = (tick + 1) % 4;
    entry.textContent = `Understanding${".".repeat(tick)}`;
  }, 180);
  return () => {
    clearInterval(interval);
    entry.remove();
  };
};

class JarvisController {
  constructor(ui) {
    this.ui = ui;
  }

  async handle_input(user_input) {
    const clean = String(user_input || "").trim();
    if (!clean) {
      return;
    }

    this.ui.add_to_feed(`> ${clean}`);
    this.ui.reactor_state("listening");
    this.ui.play_sound("listen");
    const stopTyping = startTypingIndicator();

    const parsedResponse = await runBridgeResult("parseAutomationStatus", [clean]);
    stopTyping();
    if (!parsedResponse?.ok) {
      const message = parsedResponse?.message || "Parser unavailable";
      this.ui.show_result(message);
      this.ui.play_sound("error");
      this.ui.reactor_state("error");
      return;
    }

    this.ui.show_parsed(parsedResponse.parsed || {});
    rememberCommandPattern(parsedResponse.parsed || {});
    this.ui.reactor_state("thinking");
    await new Promise((resolve) => setTimeout(resolve, 90));
    this.ui.reactor_state("executing");

    const payload = JSON.stringify(parsedResponse.parsed || {});
    const execResponse = await runBridgeResult("executeParsedAutomationStatus", [payload]);
    if (!execResponse?.ok) {
      const message = execResponse?.message || "Execution failed";
      this.ui.show_result(message);
      this.ui.play_sound("error");
      this.ui.reactor_state("error");
      return;
    }

    this.ui.show_result(execResponse.result_text || execResponse.message || "Done");
    if (execResponse.status === "error") {
      this.ui.play_sound("error");
      this.ui.reactor_state("error");
    } else {
      this.ui.play_sound("success");
      this.ui.reactor_state("success");
    }
  }
}

const jarvisController = new JarvisController(JarvisUI);

const isTextInputTarget = (target) => {
  const el = target instanceof Element ? target : null;
  if (!el) {
    return false;
  }
  const tag = String(el.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") {
    return true;
  }
  return el.isContentEditable || Boolean(el.closest("[contenteditable='true']"));
};

const ORBIT_SOURCES = [
  { id: "gmail", label: "GMAIL", icon: "MAIL", color: "#EA4335", command: "open gmail", ring: "inner", angle: 330 },
  { id: "whatsapp", label: "WHATSAPP", icon: "CHAT", color: "#25D366", command: "open whatsapp", ring: "inner", angle: 30 },
  { id: "reminder", label: "REMINDER", icon: "ALRT", color: "#F59C23", command: null, ring: "inner", angle: 150 },
  { id: "instagram", label: "INSTAGRAM", icon: "CAM", color: "#E1306C", command: "open instagram", ring: "inner", angle: 210 },
  { id: "linkedin", label: "LINKEDIN", icon: "BIZ", color: "#0A66C2", command: "open linkedin", ring: "outer", angle: 0 },
  { id: "facebook", label: "FACEBOOK", icon: "SOC", color: "#1877F2", command: "open facebook", ring: "outer", angle: 60 },
  { id: "messenger", label: "MESSENGER", icon: "MSG", color: "#0084FF", command: "open messenger", ring: "outer", angle: 120 },
  { id: "outlook", label: "OUTLOOK", icon: "CAL", color: "#0072C6", command: "open outlook", ring: "outer", angle: 200 },
  { id: "discord", label: "DISCORD", icon: "CHAT", color: "#5865F2", command: "open discord", ring: "outer", angle: 280 },
  { id: "twitter", label: "X / TWI", icon: "NEWS", color: "#1DA1F2", command: "open twitter", ring: "outer", angle: 340 },
];

const ORBIT_RADIUS_INNER = 0.18;
const ORBIT_RADIUS_OUTER = 0.96;
const ORBIT_ROTATION_INNER_SPD = 28;
const ORBIT_ROTATION_OUTER_SPD = 44;
const ORBIT_POLL_MS = 8000;
const ORBIT_MAX_TEXT = 72;
const ORBIT_BASE_SPEED_MIN = 16;
const ORBIT_BASE_SPEED_MAX = 26;

const _orbitState = {
  notifData: {},
  nodes: {},
  nodePhysics: {},
  activeSourceId: null,
  innerAngle: 0,
  outerAngle: 0,
  lastRaf: 0,
  rafId: null,
  initialized: false,
  uiScale: 1,
  reactorCyanArc: null,
  reactorAmberArc: null,
  camOrangeArc: null,
  camThinArc: null,
  camSweepArc: null,
  camSpin: 0,
};

const ORBIT_NODE_DRIFT = {
  jitter: 9.5,
  damping: 0.993,
  maxSpeed: ORBIT_BASE_SPEED_MAX + 7,
};

const _fallbackUrls = {
  "open gmail": "https://mail.google.com",
  "open whatsapp": "https://web.whatsapp.com",
  "open instagram": "https://www.instagram.com",
  "open linkedin": "https://www.linkedin.com",
  "open facebook": "https://www.facebook.com",
  "open messenger": "https://www.messenger.com",
  "open outlook": "https://outlook.live.com",
  "open discord": "https://discord.com/app",
  "open twitter": "https://x.com",
};

const _normalizeSourceId = (raw) => {
  const key = String(raw || "system").trim().toLowerCase();
  const map = {
    mail: "gmail",
    email: "gmail",
    googlemail: "gmail",
    wa: "whatsapp",
    ig: "instagram",
    insta: "instagram",
    fb: "facebook",
    meta: "facebook",
    msg: "messenger",
    x: "twitter",
    twit: "twitter",
    tiktok: "twitter",
    calendar: "outlook",
    teams: "outlook",
  };
  return map[key] || key;
};

const _truncateOrbitText = (text) => {
  const value = String(text || "").trim();
  if (!value) {
    return "";
  }
  if (value.length <= ORBIT_MAX_TEXT) {
    return value;
  }
  return `${value.slice(0, ORBIT_MAX_TEXT - 1)}…`;
};

const _clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const _randomInRange = (min, max) => min + Math.random() * (max - min);

const _computeUiScale = () => {
  const size = _getSystemSize();
  return _clamp(size / 860, 0.58, 1);
};

const _computeFloatBounds = () => {
  const size = _getSystemSize();
  const half = size / 2;
  const noFly = _getReactorNoFlyRadius();
  return {
    minR: noFly * 1.03,
    maxR: ORBIT_RADIUS_OUTER * half,
  };
};

const _getReactorNoFlyRadius = () => {
  const half = _getSystemSize() / 2;
  // Keep notification nodes clear of the reactor assembly and core rings.
  return half * 0.66;
};

const _seedFloatingNodes = () => {
  const { minR, maxR } = _computeFloatBounds();
  const minSep = 190 * _orbitState.uiScale;
  const placed = [];

  for (const src of ORBIT_SOURCES) {
    let x = 0;
    let y = 0;
    let placedOk = false;

    for (let i = 0; i < 120; i += 1) {
      const theta = _randomInRange(0, Math.PI * 2);
      const radius = _randomInRange(minR, maxR);
      const tx = Math.cos(theta) * radius;
      const ty = Math.sin(theta) * radius;

      const hasOverlap = placed.some((p) => {
        const dx = tx - p.x;
        const dy = ty - p.y;
        return Math.sqrt(dx * dx + dy * dy) < minSep;
      });

      if (!hasOverlap) {
        x = tx;
        y = ty;
        placedOk = true;
        break;
      }
    }

    if (!placedOk) {
      const theta = _randomInRange(0, Math.PI * 2);
      const radius = _randomInRange(minR, maxR);
      x = Math.cos(theta) * radius;
      y = Math.sin(theta) * radius;
    }

    const velocityAngle = _randomInRange(0, Math.PI * 2);
    const speed = _randomInRange(ORBIT_BASE_SPEED_MIN, ORBIT_BASE_SPEED_MAX);

    _orbitState.nodePhysics[src.id] = {
      x,
      y,
      vx: Math.cos(velocityAngle) * speed,
      vy: Math.sin(velocityAngle) * speed,
    };
    placed.push({ x, y });
  }
};

const _applyFloatPhysics = (dt) => {
  const ids = ORBIT_SOURCES.map((src) => src.id);
  const { minR, maxR } = _computeFloatBounds();
  const maxSpeed = ORBIT_NODE_DRIFT.maxSpeed;
  const noFlyRadius = _getReactorNoFlyRadius();
  const half = _getSystemSize() / 2;
  const exclusionX = half * 0.38;
  const exclusionY = half * 0.70;

  ids.forEach((id) => {
    const p = _orbitState.nodePhysics[id];
    if (!p) {
      return;
    }

    p.x += p.vx * dt;
    p.y += p.vy * dt;

    // Free-roam motion: tiny randomized drift so nodes move independently
    // instead of following a fixed orbital lane.
    p.vx += _randomInRange(-ORBIT_NODE_DRIFT.jitter, ORBIT_NODE_DRIFT.jitter) * dt;
    p.vy += _randomInRange(-ORBIT_NODE_DRIFT.jitter, ORBIT_NODE_DRIFT.jitter) * dt;

    const r = Math.sqrt(p.x * p.x + p.y * p.y) || 1;
    const nx = p.x / r;
    const ny = p.y / r;
    const radialVelocity = p.vx * nx + p.vy * ny;

    // Hard no-fly zone: nodes are never allowed to overlap the reactor core area.
    if (r < noFlyRadius) {
      p.x = nx * noFlyRadius;
      p.y = ny * noFlyRadius;
      const outwardBoost = Math.max(12, noFlyRadius - r);
      p.vx += nx * outwardBoost;
      p.vy += ny * outwardBoost;
    }

    if (r > maxR) {
      p.x = nx * maxR;
      p.y = ny * maxR;
      if (radialVelocity > 0) {
        p.vx -= 2 * radialVelocity * nx;
        p.vy -= 2 * radialVelocity * ny;
      }
    } else if (r < minR) {
      p.x = nx * minR;
      p.y = ny * minR;
      if (radialVelocity < 0) {
        p.vx -= 2 * radialVelocity * nx;
        p.vy -= 2 * radialVelocity * ny;
      }
    }

    // Keep nodes from collapsing toward the no-fly boundary while preserving free roaming.
    if (r < minR * 1.12) {
      const pushOut = (minR * 1.12 - r) * 2.1;
      p.vx += nx * pushOut * dt;
      p.vy += ny * pushOut * dt;
    }

    // Keep a clear lane on the right side for reactor-side option labels.
    if (p.x > exclusionX && Math.abs(p.y) < exclusionY) {
      const push = ((p.x - exclusionX) / Math.max(1, half)) * 48;
      p.vx -= push * dt;
      p.x -= push * dt;
    }
  });

  const separation = 170 * _orbitState.uiScale;
  for (let i = 0; i < ids.length; i += 1) {
    for (let j = i + 1; j < ids.length; j += 1) {
      const a = _orbitState.nodePhysics[ids[i]];
      const b = _orbitState.nodePhysics[ids[j]];
      if (!a || !b) {
        continue;
      }
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      let dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 0.001) {
        dx = 1;
        dy = 0;
        dist = 1;
      }

      if (dist < separation) {
        const overlap = (separation - dist) * 0.5;
        const ux = dx / dist;
        const uy = dy / dist;
        a.x -= ux * overlap;
        a.y -= uy * overlap;
        b.x += ux * overlap;
        b.y += uy * overlap;

        a.vx -= ux * 6;
        a.vy -= uy * 6;
        b.vx += ux * 6;
        b.vy += uy * 6;
      }
    }
  }

  ids.forEach((id) => {
    const p = _orbitState.nodePhysics[id];
    if (!p) {
      return;
    }
    p.vx *= ORBIT_NODE_DRIFT.damping;
    p.vy *= ORBIT_NODE_DRIFT.damping;
    const speed = Math.sqrt(p.vx * p.vx + p.vy * p.vy);
    if (speed > maxSpeed) {
      const ratio = maxSpeed / speed;
      p.vx *= ratio;
      p.vy *= ratio;
    }
  });
};

const _fetchOrbitNotifs = () => {
  const used = withBridge((bridge) => {
    if (typeof bridge.getNotifications !== "function") {
      _applyFallbackNotifs();
      return;
    }
    bridge.getNotifications((raw) => {
      try {
        const list = JSON.parse(raw);
        _ingestNotifList(list);
      } catch (_error) {
        _applyFallbackNotifs();
      }
    });
  });
  if (!used) {
    _applyFallbackNotifs();
  }
};

const _ingestNotifList = (list) => {
  if (!Array.isArray(list)) {
    return;
  }
  const grouped = {};
  for (const item of list) {
    const src = _normalizeSourceId(item?.source || item?.tag || "system");
    if (!grouped[src]) {
      grouped[src] = { count: 0, preview: "", severity: "info" };
    }
    const sev = normalizeSeverity(item?.severity, item);
    grouped[src].severity = maxSeverity(grouped[src].severity, sev);
    if (!item?.read) {
      grouped[src].count += 1;
      if (!grouped[src].preview) {
        grouped[src].preview = _truncateOrbitText(item?.title || item?.message || item?.body || "");
      }
    }
  }
  _orbitState.notifData = grouped;
  _refreshNodeLabels();
  _refreshNotifList();
};

const _applyFallbackNotifs = () => {
  _orbitState.notifData = {
    gmail: { count: 3, preview: "New email received", severity: "info" },
    whatsapp: { count: 7, preview: "7 unread messages", severity: "important" },
    reminder: { count: 1, preview: "Team standup at 3 PM", severity: "important" },
    instagram: { count: 12, preview: "12 new likes", severity: "success" },
    linkedin: { count: 2, preview: "2 connection requests", severity: "info" },
    outlook: { count: 1, preview: "Meeting: Project Review", severity: "important" },
    discord: { count: 5, preview: "5 mentions in #general", severity: "critical" },
    facebook: { count: 0, preview: "", severity: "info" },
    messenger: { count: 2, preview: "Hey, are you free?", severity: "info" },
    twitter: { count: 8, preview: "8 new notifications", severity: "info" },
  };
  _refreshNodeLabels();
  _refreshNotifList();
};

const _createNode = (src) => {
  const node = document.createElement("button");
  node.type = "button";
  node.id = `_onode_${src.id}`;
  node.setAttribute("aria-label", `${src.label} notifications`);
  node.style.cssText = `
    position:absolute;
    left:50%;
    top:50%;
    pointer-events:auto;
    cursor:pointer;
    background:linear-gradient(180deg, rgba(13,19,35,0.94), rgba(9,14,28,0.92));
    border:1px solid ${src.color}55;
    padding:10px 13px;
    min-width:220px;
    max-width:300px;
    clip-path:polygon(6px 0%,100% 0%,calc(100% - 6px) 100%,0% 100%);
    transition:border-color 0.2s, box-shadow 0.2s, transform 0.2s;
    z-index:5;
    font-family:var(--mono, monospace);
    text-align:left;
    will-change:transform;
    outline:none;
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
  `;
  node.innerHTML = `
    <span class="_on-top" style="display:flex;align-items:center;justify-content:space-between;gap:8px;line-height:1;">
      <span class="_on-icon" style="font-size:14px;color:${src.color};">${src.icon}</span>
      <span class="_on-count" style="font-size:28px;font-weight:700;color:#dde8f3;">-</span>
    </span>
    <span class="_on-preview" style="font-size:18px;font-weight:700;color:#f2f7ff;display:block;line-height:1.15;margin-top:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"></span>
    <span class="_on-meta" style="font-size:11px;letter-spacing:0.1em;color:rgba(221,232,243,0.62);display:block;margin-top:7px;text-transform:uppercase;"></span>
  `;

  node.addEventListener("mouseenter", () => {
    node.style.borderColor = src.color;
    node.style.boxShadow = `0 0 14px ${src.color}55, inset 0 0 8px ${src.color}11`;
    _showActiveBar(src);
  });

  node.addEventListener("mouseleave", () => {
    const data = _orbitState.notifData[src.id] || { count: 0 };
    node.style.borderColor = data.count > 0 ? `${src.color}88` : `${src.color}33`;
    node.style.boxShadow = data.count > 0 ? `0 0 8px ${src.color}33` : "";
    _orbitState.activeSourceId = null;
  });

  node.addEventListener("click", () => _handleNodeClick(src));
  return node;
};

const _getSystemSize = () => {
  const sys = document.getElementById("reactorSystem");
  return sys ? sys.offsetWidth : 400;
};

const _positionNode = (src) => {
  const node = _orbitState.nodes[src.id];
  const line = _orbitState.nodes[`${src.id}_line`];
  const p = _orbitState.nodePhysics[src.id];
  if (!node) {
    return;
  }

  if (!p) {
    return;
  }

  node.style.transform = `translate(calc(${p.x}px - 50%), calc(${p.y}px - 50%)) scale(${_orbitState.uiScale})`;

  if (line) {
    const dist = Math.sqrt(p.x * p.x + p.y * p.y);
    const lineAngle = (Math.atan2(p.y, p.x) * 180) / Math.PI;
    line.style.height = `${dist * 0.72}px`;
    line.style.transform = `rotate(${lineAngle + 90}deg)`;
  }
};

const _repositionOrbitNodes = () => {
  ORBIT_SOURCES.forEach((src) => _positionNode(src));
};

const _buildOrbitSystem = () => {
  if (!orbitLayer || _orbitState.initialized) {
    return;
  }

  const system = document.getElementById("reactorSystem");
  if (!system) {
    return;
  }

  _orbitState.initialized = true;
  orbitLayer.innerHTML = "";
  orbitLayer.style.pointerEvents = "none";

  // Fallback-driven arc rotation keeps reactor visuals moving reliably in Qt embeds.
  _orbitState.reactorCyanArc = document.querySelector(".r-cyan");
  _orbitState.reactorAmberArc = document.querySelector(".r-amber");
  _orbitState.camOrangeArc = document.querySelector(".cam-orange");
  _orbitState.camThinArc = document.querySelector(".cam-thin");
  _orbitState.camSweepArc = document.querySelector(".cam-sweep");
  if (_orbitState.reactorCyanArc) {
    _orbitState.reactorCyanArc.style.animation = "none";
  }
  if (_orbitState.reactorAmberArc) {
    _orbitState.reactorAmberArc.style.animation = "none";
  }
  if (_orbitState.camOrangeArc) {
    _orbitState.camOrangeArc.style.animation = "none";
  }
  if (_orbitState.camThinArc) {
    _orbitState.camThinArc.style.animation = "none";
  }
  if (_orbitState.camSweepArc) {
    _orbitState.camSweepArc.style.animation = "none";
  }

  const freeLayer = document.createElement("div");
  freeLayer.id = "_orbitFreeLayer";
  freeLayer.style.cssText = "position:absolute;inset:0;border-radius:50%;will-change:transform;contain:layout style paint;";
  orbitLayer.appendChild(freeLayer);

  _orbitState.uiScale = _computeUiScale();
  _seedFloatingNodes();

  for (const src of ORBIT_SOURCES) {
    const node = _createNode(src);
    freeLayer.appendChild(node);
    _orbitState.nodes[src.id] = node;

    const line = document.createElement("div");
    line.className = "_orbit-connector";
    line.id = `_conn_${src.id}`;
    line.style.cssText = `
      position:absolute;
      left:50%;
      top:50%;
      width:2px;
      background:linear-gradient(180deg, ${src.color}08, ${src.color}99);
      transform-origin:0 0;
      pointer-events:none;
      transition:background 0.3s, box-shadow 0.3s;
      filter: drop-shadow(0 0 4px ${src.color}66);
      box-shadow: 0 0 10px ${src.color}33;
    `;
    freeLayer.appendChild(line);
    _orbitState.nodes[`${src.id}_line`] = line;
  }

  _repositionOrbitNodes();
  _fetchOrbitNotifs();
  registerInterval(_fetchOrbitNotifs, ORBIT_POLL_MS);
  _startOrbitAnim();
};

const _startOrbitAnim = () => {
  if (_orbitState.rafId) {
    return;
  }

  _orbitState.lastRaf = performance.now();
  const tick = (now) => {
    const dt = (now - _orbitState.lastRaf) / 1000;
    _orbitState.lastRaf = now;

    _orbitState.innerAngle = (_orbitState.innerAngle + (360 / ORBIT_ROTATION_INNER_SPD) * dt * reactorSpeedMultiplier) % 360;
    _orbitState.outerAngle = (_orbitState.outerAngle - (360 / ORBIT_ROTATION_OUTER_SPD) * dt * reactorSpeedMultiplier + 360) % 360;
    _orbitState.camSpin = (_orbitState.camSpin + dt * 48) % 360;

    _applyFloatPhysics(dt);

    if (_orbitState.reactorCyanArc) {
      _orbitState.reactorCyanArc.style.transform = `rotate(${(_orbitState.innerAngle * 1.9) % 360}deg)`;
    }
    if (_orbitState.reactorAmberArc) {
      _orbitState.reactorAmberArc.style.transform = `rotate(${(-_orbitState.outerAngle * 2.4) % 360}deg)`;
    }
    if (_orbitState.camOrangeArc) {
      _orbitState.camOrangeArc.style.transform = `rotate(${_orbitState.camSpin}deg)`;
    }
    if (_orbitState.camThinArc) {
      _orbitState.camThinArc.style.transform = `rotate(${-_orbitState.camSpin * 1.25}deg)`;
    }
    if (_orbitState.camSweepArc) {
      _orbitState.camSweepArc.style.transform = `rotate(${_orbitState.camSpin * 2.1}deg)`;
    }

    _repositionOrbitNodes();
    _orbitState.rafId = requestAnimationFrame(tick);
  };

  _orbitState.rafId = requestAnimationFrame(tick);
};

const _stopOrbitAnim = () => {
  if (_orbitState.rafId) {
    cancelAnimationFrame(_orbitState.rafId);
    _orbitState.rafId = null;
  }
};

const _refreshNodeLabels = () => {
  for (const src of ORBIT_SOURCES) {
    const node = _orbitState.nodes[src.id];
    if (!node) {
      continue;
    }
    const data = _orbitState.notifData[src.id] || { count: 0, preview: "" };
    const severity = normalizeSeverity(data.severity, data);
    const countEl = node.querySelector("._on-count");
    const previewEl = node.querySelector("._on-preview");
    const metaEl = node.querySelector("._on-meta");
    if (countEl) {
      countEl.textContent = data.count > 0 ? String(data.count) : "-";
      countEl.style.color = data.count > 0 ? src.color : "rgba(221,232,243,0.3)";
    }
    if (previewEl) {
      previewEl.textContent = data.preview || "No new notifications";
    }
    if (metaEl) {
      metaEl.textContent = data.count > 0
        ? `${severityLabel(severity)} • ${data.count} unread notification${data.count > 1 ? "s" : ""}`
        : "No unread notifications";
    }

    node.dataset.unread = data.count > 0 ? "true" : "false";

    const line = _orbitState.nodes[`${src.id}_line`];
    if (line) {
      line.style.background = data.count > 0 ? `${src.color}66` : `${src.color}22`;
    }
    if (data.count > 0) {
      node.style.borderColor = `${src.color}88`;
      node.style.boxShadow = `0 0 8px ${src.color}33`;
    } else {
      node.style.borderColor = `${src.color}33`;
      node.style.boxShadow = "";
    }
  }
};

const _refreshNotifList = () => {
  if (!notifList) {
    return;
  }

  notifList.innerHTML = "";
  const activeSources = ORBIT_SOURCES.filter((src) => {
    const data = _orbitState.notifData[src.id] || { count: 0 };
    return (Number(data.count) || 0) > 0;
  });

  if (!activeSources.length) {
    const empty = document.createElement("div");
    empty.className = "notif-item notif-empty";
    empty.innerHTML = `
      <span class="ni-dot"></span>
      <span>No unread notifications</span>
      <span class="ni-tag">CLEAR</span>
    `;
    notifList.appendChild(empty);
    return;
  }

  activeSources.forEach((src) => {
    const data = _orbitState.notifData[src.id] || { count: 0, preview: "", severity: "info" };
    const severity = normalizeSeverity(data.severity, data);
    const row = document.createElement("div");
    row.className = `notif-item sev-${severity}`;
    row.tabIndex = 0;
    row.setAttribute("role", "button");
    row.setAttribute("aria-label", `${src.label} notifications`);
    row.innerHTML = `
      <span class="ni-dot"></span>
      <span>${data.preview || "No new notifications"}</span>
      <span class="ni-tag">${data.count > 0 ? `${severityLabel(severity)} • ${data.count}` : "CLEAR"}</span>
    `;
    row.addEventListener("mouseenter", () => _showActiveBar(src));
    row.addEventListener("click", () => _handleNodeClick(src));
    row.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        _handleNodeClick(src);
      }
    });
    notifList.appendChild(row);
  });
};

const _updateNotifHeadingBadge = (count) => {
  const heading = document.querySelector(".notif-section h3");
  if (!heading) {
    return;
  }
  const safeCount = Math.max(0, Number(count) || 0);
  heading.textContent = safeCount > 0 ? `NOTIFICATIONS (${safeCount})` : "NOTIFICATIONS";
};

const _pollOrbitNotificationCount = () => {
  const localUnread = ORBIT_SOURCES.reduce((sum, src) => {
    const data = _orbitState.notifData[src.id] || { count: 0 };
    return sum + (Number(data.count) || 0);
  }, 0);

  const used = withBridge((bridge) => {
    if (typeof bridge.notificationCount !== "function") {
      _updateNotifHeadingBadge(localUnread);
      return;
    }
    bridge.notificationCount((raw) => {
      _updateNotifHeadingBadge(parseInt(raw, 10));
    });
  });

  if (!used) {
    _updateNotifHeadingBadge(localUnread);
  }
};

const _showActiveBar = (src) => {
  if (!activeNotifBar) {
    return;
  }

  if (!src) {
    if (anbIcon) {
      anbIcon.textContent = "SYS";
    }
    if (anbTag) {
      anbTag.textContent = "SYSTEM";
    }
    if (anbTitle) {
      anbTitle.textContent = "No unread notifications";
    }
    if (anbBody) {
      anbBody.textContent = "Incoming alerts will appear here.";
    }
    activeNotifBar.style.borderColor = "rgba(255,183,0,0.3)";
    activeNotifBar.classList.remove("sev-critical", "sev-important", "sev-info", "sev-success");
    activeNotifBar.classList.add("sev-info");
    activeNotifBar.classList.remove("has-notif");
    _orbitState.activeSourceId = null;
    return;
  }

  const data = _orbitState.notifData[src.id] || { count: 0, preview: "", severity: "info" };
  const severity = normalizeSeverity(data.severity, data);
  if (anbIcon) {
    anbIcon.textContent = src.icon;
  }
  if (anbTag) {
    anbTag.textContent = data.count > 0 ? severityLabel(severity) : src.label;
  }
  if (anbTitle) {
    anbTitle.textContent = data.preview || "No new notifications";
  }
  if (anbBody) {
    anbBody.textContent = data.count > 0
      ? `${data.count} unread ${data.count > 1 ? "items" : "item"}`
      : "Click to open";
  }
  activeNotifBar.style.borderColor = data.count > 0 ? src.color : "rgba(255,183,0,0.3)";
  activeNotifBar.classList.remove("sev-critical", "sev-important", "sev-info", "sev-success");
  activeNotifBar.classList.add(`sev-${severity}`);
  activeNotifBar.classList.toggle("has-notif", data.count > 0);
  _orbitState.activeSourceId = src.id;
};

const _handleNodeClick = (src) => {
  const data = _orbitState.notifData[src.id] || {};
  const severity = normalizeSeverity(data.severity, data);

  if (src.id === "reminder") {
    if (typeof openWorkflowPanel === "function") {
      openWorkflowPanel();
    }
    showToast(`Opening reminders (${data.count || 0} pending)`, severity);
  } else if (src.command) {
    const used = runBridgeCommand(src.command);
    if (!used) {
      const fallback = _fallbackUrls[src.command];
      if (fallback) {
        openExternalUrl(fallback);
      }
    }
    showToast(`Opening ${src.label}`, severity === "critical" ? "important" : severity);
  }

  if (hasBridgeMethod("markNotificationRead")) {
    withBridge((bridge) => {
      bridge.markNotificationRead(src.id, () => {});
    });
  }

  if (_orbitState.notifData[src.id]) {
    _orbitState.notifData[src.id].count = 0;
  }
  _refreshNodeLabels();
  _refreshNotifList();
  const nextSource = ORBIT_SOURCES.find((item) => Number(_orbitState.notifData[item.id]?.count || 0) > 0);
  _showActiveBar(nextSource || null);
};

const renderOrbitNodes = () => {
  _orbitState.uiScale = _computeUiScale();
  _repositionOrbitNodes();
};

const initNotificationPanel = () => {
  _buildOrbitSystem();
  const firstSource = ORBIT_SOURCES.find((src) => Number(_orbitState.notifData[src.id]?.count || 0) > 0) || null;
  _showActiveBar(firstSource);
  _pollOrbitNotificationCount();
  registerInterval(_pollOrbitNotificationCount, ORBIT_POLL_MS);
};

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    _stopOrbitAnim();
    return;
  }
  if (_orbitState.initialized) {
    _startOrbitAnim();
  }
});

window.addEventListener("beforeunload", _stopOrbitAnim, { once: true });

class ConnectionManager {
  constructor() {
    this.retryCount = 0;
    this.maxRetries = 5;
    this.connected = false;
    this.pendingOperations = [];
  }

  async executeWithRetry(operation, context = "") {
    try {
      const result = await operation();
      this.retryCount = 0;
      this.connected = true;
      return result;
    } catch (error) {
      this.connected = false;
      if (this.retryCount < this.maxRetries) {
        this.retryCount += 1;
        const delay = 2 ** this.retryCount * 1000;
        showToast(`Retrying ${context} (${this.retryCount}/${this.maxRetries})...`, "warning");
        await new Promise((resolve) => {
          registerTimeout(resolve, delay);
        });
        return this.executeWithRetry(operation, context);
      }
      showToast(`${context} failed after ${this.maxRetries} attempts`, "error");
      throw error;
    }
  }

  queueOperation(operation) {
    if (this.connected) {
      operation();
      return;
    }
    this.pendingOperations.push(operation);
  }

  processQueue() {
    while (this.pendingOperations.length > 0) {
      const op = this.pendingOperations.shift();
      try {
        op();
      } catch (_error) {
      }
    }
  }
}

const eventManager = new EventManager();
const connectionManager = new ConnectionManager();
const inMemoryErrorLog = [];

function logError(error) {
  if (!error) {
    return;
  }
  const errorLog = {
    timestamp: new Date().toISOString(),
    message: String(error?.message || "Unknown error"),
    stack: String(error?.stack || ""),
    url: window.location.href,
  };
  inMemoryErrorLog.push(errorLog);
  if (inMemoryErrorLog.length > 20) {
    inMemoryErrorLog.shift();
  }
}

eventManager.addListener(window, "error", (event) => {
  console.error("Global error caught:", event.error || event.message);
  const msg = String(event?.error?.message || event?.message || "").toLowerCase();
  if (msg.includes("webgl")) {
    useMapFallback();
    showToast("3D map unavailable, using 2D fallback", "warning");
  }
  if (msg.includes("camera")) {
    showToast("Camera unavailable", "warning");
  }
  logError(event.error || new Error(String(event.message || "Unhandled error")));
});

const lazyLoadMap = () => {
  if (lazyLoadModules.map) {
    return Promise.resolve(lazyLoadModules.map);
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js";
    script.onload = () => {
      lazyLoadModules.map = window.maplibregl;
      resolve(window.maplibregl);
    };
    script.onerror = () => reject(new Error("Failed to load map module"));
    document.head.appendChild(script);
  });
};

const lazyLoadCamera = async () => {
  if (lazyLoadModules.camera) {
    return;
  }
  lazyLoadModules.camera = true;
};

const withBridge = (fn) => {
  if (!jarvisBridge || typeof fn !== "function") {
    return false;
  }
  try {
    fn(jarvisBridge);
    return true;
  } catch (_error) {
    return false;
  }
};

const runBridgeCommand = (command) => withBridge((bridge) => bridge.runCommand(command));

const hasBridgeMethod = (method) => Boolean(jarvisBridge && typeof jarvisBridge[method] === "function");

const parseBridgePayload = (raw) => {
  try {
    return JSON.parse(raw);
  } catch (_error) {
    return null;
  }
};

const parseBridgeStatus = (raw) => {
  try {
    const data = JSON.parse(raw);
    return {
      ok: Boolean(data?.ok),
      message: String(data?.message || "Done"),
    };
  } catch (_error) {
    return { ok: false, message: "Invalid bridge response" };
  }
};

const runBridgeResult = (method, args = []) =>
  new Promise((resolve) => {
    const used = withBridge((bridge) => {
      const fn = bridge?.[method];
      if (typeof fn !== "function") {
        resolve(null);
        return;
      }
      fn(...args, (raw) => {
        const data = parseBridgePayload(raw);
        resolve(data || null);
      });
    });
    if (!used) {
      resolve(null);
    }
  });

const updateSearchStatus = (text, progress = 0) => {
  if (searchPanel) {
    searchPanel.hidden = false;
  }
  if (searchProgress) {
    searchProgress.style.width = `${Math.max(0, Math.min(100, Number(progress) || 0))}%`;
  }
  if (typeof text === "string" && text) {
    showToast(text, "info");
  }
};

const displaySearchResults = (results = []) => {
  if (!searchResults) {
    return;
  }
  searchResults.innerHTML = "";
  const rows = Array.isArray(results) ? results : [];
  rows.forEach((item, index) => {
    const card = document.createElement("article");
    card.className = "search-card";

    const title = document.createElement("h4");
    title.textContent = `${index + 1}. ${String(item?.title || "Result")}`;

    const link = document.createElement("a");
    link.href = String(item?.url || "#");
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = String(item?.url || "");

    const snippet = document.createElement("p");
    snippet.textContent = String(item?.snippet || "");

    const source = document.createElement("small");
    source.textContent = `Source: ${String(item?.source || "unknown")}`;

    card.appendChild(title);
    card.appendChild(link);
    card.appendChild(snippet);
    card.appendChild(source);
    searchResults.appendChild(card);
  });
};

const createImageCard = (item) => {
  const wrap = document.createElement("article");
  wrap.className = "image-card";

  const img = document.createElement("img");
  img.loading = "lazy";
  img.alt = String(item?.prompt || "Generated image");
  img.src = String(item?.url || "");

  const meta = document.createElement("small");
  meta.textContent = `${String(item?.provider || "provider")} • ${String(item?.prompt || "")}`;

  wrap.appendChild(img);
  wrap.appendChild(meta);
  return wrap;
};

const displayGeneratedImages = (images = []) => {
  if (imageGenPanel) {
    imageGenPanel.hidden = false;
  }
  if (!imageGrid) {
    return;
  }
  imageGrid.innerHTML = "";
  const rows = Array.isArray(images) ? images : [];
  rows.forEach((item) => imageGrid.appendChild(createImageCard(item)));
};

const showIntentBadge = (intent, confidence = 0) => {
  const label = `Intent: ${String(intent || "general")} (${Number(confidence || 0).toFixed(2)})`;
  showToast(label, "success");
};

const bridgeCommands = {
  generateImage: async (prompt) => {
    if (genStatus) {
      genStatus.textContent = "Generating...";
    }
    const data = await runBridgeResult("generateImage", [String(prompt || "")]);
    if (!data?.ok) {
      if (genStatus) {
        genStatus.textContent = String(data?.message || "Generation failed");
      }
      showToast(String(data?.message || "Generation failed"), "error");
      return;
    }
    if (genStatus) {
      genStatus.textContent = `${String(data?.message || "Done")} via ${String(data?.provider || "provider")}`;
    }
    displayGeneratedImages(data?.images || []);
  },

  searchRealtime: async (query) => {
    updateSearchStatus("Searching...", 20);
    const data = await runBridgeResult("searchWithProgress", [String(query || "")]);
    if (!data?.ok) {
      updateSearchStatus(String(data?.message || "Search failed"), 0);
      showToast(String(data?.message || "Search failed"), "error");
      return;
    }
    updateSearchStatus("Search completed", Number(data?.progress || 100));
    displaySearchResults(data?.results || []);
  },

  classifyQuery: async (query) => {
    const data = await runBridgeResult("classifyQuery", [String(query || "")]);
    if (!data?.ok) {
      showToast(String(data?.message || "Classification failed"), "error");
      return null;
    }
    showIntentBadge(data?.intent, data?.confidence);
    return data;
  },
};

const setAuthNotice = (text) => {
  if (authNotice && text) {
    authNotice.textContent = String(text);
  }
};

const setBackendCameraNotice = (_active, _message = "") => {
  if (cameraFeed) {
    cameraFeed.hidden = false;
  }
};

const requestFaceUnlock = (notice = "Starting face authentication...") => {
  if (!authHasFace) {
    showToast("No enrolled face found. Run first setup.", "error");
    return;
  }
  if (authInProgress) {
    showToast("Face authentication already in progress", "warning");
    return;
  }

  // Keep camera panel visible for UX, but avoid browser preview stream while backend auth runs.
  openCameraPanel(false);
  stopCameraFeed();
  setAuthNotice(notice);
  runAuthAction("authCameraUnlockStatus");
};

const syncAuthControls = () => {
  if (profileAuthSetupBtn) {
    profileAuthSetupBtn.hidden = !authSetupRequired;
    profileAuthSetupBtn.disabled = authInProgress;
  }

  if (profileFaceUnlockBtn) {
    profileFaceUnlockBtn.disabled = authInProgress || !authHasFace;
  }

  if (profileFaceAddBtn) {
    profileFaceAddBtn.disabled = authInProgress || authLocked;
  }

  if (profileFaceRemoveBtn) {
    profileFaceRemoveBtn.disabled = authInProgress || authLocked || !authHasFace;
  }

  if (authFaceManualUnlockBtn) {
    authFaceManualUnlockBtn.disabled = authInProgress || !authHasFace;
  }
};

const triggerAutoFaceUnlock = async () => {
  if (!AUTO_FACE_UNLOCK_ENABLED) {
    return;
  }
  if (!authLocked || authSetupRequired || authInProgress || !authHasFace) {
    return;
  }
  if (autoFaceUnlockInFlight) {
    return;
  }
  if (!hasBridgeMethod("authCameraUnlockStatus")) {
    return;
  }
  const now = Date.now();
  if (now - autoFaceLastAttemptMs < 4000) {
    return;
  }

  autoFaceUnlockInFlight = true;
  autoFaceLastAttemptMs = now;
  if (cameraPanel && cameraPanel.hidden) {
    openCameraPanel(false);
  }
  stopCameraFeed();
  setAuthNotice("Scanning face to authenticate automatically...");
  const data = await runBridgeResult("authCameraUnlockStatus");
  if (data) {
    if (data.ok) {
      authFaceFailed = false;
      applyAuthStatusPayload(data);
      if (authInProgress) {
        startAuthProgressPolling();
        setAuthNotice("Scanning face to authenticate automatically...");
      } else if (!authLocked) {
        showToast(data.message || "Face authentication successful", "success");
        closeCameraPanel();
      }
    } else {
      authFaceFailed = true;
      syncAuthControls();
      setAuthNotice(data.message || "Face authentication failed.");
    }
  }
  autoFaceUnlockInFlight = false;
};

const applyAuthLockUi = () => {
  if (hud) {
    hud.classList.toggle("auth-locked", authLocked);
  }

  if (authPanel) {
    authPanel.hidden = !authLocked;
  }

};

const applyAuthStatusPayload = (data) => {
  if (!data || typeof data !== "object") {
    return;
  }

  const wasLocked = authLocked;
  authLocked = Boolean(data.locked ?? !data.authenticated);
  authSetupRequired = Boolean(data.setup_required);
  authHasFace = Boolean(data.has_face);
  authInProgress = Boolean(data.in_progress);
  if ((!wasLocked && authLocked) || !authLocked) {
    authFaceFailed = false;
  }
  setAuthNotice(data.message || (authSetupRequired ? "First setup required: face" : "Authenticate to unlock"));
  syncAuthControls();
  applyAuthLockUi();

  if (authLocked) {
    if (AUTO_CAMERA_PREVIEW_ON_LOCK) {
      openCameraPanel(false);
    }
    triggerAutoFaceUnlock();
    if (authSetupRequired) {
      openWorkflowPanel();
    }
  } else {
    setBackendCameraNotice(false);
    closeCameraPanel();
  }
};

const startAuthProgressPolling = () => {
  if (authProgressPollTimer) {
    return;
  }
  authProgressPollTimer = registerInterval(async () => {
    await refreshAuthStatus();
    if (!authInProgress) {
      clearInterval(authProgressPollTimer);
      authProgressPollTimer = null;
    }
  }, AUTH_PROGRESS_POLL_MS);
};

const refreshAuthStatus = async () => {
  if (authRefreshInFlight) {
    return;
  }
  authRefreshInFlight = true;
  const data = await runBridgeResult("authStatus");
  authRefreshInFlight = false;
  if (!data) {
    return;
  }
  applyAuthStatusPayload(data);
};

const runAuthAction = async (method, args = []) => {
  const data = await runBridgeResult(method, args);
  if (!data) {
    showToast("Authentication bridge unavailable", "error");
    return null;
  }

  if (!data.ok) {
    setAuthNotice(data.message || "Authentication failed");
    showToast(data.message || "Authentication failed", "error");
    return data;
  }

  applyAuthStatusPayload(data);
  if (authInProgress) {
    startAuthProgressPolling();
  }
  showToast(data.message || "Authentication updated", "success");
  if (!authLocked) {
    if (cameraPanel) {
      cameraPanel.hidden = true;
    }
    closeCameraPanel();
  }
  return data;
};

const installAuthInteractionGuard = () => {
  document.addEventListener(
    "click",
    (event) => {
      if (!authLocked) {
        return;
      }
      const target = event.target?.closest?.("button,a,input,textarea,select");
      if (!target) {
        return;
      }

      if (authPanel && authPanel.contains(target)) {
        return;
      }

      if (profileAuthSettings && profileAuthSettings.contains(target)) {
        return;
      }

      if (authSetupRequired && workflowPanel && workflowPanel.contains(target)) {
        return;
      }

      if (target.closest("[data-auth-control='true']")) {
        return;
      }

      event.preventDefault();
      event.stopImmediatePropagation();
      showToast("System locked. Authenticate first.", "error");
    },
    true,
  );
};

const getMapStyleUrl = (mode) => {
  if (!mapConfig) {
    return "";
  }

  if (mapConfig.provider === "demo" && mode === "satellite") {
    return {
      version: 8,
      sources: {
        esri: {
          type: "raster",
          tiles: ["https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
          tileSize: 256,
        },
      },
      layers: [
        {
          id: "esri-base",
          type: "raster",
          source: "esri",
        },
      ],
    };
  }

  return mode === "satellite" ? String(mapConfig.satellite_style || "") : String(mapConfig.road_style || "");
};

const useMapFallback = () => {
  if (map3dCanvas) {
    map3dCanvas.hidden = true;
  }
  if (gpsMapFrame) {
    gpsMapFrame.hidden = false;
  }
};

const applyMapTerrain = () => {
  if (!map3d || !mapConfig?.terrain_tiles) {
    return;
  }

  const terrainSourceId = "jarvis-terrain";
  if (!map3d.getSource(terrainSourceId)) {
    map3d.addSource(terrainSourceId, {
      type: "raster-dem",
      url: String(mapConfig.terrain_tiles),
      tileSize: 256,
      maxzoom: 14,
    });
  }

  map3d.setTerrain({ source: terrainSourceId, exaggeration: 1.45 });
};

const ensureMapConfig = async () => {
  if (mapConfigRequested) {
    return mapConfig;
  }

  mapConfigRequested = true;
  const configData = await runBridgeResult("mapConfigStatus");
  if (!configData?.ok || !configData?.road_style) {
    mapConfig = {
      ok: true,
      provider: "demo",
      message: "Using built-in demo WebGL map",
      road_style: "https://demotiles.maplibre.org/style.json",
      satellite_style: "",
      terrain_tiles: "",
    };
    showToast("Using demo WebGL map", "info");
    return mapConfig;
  }

  mapConfig = configData;
  return mapConfig;
};

const ensureWebGlMap = async () => {
  if (map3d) {
    return true;
  }

  if (!map3dCanvas) {
    useMapFallback();
    return false;
  }

  try {
    await lazyLoadMap();
  } catch (_error) {
    useMapFallback();
    return false;
  }

  if (!window.maplibregl) {
    useMapFallback();
    return false;
  }

  const cfg = await ensureMapConfig();
  if (!cfg) {
    useMapFallback();
    return false;
  }

  const styleUrl = getMapStyleUrl(mapMode);
  if (!styleUrl) {
    useMapFallback();
    return false;
  }

  map3dCanvas.hidden = false;
  if (gpsMapFrame) {
    gpsMapFrame.hidden = true;
  }

  map3d = await connectionManager.executeWithRetry(
    async () =>
      new window.maplibregl.Map({
        container: map3dCanvas,
        style: styleUrl,
        center: [lastGpsPosition.longitude, lastGpsPosition.latitude],
        zoom: 15,
        pitch: 68,
        bearing: -20,
        antialias: true,
      }),
    "map initialization",
  );

  map3d.addControl(new window.maplibregl.NavigationControl({ showCompass: true }), "top-right");

  map3d.on("load", () => {
    applyMapTerrain();
  });

  map3d.on("styledata", () => {
    try {
      applyMapTerrain();
    } catch (_error) {
    }
  });

  return true;
};

const runBridgeStatus = (method, args = [], fallbackMessage = "Bridge unavailable") => {
  const usedBridge = withBridge((bridge) => {
    const cb = (raw) => {
      const status = parseBridgeStatus(raw);
      showToast(status.message, status.ok ? "success" : "error");
    };
    const fn = bridge?.[method];
    if (typeof fn !== "function") {
      showToast(`Missing bridge method: ${method}`, "error");
      return;
    }
    fn(...args, cb);
  });

  if (!usedBridge) {
    showToast(fallbackMessage, "error");
  }
};

const applySystemStats = (stats) => {
  if (!stats || typeof stats !== "object") {
    return;
  }

  if (clockValue && typeof stats.time === "string") {
    clockValue.textContent = stats.time;
  }

  if (dateDay && typeof stats.day === "string") {
    dateDay.textContent = stats.day;
  }

  if (dateMonth && typeof stats.month === "string") {
    dateMonth.textContent = stats.month;
  }

  if (ramValue && ramFill && Number.isFinite(stats.ram_percent)) {
    const ramPercent = Math.max(0, Math.min(100, Math.round(stats.ram_percent)));
    ramValue.textContent = `${ramPercent}%`;
    ramFill.style.height = `${ramPercent}%`;
  }

  if (wifiValue) {
    wifiValue.textContent = String(stats.wifi_label || "Online");
  }

  if (downValue && Number.isFinite(stats.down_mbps)) {
    downValue.textContent = `${stats.down_mbps.toFixed(2)} Mbps`;
  }

  if (upValue && Number.isFinite(stats.up_mbps)) {
    upValue.textContent = `${stats.up_mbps.toFixed(2)} Mbps`;
  }

  setSystemState(Boolean(stats.online ?? true));
};

const pollSystemStats = () => {
  if (systemStatsInFlight) {
    return;
  }
  const usedBridge = withBridge((bridge) => {
    systemStatsInFlight = true;
    bridge.getSystemStats((raw) => {
      try {
        const stats = JSON.parse(raw);
        applySystemStats(stats);
      } catch (_error) {
      } finally {
        systemStatsInFlight = false;
      }
    });
  });

  if (!usedBridge) {
    systemStatsInFlight = false;
    updateNetworkStats();
  }
};

const initQtBridge = () => {
  const canInit = () => Boolean(window.qt?.webChannelTransport && window.QWebChannel);

  const setup = () => {
    if (!canInit()) {
      return false;
    }
    new window.QWebChannel(window.qt.webChannelTransport, (channel) => {
      jarvisBridge = channel.objects?.jarvisBridge || null;
      if (jarvisBridge) {
        showToast("Desktop bridge connected", "success");
      }
    });
    return true;
  };

  if (canInit()) {
    setup();
    return;
  }

  const script = document.createElement("script");
  script.src = "qrc:///qtwebchannel/qwebchannel.js";
  script.onload = () => {
    if (setup()) {
      return;
    }
    let attempts = 0;
    const timer = registerInterval(() => {
      attempts += 1;
      if (setup() || attempts >= 20) {
        clearInterval(timer);
      }
    }, 250);
  };
  script.onerror = () => {
    showToast("Bridge script failed to load", "error");
  };
  document.head.appendChild(script);

  let attempts = 0;
  const timer = registerInterval(() => {
    attempts += 1;
    if (setup() || attempts >= 20) {
      clearInterval(timer);
    }
  }, 250);
};

const openExternalUrl = (url) => {
  const targetUrl = String(url || "").trim();
  if (!targetUrl) {
    return false;
  }

  try {
    const popup = window.open(targetUrl, "_blank", "noopener,noreferrer");
    if (popup) {
      return true;
    }
  } catch (_error) {
  }

  try {
    window.location.href = targetUrl;
    return true;
  } catch (_error) {
    return false;
  }
};

const bindCommandButtons = () => {
  const buttons = document.querySelectorAll("button[data-command], button[data-url]");

  buttons.forEach((button) => {
    const directCommand = String(button.dataset.command || "").trim().toLowerCase();
    const directUrl = String(button.dataset.url || "").trim();
    const command = directCommand;

    if (!command && !directUrl) {
      return;
    }

    button.addEventListener("click", () => {
      playUiSound("click");
      if (command && hasBridgeMethod("runCommandStatus")) {
        runBridgeStatus("runCommandStatus", [command], "Action unavailable outside desktop app");
        return;
      }

      if (directUrl) {
        const opened = openExternalUrl(directUrl);
        if (opened) {
          showToast("Opened in browser", "success");
        }
        return;
      }

      if (command && !hasBridgeMethod("runCommandStatus")) {
        showToast("Action unavailable outside desktop app", "error");
      }
    });
  });
};

const bindWorkflowButtons = () => {
  const buttons = document.querySelectorAll(".wf-app-btn");

  buttons.forEach((button) => {
    const action = String(button.dataset.action || "").trim().toLowerCase();
    if (action === "open-map") {
      button.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        openMapPanel();
      });
      return;
    }

    const command = String(button.dataset.command || "").trim().toLowerCase();
    const url = String(button.dataset.url || "").trim();

    if (!command && !url) {
      return;
    }

    button.addEventListener("click", () => {
      playUiSound("click");
      if (command && hasBridgeMethod("runCommandStatus")) {
        runBridgeStatus("runCommandStatus", [command], "Action unavailable outside desktop app");
        return;
      }

      if (url) {
        const opened = openExternalUrl(url);
        if (opened) {
          showToast("Opened in browser", "success");
        }
        return;
      }

      if (command && !hasBridgeMethod("runCommandStatus")) {
        showToast("Action unavailable outside desktop app", "error");
      }
    });
  });
};

const installMicroInteractions = () => {
  const selectors = "button, .edge-btn, .shortcut-btn, .social-btn, .panel-btn, .command-btn, .wf-app-btn, .r-core";
  document.querySelectorAll(selectors).forEach((el) => {
    if (!(el instanceof HTMLElement)) {
      return;
    }
    el.classList.add("ripple-host");
    el.addEventListener("click", addClickRipple);
  });
};

const appendChatLine = (role, text) => {
  if (!chatLog || !text) {
    return;
  }
  const line = document.createElement("div");
  line.className = `chat-line ${role}`;
  line.textContent = text;
  chatLog.appendChild(line);
  chatLog.scrollTop = chatLog.scrollHeight;
  return line;
};

const upsertAssistantPartial = (text) => {
  if (!chatLog) {
    return;
  }
  const clean = String(text || "").trim();
  if (!clean) {
    return;
  }
  if (!liveAssistantNode) {
    liveAssistantNode = document.createElement("div");
    liveAssistantNode.className = "chat-line assistant";
    chatLog.appendChild(liveAssistantNode);
  }
  liveAssistantNode.textContent = `JARVIS: ${clean}`;
  chatLog.scrollTop = chatLog.scrollHeight;
};

const finalizeAssistantPartial = () => {
  if (!liveAssistantNode) {
    liveAssistantPartial = "";
    return;
  }
  liveAssistantNode = null;
  liveAssistantPartial = "";
};

const setMicUi = (enabled) => {
  micEnabled = enabled;

  if (micToggleBtn) {
    micToggleBtn.classList.toggle("is-on", enabled);
    micToggleBtn.setAttribute("aria-pressed", enabled ? "true" : "false");
    micToggleBtn.setAttribute("aria-label", enabled ? "Disable microphone" : "Enable microphone");
    micToggleBtn.textContent = enabled ? "🎤 MICROPHONE ON" : "🎤 MICROPHONE OFF";
  }

  if (micStatus) {
    micStatus.textContent = enabled ? "MIC ON" : "MIC OFF";
    micStatus.classList.toggle("on", enabled);
  }

  if (!enabled) {
    setMicLiveState("idle");
  }
};

const setVoiceMuteUi = (muted) => {
  voiceMuted = Boolean(muted);
  if (!voiceMuteBtn) {
    return;
  }

  voiceMuteBtn.classList.toggle("is-on", voiceMuted);
  voiceMuteBtn.setAttribute("aria-pressed", voiceMuted ? "true" : "false");
  voiceMuteBtn.setAttribute("aria-label", voiceMuted ? "Unmute voice output" : "Mute voice output");
  voiceMuteBtn.textContent = voiceMuted ? "🔇 VOICE MUTED" : "🔊 VOICE ON";
};

const syncVoiceMuteToBackend = () => {
  if (!hasBridgeMethod("conversationSetVoiceMutedStatus")) {
    return;
  }

  withBridge((bridge) => {
    bridge.conversationSetVoiceMutedStatus(Boolean(voiceMuted), (raw) => {
      const data = parseBridgePayload(raw);
      if (!data?.ok && data?.message) {
        showToast(String(data.message), "error");
      }
    });
  });
};

const setMicLiveState = (state, wakeWord = "hey jarvis") => {
  micLiveState = state || "idle";

  if (micLiveState === "listening") {
    setReactorState("listening");
  } else if (micLiveState === "speaking") {
    setReactorState("processing");
  } else if (micLiveState === "idle" && reactorState !== "processing") {
    setReactorState("idle");
  }

  if (micToggleBtn) {
    micToggleBtn.classList.remove("state-idle", "state-sleeping", "state-listening", "state-speaking");
    micToggleBtn.classList.add(`state-${micLiveState}`);
  }

  if (micStatus) {
    micStatus.classList.remove("state-idle", "state-sleeping", "state-listening", "state-speaking");
    micStatus.classList.add(`state-${micLiveState}`);

    if (!micEnabled || micLiveState === "idle") {
      micStatus.textContent = "MIC OFF";
      return;
    }

    if (micLiveState === "sleeping") {
      micStatus.textContent = `WAITING: ${String(wakeWord || "hey jarvis").toUpperCase()}`;
      return;
    }

    if (micLiveState === "listening") {
      micStatus.textContent = "LISTENING";
      return;
    }

    if (micLiveState === "speaking") {
      micStatus.textContent = "JARVIS SPEAKING";
      return;
    }

    micStatus.textContent = "MIC ON";
  }
};

const speakResponse = (text) => {
  if (!text || voiceMuted) {
    return;
  }

  if (hasBridgeMethod("speakStatus")) {
    withBridge((bridge) => {
      bridge.speakStatus(String(text), (raw) => {
        const data = parseBridgePayload(raw);
        if (!data?.ok && data?.message) {
          showToast(String(data.message), "error");
        }
      });
    });
    return;
  }

  if (!("speechSynthesis" in window)) {
    return;
  }

  const utterance = new SpeechSynthesisUtterance(String(text));
  utterance.rate = 1;
  utterance.pitch = 1;
  utterance.volume = 1;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(utterance);
};

const dispatchChatMessage = (text) => {
  const cleanText = String(text || "").trim();
  if (!cleanText) {
    return;
  }

  appendChatLine("user", `You: ${cleanText}`);

  if (cleanText.toLowerCase().startsWith("/image ")) {
    const prompt = cleanText.slice(7).trim();
    if (!prompt) {
      appendChatLine("assistant", "JARVIS: Provide an image prompt after /image");
      return;
    }
    bridgeCommands.generateImage(prompt);
    appendChatLine("assistant", `JARVIS: Generating image for '${prompt}'`);
    return;
  }

  if (cleanText.toLowerCase().startsWith("/search ")) {
    const query = cleanText.slice(8).trim();
    if (!query) {
      appendChatLine("assistant", "JARVIS: Provide a query after /search");
      return;
    }
    bridgeCommands.searchRealtime(query);
    appendChatLine("assistant", `JARVIS: Searching web for '${query}'`);
    return;
  }

  if (cleanText.toLowerCase().startsWith("/classify ")) {
    const query = cleanText.slice(10).trim();
    if (!query) {
      appendChatLine("assistant", "JARVIS: Provide text after /classify");
      return;
    }
    bridgeCommands.classifyQuery(query).then((result) => {
      if (result?.intent) {
        appendChatLine("assistant", `JARVIS: Classified as ${result.intent} (${Number(result.confidence || 0).toFixed(2)})`);
      }
    });
    return;
  }

  const lowered = cleanText.toLowerCase();
  if (["mute", "mute voice", "mute jarvis", "silent mode"].includes(lowered)) {
    setVoiceMuteUi(true);
    syncVoiceMuteToBackend();
    appendChatLine("assistant", "JARVIS: Voice muted. I will continue in chat.");
    showToast("Voice muted", "info");
    return;
  }

  if (["unmute", "unmute voice", "unmute jarvis", "speak again"].includes(lowered)) {
    setVoiceMuteUi(false);
    syncVoiceMuteToBackend();
    appendChatLine("assistant", "JARVIS: Voice unmuted.");
    showToast("Voice unmuted", "success");
    return;
  }

  if (hasBridgeMethod("conversationSubmitStatus") && micEnabled) {
    const usedBridge = withBridge((bridge) => {
      bridge.conversationSubmitStatus(cleanText, (raw) => {
        const data = parseBridgePayload(raw);
        if (!data?.ok) {
          const message = `JARVIS: ${data?.message || "Conversation submit failed"}`;
          appendChatLine("assistant", message);
          showToast(data?.message || "Conversation submit failed", "error");
        }
      });
    });

    if (!usedBridge) {
      appendChatLine("assistant", "JARVIS: Bridge unavailable in browser mode");
      showToast("Chat unavailable outside desktop app", "error");
    }
    return;
  }

  const usedBridge = withBridge((bridge) => {
    if (typeof bridge.askAssistant !== "function") {
      showToast("Chat API unavailable", "error");
      return;
    }
    bridge.askAssistant(cleanText, (raw) => {
      let data;
      try {
        data = JSON.parse(raw);
      } catch (_error) {
        const message = "JARVIS: Failed to parse response";
        appendChatLine("assistant", message);
        return;
      }

      if (!data?.ok) {
        const message = `JARVIS: ${data?.message || "Error"}`;
        appendChatLine("assistant", message);
        showToast(data?.message || "Chat failed", "error");
        return;
      }

      const responseText = String(data.response || "");
      appendChatLine("assistant", `JARVIS: ${responseText}`);
      speakResponse(responseText);
    });
  });

  if (!usedBridge) {
    const fallback = "JARVIS: Bridge unavailable in browser mode";
    appendChatLine("assistant", fallback);
    showToast("Chat unavailable outside desktop app", "error");
    speakResponse("Bridge unavailable in browser mode.");
  }
};

const getSpeechRecognitionCtor = () => window.SpeechRecognition || window.webkitSpeechRecognition || null;

const stopBackendVoiceInput = () => {
  if (backendMicPollTimer) {
    clearInterval(backendMicPollTimer);
    backendMicPollTimer = null;
  }
  backendSttInFlight = false;
};

const startBackendVoiceInput = () => {
  if (!hasBridgeMethod("sttStatus") && !hasBridgeMethod("conversationStatus")) {
    return false;
  }

  stopBackendVoiceInput();
  backendMicPollTimer = registerInterval(() => {
    if (!micEnabled || backendSttInFlight || (!hasBridgeMethod("sttStatus") && !hasBridgeMethod("conversationStatus"))) {
      return;
    }

    backendSttInFlight = true;
    withBridge((bridge) => {
      const onDone = (raw) => {
        backendSttInFlight = false;
        const data = parseBridgePayload(raw);
        if (!data || !data.ok) {
          if (data?.message && data.message !== "Microphone is muted") {
            showToast(String(data.message), "error");
          }
          return;
        }

        const state = String(data.state || "").trim().toLowerCase() || "listening";
        const wakeWord = String(data.wake_word || "hey jarvis");
        const sttError = String(data.stt_error || "").trim();
        setMicLiveState(state, wakeWord);

        if (sttError) {
          const now = Date.now();
          if (sttError !== lastBackendSttError || now - lastBackendSttErrorAt > 4000) {
            showToast(sttError, "error");
            lastBackendSttError = sttError;
            lastBackendSttErrorAt = now;
          }
        } else {
          lastBackendSttError = "";
          lastBackendSttErrorAt = 0;
        }

        if (data.wake_just_detected) {
          showToast(`Wake word detected: ${wakeWord}`, "success");
          setReactorState("listening");
          playUiSound("listen");
          emitReactorBurst(1.35, "cyan");
        }

        const transcript = String(data.transcript || "").trim();
        if (!transcript) {
          const partial = String(data.assistant_partial || "").trim();
          if (partial && partial !== liveAssistantPartial) {
            liveAssistantPartial = partial;
            upsertAssistantPartial(partial);
          }

          const chunks = Array.isArray(data.assistant_new_chunks) ? data.assistant_new_chunks : [];
          if (chunks.length > 0) {
            if (!liveAssistantNode) {
              const merged = chunks
                .map((chunk) => String(chunk || "").trim())
                .filter(Boolean)
                .join(" ");
              if (merged) {
                appendChatLine("assistant", `JARVIS: ${merged}`);
              }
            }
            finalizeAssistantPartial();
          }
          return;
        }

        if (chatInput) {
          chatInput.value = transcript;
        }
        if (transcript !== lastBackendFinalTranscript) {
          appendChatLine("user", `You: ${transcript}`);
          lastBackendFinalTranscript = transcript;
        }
        if (chatInput) {
          chatInput.value = "";
        }
      };

      if (typeof bridge.conversationStatus === "function") {
        bridge.conversationStatus(onDone);
      } else {
        bridge.sttStatus(onDone);
      }
    });
  }, BACKEND_STT_POLL_MS);

  return true;
};

const stopVoiceInput = () => {
  stopBackendVoiceInput();

  if (hasBridgeMethod("conversationInterruptStatus")) {
    withBridge((bridge) => {
      bridge.conversationInterruptStatus(() => {
      });
    });
  }

  if (speechRecognition) {
    try {
      speechRecognition.stop();
    } catch (_error) {
    }
  }
  speechListening = false;
};

const startVoiceInput = () => {
  if (hasBridgeMethod("micOnStatus") && hasBridgeMethod("sttStatus")) {
    withBridge((bridge) => {
      bridge.micOnStatus((_raw) => {
        startBackendVoiceInput();
      });
    });
    return;
  }

  const RecognitionCtor = getSpeechRecognitionCtor();
  if (!RecognitionCtor) {
    showToast("Speech recognition unsupported in this web view", "error");
    return;
  }

  if (!speechRecognition) {
    speechRecognition = new RecognitionCtor();
    speechRecognition.lang = "en-US";
    speechRecognition.continuous = true;
    speechRecognition.interimResults = false;

    speechRecognition.onstart = () => {
      speechListening = true;
    };

    speechRecognition.onend = () => {
      speechListening = false;
      if (micEnabled) {
        registerTimeout(() => {
          if (!micEnabled || speechListening || !speechRecognition) {
            return;
          }
          try {
            speechRecognition.start();
          } catch (_error) {
          }
        }, 350);
      }
    };

    speechRecognition.onerror = (event) => {
      const code = String(event?.error || "");
      if (code === "not-allowed" || code === "service-not-allowed") {
        setMicUi(false);
      }
      if (code && code !== "aborted") {
        showToast(`Mic error: ${code}`, "error");
      }
    };

    speechRecognition.onresult = (event) => {
      const resultIndex = event.resultIndex;
      const result = event.results?.[resultIndex];
      if (!result?.isFinal) {
        return;
      }
      const transcript = String(result[0]?.transcript || "").trim();
      if (!transcript) {
        return;
      }
      if (chatInput) {
        chatInput.value = transcript;
      }
      dispatchChatMessage(transcript);
      if (chatInput) {
        chatInput.value = "";
      }
    };
  }

  if (!speechListening) {
    try {
      speechRecognition.start();
    } catch (_error) {
    }
  }
};

const toggleMic = () => {
  const nextState = !micEnabled;
  setMicUi(nextState);

  if (nextState) {
    syncVoiceMuteToBackend();
    startVoiceInput();
  } else {
    if (hasBridgeMethod("micOffStatus")) {
      withBridge((bridge) => {
        bridge.micOffStatus(() => {
        });
      });
    }
    stopVoiceInput();
    finalizeAssistantPartial();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
    }
  }
};

const toggleVoiceMute = () => {
  const nextState = !voiceMuted;
  setVoiceMuteUi(nextState);
  syncVoiceMuteToBackend();
  showToast(nextState ? "Voice muted" : "Voice unmuted", "info");
};

const openChatPanel = () => {
  if (!chatPanel) {
    return;
  }
  chatPanel.hidden = false;
  if (chatInput) {
    chatInput.focus();
  }
};

const closeChatPanel = () => {
  if (!chatPanel) {
    return;
  }
  chatPanel.hidden = true;
};

const openWorkflowPanel = () => {
  if (!workflowPanel) {
    return;
  }

  closeMapPanel();
  closeCameraPanel();
  workflowPanel.hidden = false;
};

const closeWorkflowPanel = () => {
  if (!workflowPanel) {
    return;
  }
  workflowPanel.hidden = true;
};

const stopCameraFeed = () => {
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
  }
  cameraStream = null;

  if (cameraFeed) {
    cameraFeed.srcObject = null;
  }
};

const startCameraFeed = async () => {
  await lazyLoadCamera();
  if (!navigator.mediaDevices?.getUserMedia) {
    showToast("Camera unsupported in this environment", "error");
    return;
  }

  stopCameraFeed();

  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
      },
      audio: false,
    });

    if (cameraFeed) {
      cameraFeed.srcObject = cameraStream;
    }
  } catch (_error) {
    const reason = String(_error?.name || _error?.message || "permission denied");
    if (authLocked) {
      setAuthNotice("Scanning face to authenticate automatically...");
      return;
    }
    showToast(`Camera unavailable: ${reason}`, "error");
  }
};

const openCameraPanel = (startPreview = true) => {
  if (!cameraPanel) {
    return;
  }

  if (workflowPanel) {
    workflowPanel.hidden = true;
  }
  if (mapPanel) {
    mapPanel.hidden = true;
  }
  stopGpsTracking();

  cameraPanel.hidden = false;
  if (centerBody) {
    centerBody.classList.add("camera-open");
  }
  setBackendCameraNotice(false);
  if (startPreview) {
    lazyLoadCamera().then(() => {
      startCameraFeed();
    });
  } else {
    stopCameraFeed();
  }
};

const closeCameraPanel = () => {
  if (!cameraPanel) {
    return;
  }

  if (authLocked) {
    return;
  }

  cameraPanel.hidden = true;
  if (centerBody) {
    centerBody.classList.remove("camera-open");
  }
  stopCameraFeed();
  setBackendCameraNotice(false);
};

const setMapModeUi = (mode) => {
  const isRoad = mode === "road";

  if (mapRoadBtn) {
    mapRoadBtn.classList.toggle("is-active", isRoad);
    mapRoadBtn.setAttribute("aria-pressed", isRoad ? "true" : "false");
  }

  if (mapSatelliteBtn) {
    mapSatelliteBtn.classList.toggle("is-active", !isRoad);
    mapSatelliteBtn.setAttribute("aria-pressed", !isRoad ? "true" : "false");
  }
};

const setMapMode = (mode) => {
  if (mode !== "road" && mode !== "satellite") {
    return;
  }

  mapMode = mode;
  setMapModeUi(mapMode);
  if (map3d && mapConfig) {
    const styleUrl = getMapStyleUrl(mapMode);
    if (styleUrl) {
      map3d.setStyle(styleUrl);
    }
  }
  updateMapEmbed(lastGpsPosition.latitude, lastGpsPosition.longitude);
};

const updateMapEmbed = (latitude, longitude) => {
  if (!gpsMapFrame || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    return;
  }

  lastGpsPosition = {
    latitude,
    longitude,
  };

  if (map3d) {
    map3d.easeTo({
      center: [longitude, latitude],
      duration: 750,
      essential: true,
    });
  }

  const mapTypeCode = mapMode === "satellite" ? "k" : "m";
  gpsMapFrame.src = `https://maps.google.com/maps?q=${latitude.toFixed(6)},${longitude.toFixed(6)}&z=15&t=${mapTypeCode}&output=embed`;
};

const stopGpsTracking = () => {
  if (gpsWatchId !== null && navigator.geolocation) {
    navigator.geolocation.clearWatch(gpsWatchId);
  }
  gpsWatchId = null;
};

const startGpsTracking = () => {
  if (!navigator.geolocation) {
    if (gpsStatus) {
      gpsStatus.textContent = "GPS not supported";
    }
    showToast("Geolocation unsupported in this environment", "error");
    return;
  }

  stopGpsTracking();

  if (gpsStatus) {
    gpsStatus.textContent = "Locating…";
  }

  gpsWatchId = navigator.geolocation.watchPosition(
    (position) => {
      const latitude = Number(position.coords?.latitude);
      const longitude = Number(position.coords?.longitude);
      const accuracy = Number(position.coords?.accuracy);

      if (gpsStatus) {
        gpsStatus.textContent = "GPS Active";
      }
      if (gpsLat && Number.isFinite(latitude)) {
        gpsLat.textContent = latitude.toFixed(5);
      }
      if (gpsLon && Number.isFinite(longitude)) {
        gpsLon.textContent = longitude.toFixed(5);
      }
      if (gpsAcc && Number.isFinite(accuracy)) {
        gpsAcc.textContent = `${Math.round(accuracy)} m`;
      }

      updateMapEmbed(latitude, longitude);
    },
    (_error) => {
      if (gpsStatus) {
        gpsStatus.textContent = "GPS blocked";
      }
      showToast("Location permission denied or unavailable", "error");
    },
    {
      enableHighAccuracy: true,
      maximumAge: 5000,
      timeout: 12000,
    },
  );
};

const openMapPanel = () => {
  if (!mapPanel) {
    return;
  }

  if (workflowPanel) {
    workflowPanel.hidden = true;
  }
  closeCameraPanel();
  mapPanel.hidden = false;
  startGpsTracking();
  ensureWebGlMap().then((ok) => {
    if (gpsStatus) {
      gpsStatus.textContent = ok ? "3D Map Active" : "Fallback map active";
    }
  });
};

const closeMapPanel = () => {
  if (!mapPanel) {
    return;
  }
  mapPanel.hidden = true;
  stopGpsTracking();
};

const sendChatMessage = () => {
  if (authLocked) {
    showToast("System locked. Authenticate first.", "error");
    return;
  }
  const text = (chatInput?.value || "").trim();
  if (!text) {
    return;
  }
  if (chatInput) {
    chatInput.value = "";
  }
  dispatchChatMessage(text);
};

const runQuickSlashCommand = (prefix, promptLabel, emptyMessage) => {
  if (authLocked) {
    showToast("System locked. Authenticate first.", "error");
    return;
  }
  const raw = window.prompt(promptLabel, "");
  if (raw === null) {
    return;
  }
  const value = String(raw || "").trim();
  if (!value) {
    showToast(emptyMessage, "warning");
    return;
  }
  openChatPanel();
  dispatchChatMessage(`${prefix} ${value}`);
};

const openAvatarPicker = () => {
  if (avatarInput) {
    // Allow selecting the same file again and still trigger change event.
    avatarInput.value = "";
    avatarInput.click();
  }
};

const _loadImageFromDataUrl = (dataUrl) =>
  new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Failed to load image"));
    img.src = dataUrl;
  });

const _downscaleAvatarDataUrl = async (dataUrl) => {
  const img = await _loadImageFromDataUrl(dataUrl);
  const maxSide = 320;
  const scale = Math.min(1, maxSide / Math.max(img.width || 1, img.height || 1));
  const width = Math.max(1, Math.round(img.width * scale));
  const height = Math.max(1, Math.round(img.height * scale));

  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    return dataUrl;
  }

  ctx.drawImage(img, 0, 0, width, height);
  // JPEG keeps payload small enough for reliable localStorage persistence.
  return canvas.toDataURL("image/jpeg", 0.82);
};

const updateAvatarPreview = (event) => {
  if (!avatarButton) {
    return;
  }

  const file = event.target?.files?.[0];

  if (!file) {
    return;
  }

  if (!String(file.type || "").startsWith("image/")) {
    showToast("Please select an image file", "error");
    return;
  }

  const reader = new FileReader();
  reader.onload = async () => {
    const rawDataUrl = String(reader.result || "");
    if (!rawDataUrl) {
      return;
    }

    let dataUrl = rawDataUrl;
    try {
      dataUrl = await _downscaleAvatarDataUrl(rawDataUrl);
    } catch (_error) {
      dataUrl = rawDataUrl;
    }

    avatarImageUrl = dataUrl;
    avatarButton.style.backgroundImage = `url("${dataUrl}")`;
    avatarButton.classList.add("has-image");
    try {
      window.localStorage.setItem(AVATAR_STORAGE_KEY, dataUrl);
    } catch (_error) {
      showToast("Avatar loaded, but could not be saved", "warning");
    }
  };
  reader.readAsDataURL(file);
};

const restoreAvatarPreview = () => {
  if (!avatarButton) {
    return;
  }
  try {
    const saved = String(window.localStorage.getItem(AVATAR_STORAGE_KEY) || "").trim();
    if (!saved) {
      avatarButton.style.backgroundImage = "";
      avatarButton.classList.remove("has-image");
      return;
    }
    avatarImageUrl = saved;
    avatarButton.style.backgroundImage = `url("${saved}")`;
    avatarButton.classList.add("has-image");
  } catch (_error) {
  }
};

const setSystemState = (online) => {
  isOnline = online;

  if (hud) {
    hud.dataset.state = online ? "online" : "offline";
  }
  if (systemState) {
    systemState.textContent = online ? "SYSTEM ONLINE" : "SYSTEM OFFLINE";
    systemState.classList.toggle("online", online);
    systemState.classList.toggle("offline", !online);
  }
};

const updateClock = () => {
  if (!clockValue) {
    return;
  }

  const now = new Date();
  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  clockValue.textContent = `${hh}:${mm}`;
};

const updateRam = () => {
  if (!ramValue || !ramFill) {
    return;
  }

  ramValue.textContent = `${ramLevel}%`;
  ramFill.style.height = `${ramLevel}%`;
};

const updateNetworkStats = () => {
  if (!wifiValue || !downValue || !upValue) {
    return;
  }

  const isConnected = navigator.onLine;
  const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;

  if (!isConnected) {
    wifiValue.textContent = "Offline";
    downValue.textContent = "0.00 Mbps";
    upValue.textContent = "0.00 Mbps";
    return;
  }

  const type = connection?.effectiveType ? connection.effectiveType.toUpperCase() : "Online";
  const downlink = Number.isFinite(connection?.downlink) ? connection.downlink : null;

  wifiValue.textContent = type;

  if (downlink !== null && downlink > 0) {
    downValue.textContent = `${downlink.toFixed(2)} Mbps`;
    const uploadEstimate = Math.max(0.2, downlink * 0.34);
    upValue.textContent = `${uploadEstimate.toFixed(2)} Mbps`;
  } else {
    downValue.textContent = "-- Mbps";
    upValue.textContent = "-- Mbps";
  }
};

let newsIndex = 0;
const rotateNewsTicker = () => {
  if (!liveNewsTicker || NEWS_BRIEFINGS.length === 0) {
    return;
  }
  liveNewsTicker.textContent = NEWS_BRIEFINGS[newsIndex % NEWS_BRIEFINGS.length];
  newsIndex += 1;
};

const preventLayoutZoom = () => {
  const zoomKeys = new Set(["+", "-", "=", "0", "ArrowUp", "ArrowDown"]);

  window.addEventListener(
    "wheel",
    (event) => {
      if (event.ctrlKey) {
        event.preventDefault();
      }
    },
    { passive: false },
  );

  window.addEventListener("keydown", (event) => {
    if (!event.ctrlKey) {
      return;
    }
    if (zoomKeys.has(event.key)) {
      event.preventDefault();
    }
  });
};

const tickMediaProgress = () => {
  if (!isPlaying || document.hidden || !hud || hud.hidden) {
    return;
  }

  const duration = tracks[trackIndex].duration;
  elapsedSeconds += 1;

  if (elapsedSeconds >= duration) {
    changeTrack(1);
    isPlaying = true;
  }

  renderTrackUi();
};

if (playPause) {
  eventManager.addListener(playPause, "click", () => {
    runBridgeStatus("mediaStatus", ["playpause"], "Media control unavailable");
    togglePlayback();
  });
}

if (avatarButton) {
  eventManager.addListener(avatarButton, "click", openAvatarPicker);
}

if (avatarInput) {
  eventManager.addListener(avatarInput, "change", updateAvatarPreview);
}

if (prevTrack) {
  eventManager.addListener(prevTrack, "click", () => {
    runBridgeStatus("mediaStatus", ["previous"], "Media control unavailable");
    changeTrack(-1);
  });
}

if (nextTrack) {
  eventManager.addListener(nextTrack, "click", () => {
    runBridgeStatus("mediaStatus", ["next"], "Media control unavailable");
    changeTrack(1);
  });
}

if (shutdownBtn) {
  eventManager.addListener(shutdownBtn, "click", () => {
    runBridgeStatus("shutdownStatus", [], "Shutdown unavailable outside desktop app");
    isPlaying = false;
    setSystemState(false);
    renderTrackUi();
  });
}

if (restartBtn) {
  eventManager.addListener(restartBtn, "click", () => {
    runBridgeStatus("restartStatus", [], "Restart unavailable outside desktop app");
    elapsedSeconds = 0;
    isPlaying = false;
    setSystemState(false);
    renderTrackUi();

    registerTimeout(() => {
      setSystemState(true);
    }, 1200);
  });
}

if (reactorCoreBtn) {
  eventManager.addListener(reactorCoreBtn, "click", openWorkflowPanel);
}

if (workflowCloseBtn) {
  eventManager.addListener(workflowCloseBtn, "click", closeWorkflowPanel);
}

if (aiAgentBtn) {
  eventManager.addListener(aiAgentBtn, "click", () => {
    openChatPanel();
    showToast("AI Agent chat ready", "success");
  });
}

if (orbitalCameraBtn) {
  eventManager.addListener(orbitalCameraBtn, "click", () => {
    openCameraPanel(!authLocked);
    if (authLocked) {
      setAuthNotice("Authenticate first, then use camera controls.");
      showToast("System locked. Use Face Unlock once, then open camera.", "warning");
    }
  });
}

const reactorAuthArcBtn = document.getElementById("reactorAuthArcBtn");
if (reactorAuthArcBtn) {
  eventManager.addListener(reactorAuthArcBtn, "click", () => {
    openCameraPanel(false);
    requestFaceUnlock("Starting face authentication from reactor arc...");
  });
}

if (cameraCloseBtn) {
  eventManager.addListener(cameraCloseBtn, "click", closeCameraPanel);
}

if (mapCloseBtn) {
  eventManager.addListener(mapCloseBtn, "click", closeMapPanel);
}

if (mapRoadBtn) {
  eventManager.addListener(mapRoadBtn, "click", () => setMapMode("road"));
}

if (mapSatelliteBtn) {
  eventManager.addListener(mapSatelliteBtn, "click", () => setMapMode("satellite"));
}

if (chatCloseBtn) {
  eventManager.addListener(chatCloseBtn, "click", closeChatPanel);
}

if (chatSendBtn) {
  eventManager.addListener(chatSendBtn, "click", sendChatMessage);
}


if (quickImageBtn) {
  eventManager.addListener(quickImageBtn, "click", () => {
    runQuickSlashCommand("/image", "Image prompt", "Please enter an image prompt");
  });
}

if (quickSearchBtn) {
  eventManager.addListener(quickSearchBtn, "click", () => {
    runQuickSlashCommand("/search", "Search query", "Please enter a search query");
  });
}

if (quickClassifyBtn) {
  eventManager.addListener(quickClassifyBtn, "click", () => {
    runQuickSlashCommand("/classify", "Text to classify", "Please enter text to classify");
  });
}

if (micToggleBtn) {
  eventManager.addListener(micToggleBtn, "click", toggleMic);
}

if (voiceMuteBtn) {
  eventManager.addListener(voiceMuteBtn, "click", toggleVoiceMute);
}

if (chatInput) {
  eventManager.addListener(chatInput, "input", () => {
    if (hasBridgeMethod("conversationInterruptStatus")) {
      withBridge((bridge) => {
        bridge.conversationInterruptStatus(() => {
        });
      });
    }
  });

  eventManager.addListener(chatInput, "keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (hasBridgeMethod("conversationInterruptStatus")) {
        withBridge((bridge) => {
          bridge.conversationInterruptStatus(() => {
          });
        });
      }
      sendChatMessage();
    }
  });
}

if (profileAuthSetupBtn) {
  eventManager.addListener(profileAuthSetupBtn, "click", () => {
    if (!authSetupRequired) {
      showToast("First-time setup is disabled after provisioning", "error");
      return;
    }
    if (authInProgress) {
      showToast("Face setup already in progress", "warning");
      return;
    }
    stopCameraFeed();
    setAuthNotice("Opening camera for first-time face setup…");
    runAuthAction("authSetupFaceStatus");
  });
}

if (profileFaceAddBtn) {
  eventManager.addListener(profileFaceAddBtn, "click", () => {
    stopCameraFeed();
    openCameraPanel();
    runAuthAction("authFaceAddNoPinStatus");
  });
}

if (profileFaceUnlockBtn) {
  eventManager.addListener(profileFaceUnlockBtn, "click", () => {
    requestFaceUnlock("Starting manual face authentication...");
  });
}

if (profileFaceRemoveBtn) {
  eventManager.addListener(profileFaceRemoveBtn, "click", () => {
    runAuthAction("authFaceRemoveNoPinStatus");
  });
}

if (authFaceManualUnlockBtn) {
  eventManager.addListener(authFaceManualUnlockBtn, "click", () => {
    requestFaceUnlock("Starting manual face authentication...");
  });
}

registerInterval(pollSystemStats, SYSTEM_STATS_POLL_MS);
registerInterval(tickMediaProgress, MEDIA_TICK_MS);
registerInterval(updateClock, 60000);
registerInterval(rotateNewsTicker, 7000);

if (navigator.connection) {
  eventManager.addListener(navigator.connection, "change", updateNetworkStats);
}

eventManager.addListener(window, "online", updateNetworkStats);
eventManager.addListener(window, "offline", updateNetworkStats);
eventManager.addListener(window, "resize", renderOrbitNodes);
eventManager.addListener(window, "resize", resizeReactorFxCanvas);
eventManager.addListener(window, "keydown", (event) => {
  if (isTextInputTarget(event.target)) {
    return;
  }

  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "m") {
    event.preventDefault();
    toggleMic();
    return;
  }

  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "g") {
    event.preventDefault();
    openMapPanel();
    return;
  }

  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "c") {
    event.preventDefault();
    openCameraPanel(!authLocked);
    return;
  }

  if ((event.ctrlKey || event.metaKey) && event.shiftKey && event.key.toLowerCase() === "a") {
    event.preventDefault();
    openWorkflowPanel();
    return;
  }

  if (event.key === "/") {
    event.preventDefault();
    openChatPanel();
    if (chatInput) {
      chatInput.focus();
      chatInput.select?.();
    }
    return;
  }

  if (event.key === "Escape" && cameraPanel && !cameraPanel.hidden) {
    closeCameraPanel();
    return;
  }

  if (event.key === "Escape" && mapPanel && !mapPanel.hidden) {
    closeMapPanel();
    return;
  }

  if (event.key === "Escape" && workflowPanel && !workflowPanel.hidden) {
    closeWorkflowPanel();
  }
});

class PerformanceMonitor {
  constructor() {
    this.fps = 60;
    this.lastFrame = performance.now();
    this.frameCount = 0;
    this.memoryInterval = null;
    this.rafId = null;
    this.running = false;
  }

  startMonitoring() {
    if (this.running) {
      return;
    }
    this.running = true;
    this.measureFPS();
    this.measureMemory();
  }

  stopMonitoring() {
    this.running = false;
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    if (this.memoryInterval) {
      clearInterval(this.memoryInterval);
      this.memoryInterval = null;
    }
  }

  measureFPS() {
    const measure = (now) => {
      if (!this.running) {
        return;
      }
      this.frameCount += 1;
      const delta = now - this.lastFrame;
      if (delta >= 1000) {
        this.fps = Math.round((this.frameCount * 1000) / delta);
        this.frameCount = 0;
        this.lastFrame = now;
      }
      this.rafId = requestAnimationFrame(measure);
    };
    this.rafId = requestAnimationFrame(measure);
  }

  measureMemory() {
    if (!performance.memory) {
      return;
    }
    this.memoryInterval = registerInterval(() => {
      const used = performance.memory.usedJSHeapSize / 1024 / 1024;
      const total = performance.memory.jsHeapSizeLimit / 1024 / 1024;
      if (used > total * 0.8) {
        this.forceGC();
      }
    }, 30000);
  }

  forceGC() {
    console.debug("[Perf] High memory detected; skipping aggressive cache clear");
  }
}

eventManager.addListener(window, "beforeunload", () => {
  stopVoiceInput();
  stopGpsTracking();
  stopCameraFeed();

  document.querySelectorAll(".spin-slow, .spin-reverse, .spin-fast").forEach((el) => {
    el.style.animation = "none";
  });

  if (perfMonitor) {
    perfMonitor.stopMonitoring();
  }

  clearManagedTimers();
  eventManager.removeAllListeners();

  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
  }

  if (map3d) {
    map3d.remove();
    map3d = null;
  }
});

initQtBridge();
bindCommandButtons();
bindWorkflowButtons();
installMicroInteractions();
preventLayoutZoom();
installAuthInteractionGuard();
restoreAvatarPreview();
setSystemState(true);
setReactorState("idle");
setMicUi(false);
setVoiceMuteUi(false);
setMapModeUi(mapMode);
initNotificationPanel();
startReactorFxLoop();
rotateNewsTicker();
updateClock();
pollSystemStats();
renderTrackUi();
perfMonitor = new PerformanceMonitor();
if (!LOW_POWER_MODE) {
  perfMonitor.startMonitoring();
}

document.addEventListener("pointerdown", () => {
  startReactorHum();
}, { once: true });

const authBootTimer = registerInterval(() => {
  if (!jarvisBridge) {
    return;
  }
  clearInterval(authBootTimer);
  refreshAuthStatus().then(() => {
    if (authLocked) {
      openCameraPanel();
      triggerAutoFaceUnlock();
    }
  });
}, AUTH_BOOT_POLL_MS);