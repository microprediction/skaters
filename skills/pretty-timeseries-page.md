# pretty-timeseries-page skill

When building or restyling a **time-series page in JavaScript** — a live chart,
a forecast, a dashboard panel — apply these rules. They are distilled from the
[skaters playground](https://skaters.microprediction.org/demos/playground.html);
steal from its source freely. No chart library required: a `<canvas>`, ~80 lines
of drawing code, and discipline beat a default-themed Plotly embed every time.

## The three-color rule

One page, three hues, fixed roles. Everything else is grey.

- **Ink** `#1a1a1a` — observed data. Data is ink; nothing else is this dark.
- **Accent** `#4a3aff` — the model's *present* (fitted mean, current interval).
- **Hot accent** `#ff8a3a` — the model's *future* (the forecast fan). The eye
  should find "what happens next" instantly, and warm-vs-cool does that.

Uncertainty bands are the parent line's color at **16–18% alpha**
(`rgba(74,58,255,0.16)`), never a new hue. If you need a fourth color, you have
too many series on one panel — split the panel.

## Uncertainty is the point

A time-series page without a band is a lie of omission.

- Draw intervals as one **closed filled band** (trace the upper edge forward,
  the lower edge backward, `closePath`, `fill`) — not error bars, not two lines.
- Use real quantiles (2.5/97.5%) from the predictive, not mean ± 2σ.
- Bands must **widen with horizon**. If your forecast fan has constant width,
  say so in a caption or fix the model.

## The forecast fan

Project the k-step forecast from the last revealed point: dashed mean
trajectory (`setLineDash([4,3])`), band at 18% alpha, both in the hot accent.
Two details separate pretty from broken:

- **Reserve room**: map the x-domain over `[0, n-1+k]`, not `[0, n-1]`, so the
  fan never runs off the right edge.
- **Anchor it**: start the fan's mean line at the last observation itself, so
  it reads as a continuation, not a floating object.

## Canvas discipline

```js
// crisp on retina: scale the backing store, not the CSS size
const dpr = window.devicePixelRatio || 1;
canvas.width = cssW * dpr; canvas.height = cssH * dpr;
ctx.scale(dpr, dpr);
```

**The read-back trap** (learned the hard way on the timemachines demo): never
derive `cssW`/`cssH` from the canvas's own `width`/`height` attributes — you
scaled those by `dpr` last frame, so on retina the canvas doubles every redraw
and the page "jumps." Pin the CSS size somewhere nothing rewrites (a `data-h`
attribute, a constant), and resize the backing store **only when the layout
size actually changed**. If the y-range is recomputed per frame, smooth it
(EWMA toward the new range, never clipping data) so a spike scrolling in or
out glides instead of snapping the axes.

- One light baseline (`#e2e2e2`, 1px) is the only axis chrome. **No gridlines,
  no border box, no tick forest.** The data is the decoration.
- Observations: small dots (~1.7px radius), never a connecting line — the line
  is the *model's* mean (1.8px), and keeping them distinct shows residuals.
- Pad the drawing area (~36px) and recompute the y-range from what is visible
  *including the fan*, with ~8% headroom.

## Motion, sparingly

- Reveal the series with `requestAnimationFrame` and a **speed slider**;
  animation is how a stream reads as a stream. Always provide Pause/Resume,
  and make "Regenerate" reseed visibly.
- The only CSS transition on the page: bar widths, `width 0.12s linear`.
  Nothing else animates. Easing curves on charts read as advertising.

## Live diagnostics as ranked bars

Whatever your model weighs — ensemble members, scales, features — show it as a
ranked bar list that updates each frame, because watching weights shift *is*
the explanation:

```html
<div class="wrow">
  <span class="wlabel">fractional differencing → leaf</span>
  <span class="wtrack"><span class="wbar" style="width:73%"></span></span>
  <span class="wval">31%</span>
</div>
```

- Right-align labels in a fixed-width column (`flex: 0 0 200px`, ellipsis);
  bars in a rounded grey track; values in a fixed 34px column.
- Normalize to shares (softmax if you have log-scores), sort descending,
  drop rows under ~0.5%, cap at 8. A 40-row weight list is a log file.

## Typography and chrome

- `font-variant-numeric: tabular-nums` on **every** number that changes —
  values, sliders, status lines. Jittering digits are the #1 amateur tell.
- Muted secondary text (`#666`–`#888`) for status, legends, captions; reserve
  full-contrast text for headings and data labels.
- A legend of 14px rounded swatches naming things plainly: "observation",
  "1-step mean", "k-step forecast fan". No abbreviations you'd have to define.
- One sentence under the chart telling the eye what to notice ("the band
  widens with the horizon; on mean-reverting data the fan curves home").

## The skeleton

```html
<main>
  <h1>Title</h1>
  <p class="subtitle">One sentence: what is live on this page.</p>
  <div class="panel">           <!-- border 1px #e6e6ef, radius 8, padding 18 -->
    <div class="controls">…sliders/selects, label above control…</div>
    <canvas id="plot" width="940" height="420"></canvas>
    <div class="legend">…swatches…</div>
    <p class="status">step 214 / 240</p>
    <div class="weights">…ranked bars…</div>
  </div>
  <p>One paragraph of what the demo shows. Then stop.</p>
</main>
```

Single centered column (~940px), generous whitespace, no sidebars. If the page
needs tabs, it needs to be two pages.

## Anti-patterns (refuse these politely)

- Default chart-library themes: rainbow palettes, drop shadows, gradient fills.
- Points joined by lines *and* a mean line (which is the data?).
- Legends naming series "y", "yhat", "yhat_lower".
- Percent axes that rescale every frame (pin the y-range to the revealed data
  plus fan, recompute smoothly).
- Spinners. If compute takes time, reveal progressively — it is a stream.

The test: pause the animation at any frame and screenshot it. If it could go in
a paper without edits, the page is done.
