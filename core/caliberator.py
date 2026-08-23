"""
core/calibrator.py
==========================
Interactive gamepad calibration. Runs entirely inside the PsychoPy
window. Returns a fully configured JoystickController with dead-zone and centre drift correction.
"""

import math
import time
from typing import Tuple, Dict, Optional

import pygame
from psychopy import visual, event

from core.joystick import JoystickController, clamp_100
from core.exceptions import ExperimentAborted

# ── Colours (PsychoPy –1to+1 RGB) ─────────────────────────────────────────────
COL_WHITE = ( 0.92,  0.92,  0.92)
COL_DIM   = ( 0.45,  0.45,  0.45)
COL_GREEN = ( 0.20,  0.80,  0.30)
COL_RED   = ( 1.00,  0.22,  0.22)
COL_AMBER = ( 1.00,  0.65,  0.00)


# ─────────────────────────────────────────────────────────────────────────────
# Entry
# ─────────────────────────────────────────────────────────────────────────────
def run_calibration_wizard(win: visual.Window) -> JoystickController:
    # 1. run step 1 – get joystick function
    joy = _get_joystick(win)

    # 2. run step 2 – detect thumbsticks
    left_axes,  left_drift  = _detect_stick(win, joy, side="LEFT")
    right_axes, right_drift = _detect_stick(win, joy, side="RIGHT")

    # 3. run step 3 – detect shoulder buttons
    left_btn  = _detect_button(win, joy, label="LEFT shoulder  (L1 / LB)")
    right_btn = _detect_button(win, joy, label="RIGHT shoulder  (R1 / RB)")

    # 4. run step 4 – choose combo of stick + shoulder
    stick_axes, confirm_btn, lock_btn = _choose_combo(win, joy, left_axes, right_axes, left_btn, right_btn)

    # 5. run step 5 – measure dead-zone (caliberation of the Gamepad)
    axis_x, axis_y = stick_axes
    dead_zone = _measure_dead_zone(win, joy, axis_x, axis_y)

    # 6. run step 6 – check Y-axis inversion (caliberation of the Gamepad)
    confirm_label = "RIGHT" if confirm_btn == right_btn else "LEFT"
    lock_label    = "LEFT"  if confirm_btn == right_btn else "RIGHT"
    invert_y  = _check_inversion(win, joy, axis_x, axis_y, dead_zone, confirm_btn, lock_btn, confirm_label=confirm_label, lock_label=lock_label)

    # 7. run step 7 – verification of final configuration (caliberation of the Gamepad)
    _verify(win, joy, axis_x, axis_y, invert_y, dead_zone, confirm_btn, confirm_label=confirm_label, lock_label=lock_label)

    ctrl = JoystickController(
        handedness="custom",
        dead_zone=dead_zone,
        axis_x=axis_x,
        axis_y=axis_y,
        btn_confirm=confirm_btn,
        btn_lock=lock_btn,
        invert_y=invert_y,
    )
    ctrl._joystick = joy
    return ctrl


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 – get joystick function
# ─────────────────────────────────────────────────────────────────────────────
def _get_joystick(win: visual.Window) -> pygame.joystick.Joystick:
    pygame.event.pump()
    if pygame.joystick.get_count() == 0:
        _show(win,
            "No gamepad detected.\n\n"
            "Please plug in your USB gamepad,\nthen press SPACE to retry.",
            color=COL_RED,
        )
        event.waitKeys(keyList=["space"])
        pygame.joystick.quit()
        pygame.joystick.init()
        if pygame.joystick.get_count() == 0:
            raise RuntimeError("No gamepad found after retry.")

    joy = pygame.joystick.Joystick(0)
    joy.init()

    _show(win,
        f"GAMEPAD DETECTED\n\n"
        f"\"{joy.get_name()}\"\n\n"
        f"Axes    : {joy.get_numaxes()}\n"
        f"Buttons : {joy.get_numbuttons()}\n"
        f"Hats    : {joy.get_numhats()}  (D-pad)\n\n"
        f"We will now calibrate the controller step by step.\n"
        f"Take your time to read the instructions and follow the prompts.\n\n"
        f"Press any button on the Gamepad or SPACE to begin.",
        color=COL_GREEN,
    )
    _wait_btn_or_space(win, joy)
    return joy


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 – detect thumbsticks 
# ─────────────────────────────────────────────────────────────────────────────
def _detect_stick(
    win: visual.Window,
    joy: pygame.joystick.Joystick,
    side: str) -> Tuple[Tuple[int, int], float]:

    # Standard XInput axis layout:
    # Left stick:  axis 0 (X), axis 1 (Y)
    # Right stick: axis 2 (X), axis 3 (Y)
    if side == "LEFT":
        axis_x, axis_y = 0, 1
    else:
        axis_x, axis_y = 2, 3

    # Measure centre drift
    _show(win,
        f"SETUP  –  {side} THUMBSTICK\n\n"
        f"Leave the {side} thumbstick at rest\n"
        f"(do not touch or move anything).\n\n"
        f"Measuring resting drift for 3 seconds …\n\n"
        f"(starting automatically)",
        color=COL_WHITE,
    )
    # time.sleep tells the function to wait for a certain amount of time before continuing. In this case, it waits for 2 seconds before starting the measurement. Helps the participant to get ready and not touch the stick during the measurement.

    time.sleep(2.0)
    resting = _collect_axes(win, joy, duration=3.0, show_bar=True)

    rest_x = sum(s[axis_x] for s in resting) / len(resting)
    rest_y = sum(s[axis_y] for s in resting) / len(resting)
    drift  = math.sqrt(rest_x**2 + rest_y**2)

    _show(win,
        f"{side} STICK  –  Complete\n\n"
        f"  X axis (left/right) : Axis {axis_x}\n"
        f"  Y axis (up/down)    : Axis {axis_y}\n\n"
        f"  Centre drift : {drift:.4f}\n\n"
        f"Press any button or SPACE to continue.",
        color=COL_GREEN,
    )
    _wait_btn_or_space(win, joy)
    return (axis_x, axis_y), drift

# ─────────────────────────────────────────────────────────────────────────────
# Step 3 – identify a button
# ─────────────────────────────────────────────────────────────────────────────
def _detect_button(
    win: visual.Window,
    joy: pygame.joystick.Joystick,
    label: str,
) -> int:

    n_buttons = joy.get_numbuttons()
    detected: Optional[int] = None

    # Debounce: wait until all buttons released
    _wait_all_released(joy)

    _show(win,
        f"BUTTON DETECTION\n\n"
        f"Please press the\n\n"
        f"    {label}\n\n"
        f"button now.\n\n"
        f"The button display below updates in real time.\n"
        f"When you press the correct button it will be captured automatically.",
        color=COL_WHITE,
    )
    time.sleep(3.5)

    deadline = time.perf_counter() + 15.0
    while detected is None and time.perf_counter() < deadline:
        pygame.event.pump()
        btn_states = [joy.get_button(i) for i in range(n_buttons)]
        pressed    = [i for i, b in enumerate(btn_states) if b]

        # Build a wrapped button grid (8 per row)
        rows = []
        for row_start in range(0, n_buttons, 8):
            row = "  ".join(
                f"[{'●' if btn_states[i] else 'B'}{i}]"
                for i in range(row_start, min(row_start + 8, n_buttons))
            )
            rows.append(row)
        btn_display = "\n".join(rows)

        status = f"Waiting …" if not pressed else f"Detected: Button {pressed[0]}  ✓"
        text   = (
            f"BUTTON DETECTION\n\n"
            f"Press the  {label}  button:\n\n"
            f"{btn_display}\n\n"
            f"{status}"
        )
        _draw(win, text, color=COL_WHITE if not pressed else COL_GREEN)
        win.flip()
        time.sleep(0.04)

        if pressed:
            detected = pressed[0]

        if "escape" in event.getKeys():
            break

    if detected is None:
        detected = 4 if "LEFT" in label.upper() else 5

    time.sleep(3.5)  # debounce hold

    _show(win,
        f"BUTTON DETECTION  –  Complete\n\n"
        f"{label}\n\n"
        f"Recorded as:  Button {detected}\n\n"
        f"Read the above and press any button or SPACE to continue.",
        color=COL_GREEN,
    )
    _wait_btn_or_space(win, joy)
    return detected


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 – choose combo
# ─────────────────────────────────────────────────────────────────────────────
def _choose_combo(
    win, joy,
    left_axes:  Tuple[int, int],
    right_axes: Tuple[int, int],
    left_btn:   int,
    right_btn:  int
) -> Tuple[Tuple[int, int], int, int]:

    options = [
        (f"LEFT stick   +   RIGHT shoulder",  left_axes,  right_btn, left_btn),
        (f"RIGHT stick  +   LEFT shoulder",  right_axes, left_btn,  right_btn),
        (f"LEFT stick   +   LEFT shoulder",  left_axes,  left_btn,  right_btn),
        (f"RIGHT stick  +   RIGHT shoulder",  right_axes, right_btn, left_btn),
    ]

    _show(win,
        "COMBO SELECTION\n\n"
        "On the next screen, choose which thumbstick and\n"
        "shoulder button combination you prefer.\n\n"
        "Navigate UP / DOWN using:\n"
        "  •  D-pad up/down\n"
        "  •  Either thumbstick pushed up or down\n\n"
        "Press either shoulder button or SPACE to confirm your choice.\n\n"
        "Press any button or SPACE to see the options.",
        color=COL_WHITE,
    )
    _wait_btn_or_space(win, joy)

    choice   = 0
    n_opts   = len(options)
    last_dir = 0.0   # for stick debounce

    _wait_all_released(joy)

    # Track previous hat and axis states to detect edges (not levels)
    prev_hat   = (0, 0)
    prev_axes  = [joy.get_axis(i) for i in range(joy.get_numaxes())]

    selecting = True
    while selecting:
        # Build display
        lines = ["CHOOSE YOUR PREFERRED COMBO\n"]
        for i, (name, *_) in enumerate(options):
            prefix = "  ►  " if i == choice else "       "
            lines.append(f"{prefix}{name}")
        lines += [
            "",
            "D-pad UP/DOWN or stick UP/DOWN  to move",
            "Either shoulder button or SPACE  to confirm",
        ]
        _draw(win, "\n".join(lines), color=COL_WHITE)
        win.flip()

        pygame.event.pump()

        moved = False

        # ── D-pad (hat) — edge detect ────────────────────────────────────────
        if joy.get_numhats() > 0:
            hat = joy.get_hat(0)
            if hat[1] == 1 and prev_hat[1] != 1:       # fresh UP press
                choice = (choice - 1) % n_opts
                moved  = True
            elif hat[1] == -1 and prev_hat[1] != -1:   # fresh DOWN press
                choice = (choice + 1) % n_opts
                moved  = True
            prev_hat = hat

        # ── Stick — edge detect on any axis ──────────────────────────────────
        if not moved:
            curr_axes = [joy.get_axis(i) for i in range(joy.get_numaxes())]
            for i, (curr, prev) in enumerate(zip(curr_axes, prev_axes)):
                if curr < -0.5 and prev >= -0.5:    # crossed threshold upward
                    choice = (choice - 1) % n_opts
                    moved  = True
                    break
                elif curr > 0.5 and prev <= 0.5:    # crossed threshold downward
                    choice = (choice + 1) % n_opts
                    moved  = True
                    break
            prev_axes = curr_axes

        if moved:
            time.sleep(0.20)
            continue

        # ── Confirm — only checked when nothing moved ────────────────────────
        btn_states = [joy.get_button(b) for b in range(joy.get_numbuttons())]
        if btn_states[left_btn] or btn_states[right_btn]:
            selecting = False
            time.sleep(0.30)
        elif "space" in event.getKeys():
            selecting = False

        time.sleep(0.03)

    name, stick_axes, confirm_btn, lock_btn = options[choice]

    _show(win,
        f"COMBO SELECTION  –  Confirmed\n\n"
        f"You chose:\n\n"
        f"    {name}\n\n"
        f"  Thumbstick axes  :  X = Axis {stick_axes[0]},  "
        f"Y = Axis {stick_axes[1]}\n"
        f"  Confirm button   :  Button {confirm_btn}\n"
        f"  Lock button      :  Button {lock_btn}\n\n"
        f"Read the above and press any button or SPACE to continue.",
        color=COL_GREEN,
    )
    _wait_btn_or_space(win, joy)
    return stick_axes, confirm_btn, lock_btn


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 – dead-zone
# ─────────────────────────────────────────────────────────────────────────────
def _measure_dead_zone(win, joy, axis_x: int, axis_y: int) -> float:
    _show(win,
        "DEAD-ZONE MEASUREMENT\n\n"
        "Release the thumbstick and leave it completely at rest.\n\n"
        "Do not touch the controller for 3 seconds.\n\n"
        "We will measure how much the stick drifts when untouched.\n\n"
        "(starting automatically in 1 second …)",
        color=COL_WHITE,
    )
    time.sleep(1.5)
    samples = _collect_axes(win, joy, duration=3.0, show_bar=False)
    xs     = [s[axis_x] for s in samples]
    ys     = [s[axis_y] for s in samples]
    drifts = [math.sqrt(x**2 + y**2) for x, y in zip(xs, ys)]
    dz     = min(0.15, max(0.04, max(drifts) * 1.25))

    _show(win,
        f"DEAD-ZONE MEASUREMENT  –  Complete\n\n"
        f"  Max resting drift  :  {max(drifts):.4f}\n"
        f"  Dead-zone set to   :  {dz:.4f}\n\n"
        f"This means the cursor will not move until\n"
        f"you push the stick past {dz*100:.1f}% of its travel.\n\n"
        f"Read the above and press any button or SPACE to continue.",
        color=COL_GREEN,
    )
    _wait_btn_or_space(win, joy)
    return dz


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 – Y-axis inversion check (participant decides)
# ─────────────────────────────────────────────────────────────────────────────
def _check_inversion(win, joy, axis_x, axis_y, dead_zone, confirm_btn, lock_btn, confirm_label="RIGHT", lock_label="LEFT"):
    """
    Show a live dot on a mini grid. The participant sees whether pushing UP
    on the stick moves the dot UP (correct for high arousal) or DOWN (inverted).
    They press CONFIRM if it looks correct, or LOCK to flip it.
    """
    _show(win,
        "Y-AXIS CHECK\n\n"
        "On the next screen you will see a red dot that moves with your stick.\n\n"
        "Push the stick UPWARD and check whether the dot moves UP.\n\n"
        "  •  If the dot moves UP when you push UP  →  press the [" + confirm_label + "] shoulder\n"
        "  •  If the dot moves DOWN when you push UP →  press the [" + lock_label + "] shoulder\n\n"
        "   (Confirm = your active shoulder,  Lock = the other shoulder)\n\n"
        "Press any button or SPACE to open the check screen.",
        color=COL_WHITE,
    )
    _wait_btn_or_space(win, joy)

    invert_y = False   # start with inversion; participant can flip

    gs = 0.70
    cx, cy = 0.0, 0.04

    grid   = visual.Rect(win, pos=(cx, cy), width=gs, height=gs,
                         fillColor=(-0.85,-0.85,-0.85), lineColor=COL_WHITE,
                         lineWidth=1.5, units="norm")
    h_line = visual.Line(win, start=(cx-gs/2, cy), end=(cx+gs/2, cy),
                         lineColor=COL_DIM, lineWidth=1, units="norm")
    v_line = visual.Line(win, start=(cx, cy-gs/2), end=(cx, cy+gs/2),
                         lineColor=COL_DIM, lineWidth=1, units="norm")

    lkw = dict(win=win, height=0.040, color=COL_DIM, units="norm")
    edge_labels = [
        visual.TextStim(text="Negative Valence", pos=(cx-gs/2, cy-gs/2-0.07),
                        anchorHoriz="left",  **lkw),
        visual.TextStim(text="Positive Valence", pos=(cx+gs/2, cy-gs/2-0.07),
                        anchorHoriz="right", **lkw),
        visual.TextStim(text="High Arousal",     pos=(cx, cy+gs/2+0.07),   **lkw),
        visual.TextStim(text="Low Arousal",      pos=(cx, cy-gs/2-0.07),   **lkw),
    ]

    dot = visual.Circle(win, radius=0.025, pos=(cx, cy),
                        fillColor=COL_RED, lineColor=COL_WHITE,
                        lineWidth=1.5, units="norm")

    instr_txt = visual.TextStim(
        win, pos=(0,  0.88), height=0.048, color=COL_WHITE,
        wrapWidth=1.85, units="norm",
    )
    status_txt = visual.TextStim(
        win, pos=(0, -0.88), height=0.048, color=COL_AMBER, units="norm",
    )

    _wait_all_released(joy)
    confirmed = False

    while not confirmed:
        pygame.event.pump()

        raw_x = joy.get_axis(axis_x)
        raw_y = joy.get_axis(axis_y)

        mag = math.sqrt(raw_x**2 + raw_y**2)
        if mag < dead_zone:
            raw_x, raw_y = 0.0, 0.0
        else:
            sc = (mag - dead_zone) / (1.0 - dead_zone)
            raw_x = (raw_x / mag) * sc
            raw_y = (raw_y / mag) * sc

        raw_y_up = -raw_y if invert_y else raw_y
        valence  = clamp_100((raw_x    + 1.0) * 50.0)
        arousal  = clamp_100((raw_y_up + 1.0) * 50.0)

        dot.pos = (
            cx - gs/2 + (valence / 100.0) * gs,
            cy - gs/2 + (arousal / 100.0) * gs,
        )

        flip_str = "FLIPPED" if invert_y else "NORMAL"
        # instr_txt.text  = (
        #     "Y-AXIS CHECK\n\n"
        #     "Push stick UP  →  dot should move UP (High Arousal)\n\n"
        #     f"Current mode: {flip_str}\n\n"
        #     "CONFIRM shoulder = looks correct  |  LOCK shoulder = flip direction"
        # )

        instr_txt.text  = (
            "Y-AXIS CHECK\n\n"
            "Push stick UP  →  dot should move UP (High Arousal)\n\n"
            f"Y inversion currently: {flip_str}\n\n"
            f"Press  [{confirm_label}]  to accept\n"
            f"Press  [{lock_label}]     to toggle invert Y on/off"
        )
        status_txt.text = f"Valence {valence:.0f}   Arousal {arousal:.0f}"

        grid.draw(); h_line.draw(); v_line.draw()
        for lb in edge_labels: lb.draw()
        dot.draw()
        instr_txt.draw()
        status_txt.draw()
        win.flip()

        if joy.get_button(lock_btn):
            invert_y = not invert_y   # toggle flip
            time.sleep(0.40)
        elif joy.get_button(confirm_btn):
            confirmed = True
            time.sleep(0.30)


        if "escape" in event.getKeys():
            raise ExperimentAborted()
        if "space" in event.getKeys():
            confirmed = True

    flip_str = "Yes (corrected)" if invert_y else "No"
    _show(win,
        f"Y-AXIS CHECK  –  Complete\n\n"
        f"  Y inversion applied : {flip_str}\n\n"
        f"Pushing UP on the stick now increases Arousal.\n\n"
        f"Read the above and press any button or SPACE to continue.",
        color=COL_GREEN,
    )
    _wait_btn_or_space(win, joy)
    return invert_y


# ─────────────────────────────────────────────────────────────────────────────
# Step 7 – verification
# ─────────────────────────────────────────────────────────────────────────────
def _verify(win, joy, axis_x, axis_y, invert_y, dead_zone, confirm_btn, confirm_label="RIGHT", lock_label="LEFT"):
    _show(win,
        "VERIFICATION\n\n"
        "On the next screen, move the stick to all four corners\n"
        "and confirm that the dot tracks correctly:\n\n"
        "  •  Stick RIGHT  →  dot moves RIGHT  (Positive Valence)\n"
        "  •  Stick LEFT   →  dot moves LEFT   (Negative Valence)\n"
        "  •  Stick UP     →  dot moves UP     (High Arousal)\n"
        "  •  Stick DOWN   →  dot moves DOWN   (Low Arousal)\n\n"
        "When everything looks correct,\n"
        f"press the [{confirm_label}] shoulder button to finish calibration.\n\n"
        "Press any button or SPACE to open the verification screen.",
        color=COL_WHITE,
    )
    _wait_btn_or_space(win, joy)

    gs = 0.78
    cx, cy = 0.0, 0.02

    grid   = visual.Rect(win, pos=(cx, cy), width=gs, height=gs,
                         fillColor=(-0.85,-0.85,-0.85), lineColor=COL_WHITE,
                         lineWidth=1.5, units="norm")
    h_line = visual.Line(win, start=(cx-gs/2, cy), end=(cx+gs/2, cy),
                         lineColor=COL_DIM, lineWidth=1, units="norm")
    v_line = visual.Line(win, start=(cx, cy-gs/2), end=(cx, cy+gs/2),
                         lineColor=COL_DIM, lineWidth=1, units="norm")

    lkw = dict(win=win, height=0.042, color=COL_DIM, units="norm")
    edge_labels = [
        visual.TextStim(text="Negative Valence", pos=(cx-gs/2, cy-gs/2-0.08),
                        anchorHoriz="left",  **lkw),
        visual.TextStim(text="Positive Valence", pos=(cx+gs/2, cy-gs/2-0.08),
                        anchorHoriz="right", **lkw),
        visual.TextStim(text="High Arousal",     pos=(cx, cy+gs/2+0.07),     **lkw),
        visual.TextStim(text="Low Arousal",      pos=(cx, cy-gs/2-0.08),     **lkw),
    ]

    dot = visual.Circle(win, radius=0.025, pos=(cx, cy),
                        fillColor=COL_RED, lineColor=COL_WHITE,
                        lineWidth=1.5, units="norm")

    instr = visual.TextStim(
        win,
        text="VERIFICATION  –  Move stick to all four corners\n"
             f"Press [{confirm_label}] shoulder when satisfied",
        pos=(0, 0.90), height=0.048, color=COL_WHITE,
        wrapWidth=1.85, units="norm",
    )
    val_txt = visual.TextStim(win, pos=(0, -0.90), height=0.046,
                              color=COL_AMBER, units="norm")

    _wait_all_released(joy)

    running = True
    while running:
        pygame.event.pump()

        raw_x = joy.get_axis(axis_x)
        raw_y = joy.get_axis(axis_y)
        mag   = math.sqrt(raw_x**2 + raw_y**2)
        if mag < dead_zone:
            raw_x, raw_y = 0.0, 0.0
        else:
            sc    = (mag - dead_zone) / (1.0 - dead_zone)
            raw_x = (raw_x / mag) * sc
            raw_y = (raw_y / mag) * sc

        raw_y_up = -raw_y if invert_y else raw_y
        valence  = clamp_100((raw_x    + 1.0) * 50.0)
        arousal  = clamp_100((raw_y_up + 1.0) * 50.0)

        dot.pos = (
            cx - gs/2 + (valence / 100.0) * gs,
            cy - gs/2 + (arousal / 100.0) * gs,
        )
        val_txt.text = f"Valence {valence:.0f}   Arousal {arousal:.0f}"

        grid.draw(); h_line.draw(); v_line.draw()
        for lb in edge_labels: lb.draw()
        dot.draw(); instr.draw(); val_txt.draw()
        win.flip()

        if joy.get_button(confirm_btn):
            running = False
            time.sleep(0.30)
            time.sleep(0.30)
        if "escape" in event.getKeys():
            raise ExperimentAborted("User pressed ESCAPE during verification.")
            # running = False

    _show(win,
        "CALIBRATION COMPLETE\n\n"
        "The controller is now fully configured.\n\n"
        "The experiment will begin after you press\n"
        "any button or SPACE.",
        color=COL_GREEN,
    )
    _wait_btn_or_space(win, joy)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers used throughout the Calibration wizard
# ─────────────────────────────────────────────────────────────────────────────

def _collect_axes(win, joy, duration: float, show_bar: bool) -> list:
    """Poll all axes for *duration* seconds. Returns list of snapshots."""
    n_axes   = joy.get_numaxes()
    samples  = []
    start    = time.perf_counter()
    deadline = start + duration

    if show_bar:
        prog_bg   = visual.Rect(win, pos=(0, -0.82), width=1.50, height=0.055,
                                 fillColor=(-0.55,-0.55,-0.55),
                                 lineColor=None, units="norm")
        prog_fill = visual.Rect(win, pos=(-0.75, -0.82), width=0.001,
                                 height=0.055, fillColor=COL_GREEN,
                                 lineColor=None, units="norm")

    while time.perf_counter() < deadline:
        pygame.event.pump()
        snap = [joy.get_axis(i) for i in range(n_axes)]
        samples.append(snap)

        if show_bar:
            frac = (time.perf_counter() - start) / duration
            w    = max(0.002, 1.50 * frac)
            prog_fill.width = w
            prog_fill.pos   = (-0.75 + w / 2, -0.82)
            prog_bg.draw()
            prog_fill.draw()
            win.flip()
        else:
            time.sleep(0.016)

    return samples


def _show(win, text: str, color=COL_WHITE) -> None:
    _draw(win, text, color)
    win.flip()


def _draw(win, text: str, color=COL_WHITE) -> None:
    visual.TextStim(
        win, text=text,
        height=0.055, color=color,
        wrapWidth=1.82, units="norm",
        anchorVert="center",
    ).draw()


def _wait_btn_or_space(win, joy, timeout: float = 60.0) -> None:
    """Wait until any gamepad button OR spacebar is pressed."""
    # First make sure nothing is currently held
    _wait_all_released(joy)

    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        pygame.event.pump()
        if any(joy.get_button(i) for i in range(joy.get_numbuttons())):
            time.sleep(0.25)
            return
        if "space" in event.getKeys():
            return
        time.sleep(0.04)


def _wait_all_released(joy, timeout: float = 3.0) -> None:
    """Block until no buttons or axes 4 and 5 (trigger axes) are held (debounce guard)."""
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        pygame.event.pump()
        if not any(joy.get_button(i) for i in range(joy.get_numbuttons())):
            if joy.get_numaxes() >= 6:
                if abs(joy.get_axis(4)) < 0.05 and abs(joy.get_axis(5)) < 0.05:
                    return
        time.sleep(0.04)

def _ab_button_pressed(joy, a_btn: int, b_btn: int) -> bool:
    """Return True if either of the two buttons is pressed."""
    pygame.event.pump()
    return joy.get_button(a_btn) or joy.get_button(b_btn)

def _xy_button_pressed(joy, x_btn: int, y_btn: int) -> bool:
    """Return True if either of the two buttons is pressed."""
    pygame.event.pump()
    return joy.get_button(x_btn) or joy.get_button(y_btn)
