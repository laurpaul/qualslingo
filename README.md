# Quals Lingo

Daily, Duolingo-style practice for the SDO and SMM oral qualifying exams, with Delta the jet keeping you honest.

- 920 lesson questions, 280 oral board prompts, 38 oral ladders, 150 board problems with figures, 362 memory questions, 209 formulas with memory cues, 149 teaching figures
- Accounts, so progress follows each person to any phone or laptop and survives every code update
- League, shared mock-board bookings and live duels for a study group
- Installs to a phone's home screen and works offline

## What is in this repository

| Path | What it is |
|---|---|
| `src/app/` | The app: markup and code (`body.html`), styles (`extra.css`, `theme.css`), page head (`template.html`) |
| `src/content/` | All study content as JSON (questions, boards, problems, figures, ladders, memory items) |
| `src/web/` | Website files: account layer (`auth.js`), service worker, manifest, icons, the Supabase client |
| `supabase/schema.sql` | Database tables and access rules for accounts |
| `config.js` | Your Supabase project URL and public key (empty means no accounts) |
| `build.py` | Builds the website into `site/` and two single files into `dist/` |
| `.github/workflows/deploy.yml` | Builds and publishes to GitHub Pages on every push to `main` |
| `tools/` | Automated tests |

## 1. Put it on GitHub Pages (about 5 minutes)

1. Create a new repository on GitHub and push this folder to its `main` branch:
   ```
   git remote add origin https://github.com/<you>/quals-lingo.git
   git push -u origin main
   ```
2. In the repository: Settings > Pages > Build and deployment > Source: **GitHub Actions**.
3. The "Build and deploy Quals Lingo" workflow runs on the push. When it finishes, the site is at `https://<you>.github.io/quals-lingo/`.

At this point the site works with no accounts: each browser keeps its own progress.

## 2. Turn on accounts (about 10 minutes, free)

Accounts use [Supabase](https://supabase.com) (hosted Postgres plus sign-in). The website stays a static GitHub Pages site; it talks to Supabase from the browser.

1. Create a free Supabase project.
2. Open **SQL Editor > New query**, paste all of `supabase/schema.sql`, and press **Run**. It is safe to run again later.
3. **Authentication > URL Configuration**: set **Site URL** to your Pages address (for example `https://<you>.github.io/quals-lingo/`) and add the same address under **Redirect URLs**. This is where confirmation and password reset emails send people.
4. **Authentication > Providers > Email**: keep Email enabled. "Confirm email" on is safer; turn it off if you want people in immediately.
5. **Project Settings > API**: copy the **Project URL** and the **anon public** key into `config.js`:
   ```js
   window.QL_CONFIG = {
     supabaseUrl: "https://abcdefgh.supabase.co",
     supabaseAnonKey: "eyJhbGciOi..."
   };
   ```
   The anon key is meant to be public. The rules in `schema.sql` decide what each signed-in person can read and write.
6. Commit and push. The site now opens with a sign-in screen; people can also choose "Use without an account".

### Make yourself the coordinator

Coordinators can post a notice, hide a question, add questions, and review flagged and suggested questions. After you have signed up once, run in the SQL Editor:

```sql
insert into public.admins (user_id) select id from auth.users where email = 'you@example.com';
```

### Who can see what

- Your progress: only you (and coordinators).
- League rows, session bookings, the coordinator notice and coordinator questions: everyone who is signed in.
- Display names: everyone who is signed in.
- Anyone with the link can create an account. To limit sign-ups to your group, turn off **Allow new users to sign up** in the Authentication settings once everyone has joined, or invite people from **Authentication > Users**.

## 3. Updating the app without losing anyone's progress

1. Edit files in `src/` (content JSON or app code).
2. Preview locally:
   ```
   python3 build.py
   python3 -m http.server 8000 -d site
   ```
   then open http://localhost:8000.
3. Commit and push. GitHub Actions rebuilds and redeploys. Everyone gets the new version the next time they open the app.

Progress is safe across updates because:

- Each person's progress is stored in the database under their account, separate from the code.
- Progress is keyed by question, problem and memory ids. **Never rename or reuse an existing id**; add new ids for new content. Deleting an item simply drops it from reviews.
- New settings and fields get default values when an older saved copy loads (`normalize()` in `body.html`).
- If someone studied offline or on two devices, the newest copy wins when they next open the app.
- The service worker always fetches the page fresh when online, and app files carry a content hash in their names, so no one is stuck on an old version.

## 4. On a phone

Open the site and use **Share > Add to Home Screen** (iPhone, Safari) or **Install app** (Android, Chrome). It opens full screen like an app and works offline; progress syncs when the phone is back online. Layouts are tested from 320 px wide (iPhone SE) up to desktop.

## 5. Tests

```
pip install playwright        # Chromium must be available
python3 build.py
python3 tools/test_site.py
```

The test serves the built site twice: once without accounts, and once with a stand-in for Supabase. It checks progress saving, sync to a fresh device, picking up an app update with progress intact, sign out, two people on one device, offline loading, and phone layouts. `tools/test_schema.sql` and `tools/test_rls.sql` check the database access rules against a plain Postgres.

## Notes

- Supabase's free tier is plenty for a study group. At the time of writing, free projects pause after about a week with no activity; the data stays, and you resume the project from the dashboard.
- `dist/Quals-Lingo.html` is a single file that works offline with no account, handy to email to someone.
- Fonts load from Google Fonts; without a connection the app falls back to system fonts.
