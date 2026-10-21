# G-CATS app design

> ## Code layout
> 
> ```
> run_gcats.py      start here
> gcats/
>   app.py          main window, title bar, page rail, logging
>   config.py       all settings, preset save/load
>   gamepad.py      reads the gamepad
>   mapping.py      dead-zone, circle-to-square, scale
>   stimuli.py      finds media files, sets order
>   media.py        image / video / audio players
>   overlay.py      draws the rating grid and cursor
>   runner.py       fullscreen session
>   logger.py       writes CSV and JSON files
>   theme.py        colours and styles
>   pages/          one file per setup page
> ```

## 1. Start-up

|  |  | Code |
|---|---|---|
| Launch | `python run_gcats.py` or `python -m gcats` | [run_gcats.py](run_gcats.py), [gcats/\_\_main\_\_.py](gcats/__main__.py) |
| Logging | Messages go to the console and `~/.gcats/gcats.log` | `_setup_logging()` in [gcats/app.py](gcats/app.py) |
| Splash | Logo shows for 1.4 s | `SplashScreen`, `run()` in [gcats/app.py](gcats/app.py) |
| Main window | Builds settings, gamepad and pages | `MainWindow.__init__` in [gcats/app.py](gcats/app.py) |

## 2. Main window

|  |  | Code |
|---|---|---|
| `TitleBar` | Drag to move, minimise, close | [gcats/app.py](gcats/app.py) |
| `StageRow` | One rail entry; click to jump to that page | [gcats/app.py](gcats/app.py) |
| `MainWindow.goto()` | Shows a page and colours the rail | [gcats/app.py](gcats/app.py) |
| `MainWindow.next_page()` | Moves to the next page, or starts the session after the last one | [gcats/app.py](gcats/app.py) |
| `MainWindow.start_session()` | Orders the stimuli and opens the fullscreen window | [gcats/app.py](gcats/app.py) |
| `MainWindow._show_data_saved()` / `_restart()` | End screen: run again or quit | [gcats/app.py](gcats/app.py) |

## 3. Shared objects

Every page and the session window share the same two objects.

|  |  | Code |
|---|---|---|
| `Config` | All settings for the session | [gcats/config.py](gcats/config.py) |
| `Gamepad` | The connected controller and its settings | [gcats/gamepad.py](gcats/gamepad.py) |

`Gamepad.apply(cfg)` copies stick, button, dead-zone and scale settings from `Config` into the gamepad. Call it after changing any of those.

## 4. Setup pages

The order is set by `SEQUENCE` in [gcats/pages/\_\_init\_\_.py](gcats/pages/__init__.py).
All pages extend `Page` in [gcats/pages/base.py](gcats/pages/base.py):

- `build(layout)` adds the page's widgets (runs once)
- `on_enter()` runs each time the page is shown and fills widgets from `Config`
- `on_leave()` runs on Continue and writes widget values into `Config`
- `done` is the signal that tells `MainWindow` to move on

|  |  |  | Writes to `Config` |
|---|---|---|---|
| 1 | Startup | [startup.py](gcats/pages/startup.py) | nothing; checks packages and opens the gamepad |
| 2 | Participant | [participant.py](gcats/pages/participant.py) | `participant_id`, `session`, `age`, `gender` |
| 3 | Stimuli | [stimuli_page.py](gcats/pages/stimuli_page.py) | `stimuli`, `order`, `image_duration`, `media_aspect`, `media_margin_percent` |
| 4 | Protocol | [protocol.py](gcats/pages/protocol.py) | `gap_kind`, `gap_duration`, `rating_mode`, `summary_when` |
| 5 | Configuration | [settings.py](gcats/pages/settings.py) | sampling, scale, mapping, look, labels; also saves `~/.gcats/default_preset.json` |
| 6 | Controls | [mapping.py](gcats/pages/mapping.py) | `axis_x`, `axis_y`, `btn_confirm`, `btn_lock` |
| 7 | Dead-zone | [deadzone.py](gcats/pages/deadzone.py) | `centre_x`, `centre_y`, `dead_zone` |
| 8 | Check | [verify.py](gcats/pages/verify.py) | `invert_y` |

## 5. Session (fullscreen)

`SessionWindow` in [gcats/runner.py](gcats/runner.py). A timer calls `tick()` every 4 ms (`TICK_MS`).

```
GAP --> [SUMMARY before] --> STIMULUS --> [SUMMARY after] --> GAP --> ... --> DONE
```

|---|---|---|
| GAP | `step_gap()` | Fixation cross or blank for `gap_duration`, then the next trial |
| STIMULUS | `begin_stimulus()`, `step_stimulus()` | Plays the media and records the stick |
| SUMMARY | `step_summary()` | Waits for the confirm button, saves one rating |
| DONE | `end_session()` | "Thank you" screen, then the window closes |

Every tick:
1. `pad.poll()` reads the stick.
2. The reading is added to the raw file (`log_raw`).
3. If the output interval has passed, it is also added to the continuous file (`log_continuous`).

Stopping: `end_session()`, `fail()`, Escape and closing the window all go through `_stop_and_save()`. It runs only once, so data is never written twice. `closeEvent()` sends `finished` once, and `MainWindow.session_over()` picks that up.

## 6. Stick reading → rating

[gcats/gamepad.py](gcats/gamepad.py) `Gamepad.poll()` uses the functions in [gcats/mapping.py](gcats/mapping.py):

```
raw_x, raw_y        stick, as pygame gives it
  subtract centre   resting position found on the Dead-zone page
  apply_dead_zone() small jitter near the centre counts as zero
  invert_y          flip up/down if needed
  map_coords()      circle_to_square() so corners can be reached (optional)
mapped_x, mapped_y  -1 .. 1
  to_scale()        stretch to axis_min .. axis_max
valence, arousal
```

All three pairs are saved in each row (`Reading` in [gamepad.py](gcats/gamepad.py)).

## 7. Media playback

[gcats/media.py](gcats/media.py). `make_player()` picks a player from the stimulus type. All three players have the same methods: `start`, `frame`, `finished`, `progress`, `media_rect`, `stop`.

| Player | Used for | Notes |
|---|---|---|
| `ImagePlayer` | images | Shown for `image_duration` seconds |
| `VideoPlayer` | video | ffpyplayer; frames shown on time even without sound output |
| `AudioPlayer` | audio | Runner draws a progress bar (`draw_time_bar`) |

`fit_rect()` works out where the media sits on screen (margin, aspect ratio, never enlarged). The grid in [gcats/overlay.py](gcats/overlay.py) (`draw()`, `response_rect()`) is centred on that rectangle.

## 8. Files on disk

| What | Where | Code |
|---|---|---|
| Raw, continuous CSV + config JSON | `data/<id>_S<n>_<time>_*` | `SessionLogger` in [gcats/logger.py](gcats/logger.py) |
| Default preset | `~/.gcats/default_preset.json` | `Config.save_as_default()` / `load_default()` |
| App log | `~/.gcats/gcats.log` (up to 4 files of 1 MB) | `_setup_logging()` in [gcats/app.py](gcats/app.py) |

Rows stay in memory during a trial and are written at the end of each trial (`SessionLogger.flush()`). Escape or a crash between trials loses nothing. A crash in the middle of a trial loses that trial only.

## 9. Debugging

| Problem | Look at |
|---|---|
| Anything | `~/.gcats/gcats.log`. Run with `GCATS_DEBUG=1` for state changes, pad settings and flushes |
| No gamepad found | `Gamepad.open()`, `StartupPage.look_for_pad()` |
| Cursor goes the wrong way | `invert_y` (Check page), `Gamepad.poll()` |
| Cursor can't reach corners | `joystick_mapping` → `circle_to_square()` |
| Video won't play | `_open_player()` in media.py; the error box text is also in the log |
| Wrong rate in data | `achieved_hz` column; `SessionWindow.step_stimulus()` |
| Settings not restored | `Config.load_default()`; check the log for "loaded preset" |

## 10. How a stick position becomes a rating

Each gamepad reading goes through five steps. The values from steps 1, 4 and 5 are all saved in the CSV, so any step can be redone later.

| Step | Name | Input → output | Setting |
|---|---|---|---|
| 1 | Raw | stick position as the gamepad reports it → `raw_x`, `raw_y` (-1 to 1) | |
| 2 | Centre and dead-zone | `raw` → corrected `x`, `y` | Dead-zone page |
| 3 | Flip up/down | `y` → `-y` (gamepads report up as negative) | Check page |
| 4 | Circle to square | `x`, `y` → `mapped_x`, `mapped_y` (-1 to 1) | Configuration page |
| 5 | Scale | `mapped` → `valence`, `arousal` | Configuration page |

### The maths

Symbols: `c` is the resting centre, `d` the dead-zone size, `lo` and `hi` the ends of your rating scale.

**Step 2, centre and dead-zone.** Subtract the centre, keep the result within -1 to 1, and measure how far the stick is from the middle:

```
x' = clamp(raw_x - c_x)        y' = clamp(raw_y - c_y)
r  = sqrt(x'^2 + y'^2)
```

If `r < d`, the output is (0, 0). Otherwise the distance is shrunk so that full tilt still gives exactly 1:

```
k = (r - d) / ((1 - d) * r)
x = k * x'        y = k * y'
```

Example: with `d = 0.05`, a stick at r = 0.05 gives 0 and a stick at r = 1 gives 1.

**Step 4, circle to square.** The stick moves inside a circle, but the rating grid is a square. With `(u, v)` as the point from step 3 (pulled back onto the circle if `r > 1`):

```
mapped_x = 1/2 * sqrt(2 + u^2 - v^2 + 2*sqrt(2)*u) - 1/2 * sqrt(2 + u^2 - v^2 - 2*sqrt(2)*u)
mapped_y = 1/2 * sqrt(2 - u^2 + v^2 + 2*sqrt(2)*v) - 1/2 * sqrt(2 - u^2 + v^2 - 2*sqrt(2)*v)
```

This is the elliptical grid mapping. It sends the edge of the circle onto the edge of the square, so the corners (±1, ±1) can be reached. Without it ("Direct" mapping), the stick at 45° can only give ±0.707 on both axes, about 71% of the way to the corner.

**Step 5, scale.** Stretch -1 to 1 onto your chosen range:

```
valence = lo + (mapped_x + 1) / 2 * (hi - lo)
arousal = lo + (mapped_y + 1) / 2 * (hi - lo)
```

Example with a 0 to 100 scale: `mapped = -1` gives 0, `0` gives 50, `+1` gives 100. With -100 to +100, `0` gives 0.
