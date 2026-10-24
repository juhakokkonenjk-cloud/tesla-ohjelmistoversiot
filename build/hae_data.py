#!/usr/bin/env python3
"""Hakee Tesla-ohjelmistoversiotiedot julkisista lähteistä ja tallentaa data.json:iin.

Lähteet: TeslaFi (firmware.php + versiokohtaiset detail-sivut), Teslascope (/software +
aktiivisten versioiden sivut), NotATeslaApp (päivityslista + julkaisutiedotteet).
Ei kirjautumista, ei suojausten kiertämistä. Pyynnöt hidastettu (DELAY s).

Käyttö:  python3 hae_data.py            # hae kaikki verkosta
         python3 hae_data.py --cache    # käytä raw/-kansion välimuistia jos olemassa
"""
import json, re, sys, time, os, datetime
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
os.makedirs(os.path.join(RAW, 'teslafi_detail'), exist_ok=True)
UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/130.0 Safari/537.36 (tesla-ohjelmistoversiot stats page; polite fetch)')
DELAY = float(os.environ.get("DELAY", "1.0"))
USE_CACHE = '--cache' in sys.argv
S = requests.Session(); S.headers['User-Agent'] = UA
LOG = []  # (source, url, status)

def get(url, cache_name=None):
    path = os.path.join(RAW, cache_name) if cache_name else None
    if USE_CACHE and path and os.path.exists(path):
        LOG.append((url, 'cache')); return open(path, encoding='utf-8', errors='ignore').read()
    try:
        r = S.get(url, timeout=40, allow_redirects=True)
        LOG.append((url, r.status_code))
        time.sleep(DELAY)
        if r.status_code != 200:
            return None
        if path:
            open(path, 'w', encoding='utf-8').write(r.text)
        return r.text
    except Exception as e:
        LOG.append((url, 'ERR %s' % e)); return None

def num(s):
    s = (s or '').replace(',', '').replace('%', '').strip()
    try: return float(s) if '.' in s else int(s)
    except ValueError: return None

def split_ver(cell):
    parts = [p.strip() for p in cell.split('|')]
    return parts[0], (parts[1] if len(parts) > 1 else '')

def rows(table):
    return [[c.get_text(' | ', strip=True) for c in tr.find_all(['td', 'th'])] for tr in table.find_all('tr')]

# ---------------------------------------------------------------- TeslaFi main
def teslafi_main():
    url = 'https://www.teslafi.com/firmware.php'
    h = get(url, 'teslafi_firmware.html')
    if not h: return None
    b = BeautifulSoup(h, 'lxml')
    out = {'url': url}
    txt = b.get_text(' ', strip=True)
    m = re.search(r'Rolling out now\s+([\d.]+)\s+([\d,]+) cars \(([\d.]+)%\)\s+([\d,]+) waiting', txt)
    if m:
        out['rolling'] = {'version': m.group(1), 'cars': num(m.group(2)), 'pct': num(m.group(3)), 'pending': num(m.group(4))}
    m = re.search(r'([\d,]+) contributing vehicles', txt)
    out['contributing'] = num(m.group(1)) if m else None
    vers = []
    for r in rows(b.find('table', id='contributing_vehicles'))[1:]:
        if len(r) < 4: continue
        v, badge = split_ver(r[0])
        vers.append({'v': v, 'fsd': badge, 'count': num(r[1]), 'pct': num(r[2]), 'pending': num(r[3]) or 0})
    out['versions'] = vers
    ai = {}
    for tid, key in [('auto_pilot_4', 'AP4'), ('auto_pilot_3', 'AP3'), ('auto_pilot_2_5', 'AP2.5'),
                     ('auto_pilot_2', 'AP2'), ('auto_pilot_1', 'AP1'), ('pre_auto_pilot', 'NoAP')]:
        t = b.find('table', id=tid)
        if not t: continue
        lst = []
        for r in rows(t)[1:]:
            if len(r) < 3: continue
            v, badge = split_ver(r[0]); lst.append({'v': v, 'fsd': badge, 'count': num(r[1]), 'pct': num(r[2])})
        ai[key] = lst
    out['by_ai'] = ai
    rec = []
    for r in rows(b.find('table', id='latest_fleet_updates2'))[1:]:
        if len(r) < 7: continue
        nv, nb = split_ver(r[1]); pv, pb = split_ver(r[2])
        rec.append({'time_us_central': r[0], 'new': nv, 'new_fsd': nb, 'prev': pv, 'model': r[3],
                    'region': r[4], 'country': r[5], 'ai': r[6]})
    out['recent'] = rec
    m = re.search(r'renderLatestUpdatesChart\((\{.*?\})\);', h, re.S)
    if m:
        try: out['daily'] = json.loads(m.group(1))
        except Exception: pass
    return out

HWCOLS = ['NoAP', 'AP1', 'AP2', 'AP2.5', 'AP3', 'AP4']

def teslafi_detail(v):
    url = 'https://www.teslafi.com/firmware.php?detail=' + quote(v)
    h = get(url, 'teslafi_detail/%s.html' % v)
    if not h: return None
    b = BeautifulSoup(h, 'lxml')
    d = {'url': url, 'countries': {}, 'models': {}, 'pending_by_model': {}}
    t = b.find('table', id='cur_installed1')
    if t:
        section = None
        for r in rows(t)[1:]:
            if len(r) < 9: continue
            vals = [num(x) or 0 for x in r[3:9]]
            if r[0].startswith('+'):
                section = r[0][1:].strip(' |')
                key = {'All': 'All', 'Model S': 'S', 'Model X': 'X', 'Model 3': '3', 'Model Y': 'Y', 'Cybertruck': 'CT'}.get(section, section)
                d['models'][key] = vals
            elif section == 'All' and r[1] and r[1] != '-':
                d['countries'][r[1]] = vals
    t = b.find('table', id='total_pending')
    if t:
        tds = [x.get_text(strip=True) for x in t.find_all('td')]
        for i in range(0, len(tds) - 6, 7):
            d['pending_by_model'][tds[i]] = num(tds[i + 1])
    t = b.find('table', id='pre_installed')
    if t:
        d['prev'] = [{'v': r[0], 'count': num(r[1]), 'pct': num(r[2])} for r in rows(t)[1:] if len(r) >= 3]
    m = re.search(r'([\dhms ]+) average install', b.get_text(' ', strip=True))
    d['avg_install'] = m.group(1).strip() if m else None
    return d

# ---------------------------------------------------------------- Teslascope
def teslascope():
    url = 'https://teslascope.com/software'
    h = get(url, 'teslascope_software.html')
    if not h: return None
    b = BeautifulSoup(h, 'lxml')
    out = {'url': url, 'active': [], 'fsd': {}}
    tables = b.find_all('table')
    if tables:
        for r in rows(tables[0])[1:]:
            if len(r) < 5: continue
            parts = [p.strip() for p in r[0].split('|')]
            rel = [p.strip() for p in r[1].split('|')]; wave = [p.strip() for p in r[2].split('|')]
            ctry = r[3].replace('| Details', '').strip(' |')
            out['active'].append({'v': parts[0], 'fsd': ' '.join(parts[1:]), 'released': rel[-1], 'released_rel': rel[0],
                                  'wave': wave[-1], 'wave_rel': wave[0], 'regions': ctry, 'dist': r[4]})
    for idx, key in [(1, 'AI4'), (2, 'HW3')]:
        if len(tables) > idx:
            lst = []; cur = None
            for r in rows(tables[idx])[1:]:
                if len(r) == 4: cur = r[0]; r = r[1:]
                if len(r) == 3: lst.append({'fsd': cur, 'v': r[0], 'released': r[1], 'dist': r[2]})
            out['fsd'][key] = lst
    # version pages for active versions
    out['pages'] = {}
    for a in out['active']:
        vu = 'https://teslascope.com/software/' + a['v']
        vh = get(vu, 'teslascope_%s.html' % a['v'])
        if not vh: continue
        t = BeautifulSoup(vh, 'lxml').get_text(' ', strip=True)
        p = {'url': vu}
        m = re.search(r'Installs ([\d,]+)', t); p['installs'] = num(m.group(1)) if m else None
        m = re.search(r'Models \(?\w*\)?\s*(Model S \(\d+\).*?)FSD Hardware', t)
        p['models'] = re.findall(r'(Model [S3XY]) \((\d+)\) ([\d.]+)%', m.group(1)) if m else []
        m = re.search(r'FSD Hardware (.*?) Countries', t)
        p['hw'] = re.findall(r'((?:HW|AI)[\d.]+) \((\d+)\) ([\d.]+)%', m.group(1)) if m else []
        m = re.search(r'Country Percentage Share (.*?) Other Countries', t)
        p['countries'] = re.findall(r'([A-Z][A-Za-z .\-]+?) ([\d.]+)%', m.group(1)) if m else []
        out['pages'][a['v']] = p
    return out

# ---------------------------------------------------------------- NotATeslaApp
def nata(versions_for_notes):
    url = 'https://www.notateslaapp.com/software-updates/'
    h = get(url, 'nata_updates.html')
    out = {'url': url, 'list': [], 'notes': {}}
    if h:
        t = BeautifulSoup(h, 'lxml').get_text(' ', strip=True)
        seen = set()
        for m in re.finditer(r'(20\d\d\.\d+(?:\.\d+)*) (?:FSD ([\w.& ]+?) )?(N\. America|Europe|Oceania|Asia|China|Worldwide)? ?(New|Fixes|N/A) '
                             r'((?:January|February|March|April|May|June|July|August|September|October|November|December) \d+, \d{4})', t):
            v = m.group(1)
            if v in seen: continue
            seen.add(v)
            out['list'].append({'v': v, 'fsd': (m.group(2) or '').strip(), 'region': m.group(3) or '', 'type': m.group(4), 'date': m.group(5)})
    for v in versions_for_notes:
        nu = 'https://www.notateslaapp.com/software-updates/version/%s/release-notes' % v
        nh = get(nu, 'nata_%s.html' % v)
        if not nh: continue
        b = BeautifulSoup(nh, 'lxml'); feats = []
        for c in b.find_all('div', class_='mod-update-feature-details'):
            h2 = c.find('h2')
            if not h2: continue
            ps = [p.get_text(' ', strip=True) for p in c.find_all('p')]
            desc = ' '.join(x for x in ps if x)
            if not desc:
                desc = c.get_text(' ', strip=True).replace(h2.get_text(strip=True), '', 1)
                desc = re.sub(r'^.*?Models:( (New|S|3|X|Y|CT|AMD|Intel))*', '', desc).strip()
            feats.append({'title': h2.get_text(' ', strip=True), 'desc': desc[:420]})
        out['notes'][v] = {'url': nu, 'features': feats}
    return out

def main():
    t0 = datetime.datetime.now(datetime.timezone.utc)
    data = {'fetched_utc': t0.isoformat(timespec='seconds')}
    tf = teslafi_main(); data['teslafi'] = tf
    p = os.path.join(RAW, 'teslafi_firmware.html')
    if USE_CACHE and os.path.exists(p):  # aikaleima = päälähteen todellinen hakuhetki
        data['fetched_utc'] = datetime.datetime.fromtimestamp(os.path.getmtime(p), datetime.timezone.utc).isoformat(timespec='seconds')
    det = {}
    if tf:
        for i, v in enumerate(tf['versions']):
            d = teslafi_detail(v['v'])
            if d: det[v['v']] = d
            print('detail %d/%d %s %s' % (i + 1, len(tf['versions']), v['v'], 'ok' if d else 'FAIL'), flush=True)
    data['teslafi_detail'] = det
    ts = teslascope(); data['teslascope'] = ts
    notes_for = []
    if ts: notes_for += [a['v'] for a in ts['active']]
    if tf and tf.get('rolling'): notes_for.append(tf['rolling']['version'])
    # Europe-specific build (if NotATeslaApp marks one) gets notes too
    na = nata([]); eu = [x['v'] for x in na['list'] if x['region'] == 'Europe'][:2]
    seen = []
    for v in notes_for + eu:
        if v not in seen: seen.append(v)
    na2 = nata(seen); data['nata'] = na2
    data['fetch_log'] = LOG
    json.dump(data, open(os.path.join(HERE, 'data.json'), 'w'), ensure_ascii=False, indent=1)
    print('OK, data.json kirjoitettu; pyyntöjä', len(LOG), 'virheitä', sum(1 for _, s in LOG if s not in (200, 'cache')))

if __name__ == '__main__':
    main()
