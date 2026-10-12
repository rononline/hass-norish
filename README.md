# Norish Home Assistant Integration

[![Version](https://img.shields.io/github/v/release/rononline/hass-norish?label=version&color=blue)](https://github.com/rononline/hass-norish/releases)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![HA Version](https://img.shields.io/badge/Home%20Assistant-2024.11%2B-blue.svg)](https://www.home-assistant.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Validate](https://github.com/rononline/hass-norish/actions/workflows/validate.yaml/badge.svg)](https://github.com/rononline/hass-norish/actions/workflows/validate.yaml)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-caps3n-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/caps3n)

A full-featured Home Assistant integration for [Norish](https://github.com/norish-recipes/norish) — the open-source recipe and meal planning app.

> **This is a fork** of [Caps3n/hass-norish](https://github.com/Caps3n/hass-norish), tracking
> upstream and adding a few fixes of its own. Report issues with *this* fork here; for the
> original integration, please use the upstream repository.

> Connects your Norish instance to Home Assistant, giving you meal sensors, a shopping list, a calendar, recipe images, and video support — all in one integration.

---

## ✨ Features

### 🍳 Meal Sensors
- **6 sensors**: All meals today, Breakfast, Lunch, Dinner, Snack, Week Planner
- Automatic **recipe image** display via `entity_picture`
- **Video support** — autoplay, loop, muted (just like in the Norish app)
- Attributes include recipe name, type, image URL, and recipe ID

### 📅 Week Planner Sensor
- 7-day overview of all planned meals
- Per-day attributes: `mo`, `tu`, `we`, `th`, `fr`, `sa`, `su`
- Highlights today and weekends
- Sorted by meal type (Breakfast → Lunch → Dinner → Snack)
- **Past meals auto-hidden** — meals are removed from today's view 6 h after their default time slot (`MEAL_HIDE_AFTER` in `sensor.py`)

### 📆 Calendar
- Native Home Assistant calendar entity
- One event per meal with correct time slots
- Full date-range support

### 🛒 Shopping List
- Native Home Assistant Todo list entity — one per store, plus "Unsorted"
- Displays items with quantity and unit
- Add, check off and delete items; also by voice via Assist
  ("add 2 milk to the shopping list" → 2 × milk, filed under that store)

### ⚡ Realtime Updates
- Listens to Norish's WebSocket: changes in the Norish app show up in
  Home Assistant within seconds
- While connected, polling only runs every 30 minutes as a safety net;
  without the WebSocket the integration simply polls as before

### 🧩 Dashboard Card
- `custom:norish-card` ships with the integration — no extra resource needed
- Today's meals as photo tiles, the coming days as a list
- Tap a meal for the full recipe: times, servings, ingredients and steps
- **Servings**: − / + recalculates the ingredient amounts (and what
  "Add to shopping list" puts on the list)
- **Cook mode**: one step at a time in large type, timers for durations in
  a step ("8 tot 10 minuten"), screen stays awake
- **Shopping list view**: lists per store, tap to check off, add items
- "Add to shopping list" puts a recipe's ingredients on the list
- Landscape layout for kitchen displays, light/dark theme, NL/EN/DE
- Keeps showing the last plan (with an "Offline" badge) during outages
- `tomorrow_after: "20:00"` — in the evening, show tomorrow's meals instead

### 🗓️ Plan Meals from Home Assistant
- Create an event in the Norish calendar: a title that matches a recipe
  plans that recipe, anything else becomes a note ("Uit eten")
- The meal comes from a prefix ("Diner: Pasta") or the start time
- Deleting an event removes it from Norish

### 🗣️ Assist: "Wat eten we vanavond?"
[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frononline%2Fhass-norish%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fnorish%2Fwhats_for_dinner.yaml)

Import the blueprint, create an automation from it and ask Assist
"wat eten we vanavond?" or "wat eten we morgen?". Sentences and answers
are inputs, so any language works.

### 🧺 Assist: a recipe on the shopping list
[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frononline%2Fhass-norish%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fnorish%2Frecipe_to_groceries.yaml)

"Zet de ingrediënten van lasagne op de boodschappenlijst" looks the recipe up
in Norish by name and puts its ingredients on the list. "Zet melk op de
boodschappenlijst" still adds just milk.

### ⏰ Reminder when nothing is planned
[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Frononline%2Fhass-norish%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fnorish%2Fmeal_reminder.yaml)

At a time you choose, checks whether today's (or tomorrow's) dinner is planned
in Norish and otherwise runs your actions – a notification, a message on a
speaker. A note like "Uit eten" counts as planned.

### 🔔 Events for Automations
Every change Norish pushes fires a `norish_change` event:

| `kind` | Extra data |
|---|---|
| `groceries.created` / `groceries.updated` / `groceries.deleted` | `names` |
| `calendar.item_created` / `item_updated` / `item_moved` / `item_deleted` | `date`, `slot`, `title` |
| `stores.created` / `stores.updated` / `stores.deleted` | — |

```yaml
triggers:
  - trigger: event
    event_type: norish_change
    event_data:
      kind: groceries.created
actions:
  - action: notify.mobile_app_phone
    data:
      message: "Op de boodschappenlijst: {{ trigger.event.data.names | join(', ') }}"
```

### 🩺 Status and Diagnostics
- Diagnostic entities "Norish Realtime" and "Norish Last Update"
- Download diagnostics (credentials redacted) from the integration page
- A repair notice explains when realtime updates cannot connect

### 📷 Camera Entities
- One camera entity per meal type (Breakfast, Lunch, Dinner, Snack)
- Locally cached images for fast display
- Fallback to remote image if cache is empty

### 🎬 Media Player Entities
- One media player per meal type
- Shows recipe video when available
- Compatible with dashboard `media-player` cards

### 🌍 Multilingual
- 6 languages: 🇳🇱 Dutch · 🇩🇪 German · 🇬🇧 English · 🇫🇷 French · 🇪🇸 Spanish · 🇮🇹 Italian

---

## 📸 Screenshots

### Week Planner
![Week Planner](https://github.com/Caps3n/hass-norish/blob/main/images/week_planner.png?raw=true)

### Calendar
![Calendar](https://github.com/Caps3n/hass-norish/blob/main/images/calendar.png?raw=true)

### Todo / Shopping List
![Shopping List](https://github.com/Caps3n/hass-norish/blob/main/images/todo.png?raw=true)

---

## 🚀 Installation

### Option 1: HACS (Recommended)

1. Open **HACS** in Home Assistant
2. Go to **Integrations**
3. Click the **⋮ menu** (top right) → **Custom repositories**
4. Add: `https://github.com/rononline/hass-norish` → Category: `Integration`
5. Search for **"Norish"** and click **Install**
6. Restart Home Assistant

### Option 2: Manual

1. Download the [latest release](https://github.com/rononline/hass-norish/releases)
2. Copy the `norish` folder into your `config/custom_components/` directory
3. Restart Home Assistant

---

## ⚙️ Configuration

1. Go to **Settings → Devices & Services**
2. Click **+ Add Integration**
3. Search for **"Norish"**
4. Enter:
   - **Server URL** — e.g. `https://norish.yourdomain.com`
   - **API Key** — find this in your Norish settings under **API Keys**
5. Click **Submit**

### API key usage

Norish allows 500 requests per API key and only resets that counter after
the key has been idle for a full hour. The integration therefore:

- fetches calendar and groceries in **one** request per update
- makes **no requests between 03:00 and 04:05**, so the counter resets nightly
- recognises Norish's request limit and pauses instead of asking you to
  re-authenticate; the last data stays visible meanwhile

The shortest poll interval is 5 minutes (Options).

### Actions

`norish.add_recipe_to_groceries` puts a recipe's ingredients on the shopping
list — by `recipe_id`, by `recipe` name (best match in Norish), or the recipes
planned on a `date` (default today), optionally one `slot`, for a number of
`days`. `servings` scales the amounts:

```yaml
action: norish.add_recipe_to_groceries
data:
  days: 7        # the whole coming week
```

```yaml
action: norish.add_recipe_to_groceries
data:
  recipe: Lasagne
  servings: 6
```

### Updating your API Key

Normally the integration handles this itself (see Troubleshooting). If your API key is deleted or expires without stored credentials, Home Assistant will show a **"Reconfigure"** notification automatically. Click it (or use the ⋮ menu on the integration card → **Reconfigure**) to enter a new key — no need to delete and re-add the integration.

---

## 📊 Entities

### Sensors

| Entity | Description |
|--------|-------------|
| `sensor.norish_meals_today` | All meals for today |
| `sensor.norish_breakfast` | Today's breakfast |
| `sensor.norish_lunch` | Today's lunch |
| `sensor.norish_dinner` | Today's dinner |
| `sensor.norish_snack` | Today's snack |
| `sensor.norish_week_planner` | 7-day meal overview |

Each sensor includes: meal name (state), `image_url`, `recipe_id`, `meal_count`, `meals`, `raw_data`.
The week planner also has `stale` (true while it shows the last known plan during an outage)
and `last_success`.

### Diagnostics

| Entity | Description |
|--------|-------------|
| `binary_sensor.norish_realtime` | On while the WebSocket to Norish is connected |
| `sensor.norish_last_update` | Time of the last successful update from Norish |

### Calendar

| Entity | Description |
|--------|-------------|
| `calendar.norish_meal_calendar` | Meal calendar — also lets you plan meals and notes |

### Todo

| Entity | Description |
|--------|-------------|
| `todo.norish_unsorted` | Groceries without a store |
| `todo.norish_<store>` | One list per Norish store (e.g. `todo.norish_albert_heijn`) |

### Cameras

| Entity | Description |
|--------|-------------|
| `camera.norish_breakfast_image` | Breakfast recipe image |
| `camera.norish_lunch_image` | Lunch recipe image |
| `camera.norish_dinner_image` | Dinner recipe image |
| `camera.norish_snack_image` | Snack recipe image |

### Media Players

| Entity | Description |
|--------|-------------|
| `media_player.norish_breakfast_video` | Breakfast recipe video |
| `media_player.norish_lunch_video` | Lunch recipe video |
| `media_player.norish_dinner_video` | Dinner recipe video |
| `media_player.norish_snack_video` | Snack recipe video |

---

## 🎨 Dashboard Examples

### Norish card (recommended)

```yaml
type: custom:norish-card
view: full          # full | today | week | recipe | shopping
# slot: dinner      # view: recipe — always show the next dinner
# layout: auto      # auto | horizontal (landscape screen) | vertical
# days: 7
# norish_url: https://norish.yourdomain.com   # "Open in Norish" link
# tomorrow_after: "20:00"   # from 20:00 show tomorrow instead of today
```

For a kitchen display, put `view: recipe` in a **Panel (single card)** view
so the card gets the full width (three columns from 900 px).

### Simple image card

```yaml
type: picture-entity
entity: sensor.norish_lunch
show_name: true
show_state: true
```

### Looping video (Norish style)

```yaml
type: markdown
content: |
  <video autoplay loop muted playsinline
         style="width:100%;height:400px;object-fit:cover;border-radius:12px;">
    <source src="{{ state_attr('sensor.norish_lunch', 'raw_data')[0]['image'] }}" type="video/mp4">
  </video>
```

### 2×2 meal grid

```yaml
type: grid
columns: 2
cards:
  - type: picture-entity
    entity: sensor.norish_breakfast
  - type: picture-entity
    entity: sensor.norish_lunch
  - type: picture-entity
    entity: sensor.norish_dinner
  - type: picture-entity
    entity: sensor.norish_snack
```

### Week overview (with today highlight)

```yaml
type: markdown
content: |
  {% set week = state_attr('sensor.norish_week_planner', 'week_data') %}
  {% for day in week %}
  <div style="background:{% if day.is_today %}#1e3a5f{% else %}#1c1c1c{% endif %};
              border-radius:10px;padding:12px;margin:6px 0;">
    <strong style="color:white;">{{ day.weekday }} · {{ day.date_formatted }}</strong>
    <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;">
    {% for meal in day.meals %}
      <div style="flex:1;min-width:80px;height:70px;border-radius:6px;overflow:hidden;position:relative;">
        {% if meal.image %}
          <img src="{{ meal.image }}" style="width:100%;height:100%;object-fit:cover;">
        {% endif %}
        <div style="position:absolute;bottom:0;left:0;right:0;background:rgba(0,0,0,.5);
                    color:white;font-size:10px;padding:2px 4px;">{{ meal.type }}</div>
      </div>
    {% endfor %}
    </div>
  </div>
  {% endfor %}
```

More examples in [DASHBOARD_BEISPIELE.yaml](DASHBOARD_BEISPIELE.yaml)

---

## 🗓️ Week Planner Attributes

```yaml
sensor.norish_week_planner:
  state: "5 days planned"
  attributes:
    days_planned: 5
    total_meals: 14

    mo:
      date: "2026-03-23"
      weekday: "Monday"
      is_today: true
      is_weekend: false
      meals:
        - name: "Oatmeal"
          type: "BREAKFAST"
          image: "/local/norish_images/..."
          recipe_id: "abc123"
      meal_count: 1
      has_meals: true

    tu: { ... }
    we: { ... }
    # ...
    week_data: [...]
```

---

## 🔧 Troubleshooting

**"Request limit reached" in the log / no updates for a while**
- Norish allows 500 requests per API key and resets the counter after an hour
  without requests. The integration pauses until Norish allows requests again
  and keeps showing the last data (see [API key usage](#api-key-usage)).
- Raise the poll interval in the integration's **Options** if this happens often.

**Home Assistant asks to re-authenticate**
- Only happens after 3 rejected requests in a row that are *not* the request
  limit — usually a deleted or expired key.
- With your Norish e-mail and password stored (optional, in setup or
  Reconfigure) the integration creates a new key by itself.
- Otherwise: **Settings → Devices & Services → Norish → ⋮ → Reconfigure** and
  enter a new key from Norish under **API Keys**.

**"Norish realtime updates are not available" (Repairs) / Realtime stays off**
- Home Assistant could not open the WebSocket at `wss://<your norish>/trpc`.
  Everything keeps working with regular polling; only instant updates are missing.
- Behind a reverse proxy, forward WebSocket upgrades. For nginx:

  ```nginx
  location / {
      proxy_pass http://norish:3000;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
      proxy_set_header Host $host;
      proxy_read_timeout 1h;
  }
  ```

- The notice disappears by itself once the connection works.

**No meals shown / "No meals planned"**
- Check the integration is active (not showing a setup error)
- Past meals are automatically hidden: Breakfast after 08:30, Lunch after 12:30, Snack after 15:30, Dinner after 18:30
- Future days always show all meals regardless of time

**No images displayed**
- Check that the recipe has a photo in Norish
- Verify the images are accessible from your Home Assistant host
- The card and camera entities use the first photo of a recipe's gallery

**The card does not appear / shows an old version**
- The card is registered automatically; reload the browser (or clear the
  Companion app's frontend cache) after an update.

**Connection error on setup**
- Confirm the Server URL is reachable from Home Assistant (use `https://` when
  Norish runs behind a reverse proxy with a certificate)
- Verify your API key is correct (Settings → Norish → API Keys)
- Check firewall / reverse proxy settings

**Enable debug logging**

Add to `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.norish: debug
```

---

## 🆕 What's New in v1.10.0

- **Servings** in the card: − / + recalculates ingredient amounts
- **Tomorrow in the evening**: `tomorrow_after` shows tomorrow's meals from a set time
- **Blueprints**: a recipe on the shopping list by voice, and a reminder when nothing is planned
- `norish.add_recipe_to_groceries` accepts a recipe **name** and **servings**

Earlier: cook mode, shopping list view, planning from Home Assistant and
`norish_change` events (1.9.0), realtime updates (1.8.0).

See [CHANGELOG.md](CHANGELOG.md) for the full version history.

---

## 📚 Documentation

- [CHANGELOG.md](CHANGELOG.md) — Version history

The German guides below come from the original project and describe its
older versions; this README is the up-to-date reference.

- [INSTALLATION.md](INSTALLATION.md) — Detailed installation guide (German)
- [DASHBOARD_BEISPIELE.yaml](DASHBOARD_BEISPIELE.yaml) — Dashboard templates
- [WOCHENPLAN_DASHBOARDS.md](WOCHENPLAN_DASHBOARDS.md) — Week planner dashboard examples
- [VIDEO_SUPPORT.md](VIDEO_SUPPORT.md) — Video integration guide

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Credits

- Created by [@Caps3n](https://github.com/Caps3n)
- Built for [Norish](https://github.com/norish-recipes/norish)
- Made with ❤️ for the Home Assistant community

## 🔗 Links

- [Norish App](https://github.com/norish-recipes/norish)
- [Home Assistant](https://www.home-assistant.io/)
- [HACS](https://hacs.xyz/)
- [Report a Bug](https://github.com/rononline/hass-norish/issues)
- [Request a Feature](https://github.com/rononline/hass-norish/issues)
