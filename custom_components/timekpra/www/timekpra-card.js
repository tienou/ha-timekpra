const CARD_VERSION = "1.8.0";

class TimekpraCard extends HTMLElement {
  static get properties() {
    return { hass: {}, config: {} };
  }

  static getConfigElement() {
    return document.createElement("timekpra-card-editor");
  }

  static getStubConfig() {
    return { target_user: "camille" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config.target_user) {
      throw new Error("Veuillez définir target_user");
    }
    this.config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _prefix() {
    return `timekpra_${this.config.target_user}`;
  }

  _entity(domain, suffix) {
    return `${domain}.${this._prefix()}_${suffix}`;
  }

  _state(entityId) {
    if (!this._hass || !this._hass.states[entityId]) return null;
    return this._hass.states[entityId];
  }

  _stateValue(entityId) {
    const s = this._state(entityId);
    return s ? s.state : "indisponible";
  }

  _toggle(entityId) {
    const state = this._state(entityId);
    if (!state) return;
    this._hass.callService("switch", state.state === "on" ? "turn_off" : "turn_on", {
      entity_id: entityId,
    });
  }

  _setNumber(entityId, value) {
    this._hass.callService("number", "set_value", {
      entity_id: entityId,
      value: parseFloat(value),
    });
  }

  _adjustNumber(entityId, delta) {
    const state = this._state(entityId);
    if (!state) return;
    const current = parseFloat(state.state);
    if (isNaN(current)) return;
    const min = state.attributes.min || 0;
    const max = state.attributes.max || 1440;
    const step = state.attributes.step || 1;
    const newVal = Math.min(max, Math.max(min, current + delta));
    this._setNumber(entityId, newVal);
  }

  _setSelect(entityId, option) {
    this._hass.callService("select", "select_option", {
      entity_id: entityId,
      option: option,
    });
  }

  _fireEvent(entityId) {
    const event = new Event("hass-more-info", { bubbles: true, composed: true });
    event.detail = { entityId };
    this.dispatchEvent(event);
  }

  _saveProfile(name) {
    if (!name || !name.trim()) return;
    this._hass.callService("timekpra", "save_profile", { name: name.trim() });
  }

  _deleteProfile(name) {
    if (!name || name === "Personnalisé") return;
    this._hass.callService("timekpra", "delete_profile", { name });
  }

  _render() {
    if (!this.config || !this._hass) return;

    const p = this._prefix();
    const days = [
      { key: "lundi", label: "Lun" },
      { key: "mardi", label: "Mar" },
      { key: "mercredi", label: "Mer" },
      { key: "jeudi", label: "Jeu" },
      { key: "vendredi", label: "Ven" },
      { key: "samedi", label: "Sam" },
      { key: "dimanche", label: "Dim" },
    ];

    const online = this._stateValue(this._entity("sensor", "ordinateur"));
    const pending = this._stateValue(this._entity("sensor", "modifications_en_attente"));
    const timeToday = this._stateValue(this._entity("sensor", "temps_utilise_aujourd_hui"));
    const timeWeek = this._stateValue(this._entity("sensor", "temps_utilise_cette_semaine"));
    const isOnline = online === "En ligne";

    const hourStartEid = this._entity("number", "heure_de_debut");
    const minuteStartEid = this._entity("number", "minute_de_debut");
    const hourEndEid = this._entity("number", "heure_de_fin");
    const minuteEndEid = this._entity("number", "minute_de_fin");
    const hourStart = this._stateValue(hourStartEid);
    const minuteStart = this._stateValue(minuteStartEid);
    const hourEnd = this._stateValue(hourEndEid);
    const minuteEnd = this._stateValue(minuteEndEid);

    const dailyLimitActive = this._stateValue(this._entity("switch", "limites_quotidiennes_actives")) === "on";
    const weeklyLimitActive = this._stateValue(this._entity("switch", "limite_hebdomadaire_active")) === "on";
    const monthlyLimitActive = this._stateValue(this._entity("switch", "limite_mensuelle_active")) === "on";
    const weeklyLimitEid = this._entity("number", "limite_hebdomadaire");
    const monthlyLimitEid = this._entity("number", "limite_mensuelle");
    const weeklyLimit = this._stateValue(weeklyLimitEid);
    const monthlyLimit = this._stateValue(monthlyLimitEid);

    const overrideActive = this._stateValue(this._entity("switch", "deblocage_temporaire")) === "on";

    const lockoutType = this._stateValue(this._entity("select", "action_fin_de_temps"));
    const trackInactive = this._stateValue(this._entity("switch", "compter_le_temps_inactif")) === "on";

    // Profile
    const profileSelectEid = this._entity("select", "profil");
    const profileState = this._state(profileSelectEid);
    const activeProfile = profileState ? profileState.state : "Personnalisé";
    const profileOptions = profileState && profileState.attributes.options ? profileState.attributes.options : ["Personnalisé"];
    const isCustomProfile = activeProfile === "Personnalisé";
    const isOverrideProfile = activeProfile === "Déblocage temporaire";
    const builtInProfiles = ["Personnalisé", "Déblocage temporaire", "École", "Vacances", "Chez Papi Mamie"];
    const isBuiltIn = builtInProfiles.includes(activeProfile);
    const canDelete = !isBuiltIn;
    const canSave = !isOverrideProfile;

    const timeRemaining = this._stateValue(this._entity("sensor", "temps_restant_aujourd_hui"));
    const notifThresholdEid = this._entity("number", "notification_avant_verrouillage");
    const notifThreshold = this._stateValue(notifThresholdEid);

    const user = this.config.target_user;
    const title = this.config.title || `Contrôle Parental - ${user.charAt(0).toUpperCase() + user.slice(1)}`;

    // Build day toggles
    let dayTogglesHtml = days.map((d) => {
      const eid = this._entity("switch", `jour_autorise_${d.key}`);
      const isOn = this._stateValue(eid) === "on";
      return `<div class="day-chip ${isOn ? "active" : ""}" data-toggle="${eid}">${d.label}</div>`;
    }).join("");

    // Build daily limits with +/- controls
    let dailyLimitsHtml = "";
    if (dailyLimitActive) {
      dailyLimitsHtml = days.map((d) => {
        const eid = this._entity("number", `limite_${d.key}`);
        const val = this._stateValue(eid);
        const numVal = parseInt(val);
        const displayVal = val === "indisponible" ? "-" : (numVal >= 1440 ? "Illimité" : `${val} min`);
        return `<div class="limit-row">
          <span class="limit-label">${d.label}</span>
          <div class="limit-controls">
            <button class="tkp-btn" data-adjust="${eid}" data-delta="-15">-</button>
            <span class="limit-value" data-more-info="${eid}">${displayVal}</span>
            <button class="tkp-btn" data-adjust="${eid}" data-delta="15">+</button>
          </div>
        </div>`;
      }).join("");
    }

    // Lockout options
    const lockoutOptions = ["lock", "suspend", "shutdown"];
    const lockoutLabels = { lock: "Verrouiller", suspend: "Suspendre", shutdown: "Éteindre" };
    const lockoutSelectId = this._entity("select", "action_fin_de_temps");
    const lockoutOptionsHtml = lockoutOptions.map((opt) =>
      `<option value="${opt}" ${lockoutType === opt ? "selected" : ""}>${lockoutLabels[opt] || opt}</option>`
    ).join("");

    // Format time
    const formatTime = (val) => {
      if (val === "indisponible" || val === null || val === "None") return "-";
      const n = parseInt(val);
      if (isNaN(n)) return val;
      const h = Math.floor(n / 60);
      const m = n % 60;
      return h > 0 ? `${h}h${m.toString().padStart(2, "0")}` : `${m}min`;
    };

    this.shadowRoot.innerHTML = `
      <ha-card>
        <style>
          .tkp-card { padding: 16px; }
          .tkp-header {
            display: flex; align-items: center; gap: 12px;
            margin-bottom: 16px; padding-bottom: 12px;
            border-bottom: 1px solid var(--divider-color);
          }
          .tkp-header-icon {
            width: 40px; height: 40px; border-radius: 50%;
            background: ${isOnline ? "var(--success-color, #4caf50)" : "var(--error-color, #f44336)"};
            display: flex; align-items: center; justify-content: center;
            color: white; font-size: 20px;
          }
          .tkp-header-info { flex: 1; }
          .tkp-header-title { font-size: 16px; font-weight: 500; }
          .tkp-header-status {
            font-size: 12px;
            color: ${isOnline ? "var(--success-color, #4caf50)" : "var(--secondary-text-color)"};
          }
          .tkp-section { margin-bottom: 16px; }
          .tkp-section-title {
            font-size: 13px; font-weight: 500; text-transform: uppercase;
            color: var(--secondary-text-color); margin-bottom: 8px;
            display: flex; align-items: center; gap: 6px;
          }
          .tkp-stats {
            display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;
            margin-bottom: 16px;
          }
          .tkp-stat {
            background: var(--card-background-color, var(--ha-card-background));
            border: 1px solid var(--divider-color);
            border-radius: 12px; padding: 12px; text-align: center;
            cursor: pointer;
          }
          .tkp-stat:hover { border-color: var(--primary-color); }
          .tkp-stat-value { font-size: 20px; font-weight: 600; }
          .tkp-stat-label { font-size: 11px; color: var(--secondary-text-color); }
          .day-chips {
            display: flex; gap: 4px; flex-wrap: wrap; justify-content: center;
          }
          .day-chip {
            padding: 6px 10px; border-radius: 16px; font-size: 12px; font-weight: 500;
            cursor: pointer; user-select: none; transition: all 0.2s;
            background: var(--disabled-color, #e0e0e0); color: var(--secondary-text-color);
          }
          .day-chip.active { background: var(--primary-color); color: white; }
          .day-chip:hover { opacity: 0.8; }
          .tkp-row {
            display: flex; align-items: center; justify-content: space-between;
            padding: 8px 0; border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.06));
          }
          .tkp-row:last-child { border-bottom: none; }
          .tkp-row-label { font-size: 14px; }
          .tkp-row-value { font-size: 14px; font-weight: 500; }
          .tkp-row-controls {
            display: flex; align-items: center; gap: 8px;
          }
          .tkp-btn {
            width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--divider-color);
            background: var(--card-background-color, var(--ha-card-background));
            color: var(--primary-text-color); font-size: 16px; font-weight: 600;
            cursor: pointer; display: flex; align-items: center; justify-content: center;
            transition: all 0.15s; padding: 0; line-height: 1;
          }
          .tkp-btn:hover { background: var(--primary-color); color: white; border-color: var(--primary-color); }
          .tkp-btn:active { transform: scale(0.9); }
          .limit-row {
            display: flex; justify-content: space-between; align-items: center;
            padding: 4px 0; font-size: 13px;
          }
          .limit-controls {
            display: flex; align-items: center; gap: 6px;
          }
          .limit-label { color: var(--primary-text-color); }
          .limit-value { font-weight: 500; min-width: 55px; text-align: center; cursor: pointer; }
          .limit-value:hover { color: var(--primary-color); }
          .tkp-toggle {
            display: flex; align-items: center; justify-content: space-between;
            padding: 8px 0; cursor: pointer;
          }
          .tkp-toggle-label { font-size: 14px; }
          .tkp-toggle-switch {
            width: 36px; height: 20px; border-radius: 10px; position: relative;
            transition: background 0.2s; cursor: pointer;
          }
          .tkp-toggle-switch.on { background: var(--primary-color); }
          .tkp-toggle-switch.off { background: var(--disabled-color, #ccc); }
          .tkp-toggle-switch::after {
            content: ""; position: absolute; top: 2px;
            width: 16px; height: 16px; border-radius: 50%; background: white;
            transition: left 0.2s;
          }
          .tkp-toggle-switch.on::after { left: 18px; }
          .tkp-toggle-switch.off::after { left: 2px; }
          .tkp-pending-badge {
            background: var(--warning-color, #ff9800); color: white;
            border-radius: 10px; padding: 2px 8px; font-size: 11px;
          }
          .tkp-header-badges {
            display: flex; gap: 12px; margin-top: 2px;
          }
          .tkp-service-badge {
            font-size: 12px; font-weight: 500;
            color: var(--primary-text-color);
            display: flex; align-items: center; gap: 4px;
          }
          .tkp-service-badge::before {
            content: ""; display: inline-block;
            width: 8px; height: 8px; border-radius: 50%;
            background: var(--success-color, #4caf50);
          }
          .tkp-service-badge.offline::before {
            background: var(--disabled-color, #bdbdbd);
          }
          .tkp-time-row {
            display: flex; align-items: center; justify-content: space-between;
            padding: 8px 0; border-bottom: 1px solid var(--divider-color, rgba(0,0,0,0.06));
          }
          .tkp-time-row:last-child { border-bottom: none; }
          .tkp-time-controls {
            display: flex; align-items: center; gap: 4px;
          }
          .tkp-time-group {
            display: flex; align-items: center; gap: 4px;
          }
          .tkp-time-value {
            font-size: 16px; font-weight: 600; min-width: 28px; text-align: center;
          }
          .tkp-time-colon {
            font-size: 16px; font-weight: 600; padding: 0 2px;
          }
          .tkp-select {
            background: var(--card-background-color, var(--ha-card-background));
            border: 1px solid var(--divider-color); border-radius: 8px;
            padding: 6px 10px; font-size: 13px; color: var(--primary-text-color);
            cursor: pointer; outline: none;
          }
          .tkp-select:hover { border-color: var(--primary-color); }
          .tkp-override {
            display: flex; align-items: center; gap: 10px;
            padding: 10px 12px; margin-bottom: 16px;
            border-radius: 12px; cursor: pointer; user-select: none;
            transition: all 0.2s;
          }
          .tkp-override.active {
            background: rgba(255, 152, 0, 0.12);
            border: 1px solid var(--warning-color, #ff9800);
          }
          .tkp-override.inactive {
            background: var(--card-background-color, var(--ha-card-background));
            border: 1px solid var(--divider-color);
          }
          .tkp-override:hover { opacity: 0.85; }
          .tkp-override-checkbox {
            width: 20px; height: 20px; border-radius: 4px;
            border: 2px solid var(--divider-color); display: flex;
            align-items: center; justify-content: center;
            transition: all 0.2s; flex-shrink: 0;
          }
          .tkp-override.active .tkp-override-checkbox {
            background: var(--warning-color, #ff9800);
            border-color: var(--warning-color, #ff9800);
          }
          .tkp-override-checkbox ha-icon {
            --mdc-icon-size: 14px; color: white;
          }
          .tkp-override-label { font-size: 14px; font-weight: 500; }
          .tkp-override-desc {
            font-size: 11px; color: var(--secondary-text-color);
          }
          .tkp-override.active .tkp-override-label {
            color: var(--warning-color, #ff9800);
          }
          .tkp-profile-section {
            margin-bottom: 16px; padding: 12px;
            background: var(--card-background-color, var(--ha-card-background));
            border: 1px solid var(--divider-color); border-radius: 12px;
          }
          .tkp-profile-row {
            display: flex; align-items: center; gap: 8px;
          }
          .tkp-profile-row .tkp-select { flex: 1; }
          .tkp-profile-actions {
            display: flex; align-items: center; gap: 6px; margin-top: 8px;
          }
          .tkp-profile-actions input {
            flex: 1; padding: 6px 10px; border: 1px solid var(--divider-color);
            border-radius: 8px; font-size: 13px; background: transparent;
            color: var(--primary-text-color); outline: none;
          }
          .tkp-profile-actions input:focus { border-color: var(--primary-color); }
          .tkp-profile-actions input::placeholder { color: var(--secondary-text-color); }
          .tkp-icon-btn {
            width: 32px; height: 32px; border-radius: 50%; border: 1px solid var(--divider-color);
            background: var(--card-background-color, var(--ha-card-background));
            color: var(--primary-text-color); cursor: pointer;
            display: flex; align-items: center; justify-content: center;
            transition: all 0.15s; padding: 0; flex-shrink: 0;
          }
          .tkp-icon-btn:hover { background: var(--primary-color); color: white; border-color: var(--primary-color); }
          .tkp-icon-btn.danger:hover { background: var(--error-color, #f44336); border-color: var(--error-color, #f44336); }
          .tkp-icon-btn:active { transform: scale(0.9); }
        </style>

        <div class="tkp-card">
          <!-- Header -->
          <div class="tkp-header">
            <div class="tkp-header-icon">
              <ha-icon icon="${isOnline ? "mdi:desktop-classic" : "mdi:desktop-classic-off"}"></ha-icon>
            </div>
            <div class="tkp-header-info">
              <div class="tkp-header-title">${title}</div>
              <div class="tkp-header-status">
                ${isOnline ? "En ligne" : "Hors ligne"}
                ${parseInt(pending) > 0 ? `<span class="tkp-pending-badge">${pending} en attente</span>` : ""}
              </div>
              <div class="tkp-header-badges">
                <span class="tkp-service-badge${isOnline ? "" : " offline"}">Timekpr-nExT</span>
              </div>
            </div>
          </div>

          <!-- Override -->
          <div class="tkp-override ${overrideActive ? "active" : "inactive"}" data-toggle="${this._entity("switch", "deblocage_temporaire")}">
            <div class="tkp-override-checkbox">
              ${overrideActive ? '<ha-icon icon="mdi:check"></ha-icon>' : ""}
            </div>
            <div>
              <div class="tkp-override-label">${overrideActive ? "Déblocage actif" : "Déblocage temporaire"}</div>
              <div class="tkp-override-desc">${overrideActive ? "Toutes les restrictions sont ignorées" : "Cocher pour ignorer toutes les restrictions"}</div>
            </div>
          </div>

          <!-- Profile -->
          <div class="tkp-profile-section">
            <div class="tkp-section-title" style="margin-bottom: 10px">
              <ha-icon icon="mdi:account-switch" style="--mdc-icon-size:16px"></ha-icon> Profil
            </div>
            <div class="tkp-profile-row">
              <select class="tkp-select" id="tkp-profile-select" data-select="${profileSelectEid}">
                ${profileOptions.map((opt) =>
                  `<option value="${opt}" ${activeProfile === opt ? "selected" : ""}>${opt}</option>`
                ).join("")}
              </select>
              ${canDelete ? `<button class="tkp-icon-btn danger" id="tkp-profile-delete" title="Supprimer ce profil">
                <ha-icon icon="mdi:delete" style="--mdc-icon-size:16px"></ha-icon>
              </button>` : ""}
            </div>
            ${canSave ? `<div class="tkp-profile-actions">
              <input type="text" id="tkp-profile-name" placeholder="Nom du profil..." value="${isCustomProfile ? "" : activeProfile}">
              <button class="tkp-icon-btn" id="tkp-profile-save" title="Sauvegarder les réglages actuels">
                <ha-icon icon="mdi:content-save" style="--mdc-icon-size:16px"></ha-icon>
              </button>
            </div>` : ""}
          </div>

          <!-- Stats -->
          <div class="tkp-stats">
            <div class="tkp-stat" data-more-info="${this._entity("sensor", "temps_utilise_aujourd_hui")}">
              <div class="tkp-stat-value">${formatTime(timeToday)}</div>
              <div class="tkp-stat-label">Aujourd'hui</div>
            </div>
            <div class="tkp-stat" data-more-info="${this._entity("sensor", "temps_utilise_cette_semaine")}">
              <div class="tkp-stat-value">${formatTime(timeWeek)}</div>
              <div class="tkp-stat-label">Cette semaine</div>
            </div>
            <div class="tkp-stat" data-more-info="${this._entity("sensor", "temps_restant_aujourd_hui")}">
              <div class="tkp-stat-value" style="${timeRemaining !== "indisponible" && parseInt(timeRemaining) <= parseInt(notifThreshold || 15) ? "color: var(--error-color, #f44336)" : ""}">${formatTime(timeRemaining)}</div>
              <div class="tkp-stat-label">Restant</div>
            </div>
          </div>

          <!-- Days -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:calendar" style="--mdc-icon-size:16px"></ha-icon> Jours autorisés</div>
            <div class="day-chips">${dayTogglesHtml}</div>
          </div>

          <!-- Hours -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:clock-outline" style="--mdc-icon-size:16px"></ha-icon> Plage horaire</div>
            <div class="tkp-time-row">
              <span class="tkp-row-label">Début</span>
              <div class="tkp-time-controls">
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${hourStartEid}" data-delta="-1">-</button>
                  <span class="tkp-time-value">${hourStart !== "indisponible" ? hourStart : "-"}</span>
                  <button class="tkp-btn" data-adjust="${hourStartEid}" data-delta="1">+</button>
                </div>
                <span class="tkp-time-colon">:</span>
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${minuteStartEid}" data-delta="-5">-</button>
                  <span class="tkp-time-value">${minuteStart !== "indisponible" ? minuteStart.toString().padStart(2, "0") : "00"}</span>
                  <button class="tkp-btn" data-adjust="${minuteStartEid}" data-delta="5">+</button>
                </div>
              </div>
            </div>
            <div class="tkp-time-row">
              <span class="tkp-row-label">Fin</span>
              <div class="tkp-time-controls">
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${hourEndEid}" data-delta="-1">-</button>
                  <span class="tkp-time-value">${hourEnd !== "indisponible" ? hourEnd : "-"}</span>
                  <button class="tkp-btn" data-adjust="${hourEndEid}" data-delta="1">+</button>
                </div>
                <span class="tkp-time-colon">:</span>
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${minuteEndEid}" data-delta="-5">-</button>
                  <span class="tkp-time-value">${minuteEnd !== "indisponible" ? minuteEnd.toString().padStart(2, "0") : "59"}</span>
                  <button class="tkp-btn" data-adjust="${minuteEndEid}" data-delta="5">+</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Daily limits -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:timer-outline" style="--mdc-icon-size:16px"></ha-icon> Limites quotidiennes</div>
            <div class="tkp-toggle" data-toggle="${this._entity("switch", "limites_quotidiennes_actives")}">
              <span class="tkp-toggle-label">Activer</span>
              <div class="tkp-toggle-switch ${dailyLimitActive ? "on" : "off"}"></div>
            </div>
            ${dailyLimitsHtml}
          </div>

          <!-- Weekly / Monthly limits -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:calendar-clock" style="--mdc-icon-size:16px"></ha-icon> Limites globales</div>
            <div class="tkp-toggle" data-toggle="${this._entity("switch", "limite_hebdomadaire_active")}">
              <span class="tkp-toggle-label">Limite hebdomadaire</span>
              <div class="tkp-toggle-switch ${weeklyLimitActive ? "on" : "off"}"></div>
            </div>
            ${weeklyLimitActive ? `<div class="limit-row">
              <span class="limit-label">Hebdomadaire</span>
              <div class="limit-controls">
                <button class="tkp-btn" data-adjust="${weeklyLimitEid}" data-delta="-1">-</button>
                <span class="limit-value" data-more-info="${weeklyLimitEid}">${parseInt(weeklyLimit) >= 168 ? "Illimité" : weeklyLimit + "h"}</span>
                <button class="tkp-btn" data-adjust="${weeklyLimitEid}" data-delta="1">+</button>
              </div>
            </div>` : ""}
            <div class="tkp-toggle" data-toggle="${this._entity("switch", "limite_mensuelle_active")}">
              <span class="tkp-toggle-label">Limite mensuelle</span>
              <div class="tkp-toggle-switch ${monthlyLimitActive ? "on" : "off"}"></div>
            </div>
            ${monthlyLimitActive ? `<div class="limit-row">
              <span class="limit-label">Mensuelle</span>
              <div class="limit-controls">
                <button class="tkp-btn" data-adjust="${monthlyLimitEid}" data-delta="-1">-</button>
                <span class="limit-value" data-more-info="${monthlyLimitEid}">${parseInt(monthlyLimit) >= 744 ? "Illimité" : monthlyLimit + "h"}</span>
                <button class="tkp-btn" data-adjust="${monthlyLimitEid}" data-delta="1">+</button>
              </div>
            </div>` : ""}
          </div>

          <!-- Settings -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:cog" style="--mdc-icon-size:16px"></ha-icon> Réglages</div>
            <div class="tkp-row">
              <span class="tkp-row-label">Action fin de temps</span>
              <select class="tkp-select" data-select="${lockoutSelectId}">
                ${lockoutOptionsHtml}
              </select>
            </div>
            <div class="tkp-toggle" data-toggle="${this._entity("switch", "compter_le_temps_inactif")}">
              <span class="tkp-toggle-label">Compter le temps inactif</span>
              <div class="tkp-toggle-switch ${trackInactive ? "on" : "off"}"></div>
            </div>
            <div class="tkp-row">
              <span class="tkp-row-label">Alerte avant fin</span>
              <div class="tkp-row-controls">
                <button class="tkp-btn" data-adjust="${notifThresholdEid}" data-delta="-5">-</button>
                <span class="tkp-row-value" data-more-info="${notifThresholdEid}">${notifThreshold !== "indisponible" ? (parseInt(notifThreshold) === 0 ? "Off" : notifThreshold + " min") : "-"}</span>
                <button class="tkp-btn" data-adjust="${notifThresholdEid}" data-delta="5">+</button>
              </div>
            </div>
          </div>
        </div>
      </ha-card>
    `;

    // Bind toggle events
    this.shadowRoot.querySelectorAll("[data-toggle]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        this._toggle(el.dataset.toggle);
      });
    });

    // Bind +/- buttons
    this.shadowRoot.querySelectorAll("[data-adjust]").forEach((el) => {
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        this._adjustNumber(el.dataset.adjust, parseInt(el.dataset.delta));
      });
    });

    // Bind more-info clicks
    this.shadowRoot.querySelectorAll("[data-more-info]").forEach((el) => {
      el.style.cursor = "pointer";
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        this._fireEvent(el.dataset.moreInfo);
      });
    });

    // Bind select dropdowns
    this.shadowRoot.querySelectorAll("[data-select]").forEach((el) => {
      el.addEventListener("change", (e) => {
        e.stopPropagation();
        this._setSelect(el.dataset.select, e.target.value);
      });
    });

    // Bind profile save
    const saveBtn = this.shadowRoot.querySelector("#tkp-profile-save");
    if (saveBtn) {
      saveBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const input = this.shadowRoot.querySelector("#tkp-profile-name");
        if (input && input.value.trim()) {
          this._saveProfile(input.value.trim());
        }
      });
    }

    // Bind profile delete
    const deleteBtn = this.shadowRoot.querySelector("#tkp-profile-delete");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._deleteProfile(activeProfile);
      });
    }
  }

  getCardSize() {
    return 8;
  }
}

// ── Config editor ──────────────────────────────────────────────────

class TimekpraCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <div style="padding: 16px;">
        <div style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">
            Utilisateur cible (login de l'enfant)
          </label>
          <input type="text" id="target_user"
            value="${this._config.target_user || ""}"
            style="width: 100%; padding: 8px; border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box;"
            placeholder="camille">
        </div>
        <div>
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">
            Titre (optionnel)
          </label>
          <input type="text" id="title"
            value="${this._config.title || ""}"
            style="width: 100%; padding: 8px; border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box;"
            placeholder="Contrôle Parental - Camille">
        </div>
      </div>
    `;

    this.shadowRoot.querySelector("#target_user").addEventListener("input", (e) => {
      this._config = { ...this._config, target_user: e.target.value };
      this._dispatch();
    });

    this.shadowRoot.querySelector("#title").addEventListener("input", (e) => {
      this._config = { ...this._config, title: e.target.value };
      this._dispatch();
    });
  }

  _dispatch() {
    this.dispatchEvent(
      new CustomEvent("config-changed", { detail: { config: this._config } })
    );
  }
}

/* Guard against double-load on Android WebView */
if (!customElements.get("timekpra-card")) {
  customElements.define("timekpra-card", TimekpraCard);
}
if (!customElements.get("timekpra-card-editor")) {
  customElements.define("timekpra-card-editor", TimekpraCardEditor);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "timekpra-card")) {
  window.customCards.push({
    type: "timekpra-card",
    name: "Timekpra - Contrôle Parental",
    description: "Carte de gestion du contrôle parental Timekpr-nExT",
    preview: true,
    documentationURL: "https://github.com/tienou/ha-timekpra",
  });
}

console.info(
  `%c TIMEKPRA-CARD %c v${CARD_VERSION} `,
  "color: white; background: #2962ff; font-weight: bold; padding: 2px 4px; border-radius: 4px 0 0 4px;",
  "color: #2962ff; background: white; font-weight: bold; padding: 2px 4px; border-radius: 0 4px 4px 0; border: 1px solid #2962ff;"
);
