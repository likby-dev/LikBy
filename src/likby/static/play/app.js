/**
 * LIKBY PLAY — CLIENT ENGINE & INTERACTIVE MINI APP
 * Connects to FastAPI backend, supports all 17 games, WebSockets & Quota Management
 */

(function () {
  "use strict";

  // State
  let tg = window.Telegram?.WebApp;
  let initData = tg?.initData || "";
  let currentUserId = tg?.initDataUnsafe?.user?.id ? `tg_${tg.initDataUnsafe.user.id}` : "test_player_1";
  let currentEntitlements = null;
  let gamesCatalogue = [];
  let currentFilter = "all";
  let soundEnabled = true;

  // Active Game State
  let activeGameId = null;
  let activeSessionId = null;
  let activeSessionState = null;
  let activeWs = null;
  let activeGameMode = "SOLO"; // 'SOLO' or 'DUEL'
  let pendingInviteGameId = null;

  // Audio Synth Context
  let audioCtx = null;
  function playSound(type) {
    if (!soundEnabled) return;
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      const now = audioCtx.currentTime;

      if (type === "click") {
        osc.frequency.setValueAtTime(600, now);
        osc.frequency.exponentialRampToValueAtTime(800, now + 0.05);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.05);
        osc.start(now);
        osc.stop(now + 0.05);
      } else if (type === "win") {
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.setValueAtTime(554, now + 0.1);
        osc.frequency.setValueAtTime(659, now + 0.2);
        gain.gain.setValueAtTime(0.2, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.35);
        osc.start(now);
        osc.stop(now + 0.35);
      } else if (type === "score") {
        osc.frequency.setValueAtTime(523, now);
        osc.frequency.exponentialRampToValueAtTime(784, now + 0.12);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.12);
        osc.start(now);
        osc.stop(now + 0.12);
      }
    } catch (e) {
      // AudioContext fallback
    }
  }

  // Toast Helper
  function showToast(msg) {
    const toast = document.getElementById("toast");
    if (!toast) return;
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 2800);
  }

  // API Client Helper
  async function apiCall(endpoint, method = "GET", body = null) {
    const headers = {
      "Content-Type": "application/json",
      "X-User-Id": currentUserId,
    };
    if (initData) {
      headers["X-Telegram-Init-Data"] = initData;
    }

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    const res = await fetch(endpoint, opts);
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.message || "Request failed");
    }
    return data;
  }

  // DOM Elements
  const gameGrid = document.getElementById("gameGrid");
  const userTierBadge = document.getElementById("userTierBadge");
  const quotaCounterText = document.getElementById("quotaCounterText");
  const quotaPills = document.getElementById("quotaPills");
  const quotaResetText = document.getElementById("quotaResetText");
  const gameViewport = document.getElementById("gameViewport");
  const viewportTitle = document.getElementById("viewportTitle");
  const viewportIcon = document.getElementById("viewportIcon");
  const canvasContainer = document.getElementById("canvasContainer");
  const inviteModal = document.getElementById("inviteModal");
  const quotaExhaustedModal = document.getElementById("quotaExhaustedModal");
  const soundToggleBtn = document.getElementById("soundToggleBtn");

  // Initialize
  async function init() {
    if (tg) {
      tg.ready();
      tg.expand();
      if (tg.setHeaderColor) tg.setHeaderColor("#050816");
    }

    setupEventListeners();
    await loadCatalogue();
    await loadEntitlements();
  }

  function setupEventListeners() {
    // Sound toggle
    soundToggleBtn?.addEventListener("click", () => {
      soundEnabled = !soundEnabled;
      soundToggleBtn.textContent = soundEnabled ? "🔊" : "🔇";
      showToast(soundEnabled ? "Sound enabled" : "Sound muted");
    });

    // Tab buttons
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.dataset.filter;
        renderGameGrid();
      });
    });

    // Quick chips
    document.querySelectorAll(".quick-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const gameId = chip.dataset.game;
        launchGamePrompt(gameId);
      });
    });

    // Featured hero CTA
    document.getElementById("featuredPlayBtn")?.addEventListener("click", () => {
      launchGamePrompt("carrom_clash");
    });

    // Modals
    document.getElementById("closeInviteModal")?.addEventListener("click", () => {
      inviteModal.classList.remove("active");
    });
    document.getElementById("closeQuotaModal")?.addEventListener("click", () => {
      quotaExhaustedModal.classList.remove("active");
    });
    document.getElementById("exploreSoloBtn")?.addEventListener("click", () => {
      quotaExhaustedModal.classList.remove("active");
      const soloBtn = document.querySelector(".tab-btn[data-filter='solo']");
      if (soloBtn) soloBtn.click();
    });
    document.getElementById("upgradePlanBtn")?.addEventListener("click", () => {
      showToast("Upgrade via Telegram: /upgrade or /plans 💎");
    });
    document.getElementById("upgradeTiersBtn")?.addEventListener("click", () => {
      showToast("Send /plans in LikBy Bot to unlock more duels! ✨");
    });

    // Send Invite
    document.getElementById("sendInviteBtn")?.addEventListener("click", async () => {
      const partnerId = document.getElementById("partnerIdInput").value.trim();
      if (!partnerId) {
        showToast("Please enter a valid partner ID");
        return;
      }
      inviteModal.classList.remove("active");
      await startDuelMatch(pendingInviteGameId, partnerId);
    });

    // Exit Game
    document.getElementById("exitGameBtn")?.addEventListener("click", () => {
      closeGameViewport();
    });
  }

  // Load Catalogue
  async function loadCatalogue() {
    try {
      const res = await apiCall("/api/v1/play/catalogue");
      gamesCatalogue = res.games || [];
      renderGameGrid();
    } catch (e) {
      console.error("Failed to load catalogue:", e);
      showToast("Error loading games catalogue");
    }
  }

  // Load Entitlements
  async function loadEntitlements() {
    try {
      const res = await apiCall("/api/v1/play/entitlements");
      currentEntitlements = res;
      updateEntitlementsUI();
    } catch (e) {
      console.error("Failed to load entitlements:", e);
    }
  }

  function updateEntitlementsUI() {
    if (!currentEntitlements) return;

    // Tier badge
    const tier = currentEntitlements.tier || "BASE";
    userTierBadge.textContent = tier;
    userTierBadge.className = `tier-badge ${tier.toLowerCase()}`;

    // Quota counter
    const limit = currentEntitlements.daily_duel_limit;
    const remaining = currentEntitlements.daily_duels_remaining;
    if (limit === -1) {
      quotaCounterText.textContent = "Unlimited duels (Diamond 👑)";
      quotaPills.innerHTML = '<div class="quota-pill active" style="flex: 1;"></div>';
    } else {
      quotaCounterText.textContent = `${remaining} of ${limit} remaining today`;
      quotaPills.innerHTML = "";
      for (let i = 0; i < limit; i++) {
        const pill = document.createElement("div");
        pill.className = `quota-pill ${i < remaining ? "active" : ""}`;
        quotaPills.appendChild(pill);
      }
    }

    if (currentEntitlements.next_reset_utc) {
      const resetDate = new Date(currentEntitlements.next_reset_utc);
      quotaResetText.textContent = `Resets at 00:00 IST (${resetDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })})`;
    }
  }

  // Render Game Grid
  function renderGameGrid() {
    if (!gameGrid) return;
    gameGrid.innerHTML = "";

    const filtered = gamesCatalogue.filter((g) => {
      if (currentFilter === "duel") return g.mode === "DUEL";
      if (currentFilter === "solo") return g.mode === "SOLO";
      return true;
    });

    filtered.forEach((game) => {
      const card = document.createElement("div");
      card.className = "game-card";
      card.innerHTML = `
        <div class="card-top">
          <div class="game-icon-wrap">${game.icon}</div>
          <span class="mode-badge ${game.mode.toLowerCase()}">${game.mode}</span>
        </div>
        <div class="card-info">
          <div class="card-title">${game.name}</div>
          <div class="card-desc">${game.description}</div>
        </div>
        <div class="card-bottom">
          <div class="card-meta">⏱️ ${game.typical_duration_minutes}m</div>
          <button class="card-btn">${game.mode === "SOLO" ? "Play Solo" : "Challenge"}</button>
        </div>
      `;

      card.addEventListener("click", () => {
        playSound("click");
        launchGamePrompt(game.id);
      });

      gameGrid.appendChild(card);
    });
  }

  // Launch Prompt
  function launchGamePrompt(gameId) {
    const game = gamesCatalogue.find((g) => g.id === gameId);
    if (!game) return;

    if (game.mode === "SOLO") {
      startSoloGame(gameId);
    } else {
      // Check quota first
      if (currentEntitlements && currentEntitlements.daily_duels_remaining === 0) {
        quotaExhaustedModal.classList.add("active");
        return;
      }
      pendingInviteGameId = gameId;
      document.getElementById("inviteModalTitle").textContent = `Challenge to ${game.name}`;
      inviteModal.classList.add("active");
    }
  }

  // Start Solo Game
  async function startSoloGame(gameId) {
    try {
      showToast("Starting solo game...");
      const res = await apiCall(`/api/v1/play/solo/${gameId}/start`, "POST");
      activeGameId = gameId;
      activeSessionId = res.session_id;
      activeSessionState = res.game_state;
      activeGameMode = "SOLO";

      openGameViewport(res.game_name, res.icon);
      renderInteractiveGame(gameId, res.game_state);
    } catch (e) {
      console.error(e);
      showToast("Failed to start solo game: " + e.message);
    }
  }

  // Start Duel Match (Invite + Auto-Accept simulation for playground/test partner)
  async function startDuelMatch(gameId, partnerId) {
    try {
      showToast("Sending challenge...");
      const inviteRes = await apiCall("/api/v1/play/invitations", "POST", {
        game_id: gameId,
        invitee_id: partnerId,
      });

      // Accept invitation to begin authoritative match
      const acceptRes = await apiCall(`/api/v1/play/invitations/${inviteRes.invitation_id}/accept`, "POST");
      activeGameId = gameId;
      activeSessionId = acceptRes.session_id;
      activeSessionState = acceptRes.game_state;
      activeGameMode = "DUEL";

      // Refresh entitlements after starting duel
      await loadEntitlements();

      openGameViewport(acceptRes.game_name, acceptRes.icon);
      connectDuelWebSocket(acceptRes.session_id);
      renderInteractiveGame(gameId, acceptRes.game_state);
    } catch (e) {
      console.error(e);
      showToast(e.message || "Duel error");
    }
  }

  // Connect WebSocket for Duel Realtime events
  function connectDuelWebSocket(sessionId) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/v1/play/ws/${sessionId}?token=${currentUserId}`;
    try {
      activeWs = new WebSocket(wsUrl);
      activeWs.onopen = () => console.log("WebSocket connected to duel session", sessionId);
      activeWs.onmessage = (evt) => {
        try {
          const data = JSON.parse(evt.data);
          if (data.type === "game.state" || data.type === "game.action") {
            activeSessionState = data.state;
            renderInteractiveGame(activeGameId, activeSessionState);
            if (data.state.winner) {
              playSound("win");
              showToast(`Match Ended! Winner: ${data.state.winner}`);
            }
          }
        } catch (err) {
          console.error(err);
        }
      };
      activeWs.onclose = () => console.log("WebSocket closed");
    } catch (err) {
      console.warn("WS initialization fallback to REST:", err);
    }
  }

  // Submit Action (WS or REST fallback)
  async function submitAction(actionType, actionPayload = {}) {
    playSound("click");
    if (activeWs && activeWs.readyState === WebSocket.OPEN) {
      activeWs.send(
        JSON.stringify({
          type: "game.action",
          action_type: actionType,
          action_payload: actionPayload,
        })
      );
    } else {
      try {
        const res = await apiCall(`/api/v1/play/sessions/${activeSessionId}/action`, "POST", {
          action_type: actionType,
          action_payload: actionPayload,
        });
        activeSessionState = res.game_state;
        renderInteractiveGame(activeGameId, activeSessionState);
        if (res.is_completed) {
          playSound("win");
          showToast(`Game Completed! Winner: ${res.winner || "Draw"}`);
        }
      } catch (err) {
        showToast(err.message);
      }
    }
  }

  // Open & Close Viewport
  function openGameViewport(name, icon) {
    viewportTitle.textContent = name;
    viewportIcon.textContent = icon;
    gameViewport.classList.add("active");
  }

  function closeGameViewport() {
    if (activeWs) {
      activeWs.close();
      activeWs = null;
    }
    gameViewport.classList.remove("active");
    canvasContainer.innerHTML = "";
    activeGameId = null;
    activeSessionId = null;
    activeSessionState = null;
  }

  // =========================================================================
  // INTERACTIVE GAME RENDERERS FOR ALL 17 GAMES
  // =========================================================================
  function renderInteractiveGame(gameId, state) {
    canvasContainer.innerHTML = "";

    switch (gameId) {
      case "carrom_clash":
        renderCarromClash(state);
        break;
      case "air_rush":
        renderAirRush(state);
        break;
      case "pocket_pool":
        renderPocketPool(state);
        break;
      case "stick_arena":
        renderStickArena(state);
        break;
      case "quickdraw":
        renderQuickDraw(state);
        break;
      case "word_rush":
        renderWordRush(state);
        break;
      case "brain_blitz":
        renderBrainBlitz(state);
        break;
      case "reflex_rush":
        renderReflexRush(state);
        break;
      case "connect_four":
        renderConnectFour(state);
        break;
      case "mindmatch":
        renderMindMatch(state);
        break;
      case "mystery_mission":
        renderMysteryMission(state);
        break;
      case "zen_merge":
        renderZenMerge(state);
        break;
      case "word_hunt":
        renderWordHunt(state);
        break;
      case "color_flow":
        renderColorFlow(state);
        break;
      case "pocket_golf":
        renderPocketGolf(state);
        break;
      case "reflex_lab":
        renderReflexLab(state);
        break;
      case "daily_mystery":
        renderDailyMystery(state);
        break;
      default:
        canvasContainer.innerHTML = `<div style="padding: 20px; text-align: center;">Active Game: ${gameId}</div>`;
    }
  }

  // 1. CARROM CLASH
  function renderCarromClash(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 13px;">
          <span>P1 Score: <b style="color: var(--likby-cyan);">${state.p1_score}</b> (Whites: ${state.white_coins_remaining})</span>
          <span>P2 Score: <b style="color: var(--likby-violet);">${state.p2_score}</b> (Blacks: ${state.black_coins_remaining})</span>
        </div>
        <div style="width: 280px; height: 280px; background: #c29b61; border: 8px solid #5a381e; border-radius: 12px; position: relative; box-shadow: inset 0 0 20px rgba(0,0,0,0.5);">
          <!-- Carrom Board Center Circle -->
          <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 70px; height: 70px; border: 3px solid #b22222; border-radius: 50%;"></div>
          <!-- Queen -->
          ${state.queen_remaining ? '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 20px; height: 20px; background: #b22222; border-radius: 50%; border: 2px solid #fff;"></div>' : ""}
          <!-- Pockets -->
          <div style="position: absolute; top: 4px; left: 4px; width: 26px; height: 26px; background: #111; border-radius: 50%;"></div>
          <div style="position: absolute; top: 4px; right: 4px; width: 26px; height: 26px; background: #111; border-radius: 50%;"></div>
          <div style="position: absolute; bottom: 4px; left: 4px; width: 26px; height: 26px; background: #111; border-radius: 50%;"></div>
          <div style="position: absolute; bottom: 4px; right: 4px; width: 26px; height: 26px; background: #111; border-radius: 50%;"></div>
        </div>
        <div style="display: flex; gap: 10px; width: 100%;">
          <input type="range" id="carromAngle" min="-45" max="45" value="0" style="flex: 1;" />
          <button class="btn-primary" id="carromStrikeBtn" style="padding: 8px 16px;">Strike!</button>
        </div>
      </div>
    `;
    document.getElementById("carromStrikeBtn")?.addEventListener("click", () => {
      const angle = parseFloat(document.getElementById("carromAngle").value);
      submitAction("strike", { angle, power: 75.0 });
    });
  }

  // 2. AIR RUSH
  function renderAirRush(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 14px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>P1 Goals: <b style="color: var(--likby-cyan);">${state.p1_score}</b></span>
          <span>Target: <b>5</b></span>
          <span>P2 Goals: <b style="color: var(--likby-pink);">${state.p2_score}</b></span>
        </div>
        <div style="width: 290px; height: 320px; background: #0b1c38; border: 4px solid var(--likby-cyan); border-radius: 16px; position: relative; overflow: hidden;">
          <div style="position: absolute; top: 50%; left: 0; right: 0; height: 2px; background: rgba(34, 211, 238, 0.4);"></div>
          <!-- Puck -->
          <div style="position: absolute; top: 48%; left: 48%; width: 24px; height: 24px; background: #ff0055; border-radius: 50%; box-shadow: 0 0 10px #ff0055;"></div>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="card-btn" id="airRushDefendBtn">Move Paddle</button>
          <button class="btn-primary" id="airRushScoreBtn">Score Goal 🏒</button>
        </div>
      </div>
    `;
    document.getElementById("airRushDefendBtn")?.addEventListener("click", () => {
      submitAction("move_paddle", { x: Math.random() * 200 + 50, y: 150 });
    });
    document.getElementById("airRushScoreBtn")?.addEventListener("click", () => {
      submitAction("score_goal", {});
    });
  }

  // 3. POCKET POOL
  function renderPocketPool(state) {
    const solidsRem = state.balls_remaining?.SOLIDS?.length || 0;
    const stripesRem = state.balls_remaining?.STRIPES?.length || 0;
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 13px;">
          <span>Solids Left: <b style="color: #facc15;">${solidsRem}</b></span>
          <span>Turn: <b style="color: var(--likby-cyan);">${state.current_turn}</b></span>
          <span>Stripes Left: <b style="color: #38bdf8;">${stripesRem}</b></span>
        </div>
        <div style="width: 290px; height: 190px; background: #065f46; border: 10px solid #78350f; border-radius: 12px; position: relative;">
          <!-- Cue Ball -->
          <div style="position: absolute; top: 45%; left: 30%; width: 18px; height: 18px; background: #fff; border-radius: 50%;"></div>
          <!-- 8 Ball -->
          <div style="position: absolute; top: 45%; left: 70%; width: 18px; height: 18px; background: #000; color: #fff; border-radius: 50%; font-size: 10px; display: flex; align-items: center; justify-content: center;">8</div>
        </div>
        <div style="display: flex; gap: 8px; width: 100%;">
          <button class="card-btn" id="poolPotSolid" style="flex: 1;">Pot Solid</button>
          <button class="card-btn" id="poolPotStripe" style="flex: 1;">Pot Stripe</button>
          <button class="btn-primary" id="poolStrikeBtn" style="flex: 1;">Strike Cue</button>
        </div>
      </div>
    `;
    document.getElementById("poolPotSolid")?.addEventListener("click", () => {
      const solids = state.balls_remaining?.SOLIDS || [];
      const pot = solids.length > 0 ? solids[0] : 8;
      submitAction("strike_cue_ball", { pot_ball: pot });
    });
    document.getElementById("poolPotStripe")?.addEventListener("click", () => {
      const stripes = state.balls_remaining?.STRIPES || [];
      const pot = stripes.length > 0 ? stripes[0] : 8;
      submitAction("strike_cue_ball", { pot_ball: pot });
    });
    document.getElementById("poolStrikeBtn")?.addEventListener("click", () => {
      submitAction("strike_cue_ball", { angle: 45, power: 80 });
    });
  }

  // 4. STICK ARENA
  function renderStickArena(state) {
    const f1 = state.fighters?.[state.p1_id] || { hp: 100 };
    const f2 = state.fighters?.[state.p2_id] || { hp: 100 };
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 14px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <div style="width: 45%;">
            <div style="font-size: 11px;">P1 HP: ${f1.hp}%</div>
            <div style="height: 10px; background: #333; border-radius: 5px; overflow: hidden;">
              <div style="width: ${f1.hp}%; height: 100%; background: var(--likby-cyan);"></div>
            </div>
          </div>
          <div style="width: 45%; text-align: right;">
            <div style="font-size: 11px;">P2 HP: ${f2.hp}%</div>
            <div style="height: 10px; background: #333; border-radius: 5px; overflow: hidden;">
              <div style="width: ${f2.hp}%; height: 100%; background: var(--likby-pink); float: right;"></div>
            </div>
          </div>
        </div>
        <div style="height: 220px; background: #111c32; border-radius: 12px; position: relative; border-bottom: 8px solid var(--likby-blue);">
          <div style="position: absolute; bottom: 0; left: ${f1.x ? f1.x / 2 : 50}px; font-size: 40px;">🤺</div>
          <div style="position: absolute; bottom: 0; right: 50px; font-size: 40px; transform: scaleX(-1);">🥷</div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="card-btn" id="stickMoveLeft">◀ Move</button>
          <button class="card-btn" id="stickMoveRight">Move ▶</button>
          <button class="btn-primary" id="stickLightAttack">Light ⚔️</button>
          <button class="btn-primary" id="stickHeavyAttack" style="background: linear-gradient(135deg, var(--likby-violet), var(--likby-pink));">Heavy 💥</button>
        </div>
      </div>
    `;
    document.getElementById("stickMoveLeft")?.addEventListener("click", () => submitAction("move", { dx: -30 }));
    document.getElementById("stickMoveRight")?.addEventListener("click", () => submitAction("move", { dx: 30 }));
    document.getElementById("stickLightAttack")?.addEventListener("click", () => submitAction("attack", { attack_type: "light" }));
    document.getElementById("stickHeavyAttack")?.addEventListener("click", () => submitAction("attack", { attack_type: "heavy" }));
  }

  // 5. QUICKDRAW
  function renderQuickDraw(state) {
    const isArtist = state.artist_id === currentUserId;
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 12px;">
        <div style="font-size: 13px; text-align: center;">
          ${isArtist ? `Draw: <b style="color: var(--likby-cyan);">${state.secret_word || "Secret"}</b>` : `Guess the word! (${state.word_length || "?"} letters)`}
        </div>
        <canvas id="qdCanvas" width="280" height="240" style="background: #fff; border-radius: 10px; margin: 0 auto; cursor: crosshair;"></canvas>
        <div style="display: flex; gap: 8px; width: 100%;">
          ${
            isArtist
              ? '<button class="card-btn" id="qdClearBtn" style="flex: 1;">Clear</button><button class="btn-primary" id="qdStrokeBtn" style="flex: 2;">Send Drawing</button>'
              : '<input type="text" id="qdGuessInput" class="input-field" placeholder="Type your guess..." /><button class="btn-primary" id="qdSubmitGuess">Guess</button>'
          }
        </div>
      </div>
    `;
    if (isArtist) {
      document.getElementById("qdStrokeBtn")?.addEventListener("click", () => {
        submitAction("add_stroke", { stroke: [{ x: 10, y: 10 }, { x: 50, y: 50 }] });
      });
    } else {
      document.getElementById("qdSubmitGuess")?.addEventListener("click", () => {
        const val = document.getElementById("qdGuessInput").value.trim();
        if (val) submitAction("submit_guess", { guess: val });
      });
    }
  }

  // 6. WORD RUSH
  function renderWordRush(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>Letters: <b style="letter-spacing: 4px; color: var(--likby-cyan);">${state.letters?.join(" ") || "R U S H"}</b></span>
          <span>Score: <b>${state.p1_score || 0}</b></span>
        </div>
        <div style="text-align: center; padding: 20px; font-size: 28px; font-weight: 800; background: var(--likby-surface-raised); border-radius: 12px;">
          🔤 ${state.letters?.slice(0, 5).join(" ") || "A B C D E"}
        </div>
        <div style="display: flex; gap: 8px; width: 100%;">
          <input type="text" id="wordRushInput" class="input-field" placeholder="Enter valid word..." />
          <button class="btn-primary" id="wordRushSubmit">Submit</button>
        </div>
      </div>
    `;
    document.getElementById("wordRushSubmit")?.addEventListener("click", () => {
      const w = document.getElementById("wordRushInput").value.trim();
      if (w) submitAction("submit_word", { word: w });
    });
  }

  // 7. BRAIN BLITZ
  function renderBrainBlitz(state) {
    const q = state.question || { q: "Loading trivia...", options: ["A", "B", "C", "D"] };
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 12px; color: var(--likby-muted);">
          <span>Question ${(state.current_question_index || 0) + 1} of ${state.total_questions || 5}</span>
          <span>P1: ${state.p1_score || 0} pts</span>
        </div>
        <div style="font-size: 16px; font-weight: 700; text-align: center; margin: 12px 0;">${q.q}</div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; width: 100%;">
          ${q.options.map((opt, i) => `<button class="card-btn bb-opt-btn" data-idx="${i}" style="padding: 12px 8px; font-size: 12px; height: auto;">${opt}</button>`).join("")}
        </div>
      </div>
    `;
    document.querySelectorAll(".bb-opt-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        submitAction("answer_question", { option_index: parseInt(btn.dataset.idx) });
      });
    });
  }

  // 8. REFLEX RUSH
  function renderReflexRush(state) {
    const isCueActive = state.status !== "COMPLETED";
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>Round: <b>${state.round || 1}</b></span>
          <span>Wins: P1 (${state.p1_wins || 0}) - P2 (${state.p2_wins || 0})</span>
        </div>
        <div id="reflexBox" style="width: 240px; height: 240px; border-radius: 50%; background: #22c55e; display: flex; align-items: center; justify-content: center; font-size: 24px; font-weight: 800; color: #050816; cursor: pointer; box-shadow: 0 0 30px rgba(34, 197, 94, 0.4);">
          TAP NOW! ⚡
        </div>
        <p style="font-size: 12px; color: var(--likby-muted);">Test reaction time! Avoid false starts.</p>
      </div>
    `;
    document.getElementById("reflexBox")?.addEventListener("click", () => {
      submitAction("tap", { client_timestamp_ms: Date.now() });
    });
  }

  // 9. CONNECT FOUR
  function renderConnectFour(state) {
    const board = state.board || Array(6).fill(null).map(() => Array(7).fill(0));
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 12px;">
        <div style="font-size: 13px;">Turn: <b style="color: var(--likby-cyan);">${state.current_turn}</b></div>
        <div style="background: #1e3a8a; padding: 10px; border-radius: 12px; display: grid; grid-template-columns: repeat(7, 34px); gap: 6px;">
          ${board.map((row, r) => row.map((cell, c) => `
            <div class="c4-cell" data-col="${c}" style="width: 34px; height: 34px; border-radius: 50%; background: ${cell === 1 ? "#22d3ee" : cell === 2 ? "#ec4899" : "#0b1224"}; cursor: pointer;"></div>
          `).join("")).join("")}
        </div>
        <div style="display: flex; gap: 4px; width: 100%; justify-content: center;">
          ${[0, 1, 2, 3, 4, 5, 6].map((col) => `<button class="card-btn c4-drop-btn" data-col="${col}" style="padding: 6px 10px;">↓</button>`).join("")}
        </div>
      </div>
    `;
    document.querySelectorAll(".c4-cell, .c4-drop-btn").forEach((el) => {
      el.addEventListener("click", () => {
        submitAction("drop_disc", { column: parseInt(el.dataset.col) });
      });
    });
  }

  // 10. MINDMATCH
  function renderMindMatch(state) {
    const d = state.current_dilemma || { prompt: "Your ideal vibe:", a: "Sunrise 🌅", b: "Stargazing 🌙" };
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 13px;">
          <span>Round: <b>${(state.round || 0) + 1} of 5</b></span>
          <span>Harmony: <b style="color: var(--likby-cyan);">${state.match_score || 0}%</b></span>
        </div>
        <div style="text-align: center; font-size: 17px; font-weight: 700; margin: 10px 0;">${d.prompt}</div>
        <div style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
          <button class="btn-primary mm-choice-btn" data-choice="a" style="padding: 16px;">${d.a}</button>
          <button class="btn-primary mm-choice-btn" data-choice="b" style="background: linear-gradient(135deg, var(--likby-violet), var(--likby-pink)); padding: 16px;">${d.b}</button>
        </div>
      </div>
    `;
    document.querySelectorAll(".mm-choice-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        submitAction("select_option", { choice: btn.dataset.choice });
      });
    });
  }

  // 11. MYSTERY MISSION
  function renderMysteryMission(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 13px;">
          <span>${state.prompt || "Mystery Room"}</span>
          <span>Stage: <b>${(state.stage || 0) + 1} / 3</b></span>
        </div>
        <div style="background: var(--likby-surface-raised); border: 1px solid var(--likby-border-glow); border-radius: 12px; padding: 16px; margin: 14px 0;">
          <div style="font-size: 11px; text-transform: uppercase; color: var(--likby-cyan); font-weight: 700; margin-bottom: 6px;">Your Private Clue 🔍</div>
          <div style="font-size: 14px; color: var(--likby-text);">${state.private_clue || state.my_clue || "Combine clues with partner!"}</div>
        </div>
        <div style="display: flex; gap: 8px; width: 100%;">
          <input type="text" id="missionAnswer" class="input-field" placeholder="Enter passcode..." />
          <button class="btn-primary" id="missionSubmit">Unlock</button>
        </div>
      </div>
    `;
    document.getElementById("missionSubmit")?.addEventListener("click", () => {
      const ans = document.getElementById("missionAnswer").value.trim();
      if (ans) submitAction("submit_solution", { answer: ans });
    });
  }

  // 12. ZEN MERGE (Solo)
  function renderZenMerge(state) {
    const grid = state.grid || [[2, 0, 0, 0], [0, 2, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]];
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 14px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>Zen Score: <b style="color: var(--likby-cyan);">${state.score || 0}</b></span>
          <span>Max Tile: <b style="color: #facc15;">${state.max_tile || 2}</b></span>
        </div>
        <div style="width: 250px; height: 250px; background: #0e172a; border-radius: 12px; padding: 8px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px;">
          ${grid.map((row) => row.map((cell) => `
            <div style="background: ${cell > 0 ? "var(--likby-cyan)" : "rgba(255,255,255,0.05)"}; color: #050816; font-weight: 800; font-size: 16px; border-radius: 6px; display: flex; align-items: center; justify-content: center;">
              ${cell > 0 ? cell : ""}
            </div>
          `).join("")).join("")}
        </div>
        <div style="display: grid; grid-template-columns: repeat(3, 50px); gap: 6px;">
          <div></div><button class="card-btn zm-btn" data-dir="UP">▲</button><div></div>
          <button class="card-btn zm-btn" data-dir="LEFT">◀</button><button class="card-btn zm-btn" data-dir="DOWN">▼</button><button class="card-btn zm-btn" data-dir="RIGHT">▶</button>
        </div>
      </div>
    `;
    document.querySelectorAll(".zm-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        submitAction("swipe", { direction: btn.dataset.dir });
      });
    });
  }

  // 13. WORD HUNT (Solo)
  function renderWordHunt(state) {
    const grid = state.grid || [["L", "I", "K", "B", "Y"], ["G", "A", "M", "E", "S"]];
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 14px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>Found: <b>${state.found_words?.length || 0} / ${state.hidden_words?.length || 4}</b></span>
          <button class="card-btn" id="wordHuntHint">Hint 💡</button>
        </div>
        <div style="display: grid; grid-template-columns: repeat(5, 38px); gap: 6px; margin: 0 auto;">
          ${grid.slice(0, 5).map((row) => row.slice(0, 5).map((char) => `
            <div style="width: 38px; height: 38px; background: var(--likby-surface-raised); border: 1px solid var(--likby-border); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700;">${char}</div>
          `).join("")).join("")}
        </div>
        <div style="display: flex; gap: 8px; width: 100%;">
          <input type="text" id="wordHuntInput" class="input-field" placeholder="Found word..." />
          <button class="btn-primary" id="wordHuntSubmit">Submit</button>
        </div>
      </div>
    `;
    document.getElementById("wordHuntSubmit")?.addEventListener("click", () => {
      const val = document.getElementById("wordHuntInput").value.trim();
      if (val) submitAction("select_word", { word: val });
    });
    document.getElementById("wordHuntHint")?.addEventListener("click", () => submitAction("hint", {}));
  }

  // 14. COLOR FLOW (Solo)
  function renderColorFlow(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>Level: <b>${state.level || 1}</b></span>
          <span>Flows: <b style="color: var(--likby-cyan);">${state.flows_connected || 0}</b></span>
        </div>
        <div style="width: 240px; height: 240px; background: #0c1527; border-radius: 12px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; padding: 12px;">
          <div style="background: #22d3ee; border-radius: 50%;"></div><div></div><div></div><div style="background: #22d3ee; border-radius: 50%;"></div>
          <div></div><div style="background: #ec4899; border-radius: 50%;"></div><div></div><div></div>
          <div></div><div></div><div style="background: #ec4899; border-radius: 50%;"></div><div></div>
          <div style="background: #8b5cf6; border-radius: 50%;"></div><div></div><div></div><div style="background: #8b5cf6; border-radius: 50%;"></div>
        </div>
        <button class="btn-primary" id="colorFlowConnect">Connect Flow 🎨</button>
      </div>
    `;
    document.getElementById("colorFlowConnect")?.addEventListener("click", () => {
      submitAction("connect_path", { color: "CYAN", path: [{ r: 0, c: 0 }, { r: 0, c: 3 }] });
    });
  }

  // 15. POCKET GOLF (Solo)
  function renderPocketGolf(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>Course: <b>Hole 1</b></span>
          <span>Strokes: <b style="color: var(--likby-cyan);">${state.strokes || 0}</b></span>
        </div>
        <div style="width: 260px; height: 260px; background: #064e3b; border: 6px solid #042f2e; border-radius: 16px; position: relative;">
          <!-- Hole -->
          <div style="position: absolute; top: 30px; left: 120px; width: 22px; height: 22px; background: #000; border-radius: 50%;"></div>
          <!-- Ball -->
          <div style="position: absolute; bottom: 30px; left: 120px; width: 14px; height: 14px; background: #fff; border-radius: 50%;"></div>
        </div>
        <div style="display: flex; gap: 8px; width: 100%;">
          <button class="card-btn" id="golfPuttShort" style="flex: 1;">Short Putt</button>
          <button class="btn-primary" id="golfPuttPower" style="flex: 2;">Putt to Hole ⛳</button>
        </div>
      </div>
    `;
    document.getElementById("golfPuttShort")?.addEventListener("click", () => {
      submitAction("putt", { angle: 90, power: 40 });
    });
    document.getElementById("golfPuttPower")?.addEventListener("click", () => {
      submitAction("putt", { angle: 90, power: 85 });
    });
  }

  // 16. REFLEX LAB (Solo)
  function renderReflexLab(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%;">
          <span>Reflex Lab</span>
          <span>Score: <b style="color: var(--likby-cyan);">${state.score || 0}</b></span>
        </div>
        <div style="text-align: center; margin: 20px 0;">
          <div style="font-size: 14px; color: var(--likby-muted); margin-bottom: 8px;">Challenge: ${state.mode || "TAP_FAST"}</div>
          <button class="btn-primary" id="labTrigger" style="width: 160px; height: 160px; border-radius: 50%; font-size: 20px;">⚡ TAP</button>
        </div>
        <p style="font-size: 11px; text-align: center; color: var(--likby-muted);">Casual reaction training (non-diagnostic)</p>
      </div>
    `;
    document.getElementById("labTrigger")?.addEventListener("click", () => {
      submitAction("record_result", { mode: "TAP_FAST", reaction_ms: 210 });
    });
  }

  // 17. DAILY MYSTERY (Solo)
  function renderDailyMystery(state) {
    canvasContainer.innerHTML = `
      <div style="width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: space-between; padding: 16px;">
        <div style="display: flex; justify-content: space-between; width: 100%; font-size: 13px;">
          <span>Daily Riddle 🔐</span>
          <span>Hints: <b>${state.hints_used || 0}</b></span>
        </div>
        <div style="background: var(--likby-surface-raised); border-radius: 12px; padding: 16px; margin: 12px 0;">
          <p style="font-size: 14px; line-height: 1.5;">${state.clue || "What has keys but cannot open locks, has space but no room, and allows you to enter without ever leaving?"}</p>
        </div>
        <div style="display: flex; gap: 8px; width: 100%;">
          <input type="text" id="dailyMysteryInput" class="input-field" placeholder="Answer..." />
          <button class="btn-primary" id="dailyMysterySubmit">Solve</button>
        </div>
      </div>
    `;
    document.getElementById("dailyMysterySubmit")?.addEventListener("click", () => {
      const a = document.getElementById("dailyMysteryInput").value.trim();
      if (a) submitAction("solve", { answer: a });
    });
  }

  // Boot
  document.addEventListener("DOMContentLoaded", init);
})();
