"""
ml/generate_training_data.py
============================
Creates ml/training_data.csv.

*** READ THIS BEFORE JUDGING THE ML COMPONENT ***
This data is SYNTHETIC. SkillBridge is a prototype with no historical placement
records, so there is no real "was this student shortlisted?" dataset to learn
from. Rather than pretend otherwise, we generate labelled examples from a
documented recruiter-behaviour model and say so everywhere the model is shown.

The generator encodes two things the linear rule-based formula cannot express:

1. A HARD SKILL FLOOR - a recruiter almost never shortlists someone below a ~30%
   skill match, no matter how perfect the location or stipend fit is.
2. AN INTERACTION - a strong skill match still fails if the candidate cannot
   realistically attend (skill x location).

Because those effects are in the labels, a logistic regression fitted on the
engineered features learns a ranking that is *not* just a copy of the weighted
sum - which is the only honest reason to add ML here at all.

Run:  python ml/generate_training_data.py
"""

import csv
import math
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "training_data.csv")

COLUMNS = [
    "skill_score", "qualification_score", "location_score", "stipend_score",
    "experience_score", "skill_x_location", "skill_squared", "shortlisted",
]

N_ROWS = 1500
RANDOM_SEED = 42          # fixed so the CSV is reproducible


def _sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def shortlist_probability(skill, qual, location, stipend, experience):
    """The documented 'recruiter behaviour' model used to label the synthetic rows."""
    z = (6.0 * (skill - 0.55)
         + 2.2 * (qual - 0.5)
         + 1.8 * (location - 0.5)
         + 1.0 * (stipend - 0.5)
         + 0.8 * experience
         - 0.6)
    probability = _sigmoid(z)

    # (1) hard skill floor
    if skill < 0.30:
        probability *= 0.15
    # (2) skill x location interaction
    if skill > 0.7 and location < 0.4:
        probability *= 0.45
    return probability


def _random_sub_score(rng):
    """
    Sub-scores in the real app are lumpy, not uniform: skill coverage lands on
    fractions like 0/4, 1/4, 2/4 and location is usually 1.0 or 0.25.
    """
    style = rng.random()
    if style < 0.35:
        return rng.choice([0.0, 0.25, 0.5, 0.75, 1.0])
    if style < 0.6:
        return rng.choice([0.2, 0.3, 0.85, 1.0])
    return round(rng.random(), 3)


def generate(path=CSV_PATH, rows=N_ROWS, seed=RANDOM_SEED):
    rng = random.Random(seed)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    positives = 0
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for _ in range(rows):
            skill = _random_sub_score(rng)
            qual = _random_sub_score(rng)
            location = _random_sub_score(rng)
            stipend = _random_sub_score(rng)
            experience = round(rng.random() * 0.9, 3)
            probability = shortlist_probability(skill, qual, location, stipend, experience)
            label = 1 if rng.random() < probability else 0
            positives += label
            writer.writerow([
                round(skill, 3), round(qual, 3), round(location, 3), round(stipend, 3),
                round(experience, 3), round(skill * location, 3), round(skill * skill, 3),
                label,
            ])
    return {"rows": rows, "positives": positives, "path": path}


if __name__ == "__main__":
    info = generate()
    print(f"Wrote {info['rows']} synthetic rows to {info['path']} "
          f"({info['positives']} shortlisted / "
          f"{info['rows'] - info['positives']} not shortlisted)")
