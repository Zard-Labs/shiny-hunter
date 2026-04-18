# Seed Templates — Community Automation Templates

This directory contains **pre-built automation templates** that ship with ShinyStarter.  
When a new user installs the app and starts it for the first time, every template here is
automatically seeded into the database along with its reference screenshot images.

---

## How It Works

On first run (empty database), the backend scans each subdirectory under `seed_templates/`.
For every folder that contains a valid `definition.json`:

1. A new `automation_template` row is inserted (with a fresh UUID).
2. `template_image` rows are created for each entry in the `images` array.
3. The screenshot files from the `images/` subfolder are **copied** into a
   unique per-template directory (`templates/<new-uuid>/`).

Because each seeded template gets its own UUID and its own copy of the images,
user edits never affect the seed data — and seed images never collide with
user-captured images.

---

## Directory Structure

```
seed_templates/
├── README.md                    ← this file
├── 01_starter_hunt/
│   ├── definition.json          ← template metadata + step definition + image list
│   └── images/
│       ├── title_screen.png          (grayscale — used for template matching)
│       ├── title_screen_color.png    (color — shown in the UI as reference)
│       ├── load_game.png
│       ├── load_game_color.png
│       └── ...
└── 02_magikarp_hunt/
    ├── definition.json
    └── images/
        ├── karp_purchase.png
        ├── karp_purchase_color.png
        └── ...

> **Note:** Directories are sorted alphabetically to determine seed order.
> The first template (by sort order) is set as the **active** template.
> Use numeric prefixes (e.g., `01_`, `02_`) to control the order.
```

---

## Contributing a New Template via Pull Request

Anyone can contribute a new shiny-hunt automation! Here's how:

### 1. Create a new folder

Pick a short, descriptive name using `snake_case`:

```
seed_templates/my_awesome_hunt/
```

### 2. Add reference screenshots

Create an `images/` subfolder and add your screenshots:

```
seed_templates/my_awesome_hunt/images/
├── title_screen.png           ← grayscale (what OpenCV uses for matching)
├── title_screen_color.png     ← color (what users see in the UI)
├── some_other_screen.png
├── some_other_screen_color.png
└── ...
```

**Image guidelines:**
- Grayscale files (`{key}.png`) are used by the OpenCV template matcher
- Color files (`{key}_color.png`) are displayed in the UI as reference previews
- Both are optional — if only grayscale exists, it's used for the preview too
- Images should be captured from the actual game at the resolution your capture card produces

### 3. Create `definition.json`

This file contains everything the automation engine needs:

```json
{
  "name": "My Awesome Hunt",
  "description": "A brief description of the hunt strategy.",
  "game": "Pokemon FireRed",
  "pokemon_name": "Eevee",
  "definition": {
    "version": 1,
    "detection": {
      "method": "yellow_star_pixels",
      "zone": { "upper_x": 264, "upper_y": 109, "lower_x": 312, "lower_y": 151 },
      "threshold": 20,
      "color_bounds": {
        "lower_hsv": [20, 100, 150],
        "upper_hsv": [35, 255, 255]
      }
    },
    "soft_reset": {
      "hold_duration": 0.5,
      "wait_after": 3.0,
      "max_retries": 3
    },
    "steps": [
      {
        "name": "BOOT",
        "display_name": "Boot Game",
        "type": "navigate",
        "cooldown": 0.6,
        "rules": [
          {
            "condition": { "type": "template_match", "template": "title_screen", "threshold": 0.80 },
            "actions": [{ "type": "press_button", "button": "A" }]
          }
        ],
        "default_action": [{ "type": "press_button", "button": "A" }]
      }
    ]
  },
  "images": [
    {
      "key": "title_screen",
      "label": "Title Screen",
      "description": "The game's main title/start screen",
      "threshold": 0.80
    }
  ]
}
```

**Key fields:**
| Field | Description |
|-------|-------------|
| `name` | Display name shown in the template library |
| `description` | Brief explanation of the hunt strategy |
| `game` | Game title (e.g. "Pokemon FireRed", "Pokemon Emerald") |
| `pokemon_name` | Target Pokemon or category (e.g. "Charmander", "Starters") |
| `definition.steps` | The state-machine steps that drive the automation |
| `definition.detection` | Shiny detection configuration |
| `images[].key` | Must match the filename (without `.png`) in `images/` |
| `images[].threshold` | OpenCV template match confidence threshold (0.0–1.0) |

### 4. Test locally

1. Delete your local `backend/shiny_hunter.db`
2. Restart the backend server
3. Verify your template appears in the Template Library with all images

### 5. Submit your PR

- Include the `definition.json` and all image files
- Describe the hunt strategy and what game/Pokemon it targets
- Screenshots of the template working are appreciated!

---

## Tips

- **Export an existing template** as a starting point:
  `GET /api/automation-templates/{id}/export` returns a JSON you can save as `definition.json`
- **The `images[].key`** in `definition.json` must match the filenames in the `images/` folder
  (e.g., key `"title_screen"` → `images/title_screen.png` and `images/title_screen_color.png`)
- Reference images serve as **visual guides** — users will recapture them for their own
  capture card/resolution, but having references helps them know what screen to capture
