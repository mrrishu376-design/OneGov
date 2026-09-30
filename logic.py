"""OneGov core logic (no UI imports, so it can be tested on its own).

Covers: service catalogue, AI-style routing, master profile + data quality,
consent manager, connectors (REST / SOAP-XML / CSV adapters), workflow
orchestration, event log, audit log, duplicate prevention and complaint grouping.
All department systems are SIMULATED for the hackathon demo.
"""
import csv
import datetime as dt
import io
import random
import re
from xml.sax.saxutils import escape

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def now():
    return dt.datetime.now(IST)


OFFICER_PW, ADMIN = "Officer@2026", ("admin@gov.in", "Admin@2026")
DEMO_CITIZEN = ("ramesh.kumar@gov.in", "Citizen@2026")
WARDS = [f"Ward {i}" for i in range(1, 11)]

WORKFLOWS = {
    "complaint": ["Submitted", "Routed to department", "Assigned to officer", "In progress", "Resolved"],
    "application": ["Submitted", "Documents verified", "Under officer review", "Approved", "Issued"],
}

# ---------------- Departments and their (simulated) legacy / modern systems ----------------
DEPTS = {
    "Revenue Department": {"slug": "revenue", "system": "e-District portal", "type": "Legacy SOAP/XML"},
    "Water Board": {"slug": "water", "system": "Jal Seva portal", "type": "Modern REST/JSON"},
    "Electricity Board": {"slug": "electricity", "system": "Billing & CRM", "type": "Legacy CSV batch"},
    "Public Works Department": {"slug": "pwd", "system": "PWD grievance MIS", "type": "Modern REST/JSON"},
    "Police Department": {"slug": "police", "system": "Crime & complaint system", "type": "Legacy SOAP/XML"},
    "Transport Department": {"slug": "transport", "system": "Licence & vehicle system", "type": "Modern REST/JSON"},
    "Municipal Corporation": {"slug": "municipal", "system": "Nagar Seva portal", "type": "Modern REST/JSON"},
    "Food & Civil Supplies": {"slug": "food", "system": "PDS portal", "type": "Legacy CSV batch"},
    "District Administration": {"slug": "district", "system": "Public grievance portal", "type": "Modern REST/JSON"},
}

AADHAAR = "Aadhaar eKYC (UIDAI, simulated)"
S_INCOME = "Income records (Revenue Dept)"
S_CASTE = "Caste records (Revenue Dept)"
S_ADDR = "Address records (Revenue Dept)"
S_FAMILY = "Family records (Revenue Dept)"
S_LICENCE = "Licence records (Transport Dept)"
S_PROPERTY = "Property records (Municipal Corp)"
ALL_SOURCES = [AADHAAR, S_INCOME, S_CASTE, S_ADDR, S_FAMILY, S_LICENCE, S_PROPERTY]

SERVICES = {
    "water_supply": {"name": "Water supply problem", "icon": "💧", "dept": "Water Board", "kind": "complaint", "sla": 3,
                     "keywords": ["water", "paani", "pani", "tanker", "pipeline", "nal", "handpump", "hand pump", "पानी", "जल"],
                     "sources": [], "extras": []},
    "road_repair": {"name": "Road / pothole repair", "icon": "🛣️", "dept": "Public Works Department", "kind": "complaint", "sla": 7,
                    "keywords": ["road", "sadak", "pothole", "gadde", "bridge", "pul", "rasta", "सड़क", "गड्ढा"],
                    "sources": [], "extras": []},
    "electricity_complaint": {"name": "Electricity / power fault", "icon": "⚡", "dept": "Electricity Board", "kind": "complaint", "sla": 2,
                              "keywords": ["electricity", "bijli", "power", "taar", "transformer", "street light", "streetlight", "light", "बिजली"],
                              "sources": [], "extras": []},
    "police_complaint": {"name": "Police complaint", "icon": "🚓", "dept": "Police Department", "kind": "complaint", "sla": 3,
                         "keywords": ["police", "thana", "fir", "theft", "chori", "stolen", "robbery", "cheating", "fraud", "पुलिस", "चोरी"],
                         "sources": [], "extras": []},
    "criminal_activity": {"name": "Report criminal activity", "icon": "🚨", "dept": "Police Department", "kind": "complaint", "sla": 1,
                          "keywords": ["criminal", "crime", "gunda", "drugs", "nasha", "violence", "suspicious", "illegal", "weapon",
                                       "hathiyar", "harassment", "maar peet", "fight", "अपराध"],
                          "sources": [], "extras": []},
    "sanitation": {"name": "Garbage / drainage", "icon": "🗑️", "dept": "Municipal Corporation", "kind": "complaint", "sla": 5,
                   "keywords": ["garbage", "kooda", "kachra", "naali", "drain", "sewage", "gandagi", "badbu", "safai", "कचरा", "नाली"],
                   "sources": [], "extras": []},
    "income_certificate": {"name": "Income certificate", "icon": "📄", "dept": "Revenue Department", "kind": "application", "sla": 10,
                           "keywords": ["income", "aay", "aamdani", "income certificate", "आय"],
                           "sources": [AADHAAR, S_INCOME], "extras": [("Purpose", ["Scholarship", "Job / exam", "Loan", "Other"])]},
    "caste_certificate": {"name": "Caste certificate", "icon": "📄", "dept": "Revenue Department", "kind": "application", "sla": 12,
                          "keywords": ["caste", "jati", "jaati", "obc", "caste certificate", "जाति"],
                          "sources": [AADHAAR, S_CASTE], "extras": [("Purpose", ["Education", "Job / exam", "Other"])]},
    "residence_certificate": {"name": "Residence certificate", "icon": "🏠", "dept": "Revenue Department", "kind": "application", "sla": 8,
                              "keywords": ["residence", "residential", "niwas", "nivas", "domicile", "address proof", "निवास"],
                              "sources": [AADHAAR, S_ADDR], "extras": [("Purpose", ["School / college", "Job / exam", "Other"])]},
    "driving_licence": {"name": "Driving licence", "icon": "🪪", "dept": "Transport Department", "kind": "application", "sla": 15,
                        "keywords": ["license", "licence", "driving", "dl", "driving licence", "लाइसेंस"],
                        "sources": [AADHAAR, S_LICENCE],
                        "extras": [("Licence type", ["Learner's licence", "Permanent licence (new)", "Renewal"])]},
    "ration_card": {"name": "Ration card", "icon": "🍚", "dept": "Food & Civil Supplies", "kind": "application", "sla": 12,
                    "keywords": ["ration", "pds", "rashan", "ration card", "राशन"],
                    "sources": [AADHAAR, S_FAMILY], "extras": [("Card type", ["New", "Add family member", "Correction"])]},
    "birth_certificate": {"name": "Birth certificate", "icon": "👶", "dept": "Municipal Corporation", "kind": "application", "sla": 7,
                          "keywords": ["birth", "janm", "birth certificate", "जन्म"],
                          "sources": [AADHAAR], "extras": [("Child's name", None), ("Child's date of birth", None)]},
    "new_water_connection": {"name": "New water connection", "icon": "🚰", "dept": "Water Board", "kind": "application", "sla": 14,
                             "keywords": ["water connection", "new water connection", "nal connection", "pipeline connection"],
                             "sources": [AADHAAR, S_PROPERTY], "extras": [("Connection type", ["Domestic", "Commercial"])]},
    "new_electricity_connection": {"name": "New electricity connection", "icon": "🔌", "dept": "Electricity Board", "kind": "application",
                                   "sla": 14, "keywords": ["electricity connection", "bijli connection", "new meter", "meter", "new connection"],
                                   "sources": [AADHAAR, S_PROPERTY], "extras": [("Load type", ["Domestic", "Commercial", "Agriculture"])]},
    "general_grievance": {"name": "Other / general grievance", "icon": "📝", "dept": "District Administration", "kind": "complaint",
                          "sla": 10, "keywords": [], "sources": [], "extras": []},
}

QUICK = ["water_supply", "road_repair", "electricity_complaint", "police_complaint",
         "income_certificate", "caste_certificate", "residence_certificate", "driving_licence"]
URGENT_WORDS = ["danger", "accident", "fire", "weapon", "hathiyar", "injur", "emergency", "gun", "death", "live wire",
                "khatra", "haadsa", "sparking", "latak", "days"]
STOP = set("the a an is are was of in on at to for and or my our not no hai hain ka ki ke se mein me par nahi ho raha rahi "
           "rha hamare mere yaha here there it this that with from have has been since near very".split())


# ---------------- Routing ----------------
def route_keywords(query):
    q = " " + re.sub(r"[^\w\u0900-\u097F ]", " ", query.lower()) + " "
    scores = {}
    for key, svc in SERVICES.items():
        sc = 0
        for kw in svc["keywords"]:
            if (" " + kw + " ") in q or (len(kw) >= 5 and kw in q):
                sc += 1 + len(kw.split())
        if sc:
            scores[key] = sc
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    return ranked or [("general_grievance", 0)]


def urgency_for(service_key, text):
    svc = SERVICES[service_key]
    if svc["kind"] == "application":
        return 2
    base = {"criminal_activity": 4, "police_complaint": 3, "electricity_complaint": 3, "water_supply": 3}.get(service_key, 2)
    t = text.lower()
    if any(w in t for w in URGENT_WORDS):
        base += 1
    return min(5, base)


# ---------------- Profile, validation, masking ----------------
PROFILE_FIELDS = ["full_name", "father_name", "dob", "gender", "mobile", "email", "aadhaar", "address", "ward", "pin",
                  "district", "category", "occupation", "income"]
NEEDED = {"complaint": ["full_name", "mobile", "address", "ward"],
          "application": ["full_name", "father_name", "dob", "mobile", "address", "aadhaar", "pin", "district"]}


def mask_aadhaar(a):
    a = re.sub(r"\D", "", a or "")
    return "XXXX XXXX " + a[-4:] if len(a) >= 4 else "XXXX XXXX XXXX"


def validate_profile(p):
    issues = []
    if len((p.get("full_name") or "").strip()) < 3:
        issues.append("Name is too short")
    if not re.fullmatch(r"[6-9]\d{9}", p.get("mobile", "") or ""):
        issues.append("Mobile must be 10 digits starting with 6-9")
    if not re.fullmatch(r"\d{12}", p.get("aadhaar", "") or ""):
        issues.append("Aadhaar must be 12 digits")
    if not re.fullmatch(r"\d{6}", p.get("pin", "") or ""):
        issues.append("PIN code must be 6 digits")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", p.get("email", "") or ""):
        issues.append("Email looks invalid")
    try:
        dt.date.fromisoformat(p.get("dob", ""))
    except Exception:  # noqa: BLE001
        issues.append("Date of birth must be YYYY-MM-DD")
    if not (p.get("address") or "").strip():
        issues.append("Address is required")
    return issues


# ---------------- Store, audit, events ----------------
def audit(store, actor, role, action, detail=""):
    store["audit"].append({"time": now(), "actor": actor, "role": role, "action": action, "detail": detail})


def event(store, topic, app=None, citizen=None, dept=None, detail=""):
    store["events"].append({"time": now(), "topic": topic, "app_id": app["id"] if app else "",
                            "citizen": citizen or (app["citizen"] if app else ""),
                            "dept": dept or (app["dept"] if app else ""), "detail": detail})


def create_user(store, profile, password):
    issues = validate_profile(profile)
    email = profile["email"].strip().lower()
    if email in store["users"]:
        issues.append("This email is already registered")
    if len(password) < 6:
        issues.append("Password must be at least 6 characters")
    if issues:
        return False, issues
    profile["email"] = email
    store["users"][email] = {"password": password, "profile": profile, "consents": {}}
    audit(store, email, "citizen", "profile.created", "Master profile created (single sign-on identity)")
    return True, []


def update_profile(store, email, profile):
    issues = validate_profile(profile)
    if issues:
        return False, issues
    store["users"][email]["profile"].update(profile)
    audit(store, email, "citizen", "profile.updated", "Master profile updated once; all departments see the new data")
    return True, []


def has_consent(store, email, source):
    return bool(store["users"][email]["consents"].get(source, {}).get("granted"))


def grant_consent(store, email, source, actor=None):
    store["users"][email]["consents"][source] = {"granted": True, "time": now()}
    audit(store, actor or email, "citizen", "consent.granted", source)
    event(store, "consent.granted", citizen=email, detail=source)


def revoke_consent(store, email, source):
    store["users"][email]["consents"][source] = {"granted": False, "time": now()}
    audit(store, email, "citizen", "consent.revoked", source)
    event(store, "consent.revoked", citizen=email, detail=source)


# ---------------- Connectors (simulated adapters to legacy / modern systems) ----------------
def canonical(app, user):
    p = user["profile"]
    return {"applicationId": app["id"], "serviceCode": app["service"], "serviceName": SERVICES[app["service"]]["name"],
            "department": app["dept"], "kind": app["kind"], "priority": app["urgency"],
            "citizen": {"name": p["full_name"], "dob": p["dob"], "mobile": p["mobile"], "address": p["address"],
                        "ward": app["ward"], "aadhaarRef": mask_aadhaar(p["aadhaar"])},
            "description": app["text"], "extras": app["extras"], "consentedSources": app["sources"],
            "submittedAt": app["created"].isoformat(timespec="seconds")}


def _flat(d, prefix=""):
    out = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(_flat(v, key + "."))
        else:
            out[key] = "; ".join(map(str, v)) if isinstance(v, (list, tuple)) else v
    return out


def to_payload(conn_type, canon):
    if conn_type.startswith("Modern"):
        import json
        return json.dumps(canon, indent=2, ensure_ascii=False)
    flat = _flat(canon)
    if "SOAP" in conn_type:
        body = "".join(f"    <{k.replace('.', '_')}>{escape(str(v))}</{k.replace('.', '_')}>\n" for k, v in flat.items())
        return ('<soap:Envelope>\n  <soap:Body>\n   <SubmitRequest>\n' + body +
                '   </SubmitRequest>\n  </soap:Body>\n</soap:Envelope>')
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(flat.keys())
    w.writerow(flat.values())
    return buf.getvalue()


def submit_to_connector(store, app):
    info = DEPTS[app["dept"]]
    if not store["connectors"][app["dept"]]["up"]:
        return False, "", "503 Service Unavailable (simulated outage)"
    payload = to_payload(info["type"], canonical(app, store["users"][app["citizen"]]))
    ack = f"{info['slug'].upper()}-ACK-{random.randint(1000, 9999)}"
    return True, payload, ack


# ---------------- Applications / workflow ----------------
def due(store, app):
    return app["created"] + dt.timedelta(days=store["sla"][app["service"]])


def is_overdue(store, app):
    return app["status"] < 4 and now() > due(store, app)


def _tokens(text):
    return {w for w in re.findall(r"[\w\u0900-\u097F]+", text.lower()) if w not in STOP and len(w) > 2}


def jaccard(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def log(app, text):
    app["history"].append((now(), text))


def create_application(store, email, service_key, text, ward, extras=None, granted=None,
                       has_photo=False, created=None, status=None, silent_dup=False):
    svc, user = SERVICES[service_key], store["users"][email]
    granted = granted or []
    missing = [s for s in svc["sources"] if not has_consent(store, email, s) and s not in granted]
    if missing:
        return False, "consent_missing", missing
    for s in granted:
        if s in svc["sources"] and not has_consent(store, email, s):
            grant_consent(store, email, s)
    for a in store["apps"]:
        if a["citizen"] == email and a["service"] == service_key and a["status"] < 4:
            if svc["kind"] == "application" or jaccard(a["text"], text) >= 0.7:
                if not silent_dup:
                    store["stats"]["dup_blocked"] += 1
                    audit(store, email, "citizen", "duplicate.blocked", f"{service_key} already open as {a['id']}")
                    event(store, "duplicate.blocked", a, detail="Duplicate submission prevented")
                return False, "duplicate", a
    store["seq"] += 1
    app = {"id": f"OG-{store['seq']}", "citizen": email, "service": service_key, "dept": svc["dept"], "kind": svc["kind"],
           "text": text.strip() or svc["name"], "ward": ward, "extras": extras or {}, "sources": list(svc["sources"]),
           "urgency": urgency_for(service_key, text), "status": 0, "created": created or now(), "history": [],
           "queued": False, "payload": "", "ack": "", "has_photo": has_photo}
    log(app, "Submitted by citizen")
    n = len([f for f in NEEDED[svc["kind"]] if user["profile"].get(f)])
    store["stats"]["autofilled"] += n
    log(app, f"{n} fields auto-filled from master profile (no re-typing)")
    store["apps"].append(app)
    audit(store, email, "citizen", "application.created", f"{app['id']} {svc['name']} -> {app['dept']}")
    event(store, "application.created", app, detail=svc["name"])
    deliver(store, app)
    if status is not None and app["status"] < status:
        app["status"] = status
        log(app, f"Status: {WORKFLOWS[app['kind']][status]}")
    return True, "ok", app


def deliver(store, app):
    ok, payload, ack = submit_to_connector(store, app)
    if ok:
        app.update(queued=False, payload=payload, ack=ack, status=max(app["status"], 1))
        log(app, f"Routed to {app['dept']} via {DEPTS[app['dept']]['type']} connector ({ack})")
        event(store, "application.routed", app, detail=ack)
    else:
        app["queued"] = True
        log(app, f"Queued for retry: {ack}")
        audit(store, "connector", "system", "connector.failed", f"{app['id']} -> {app['dept']}: {ack}")
        event(store, "connector.failed", app, detail=ack)
    return ok


def retry_queued(store, dept, actor):
    done = 0
    for a in store["apps"]:
        if a["dept"] == dept and a["queued"] and deliver(store, a):
            done += 1
            audit(store, actor, "admin", "connector.retry_ok", a["id"])
            event(store, "connector.retry_ok", a, detail="Delivered after retry")
    return done


def set_status(store, app, new, actor, role="officer"):
    new = max(0, min(4, new))
    if new == app["status"]:
        return
    app["status"] = new
    step = WORKFLOWS[app["kind"]][new]
    log(app, f"Status: {step} (by {actor})")
    audit(store, actor, role, "status.changed", f"{app['id']} -> {step}")
    event(store, "status.changed", app, detail=step)


# ---------------- AI grouping of similar complaints ----------------
def group_complaints(apps):
    """Group open complaints of the same service that are in the same ward or describe the same thing."""
    apps = [a for a in apps if a["kind"] == "complaint" and a["status"] < 4]
    parent = list(range(len(apps)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(apps)):
        for j in range(i + 1, len(apps)):
            a, b = apps[i], apps[j]
            if a["service"] == b["service"] and (a["ward"] == b["ward"] or jaccard(a["text"], b["text"]) >= 0.3):
                parent[find(i)] = find(j)
    groups = {}
    for i, a in enumerate(apps):
        groups.setdefault(find(i), []).append(a)
    return sorted(groups.values(), key=lambda g: (-len(g), -max(x["urgency"] for x in g)))


def group_summary(group):
    svc = SERVICES[group[0]["service"]]["name"]
    wards = ", ".join(sorted({a["ward"] for a in group}))
    return f"{len(group)} citizens report '{svc}' in {wards}. Highest urgency {max(a['urgency'] for a in group)}/5. Solve once, close all."


# ---------------- Data quality ----------------
def dq_report(store):
    rows, seen = [], {}
    for email, u in store["users"].items():
        for issue in validate_profile(u["profile"]):
            rows.append({"citizen": email, "issue": issue})
        seen.setdefault(u["profile"].get("aadhaar", ""), []).append(email)
    for a, emails in seen.items():
        if a and len(emails) > 1:
            rows.append({"citizen": ", ".join(emails), "issue": f"Same Aadhaar ({mask_aadhaar(a)}) on {len(emails)} profiles - possible duplicate identity"})
    return rows


# ---------------- Seed data ----------------
def _profile(name, email, father, mobile, aadhaar, ward, dob="1995-04-12", income="180000", cat="OBC", occ="Self-employed"):
    return {"full_name": name, "father_name": father, "dob": dob, "gender": "Male" if name.split()[0] not in ("Sunita", "Pooja", "Meena") else "Female",
            "mobile": mobile, "email": email, "aadhaar": aadhaar, "address": f"House 12, Main Road, {ward}", "ward": ward,
            "pin": "800001", "district": "Patna", "category": cat, "occupation": occ, "income": income}


def new_store():
    store = {"users": {}, "officers": {}, "apps": [], "audit": [], "events": [], "connectors": {},
             "stats": {"dup_blocked": 0, "autofilled": 0}, "sla": {k: v["sla"] for k, v in SERVICES.items()}, "seq": 2800}
    for d, info in DEPTS.items():
        store["connectors"][d] = {"up": True}
        store["officers"][f"{info['slug']}.officer@gov.in"] = {"password": OFFICER_PW, "name": f"{d} Officer", "dept": d}
    people = [
        (DEMO_CITIZEN[0], "Ramesh Kumar", "Mohan Kumar", "9876501234", "234567890123", "Ward 7"),
        ("sunita@example.in", "Sunita Devi", "Raj Kishore", "9876501235", "345678901234", "Ward 7"),
        ("amit@example.in", "Amit Singh", "Ravi Singh", "9876501236", "456789012345", "Ward 7"),
        ("pooja@example.in", "Pooja Kumari", "Sanjay Prasad", "9876501237", "567890123456", "Ward 3"),
        ("rahul@example.in", "Rahul Verma", "Dinesh Verma", "98765", "678901234567", "Ward 3"),
        ("meena@example.in", "Meena Yadav", "Bhola Yadav", "9876501239", "234567890123", "Ward 4"),
        ("vikash@example.in", "Vikash Kumar", "Ajay Kumar", "9876501240", "789012345678", "Ward 5"),
    ]
    for email, name, father, mob, aad, ward in people:
        store["users"][email] = {"password": DEMO_CITIZEN[1], "consents": {},
                                 "profile": _profile(name, email, father, mob, aad, ward)}
    H = lambda h: now() - dt.timedelta(hours=h)  # noqa: E731
    seed = [
        (DEMO_CITIZEN[0], "income_certificate", "Income certificate for scholarship", "Ward 7", {"Purpose": "Scholarship"}, [AADHAAR, S_INCOME], 30, 2),
        (DEMO_CITIZEN[0], "road_repair", "Big pothole near our lane causing accidents", "Ward 7", {}, [], 20, 1),
        ("sunita@example.in", "water_supply", "Paani 4 din se band hai, tanker bhi nahi aa raha", "Ward 7", {}, [], 100, 1),
        ("amit@example.in", "water_supply", "No water supply for 3 days, tanker not coming", "Ward 7", {}, [], 40, 1),
        ("meena@example.in", "water_supply", "Water pipeline leaking and no water in the morning", "Ward 7", {}, [], 8, 0),
        ("pooja@example.in", "road_repair", "Sadak par bade gadde hain, bike slip ho rahi hai", "Ward 3", {}, [], 70, 1),
        ("rahul@example.in", "road_repair", "Big potholes on main road near school, dangerous", "Ward 3", {}, [], 60, 1),
        ("vikash@example.in", "criminal_activity", "Suspicious people selling drugs near the school gate", "Ward 5", {}, [], 6, 0),
        ("sunita@example.in", "police_complaint", "Mobile phone stolen near market, want to file FIR", "Ward 2", {}, [], 12, 1),
        ("meena@example.in", "sanitation", "Garbage not collected for 10 days, bad smell", "Ward 4", {}, [], 150, 1),
        ("pooja@example.in", "sanitation", "Kooda nahi uthaya gaya, naali ka paani bhi beh raha hai", "Ward 4", {}, [], 30, 2),
        ("amit@example.in", "electricity_complaint", "Bijli ka taar latak raha hai, kabhi bhi haadsa ho sakta hai", "Ward 4", {}, [], 5, 1),
        ("vikash@example.in", "caste_certificate", "Caste certificate for exam form", "Ward 5", {"Purpose": "Job / exam"}, [AADHAAR, S_CASTE], 25, 1),
        ("rahul@example.in", "driving_licence", "Learner's licence", "Ward 3", {"Licence type": "Learner's licence"}, [AADHAAR, S_LICENCE], 15, 0),
        ("meena@example.in", "ration_card", "Add family member", "Ward 4", {"Card type": "Add family member"}, [AADHAAR, S_FAMILY], 200, 3),
    ]
    for email, key, text, ward, extras, srcs, hours, status in seed:
        create_application(store, email, key, text, ward, extras, srcs, created=H(hours), status=status, silent_dup=True)
    store["stats"] = {"dup_blocked": 0, "autofilled": store["stats"]["autofilled"]}
    store["audit"], store["events"] = store["audit"][-40:], store["events"][-40:]
    return store
