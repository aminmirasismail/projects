"""Build the 'Over the years' section of folio.html from renders/v2/structure.json.

    python durability_page.py

Inline SVG line chart (one y axis, thin 2 px lines, legend + direct labels, recessive grid) with a
hover crosshair, plus the grip table. Replaces the block between the DURABILITY markers.
Series colours: the reference palette's validated dark-mode categorical slots 1-3, in order.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(HERE, "renders", "v2", "structure.json")))
du = d["duty"]
cons, typ = du["cases"]["conservative"], du["cases"]["typical"]
p = cons["every 2 weeks"]

W, H = 760, 340
L, R, T, B = 56, 150, 20, 44
xmax, ymax = 10.0, 1.4


def X(y):
    return L + (W - L - R) * y / xmax


def Y(v):
    return T + (H - T - B) * (1 - v / ymax)


def path(xs, ys):
    return "M" + " L".join(f"{X(x):.1f},{Y(v):.1f}" for x, v in zip(xs, ys))


yrs = p["years"]
series = [
    ("worst", "No-recovery estimate", "#d95926", p["worst_peak"]),
    ("use", "During a dry (realistic)", "#3987e5", p["real_peak"]),
    ("rest", "Folded, between dries", "#199e70", p["real_rest"]),
]
cont_x = [i / 10 for i in range(0, 101)]
n, tau, d0 = cons["n"], cons["tau_h"], du["d0_mm"]
cont_y = [d0 * (1 + (x * 8760 / tau) ** n) if x > 0 else d0 for x in cont_x]

svg = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-labelledby="durT durD" class="dchart">',
       '<title id="durT">Front-edge sag of the shelf over ten years</title>',
       '<desc id="durD">Conservative PLA creep, brushes hung for 24 hours every two weeks. Sag during a dry stays '
       'near 0.3 mm; between dries it settles under 0.07 mm; even if no creep ever recovered it stays under 0.7 mm. '
       'Left loaded continuously it would reach about 1.3 mm.</desc>']
for v in (0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.2, 1.4):
    svg.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" class="g{" b" if v == 0 else ""}"/>')
    svg.append(f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" class="ax" text-anchor="end">{v:.1f}</text>')
for x in range(0, 11, 2):
    svg.append(f'<text x="{X(x):.1f}" y="{H - B + 18}" class="ax" text-anchor="middle">{x}</text>')
svg.append(f'<text x="{(L + W - R) / 2:.1f}" y="{H - 6}" class="ax" text-anchor="middle">years of use</text>')
svg.append(f'<text x="{L - 44}" y="{T - 6}" class="ax">mm</text>')
# 1 mm line: the "visible" threshold used throughout
svg.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(1.0):.1f}" y2="{Y(1.0):.1f}" class="lim"/>')
svg.append(f'<text x="{L + 6}" y="{Y(1.0) - 6:.1f}" class="ax">1 mm: about where you could start to see it</text>')
svg.append(f'<path d="{path(cont_x, cont_y)}" class="ref"/>')
svg.append(f'<text x="{X(10) + 6:.1f}" y="{Y(cont_y[-1]) + 4:.1f}" class="lbl">hard limit</text>')
for key, name, col, ys in series:
    svg.append(f'<path d="{path(yrs, ys)}" stroke="{col}" class="ln"/>')
    svg.append(f'<text x="{X(10) + 6:.1f}" y="{Y(ys[-1]) + 4:.1f}" class="lbl">{["no recovery", "during a dry", "folded"][[s[0] for s in series].index(key)]}</text>')
svg.append(f'<line class="xh" x1="0" x2="0" y1="{T}" y2="{H - B}" visibility="hidden"/>')
svg.append(f'<rect class="hit" x="{L}" y="{T}" width="{W - L - R}" height="{H - T - B}" fill="transparent"/>')
svg.append("</svg>")

# hover data, thinned to ~monthly
step = 2
hov = [dict(y=round(yrs[i], 2), w=p["worst_peak"][i], u=p["real_peak"][i], r=p["real_rest"][i],
            c=round(d0 * (1 + (max(yrs[i], 1e-6) * 8760 / tau) ** n), 3)) for i in range(0, len(yrs), step)]

legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{nm}</span>' for _k, nm, c, _ys in series)
legend += '<span class="lg"><i class="dash"></i>Hard limit: brushes never taken off</span>'

g_c, g_t = cons["grip"], typ["grip"]


def row(label, key):
    return (f'<tr><td>{label}</td><td class="num">{g_t[key]["sf_start_wet"]} / {g_t[key]["sf_end_dry"]}</td>'
            f'<td class="num">{g_c[key]["sf_start_wet"]} / {g_c[key]["sf_end_dry"]}</td></tr>')


s2, s3 = cons["every 2 weeks"]["summary"], cons["every 3 weeks"]["summary"]
html = f'''<!-- DURABILITY -->
  <section id="years">
    <div class="head"><span class="tag">Durability</span><h2>Over the years</h2>
      <p class="muted">Chelsea's routine: unfold, hang the wet brushes for 24 hours, take them off, fold it away for 2–3 weeks. PLA creeps under load, then slowly recovers once the load is off, so the right question is what happens over hundreds of those cycles. Assumptions: conservative PLA creep, the same stiffness I used above; and one hot shower during every dry, counted as an hour at about 30 °C, when PLA creeps roughly 4× faster.</p></div>
    <figure class="chartfig">
      <div class="legend">{legend}</div>
      <div class="chartwrap">{"".join(svg)}<div class="tip" hidden></div></div>
      <figcaption>Front-edge sag, brushes hung every 2 weeks, 10 years (260 dries)</figcaption>
    </figure>
    <div class="facts">
      <div class="fact"><span class="tag">During a dry, 10 years in</span><b>{s2["10 y"]["real_in_use"]:.2f} mm</b><p>Compared with {s2["1 y"]["real_in_use"]:.2f} mm in year one. It barely creeps up.</p></div>
      <div class="fact"><span class="tag">Folded, 10 years in</span><b>{s2["10 y"]["real_resting"]:.2f} mm</b><p>What's left between uses: a few hundredths of a mm.</p></div>
      <div class="fact"><span class="tag">If nothing recovered</span><b>{s2["10 y"]["worst_in_use"]:.2f} mm</b><p>The 260 dries treated as one 9-month load. A pessimistic estimate.</p></div>
      <div class="fact"><span class="tag">Hard limit, 10 years</span><b>{cons["hard_bound_10y"]:.2f} mm</b><p>Brushes never taken off for 10 years. No pattern of use can sag more ({typ["hard_bound_10y"]:.2f} mm with typical creep). That's 0.5° at most.</p></div>
    </div>
    <div class="cards">
      <div class="card ok"><h3>The frame: good for many years</h3><p>Ten years of Chelsea's routine leaves the shelf sagging less than it would after three months loaded non-stop. Every 3 weeks instead of 2, it's {s3["10 y"]["real_in_use"]:.2f} mm. Even if no creep ever recovered it stays under 0.7 mm, and the absolute limit, brushes never taken off for 10 years, is {cons["hard_bound_10y"]:.2f} mm, about half a degree. Forgetting the brushes on it for a week only adds about {cons["forgot_one_week_mm"] - du["d0_mm"] * (1 + (27 / tau) ** n):.2f} mm compared with a normal day, and that recovers once it's folded. Steam matters less than you might think: it softens PLA a little for an hour, nowhere near PLA's 55–60 °C softening point. Even a much steamier shower (10× faster creep for 1.5 h every dry) moves a dry's sag from {du["steam_4x_peak_mm"]:.2f} to {du["steam_10x_peak_mm"]:.2f} mm. Opening the doors helps the brushes dry more than it helps the plastic.</p></div>
      <div class="card warn"><h3>The clips age first</h3><p>The spring fingers are held bent for each 24-hour dry at about 14 MPa, roughly 30% of PLA's strength. That's much harder working than the frame (under 1.2 MPa), so their grip relaxes faster than this simple model shows, and only partly recovers while stored. The table is optimistic. Plan on the cartridges being consumables: print a spare set now and expect to reprint them about once a year (20 minutes each). The test strip, hung wet for 72 h and then re-checked after a week off, will show the real rate.</p></div>
    </div>
    <div class="tablewrap"><table>
      <thead><tr><th scope="col">Clip hold safety factor, wet going on / dry at the end (simple model, optimistic)</th><th scope="col">Typical PLA creep</th><th scope="col">Conservative creep</th></tr></thead>
      <tbody>
        {row("New clip, any dry", "new")}
        {row("After 1 year, if none of the relaxation came back", "after 1 y, worst")}
        {row("After 10 years, if none of it came back", "after 10 y, worst")}
      </tbody>
    </table></div>
  </section>
<script>
(() => {{
  const D = {json.dumps(hov)};
  const svg = document.querySelector('#years svg'), tip = document.querySelector('#years .tip');
  const xh = svg.querySelector('.xh'), hit = svg.querySelector('.hit');
  const L = {L}, R = {W - R}, VW = {W};
  hit.addEventListener('pointermove', e => {{
    const b = svg.getBoundingClientRect(), sx = (e.clientX - b.left) * VW / b.width;
    const yr = Math.max(0, Math.min(10, (sx - L) / (R - L) * 10));
    let best = D[0]; for (const d of D) if (Math.abs(d.y - yr) < Math.abs(best.y - yr)) best = d;
    const px = L + (R - L) * best.y / 10;
    xh.setAttribute('x1', px); xh.setAttribute('x2', px); xh.setAttribute('visibility', 'visible');
    tip.innerHTML = `<b>${{best.y.toFixed(1)}} years</b><br>No recovery: ${{best.w.toFixed(2)}} mm<br>During a dry: ${{best.u.toFixed(2)}} mm<br>Folded: ${{best.r.toFixed(2)}} mm<br><span class="m">Hard limit: ${{best.c.toFixed(2)}} mm</span>`;
    tip.hidden = false;
    const left = px / VW * b.width;
    tip.style.left = Math.min(left + 12, b.width - 190) + 'px';
  }});
  hit.addEventListener('pointerleave', () => {{ tip.hidden = true; xh.setAttribute('visibility', 'hidden'); }});
}})();
</script>
<!-- /DURABILITY -->
'''

css = '''<!-- DURCSS -->
<style>
.chartfig { gap: 10px; }
.chartwrap { position: relative; background: var(--surface); border-radius: 8px; padding: 12px 8px 4px; }
.dchart { width: 100%; height: auto; display: block; }
.dchart .g { stroke: #2c2c2a; stroke-width: 1; }
.dchart .g.b { stroke: #383835; }
.dchart .ax { fill: #898781; font: 11px var(--f-mono); }
.dchart .lbl { fill: var(--ink-2); font: 12px var(--f-display); }
.dchart .ln { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.dchart .ref { fill: none; stroke: #898781; stroke-width: 1.5; stroke-dasharray: 5 4; }
.dchart .lim { stroke: #52514e; stroke-width: 1; stroke-dasharray: 2 3; }
.dchart .xh { stroke: #898781; stroke-width: 1; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; font-size: 13px; color: var(--ink-2); }
.lg { display: inline-flex; align-items: center; gap: 8px; }
.lg i { width: 14px; height: 3px; border-radius: 2px; display: inline-block; }
.lg i.dash { background: repeating-linear-gradient(90deg, #898781 0 5px, transparent 5px 9px); }
.tip { position: absolute; top: 14px; background: #0d0d0e; border: 1px solid var(--rule); border-radius: 6px; padding: 8px 10px; font-size: 12px; line-height: 1.5; pointer-events: none; color: var(--ink); min-width: 170px; }
.tip .m { color: var(--ink-2); }
</style>
<!-- /DURCSS -->
'''

page = os.path.join(HERE, "folio.html")
s = open(page, encoding="utf-8").read()
if "<!-- DURCSS -->" in s:
    a, b = s.index("<!-- DURCSS -->"), s.index("<!-- /DURCSS -->") + len("<!-- /DURCSS -->\n")
    s = s[:a] + s[b:]
s = s.replace("</style>\n", "</style>\n" + css, 1)
if "<!-- DURABILITY -->" in s:
    a, b = s.index("<!-- DURABILITY -->"), s.index("<!-- /DURABILITY -->") + len("<!-- /DURABILITY -->\n")
    s = s[:a] + html + s[b:]
else:
    marker = '  <section id="test">'
    s = s.replace(marker, html + "\n" + marker, 1)
open(page, "w", encoding="utf-8").write(s)
print("ok")
