#!/usr/bin/env python3
"""Generoi Tesla-ohjelmistoversiot -tilastosivun data.json:sta.
Käyttö: python3 rakenna_sivu.py [ulostulo.html]"""
import json, os, sys, html, datetime, re
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, '..', 'Tesla-ohjelmistoversiot-v1.html')
D = json.load(open(os.path.join(HERE, 'data.json')))
HEL = ZoneInfo('Europe/Helsinki'); CHI = ZoneInfo('America/Chicago')
E = html.escape
HW = ['NoAP', 'AP1', 'AP2', 'AP2.5', 'AP3', 'AP4']
HWL = {'NoAP': 'Ei AP', 'AP1': 'HW1 / AP1', 'AP2': 'HW2', 'AP2.5': 'HW2.5', 'AP3': 'HW3', 'AP4': 'HW4 / AI4'}
HWL_EN = {'NoAP': 'No AP', 'AP1': 'HW1 / AP1', 'AP2': 'HW2', 'AP2.5': 'HW2.5', 'AP3': 'HW3', 'AP4': 'HW4 / AI4'}
MODELS = ['S', '3', 'X', 'Y', 'CT']
ML = {'S': 'Model S', '3': 'Model 3', 'X': 'Model X', 'Y': 'Model Y', 'CT': 'Cybertruck'}
EUROPE = {'Finland', 'Sweden', 'Norway', 'Denmark', 'Iceland', 'Estonia', 'Latvia', 'Lithuania', 'Poland', 'Germany',
          'Netherlands', 'Belgium', 'Luxembourg', 'France', 'United Kingdom', 'Ireland', 'Spain', 'Portugal', 'Italy',
          'Switzerland', 'Austria', 'Czech Republic', 'Czechia', 'Slovakia', 'Slovenia', 'Hungary', 'Romania', 'Bulgaria',
          'Greece', 'Croatia', 'Serbia', 'Malta', 'Cyprus', 'Monaco', 'Liechtenstein', 'Ukraine', 'Bosnia and Herzegovina',
          'Montenegro', 'North Macedonia', 'Albania', 'Andorra', 'San Marino', 'Turkey', 'Türkiye'}

def bi(fi, en, tag='span'):
    return '<span class="fi">%s</span><span class="en">%s</span>' % (fi, en)

def fmt(n):
    return '{:,}'.format(n).replace(',', '\u00a0') if isinstance(n, int) else str(n)

def pct(a, b):
    return ('%.1f' % (100.0 * a / b)).replace('.', ',') if b else '–'

def vt(v):
    return tuple(int(x) for x in re.findall(r'\d+', v))

def hel(dt):
    dt = dt.astimezone(HEL)
    return dt, ('EEST, UTC+3' if dt.utcoffset().total_seconds() == 10800 else 'EET, UTC+2')

fetched = datetime.datetime.fromisoformat(D['fetched_utc'])
fdt, fz = hel(fetched)
FETCHED_FI = '%s klo %s Suomen aikaa (%s)' % (fdt.strftime('%-d.%-m.%Y'), fdt.strftime('%H.%M'), fz)
FETCHED_EN = '%s %s Finnish time (%s)' % (fdt.strftime('%-d %b %Y'), fdt.strftime('%H:%M'), fz)

TF = D['teslafi']; DET = D['teslafi_detail']; TS = D.get('teslascope') or {}; NA = D.get('nata') or {}
fsd_of = {v['v']: v['fsd'] for v in TF['versions']}
pend_of = {v['v']: v['pending'] for v in TF['versions']}

# --- per-version vectors
rows = []
for v in TF['versions']:
    d = DET.get(v['v'])
    if not d: continue
    w = d['models'].get('All', [0] * 6)
    fi = d['countries'].get('Finland', [0] * 6)
    eu = [0] * 6
    for c, vals in d['countries'].items():
        if c in EUROPE:
            eu = [a + b for a, b in zip(eu, vals)]
    rows.append({'v': v['v'], 'f': v['fsd'], 'p': v['pending'], 'w': w, 'fi': fi, 'eu': eu,
                 'm': {k: d['models'][k] for k in MODELS if k in d['models']}})
missing_detail = [v['v'] for v in TF['versions'] if v['v'] not in DET]
rows.sort(key=lambda r: vt(r['v']), reverse=True)

tot_w = sum(sum(r['w']) for r in rows); tot_fi = sum(sum(r['fi']) for r in rows); tot_eu = sum(sum(r['eu']) for r in rows)

def best(getter, min_n):
    cand = [(r, getter(r)) for r in rows if getter(r) >= min_n]
    if not cand: return None, None
    newest = max(cand, key=lambda x: vt(x[0]['v']))
    common = max(cand, key=lambda x: x[1])
    return newest, common

def total(r, scope, model=None, hws=None):
    vec = r['m'].get(model, [0] * 6) if model else r[scope]
    idx = [HW.index(h) for h in hws] if hws else range(6)
    return sum(vec[i] for i in idx)

# Finland details
fi_rows = sorted([r for r in rows if sum(r['fi'])], key=lambda r: sum(r['fi']), reverse=True)
fi_new, fi_common = best(lambda r: sum(r['fi']), 1)
fi_hw_tot = [sum(r['fi'][i] for r in rows) for i in range(6)]

# recent updates in Finland / Europe from TeslaFi 100 most recent
def conv(t):
    try:
        dt = datetime.datetime.strptime(t, '%m/%d/%Y %I:%M %p').replace(tzinfo=CHI)
        return hel(dt)[0].strftime('%-d.%-m. %H.%M')
    except Exception:
        return t
recent = TF.get('recent', [])
recent_fi = [x for x in recent if x['country'] == 'Finland']
recent_eu = [x for x in recent if x['country'] in EUROPE]

# --- SVG bar chart (horizontal)
def svg_bars(items, color='#38bdf8', w=640, label_w=150):
    if not items: return ''
    mx = max(c for _, c, _ in items) or 1
    bh, gap = 22, 6; h = len(items) * (bh + gap) + 4
    out = ['<svg viewBox="0 0 %d %d" width="100%%" role="img" xmlns="http://www.w3.org/2000/svg" style="max-width:%dpx">' % (w, h, w)]
    for i, (lab, c, extra) in enumerate(items):
        y = i * (bh + gap) + 2; bw = (w - label_w - 110) * c / mx
        out.append('<text x="%d" y="%d" fill="#e2e8f0" font-size="13" text-anchor="end">%s</text>' % (label_w - 8, y + 16, E(lab)))
        out.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="4" fill="%s"/>' % (label_w, y, max(bw, 2), bh, color))
        out.append('<text x="%.1f" y="%d" fill="#94a3b8" font-size="12">%s</text>' % (label_w + bw + 6, y + 16, E(extra)))
    out.append('</svg>'); return ''.join(out)

def stacked_hw_svg(vec_by_label, w=640):
    """stacked horizontal bars of hardware shares per label"""
    cols = {'NoAP': '#64748b', 'AP1': '#a78bfa', 'AP2': '#f472b6', 'AP2.5': '#fb923c', 'AP3': '#22c55e', 'AP4': '#38bdf8'}
    lw = 110; bh = 22; gap = 8; h = len(vec_by_label) * (bh + gap) + 34
    o = ['<svg viewBox="0 0 %d %d" width="100%%" xmlns="http://www.w3.org/2000/svg" style="max-width:%dpx">' % (w, h, w)]
    for i, (lab, vec) in enumerate(vec_by_label):
        y = i * (bh + gap) + 2; t = sum(vec) or 1; x = lw
        o.append('<text x="%d" y="%d" fill="#e2e8f0" font-size="13" text-anchor="end">%s</text>' % (lw - 8, y + 16, E(lab)))
        for k, c in zip(HW, vec):
            ww = (w - lw - 10) * c / t
            if ww > 0:
                o.append('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s"><title>%s: %d (%s %%)</title></rect>' % (x, y, ww, bh, cols[k], HWL[k], c, pct(c, t)))
            x += ww
    y = len(vec_by_label) * (bh + gap) + 14; x = lw
    for k in HW:
        o.append('<rect x="%d" y="%d" width="12" height="12" fill="%s"/><text x="%d" y="%d" fill="#94a3b8" font-size="12">%s</text>' % (x, y, cols[k], x + 16, y + 11, HWL[k]))
        x += 88
    o.append('</svg>'); return ''.join(o)

# ---------------- sections
rl = TF.get('rolling') or {}
kpi = []
kpi.append((bi('Jaossa nyt (TeslaFi, maailma)', 'Rolling out now (TeslaFi, world)'), rl.get('version', '–'),
            bi('%s autoa (%s %%), %s odottaa' % (fmt(rl.get('cars', 0)), str(rl.get('pct', '')).replace('.', ','), fmt(rl.get('pending', 0))),
               '%s cars (%s%%), %s waiting' % (rl.get('cars', 0), rl.get('pct', ''), rl.get('pending', 0)))))
if fi_common:
    kpi.append((bi('Yleisin versio Suomessa', 'Most common in Finland'), fi_common[0]['v'],
                bi('%d / %d suomalaista autoa (%s %%)' % (fi_common[1], tot_fi, pct(fi_common[1], tot_fi)),
                   '%d of %d Finnish cars' % (fi_common[1], tot_fi))))
if fi_new:
    kpi.append((bi('Uusin versio Suomessa', 'Newest seen in Finland'), fi_new[0]['v'],
                bi('%d autoa' % fi_new[1], '%d cars' % fi_new[1])))
kpi.append((bi('Suomalaisia autoja TeslaFi-otoksessa', 'Finnish cars in TeslaFi sample'), fmt(tot_fi),
            bi('koko otos %s autoa' % fmt(tot_w), 'whole sample %s cars' % tot_w)))
kpi_html = ''.join('<div class="kpi"><div class="kl">%s</div><div class="kv">%s</div><div class="ks">%s</div></div>' % k for k in kpi)

# Finland table + chart
fi_chart = svg_bars([(r['v'], sum(r['fi']), '%d (%s %%)' % (sum(r['fi']), pct(sum(r['fi']), tot_fi))) for r in fi_rows[:15]])
def fi_table():
    h = ['<table class="st"><thead><tr><th>%s</th><th>FSD</th>' % bi('Versio', 'Version')]
    h += ['<th class="n">%s</th>' % HWL[k] for k in HW] + ['<th class="n">%s</th><th class="n">%%</th></tr></thead><tbody>' % bi('Yht.', 'Total')]
    for r in fi_rows:
        t = sum(r['fi'])
        h.append('<tr><td><b>%s</b></td><td class="mut">%s</td>%s<td class="n"><b>%d</b></td><td class="n">%s</td></tr>' % (
            E(r['v']), E(r['f']), ''.join('<td class="n">%s</td>' % (c or '<span class="mut">·</span>') for c in r['fi']), t, pct(t, tot_fi)))
    h.append('<tr class="tot"><td>%s</td><td></td>%s<td class="n">%d</td><td class="n">100</td></tr></tbody></table>' % (
        bi('Yhteensä', 'Total'), ''.join('<td class="n">%d</td>' % c for c in fi_hw_tot), tot_fi))
    return ''.join(h)

# newest/most common per hardware & per model (world) + Finland per hardware
def per_table():
    h = ['<table class="st"><thead><tr><th>%s</th><th>%s</th><th>%s</th><th class="n">%s</th><th>%s</th><th class="n">%%</th></tr></thead><tbody>' % (
        bi('Ryhmä', 'Group'), bi('Alue', 'Area'), bi('Uusin versio (≥3 autoa, Suomi ≥1)', 'Newest version (≥3 cars, Finland ≥1)'), bi('autoja', 'cars'),
        bi('Yleisin versio', 'Most common version'), )]
    def line(name, area, getter, denom, mn=3):
        n, c = best(getter, mn)
        if not n: return
        h.append('<tr><td>%s</td><td>%s</td><td><b>%s</b> <span class="mut">%s</span></td><td class="n">%d</td><td><b>%s</b></td><td class="n">%s</td></tr>' % (
            name, area, E(n[0]['v']), E(n[0]['f']), n[1], E(c[0]['v']), pct(c[1], denom)))
    for m in MODELS:
        den = sum(total(r, 'w', m) for r in rows)
        if den: line(ML[m], bi('Maailma', 'World'), lambda r, m=m: total(r, 'w', m), den)
    for k in HW:
        den = sum(total(r, 'w', None, [k]) for r in rows)
        if den: line(HWL[k], bi('Maailma', 'World'), lambda r, k=k: total(r, 'w', None, [k]), den)
    for k in HW:
        den = sum(total(r, 'fi', None, [k]) for r in rows)
        if den: line(HWL[k], '<b>%s</b>' % bi('Suomi', 'Finland'), lambda r, k=k: total(r, 'fi', None, [k]), den, 1)
    h.append('</tbody></table>'); return ''.join(h)

# Model x hardware matrix (world)
def matrix():
    h = ['<table class="st"><thead><tr><th>%s</th>%s<th class="n">%s</th></tr></thead><tbody>' % (
        bi('Malli', 'Model'), ''.join('<th class="n">%s</th>' % HWL[k] for k in HW), bi('Yht.', 'Total'))]
    for m in MODELS:
        vec = [sum(r['m'].get(m, [0] * 6)[i] for r in rows) for i in range(6)]
        if sum(vec):
            h.append('<tr><td>%s</td>%s<td class="n"><b>%s</b></td></tr>' % (ML[m], ''.join('<td class="n">%s</td>' % (fmt(c) if c else '<span class="mut">·</span>') for c in vec), fmt(sum(vec))))
    h.append('</tbody></table>'); return ''.join(h)

model_hw_svg = stacked_hw_svg([(ML[m], [sum(r['m'].get(m, [0] * 6)[i] for r in rows) for i in range(6)]) for m in MODELS
                               if sum(sum(r['m'].get(m, [0] * 6)) for r in rows)] +
                              [('Suomi / FI', fi_hw_tot)])

# Teslascope active
def ts_table():
    if not TS.get('active'): return '<p class="mut">%s</p>' % bi('Teslascope-tietoja ei saatu.', 'No Teslascope data.')
    h = ['<table class="st"><thead><tr><th>%s</th><th>FSD</th><th>%s</th><th>%s</th><th>%s</th><th class="n">%s</th></tr></thead><tbody>' % (
        bi('Versio', 'Version'), bi('Julkaistu', 'Released'), bi('Viimeisin aalto', 'Latest wave'), bi('Alueet', 'Regions'), bi('Osuus', 'Share'))]
    for a in TS['active']:
        eu = 'Europe' in a['regions'] or 'Finland' in a['regions']
        h.append('<tr%s><td><b>%s</b></td><td class="mut">%s</td><td>%s</td><td>%s</td><td>%s%s</td><td class="n">%s</td></tr>' % (
            ' class="hl"' if eu else '', E(a['v']), E(a['fsd']), E(a['released']), E(a['wave_rel']), E(a['regions']),
            ' <span class="tag">EU</span>' if eu else '', E(a['dist'])))
    h.append('</tbody></table>'); return ''.join(h)

def ts_fsd():
    out = []
    for k, lst in (TS.get('fsd') or {}).items():
        items = ', '.join('%s → %s (%s)' % (E(x['fsd'] or ''), E(x['v']), E(x['dist'])) for x in lst[:6])
        out.append('<li><b>%s:</b> %s</li>' % (k, items))
    return '<ul class="mut small">%s</ul>' % ''.join(out) if out else ''

def ts_pages():
    out = []
    for v, p in (TS.get('pages') or {}).items():
        if not p.get('hw') and not p.get('models'): continue
        hw = ', '.join('%s %s %%' % (a, c.replace('.', ',')) for a, b, c in p['hw'])
        md = ', '.join('%s %s %%' % (a, c.replace('.', ',')) for a, b, c in p['models'])
        ct = ', '.join('%s %s %%' % (a.strip(), c.replace('.', ',')) for a, c in p['countries'][:6])
        fi = [c for a, c in p['countries'] if a.strip() == 'Finland']
        out.append('<tr><td><a href="%s">%s</a></td><td class="n">%s</td><td>%s</td><td>%s</td><td>%s%s</td></tr>' % (
            E(p['url']), E(v), fmt(p.get('installs') or 0), md, hw, ct, (' · <b>Finland %s %%</b>' % fi[0]) if fi else ''))
    if not out: return ''
    return '<table class="st small"><thead><tr><th>%s</th><th class="n">%s</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>' % (
        bi('Versio', 'Version'), bi('Asennuksia', 'Installs'), bi('Mallit', 'Models'), bi('Rauta', 'Hardware'), bi('Maat (top)', 'Countries (top)'), ''.join(out))

# Release notes
def notes():
    out = []
    lst = {x['v']: x for x in NA.get('list', [])}
    for v, n in (NA.get('notes') or {}).items():
        if not n['features']: continue
        meta = lst.get(v, {})
        items = ''.join('<li><b>%s</b> – <span class="mut">%s</span></li>' % (E(f['title']), E(f['desc'][:260] + ('…' if len(f['desc']) > 260 else ''))) for f in n['features'][:10])
        out.append('<details%s><summary><b>%s</b> <span class="mut">%s %s</span> <span class="tag">%d %s</span></summary><ul class="notes">%s</ul><p class="small"><a href="%s">%s</a></p></details>' % (
            ' open' if not out else '', E(v), E(meta.get('date', '')), ('· ' + E(meta['region'])) if meta.get('region') else '', len(n['features']),
            bi('kohtaa', 'items'), items, E(n['url']), bi('Koko julkaisutiedote (NotATeslaApp, englanniksi)', 'Full release notes (NotATeslaApp)')))
    return ''.join(out)

def nata_list():
    rows_ = sorted(NA.get('list', []), key=lambda x: vt(x['v']), reverse=True)[:14]
    if not rows_: return ''
    return '<table class="st small"><thead><tr><th>%s</th><th>FSD</th><th>%s</th><th>%s</th><th>%s</th></tr></thead><tbody>%s</tbody></table>' % (
        bi('Versio', 'Version'), bi('Alue', 'Region'), bi('Tyyppi', 'Type'), bi('Päivä', 'Date'),
        ''.join('<tr%s><td><b>%s</b></td><td class="mut">%s</td><td>%s</td><td>%s</td><td>%s</td></tr>' % (
            ' class="hl"' if x['region'] == 'Europe' else '', E(x['v']), E(x['fsd']), E(x['region'] or '–'), E(x['type']), E(x['date'])) for x in rows_))

def recent_table(lst):
    if not lst: return '<p class="mut">%s</p>' % bi('Ei suomalaisia päivityksiä TeslaFin 100 viimeisimmän joukossa hakuhetkellä.', 'No Finnish updates among the 100 most recent at fetch time.')
    return '<table class="st small"><thead><tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>AI/HW</th></tr></thead><tbody>%s</tbody></table>' % (
        bi('Aika (Suomen aikaa)', 'Time (Finnish)'), bi('Maa', 'Country'), bi('Uusi versio', 'New version'), bi('Edellinen', 'Previous'), bi('Malli', 'Model'),
        ''.join('<tr><td>%s</td><td>%s</td><td><b>%s</b></td><td class="mut">%s</td><td>%s</td><td>%s</td></tr>' % (
            conv(x['time_us_central']), E(x['country']), E(x['new']), E(x['prev']), E(x['model']), E(x['ai'])) for x in lst))

# interactive data
JS_ROWS = [{'v': r['v'], 'f': r['f'], 'p': r['p'], 'w': r['w'], 'eu': r['eu'], 'fi': r['fi'], 'm': r['m']} for r in rows]

CSS = r'''
:root{--bg:#0f172a;--card:#1e293b;--txt:#e2e8f0;--mut:#94a3b8;--acc:#38bdf8;--ok:#22c55e;--bad:#ef4444}
*{box-sizing:border-box}
body{margin:0;font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:linear-gradient(160deg,#0f172a,#1e1b4b);color:var(--txt);min-height:100vh;display:flex;align-items:flex-start;justify-content:center;padding:24px 14px;line-height:1.5}
.card{background:var(--card);border-radius:16px;padding:28px;max-width:1100px;width:100%;box-shadow:0 20px 50px rgba(0,0,0,.4)}
h1{margin:0 0 8px;font-size:1.9rem}h2{font-size:1.25rem;margin:30px 0 10px;padding-top:14px;border-top:1px solid #334155}h3{font-size:1.02rem;margin:18px 0 6px}
a{color:var(--acc)}
button{font:inherit;cursor:pointer;border:none;border-radius:10px}
.primary{background:var(--acc);color:#0f172a;font-weight:600;padding:10px 20px}
.tag{display:inline-block;background:#334155;color:var(--acc);padding:2px 10px;border-radius:999px;font-size:.8rem}
.chip{background:#0f172a;border:2px solid #334155;color:var(--txt);padding:6px 13px;border-radius:999px;font-size:.88rem;margin:3px 2px}.chip.on{border-color:var(--acc);background:rgba(56,189,248,.15)}
.langs{display:flex;gap:8px;justify-content:flex-end}.link{background:none;color:var(--acc);border:1px solid #334155;padding:8px 14px}.link.on{background:rgba(56,189,248,.15);border-color:var(--acc)}
.fig{background:#0b1222;border:1px solid #334155;border-radius:12px;padding:12px;margin:10px 0;overflow-x:auto}
.mut{color:var(--mut)}.small{font-size:.86rem}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:18px 0}
.kpi{background:#0f172a;border:1px solid #334155;border-radius:12px;padding:14px}.kl{color:var(--mut);font-size:.85rem}.kv{font-size:1.55rem;font-weight:700;color:var(--acc);margin:4px 0}.ks{font-size:.85rem;color:var(--mut)}
.tw{overflow-x:auto}
table.st{width:100%;border-collapse:collapse;font-size:.92rem;margin:8px 0}
.st th{text-align:left;color:var(--mut);font-weight:600;padding:8px 6px;border-bottom:2px solid #334155;white-space:nowrap}
.st td{padding:7px 6px;border-bottom:1px solid #334155}
.st .n{text-align:right;font-variant-numeric:tabular-nums}
.st tr.tot td{font-weight:700;border-top:2px solid #334155}
.st tr.hl td{background:rgba(56,189,248,.07)}
#vt th{cursor:pointer;user-select:none}#vt th:hover{color:var(--acc)}
.mini{height:6px;background:#334155;border-radius:3px;min-width:60px}.mini div{background:var(--acc);height:6px;border-radius:3px}
.ctrl{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:6px 0}.ctrl .lab{color:var(--mut);font-size:.85rem;min-width:84px}
input[type=search]{font:inherit;background:#0f172a;border:2px solid #334155;color:var(--txt);border-radius:10px;padding:7px 12px}
details{background:#0f172a;border:1px solid #334155;border-radius:12px;padding:10px 14px;margin:8px 0}summary{cursor:pointer}
ul.notes li{margin:5px 0}
.hwg{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.hwc{background:#0f172a;border:1px solid #334155;border-radius:12px;padding:12px}.hwc h4{margin:0 0 4px;color:var(--acc)}
.warn{border-left:4px solid #f59e0b;background:rgba(245,158,11,.08);padding:10px 14px;border-radius:8px}
body.lang-fi .en{display:none}body.lang-en .fi{display:none}
@media(max-width:480px){.card{padding:18px}h1{font-size:1.5rem}.kv{font-size:1.3rem}}
'''

JS = r'''
const ROWS=__ROWS__;const HW=["NoAP","AP1","AP2","AP2.5","AP3","AP4"];
const HWL={"NoAP":"Ei AP / No AP","AP1":"HW1 / AP1","AP2":"HW2","AP2.5":"HW2.5","AP3":"HW3","AP4":"HW4 / AI4"};
let st={scope:"fi",model:"",hw:new Set(),q:"",sort:"n",dir:-1};
function setLang(l){document.body.className="lang-"+l;document.documentElement.lang=l;
 document.querySelectorAll(".langs .link").forEach(b=>b.classList.toggle("on",b.dataset.l==l));try{localStorage.setItem("tvl",l)}catch(e){}}
function vt(v){return v.split(".").map(Number)}
function cmpV(a,b){a=vt(a);b=vt(b);for(let i=0;i<Math.max(a.length,b.length);i++){const d=(a[i]||0)-(b[i]||0);if(d)return d}return 0}
function vec(r){if(st.model){return r.m[st.model]||[0,0,0,0,0,0]}return r[st.scope]}
function cnt(r){const v=vec(r);let s=0;HW.forEach((h,i)=>{if(!st.hw.size||st.hw.has(h))s+=v[i]});return s}
function fmt(n){return n.toLocaleString("fi-FI")}
function render(){
 if(st.model&&st.scope!="w"){st.scope="w";syncChips()}
 let rs=ROWS.map(r=>({r,n:cnt(r)})).filter(x=>x.n>0&&(!st.q||x.r.v.includes(st.q)||(x.r.f||"").toLowerCase().includes(st.q.toLowerCase())));
 const tot=rs.reduce((a,x)=>a+x.n,0);
 rs.sort((a,b)=>{let d=0;if(st.sort=="v")d=cmpV(a.r.v,b.r.v);else if(st.sort=="f")d=(a.r.f||"").localeCompare(b.r.f||"");else if(st.sort=="p")d=a.r.p-b.r.p;else d=a.n-b.n;return d*st.dir||cmpV(b.r.v,a.r.v)});
 const mx=Math.max(1,...rs.map(x=>x.n));
 document.querySelector("#vt tbody").innerHTML=rs.map(x=>`<tr><td><b>${x.r.v}</b></td><td class="mut">${x.r.f||""}</td><td class="n">${fmt(x.n)}</td><td class="n">${(100*x.n/tot).toFixed(1).replace(".",",")}</td><td><div class="mini"><div style="width:${(100*x.n/mx).toFixed(1)}%"></div></div></td><td class="n mut">${st.scope=="w"&&!st.model&&!st.hw.size?fmt(x.r.p):"–"}</td></tr>`).join("")||`<tr><td colspan=6 class="mut">–</td></tr>`;
 document.getElementById("vtsum").textContent=fmt(tot)+" / "+rs.length;
 const top=[...rs].sort((a,b)=>b.n-a.n).slice(0,12);const W=640,lw=110,bh=20,g=6,H=top.length*(bh+g)+4;
 let s=`<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px" xmlns="http://www.w3.org/2000/svg">`;
 const m2=Math.max(1,...top.map(x=>x.n));
 top.forEach((x,i)=>{const y=i*(bh+g)+2,w=(W-lw-100)*x.n/m2;s+=`<text x="${lw-8}" y="${y+15}" fill="#e2e8f0" font-size="13" text-anchor="end">${x.r.v}</text><rect x="${lw}" y="${y}" width="${Math.max(w,2)}" height="${bh}" rx="4" fill="#38bdf8"/><text x="${lw+w+6}" y="${y+15}" fill="#94a3b8" font-size="12">${fmt(x.n)} (${(100*x.n/tot).toFixed(1).replace(".",",")} %)</text>`});
 document.getElementById("vchart").innerHTML=s+"</svg>";
 document.querySelectorAll("#vt th").forEach(th=>{th.dataset.arrow=th.dataset.k==st.sort?(st.dir<0?" ▼":" ▲"):"";th.querySelector(".ar").textContent=th.dataset.arrow});
}
function syncChips(){document.querySelectorAll("[data-scope]").forEach(b=>b.classList.toggle("on",b.dataset.scope==st.scope));
 document.querySelectorAll("[data-model]").forEach(b=>b.classList.toggle("on",b.dataset.model==st.model));
 document.querySelectorAll("[data-hw]").forEach(b=>b.classList.toggle("on",b.dataset.hw==""?!st.hw.size:st.hw.has(b.dataset.hw)))}
document.addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;
 if(b.dataset.scope){st.scope=b.dataset.scope;if(st.scope!="w")st.model=""}
 else if(b.dataset.model!==undefined){st.model=b.dataset.model;if(st.model)st.scope="w"}
 else if(b.dataset.hw!==undefined){if(b.dataset.hw=="")st.hw.clear();else st.hw.has(b.dataset.hw)?st.hw.delete(b.dataset.hw):st.hw.add(b.dataset.hw)}
 else if(b.dataset.l){setLang(b.dataset.l);return}else return;syncChips();render()});
document.querySelectorAll("#vt th").forEach(th=>th.addEventListener("click",()=>{const k=th.dataset.k;if(st.sort==k)st.dir*=-1;else{st.sort=k;st.dir=k=="f"?1:-1}render()}));
document.getElementById("q").addEventListener("input",e=>{st.q=e.target.value.trim();render()});
let l="fi";try{l=localStorage.getItem("tvl")||"fi"}catch(e){}setLang(l);syncChips();render();
'''

srcs = [('TeslaFi – Firmware Tracker', TF['url'], bi('versiojakauma, rautakohtaiset taulukot, 100 viimeisintä päivitystä; versiokohtaiset sivut (maa × rauta, malli × rauta)', 'distribution, per-hardware tables, latest 100 updates; per-version pages (country × hw, model × hw)')),
        ('Teslascope – Software', TS.get('url', 'https://teslascope.com/software'), bi('aktiiviset jakelut ja alueet, FSD-versiot, versiokohtaiset maaosuudet', 'active rollouts and regions, FSD versions, per-version country shares')),
        ('Not a Tesla App – Software Updates', NA.get('url', 'https://www.notateslaapp.com/software-updates/'), bi('versiolista alueineen ja julkaisutiedotteet', 'version list with regions, release notes'))]
n_ok = sum(1 for _, s in D.get('fetch_log', []) if s in (200, 'cache')); n_all = len(D.get('fetch_log', []))

hw_cards = [
 ('Ei AP / pre-AP', 'Model S 2012 – syys 2014', 'Model S 2012 – Sep 2014', 'Ei Autopilot-rautaa. Saa yhä ohjelmistopäivityksiä (oma haara).', 'No Autopilot hardware; still receives updates.'),
 ('HW1 / AP1 (Mobileye)', 'Model S syys 2014 – loka 2016, Model X 2015–2016', 'Model S Sep 2014 – Oct 2016, Model X 2015–16', 'Mobileye EyeQ3, 1 etukamera + tutka. Ei FSD-tukea.', 'Mobileye EyeQ3, one camera + radar. No FSD.'),
 ('HW2', 'Model S/X loka 2016 – n. elo 2017', 'Model S/X Oct 2016 – ~Aug 2017', 'Teslan oma 8 kameran Autopilot, Nvidia Drive PX2. FSD vaatii päivityksen HW3:een.', 'Tesla Vision 8 cameras, Nvidia Drive PX2; FSD needs HW3 retrofit.'),
 ('HW2.5', 'Model S/X n. 2017–2019, Model 3 2017 – kevät 2019', 'Model S/X ~2017–19, Model 3 2017 – spring 2019', 'Paranneltu HW2 (redundanssi). FSD vaatii päivityksen HW3:een.', 'Improved HW2; FSD needs HW3 retrofit.'),
 ('HW3 (FSD Computer 1)', 'S/X/3 kevät 2019 →, Model Y 2020 → (n. 2023 asti)', 'S/X/3 spring 2019 →, Model Y 2020 → (until ~2023)', 'Teslan oma siru. Saa "FSD V14 Lite" -haaraa Pohjois-Amerikassa; Euroopan hyväksyntä koskee vain uusinta rautaa.', 'Tesla’s own chip. Gets "FSD V14 Lite" in N. America; European approval covers latest hardware only.'),
 ('HW4 / AI4', 'Model S/X 2023 →, Model Y 2023 →, Cybertruck, Model 3 Highland 2024 →', 'S/X 2023 →, Y 2023 →, Cybertruck, Model 3 Highland 2024 →', 'Nykyinen rauta kaikissa uusissa Tesloissa; tarkemmat kamerat. FSD (Supervised) / TAD -hyväksynnät koskevat tätä.', 'Current hardware in all new cars. FSD (Supervised)/TAD approvals target this.'),
 ('AI5 (tulossa)', 'Ei vielä autoissa', 'Not yet in cars', 'Koetuotanto alkanut syksyllä 2026 (Samsung, TSMC); autoihin arviolta 2027. Ei näy versiotilastoissa.', 'Trial production started autumn 2026 (Samsung, TSMC); cars expected ~2027. Not in version stats.'),
]
hw_html = ''.join('<div class="hwc"><h4>%s</h4><div class="small"><b>%s</b></div><div class="small mut">%s</div></div>' % (
    t, bi(fy, ey), bi(fd, ed)) for t, fy, ey, fd, ed in hw_cards)

eu_new, eu_common = best(lambda r: sum(r['eu']), 3)
w_new, w_common = best(lambda r: sum(r['w']), 5)

page = f'''<!DOCTYPE html>
<html lang="fi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tesla-ohjelmistoversiot Suomessa – tilastot</title>
<meta name="description" content="Mitä Teslan ohjelmistoversioita Suomessa jaetaan: jakauma mallin ja Autopilot/AI-raudan mukaan. Lähteet TeslaFi, Teslascope, NotATeslaApp.">
<style>{CSS}</style></head>
<body class="lang-fi"><div class="card">
<div class="langs"><button class="link on" data-l="fi">FI</button><button class="link" data-l="en">EN</button></div>
<span class="tag">{bi('Tilastot', 'Statistics')}</span>
<h1>{bi('Tesla-ohjelmistoversiot – mitä Suomessa jaetaan?', 'Tesla software versions – what is rolling out in Finland?')}</h1>
<p class="mut">{bi('Tiedot haettu: ' + FETCHED_FI, 'Data fetched: ' + FETCHED_EN)}. {bi('Kaikki luvut julkisista lähteistä (linkit alla); TeslaFi on vapaaehtoisten otos, ei koko autokanta.', 'All figures from public sources (links below); TeslaFi is a volunteer sample, not the whole fleet.')}</p>
<div class="kpis">{kpi_html}</div>

<h2>🇫🇮 {bi('Suomi: versiot ja rauta', 'Finland: versions and hardware')}</h2>
<p class="small mut">{bi(f'TeslaFi-otoksessa {tot_fi} suomalaista autoa. Versiokohtaisilta sivuilta poimittu maa × rauta -jako. TeslaFi ei julkaise Suomen lukuja mallikohtaisesti, joten Suomen mallijakoa ei ole saatavilla.', f'{tot_fi} Finnish cars in the TeslaFi sample (country × hardware from per-version pages). TeslaFi does not publish a Finland × model split.')}</p>
<div class="fig">{fi_chart}</div>
<div class="tw">{fi_table()}</div>
<h3>{bi('Viimeisimmät päivitykset Suomessa (TeslaFi, 100 tuoreinta koko maailmassa)', 'Latest updates in Finland (TeslaFi, among 100 most recent worldwide)')}</h3>
{recent_table(recent_fi)}
<p class="small mut">{bi(f'Samassa 100 päivityksen listassa Euroopan autoja: {len(recent_eu)}. Ajat muunnettu TeslaFin oletetusta Yhdysvaltain keskiajasta (America/Chicago) Suomen aikaan.', f'European cars in the same list: {len(recent_eu)}. Times converted from TeslaFi’s assumed US Central time.')}</p>

<h2>🌍 {bi('Suomi vs. Eurooppa vs. maailma', 'Finland vs Europe vs world')}</h2>
<table class="st"><thead><tr><th></th><th class="n">{bi('Autoja', 'Cars')}</th><th>{bi('Yleisin versio', 'Most common')}</th><th>{bi('Uusin versio', 'Newest')}</th></tr></thead><tbody>
<tr><td><b>{bi('Suomi', 'Finland')}</b></td><td class="n">{fmt(tot_fi)}</td><td>{fi_common[0]['v'] if fi_common else '–'} ({pct(fi_common[1], tot_fi) if fi_common else ''} %)</td><td>{fi_new[0]['v'] if fi_new else '–'} ({bi('≥1 auto', '≥1 car')})</td></tr>
<tr><td>{bi('Eurooppa', 'Europe')}</td><td class="n">{fmt(tot_eu)}</td><td>{eu_common[0]['v'] if eu_common else '–'} ({pct(eu_common[1], tot_eu) if eu_common else ''} %)</td><td>{eu_new[0]['v'] if eu_new else '–'} ({bi('≥3 autoa', '≥3 cars')})</td></tr>
<tr><td>{bi('Maailma', 'World')}</td><td class="n">{fmt(tot_w)}</td><td>{w_common[0]['v'] if w_common else '–'} ({pct(w_common[1], tot_w) if w_common else ''} %)</td><td>{w_new[0]['v'] if w_new else '–'} ({bi('≥5 autoa', '≥5 cars')})</td></tr>
</tbody></table>
<p class="small mut">{bi('Eurooppa = TeslaFin maarivien summa Euroopan maille (ml. Turkki, Ukraina, Iso-Britannia, Norja, Sveitsi).', 'Europe = sum of TeslaFi country rows for European countries (incl. Turkey, Ukraine, UK, Norway, Switzerland).')}</p>

<h2>📡 {bi('Aktiiviset jakelut nyt (Teslascope)', 'Active rollouts now (Teslascope)')}</h2>
<p class="small mut">{bi('Korostetut rivit jaetaan myös Eurooppaan. Osuus = Teslascope-kannan osuus.', 'Highlighted rows also roll out to Europe. Share = share of Teslascope fleet.')}</p>
<div class="tw">{ts_table()}</div>
<div class="tw">{ts_pages()}</div>
<h3>{bi('FSD-haarat raudan mukaan (Teslascope)', 'FSD branches by hardware (Teslascope)')}</h3>{ts_fsd()}
<h3>{bi('Uusimmat versiot ja alueet (NotATeslaApp)', 'Latest versions and regions (NotATeslaApp)')}</h3>
<div class="tw">{nata_list()}</div>

<h2>🔎 {bi('Versiojakauma – suodata ja lajittele', 'Version distribution – filter and sort')}</h2>
<div class="ctrl"><span class="lab">{bi('Alue', 'Area')}</span><button class="chip" data-scope="fi">{bi('Suomi', 'Finland')}</button><button class="chip" data-scope="eu">{bi('Eurooppa', 'Europe')}</button><button class="chip" data-scope="w">{bi('Maailma', 'World')}</button></div>
<div class="ctrl"><span class="lab">{bi('Malli', 'Model')}</span><button class="chip" data-model="">{bi('Kaikki', 'All')}</button>{''.join('<button class="chip" data-model="%s">%s</button>' % (m, ML[m]) for m in MODELS)}</div>
<div class="ctrl"><span class="lab">{bi('Rauta', 'Hardware')}</span><button class="chip" data-hw="">{bi('Kaikki', 'All')}</button>{''.join('<button class="chip" data-hw="%s">%s</button>' % (k, HWL[k]) for k in HW)}</div>
<div class="ctrl"><span class="lab">{bi('Haku', 'Search')}</span><input type="search" id="q" placeholder="2026.38 / FSD"> <span class="small mut">{bi('Autoja / versioita:', 'Cars / versions:')} <b id="vtsum"></b></span></div>
<p class="small mut">{bi('Mallisuodatin käyttää maailman lukuja (TeslaFi ei jaa maita mallin mukaan). Rautasuodattimessa voi valita useita.', 'Model filter uses world figures (TeslaFi has no country × model split). Multiple hardware chips can be selected.')}</p>
<div class="fig" id="vchart"></div>
<div class="tw"><table class="st" id="vt"><thead><tr><th data-k="v">{bi('Versio', 'Version')}<span class="ar"></span></th><th data-k="f">FSD<span class="ar"></span></th><th class="n" data-k="n">{bi('Autoja', 'Cars')}<span class="ar"></span></th><th class="n" data-k="n">%<span class="ar"></span></th><th data-k="n"></th><th class="n" data-k="p">{bi('Odottaa', 'Pending')}<span class="ar"></span></th></tr></thead><tbody></tbody></table></div>

<h2>🚗 {bi('Mallit ja rauta', 'Models and hardware')}</h2>
<h3>{bi('Uusin ja yleisin versio mallin ja raudan mukaan', 'Newest and most common version by model and hardware')}</h3>
<div class="tw">{per_table()}</div>
<h3>{bi('Raudan osuudet malleittain (TeslaFi, maailma) ja Suomessa', 'Hardware share by model (TeslaFi, world) and Finland')}</h3>
<div class="fig">{model_hw_svg}</div>
<div class="tw">{matrix()}</div>

<h2>📝 {bi('Julkaisutiedotteiden kohokohdat', 'Release notes highlights')}</h2>
<p class="small mut">{bi('Otsikot ja kuvaukset alkuperäisinä (englanniksi) NotATeslaAppista.', 'Titles and descriptions as published by NotATeslaApp.')}</p>
{notes()}

<h2>🧠 {bi('Autopilot- ja AI-rauta: mikä missäkin?', 'Autopilot and AI hardware explained')}</h2>
<div class="hwg">{hw_html}</div>
<p class="small mut">{bi('Vuosimallit ovat suuntaa antavia; vaihtuminen tapahtui tuotannossa kesken mallivuoden ja vaihtelee markkinoittain. HW2/2.5-autoihin on voitu vaihtaa HW3. TeslaFi-sarakkeet: No AP, AP1, AP2, AP2.5, AP3, AP4.', 'Model years are approximate; changeovers happened mid-year. HW2/2.5 cars may have HW3 retrofits. TeslaFi columns: No AP, AP1, AP2, AP2.5, AP3, AP4.')}</p>

<h2>🛣️ {bi('FSD (Supervised) Euroopassa ja Suomessa', 'FSD (Supervised) in Europe and Finland')}</h2>
<div class="warn">{bi('<b>Suomessa FSD (Supervised) ei ole hyväksytty</b> (tilanne 22.10.2026). Traficom arvioi hyväksyntää; arvio koskee vain uusinta rautaa (HW4/AI4), noin 6 500 autoa Suomessa.', '<b>FSD (Supervised) is not approved in Finland</b> (as of 22 Oct 2026). Traficom is assessing it; the assessment covers latest hardware (HW4/AI4) only, about 6,500 cars in Finland.')}</div>
<ul>
<li>{bi('Alankomaiden RDW myönsi väliaikaisen kansallisen tyyppihyväksynnän 10.4.2026.', 'Dutch RDW granted provisional national type approval on 10 Apr 2026.')} <a href="https://www.rdw.nl/en/news/2026/rdw-explanation-of-european-type-approval-tesla-with-provisional-validity-in-the-netherlands">RDW</a></li>
<li>{bi('Kansallinen hyväksyntä 9/27 EU-maassa: NL, LT, EE, DK, BE, SI, CZ, HR, SK. Arvioitavana mm. Suomi (23.6. alkaen), Ruotsi, Ranska, Saksa.', 'National approval in 9/27 EU countries: NL, LT, EE, DK, BE, SI, CZ, HR, SK. Under review incl. Finland (since 23 Jun), Sweden, France, Germany.')} <a href="https://tad-tracker.eu/">tad-tracker.eu</a></li>
<li>{bi('Tesla nimesi FSD (Supervised) -toiminnon Euroopassa uudelleen nimellä "Tesla Assisted Driving" (TAD) 9.10.2026.', 'Tesla renamed FSD (Supervised) in Europe to "Tesla Assisted Driving" (TAD) on 9 Oct 2026.')} <a href="https://tad-tracker.eu/">tad-tracker.eu</a></li>
<li>{bi('Traficom 23.6.2026: arviointi käynnissä, vanhemmille autoille ei vastaavaa menettelyä.', 'Traficom 23 Jun 2026: assessment ongoing; no equivalent procedure for older cars.')} <a href="https://www.traficom.fi/fi/uutiset/traficom-arvioi-teslan-fsd-supervised-jarjestelman-hyvaksyntaa-suomessa">Traficom</a></li>
<li>{bi('EU-laajuinen äänestys (TCMV) siirtyi lokakuulta aikaisintaan joulukuulle 2026. Musk arvioi Q3-puhelussa EU-hyväksynnän ehkä Q1 2027.', 'EU-wide TCMV vote postponed from October to December 2026 at the earliest. Musk said on the Q3 call EU approval may come by Q1 2027.')} <a href="https://www.kauppalehti.fi/">Kauppalehti 28.9.2026</a> · <a href="https://www.fool.com/earnings/call-transcripts/">Q3 2026 call transcript</a></li>
<li>{bi('Euroopan FSD/TAD-versio näkyy erillisenä haarana (esim. NotATeslaApp merkitsee Europe-versiot yllä).', 'The European FSD/TAD build appears as a separate branch (e.g. NotATeslaApp marks Europe builds above).')}</li>
</ul>

<h2>📚 {bi('Lähteet ja rajoitukset', 'Sources and caveats')}</h2>
<ul>{''.join('<li><a href="%s">%s</a> – %s</li>' % (E(u), E(n), d) for n, u, d in srcs)}</ul>
<ul class="small mut">
<li>{bi(f'TeslaFi: {fmt(TF.get("contributing") or 0)} osallistuvaa autoa – itsevalikoitunut otos (enemmän USA:ta ja innokkaita omistajia), ei koko Tesla-kanta. Suomen otos on pieni ({tot_fi} autoa), joten prosentit heiluvat.', f'TeslaFi: {TF.get("contributing")} contributing cars – self-selected sample, not the whole fleet. Finland sample is small ({tot_fi}).')}</li>
<li>{bi('Teslascope- ja TeslaFi-osuudet eivät ole vertailukelpoisia keskenään (eri otokset).', 'Teslascope and TeslaFi shares are different samples and not directly comparable.')}</li>
<li>{bi('"Uusin versio" = suurin versionumero, jolla vähintään mainittu määrä autoja; yksittäiset testiversiot suodatettu pois.', '"Newest" = highest version number with at least the stated number of cars.')}</li>
<li>{bi(f'Haettu {n_ok}/{n_all} sivua onnistuneesti.', f'Fetched {n_ok}/{n_all} pages successfully.')}{(' ' + bi('Versiot ilman yksityiskohtasivua (ei mukana maa/malli-jaossa): ', 'Versions without detail page: ') + E(', '.join(missing_detail))) if missing_detail else ''}</li>
<li>{bi('Sivu generoidaan Python-skriptillä (build/hae_data.py + build/rakenna_sivu.py), ei ulkoisia riippuvuuksia selaimessa.', 'Generated by Python scripts; no external runtime dependencies.')}</li>
</ul>
<p class="small mut">{bi('Ei Teslan virallinen sivu. Tiedot haettu ', 'Not an official Tesla page. Data fetched ')}{bi(FETCHED_FI, FETCHED_EN)}.</p>
</div>
<script>{JS.replace('__ROWS__', json.dumps(JS_ROWS, separators=(',', ':')))}</script>
</body></html>'''
open(OUT, 'w', encoding='utf-8').write(page)
print('kirjoitettu', os.path.abspath(OUT), len(page), 'tavua; FI autoja', tot_fi, 'rivejä', len(rows))
