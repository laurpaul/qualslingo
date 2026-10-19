/* Quals Lingo: accounts and shared data on Supabase.
 *
 * The app was written against a small storage API (window.claude.use("db" | "user" | "room" | "downloads")).
 * This file provides that API on top of Supabase, so the app code runs unchanged:
 *   db    -> table public.docs (path text primary key, data jsonb), see supabase/schema.sql
 *   user  -> Supabase Auth user + public.profiles (display names) + public.admins (coordinators)
 *   room  -> Supabase Realtime presence channels (live duels)
 * If config.js has no Supabase keys, nothing here runs and the app works on this device only.
 */
(function () {
  "use strict";
  var cfg = window.QL_CONFIG || {};
  if (!cfg.supabaseUrl || !cfg.supabaseAnonKey || !window.supabase) return;

  var OFFLINE_KEY = "ql-offline";
  var sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, storageKey: "ql-auth" }
  });

  /* Read the cached session synchronously so the first paint already shows this person's progress. */
  var cached = null;
  try { cached = JSON.parse(localStorage.getItem("ql-auth") || "null"); } catch (e) {}
  var cachedUser = cached && (cached.user || (cached.currentSession && cached.currentSession.user));
  if (cachedUser && cachedUser.id) window.QL_UID = cachedUser.id;

  var session = null, profileName = "";
  var readyResolve; var ready = new Promise(function (r) { readyResolve = r; });
  var offline = localStorage.getItem(OFFLINE_KEY) === "1";

  function setSession(s) {
    var before = session && session.user && session.user.id;
    session = s;
    if (s && s.user) {
      localStorage.removeItem(OFFLINE_KEY);
      hideGate();
      ensureProfile().finally(function () { readyResolve(true); });
      // A different person signed in on this device: start the app fresh for them.
      if (window.QL_UID && window.QL_UID !== s.user.id) location.reload();
    } else if (before) {
      location.reload();
    }
  }

  sb.auth.onAuthStateChange(function (evt, s) {
    if (evt === "PASSWORD_RECOVERY") { showGate("reset"); return; }
    if (evt === "SIGNED_OUT") { window.QL_UID = null; location.reload(); return; }
    if (s && s.user) setSession(s);
  });
  sb.auth.getSession().then(function (r) {
    var s = r && r.data && r.data.session;
    if (s && s.user) setSession(s);
    else if (offline) readyResolve(false);
    else { window.QL_UID = null; showGate("in"); }
  });

  function uid() { return session && session.user ? session.user.id : null; }

  async function ensureProfile() {
    var id = uid(); if (!id) return;
    try {
      var r = await sb.from("profiles").select("name").eq("id", id).maybeSingle();
      var meta = (session.user.user_metadata || {}).name || "";
      profileName = (r.data && r.data.name) || meta || (session.user.email || "").split("@")[0];
      if (!r.data || !r.data.name) await sb.from("profiles").upsert({ id: id, name: profileName });
    } catch (e) {}
  }

  /* ---------- Sign-in gate ---------- */
  var gate = null, mode = "in";
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function hideGate() { if (gate) { gate.remove(); gate = null; document.body.style.overflow = ""; } }
  function showGate(m) {
    mode = m || "in";
    if (!document.body) { document.addEventListener("DOMContentLoaded", function () { showGate(mode); }); return; }
    if (!gate) { gate = document.createElement("div"); gate.className = "authgate"; document.body.appendChild(gate); }
    document.body.style.overflow = "hidden";
    var title = { in: "Sign in", up: "Create your account", forgot: "Reset your password", reset: "Choose a new password", check: "Check your email" }[mode];
    var body = "";
    if (mode === "check") {
      body = '<p>We sent you a link. Open it on this device to finish, then come back here.</p><div class="row"><button class="btn" data-go="in">Back to sign in</button></div>';
    } else if (mode === "reset") {
      body = '<form data-act="reset"><label class="label" for="agPw">New password</label><input id="agPw" type="password" minlength="8" autocomplete="new-password" required><div class="row"><button class="btn" type="submit">Save password</button></div></form>';
    } else {
      body = '<form data-act="' + mode + '">' +
        (mode === "up" ? '<label class="label" for="agName">Your name (shown to your study group)</label><input id="agName" maxlength="40" autocomplete="nickname" required>' : "") +
        '<label class="label" for="agEmail">Email</label><input id="agEmail" type="email" autocomplete="email" inputmode="email" required>' +
        (mode !== "forgot" ? '<label class="label" for="agPw">Password</label><input id="agPw" type="password" minlength="8" autocomplete="' + (mode === "up" ? "new-password" : "current-password") + '" required>' : "") +
        '<div class="row"><button class="btn" type="submit">' + { in: "Sign in", up: "Create account", forgot: "Send reset link" }[mode] + "</button></div></form>" +
        '<p class="agmsg" role="status"></p>' +
        '<div class="aglinks">' +
        (mode === "in" ? '<button class="link" data-go="up">New here? Create an account</button><button class="link" data-go="forgot">Forgot password</button>' : '<button class="link" data-go="in">I already have an account</button>') +
        "</div>";
    }
    gate.innerHTML = '<div class="agcard" role="dialog" aria-modal="true" aria-labelledby="agT">' +
      '<div class="agtop">' + (window.mascotSVG ? window.mascotSVG(mode === "in" ? "stern" : "smug", 80) : "") + '<div><span class="label">Quals Lingo</span><h2 id="agT">' + title + "</h2></div></div>" +
      body +
      '<button class="link agoff" data-off="1">Use without an account on this device</button>' +
      '<p class="note">With an account your progress follows you to any phone or laptop and survives app updates.</p></div>';
    gate.querySelectorAll("[data-go]").forEach(function (b) { b.onclick = function () { showGate(b.getAttribute("data-go")); }; });
    gate.querySelector("[data-off]").onclick = function () { localStorage.setItem(OFFLINE_KEY, "1"); hideGate(); readyResolve(false); };
    var f = gate.querySelector("form"); if (f) f.onsubmit = submit;
    var first = gate.querySelector("input"); if (first) first.focus();
    if (!window.mascotSVG && document.readyState !== "complete") addEventListener("load", function () { if (gate && ![].some.call(gate.querySelectorAll("input"), function (i) { return i.value; })) showGate(mode); }, { once: true });
  }
  async function submit(e) {
    e.preventDefault();
    var msg = gate.querySelector(".agmsg"), btn = gate.querySelector("button[type=submit]");
    var act = e.target.getAttribute("data-act");
    var email = (gate.querySelector("#agEmail") || {}).value, pw = (gate.querySelector("#agPw") || {}).value;
    var redirect = location.origin + location.pathname;
    btn.disabled = true; if (msg) msg.textContent = "";
    try {
      var r;
      if (act === "in") r = await sb.auth.signInWithPassword({ email: email, password: pw });
      else if (act === "up") {
        var name = gate.querySelector("#agName").value.trim();
        r = await sb.auth.signUp({ email: email, password: pw, options: { data: { name: name }, emailRedirectTo: redirect } });
        if (!r.error && !(r.data && r.data.session)) { showGate("check"); return; }
      } else if (act === "forgot") {
        r = await sb.auth.resetPasswordForEmail(email, { redirectTo: redirect });
        if (!r.error) { showGate("check"); return; }
      } else if (act === "reset") {
        r = await sb.auth.updateUser({ password: pw });
        if (!r.error) { hideGate(); return; }
      }
      if (r && r.error) throw r.error;
    } catch (err) {
      if (msg) msg.textContent = (err && err.message) || "That did not work. Try again.";
    } finally { if (btn) btn.disabled = false; }
  }

  /* ---------- db: document store over public.docs ---------- */
  function err(e) { var x = new Error(e && e.message || "db error"); x.code = e && e.code === "42501" ? "permission_denied" : (e && e.code) || "unknown"; return x; }
  function snap(path, data) { return { id: path.split("/").pop(), exists: data != null, data: function () { return data; } }; }
  function qsnap(rows) { return { docs: rows.map(function (r) { return snap(r.path, r.data); }), size: rows.length, empty: !rows.length }; }
  var uidCounter = 0;
  function newId() { return Date.now().toString(36) + Math.random().toString(36).slice(2, 8) + (uidCounter++); }

  function watch(filter, refetch, cb, onErr) {
    var alive = true, t = null;
    function run() { refetch().then(function (v) { if (alive) cb(v); }).catch(function (e) { if (alive && onErr) onErr(err(e)); }); }
    run();
    var ch = sb.channel("w-" + newId()).on("postgres_changes", { event: "*", schema: "public", table: "docs", filter: filter },
      function () { clearTimeout(t); t = setTimeout(run, 150); }).subscribe();
    return function () { alive = false; sb.removeChannel(ch); };
  }

  function docRef(path) {
    return {
      id: path.split("/").pop(), path: path,
      get: async function () {
        var r = await sb.from("docs").select("data").eq("path", path).maybeSingle();
        if (r.error) throw err(r.error); return snap(path, r.data ? r.data.data : null);
      },
      set: async function (data) {
        var r = await sb.from("docs").upsert({ path: path, data: data }, { onConflict: "path" });
        if (r.error) throw err(r.error);
      },
      update: async function (patch) {
        var r = await sb.rpc("doc_merge", { p_path: path, p_patch: patch });
        if (r.error) throw err(r.error);
      },
      delete: async function () {
        var r = await sb.from("docs").delete().eq("path", path);
        if (r.error) throw err(r.error);
      },
      onSnapshot: function (cb, onErr) {
        return watch("path=eq." + path, function () { return docRef(path).get(); }, cb, onErr);
      }
    };
  }
  function query(coll, filters) {
    function apply(rows) {
      return rows.filter(function (r) {
        return filters.every(function (f) {
          var v = r.data ? r.data[f[0]] : undefined;
          switch (f[1]) { case ">=": return v >= f[2]; case ">": return v > f[2]; case "<=": return v <= f[2]; case "<": return v < f[2]; case "==": return v === f[2]; case "!=": return v !== f[2]; default: return true; }
        });
      });
    }
    async function fetchAll() {
      var r = await sb.from("docs").select("path,data").eq("coll", coll).limit(2000);
      if (r.error) throw err(r.error); return qsnap(apply(r.data || []));
    }
    return {
      where: function (f, op, v) { return query(coll, filters.concat([[f, op, v]])); },
      get: fetchAll,
      onSnapshot: function (cb, onErr) { return watch("coll=eq." + coll, fetchAll, cb, onErr); },
      add: async function (data) { var ref = docRef(coll + "/" + newId()); await ref.set(data); return ref; },
      doc: function (id) { return docRef(coll + "/" + (id || newId())); }
    };
  }
  var db = { doc: docRef, collection: function (c) { return query(c, []); } };

  /* ---------- user ---------- */
  var user = {
    id: async function () { return uid(); },
    profiles: async function (ids) {
      var out = {}; if (!ids || !ids.length) return out;
      var r = await sb.from("profiles").select("id,name").in("id", ids.slice(0, 200));
      (r.data || []).forEach(function (p) { out[p.id] = { name: p.name || "" }; });
      return out;
    },
    canEdit: async function () { var r = await sb.rpc("is_admin"); return !!(r && r.data); }
  };

  /* ---------- room: realtime presence for live duels ---------- */
  var room = {
    join: function (name) {
      return new Promise(function (resolve, reject) {
        var key = (uid() || "anon") + "-" + newId();
        var ch = sb.channel("room-" + name, { config: { presence: { key: key } } });
        var mine = {}, peerCbs = [], closeCbs = [];
        ch.on("presence", { event: "sync" }, function () { peerCbs.forEach(function (f) { try { f(); } catch (e) {} }); });
        var api = {
          presence: function (obj) { mine = Object.assign({}, mine, obj); return ch.track(mine); },
          peers: function () {
            var st = ch.presenceState(); var out = [];
            Object.keys(st).forEach(function (k) { var a = st[k]; if (a && a.length) { var p = a[a.length - 1]; out.push({ by: p.uid || k, presence: p, self: k === key }); } });
            return out;
          },
          onPeers: function (cb, onClose) { if (cb) peerCbs.push(cb); if (onClose) closeCbs.push(onClose); },
          leave: function () { return sb.removeChannel(ch); }
        };
        ch.subscribe(function (status) {
          if (status === "SUBSCRIBED") resolve(api);
          else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") { reject(new Error(status)); closeCbs.forEach(function (f) { try { f(); } catch (e) {} }); }
          else if (status === "CLOSED") closeCbs.forEach(function (f) { try { f(); } catch (e) {} });
        });
      });
    }
  };

  /* ---------- the API the app expects ---------- */
  window.claude = {
    hosted: true,
    use: function (name) {
      if (name === "downloads" || name === "sample") return Promise.resolve(null);
      return ready.then(function (ok) {
        if (!ok) return null;
        return { db: db, user: user, room: room }[name] || null;
      });
    }
  };
  window.QL_AUTH = {
    signedIn: function () { return !!uid(); },
    email: function () { return session && session.user ? session.user.email : ""; },
    name: function () { return profileName; },
    setName: async function (n) { if (!uid() || !n) return; profileName = n; var r = await sb.from("profiles").upsert({ id: uid(), name: n }); if (r.error) throw r.error; },
    signOut: async function () { try { await sb.auth.signOut(); } finally { location.reload(); } },
    signIn: function () { localStorage.removeItem(OFFLINE_KEY); showGate("in"); }
  };
})();
