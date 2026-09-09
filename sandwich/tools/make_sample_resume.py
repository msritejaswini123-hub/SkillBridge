"""
tools/make_sample_resume.py
===========================
Writes sample_data/sample_resume.pdf (and two variants) so the resume-upload
flow can be demonstrated without hunting for a real PDF.

It builds a minimal, valid PDF by hand - no reportlab, no extra dependency.
A PDF is just a few numbered objects plus a cross-reference table, so this is
about 40 lines of byte-pushing.

Run:  python tools/make_sample_resume.py
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(os.path.dirname(HERE), "sample_data")

PAGE_WIDTH, PAGE_HEIGHT = 595, 842       # A4 in points
LEFT_MARGIN, TOP_START = 56, 780
FONT_SIZE, LINE_HEIGHT = 11, 15
MAX_LINES = int((TOP_START - 60) / LINE_HEIGHT)


def _escape(text):
    """Escape the three characters that are special inside a PDF string."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _content_stream(lines):
    """Build the page's drawing commands: begin text, set font, write lines."""
    parts = ["BT", f"/F1 {FONT_SIZE} Tf", f"{LINE_HEIGHT} TL",
             f"1 0 0 1 {LEFT_MARGIN} {TOP_START} Tm"]
    for line in lines[:MAX_LINES]:
        parts.append(f"({_escape(line)}) Tj")
        parts.append("T*")                      # next line
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", "replace")


def write_pdf(path, lines):
    """Assemble a single-page PDF containing `lines` of text."""
    content = _content_stream(lines)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
         f"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>").encode(),
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_start = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n").encode()

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(bytes(out))
    return path


# ---------------------------------------------------------------------------
# The sample resumes
# ---------------------------------------------------------------------------

MAIN_RESUME = [
    "RAHUL VERMA",
    "Hyderabad, Telangana  |  rahul.verma@example.com  |  +91 90000 00001",
    "github.com/rahulverma  |  linkedin.com/in/rahulverma",
    "",
    "OBJECTIVE",
    "B.Tech CSE student seeking a software development internship where I can apply",
    "my Python and web development skills to real production systems.",
    "",
    "EDUCATION",
    "B.Tech CSE - CVR College of Engineering, Hyderabad",
    "Expected graduation 2026  |  CGPA 8.4 / 10",
    "Intermediate MPC - Narayana Junior College, 2022  |  94%",
    "",
    "TECHNICAL SKILLS",
    "Languages: Python, C, C++, SQL",
    "Web: HTML, CSS, JavaScript, Flask, REST API",
    "Databases: MySQL, SQLite",
    "Tools: Git, GitHub, VS Code, Postman",
    "Core CS: Data Structures, Algorithms, OOP, DBMS, Operating Systems",
    "",
    "PROJECTS",
    "Student Result Portal - Python, Flask, SQLite, HTML, CSS",
    "  Built a web portal where staff upload marks and students view results.",
    "  Used Flask blueprints, Jinja templates and parameterised SQL queries.",
    "  Version controlled with Git and deployed on a college server.",
    "Weather Dashboard - Python, REST API, JavaScript",
    "  Consumed a public weather REST API and charted a 7 day forecast.",
    "Library Management System - C++, OOP",
    "  Console application demonstrating inheritance and file handling.",
    "",
    "EXPERIENCE",
    "Web Development Intern - BrightLogic Software, Hyderabad",
    "  3 months internship. Fixed bugs in a Flask reporting module, wrote SQL",
    "  queries for a sales dashboard and raised 20+ reviewed pull requests.",
    "",
    "CERTIFICATIONS",
    "Python for Everybody - Coursera",
    "SQL Basics - HackerRank",
    "",
    "ACHIEVEMENTS",
    "Runner up, college hackathon 2025 (team of 4)",
    "",
    "LANGUAGES",
    "English, Hindi, Telugu",
]

DATA_RESUME = [
    "SNEHA IYER",
    "Bangalore, Karnataka  |  sneha.iyer@example.com",
    "",
    "EDUCATION",
    "B.Tech CSE - 2025  |  CGPA 8.9 / 10",
    "",
    "TECHNICAL SKILLS",
    "Python, SQL, Machine Learning, Pandas, NumPy, Scikit-learn",
    "Statistics, Data Visualization, Power BI, Excel, Git",
    "",
    "PROJECTS",
    "Customer Churn Prediction - Python, Scikit-learn, Pandas",
    "  Trained a logistic regression and random forest on a telecom dataset.",
    "  Reported precision, recall and ROC AUC for both models.",
    "Sales Forecasting Notebook - Python, Statistics, Data Visualization",
    "  Time series analysis with seasonal decomposition and Matplotlib charts.",
    "",
    "EXPERIENCE",
    "Data Science Intern - Analytics startup, Bangalore",
    "  6 months. Cleaned datasets, built dashboards, presented weekly findings.",
    "",
    "CERTIFICATIONS",
    "Intro to Machine Learning - Kaggle Learn",
]

ECE_RESUME = [
    "ARJUN REDDY",
    "Hyderabad  |  arjun.reddy@example.com",
    "",
    "EDUCATION",
    "B.Tech ECE - CVR College of Engineering, 2026  |  CGPA 7.8 / 10",
    "",
    "TECHNICAL SKILLS",
    "C, C++, Java, Python, SQL, MATLAB, Embedded C, IoT, Excel, Git",
    "",
    "PROJECTS",
    "Line Following Robot - Embedded C, 8051 microcontroller",
    "  Wrote sensor driver code and PWM motor control.",
    "Sensor Data Logger - Python, Excel",
    "  Logged temperature readings over serial and produced daily reports.",
    "",
    "EXPERIENCE",
    "Hardware Lab Intern - 2 months, campus electronics lab",
    "",
    "ACHIEVEMENTS",
    "First place, inter-college robotics event 2025",
]

SAMPLES = [
    ("sample_resume.pdf", MAIN_RESUME,
     "the main demo resume - B.Tech CSE with Python, SQL, HTML, CSS, Flask"),
    ("sample_resume_data_science.pdf", DATA_RESUME,
     "a data/ML profile, for showing a different ranking"),
    ("sample_resume_ece.pdf", ECE_RESUME,
     "an ECE profile, for showing the qualification mismatch penalty"),
]


def main():
    print("Writing sample resumes ...")
    for filename, lines, description in SAMPLES:
        path = write_pdf(os.path.join(OUT_DIR, filename), lines)
        size_kb = os.path.getsize(path) / 1024
        print(f"  {filename:<38} {size_kb:5.1f} KB   {description}")

    # Verify the PDFs are readable by the same parser the app uses.
    try:
        import sys
        sys.path.insert(0, os.path.dirname(HERE))
        import resume_parser as rp
        print("\nChecking them with the app's own parser:")
        for filename, _lines, _description in SAMPLES:
            parsed = rp.parse_resume(os.path.join(OUT_DIR, filename))
            print(f"  {filename}")
            print(f"     qualification : {parsed['qualification'] or '(none found)'}")
            print(f"     experience    : {parsed['experience_months']} months")
            print(f"     skills ({len(parsed['skills'])}) : {', '.join(parsed['skills'])}")
    except Exception as error:
        print(f"\n  (Could not verify with the parser: {error})")


if __name__ == "__main__":
    main()
