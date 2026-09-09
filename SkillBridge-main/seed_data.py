"""
seed_data.py
============
All DEMO data for SkillBridge, in one readable place.

*** EVERY record created here is fictional demo data. ***
Internships are stored with is_demo = 1 and the UI shows a "Demo" tag on them,
so nobody mistakes them for real openings.

The one thing that is NOT hardcoded: the match_score saved on each demo
application is computed by the real recommendation engine at seed time.
"""

import os
import shutil

from werkzeug.security import generate_password_hash

import resume_parser as rp
from database import execute, get_or_create_skill, query_one

DEMO_PASSWORD = "demo1234"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_DIR = os.path.join(BASE_DIR, "sample_data")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")


# ---------------------------------------------------------------------------
# COMPANIES
# ---------------------------------------------------------------------------
COMPANIES = [
    {
        "name": "TechNova HR Team", "email": "hr@technova.com",
        "company_name": "TechNova Solutions", "industry": "IT Services & Product",
        "website": "https://technova.example.com", "location": "Hyderabad",
        "about": "Product engineering company building web platforms for logistics "
                 "and retail clients. 400+ engineers across Hyderabad and Bangalore.",
    },
    {
        "name": "DataSphere Talent", "email": "hr@datasphere.com",
        "company_name": "DataSphere Analytics", "industry": "Data & Analytics",
        "website": "https://datasphere.example.com", "location": "Bangalore",
        "about": "Analytics consultancy delivering dashboards, forecasting and ML "
                 "models for BFSI and e-commerce customers.",
    },
    {
        "name": "CloudCraft Recruiting", "email": "hr@cloudcraft.com",
        "company_name": "CloudCraft Systems", "industry": "Cloud & DevOps",
        "website": "https://cloudcraft.example.com", "location": "Pune",
        "about": "Cloud migration and platform-engineering specialists. AWS and "
                 "Azure partner with a strong internship-to-hire track record.",
    },
    {
        "name": "MediCore People", "email": "hr@medicore.com",
        "company_name": "MediCore Health Tech", "industry": "Healthcare Technology",
        "website": "https://medicore.example.com", "location": "Chennai",
        "about": "Hospital management software and patient-facing mobile apps used "
                 "by 120 hospitals across South India.",
    },
    {
        "name": "FinEdge Careers", "email": "hr@finedge.com",
        "company_name": "FinEdge Fintech", "industry": "Fintech",
        "website": "https://finedge.example.com", "location": "Mumbai",
        "about": "Digital lending and payments startup. Backend-heavy engineering "
                 "culture with a strong focus on Python and Java services.",
    },
    {
        "name": "GreenVolt Hiring", "email": "hr@greenvolt.com",
        "company_name": "GreenVolt Energy", "industry": "Energy & Embedded Systems",
        "website": "https://greenvolt.example.com", "location": "Delhi",
        "about": "Smart-metering and EV-charging hardware company. Works across "
                 "embedded firmware, IoT and computer vision.",
    },
]


# ---------------------------------------------------------------------------
# INTERNSHIPS  (23 demo openings)
# ---------------------------------------------------------------------------
# company_email links the opening to its company above.
INTERNSHIPS = [
    {
        "company_email": "hr@technova.com",
        "title": "Python Developer Intern",
        "domain": "Web Development",
        "location": "Hyderabad",
        "stipend_min": 15000, "stipend_max": 15000,
        "duration_months": 6, "openings": 4,
        "qualification": "B.Tech CSE / IT",
        "description": "Work with our backend team on internal Flask services. You will "
                       "write REST endpoints, run SQL queries against reporting tables and "
                       "raise pull requests reviewed by senior engineers. Strong performers "
                       "receive a full-time offer.",
        "required": ["Python", "SQL", "Flask", "Git"],
        "preferred": ["REST API", "Docker"],
    },
    {
        "company_email": "hr@datasphere.com",
        "title": "Data Analyst Intern",
        "domain": "Data Analytics",
        "location": "Hyderabad",
        "stipend_min": 12000, "stipend_max": 12000,
        "duration_months": 3, "openings": 3,
        "qualification": "B.Tech Any Branch / B.Sc",
        "description": "Support the client reporting team. Clean raw sales extracts in Excel, "
                       "write SQL to build summary tables and publish weekly Power BI "
                       "dashboards for two retail accounts.",
        "required": ["SQL", "Excel", "Power BI"],
        "preferred": ["Python", "Statistics"],
    },
    {
        "company_email": "hr@technova.com",
        "title": "Full Stack Web Development Intern",
        "domain": "Web Development",
        "location": "Bangalore",
        "stipend_min": 18000, "stipend_max": 22000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / IT / MCA",
        "description": "Build customer-facing screens end to end: React components on the "
                       "front end, Node.js APIs behind them. You will own small features "
                       "from design review through production release.",
        "required": ["HTML", "CSS", "JavaScript", "React", "Node.js"],
        "preferred": ["MongoDB", "Git"],
    },
    {
        "company_email": "hr@datasphere.com",
        "title": "Machine Learning Intern",
        "domain": "Machine Learning",
        "location": "Bangalore",
        "stipend_min": 20000, "stipend_max": 25000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / M.Tech / MCA",
        "description": "Join the modelling pod working on churn prediction and demand "
                       "forecasting. Expect heavy feature engineering in Pandas, model "
                       "training with Scikit-learn and clear written experiment reports.",
        "required": ["Python", "Machine Learning", "Scikit-learn", "Pandas", "NumPy"],
        "preferred": ["Deep Learning", "TensorFlow", "SQL"],
    },
    {
        "company_email": "hr@cloudcraft.com",
        "title": "Cloud Engineering Intern",
        "domain": "Cloud & DevOps",
        "location": "Pune",
        "stipend_min": 18000, "stipend_max": 18000,
        "duration_months": 6, "openings": 3,
        "qualification": "B.Tech Any Branch",
        "description": "Help migrate customer workloads to AWS. Day to day you will work in "
                       "Linux shells, package services into Docker images and document "
                       "runbooks for the platform team.",
        "required": ["Linux", "AWS", "Docker"],
        "preferred": ["Kubernetes", "CI/CD", "Python"],
    },
    {
        "company_email": "hr@medicore.com",
        "title": "Frontend Developer Intern",
        "domain": "Web Development",
        "location": "Chennai",
        "stipend_min": 10000, "stipend_max": 14000,
        "duration_months": 3, "openings": 2,
        "qualification": "Any Degree",
        "description": "Convert Figma designs of our patient portal into responsive, "
                       "accessible pages. Good HTML and CSS fundamentals matter more to us "
                       "here than framework experience.",
        "required": ["HTML", "CSS", "JavaScript"],
        "preferred": ["React", "Figma"],
    },
    {
        "company_email": "hr@finedge.com",
        "title": "Backend Developer Intern (Django)",
        "domain": "Web Development",
        "location": "Mumbai",
        "stipend_min": 20000, "stipend_max": 20000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / IT",
        "description": "Work on the lending service: Django models, PostgreSQL queries and "
                       "REST APIs consumed by our mobile app. Code review and automated "
                       "tests are part of every merge.",
        "required": ["Python", "Django", "PostgreSQL", "REST API"],
        "preferred": ["Docker", "Redis", "Git"],
    },
    {
        "company_email": "hr@finedge.com",
        "title": "Business Analytics Intern",
        "domain": "Business Analytics",
        "location": "Mumbai",
        "stipend_min": 15000, "stipend_max": 15000,
        "duration_months": 4, "openings": 2,
        "qualification": "MBA / B.Tech Any Branch / B.Com",
        "description": "Sit with the growth team and measure what actually moves loan "
                       "conversions. Heavy Excel modelling, SQL pulls and a weekly readout "
                       "to the product manager.",
        "required": ["Excel", "SQL", "Data Analysis"],
        "preferred": ["Power BI", "Tableau", "Communication"],
    },
    {
        "company_email": "hr@cloudcraft.com",
        "title": "Cybersecurity Analyst Intern",
        "domain": "Cybersecurity",
        "location": "Delhi",
        "stipend_min": 16000, "stipend_max": 16000,
        "duration_months": 6, "openings": 1,
        "qualification": "B.Tech CSE / IT",
        "description": "Assist the security operations team with log triage, vulnerability "
                       "scan reviews and hardening checklists for Linux servers.",
        "required": ["Computer Networks", "Linux", "Cybersecurity"],
        "preferred": ["Python", "Operating Systems"],
    },
    {
        "company_email": "hr@datasphere.com",
        "title": "Data Science Intern (Remote)",
        "domain": "Data Science",
        "location": "Remote",
        "stipend_min": 14000, "stipend_max": 18000,
        "duration_months": 3, "openings": 4,
        "qualification": "B.Tech Any Branch / B.Sc / MCA",
        "description": "Fully remote project role. Explore customer datasets, build clear "
                       "visualisations and present findings in a fortnightly demo. Good "
                       "written communication is essential.",
        "required": ["Python", "Pandas", "Statistics", "Data Visualization"],
        "preferred": ["Machine Learning", "SQL"],
    },
    {
        "company_email": "hr@medicore.com",
        "title": "Android Developer Intern",
        "domain": "Mobile Development",
        "location": "Bangalore",
        "stipend_min": 15000, "stipend_max": 15000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / IT / MCA",
        "description": "Ship features in our patient appointment app. Kotlin for new screens, "
                       "Java for the older modules, SQLite for offline storage.",
        "required": ["Java", "Kotlin", "SQLite"],
        "preferred": ["Git", "REST API"],
    },
    {
        "company_email": "hr@technova.com",
        "title": "Software Testing / QA Intern",
        "domain": "Software Testing",
        "location": "Hyderabad",
        "stipend_min": 10000, "stipend_max": 10000,
        "duration_months": 3, "openings": 5,
        "qualification": "Any Degree",
        "description": "Write and run test cases for our logistics web app, automate the "
                       "regression suite in Selenium and log clean, reproducible defects "
                       "in Jira.",
        "required": ["Software Testing", "Selenium", "SQL"],
        "preferred": ["Java", "Jira"],
    },
    {
        "company_email": "hr@medicore.com",
        "title": "UI/UX Design Intern",
        "domain": "UI/UX Design",
        "location": "Remote",
        "stipend_min": 8000, "stipend_max": 12000,
        "duration_months": 3, "openings": 2,
        "qualification": "Any Degree",
        "description": "Research, wireframe and prototype improvements to our doctor "
                       "dashboard in Figma. You will run two usability sessions with real "
                       "hospital staff.",
        "required": ["Figma", "UI/UX Design"],
        "preferred": ["HTML", "CSS", "Communication"],
    },
    {
        "company_email": "hr@cloudcraft.com",
        "title": "DevOps Intern",
        "domain": "Cloud & DevOps",
        "location": "Hyderabad",
        "stipend_min": 22000, "stipend_max": 22000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / IT",
        "description": "Own pieces of our delivery pipeline: Jenkins jobs, Docker builds and "
                       "deployment scripts. You will be on call with a mentor during "
                       "release windows.",
        "required": ["Linux", "Docker", "CI/CD", "Jenkins"],
        "preferred": ["Kubernetes", "AWS", "Git"],
    },
    {
        "company_email": "hr@technova.com",
        "title": "AI / Generative AI Intern",
        "domain": "Machine Learning",
        "location": "Remote",
        "stipend_min": 25000, "stipend_max": 25000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / M.Tech / MCA",
        "description": "Prototype LLM features for our support product: retrieval over "
                       "internal docs, prompt evaluation harnesses and latency testing. "
                       "Research-minded interns do well in this team.",
        "required": ["Python", "Generative AI", "NLP"],
        "preferred": ["PyTorch", "Machine Learning", "REST API"],
    },
    {
        "company_email": "hr@greenvolt.com",
        "title": "Embedded Systems Intern",
        "domain": "Embedded & IoT",
        "location": "Pune",
        "stipend_min": 12000, "stipend_max": 12000,
        "duration_months": 6, "openings": 3,
        "qualification": "B.Tech ECE / EEE",
        "description": "Firmware work on our smart-meter board: sensor drivers in Embedded C, "
                       "bench testing and IoT telemetry over MQTT.",
        "required": ["Embedded C", "C", "IoT"],
        "preferred": ["MATLAB", "Linux"],
    },
    {
        "company_email": "hr@datasphere.com",
        "title": "Power BI Reporting Intern",
        "domain": "Data Analytics",
        "location": "Chennai",
        "stipend_min": 11000, "stipend_max": 13000,
        "duration_months": 3, "openings": 2,
        "qualification": "B.Com / MBA / B.Tech Any Branch",
        "description": "Rebuild legacy Excel reports as Power BI dashboards for a healthcare "
                       "client. Includes writing the SQL views behind each visual.",
        "required": ["Power BI", "Excel", "SQL"],
        "preferred": ["Data Visualization", "Data Analysis"],
    },
    {
        "company_email": "hr@finedge.com",
        "title": "Java Backend Intern",
        "domain": "Web Development",
        "location": "Chennai",
        "stipend_min": 17000, "stipend_max": 17000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / IT / MCA",
        "description": "Build Spring Boot microservices for the payments ledger. Solid OOP "
                       "fundamentals and comfort with MySQL are what we look for.",
        "required": ["Java", "Spring Boot", "MySQL", "OOP"],
        "preferred": ["Git", "REST API", "Docker"],
    },
    {
        "company_email": "hr@greenvolt.com",
        "title": "Digital Marketing Intern",
        "domain": "Digital Marketing",
        "location": "Delhi",
        "stipend_min": 8000, "stipend_max": 10000,
        "duration_months": 3, "openings": 2,
        "qualification": "Any Degree",
        "description": "Run our EV-charging launch campaign: SEO-focused blog posts, "
                       "LinkedIn content calendar and a simple performance tracker.",
        "required": ["Digital Marketing", "Content Writing"],
        "preferred": ["Excel", "Communication"],
    },
    {
        "company_email": "hr@technova.com",
        "title": "Database Intern (SQL)",
        "domain": "Data Analytics",
        "location": "Hyderabad",
        "stipend_min": 13000, "stipend_max": 13000,
        "duration_months": 4, "openings": 2,
        "qualification": "B.Tech Any Branch / MCA",
        "description": "Tune slow reporting queries, design indexes and help normalise a "
                       "legacy schema. A good role if you enjoyed your DBMS course.",
        "required": ["SQL", "MySQL", "DBMS"],
        "preferred": ["Python", "PostgreSQL"],
    },
    {
        "company_email": "hr@medicore.com",
        "title": "Flask Web Intern",
        "domain": "Web Development",
        "location": "Hyderabad",
        "stipend_min": 12000, "stipend_max": 16000,
        "duration_months": 4, "openings": 3,
        "qualification": "B.Tech CSE / IT / MCA",
        "description": "Small internal tools team. You will build complete Flask pages with "
                       "Jinja templates, SQLite storage and light JavaScript - a great fit "
                       "if you have built academic projects in Flask.",
        "required": ["Python", "Flask", "HTML", "CSS", "SQLite"],
        "preferred": ["JavaScript", "Git"],
    },
    {
        "company_email": "hr@greenvolt.com",
        "title": "Computer Vision Intern",
        "domain": "Machine Learning",
        "location": "Bangalore",
        "stipend_min": 18000, "stipend_max": 21000,
        "duration_months": 6, "openings": 1,
        "qualification": "B.Tech ECE / CSE / M.Tech",
        "description": "Detect meter-reading digits from field photographs. OpenCV "
                       "preprocessing, dataset labelling and a small CNN at the end.",
        "required": ["Python", "OpenCV", "Computer Vision"],
        "preferred": ["Deep Learning", "NumPy", "Machine Learning"],
    },
    {
        "company_email": "hr@cloudcraft.com",
        "title": "Data Engineering Intern",
        "domain": "Data Science",
        "location": "Remote",
        "stipend_min": 20000, "stipend_max": 20000,
        "duration_months": 6, "openings": 2,
        "qualification": "B.Tech CSE / IT / MCA",
        "description": "Build batch pipelines that move client data into our warehouse. "
                       "Python scripting, a lot of SQL, and Linux cron in between.",
        "required": ["Python", "SQL", "Linux"],
        "preferred": ["AWS", "Docker", "PostgreSQL"],
    },
]


# ---------------------------------------------------------------------------
# STUDENTS
# ---------------------------------------------------------------------------
STUDENTS = [
    {
        "name": "Rahul Verma", "email": "rahul@demo.com",
        "college": "CVR College of Engineering",
        "qualification": "B.Tech", "branch": "CSE", "graduation_year": 2026,
        "preferred_location": "Hyderabad",
        "min_stipend": 10000, "max_stipend": 20000,
        "phone": "9000000001",
        "resume_file": "sample_resume.pdf",
        "experience_months": 3,
        "projects_text": "Student Result Portal - built with Python, Flask, SQLite and "
                         "Jinja templates, deployed with Git version control.\n"
                         "Weather REST API client using Python requests and JSON parsing.",
        "skills": ["Python", "SQL", "HTML", "CSS", "Flask", "Git", "SQLite",
                   "REST API", "Data Structures", "OOP"],
        "resume_text": (
            "RAHUL VERMA\nB.Tech CSE student at CVR College of Engineering, graduating 2026.\n"
            "TECHNICAL SKILLS\nPython, SQL, HTML, CSS, Flask, Git, SQLite, REST API, "
            "Data Structures, OOP\n"
            "PROJECTS\nStudent Result Portal - Python, Flask, SQLite, Git\n"
            "Weather REST API client - Python\n"
            "EXPERIENCE\n3 months web development internship at a local startup\n"
        ),
    },
    {
        "name": "Priya Sharma", "email": "priya@demo.com",
        "college": "CVR College of Engineering",
        "qualification": "B.Tech", "branch": "IT", "graduation_year": 2026,
        "preferred_location": "Hyderabad",
        "min_stipend": 12000, "max_stipend": 25000,
        "phone": "9000000002",
        "experience_months": 6,
        "projects_text": "E-commerce storefront in React with a Node.js and MongoDB "
                         "backend.\nPortfolio website using HTML, CSS and JavaScript.",
        "skills": ["Python", "SQL", "Git", "REST API", "JavaScript", "HTML", "CSS",
                   "React", "MongoDB", "Node.js"],
        "resume_text": (
            "PRIYA SHARMA\nB.Tech IT, CVR College of Engineering, 2026.\n"
            "SKILLS\nPython, SQL, Git, REST API, JavaScript, HTML, CSS, React, MongoDB, "
            "Node.js\nPROJECTS\nE-commerce storefront - React, Node.js, MongoDB\n"
            "EXPERIENCE\n6 months frontend internship\n"
        ),
    },
    {
        "name": "Arjun Reddy", "email": "arjun@demo.com",
        "college": "CVR College of Engineering",
        "qualification": "B.Tech", "branch": "ECE", "graduation_year": 2026,
        "preferred_location": "Hyderabad",
        "min_stipend": 8000, "max_stipend": 15000,
        "phone": "9000000003",
        "resume_file": "sample_resume_ece.pdf",
        "experience_months": 2,
        "projects_text": "Line-following robot using Embedded C on an 8051 board.\n"
                         "Sensor data logger written in Python with Excel reporting.",
        "skills": ["C", "C++", "Java", "Python", "SQL", "Excel", "MATLAB",
                   "Embedded C", "IoT", "Git", "Data Structures"],
        "resume_text": (
            "ARJUN REDDY\nB.Tech ECE, CVR College of Engineering, 2026.\n"
            "SKILLS\nC, C++, Java, Python, SQL, Excel, MATLAB, Embedded C, IoT, Git\n"
            "PROJECTS\nLine following robot - Embedded C\nSensor data logger - Python, Excel\n"
            "EXPERIENCE\n2 months hardware lab internship\n"
        ),
    },
    {
        "name": "Sneha Iyer", "email": "sneha@demo.com",
        "college": "CVR College of Engineering",
        "qualification": "B.Tech", "branch": "CSE", "graduation_year": 2025,
        "preferred_location": "Bangalore",
        "min_stipend": 15000, "max_stipend": 30000,
        "phone": "9000000004",
        "resume_file": "sample_resume_data_science.pdf",
        "experience_months": 6,
        "projects_text": "Customer churn prediction with Scikit-learn and Pandas.\n"
                         "Sales forecasting notebook using Statistics and Data "
                         "Visualization in Python.",
        "skills": ["Python", "Machine Learning", "Pandas", "NumPy", "Scikit-learn",
                   "SQL", "Statistics", "Data Visualization", "Git"],
        "resume_text": (
            "SNEHA IYER\nB.Tech CSE, 2025.\nSKILLS\nPython, Machine Learning, Pandas, "
            "NumPy, Scikit-learn, SQL, Statistics, Data Visualization, Git\n"
            "PROJECTS\nCustomer churn prediction - Scikit-learn, Pandas\n"
            "EXPERIENCE\n6 months data science internship\n"
        ),
    },
    {
        "name": "Karthik Nair", "email": "karthik@demo.com",
        "college": "St. Ann's College", "qualification": "MCA", "branch": "CSE",
        "graduation_year": 2026, "preferred_location": "Chennai",
        "min_stipend": 12000, "max_stipend": 20000,
        "phone": "9000000005",
        "experience_months": 0,
        "projects_text": "Library management system in Java with Spring Boot and MySQL.",
        "skills": ["Java", "Spring Boot", "MySQL", "OOP", "Git", "HTML", "CSS", "DBMS"],
        "resume_text": (
            "KARTHIK NAIR\nMCA, St. Ann's College, 2026.\nSKILLS\nJava, Spring Boot, "
            "MySQL, OOP, Git, HTML, CSS, DBMS\nPROJECTS\nLibrary management system - "
            "Java, Spring Boot, MySQL\n"
        ),
    },
    {
        "name": "Ananya Gupta", "email": "ananya@demo.com",
        "college": "CVR College of Engineering",
        "qualification": "B.Tech", "branch": "IT", "graduation_year": 2027,
        "preferred_location": "Remote",
        "min_stipend": 8000, "max_stipend": 15000,
        "phone": "9000000006",
        "experience_months": 0,
        "projects_text": "Redesigned the college fest website in Figma, then built the "
                         "landing page in HTML, CSS and JavaScript.",
        "skills": ["HTML", "CSS", "JavaScript", "React", "Figma", "UI/UX Design", "Git"],
        "resume_text": (
            "ANANYA GUPTA\nB.Tech IT, 2027.\nSKILLS\nHTML, CSS, JavaScript, React, "
            "Figma, UI/UX Design, Git\nPROJECTS\nCollege fest website - Figma, HTML, CSS\n"
        ),
    },
    {
        "name": "Vikram Singh", "email": "vikram@demo.com",
        "college": "Government Engineering College",
        "qualification": "B.Tech", "branch": "EEE", "graduation_year": 2026,
        "preferred_location": "Pune",
        "min_stipend": 8000, "max_stipend": 14000,
        "phone": "9000000007",
        "experience_months": 0,
        "projects_text": "Solar inverter monitoring prototype using Embedded C and IoT "
                         "sensors, results analysed in Excel.",
        "skills": ["C", "Embedded C", "MATLAB", "IoT", "Excel", "Communication"],
        "resume_text": (
            "VIKRAM SINGH\nB.Tech EEE, 2026.\nSKILLS\nC, Embedded C, MATLAB, IoT, Excel\n"
            "PROJECTS\nSolar inverter monitoring - Embedded C, IoT\n"
        ),
    },
]


# ---------------------------------------------------------------------------
# ACADEMIA
# ---------------------------------------------------------------------------
ACADEMIA = [
    {
        "name": "Dr. Meera Rao", "email": "dean@cvr.edu.in",
        "college_name": "CVR College of Engineering",
        "department": "Training & Placement Cell",
        "contact": "placements@cvr.edu.in",
    },
]


# ---------------------------------------------------------------------------
# COURSES  (suggested when a skill is missing)
# ---------------------------------------------------------------------------
# (skill, title, provider, url, level, duration, is_free)
COURSES = [
    ("Flask", "Flask Official Quickstart Tutorial", "Flask Docs",
     "https://flask.palletsprojects.com/en/stable/quickstart/", "Beginner", "4 hours", 1),
    ("Flask", "Python Flask Full Course", "freeCodeCamp",
     "https://www.freecodecamp.org/news/tag/flask/", "Beginner", "8 hours", 1),
    ("Git", "Git Handbook", "GitHub Docs",
     "https://docs.github.com/en/get-started/using-git/about-git", "Beginner", "3 hours", 1),
    ("GitHub", "Introduction to GitHub", "GitHub Skills",
     "https://skills.github.com/", "Beginner", "2 hours", 1),
    ("SQL", "Intro to SQL", "Kaggle Learn",
     "https://www.kaggle.com/learn/intro-to-sql", "Beginner", "3 hours", 1),
    ("SQL", "SQL Tutorial", "W3Schools",
     "https://www.w3schools.com/sql/", "Beginner", "6 hours", 1),
    ("Python", "Python for Everybody", "freeCodeCamp",
     "https://www.freecodecamp.org/learn/scientific-computing-with-python/",
     "Beginner", "20 hours", 1),
    ("Docker", "Docker Getting Started", "Docker Docs",
     "https://docs.docker.com/get-started/", "Beginner", "5 hours", 1),
    ("AWS", "AWS Cloud Practitioner Essentials", "AWS Skill Builder",
     "https://explore.skillbuilder.aws/", "Beginner", "12 hours", 1),
    ("Azure", "Azure Fundamentals", "Microsoft Learn",
     "https://learn.microsoft.com/en-us/training/paths/azure-fundamentals/",
     "Beginner", "10 hours", 1),
    ("Machine Learning", "Intro to Machine Learning", "Kaggle Learn",
     "https://www.kaggle.com/learn/intro-to-machine-learning", "Beginner", "6 hours", 1),
    ("Scikit-learn", "Scikit-learn Getting Started", "Scikit-learn Docs",
     "https://scikit-learn.org/stable/getting_started.html", "Intermediate", "4 hours", 1),
    ("Deep Learning", "Intro to Deep Learning", "Kaggle Learn",
     "https://www.kaggle.com/learn/intro-to-deep-learning", "Intermediate", "5 hours", 1),
    ("TensorFlow", "TensorFlow Beginner Tutorials", "TensorFlow",
     "https://www.tensorflow.org/tutorials", "Intermediate", "8 hours", 1),
    ("PyTorch", "PyTorch Learn the Basics", "PyTorch",
     "https://pytorch.org/tutorials/beginner/basics/intro.html", "Intermediate", "6 hours", 1),
    ("Pandas", "Pandas Course", "Kaggle Learn",
     "https://www.kaggle.com/learn/pandas", "Beginner", "4 hours", 1),
    ("NumPy", "NumPy Absolute Basics", "NumPy Docs",
     "https://numpy.org/doc/stable/user/absolute_beginners.html", "Beginner", "3 hours", 1),
    ("Power BI", "Power BI Learning Paths", "Microsoft Learn",
     "https://learn.microsoft.com/en-us/training/powerplatform/power-bi",
     "Beginner", "8 hours", 1),
    ("Tableau", "Tableau Free Training Videos", "Tableau",
     "https://www.tableau.com/learn/training/", "Beginner", "6 hours", 1),
    ("Excel", "Excel Basics", "Microsoft Support",
     "https://support.microsoft.com/en-us/excel", "Beginner", "5 hours", 1),
    ("React", "React Official Tutorial", "React Docs",
     "https://react.dev/learn", "Intermediate", "10 hours", 1),
    ("JavaScript", "JavaScript Guide", "MDN Web Docs",
     "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide",
     "Beginner", "12 hours", 1),
    ("Node.js", "Node.js Getting Started", "Node.js Docs",
     "https://nodejs.org/en/learn", "Intermediate", "8 hours", 1),
    ("MongoDB", "MongoDB Basics", "MongoDB University",
     "https://learn.mongodb.com/", "Beginner", "6 hours", 1),
    ("PostgreSQL", "PostgreSQL Tutorial", "PostgreSQL Docs",
     "https://www.postgresql.org/docs/current/tutorial.html", "Beginner", "5 hours", 1),
    ("MySQL", "MySQL Tutorial", "MySQL Docs",
     "https://dev.mysql.com/doc/mysql-tutorial-excerpt/en/", "Beginner", "5 hours", 1),
    ("Linux", "Linux Command Line Basics", "Ubuntu Tutorials",
     "https://ubuntu.com/tutorials/command-line-for-beginners", "Beginner", "4 hours", 1),
    ("Kubernetes", "Kubernetes Basics", "Kubernetes Docs",
     "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "Advanced", "8 hours", 1),
    ("CI/CD", "GitHub Actions Quickstart", "GitHub Docs",
     "https://docs.github.com/en/actions/quickstart", "Intermediate", "4 hours", 1),
    ("Jenkins", "Jenkins Getting Started", "Jenkins Docs",
     "https://www.jenkins.io/doc/pipeline/tour/getting-started/", "Intermediate", "5 hours", 1),
    ("REST API", "REST API Tutorial", "MDN Web Docs",
     "https://developer.mozilla.org/en-US/docs/Web/HTTP", "Beginner", "4 hours", 1),
    ("Django", "Django Getting Started", "Django Docs",
     "https://docs.djangoproject.com/en/stable/intro/tutorial01/",
     "Intermediate", "10 hours", 1),
    ("Spring Boot", "Spring Boot Guides", "Spring",
     "https://spring.io/guides", "Intermediate", "10 hours", 1),
    ("Java", "Java Tutorials", "Oracle Docs",
     "https://docs.oracle.com/javase/tutorial/", "Beginner", "15 hours", 1),
    ("Kotlin", "Kotlin Basics", "Kotlin Docs",
     "https://kotlinlang.org/docs/getting-started.html", "Beginner", "6 hours", 1),
    ("Cybersecurity", "Cyber Security Tutorial", "TryHackMe",
     "https://tryhackme.com/", "Beginner", "10 hours", 0),
    ("Computer Networks", "Computer Networks Course", "NPTEL",
     "https://nptel.ac.in/courses", "Intermediate", "12 weeks", 1),
    ("Selenium", "Selenium Getting Started", "Selenium Docs",
     "https://www.selenium.dev/documentation/webdriver/getting_started/",
     "Intermediate", "5 hours", 1),
    ("Software Testing", "Software Testing Fundamentals", "NPTEL",
     "https://nptel.ac.in/courses", "Beginner", "8 weeks", 1),
    ("Figma", "Figma Learn", "Figma",
     "https://help.figma.com/hc/en-us/categories/360002051613", "Beginner", "4 hours", 1),
    ("UI/UX Design", "UX Design Foundations", "Google UX (Coursera)",
     "https://www.coursera.org/professional-certificates/google-ux-design",
     "Beginner", "3 months", 0),
    ("Generative AI", "Generative AI Learning Path", "Microsoft Learn",
     "https://learn.microsoft.com/en-us/training/", "Intermediate", "8 hours", 1),
    ("NLP", "NLP Course", "Hugging Face",
     "https://huggingface.co/learn/nlp-course", "Intermediate", "12 hours", 1),
    ("OpenCV", "OpenCV Python Tutorials", "OpenCV Docs",
     "https://docs.opencv.org/4.x/d6/d00/tutorial_py_root.html",
     "Intermediate", "8 hours", 1),
    ("Computer Vision", "Computer Vision Course", "Kaggle Learn",
     "https://www.kaggle.com/learn/computer-vision", "Intermediate", "5 hours", 1),
    ("Statistics", "Statistics Fundamentals", "Khan Academy",
     "https://www.khanacademy.org/math/statistics-probability", "Beginner", "10 hours", 1),
    ("Data Visualization", "Data Visualization", "Kaggle Learn",
     "https://www.kaggle.com/learn/data-visualization", "Beginner", "4 hours", 1),
    ("Data Analysis", "Data Analysis with Python", "freeCodeCamp",
     "https://www.freecodecamp.org/learn/data-analysis-with-python/",
     "Beginner", "12 hours", 1),
    ("DBMS", "Database Management Systems", "NPTEL",
     "https://nptel.ac.in/courses", "Intermediate", "12 weeks", 1),
    ("Data Structures", "Data Structures and Algorithms", "NPTEL",
     "https://nptel.ac.in/courses", "Intermediate", "12 weeks", 1),
    ("Embedded C", "Embedded C Programming", "NPTEL",
     "https://nptel.ac.in/courses", "Intermediate", "8 weeks", 1),
    ("IoT", "Introduction to IoT", "NPTEL",
     "https://nptel.ac.in/courses", "Beginner", "8 weeks", 1),
    ("MATLAB", "MATLAB Onramp", "MathWorks",
     "https://matlabacademy.mathworks.com/", "Beginner", "2 hours", 1),
    ("Digital Marketing", "Fundamentals of Digital Marketing", "Google Digital Garage",
     "https://learndigital.withgoogle.com/digitalgarage", "Beginner", "40 hours", 1),
    ("Content Writing", "Technical Writing Courses", "Google",
     "https://developers.google.com/tech-writing", "Beginner", "4 hours", 1),
    ("SQLite", "SQLite Tutorial", "SQLite Docs",
     "https://www.sqlite.org/quickstart.html", "Beginner", "2 hours", 1),
    ("HTML", "HTML Basics", "MDN Web Docs",
     "https://developer.mozilla.org/en-US/docs/Learn/HTML", "Beginner", "6 hours", 1),
    ("CSS", "CSS Basics", "MDN Web Docs",
     "https://developer.mozilla.org/en-US/docs/Learn/CSS", "Beginner", "8 hours", 1),
    ("OOP", "Object Oriented Programming", "NPTEL",
     "https://nptel.ac.in/courses", "Beginner", "8 weeks", 1),
    ("Operating Systems", "Operating Systems Course", "NPTEL",
     "https://nptel.ac.in/courses", "Intermediate", "12 weeks", 1),
    ("Communication", "Effective Communication", "Coursera",
     "https://www.coursera.org/", "Beginner", "4 weeks", 0),
    ("Jira", "Jira Getting Started", "Atlassian",
     "https://www.atlassian.com/software/jira/guides", "Beginner", "2 hours", 1),
    ("Redis", "Redis Getting Started", "Redis Docs",
     "https://redis.io/docs/latest/develop/get-started/", "Intermediate", "3 hours", 1),
]


# ---------------------------------------------------------------------------
# DEMO APPLICATIONS  (student email, internship title, status)
# The match_score stored is calculated by the live engine, not typed in here.
# ---------------------------------------------------------------------------
APPLICATIONS = [
    ("rahul@demo.com", "Python Developer Intern", "Shortlisted"),
    ("rahul@demo.com", "Flask Web Intern", "Applied"),
    ("priya@demo.com", "Python Developer Intern", "Under Review"),
    ("priya@demo.com", "Full Stack Web Development Intern", "Selected"),
    ("arjun@demo.com", "Embedded Systems Intern", "Applied"),
    ("arjun@demo.com", "Database Intern (SQL)", "Rejected"),
    ("sneha@demo.com", "Machine Learning Intern", "Shortlisted"),
    ("sneha@demo.com", "Data Science Intern (Remote)", "Selected"),
    ("karthik@demo.com", "Java Backend Intern", "Applied"),
    ("ananya@demo.com", "UI/UX Design Intern", "Shortlisted"),
    ("ananya@demo.com", "Frontend Developer Intern", "Applied"),
    ("vikram@demo.com", "Embedded Systems Intern", "Under Review"),
]


# ---------------------------------------------------------------------------
# The seeding routine
# ---------------------------------------------------------------------------

def is_seeded(conn):
    """True if demo data is already present (so we never double-insert)."""
    row = query_one(conn, "SELECT COUNT(*) AS n FROM users")
    return bool(row and row["n"])


def _attach_sample_resume(student_id, sample_filename):
    """
    Copy one of the generated sample PDFs into uploads/ so the demo student's
    "Open my resume" link works. Returns the stored filename, or None if the
    sample has not been generated yet (tools/make_sample_resume.py).
    """
    if not sample_filename:
        return None
    source = os.path.join(SAMPLE_DIR, sample_filename)
    if not os.path.exists(source):
        return None
    stored_name = f"student{student_id}_demo_{sample_filename}"
    try:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        shutil.copyfile(source, os.path.join(UPLOAD_DIR, stored_name))
    except OSError:
        return None
    return stored_name


def _create_user(conn, name, email, role):
    cursor = execute(
        conn,
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, generate_password_hash(DEMO_PASSWORD), role),
    )
    return cursor.lastrowid


def seed(conn, verbose=True):
    """Insert every demo record. Assumes the tables already exist."""
    log = print if verbose else (lambda *a, **k: None)

    # ---- 1. the skill dictionary becomes rows in `skills` ----
    for name in rp.all_skill_names():
        get_or_create_skill(conn, name, rp.skill_category(name))
    log(f"  skills ................ {len(rp.all_skill_names())}")

    # ---- 2. companies ----
    company_ids = {}
    for company in COMPANIES:
        user_id = _create_user(conn, company["name"], company["email"], "company")
        cursor = execute(
            conn,
            """INSERT INTO companies (user_id, company_name, industry, website, location, about)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, company["company_name"], company["industry"], company["website"],
             company["location"], company["about"]),
        )
        company_ids[company["email"]] = cursor.lastrowid
    log(f"  companies ............. {len(COMPANIES)}")

    # ---- 3. internships + their skills ----
    internship_ids = {}
    for internship in INTERNSHIPS:
        cursor = execute(
            conn,
            """INSERT INTO internships
               (company_id, title, description, domain, location, stipend_min, stipend_max,
                duration_months, qualification, openings, is_active, is_demo)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1)""",
            (company_ids[internship["company_email"]], internship["title"],
             internship["description"], internship["domain"], internship["location"],
             internship["stipend_min"], internship["stipend_max"],
             internship["duration_months"], internship["qualification"],
             internship["openings"]),
        )
        internship_id = cursor.lastrowid
        internship_ids[internship["title"]] = internship_id
        for importance in ("required", "preferred"):
            for skill_name in internship.get(importance, []):
                canonical = rp.normalize_skill(skill_name)
                skill_id = get_or_create_skill(conn, canonical, rp.skill_category(canonical))
                execute(
                    conn,
                    """INSERT OR IGNORE INTO internship_skills
                       (internship_id, skill_id, importance) VALUES (?, ?, ?)""",
                    (internship_id, skill_id, importance),
                )
    log(f"  internships ........... {len(INTERNSHIPS)}")

    # ---- 4. students + their skills ----
    student_ids = {}
    for student in STUDENTS:
        user_id = _create_user(conn, student["name"], student["email"], "student")
        cursor = execute(
            conn,
            """INSERT INTO student_profiles
               (user_id, college, qualification, branch, graduation_year,
                preferred_location, min_stipend, max_stipend, phone,
                experience_months, projects_text, resume_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, student["college"], student["qualification"], student["branch"],
             student["graduation_year"], student["preferred_location"],
             student["min_stipend"], student["max_stipend"], student["phone"],
             student["experience_months"], student["projects_text"],
             student["resume_text"]),
        )
        student_id = cursor.lastrowid
        student_ids[student["email"]] = student_id

        # Give some demo students a real file on disk, so the resume link works.
        stored = _attach_sample_resume(student_id, student.get("resume_file"))
        if stored:
            execute(conn, "UPDATE student_profiles SET resume_filename = ? WHERE id = ?",
                    (stored, student_id))

        for skill_name in student["skills"]:
            canonical = rp.normalize_skill(skill_name)
            skill_id = get_or_create_skill(conn, canonical, rp.skill_category(canonical))
            execute(
                conn,
                """INSERT OR IGNORE INTO student_skills (student_id, skill_id, source)
                   VALUES (?, ?, 'resume')""",
                (student_id, skill_id),
            )
    log(f"  students .............. {len(STUDENTS)}")

    # ---- 5. academia ----
    for entry in ACADEMIA:
        user_id = _create_user(conn, entry["name"], entry["email"], "academia")
        execute(
            conn,
            """INSERT INTO academia (user_id, college_name, department, contact)
               VALUES (?, ?, ?, ?)""",
            (user_id, entry["college_name"], entry["department"], entry["contact"]),
        )
    log(f"  academia accounts ..... {len(ACADEMIA)}")

    # ---- 6. courses ----
    added_courses = 0
    for skill_name, title, provider, url, level, duration, is_free in COURSES:
        canonical = rp.normalize_skill(skill_name)
        skill_id = get_or_create_skill(conn, canonical, rp.skill_category(canonical))
        if skill_id is None:
            continue
        execute(
            conn,
            """INSERT INTO courses (skill_id, title, provider, url, level, duration, is_free)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (skill_id, title, provider, url, level, duration, is_free),
        )
        added_courses += 1
    log(f"  courses ............... {added_courses}")

    # ---- 7. applications, scored by the REAL engine ----
    from database import internship_skill_map, student_skill_names
    from recommendation import score_match

    added_applications = 0
    for email, title, status in APPLICATIONS:
        student_id = student_ids.get(email)
        internship_id = internship_ids.get(title)
        if not student_id or not internship_id:
            continue
        student = query_one(conn, "SELECT * FROM student_profiles WHERE id = ?", (student_id,))
        internship = query_one(conn, "SELECT * FROM internships WHERE id = ?", (internship_id,))
        match = score_match(
            student, internship,
            student_skill_names(conn, student_id),
            internship_skill_map(conn, internship_id),
        )
        execute(
            conn,
            """INSERT OR IGNORE INTO applications
               (internship_id, student_id, status, match_score) VALUES (?, ?, ?, ?)""",
            (internship_id, student_id, status, match["score_exact"]),
        )
        added_applications += 1
    log(f"  applications .......... {added_applications}")

    # ---- 8. saved internships (a couple, so the Saved page is not empty) ----
    for email, title in [("rahul@demo.com", "DevOps Intern"),
                         ("rahul@demo.com", "AI / Generative AI Intern"),
                         ("priya@demo.com", "Backend Developer Intern (Django)")]:
        student_id = student_ids.get(email)
        internship_id = internship_ids.get(title)
        if student_id and internship_id:
            execute(
                conn,
                """INSERT OR IGNORE INTO saved_internships (student_id, internship_id)
                   VALUES (?, ?)""",
                (student_id, internship_id),
            )

    # ---- 9. pre-compute each student's skill gaps ----
    from recommendation import recommend_for_student, refresh_skill_gaps
    for email, student_id in student_ids.items():
        student = query_one(conn, "SELECT * FROM student_profiles WHERE id = ?", (student_id,))
        recommendations = recommend_for_student(conn, student, use_ml=False)
        refresh_skill_gaps(conn, student_id, recommendations)
    log(f"  skill gap rows ........ computed for {len(student_ids)} students")
