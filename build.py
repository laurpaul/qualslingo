#!/usr/bin/env python3
"""Build Quals Lingo.

  python3 build.py

Writes:
  site/                     the website to host (GitHub Pages deploys this folder)
  dist/Quals-Lingo.html     one self-contained file that works offline, no account
  dist/quals-artifact.html  the variant used inside a Claude artifact

Edit sources in src/ (app code in src/app, content JSON in src/content, web shell in src/web) and rebuild.
Saved progress is keyed by question ids, so never rename an existing id; add new ids instead.
"""
import base64, hashlib, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
# Sources live in src/app, src/content, src/web. A web upload can flatten them to app/, content/, web/ at the top; both work.
SRC = os.path.join(ROOT, 'src') if os.path.isdir(os.path.join(ROOT, 'src', 'app')) else ROOT
APP = os.path.join(SRC, 'app'); CON = os.path.join(SRC, 'content'); WEB = os.path.join(SRC, 'web')
SITE = os.path.join(ROOT, 'site'); DIST = os.path.join(ROOT, 'dist')
sys.path.insert(0, APP)
from svgmath import fix_svg

def rd(*p): return open(os.path.join(*p), encoding='utf-8').read()
def js(name): return json.load(open(os.path.join(CON, name), encoding='utf-8'))
AREAS = ['opt', 'fw', 'sm', 'st']

# ---------- content ----------
qs, bs = [], []
for f in ['c_opt', 'c_fw', 'c_smm', 'd_opt', 'd_fw', 'd_sm', 'd_st', 't_slips'] + ['q2_' + a for a in AREAS]:
    d = js(f + '.json'); qs += d['questions']; bs += d.get('boards', [])
for a in AREAS: bs += js(f'b2_{a}.json')['boards']
assert len({q['id'] for q in qs}) == len(qs), 'duplicate question id'
figs = js('figs.json')['figs'] + js('figs2.json')['figs']
for n in (3, 4, 5, 6): figs += [x for a in AREAS for x in js(f'figs{n}_{a}.json')['figs']]
assert len({x['title'] for x in figs}) == len(figs), 'duplicate figure title'
probs = [p for f in ['p_', 'p2_', 'p3_', 'p4_'] for a in AREAS for p in js(f + a + '.json')['problems']]
assert len({p['id'] for p in probs}) == len(probs), 'duplicate problem id'
pfig = js('figs_prob.json')['figs']
for n in (2, 3, 4, 5):
    for a in AREAS:
        fn = f'figs_prob{n}_{a}.json'
        if os.path.exists(os.path.join(CON, fn)): pfig.update(js(fn)['figs'])
assert all(p['id'] in pfig for p in probs), [p['id'] for p in probs if p['id'] not in pfig]
lfig = js('figs_lad.json')['figs']
for a in AREAS: lfig.update(js(f'figs_lad2_{a}.json')['figs'])
lads = js('ladders.json')['ladders'] + [l for a in AREAS for l in js(f'ladders2_{a}.json')['ladders']]
assert len({l['id'] for l in lads}) == len(lads) and all(l['id'] in lfig for l in lads)
mem = [m for a in AREAS for f in (f'mem_{a}.json', f'mem2_{a}.json') for m in js(f)['items']]
assert len({m['id'] for m in mem}) == len(mem), 'duplicate memory id'
cues = {}
for a in AREAS: cues.update(js(f'cues_{a}.json')['cues'])
for x in figs: x['svg'] = fix_svg(x['svg'])
pfig = {k: fix_svg(v) for k, v in pfig.items()}
lfig = {k: fix_svg(v) for k, v in lfig.items()}
CONTENT = {'questions': qs, 'boards': bs, 'figs': figs, 'derivs': js('derivs.json')['derivs'], 'formulas': js('formulas.json')['formulas'],
           'problems': probs, 'ladders': lads, 'ladfigs': lfig, 'probfigs': pfig, 'memory': mem, 'cues': cues}
content_json = json.dumps(CONTENT, ensure_ascii=False)
content_json = content_json.replace('Bricolage Grotesque, system-ui', 'Roboto, system-ui')

# ---------- page parts ----------
t = rd(APP, 'template.html')
head = t[:t.index('</style>')].replace('<title>Quals Daily</title>', '<title>Quals Lingo</title>')
head = re.sub(r'<link rel="stylesheet" href="https://fonts.googleapis.com/css2[^"]*">',
              '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Roboto:ital,wght@0,300;0,400;0,500;0,700;0,900;1,400&family=STIX+Two+Text:ital,wght@0,400;0,600;1,400&display=swap">', head)
head = head.replace('"Bricolage Grotesque",', '"Roboto",').replace('"Spectral",', '')
css = rd(APP, 'extra.css') + rd(APP, 'theme.css')
body = rd(APP, 'body.html')
i = body.index('<script>'); markup, script = body[:i], body[i + 8:body.rindex('</script>')]
assert '/*__CONTENT__*/' in script
for chk in (head, css, markup, script, content_json):
    assert not any(c in '—–' for c in chk), 'em or en dash found'
    assert 'ASDL' not in chk.replace('ASDL//', '')

def h(s): return hashlib.sha256(s.encode()).hexdigest()[:10]
META = ('<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="color-scheme" content="dark light"><meta name="theme-color" content="#002C56">')

# ---------- single-file builds ----------
inline = head + css + '</style>\n\n' + markup + '<script>' + script.replace('/*__CONTENT__*/', content_json.replace('</', '<\\/')) + '</script>'
os.makedirs(DIST, exist_ok=True)
open(os.path.join(DIST, 'quals-artifact.html'), 'w', encoding='utf-8').write(inline)
j = inline.index('</style>') + len('</style>')
open(os.path.join(DIST, 'Quals-Lingo.html'), 'w', encoding='utf-8').write(
    '<!doctype html>\n<html lang="en"><head>' + META + inline[:j] + '</head>\n<body>\n' + inline[j:] + '\n</body></html>\n')

# ---------- website ----------
if os.path.exists(SITE): shutil.rmtree(SITE)
os.makedirs(os.path.join(SITE, 'vendor')); os.makedirs(os.path.join(SITE, 'icons'))
app_js = script.replace('/*__CONTENT__*/', 'window.QL_CONTENT')
content_js = 'window.QL_CONTENT=' + content_json + ';'
auth_js = rd(WEB, 'auth.js')
files = {f'app.{h(app_js)}.js': app_js, f'content.{h(content_js)}.js': content_js, f'auth.{h(auth_js)}.js': auth_js}
for name, text in files.items(): open(os.path.join(SITE, name), 'w', encoding='utf-8').write(text)
for v in os.listdir(os.path.join(WEB, 'vendor')): shutil.copy(os.path.join(WEB, 'vendor', v), os.path.join(SITE, 'vendor', v))
cfg = os.path.join(ROOT, 'config.js')
shutil.copy(cfg if os.path.exists(cfg) else os.path.join(ROOT, 'config.example.js'), os.path.join(SITE, 'config.js'))
for f in os.listdir(os.path.join(WEB, 'icons')): shutil.copy(os.path.join(WEB, 'icons', f), os.path.join(SITE, 'icons', f))
shutil.copy(os.path.join(WEB, 'manifest.webmanifest'), SITE)
open(os.path.join(SITE, '.nojekyll'), 'w').write('')
app_name, content_name, auth_name = list(files)
index = ('<!doctype html>\n<html lang="en"><head>' + META +
         '<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes">'
         '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent"><meta name="apple-mobile-web-app-title" content="Quals Lingo">'
         '<meta name="description" content="Daily reps for the SDO and SMM oral qualifying exams.">'
         '<link rel="manifest" href="manifest.webmanifest"><link rel="icon" href="icons/icon-32.png" sizes="32x32">'
         '<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">'
         + head + css + '</style></head>\n<body>\n' + markup +
         '<script src="config.js"></script>\n<script src="vendor/supabase.js"></script>\n'
         f'<script src="{auth_name}"></script>\n<script src="{content_name}"></script>\n<script src="{app_name}"></script>\n'
         '<script>if("serviceWorker" in navigator&&location.protocol!=="file:")addEventListener("load",()=>navigator.serviceWorker.register("sw.js").catch(()=>{}));</script>\n'
         '</body></html>\n')
open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8').write(index)
version = h(index + ''.join(files))
sw = rd(WEB, 'sw.js').replace('__VERSION__', version).replace('__ASSETS__', json.dumps(['./', 'index.html', 'config.js', 'manifest.webmanifest', 'vendor/supabase.js'] + list(files)))
open(os.path.join(SITE, 'sw.js'), 'w', encoding='utf-8').write(sw)
print(f'built site/ ({len(qs)} questions, {len(probs)} problems, {len(figs)} figures, {len(lads)} ladders, {len(mem)} memory items), version {version}')
