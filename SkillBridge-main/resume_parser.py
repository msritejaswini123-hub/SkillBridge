"""
resume_parser.py
================
Turns an uploaded PDF resume into structured data:

    PDF  ->  raw text  ->  { qualification, branch, skills, experience_months, projects }

How it works (kept deliberately simple and explainable):

1. `pypdf` extracts the text of every page.
2. A predefined SKILL_LIBRARY (canonical name + spelling variants) is matched
   against the text using word-boundary regexes. This is a dictionary lookup,
   not machine learning - so it is 100% predictable and easy to debug.
3. Small regexes pull out the degree ("B.Tech"), the branch ("CSE"), months of
   experience and the PROJECTS section.

The student always reviews and can edit everything before it is saved.
"""

import re

# ---------------------------------------------------------------------------
# 1. THE SKILL DICTIONARY
# ---------------------------------------------------------------------------
# canonical name -> (category, [alternative spellings found in real resumes])
# The canonical name is what we store in the `skills` table, so "sklearn",
# "Sci-kit learn" and "scikit learn" all normalise to "Scikit-learn".

SKILL_LIBRARY = {
    # ---- Programming languages ----
    "Python": ("Programming", ["python3", "python 3"]),
    "C": ("Programming", ["c language", "c programming"]),
    "C++": ("Programming", ["cpp", "c plus plus"]),
    "Java": ("Programming", ["core java"]),
    "JavaScript": ("Programming", ["js", "java script", "es6"]),
    "TypeScript": ("Programming", ["ts"]),
    "C#": ("Programming", ["c sharp", "csharp"]),
    "Go": ("Programming", ["golang"]),
    "R": ("Programming", ["r language"]),
    "PHP": ("Programming", []),
    "Kotlin": ("Programming", []),
    "Swift": ("Programming", []),
    "MATLAB": ("Programming", ["mat lab"]),
    "Embedded C": ("Programming", ["embedded-c"]),

    # ---- Web ----
    "HTML": ("Web", ["html5", "html 5"]),
    "CSS": ("Web", ["css3", "css 3"]),
    "Bootstrap": ("Web", []),
    "Tailwind CSS": ("Web", ["tailwind", "tailwindcss"]),
    "React": ("Web", ["react.js", "reactjs", "react js"]),
    "Angular": ("Web", ["angular.js", "angularjs"]),
    "Vue.js": ("Web", ["vue", "vuejs"]),
    "Node.js": ("Web", ["node", "nodejs", "node js"]),
    "jQuery": ("Web", ["jquery"]),
    "REST API": ("Web", ["rest apis", "restful api", "rest", "api development"]),

    # ---- Frameworks ----
    "Flask": ("Framework", []),
    "Django": ("Framework", []),
    "FastAPI": ("Framework", ["fast api"]),
    "Spring Boot": ("Framework", ["springboot", "spring"]),
    "Express.js": ("Framework", ["express", "expressjs"]),
    ".NET": ("Framework", ["dotnet", "asp.net", "dot net"]),

    # ---- Databases ----
    "SQL": ("Database", ["structured query language"]),
    "MySQL": ("Database", ["my sql"]),
    "PostgreSQL": ("Database", ["postgres", "postgre sql"]),
    "SQLite": ("Database", ["sqlite3"]),
    "MongoDB": ("Database", ["mongo", "mongo db"]),
    "Oracle DB": ("Database", ["oracle", "oracle database", "plsql", "pl/sql"]),
    "Redis": ("Database", []),
    "DBMS": ("Database", ["database management system", "database management systems"]),

    # ---- Data & AI ----
    "Machine Learning": ("Data & AI", ["ml", "machine-learning"]),
    "Deep Learning": ("Data & AI", ["dl", "neural networks"]),
    "Data Science": ("Data & AI", ["datascience"]),
    "NLP": ("Data & AI", ["natural language processing"]),
    "Computer Vision": ("Data & AI", ["cv model", "image processing"]),
    "TensorFlow": ("Data & AI", ["tensor flow", "keras"]),
    "PyTorch": ("Data & AI", ["py torch", "torch"]),
    "Scikit-learn": ("Data & AI", ["sklearn", "scikit learn", "sci-kit learn"]),
    "Pandas": ("Data & AI", []),
    "NumPy": ("Data & AI", ["numpy"]),
    "OpenCV": ("Data & AI", ["open cv"]),
    "Generative AI": ("Data & AI", ["genai", "gen ai", "llm", "llms", "prompt engineering"]),

    # ---- Analytics ----
    "Data Analysis": ("Analytics", ["data analytics", "data analyst"]),
    "Power BI": ("Analytics", ["powerbi", "power-bi"]),
    "Tableau": ("Analytics", []),
    "Excel": ("Analytics", ["ms excel", "microsoft excel", "advanced excel"]),
    "Statistics": ("Analytics", ["statistical analysis"]),
    "Data Visualization": ("Analytics", ["data visualisation", "dataviz"]),

    # ---- Cloud & DevOps ----
    "AWS": ("Cloud & DevOps", ["amazon web services"]),
    "Azure": ("Cloud & DevOps", ["microsoft azure"]),
    "Google Cloud": ("Cloud & DevOps", ["gcp", "google cloud platform"]),
    "Cloud Computing": ("Cloud & DevOps", ["cloud"]),
    "Docker": ("Cloud & DevOps", []),
    "Kubernetes": ("Cloud & DevOps", ["k8s"]),
    "Linux": ("Cloud & DevOps", ["ubuntu", "shell scripting"]),
    "CI/CD": ("Cloud & DevOps", ["ci cd", "continuous integration"]),
    "Jenkins": ("Cloud & DevOps", []),

    # ---- Tools ----
    "Git": ("Tools", []),
    "GitHub": ("Tools", ["git hub"]),
    "Jira": ("Tools", []),
    "Figma": ("Tools", []),
    "Postman": ("Tools", []),
    "Selenium": ("Tools", []),
    "AutoCAD": ("Tools", ["auto cad"]),
    "SolidWorks": ("Tools", ["solid works"]),

    # ---- Core CS ----
    "Data Structures": ("Core CS", ["dsa", "data structure"]),
    "Algorithms": ("Core CS", ["algorithm"]),
    "OOP": ("Core CS", ["object oriented programming", "oops"]),
    "Operating Systems": ("Core CS", ["operating system"]),
    "Computer Networks": ("Core CS", ["computer networking", "networking"]),
    "Cybersecurity": ("Core CS", ["cyber security", "information security"]),
    "Software Testing": ("Core CS", ["manual testing", "qa testing", "test automation"]),
    "Agile": ("Core CS", ["scrum", "agile methodology"]),
    "IoT": ("Core CS", ["internet of things"]),

    # ---- Business / soft skills ----
    "Digital Marketing": ("Business", ["seo", "social media marketing"]),
    "Content Writing": ("Business", ["copywriting", "technical writing"]),
    "UI/UX Design": ("Business", ["ui ux", "ux design", "ui design"]),
    "Communication": ("Soft Skills", ["communication skills"]),
    "Teamwork": ("Soft Skills", ["team work", "team player", "collaboration"]),
    "Problem Solving": ("Soft Skills", ["problem-solving", "analytical skills"]),
    "Leadership": ("Soft Skills", ["team lead", "led a team"]),
}

# Flat lookup used by the matcher: every spelling -> canonical name
_ALIAS_TO_CANONICAL = {}
for _canonical, (_category, _aliases) in SKILL_LIBRARY.items():
    _ALIAS_TO_CANONICAL[_canonical.lower()] = _canonical
    for _alias in _aliases:
        _ALIAS_TO_CANONICAL[_alias.lower()] = _canonical


def all_skill_names():
    """Canonical skill names, alphabetically - used to seed the DB and for autocomplete."""
    return sorted(SKILL_LIBRARY.keys())


def skill_category(name):
    """Category of a canonical skill (defaults to 'Other' for custom skills)."""
    entry = SKILL_LIBRARY.get(name)
    return entry[0] if entry else "Other"


def normalize_skill(text):
    """
    Turn any user/company typed skill into its canonical form.
    'sklearn' -> 'Scikit-learn',  'HTML5' -> 'HTML',  'Rust' -> 'Rust' (unknown, title-cased).
    """
    if not text:
        return None
    cleaned = " ".join(str(text).split()).strip(" ,.;:/|")
    if not cleaned:
        return None
    canonical = _ALIAS_TO_CANONICAL.get(cleaned.lower())
    if canonical:
        return canonical
    # Unknown skill: keep it, but tidy the capitalisation.
    return cleaned if cleaned.isupper() else cleaned.title()


# Short aliases need tight rules, otherwise "C" matches inside "CSE", "ml" matches
# inside "HTML" and the English word "go" becomes the Go language.
#   * every alias is matched on word boundaries that also respect '+' and '#'
#     (so "C" does not match the C in "C++", but "C++" itself does)
#   * 1-2 character aliases (C, R, Go, ML, JS) must contain a capital letter,
#     because resumes always write those as "C", "ML", "Go" - never "c", "ml", "go"
#   * 1 character aliases must also be followed by a separator (", / | ; newline"),
#     so a middle initial in "Rahul R Sharma" is not read as the R language
_BOUNDARY_LEFT = r"(?<![A-Za-z0-9+#._])"
_BOUNDARY_RIGHT = r"(?![A-Za-z0-9+#_])"
_SEPARATOR_AHEAD = r"(?=\s*(?:[,/|;•·\-]|$|\n))"
_HAS_UPPERCASE = re.compile(r"[A-Z]")
_ALPHA_ONLY = re.compile(r"^[A-Za-z]+$")


def _looks_like_an_english_word(text):
    """
    True for 'it', 'It', 'be', 'Be', 'go' - ordinary words that happen to spell a
    branch or degree code. False for 'IT', 'BE', 'B.E', 'BSc' - real abbreviations.

    The test is: letters only AND (all lowercase OR Title-case). A sentence such as
    "It is a good idea" must never be read as the IT branch, and .istitle() is what
    separates the sentence-initial "It" from the abbreviation "IT".
    """
    if not _ALPHA_ONLY.match(text):
        return False              # contains a dot/digit, e.g. "B.E" - keep it
    return text.islower() or text.istitle()


def _alias_pattern(alias, case_insensitive=True):
    """Compile one alias into a word-boundary regex ('c++', 'c#' and '.net' safe)."""
    escaped = re.escape(alias).replace(r"\ ", r"[\s\-_]+")
    tail = _SEPARATOR_AHEAD if len(alias) == 1 else ""
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(_BOUNDARY_LEFT + escaped + _BOUNDARY_RIGHT + tail, flags | re.MULTILINE)


def _compile_alias_list():
    """(pattern, canonical, needs_uppercase) for every spelling in the library."""
    compiled = []
    for alias, canonical in _ALIAS_TO_CANONICAL.items():
        compiled.append((_alias_pattern(alias), canonical, len(alias) <= 2))
    return compiled


_COMPILED_ALIASES = _compile_alias_list()


def extract_skills(text):
    """
    Match the skill dictionary against resume text.
    Returns a sorted list of canonical skill names (no duplicates).
    """
    if not text:
        return []
    found = set()
    for pattern, canonical, needs_uppercase in _COMPILED_ALIASES:
        for match in pattern.finditer(text):
            if needs_uppercase and not _HAS_UPPERCASE.search(match.group(0)):
                continue  # 'go' the verb, not 'Go' the language
            found.add(canonical)
            break
    return sorted(found)


# ---------------------------------------------------------------------------
# 2. QUALIFICATION / BRANCH
# ---------------------------------------------------------------------------
# spelling -> canonical degree
DEGREE_ALIASES = {
    "b.tech": "B.Tech", "btech": "B.Tech", "b tech": "B.Tech",
    "bachelor of technology": "B.Tech",
    "b.e": "B.E", "be": "B.E", "bachelor of engineering": "B.E",
    "m.tech": "M.Tech", "mtech": "M.Tech", "master of technology": "M.Tech",
    "mca": "MCA", "bca": "BCA",
    "b.sc": "B.Sc", "bsc": "B.Sc", "m.sc": "M.Sc", "msc": "M.Sc",
    "mba": "MBA", "b.com": "B.Com", "bcom": "B.Com",
    "diploma": "Diploma", "phd": "PhD", "ph.d": "PhD",
}

BRANCH_ALIASES = {
    "cse": "CSE", "cs": "CSE", "computer science": "CSE",
    "computer science and engineering": "CSE", "computer engineering": "CSE",
    "it": "IT", "information technology": "IT",
    "ece": "ECE", "electronics and communication": "ECE", "electronics": "ECE",
    "eee": "EEE", "electrical": "EEE", "electrical engineering": "EEE",
    "mechanical": "Mechanical", "mech": "Mechanical",
    "civil": "Civil", "chemical": "Chemical",
    "aiml": "AI & ML", "ai & ml": "AI & ML", "ai&ml": "AI & ML",
    "artificial intelligence": "AI & ML",
    "data science": "Data Science", "aids": "Data Science",
    "biotechnology": "Biotechnology", "biotech": "Biotechnology",
}

# Degrees that are close enough to be treated as near-equivalent by the matcher.
DEGREE_FAMILIES = {
    "B.Tech": {"B.Tech", "B.E"},
    "B.E": {"B.Tech", "B.E"},
    "M.Tech": {"M.Tech", "M.E"},
    "MCA": {"MCA", "M.Sc", "M.Tech"},
    "BCA": {"BCA", "B.Sc", "B.Tech"},
    "B.Sc": {"B.Sc", "BCA"},
    "M.Sc": {"M.Sc", "MCA"},
}


def _find_first(text, alias_map, strict=True):
    """
    Find whichever alias appears earliest in the text.

    strict=True (long resume text): short aliases such as "be", "it" and "cs" only
    count when written as abbreviations ("B.E", "IT", "CS"). Otherwise the English
    words "be" and "it" - including a sentence-initial "It" - would be read as a
    degree or branch on almost every resume.
    strict=False (a short form field the user typed, e.g. "b.tech cse"): match
    case-insensitively, because the whole string IS the qualification.
    """
    if not text:
        return None
    best = None
    for alias in sorted(alias_map, key=len, reverse=True):
        for match in _alias_pattern(alias).finditer(text):
            if strict and len(alias) <= 3 and _looks_like_an_english_word(match.group(0)):
                continue
            if best is None or match.start() < best[0]:
                best = (match.start(), alias_map[alias])
            break
    return best[1] if best else None


def extract_qualification(text):
    """'B.Tech CSE student ...' -> ('B.Tech', 'CSE'). For long resume text."""
    return _find_first(text, DEGREE_ALIASES), _find_first(text, BRANCH_ALIASES)


def find_all_aliases(text, alias_map, strict=False):
    """
    Every canonical value mentioned in `text`.
    'B.Tech / MCA - CSE, IT' -> {'B.Tech', 'MCA'} for degrees, {'CSE','IT'} for branches.
    """
    if not text:
        return set()
    found = set()
    for alias, canonical in alias_map.items():
        for match in _alias_pattern(alias).finditer(text):
            if strict and len(alias) <= 3 and _looks_like_an_english_word(match.group(0)):
                continue
            found.add(canonical)
            break
    return found


def parse_qualification_field(value):
    """
    For short typed values such as 'B.Tech CSE', 'btech cse' or 'Any Degree'.
    Returns (degree, branch); either can be None.
    """
    return (_find_first(value, DEGREE_ALIASES, strict=False),
            _find_first(value, BRANCH_ALIASES, strict=False))


def extract_experience_months(text):
    """
    Rough internship/work experience in months.
    Looks for '6 months internship', '1 year experience', etc.
    """
    if not text:
        return 0
    months = 0
    for value, unit in re.findall(r"(\d{1,2})\s*\+?\s*(month|months|year|years|yr|yrs)", text, re.I):
        amount = int(value) * (12 if unit.lower().startswith(("year", "yr")) else 1)
        months = max(months, min(amount, 60))  # cap at 5 years - guards against typos
    return months


_SECTION_HEADINGS = (
    "education", "skills", "technical skills", "experience", "internship",
    "internships", "certifications", "achievements", "hobbies", "interests",
    "declaration", "languages", "contact", "summary", "objective", "activities",
)


def extract_projects(text):
    """Pull the PROJECTS section (used as a light 'project relevance' signal)."""
    if not text:
        return ""
    lines = text.splitlines()
    collected, inside = [], False
    for line in lines:
        stripped = line.strip()
        heading = stripped.lower().strip(" :-*")
        if not inside:
            if heading in ("projects", "project", "academic projects", "personal projects",
                           "key projects", "project work"):
                inside = True
            continue
        if heading in _SECTION_HEADINGS:  # next section started
            break
        if stripped:
            collected.append(stripped)
    return "\n".join(collected)[:2000]


# ---------------------------------------------------------------------------
# 3. PDF -> TEXT
# ---------------------------------------------------------------------------

class ResumeError(Exception):
    """Raised for anything the student should see a friendly message about."""


def extract_text_from_pdf(path):
    """
    Read every page of the PDF and return its text.
    Raises ResumeError with a human-readable message when the file is unusable.
    """
    try:
        from pypdf import PdfReader
    except ImportError:  # pragma: no cover - dependency missing
        raise ResumeError("PDF support is not installed. Run: pip install pypdf")

    try:
        reader = PdfReader(path)
        if reader.is_encrypted:
            try:
                reader.decrypt("")  # some resumes are "encrypted" with an empty password
            except Exception:
                raise ResumeError("This PDF is password protected. Please upload an unlocked file.")
        pages = [(page.extract_text() or "") for page in reader.pages]
    except ResumeError:
        raise
    except Exception:
        # Never leak the library traceback to the browser.
        raise ResumeError("That file could not be read as a PDF. Please upload a valid PDF resume.")

    text = "\n".join(pages).strip()
    if len(text) < 30:
        raise ResumeError(
            "No readable text found. This looks like a scanned/image-only PDF - "
            "please upload a text-based PDF, or add your skills manually."
        )
    return text


def parse_resume(path):
    """
    Full pipeline for one uploaded file.
    Returns a dict the /student/skills review screen renders.
    """
    text = extract_text_from_pdf(path)
    degree, branch = extract_qualification(text)
    return {
        "text": text,
        "degree": degree,
        "branch": branch,
        "qualification": " ".join(p for p in (degree, branch) if p),
        "skills": extract_skills(text),
        "experience_months": extract_experience_months(text),
        "projects": extract_projects(text),
    }
