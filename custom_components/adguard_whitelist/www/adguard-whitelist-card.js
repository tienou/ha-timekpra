const CARD_VERSION = "2.5.4";

/* Firefox SVG (mdi:firefox removed from MDI 7.x used by modern HA) */
const FF_ICON = `<svg viewBox="0 0 24 24" width="18" height="18" style="vertical-align:middle"><path fill="currentColor" d="M9.27 7.94c.34-.98.98-1.93 1.86-2.6-.9.83-1.4 1.81-1.6 2.6-.02.09-.04.18-.05.27.01-.09.02-.18.05-.27m11.17 4.09c-.41-2.53-2.15-4.75-4.02-5.96.58 1.14.88 2.47.88 3.87 0 .82-.12 1.6-.33 2.34-.22.74-.54 1.43-.95 2.06-.83 1.27-2.01 2.24-3.33 2.93.71.11 1.43.07 2.12-.12a6.89 6.89 0 0 0 4.17-3.21c.67-1.2.63-2.56 1.46-1.91M12 22C6.48 22 2 17.52 2 12S6.48 2 12 2s10 4.48 10 10-4.48 10-10 10m0-18C7.03 4 3 8.03 3 12s4.03 8 9 8 9-4.03 9-8-4.03-8-9-8m-1.17 10.19a5.28 5.28 0 0 0 3.16-1.18 5.29 5.29 0 0 0 1.6-2.56 5.3 5.3 0 0 0 .1-2.78c-.21-.91-.64-1.72-1.21-2.42a5.32 5.32 0 0 0-2.1-1.63 5.27 5.27 0 0 0-2.53-.52c-.88.07-1.72.37-2.44.87-.72.49-1.3 1.17-1.67 1.97-.37.8-.51 1.69-.4 2.55.11.87.46 1.69 1 2.36.54.68 1.26 1.19 2.09 1.48.48.17.99.26 1.5.26.3 0 .6-.03.9-.09"/></svg>`;

/* ── Autocomplete suggestions ────────────────────────────── */
const DOMAIN_SUGGESTIONS = [
  "lumni.fr", "logicieleducatif.fr", "calculatice.ac-lille.fr",
  "khanacademy.org", "fr.khanacademy.org", "bescherelle.com",
  "scratch.mit.edu", "mathador.fr", "lalilo.com", "education.fr",
  "eduscol.education.fr", "reseau-canope.fr", "cned.fr",
  "maxicours.com", "kartable.fr", "afterclasse.fr",
  "duolingo.com", "quizlet.com", "brainpop.fr",
  "code.org", "codecademy.com", "freecodecamp.org",
  "w3schools.com", "developer.mozilla.org", "stackoverflow.com",
  "github.com", "gitlab.com", "codepen.io",
  "wikipedia.org", "fr.wikipedia.org", "en.wikipedia.org",
  "wikimedia.org", "wiktionary.org",
  "youtube.com", "www.youtube.com", "youtu.be",
  "vimeo.com", "dailymotion.com", "twitch.tv",
  "google.com", "google.fr", "accounts.google.com",
  "docs.google.com", "drive.google.com", "mail.google.com",
  "translate.google.com", "maps.google.com",
  "outlook.com", "outlook.live.com", "office.com",
  "teams.microsoft.com", "onedrive.live.com",
  "discord.com", "discord.gg", "slack.com",
  "reddit.com", "old.reddit.com",
  "amazon.fr", "amazon.com", "ebay.fr",
  "leboncoin.fr", "cdiscount.com", "fnac.com",
  "netflix.com", "disneyplus.com", "primevideo.com",
  "spotify.com", "deezer.com", "soundcloud.com",
  "apple.com", "icloud.com", "microsoft.com",
  "mozilla.org", "addons.mozilla.org",
  "cloudflare.com", "fastly.net", "akamai.net",
  "whatsapp.com", "web.whatsapp.com", "signal.org",
  "telegram.org", "messenger.com",
  "twitter.com", "x.com", "instagram.com", "facebook.com",
  "linkedin.com", "pinterest.com", "tiktok.com",
  "openai.com", "chat.openai.com", "claude.ai", "anthropic.com",
  "notion.so", "trello.com", "asana.com",
  "figma.com", "canva.com", "adobe.com",
  "zoom.us", "meet.google.com",
  "stackexchange.com", "superuser.com", "askubuntu.com",
  "npmjs.com", "pypi.org", "hub.docker.com",
  "vercel.com", "netlify.com", "heroku.com",
  "medium.com", "dev.to", "hashnode.dev",
  "archive.org", "gutenberg.org",
  "france.tv", "arte.tv", "tf1.fr", "6play.fr",
  "lemonde.fr", "lefigaro.fr", "liberation.fr",
  "franceinfo.fr", "bfmtv.com",
  "meteofrance.com", "service-public.fr", "impots.gouv.fr",
  "ameli.fr", "caf.fr", "pole-emploi.fr",
  "laposte.fr", "chronopost.fr", "ups.com", "dhl.com",
  "sncf.com", "ratp.fr", "blablacar.fr",
].sort();

const CATEGORY_OPTIONS = [
  "Éducation",
  "Programmation",
  "CDN / Technique",
  "Divertissement",
  "Communication",
  "Shopping",
  "Actualités",
  "Services publics",
  "Autre",
];

const CAT_ICONS = {
  "Éducation": "mdi:school",
  "Programmation": "mdi:code-braces",
  "CDN / Technique": "mdi:server-network",
  "Divertissement": "mdi:movie-open",
  "Communication": "mdi:message-text",
  "Shopping": "mdi:cart",
  "Actualités": "mdi:newspaper",
  "Services publics": "mdi:bank",
  "Autre": "mdi:web",
};

const CAT_COLORS = {
  "Éducation": "var(--info-color, #2196f3)",
  "Programmation": "var(--success-color, #4caf50)",
  "CDN / Technique": "var(--secondary-text-color)",
  "Divertissement": "#e91e63",
  "Communication": "#9c27b0",
  "Shopping": "#ff9800",
  "Actualités": "#607d8b",
  "Services publics": "#795548",
  "Autre": "var(--warning-color, #ff9800)",
};

const CARD_STYLES = `
  :host { display: block; }
  ha-card { overflow: visible; }
  .aw-card { padding: 16px; }
  .aw-header {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 16px; padding-bottom: 12px;
    border-bottom: 1px solid var(--divider-color);
  }
  .aw-header-icon {
    width: 40px; height: 40px; border-radius: 50%;
    background: var(--primary-color);
    display: flex; align-items: center; justify-content: center;
    color: white; font-size: 20px; transition: background 0.3s;
    flex-shrink: 0;
  }
  .aw-header-info { flex: 1; min-width: 0; }
  .aw-header-title { font-size: 16px; font-weight: 500; }
  .aw-header-status { font-size: 12px; transition: color 0.3s; }
  .aw-status-row {
    display: flex; align-items: center; gap: 10px; margin-top: 2px;
    font-size: 11px;
  }
  .aw-status-dot {
    display: inline-block; width: 8px; height: 8px; border-radius: 50%;
    margin-right: 3px; vertical-align: middle;
  }
  .aw-status-dot.online { background: var(--success-color, #4caf50); }
  .aw-status-dot.offline { background: var(--error-color, #f44336); }
  .aw-pending-badge {
    background: var(--warning-color, #ff9800); color: white;
    border-radius: 10px; padding: 2px 8px; font-size: 11px; margin-left: 4px;
  }
  .aw-stats {
    display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 16px;
  }
  .aw-stat {
    background: var(--card-background-color, var(--ha-card-background));
    border: 1px solid var(--divider-color);
    border-radius: 12px; padding: 12px; text-align: center;
  }
  .aw-stat-value { font-size: 20px; font-weight: 600; }
  .aw-stat-label { font-size: 11px; color: var(--secondary-text-color); }

  /* Add form */
  .aw-add-form { position: relative; display: flex; gap: 8px; margin-bottom: 16px; overflow: hidden; }
  .aw-add-input {
    flex: 1; min-width: 0; padding: 8px 12px;
    border: 1px solid var(--divider-color); border-radius: 8px;
    background: var(--card-background-color, var(--ha-card-background));
    color: var(--primary-text-color); font-size: 16px; outline: none;
    -webkit-appearance: none; appearance: none;
    box-sizing: border-box;
  }
  .aw-add-input:focus { border-color: var(--primary-color); }
  .aw-add-input::placeholder { color: var(--secondary-text-color); }
  .aw-add-btn {
    padding: 8px 12px; border: none; border-radius: 8px;
    background: var(--primary-color); color: white;
    font-size: 14px; font-weight: 500; cursor: pointer;
    display: flex; align-items: center; gap: 4px;
    white-space: nowrap; flex-shrink: 0;
    -webkit-tap-highlight-color: transparent;
  }

  /* Autocomplete dropdown */
  .aw-dd {
    display: none; position: absolute; top: 100%; left: 0; right: 70px;
    max-height: 200px; overflow-y: auto; z-index: 50;
    background: var(--card-background-color, #fff);
    border: 1px solid var(--divider-color); border-radius: 0 0 8px 8px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }
  .aw-dd.visible { display: block; }
  .aw-dd-item {
    padding: 10px 12px; cursor: pointer; font-size: 14px;
    color: var(--primary-text-color);
    -webkit-tap-highlight-color: transparent;
  }
  .aw-dd-item:hover, .aw-dd-item.active {
    background: var(--primary-color); color: white;
  }

  /* Categories */
  .aw-category { margin-bottom: 12px; }
  .aw-category-header {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; font-weight: 600; text-transform: uppercase;
    margin-bottom: 6px;
  }
  .aw-category-count {
    background: var(--divider-color); border-radius: 10px;
    padding: 1px 6px; font-size: 10px;
  }
  .aw-site-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px; border-radius: 8px; transition: background 0.15s;
    min-height: 36px;
  }
  .aw-site-item:hover { background: var(--secondary-background-color, rgba(0,0,0,0.04)); }
  .aw-site-name {
    font-size: 14px; color: var(--primary-text-color);
    display: flex; align-items: center; gap: 6px;
    flex: 1; min-width: 0; overflow: hidden;
  }
  .aw-site-link {
    color: var(--primary-text-color); text-decoration: none;
    cursor: pointer; -webkit-tap-highlight-color: transparent;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .aw-site-link:hover, .aw-site-link:active { color: var(--primary-color); text-decoration: underline; }
  .aw-ff-icon { color: #ff6611; flex-shrink: 0; display: inline-flex; align-items: center; }
  .aw-ff-add {
    color: var(--disabled-text-color, #999);
    cursor: pointer; opacity: 0.5; transition: all 0.15s;
    display: inline-flex; align-items: center;
    -webkit-tap-highlight-color: transparent;
    padding: 2px; flex-shrink: 0;
  }
  .aw-ff-add:hover, .aw-ff-add:active { color: #ff6611; opacity: 1; }
  .aw-site-actions {
    display: flex; align-items: center; gap: 4px; flex-shrink: 0; margin-left: 8px;
  }
  .aw-site-remove {
    cursor: pointer; color: var(--error-color, #f44336);
    opacity: 0.5; transition: opacity 0.15s; display: flex; align-items: center;
    -webkit-tap-highlight-color: transparent; padding: 2px;
  }
  .aw-site-remove:active { opacity: 1; }
  #aw-sites-container { min-height: 20px; }
`;

/* ── Main Card (Shadow DOM) ──────────────────────────────── */

class AdGuardWhitelistCard extends HTMLElement {
  static get properties() {
    return { hass: {}, config: {} };
  }
  static getConfigElement() {
    return document.createElement("adguard-whitelist-card-editor");
  }
  static getStubConfig() {
    return { client_ip: "192.168.8.50" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._newDomain = "";
    this._ddVisible = false;
    this._ddIndex = -1;
    this._suggestions = [];
    this._pendingDomain = "";
    this._built = false;
  }

  setConfig(config) {
    if (!config.client_ip) throw new Error("Veuillez définir client_ip");
    this.config = config;
    this._built = false;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) {
      this._buildCard();
      this._built = true;
    }
    this._updateData();
  }

  /* ── Helpers ─────────────────────────────────────────────── */

  $(sel) { return this.shadowRoot.querySelector(sel); }
  $$(sel) { return this.shadowRoot.querySelectorAll(sel); }

  _findSensor() {
    if (!this._hass) return null;
    for (const eid of Object.keys(this._hass.states)) {
      if (eid.startsWith("sensor.") && eid.includes("sites_autoris")) {
        const s = this._hass.states[eid];
        if (s.attributes && s.attributes.domains) return s;
      }
    }
    return null;
  }

  /* ── Build DOM once (in Shadow DOM) ──────────────────────── */

  _buildCard() {
    const title = this.config.title || "Sites Autorisés";
    const childSuffix = this.config.child_name ? ` — ${this.config.child_name}` : "";

    this.shadowRoot.innerHTML = `
      <style>${CARD_STYLES}</style>
      <ha-card>
        <div class="aw-card">
          <div class="aw-header">
            <div class="aw-header-icon" id="aw-header-icon">
              <ha-icon icon="mdi:shield-check"></ha-icon>
            </div>
            <div class="aw-header-info">
              <div class="aw-header-title" id="aw-header-title">${title}${childSuffix}</div>
              <div class="aw-header-status" id="aw-status">${this.config.client_ip}</div>
              <div class="aw-status-row" id="aw-status-row"></div>
            </div>
          </div>

          <div class="aw-stats">
            <div class="aw-stat">
              <div class="aw-stat-value" id="aw-count">?</div>
              <div class="aw-stat-label">Sites autorisés</div>
            </div>
            <div class="aw-stat">
              <div class="aw-stat-value" id="aw-rules">?</div>
              <div class="aw-stat-label">Règles totales</div>
            </div>
          </div>

          <div class="aw-add-form" id="aw-add-form">
            <input type="text" class="aw-add-input" id="aw-input"
              placeholder="domaine.fr" autocomplete="off" autocorrect="off"
              autocapitalize="off" spellcheck="false" inputmode="url">
            <div class="aw-dd" id="aw-dd"></div>
            <button class="aw-add-btn" id="aw-add-btn" type="button">
              <ha-icon icon="mdi:plus" style="--mdc-icon-size:16px"></ha-icon>
              Ajouter
            </button>
          </div>

          <div id="aw-sites-container"></div>
        </div>
      </ha-card>
    `;

    this._bindEvents();
  }

  /* ── Bind events (once) ──────────────────────────────────── */

  _bindEvents() {
    const input = this.$("#aw-input");
    const addBtn = this.$("#aw-add-btn");

    // Stop HA from intercepting keyboard events inside Shadow DOM
    for (const evt of ["keydown", "keyup", "keypress"]) {
      input.addEventListener(evt, (e) => e.stopPropagation());
    }

    input.addEventListener("input", (e) => {
      this._newDomain = e.target.value;
      this._showSuggestions();
    });

    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        this._ddIndex = Math.min(this._ddIndex + 1, this._suggestions.length - 1);
        this._highlightDD();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        this._ddIndex = Math.max(this._ddIndex - 1, -1);
        this._highlightDD();
      } else if (e.key === "Enter") {
        e.preventDefault();
        if (this._ddIndex >= 0 && this._suggestions[this._ddIndex]) {
          this._selectSuggestion(this._suggestions[this._ddIndex]);
        } else {
          this._openAddDialog();
        }
      } else if (e.key === "Escape") {
        this._closeDD();
      }
    });

    input.addEventListener("focus", () => this._showSuggestions());
    input.addEventListener("blur", () => {
      setTimeout(() => this._closeDD(), 250);
    });

    // Add button
    addBtn.addEventListener("mousedown", (e) => e.preventDefault());
    addBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      e.preventDefault();
      this._openAddDialog();
    });

    // Prevent HA more-info on card clicks but allow links to work
    this.addEventListener("click", (e) => {
      // Let <a> links through to the WebView/browser
      const path = e.composedPath();
      const isLink = path.some((el) => el.tagName === "A");
      if (!isLink) {
        e.stopPropagation();
      }
    });
  }

  /* ── Autocomplete ──────────────────────────────────────── */

  _showSuggestions() {
    const dd = this.$("#aw-dd");
    const val = (this._newDomain || "").trim().toLowerCase();
    if (val.length < 1) { this._closeDD(); return; }

    const sensor = this._findSensor();
    const existing = new Set(sensor ? (sensor.attributes.domains || []) : []);

    this._suggestions = DOMAIN_SUGGESTIONS
      .filter((d) => d.includes(val) && !existing.has(d))
      .slice(0, 8);

    if (this._suggestions.length === 0) { this._closeDD(); return; }

    dd.innerHTML = this._suggestions
      .map((d, i) => `<div class="aw-dd-item${i === this._ddIndex ? " active" : ""}" data-dd="${d}">${d}</div>`)
      .join("");

    dd.classList.add("visible");
    this._ddVisible = true;

    dd.querySelectorAll(".aw-dd-item").forEach((el) => {
      el.addEventListener("mousedown", (e) => {
        e.preventDefault();
        this._selectSuggestion(el.dataset.dd);
      });
      // Mobile: touchend fires reliably in Shadow DOM
      el.addEventListener("touchend", (e) => {
        e.preventDefault();
        this._selectSuggestion(el.dataset.dd);
      });
    });
  }

  _highlightDD() {
    this.$$(".aw-dd-item").forEach((el, i) => {
      el.classList.toggle("active", i === this._ddIndex);
    });
  }

  _selectSuggestion(domain) {
    this._newDomain = domain;
    const input = this.$("#aw-input");
    if (input) input.value = domain;
    this._closeDD();
    this._openAddDialog();
  }

  _closeDD() {
    const dd = this.$("#aw-dd");
    if (dd) dd.classList.remove("visible");
    this._ddVisible = false;
    this._ddIndex = -1;
  }

  /* ── Dialog (appended to document.body — outside Shadow DOM) ─ */

  _openAddDialog() {
    if (!this._newDomain) return;
    let domain = this._newDomain.trim().toLowerCase()
      .replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    if (!domain) return;
    this._closeDD();
    this._pendingDomain = domain;
    this._removeDialog();

    const sensor = this._findSensor();
    const sshEnabled = sensor ? (sensor.attributes.ssh_enabled || false) : false;

    const catOptions = CATEGORY_OPTIONS
      .map((c) => `<option value="${c}">${c}</option>`)
      .join("");

    const overlay = document.createElement("div");
    overlay.id = "aw-dialog-overlay";
    overlay.style.cssText = "position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);z-index:99999;display:flex;justify-content:center;align-items:center;font-family:var(--paper-font-body1_-_font-family,Roboto,sans-serif);";
    overlay.innerHTML = `
      <div style="background:var(--card-background-color,#1c1c1c);color:var(--primary-text-color,#fff);border-radius:16px;padding:24px;width:340px;max-width:90vw;box-shadow:0 8px 32px rgba(0,0,0,0.3);">
        <h3 style="margin:0 0 16px;font-size:18px;font-weight:500;">Ajouter un site</h3>
        <div style="background:var(--secondary-background-color,#333);padding:8px 12px;border-radius:8px;font-family:monospace;font-size:14px;margin-bottom:16px;word-break:break-all;">${domain}</div>
        <label style="display:block;font-size:13px;font-weight:500;margin-bottom:4px;color:var(--secondary-text-color,#aaa);">Catégorie</label>
        <select id="aw-dlg-cat" style="width:100%;padding:10px 12px;border:1px solid var(--divider-color,#555);border-radius:8px;font-size:14px;margin-bottom:12px;background:var(--card-background-color,#1c1c1c);color:var(--primary-text-color,#fff);box-sizing:border-box;-webkit-appearance:none;">
          <option value="">— Auto-détection —</option>
          ${catOptions}
        </select>
        <div style="display:${sshEnabled ? "flex" : "none"};align-items:center;gap:8px;margin-bottom:16px;font-size:14px;">
          <input type="checkbox" id="aw-dlg-bm" ${sshEnabled ? "checked" : ""} style="width:20px;height:20px;accent-color:var(--primary-color,#03a9f4);">
          <label for="aw-dlg-bm" style="margin:0;cursor:pointer;">Créer un raccourci Firefox</label>
        </div>
        <div style="display:flex;gap:8px;justify-content:flex-end;">
          <button id="aw-dlg-cancel" style="padding:10px 20px;border:none;border-radius:8px;font-size:14px;font-weight:500;cursor:pointer;background:var(--secondary-background-color,#333);color:var(--primary-text-color,#fff);-webkit-tap-highlight-color:transparent;">Annuler</button>
          <button id="aw-dlg-confirm" style="padding:10px 20px;border:none;border-radius:8px;font-size:14px;font-weight:500;cursor:pointer;background:var(--primary-color,#03a9f4);color:white;-webkit-tap-highlight-color:transparent;">Ajouter</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector("#aw-dlg-cancel").addEventListener("click", () => this._removeDialog());
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) this._removeDialog();
    });
    overlay.querySelector("#aw-dlg-confirm").addEventListener("click", () => this._confirmAdd());
    overlay.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Escape") this._removeDialog();
      if (e.key === "Enter") this._confirmAdd();
    });
  }

  _confirmAdd() {
    if (!this._hass || !this._pendingDomain) return;
    const overlay = document.getElementById("aw-dialog-overlay");
    if (!overlay) return;

    const category = overlay.querySelector("#aw-dlg-cat").value || undefined;
    const bmCheckbox = overlay.querySelector("#aw-dlg-bm");
    const createBookmark = bmCheckbox ? bmCheckbox.checked : false;

    const serviceData = { domain: this._pendingDomain };
    if (category) serviceData.category = category;
    serviceData.create_bookmark = createBookmark;

    this._hass.callService("adguard_whitelist", "add_site", serviceData);
    this._newDomain = "";
    this._pendingDomain = "";
    const input = this.$("#aw-input");
    if (input) input.value = "";
    this._removeDialog();
  }

  _removeDialog() {
    const overlay = document.getElementById("aw-dialog-overlay");
    if (overlay) overlay.remove();
  }

  /* ── Update dynamic data ─────────────────────────────────── */

  _updateData() {
    const sensor = this._findSensor();
    if (!sensor) return;

    const count = sensor.state;
    const totalRules = sensor.attributes.total_rules || 0;
    const pendingSsh = sensor.attributes.pending_ssh || 0;
    const bookmarked = new Set(sensor.attributes.bookmarked_domains || []);
    const showCdn = this.config.show_cdn !== false;

    const countEl = this.$("#aw-count");
    const rulesEl = this.$("#aw-rules");
    if (countEl) countEl.textContent = count;
    if (rulesEl) rulesEl.textContent = totalRules;

    const adguardOk = sensor.attributes.adguard_reachable !== false;
    const sshOk = sensor.attributes.ssh_reachable || false;
    const sshEnabled = sensor.attributes.ssh_enabled || false;

    const headerIcon = this.$("#aw-header-icon");
    if (headerIcon) {
      // Icon is green only if ALL enabled services are OK
      const allOk = adguardOk && (!sshEnabled || sshOk);
      headerIcon.style.background = allOk
        ? "var(--success-color, #4caf50)"
        : "var(--error-color, #f44336)";
    }

    const statusEl = this.$("#aw-status");
    if (statusEl) {
      const allOk = adguardOk && (!sshEnabled || sshOk);
      statusEl.style.color = allOk
        ? "var(--success-color, #4caf50)"
        : "var(--error-color, #f44336)";
      const statusText = !adguardOk ? "Hors ligne" : (sshEnabled && !sshOk ? "SSH hors ligne" : "Connecté");
      statusEl.innerHTML = statusText +
        (pendingSsh > 0 ? ` <span class="aw-pending-badge">${pendingSsh} synchro en attente</span>` : "");
    }

    const statusRow = this.$("#aw-status-row");
    if (statusRow) {
      let dots = `<span><span class="aw-status-dot ${adguardOk ? "online" : "offline"}"></span>AdGuard</span>`;
      if (sshEnabled) {
        dots += `<span><span class="aw-status-dot ${sshOk ? "online" : "offline"}"></span>SSH</span>`;
      }
      statusRow.innerHTML = dots;
    }

    // Build categories
    const categories = {};
    const attrs = sensor.attributes;
    for (const key of Object.keys(attrs)) {
      if (key.startsWith("category_")) {
        let displayName = key.replace("category_", "");
        if (key === "category_éducation" || key === "category_education") displayName = "Éducation";
        else if (key === "category_programmation") displayName = "Programmation";
        else if (key === "category_cdn_technique" || key === "category_cdn_/_technique") displayName = "CDN / Technique";
        else if (key === "category_divertissement") displayName = "Divertissement";
        else if (key === "category_communication") displayName = "Communication";
        else if (key === "category_shopping") displayName = "Shopping";
        else if (key === "category_actualités" || key === "category_actualites") displayName = "Actualités";
        else if (key === "category_services_publics") displayName = "Services publics";
        else if (key === "category_autre") displayName = "Autre";

        const domains = attrs[key];
        if (Array.isArray(domains) && domains.length > 0) {
          categories[displayName] = domains;
        }
      }
    }

    const CAT_ORDER = [
      "Éducation", "Programmation", "Divertissement", "Communication",
      "Shopping", "Actualités", "Services publics", "Autre", "CDN / Technique",
    ];
    const sortedCats = Object.entries(categories).sort(([a], [b]) => {
      const ia = CAT_ORDER.indexOf(a);
      const ib = CAT_ORDER.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

    const container = this.$("#aw-sites-container");
    if (!container) return;

    let html = "";
    for (const [catName, catDomains] of sortedCats) {
      if (!showCdn && catName === "CDN / Technique") continue;

      const icon = CAT_ICONS[catName] || "mdi:web";
      const color = CAT_COLORS[catName] || "var(--primary-text-color)";

      html += `<div class="aw-category">
        <div class="aw-category-header">
          <ha-icon icon="${icon}" style="--mdc-icon-size:14px;color:${color}"></ha-icon>
          <span style="color:${color}">${catName}</span>
          <span class="aw-category-count">${catDomains.length}</span>
        </div>`;

      for (const d of catDomains) {
        const hasBm = bookmarked.has(d);
        let ffHtml = "";
        if (hasBm) {
          ffHtml = `<span class="aw-ff-icon">${FF_ICON}</span>`;
        } else if (sshEnabled) {
          ffHtml = `<span class="aw-ff-add" data-bookmark="${d}" title="Créer un raccourci Firefox">${FF_ICON}</span>`;
        }
        html += `<div class="aw-site-item">
          <span class="aw-site-name">${ffHtml}<a href="https://${d}" target="_blank" rel="noopener" class="aw-site-link">${d}</a></span>
          <div class="aw-site-actions">
            <div class="aw-site-remove" data-remove="${d}" title="Supprimer">
              <ha-icon icon="mdi:close-circle-outline" style="--mdc-icon-size:20px"></ha-icon>
            </div>
          </div>
        </div>`;
      }

      html += `</div>`;
    }

    if (!html) {
      html = '<div style="text-align:center;color:var(--secondary-text-color);padding:16px;">Aucun site autorisé</div>';
    }

    container.innerHTML = html;

    // Force ha-icon elements to upgrade in Shadow DOM
    container.querySelectorAll("ha-icon").forEach((el) => {
      customElements.upgrade(el);
    });

    // Bind remove buttons
    container.querySelectorAll("[data-remove]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const domain = el.dataset.remove;
        if (confirm(`Supprimer ${domain} de la liste blanche ?`)) {
          this._removeSite(domain);
        }
      });
    });

    // Bind bookmark buttons
    container.querySelectorAll("[data-bookmark]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        e.preventDefault();
        this._addBookmark(el.dataset.bookmark);
      });
    });

    // <a> tags work naturally — event listener on host lets links through
  }

  _removeSite(domain) {
    if (!this._hass) return;
    this._hass.callService("adguard_whitelist", "remove_site", { domain });
  }

  _addBookmark(domain) {
    if (!this._hass) return;
    this._hass.callService("adguard_whitelist", "add_bookmark", { domain });
  }

  getCardSize() {
    return 6;
  }
}

/* ── Config Editor ───────────────────────────────────────── */

class AdGuardWhitelistCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }
  set hass(hass) { this._hass = hass; }

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        .editor { padding: 16px; }
        .field { margin-bottom: 12px; }
        label { display: block; margin-bottom: 4px; font-weight: 500; font-size: 14px; }
        input[type="text"] {
          width: 100%; padding: 8px; border: 1px solid var(--divider-color);
          border-radius: 4px; box-sizing: border-box; font-size: 14px;
          background: var(--card-background-color); color: var(--primary-text-color);
        }
        .check-label {
          display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px;
        }
      </style>
      <div class="editor">
        <div class="field">
          <label>IP du client</label>
          <input type="text" id="client_ip" value="${this._config.client_ip || ""}" placeholder="192.168.8.50">
        </div>
        <div class="field">
          <label>Nom de l'enfant (optionnel)</label>
          <input type="text" id="child_name" value="${this._config.child_name || ""}" placeholder="Camille">
        </div>
        <div class="field">
          <label>Titre (optionnel)</label>
          <input type="text" id="title" value="${this._config.title || ""}" placeholder="Sites Autorisés">
        </div>
        <div class="field">
          <label class="check-label">
            <input type="checkbox" id="show_cdn" ${this._config.show_cdn !== false ? "checked" : ""}>
            Afficher les CDN / domaines techniques
          </label>
        </div>
      </div>
    `;

    this.shadowRoot.querySelector("#client_ip").addEventListener("input", (e) => {
      this._config = { ...this._config, client_ip: e.target.value };
      this._dispatch();
    });
    this.shadowRoot.querySelector("#child_name").addEventListener("input", (e) => {
      this._config = { ...this._config, child_name: e.target.value };
      this._dispatch();
    });
    this.shadowRoot.querySelector("#title").addEventListener("input", (e) => {
      this._config = { ...this._config, title: e.target.value };
      this._dispatch();
    });
    this.shadowRoot.querySelector("#show_cdn").addEventListener("change", (e) => {
      this._config = { ...this._config, show_cdn: e.target.checked };
      this._dispatch();
    });
  }

  _dispatch() {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: this._config } }));
  }
}

/* ── Register ────────────────────────────────────────────── */

customElements.define("adguard-whitelist-card", AdGuardWhitelistCard);
customElements.define("adguard-whitelist-card-editor", AdGuardWhitelistCardEditor);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "adguard-whitelist-card",
  name: "AdGuard Whitelist - Sites Autorisés",
  description: "Gérer les sites autorisés dans AdGuard Home",
  preview: true,
});

console.info(
  `%c ADGUARD-WHITELIST-CARD %c v${CARD_VERSION} `,
  "color: white; background: #4caf50; font-weight: bold; padding: 2px 4px; border-radius: 4px 0 0 4px;",
  "color: #4caf50; background: white; font-weight: bold; padding: 2px 4px; border-radius: 0 4px 4px 0; border: 1px solid #4caf50;"
);
