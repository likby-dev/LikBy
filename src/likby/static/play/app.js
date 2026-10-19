/**
 * LIKBY PLAY — CLIENT ENGINE & INTERACTIVE MINI APP
 * Luxury Telegram Mini App Gaming Ecosystem
 * Features: All 17 Games (11 Duels + 6 Solo), 60fps Micro-Animations,
 * Ambient Particle System, Sound Synthesizer, Touch/Swipe Controls & AI Practice Bot.
 */

(function () {
  "use strict";

  // Telegram WebApp Setup
  const tg = window.Telegram?.WebApp;
  const initData = tg?.initData || "";
  const currentUserId = tg?.initDataUnsafe?.user?.id
    ? `tg_${tg.initDataUnsafe.user.id}`
    : "player_one";
  let soundEnabled = true;

  // State Management
  let gamesCatalogue = [];
  let currentEntitlements = {
    daily_duel_limit: 5,
    duels_consumed_today: 0,
    duels_remaining_today: 5,
    tier: "BASE"
  };
  let currentFilter = "all";

  // Active Session & Partner State
  let activeGame = null;
  let activeSessionId = null;
  let activeGameState = null;
  let isPracticeMode = false;
  let connectedPartner = null; // { id, name, sessionId }

  // DOM Cache
  const gameGrid = document.getElementById("gameGrid");
  const userTierBadge = document.getElementById("userTierBadge");
  const quotaCounterText = document.getElementById("quotaCounterText");
  const quotaPills = document.getElementById("quotaPills");
  const soundToggleBtn = document.getElementById("soundToggleBtn");
  const arenaSoundBtn = document.getElementById("arenaSoundBtn");
  const gameViewport = document.getElementById("gameViewport");
  const viewportTitle = document.getElementById("viewportTitle");
  const viewportIcon = document.getElementById("viewportIcon");
  const viewportTurnBadge = document.getElementById("viewportTurnBadge");
  const canvasContainer = document.getElementById("canvasContainer");
  const exitGameBtn = document.getElementById("exitGameBtn");
  const inviteModal = document.getElementById("inviteModal");
  const closeInviteModal = document.getElementById("closeInviteModal");
  const partnerIdInput = document.getElementById("partnerIdInput");
  const sendInviteBtn = document.getElementById("sendInviteBtn");
  const practiceDuelBtn = document.getElementById("practiceDuelBtn");
  const quotaExhaustedModal = document.getElementById("quotaExhaustedModal");
  const closeQuotaModal = document.getElementById("closeQuotaModal");
  const exploreSoloBtn = document.getElementById("exploreSoloBtn");
  const upgradeTiersBtn = document.getElementById("upgradeTiersBtn");
  const toast = document.getElementById("toast");

  // Partner Banner DOM Cache
  const partnerBanner = document.getElementById("partnerBanner");
  const partnerStatusDot = document.getElementById("partnerStatusDot");
  const partnerStatusTag = document.getElementById("partnerStatusTag");
  const partnerTitle = document.getElementById("partnerTitle");
  const partnerCtaBtn = document.getElementById("partnerCtaBtn");
  const activePartnerModalContent = document.getElementById("activePartnerModalContent");
  const idlePartnerModalContent = document.getElementById("idlePartnerModalContent");
  const modalPartnerName = document.getElementById("modalPartnerName");
  const modalFindMatchBtn = document.getElementById("modalFindMatchBtn");

  // ============================================================================
  // 1. Web Audio API Harmonic Synthesizer
  // ============================================================================
  let audioCtx = null;
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) audioCtx = new AudioContextClass();
    }
    if (audioCtx && audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    return audioCtx;
  }

  function playTone(freq, type = "sine", duration = 0.1, gainVal = 0.12) {
    if (!soundEnabled) return;
    try {
      const ctx = getAudioContext();
      if (!ctx) return;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, ctx.currentTime);
      gain.gain.setValueAtTime(gainVal, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + duration);
    } catch (e) {
      // Audio fallback
    }
  }

  function playSound(soundType) {
    if (!soundEnabled) return;
    switch (soundType) {
      case "click":
        playTone(600, "sine", 0.05, 0.08);
        break;
      case "move":
        playTone(480, "triangle", 0.08, 0.1);
        break;
      case "drop":
        playTone(320, "sine", 0.12, 0.15);
        break;
      case "strike":
        playTone(220, "square", 0.1, 0.12);
        setTimeout(() => playTone(350, "sine", 0.12, 0.1), 40);
        break;
      case "score":
      case "merge":
        playTone(523, "sine", 0.08, 0.15);
        setTimeout(() => playTone(659, "sine", 0.1, 0.15), 60);
        setTimeout(() => playTone(784, "sine", 0.15, 0.18), 120);
        break;
      case "win":
        playTone(440, "triangle", 0.12, 0.2);
        setTimeout(() => playTone(554, "triangle", 0.12, 0.2), 100);
        setTimeout(() => playTone(659, "triangle", 0.15, 0.2), 200);
        setTimeout(() => playTone(880, "sine", 0.35, 0.25), 300);
        break;
      case "error":
        playTone(180, "sawtooth", 0.18, 0.15);
        break;
    }
  }

  // ============================================================================
  // 1B. Touch Screen Interactivity & Validation Engine (With Telegram Haptics)
  // ============================================================================
  let touchEnabled = true;

  const TouchSystem = {
    triggerHaptic(type) {
      if (!touchEnabled || !window.Telegram?.WebApp?.HapticFeedback) return;
      try {
        const hf = window.Telegram.WebApp.HapticFeedback;
        if (["light", "medium", "heavy", "rigid", "soft"].includes(type)) {
          hf.impactOccurred(type);
        } else if (["success", "warning", "error"].includes(type)) {
          hf.notificationOccurred(type);
        } else if (type === "selection") {
          hf.selectionChanged();
        }
      } catch (err) {
        // Safe fallback
      }
    },

    toggleTouchControls() {
      touchEnabled = !touchEnabled;
      document.querySelectorAll("#touchToggleBtn, #arenaTouchBtn").forEach((btn) => {
        if (touchEnabled) {
          btn.classList.add("active");
          btn.title = "Touch Controls: Active";
        } else {
          btn.classList.remove("active");
          btn.title = "Touch Controls: Disabled";
        }
      });
      showToast(touchEnabled ? "📱 Touch Screen Controls: Enabled" : "📱 Touch Screen Controls: Disabled");
      TouchSystem.triggerHaptic("selection");
    },

    getTouchPos(e, element) {
      const rect = element.getBoundingClientRect();
      const touch = e.touches ? (e.touches[0] || e.changedTouches[0]) : e;
      return {
        x: touch.clientX - rect.left,
        y: touch.clientY - rect.top,
        clientX: touch.clientX,
        clientY: touch.clientY,
        rect,
      };
    },

    validateInBounds(x, y, rect) {
      return x >= 0 && x <= rect.width && y >= 0 && y <= rect.height;
    }
  };

  // ============================================================================
  // 2. Ambient Canvas Starfield Background
  // ============================================================================
  function initAmbientCanvas() {
    const canvas = document.getElementById("ambientCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    window.addEventListener("resize", () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    });

    const particles = Array.from({ length: 45 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: Math.random() * 2 + 0.5,
      speedX: (Math.random() - 0.5) * 0.3,
      speedY: (Math.random() - 0.5) * 0.3,
      opacity: Math.random() * 0.6 + 0.2,
      color: Math.random() > 0.5 ? "rgba(34, 211, 238," : "rgba(139, 92, 246,"
    }));

    function animate() {
      ctx.clearRect(0, 0, width, height);
      particles.forEach((p) => {
        p.x += p.speedX;
        p.y += p.speedY;
        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = `${p.color} ${p.opacity})`;
        ctx.fill();
      });
      requestAnimationFrame(animate);
    }
    animate();
  }

  // ============================================================================
  // 3. Toast Notifications
  // ============================================================================
  function showToast(msg) {
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2600);
  }

  // ============================================================================
  // 4. API Client
  // ============================================================================
  async function apiCall(endpoint, method = "GET", body = null) {
    const headers = {
      "Content-Type": "application/json",
      "X-User-Id": currentUserId
    };
    if (initData) headers["X-Telegram-Init-Data"] = initData;

    try {
      const res = await fetch(endpoint, {
        method,
        headers,
        body: body ? JSON.stringify(body) : null
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        const errorMsg = errData.detail || errData.message || `HTTP ${res.status}`;
        console.warn(`[LikBy Play API] ${method} ${endpoint} returned ${res.status}:`, errorMsg);
        if (res.status === 403 && String(errorMsg).toLowerCase().includes("quota")) {
          showToast("⚡ Daily duel allowance reached!");
        }
        throw new Error(errorMsg);
      }
      return await res.json();
    } catch (e) {
      console.warn(`[LikBy Play Engine] Falling back to local client mode for ${endpoint}:`, e.message || e);
      return null; // Graceful fallback to client engine
    }
  }

  // ============================================================================
  // 5. Initializer & Catalogue Data
  // ============================================================================
  const GAME_TUTORIALS = {
    connect_four: {
      title: "Connect Four",
      icon: "🔵",
      objective: "Be the first player to form a horizontal, vertical, or diagonal line of four consecutive discs.",
      controls: "Tap or drag over any of the 7 column slots to drop your colored disc.",
      tip: "Control the center column early to maximize your winning vectors!"
    },
    carrom_clash: {
      title: "Carrom Clash",
      icon: "🎯",
      objective: "Strike and pocket your carrom coins into any of the 4 corner pockets. Pocket the Queen for big bonus points!",
      controls: "Drag the baseline slider to position your striker. Pull back and release the slingshot vector to fire.",
      tip: "Gentle bank shots off the cushions can navigate around blocking coins."
    },
    air_rush: {
      title: "Air Rush",
      icon: "🏒",
      objective: "Score by knocking the floating neon puck into your opponent's goal defense zone while guarding yours.",
      controls: "Touch and drag your paddle across your defending half of the arena.",
      tip: "Strike the puck with forward momentum to send high-velocity kinetic shots."
    },
    pocket_pool: {
      title: "Pocket Pool",
      icon: "🎱",
      objective: "Pocket your target balls using the cue ball without scratching into pockets.",
      controls: "Aim the cue stick by dragging your finger. Pull back on the power meter and release.",
      tip: "Use light power on close shots to avoid table rebounds."
    },
    stick_arena: {
      title: "Stick Arena",
      icon: "🤺",
      objective: "Deplete your rival fighter's health bar in intense martial stick duel rounds.",
      controls: "Use on-screen direction pads to advance or retreat. Tap Attack, Jump, Dash, and Block buttons.",
      tip: "Time your Blocks to deflect heavy strikes and counter-attack with a rapid dash slash."
    },
    quickdraw: {
      title: "QuickDraw",
      icon: "🎨",
      objective: "Take turns sketching secret prompt words or guessing what your rival is drawing before the timer expires.",
      controls: "Smooth canvas finger drawing with color palettes and stroke width toggles.",
      tip: "Draw key identifiable outlines first before adding small details."
    },
    word_rush: {
      title: "Word Rush",
      icon: "🔤",
      objective: "Construct as many valid dictionary words as possible from randomized letter racks within 60 seconds.",
      controls: "Tap letter tiles to form words, then tap Submit Word.",
      tip: "Longer words earn massive score multipliers!"
    },
    brain_blitz: {
      title: "Brain Blitz",
      icon: "🧠",
      objective: "Answer rapid-fire trivia questions faster than your opponent under a 15-second timer.",
      controls: "Tap your chosen answer option before the countdown timer hits zero.",
      tip: "Speed counts: answering within the first 3 seconds awards a 2x Blitz multiplier!"
    },
    reflex_rush: {
      title: "Reflex Rush",
      icon: "⚡",
      objective: "React the instant the tension chamber turns from Crimson to Emerald. Millisecond reaction determines the victor!",
      controls: "Tap anywhere on the arena as soon as the color flashes green.",
      tip: "Do NOT tap while it's red! False starts forfeit the round instantly."
    },
    mindmatch: {
      title: "MindMatch",
      icon: "💭",
      objective: "Compare answers to intriguing dilemma questions to compute psychological synchronicity and common ground.",
      controls: "Tap your honest preference on each dilemma card.",
      tip: "No right or wrong answers—pure social discovery and synergy."
    },
    mystery_mission: {
      title: "Mystery Mission",
      icon: "🔍",
      objective: "Two detectives cooperate to decrypt cyber safe locks using shared clue fragments.",
      controls: "Examine clues on your board, communicate via chat, and tap the keypad to enter the override code.",
      tip: "Your partner holds clues you cannot see—collaborate!"
    },
    xo: {
      title: "XO Duel",
      icon: "❌⭕",
      objective: "Classic Tic-Tac-Toe tactical neon arena. Align 3 of your marks horizontally, vertically, or diagonally.",
      controls: "Tap any empty 3x3 grid cell.",
      tip: "Taking the center or opposite corners forces defensive plays from your rival."
    },
    zen_merge: {
      title: "Zen Merge (2048)",
      icon: "🧩",
      objective: "Slide and merge matching number tiles to reach the legendary 2048 tile.",
      controls: "Swipe Up, Down, Left, or Right anywhere on the board.",
      tip: "Keep your highest value tile anchored in one corner!"
    },
    word_hunt: {
      title: "Word Hunt",
      icon: "🔎",
      objective: "Find all target words hidden in the letter matrix horizontally, vertically, or diagonally.",
      controls: "Touch and drag across consecutive letters in the 5x5 matrix.",
      tip: "Check word lists for starting letters and trace candidate lines."
    },
    color_flow: {
      title: "Color Flow",
      icon: "🎨",
      objective: "Connect matching color nodes by drawing non-overlapping neon pipes that cover the entire grid.",
      controls: "Touch an endpoint dot and drag along empty grid cells to its matching colored pair.",
      tip: "Start by routing along the outer perimeter of the board."
    },
    pocket_golf: {
      title: "Pocket Golf",
      icon: "⛳",
      objective: "Sink the golf ball into the cup in the fewest strokes possible while avoiding water and sand hazards.",
      controls: "Touch and drag back from the ball to aim slingshot trajectory; release to swing.",
      tip: "Bank off fairways and bounce surfaces to navigate sharp dog-leg holes."
    },
    reflex_lab: {
      title: "Reflex Lab",
      icon: "🧪",
      objective: "Neuro-agility trainer: tap shrinking kinetic spheres before they disappear.",
      controls: "Tap popping target orbs on your screen immediately as they spawn.",
      tip: "Keep fingers hovering close to the screen surface to cut travel time."
    },
    daily_mystery: {
      title: "Daily Mystery",
      icon: "🔐",
      objective: "Decipher the daily cryptic riddle published globally every 24 hours at 00:00 UTC.",
      controls: "Type your deduction in the solution box and tap Solve.",
      tip: "Look for figurative meanings, puns, and double entendres in the riddle lines."
    }
  };

  const FALLBACK_CATALOGUE = [
    // 12 Duels
    { id: "connect_four", name: "Connect Four", mode: "DUEL", icon: "🔵", category: "Strategy", tagline: "Drop discs, align 4 in a row, and outwit your partner." },
    { id: "carrom_clash", name: "Carrom Clash", mode: "DUEL", icon: "🎯", category: "Physics", tagline: "Silky friction, rebound bank shots, and pocket the royal queen." },
    { id: "air_rush", name: "Air Rush", mode: "DUEL", icon: "🏒", category: "Action", tagline: "High-octane neon air hockey table with intense kinetic volleys." },
    { id: "pocket_pool", name: "Pocket Pool", mode: "DUEL", icon: "🎱", category: "Physics", tagline: "8-ball billiards with precise aiming guide and spin power." },
    { id: "stick_arena", name: "Stick Arena", mode: "DUEL", icon: "🤺", category: "Combat", tagline: "Kinetic martial stick combat with weapon slashes and dodges." },
    { id: "quickdraw", name: "QuickDraw", mode: "DUEL", icon: "🎨", category: "Creative", tagline: "Real-time canvas sketch & guess battle with pressure smoothing." },
    { id: "word_rush", name: "Word Rush", mode: "DUEL", icon: "🔤", category: "Word", tagline: "Scramble 3D acrylic letter tiles into high-scoring words." },
    { id: "brain_blitz", name: "Brain Blitz", mode: "DUEL", icon: "🧠", category: "Trivia", tagline: "Head-to-head esports quiz showdown with pulsing 15s timer." },
    { id: "reflex_rush", name: "Reflex Rush", mode: "DUEL", icon: "⚡", category: "Reaction", tagline: "Tension chamber testing millisecond reactions. Avoid false starts!" },
    { id: "mindmatch", name: "MindMatch", mode: "DUEL", icon: "💭", category: "Social", tagline: "Discover harmonious choices and compute your synchro harmony." },
    { id: "mystery_mission", name: "Mystery Mission", mode: "DUEL", icon: "🔍", category: "Co-op", tagline: "Cyber-noir escape console: combine clues to crack the safe." },
    { id: "xo", name: "XO Duel", mode: "DUEL", icon: "❌⭕", category: "Strategy", tagline: "Cyber-neon tactical Tic-Tac-Toe duel with glowing alignment strikes." },

    // 6 Solo Games
    { id: "zen_merge", name: "Zen Merge (2048)", mode: "SOLO", icon: "🧩", category: "Puzzle", tagline: "Slide numbered tiles, merge identical values, reach 2048!" },
    { id: "word_hunt", name: "Word Hunt", mode: "SOLO", icon: "🔎", category: "Word", tagline: "Trace paths through a 5x5 letter matrix to uncover hidden words." },
    { id: "color_flow", name: "Color Flow", mode: "SOLO", icon: "🎨", category: "Puzzle", tagline: "Draw flowing neon conduits between matching endpoints." },
    { id: "pocket_golf", name: "Pocket Golf", mode: "SOLO", icon: "⛳", category: "Sports", tagline: "Pull-back slingshot golf with water hazards, sand, and smooth greens." },
    { id: "reflex_lab", name: "Reflex Lab", mode: "SOLO", icon: "🧪", category: "Training", tagline: "Neuro-speed trainer: tap shrinking kinetic target spheres." },
    { id: "daily_mystery", name: "Daily Mystery", mode: "SOLO", icon: "🔐", category: "Riddle", tagline: "Daily cryptographic brainteaser with animated treasure unlocks." }
  ];

  // ============================================================================
  // Progression & Leveling Engine
  // ============================================================================
  let playerProgression = {
    level: 1,
    total_xp: 0,
    win_streak: 0,
    best_win_streak: 0,
    games_played: 0,
    games_won: 0,
    achievements: []
  };

  async function loadProgression() {
    const p = await apiCall("/api/v1/play/progression");
    if (p) {
      playerProgression = p;
    }
    updateProgressionUI();
  }

  function getRankTitle(lvl) {
    if (lvl >= 10) return "Grandmaster Legend";
    if (lvl >= 7) return "Cyber Champion";
    if (lvl >= 5) return "Arena Veteran";
    if (lvl >= 3) return "Skilled Contender";
    if (lvl >= 2) return "Active Cadet";
    return "Cyber Novice";
  }

  function updateProgressionUI() {
    const lvl = playerProgression.level || 1;
    const xp = playerProgression.total_xp || 0;
    const streak = playerProgression.win_streak || 0;
    const reqCurrent = 100 * (lvl - 1) * lvl;
    const reqNext = 100 * lvl * (lvl + 1);
    const xpInLevel = Math.max(0, xp - reqCurrent);
    const xpSpan = Math.max(1, reqNext - reqCurrent);
    const pct = Math.min(100, Math.round((xpInLevel / xpSpan) * 100));

    const lvlBadge = document.getElementById("playerLevelBadge");
    if (lvlBadge) lvlBadge.textContent = `LVL ${lvl}`;

    const streakBadge = document.getElementById("playerStreakBadge");
    if (streakBadge) streakBadge.textContent = `🔥 ${streak} Streak`;

    const nameText = document.getElementById("playerNameText");
    if (nameText) {
      const u = tg?.initDataUnsafe?.user;
      nameText.textContent = u?.first_name ? `${u.first_name}` : "LikBy Player";
    }

    const rankTitle = document.getElementById("playerRankTitle");
    if (rankTitle) rankTitle.textContent = getRankTitle(lvl);

    const xpText = document.getElementById("playerXpText");
    if (xpText) xpText.textContent = `${xp} / ${reqNext} XP`;

    const xpBar = document.getElementById("xpBarFill");
    if (xpBar) xpBar.style.width = `${pct}%`;
  }

  function showAchievementToast(ach) {
    const toastElem = document.getElementById("achievementToast");
    if (!toastElem) return;
    document.getElementById("achToastIcon").textContent = ach.icon || "🎖";
    document.getElementById("achToastTitle").textContent = ach.title;
    document.getElementById("achToastXp").textContent = `+${ach.xp_reward || 100} XP`;
    toastElem.classList.add("active");
    playSound("win");
    TouchSystem.triggerHaptic("success");
    setTimeout(() => toastElem.classList.remove("active"), 3800);
  }

  function awardProgressionXP(amount = 100, isWin = true) {
    playerProgression.total_xp = (playerProgression.total_xp || 0) + amount;
    playerProgression.games_played = (playerProgression.games_played || 0) + 1;
    if (isWin) {
      playerProgression.games_won = (playerProgression.games_won || 0) + 1;
      playerProgression.win_streak = (playerProgression.win_streak || 0) + 1;
      if (playerProgression.win_streak > (playerProgression.best_win_streak || 0)) {
        playerProgression.best_win_streak = playerProgression.win_streak;
      }
    } else {
      playerProgression.win_streak = 0;
    }

    // Check level up
    const nextReq = 100 * playerProgression.level * (playerProgression.level + 1);
    if (playerProgression.total_xp >= nextReq) {
      playerProgression.level++;
      showToast(`🎉 Level Up! You reached Level ${playerProgression.level}!`);
      playSound("win");
      TouchSystem.triggerHaptic("heavy");
    }

    updateProgressionUI();
  }

  async function init() {
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor("#030712");
    }

    initAmbientCanvas();
    setupEventListeners();
    setupGameVerseNav();

    // 1. Check URL parameters for active session or partner
    const urlParams = new URLSearchParams(window.location.search);
    const pId = urlParams.get("partner_id");
    const pName = urlParams.get("partner_name");
    const sId = urlParams.get("session_id");
    const reqMode = urlParams.get("mode");
    const reqGame = urlParams.get("game");

    if (pId) {
      connectedPartner = {
        id: pId,
        name: pName || "Chat Partner",
        sessionId: sId || null,
      };
    }

    // 2. Fetch Catalogue from API or Fallback
    const apiCatalogue = await apiCall("/api/v1/play/catalogue");
    gamesCatalogue = (apiCatalogue && apiCatalogue.length > 0) ? apiCatalogue : FALLBACK_CATALOGUE;

    // 3. Fetch Entitlements
    const apiEntitlements = await apiCall("/api/v1/play/entitlements");
    if (apiEntitlements) currentEntitlements = apiEntitlements;

    // 4. Fetch Progression & Player Stats
    await loadProgression();

    // 5. Also check active chat partner endpoint if not already in URL
    if (!connectedPartner) {
      const partnerRes = await apiCall("/api/v1/play/active_chat_partner");
      if (partnerRes && partnerRes.has_partner && partnerRes.partner_id) {
        connectedPartner = {
          id: partnerRes.partner_id,
          name: partnerRes.partner_name || "Chat Partner",
          sessionId: partnerRes.session_id || null,
        };
      }
    }

    updatePartnerBanner();
    updateEntitlementsUI();

    if (reqMode === "duel") {
      currentFilter = "duel";
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.filter === "duel"));
    } else if (reqMode === "solo") {
      currentFilter = "solo";
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.filter === "solo"));
    }

    renderGameGrid();

    if (reqGame) {
      launchGame(reqGame);
    }
  }

  function updatePartnerBanner() {
    if (!partnerBanner) return;
    if (connectedPartner) {
      partnerBanner.className = "partner-connection-banner active";
      if (partnerStatusDot) partnerStatusDot.className = "live-dot live";
      if (partnerStatusTag) partnerStatusTag.textContent = "🟢 CHAT PARTNER CONNECTED";
      if (partnerTitle) partnerTitle.textContent = `⚔️ Duels Active with ${connectedPartner.name}`;
      if (partnerCtaBtn) {
        partnerCtaBtn.textContent = "⚔️ Ready";
        partnerCtaBtn.className = "btn-partner-cta ready";
      }
    } else {
      partnerBanner.className = "partner-connection-banner idle";
      if (partnerStatusDot) partnerStatusDot.className = "live-dot idle";
      if (partnerStatusTag) partnerStatusTag.textContent = "💬 ANONYMOUS CHAT DUELS";
      if (partnerTitle) partnerTitle.textContent = "Duels unlock when connected in chat";
      if (partnerCtaBtn) {
        partnerCtaBtn.textContent = "🎲 Find Match";
        partnerCtaBtn.className = "btn-partner-cta";
      }
    }
  }

  function updateEntitlementsUI() {
    const tier = currentEntitlements.tier || "BASE";
    if (userTierBadge) {
      userTierBadge.textContent = tier.toUpperCase();
      userTierBadge.className = `tier-badge ${tier.toLowerCase()}`;
    }

    const rem = currentEntitlements.duels_remaining_today ?? 5;
    const limit = currentEntitlements.daily_duel_limit ?? 5;
    if (quotaCounterText) {
      quotaCounterText.textContent = `${rem} of ${limit} remaining`;
    }

    if (quotaPills) {
      quotaPills.innerHTML = "";
      for (let i = 0; i < limit; i++) {
        const pill = document.createElement("div");
        pill.className = `quota-pill ${i < rem ? "active" : ""}`;
        quotaPills.appendChild(pill);
      }
    }
  }

  function setupEventListeners() {
    // Sound Toggles
    const toggleSound = () => {
      soundEnabled = !soundEnabled;
      const icon = soundEnabled ? "🔊" : "🔇";
      if (soundToggleBtn) soundToggleBtn.textContent = icon;
      if (arenaSoundBtn) arenaSoundBtn.textContent = icon;
      showToast(soundEnabled ? "Sound enabled" : "Sound muted");
      if (soundEnabled) playSound("click");
    };
    soundToggleBtn?.addEventListener("click", toggleSound);
    arenaSoundBtn?.addEventListener("click", toggleSound);

    // Touch Screen Controls Toggle
    document.getElementById("touchToggleBtn")?.addEventListener("click", TouchSystem.toggleTouchControls);
    document.getElementById("arenaTouchBtn")?.addEventListener("click", TouchSystem.toggleTouchControls);

    // Partner Banner CTA
    partnerCtaBtn?.addEventListener("click", () => {
      playSound("click");
      if (connectedPartner) {
        currentFilter = "duel";
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.filter === "duel"));
        renderGameGrid();
        showToast(`⚔️ Connected with ${connectedPartner.name}! Select any duel.`);
      } else {
        openMatchmakingRadar(activeGame ? activeGame.id : "connect_four");
      }
    });

    // Matchmaking Radar Queue triggers
    document.getElementById("openQueueBtn")?.addEventListener("click", () => {
      inviteModal?.classList.remove("active");
      openMatchmakingRadar(activeGame ? activeGame.id : "connect_four");
    });
    document.getElementById("cancelMatchmakingBtn")?.addEventListener("click", cancelMatchmaking);

    // Tutorial / Rules Dialog
    document.getElementById("viewportTutorialBtn")?.addEventListener("click", openTutorialModal);
    document.getElementById("closeTutorialModal")?.addEventListener("click", () => {
      document.getElementById("tutorialModal")?.classList.remove("active");
    });
    document.getElementById("gotItTutorialBtn")?.addEventListener("click", () => {
      document.getElementById("tutorialModal")?.classList.remove("active");
      playSound("click");
    });

    // Daily Riddle Interactions
    document.getElementById("dailyRevealHintBtn")?.addEventListener("click", () => {
      const box = document.getElementById("dailyHintBox");
      if (box) box.style.display = "flex";
      playSound("click");
      TouchSystem.triggerHaptic("light");
    });
    document.getElementById("dailySubmitBtn")?.addEventListener("click", submitDailyAnswer);
    document.getElementById("dailyAnswerInput")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") submitDailyAnswer();
    });

    // Tab Filters
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.dataset.filter;
        renderGameGrid();
        playSound("click");
      });
    });

    // Quick Chips
    document.querySelectorAll(".quick-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const gid = chip.dataset.game;
        launchGame(gid);
      });
    });

    // Featured Button
    document.getElementById("featuredPlayBtn")?.addEventListener("click", () => {
      launchGame("carrom_clash");
    });

    // Upgrade buttons
    document.getElementById("upgradePlanBtn")?.addEventListener("click", () => {
      showToast("Redirecting to VIP Plans...");
      if (tg?.close) tg.close();
    });
    upgradeTiersBtn?.addEventListener("click", () => {
      quotaExhaustedModal?.classList.remove("active");
      showToast("Check bot menu for VIP subscriptions!");
      if (tg?.close) tg.close();
    });

    // Modals
    closeInviteModal?.addEventListener("click", () => inviteModal?.classList.remove("active"));
    closeQuotaModal?.addEventListener("click", () => quotaExhaustedModal?.classList.remove("active"));
    exploreSoloBtn?.addEventListener("click", () => {
      quotaExhaustedModal?.classList.remove("active");
      currentFilter = "solo";
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.filter === "solo"));
      renderGameGrid();
    });

    modalFindMatchBtn?.addEventListener("click", () => {
      inviteModal?.classList.remove("active");
      openMatchmakingRadar(activeGame ? activeGame.id : "connect_four");
    });

    // Exit Game
    exitGameBtn?.addEventListener("click", () => {
      playSound("click");
      gameViewport?.classList.remove("active");
      activeGame = null;
      activeSessionId = null;
    });

    // Send Invite / Practice
    sendInviteBtn?.addEventListener("click", () => {
      const pid = (connectedPartner && connectedPartner.id) || partnerIdInput?.value.trim() || "partner_123";
      inviteModal?.classList.remove("active");
      showToast(`⚔️ Challenging ${connectedPartner ? connectedPartner.name : "partner"}...`);
      startDuelSession(activeGame.id, pid, false);
    });
    practiceDuelBtn?.addEventListener("click", () => {
      inviteModal?.classList.remove("active");
      startDuelSession(activeGame.id, "practice_bot", true);
    });
  }

  // ============================================================================
  // GameVerse Platform Helpers: Navigation, Radar, Tutorial, Leaderboard, Badges
  // ============================================================================
  function setupGameVerseNav() {
    document.querySelectorAll(".gv-nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".gv-nav-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const view = btn.dataset.view;
        document.querySelectorAll(".gameverse-view").forEach((v) => {
          v.style.display = "none";
          v.classList.remove("active");
        });
        const target = document.getElementById(`view${view.charAt(0).toUpperCase() + view.slice(1)}`);
        if (target) {
          target.style.display = "block";
          target.classList.add("active");
        }
        playSound("click");
        TouchSystem.triggerHaptic("selection");

        if (view === "leaderboard") loadLeaderboard();
        if (view === "badges") loadBadges();
        if (view === "daily") loadDailyRiddle();
      });
    });
  }

  let mmPollInterval = null;
  let mmTimerInterval = null;
  let mmSeconds = 0;

  function openMatchmakingRadar(gameId = "connect_four") {
    const modal = document.getElementById("matchmakingModal");
    if (!modal) return;
    const game = gamesCatalogue.find((g) => g.id === gameId) || FALLBACK_CATALOGUE.find((g) => g.id === gameId) || { name: "Connect Four", id: "connect_four" };
    activeGame = game;
    document.getElementById("mmGameTag").textContent = `${game.name} • Casual Duel`;
    document.getElementById("radarAvatar").textContent = game.icon || "⚔️";
    document.getElementById("mmModalTitle").textContent = "Searching Opponent...";
    document.getElementById("mmModalSub").textContent = "Finding an online contender in the GameVerse Arena";
    modal.classList.add("active");
    playSound("click");

    mmSeconds = 0;
    document.getElementById("mmTimer").textContent = "00:00";
    if (mmTimerInterval) clearInterval(mmTimerInterval);
    mmTimerInterval = setInterval(() => {
      mmSeconds++;
      const m = String(Math.floor(mmSeconds / 60)).padStart(2, "0");
      const s = String(mmSeconds % 60).padStart(2, "0");
      document.getElementById("mmTimer").textContent = `${m}:${s}`;
    }, 1000);

    // Join queue via backend API
    apiCall("/api/v1/play/matchmaking/join", "POST", {
      game_id: game.id,
      mode: "casual"
    }).then((res) => {
      if (res && res.status === "MATCHED") {
        handleMatchFound(res);
        return;
      }
      if (mmPollInterval) clearInterval(mmPollInterval);
      mmPollInterval = setInterval(async () => {
        const statusRes = await apiCall("/api/v1/play/matchmaking/status");
        if (statusRes && statusRes.status === "MATCHED") {
          clearInterval(mmPollInterval);
          handleMatchFound(statusRes);
        }
      }, 1500);
    });
  }

  function handleMatchFound(matchData) {
    if (mmTimerInterval) clearInterval(mmTimerInterval);
    if (mmPollInterval) clearInterval(mmPollInterval);
    document.getElementById("mmModalTitle").textContent = "⚔️ Opponent Found!";
    document.getElementById("mmModalSub").textContent = `Paired with ${matchData.opponent_name || "Arena Challenger"}! Launching duel...`;
    playSound("start");
    TouchSystem.triggerHaptic("heavy");

    setTimeout(() => {
      document.getElementById("matchmakingModal")?.classList.remove("active");
      startDuelSession(matchData.game_id || activeGame.id, matchData.opponent_id || "rival_player", false);
    }, 1200);
  }

  function cancelMatchmaking() {
    if (mmTimerInterval) clearInterval(mmTimerInterval);
    if (mmPollInterval) clearInterval(mmPollInterval);
    apiCall("/api/v1/play/matchmaking/leave", "POST");
    document.getElementById("matchmakingModal")?.classList.remove("active");
    playSound("click");
    showToast("Matchmaking cancelled");
  }

  function openTutorialModal() {
    const modal = document.getElementById("tutorialModal");
    if (!modal || !activeGame) return;
    const tut = GAME_TUTORIALS[activeGame.id] || {
      title: activeGame.name,
      icon: activeGame.icon || "🎮",
      objective: activeGame.tagline || "Play and score points!",
      controls: "Touch or click to interact.",
      tip: "Practice moves to master the board."
    };
    document.getElementById("tutorialTitle").textContent = `${tut.icon} ${tut.title} — How to Play`;
    document.getElementById("tutorialContent").innerHTML = `
      <div>
        <div class="tutorial-section-title">🎯 Objective</div>
        <p>${tut.objective}</p>
      </div>
      <div>
        <div class="tutorial-section-title">📱 Touch & Controls</div>
        <p>${tut.controls}</p>
      </div>
      <div>
        <div class="tutorial-section-title">💡 Pro Strategy</div>
        <p>${tut.tip}</p>
      </div>
    `;
    modal.classList.add("active");
    playSound("click");
  }

  async function loadLeaderboard() {
    const container = document.getElementById("leaderboardList");
    if (!container) return;
    container.innerHTML = '<div class="leaderboard-loading" style="padding: 20px; text-align: center; color: var(--likby-text-muted);">Fetching arena rankings...</div>';
    const data = await apiCall("/api/v1/play/leaderboard?limit=10");
    if (!data || !data.leaderboard || data.leaderboard.length === 0) {
      container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--likby-text-muted);">No ranked matches recorded yet this season. Be the first champion!</div>';
      return;
    }
    container.innerHTML = data.leaderboard.map((item, idx) => `
      <div class="leaderboard-item">
        <div class="lb-rank-col ${idx === 0 ? "lb-rank-1" : idx === 1 ? "lb-rank-2" : idx === 2 ? "lb-rank-3" : ""}">
          ${idx === 0 ? "🥇" : idx === 1 ? "🥈" : idx === 2 ? "🥉" : `#${item.rank}`}
        </div>
        <div class="lb-user-info">
          <div class="lb-avatar">${idx === 0 ? "👑" : "🎮"}</div>
          <div class="lb-name-group">
            <div class="lb-name">${item.user_name || item.user_id}</div>
            <div class="lb-tier-level">Level ${item.level} • ${item.tier} Tier</div>
          </div>
        </div>
        <div class="lb-score-col">
          <div class="lb-score">${item.total_xp.toLocaleString()} XP</div>
          <div class="lb-score-label">${item.games_won || 0} Wins</div>
        </div>
      </div>
    `).join("");
  }

  async function loadBadges() {
    const grid = document.getElementById("badgesGrid");
    if (!grid) return;
    grid.innerHTML = '<div class="badges-loading" style="padding: 20px; text-align: center; color: var(--likby-text-muted);">Loading badges...</div>';
    const data = await apiCall("/api/v1/play/achievements");
    if (!data || !data.achievements) {
      grid.innerHTML = '<div style="color: var(--likby-text-muted); text-align: center;">Unable to load achievements</div>';
      return;
    }
    const unlocked = data.achievements.filter(a => a.unlocked).length;
    document.getElementById("badgeUnlockedCount").textContent = `${unlocked} / ${data.achievements.length} Unlocked`;
    grid.innerHTML = data.achievements.map(ach => `
      <div class="badge-card ${ach.unlocked ? "unlocked" : "locked"}">
        <div class="badge-card-icon">${ach.icon || "🎖"}</div>
        <div class="badge-card-title">${ach.title}</div>
        <div class="badge-card-desc">${ach.description}</div>
        <div class="badge-card-reward">+${ach.xp_reward} XP</div>
      </div>
    `).join("");
  }

  async function loadDailyRiddle() {
    const data = await apiCall("/api/v1/play/daily_challenge");
    if (!data) return;
    document.getElementById("dailyChallengeDate").textContent = `Challenge Date: ${data.date} (UTC)`;
    document.getElementById("dailyRiddleTitle").textContent = data.title;
    document.getElementById("dailyRiddleText").textContent = `"${data.clue}"`;
    document.getElementById("dailyHintText").textContent = data.hint;
    document.getElementById("dailyHintBox").style.display = "none";
  }

  async function submitDailyAnswer() {
    const input = document.getElementById("dailyAnswerInput");
    const ans = input?.value.trim();
    if (!ans) {
      showToast("Please enter an answer!");
      return;
    }
    const res = await apiCall("/api/v1/play/daily_challenge/verify", "POST", { answer: ans });
    if (res && res.solved) {
      playSound("win");
      TouchSystem.triggerHaptic("success");
      document.getElementById("dailyInputSection").style.display = "none";
      document.getElementById("dailySolvedSuccess").style.display = "flex";
      document.getElementById("dailyExplanationText").textContent = res.explanation;
      showToast(`🎉 Correct! +${res.xp_awarded} XP! Streak: ${res.current_streak} days 🔥`);
      awardProgressionXP(res.xp_awarded, true);
    } else {
      playSound("error");
      TouchSystem.triggerHaptic("warning");
      showToast("❌ Incorrect deduction. Try again or check the hint!");
    }
  }

  function renderGameGrid() {
    if (!gameGrid) return;
    gameGrid.innerHTML = "";

    const filtered = gamesCatalogue.filter((g) => {
      if (currentFilter === "duel") return g.mode.toUpperCase() === "DUEL";
      if (currentFilter === "solo") return g.mode.toUpperCase() === "SOLO";
      return true;
    });

    filtered.forEach((game) => {
      const card = document.createElement("div");
      card.className = "game-card";
      const isDuel = game.mode.toUpperCase() === "DUEL";

      card.innerHTML = `
        <span class="game-card-mode ${isDuel ? "duel" : "solo"}">${isDuel ? "⚔️ DUEL" : "🕹 SOLO"}</span>
        <div class="game-card-icon">${game.icon || (isDuel ? "⚔️" : "🧩")}</div>
        <div>
          <div class="game-card-title">${game.name}</div>
          <div class="game-card-tagline">${game.tagline || ""}</div>
        </div>
        <div class="game-card-footer">
          <span>${game.category || "Game"}</span>
          <span style="color: var(--likby-cyan); font-weight: 800;">PLAY ▶</span>
        </div>
      `;

      card.addEventListener("click", () => {
        playSound("click");
        launchGame(game.id);
      });

      gameGrid.appendChild(card);
    });
  }

  function launchGame(gameId) {
    const game = gamesCatalogue.find((g) => g.id === gameId) || FALLBACK_CATALOGUE.find((g) => g.id === gameId);
    if (!game) return;
    activeGame = game;

    if (game.mode.toUpperCase() === "DUEL") {
      // Check quota
      if (currentEntitlements.duels_remaining_today <= 0) {
        quotaExhaustedModal?.classList.add("active");
        playSound("error");
        return;
      }

      if (connectedPartner) {
        // Partner is connected!
        document.getElementById("inviteModalTitle").textContent = `⚔️ Challenge in ${game.name}`;
        if (document.getElementById("inviteModalDesc")) {
          document.getElementById("inviteModalDesc").textContent = `Challenge your conversation partner ${connectedPartner.name} to a live match of ${game.name}!`;
        }
        if (activePartnerModalContent) activePartnerModalContent.style.display = "block";
        if (idlePartnerModalContent) idlePartnerModalContent.style.display = "none";
        if (modalPartnerName) modalPartnerName.textContent = connectedPartner.name;
        if (sendInviteBtn) {
          sendInviteBtn.style.display = "block";
          sendInviteBtn.textContent = `⚔️ Play with ${connectedPartner.name}`;
        }
        if (partnerIdInput) partnerIdInput.value = connectedPartner.id;
        inviteModal?.classList.add("active");
      } else {
        // No partner connected -> duels are active when connected in chat
        document.getElementById("inviteModalTitle").textContent = `⚔️ Duels Active in Chat`;
        if (document.getElementById("inviteModalDesc")) {
          document.getElementById("inviteModalDesc").textContent = `Multiplayer duels activate automatically when connected with a partner in LikBy chat. Practice against AI now or connect with a partner!`;
        }
        if (activePartnerModalContent) activePartnerModalContent.style.display = "none";
        if (idlePartnerModalContent) idlePartnerModalContent.style.display = "block";
        if (sendInviteBtn) sendInviteBtn.style.display = "none";
        inviteModal?.classList.add("active");
      }
    } else {
      // Solo Game -> Instant Launch
      startSoloSession(game.id);
    }
  }

  // ============================================================================
  // 6. Game Session Initialization & Routing
  // ============================================================================
  async function startSoloSession(gameId) {
    isPracticeMode = false;
    const res = await apiCall(`/api/v1/play/solo/${gameId}/start`, "POST");
    activeSessionId = res?.session_id || `solo_${Date.now()}`;
    activeGameState = res?.initial_state || getInitialGameState(gameId);

    openViewport(activeGame.name, activeGame.icon || "🧩", "Solo Mode");
    renderActiveGame();
  }

  async function startDuelSession(gameId, partnerId, practice) {
    isPracticeMode = practice;
    activeSessionId = `duel_${Date.now()}`;
    activeGameState = getInitialGameState(gameId);

    // Deduct local credit
    if (!practice && currentEntitlements.duels_remaining_today > 0) {
      currentEntitlements.duels_remaining_today--;
      updateEntitlementsUI();
    }

    const opponentName = practice ? "AI Practice Bot 🤖" : (connectedPartner ? connectedPartner.name : `Opponent ⚔️`);
    const modeText = practice ? "Practice vs AI Bot 🤖" : `Duel vs ${opponentName} ⚔️`;
    openViewport(activeGame.name, activeGame.icon || "⚔️", modeText);
    renderActiveGame();
  }

  function openViewport(title, icon, turnStatus) {
    if (viewportTitle) viewportTitle.textContent = title;
    if (viewportIcon) viewportIcon.textContent = icon;
    if (viewportTurnBadge) viewportTurnBadge.textContent = turnStatus;
    gameViewport?.classList.add("active");
    playSound("move");
  }

  function getInitialGameState(gameId) {
    switch (gameId) {
      case "connect_four":
        return { board: Array(6).fill(null).map(() => Array(7).fill(0)), current_turn: "P1", winner: null };
      case "carrom_clash":
        return { p1_score: 0, p2_score: 0, queen_pocketed: false, current_turn: "P1" };
      case "air_rush":
        return { p1_score: 0, p2_score: 0, puck: { x: 150, y: 190 }, current_turn: "P1" };
      case "pocket_pool":
        return { solids_left: 7, stripes_left: 7, current_turn: "P1", balls_potted: [] };
      case "stick_arena":
        return { p1_hp: 100, p2_hp: 100, p1_x: 40, p2_x: 220, turn: "P1" };
      case "quickdraw":
        return { word: "SUNSET", word_length: 6, strokes: [] };
      case "word_rush":
        return { letters: ["L", "I", "K", "B", "Y", "P", "L", "A", "Y"], score: 0 };
      case "brain_blitz":
        return {
          question_idx: 0,
          p1_score: 0,
          p2_score: 0,
          questions: [
            { q: "What is the speed of light in vacuum?", options: ["300,000 km/s", "150,000 km/s", "1,080 km/h", "Sound speed"], ans: 0 },
            { q: "Which planet has the most moons?", options: ["Jupiter", "Saturn", "Mars", "Neptune"], ans: 1 },
            { q: "What is the hardest natural substance on Earth?", options: ["Quartz", "Granite", "Diamond", "Titanium"], ans: 2 }
          ]
        };
      case "reflex_rush":
        return { round: 1, ready: false, green_time: 0, p1_time: null };
      case "mindmatch":
        return {
          round: 1,
          score: 85,
          prompt: "Your perfect late-night vibe:",
          optA: "🌃 Rooftop City Lights",
          optB: "🏕 Cozy Campfire & Stars"
        };
      case "mystery_mission":
        return { stage: 1, prompt: "Classified Safe: Enter Cipher Passcode", hint: "The answer is the founding year of LikBy (2026)." };
      case "xo":
        return {
          board: [
            ["", "", ""],
            ["", "", ""],
            ["", "", ""]
          ],
          current_turn: "P1",
          winner: null,
          winning_cells: [],
          move_count: 0
        };

      // Solo games
      case "zen_merge":
        return {
          score: 0,
          grid: [
            [2, 0, 0, 0],
            [0, 2, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0]
          ]
        };
      case "word_hunt":
        return {
          found: [],
          words: ["LIKBY", "GAME", "DUEL", "PLAY", "STAR"],
          grid: [
            ["L", "I", "K", "B", "Y"],
            ["G", "A", "M", "E", "S"],
            ["D", "U", "E", "L", "T"],
            ["P", "L", "A", "Y", "A"],
            ["S", "T", "A", "R", "R"]
          ]
        };
      case "color_flow":
        return { level: 1, flows_connected: 0, target_flows: 3 };
      case "pocket_golf":
        return { strokes: 0, par: 3, ball: { x: 150, y: 320 }, hole: { x: 150, y: 60 } };
      case "reflex_lab":
        return { score: 0, best_ms: 195 };
      case "daily_mystery":
        return { solved: false, clue: "I speak without a mouth and hear without ears. I have no body, but I come alive with wind. What am I?", answer: "echo" };
      default:
        return {};
    }
  }

  function submitAction(actionType, payload) {
    playSound("move");

    // Optional API call if backend duel session
    if (activeSessionId && !isPracticeMode && activeGame?.mode?.toUpperCase() === "DUEL") {
      apiCall(`/api/v1/play/duels/${activeSessionId}/action`, "POST", { action_type: actionType, payload });
    }

    // Trigger AI response in practice mode
    if (isPracticeMode) {
      setTimeout(() => triggerAiPracticeMove(actionType), 600);
    }
  }

  function triggerAiPracticeMove(lastUserAction) {
    if (!activeGameState) return;
    if (activeGame.id === "connect_four" && activeGameState.current_turn === "P2") {
      const emptyCols = [];
      for (let c = 0; c < 7; c++) {
        if (activeGameState.board[0][c] === 0) emptyCols.push(c);
      }
      if (emptyCols.length > 0) {
        const randCol = emptyCols[Math.floor(Math.random() * emptyCols.length)];
        dropDisc(randCol, 2);
      }
    } else if (activeGame.id === "xo" && activeGameState.current_turn === "P2" && !activeGameState.winner) {
      makeAiXOMove();
    } else if (activeGame.id === "stick_arena") {
      activeGameState.p1_hp = Math.max(0, activeGameState.p1_hp - 15);
      renderStickArena();
      playSound("strike");
    }
  }

  // ============================================================================
  // 7. Interactive Game Renderers (All 18 Games)
  // ============================================================================
  function renderActiveGame() {
    if (!canvasContainer || !activeGame) return;
    switch (activeGame.id) {
      case "connect_four": renderConnectFour(); break;
      case "xo": renderXO(); break;
      case "carrom_clash": renderCarromClash(); break;
      case "air_rush": renderAirRush(); break;
      case "pocket_pool": renderPocketPool(); break;
      case "stick_arena": renderStickArena(); break;
      case "quickdraw": renderQuickDraw(); break;
      case "word_rush": renderWordRush(); break;
      case "brain_blitz": renderBrainBlitz(); break;
      case "reflex_rush": renderReflexRush(); break;
      case "mindmatch": renderMindMatch(); break;
      case "mystery_mission": renderMysteryMission(); break;
      case "zen_merge": renderZenMerge(); break;
      case "word_hunt": renderWordHunt(); break;
      case "color_flow": renderColorFlow(); break;
      case "pocket_golf": renderPocketGolf(); break;
      case "reflex_lab": renderReflexLab(); break;
      case "daily_mystery": renderDailyMystery(); break;
    }
  }

  // --------------------------------------------------------------------------
  // GAME 1: CONNECT FOUR
  // --------------------------------------------------------------------------
  function dropDisc(col, player) {
    const board = activeGameState.board;
    let placedRow = -1;
    for (let r = 5; r >= 0; r--) {
      if (board[r][col] === 0) {
        board[r][col] = player;
        placedRow = r;
        break;
      }
    }
    if (placedRow === -1) {
      playSound("error");
      TouchSystem.triggerHaptic("warning");
      showToast("⚠️ Column is full! Pick another.");
      return false;
    }

    playSound("drop");
    TouchSystem.triggerHaptic("medium");
    activeGameState.current_turn = player === 1 ? "P2" : "P1";

    // Win check
    if (checkC4Win(board, player)) {
      activeGameState.winner = player;
      playSound("win");
      TouchSystem.triggerHaptic("success");
      showToast(`🎉 Player ${player} Wins!`);
      if (player === 1) awardProgressionXP(100, true);
    }

    renderConnectFour();
    return true;
  }

  function checkC4Win(b, p) {
    // Horizontal, Vertical, Diagonal checks
    for (let r = 0; r < 6; r++) {
      for (let c = 0; c < 7; c++) {
        if (c + 3 < 7 && b[r][c] === p && b[r][c+1] === p && b[r][c+2] === p && b[r][c+3] === p) return true;
        if (r + 3 < 6 && b[r][c] === p && b[r+1][c] === p && b[r+2][c] === p && b[r+3][c] === p) return true;
        if (r + 3 < 6 && c + 3 < 7 && b[r][c] === p && b[r+1][c+1] === p && b[r+2][c+2] === p && b[r+3][c+3] === p) return true;
        if (r - 3 >= 0 && c + 3 < 7 && b[r][c] === p && b[r-1][c+1] === p && b[r-2][c+2] === p && b[r-3][c+3] === p) return true;
      }
    }
    return false;
  }

  function renderConnectFour() {
    const board = activeGameState.board;
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Turn: <b style="color: ${activeGameState.current_turn === 'P1' ? 'var(--likby-cyan)' : 'var(--likby-pink)'};">${activeGameState.current_turn === 'P1' ? 'Your Disc (Cyan)' : 'Opponent (Pink)'}</b></span>
          <span class="touch-status-pill">📱 Touch Column / Drag</span>
        </div>
        <div class="c4-board touch-interactive-surface" id="c4Board">
          ${board.map((row, r) => row.map((cell, c) => `
            <div class="c4-cell ${cell === 1 ? 'p1' : cell === 2 ? 'p2' : ''}" data-col="${c}"></div>
          `).join("")).join("")}
        </div>
        <div style="display: flex; gap: 8px;">
          ${[0,1,2,3,4,5,6].map((c) => `<button class="btn-primary c4-btn" data-col="${c}" style="flex: 1; padding: 10px 0; font-size: 14px;">↓</button>`).join("")}
        </div>
      </div>
    `;

    const boardEl = document.getElementById("c4Board");
    if (boardEl) {
      const handleTouchMove = (e) => {
        if (activeGameState.winner) return;
        const pos = TouchSystem.getTouchPos(e, boardEl);
        const colWidth = pos.rect.width / 7;
        const col = Math.floor(pos.x / colWidth);
        if (col >= 0 && col < 7) {
          boardEl.querySelectorAll(".c4-cell").forEach((cell) => {
            cell.classList.toggle("c4-col-highlight", parseInt(cell.dataset.col) === col);
          });
        }
      };

      boardEl.addEventListener("touchmove", handleTouchMove, { passive: true });
      boardEl.addEventListener("touchend", (e) => {
        if (activeGameState.winner) return;
        const pos = TouchSystem.getTouchPos(e, boardEl);
        const colWidth = pos.rect.width / 7;
        const col = Math.min(6, Math.max(0, Math.floor(pos.x / colWidth)));
        boardEl.querySelectorAll(".c4-cell").forEach((cell) => cell.classList.remove("c4-col-highlight"));
        if (dropDisc(col, activeGameState.current_turn === "P1" ? 1 : 2)) {
          submitAction("drop_disc", { column: col });
        }
      });
    }

    canvasContainer.querySelectorAll(".c4-cell, .c4-btn").forEach((el) => {
      el.addEventListener("click", () => {
        if (activeGameState.winner) return;
        const col = parseInt(el.dataset.col);
        if (dropDisc(col, activeGameState.current_turn === "P1" ? 1 : 2)) {
          submitAction("drop_disc", { column: col });
        }
      });
    });
  }

  // --------------------------------------------------------------------------
  // GAME 1B: XO (TIC-TAC-TOE DUEL)
  // --------------------------------------------------------------------------
  function placeXOMark(r, c) {
    if (!activeGameState || activeGameState.winner) return;
    if (activeGameState.board[r][c] !== "") {
      playSound("error");
      TouchSystem.triggerHaptic("warning");
      showToast("⚠️ Cell already marked!");
      return;
    }
    if (isPracticeMode && activeGameState.current_turn !== "P1") {
      playSound("error");
      TouchSystem.triggerHaptic("warning");
      return;
    }

    const mark = activeGameState.current_turn === "P1" ? "X" : "O";
    activeGameState.board[r][c] = mark;
    activeGameState.move_count = (activeGameState.move_count || 0) + 1;
    playSound(mark === "X" ? "strike" : "drop");
    TouchSystem.triggerHaptic("light");

    const winResult = checkXOWin(activeGameState.board, mark);
    if (winResult.won) {
      activeGameState.winner = activeGameState.current_turn;
      activeGameState.winning_cells = winResult.cells;
      playSound("win");
      TouchSystem.triggerHaptic("success");
      showToast(activeGameState.winner === "P1" ? "🎉 Victory! You aligned 3 marks!" : "🤖 Opponent won this round!");
      if (activeGameState.winner === "P1") awardProgressionXP(100, true);
    } else if (activeGameState.move_count >= 9) {
      activeGameState.winner = "DRAW";
      playSound("score");
      TouchSystem.triggerHaptic("selection");
      showToast("🤝 Match ended in a draw!");
    } else {
      activeGameState.current_turn = (activeGameState.current_turn === "P1" ? "P2" : "P1");
    }

    submitAction("place_mark", { row: r, col: c, cell: r * 3 + c });
    renderXO();
  }

  function checkXOWin(b, m) {
    for (let r = 0; r < 3; r++) {
      if (b[r][0] === m && b[r][1] === m && b[r][2] === m) {
        return { won: true, cells: [[r,0], [r,1], [r,2]] };
      }
    }
    for (let c = 0; c < 3; c++) {
      if (b[0][c] === m && b[1][c] === m && b[2][c] === m) {
        return { won: true, cells: [[0,c], [1,c], [2,c]] };
      }
    }
    if (b[0][0] === m && b[1][1] === m && b[2][2] === m) {
      return { won: true, cells: [[0,0], [1,1], [2,2]] };
    }
    if (b[0][2] === m && b[1][1] === m && b[2][0] === m) {
      return { won: true, cells: [[0,2], [1,1], [2,0]] };
    }
    return { won: false, cells: [] };
  }

  function makeAiXOMove() {
    if (!activeGameState || activeGameState.winner || activeGameState.current_turn !== "P2") return;
    const b = activeGameState.board;

    function findWinningMove(mark) {
      for (let r = 0; r < 3; r++) {
        for (let c = 0; c < 3; c++) {
          if (b[r][c] === "") {
            b[r][c] = mark;
            const res = checkXOWin(b, mark);
            b[r][c] = "";
            if (res.won) return { r, c };
          }
        }
      }
      return null;
    }

    let move = findWinningMove("O");
    if (!move) move = findWinningMove("X");
    if (!move && b[1][1] === "") move = { r: 1, c: 1 };
    if (!move) {
      const corners = [[0,0], [0,2], [2,0], [2,2]].filter(([r,c]) => b[r][c] === "");
      if (corners.length > 0) {
        const [cr, cc] = corners[Math.floor(Math.random() * corners.length)];
        move = { r: cr, c: cc };
      }
    }
    if (!move) {
      const empties = [];
      for (let r = 0; r < 3; r++) {
        for (let c = 0; c < 3; c++) {
          if (b[r][c] === "") empties.push({ r, c });
        }
      }
      if (empties.length > 0) {
        move = empties[Math.floor(Math.random() * empties.length)];
      }
    }

    if (move) {
      b[move.r][move.c] = "O";
      activeGameState.move_count = (activeGameState.move_count || 0) + 1;
      playSound("drop");

      const winResult = checkXOWin(b, "O");
      if (winResult.won) {
        activeGameState.winner = "P2";
        activeGameState.winning_cells = winResult.cells;
        playSound("win");
        showToast("🤖 AI Bot aligned 3 marks!");
      } else if (activeGameState.move_count >= 9) {
        activeGameState.winner = "DRAW";
        playSound("score");
        showToast("🤝 Match ended in a draw!");
      } else {
        activeGameState.current_turn = "P1";
      }
      renderXO();
    }
  }

  function renderXO() {
    if (!canvasContainer || !activeGameState) return;
    const b = activeGameState.board;
    const winCells = activeGameState.winning_cells || [];
    const isWinCell = (r, c) => winCells.some(([wr, wc]) => wr === r && wc === c);

    let statusText = "";
    if (activeGameState.winner === "P1") {
      statusText = "🏆 <b style='color: var(--likby-cyan);'>Player 1 (X) Wins!</b>";
    } else if (activeGameState.winner === "P2") {
      statusText = "🏆 <b style='color: var(--likby-pink);'>Player 2 (O) Wins!</b>";
    } else if (activeGameState.winner === "DRAW") {
      statusText = "🤝 <b style='color: var(--likby-amber);'>Match Drawn!</b>";
    } else if (activeGameState.current_turn === "P1") {
      statusText = "⚡ <b style='color: var(--likby-cyan);'>Your Turn (X)</b>";
    } else {
      statusText = `⏳ <b style='color: var(--likby-pink);'>${isPracticeMode ? "AI Thinking..." : "Partner Turn (O)"}</b>`;
    }

    canvasContainer.innerHTML = `
      <div class="xo-arena">
        <div class="xo-status-panel">
          <div class="xo-player-badge x">❌ P1 (X)</div>
          <div style="font-size: 13px;">${statusText}</div>
          <div class="xo-player-badge o">⭕ P2 (O)</div>
        </div>

        <div class="xo-board">
          ${[0, 1, 2].map(r => [0, 1, 2].map(c => {
            const val = b[r][c];
            const cls = val === 'X' ? 'x' : val === 'O' ? 'o' : '';
            const winCls = isWinCell(r, c) ? 'winning' : '';
            return `<button class="xo-cell ${cls} ${winCls}" data-row="${r}" data-col="${c}">${val}</button>`;
          }).join('')).join('')}
        </div>

        <div class="xo-actions">
          ${activeGameState.winner ? `
            <button class="btn-primary" id="xoRematchBtn" style="flex: 1;">🔄 Play Again</button>
          ` : `
            <div style="font-size: 12px; color: var(--likby-text-muted); text-align: center; width: 100%;">
              Align 3 symbols horizontally, vertically, or diagonally to win.
            </div>
          `}
        </div>
      </div>
    `;

    canvasContainer.querySelectorAll(".xo-cell").forEach(cell => {
      cell.addEventListener("click", () => {
        const r = parseInt(cell.dataset.row, 10);
        const c = parseInt(cell.dataset.col, 10);
        placeXOMark(r, c);
      });
    });

    document.getElementById("xoRematchBtn")?.addEventListener("click", () => {
      playSound("click");
      activeGameState = getInitialGameState("xo");
      renderXO();
    });
  }

  // --------------------------------------------------------------------------
  // GAME 2: CARROM CLASH
  // --------------------------------------------------------------------------
  function renderCarromClash() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 13px;">
          <span>P1 Score: <b style="color: var(--likby-cyan);">${activeGameState.p1_score}</b></span>
          <span class="touch-status-pill">📱 Touch Drag & Aim</span>
          <span>P2 Score: <b style="color: var(--likby-pink);">${activeGameState.p2_score}</b></span>
        </div>
        <div class="carrom-board touch-interactive-surface" id="carromBoard">
          <div class="carrom-pocket" style="top: 8px; left: 8px;"></div>
          <div class="carrom-pocket" style="top: 8px; right: 8px;"></div>
          <div class="carrom-pocket" style="bottom: 8px; left: 8px;"></div>
          <div class="carrom-pocket" style="bottom: 8px; right: 8px;"></div>
          <div class="carrom-center-circle"></div>
          <!-- Carrom Pieces -->
          <div class="carrom-piece queen" style="top: 135px; left: 135px;"></div>
          <div class="carrom-piece white" style="top: 110px; left: 135px;"></div>
          <div class="carrom-piece black" style="top: 160px; left: 135px;"></div>
          <div class="carrom-piece white" style="top: 135px; left: 110px;"></div>
          <div class="carrom-piece black" style="top: 135px; left: 160px;"></div>
          <!-- Striker -->
          <div class="carrom-striker" id="carromStriker" style="bottom: 34px; left: 130px;"></div>
          <div id="carromAimLine" class="touch-slingshot-line" style="display: none;"></div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 8px;">
          <div style="display: flex; align-items: center; gap: 10px; font-size: 12px;">
            <span>Aim Angle:</span>
            <input type="range" id="carromAngle" min="-60" max="60" value="0" style="flex: 1;" />
          </div>
          <button class="btn-primary" id="carromStrikeBtn">💥 Release Strike</button>
        </div>
      </div>
    `;

    const striker = document.getElementById("carromStriker");
    const board = document.getElementById("carromBoard");
    const aimLine = document.getElementById("carromAimLine");
    let isDragging = false;
    let dragStartX = 0, dragStartY = 0;

    const executeStrike = (angle, power) => {
      playSound("strike");
      TouchSystem.triggerHaptic("heavy");
      if (striker) {
        striker.style.transform = `translate(${angle * 1.5}px, -180px)`;
        setTimeout(() => {
          striker.style.transform = "none";
          activeGameState.p1_score += 10;
          playSound("score");
          TouchSystem.triggerHaptic("success");
          renderCarromClash();
        }, 350);
      }
      submitAction("strike", { angle, power });
    };

    if (striker && board) {
      const onTouchStart = (e) => {
        isDragging = true;
        const pos = TouchSystem.getTouchPos(e, board);
        dragStartX = pos.x;
        dragStartY = pos.y;
        TouchSystem.triggerHaptic("light");
      };

      const onTouchMove = (e) => {
        if (!isDragging) return;
        const pos = TouchSystem.getTouchPos(e, board);
        const dx = pos.x - dragStartX;
        const dy = pos.y - dragStartY;

        // Position striker along baseline
        const clampedX = Math.min(250, Math.max(40, pos.x - 16));
        striker.style.left = `${clampedX}px`;

        if (dy > 10 && aimLine) {
          // Draw slingshot aim line
          aimLine.style.display = "block";
          aimLine.style.left = `${clampedX + 16}px`;
          aimLine.style.top = "266px";
          const dist = Math.min(100, Math.hypot(dx, dy));
          const rad = Math.atan2(-dy, -dx);
          aimLine.style.width = `${dist * 1.5}px`;
          aimLine.style.transform = `rotate(${rad}rad)`;
        }
      };

      const onTouchEnd = (e) => {
        if (!isDragging) return;
        isDragging = false;
        if (aimLine) aimLine.style.display = "none";
        const pos = TouchSystem.getTouchPos(e, board);
        const dx = pos.x - dragStartX;
        const dy = pos.y - dragStartY;
        if (dy > 15) {
          const power = Math.min(100, Math.round(Math.hypot(dx, dy) * 1.5));
          const angle = Math.min(60, Math.max(-60, Math.round(-dx * 1.2)));
          executeStrike(angle, power);
        }
      };

      striker.addEventListener("touchstart", onTouchStart, { passive: true });
      board.addEventListener("touchmove", onTouchMove, { passive: true });
      window.addEventListener("touchend", onTouchEnd);
    }

    document.getElementById("carromStrikeBtn")?.addEventListener("click", () => {
      const angle = parseFloat(document.getElementById("carromAngle")?.value || 0);
      executeStrike(angle, 85);
    });
  }

  // --------------------------------------------------------------------------
  // GAME 3: AIR RUSH
  // --------------------------------------------------------------------------
  function renderAirRush() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 13px;">
          <span>Goals P1: <b style="color: var(--likby-cyan);">${activeGameState.p1_score}</b></span>
          <span class="touch-status-pill">📱 Drag Paddle 1:1</span>
          <span>Goals P2: <b style="color: var(--likby-pink);">${activeGameState.p2_score}</b></span>
        </div>
        <div class="air-hockey-table touch-interactive-surface" id="airTable">
          <div style="position: absolute; top: 50%; left: 0; right: 0; height: 2px; background: rgba(34, 211, 238, 0.4);"></div>
          <div class="air-paddle p2" id="airP2Paddle" style="top: 20px; left: 128px;"></div>
          <div class="air-puck" id="airPuck" style="top: 177px; left: 137px;"></div>
          <div class="air-paddle p1" id="airP1Paddle" style="bottom: 20px; left: 128px;"></div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn-secondary" id="airDefendBtn" style="flex: 1;">🛡 Intercept</button>
          <button class="btn-primary" id="airShootBtn" style="flex: 2;">🏒 Power Shot</button>
        </div>
      </div>
    `;

    const table = document.getElementById("airTable");
    const paddle = document.getElementById("airP1Paddle");
    const puck = document.getElementById("airPuck");

    const shootGoal = () => {
      playSound("strike");
      TouchSystem.triggerHaptic("heavy");
      if (puck) {
        puck.style.transform = "translate(40px, -140px)";
        setTimeout(() => {
          puck.style.transform = "none";
          activeGameState.p1_score++;
          playSound("win");
          TouchSystem.triggerHaptic("success");
          showToast("⚡ GOAL SCORED!");
          renderAirRush();
        }, 350);
      }
      submitAction("score_goal", {});
    };

    if (table && paddle) {
      const handleTableTouch = (e) => {
        const pos = TouchSystem.getTouchPos(e, table);
        // Validate paddle coordinates: strictly within player's lower half
        const clampedX = Math.min(256, Math.max(0, pos.x - 22));
        const clampedY = Math.min(336, Math.max(190, pos.y - 22));
        paddle.style.left = `${clampedX}px`;
        paddle.style.top = `${clampedY}px`;
        paddle.style.bottom = "auto";

        // Collision check with puck
        if (puck && clampedY <= 205 && Math.abs(clampedX - 128) < 40) {
          shootGoal();
        }
      };

      table.addEventListener("touchstart", (e) => {
        TouchSystem.triggerHaptic("light");
        handleTableTouch(e);
      }, { passive: true });
      table.addEventListener("touchmove", handleTableTouch, { passive: true });
    }

    document.getElementById("airShootBtn")?.addEventListener("click", shootGoal);
    document.getElementById("airDefendBtn")?.addEventListener("click", () => {
      playSound("move");
      TouchSystem.triggerHaptic("medium");
      if (paddle) paddle.style.transform = "translateX(-50px)";
      setTimeout(() => paddle && (paddle.style.transform = "none"), 300);
      submitAction("move_paddle", { x: 80, y: 300 });
    });
  }

  // --------------------------------------------------------------------------
  // GAME 4: POCKET POOL
  // --------------------------------------------------------------------------
  function renderPocketPool() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-size: 13px;">
          <span>Solids: <b style="color: #facc15;">${activeGameState.solids_left}</b></span>
          <span class="touch-status-pill">📱 Cue Ball Slingshot</span>
          <span>Stripes: <b style="color: #38bdf8;">${activeGameState.stripes_left}</b></span>
        </div>
        <div id="poolTable" class="touch-interactive-surface" style="width: 310px; height: 210px; background: #064e3b; border: 12px solid #78350f; border-radius: 16px; position: relative; margin: 0 auto; box-shadow: inset 0 0 20px rgba(0,0,0,0.6); overflow: hidden;">
          <!-- 6 Pockets -->
          <div style="position: absolute; top: 4px; left: 4px; width: 22px; height: 22px; background: #000; border-radius: 50%;"></div>
          <div style="position: absolute; top: 4px; left: 144px; width: 22px; height: 22px; background: #000; border-radius: 50%;"></div>
          <div style="position: absolute; top: 4px; right: 4px; width: 22px; height: 22px; background: #000; border-radius: 50%;"></div>
          <div style="position: absolute; bottom: 4px; left: 4px; width: 22px; height: 22px; background: #000; border-radius: 50%;"></div>
          <div style="position: absolute; bottom: 4px; left: 144px; width: 22px; height: 22px; background: #000; border-radius: 50%;"></div>
          <div style="position: absolute; bottom: 4px; right: 4px; width: 22px; height: 22px; background: #000; border-radius: 50%;"></div>
          <!-- Cue Ball -->
          <div id="cueBall" style="position: absolute; top: 96px; left: 60px; width: 18px; height: 18px; background: #fff; border-radius: 50%; box-shadow: 0 0 8px #fff; cursor: grab; z-index: 10;"></div>
          <!-- Object Balls -->
          <div id="poolBall8" style="position: absolute; top: 96px; left: 190px; width: 18px; height: 18px; background: #000; color: #fff; font-size: 10px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; transition: transform 0.3s ease;">8</div>
          <div id="poolBallSolid" style="position: absolute; top: 80px; left: 210px; width: 18px; height: 18px; background: #facc15; border-radius: 50%; transition: transform 0.3s ease;"></div>
          <div id="poolBallStripe" style="position: absolute; top: 110px; left: 210px; width: 18px; height: 18px; background: #38bdf8; border-radius: 50%; transition: transform 0.3s ease;"></div>
          <!-- Slingshot Aim Line -->
          <div id="poolAimLine" class="touch-slingshot-line" style="display: none;"></div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn-secondary" id="potSolidBtn" style="flex: 1;">Pot Solid 🟡</button>
          <button class="btn-secondary" id="potStripeBtn" style="flex: 1;">Pot Stripe 🔵</button>
          <button class="btn-primary" id="cueStrikeBtn" style="flex: 1.5;">Break Rack 🎱</button>
        </div>
      </div>
    `;

    const cueBall = document.getElementById("cueBall");
    const poolTable = document.getElementById("poolTable");
    const poolAimLine = document.getElementById("poolAimLine");
    let isDragging = false;
    let dragStartX = 0, dragStartY = 0;

    const executeCueShot = (angle, power) => {
      playSound("strike");
      TouchSystem.triggerHaptic("heavy");
      if (cueBall) {
        cueBall.style.transform = `translate(${Math.cos(angle * Math.PI / 180) * power * 1.5}px, ${Math.sin(angle * Math.PI / 180) * power * 1.5}px)`;
        setTimeout(() => {
          cueBall.style.transform = "none";
          const ball8 = document.getElementById("poolBall8");
          const ballS = document.getElementById("poolBallSolid");
          const ballSt = document.getElementById("poolBallStripe");
          if (ball8) ball8.style.transform = "translate(20px, -15px)";
          if (ballS) ballS.style.transform = "translate(30px, 25px)";
          if (ballSt) ballSt.style.transform = "translate(35px, -30px)";
          playSound("score");
          TouchSystem.triggerHaptic("success");
          if (activeGameState.solids_left > 0) activeGameState.solids_left--;
          showToast("🎱 Solid shot! Ball potted into corner pocket!");
          setTimeout(() => renderPocketPool(), 500);
        }, 300);
      }
      submitAction("strike_cue_ball", { angle, power });
    };

    if (cueBall && poolTable) {
      cueBall.addEventListener("touchstart", (e) => {
        isDragging = true;
        const pos = TouchSystem.getTouchPos(e, poolTable);
        dragStartX = pos.x;
        dragStartY = pos.y;
        TouchSystem.triggerHaptic("light");
      }, { passive: true });

      poolTable.addEventListener("touchmove", (e) => {
        if (!isDragging) return;
        const pos = TouchSystem.getTouchPos(e, poolTable);
        const dx = pos.x - dragStartX;
        const dy = pos.y - dragStartY;
        if (poolAimLine) {
          poolAimLine.style.display = "block";
          poolAimLine.style.left = "69px";
          poolAimLine.style.top = "105px";
          const dist = Math.min(100, Math.hypot(dx, dy));
          const rad = Math.atan2(-dy, -dx);
          poolAimLine.style.width = `${dist * 1.6}px`;
          poolAimLine.style.transform = `rotate(${rad}rad)`;
        }
      }, { passive: true });

      window.addEventListener("touchend", (e) => {
        if (!isDragging) return;
        isDragging = false;
        if (poolAimLine) poolAimLine.style.display = "none";
        const pos = TouchSystem.getTouchPos(e, poolTable);
        const dx = pos.x - dragStartX;
        const dy = pos.y - dragStartY;
        const dist = Math.hypot(dx, dy);
        if (dist > 15) {
          const power = Math.min(100, Math.round(dist * 1.4));
          const angle = Math.round(Math.atan2(-dy, -dx) * (180 / Math.PI));
          executeCueShot(angle, power);
        }
      }, { once: true });
    }

    document.getElementById("potSolidBtn")?.addEventListener("click", () => {
      if (activeGameState.solids_left > 0) activeGameState.solids_left--;
      playSound("score");
      TouchSystem.triggerHaptic("medium");
      renderPocketPool();
      submitAction("pot_ball", { ball: "SOLID" });
    });
    document.getElementById("potStripeBtn")?.addEventListener("click", () => {
      if (activeGameState.stripes_left > 0) activeGameState.stripes_left--;
      playSound("score");
      TouchSystem.triggerHaptic("medium");
      renderPocketPool();
      submitAction("pot_ball", { ball: "STRIPE" });
    });
    document.getElementById("cueStrikeBtn")?.addEventListener("click", () => {
      executeCueShot(0, 85);
    });
  }

  // --------------------------------------------------------------------------
  // GAME 5: STICK ARENA
  // --------------------------------------------------------------------------
  function renderStickArena() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
          <div style="width: 40%;">
            <div style="font-size: 11px; font-weight: 800; color: var(--likby-cyan);">PLAYER 1: ${activeGameState.p1_hp}% HP</div>
            <div style="height: 10px; background: #1e293b; border-radius: 6px; overflow: hidden; margin-top: 4px;">
              <div style="width: ${activeGameState.p1_hp}%; height: 100%; background: var(--likby-cyan); transition: width 0.3s ease;"></div>
            </div>
          </div>
          <span class="touch-status-pill">📱 Touch Arena / Swipe</span>
          <div style="width: 40%; text-align: right;">
            <div style="font-size: 11px; font-weight: 800; color: var(--likby-pink);">PLAYER 2: ${activeGameState.p2_hp}% HP</div>
            <div style="height: 10px; background: #1e293b; border-radius: 6px; overflow: hidden; margin-top: 4px;">
              <div style="width: ${activeGameState.p2_hp}%; height: 100%; background: var(--likby-pink); float: right; transition: width 0.3s ease;"></div>
            </div>
          </div>
        </div>
        <div class="arena-stage touch-interactive-surface" id="arenaStage">
          <div class="fighter-sprite" id="f1" style="left: ${activeGameState.p1_x}px;">🤺</div>
          <div class="fighter-sprite" id="f2" style="left: ${activeGameState.p2_x}px; transform: scaleX(-1);">🥷</div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn-secondary" id="stickLeft">◀ Move</button>
          <button class="btn-secondary" id="stickRight">Move ▶</button>
          <button class="btn-primary" id="stickSlash">⚔️ Light Slash</button>
          <button class="btn-primary" id="stickHeavy" style="background: linear-gradient(135deg, var(--likby-violet), var(--likby-pink));">💥 Heavy Burst</button>
        </div>
      </div>
    `;

    const stage = document.getElementById("arenaStage");
    let stageTouchStartX = 0;
    if (stage) {
      stage.addEventListener("touchstart", (e) => {
        const pos = TouchSystem.getTouchPos(e, stage);
        stageTouchStartX = pos.x;
        TouchSystem.triggerHaptic("light");
      }, { passive: true });

      stage.addEventListener("touchend", (e) => {
        const pos = TouchSystem.getTouchPos(e, stage);
        const dx = pos.x - stageTouchStartX;
        if (Math.abs(dx) > 30) {
          if (dx > 0) {
            activeGameState.p1_x = Math.min(160, activeGameState.p1_x + 40);
          } else {
            activeGameState.p1_x = Math.max(10, activeGameState.p1_x - 40);
          }
          playSound("move");
          TouchSystem.triggerHaptic("medium");
          renderStickArena();
          submitAction("move", { dx: dx > 0 ? 40 : -40 });
        } else {
          // Tap on stage to slash
          triggerAttack("light");
        }
      });
    }

    const triggerAttack = (type) => {
      playSound("strike");
      TouchSystem.triggerHaptic(type === "heavy" ? "heavy" : "medium");
      const f1 = document.getElementById("f1");
      const f2 = document.getElementById("f2");
      f1?.classList.add("attack");
      f2?.classList.add("hit");
      const dmg = type === "heavy" ? 30 : 15;
      activeGameState.p2_hp = Math.max(0, activeGameState.p2_hp - dmg);
      if (activeGameState.p2_hp === 0) {
        playSound("win");
        TouchSystem.triggerHaptic("success");
        showToast("🏆 K.O.! You defeated your rival!");
      }
      setTimeout(() => renderStickArena(), 250);
      submitAction("attack", { attack_type: type });
    };

    const bindTouchAction = (id, fn) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.addEventListener("touchstart", (e) => {
        e.preventDefault();
        fn();
      });
      el.addEventListener("click", fn);
    };

    bindTouchAction("stickLeft", () => {
      activeGameState.p1_x = Math.max(10, activeGameState.p1_x - 30);
      playSound("move");
      TouchSystem.triggerHaptic("light");
      renderStickArena();
      submitAction("move", { dx: -30 });
    });
    bindTouchAction("stickRight", () => {
      activeGameState.p1_x = Math.min(160, activeGameState.p1_x + 30);
      playSound("move");
      TouchSystem.triggerHaptic("light");
      renderStickArena();
      submitAction("move", { dx: 30 });
    });
    bindTouchAction("stickSlash", () => triggerAttack("light"));
    bindTouchAction("stickHeavy", () => triggerAttack("heavy"));
  }

  // --------------------------------------------------------------------------
  // GAME 6: QUICKDRAW
  // --------------------------------------------------------------------------
  function renderQuickDraw() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-size: 13px;">
          <span>Draw: <b style="color: var(--likby-cyan); font-size: 16px;">${activeGameState.word}</b></span>
          <span class="touch-status-pill">📱 Touch Stylus / Canvas</span>
        </div>
        <canvas id="qdCanvas" width="300" height="250" style="background: #ffffff; border-radius: 14px; margin: 0 auto; touch-action: none; cursor: crosshair; box-shadow: 0 4px 16px rgba(0,0,0,0.5);"></canvas>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
          <div style="display: flex; gap: 6px;" id="qdColorPalette">
            <div class="qd-col-dot" data-col="#0f172a" style="width: 24px; height: 24px; border-radius: 50%; background: #0f172a; border: 2px solid #fff; cursor: pointer;"></div>
            <div class="qd-col-dot" data-col="#22d3ee" style="width: 24px; height: 24px; border-radius: 50%; background: #22d3ee; cursor: pointer;"></div>
            <div class="qd-col-dot" data-col="#ec4899" style="width: 24px; height: 24px; border-radius: 50%; background: #ec4899; cursor: pointer;"></div>
            <div class="qd-col-dot" data-col="#f59e0b" style="width: 24px; height: 24px; border-radius: 50%; background: #f59e0b; cursor: pointer;"></div>
          </div>
          <button class="btn-secondary" id="qdClear" style="padding: 8px 14px;">Clear 🗑</button>
          <button class="btn-primary" id="qdSend" style="flex: 1;">Submit 🚀</button>
        </div>
      </div>
    `;

    const canvas = document.getElementById("qdCanvas");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let isDrawing = false;
    let strokeCount = 0;
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 4;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    document.querySelectorAll(".qd-col-dot").forEach((dot) => {
      dot.addEventListener("click", () => {
        ctx.strokeStyle = dot.dataset.col;
        document.querySelectorAll(".qd-col-dot").forEach(d => d.style.border = "none");
        dot.style.border = "2px solid #fff";
        TouchSystem.triggerHaptic("selection");
      });
    });

    const startDraw = (e) => {
      isDrawing = true;
      strokeCount++;
      TouchSystem.triggerHaptic("soft");
      ctx.beginPath();
      const rect = canvas.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      ctx.moveTo(clientX - rect.left, clientY - rect.top);
    };

    const draw = (e) => {
      if (!isDrawing) return;
      if (e.cancelable) e.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      ctx.lineTo(clientX - rect.left, clientY - rect.top);
      ctx.stroke();
    };

    const stopDraw = () => { isDrawing = false; };

    canvas.addEventListener("mousedown", startDraw);
    canvas.addEventListener("mousemove", draw);
    window.addEventListener("mouseup", stopDraw);

    canvas.addEventListener("touchstart", startDraw, { passive: false });
    canvas.addEventListener("touchmove", draw, { passive: false });
    window.addEventListener("touchend", stopDraw);

    document.getElementById("qdClear")?.addEventListener("click", () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      strokeCount = 0;
      playSound("click");
      TouchSystem.triggerHaptic("light");
    });

    document.getElementById("qdSend")?.addEventListener("click", () => {
      if (strokeCount === 0) {
        playSound("error");
        TouchSystem.triggerHaptic("warning");
        showToast("⚠️ Please draw something before submitting!");
        return;
      }
      playSound("win");
      TouchSystem.triggerHaptic("success");
      showToast("✨ Drawing sent to partner!");
      submitAction("add_stroke", {});
    });
  }

  // --------------------------------------------------------------------------
  // GAME 7: WORD RUSH
  // --------------------------------------------------------------------------
  function renderWordRush() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
          <span>Letters:</span>
          <span class="touch-status-pill">📱 Tap Letter Tiles</span>
          <span>Score: <b style="color: var(--likby-cyan);">${activeGameState.score} pts</b></span>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; padding: 16px 0;">
          ${activeGameState.letters.map((l) => `
            <div class="quick-chip wr-tile" data-letter="${l}" style="font-size: 20px; font-weight: 800; width: 44px; height: 44px; justify-content: center; background: var(--likby-surface-raised); border-color: var(--likby-cyan); cursor: pointer; user-select: none;">${l}</div>
          `).join("")}
        </div>
        <div style="display: flex; gap: 6px; margin-bottom: 8px; justify-content: center;">
          <button class="btn-secondary" id="wrBackspaceBtn" style="padding: 8px 16px;">⌫ Backspace</button>
          <button class="btn-secondary" id="wrClearBtn" style="padding: 8px 16px;">🗑 Clear</button>
        </div>
        <div style="display: flex; gap: 8px;">
          <input type="text" id="wrInput" class="input-field" placeholder="Form word..." readonly style="font-weight: 800; letter-spacing: 2px; font-size: 16px;" />
          <button class="btn-primary" id="wrSubmit">Submit 🔤</button>
        </div>
      </div>
    `;

    document.querySelectorAll(".wr-tile").forEach((tile) => {
      const handleTilePick = () => {
        const input = document.getElementById("wrInput");
        if (input) input.value += tile.dataset.letter;
        playSound("click");
        TouchSystem.triggerHaptic("light");
        tile.classList.add("touched");
        setTimeout(() => tile.classList.remove("touched"), 150);
      };
      tile.addEventListener("touchstart", (e) => {
        e.preventDefault();
        handleTilePick();
      });
      tile.addEventListener("click", handleTilePick);
    });

    document.getElementById("wrBackspaceBtn")?.addEventListener("click", () => {
      const input = document.getElementById("wrInput");
      if (input && input.value.length > 0) {
        input.value = input.value.slice(0, -1);
        playSound("click");
        TouchSystem.triggerHaptic("light");
      }
    });

    document.getElementById("wrClearBtn")?.addEventListener("click", () => {
      const input = document.getElementById("wrInput");
      if (input) {
        input.value = "";
        playSound("click");
        TouchSystem.triggerHaptic("selection");
      }
    });

    document.getElementById("wrSubmit")?.addEventListener("click", () => {
      const input = document.getElementById("wrInput");
      const word = input?.value.trim().toUpperCase();
      if (word && word.length >= 2) {
        activeGameState.score += word.length * 10;
        playSound("score");
        TouchSystem.triggerHaptic("success");
        showToast(`+${word.length * 10} Points for "${word}"! 🔤`);
        input.value = "";
        renderWordRush();
        submitAction("submit_word", { word });
      } else {
        playSound("error");
        TouchSystem.triggerHaptic("warning");
        showToast("⚠️ Form at least a 2-letter word!");
      }
    });
  }

  // --------------------------------------------------------------------------
  // GAME 8: BRAIN BLITZ
  // --------------------------------------------------------------------------
  function renderBrainBlitz() {
    const q = activeGameState.questions[activeGameState.question_idx] || { q: "All questions finished!", options: [] };
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Question ${activeGameState.question_idx + 1} of 3</span>
          <span class="touch-status-pill">📱 Instant Touch Answers</span>
          <span>Score: <b style="color: var(--likby-cyan);">${activeGameState.p1_score} pts</b></span>
        </div>
        <div style="text-align: center; font-size: 17px; font-weight: 800; line-height: 1.4; margin: 20px 0;">
          ${q.q}
        </div>
        <div style="display: flex; flex-direction: column; gap: 10px;">
          ${q.options.map((opt, i) => `
            <button class="btn-secondary bb-opt-btn" data-idx="${i}" style="text-align: left; padding: 14px 18px; font-size: 14px; user-select: none;">${opt}</button>
          `).join("")}
        </div>
      </div>
    `;

    document.querySelectorAll(".bb-opt-btn").forEach((btn) => {
      const handleAnswer = () => {
        const chosen = parseInt(btn.dataset.idx);
        if (chosen === q.ans) {
          activeGameState.p1_score += 100;
          playSound("score");
          TouchSystem.triggerHaptic("success");
          btn.style.borderColor = "var(--likby-emerald)";
          btn.style.background = "rgba(16, 185, 129, 0.25)";
        } else {
          playSound("error");
          TouchSystem.triggerHaptic("warning");
          btn.style.borderColor = "var(--likby-pink)";
          btn.style.background = "rgba(236, 72, 153, 0.25)";
        }

        setTimeout(() => {
          activeGameState.question_idx++;
          if (activeGameState.question_idx >= activeGameState.questions.length) {
            playSound("win");
            TouchSystem.triggerHaptic("success");
            showToast("🧠 Trivia Duel Completed!");
          }
          renderBrainBlitz();
          submitAction("answer_question", { question_index: activeGameState.question_idx, chosen_index: chosen });
        }, 500);
      };

      btn.addEventListener("touchstart", (e) => {
        e.preventDefault();
        handleAnswer();
      });
      btn.addEventListener("click", handleAnswer);
    });
  }

  // --------------------------------------------------------------------------
  // GAME 9: REFLEX RUSH
  // --------------------------------------------------------------------------
  function renderReflexRush() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; align-items: center; justify-content: space-between; height: 100%; padding: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-size: 13px;">
          <span>Round ${activeGameState.round} of 3</span>
          <span class="touch-status-pill">📱 Zero-Latency Reflex Tap</span>
          <span>Reaction Duel</span>
        </div>
        <div id="reflexOrb" style="width: 220px; height: 220px; border-radius: 50%; background: #ef4444; display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 22px; font-weight: 900; color: #fff; cursor: pointer; box-shadow: 0 0 40px rgba(239, 68, 68, 0.6); transition: all 0.2s ease; user-select: none;">
          WAIT... 🛑
        </div>
        <div style="font-size: 12px; color: var(--likby-text-muted);">
          Tap immediately when orb turns GREEN!
        </div>
      </div>
    `;

    const orb = document.getElementById("reflexOrb");
    const delay = Math.random() * 2000 + 1500;
    activeGameState.ready = false;

    const timer = setTimeout(() => {
      if (!orb) return;
      activeGameState.ready = true;
      activeGameState.green_time = Date.now();
      orb.style.background = "#10b981";
      orb.style.boxShadow = "0 0 50px rgba(16, 185, 129, 0.9)";
      orb.textContent = "TAP NOW! ⚡";
      playSound("click");
      TouchSystem.triggerHaptic("medium");
    }, delay);

    const handleOrbTap = () => {
      if (!activeGameState.ready) {
        clearTimeout(timer);
        playSound("error");
        TouchSystem.triggerHaptic("warning");
        showToast("⚠️ False start! Wait for green.");
        renderReflexRush();
      } else {
        const ms = Date.now() - activeGameState.green_time;
        playSound("win");
        TouchSystem.triggerHaptic("heavy");
        showToast(`⚡ Superfast! ${ms} ms reaction!`);
        activeGameState.round++;
        setTimeout(() => renderReflexRush(), 1200);
        submitAction("tap", { reaction_ms: ms });
      }
    };

    orb?.addEventListener("touchstart", (e) => {
      e.preventDefault();
      handleOrbTap();
    });
    orb?.addEventListener("click", handleOrbTap);
  }

  // --------------------------------------------------------------------------
  // GAME 10: MINDMATCH
  // --------------------------------------------------------------------------
  function renderMindMatch() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Round ${activeGameState.round} of 5</span>
          <span class="touch-status-pill">📱 Touch Choice Sync</span>
          <span>Harmony: <b style="color: var(--likby-cyan);">${activeGameState.score}%</b></span>
        </div>
        <div style="text-align: center; font-size: 18px; font-weight: 800; margin: 20px 0;">
          ${activeGameState.prompt}
        </div>
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <button class="btn-primary mm-btn" data-choice="A" style="padding: 16px; font-size: 15px; user-select: none;">${activeGameState.optA}</button>
          <button class="btn-primary mm-btn" data-choice="B" style="padding: 16px; font-size: 15px; background: linear-gradient(135deg, var(--likby-violet), var(--likby-pink)); user-select: none;">${activeGameState.optB}</button>
        </div>
      </div>
    `;

    document.querySelectorAll(".mm-btn").forEach((btn) => {
      const handleChoice = () => {
        playSound("score");
        TouchSystem.triggerHaptic("medium");
        showToast("💙 Selection synced with partner!");
        activeGameState.round++;
        submitAction("choose_option", { choice: btn.dataset.choice });
      };

      btn.addEventListener("touchstart", (e) => {
        e.preventDefault();
        handleChoice();
      });
      btn.addEventListener("click", handleChoice);
    });
  }

  // --------------------------------------------------------------------------
  // GAME 11: MYSTERY MISSION
  // --------------------------------------------------------------------------
  function renderMysteryMission() {
    let currentCode = "";
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Stage ${activeGameState.stage} of 3</span>
          <span class="touch-status-pill">📱 Touch Keypad Safe</span>
          <span style="color: var(--likby-amber); font-weight: 800;">🔒 LOCKED SAFE</span>
        </div>
        <div style="background: var(--likby-surface-raised); border: 1px solid var(--likby-cyan); border-radius: 14px; padding: 12px; margin: 6px 0;">
          <div style="font-size: 11px; text-transform: uppercase; color: var(--likby-cyan); font-weight: 800; margin-bottom: 4px;">Co-op Mission Clue:</div>
          <div style="font-size: 13px; line-height: 1.4;">${activeGameState.hint}</div>
        </div>
        <div class="safe-code-dots">
          <div class="safe-dot" id="sDot0"></div>
          <div class="safe-dot" id="sDot1"></div>
          <div class="safe-dot" id="sDot2"></div>
          <div class="safe-dot" id="sDot3"></div>
        </div>
        <div class="safe-keypad" id="safeKeypad">
          ${[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => `<button class="safe-key" data-num="${n}">${n}</button>`).join("")}
          <button class="safe-key" data-action="backspace">⌫</button>
          <button class="safe-key" data-num="0">0</button>
          <button class="safe-key" data-action="unlock" style="background: var(--likby-cyan); color: #030712;">🔓</button>
        </div>
      </div>
    `;

    const updateDots = () => {
      for (let i = 0; i < 4; i++) {
        const dot = document.getElementById(`sDot${i}`);
        if (dot) dot.classList.toggle("filled", i < currentCode.length);
      }
    };

    const attemptUnlock = () => {
      if (currentCode === "2026") {
        playSound("win");
        TouchSystem.triggerHaptic("success");
        showToast("🎉 SAFE CRACKED! Mission Accomplished!");
        submitAction("submit_solution", { code: currentCode });
      } else {
        playSound("error");
        TouchSystem.triggerHaptic("warning");
        showToast("❌ Incorrect passcode. Combine clues!");
        currentCode = "";
        updateDots();
      }
    };

    document.querySelectorAll(".safe-key").forEach((key) => {
      const handleKeyPress = () => {
        const num = key.dataset.num;
        const action = key.dataset.action;
        if (num !== undefined) {
          if (currentCode.length < 4) {
            currentCode += num;
            playSound("click");
            TouchSystem.triggerHaptic("light");
            updateDots();
            if (currentCode.length === 4) {
              setTimeout(attemptUnlock, 200);
            }
          }
        } else if (action === "backspace") {
          if (currentCode.length > 0) {
            currentCode = currentCode.slice(0, -1);
            playSound("click");
            TouchSystem.triggerHaptic("light");
            updateDots();
          }
        } else if (action === "unlock") {
          attemptUnlock();
        }
      };

      key.addEventListener("touchstart", (e) => {
        e.preventDefault();
        handleKeyPress();
      });
      key.addEventListener("click", handleKeyPress);
    });
  }

  // --------------------------------------------------------------------------
  // GAME 12: ZEN MERGE (2048 SOLO)
  // --------------------------------------------------------------------------
  function renderZenMerge() {
    const grid = activeGameState.grid;
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Zen Score: <b style="color: var(--likby-cyan);">${activeGameState.score}</b></span>
          <span class="touch-status-pill">📱 4-Way Touch Swipe</span>
          <span>Goal: <b>2048</b></span>
        </div>
        <div class="zen-grid touch-interactive-surface" id="zenGrid">
          ${grid.map((row) => row.map((cell) => `
            <div class="zen-tile ${cell > 0 ? 't' + cell : ''}">${cell > 0 ? cell : ''}</div>
          `).join("")).join("")}
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; width: 180px; margin: 0 auto;">
          <div></div><button class="btn-secondary zm-dir" data-dir="UP">▲</button><div></div>
          <button class="btn-secondary zm-dir" data-dir="LEFT">◀</button>
          <button class="btn-secondary zm-dir" data-dir="DOWN">▼</button>
          <button class="btn-secondary zm-dir" data-dir="RIGHT">▶</button>
        </div>
      </div>
    `;

    const zenGrid = document.getElementById("zenGrid");
    let touchStartX = 0, touchStartY = 0;
    if (zenGrid) {
      zenGrid.addEventListener("touchstart", (e) => {
        const touch = e.touches[0];
        touchStartX = touch.clientX;
        touchStartY = touch.clientY;
      }, { passive: true });

      zenGrid.addEventListener("touchend", (e) => {
        const touch = e.changedTouches[0];
        const dx = touch.clientX - touchStartX;
        const dy = touch.clientY - touchStartY;
        if (Math.hypot(dx, dy) >= 25) {
          let dir = "UP";
          if (Math.abs(dx) > Math.abs(dy)) {
            dir = dx > 0 ? "RIGHT" : "LEFT";
          } else {
            dir = dy > 0 ? "DOWN" : "UP";
          }
          TouchSystem.triggerHaptic("selection");
          handleZenSwipe(dir);
        }
      });
    }

    document.querySelectorAll(".zm-dir").forEach((btn) => {
      const handleDir = () => {
        TouchSystem.triggerHaptic("selection");
        handleZenSwipe(btn.dataset.dir);
      };
      btn.addEventListener("touchstart", (e) => {
        e.preventDefault();
        handleDir();
      });
      btn.addEventListener("click", handleDir);
    });
  }

  function handleZenSwipe(dir) {
    playSound("move");
    const emptyCells = [];
    activeGameState.grid.forEach((row, r) => {
      row.forEach((cell, c) => {
        if (cell === 0) emptyCells.push({ r, c });
      });
    });
    if (emptyCells.length > 0) {
      const pick = emptyCells[Math.floor(Math.random() * emptyCells.length)];
      activeGameState.grid[pick.r][pick.c] = 2;
      activeGameState.score += 4;
      TouchSystem.triggerHaptic("light");
    }
    renderZenMerge();
  }

  // --------------------------------------------------------------------------
  // GAME 13: WORD HUNT (SOLO)
  // --------------------------------------------------------------------------
  function renderWordHunt() {
    const grid = activeGameState.grid;
    let selectedTiles = [];
    let currentDragWord = "";

    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Found: <b>${activeGameState.found.length} / ${activeGameState.words.length}</b></span>
          <span class="touch-status-pill">📱 Touch Drag Matrix</span>
          <span style="color: var(--likby-cyan); font-weight: 700;">Targets: ${activeGameState.words.join(", ")}</span>
        </div>
        <div id="whMatrix" class="wh-matrix touch-interactive-surface" style="display: grid; grid-template-columns: repeat(5, 42px); gap: 6px; margin: 0 auto;">
          ${grid.map((row, r) => row.map((char, c) => `
            <div class="quick-chip wh-tile" data-char="${char}" data-row="${r}" data-col="${c}" style="width: 42px; height: 42px; justify-content: center; font-size: 16px; font-weight: 800; cursor: pointer; user-select: none;">${char}</div>
          `).join("")).join("")}
        </div>
        <div style="display: flex; gap: 8px;">
          <input type="text" id="whInput" class="input-field" placeholder="Found word..." readonly style="font-weight: 800; letter-spacing: 2px; font-size: 15px;" />
          <button class="btn-primary" id="whSubmit">Claim ✨</button>
        </div>
      </div>
    `;

    const matrix = document.getElementById("whMatrix");
    const input = document.getElementById("whInput");

    const claimWord = (w) => {
      const word = (w || input?.value || "").trim().toUpperCase();
      if (activeGameState.words.includes(word) && !activeGameState.found.includes(word)) {
        activeGameState.found.push(word);
        playSound("win");
        TouchSystem.triggerHaptic("success");
        showToast(`🎉 Found: ${word}!`);
        if (input) input.value = "";
        renderWordHunt();
      } else if (activeGameState.found.includes(word)) {
        showToast("⚠️ Word already claimed!");
        TouchSystem.triggerHaptic("warning");
      } else {
        playSound("error");
        TouchSystem.triggerHaptic("warning");
      }
    };

    if (matrix) {
      let isDragging = false;
      const addTile = (tile) => {
        if (!tile || selectedTiles.includes(tile)) return;
        selectedTiles.push(tile);
        tile.classList.add("active-drag");
        currentDragWord += tile.dataset.char;
        if (input) input.value = currentDragWord;
        playSound("click");
        TouchSystem.triggerHaptic("light");
      };

      matrix.addEventListener("touchstart", (e) => {
        isDragging = true;
        selectedTiles = [];
        currentDragWord = "";
        matrix.querySelectorAll(".wh-tile").forEach(t => t.classList.remove("active-drag"));
        const touch = e.touches[0];
        const el = document.elementFromPoint(touch.clientX, touch.clientY);
        if (el?.classList.contains("wh-tile")) addTile(el);
      }, { passive: true });

      matrix.addEventListener("touchmove", (e) => {
        if (!isDragging) return;
        const touch = e.touches[0];
        const el = document.elementFromPoint(touch.clientX, touch.clientY);
        if (el?.classList.contains("wh-tile")) addTile(el);
      }, { passive: true });

      window.addEventListener("touchend", () => {
        if (!isDragging) return;
        isDragging = false;
        if (currentDragWord) {
          claimWord(currentDragWord);
        }
        setTimeout(() => {
          matrix?.querySelectorAll(".wh-tile").forEach(t => t.classList.remove("active-drag"));
        }, 300);
      }, { once: true });
    }

    document.querySelectorAll(".wh-tile").forEach((t) => {
      t.addEventListener("click", () => {
        if (input) input.value += t.dataset.char;
        playSound("click");
        TouchSystem.triggerHaptic("light");
      });
    });

    document.getElementById("whSubmit")?.addEventListener("click", () => claimWord());
  }

  // --------------------------------------------------------------------------
  // GAME 14: COLOR FLOW (SOLO)
  // --------------------------------------------------------------------------
  function renderColorFlow() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Flows: <b>${activeGameState.flows_connected} / ${activeGameState.target_flows}</b></span>
          <span class="touch-status-pill">📱 Connect Flow Conduits</span>
          <span>Target: 100%</span>
        </div>
        <div id="cfBoard" class="touch-interactive-surface" style="width: 260px; height: 260px; background: #0f172a; border-radius: 16px; margin: 0 auto; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 12px; box-shadow: inset 0 0 20px rgba(0,0,0,0.6);">
          <div class="cf-dot" data-color="CYAN" style="background: var(--likby-cyan); border-radius: 50%;"></div>
          <div></div><div></div>
          <div class="cf-dot" data-color="CYAN" style="background: var(--likby-cyan); border-radius: 50%;"></div>
          <div></div>
          <div class="cf-dot" data-color="PINK" style="background: var(--likby-pink); border-radius: 50%;"></div>
          <div class="cf-dot" data-color="PINK" style="background: var(--likby-pink); border-radius: 50%;"></div>
          <div></div>
          <div class="cf-dot" data-color="AMBER" style="background: var(--likby-amber); border-radius: 50%;"></div>
          <div></div><div></div>
          <div class="cf-dot" data-color="AMBER" style="background: var(--likby-amber); border-radius: 50%;"></div>
        </div>
        <button class="btn-primary" id="cfCompleteBtn">Complete Flow Connection 🎨</button>
      </div>
    `;

    let activeColorDot = null;
    document.querySelectorAll(".cf-dot").forEach((dot) => {
      const handleDot = () => {
        const col = dot.dataset.color;
        if (!activeColorDot) {
          activeColorDot = dot;
          dot.classList.add("active");
          playSound("click");
          TouchSystem.triggerHaptic("light");
        } else if (activeColorDot === dot) {
          activeColorDot.classList.remove("active");
          activeColorDot = null;
        } else if (activeColorDot.dataset.color === col) {
          dot.classList.add("active");
          activeGameState.flows_connected = Math.min(activeGameState.target_flows, activeGameState.flows_connected + 1);
          playSound("score");
          TouchSystem.triggerHaptic("medium");
          showToast(`⚡ ${col} flow conduit bridged!`);
          activeColorDot = null;
          if (activeGameState.flows_connected >= activeGameState.target_flows) {
            playSound("win");
            TouchSystem.triggerHaptic("success");
            showToast("✨ 100% Color Flow Achieved!");
          }
          setTimeout(() => renderColorFlow(), 400);
        } else {
          playSound("error");
          TouchSystem.triggerHaptic("warning");
          activeColorDot.classList.remove("active");
          activeColorDot = null;
        }
      };

      dot.addEventListener("touchstart", (e) => {
        e.preventDefault();
        handleDot();
      });
      dot.addEventListener("click", handleDot);
    });

    document.getElementById("cfCompleteBtn")?.addEventListener("click", () => {
      activeGameState.flows_connected = activeGameState.target_flows;
      playSound("win");
      TouchSystem.triggerHaptic("success");
      showToast("✨ 100% Color Flow Achieved!");
      renderColorFlow();
    });
  }

  // --------------------------------------------------------------------------
  // GAME 15: POCKET GOLF (SOLO)
  // --------------------------------------------------------------------------
  function renderPocketGolf() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 14px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Hole 1 (Par 3)</span>
          <span class="touch-status-pill">📱 Slingshot Putt Drag</span>
          <span>Strokes: <b style="color: var(--likby-cyan);">${activeGameState.strokes}</b></span>
        </div>
        <div id="golfCourse" class="touch-interactive-surface" style="width: 280px; height: 280px; background: #064e3b; border: 8px solid #022c22; border-radius: 20px; position: relative; margin: 0 auto; overflow: hidden; box-shadow: inset 0 0 20px rgba(0,0,0,0.6);">
          <!-- Sand trap -->
          <div style="position: absolute; top: 120px; left: 40px; width: 60px; height: 40px; background: #d97706; border-radius: 50%; opacity: 0.6;"></div>
          <!-- Hole -->
          <div id="golfHole" style="position: absolute; top: 40px; left: 130px; width: 22px; height: 22px; background: #000; border-radius: 50%; border: 2px solid #fff;"></div>
          <!-- Flag -->
          <div style="position: absolute; top: 22px; left: 138px; font-size: 18px;">🚩</div>
          <!-- Ball -->
          <div id="golfBall" style="position: absolute; bottom: 40px; left: 132px; width: 16px; height: 16px; background: #fff; border-radius: 50%; box-shadow: 0 0 8px #fff; cursor: grab; z-index: 10; transition: transform 0.4s ease-out;"></div>
          <!-- Slingshot Aim Line -->
          <div id="golfAimLine" class="touch-slingshot-line" style="display: none;"></div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn-secondary" id="golfPuttShort" style="flex: 1;">Tap Putt</button>
          <button class="btn-primary" id="golfPuttLong" style="flex: 2;">Long Drive ⛳</button>
        </div>
      </div>
    `;

    const ball = document.getElementById("golfBall");
    const course = document.getElementById("golfCourse");
    const aimLine = document.getElementById("golfAimLine");
    let isDragging = false;
    let dragStartX = 0, dragStartY = 0;

    const executePutt = (power) => {
      activeGameState.strokes++;
      playSound("strike");
      TouchSystem.triggerHaptic("heavy");
      if (ball) {
        ball.style.transform = `translate(0, -${power}px)`;
        setTimeout(() => {
          if (power >= 160) {
            playSound("win");
            TouchSystem.triggerHaptic("success");
            showToast("⛳ In the hole! Birdie!");
          } else {
            playSound("score");
            TouchSystem.triggerHaptic("medium");
            showToast("⛳ Nice approach putt!");
          }
        }, 400);
      }
    };

    if (ball && course) {
      ball.addEventListener("touchstart", (e) => {
        isDragging = true;
        const pos = TouchSystem.getTouchPos(e, course);
        dragStartX = pos.x;
        dragStartY = pos.y;
        TouchSystem.triggerHaptic("light");
      }, { passive: true });

      course.addEventListener("touchmove", (e) => {
        if (!isDragging) return;
        const pos = TouchSystem.getTouchPos(e, course);
        const dy = pos.y - dragStartY;
        if (dy > 10 && aimLine) {
          aimLine.style.display = "block";
          aimLine.style.left = "140px";
          aimLine.style.top = "230px";
          const dist = Math.min(180, dy * 2);
          aimLine.style.width = `${dist}px`;
          aimLine.style.transform = "rotate(-1.57rad)";
        }
      }, { passive: true });

      window.addEventListener("touchend", (e) => {
        if (!isDragging) return;
        isDragging = false;
        if (aimLine) aimLine.style.display = "none";
        const pos = TouchSystem.getTouchPos(e, course);
        const dy = pos.y - dragStartY;
        if (dy > 15) {
          const power = Math.min(180, Math.round(dy * 2));
          executePutt(power);
        }
      }, { once: true });
    }

    document.getElementById("golfPuttLong")?.addEventListener("click", () => executePutt(180));
    document.getElementById("golfPuttShort")?.addEventListener("click", () => executePutt(70));
  }

  // --------------------------------------------------------------------------
  // GAME 16: REFLEX LAB (SOLO)
  // --------------------------------------------------------------------------
  function renderReflexLab() {
    const randX = Math.floor(Math.random() * 80 - 40);
    const randY = Math.floor(Math.random() * 60 - 30);
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; align-items: center; justify-content: space-between; height: 100%; padding: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; width: 100%; font-size: 13px;">
          <span>Neuro Speed Matrix</span>
          <span class="touch-status-pill">📱 Pop Dynamic Target Orbs</span>
          <span>Best: <b style="color: var(--likby-cyan);">${activeGameState.best_ms} ms</b></span>
        </div>
        <div style="height: 220px; width: 220px; position: relative; display: flex; align-items: center; justify-content: center;">
          <div id="labOrb" style="width: 140px; height: 140px; border-radius: 50%; background: linear-gradient(135deg, var(--likby-cyan), var(--likby-blue)); display: flex; align-items: center; justify-content: center; font-size: 20px; font-weight: 800; color: #030712; cursor: pointer; box-shadow: var(--likby-cyan-glow); transform: translate(${randX}px, ${randY}px); user-select: none;">
            ⚡ POP
          </div>
        </div>
        <div style="font-size: 12px; color: var(--likby-text-muted);">
          Tap orbs as quickly as possible upon appearance
        </div>
      </div>
    `;

    const handleLabPop = () => {
      playSound("score");
      TouchSystem.triggerHaptic("heavy");
      const ms = Math.floor(Math.random() * 80 + 170);
      if (ms < activeGameState.best_ms) activeGameState.best_ms = ms;
      showToast(`⚡ ${ms} ms! Reaction logged.`);
      renderReflexLab();
    };

    const orb = document.getElementById("labOrb");
    orb?.addEventListener("touchstart", (e) => {
      e.preventDefault();
      handleLabPop();
    });
    orb?.addEventListener("click", handleLabPop);
  }

  // --------------------------------------------------------------------------
  // GAME 17: DAILY MYSTERY (SOLO)
  // --------------------------------------------------------------------------
  function renderDailyMystery() {
    canvasContainer.innerHTML = `
      <div style="display: flex; flex-direction: column; justify-content: space-between; height: 100%; padding: 18px;">
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 13px;">
          <span>Daily Cryptic Riddle 🔐</span>
          <span class="touch-status-pill">📱 Touch Solve & Hints</span>
          <span>Reward: +10 Karma</span>
        </div>
        <div style="background: var(--likby-surface-raised); border: 1px solid var(--likby-glass-border-hover); border-radius: 16px; padding: 18px; margin: 12px 0;">
          <p style="font-size: 15px; line-height: 1.6; color: #fff; margin-bottom: 8px;">"${activeGameState.clue}"</p>
          <div id="dmHintReveal" style="font-size: 12px; color: var(--likby-cyan); display: none;">💡 Hint: 4 letters, begins with 'E'.</div>
        </div>
        <div style="display: flex; gap: 6px; justify-content: center; margin-bottom: 8px;">
          <button class="btn-secondary" id="dmHintBtn" style="padding: 6px 14px; font-size: 12px;">💡 Clue Hint</button>
          <div class="quick-chip dm-chip" data-ans="echo">Echo</div>
          <div class="quick-chip dm-chip" data-ans="shadow">Shadow</div>
          <div class="quick-chip dm-chip" data-ans="wind">Wind</div>
        </div>
        <div style="display: flex; gap: 8px;">
          <input type="text" id="dmInput" class="input-field" placeholder="Type riddle answer..." />
          <button class="btn-primary" id="dmSubmit">Solve ✨</button>
        </div>
      </div>
    `;

    document.getElementById("dmHintBtn")?.addEventListener("click", () => {
      const hint = document.getElementById("dmHintReveal");
      if (hint) hint.style.display = "block";
      playSound("click");
      TouchSystem.triggerHaptic("light");
    });

    document.querySelectorAll(".dm-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const input = document.getElementById("dmInput");
        if (input) input.value = chip.dataset.ans;
        playSound("click");
        TouchSystem.triggerHaptic("selection");
      });
    });

    const solveRiddle = () => {
      const ans = document.getElementById("dmInput")?.value.trim().toLowerCase();
      if (ans === activeGameState.answer) {
        playSound("win");
        TouchSystem.triggerHaptic("success");
        showToast("🎉 Riddle Solved! +10 Karma Earned!");
      } else {
        playSound("error");
        TouchSystem.triggerHaptic("warning");
        showToast("❌ Not quite. Ponder deeper!");
      }
    };

    document.getElementById("dmSubmit")?.addEventListener("click", solveRiddle);
  }


  // Boot on DOM ready
  document.addEventListener("DOMContentLoaded", init);
})();
