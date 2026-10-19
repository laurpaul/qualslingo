"""End-to-end test of the built site: local mode, accounts (with a mock Supabase), sync across 'devices', updates, offline.
Run: python3 build.py && python3 tools/test_site.py"""
import os, shutil, subprocess, sys, time, json, tempfile
from playwright.sync_api import sync_playwright
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tmp = tempfile.mkdtemp()
local, acct = os.path.join(tmp, 'local'), os.path.join(tmp, 'acct')
shutil.copytree(os.path.join(ROOT, 'site'), local); shutil.copytree(os.path.join(ROOT, 'site'), acct)
shutil.copy(os.path.join(ROOT, 'tools', 'mock-supabase.js'), os.path.join(acct, 'vendor', 'supabase.js'))
open(os.path.join(acct, 'config.js'), 'w').write('window.QL_CONFIG={supabaseUrl:"https://example.supabase.co",supabaseAnonKey:"test"};')
srv = [subprocess.Popen([sys.executable, '-m', 'http.server', str(p), '-d', d], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for p, d in ((8701, local), (8702, acct))]
time.sleep(1.2)
fails = []
def check(cond, msg): print(('ok   ' if cond else 'FAIL ') + msg); cond or fails.append(msg)
def lesson(pg):
    pg.evaluate("startLesson('o1')"); pg.wait_for_timeout(150)
    for _ in range(40):
        if pg.query_selector('#layer .end'): break
        for sel in ['#bSkip', '#bCont', '#bNext']:
            b = pg.query_selector(sel)
            if b and b.is_visible() and b.is_enabled(): b.click(); pg.wait_for_timeout(40); break
    d = pg.query_selector('#layer .end .btn') ; d and d.click(); pg.wait_for_timeout(100)
try:
    with sync_playwright() as p:
        br = p.chromium.launch()
        # ---------- local mode on a phone ----------
        ctx = br.new_context(viewport={'width': 375, 'height': 667}, is_mobile=True, has_touch=True)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('http://localhost:8701/'); pg.wait_for_selector('#wStart', timeout=15000)
        check(not pg.query_selector('.authgate'), 'local mode shows no sign-in gate')
        pg.click('#wStart'); pg.wait_for_timeout(300); pg.evaluate("L=null;closeLayer();render()")
        lesson(pg); n = pg.evaluate('S.lessons')
        check(n >= 1, f'local lesson recorded (lessons={n})')
        pg.reload(); pg.wait_for_timeout(1500)
        check(pg.evaluate('S.lessons') == n, 'local progress survives reload')
        check(pg.evaluate('document.documentElement.scrollWidth') <= 375, 'no sideways scroll at 375 px')
        pg.wait_for_function('navigator.serviceWorker.controller!==null', timeout=10000)
        check(True, 'service worker controls the page')
        ctx.set_offline(True); pg.reload(); pg.wait_for_timeout(1500)
        check(pg.evaluate('typeof S==="object"&&S.lessons') == n, 'app loads offline from the service worker cache')
        ctx.set_offline(False)
        check(not errs, f'no page errors in local mode {errs[:2]}')
        ctx.close()
        # ---------- accounts ----------
        ctx = br.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        pg = ctx.new_page(); errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
        pg.goto('http://localhost:8702/'); pg.wait_for_selector('.authgate', timeout=15000)
        check(True, 'sign-in gate appears when accounts are configured')
        pg.screenshot(path=os.path.join(ROOT, 'tools', 'shot-gate.png'))
        pg.click('[data-go="up"]'); pg.fill('#agName', 'Vic'); pg.fill('#agEmail', 'vic@example.com'); pg.fill('#agPw', 'correct horse 1'); pg.click('.agcard button[type=submit]')
        pg.wait_for_selector('.authgate', state='detached', timeout=8000); pg.wait_for_timeout(800)
        check(pg.evaluate('saveMode') == 'db', 'signed in: progress saves to the account')
        w = pg.query_selector('#wStart'); w and w.click(); pg.wait_for_timeout(300); pg.evaluate("L=null;closeLayer();render()")
        lesson(pg); lesson(pg); pg.evaluate('flushSave()'); pg.wait_for_timeout(500)
        n = pg.evaluate('S.lessons'); uid = pg.evaluate('uid')
        server = json.loads(pg.evaluate("localStorage.getItem('mock-server')"))
        st = server['docs'].get(f'data/users/{uid}/state', {}).get('data', {})
        check(st.get('lessons') == n and n >= 2, f'account copy on the server has the lessons ({st.get("lessons")} of {n})')
        check(server['profiles'].get(uid) == 'Vic', 'display name stored in profiles')
        # new device: wipe this browser's local copies but keep the server and the session
        pg.evaluate("Object.keys(localStorage).filter(k=>k.startsWith('qd-state')).forEach(k=>localStorage.removeItem(k))")
        pg.reload(); pg.wait_for_timeout(2000)
        check(pg.evaluate('S.lessons') == n, 'progress restored from the account on a fresh device')
        # app update: rebuild-like change of the app bundle name keeps progress (the server copy is keyed by user, not by version)
        pg.evaluate("localStorage.setItem('qd-state:'+uid, JSON.stringify(Object.assign({},S,{ts:1})))")  # stale local copy
        pg.reload(); pg.wait_for_timeout(2000)
        check(pg.evaluate('S.lessons') == n, 'newer account copy wins over a stale local copy')
        # ship an app update: new app bundle name in index.html, served from the same site
        import glob, re as _re
        old = os.path.basename(glob.glob(os.path.join(acct, 'app.*.js'))[0])
        code = open(os.path.join(acct, old)).read() + '\nwindow.QL_UPDATED=true;'
        open(os.path.join(acct, 'app.updated.js'), 'w').write(code)
        idx = open(os.path.join(acct, 'index.html')).read().replace(old, 'app.updated.js'); open(os.path.join(acct, 'index.html'), 'w').write(idx)
        pg.reload(); pg.wait_for_timeout(2500)
        check(pg.evaluate('window.QL_UPDATED===true'), 'updated app code is picked up on the next load')
        check(pg.evaluate('S.lessons') == n, 'progress is intact after the update')
        # sign out, then a second person on the same device
        pg.evaluate('openSettings()'); pg.wait_for_timeout(200)
        check(bool(pg.query_selector('#acctOut')), 'settings shows the account and a sign-out button')
        pg.click('#acctOut'); pg.wait_for_selector('.authgate', timeout=8000)
        check(True, 'sign out returns to the gate')
        pg.click('[data-go="up"]'); pg.fill('#agName', 'Sam'); pg.fill('#agEmail', 'sam@example.com'); pg.fill('#agPw', 'another pass 2'); pg.click('.agcard button[type=submit]')
        pg.wait_for_selector('.authgate', state='detached', timeout=8000); pg.wait_for_timeout(1500)
        check(pg.evaluate('S.lessons') == 0, 'second person starts fresh (no leak of the first person\'s progress)')
        pg.evaluate('openSettings()'); pg.click('#acctOut'); pg.wait_for_selector('.authgate', timeout=8000)
        pg.fill('#agEmail', 'vic@example.com'); pg.fill('#agPw', 'correct horse 1'); pg.click('.agcard button[type=submit]')
        pg.wait_for_selector('.authgate', state='detached', timeout=8000); pg.wait_for_timeout(1500)
        check(pg.evaluate('S.lessons') == n, 'first person signs back in and gets their progress')
        pg.evaluate("setTab('group')"); pg.wait_for_timeout(300)
        check('Weekly league' in pg.inner_text('#view'), 'league shows for signed-in users')
        check(pg.evaluate('document.documentElement.scrollWidth') <= 390, 'no sideways scroll at 390 px')
        # use without an account
        pg.evaluate('openSettings()'); pg.click('#acctOut'); pg.wait_for_selector('.authgate', timeout=8000)
        pg.click('[data-off]'); pg.wait_for_timeout(800)
        check(not pg.query_selector('.authgate') and pg.evaluate('saveMode') != 'db', 'can study without an account')
        pg.reload(); pg.wait_for_timeout(1500)
        check(not pg.query_selector('.authgate'), 'the no-account choice is remembered')
        check(not errs, f'no page errors with accounts {errs[:2]}')
        br.close()
finally:
    for s in srv: s.terminate()
print('\n' + ('ALL PASSED' if not fails else f'{len(fails)} FAILED'))
sys.exit(1 if fails else 0)
