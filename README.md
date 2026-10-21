
<img src="GCATS assets/gcats-logo.svg" alt="Alt Text" width="200">

# G-CATS

**Gamepad-based Continuous Affect Tracing System**

G-CATS enables the continuous capture of self-reported affective ratings on a dual-axis Cartesian grid using a gamepad thumbstick. It also supports summary ratings within the same session, collected either before or after each stimulus. Images, videos, and audio files can be mixed in a single session.

For how the code is laid out, See [app_design.md](app_design.md).

## Install and run

Needs Python 3.10+ and a connected gamepad.

```
pip install -r requirements.txt
python run_gcats.py
```

`ffprobe` (from FFmpeg) on your PATH is optional. It only shows media lengths in the Stimuli table.

## Running a session

The left rail lists the setup pages. Click any page in the rail to jump to it.

| Page | What you do |
|---|---|
| Startup | Packages are checked; plug in the gamepad |
| Participant | ID (required), session, age, gender |
| Stimuli | Pick a file or folder; order, image duration, aspect ratio, margin |
| Protocol | Gap between stimuli; rating mode; summary before or after |
| Configuration | Output rate, rating scale, stick mapping, cursor look, labels, presets |
| Controls | Which stick; which shoulder button confirms |
| Dead-zone | Hands off the stick for 3 s while drift is measured |
| Check | Move the stick to all four corners; tick the box if up/down is reversed |

The session then runs fullscreen. **Escape** stops it early and still saves the data. When it ends, you can run new stimuli for the same participant or quit.

## Output

Saved in `data/` next to the app:

```
<id>_S<session>_<date>_<time>_raw.csv          every stick reading (about every 4 ms)
<id>_S<session>_<date>_<time>_continuous.csv   one reading per output interval
<id>_S<session>_<date>_<time>_config.json      every setting used
```

Both CSVs have the same columns:

| Column(s) | Meaning |
|---|---|
| `participant_id`, `session`, `trial`, `stimulus_id`, `stimulus_kind` | Who and what |
| `phase` | `trace` (during stimulus) or `summary` (confirmed rating) |
| `sample_number`, `t_monotonic`, `stimulus_time` | Row count, clock time, seconds since trial start |
| `raw_x`, `raw_y` | Stick position as the gamepad reports it |
| `mapped_x`, `mapped_y` | After dead-zone and mapping, -1 to 1 |
| `valence`, `arousal` | On your chosen scale |
| `confirm`, `lock` | Shoulder buttons (1 = pressed) |
| `requested_hz`, `achieved_hz`, `sample_interval_s` | Rate you asked for and rate you got |
| `axis_min`, `axis_max`, `joystick_mapping`, `cursor_opacity`, `monitor_refresh`, `*_label` | Settings, repeated so each CSV makes sense on its own |

Because raw values are always kept, you can redo the dead-zone, mapping or scale later.

## How a stick position becomes a rating

```
raw_x, raw_y        -> ignore small drift near centre (dead-zone)
                    -> optional circle-to-square stretch
mapped_x, mapped_y  -> -1..1
                    -> stretch to your scale (e.g. 0..100)
valence, arousal
```

**Why circle-to-square:** a thumbstick moves inside a circle, but the rating grid is a square. Without the stretch, the cursor can only reach about 71% of the way into each corner. "Direct" mapping is still available.

## Presets

The Configuration page can save and load settings as `.json` files:

```json
{
  "sampling_hz": 10,
  "axis_min": 0,
  "axis_max": 100,
  "joystick_mapping": "circle_to_square",
  "cursor_opacity": 0.75,
  "low_valence_label": "Unpleasant",
  "high_valence_label": "Pleasant",
  "low_arousal_label": "Calm",
  "high_arousal_label": "Activated"
}
```

- Your last-used settings are saved to `~/.gcats/default_preset.json` and loaded on the next start.
- Keys the app doesn't recognise are ignored, so old presets still load.
- Participant details and stimulus files are never stored in presets.

## Display

- The rating grid is a square centred on the media box. 
- Shown on the grid: a faint centre cross, optional guide lines through the cursor, the cursor, and the four end labels. Leave a label blank to hide it.
- **Aspect ratio:** `original` keeps the media size and only shrinks it to fit fullscreen. `1:1`, `3:2`, `4:3` and `16:9` use a fixed shape.
- **Inner margin:** this percentage is kept empty on every side of the screen (default 10%). Helps in clean display during the recording. 
- **Summary screen:** Asks the rator to give a single value on the dual-axis grid. 
- **Audio:** the grid sits in the upper part of the screen with a progress bar below.

## Gamepad layout

Axes `0/1` = left stick, `2/3` = right stick. Buttons `4` = left shoulder, `5` = right shoulder. For other layouts, edit `axis_x`, `axis_y`, `btn_confirm` in `gcats/config.py`.

## Troubleshooting

All messages go to the console and to `~/.gcats/gcats.log`. For more detail (state changes, gamepad settings, file writes):

```
set GCATS_DEBUG=1        # Windows cmd
$env:GCATS_DEBUG=1       # PowerShell
export GCATS_DEBUG=1     # macOS / Linux
python run_gcats.py
```

| Problem | Fix |
|---|---|
| Stuck on "connect a USB gamepad" | Re-plug the pad. It is checked again every second |
| "playback failed" box | Check `ffpyplayer` is installed and the file opens in a media player |
| Cursor moves the wrong way vertically | Tick the flip box on the Check page |
| Cursor drifts with no hand on the stick | Measure the dead-zone again |

## Licence

[GNU GPL v3.0](LICENSE.md)
