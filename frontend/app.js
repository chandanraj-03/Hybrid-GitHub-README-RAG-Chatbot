// ==========================================================================
// HYBRID GITHUB README RAG - FRONTEND APPLICATION JAVASCRIPT
// ==========================================================================

const API_BASE = window.location.origin.includes(":5173") || window.location.origin.includes(":3000")
  ? "http://localhost:8080"
  : "";

// State
let conversationHistory = [];
let currentRepo = "";
let currentBranch = "main";
let currentSha = "";

// DOM Elements
const chatMessagesList = document.getElementById("chat-messages-list");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const btnSend = document.getElementById("btn-send");
const btnSyncReadme = document.getElementById("btn-sync-readme");
const btnOpenSettings = document.getElementById("btn-open-settings");
const btnCloseSettings = document.getElementById("btn-close-settings");
const settingsModal = document.getElementById("settings-modal");
const repoSettingsForm = document.getElementById("repo-settings-form");

const currentRepoDisplay = document.getElementById("current-repo-display");
const currentBranchDisplay = document.getElementById("current-branch-display");
const laptopStatusPill = document.getElementById("laptop-status-pill");
const laptopDot = document.getElementById("laptop-dot");
const laptopStatusText = document.getElementById("laptop-status-text");

const readmeStatusPill = document.getElementById("readme-status-pill");
const syncDot = document.getElementById("sync-dot");
const syncStatusText = document.getElementById("sync-status-text");

const modalSha = document.getElementById("modal-sha");
const modalChunks = document.getElementById("modal-chunks");
const modalTimestamp = document.getElementById("modal-timestamp");
const inputRepoUrl = document.getElementById("input-repo-url");
const inputRepoBranch = document.getElementById("input-repo-branch");
const inputRepoToken = document.getElementById("input-repo-token");

// Configure Marked.js
if (window.marked) {
  marked.setOptions({
    highlight: function (code, lang) {
      if (window.hljs && lang && hljs.getLanguage(lang)) {
        try {
          return hljs.highlight(code, { language: lang }).value;
        } catch (e) {}
      }
      return code;
    },
    breaks: true,
    gfm: true,
  });
}

// Initialization
document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  fetchInitialStatus();
  // Poll laptop health every 10 seconds
  setInterval(checkLaptopHealth, 10000);
});

function setupEventListeners() {
  chatForm.addEventListener("submit", handleChatSubmit);

  // Auto-resize textarea
  userInput.addEventListener("input", () => {
    userInput.style.height = "auto";
    userInput.style.height = Math.min(userInput.scrollHeight, 140) + "px";
  });

  // Enter to send (Shift+Enter for newline)
  userInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      chatForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    }
  });

  btnSyncReadme.addEventListener("click", () => triggerSync(false));

  btnOpenSettings.addEventListener("click", () => {
    inputRepoUrl.value = currentRepo ? `https://github.com/${currentRepo}` : "";
    inputRepoBranch.value = currentBranch || "";
    settingsModal.classList.add("open");
  });

  btnCloseSettings.addEventListener("click", () => {
    settingsModal.classList.remove("open");
  });

  settingsModal.addEventListener("click", (e) => {
    if (e.target === settingsModal) {
      settingsModal.classList.remove("open");
    }
  });

  repoSettingsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const repoUrl = inputRepoUrl.value.trim();
    const branch = inputRepoBranch.value.trim() || null;
    const token = inputRepoToken.value.trim() || null;

    settingsModal.classList.remove("open");
    await triggerSync(true, repoUrl, branch, token);
  });

  // Suggestion chips
  document.querySelectorAll(".suggestion-chip").forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-prompt");
      userInput.value = prompt;
      chatForm.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    });
  });
}

async function fetchInitialStatus() {
  await Promise.all([checkLaptopHealth(), checkGitHubStatus()]);
}

async function checkLaptopHealth() {
  try {
    const res = await fetch(`${API_BASE}/api/laptop-status`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    if (data.online) {
      laptopDot.className = "pulse-dot local-online";
      const latencyStr = data.latency_ms ? ` (${data.latency_ms}ms)` : "";
      laptopStatusText.textContent = `Local LLM Online${latencyStr}`;
      laptopStatusPill.style.borderColor = "var(--border-local)";
    } else {
      laptopDot.className = "pulse-dot local-offline";
      laptopStatusText.textContent = "Laptop Offline ➔ Cloud Cascade Active";
      laptopStatusPill.style.borderColor = "var(--border-gemini)";
    }
  } catch (err) {
    laptopDot.className = "pulse-dot local-offline";
    laptopStatusText.textContent = "Laptop Offline ➔ Cloud Cascade Active";
  }
}

async function checkGitHubStatus() {
  try {
    const res = await fetch(`${API_BASE}/api/github/status`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();

    currentRepo = data.repository || "Repository not configured";
    currentBranch = data.branch || "main";
    currentSha = data.sha || "";

    currentRepoDisplay.textContent = currentRepo;
    currentBranchDisplay.textContent = currentBranch;

    if (data.status === "synced") {
      syncDot.className = "pulse-dot sync-active";
      syncStatusText.textContent = `README Synced (${data.chunk_count || 0} chunks)`;
    } else if (data.status === "syncing") {
      syncDot.className = "pulse-dot sync-active";
      syncStatusText.textContent = "Syncing README...";
    } else {
      syncDot.className = "pulse-dot local-offline";
      syncStatusText.textContent = `Status: ${data.status}`;
    }

    modalSha.textContent = currentSha ? currentSha.substring(0, 8) : "None";
    modalChunks.textContent = data.chunk_count || 0;
    modalTimestamp.textContent = data.last_synced_at
      ? new Date(data.last_synced_at).toLocaleTimeString()
      : "-";
  } catch (err) {
    console.error("Failed to check GitHub status:", err);
  }
}

async function triggerSync(force = false, repoUrl = null, branch = null, token = null) {
  btnSyncReadme.disabled = true;
  btnSyncReadme.querySelector("span").textContent = "Syncing...";
  syncStatusText.textContent = "Syncing with GitHub...";

  try {
    const payload = { force };
    if (repoUrl) payload.repo_url = repoUrl;
    if (branch) payload.branch = branch;
    if (token) payload.token = token;

    const res = await fetch(`${API_BASE}/api/github/sync`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) {
      alert(`Sync Failed: ${data.detail || "Unknown error"}`);
    } else {
      await checkGitHubStatus();
    }
  } catch (err) {
    alert(`Sync request failed: ${err.message}`);
  } finally {
    btnSyncReadme.disabled = false;
    btnSyncReadme.querySelector("span").textContent = "Sync README";
  }
}

async function handleChatSubmit(e) {
  e.preventDefault();
  const message = userInput.value.trim();
  if (!message) return;

  const welcomeCard = document.getElementById("welcome-hero");
  if (welcomeCard) {
    welcomeCard.style.display = "none";
  }

  appendUserMessage(message);
  userInput.value = "";
  userInput.style.height = "auto";
  btnSend.disabled = true;

  const typingIndicatorId = appendTypingIndicator();
  scrollToBottom();

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        conversation: conversationHistory,
      }),
    });

    removeTypingIndicator(typingIndicatorId);

    if (!res.ok) {
      const errData = await res.json();
      appendErrorMessage(`Error: ${errData.detail || "Failed to generate answer"}`);
      return;
    }

    const data = await res.json();
    appendAssistantMessage(data);

    conversationHistory.push({ role: "user", content: message });
    conversationHistory.push({ role: "assistant", content: data.answer });

    if (conversationHistory.length > 10) {
      conversationHistory = conversationHistory.slice(-10);
    }
  } catch (err) {
    removeTypingIndicator(typingIndicatorId);
    appendErrorMessage(`Network connection failed: ${err.message}`);
  } finally {
    btnSend.disabled = false;
    scrollToBottom();
    checkLaptopHealth();
  }
}

function appendUserMessage(text) {
  const row = document.createElement("div");
  row.className = "message-row user";
  row.innerHTML = `
    <div class="message-bubble">
      ${escapeHtml(text)}
    </div>
  `;
  chatMessagesList.appendChild(row);
}

function appendAssistantMessage(data) {
  const row = document.createElement("div");
  row.className = "message-row assistant";

  const provider = (data.provider || "local").toLowerCase();
  let providerClass = "local";
  let providerLabel = `● Local LLM (${data.model})`;

  if (provider === "gemini") {
    providerClass = "gemini";
    providerLabel = `● Gemini (${data.model})`;
  } else if (provider === "grok") {
    providerClass = "grok";
    providerLabel = `● xAI Grok (${data.model})`;
  } else if (provider === "openrouter") {
    providerClass = "openrouter";
    providerLabel = `● OpenRouter (${data.model})`;
  } else if (provider === "groq") {
    providerClass = "groq";
    providerLabel = `● Groq Cloud (${data.model})`;
  }

  let failoverNoticeHtml = "";
  if (data.failover) {
    const trailHops = data.failover_trail || [];
    const trailText = trailHops.length > 0
      ? trailHops.map(h => `${h.provider}: ${h.reason}`).join(" ➔ ")
      : (data.failover_reason || "Failover provider active");

    failoverNoticeHtml = `
      <div class="failover-notice" title="${escapeHtml(trailText)}">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"></circle>
          <line x1="12" y1="8" x2="12" y2="12"></line>
          <line x1="12" y1="16" x2="12.01" y2="16"></line>
        </svg>
        <span>Cascade Failover (${trailHops.length || 1} hop${trailHops.length > 1 ? 's' : ''})</span>
      </div>
    `;
  }

  const parsedMarkdown = window.marked ? marked.parse(data.answer) : escapeHtml(data.answer);

  let sourcesHtml = "";
  if (data.sources && data.sources.length > 0) {
    const pills = data.sources.map(s => `
      <div class="source-pill">
        <span class="file">${escapeHtml(s.file)}</span>
        <span class="arrow">➔</span>
        <span class="section">${escapeHtml(s.section)}</span>
      </div>
    `).join("");

    sourcesHtml = `
      <div class="sources-card">
        <div class="sources-title">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"></path>
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"></path>
          </svg>
          README Knowledge Sources
        </div>
        <div class="sources-pills-list">${pills}</div>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="message-bubble">
      <div class="provider-header">
        <span class="provider-tag ${providerClass}">${providerLabel}</span>
        ${failoverNoticeHtml}
      </div>
      <div class="message-content">
        ${parsedMarkdown}
      </div>
      ${sourcesHtml}
    </div>
  `;

  chatMessagesList.appendChild(row);
}

function appendTypingIndicator() {
  const id = "typing-" + Date.now();
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.id = id;
  row.innerHTML = `
    <div class="message-bubble">
      <div class="typing-bubble">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `;
  chatMessagesList.appendChild(row);
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendErrorMessage(errorText) {
  const row = document.createElement("div");
  row.className = "message-row assistant";
  row.innerHTML = `
    <div class="message-bubble" style="border-color: var(--accent-danger); background: rgba(239, 68, 68, 0.1);">
      <div style="color: var(--accent-danger); font-weight: 600; margin-bottom: 4px;">Request Failed</div>
      <div>${escapeHtml(errorText)}</div>
    </div>
  `;
  chatMessagesList.appendChild(row);
}

function scrollToBottom() {
  const viewport = document.querySelector(".chat-viewport");
  viewport.scrollTop = viewport.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
