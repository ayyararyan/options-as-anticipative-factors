from pathlib import Path
import json
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
with open(ROOT / 'results' / 'summary.json', 'r', encoding='utf-8') as f:
    p1 = json.load(f)
with open(ROOT / 'results' / 'phase2_summary.json', 'r', encoding='utf-8') as f:
    p2 = json.load(f)

metrics = {x['model']: x for x in p1['regression_metrics']}
qlike = [
    metrics['history_only']['qlike'],
    metrics['history_plus_option_level']['qlike'],
    metrics['history_plus_level_plus_skew']['qlike'],
]
labels_a = ['Spot history', '+ option level', '+ smile shape']

boot = {x['event']: x for x in p2['bootstrap'] if x['metric'] == 'brier'}
events = ['two_sided_1sigma', 'down_1sigma', 'up_1sigma']
labels_b = [r'Large move\n$|z| \geq 1$', r'Downside tail\n$z \leq -1$', r'Upside tail\n$z \geq 1$']
diffs = np.array([boot[e]['mean_diff_plus_shape_minus_level'] for e in events])
lo = np.array([boot[e]['ci_lo_95'] for e in events])
hi = np.array([boot[e]['ci_hi_95'] for e in events])
yerr = np.vstack([diffs - lo, hi - diffs])

outdir = ROOT / 'results' / 'figures'
outdir.mkdir(parents=True, exist_ok=True)

# PDF/PNG: conventional Matplotlib academic figure.
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 9.5,
    'axes.titlesize': 10.5,
    'axes.labelsize': 9.5,
    'xtick.labelsize': 8.5,
    'ytick.labelsize': 8.5,
})
fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.25), constrained_layout=True)
ax = axes[0]
x = np.arange(3)
ax.bar(x, qlike, width=0.62, color=['0.72', '0.38', '0.58'], edgecolor='black', linewidth=0.6)
ax.set_xticks(x, labels_a)
ax.set_ylabel('OOS QLIKE (lower is better)')
ax.set_ylim(0, 0.205)
ax.set_title('(a) Forecasting intraday realized variance', loc='left', fontweight='bold')
for i, v in enumerate(qlike):
    ax.text(i, v + 0.004, f'{v:.3f}', ha='center', va='bottom', fontsize=8.5)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='y', linewidth=0.35, alpha=0.35)

ax = axes[1]
x = np.arange(3)
ax.errorbar(x, diffs, yerr=yerr, fmt='o', markersize=5, color='black', ecolor='0.35', elinewidth=1.0, capsize=3)
ax.axhline(0, color='0.25', linewidth=0.8)
ax.set_xticks(x, labels_b)
ax.set_ylabel('Change in Brier score from adding shape')
ax.set_title('(b) Does smile shape add information?', loc='left', fontweight='bold')
ax.set_ylim(-0.025, 0.023)
ax.text(0.02, 0.02, 'Negative = improvement', transform=ax.transAxes, ha='left', va='bottom', fontsize=8)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)
ax.grid(axis='y', linewidth=0.35, alpha=0.35)
for ext in ['png', 'pdf']:
    fig.savefig(outdir / f'main_result.{ext}', dpi=300, bbox_inches='tight')
plt.close(fig)

# SVG: compact browser-friendly rendering of the same figure for GitHub.
W, H = 920, 410
left = (70, 55, 390, 290)
right = (535, 55, 345, 290)

def sx(panel, i, n=3):
    x0, _, w, _ = panel
    return x0 + (i + 0.5) * w / n

def y_left(v):
    _, y0, _, h = left
    return y0 + h * (1 - v / 0.205)

def y_right(v):
    _, y0, _, h = right
    lo_y, hi_y = -0.025, 0.023
    return y0 + h * (hi_y - v) / (hi_y - lo_y)

parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<style>
text {{ font-family: Georgia, 'Times New Roman', serif; fill:#111; }}
.title {{ font-size:17px; font-weight:700; }}
.label {{ font-size:13px; }}
.small {{ font-size:12px; }}
.axis {{ stroke:#111; stroke-width:1.3; }}
.grid {{ stroke:#bbb; stroke-width:0.6; opacity:0.45; }}
</style>
<rect width="100%" height="100%" fill="white"/>
<text x="70" y="28" class="title">(a) Forecasting intraday realized variance</text>
<text x="535" y="28" class="title">(b) Does smile shape add information?</text>''']

for tick in [0, .05, .10, .15, .20]:
    y = y_left(tick)
    parts.append(f'<line x1="70" y1="{y:.1f}" x2="460" y2="{y:.1f}" class="grid"/>')
    parts.append(f'<text x="62" y="{y+4:.1f}" text-anchor="end" class="small">{tick:.2f}</text>')
parts += [
    '<line x1="70" y1="55" x2="70" y2="345" class="axis"/>',
    '<line x1="70" y1="345" x2="460" y2="345" class="axis"/>',
    '<text x="18" y="205" transform="rotate(-90 18 205)" text-anchor="middle" class="label">OOS QLIKE (lower is better)</text>'
]
barw = 72
fills = ['#b8b8b8', '#666666', '#999999']
for i, (v, lab, fill) in enumerate(zip(qlike, labels_a, fills)):
    x = sx(left, i)
    y = y_left(v)
    parts.append(f'<rect x="{x-barw/2:.1f}" y="{y:.1f}" width="{barw}" height="{345-y:.1f}" fill="{fill}" stroke="#111" stroke-width="1"/>')
    parts.append(f'<text x="{x:.1f}" y="{y-8:.1f}" text-anchor="middle" class="label">{v:.3f}</text>')
    parts.append(f'<text x="{x:.1f}" y="370" text-anchor="middle" class="small">{lab}</text>')

for tick in [-.02, -.01, 0, .01, .02]:
    y = y_right(tick)
    parts.append(f'<line x1="535" y1="{y:.1f}" x2="880" y2="{y:.1f}" class="grid"/>')
    parts.append(f'<text x="527" y="{y+4:.1f}" text-anchor="end" class="small">{tick:.3f}</text>')
parts += [
    '<line x1="535" y1="55" x2="535" y2="345" class="axis"/>',
    '<line x1="535" y1="345" x2="880" y2="345" class="axis"/>',
    f'<line x1="535" y1="{y_right(0):.1f}" x2="880" y2="{y_right(0):.1f}" stroke="#333" stroke-width="1.2"/>',
    '<text x="490" y="205" transform="rotate(-90 490 205)" text-anchor="middle" class="label">Change in Brier score from adding shape</text>',
    '<text x="548" y="330" class="small">Negative = improvement</text>'
]
right_labels = [('Large move', '|z| >= 1'), ('Downside tail', 'z <= -1'), ('Upside tail', 'z >= 1')]
for i, (d, l, h, labs) in enumerate(zip(diffs, lo, hi, right_labels)):
    x = sx(right, i)
    yd, yl, yh = y_right(d), y_right(l), y_right(h)
    parts.append(f'<line x1="{x:.1f}" y1="{yh:.1f}" x2="{x:.1f}" y2="{yl:.1f}" stroke="#555" stroke-width="2"/>')
    parts.append(f'<line x1="{x-8:.1f}" y1="{yh:.1f}" x2="{x+8:.1f}" y2="{yh:.1f}" stroke="#555" stroke-width="2"/>')
    parts.append(f'<line x1="{x-8:.1f}" y1="{yl:.1f}" x2="{x+8:.1f}" y2="{yl:.1f}" stroke="#555" stroke-width="2"/>')
    parts.append(f'<circle cx="{x:.1f}" cy="{yd:.1f}" r="5.5" fill="#111"/>')
    parts.append(f'<text x="{x:.1f}" y="370" text-anchor="middle" class="small">{labs[0]}</text>')
    parts.append(f'<text x="{x:.1f}" y="388" text-anchor="middle" class="small">{labs[1]}</text>')
parts.append('</svg>')
(outdir / 'main_result.svg').write_text('\n'.join(parts), encoding='utf-8')
