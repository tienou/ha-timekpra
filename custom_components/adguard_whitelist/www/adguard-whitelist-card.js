const CARD_VERSION = "1.1.0";

/* ── Popular domains for autocomplete ── */
const DOMAIN_SUGGESTIONS = [
  // Google
  "google.fr","google.com","gmail.com","drive.google.com","docs.google.com",
  "sheets.google.com","slides.google.com","maps.google.com","translate.google.com",
  "youtube.com","classroom.google.com","meet.google.com","photos.google.com",
  "calendar.google.com","play.google.com",
  // Microsoft
  "microsoft.com","outlook.com","office.com","teams.microsoft.com",
  "onedrive.live.com","bing.com","live.com","login.microsoftonline.com",
  // GitHub / Dev
  "github.com","gitlab.com","stackoverflow.com","codepen.io","replit.com",
  "codesandbox.io","w3schools.com","developer.mozilla.org","npmjs.com",
  "python.org","openclassrooms.com","freecodecamp.org","codecademy.com",
  "leetcode.com","hackerrank.com","rust-lang.org","go.dev","devdocs.io",
  // Education FR
  "wikipedia.org","fr.wikipedia.org","wikimedia.org","khanacademy.org",
  "fr.khanacademy.org","lumni.fr","education.gouv.fr","cned.fr",
  "maxicours.com","kartable.fr","schoolmouv.fr","eduscol.education.fr",
  "pronote.net","ecole-directe.com","myriae.education.fr",
  // Maths / Sciences
  "geogebra.org","sesamath.net","labomep.sesamath.net","mathway.com",
  "wolframalpha.com","desmos.com","jeuxmaths.fr","calculatice.ac-lille.fr",
  // Langues
  "duolingo.com","babbel.com","wordreference.com","linguee.fr","deepl.com",
  "conjugueur.reverso.net","context.reverso.net",
  // Encyclopédies / Référence
  "larousse.fr","universalis.fr","vikidia.org","1jour1actu.com",
  // Coding enfants
  "scratch.mit.edu","code.org","studio.code.org","makecode.microbit.org",
  "blockly.games","hourofcode.com",
  // Vidéo
  "netflix.com","disneyplus.com","primevideo.com","france.tv","arte.tv",
  "tf1.fr","6play.fr","twitch.tv","crunchyroll.com","molotov.tv",
  // Musique
  "spotify.com","open.spotify.com","deezer.com","soundcloud.com",
  "music.youtube.com","music.apple.com",
  // Gaming
  "minecraft.net","roblox.com","steampowered.com","store.steampowered.com",
  "epicgames.com","ea.com","ubisoft.com","nintendo.com",
  "playstation.com","xbox.com",
  // Social / Messagerie
  "discord.com","whatsapp.com","web.whatsapp.com","telegram.org",
  "signal.org","snapchat.com",
  // Outils
  "canva.com","notion.so","trello.com","figma.com","draw.io",
  "excalidraw.com","overleaf.com","chatgpt.com","claude.ai",
  // Shopping FR
  "amazon.fr","fnac.com","cdiscount.com","darty.com","leboncoin.fr",
  "vinted.fr","backmarket.fr",
  // Presse FR
  "lemonde.fr","lefigaro.fr","liberation.fr","francetvinfo.fr",
  "20minutes.fr","lequipe.fr","ouest-france.fr",
  // Services FR
  "allocine.fr","marmiton.org","meteofrance.com","laposte.fr",
  "impots.gouv.fr","ameli.fr","service-public.fr","sncf-connect.com",
  // Autres
  "apple.com","icloud.com","zoom.us","dropbox.com","wetransfer.com",
  "pinterest.com","reddit.com","medium.com","linkedin.com","adobe.com",
  // CDN / Technique
  "cloudflare.com","googleapis.com","gstatic.com","amazonaws.com",
  "akamaized.net","jsdelivr.net","unpkg.com","cdnjs.cloudflare.com",
  "bootstrapcdn.com","fonts.googleapis.com","fontawesome.com",
  "gravatar.com","wp.com","fastly.net",
].sort();

/* ── Card ── */
class AdGuardWhitelistCard extends HTMLElement {
  constructor() {
    super();
    this._built = false;
    this._newDomain = "";
    this._highlightIdx = -1;
    this._lastDataJson = "";
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
    if (this._hass && !this._built) this._buildCard();
    else if (this._built) this._updateHeader();
  }

  set hass(hass) {
    this._hass = hass;
    if (this.config && !this._built) { this._buildCard(); return; }
    if (!this._built) return;
    const sensor = this._findSensor();
    const json = sensor
      ? JSON.stringify({ s: sensor.state, a: sensor.attributes })
      : "";
    if (json !== this._lastDataJson) {
      this._lastDataJson = json;
      this._updateData(sensor);
    }
  }

  _findSensor() {
    if (!this._hass) return null;
    for (const eid of Object.keys(this._hass.states)) {
      if (eid.startsWith("sensor.") && eid.includes("sites_autoris")) {
        const st = this._hass.states[eid];
        if (st.attributes && st.attributes.domains) return st;
      }
    }
    return null;
  }

  /* ── Build DOM once ── */
  _buildCard() {
    if (!this.config || !this._hass) return;

    const title = this.config.title || "Sites Autorisés";

    this.innerHTML = `
    <ha-card>
      <style>${AdGuardWhitelistCard._css()}</style>
      <div class="aw-card">
        <div class="aw-header">
          <div class="aw-header-icon"><ha-icon icon="mdi:shield-check"></ha-icon></div>
          <div class="aw-header-info">
            <div class="aw-header-title" id="aw-title">${title}</div>
            <div class="aw-header-status" id="aw-status">
              AdGuard Home &middot; ${this.config.client_ip}
            </div>
          </div>
        </div>
        <div class="aw-stats">
          <div class="aw-stat">
            <div class="aw-stat-value" id="aw-count">?</div>
            <div class="aw-stat-label">Sites autorisés</div>
          </div>
          <div class="aw-stat">
            <div class="aw-stat-value" id="aw-rules">0</div>
            <div class="aw-stat-label">Règles totales</div>
          </div>
        </div>
        <div class="aw-add-form">
          <div class="aw-input-wrapper">
            <input type="text" class="aw-add-input" id="aw-input"
                   placeholder="Ajouter un domaine..." autocomplete="off">
            <div class="aw-dropdown" id="aw-dropdown"></div>
          </div>
          <button class="aw-add-btn" id="aw-add-btn">
            <ha-icon icon="mdi:plus" style="--mdc-icon-size:16px"></ha-icon>
            Ajouter
          </button>
        </div>
        <div id="aw-sites"></div>
      </div>
    </ha-card>`;

    this._bindEvents();
    this._built = true;
    this._updateData(this._findSensor());
  }

  /* ── Events (bound once) ── */
  _bindEvents() {
    const input = this.querySelector("#aw-input");
    const addBtn = this.querySelector("#aw-add-btn");
    const dropdown = this.querySelector("#aw-dropdown");

    // Stop ALL keyboard/focus events from bubbling to HA's global handlers
    const stop = (e) => e.stopPropagation();
    input.addEventListener("keydown", stop);
    input.addEventListener("keyup", stop);
    input.addEventListener("keypress", stop);
    input.addEventListener("focusin", stop);
    input.addEventListener("focusout", stop);

    input.addEventListener("input", () => {
      this._newDomain = input.value;
      this._highlightIdx = -1;
      this._updateSuggestions();
    });

    input.addEventListener("focus", () => {
      if (this._newDomain.length >= 2) this._updateSuggestions();
    });

    input.addEventListener("keydown", (e) => {
      const items = dropdown.querySelectorAll(".aw-sug");
      if (e.key === "Enter") {
        e.preventDefault();
        if (this._highlightIdx >= 0 && items[this._highlightIdx]) {
          this._selectSuggestion(items[this._highlightIdx].dataset.domain);
        } else {
          this._addSite();
        }
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        this._moveHL(1, items);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        this._moveHL(-1, items);
      } else if (e.key === "Escape") {
        this._closeDD();
      }
    });

    addBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      this._addSite();
    });

    // close dropdown on outside click
    document.addEventListener("click", (e) => {
      if (!this.contains(e.target)) this._closeDD();
    });

    // delegate remove clicks in #aw-sites
    this.querySelector("#aw-sites").addEventListener("click", (e) => {
      const rm = e.target.closest("[data-remove]");
      if (rm) {
        e.stopPropagation();
        this._removeSite(rm.dataset.remove);
      }
    });
  }

  /* ── Autocomplete ── */
  _updateSuggestions() {
    const dropdown = this.querySelector("#aw-dropdown");
    const q = this._newDomain.trim().toLowerCase();
    if (q.length < 2) { this._closeDD(); return; }

    const matches = DOMAIN_SUGGESTIONS.filter((d) => d.includes(q)).slice(0, 8);
    if (!matches.length) { this._closeDD(); return; }

    dropdown.innerHTML = matches
      .map((d, i) => {
        const idx = d.indexOf(q);
        const before = d.slice(0, idx);
        const bold = d.slice(idx, idx + q.length);
        const after = d.slice(idx + q.length);
        return `<div class="aw-sug${i === this._highlightIdx ? " hl" : ""}" data-domain="${d}">${before}<strong>${bold}</strong>${after}</div>`;
      })
      .join("");
    dropdown.style.display = "block";

    dropdown.querySelectorAll(".aw-sug").forEach((el) => {
      el.addEventListener("mousedown", (e) => {
        e.preventDefault();
        e.stopPropagation();
        this._selectSuggestion(el.dataset.domain);
      });
    });
  }

  _selectSuggestion(domain) {
    const input = this.querySelector("#aw-input");
    input.value = domain;
    this._newDomain = domain;
    this._closeDD();
    this._addSite();
  }

  _closeDD() {
    const dd = this.querySelector("#aw-dropdown");
    if (dd) dd.style.display = "none";
    this._highlightIdx = -1;
  }

  _moveHL(dir, items) {
    if (!items || !items.length) return;
    this._highlightIdx += dir;
    if (this._highlightIdx < 0) this._highlightIdx = items.length - 1;
    if (this._highlightIdx >= items.length) this._highlightIdx = 0;
    items.forEach((el, i) => el.classList.toggle("hl", i === this._highlightIdx));
    // update input with highlighted value
    if (items[this._highlightIdx]) {
      const input = this.querySelector("#aw-input");
      input.value = items[this._highlightIdx].dataset.domain;
    }
  }

  /* ── Actions ── */
  _addSite() {
    if (!this._hass || !this._newDomain) return;
    let domain = this._newDomain
      .trim()
      .toLowerCase()
      .replace(/^https?:\/\//, "")
      .replace(/\/.*$/, "");
    if (!domain) return;
    this._hass.callService("adguard_whitelist", "add_site", { domain });
    this._newDomain = "";
    const input = this.querySelector("#aw-input");
    if (input) input.value = "";
    this._closeDD();
  }

  _removeSite(domain) {
    if (!this._hass) return;
    this._hass.callService("adguard_whitelist", "remove_site", { domain });
  }

  /* ── Partial DOM updates (no full re-render) ── */
  _updateHeader() {
    const el = this.querySelector("#aw-title");
    if (el) el.textContent = this.config.title || "Sites Autorisés";
    const st = this.querySelector("#aw-status");
    if (st) st.innerHTML = `AdGuard Home &middot; ${this.config.client_ip}`;
  }

  _updateData(sensor) {
    const count = sensor ? sensor.state : "?";
    const totalRules = sensor ? (sensor.attributes.total_rules || 0) : 0;
    const pendingSsh = sensor ? (sensor.attributes.pending_ssh || 0) : 0;

    const ce = this.querySelector("#aw-count");
    const re = this.querySelector("#aw-rules");
    if (ce) ce.textContent = count;
    if (re) re.textContent = totalRules;

    const st = this.querySelector("#aw-status");
    if (st) {
      st.innerHTML =
        `AdGuard Home &middot; ${this.config.client_ip}` +
        (pendingSsh > 0
          ? ` <span class="aw-pending-badge">${pendingSsh} synchro en attente</span>`
          : "");
    }

    this._updateSites(sensor);
  }

  _updateSites(sensor) {
    const container = this.querySelector("#aw-sites");
    if (!container) return;

    const showCdn = this.config.show_cdn !== false;

    const cats = {};
    if (sensor) {
      const a = sensor.attributes;
      const ed = a["category_éducation"] || a["category_\u00e9ducation"] || [];
      const pr = a.category_programmation || [];
      const cdn = a.category_cdn_technique || [];
      const other = a.category_autre || [];
      if (ed.length) cats["Éducation"] = ed;
      if (pr.length) cats["Programmation"] = pr;
      if (cdn.length && showCdn) cats["CDN / Technique"] = cdn;
      if (other.length) cats["Autre"] = other;
    }

    const catMeta = {
      "Éducation":      { icon: "mdi:school",         color: "var(--info-color, #2196f3)" },
      "Programmation":  { icon: "mdi:code-braces",     color: "var(--success-color, #4caf50)" },
      "CDN / Technique":{ icon: "mdi:server-network",  color: "var(--secondary-text-color)" },
      "Autre":          { icon: "mdi:web",             color: "var(--warning-color, #ff9800)" },
    };

    let html = "";
    for (const [name, domains] of Object.entries(cats)) {
      const m = catMeta[name] || { icon: "mdi:web", color: "var(--primary-text-color)" };
      html += `<div class="aw-cat">
        <div class="aw-cat-hdr">
          <ha-icon icon="${m.icon}" style="--mdc-icon-size:14px;color:${m.color}"></ha-icon>
          <span style="color:${m.color}">${name}</span>
          <span class="aw-cat-cnt">${domains.length}</span>
        </div>`;
      for (const d of domains) {
        html += `<div class="aw-site">
          <span class="aw-site-name">${d}</span>
          <div class="aw-site-rm" data-remove="${d}" title="Supprimer ${d}">
            <ha-icon icon="mdi:close-circle-outline" style="--mdc-icon-size:18px"></ha-icon>
          </div>
        </div>`;
      }
      html += `</div>`;
    }

    if (!html) {
      html = `<div class="aw-empty">Aucun site autorisé</div>`;
    }

    container.innerHTML = html;
  }

  getCardSize() {
    return 6;
  }

  /* ── CSS ── */
  static _css() {
    return `
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
        color: white; font-size: 20px;
      }
      .aw-header-info { flex: 1; }
      .aw-header-title { font-size: 16px; font-weight: 500; }
      .aw-header-status { font-size: 12px; color: var(--secondary-text-color); }
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

      /* ── Add form ── */
      .aw-add-form { display: flex; gap: 8px; margin-bottom: 16px; }
      .aw-input-wrapper { position: relative; flex: 1; }
      .aw-add-input {
        width: 100%; padding: 10px 12px; box-sizing: border-box;
        border: 1px solid var(--divider-color); border-radius: 8px;
        background: var(--card-background-color, var(--ha-card-background));
        color: var(--primary-text-color); font-size: 14px; outline: none;
      }
      .aw-add-input:focus { border-color: var(--primary-color); }
      .aw-add-input::placeholder { color: var(--secondary-text-color); }
      .aw-add-btn {
        padding: 10px 16px; border: none; border-radius: 8px;
        background: var(--primary-color); color: white;
        font-size: 14px; font-weight: 500; cursor: pointer;
        display: flex; align-items: center; gap: 4px;
        white-space: nowrap;
      }
      .aw-add-btn:hover { opacity: 0.9; }
      .aw-add-btn:active { opacity: 0.7; }

      /* ── Autocomplete dropdown ── */
      .aw-dropdown {
        display: none; position: absolute; top: 100%; left: 0; right: 0;
        background: var(--card-background-color, var(--ha-card-background));
        border: 1px solid var(--divider-color);
        border-top: none; border-radius: 0 0 8px 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 100; max-height: 240px; overflow-y: auto;
      }
      .aw-sug {
        padding: 10px 12px; cursor: pointer;
        font-size: 13px; color: var(--primary-text-color);
        border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.05));
      }
      .aw-sug:last-child { border-bottom: none; }
      .aw-sug:hover, .aw-sug.hl {
        background: var(--primary-color); color: white;
      }
      .aw-sug strong { font-weight: 700; }

      /* ── Categories & sites ── */
      .aw-cat { margin-bottom: 12px; }
      .aw-cat-hdr {
        display: flex; align-items: center; gap: 6px;
        font-size: 12px; font-weight: 600; text-transform: uppercase;
        margin-bottom: 6px;
      }
      .aw-cat-cnt {
        background: var(--divider-color); border-radius: 10px;
        padding: 1px 6px; font-size: 10px;
      }
      .aw-site {
        display: flex; align-items: center; justify-content: space-between;
        padding: 6px 8px; border-radius: 8px; transition: background 0.15s;
      }
      .aw-site:hover {
        background: var(--secondary-background-color, rgba(0,0,0,0.04));
      }
      .aw-site-name { font-size: 13px; color: var(--primary-text-color); }
      .aw-site-rm {
        cursor: pointer; color: var(--error-color, #f44336);
        opacity: 0.3; transition: opacity 0.15s; display: flex; align-items: center;
      }
      .aw-site:hover .aw-site-rm { opacity: 1; }
      .aw-empty {
        text-align: center; color: var(--secondary-text-color); padding: 24px 16px;
        font-size: 14px;
      }
    `;
  }
}

/* ── Config editor ── */
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
      <div style="padding:16px;">
        <div style="margin-bottom:12px;">
          <label style="display:block;margin-bottom:4px;font-weight:500;">IP du client</label>
          <input type="text" id="client_ip" value="${this._config.client_ip || ""}"
            style="width:100%;padding:8px;border:1px solid var(--divider-color);border-radius:4px;box-sizing:border-box;"
            placeholder="192.168.8.50">
        </div>
        <div style="margin-bottom:12px;">
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
      </div>`;

    this.querySelector("#client_ip").addEventListener("input", (e) => {
      this._config = { ...this._config, client_ip: e.target.value };
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
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config } })
    );
  }
}

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
  "color:white;background:#4caf50;font-weight:bold;padding:2px 4px;border-radius:4px 0 0 4px;",
  "color:#4caf50;background:white;font-weight:bold;padding:2px 4px;border-radius:0 4px 4px 0;border:1px solid #4caf50;"
);
