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

> ## App settings presets
> 
> The Configuration page can save and load settings as `.json` files:
> 
> ```json
> {
>   "sampling_hz": 10,
>   "axis_min": 0,
>   "axis_max": 100,
>   "joystick_mapping": "circle_to_square",
>   "cursor_opacity": 0.75,
>   "low_valence_label": "Unpleasant",
>   "high_valence_label": "Pleasant",
>   "low_arousal_label": "Calm",
>   "high_arousal_label": "Activated"
> }
> ```
> 
> - Your last-used settings are saved to `C:\Users\<you>\.gcats\default_preset.json` (Windows) | `~/.gcats/default_preset.json` (macOS / Linux) and loaded on the next start.

# Design Statements 

Our development of GCATS is guided by FAIR Guiding Principles for scientific data management ([Wilkinson et al., 2016](https://doi.org/10.1038/sdata.2016.18)) and their adaptation for research software, FAIR4RS ([Barker et al., 2022](https://doi.org/10.1038/s41597-022-01710-x)). Our source code is openly hosted on this Github Repository. Each release is archived on Zenodo with a persistent DOI - [https://doi.org/10.5281/zenodo.23536403](https://doi.org/10.5281/zenodo.23536403). The software is distributed under an open-source licence and documented in the `README.md` and the `GCATS wiki` so that others can install it easily. GCATS also follows the Software Citation Principles ([Smith et al., 2016](https://doi.org/10.7717/peerj-cs.86
)), with a recommended citation provided in the `README.md`. Our starting goal for the organisation of the software was to make it modular so that it can be maintained and debugged easily. The general organisation of the project, including the **modular code**, version control, a requirements file, a README and contribution guidelines, follows the recommendations of [Wilson et al. (2017)](https://doi.org/10.1371/journal.pcbi.1005510) for scientific computing. The project’s transparency practices are aligned with the Transparency and Openness Promotion (TOP) Guidelines ([Nosek et al., 2015](https://doi.org/10.1126/science.aab2374)).

The rating interface that overlays on top of the stimuli, builds on the dual-axis valence–arousal space of the circumplex model of affect ([Russell, 1980](https://doi.org/10.1037/h0077714)). It also builds on earlier continuous rating tools, in particular DARMA ([Girard & Wright, 2018](https://doi.org/10.3758/s13428-017-0915-5)), and on joystick-based continuous annotation as used in the CASE dataset ([Sharma et al., 2019](https://doi.org/10.1038/s41597-019-0209-0)) and described in ([Sharma et al,. 2017](10.1109/TAFFC.2017.2772882)) . Interface design was informed by usability heuristics ([Nielsen, 1994](https://doi.org/10.1145/191666.191729)), especially visibility of system status, error prevention and consistency. These appear in GCATS as the lefthand side rails that shows setup progress, the live verification page and the saving of all settings with each session.

Gamepad handling draws on game-development practice. The dead zone and drift correction follow widely used guidance on thumbstick dead zones ([Sutphin, 2013](https://www.gamedeveloper.com/disciplines/doing-thumbstick-dead-zones-right)). Gamepad mapping, button choices and the holding style were informed by the Xbox Accessibility Guidelines ([Microsoft](https://learn.microsoft.com/en-us/gaming/accessibility/guidelines)). The mapping from the circular thumbstick range to the square rating grid is based on analytical disc-to-square mappings ([Fong, 2015](https://arxiv.org/abs/1509.06344
)). Input is read through the [pygame joystick module](https://www.pygame.org), and the interface is built with Qt for Python ([PySide6](https://doc.qt.io/qtforpython-6/)) and we use [ffpyplayer](https://matham.github.io/ffpyplayer) for media playback.

> References
> 
> - Barker, M., Chue Hong, N. P., Katz, D. S., Lamprecht, A.-L., Martinez-Ortiz, C., Psomopoulos, F., Harrow, J., Castro, L. J., Gruenpeter, M., Martinez, P. A., & Honeyman, T. (2022). Introducing the FAIR Principles for research software. Scientific Data, 9, 622. https://doi.org/10.1038/s41597-022-01710-x
> 
> - Fong, C. (2015). Analytical methods for squaring the disc [Preprint]. arXiv. https://arxiv.org/abs/1509.06344
> 
> - Girard, J. M., & Wright, A. G. C. (2018). DARMA: Software for dual axis rating and media annotation. Behavior Research Methods, 50(3), 902–909. https://doi.org/10.3758/s13428-017-0915-5
> 
> - Microsoft Learn. Xbox Accessibility Guidelines. Retrieved October 23, 2026, from https://learn.microsoft.com/en-us/gaming/accessibility/guidelines
> 
> - Nielsen, J. (1994). Enhancing the explanatory power of usability heuristics. In Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (pp. 152–158). ACM. https://doi.org/10.1145/191666.191729
> 
> - Nosek, B. A., Alter, G., Banks, G. C., Borsboom, D., Bowman, S. D., Breckler, S. J., … Yarkoni, T. (2015). Promoting an open research culture. Science, 348(6242), 1422–1425. https://doi.org/10.1126/science.aab2374
> 
> - Russell, J. A. (1980). A circumplex model of affect. Journal of Personality and Social Psychology, 39(6), 1161–1178. https://doi.org/10.1037/h0077714
> 
> - Sharma, K., Castellini, C., van den Broek, E. L., Albu-Schaeffer, A., & Schwenker, F. (2019). A dataset of continuous affect annotations and physiological signals for emotion analysis. Scientific Data, 6, 196. https://doi.org/10.1038/s41597-019-0209-0
> 
> - Sharma, K., Castellini, C., Stulp, F., & Van den Broek, E. L. (2017). Continuous, real-time emotion annotation: A novel joystick-based analysis framework. IEEE Transactions on Affective Computing, 11(1), 78-84.
> 
> - Smith, A. M., Katz, D. S., Niemeyer, K. E., & FORCE11 Software Citation Working Group. (2016). Software citation principles. PeerJ Computer Science, 2, e86. https://doi.org/10.7717/peerj-cs.86
> 
> - Sutphin, J. (2013). Doing thumbstick dead zones right. Game Developer. https://www.gamedeveloper.com/disciplines/doing-thumbstick-dead-zones-right
> 
> - Wilkinson, M. D., Dumontier, M., Aalbersberg, Ij. J., et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. Scientific Data, 3, 160018. https://doi.org/10.1038/sdata.2016.18
> 
> - Wilson, G., Bryan, J., Cranston, K., Kitzes, J., Nederbragt, L., & Teal, T. K. (2017). Good enough practices in scientific computing. PLOS Computational Biology, 13(6), e1005510. https://doi.org/10.1371/journal.pcbi.1005510
> 
> - Software: pygame (https://www.pygame.org), Qt for Python / PySide6 (https://doc.qt.io/qtforpython-6/), ffpyplayer (https://matham.github.io/ffpyplayer/).

## Suggested reading for making behavioural research Applications

> Some other referenences that I found really useful while deciding on the UI were - [Accessibility Training 101 by Accessibility at Perpendicular Angel Design](https://accessibility.perpendicularangel.com/accessibility-training-for-everyone/), [Xinyi Liu. 2026](https://dl.acm.org/doi/10.1145/3820915.3821089), [Esposito et al., 2025](https://dl.acm.org/doi/full/10.1145/3696593.3696613), [Yuri Pribysh's article on Appsilon](https://www.appsilon.com/post/accessible-research-with-r-shiny-ui-design),
