const CARD_VERSION = "1.25.0";

const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
);

// Card-chrome strings (text not covered by the integration's entity
// translations). Entity names/states, lockout and profile labels are reused
// from the integration translations via hass.localize / formatEntityState.
const STRINGS = {
  en: {
    profile: "Profile", today: "Today", this_week: "This week", remaining: "Remaining",
    allowed_days: "Allowed days", time_range: "Time range", start: "Start", end: "End",
    daily_limits: "Daily limits", enable: "Enable", global_limits: "Global limits",
    weekly_limit: "Weekly limit", weekly: "Weekly", monthly_limit: "Monthly limit", monthly: "Monthly",
    settings: "Settings", action_when_time_runs_out: "Action when time runs out",
    count_idle_time: "Count idle time", alert_before_end: "Alert before end",
    unlimited: "Unlimited", off: "Off", pending: "pending", online: "Online", offline: "Offline",
    new_profile_placeholder: "New profile name...", create: "Create", cancel: "Cancel",
    update_profile_title: "Update this profile", delete_profile_title: "Delete this profile",
    create_profile_title: "Create a new profile", confirm_delete: 'Delete profile "%s"?',
    target_user_label: "Target user (child's login)", title_label: "Title (optional)",
    define_target_user: "Please define target_user", default_title: "Parental Control",
  },
  de: {
    profile: "Profil", today: "Heute", this_week: "Diese Woche", remaining: "Verbleibend",
    allowed_days: "Erlaubte Tage", time_range: "Zeitspanne", start: "Start", end: "Ende",
    daily_limits: "Tägliche Limits", enable: "Aktivieren", global_limits: "Globale Limits",
    weekly_limit: "Wöchentliches Limit", weekly: "Wöchentlich", monthly_limit: "Monatliches Limit", monthly: "Monatlich",
    settings: "Einstellungen", action_when_time_runs_out: "Aktion bei Zeitablauf",
    count_idle_time: "Inaktive Zeit zählen", alert_before_end: "Hinweis vor Ablauf",
    unlimited: "Unbegrenzt", off: "Aus", pending: "ausstehend", online: "Online", offline: "Offline",
    new_profile_placeholder: "Name des neuen Profils...", create: "Erstellen", cancel: "Abbrechen",
    update_profile_title: "Dieses Profil aktualisieren", delete_profile_title: "Dieses Profil löschen",
    create_profile_title: "Neues Profil erstellen", confirm_delete: 'Profil „%s“ löschen?',
    target_user_label: "Zielbenutzer (Login des Kindes)", title_label: "Titel (optional)",
    define_target_user: "Bitte target_user angeben", default_title: "Kindersicherung",
  },
  fr: {
    profile: "Profil", today: "Aujourd'hui", this_week: "Cette semaine", remaining: "Restant",
    allowed_days: "Jours autorisés", time_range: "Plage horaire", start: "Début", end: "Fin",
    daily_limits: "Limites quotidiennes", enable: "Activer", global_limits: "Limites globales",
    weekly_limit: "Limite hebdomadaire", weekly: "Hebdomadaire", monthly_limit: "Limite mensuelle", monthly: "Mensuelle",
    settings: "Réglages", action_when_time_runs_out: "Action fin de temps",
    count_idle_time: "Compter le temps inactif", alert_before_end: "Alerte avant fin",
    unlimited: "Illimité", off: "Off", pending: "en attente", online: "En ligne", offline: "Hors ligne",
    new_profile_placeholder: "Nom du nouveau profil...", create: "Créer", cancel: "Annuler",
    update_profile_title: "Mettre à jour ce profil", delete_profile_title: "Supprimer ce profil",
    create_profile_title: "Créer un nouveau profil", confirm_delete: 'Supprimer le profil « %s » ?',
    target_user_label: "Utilisateur cible (login de l'enfant)", title_label: "Titre (optionnel)",
    define_target_user: "Veuillez définir target_user", default_title: "Contrôle Parental",
  },
};

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
    // Intercept events in CAPTURE phase on the host element so HA
    // cannot steal focus from inputs and selects inside the card
    const stop = (e) => {
      const path = e.composedPath();
      if (path.some((el) => el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "TEXTAREA")) {
        e.stopPropagation();
      }
    };
    for (const evt of ["pointerdown", "mousedown", "touchstart", "keydown", "keyup", "keypress", "click", "focusin"]) {
      this.addEventListener(evt, stop, true);
    }
    // Values chosen with +/- but not sent yet (debounced), per entity.
    this._pendingVals = {};
    this._timers = {};
    // Updates skipped while a field had the focus are applied when it leaves.
    this.shadowRoot.addEventListener("focusout", () => {
      if (!this._dirty) return;
      this._dirty = false;
      setTimeout(() => this._render(), 0);
    });
  }

  setConfig(config) {
    if (!config.target_user) {
      throw new Error(this._t("define_target_user"));
    }
    this.config = config;
    this._render();
  }

  set hass(hass) {
    const oldHass = this._hass;
    this._hass = hass;
    // Skip re-render while a field of the card has the focus (typing a
    // profile name, or a drop-down open: re-rendering closed it). The skipped
    // update is applied on focusout.
    const active = this.shadowRoot && this.shadowRoot.activeElement;
    if (active && (active.tagName === "INPUT" || active.tagName === "SELECT")) {
      this._dirty = true;
      return;
    }
    // Skip re-render if relevant entity states haven't changed. The card's
    // entities come from the registry lookup (not an entity_id prefix, which
    // missed users like "jean-paul" and renamed entities); a registry or
    // language change also re-renders.
    if (oldHass && this.config) {
      const registryChanged = hass.entities !== oldHass.entities ||
        hass.devices !== oldHass.devices || hass.language !== oldHass.language;
      const eids = Object.values(this._buildLookup());
      const changed = registryChanged ||
        eids.some((eid) => hass.states[eid] !== oldHass.states[eid]);
      if (!changed) return;
    }
    this._render();
  }

  // Resolve translation_key -> entity_id via the entity registry, scoped to
  // this target_user's device. Avoids guessing entity_ids from (translated)
  // names, which differ per language and per install.
  _buildLookup() {
    const map = {};
    if (!this._hass || !this._hass.entities || !this._hass.devices) return map;
    const user = String(this.config.target_user);
    const findDevice = (match) => Object.keys(this._hass.devices).find((did) => {
      const d = this._hass.devices[did];
      return d.identifiers && d.identifiers.some((ident) => ident[0] === "timekpra" && match(String(ident[1])));
    });
    const deviceId = findDevice((u) => u === user) ||
      findDevice((u) => u.toLowerCase() === user.toLowerCase());
    // Unknown target_user: show nothing rather than another child's entities
    // (without a device every timekpra entity matched, last one winning).
    if (!deviceId) return map;
    for (const eid in this._hass.entities) {
      const e = this._hass.entities[eid];
      if (e.platform !== "timekpra" || !e.translation_key) continue;
      if (e.device_id !== deviceId) continue;
      map[e.translation_key] = eid;
    }
    return map;
  }

  _state(entityId) {
    if (!entityId || !this._hass || !this._hass.states[entityId]) return null;
    return this._hass.states[entityId];
  }

  _stateValue(entityId) {
    if (entityId && entityId in this._pendingVals) {
      return String(this._pendingVals[entityId]);
    }
    const s = this._state(entityId);
    return s && s.state !== "unknown" ? s.state : "unavailable";
  }

  _notify(err) {
    // Service errors (e.g. "start must be before end") are not shown by HA
    // for a custom card: show them as a toast instead of failing silently.
    const message = (err && (err.message || err.error || err.code)) || String(err);
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message }, bubbles: true, composed: true,
    }));
  }

  _t(key) {
    const lang = ((this._hass && this._hass.language) || "en").split("-")[0];
    return (STRINGS[lang] && STRINGS[lang][key]) ?? STRINGS.en[key] ?? key;
  }

  // Reuse the integration's select state translations (entity.select.<key>.state).
  // Falls back to the raw value (e.g. user-created profiles not in translations).
  _localizeOption(selectKey, value) {
    if (!this._hass || !value) return value;
    const s = this._hass.localize(`component.timekpra.entity.select.${selectKey}.state.${value}`);
    return s || value;
  }

  _toggle(entityId) {
    const state = this._state(entityId);
    if (!state) return;
    this._hass.callService("switch", state.state === "on" ? "turn_off" : "turn_on", {
      entity_id: entityId,
    }).catch((err) => this._notify(err));
  }

  _setNumber(entityId, value) {
    return this._hass.callService("number", "set_value", {
      entity_id: entityId,
      value: parseFloat(value),
    });
  }

  // +/- : the value is shown at once and sent ONCE, 700 ms after the last
  // click. Each click used to send its own command to the computer (two
  // clicks = two SSH commands that could arrive in the wrong order), and two
  // fast clicks computed from the same state lost one step.
  _adjustNumber(entityId, delta) {
    const state = this._state(entityId);
    if (!state) return;
    const base = entityId in this._pendingVals
      ? this._pendingVals[entityId]
      : parseFloat(state.state);
    if (isNaN(base)) return;
    const min = Number(state.attributes.min ?? 0);
    const max = Number(state.attributes.max ?? 1440);
    let v = base + delta;
    const stepAbs = Math.abs(delta);
    // Snap to the button step (59 - 5 -> 55, not 54); the max stays reachable.
    if (stepAbs > 1 && v < max) v = Math.round(v / stepAbs) * stepAbs;
    v = Math.min(max, Math.max(min, v));
    if (v === base) return;
    this._pendingVals[entityId] = v;
    this._render();
    clearTimeout(this._timers[entityId]);
    this._timers[entityId] = setTimeout(() => {
      delete this._timers[entityId];
      const value = this._pendingVals[entityId];
      this._setNumber(entityId, value)
        .catch((err) => this._notify(err))
        .finally(() => {
          // Keep a newer pending value if more clicks happened meanwhile.
          if (this._pendingVals[entityId] === value && !this._timers[entityId]) {
            delete this._pendingVals[entityId];
          }
          this._render();
        });
    }, 700);
  }

  _setSelect(entityId, option) {
    this._hass.callService("select", "select_option", {
      entity_id: entityId,
      option: option,
    }).catch((err) => this._notify(err));
  }

  _fireEvent(entityId) {
    if (!entityId || entityId === "undefined") return;
    const event = new Event("hass-more-info", { bubbles: true, composed: true });
    event.detail = { entityId };
    this.dispatchEvent(event);
  }

  _saveProfile(name) {
    if (!name || !name.trim()) return;
    this._hass.callService("timekpra", "save_profile", { name: name.trim() }).then(() => {
      setTimeout(() => this._render(), 1000);
    }).catch((err) => this._notify(err));
  }

  _deleteProfile(name) {
    if (!name || name === "custom") return;
    this._hass.callService("timekpra", "delete_profile", { name }).then(() => {
      setTimeout(() => this._render(), 1000);
    }).catch((err) => this._notify(err));
  }

  _render() {
    if (!this.config || !this._hass) return;

    // Escape user-controlled strings (profile names, title) before inserting
    // them into innerHTML — prevents stored XSS via a crafted profile name.
    const esc = escapeHtml;

    const E = this._buildLookup();
    // Short weekday names in the HA language (2024-01-01 is a Monday).
    let dayFmt;
    try {
      dayFmt = new Intl.DateTimeFormat(this._hass.language || "en", { weekday: "short" });
    } catch (err) {
      dayFmt = new Intl.DateTimeFormat("en", { weekday: "short" });
    }
    const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
      .map((key, i) => ({ key, label: escapeHtml(dayFmt.format(new Date(2024, 0, 1 + i))) }));

    const online = this._stateValue(E.computer);
    const pending = this._stateValue(E.pending);
    const timeToday = this._stateValue(E.time_spent_today);
    const timeWeek = this._stateValue(E.time_spent_week);
    const isOnline = online === "online";
    const computerState = this._state(E.computer);
    const onlineLabel = computerState && this._hass.formatEntityState
      ? this._hass.formatEntityState(computerState)
      : this._t(isOnline ? "online" : "offline");

    const hourStartEid = E.hour_start;
    const minuteStartEid = E.minute_start;
    const hourEndEid = E.hour_end;
    const minuteEndEid = E.minute_end;
    const hourStart = this._stateValue(hourStartEid);
    const minuteStart = this._stateValue(minuteStartEid);
    const hourEnd = this._stateValue(hourEndEid);
    const minuteEnd = this._stateValue(minuteEndEid);

    const dailyLimitActive = this._stateValue(E.daily_limit_enabled) === "on";
    const weeklyLimitActive = this._stateValue(E.weekly_limit_enabled) === "on";
    const monthlyLimitActive = this._stateValue(E.monthly_limit_enabled) === "on";
    const weeklyLimitEid = E.limit_week;
    const monthlyLimitEid = E.limit_month;
    const weeklyLimit = this._stateValue(weeklyLimitEid);
    const monthlyLimit = this._stateValue(monthlyLimitEid);

    const lockoutType = this._stateValue(E.lockout_type);
    const trackInactive = this._stateValue(E.track_inactive) === "on";

    // Profile
    const profileSelectEid = E.profile;
    const profileState = this._state(profileSelectEid);
    const activeProfile = profileState ? profileState.state : "custom";
    const profileOptions = profileState && profileState.attributes.options ? profileState.attributes.options : ["custom"];
    const isCustomProfile = activeProfile === "custom";
    const isOverrideProfile = activeProfile === "override";
    const canDelete = !isCustomProfile && !isOverrideProfile;
    const canSave = !isOverrideProfile;

    const timeRemaining = this._stateValue(E.time_remaining);
    const notifThresholdEid = E.notification_threshold;
    const notifThreshold = this._stateValue(notifThresholdEid);

    const user = String(this.config.target_user);
    const title = this.config.title || `${this._t("default_title")} - ${user.charAt(0).toUpperCase() + user.slice(1)}`;

    // Build day toggles
    let dayTogglesHtml = days.map((d) => {
      const eid = E[`day_${d.key}`];
      const isOn = this._stateValue(eid) === "on";
      return `<div class="day-chip ${isOn ? "active" : ""}" data-toggle="${eid}">${d.label}</div>`;
    }).join("");

    // Build daily limits with +/- controls
    let dailyLimitsHtml = "";
    if (dailyLimitActive) {
      dailyLimitsHtml = days.map((d) => {
        const eid = E[`limit_${d.key}`];
        const val = this._stateValue(eid);
        const numVal = parseInt(val);
        const displayVal = esc(val === "unavailable" ? "-" : (numVal >= 1440 ? this._t("unlimited") : `${val} min`));
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

    // Lockout options (labels reused from integration select translations)
    const lockoutState = this._state(E.lockout_type);
    const lockoutOptions = (lockoutState && lockoutState.attributes.options) ||
      ["lock", "suspend", "terminate", "kill", "shutdown"];
    const lockoutSelectId = E.lockout_type;
    const lockoutOptionsHtml = lockoutOptions.map((opt) =>
      `<option value="${esc(opt)}" ${lockoutType === opt ? "selected" : ""}>${esc(this._localizeOption("lockout_type", opt))}</option>`
    ).join("");

    // Format time
    const formatTime = (val) => {
      if (val === "unavailable" || val === "unknown" || val === null || val === "None") return "-";
      const n = parseInt(val);
      if (isNaN(n)) return esc(val);
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
              <div class="tkp-header-title">${esc(title)}</div>
              <div class="tkp-header-status">
                ${esc(onlineLabel)}
                ${parseInt(pending) > 0 ? `<span class="tkp-pending-badge">${esc(pending)} ${esc(this._t("pending"))}</span>` : ""}
              </div>
              <div class="tkp-header-badges">
                <span class="tkp-service-badge${isOnline ? "" : " offline"}">Timekpr-nExT</span>
              </div>
            </div>
          </div>


          <!-- Profile -->
          <div class="tkp-profile-section">
            <div class="tkp-section-title" style="margin-bottom: 10px">
              <ha-icon icon="mdi:account-switch" style="--mdc-icon-size:16px"></ha-icon> ${this._t("profile")}
            </div>
            <div class="tkp-profile-row">
              <select class="tkp-select" id="tkp-profile-select" data-select="${profileSelectEid}">
                ${profileOptions.map((opt) =>
                  `<option value="${esc(opt)}" ${activeProfile === opt ? "selected" : ""}>${esc(this._localizeOption("profile", opt))}</option>`
                ).join("")}
              </select>
              ${canDelete ? `<button class="tkp-icon-btn" id="tkp-profile-update" title="${this._t("update_profile_title")}">
                <ha-icon icon="mdi:content-save-edit" style="--mdc-icon-size:16px"></ha-icon>
              </button>
              <button class="tkp-icon-btn danger" id="tkp-profile-delete" title="${this._t("delete_profile_title")}">
                <ha-icon icon="mdi:delete" style="--mdc-icon-size:16px"></ha-icon>
              </button>` : ""}
              ${canSave ? `<button class="tkp-icon-btn" id="tkp-profile-add-toggle" title="${this._t("create_profile_title")}">
                <ha-icon icon="mdi:plus" style="--mdc-icon-size:16px"></ha-icon>
              </button>` : ""}
            </div>
            ${canSave ? `<div class="tkp-profile-actions" id="tkp-profile-new-row" style="display:${this._showNewProfile ? "flex" : "none"}">
              <input type="text" id="tkp-profile-name" placeholder="${this._t("new_profile_placeholder")}">
              <button class="tkp-icon-btn" id="tkp-profile-save" title="${this._t("create")}">
                <ha-icon icon="mdi:check" style="--mdc-icon-size:16px"></ha-icon>
              </button>
              <button class="tkp-icon-btn" id="tkp-profile-add-cancel" title="${this._t("cancel")}">
                <ha-icon icon="mdi:close" style="--mdc-icon-size:16px"></ha-icon>
              </button>
            </div>` : ""}
          </div>

          <!-- Stats -->
          <div class="tkp-stats">
            <div class="tkp-stat" data-more-info="${E.time_spent_today}">
              <div class="tkp-stat-value">${formatTime(timeToday)}</div>
              <div class="tkp-stat-label">${this._t("today")}</div>
            </div>
            <div class="tkp-stat" data-more-info="${E.time_spent_week}">
              <div class="tkp-stat-value">${formatTime(timeWeek)}</div>
              <div class="tkp-stat-label">${this._t("this_week")}</div>
            </div>
            <div class="tkp-stat" data-more-info="${E.time_remaining}">
              <div class="tkp-stat-value" style="${timeRemaining !== "unavailable" && parseInt(timeRemaining) <= parseInt(notifThreshold || 15) ? "color: var(--error-color, #f44336)" : ""}">${formatTime(timeRemaining)}</div>
              <div class="tkp-stat-label">${this._t("remaining")}</div>
            </div>
          </div>

          <!-- Days -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:calendar" style="--mdc-icon-size:16px"></ha-icon> ${this._t("allowed_days")}</div>
            <div class="day-chips">${dayTogglesHtml}</div>
          </div>

          <!-- Hours -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:clock-outline" style="--mdc-icon-size:16px"></ha-icon> ${this._t("time_range")}</div>
            <div class="tkp-time-row">
              <span class="tkp-row-label">${this._t("start")}</span>
              <div class="tkp-time-controls">
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${hourStartEid}" data-delta="-1">-</button>
                  <span class="tkp-time-value">${hourStart !== "unavailable" ? esc(parseInt(hourStart)) : "-"}</span>
                  <button class="tkp-btn" data-adjust="${hourStartEid}" data-delta="1">+</button>
                </div>
                <span class="tkp-time-colon">:</span>
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${minuteStartEid}" data-delta="-5">-</button>
                  <span class="tkp-time-value">${minuteStart !== "unavailable" ? esc(String(parseInt(minuteStart)).padStart(2, "0")) : "-"}</span>
                  <button class="tkp-btn" data-adjust="${minuteStartEid}" data-delta="5">+</button>
                </div>
              </div>
            </div>
            <div class="tkp-time-row">
              <span class="tkp-row-label">${this._t("end")}</span>
              <div class="tkp-time-controls">
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${hourEndEid}" data-delta="-1">-</button>
                  <span class="tkp-time-value">${hourEnd !== "unavailable" ? esc(parseInt(hourEnd)) : "-"}</span>
                  <button class="tkp-btn" data-adjust="${hourEndEid}" data-delta="1">+</button>
                </div>
                <span class="tkp-time-colon">:</span>
                <div class="tkp-time-group">
                  <button class="tkp-btn" data-adjust="${minuteEndEid}" data-delta="-5">-</button>
                  <span class="tkp-time-value">${minuteEnd !== "unavailable" ? esc(String(parseInt(minuteEnd)).padStart(2, "0")) : "-"}</span>
                  <button class="tkp-btn" data-adjust="${minuteEndEid}" data-delta="5">+</button>
                </div>
              </div>
            </div>
          </div>

          <!-- Daily limits -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:timer-outline" style="--mdc-icon-size:16px"></ha-icon> ${this._t("daily_limits")}</div>
            <div class="tkp-toggle" data-toggle="${E.daily_limit_enabled}">
              <span class="tkp-toggle-label">${this._t("enable")}</span>
              <div class="tkp-toggle-switch ${dailyLimitActive ? "on" : "off"}"></div>
            </div>
            ${dailyLimitsHtml}
          </div>

          <!-- Weekly / Monthly limits -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:calendar-clock" style="--mdc-icon-size:16px"></ha-icon> ${this._t("global_limits")}</div>
            <div class="tkp-toggle" data-toggle="${E.weekly_limit_enabled}">
              <span class="tkp-toggle-label">${this._t("weekly_limit")}</span>
              <div class="tkp-toggle-switch ${weeklyLimitActive ? "on" : "off"}"></div>
            </div>
            ${weeklyLimitActive ? `<div class="limit-row">
              <span class="limit-label">${this._t("weekly")}</span>
              <div class="limit-controls">
                <button class="tkp-btn" data-adjust="${weeklyLimitEid}" data-delta="-1">-</button>
                <span class="limit-value" data-more-info="${weeklyLimitEid}">${esc(parseInt(weeklyLimit) >= 168 ? this._t("unlimited") : weeklyLimit + "h")}</span>
                <button class="tkp-btn" data-adjust="${weeklyLimitEid}" data-delta="1">+</button>
              </div>
            </div>` : ""}
            <div class="tkp-toggle" data-toggle="${E.monthly_limit_enabled}">
              <span class="tkp-toggle-label">${this._t("monthly_limit")}</span>
              <div class="tkp-toggle-switch ${monthlyLimitActive ? "on" : "off"}"></div>
            </div>
            ${monthlyLimitActive ? `<div class="limit-row">
              <span class="limit-label">${this._t("monthly")}</span>
              <div class="limit-controls">
                <button class="tkp-btn" data-adjust="${monthlyLimitEid}" data-delta="-1">-</button>
                <span class="limit-value" data-more-info="${monthlyLimitEid}">${esc(parseInt(monthlyLimit) >= 744 ? this._t("unlimited") : monthlyLimit + "h")}</span>
                <button class="tkp-btn" data-adjust="${monthlyLimitEid}" data-delta="1">+</button>
              </div>
            </div>` : ""}
          </div>

          <!-- Settings -->
          <div class="tkp-section">
            <div class="tkp-section-title"><ha-icon icon="mdi:cog" style="--mdc-icon-size:16px"></ha-icon> ${this._t("settings")}</div>
            <div class="tkp-row">
              <span class="tkp-row-label">${this._t("action_when_time_runs_out")}</span>
              <select class="tkp-select" data-select="${lockoutSelectId}">
                ${lockoutOptionsHtml}
              </select>
            </div>
            <div class="tkp-toggle" data-toggle="${E.track_inactive}">
              <span class="tkp-toggle-label">${this._t("count_idle_time")}</span>
              <div class="tkp-toggle-switch ${trackInactive ? "on" : "off"}"></div>
            </div>
            <div class="tkp-row">
              <span class="tkp-row-label">${this._t("alert_before_end")}</span>
              <div class="tkp-row-controls">
                <button class="tkp-btn" data-adjust="${notifThresholdEid}" data-delta="-5">-</button>
                <span class="tkp-row-value" data-more-info="${notifThresholdEid}">${esc(notifThreshold !== "unavailable" ? (parseInt(notifThreshold) === 0 ? this._t("off") : notifThreshold + " min") : "-")}</span>
                <button class="tkp-btn" data-adjust="${notifThresholdEid}" data-delta="5">+</button>
              </div>
            </div>
          </div>
        </div>
      </ha-card>
    `;

    // Bind toggle events (mouse + keyboard: they are plain divs)
    this.shadowRoot.querySelectorAll("[data-toggle]").forEach((el) => {
      el.setAttribute("role", "switch");
      el.setAttribute("tabindex", "0");
      const st = this._state(el.dataset.toggle);
      el.setAttribute("aria-checked", st && st.state === "on" ? "true" : "false");
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        this._toggle(el.dataset.toggle);
      });
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          this._toggle(el.dataset.toggle);
        }
      });
    });

    // Bind +/- buttons
    this.shadowRoot.querySelectorAll("[data-adjust]").forEach((el) => {
      const row = el.closest(".limit-row, .tkp-time-row, .tkp-row");
      const label = row && row.querySelector(".limit-label, .tkp-row-label");
      const delta = parseInt(el.dataset.delta);
      el.setAttribute("aria-label",
        `${label ? label.textContent.trim() : ""} ${delta > 0 ? "+" : ""}${delta}`.trim());
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
      // Prevent HA from intercepting events on selects
      for (const evt of ["keydown", "keyup", "keypress", "pointerdown", "mousedown", "touchstart", "click"]) {
        el.addEventListener(evt, (e) => e.stopPropagation());
      }
    });

    // Prevent HA from capturing events inside the profile input
    // and persist value so it survives re-renders
    const profileInput = this.shadowRoot.querySelector("#tkp-profile-name");
    if (profileInput) {
      for (const evt of ["keydown", "keyup", "keypress", "pointerdown", "mousedown", "touchstart", "click", "focus"]) {
        profileInput.addEventListener(evt, (e) => e.stopPropagation());
      }
      profileInput.addEventListener("input", () => {
        this._profileInputValue = profileInput.value;
      });
      // Restore persisted value if re-rendered
      if (this._profileInputValue !== undefined) {
        profileInput.value = this._profileInputValue;
      }
    }

    // mousedown fires before the input loses focus (mouse); a keyboard
    // activation only fires "click" with detail 0.
    const onPress = (el, fn) => {
      el.addEventListener("mousedown", (e) => {
        e.stopPropagation();
        e.preventDefault();
        fn();
      });
      el.addEventListener("click", (e) => {
        e.stopPropagation();
        if (e.detail === 0) fn();
      });
    };

    // Toggle "new profile" row
    const addToggleBtn = this.shadowRoot.querySelector("#tkp-profile-add-toggle");
    const newRow = this.shadowRoot.querySelector("#tkp-profile-new-row");
    if (addToggleBtn && newRow) {
      onPress(addToggleBtn, () => {
        this._showNewProfile = true;
        newRow.style.display = "flex";
        setTimeout(() => {
          const input = this.shadowRoot.querySelector("#tkp-profile-name");
          if (input) input.focus();
        }, 50);
      });
    }

    // Cancel new profile
    const cancelBtn = this.shadowRoot.querySelector("#tkp-profile-add-cancel");
    if (cancelBtn && newRow) {
      onPress(cancelBtn, () => {
        this._showNewProfile = false;
        this._profileInputValue = "";
        const input = this.shadowRoot.querySelector("#tkp-profile-name");
        if (input) input.blur();
        newRow.style.display = "none";
      });
    }

    // Bind profile save (use mousedown to fire BEFORE blur resets the input)
    const saveBtn = this.shadowRoot.querySelector("#tkp-profile-save");
    if (saveBtn) {
      const doSave = () => {
        const name = this._profileInputValue || (profileInput && profileInput.value) || "";
        if (name.trim()) {
          this._saveProfile(name.trim());
          this._profileInputValue = "";
          this._showNewProfile = false;
          if (profileInput) {
            profileInput.value = "";
            profileInput.blur();
          }
          if (newRow) newRow.style.display = "none";
        }
      };
      onPress(saveBtn, doSave);
      if (profileInput) {
        profileInput.addEventListener("keydown", (e) => {
          if (e.key === "Enter") doSave();
          if (e.key === "Escape" && cancelBtn) cancelBtn.click();
        });
      }
    }

    // Bind profile update (overwrite current profile with current settings)
    const updateBtn = this.shadowRoot.querySelector("#tkp-profile-update");
    if (updateBtn) {
      onPress(updateBtn, () => this._saveProfile(activeProfile));
    }

    // Bind profile delete (mousedown to avoid event interception)
    const deleteBtn = this.shadowRoot.querySelector("#tkp-profile-delete");
    if (deleteBtn) {
      onPress(deleteBtn, () => {
        if (confirm(this._t("confirm_delete").replace("%s", this._localizeOption("profile", activeProfile)))) {
          this._deleteProfile(activeProfile);
        }
      });
    }
  }

  getCardSize() {
    // Rows of 50 px: header, profile, stats, days, hours, limits, settings.
    return 14;
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
    if (!this.shadowRoot.querySelector("#target_user")) {
      this._render();
      return;
    }
    for (const field of ["target_user", "title"]) {
      const input = this.shadowRoot.querySelector(`#${field}`);
      const value = String(this._config[field] ?? "");
      if (input && input.value !== value) input.value = value;
    }
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    // Labels depend on the language: render once it is known.
    if (first && this._config) this._render();
  }

  _t(key) {
    const lang = ((this._hass && this._hass.language) || "en").split("-")[0];
    return (STRINGS[lang] && STRINGS[lang][key]) ?? STRINGS.en[key] ?? key;
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <div style="padding: 16px;">
        <div style="margin-bottom: 12px;">
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">
            ${this._t("target_user_label")}
          </label>
          <input type="text" id="target_user"
            value="${escapeHtml(this._config.target_user || "")}"
            style="width: 100%; padding: 8px; border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box;"
            placeholder="camille">
        </div>
        <div>
          <label style="display: block; margin-bottom: 4px; font-weight: 500;">
            ${this._t("title_label")}
          </label>
          <input type="text" id="title"
            value="${escapeHtml(this._config.title || "")}"
            style="width: 100%; padding: 8px; border: 1px solid var(--divider-color); border-radius: 4px; box-sizing: border-box;"
            placeholder="${escapeHtml(this._t("default_title"))} - Camille">
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
    name: "Timekpra - Parental Control",
    description: "Timekpr-nExT parental control management card",
    preview: true,
    documentationURL: "https://github.com/tienou/ha-timekpra",
  });
}

console.info(
  `%c TIMEKPRA-CARD %c v${CARD_VERSION} `,
  "color: white; background: #2962ff; font-weight: bold; padding: 2px 4px; border-radius: 4px 0 0 4px;",
  "color: #2962ff; background: white; font-weight: bold; padding: 2px 4px; border-radius: 0 4px 4px 0; border: 1px solid #2962ff;"
);
