/**
 * Norish meal planner card for Home Assistant.
 *
 * Shows today's meals as large photo tiles and the coming days as a compact
 * list; tapping a meal opens the recipe (times, ingredients, steps).
 * Data comes from the Norish week planner sensor (attribute week_data).
 *
 * type: custom:norish-card
 * entity: sensor.norish_week_planner     # optional, auto-detected
 * view: full | today | week | recipe | shopping   # optional, default: full
 * slot: dinner                           # optional, view: recipe only
 * layout: auto | horizontal | vertical   # optional, recipe columns side by side
 * days: 7                                # optional, days in the list (1-7)
 * title: Maaltijden                      # optional
 * norish_url: https://norish.example     # optional, adds an "open in Norish" link
 * shopping_lists: [todo.norish_ah]       # optional, view: shopping (default: all)
 * tomorrow_after: "20:00"                # optional, from then on show tomorrow
 */

const CARD_VERSION = "1.5.0";

const I18N = {
  en: {
    title: "Meal plan", today: "Today", tomorrow: "Tomorrow",
    nothing_today: "Nothing planned for the rest of today",
    nothing_day: "Nothing planned", nothing_week: "No meals planned yet",
    no_entity: "Norish week planner sensor not found",
    note: "Note", back: "Back", open: "Open in Norish",
    prep: "Preparation", cook: "Cooking", total: "Total time", servings: "Servings",
    ingredients: "Ingredients", steps: "Method", hour: "h",
    no_details: "No recipe details available", no_recipe: "No recipe planned",
    offline: "Offline", updated: "updated",
    cook: "Cook mode", step_of: "Step {n} of {total}", prev: "Previous", next: "Next",
    done: "Done", close: "Close", to_list: "Add to shopping list",
    added: "Ingredients added to the shopping list", failed: "That did not work",
    timer_done: "Timer done", shopping: "Shopping list", add_placeholder: "Add an item…",
    add: "Add", nothing_needed: "Nothing needed", checked: "checked off",
    no_lists: "No Norish shopping lists found",
    fewer: "Fewer servings", more: "More servings", nothing_tomorrow: "Nothing planned for tomorrow",
    BREAKFAST: "Breakfast", LUNCH: "Lunch", DINNER: "Dinner", SNACK: "Snack",
  },
  nl: {
    title: "Maaltijdplanning", today: "Vandaag", tomorrow: "Morgen",
    nothing_today: "Vandaag niets meer gepland",
    nothing_day: "Niets gepland", nothing_week: "Nog geen maaltijden gepland",
    no_entity: "Norish weekplanner-sensor niet gevonden",
    note: "Notitie", back: "Terug", open: "Openen in Norish",
    prep: "Voorbereiding", cook: "Kooktijd", total: "Totale tijd", servings: "Porties",
    ingredients: "Ingrediënten", steps: "Bereiding", hour: "u",
    no_details: "Geen receptdetails beschikbaar", no_recipe: "Geen recept gepland",
    offline: "Offline", updated: "bijgewerkt",
    cook: "Kookstand", step_of: "Stap {n} van {total}", prev: "Vorige", next: "Volgende",
    done: "Klaar", close: "Sluiten", to_list: "Op boodschappenlijst",
    added: "Ingrediënten op de boodschappenlijst gezet", failed: "Dat lukte niet",
    timer_done: "Timer klaar", shopping: "Boodschappen", add_placeholder: "Iets toevoegen…",
    add: "Toevoegen", nothing_needed: "Niets nodig", checked: "afgevinkt",
    no_lists: "Geen Norish-boodschappenlijsten gevonden",
    fewer: "Minder porties", more: "Meer porties", nothing_tomorrow: "Morgen nog niets gepland",
    BREAKFAST: "Ontbijt", LUNCH: "Lunch", DINNER: "Diner", SNACK: "Tussendoortje",
  },
  de: {
    title: "Essensplan", today: "Heute", tomorrow: "Morgen",
    nothing_today: "Heute nichts mehr geplant",
    nothing_day: "Nichts geplant", nothing_week: "Noch keine Mahlzeiten geplant",
    no_entity: "Norish Wochenplaner-Sensor nicht gefunden",
    note: "Notiz", back: "Zurück", open: "In Norish öffnen",
    prep: "Vorbereitung", cook: "Kochzeit", total: "Gesamtzeit", servings: "Portionen",
    ingredients: "Zutaten", steps: "Zubereitung", hour: "Std.",
    no_details: "Keine Rezeptdetails verfügbar", no_recipe: "Kein Rezept geplant",
    offline: "Offline", updated: "aktualisiert",
    cook: "Kochmodus", step_of: "Schritt {n} von {total}", prev: "Zurück", next: "Weiter",
    done: "Fertig", close: "Schließen", to_list: "Auf die Einkaufsliste",
    added: "Zutaten auf die Einkaufsliste gesetzt", failed: "Das hat nicht geklappt",
    timer_done: "Timer abgelaufen", shopping: "Einkaufsliste", add_placeholder: "Etwas hinzufügen…",
    add: "Hinzufügen", nothing_needed: "Nichts nötig", checked: "abgehakt",
    no_lists: "Keine Norish-Einkaufslisten gefunden",
    fewer: "Weniger Portionen", more: "Mehr Portionen", nothing_tomorrow: "Für morgen nichts geplant",
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

/** Escape, then render the bit of Markdown Norish uses: **bold** and *italic*. */
const md = (value) =>
  esc(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/__(.+?)__/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*(?!\s)([^*]+?)\*(?!\w)/g, "$1<em>$2</em>");

/**
 * Durations in a step ("8 tot 10 minuten", "1 uur", "30 sec") → timers.
 * A range uses its lower bound, so the timer goes off at the first check.
 */
const TIMER_UNITS = [
  [/^(uur|uren|hours?|hrs?|stunden?|std\.?)$/i, 3600],
  [/^(minuten|minuut|minutes?|mins?\.?|min\.?)$/i, 60],
  [/^(seconden|seconde|seconds?|secs?\.?|sekunden?|sek\.?|s)$/i, 1],
];
const TIMER_RE = /(\d+(?:[.,]\d+)?)(?:\s*(?:-|–|tot|to|bis)\s*(\d+(?:[.,]\d+)?))?\s*(uur|uren|hours?|hrs?|stunden?|std\.?|minuten|minuut|minutes?|mins?\.?|min\.?|seconden|seconde|seconds?|secs?\.?|sekunden?|sek\.?)(?![a-z])/gi;

function findTimers(text) {
  const found = [];
  const seen = new Set();
  for (const match of String(text || "").matchAll(TIMER_RE)) {
    const unit = TIMER_UNITS.find(([re]) => re.test(match[3]));
    if (!unit) continue;
    const seconds = Math.round(parseFloat(match[1].replace(",", ".")) * unit[1]);
    if (!seconds || seconds > 24 * 3600 || seen.has(seconds)) continue;
    seen.add(seconds);
    found.push({ seconds, label: match[0].trim() });
  }
  return found;
}

function formatClock(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const sec = String(seconds % 60).padStart(2, "0");
  return h ? `${h}:${String(m).padStart(2, "0")}:${sec}` : `${m}:${sec}`;
}

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
                { value: "recipe", label: "Next recipe (ingredients + steps)" },
                { value: "shopping", label: "Shopping lists" },
              ],
            },
          },
        },
        {
          name: "slot",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: "breakfast", label: "Breakfast" },
                { value: "lunch", label: "Lunch" },
                { value: "dinner", label: "Dinner" },
                { value: "snack", label: "Snack" },
              ],
            },
          },
        },
        {
          name: "layout",
          selector: {
            select: {
              mode: "dropdown",
              options: [
                { value: "auto", label: "Automatic (by width)" },
                { value: "horizontal", label: "Side by side (landscape screen)" },
                { value: "vertical", label: "Stacked" },
              ],
            },
          },
        },
        { name: "days", selector: { number: { min: 1, max: 7, mode: "box" } } },
        { name: "tomorrow_after", selector: { time: {} } },
        { name: "norish_url", selector: { text: { type: "url" } } },
        { name: "shopping_lists", selector: { entity: { domain: "todo", multiple: true } } },
      ],
    };
  }

  setConfig(config) {
    if (config.view && !["full", "today", "week", "recipe", "shopping"].includes(config.view)) {
      throw new Error("view must be one of: full, today, week, recipe, shopping");
    }
    if (config.layout && !["auto", "horizontal", "vertical"].includes(config.layout)) {
      throw new Error("layout must be one of: auto, horizontal, vertical");
    }
    this._config = { view: "full", days: 7, layout: "auto", ...config };
    this._selected = undefined;
    this._cook = undefined;
    this._lastState = undefined;
    this._shop = this._shop || {};
    this._servings = this._servings || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._config?.view === "shopping") {
      // Re-load items whenever one of the lists changed (state = open items)
      const lists = this._shoppingEntities();
      const key = lists.map((id) => `${id}:${hass.states[id]?.last_updated}`).join("|");
      if (key !== this._shopKey) {
        this._shopKey = key;
        this._loadShopping(lists);
      }
      return;
    }
    const state = hass.states[this._entityId()];
    // Only re-render when our entity (or the language) actually changed
    const key = `${hass.locale?.language || hass.language}|${this._tomorrowMode()}`;
    if (state === this._lastState && key === this._lastKey) return;
    this._lastState = state;
    this._lastKey = key;
    this._render();
  }

  disconnectedCallback() {
    this._releaseWakeLock();
    clearInterval(this._ticker);
    this._ticker = undefined;
  }

  connectedCallback() {
    if (this._timers?.length) this._ensureTicker();
  }

  getCardSize() {
    return { today: 4, recipe: 9, shopping: 6 }[this._config?.view] ?? 7;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  _entityId() {
    if (this._config?.entity) return this._config.entity;
    if (!this._hass) return undefined;
    if (!this._autoEntity || !this._hass.states[this._autoEntity]) {
      const found = Object.keys(this._hass.states).find(
        (id) => id.startsWith("sensor.") &&
          Array.isArray(this._hass.states[id].attributes?.week_data)
      );
      if (found) {
        this._autoEntity = found;
        try { localStorage.setItem("norish-card:entity", found); } catch (err) { /* ignore */ }
      } else {
        // Sensor unavailable (no attributes): use the one seen before
        let remembered = null;
        try { remembered = localStorage.getItem("norish-card:entity"); } catch (err) { /* ignore */ }
        this._autoEntity = [remembered, "sensor.norish_week_planner"]
          .find((id) => id && this._hass.states[id]);
      }
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

  _mealAttrs(meal, day) {
    if (!meal.recipe_id) return "";
    return `data-recipe="${esc(meal.recipe_id)}" data-date="${esc(day?.date)}"
      data-type="${esc(meal.type)}" tabindex="0" role="button"`;
  }

  _lang_full() {
    return this._hass?.locale?.language || this._hass?.language || "en";
  }

  _minutes(value) {
    const min = Number(value);
    if (!min || min <= 0) return "";
    if (min < 60) return `${min} min`;
    const rest = min % 60;
    return `${Math.floor(min / 60)} ${this._t("hour")}${rest ? ` ${rest} min` : ""}`;
  }

  _amount(value) {
    if (value === null || value === undefined || value === "") return "";
    const num = Number(value);
    if (Number.isNaN(num)) return String(value);
    return new Intl.NumberFormat(this._lang_full(), { maximumFractionDigits: 2 }).format(num);
  }

  /** After the configured tomorrow_after time, today's part shows tomorrow. */
  _tomorrowMode() {
    const match = /^(\d{1,2}):(\d{2})/.exec(String(this._config?.tomorrow_after || ""));
    if (!match) return false;
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes() >= Number(match[1]) * 60 + Number(match[2]);
  }

  /** Servings of a recipe: as written, as chosen in the card, and the factor. */
  _portions(meal) {
    const base = Number(meal.servings);
    if (!base || base <= 0) return { base: 0, now: 0, factor: 1 };
    const now = this._servings?.[meal.recipe_id] || base;
    return { base, now, factor: now / base };
  }

  _ingredientList(meal) {
    const { factor } = this._portions(meal);
    return (meal.ingredients || []).map((ing) => {
      const name = String(ing.name || "");
      if (name.trim().startsWith("#")) {
        return `<li class="sub">${esc(name.trim().replace(/^#+\s*/, ""))}</li>`;
      }
      const amount = factor !== 1 && ing.amount !== null && ing.amount !== "" && !Number.isNaN(Number(ing.amount))
        ? Number(ing.amount) * factor : ing.amount;
      const qty = [this._amount(amount), ing.unit].filter(Boolean).join(" ");
      return `<li><span class="qty">${esc(qty)}</span><span class="ing">${esc(name)}</span></li>`;
    }).join("");
  }

  _servingsMeta(meal) {
    const { base, now } = this._portions(meal);
    if (!base) return "";
    const rid = esc(meal.recipe_id);
    return `<div class="meta-item"><ha-icon icon="mdi:account-group-outline"></ha-icon>
      <div><div class="meta-label">${esc(this._t("servings"))}</div>
      <div class="stepper">
        <button class="step-btn" data-action="serv-dec" data-rid="${rid}" ${now <= 1 ? "disabled" : ""}
          title="${esc(this._t("fewer"))}" aria-label="${esc(this._t("fewer"))}"><ha-icon icon="mdi:minus"></ha-icon></button>
        <span class="meta-value ${now !== base ? "changed" : ""}">${now}</span>
        <button class="step-btn" data-action="serv-inc" data-rid="${rid}"
          title="${esc(this._t("more"))}" aria-label="${esc(this._t("more"))}"><ha-icon icon="mdi:plus"></ha-icon></button>
      </div></div></div>`;
  }

  /** Find a meal (and its day) in week_data. */
  _findMeal(week, wanted) {
    for (const [index, day] of week.entries()) {
      for (const meal of day.meals || []) {
        if (wanted(meal, day)) return { meal, day, index };
      }
    }
    return undefined;
  }

  _renderRecipe({ meal, day, index }, withBack) {
    const slot = this._slot(meal);
    const meta = [
      ["prep", "mdi:knife", this._minutes(meal.prep_minutes)],
      ["cook", "mdi:pot-steam-outline", this._minutes(meal.cook_minutes)],
      ["total", "mdi:clock-outline", this._minutes(meal.total_minutes)],
    ].filter(([, , value]) => value);
    const servings = this._servingsMeta(meal);

    const ingredients = this._ingredientList(meal);

    let number = 0;
    const steps = (meal.steps || []).map((step) => {
      const text = String(step || "").trim();
      if (text.startsWith("#")) {
        return `<li class="sub">${esc(text.replace(/^#+\s*/, ""))}</li>`;
      }
      number += 1;
      return `<li><span class="num">${number}</span><span>${md(text)}</span></li>`;
    }).join("");

    const link = this._config.norish_url && meal.recipe_id
      ? `<a class="action" href="${esc(this._config.norish_url.replace(/\/$/, ""))}/recipes/${encodeURIComponent(meal.recipe_id)}"
          target="_blank" rel="noopener"><ha-icon icon="mdi:open-in-new"></ha-icon>${esc(this._t("open"))}</a>`
      : "";

    return `<div class="recipe ${esc(this._config.layout)}">
      <div class="recipe-main">
        <div class="hero">
          ${this._image(meal, "tile-img")}
          <div class="shade"></div>
          ${withBack ? `<button class="back" data-action="back" title="${esc(this._t("back"))}"
            aria-label="${esc(this._t("back"))}"><ha-icon icon="mdi:arrow-left"></ha-icon></button>` : ""}
          <div class="tile-body">
            <div class="chips">
              <span class="chip day-chip">${esc(this._dayLabel(day, index))}</span>
              <span class="chip" style="--hue:${SLOTS[slot].hue}">
                <ha-icon icon="${SLOTS[slot].icon}"></ha-icon>${esc(this._slotLabel(meal))}</span>
            </div>
            <div class="hero-name">${esc(meal.name)}</div>
          </div>
        </div>
        ${meta.length || servings ? `<div class="meta">${meta.map(([key, icon, value]) => `
          <div class="meta-item"><ha-icon icon="${icon}"></ha-icon>
            <div><div class="meta-label">${esc(this._t(key))}</div>
            <div class="meta-value">${esc(value)}</div></div></div>`).join("")}${servings}</div>` : ""}
        ${meal.description ? `<p class="description">${md(meal.description)}</p>` : ""}
      </div>
      ${ingredients ? `<div class="recipe-ing"><section>
        <h3><ha-icon icon="mdi:carrot"></ha-icon>${esc(this._t("ingredients"))}</h3>
        <ul class="ingredients">${ingredients}</ul></section></div>` : ""}
      <div class="recipe-side">
        ${steps ? `<section><h3><ha-icon icon="mdi:chef-hat"></ha-icon>${esc(this._t("steps"))}</h3>
          <ol class="steps">${steps}</ol></section>` : ""}
        ${!steps && !ingredients ? `<div class="nothing">${esc(this._t("no_details"))}</div>` : ""}
        <div class="actions">
          ${steps ? `<button class="action primary" data-action="cook" data-rid="${esc(meal.recipe_id)}"
            data-date="${esc(day?.date)}" data-type="${esc(meal.type)}">
            <ha-icon icon="mdi:chef-hat"></ha-icon>${esc(this._t("cook"))}</button>` : ""}
          ${ingredients && meal.recipe_id ? `<button class="action" data-action="to-list" data-rid="${esc(meal.recipe_id)}">
            <ha-icon icon="mdi:cart-plus"></ha-icon>${esc(this._t("to_list"))}</button>` : ""}
          ${link}
        </div>
      </div>
    </div>`;
  }

  _renderToday(today, tomorrow = false) {
    const meals = today?.meals || [];
    const heading = tomorrow ? `<div class="day-heading">${esc(this._t("tomorrow"))}</div>` : "";
    if (!meals.length) {
      return `${heading}<div class="empty-today">
        <ha-icon icon="mdi:check-circle-outline"></ha-icon>
        <span>${esc(this._t(tomorrow ? "nothing_tomorrow" : "nothing_today"))}</span></div>`;
    }
    const tiles = meals.map((meal) => {
      const slot = this._slot(meal);
      const showNote = meal.note && meal.note !== meal.name;
      return `<div class="tile" ${this._mealAttrs(meal, today)}>
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
    return `${heading}<div class="tiles count-${Math.min(meals.length, 4)}">${tiles}</div>`;
  }

  _renderWeek(days, startIndex) {
    const rows = days.map((day, i) => {
      const index = i + startIndex;
      const meals = day.meals || [];
      const items = meals.length
        ? meals.map((meal) => `<div class="meal" ${this._mealAttrs(meal, day)}>
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

  /**
   * Week data to show: live from the sensor, or – when the sensor is
   * unavailable – the last data this card saw (kept in memory and in
   * localStorage, so a kitchen display survives a reload during an outage).
   */
  _weekData(entityId, state) {
    const key = `norish-card:${entityId}`;
    const live = state?.attributes?.week_data;
    if (Array.isArray(live)) {
      this._cache = {
        week: live,
        lastSuccess: state.attributes.last_success || new Date().toISOString(),
      };
      try {
        localStorage.setItem(key, JSON.stringify(this._cache));
      } catch (err) { /* storage unavailable – memory cache only */ }
      return { week: live, offline: !!state.attributes.stale, lastSuccess: this._cache.lastSuccess };
    }
    if (!this._cache) {
      try {
        this._cache = JSON.parse(localStorage.getItem(key) || "null");
      } catch (err) { this._cache = null; }
    }
    if (!this._cache || !Array.isArray(this._cache.week)) return undefined;
    // Cached days may be from yesterday: drop past days, re-mark today
    const now = new Date();
    const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
    const week = this._cache.week
      .filter((d) => d.date >= today)
      .map((d) => ({ ...d, is_today: d.date === today }));
    return { week, offline: true, lastSuccess: this._cache.lastSuccess };
  }

  _offlineBadge(lastSuccess) {
    const when = lastSuccess ? new Date(lastSuccess) : null;
    const time = when && !Number.isNaN(when.getTime())
      ? when.toLocaleTimeString(this._lang_full(), { hour: "2-digit", minute: "2-digit" })
      : "";
    return `<span class="offline"><ha-icon icon="mdi:cloud-off-outline"></ha-icon>${esc(this._t("offline"))}${
      time ? ` · ${esc(this._t("updated"))} ${esc(time)}` : ""}</span>`;
  }

  // ---------------------------------------------------------------- cook mode

  _cookSteps(meal) {
    const steps = [];
    let section = "";
    for (const raw of meal.steps || []) {
      const text = String(raw || "").trim();
      if (!text) continue;
      if (text.startsWith("#")) {
        section = text.replace(/^#+\s*/, "");
        continue;
      }
      steps.push({ text, section });
    }
    return steps;
  }

  _renderCook(meal) {
    const steps = this._cookSteps(meal);
    const total = steps.length;
    const index = Math.max(0, Math.min(this._cook.step, total - 1));
    this._cook.step = index;
    const step = steps[index] || { text: "", section: "" };
    const last = index >= total - 1;
    const timers = findTimers(step.text).map((t) => `
      <button class="timer-chip" data-action="timer" data-seconds="${t.seconds}" data-label="${esc(t.label)}">
        <ha-icon icon="mdi:timer-outline"></ha-icon>${esc(t.label)}</button>`).join("");
    const ingredients = this._ingredientList(meal);
    const count = this._t("step_of").replace("{n}", index + 1).replace("{total}", total);
    return `<div class="cook">
      <div class="cook-top">
        <button class="icon-btn" data-action="cook-close" title="${esc(this._t("close"))}"
          aria-label="${esc(this._t("close"))}"><ha-icon icon="mdi:close"></ha-icon></button>
        <div class="cook-title">${esc(meal.name)}</div>
        <div class="cook-count">${esc(count)}</div>
      </div>
      <div class="cook-progress"><span style="width:${total ? ((index + 1) / total) * 100 : 0}%"></span></div>
      ${step.section ? `<div class="cook-section">${esc(step.section)}</div>` : ""}
      <div class="cook-step">${md(step.text)}</div>
      ${timers ? `<div class="timer-chips">${timers}</div>` : ""}
      ${ingredients ? `<details class="cook-ing"><summary>${esc(this._t("ingredients"))}</summary>
        <ul class="ingredients">${ingredients}</ul></details>` : ""}
      <div class="cook-nav">
        <button class="nav-btn" data-action="cook-prev" ${index === 0 ? "disabled" : ""}>
          <ha-icon icon="mdi:chevron-left"></ha-icon>${esc(this._t("prev"))}</button>
        ${last
          ? `<button class="nav-btn primary" data-action="cook-close">${esc(this._t("done"))}
              <ha-icon icon="mdi:check"></ha-icon></button>`
          : `<button class="nav-btn primary" data-action="cook-next">${esc(this._t("next"))}
              <ha-icon icon="mdi:chevron-right"></ha-icon></button>`}
      </div>
    </div>`;
  }

  async _requestWakeLock() {
    try {
      if ("wakeLock" in navigator && !this._wakeLock) {
        this._wakeLock = await navigator.wakeLock.request("screen");
        this._wakeLock.addEventListener("release", () => { this._wakeLock = undefined; });
      }
    } catch (err) { /* not allowed (e.g. no HTTPS) – the screen may dim */ }
    if (!this._onVisible) {
      this._onVisible = () => {
        if (document.visibilityState === "visible" && this._cook) this._requestWakeLock();
      };
      document.addEventListener("visibilitychange", this._onVisible);
    }
  }

  _releaseWakeLock() {
    try { this._wakeLock?.release(); } catch (err) { /* ignore */ }
    this._wakeLock = undefined;
    if (this._onVisible) {
      document.removeEventListener("visibilitychange", this._onVisible);
      this._onVisible = undefined;
    }
  }

  // ------------------------------------------------------------------- timers

  _startTimer(seconds, label) {
    this._timers = this._timers || [];
    this._timers.push({ id: Date.now() + Math.random(), label, end: Date.now() + seconds * 1000, done: false });
    // Audio may only start after a user gesture – this click is one
    try {
      this._audio = this._audio || new (window.AudioContext || window.webkitAudioContext)();
      this._audio.resume?.();
    } catch (err) { this._audio = undefined; }
    this._ensureTicker();
    this._render();
  }

  _ensureTicker() {
    if (this._ticker) return;
    this._ticker = setInterval(() => this._tick(), 1000);
  }

  _tick() {
    const now = Date.now();
    let changed = false;
    for (const timer of this._timers || []) {
      const left = Math.max(0, Math.round((timer.end - now) / 1000));
      const el = this.shadowRoot?.querySelector(`.timer[data-tid="${timer.id}"] .t-left`);
      if (el) el.textContent = formatClock(left);
      if (!left && !timer.done) {
        timer.done = true;
        changed = true;
        this._alarm(timer.label);
      }
    }
    if (!(this._timers || []).some((t) => !t.done)) {
      clearInterval(this._ticker);
      this._ticker = undefined;
    }
    if (changed) this._render();
  }

  _alarm(label) {
    try { navigator.vibrate?.([400, 200, 400, 200, 400]); } catch (err) { /* ignore */ }
    const ctx = this._audio;
    if (ctx) {
      [0, 0.5, 1].forEach((offset) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.frequency.value = 880;
        gain.gain.setValueAtTime(0.25, ctx.currentTime + offset);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + offset + 0.35);
        osc.connect(gain).connect(ctx.destination);
        osc.start(ctx.currentTime + offset);
        osc.stop(ctx.currentTime + offset + 0.4);
      });
    }
    this._toast(`${this._t("timer_done")}: ${label}`);
  }

  _renderTimers() {
    if (!this._timers?.length) return "";
    const now = Date.now();
    return `<div class="timers">${this._timers.map((t) => `
      <div class="timer ${t.done ? "done" : ""}" data-tid="${t.id}">
        <ha-icon icon="${t.done ? "mdi:bell-ring" : "mdi:timer-outline"}"></ha-icon>
        <span class="t-label">${esc(t.label)}</span>
        <span class="t-left">${formatClock(Math.max(0, Math.round((t.end - now) / 1000)))}</span>
        <button class="icon-btn small" data-action="timer-cancel" data-tid="${t.id}"
          aria-label="${esc(this._t("close"))}"><ha-icon icon="mdi:close"></ha-icon></button>
      </div>`).join("")}</div>`;
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", {
      detail: { message }, bubbles: true, composed: true,
    }));
  }

  // ---------------------------------------------------------------- shopping

  _shoppingEntities() {
    if (Array.isArray(this._config?.shopping_lists)) return this._config.shopping_lists;
    const hass = this._hass;
    if (!hass) return [];
    return Object.keys(hass.states)
      .filter((id) => id.startsWith("todo.") &&
        (hass.entities?.[id]?.platform === "norish" || id.startsWith("todo.norish")))
      .sort((a, b) => this._listName(a).localeCompare(this._listName(b)));
  }

  _listName(entityId) {
    const name = this._hass?.states[entityId]?.attributes?.friendly_name || entityId;
    return name.replace(/^Norish\s+/, "");
  }

  async _loadShopping(lists) {
    const results = await Promise.all(lists.map(async (entityId) => {
      try {
        const res = await this._hass.callWS({ type: "todo/item/list", entity_id: entityId });
        return [entityId, res.items || []];
      } catch (err) {
        return [entityId, this._shop[entityId] || []];
      }
    }));
    this._shop = Object.fromEntries(results);
    this._render();
  }

  _renderShopping() {
    const lists = this._shoppingEntities();
    if (!lists.length) return `<div class="warning">${esc(this._t("no_lists"))}</div>`;
    const options = lists.map((id) =>
      `<option value="${esc(id)}" ${id === this._addTarget ? "selected" : ""}>${esc(this._listName(id))}</option>`).join("");
    const groups = lists.map((id) => {
      const items = this._shop[id] || [];
      const open = items.filter((i) => i.status !== "completed");
      const doneCount = items.length - open.length;
      if (!open.length && lists.length > 1 && id !== this._addTarget) return "";
      const rows = open.map((i) => `
        <button class="shop-item" data-action="shop-toggle" data-entity="${esc(id)}" data-uid="${esc(i.uid)}">
          <span class="check"></span><span class="shop-name">${esc(i.summary)}</span></button>`).join("");
      return `<section class="shop-list">
        <h3>${esc(this._listName(id))}<span class="shop-count">${open.length}</span></h3>
        ${rows || `<div class="nothing">${esc(this._t("nothing_needed"))}</div>`}
        ${doneCount ? `<div class="shop-done">${doneCount} ${esc(this._t("checked"))}</div>` : ""}
      </section>`;
    }).join("");
    return `<form class="shop-add">
        <input class="shop-input" type="text" enterkeyhint="done" autocomplete="off"
          placeholder="${esc(this._t("add_placeholder"))}" aria-label="${esc(this._t("add_placeholder"))}">
        ${lists.length > 1 ? `<select class="shop-target" aria-label="list">${options}</select>` : ""}
        <button class="action primary" type="submit"><ha-icon icon="mdi:plus"></ha-icon>${esc(this._t("add"))}</button>
      </form>
      ${groups || `<div class="empty-today"><ha-icon icon="mdi:check-circle-outline"></ha-icon>
        <span>${esc(this._t("nothing_needed"))}</span></div>`}`;
  }

  async _toggleShopItem(entityId, uid) {
    const item = (this._shop[entityId] || []).find((i) => i.uid === uid);
    if (!item) return;
    item.status = "completed";  // optimistic: disappears right away
    this._render();
    try {
      await this._hass.callService("todo", "update_item",
        { item: uid, status: "completed" }, { entity_id: entityId });
    } catch (err) {
      item.status = "needs_action";
      this._render();
      this._toast(this._t("failed"));
    }
  }

  async _addShopItem() {
    const input = this.shadowRoot.querySelector(".shop-input");
    const text = input?.value.trim();
    if (!text) return;
    const lists = this._shoppingEntities();
    const target = this.shadowRoot.querySelector(".shop-target")?.value || this._addTarget || lists[0];
    this._addTarget = target;
    input.value = "";
    try {
      await this._hass.callService("todo", "add_item", { item: text }, { entity_id: target });
    } catch (err) {
      input.value = text;
      this._toast(this._t("failed"));
    }
  }

  async _addRecipeToList(recipeId, button) {
    if (button) button.disabled = true;
    const data = { recipe_id: recipeId };
    if (this._servings?.[recipeId]) data.servings = this._servings[recipeId];
    try {
      await this._hass.callService("norish", "add_recipe_to_groceries", data);
      this._toast(this._t("added"));
    } catch (err) {
      this._toast(`${this._t("failed")}: ${err?.message || err}`);
    } finally {
      if (button) button.disabled = false;
    }
  }

  _render() {
    if (!this._config) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
      this.shadowRoot.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" && ev.target?.tagName !== "INPUT") this._onClick(ev);
        if (this._cook && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) {
          this._cook.step += ev.key === "ArrowRight" ? 1 : -1;
          this._render();
        }
      });
      this.shadowRoot.addEventListener("submit", (ev) => {
        ev.preventDefault();
        this._addShopItem();
      });
    }
    const view = this._config.view;
    const defaultTitle = { recipe: "", shopping: this._t("shopping") }[view];
    const title = this._config.title ?? (defaultTitle ?? this._t("title"));
    const shopping = view === "shopping";
    const entityId = shopping ? undefined : this._entityId();
    const state = entityId && this._hass?.states[entityId];
    const data = this._hass && entityId ? this._weekData(entityId, state) : undefined;
    const badge = data?.offline ? this._offlineBadge(data.lastSuccess) : "";
    let body;

    if (!this._hass) {
      body = "";
    } else if (shopping) {
      body = this._renderShopping();
    } else if (!data) {
      body = `<div class="warning">${esc(this._t("no_entity"))}</div>`;
    } else {
      const week = data.week;
      // tomorrow_after: from that time on, "today" means tomorrow
      const offset = this._tomorrowMode() && week.length > 1 && week[0].is_today ? 1 : 0;
      const days = Math.max(1, Math.min(7, Number(this._config.days) || 7));
      const hasAny = week.some((d) => (d.meals || []).length);
      const sel = this._selected;
      const selected = sel && this._findMeal(week, (m, d) =>
        m.recipe_id === sel.recipe && d.date === sel.date && m.type === sel.type);
      if (sel && !selected) this._selected = undefined;  // meal no longer planned
      const cook = this._cook && this._findMeal(week, (m, d) =>
        m.recipe_id === this._cook.recipe && d.date === this._cook.date && m.type === this._cook.type);
      if (this._cook && !cook) this._stopCooking();

      if (cook) {
        body = this._renderCook(cook.meal);
      } else if (selected) {
        body = this._renderRecipe(selected, view !== "recipe");
      } else if (view === "recipe") {
        const slot = String(this._config.slot || "").toUpperCase();
        const next = this._findMeal(week, (m, d) =>
          m.recipe_id && d.date >= week[offset].date &&
          (!slot || String(m.type).toUpperCase() === slot));
        body = next
          ? this._renderRecipe(next, false)
          : `<div class="empty-today"><ha-icon icon="mdi:silverware-fork-knife"></ha-icon>
              <span>${esc(this._t("no_recipe"))}</span></div>`;
      } else if (!hasAny && view !== "today") {
        body = `<div class="empty-week"><ha-icon icon="mdi:calendar-blank-outline"></ha-icon>
          <span>${esc(this._t("nothing_week"))}</span></div>`;
      } else if (view === "today") {
        body = this._renderToday(week[offset], offset === 1);
      } else if (view === "week") {
        body = this._renderWeek(week.slice(offset, days), offset);
      } else {
        body = this._renderToday(week[offset], offset === 1) +
          this._renderWeek(week.slice(offset + 1, days), offset + 1);
      }
    }

    const today = new Date().toLocaleDateString(
      this._hass?.locale?.language || this._hass?.language || "en",
      { weekday: "long", day: "numeric", month: "long" }
    );

    // Keep what is being typed in the shopping field across a re-render
    const input = this.shadowRoot.querySelector(".shop-input");
    const typed = input?.value || "";
    const focused = input && this.shadowRoot.activeElement === input;

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card class="${this._cook ? "cooking" : ""}">
        ${title ? `<div class="header">
          <div class="title"><ha-icon icon="mdi:chef-hat"></ha-icon>${esc(title)}</div>
          <div class="subtitle">${badge || esc(today)}</div></div>` : ""}
        <div class="content">${!title && badge ? `<div class="badge-row">${badge}</div>` : ""}${this._renderTimers()}${body}</div>
      </ha-card>`;
    const newInput = this.shadowRoot.querySelector(".shop-input");
    if (newInput && typed) newInput.value = typed;
    if (newInput && focused) newInput.focus();
    // Image not reachable (e.g. not cached yet) → show the slot placeholder
    this.shadowRoot.querySelectorAll("img").forEach((img) => {
      img.addEventListener("error", () => {
        img.parentElement.classList.add("placeholder", "broken");
        img.remove();
      }, { once: true });
    });
  }

  _stopCooking() {
    this._cook = undefined;
    this._releaseWakeLock();
  }

  _onClick(ev) {
    const path = ev.composedPath();
    if (path.some((el) => el.tagName === "A")) return;  // let links work normally
    const actionEl = path.find((el) => el.dataset?.action && el.dataset.action !== "back");
    const action = actionEl?.dataset.action;
    if (action === "cook") {
      const { rid, date, type } = actionEl.dataset;
      this._cook = { recipe: rid, date, type, step: 0 };
      this._requestWakeLock();
      this._render();
      this.shadowRoot.querySelector("ha-card")?.scrollIntoView({ block: "start" });
      return;
    }
    if (action === "cook-close") { this._stopCooking(); this._render(); return; }
    if (action === "cook-next" || action === "cook-prev") {
      this._cook.step += action === "cook-next" ? 1 : -1;
      this._render();
      return;
    }
    if (action === "timer") {
      this._startTimer(Number(actionEl.dataset.seconds), actionEl.dataset.label);
      return;
    }
    if (action === "timer-cancel") {
      this._timers = (this._timers || []).filter((t) => String(t.id) !== actionEl.dataset.tid);
      this._render();
      return;
    }
    if (action === "serv-dec" || action === "serv-inc") {
      const rid = actionEl.dataset.rid;
      const found = this._cache && this._findMeal(this._cache.week, (m) => m.recipe_id === rid);
      const base = Number(found?.meal.servings) || 1;
      const now = (this._servings[rid] || base) + (action === "serv-inc" ? 1 : -1);
      if (now >= 1 && now <= 99) {
        if (now === base) delete this._servings[rid];
        else this._servings[rid] = now;
      }
      this._render();
      return;
    }
    if (action === "to-list") { this._addRecipeToList(actionEl.dataset.rid, actionEl); return; }
    if (action === "shop-toggle") {
      this._toggleShopItem(actionEl.dataset.entity, actionEl.dataset.uid);
      return;
    }
    if (path.some((el) => el.tagName === "INPUT" || el.tagName === "SELECT" || el.tagName === "FORM")) return;
    if (path.some((el) => el.dataset?.action === "back")) {
      this._selected = undefined;
      this._render();
      return;
    }
    const target = path.find((el) => el.dataset?.recipe);
    if (target) {
      const { recipe, date, type } = target.dataset;
      this._selected = { recipe, date, type };
      this._render();
      // Long list: make sure the opened recipe starts in view
      const card = this.shadowRoot.querySelector("ha-card");
      if (card && card.getBoundingClientRect().top < 0) card.scrollIntoView({ block: "start" });
      return;
    }
    const entityId = this._entityId();
    if (!entityId || !path.some((el) => el.classList?.contains("header"))) return;
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
  .offline {
    display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px 2px 6px;
    border-radius: 999px; font-size: 0.85em; white-space: nowrap;
    color: var(--warning-color, #e0a000);
    background: color-mix(in srgb, var(--warning-color, #e0a000) 14%, transparent);
  }
  .offline ha-icon { --mdc-icon-size: 16px; }
  .badge-row { display: flex; justify-content: flex-end; margin-bottom: -6px; }

  /* Recipe view */
  .recipe { display: flex; flex-direction: column; gap: 20px; }
  .recipe-main, .recipe-side { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .hero {
    position: relative; width: 100%; aspect-ratio: 16 / 9; max-height: 300px;
    border-radius: 14px; overflow: hidden; isolation: isolate;
  }
  .hero .tile-img.placeholder ha-icon { --mdc-icon-size: 56px; margin-bottom: 50px; }
  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .day-chip { background: rgba(255, 255, 255, 0.22); padding-left: 9px; }
  .hero-name {
    font-size: 1.5em; font-weight: 600; line-height: 1.2;
    text-shadow: 0 1px 3px rgba(0,0,0,0.45);
  }
  .back {
    position: absolute; top: 10px; left: 10px; z-index: 1;
    width: 38px; height: 38px; border: none; border-radius: 50%; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    background: rgba(0, 0, 0, 0.45); color: #fff; backdrop-filter: blur(6px);
  }
  .back:hover { background: rgba(0, 0, 0, 0.65); }
  .back ha-icon { --mdc-icon-size: 22px; }
  .meta { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); }
  .meta-item { display: flex; align-items: center; gap: 10px; }
  .meta-item ha-icon {
    flex: 0 0 auto; color: var(--primary-color); padding: 8px; border-radius: 50%;
    background: color-mix(in srgb, var(--primary-color) 14%, transparent);
    --mdc-icon-size: 20px;
  }
  .meta-label { font-weight: 600; color: var(--primary-text-color); font-size: 0.9em; }
  .meta-value { color: var(--secondary-text-color); font-size: 0.9em; }
  .meta-value.changed { color: var(--primary-color); font-weight: 600; }
  .stepper { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
  .stepper .meta-value { min-width: 1.5em; text-align: center; }
  .step-btn {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; padding: 0; border: none; border-radius: 50%; cursor: pointer;
    color: var(--primary-text-color); background: var(--secondary-background-color);
  }
  .step-btn[disabled] { opacity: 0.4; cursor: default; }
  .meta-item .step-btn ha-icon { padding: 0; background: none; color: inherit; --mdc-icon-size: 16px; }
  .day-heading {
    margin: 0 0 8px; font-weight: 600; font-size: 0.95em; color: var(--primary-color);
    text-transform: uppercase; letter-spacing: 0.04em;
  }
  .description { margin: 0; color: var(--secondary-text-color); line-height: 1.5; }
  section h3 {
    display: flex; align-items: center; gap: 8px; margin: 0 0 10px;
    font-size: 1.05em; font-weight: 600; color: var(--primary-text-color);
  }
  section h3 ha-icon { color: var(--primary-color); --mdc-icon-size: 20px; }
  .ingredients, .steps { list-style: none; margin: 0; padding: 0; }
  /* Amount column as wide as the longest amount, names aligned */
  .ingredients { display: grid; grid-template-columns: auto 1fr; column-gap: 14px; }
  .ingredients li {
    grid-column: 1 / -1; display: grid; grid-template-columns: subgrid; padding: 7px 2px;
    border-bottom: 1px dashed var(--divider-color); color: var(--primary-text-color);
  }
  .ingredients li:last-child { border-bottom: none; }
  .qty { font-weight: 600; text-align: right; white-space: nowrap; color: var(--primary-text-color); }
  .ing { min-width: 0; }
  strong { font-weight: 600; }
  .steps li {
    display: grid; grid-template-columns: 28px 1fr; gap: 12px; align-items: start;
    padding: 6px 0; line-height: 1.55; color: var(--primary-text-color);
  }
  .num {
    width: 28px; height: 28px; border-radius: 50%; font-size: 0.85em; font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    color: var(--primary-color); background: color-mix(in srgb, var(--primary-color) 14%, transparent);
  }
  .ingredients li.sub, .steps li.sub {
    display: block; border-bottom: none; padding: 12px 0 2px;
    font-weight: 600; color: var(--secondary-text-color);
    font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.05em;
  }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; }
  .action {
    display: inline-flex; align-items: center; gap: 6px; padding: 8px 14px;
    border: none; border-radius: 999px; cursor: pointer; text-decoration: none;
    font: inherit; font-weight: 500;
    color: var(--primary-color); background: color-mix(in srgb, var(--primary-color) 12%, transparent);
  }
  .action.primary { color: var(--text-primary-color, #fff); background: var(--primary-color); }
  .action:disabled { opacity: 0.5; cursor: default; }
  .action ha-icon { --mdc-icon-size: 18px; }
  .icon-btn {
    display: inline-flex; align-items: center; justify-content: center; flex: 0 0 auto;
    width: 40px; height: 40px; border: none; border-radius: 50%; cursor: pointer;
    color: var(--primary-text-color); background: var(--secondary-background-color);
  }
  .icon-btn.small { width: 28px; height: 28px; }
  .icon-btn.small ha-icon { --mdc-icon-size: 16px; }

  /* Cook mode */
  .cook { display: flex; flex-direction: column; gap: 18px; min-height: 340px; }
  .cook-top { display: flex; align-items: center; gap: 12px; }
  .cook-title { flex: 1; min-width: 0; font-weight: 600; font-size: 1.1em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--primary-text-color); }
  .cook-count { color: var(--secondary-text-color); white-space: nowrap; font-size: 0.95em; }
  .cook-progress { height: 6px; border-radius: 3px; background: var(--secondary-background-color); overflow: hidden; }
  .cook-progress span { display: block; height: 100%; background: var(--primary-color); transition: width 0.3s ease; }
  .cook-section { font-size: 0.85em; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
    color: var(--secondary-text-color); margin-bottom: -10px; }
  .cook-step { flex: 1; font-size: clamp(1.25em, 3.2cqi, 2.1em); line-height: 1.45; color: var(--primary-text-color); }
  .timer-chips { display: flex; flex-wrap: wrap; gap: 8px; }
  .timer-chip {
    display: inline-flex; align-items: center; gap: 6px; padding: 10px 16px; border-radius: 999px;
    border: 2px solid var(--primary-color); background: none; color: var(--primary-color);
    font: inherit; font-weight: 600; font-size: 1.05em; cursor: pointer;
  }
  .cook-ing summary { cursor: pointer; color: var(--secondary-text-color); font-weight: 500; padding: 4px 0; }
  .cook-ing .ingredients { margin-top: 8px; }
  .cook-nav { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .nav-btn {
    display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-height: 56px;
    border: none; border-radius: 16px; cursor: pointer; font: inherit; font-size: 1.1em; font-weight: 600;
    color: var(--primary-text-color); background: var(--secondary-background-color);
  }
  .nav-btn.primary { color: var(--text-primary-color, #fff); background: var(--primary-color); }
  .nav-btn:disabled { opacity: 0.4; cursor: default; }

  /* Timers */
  .timers { display: flex; flex-direction: column; gap: 6px; }
  .timer {
    display: flex; align-items: center; gap: 10px; padding: 8px 8px 8px 14px; border-radius: 14px;
    background: color-mix(in srgb, var(--primary-color) 12%, transparent); color: var(--primary-text-color);
  }
  .timer ha-icon { color: var(--primary-color); }
  .t-label { flex: 1; min-width: 0; }
  .t-left { font-variant-numeric: tabular-nums; font-weight: 700; font-size: 1.2em; }
  .timer.done { background: color-mix(in srgb, var(--error-color) 18%, transparent); animation: pulse 1s ease-in-out infinite; }
  .timer.done ha-icon { color: var(--error-color); }
  @keyframes pulse { 50% { opacity: 0.6; } }

  /* Shopping list */
  .shop-add { display: flex; gap: 8px; flex-wrap: wrap; }
  .shop-input {
    flex: 1 1 160px; min-width: 0; padding: 10px 14px; border-radius: 999px; font: inherit;
    border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color);
  }
  .shop-target {
    padding: 8px 10px; border-radius: 999px; font: inherit;
    border: 1px solid var(--divider-color); background: var(--card-background-color); color: var(--primary-text-color);
  }
  .shop-list h3 { justify-content: space-between; }
  .shop-count {
    margin-left: auto; min-width: 24px; padding: 0 8px; border-radius: 999px; font-size: 0.8em; line-height: 22px;
    text-align: center; background: var(--secondary-background-color); color: var(--secondary-text-color);
  }
  .shop-item {
    display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px 4px; border: none;
    border-bottom: 1px dashed var(--divider-color); background: none; cursor: pointer; text-align: left;
    font: inherit; color: var(--primary-text-color);
  }
  .shop-item:last-of-type { border-bottom: none; }
  .check { flex: 0 0 22px; height: 22px; border-radius: 50%; border: 2px solid var(--primary-color); }
  .shop-item:hover .check { background: color-mix(in srgb, var(--primary-color) 20%, transparent); }
  .shop-name { min-width: 0; }
  .shop-done { color: var(--secondary-text-color); font-size: 0.85em; padding-top: 6px; }
  /*
   * Side by side for landscape screens: forced with layout: horizontal,
   * automatic from 600px wide. Two columns (photo + ingredients | steps),
   * three from 900px (photo | ingredients | steps) so it fits without scrolling.
   */
  .recipe.horizontal {
    display: grid; gap: 16px 28px; align-items: start;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
    grid-template-areas: "main side" "ing side";
  }
  .recipe.horizontal .recipe-main { grid-area: main; }
  .recipe.horizontal .recipe-ing { grid-area: ing; }
  .recipe.horizontal .recipe-side { grid-area: side; }
  .recipe.horizontal .hero { aspect-ratio: 2 / 1; max-height: 240px; }
  .recipe.horizontal .ingredients li { padding: 5px 2px; }
  @container (min-width: 600px) {
    .recipe.auto {
      display: grid; gap: 16px 28px; align-items: start;
      grid-template-columns: minmax(0, 1fr) minmax(0, 1.15fr);
      grid-template-areas: "main side" "ing side";
    }
    .recipe.auto .recipe-main { grid-area: main; }
    .recipe.auto .recipe-ing { grid-area: ing; }
    .recipe.auto .recipe-side { grid-area: side; }
    .recipe.auto .hero { aspect-ratio: 2 / 1; max-height: 240px; }
    .recipe.auto .ingredients li { padding: 5px 2px; }
  }
  @container (min-width: 900px) {
    .recipe.auto, .recipe.horizontal {
      grid-template-columns: minmax(0, 1fr) minmax(0, 0.9fr) minmax(0, 1.3fr);
      grid-template-areas: "main ing side";
    }
    .recipe.auto .hero, .recipe.horizontal .hero { aspect-ratio: 4 / 3; max-height: none; }
  }

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
