const CARD_VERSION = "2.3.0";

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

/* ── Main Card ───────────────────────────────────────────── */

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

  setConfig(config) {
    if (!config.client_ip) throw new Error("Veuillez définir client_ip");
    this.config = config;
    this._newDomain = "";
    this._ddVisible = false;
    this._ddIndex = -1;
    this._suggestions = [];
    this._pendingDomain = "";
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

  /* ── Sensor lookup ─────────────────────────────────────── */

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

  /* ── Build DOM once ────────────────────────────────────── */

  _buildCard() {
    const title = this.config.title || "Sites Autorisés";
    this.innerHTML = `
      <ha-card>
        <style>
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
          }
          .aw-header-info { flex: 1; }
          .aw-header-title { font-size: 16px; font-weight: 500; }
          .aw-header-status {
            font-size: 12px; transition: color 0.3s;
          }
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
          .aw-add-form { position: relative; display: flex; gap: 8px; margin-bottom: 16px; }
          .aw-add-input {
            flex: 1; padding: 8px 12px;
            border: 1px solid var(--divider-color); border-radius: 8px;
            background: var(--card-background-color, var(--ha-card-background));
            color: var(--primary-text-color); font-size: 14px; outline: none;
          }
          .aw-add-input:focus { border-color: var(--primary-color); }
          .aw-add-input::placeholder { color: var(--secondary-text-color); }
          .aw-add-btn {
            padding: 8px 16px; border: none; border-radius: 8px;
            background: var(--primary-color); color: white;
            font-size: 14px; font-weight: 500; cursor: pointer;
            display: flex; align-items: center; gap: 4px;
            white-space: nowrap;
          }
          .aw-add-btn:hover { opacity: 0.9; }

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
            padding: 8px 12px; cursor: pointer; font-size: 13px;
            color: var(--primary-text-color);
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
            padding: 6px 8px; border-radius: 8px; transition: background 0.15s;
          }
          .aw-site-item:hover { background: var(--secondary-background-color, rgba(0,0,0,0.04)); }
          .aw-site-name {
            font-size: 13px; color: var(--primary-text-color);
            display: flex; align-items: center; gap: 4px;
          }
          .aw-ff-icon { color: #ff6611; --mdc-icon-size: 16px; }
          .aw-ff-add {
            color: var(--disabled-text-color, #bbb); --mdc-icon-size: 16px;
            cursor: pointer; opacity: 0.4; transition: opacity 0.15s;
          }
          .aw-site-item:hover .aw-ff-add { opacity: 0.8; }
          .aw-ff-add:hover { color: #ff6611 !important; opacity: 1 !important; }
          .aw-site-remove {
            cursor: pointer; color: var(--error-color, #f44336);
            opacity: 0.4; transition: opacity 0.15s; display: flex; align-items: center;
          }
          .aw-site-item:hover .aw-site-remove { opacity: 1; }
          #aw-sites-container { min-height: 20px; }
        </style>

        <div class="aw-card">
          <div class="aw-header">
            <div class="aw-header-icon" id="aw-header-icon">
              <ha-icon icon="mdi:shield-check"></ha-icon>
            </div>
            <div class="aw-header-info">
              <div class="aw-header-title" id="aw-header-title">${title}${this.config.child_name ? ` — ${this.config.child_name}` : ""}</div>
              <div class="aw-header-status" id="aw-status">
                ${this.config.client_ip}
              </div>
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
              placeholder="domaine.fr" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false">
            <div class="aw-dd" id="aw-dd"></div>
            <button class="aw-add-btn" id="aw-add-btn">
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

  /* ── Bind events (once) ────────────────────────────────── */

  _bindEvents() {
    const input = this.querySelector("#aw-input");
    const addBtn = this.querySelector("#aw-add-btn");
    const dd = this.querySelector("#aw-dd");

    // Prevent HA from intercepting keyboard events
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
      // Delay to allow click on suggestion
      setTimeout(() => this._closeDD(), 200);
    });

    // Prevent blur before click fires
    addBtn.addEventListener("mousedown", (e) => e.preventDefault());
    addBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this._openAddDialog();
    });
  }

  /* ── Autocomplete ──────────────────────────────────────── */

  _showSuggestions() {
    const dd = this.querySelector("#aw-dd");
    const val = (this._newDomain || "").trim().toLowerCase();
    if (val.length < 1) {
      this._closeDD();
      return;
    }
    // Get already whitelisted domains
    const sensor = this._findSensor();
    const existing = new Set(sensor ? (sensor.attributes.domains || []) : []);

    this._suggestions = DOMAIN_SUGGESTIONS
      .filter((d) => d.includes(val) && !existing.has(d))
      .slice(0, 8);

    if (this._suggestions.length === 0) {
      this._closeDD();
      return;
    }

    dd.innerHTML = this._suggestions
      .map((d, i) => `<div class="aw-dd-item${i === this._ddIndex ? " active" : ""}" data-dd="${d}">${d}</div>`)
      .join("");

    dd.classList.add("visible");
    this._ddVisible = true;

    // Use mousedown to fire before blur
    dd.querySelectorAll(".aw-dd-item").forEach((el) => {
      el.addEventListener("mousedown", (e) => {
        e.preventDefault();
        this._selectSuggestion(el.dataset.dd);
      });
    });
  }

  _highlightDD() {
    const items = this.querySelectorAll(".aw-dd-item");
    items.forEach((el, i) => {
      el.classList.toggle("active", i === this._ddIndex);
    });
  }

  _selectSuggestion(domain) {
    this._newDomain = domain;
    const input = this.querySelector("#aw-input");
    if (input) input.value = domain;
    this._closeDD();
    this._openAddDialog();
  }

  _closeDD() {
    const dd = this.querySelector("#aw-dd");
    if (dd) dd.classList.remove("visible");
    this._ddVisible = false;
    this._ddIndex = -1;
  }

  /* ── Dialog (appended to document.body) ────────────────── */

  _openAddDialog() {
    if (!this._newDomain) return;
    let domain = this._newDomain.trim().toLowerCase()
      .replace(/^https?:\/\//, "").replace(/\/.*$/, "");
    if (!domain) return;
    this._closeDD();
    this._pendingDomain = domain;

    // Remove existing dialog if any
    this._removeDialog();

    const sensor = this._findSensor();
    const sshEnabled = sensor ? (sensor.attributes.ssh_enabled || false) : false;

    // Build category options
    const catOptions = CATEGORY_OPTIONS
      .map((c) => `<option value="${c}">${c}</option>`)
      .join("");

    // Create overlay div
    const overlay = document.createElement("div");
    overlay.id = "aw-dialog-overlay";
    overlay.innerHTML = `
      <style>
        #aw-dialog-overlay {
          position: fixed; top: 0; left: 0; right: 0; bottom: 0;
          background: rgba(0,0,0,0.5); z-index: 99999;
          display: flex; justify-content: center; align-items: center;
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
        }
        .aw-dlg {
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #333);
          border-radius: 16px; padding: 24px; width: 340px; max-width: 90vw;
          box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .aw-dlg h3 { margin: 0 0 16px; font-size: 18px; font-weight: 500; }
        .aw-dlg-domain {
          background: var(--secondary-background-color, #f5f5f5);
          padding: 8px 12px; border-radius: 8px; font-family: monospace;
          font-size: 14px; margin-bottom: 16px; word-break: break-all;
        }
        .aw-dlg label {
          display: block; font-size: 13px; font-weight: 500;
          margin-bottom: 4px; color: var(--secondary-text-color, #666);
        }
        .aw-dlg select, .aw-dlg input[type="text"] {
          width: 100%; padding: 8px 12px; border: 1px solid var(--divider-color, #ddd);
          border-radius: 8px; font-size: 14px; margin-bottom: 12px;
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color, #333);
          box-sizing: border-box;
        }
        .aw-dlg-bm {
          display: flex; align-items: center; gap: 8px;
          margin-bottom: 16px; font-size: 14px;
        }
        .aw-dlg-bm input[type="checkbox"] {
          width: 18px; height: 18px; accent-color: var(--primary-color, #03a9f4);
        }
        .aw-dlg-actions {
          display: flex; gap: 8px; justify-content: flex-end;
        }
        .aw-dlg-btn {
          padding: 8px 20px; border: none; border-radius: 8px;
          font-size: 14px; font-weight: 500; cursor: pointer;
        }
        .aw-dlg-btn-cancel {
          background: var(--secondary-background-color, #e0e0e0);
          color: var(--primary-text-color, #333);
        }
        .aw-dlg-btn-confirm {
          background: var(--primary-color, #03a9f4); color: white;
        }
        .aw-dlg-btn:hover { opacity: 0.9; }
      </style>
      <div class="aw-dlg">
        <h3>Ajouter un site</h3>
        <div class="aw-dlg-domain">${domain}</div>
        <label>Catégorie</label>
        <select id="aw-dlg-cat">
          <option value="">— Auto-détection —</option>
          ${catOptions}
        </select>
        <div class="aw-dlg-bm" style="${sshEnabled ? "" : "display:none"}">
          <input type="checkbox" id="aw-dlg-bm" ${sshEnabled ? "checked" : ""}>
          <label for="aw-dlg-bm" style="margin:0; cursor:pointer;">
            Créer un raccourci Firefox
          </label>
        </div>
        <div class="aw-dlg-actions">
          <button class="aw-dlg-btn aw-dlg-btn-cancel" id="aw-dlg-cancel">Annuler</button>
          <button class="aw-dlg-btn aw-dlg-btn-confirm" id="aw-dlg-confirm">Ajouter</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // Bind dialog events
    overlay.querySelector("#aw-dlg-cancel").addEventListener("click", () => this._removeDialog());
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) this._removeDialog();
    });
    overlay.querySelector("#aw-dlg-confirm").addEventListener("click", () => this._confirmAdd());

    // Prevent HA keyboard shortcuts in dialog
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
    const input = this.querySelector("#aw-input");
    if (input) input.value = "";
    this._removeDialog();
  }

  _removeDialog() {
    const overlay = document.getElementById("aw-dialog-overlay");
    if (overlay) overlay.remove();
  }

  /* ── Update dynamic data ───────────────────────────────── */

  _updateData() {
    const sensor = this._findSensor();
    if (!sensor) return;

    const count = sensor.state;
    const totalRules = sensor.attributes.total_rules || 0;
    const pendingSsh = sensor.attributes.pending_ssh || 0;
    const bookmarked = new Set(sensor.attributes.bookmarked_domains || []);
    const showCdn = this.config.show_cdn !== false;

    // Update stats
    const countEl = this.querySelector("#aw-count");
    const rulesEl = this.querySelector("#aw-rules");
    if (countEl) countEl.textContent = count;
    if (rulesEl) rulesEl.textContent = totalRules;

    // Update status
    const adguardOk = sensor.attributes.adguard_reachable !== false;
    const sshOk = sensor.attributes.ssh_reachable || false;
    const sshEnabled = sensor.attributes.ssh_enabled || false;

    // Dynamic header icon color (like timekpra)
    const headerIcon = this.querySelector("#aw-header-icon");
    if (headerIcon) {
      headerIcon.style.background = adguardOk
        ? "var(--success-color, #4caf50)"
        : "var(--error-color, #f44336)";
    }

    const statusEl = this.querySelector("#aw-status");
    if (statusEl) {
      statusEl.style.color = adguardOk
        ? "var(--success-color, #4caf50)"
        : "var(--secondary-text-color)";
      const statusText = adguardOk ? "Connecté" : "Hors ligne";
      statusEl.innerHTML = statusText +
        (pendingSsh > 0 ? ` <span class="aw-pending-badge">${pendingSsh} synchro en attente</span>` : "");
    }

    const statusRow = this.querySelector("#aw-status-row");
    if (statusRow) {
      let dots = `<span><span class="aw-status-dot ${adguardOk ? "online" : "offline"}"></span>AdGuard</span>`;
      if (sshEnabled) {
        dots += `<span><span class="aw-status-dot ${sshOk ? "online" : "offline"}"></span>SSH</span>`;
      }
      statusRow.innerHTML = dots;
    }

    // Build categories from sensor attributes
    const categories = {};
    const attrs = sensor.attributes;
    for (const key of Object.keys(attrs)) {
      if (key.startsWith("category_")) {
        const catName = key.replace("category_", "")
          .replace(/_/g, " ")
          .replace(/\b\w/g, (c) => c.toUpperCase())
          .replace("Cdn", "CDN")
          .replace("/ ", "/ ");
        // Fix known category name mappings
        let displayName = catName;
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

    // Sort categories: Éducation, Programmation first — Autre, CDN last
    const CAT_ORDER = [
      "Éducation", "Programmation", "Divertissement", "Communication",
      "Shopping", "Actualités", "Services publics", "Autre", "CDN / Technique",
    ];
    const sortedCats = Object.entries(categories).sort(([a], [b]) => {
      const ia = CAT_ORDER.indexOf(a);
      const ib = CAT_ORDER.indexOf(b);
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    });

    // Render sites
    const container = this.querySelector("#aw-sites-container");
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
        </div>
        <div class="aw-site-list">`;

      for (const d of catDomains) {
        const hasBm = bookmarked.has(d);
        let ffHtml = "";
        if (hasBm) {
          ffHtml = '<ha-icon icon="mdi:firefox" class="aw-ff-icon"></ha-icon>';
        } else if (sshEnabled) {
          ffHtml = `<ha-icon icon="mdi:firefox" class="aw-ff-add" data-bookmark="${d}" title="Créer un raccourci Firefox"></ha-icon>`;
        }
        html += `<div class="aw-site-item">
          <span class="aw-site-name">${ffHtml}${d}</span>
          <div class="aw-site-remove" data-remove="${d}" title="Supprimer">
            <ha-icon icon="mdi:close-circle-outline" style="--mdc-icon-size:18px"></ha-icon>
          </div>
        </div>`;
      }

      html += `</div></div>`;
    }

    if (!html) {
      html = '<div style="text-align:center;color:var(--secondary-text-color);padding:16px;">Aucun site autorisé</div>';
    }

    container.innerHTML = html;

    // Bind remove buttons
    container.querySelectorAll("[data-remove]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
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
        const domain = el.dataset.bookmark;
        this._addBookmark(domain);
      });
    });
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
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }
  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    this.innerHTML = `
      <div style="padding: 16px;">
        <div style="margin-bottom: 12px;">
          <label style="display:block;margin-bottom:4px;font-weight:500;">IP du client</label>
          <input type="text" id="client_ip" value="${this._config.client_ip || ""}"
            style="width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:4px;box-sizing:border-box;"
            placeholder="192.168.8.50">
        </div>
        <div style="margin-bottom: 12px;">
          <label style="display:block;margin-bottom:4px;font-weight:500;">Nom de l'enfant (optionnel)</label>
          <input type="text" id="child_name" value="${this._config.child_name || ""}"
            style="width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:4px;box-sizing:border-box;"
            placeholder="Camille">
        </div>
        <div style="margin-bottom: 12px;">
          <label style="display:block;margin-bottom:4px;font-weight:500;">Titre (optionnel)</label>
          <input type="text" id="title" value="${this._config.title || ""}"
            style="width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:4px;box-sizing:border-box;"
            placeholder="Sites Autorisés">
        </div>
        <div>
          <label style="display:flex;align-items:center;gap:8px;cursor:pointer;">
            <input type="checkbox" id="show_cdn" ${this._config.show_cdn !== false ? "checked" : ""}>
            Afficher les CDN / domaines techniques
          </label>
        </div>
      </div>
    `;

    this.querySelector("#client_ip").addEventListener("input", (e) => {
      this._config = { ...this._config, client_ip: e.target.value };
      this._dispatch();
    });
    this.querySelector("#child_name").addEventListener("input", (e) => {
      this._config = { ...this._config, child_name: e.target.value };
      this._dispatch();
    });
    this.querySelector("#title").addEventListener("input", (e) => {
      this._config = { ...this._config, title: e.target.value };
      this._dispatch();
    });
    this.querySelector("#show_cdn").addEventListener("change", (e) => {
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
