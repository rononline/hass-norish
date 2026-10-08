/**
 * Norish meal planner card for Home Assistant.
 *
 * Shows today's meals as large photo tiles and the coming days as a compact
 * list. Data comes from the Norish week planner sensor (attribute week_data).
 *
 * type: custom:norish-card
 * entity: sensor.norish_week_planner   # optional, auto-detected
 * view: full | today | week            # optional, default: full
 * days: 7                              # optional, days in the list (1-7)
 * title: Maaltijden                    # optional
 * norish_url: https://norish.example   # optional, click opens the recipe
 */

const CARD_VERSION = "1.0.0";

const I18N = {
  en: {
    title: "Meal plan", today: "Today", tomorrow: "Tomorrow",
    nothing_today: "Nothing planned for the rest of today",
    nothing_day: "Nothing planned", nothing_week: "No meals planned yet",
    no_entity: "Norish week planner sensor not found",
    note: "Note",
    BREAKFAST: "Breakfast", LUNCH: "Lunch", DINNER: "Dinner", SNACK: "Snack",
  },
  nl: {
    title: "Maaltijdplanning", today: "Vandaag", tomorrow: "Morgen",
    nothing_today: "Vandaag niets meer gepland",
    nothing_day: "Niets gepland", nothing_week: "Nog geen maaltijden gepland",
    no_entity: "Norish weekplanner-sensor niet gevonden",
    note: "Notitie",
    BREAKFAST: "Ontbijt", LUNCH: "Lunch", DINNER: "Diner", SNACK: "Tussendoortje",
  },
  de: {
    title: "Essensplan", today: "Heute", tomorrow: "Morgen",
    nothing_today: "Heute nichts mehr geplant",
    nothing_day: "Nichts geplant", nothing_week: "Noch keine Mahlzeiten geplant",
    no_entity: "Norish Wochenplaner-Sensor nicht gefunden",
    note: "Notiz",
    BREAKFAST: "Frühstück", LUNCH: "Mittagessen", DINNER: "Abendessen", SNACK: "Snack",
  },
};

const SLOTS = {
  BREAKFAST: { icon: "mdi:coffee", hue: 38 },
  LUNCH: { icon: "mdi:food", hue: 145 },
  DINNER: { icon: "mdi:silverware-fork-knife", hue: 12 },
  SNACK: { icon: "mdi:cookie", hue: 280 },
  NOTE: { icon: "mdi:note-text-outline", hue: 210 },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);

class NorishCard extends HTMLElement {
  static getStubConfig() {
    return { view: "full" };
  }

  static getConfigForm() {
    return {
      schema: [
        { name: "entity", selector: { entity: { domain: "sensor" } } },
        { name: "title", selector: { text: {} } },
        {
          name: "view",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: "full", label: "Today + coming days" },
                { value: "today", label: "Today only" },
                { value: "week", label: "Week list only" },
              ],
            },
          },
        },
        { name: "days", selector: { number: { min: 1, max: 7, mode: "box" } } },
        { name: "norish_url", selector: { text: { type: "url" } } },
      ],
    };
  }

  setConfig(config) {
    if (config.view && !["full", "today", "week"].includes(config.view)) {
      throw new Error("view must be one of: full, today, week");
    }
    this._config = { view: "full", days: 7, ...config };
    this._lastState = undefined;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const state = hass.states[this._entityId()];
    // Only re-render when our entity (or the language) actually changed
    const key = `${hass.locale?.language || hass.language}`;
    if (state === this._lastState && key === this._lastKey) return;
    this._lastState = state;
    this._lastKey = key;
    this._render();
  }

  getCardSize() {
    return this._config?.view === "today" ? 4 : 7;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _entityId() {
    if (this._config?.entity) return this._config.entity;
    if (!this._hass) return undefined;
    if (!this._autoEntity || !this._hass.states[this._autoEntity]) {
      this._autoEntity = Object.keys(this._hass.states).find(
        (id) => id.startsWith("sensor.") &&
          Array.isArray(this._hass.states[id].attributes?.week_data)
      );
    }
    return this._autoEntity;
  }

  _lang() {
    const lang = (this._hass?.locale?.language || this._hass?.language || "en").split("-")[0];
    return I18N[lang] ? lang : "en";
  }

  _t(key) {
    return I18N[this._lang()][key] ?? I18N.en[key] ?? key;
  }

  _slot(meal) {
    if (meal.note && !meal.recipe_id) return "NOTE";
    const type = String(meal.type || "").toUpperCase();
    return SLOTS[type] ? type : "DINNER";
  }

  _slotLabel(meal) {
    const type = String(meal.type || "").toUpperCase();
    return I18N[this._lang()][type] ?? meal.type ?? "";
  }

  _dayLabel(day, index) {
    if (index === 0 && day.is_today) return this._t("today");
    if (index === 1) return this._t("tomorrow");
    const date = new Date(`${day.date}T12:00:00`);
    const lang = this._hass?.locale?.language || this._hass?.language || "en";
    const label = date.toLocaleDateString(lang, { weekday: "long" });
    return label.charAt(0).toUpperCase() + label.slice(1);
  }

  _dateLabel(day) {
    const date = new Date(`${day.date}T12:00:00`);
    const lang = this._hass?.locale?.language || this._hass?.language || "en";
    return date.toLocaleDateString(lang, { day: "numeric", month: "short" });
  }

  _placeholder(meal, cls) {
    const slot = SLOTS[this._slot(meal)];
    return `<div class="${cls} placeholder" style="--hue:${slot.hue}">
      <ha-icon icon="${slot.icon}"></ha-icon></div>`;
  }

  _image(meal, cls) {
    if (!meal.image) return this._placeholder(meal, cls);
    return `<div class="${cls}" style="--hue:${SLOTS[this._slot(meal)].hue}">
      <img src="${esc(meal.image)}" alt="" loading="lazy">
      <ha-icon class="fallback" icon="${SLOTS[this._slot(meal)].icon}"></ha-icon></div>`;
  }

  _mealAttrs(meal) {
    return meal.recipe_id ? `data-recipe="${esc(meal.recipe_id)}" tabindex="0" role="button"` : "";
  }

  _renderToday(today, upcoming) {
    const meals = today?.meals || [];
    if (!meals.length) {
      return `<div class="empty-today">
        <ha-icon icon="mdi:check-circle-outline"></ha-icon>
        <span>${esc(this._t("nothing_today"))}</span></div>`;
    }
    const tiles = meals.map((meal) => {
      const slot = this._slot(meal);
      const showNote = meal.note && meal.note !== meal.name;
      return `<div class="tile" ${this._mealAttrs(meal)}>
        ${this._image(meal, "tile-img")}
        <div class="shade"></div>
        <div class="tile-body">
          <span class="chip" style="--hue:${SLOTS[slot].hue}">
            <ha-icon icon="${SLOTS[slot].icon}"></ha-icon>${esc(this._slotLabel(meal))}</span>
          <div class="tile-name">${esc(meal.name)}</div>
          ${showNote ? `<div class="tile-note">${esc(meal.note)}</div>` : ""}
        </div>
      </div>`;
    }).join("");
    return `<div class="tiles count-${Math.min(meals.length, 4)}">${tiles}</div>`;
  }

  _renderWeek(days, startIndex) {
    const rows = days.map((day, i) => {
      const index = i + startIndex;
      const meals = day.meals || [];
      const items = meals.length
        ? meals.map((meal) => `<div class="meal" ${this._mealAttrs(meal)}>
            ${this._image(meal, "thumb")}
            <div class="meal-text">
              <span class="meal-slot">${esc(this._slotLabel(meal))}</span>
              <span class="meal-name">${esc(meal.name)}</span>
            </div></div>`).join("")
        : `<div class="nothing">${esc(this._t("nothing_day"))}</div>`;
      return `<div class="day ${day.is_today ? "is-today" : ""} ${day.is_weekend ? "weekend" : ""}">
        <div class="day-label">
          <span class="day-name">${esc(this._dayLabel(day, index))}</span>
          <span class="day-date">${esc(this._dateLabel(day))}</span>
        </div>
        <div class="meals">${items}</div>
      </div>`;
    }).join("");
    return `<div class="week">${rows}</div>`;
  }

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
      this.shadowRoot.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") this._onClick(ev);
      });
    }
    const title = this._config.title ?? this._t("title");
    const entityId = this._entityId();
    const state = entityId && this._hass?.states[entityId];
    let body;

    if (!this._hass) {
      body = "";
    } else if (!state) {
      body = `<div class="warning">${esc(this._t("no_entity"))}</div>`;
    } else {
      const week = state.attributes.week_data || [];
      const days = Math.max(1, Math.min(7, Number(this._config.days) || 7));
      const view = this._config.view;
      const hasAny = week.some((d) => (d.meals || []).length);
      if (!hasAny && view !== "today") {
        body = `<div class="empty-week"><ha-icon icon="mdi:calendar-blank-outline"></ha-icon>
          <span>${esc(this._t("nothing_week"))}</span></div>`;
      } else if (view === "today") {
        body = this._renderToday(week[0]);
      } else if (view === "week") {
        body = this._renderWeek(week.slice(0, days), 0);
      } else {
        body = this._renderToday(week[0]) + this._renderWeek(week.slice(1, days), 1);
      }
    }

    const today = new Date().toLocaleDateString(
      this._hass?.locale?.language || this._hass?.language || "en",
      { weekday: "long", day: "numeric", month: "long" }
    );

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        ${title ? `<div class="header">
          <div class="title"><ha-icon icon="mdi:chef-hat"></ha-icon>${esc(title)}</div>
          <div class="subtitle">${esc(today)}</div></div>` : ""}
        <div class="content">${body}</div>
      </ha-card>`;
    // Image not reachable (e.g. not cached yet) → show the slot placeholder
    this.shadowRoot.querySelectorAll("img").forEach((img) => {
      img.addEventListener("error", () => {
        img.parentElement.classList.add("placeholder", "broken");
        img.remove();
      }, { once: true });
    });
  }

  _onClick(ev) {
    const target = ev.composedPath().find((el) => el.dataset?.recipe);
    if (target && this._config.norish_url) {
      const base = this._config.norish_url.replace(/\/$/, "");
      window.open(`${base}/recipes/${encodeURIComponent(target.dataset.recipe)}`, "_blank", "noopener");
      return;
    }
    const entityId = this._entityId();
    if (!entityId || !(target || ev.composedPath().some((el) => el.classList?.contains("header")))) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      detail: { entityId }, bubbles: true, composed: true,
    }));
  }
}

const STYLE = `
  :host { display: block; }
  ha-card { overflow: hidden; container-type: inline-size; }
  .header {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: 8px; padding: 16px 16px 8px; cursor: pointer;
  }
  .title {
    display: flex; align-items: center; gap: 8px;
    font-size: 1.2em; font-weight: 600; color: var(--primary-text-color);
  }
  .title ha-icon { color: var(--primary-color); --mdc-icon-size: 22px; }
  .subtitle { font-size: 0.85em; color: var(--secondary-text-color); white-space: nowrap; }
  .content { padding: 8px 16px 16px; display: flex; flex-direction: column; gap: 16px; }

  /* Today: photo tiles */
  /* 1 meal: one wide tile; 3 meals: next meal wide, the others below */
  .tiles { display: grid; gap: 10px; grid-template-columns: 1fr 1fr; }
  .tiles.count-1 .tile, .tiles.count-3 .tile:first-child {
    grid-column: 1 / -1; aspect-ratio: 16 / 9; max-height: 260px;
  }
  .tile {
    position: relative; width: 100%; aspect-ratio: 4 / 3; max-height: 200px;
    border-radius: 14px; overflow: hidden;
    cursor: pointer; isolation: isolate; outline: none;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15);
  }
  .tile:focus-visible { box-shadow: 0 0 0 3px var(--primary-color); }
  .tile-img { position: absolute; inset: 0; }
  .tile-img img, .thumb img {
    width: 100%; height: 100%; object-fit: cover; display: block;
    transition: transform 0.4s ease;
  }
  .tile:hover .tile-img img { transform: scale(1.04); }
  .shade {
    position: absolute; inset: 0;
    background: linear-gradient(to top, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.25) 45%, rgba(0,0,0,0) 70%);
  }
  .tile-body {
    position: absolute; left: 0; right: 0; bottom: 0; padding: 12px;
    display: flex; flex-direction: column; align-items: flex-start; gap: 6px;
    color: #fff;
  }
  .chip {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 9px 3px 6px; border-radius: 999px;
    font-size: 0.72em; font-weight: 600; letter-spacing: 0.02em; text-transform: uppercase;
    background: hsla(var(--hue), 70%, 45%, 0.9); color: #fff;
    backdrop-filter: blur(4px);
  }
  .chip ha-icon { --mdc-icon-size: 14px; }
  .tile-name {
    font-size: 1.05em; font-weight: 600; line-height: 1.25;
    text-shadow: 0 1px 2px rgba(0,0,0,0.4);
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
  }
  .count-1 .tile-name, .count-3 .tile:first-child .tile-name { font-size: 1.3em; }
  .tile-note { font-size: 0.85em; opacity: 0.9; font-style: italic; }

  /* Placeholders (no or broken image) */
  .placeholder {
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(135deg, hsl(var(--hue), 55%, 62%), hsl(calc(var(--hue) + 30), 60%, 42%));
    color: rgba(255,255,255,0.9);
  }
  .tile-img.placeholder ha-icon { --mdc-icon-size: 48px; margin-bottom: 40px; }
  .thumb.placeholder ha-icon { --mdc-icon-size: 22px; }
  .fallback { display: none; }
  .broken .fallback { display: block; }

  /* Coming days */
  .week { display: flex; flex-direction: column; }
  .day {
    display: grid; grid-template-columns: 92px 1fr; gap: 12px; align-items: start;
    padding: 10px 0; border-top: 1px solid var(--divider-color);
  }
  .week .day:first-child { border-top: none; }
  .day-label { display: flex; flex-direction: column; padding-top: 4px; }
  .day-name { font-weight: 600; color: var(--primary-text-color); }
  .day-date { font-size: 0.8em; color: var(--secondary-text-color); }
  .day.is-today .day-name { color: var(--primary-color); }
  .meals { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
  .meal { display: flex; align-items: center; gap: 10px; min-width: 0; border-radius: 10px; outline: none; }
  .meal[data-recipe] { cursor: pointer; }
  .meal:focus-visible { box-shadow: 0 0 0 2px var(--primary-color); }
  .thumb {
    flex: 0 0 44px; width: 44px; height: 44px; border-radius: 10px; overflow: hidden;
  }
  .meal-text { display: flex; flex-direction: column; min-width: 0; }
  .meal-slot {
    font-size: 0.7em; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
    color: var(--secondary-text-color);
  }
  .meal-name {
    color: var(--primary-text-color); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .nothing { color: var(--secondary-text-color); font-size: 0.9em; padding-top: 4px; font-style: italic; }

  /* Empty / warning states */
  .empty-today, .empty-week {
    display: flex; align-items: center; gap: 10px; padding: 14px 16px; border-radius: 14px;
    background: var(--secondary-background-color); color: var(--secondary-text-color);
  }
  .empty-week { flex-direction: column; padding: 28px 16px; text-align: center; }
  .empty-week ha-icon { --mdc-icon-size: 36px; opacity: 0.6; }
  .warning { color: var(--error-color); padding: 8px 0; }

  @container (max-width: 420px) {
    .day { grid-template-columns: 74px 1fr; gap: 8px; }
    .content { padding: 4px 12px 12px; }
  }
`;

if (!customElements.get("norish-card")) {
  customElements.define("norish-card", NorishCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "norish-card",
    name: "Norish",
    description: "Today's meals with photos and the coming days from Norish.",
    preview: true,
    documentationURL: "https://github.com/rononline/hass-norish",
  });
  console.info(`%c NORISH-CARD %c ${CARD_VERSION} `,
    "color:#fff;background:#e0703c;font-weight:700", "color:#e0703c;background:#fff");
}
