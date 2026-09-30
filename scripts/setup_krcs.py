# ============================================================
# KRCS Digital Transformation Platform
# Adds: Digital Story, News Item (+ News Resource Link child)
# Run: exec(open("/home/edison/frappe/redcross-bench/scripts/setup_krcs_stories_news.py").read(), globals())
# ============================================================

import frappe

MODULE = "Kenya Red Cross Digital Transformation Platform"

# ─────────────────────────────────────────────────────────────
# HELPERS (reuse pattern from main script)
# ─────────────────────────────────────────────────────────────
def log(msg):
    print(msg)

def _dt_exists(name):
    return frappe.db.exists("DocType", name)

def _field(label, fieldname, fieldtype, **kw):
    return {
        "fieldname": fieldname,
        "label": label,
        "fieldtype": fieldtype,
        "reqd": kw.get("reqd", 0),
        "unique": kw.get("unique", 0),
        "read_only": kw.get("read_only", 0),
        "in_list_view": kw.get("in_list_view", 0),
        "in_standard_filter": kw.get("in_standard_filter", 0),
        "in_global_search": kw.get("in_global_search", 0),
        "options": kw.get("options", ""),
        "default": kw.get("default", ""),
        "hidden": kw.get("hidden", 0),
        "no_copy": kw.get("no_copy", 0),
        "print_hide": kw.get("print_hide", 0),
        "search_index": kw.get("search_index", 0),
        "length": kw.get("length", 0),
    }

def _section(label, fieldname):
    return {"fieldname": fieldname, "fieldtype": "Section Break", "label": label}

def _column(label, fieldname):
    return {"fieldname": fieldname, "fieldtype": "Column Break", "label": label}

def _make_doctype(name, fields, **kwargs):
    if _dt_exists(name):
        log(f"ℹ️  DocType exists: {name}")
        return
    doc = {
        "doctype": "DocType",
        "name": name,
        "module": MODULE,
        "custom": 0,
        "is_submittable": 0,
        "issingle": 0,
        "istable": kwargs.get("istable", 0),
        "track_changes": 1,
        "allow_rename": 1,
        "autoname": kwargs.get("autoname", "hash"),
        "naming_rule": kwargs.get("naming_rule", "Expression (old style)"),
        "engine": "InnoDB",
        "fields": fields,
        "permissions": kwargs.get("permissions", [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1,
             "delete": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1},
        ]),
    }
    frappe.get_doc(doc).insert(ignore_permissions=True)
    log(f"✅ DocType created: {name}")


log("\n🏗️  Building stories & news doctypes...\n")

# ─────────────────────────────────────────────────────────────
# 1. CHILD: News Resource Link
# ─────────────────────────────────────────────────────────────
_make_doctype(
    "News Resource Link",
    fields=[
        _field("Label", "label", "Data", reqd=1, in_list_view=1),
        _field("URL", "url", "Data"),
    ],
    istable=1,
    autoname="hash",
    permissions=[],
)


# ─────────────────────────────────────────────────────────────
# 2. MAIN: Digital Story
# ─────────────────────────────────────────────────────────────
_make_doctype(
    "Digital Story",
    fields=[
        _section("Identity", "sb_identity"),
        _field("Story ID", "story_id", "Data",
               unique=1, in_list_view=1, in_global_search=1),
        _field("Slug", "slug", "Data",
               unique=1, in_list_view=1, in_global_search=1),
        _field("Title", "title", "Data",
               reqd=1, in_list_view=1, in_global_search=1),
        _field("Subtitle", "subtitle", "Small Text"),

        _column("Meta", "cb_meta"),
        _field("Date", "date", "Date", reqd=1, in_list_view=1),
        _field("Author", "author", "Data", in_list_view=1),
        _field("Author Role", "author_role", "Data"),
        _field("Tag", "tag", "Data", in_standard_filter=1),
        _field("Cover Image", "cover_image", "Attach Image"),

        _section("Narrative", "sb_narrative"),
        _field("Challenge", "challenge", "Text Editor"),
        _field("People", "people", "Text Editor"),
        _field("Solution", "solution", "Text Editor"),
        _field("Experience", "experience", "Text Editor"),
        _field("Learning", "learning", "Text Editor"),
        _field("Impact", "impact", "Text Editor"),

        _section("Safeguarding", "sb_safeguarding"),
        _field("Safeguarding Note", "safeguarding_note", "Text Editor"),
    ],
    autoname="field:story_id",
)


# ─────────────────────────────────────────────────────────────
# 3. MAIN: News Item
# ─────────────────────────────────────────────────────────────
_make_doctype(
    "News Item",
    fields=[
        _section("Identity", "sb_identity"),
        _field("News ID", "news_id", "Data",
               unique=1, in_list_view=1, in_global_search=1),
        _field("Slug", "slug", "Data",
               unique=1, in_list_view=1, in_global_search=1),
        _field("Title", "title", "Data",
               reqd=1, in_list_view=1, in_global_search=1),

        _column("Meta", "cb_meta"),
        _field("Date", "date", "Date", reqd=1, in_list_view=1),
        _field("Author", "author", "Data", in_list_view=1),
        _field("Department", "department", "Data",
               in_list_view=1, in_standard_filter=1),
        _field("Category", "category", "Select",
               options="Digital Projects\nInnovation\nPartnerships\nEvents\nPolicy",
               reqd=1, in_list_view=1, in_standard_filter=1),

        _section("Content", "sb_content"),
        _field("Summary", "summary", "Small Text", reqd=1),
        _field("Content", "content", "Text Editor", reqd=1),
        _field("Resources", "resources", "Table",
               options="News Resource Link"),
        _field("Image Alt", "image_alt", "Data"),
        _field("Cover Image", "cover_image", "Attach Image"),
    ],
    autoname="field:news_id",
)

frappe.db.commit()


# ─────────────────────────────────────────────────────────────
# 4. SEED: Digital Stories
# ─────────────────────────────────────────────────────────────
log("\n📖 Seeding Digital Stories...\n")

DIGITAL_STORIES = [
    {
        "story_id": "story-001",
        "slug": "mobile-data-collection-garissa",
        "title": "From Paper to Palm: Mobile Data Collection in Garissa",
        "subtitle": "How field volunteers in Garissa County replaced paper forms with smartphones — and transformed community health assessments overnight.",
        "date": "2026-08-12",
        "author": "Amina Hassan",
        "author_role": "Field Coordinator, Garissa County",
        "tag": "Health & Community",
        "challenge": "Field volunteers across Garissa County spent up to three days manually transcribing handwritten household assessment forms. Data errors were common, reports arrived late, and decision-makers had no real-time visibility into evolving health situations on the ground.",
        "people": "Fourteen community health volunteers — many of whom had never used a smartphone before — worked alongside two data officers and a digital transformation lead. Their collective experience of the old process drove the design of the new one.",
        "solution": "Using KoboToolbox integrated with the KRCS data platform, the team digitised the household assessment form into a mobile-friendly survey. Volunteers received two days of training on data entry, GPS tagging, and offline sync. The backend team built an automated validation pipeline that flagged anomalies before data reached the dashboard.",
        "experience": "\"The first week was the hardest,\" recalls volunteer Fatuma Yussuf. \"But by week two, I was finishing assessments in half the time and my supervisor could see my work the same day. That felt powerful.\" Data officers noted a dramatic drop in back-and-forth correction cycles.",
        "learning": "Device familiarity is the biggest barrier, not willingness. Short, hands-on training sessions work far better than manuals. Building an offline-first workflow was non-negotiable in low-connectivity areas.",
        "impact": "Data collection time dropped by 62%. Errors in the dataset fell from 18% to under 3% within the first quarter. County health authorities now receive weekly automated summaries instead of monthly paper reports.",
        "safeguarding_note": "All participant names used in this story are with explicit consent. Household-level data is anonymised before leaving the device.",
    },
    {
        "story_id": "story-002",
        "slug": "gis-flood-response-tana-river",
        "title": "Mapping the Flood: GIS-Driven Response in Tana River",
        "subtitle": "When floods struck Tana River County, a small GIS team turned satellite imagery and community data into life-saving evacuation maps in under 48 hours.",
        "date": "2026-07-03",
        "author": "Daniel Otieno",
        "author_role": "GIS Analyst, KRCS Digital Hub",
        "tag": "Disaster Response",
        "challenge": "The 2026 Tana River floods displaced over 12,000 people within 72 hours. Response teams had no up-to-date maps of affected areas, road accessibility, or population density at sub-location level. Decisions were being made on guesswork.",
        "people": "A three-person GIS team, working with national disaster response coordinators and county government liaisons, mobilised rapidly. Community scouts provided real-time ground-truth data via WhatsApp, which was integrated into the mapping workflow.",
        "solution": "The team used Sentinel-2 satellite imagery processed in Google Earth Engine to delineate flood extents. Community scout reports were geocoded and layered onto the map. The final product — a printable PDF atlas and a live web map — was shared with all response teams via a secure link.",
        "experience": "\"We were updating the map every six hours,\" says GIS analyst Peter Mwangi. \"When coordinators told us they were routing trucks based on our road-accessibility layer, we knew this was working.\" The speed and accuracy surprised even veteran responders.",
        "learning": "Pre-established community scout networks are as important as the technology. Satellite imagery without ground truth leads to errors. Keeping outputs simple — printable PDFs alongside live dashboards — ensures field teams with poor connectivity still benefit.",
        "impact": "Evacuation routes were optimised for 23 villages, reducing average travel time by 40%. Aid pre-positioning was based on the population-density layer, ensuring equitable distribution. Post-response debrief confirmed zero duplicate distributions in mapped areas.",
        "safeguarding_note": None,
    },
    {
        "story_id": "story-003",
        "slug": "digital-cash-transfer-kajiado",
        "title": "Cash in a Click: Dignified Digital Transfers in Kajiado",
        "subtitle": "Replacing manual cash distribution with mobile money in drought-affected Kajiado — and what it revealed about trust, dignity, and financial inclusion.",
        "date": "2026-06-18",
        "author": "Grace Wanjiru",
        "author_role": "Livelihoods Programme Officer",
        "tag": "Financial Inclusion",
        "challenge": "Beneficiaries in remote Kajiado sub-counties travelled up to 40 kilometres to collect cash assistance, often spending a significant portion of the transfer on transport. Manual distribution events also created safety concerns and required large logistics teams.",
        "people": "Programme officers worked closely with 340 beneficiary households, many of them elderly women, and partnered with a local mobile money agent network. Digital literacy sessions were co-designed with community elders to ensure cultural appropriateness.",
        "solution": "Beneficiaries were onboarded onto a mobile money platform using a simplified registration flow designed for low-literacy users. Transfers were disbursed directly to phones. A network of 12 local agents provided cash-out support within a 5km radius of each beneficiary.",
        "experience": "\"I used to fear the distribution day,\" says beneficiary Nasieku Tipis. \"Now the money comes to me. I decide when I collect it, I don't have to rush.\" Programme officers noted a significant shift in dignity — beneficiaries felt in control for the first time.",
        "learning": "Digital cash works only if the last-mile agent network is reliable. Building trust takes longer than building the system. Involving community elders early prevents adoption resistance. Mobile money literacy is a prerequisite, not an afterthought.",
        "impact": "Transport costs for beneficiaries dropped by an average of KES 800 per distribution cycle. Distribution time per 100 beneficiaries fell from 6 hours to under 45 minutes. 94% of beneficiaries successfully cashed out within 24 hours of transfer.",
        "safeguarding_note": "Beneficiary identities have been anonymised in published materials. Data is stored in compliance with KRCS data protection policy.",
    },
]

for s in DIGITAL_STORIES:
    if frappe.db.exists("Digital Story", s["story_id"]):
        log(f"   ℹ️  Story exists: {s['story_id']}")
        continue
    doc = frappe.get_doc({"doctype": "Digital Story", **s})
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    log(f"   ✅ Digital Story: {s['story_id']} — {s['title'][:50]}...")

frappe.db.commit()


# ─────────────────────────────────────────────────────────────
# 5. SEED: News Items
# ─────────────────────────────────────────────────────────────
log("\n📰 Seeding News Items...\n")

NEWS_ITEMS = [
    {
        "news_id": "news-001",
        "slug": "erm-system-launch-2026",
        "title": "KRCS Launches Integrated Emergency Response Management System",
        "date": "2026-09-10",
        "author": "Digital Transformation Unit",
        "department": "ICT & Digital Transformation",
        "category": "Digital Projects",
        "summary": "Kenya Red Cross Society officially launched its Integrated Emergency Response Management (IERM) system, consolidating incident reporting, resource tracking, and volunteer dispatch into a single platform for the first time.",
        "content": """After 18 months of development and piloting across five counties, the KRCS Integrated Emergency Response Management (IERM) system went live on 1 September 2026. The platform replaces a fragmented collection of spreadsheets, phone calls, and paper logs with a real-time dashboard accessible to response coordinators at national and county levels.

The IERM system integrates with the existing volunteer management database, allowing dispatchers to identify and mobilise nearby volunteers within minutes of an incident report. Resource inventories — vehicles, medical supplies, tents — are updated automatically as items are checked out.

"This is the infrastructure we have needed for a decade," said the Head of Emergency Response. "Now when we receive an alert, the system helps us ask the right questions: Who is closest? What do they need? Where are the gaps?"

The system was developed in partnership with the KRCS Digital Hub team and an open-source humanitarian technology consortium. All code will be contributed back to the humanitarian commons under a CC BY 4.0 licence.""",
        "resources": [
            {"label": "IERM System Overview (PDF)", "url": "#"},
            {"label": "User Guide for County Coordinators", "url": "#"},
        ],
        "image_alt": "IERM dashboard interface showing real-time incident map",
    },
    {
        "news_id": "news-002",
        "slug": "ai-health-surveillance-partnership",
        "title": "KRCS and University of Nairobi Partner on AI-Powered Disease Surveillance",
        "date": "2026-08-28",
        "author": "Programmes & Partnerships",
        "department": "Health Programmes",
        "category": "Partnerships",
        "summary": "A new partnership between KRCS and the University of Nairobi's School of Computing will develop machine-learning models to detect early signals of disease outbreaks from community health worker reports.",
        "content": """Kenya Red Cross Society and the University of Nairobi (UoN) School of Computing have signed a two-year Memorandum of Understanding to co-develop an AI-assisted disease surveillance tool for community-level health data.

The project — funded through a grant from a global health innovation fund — will train natural language processing (NLP) models on anonymised KRCS community health worker (CHW) report data. The models are designed to detect statistical anomalies that might indicate early-stage disease clustering, triggering alerts before a formal outbreak declaration.

"Community health workers are often the first to see something unusual," noted the Principal Investigator from UoN. "This tool gives them a way to surface that observation automatically, at scale."

The first phase will focus on respiratory and diarrhoeal disease signals in five high-density counties. A privacy-by-design framework — including differential privacy techniques — will govern all model training.

An open beta for county health officers is planned for Q1 2027.""",
        "resources": [
            {"label": "MoU Summary Document", "url": "#"},
            {"label": "Privacy Framework Overview", "url": "#"},
        ],
        "image_alt": "University of Nairobi and KRCS representatives at MoU signing",
    },
    {
        "news_id": "news-003",
        "slug": "digital-transformation-conference-2026",
        "title": "KRCS to Host East Africa Humanitarian Technology Conference in Nairobi",
        "date": "2026-08-05",
        "author": "Communications & Events",
        "department": "External Relations",
        "category": "Events",
        "summary": "Kenya Red Cross Society will host the 3rd East Africa Humanitarian Technology Conference on 14–15 November 2026, bringing together NGOs, government agencies, and tech companies to share innovations in humanitarian response.",
        "content": """Kenya Red Cross Society is proud to announce it will host the 3rd East Africa Humanitarian Technology Conference (EAHTC 2026) at the Kenyatta International Convention Centre, Nairobi, on 14–15 November 2026.

The conference theme — "From Pilot to Scale: Sustaining Digital Transformation in Humanitarian Work" — reflects the sector's growing need to move beyond proof-of-concept projects and embed technology into durable, funded operational systems.

Expected participants include delegates from 14 countries, representatives from UNHCR, WFP, OCHA, and the ICRC, as well as innovators from Kenya's technology ecosystem.

Key sessions will include:
- Responsible AI in field operations
- Community-led data governance
- Financing digital transformation at National Society level
- Open-source tools for humanitarian logistics

Speakers and the full programme will be announced in October. Early registration is open for National Society staff at a subsidised rate.

All sessions will be livestreamed and recordings made publicly available.""",
        "resources": [
            {"label": "Conference Website", "url": "#"},
            {"label": "Call for Abstracts", "url": "#"},
            {"label": "Subsidised Registration Form", "url": "#"},
        ],
        "image_alt": "Kenyatta International Convention Centre, Nairobi",
    },
]

for n in NEWS_ITEMS:
    if frappe.db.exists("News Item", n["news_id"]):
        log(f"   ℹ️  News exists: {n['news_id']}")
        continue
    doc = frappe.get_doc({"doctype": "News Item", **n})
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    log(f"   ✅ News Item: {n['news_id']} — {n['title'][:50]}...")

frappe.db.commit()


# ─────────────────────────────────────────────────────────────
# 6. SUMMARY
# ─────────────────────────────────────────────────────────────
log("\n" + "=" * 60)
log("🎉  STORIES + NEWS SETUP COMPLETE")
log("=" * 60)
log(f"Module          : {MODULE}")
log(f"Doctypes added  : Digital Story, News Item, News Resource Link")
log(f"Digital Stories : {len(DIGITAL_STORIES)}")
log(f"News Items      : {len(NEWS_ITEMS)}")
log("=" * 60)
log("")
