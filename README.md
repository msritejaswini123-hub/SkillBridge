# SkillBridge

**Academia–Industry Collaboration Portal for Skill Mapping, Internships and Placements**

A working full-stack prototype: a student uploads a resume PDF, SkillBridge extracts their
skills, combines them with qualification, preferred location and expected stipend, and
recommends internships with a **transparent match score that explains itself**. Companies get
ranked candidates. Colleges get real skill-gap data.

> In a hurry? Read **`HOW_TO_RUN.txt`** — same instructions, single-line commands, no jargon.

---

## 1. Problem statement

Three groups all hold half a picture and never see each other's:

- **Students** don't know which internships they are actually competitive for, or which single
  missing skill is costing them interviews.
- **Companies** receive hundreds of unranked resumes and cannot tell at a glance who fits.
- **Colleges** teach a curriculum without a live signal of what industry is currently hiring
  for, so gaps such as Docker, Linux or Cloud go unnoticed for years.

The core need: turn an unstructured resume into a structured skill profile, and use it to
connect all three sides with explainable matching.

## 2. Proposed solution

A single Flask portal with three roles sharing one SQLite database:

```
Resume PDF ──▶ text extraction ──▶ skill dictionary ──▶ student skill profile
                                                              │
                    qualification + location + stipend ───────┤
                                                              ▼
                                            weighted scoring engine (explainable)
                                                              │
                    ┌─────────────────────────────────────────┼──────────────────────────┐
                    ▼                                         ▼                          ▼
          STUDENT: ranked internships            COMPANY: ranked candidates    ACADEMIA: demand
          + matched/missing skills               + why each one matched        vs supply + gaps
          + courses to close the gap
```

Everything the three roles do writes to the same tables, so the academia dashboard is a live
aggregate of real student and company activity — not a static mock-up.

## 3. Main features

**Student**
- Register / login, build a profile (qualification, branch, graduation year, college, phone)
- Set preferred location, minimum and maximum expected stipend, experience, projects
- Upload a resume PDF → text extracted → skills detected → **review and edit before saving**
- Ranked internship recommendations with a match percentage
- Per-internship matched skills, missing skills and a score breakdown that adds up
- Skill-gap report ordered by demand, with free courses for each missing skill
- Filter and search internships; save for later; apply; track application status

**Industry / Company**
- Register / login, company profile
- Post internships: title, description, domain, location, stipend range, duration,
  required qualification, required skills, preferred skills, openings
- **Recommended candidates ranked by match score, with the reason shown** (matched ✓ /
  missing ✗ skills per student)
- Review applications, filter by status, move a candidate through
  Applied → Under Review → Shortlisted → Selected / Rejected
- Most-requested-skills view across your own postings; close and reopen postings

**Academia / College**
- Industry skill demand (share of active internships asking for each skill)
- Student skill availability side by side, as a grouped bar chart **and** a table
- Biggest gaps flagged Critical / High / Medium with an icon and a word (never colour alone)
- Common student skill gaps taken from real matching output (`skill_gaps` table)
- Popular domains, stipend averages, location spread
- Placement funnel (registered → skill profile → applied → shortlisted → selected) and
  branch-wise participation

## 4. Architecture

```
Browser (HTML5 / CSS3 / vanilla JS)
        │  form posts and GET query strings
        ▼
Flask routes (app.py)  ── sessions, @role_required, input validation, upload checks
        │
        ├──▶ resume_parser.py   PDF → text → skills / degree / branch / experience
        ├──▶ recommendation.py  the weighted scoring engine + skill-gap writer
        │        └──▶ ml/model.py   optional logistic-regression re-ranking layer
        ├──▶ analytics.py       SQL aggregates for the academia dashboard
        └──▶ database.py        connections, schema, parameterised query helpers
                    │
                    ▼
             SQLite (database/portal.db)
        │
        ▼
Jinja2 templates (base.html + dash_base.html + _macros.html)
```

One module, one job. `app.py` holds no SQL strings beyond its route logic, no scoring maths
lives in the templates, and the templates share reusable macros for cards, badges, meters,
the breakdown table and the chart.

## 5. Technology stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | HTML5, CSS3, vanilla JavaScript | No build step; readable by a beginner |
| Templating | Jinja2 (ships with Flask) | `base.html` inheritance + macros |
| Backend | Python 3.9+ / Flask 3 | Minimal, standard, easy to explain |
| Database | SQLite 3 (`sqlite3` stdlib) | Single file, zero setup |
| PDF text | `pypdf` | Pure Python, no system dependency |
| ML (optional) | `scikit-learn` logistic regression | Small, interpretable coefficients |
| Passwords | `werkzeug.security` PBKDF2 hashing | Bundled with Flask |

No React, no Node, no MongoDB, no Django. Charts are plain `div`s styled with CSS — no chart
library and no CDN, so the whole app works offline.

## 6. Database design

12 tables, all with primary keys and foreign keys (`PRAGMA foreign_keys = ON` on every
connection). Schema lives in `database.py`.

| Table | Holds | Key relationships |
|---|---|---|
| `users` | one row per login: name, email (unique), password hash, role | parent of the three role tables |
| `student_profiles` | qualification, branch, graduation year, location, stipend range, experience, projects, resume text | `user_id` → users |
| `companies` | company name, industry, website, location, about | `user_id` → users |
| `academia` | college name, department, contact | `user_id` → users |
| `skills` | canonical skill name (unique, case-insensitive) + category | referenced by 4 tables |
| `student_skills` | which student has which skill, and whether it came from the resume or was typed | → student_profiles, skills |
| `internships` | title, description, domain, location, stipend range, duration, qualification, openings, `is_demo` | `company_id` → companies |
| `internship_skills` | required vs preferred skills per internship | → internships, skills |
| `applications` | status + the match score at the moment of applying | → internships, student_profiles |
| `saved_internships` | bookmarks | → student_profiles, internships |
| `courses` | learning resources per skill | `skill_id` → skills |
| `skill_gaps` | cached per-student gap analysis, refreshed on every recommendation run | → student_profiles, skills |

Design notes worth knowing:

- **Every** query uses `?` placeholders. There is no f-string SQL anywhere in the project.
- `UNIQUE (internship_id, student_id)` on `applications` makes a double-apply impossible at
  the database level, not just in the UI.
- `skills.name` is `COLLATE NOCASE` + unique, so "python" and "Python" can never both exist.
- `skill_gaps` is a genuine cache of engine output: the student's Skill Gap page writes it and
  the academia dashboard aggregates it, which is how college-level insight is derived from
  real matching activity.
- Indexes cover the joins that run on every page (`student_skills.student_id`,
  `internship_skills.internship_id`, `applications.student_id`, …).

## 7. Recommendation algorithm

The heart of the project, in `recommendation.py`. Deliberately a **transparent weighted sum**,
because a student must be able to see why they scored what they scored.

```
match % = 50% × skills
        + 20% × qualification
        + 15% × location
        + 10% × stipend
        +  5% × experience & projects
```

Each factor returns a 0–1 sub-score **and a sentence explaining itself**:

| Factor | Weight | How it is computed |
|---|---|---|
| **Skills** | 50% | `(matched required + ½ × matched preferred) ÷ (all required + ½ × all preferred)`. A preferred skill is worth half a required one. No skills listed → neutral 0.6 rather than 0 or 100. |
| **Qualification** | 20% | Degree is 65% of this factor, branch 35%. "Any Degree" / "Any Branch" scores full marks. B.Tech ≈ B.E, MCA ≈ M.Sc are accepted equivalents. Floored at 0.2 — companies do flex. |
| **Location** | 15% | Exact city or a Remote posting = 1.0. Same metro cluster (Mumbai/Pune, Delhi/Noida/Gurgaon, …) = 0.85. Different city = 0.25. Student wants Remote but the role is on-site = 0.3. |
| **Stipend** | 10% | Offer ≥ your minimum = 1.0 (including offers above your maximum). Below it, the score is the ratio: ₹8,000 against a ₹10,000 minimum = 0.8. Not disclosed = 0.4. |
| **Experience & projects** | 5% | 40% prior experience (6 months = full marks) + 60% project relevance (do your projects mention the skills or domain asked for?). |

### Worked example (real output from the seeded demo)

Rahul Verma — B.Tech CSE, Hyderabad, expects ₹10,000–20,000, 3 months experience, projects
mentioning Flask and SQLite — against **Flask Web Intern** (Hyderabad, ₹16,000, requires
Python, Flask, HTML, CSS, SQLite; prefers JavaScript, Git):

| Factor | Weight | Sub-score | Points | Why |
|---|---|---|---|---|
| Skill match | 50% | 92% | 45.8 | 5 of 5 required matched |
| Qualification | 20% | 100% | 20.0 | Degree matches (B.Tech), branch matches (CSE) |
| Location | 15% | 100% | 15.0 | Location matches (Hyderabad) |
| Stipend | 10% | 100% | 10.0 | Pays ₹16,000/month — inside your range |
| Experience & projects | 5% | 80% | 4.0 | 3 months experience; projects mention Python, Flask, SQLite |
| **Total** | **100%** | | **94.8** | **displayed as 95%** |

The breakdown table on every internship page is generated from the same numbers, so **the
percentage always equals the sum of the rows**. There is a unit test asserting exactly that
(`test_breakdown_adds_up_to_the_displayed_score`).

### Candidate ranking (the company side)

The same function scores every student against one internship. For the demo
*Python Developer Intern* (requires Python, SQL, Flask, Git):

```
94%  Rahul Verma    CSE   missing: —
82%  Priya Sharma   IT    missing: Flask
70%  Arjun Reddy    ECE   missing: Flask
67%  Sneha Iyer     CSE   missing: Flask
44%  Ananya Gupta   IT    missing: Flask, Python, SQL
```

These are computed at request time, not stored — change a student's skills and the ranking
changes.

## 8. Resume processing

`resume_parser.py`, in four steps:

1. **Validate** — the extension must be `.pdf` *and* the bytes must start with `%PDF-`, so a
   renamed `.txt` is rejected before parsing.
2. **Extract** — `pypdf` reads the text of every page. Encrypted, empty and image-only
   (scanned) PDFs each produce a specific, friendly error instead of a stack trace.
3. **Match** — the text is matched against a dictionary of **89 canonical skills** with their
   real-world spelling variants. `sklearn` → **Scikit-learn**, `HTML5` → **HTML**,
   `nodejs` → **Node.js**, `power-bi` → **Power BI**.
4. **Pull structure** — degree, branch, months of experience and the PROJECTS section.

### The matching is stricter than it looks

Naive keyword matching produces embarrassing false positives. Three guards, each with a test:

- **Word boundaries that respect `+` and `#`** — `C` does not match inside "CSE" or "C++",
  but `C++` matches itself.
- **1–2 character skills must be capitalised** — so the English verb "go" is never read as
  the Go language, and `ML` inside "HTML" can never match.
- **Single-letter skills need a following separator** — `R` matches in "Python, R, SQL" but
  not in the name "Rahul R Sharma".
- **Degree/branch codes must look like abbreviations** — a sentence-initial "It is a good
  idea" must not be read as the IT branch. The test is `.istitle()`: `IT` counts, `It`
  doesn't.

This is a dictionary lookup, **not** machine learning — which is the point. It is
predictable, debuggable, and the student sees and can correct exactly what was extracted
before anything is saved.

Generate test PDFs (three profiles: CSE, data science, ECE) with:

```
python tools/make_sample_resume.py
```

That script writes valid PDFs by hand — no `reportlab`, no extra dependency.

## 9. ML component

**Read this section honestly — it is deliberately unimpressive in scope and precise about
what it is.**

| | |
|---|---|
| **Model** | Logistic Regression (`scikit-learn`), features standardised in a `Pipeline` |
| **Input** | 7 features: the 5 sub-scores + `skill × location` + `skill²` |
| **Output** | `P(shortlisted)` — probability a recruiter shortlists this pairing |
| **Training data** | `ml/training_data.csv` — **1,500 SYNTHETIC rows**, generated by `ml/generate_training_data.py` |
| **Measured** | test accuracy **0.803**, ROC AUC **0.893** on a held-out 25% split |

### The training data is synthetic, and the app says so

SkillBridge is a prototype with no placement history, so there is no real "was this student
shortlisted?" dataset. Rather than invent one and quietly imply otherwise, the rows are
generated from a documented recruiter-behaviour model, and the `/ml-info` page states this in
a warning box. **No real student data was used and the output is never presented as a real
placement prediction.**

### Why include ML at all?

Only because it can express something the linear rule engine structurally cannot:

1. **A hard skill floor** — a recruiter almost never shortlists below a ~30% skill match, no
   matter how perfect the location and stipend are.
2. **An interaction** — a strong skill match still fails if the candidate realistically
   cannot attend.

Both effects are baked into the synthetic labels, and the `skill²` and `skill × location`
features let the regression pick them up. The learned coefficients show it did: `skill_score`
2.51, `skill_x_location` 1.52, `skill_squared` −1.46 — a saturating curve, not a straight line.

### It never touches the number you see

This mattered enough to change the design mid-build:

- The **displayed match %** is always the rule score, so the breakdown table always adds up.
- The ML probability is shown separately as a "shortlist likelihood" chip.
- Ranking has **two explicit modes**, chosen by the user with a visible toggle:
  `Match score` (default — order equals the displayed percentages) and
  `AI shortlist likelihood` (`rank_score = 70% rule + 30% ML`).

Sorting by the blended key while displaying the rule score would render a 74% above a 77% and
look like a bug, so the re-ranking is never silent. Tests assert the default ordering is
always descending in the displayed score.

**If `scikit-learn` is not installed, nothing breaks.** `predict_probability()` returns
`None`, the ML chip disappears, ranking falls back to the rule score, and `/ml-info` explains
that the layer is off.

## 10. Installation

Requires Python 3.9 or newer. Nothing else.

```bash
# 1. create a virtual environment
python3 -m venv venv

# 2. activate it
source venv/bin/activate          # macOS / Linux
venv\Scripts\activate             # Windows

# 3. install dependencies
pip install -r requirements.txt
```

`scikit-learn` and `numpy` in `requirements.txt` are only needed for the optional ML layer —
the portal runs fine without them.

## 11. How to run

```bash
python init_db.py          # create the tables + demo data  (once)
python app.py              # start the server
```

Then open **http://127.0.0.1:5000**

Other useful commands:

```bash
python init_db.py --reset             # wipe and rebuild the database
python app.py --port 5001             # if port 5000 is taken (common on macOS)
python tools/make_sample_resume.py    # regenerate the sample resume PDFs
python -m ml.model                    # train the model and print its stats
python ml/generate_training_data.py   # regenerate the synthetic training CSV
python -m unittest test_app -v        # run the 70 tests
```

## 12. Demo credentials

Password for **every** demo account: `demo1234`

| Role | Email | Good for showing |
|---|---|---|
| Student | `rahul@demo.com` | Full profile, resume, 95% top match, skill gaps |
| Student | `priya@demo.com` | Different skill set → different ranking |
| Student | `arjun@demo.com` | ECE branch → visible qualification penalty |
| Student | `sneha@demo.com` | Data/ML profile |
| Company | `hr@technova.com` | Postings, ranked candidates, applications |
| Company | `hr@datasphere.com` | A second company's view |
| College | `dean@cvr.edu.in` | Demand vs supply, gaps, placement funnel |

Seeded demo data: **6 companies, 23 internships** across 7 locations + Remote,
**7 students, 89 skills, 63 courses, 12 applications**. Internships are stored with
`is_demo = 1` and carry a visible "Demo" tag.

### The 2-minute demo script

1. Log in as `rahul@demo.com`
2. **Recommendations** — internships ranked by match %, best is 95%
3. Open any internship — matched ✓ / missing ✗ skills, and the breakdown table that sums to
   the headline percentage
4. **Apply** → **Applications** shows it with the score it was applied at
5. **Skill Gap** — missing skills ordered by demand, each with free courses
6. *(Optional, the full flow)* **Resume upload** → pick `sample_data/sample_resume.pdf` →
   review the extracted skills → save
7. Log out, log in as `hr@technova.com`
8. **Post internship** (required skills: `Python, Flask, SQL, Git`) → land straight on
   ranked candidates
9. **Candidates** — Rahul 94%, Priya 82%, Arjun 70%, with the reason for each
10. Log out, log in as `dean@cvr.edu.in`
11. **Dashboard** — demand vs availability chart, then "Where to focus the curriculum":
    Docker, Linux, AWS and PostgreSQL show large positive gaps

## 13. Limitations

Honest list, not a sales pitch:

- **Skill extraction is dictionary-based.** A skill outside the 89-entry library is only
  captured if the student types it. There is no semantic understanding, so "built REST
  services in a micro-framework" won't yield "Flask".
- **Scanned/image-only PDFs cannot be read.** There is no OCR. The app detects this and says
  so rather than failing silently.
- **The ML model is trained on synthetic data** (see §9). Its probabilities are *plausible*
  recruiter behaviour, not learned from real outcomes.
- **The weights (50/20/15/10/5) are a reasoned starting point, not a tuned result.** With
  real placement data they should be fitted, not chosen.
- **Location matching is a hardcoded cluster list**, not real geography or travel time.
- **Development server only.** `app.run(debug=True)` is not for production; a real deployment
  needs a WSGI server, HTTPS, CSRF tokens on forms and rate limiting on login.
- **No email verification, password reset, or CSRF protection.** Out of scope for a prototype.
- **Single college.** The academia dashboard aggregates all students on the portal rather
  than filtering by institution.
- Uploaded resumes are stored unencrypted in `uploads/`, readable by anyone with filesystem
  access to the machine.

## 14. Future scope

- Fit the five weights on real application outcomes instead of choosing them; retrain the
  ranking model on genuine shortlist data and report calibration
- Sentence-embedding similarity for skills, so unseen phrasing still maps to a known skill
- OCR fallback (Tesseract) for scanned resumes
- Per-college scoping with institution accounts and cohort comparison
- Interview scheduling, offer letters, and a feedback loop from companies into the score
- Learning paths that sequence the missing skills, with progress tracking
- A REST API + token auth so a college ERP can sync students automatically
- Export the academia report to PDF for Board of Studies meetings
- Deployment hardening: WSGI, Postgres, CSRF, rate limits, audit logging

---

## Project structure

```
sandwich/
├── app.py                       Flask routes, auth, validation, error handlers
├── database.py                  connection, 12-table schema, query helpers
├── recommendation.py            the weighted scoring engine + skill-gap writer
├── resume_parser.py             89-skill dictionary, PDF → structured data
├── analytics.py                 SQL aggregates for the academia dashboard
├── seed_data.py                 all demo data in one readable place
├── init_db.py                   create + seed the database
├── test_app.py                  70 tests
├── requirements.txt
├── README.md
├── HOW_TO_RUN.txt               beginner-friendly single-line instructions
│
├── templates/
│   ├── base.html                topbar, flashes, footer
│   ├── dash_base.html           sidebar shell for all dashboards
│   ├── _macros.html             job row, badges, meters, breakdown, chart, sort toggle
│   ├── _icons.html              inline SVG icon set (used instead of emoji)
│   ├── _filters.html            shared filter bar
│   ├── index.html               landing page
│   ├── login.html   register.html   error.html   ml_info.html
│   ├── student_dashboard.html   profile.html   resume.html   skills.html
│   ├── recommendations.html     internships.html   internship_detail.html
│   ├── skill_gap.html           applications.html   saved.html
│   ├── industry_dashboard.html  post_internship.html   company_internships.html
│   ├── candidates.html          company_applications.html   company_profile.html
│   └── academia_dashboard.html  skill_demand.html
│
├── static/
│   ├── css/style.css            design tokens → responsive layout, one file
│   └── js/script.js             role picker, upload preview, select-all, toggles
│
├── ml/
│   ├── model.py                 logistic regression, trains on first use
│   ├── generate_training_data.py  documented synthetic data generator
│   └── training_data.csv        1,500 synthetic rows
│
├── tools/
│   └── make_sample_resume.py    dependency-free PDF writer
│
├── sample_data/                 3 generated sample resumes
├── uploads/                     student resume uploads
└── database/portal.db           the SQLite database (created by init_db.py)
```

## UI design

The interface is deliberately built to read like an internal enterprise tool rather than a
landing page. Six rules, all enforced in `static/css/style.css`:

1. **Neutral-dominant.** A ten-step grey ramp carries the interface. Colour is reserved for
   meaning only — application status, gap severity, and the two chart series. No gradients,
   no tinted panels, no purple.
2. **Hairlines, not shadows.** 1px borders separate things. Shadows are reserved for elements
   that genuinely float.
3. **Small radii.** 6px panels, 5px controls, 3px badges. Nothing is pill-shaped except the
   match score, where it reads as data.
4. **Density.** Tighter padding and 13–14px type, so more fits on screen. Hierarchy comes from
   weight and colour, not from large type.
5. **A 4px spacing grid**, and `tabular-nums` in every column of numbers so digits align.
6. **Icons, never emoji.** `templates/_icons.html` holds a 45-icon inline-SVG set on a 24×24
   grid with a 1.5px stroke, drawn with `currentColor` so an icon always matches the text
   beside it. Emoji were removed entirely: they render differently on every OS, can't inherit
   colour or stroke weight, and sit on the baseline at the wrong size.

The primary button is near-black rather than blue, which keeps blue meaning "link or data".

**Charts** are plain `div`s — no chart library, no CDN, works offline. The two series colours
(`#2a78d6` blue, `#eb6834` orange) were validated for colour-blind separation: worst-pair
ΔE 24.7 under protanopia, 32.7 under tritanopia, both far above the ≥8 threshold. Bars are
10px with a 3px rounded data-end and a 2px gap between the pair; values live in their own
column so no label can be clipped; a zero value draws no bar at all rather than a misleading
sliver. Every severity flag is an icon **and** a word, so nothing depends on colour alone, and
the academia chart has a full table view beside it.

## Deployment

The app runs on any host that can run a long-lived Python process with a writable filesystem
(Render, Railway, Fly.io, PythonAnywhere). It is **not** suitable for serverless hosts such as
Vercel: resume uploads and SQLite both need a real filesystem.

```
Build command:  pip install -r requirements-render.txt
Start command:  gunicorn app:app --bind 0.0.0.0:$PORT
Env var:        SKILLBRIDGE_SECRET = <a long random string>
```

* `--bind 0.0.0.0:$PORT` is required — gunicorn's default `127.0.0.1:8000` is unreachable from
  outside the container.
* `requirements-render.txt` omits scikit-learn, because a 512 MB free instance is tight for
  scipy/numpy. The ML layer degrades gracefully, so everything else is identical. Use the full
  `requirements.txt` on a larger instance if you want ML enabled.
* On a fresh instance the database does not exist yet. A one-shot `before_request` hook in
  `app.py` creates the tables and demo data on the first request, so the site never serves
  `no such table`.
* **On an ephemeral filesystem your data resets on every redeploy.** The demo data re-seeds
  automatically so the demo always works, but anything a visitor types is lost on restart.
  Persisting real data means moving to Postgres.

## Security measures implemented

| Concern | Measure |
|---|---|
| Password storage | `werkzeug.security` PBKDF2 hash + salt; a test asserts the plaintext never appears in the DB |
| Session handling | Signed Flask session cookie; `session.clear()` on login and logout |
| Authorisation | `@role_required('student')` etc. on every private route; a company cannot open another company's candidates (403) |
| SQL injection | 100% parameterised queries — no string-built SQL anywhere |
| Upload type | Extension allow-list **and** a `%PDF-` magic-byte check |
| Upload size | `MAX_CONTENT_LENGTH = 5 MB` with a friendly 413 page |
| Path traversal | `secure_filename()` + a server-generated stored name |
| File access | A student can only fetch their own resume, looked up via their session |
| Input validation | Every field trimmed, length-capped and range-clamped (`clean_text`, `to_int`) |
| Open redirect | Post-login redirects must start with `/` |
| Info leakage | One generic "Incorrect email or password" for both cases; error pages never show a stack trace |

## Testing

```bash
python -m unittest test_app -v
```

**70 tests, all passing.** They run against a temporary database, so your real
`database/portal.db` is never touched. Coverage:

- Resume parsing, including the false-positive traps ("go", "It", a middle initial "R",
  `C` inside "CSE") and rejection of a fake PDF
- Scoring maths for all five factors, and that the breakdown always sums to the shown score
- Default ordering is always descending in the displayed percentage
- The ML layer's honesty (synthetic-data disclosure present, 7 coefficients, AUC > 0.6) and
  that it never changes the displayed score
- Every route for every role, plus role-based authorisation and cross-company access denial
- The complete demo journey: register → upload PDF → confirm skills → set preferences →
  recommendations → skill gap → apply → verify the row in SQLite
- The company journey: post an internship → skills normalised on the way in → students ranked
- Validation failures: no file, wrong extension, fake PDF, zero skills, swapped stipend
  range, bad application status, duplicate email, mismatched passwords
