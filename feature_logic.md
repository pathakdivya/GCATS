## Measuring (Dead-zone page)

With your hands off the stick, the app records the raw `x/y` position for 3 seconds, about 180 samples. The centre is the average of those samples: 
```
c_x = mean(x), c_y = mean(y)
```
The spread is the farthest any sample strayed from that centre: 
```
spread = max( sqrt((x − c_x)² + (y − c_y)²) )
```
The dead-zone is the spread plus a 25% safety margin, kept between 0.02 and 0.08: 
```
d = clamp(spread × 1.25, 0.02, 0.08)
```
If the spread is above 0.15, or no data arrived, the stick was probably touched. Nothing is saved and you are asked to measure again.

> Note: The centre removes a steady offset, which is a bias. The dead-zone only has to cover random jitter around the true centre, so it can stay small and doesn't throw away small deliberate movements. The raw values are saved unchanged, and centre_x, centre_y and dead_zone are saved on every row, so you can redo or check the correction later.

## How a stick position becomes a rating

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
