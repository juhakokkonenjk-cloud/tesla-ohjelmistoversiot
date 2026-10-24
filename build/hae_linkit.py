#!/usr/bin/env python3
"""Tarkistaa jokaiselle sivulla näkyvälle versiolle julkaisutiedotesivun ja kirjoittaa links.json.
Järjestys: 1) NotATeslaApp /software-updates/version/<v>/release-notes (200 ja sisältää ominaisuuksia)
           2) Teslascope /software/<v> (200)   3) TeslaFi firmware.php?detail=<v> (200)
Käyttö: python3 hae_linkit.py [--cache]   (vaatii data.json:n)"""
import json, os, re, sys, time
import requests
HERE = os.path.dirname(os.path.abspath(__file__))
C = os.path.join(HERE, 'raw', 'links'); os.makedirs(C, exist_ok=True)
DELAY = float(os.environ.get('DELAY', '1.0')); USE_CACHE = '--cache' in sys.argv
S = requests.Session(); S.headers['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) Chrome/130.0 (tesla-ohjelmistoversiot link check)'
D = json.load(open(os.path.join(HERE, 'data.json')))
V = re.compile(r'^20\d\d\.\d+(\.\d+)*$')
vers = set()
tf = D['teslafi']; vers |= {v['v'] for v in tf['versions']}
for lst in tf['by_ai'].values(): vers |= {x['v'] for x in lst}
for x in tf['recent']: vers |= {x['new'], x['prev']}
ts = D.get('teslascope') or {}
vers |= {a['v'] for a in ts.get('active', [])}
for lst in (ts.get('fsd') or {}).values(): vers |= {x['v'] for x in lst}
vers |= {x['v'] for x in (D.get('nata') or {}).get('list', [])}
vers = sorted(v for v in vers if V.match(v))
cache_f = os.path.join(C, 'status.json')
cache = json.load(open(cache_f)) if (USE_CACHE and os.path.exists(cache_f)) else {}

def check(url, need=None):
    if url in cache: return cache[url]
    try:
        r = S.get(url, timeout=30, allow_redirects=True); time.sleep(DELAY)
        if r.status_code == 429:
            time.sleep(20); r = S.get(url, timeout=30, allow_redirects=True); time.sleep(DELAY)
        ok = r.status_code == 200 and (need is None or need in r.text)
        res = {'status': r.status_code, 'ok': ok, 'n': r.text.count(need) if need else None}
    except Exception as e:
        res = {'status': 'ERR', 'ok': False}
    cache[url] = res; json.dump(cache, open(cache_f, 'w'), indent=0)
    return res

tf_set = {v['v'] for v in tf['versions']}
links = {}
for i, v in enumerate(vers):
    cand = [('NotATeslaApp', 'https://www.notateslaapp.com/software-updates/version/%s/release-notes' % v, 'mod-update-feature-details'),
            ('Teslascope', 'https://teslascope.com/software/%s' % v, None),
            ('TeslaFi', 'https://www.teslafi.com/firmware.php?detail=%s' % v, None)]
    for src, url, need in cand:
        if src == 'TeslaFi' and v in tf_set and v in D.get('teslafi_detail', {}):
            links[v] = {'src': src, 'url': url}; break  # jo haettu onnistuneesti hae_data.py:ssä
        r = check(url, need)
        if r['ok']:
            links[v] = {'src': src, 'url': url, 'n': r.get('n')}; break
    print(i + 1, len(vers), v, links.get(v, {}).get('src', 'EI LINKKIÄ'), flush=True)
json.dump({'checked': len(vers), 'links': links, 'missing': [v for v in vers if v not in links]},
          open(os.path.join(HERE, 'links.json'), 'w'), indent=1)
from collections import Counter
print(Counter(x['src'] for x in links.values()), 'puuttuu', [v for v in vers if v not in links])
