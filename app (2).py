"""OneGov - one window to every government department.
Smart India Hackathon 2026: interoperability among government digital platforms.
All department systems are simulated for the demo."""
import datetime as dt
import html
import os

import pandas as pd
import streamlit as st

import ai as AI
import logic as L

st.set_page_config(page_title="OneGov", page_icon="🏛️", layout="wide")

st.markdown("""
<style>
.block-container{max-width:1100px;padding-top:4.5rem}
footer{visibility:hidden}
.brand{display:flex;align-items:center;gap:10px;font-size:1.8rem;font-weight:800;color:#1a56db}
.logo{background:#1a56db;color:#fff;border-radius:12px;padding:6px 10px;font-size:1.3rem}
.hero{background:linear-gradient(135deg,#1e3a8a,#2563eb);color:#fff;padding:22px 26px;border-radius:20px;margin:8px 0 10px}
.hero small{letter-spacing:.08em;font-weight:700;opacity:.9}
.hero h2{color:#fff;margin:6px 0 4px}.hero p{opacity:.92;margin:0}
.card{border:1px solid rgba(128,128,128,.28);border-radius:16px;padding:14px 18px;margin-bottom:10px;background:rgba(128,128,128,.06)}
.svc{border:1px solid rgba(128,128,128,.28);border-radius:14px;padding:12px;text-align:center;background:rgba(128,128,128,.06)}
.pill{display:inline-block;padding:2px 11px;border-radius:20px;font-size:.78rem;font-weight:700;margin-right:6px}
.s0{background:#e0e7ff;color:#3730a3}.s1{background:#fef3c7;color:#92400e}.s2{background:#dbeafe;color:#1e40af}
.s3{background:#ede9fe;color:#5b21b6}.s4{background:#d1fae5;color:#065f46}
.bad{background:#fee2e2;color:#991b1b}.ok{background:#d1fae5;color:#065f46}.info{background:#e0f2fe;color:#075985}
.bar{height:8px;background:rgba(128,128,128,.25);border-radius:6px;overflow:hidden;margin:8px 0 4px}
.bar div{height:8px;background:#2563eb}.bar.done div{background:#10b981}
.small{font-size:.85rem;opacity:.8}
.urg5,.urg4{color:#dc2626;font-weight:700}.urg3{color:#d97706;font-weight:700}.urg2,.urg1{color:#059669;font-weight:700}
div[data-testid="stTextInput"] input{font-size:1.05rem}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def get_store():
    return L.new_store()


store = get_store()
ss = st.session_state
for k, v in {"user": None, "role": None, "dept": None, "selected": None, "results": None, "nonce": 0,
             "q": "", "ai_err": "", "gsum": {}}.items():
    ss.setdefault(k, v)


def esc(x):
    return html.escape(str(x))


def get_key():
    k = os.environ.get("GEMINI_API_KEY", "")
    if not k:
        try:
            k = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:  # noqa: BLE001
            k = ""
    return k


api_key = get_key()


def fmt(t):
    return t.strftime("%d %b, %I:%M %p")


def pill(a):
    return f'<span class="pill s{a["status"]}">{esc(L.WORKFLOWS[a["kind"]][a["status"]])}</span>'


def card(a, who=False):
    svc = L.SERVICES[a["service"]]
    pct = int((a["status"] + 1) / 5 * 100)
    due = L.due(store, a)
    late = L.is_overdue(store, a)
    sla = f'<span class="pill bad">SLA overdue</span>' if late else f'SLA {due:%d %b}'
    queued = '<span class="pill bad">Queued - connector down</span>' if a["queued"] else ""
    user_line = ""
    if who:
        p = store["users"][a["citizen"]]["profile"]
        user_line = f' &bull; {esc(p["full_name"])} &bull; {esc(a["ward"])}'
    done = "done" if a["status"] == 4 else ""
    return (f'<div class="card"><span class="small">{a["id"]}</span> &nbsp; {pill(a)}{queued}'
            f'<span class="urg{a["urgency"]}">U{a["urgency"]}</span><br>'
            f'<b>{svc["icon"]} {esc(svc["name"])}</b> &rarr; {esc(a["dept"])}{user_line}<br>'
            f'<span class="small">{esc(a["text"][:140])}</span>'
            f'<div class="bar {done}"><div style="width:{pct}%"></div></div>'
            f'<span class="small">{a["status"] + 1}/5 steps &bull; {sla}</span></div>')


def timeline(a):
    for t, text in a["history"]:
        st.markdown(f"- `{fmt(t)}` {text}")


def login(role, user=None, dept=None):
    ss.role, ss.user, ss.dept = role, user, dept
    L.audit(store, user or role, role, "login", "Single sign-on session started" if role == "citizen" else f"{role} login")
    st.rerun()


# ============================ LOGIN ============================
if not ss.role:
    st.markdown('<div class="brand"><span class="logo">🏛️</span>OneGov</div>', unsafe_allow_html=True)
    st.caption("One profile. One login. Every government service.")
    role = st.radio("I am a", ["🏠 Citizen", "🏛️ Department officer", "🛠️ Admin / monitoring"], horizontal=True)
    if role.startswith("🏠"):
        t1, t2 = st.tabs(["Sign in", "Create your profile"])
        with t1:
            st.subheader("Welcome back")
            with st.form("citizen_login"):
                email = st.text_input("Email address", placeholder="yourname@email.com")
                pw = st.text_input("Password", type="password")
                go = st.form_submit_button("Sign in", type="primary")
            if go:
                u = store["users"].get(email.strip().lower())
                if u and u["password"] == pw:
                    login("citizen", email.strip().lower())
                else:
                    st.error("Email or password is wrong. Use the demo credentials below.")
            st.info(f"**DEMO CITIZEN**  \nEmail: `{L.DEMO_CITIZEN[0]}`  \nPassword: `{L.DEMO_CITIZEN[1]}`")
        with t2:
            st.subheader("Create your OneGov profile (once)")
            st.caption("Enter your details one time. Every department uses this master profile, so you never type them again.")
            with st.form("signup"):
                c1, c2 = st.columns(2)
                name = c1.text_input("Full name")
                father = c2.text_input("Father's / guardian's name")
                dob = c1.date_input("Date of birth", value=dt.date(1998, 1, 1), min_value=dt.date(1930, 1, 1), max_value=dt.date.today())
                gender = c2.selectbox("Gender", ["Male", "Female", "Other"])
                mobile = c1.text_input("Mobile number (10 digits)")
                email = c2.text_input("Email address")
                aadhaar = c1.text_input("Aadhaar number (12 digits, demo - use dummy)", type="password")
                pin = c2.text_input("PIN code")
                address = st.text_input("Address")
                c3, c4, c5 = st.columns(3)
                ward = c3.selectbox("Ward / area", L.WARDS)
                district = c4.text_input("District", value="Patna")
                category = c5.selectbox("Category", ["General", "OBC", "SC", "ST", "EWS"])
                occ = c3.text_input("Occupation")
                income = c4.text_input("Annual family income (Rs)")
                pw = c5.text_input("Create password", type="password")
                go = st.form_submit_button("Create profile and continue", type="primary")
            if go:
                prof = {"full_name": name, "father_name": father, "dob": dob.isoformat(), "gender": gender, "mobile": mobile.strip(),
                        "email": email.strip(), "aadhaar": aadhaar.strip(), "address": address, "ward": ward, "pin": pin.strip(),
                        "district": district, "category": category, "occupation": occ, "income": income}
                ok, issues = L.create_user(store, prof, pw)
                if ok:
                    login("citizen", prof["email"])
                else:
                    for i in issues:
                        st.error(i)
    elif role.startswith("🏛️"):
        dept = st.selectbox("Department", list(L.DEPTS))
        slug = L.DEPTS[dept]["slug"]
        with st.form("officer_login"):
            email = st.text_input("Official email")
            pw = st.text_input("Password", type="password")
            go = st.form_submit_button("Sign in", type="primary")
        if go:
            o = store["officers"].get(email.strip().lower())
            if o and o["password"] == pw and o["dept"] == dept:
                login("officer", email.strip().lower(), dept)
            else:
                st.error("Wrong credentials for this department.")
        st.info(f"**DEMO OFFICER - {dept}**  \nEmail: `{slug}.officer@gov.in`  \nPassword: `{L.OFFICER_PW}`")
    else:
        with st.form("admin_login"):
            email = st.text_input("Admin email")
            pw = st.text_input("Password", type="password")
            go = st.form_submit_button("Sign in", type="primary")
        if go:
            if (email.strip().lower(), pw) == L.ADMIN:
                login("admin", email.strip().lower())
            else:
                st.error("Wrong admin credentials.")
        st.info(f"**DEMO ADMIN**  \nEmail: `{L.ADMIN[0]}`  \nPassword: `{L.ADMIN[1]}`")
    st.caption("Smart India Hackathon 2026 demo. All departments, registries and data are simulated.")
    st.stop()

# ============================ SIDEBAR ============================
with st.sidebar:
    st.header("⚙️ OneGov")
    who = {"citizen": lambda: store["users"][ss.user]["profile"]["full_name"],
           "officer": lambda: store["officers"][ss.user]["name"], "admin": lambda: "Administrator"}[ss.role]()
    st.write(f"**{who}**  \n`{ss.role}`")
    if not api_key:
        api_key = st.text_input("Gemini API key (optional)", type="password")
    else:
        st.success("Gemini AI connected")
    if ss.ai_err:
        st.warning("AI note: " + ss.ai_err[:160])
    st.caption("Without a key, smart keyword routing is used.")
    if st.button("Sign out"):
        ss.role = ss.user = ss.dept = ss.selected = ss.results = None
        st.rerun()
    st.divider()
    st.caption("Demo data. Departments are simulated. Data is shared by all visitors of this demo, so you can sign in as citizen and officer on two devices.")

st.markdown('<div class="brand"><span class="logo">🏛️</span>OneGov</div>', unsafe_allow_html=True)


# ============================ CITIZEN ============================
def citizen_view():
    email = ss.user
    user = store["users"][email]
    p = user["profile"]
    mine = sorted([a for a in store["apps"] if a["citizen"] == email], key=lambda a: a["created"], reverse=True)
    events = sorted([e for e in store["events"] if e["citizen"] == email], key=lambda e: e["time"], reverse=True)
    tabs = st.tabs(["🏠 Home", "📋 My applications", "🔔 Notifications", "🛡️ Profile & consent"])

    # ---------- Home ----------
    with tabs[0]:
        st.markdown(f"### Namaste, {esc(p['full_name'].split()[0])} 👋")
        st.markdown("""<div class="hero"><small>✨ AI-POWERED SERVICE SEARCH</small>
<h2>What do you need help with today?</h2>
<p>Type your problem or service in your own words (Hindi / English). OneGov finds the right department and files it for you.</p></div>""",
                    unsafe_allow_html=True)
        q = st.text_input("Search", key="q", label_visibility="collapsed",
                          placeholder='e.g. "mere area mein paani nahi aa raha" or "income certificate"')

        def set_q(v):
            ss.q = v
        chips = ["water problem", "pothole on road", "income certificate", "police complaint", "driving licence"]
        for col, ch in zip(st.columns(len(chips)), chips):
            col.button(ch, on_click=set_q, args=(ch,), key="chip_" + ch)
        if st.button("🔎 Find the right department", type="primary") and q.strip():
            ranked = L.route_keywords(q)
            top, source, summary = ranked[0][0], "Smart keyword routing", ""
            if api_key:
                res, err = AI.route(q, L.SERVICES, api_key)
                ss.ai_err = err
                if res:
                    top, source, summary = res["service_key"], "Gemini AI", res.get("summary", "")
            others = [k for k, _ in ranked if k != top][:3]
            ss.results = {"query": q, "top": top, "others": others, "source": source, "summary": summary}
            ss.selected = top
            ss.nonce += 1

        r = ss.results
        if r:
            s = L.SERVICES[r["top"]]
            info = L.DEPTS[s["dept"]]
            st.markdown(f"""<div class="card"><span class="pill info">{esc(r['source'])}</span><br>
<b style="font-size:1.15rem">{s['icon']} Best match: {esc(s['name'])}</b><br>
Goes to <b>{esc(s['dept'])}</b> &bull; system: {esc(info['system'])} ({esc(info['type'])}, simulated connector)<br>
<span class="small">{esc(r['summary'])}</span></div>""", unsafe_allow_html=True)
            if r["others"]:
                st.caption("Not what you meant? Pick another:")
                for col, k in zip(st.columns(len(r["others"])), r["others"]):
                    if col.button(f"{L.SERVICES[k]['icon']} {L.SERVICES[k]['name']}", key="oth_" + k):
                        ss.selected = k
                        ss.nonce += 1
                        st.rerun()

        st.markdown("#### Quick services")
        for start in (0, 4):
            for col, k in zip(st.columns(4), L.QUICK[start:start + 4]):
                if col.button(f"{L.SERVICES[k]['icon']} {L.SERVICES[k]['name']}", key="q_" + k):
                    ss.selected = k
                    ss.nonce += 1
                    ss.results = None
                    st.rerun()
        with st.expander("All services"):
            for k, sv in L.SERVICES.items():
                if st.button(f"{sv['icon']} {sv['name']} ({sv['dept']})", key="all_" + k):
                    ss.selected = k
                    ss.nonce += 1
                    ss.results = None
                    st.rerun()

        if ss.selected:
            key = ss.selected
            svc = L.SERVICES[key]
            st.divider()
            st.subheader(f"{svc['icon']} {svc['name']}")
            steps = " &rarr; ".join(L.WORKFLOWS[svc["kind"]])
            st.markdown(f'<div class="small">Department: <b>{esc(svc["dept"])}</b> &bull; SLA: {store["sla"][key]} days<br>Workflow: {steps}</div>',
                        unsafe_allow_html=True)
            need = L.NEEDED[svc["kind"]]
            st.markdown("**Auto-filled from your OneGov profile** (you type nothing again):")
            shown = {f.replace("_", " ").title(): (L.mask_aadhaar(p[f]) if f == "aadhaar" else p[f]) for f in need}
            st.dataframe(pd.DataFrame([shown]), hide_index=True)
            n = st.session_state.nonce
            with st.form(f"form_{key}_{n}"):
                extras, text, photo = {}, svc["name"], None
                if svc["kind"] == "complaint":
                    default = r["query"] if r and r["top"] == key else ""
                    text = st.text_area("Describe the problem", value=default, height=100, key=f"t_{key}_{n}")
                    ward = st.selectbox("Ward / area of the problem", L.WARDS, index=L.WARDS.index(p["ward"]) if p["ward"] in L.WARDS else 0,
                                        key=f"w_{key}_{n}")
                    photo = st.file_uploader("📷 Photo (optional)", type=["jpg", "jpeg", "png"], key=f"p_{key}_{n}")
                else:
                    ward = p["ward"]
                    for i, (label, opts) in enumerate(svc["extras"]):
                        extras[label] = (st.selectbox(label, opts, key=f"e{i}_{key}_{n}") if opts
                                         else st.text_input(label, key=f"e{i}_{key}_{n}"))
                    text = st.text_input("Notes (optional)", key=f"n_{key}_{n}") or svc["name"]
                allow = {}
                if svc["sources"]:
                    st.markdown("**Consent** - OneGov fetches verified data from other departments, only with your permission:")
                    for i, s_ in enumerate(svc["sources"]):
                        if L.has_consent(store, email, s_):
                            st.markdown(f"✅ {s_} - already allowed")
                        else:
                            allow[s_] = st.checkbox(f"Allow: {s_}", key=f"c{i}_{key}_{n}")
                go = st.form_submit_button("Submit", type="primary")
            if go:
                if svc["kind"] == "complaint" and not text.strip():
                    st.error("Please describe the problem.")
                else:
                    granted = [s_ for s_, v in allow.items() if v]
                    ok, msg, res = L.create_application(store, email, key, text, ward, extras, granted, has_photo=photo is not None)
                    if ok:
                        a = res
                        if a["queued"]:
                            st.warning(f"Saved as {a['id']}. The {a['dept']} system is down right now, so it is queued and will be delivered automatically.")
                        else:
                            st.success(f"Submitted! Ticket {a['id']} routed to {a['dept']} (ack {a['ack']}).")
                        st.markdown(card(a), unsafe_allow_html=True)
                        with st.expander("What was sent to the department's system (simulated connector)"):
                            st.caption(f"{L.DEPTS[a['dept']]['system']} - {L.DEPTS[a['dept']]['type']}")
                            st.code(a["payload"] or "Queued - not delivered yet", language="json" if "REST" in L.DEPTS[a["dept"]]["type"] else "xml")
                    elif msg == "duplicate":
                        st.warning(f"You already have an open request for this: {res['id']}. OneGov blocked the duplicate submission. Track it in 'My applications'.")
                    else:
                        st.error("Please tick the consent boxes so OneGov can fetch your verified data: " + ", ".join(res))

    # ---------- My applications ----------
    with tabs[1]:
        st.subheader(f"All your requests in one place ({len(mine)})")
        st.caption("Across every department - one tracking view, one ticket format.")
        if not mine:
            st.info("No requests yet. Use Home to search for a service.")
        for a in mine:
            st.markdown(card(a), unsafe_allow_html=True)
            with st.expander(f"Timeline {a['id']}"):
                timeline(a)

    # ---------- Notifications ----------
    with tabs[2]:
        st.subheader(f"Notifications ({len(events)})")
        label = {"application.created": "Request submitted", "application.routed": "Routed to department",
                 "status.changed": "Status update", "consent.granted": "Consent given", "consent.revoked": "Consent withdrawn",
                 "duplicate.blocked": "Duplicate prevented", "connector.failed": "Delivery delayed", "connector.retry_ok": "Delivered after retry"}
        if not events:
            st.info("Nothing yet.")
        for e in events[:20]:
            st.markdown(f'<div class="card"><b>{label.get(e["topic"], e["topic"])}</b> {esc(e["app_id"])}<br>'
                        f'<span class="small">{esc(e["detail"])} &bull; {fmt(e["time"])}</span></div>', unsafe_allow_html=True)

    # ---------- Profile & consent ----------
    with tabs[3]:
        st.subheader("Master profile")
        st.caption("Update once - every department sees the new data.")
        with st.form("edit_profile"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Full name", p["full_name"])
            father = c2.text_input("Father's / guardian's name", p["father_name"])
            mobile = c1.text_input("Mobile", p["mobile"])
            pin = c2.text_input("PIN code", p["pin"])
            address = st.text_input("Address", p["address"])
            go = st.form_submit_button("Save profile")
        if go:
            ok, issues = L.update_profile(store, email, {**p, "full_name": name, "father_name": father, "mobile": mobile.strip(),
                                                         "pin": pin.strip(), "address": address})
            if ok:
                st.success("Profile updated.")
            for i in issues:
                st.error(i)
        st.subheader("Consent manager")
        st.caption("You decide which data sources OneGov can use. Every change is logged.")
        for i, s_ in enumerate(L.ALL_SOURCES):
            c = user["consents"].get(s_, {})
            a_col, b_col = st.columns([4, 1])
            state = "✅ Allowed" if c.get("granted") else "⛔ Not allowed"
            a_col.markdown(f"**{s_}**  \n{state}" + (f" &bull; {fmt(c['time'])}" if c else ""))
            if c.get("granted"):
                if b_col.button("Revoke", key=f"rv{i}"):
                    L.revoke_consent(store, email, s_)
                    st.rerun()
            else:
                if b_col.button("Allow", key=f"gr{i}"):
                    L.grant_consent(store, email, s_)
                    st.rerun()


# ============================ OFFICER ============================
def officer_view():
    dept, me = ss.dept, ss.user
    apps = [a for a in store["apps"] if a["dept"] == dept and not a["queued"]]
    opn = [a for a in apps if a["status"] < 4]
    st.markdown(f"### 🏛️ {esc(dept)} - officer dashboard")
    info = L.DEPTS[dept]
    st.caption(f"Connected system: {info['system']} ({info['type']}, simulated) - status: " + ("🟢 healthy" if store["connectors"][dept]["up"] else "🔴 down"))
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Open requests", len(opn))
    k2.metric("Urgent (4-5)", sum(a["urgency"] >= 4 for a in opn))
    k3.metric("SLA overdue", sum(L.is_overdue(store, a) for a in opn))
    k4.metric("Resolved", sum(a["status"] == 4 for a in apps))
    t1, t2, t3 = st.tabs(["📥 Requests", "🧩 AI groups (solve in bulk)", "📊 Analytics"])

    with t1:
        flt = st.radio("Show", ["Open", "All"], horizontal=True)
        rows = sorted(opn if flt == "Open" else apps, key=lambda a: (-a["urgency"], L.due(store, a)))[:30]
        if not rows:
            st.info("No requests.")
        for a in rows:
            st.markdown(card(a, who=True), unsafe_allow_html=True)
            b1, b2, b3 = st.columns([4, 1.2, 1.2])
            with b1:
                with st.expander("Citizen data (only what was consented) and timeline"):
                    p = store["users"][a["citizen"]]["profile"]
                    st.markdown(f"**{p['full_name']}** &bull; {p['mobile']} &bull; {p['address']}  \nAadhaar: `{L.mask_aadhaar(p['aadhaar'])}` (masked)")
                    if a["sources"]:
                        st.markdown("Verified via consent: " + ", ".join(f"✅ {s_}" for s_ in a["sources"]))
                    if a["extras"]:
                        st.markdown("Details: " + ", ".join(f"{k}: {v}" for k, v in a["extras"].items()))
                    timeline(a)
            if a["status"] < 4:
                if b2.button("Advance ▶", key="adv_" + a["id"]):
                    L.set_status(store, a, a["status"] + 1, me)
                    st.rerun()
                if b3.button("Resolve ✔", key="res_" + a["id"]):
                    L.set_status(store, a, 4, me)
                    st.rerun()

    with t2:
        st.subheader("Similar complaints, grouped by AI")
        st.caption("Same problem, same area: solve once, close all. Saves the officer from handling each complaint separately.")
        groups = L.group_complaints(opn)
        multi = [g for g in groups if len(g) > 1]
        if not multi:
            st.info("No groups of similar complaints right now. " + (f"{len(groups)} single complaints are open." if groups else ""))
        for gi, g in enumerate(multi):
            gid = "|".join(a["id"] for a in g)
            svc = L.SERVICES[g[0]["service"]]
            st.markdown(f'<div class="card"><b>{svc["icon"]} {len(g)} similar complaints: {esc(svc["name"])}</b><br>'
                        f'<span class="small">{esc(L.group_summary(g))}</span></div>', unsafe_allow_html=True)
            with st.expander("Complaints in this group"):
                for a in g:
                    st.markdown(card(a, who=True), unsafe_allow_html=True)
            c1, c2, c3 = st.columns(3)
            if c1.button("✨ AI summary", key=f"sm{gi}"):
                txt, err = AI.summarize([a["text"] for a in g], svc["name"], api_key)
                ss.ai_err = err
                ss.gsum[gid] = txt or L.group_summary(g)
            if gid in ss.gsum:
                st.info(ss.gsum[gid])
            if c2.button(f"Advance all {len(g)} ▶", key=f"ga{gi}"):
                for a in g:
                    L.set_status(store, a, a["status"] + 1, me)
                L.audit(store, me, "officer", "group.bulk_update", f"{len(g)} complaints advanced together")
                st.rerun()
            if c3.button(f"Resolve all {len(g)} ✔", key=f"gr{gi}"):
                for a in g:
                    L.set_status(store, a, 4, me)
                L.audit(store, me, "officer", "group.bulk_resolve", f"{len(g)} complaints resolved together")
                st.rerun()

    with t3:
        if apps:
            df = pd.DataFrame(apps)
            df["stage"] = df.apply(lambda r: L.WORKFLOWS[r["kind"]][r["status"]], axis=1)
            c1, c2 = st.columns(2)
            c1.markdown("**Requests by service**")
            c1.bar_chart(df["service"].map(lambda k: L.SERVICES[k]["name"]).value_counts())
            c2.markdown("**Requests by stage**")
            c2.bar_chart(df["stage"].value_counts())
        else:
            st.info("No data yet.")


# ============================ ADMIN ============================
def admin_view():
    st.markdown("### 🛠️ Integration & monitoring console")
    apps = store["apps"]
    t = st.tabs(["📊 Monitoring", "🔌 Connectors", "⚙️ Workflow config", "📜 Audit log", "🧹 Data quality", "♻️ Demo controls"])

    with t[0]:
        total = len(apps)
        overdue = sum(L.is_overdue(store, a) for a in apps)
        up = sum(c["up"] for c in store["connectors"].values())
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total requests", total)
        c2.metric("Open", sum(a["status"] < 4 for a in apps))
        c3.metric("SLA compliance", f"{(100 * (total - overdue) // total) if total else 100}%")
        c4.metric("Connectors up", f"{up}/{len(store['connectors'])}")
        c5, c6, c7, c8 = st.columns(4)
        c5.metric("Duplicates blocked", store["stats"]["dup_blocked"])
        c6.metric("Fields auto-filled", store["stats"]["autofilled"])
        c7.metric("Queued (exceptions)", sum(a["queued"] for a in apps))
        c8.metric("Active consents", sum(1 for u in store["users"].values() for c in u["consents"].values() if c.get("granted")))
        df = pd.DataFrame(apps)
        a1, a2 = st.columns(2)
        a1.markdown("**Requests by department**")
        a1.bar_chart(df["dept"].value_counts())
        df["stage"] = df.apply(lambda r: L.WORKFLOWS[r["kind"]][r["status"]], axis=1)
        a2.markdown("**Unified status pipeline**")
        a2.bar_chart(df["stage"].value_counts())
        st.markdown("**Live event stream (event-driven notifications)**")
        ev = pd.DataFrame(sorted(store["events"], key=lambda e: e["time"], reverse=True)[:12])
        if not ev.empty:
            ev["time"] = ev["time"].map(fmt)
            st.dataframe(ev[["time", "topic", "app_id", "dept", "detail"]], hide_index=True)

    with t[1]:
        st.subheader("Department connectors (simulated adapters)")
        st.caption("Reusable adapters translate one common OneGov record into each department's format. No system needs to be replaced.")
        for d, info in L.DEPTS.items():
            queued = [a for a in apps if a["dept"] == d and a["queued"]]
            up_now = store["connectors"][d]["up"]
            c1, c2, c3 = st.columns([3, 2, 2])
            c1.markdown(f"**{d}**  \n{info['system']} &bull; {info['type']}")
            new = c2.checkbox("Simulate outage", value=not up_now, key="out_" + info["slug"])
            if new == up_now:
                store["connectors"][d]["up"] = not new
                L.audit(store, "admin", "admin", "connector.toggle", f"{d} {'DOWN' if new else 'UP'} (simulated)")
                st.rerun()
            c3.markdown("🟢 healthy" if up_now else "🔴 down")
            if queued:
                if c3.button(f"Retry {len(queued)} queued", key="retry_" + info["slug"]):
                    n = L.retry_queued(store, d, "admin")
                    st.success(f"Delivered {n} request(s).")
                    st.rerun()
            sample = next((a for a in reversed(apps) if a["dept"] == d and a["payload"]), None)
            if sample:
                with st.expander(f"Sample message sent to {d} ({sample['id']})"):
                    st.code(sample["payload"], language="json" if "REST" in info["type"] else "xml")

    with t[2]:
        st.subheader("Configurable workflow and SLA")
        st.caption("Change the SLA (days) per service - applies instantly, no code change.")
        for k, sv in L.SERVICES.items():
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"{sv['icon']} **{sv['name']}** - {sv['dept']}  \n<span class='small'>{' → '.join(L.WORKFLOWS[sv['kind']])}</span>", unsafe_allow_html=True)
            store["sla"][k] = c2.number_input("SLA days", 1, 60, store["sla"][k], key="sla_" + k, label_visibility="collapsed")

    with t[3]:
        st.subheader("Audit log")
        flt = st.text_input("Filter (actor, action or detail)")
        au = pd.DataFrame(sorted(store["audit"], key=lambda e: e["time"], reverse=True))
        if not au.empty:
            au["time"] = au["time"].map(fmt)
            if flt:
                au = au[au.apply(lambda r: flt.lower() in " ".join(map(str, r.values)).lower(), axis=1)]
            st.dataframe(au, hide_index=True)

    with t[4]:
        st.subheader("Data-quality checks on master records")
        rep = L.dq_report(store)
        st.metric("Issues found", len(rep))
        if rep:
            st.dataframe(pd.DataFrame(rep), hide_index=True)
        st.caption("Checks: name, mobile, Aadhaar, PIN, email, date of birth, duplicate identity.")

    with t[5]:
        st.warning("This resets all demo data for every visitor.")
        if st.button("Reset demo data"):
            store.clear()
            store.update(L.new_store())
            st.rerun()


{"citizen": citizen_view, "officer": officer_view, "admin": admin_view}[ss.role]()
