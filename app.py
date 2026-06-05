# ============================================================
# DROP-IN REPLACEMENTS FOR YOUR STREAMLIT APP
# Apply these two changes to sync the timetable with the PDF.
# ============================================================

# ---------------------------------------------------------------
# CHANGE 1: Expand REST_BLOCKS to also filter "FREE" (blank) slots
# Replace the existing line:
#   REST_BLOCKS = {"BREAK", "LUNCH", "TEA BREAK", "TEA"}
# With:
# ---------------------------------------------------------------
REST_BLOCKS = {"BREAK", "LUNCH", "TEA BREAK", "TEA", "FREE"}


# ---------------------------------------------------------------
# CHANGE 2: Add "GE STO" split to ELECTIVE_SPLITS if not present.
# The PDF uses "GE O/HI STO" for Social Science — map it correctly.
# Also note: "C.P" = Computer (Comp), treat as a standalone subject.
# The elective split key used in the PDF for the big group is:
#   "CH/ FREN COMP S/BST/ AGRIC" (already in ELECTIVE_SPLITS)
#   "AGRIC S/BST/ FREN CH COMP"  (already in ELECTIVE_SPLITS)
#
# Add these additional entries to ELECTIVE_SPLITS:
# ---------------------------------------------------------------
ELECTIVE_SPLITS_ADDITIONS = {
    "GE O/HI STO": ["GEO", "HIS"],        # Grade 10 Social Science variant spelling
    "AYK IE": ["COMP", "AGRIC"],           # Teacher-label elective seen in Social Science
    "CRE BIO CSL": ["CRE", "BIO", "CSL"], # (already exists, confirming)
}


# ---------------------------------------------------------------
# CHANGE 3: Full replacement for master_grids inside the importer.
#
# Format per day: 13 entries
#   [s1, s2, "TEA BREAK", s3, s4, "BREAK", s5, s6, "LUNCH", s7, s8, s9, s10]
#
# Slot times:
#   s1=08:00, s2=08:40, s3=09:20, TEA=10:00,
#   s4=10:20, s5=11:00, BREAK=11:40,
#   s6=11:50, s7=12:30, LUNCH=13:10,
#   s8=14:00, s9=14:40, s10=15:20
#
# Source: Timetable.pdf (St Michael Senior School - Kipsombe)
# ---------------------------------------------------------------
master_grids = {

    # ── PAGE 1 ── GRADE 10 STEM ────────────────────────────────
    "10 Stem": {
        "Monday":    ["FREE", "PPI",   "TEA BREAK", "G.S",   "MAT HS", "BREAK", "CH/ FREN COMP S/BST/ AGRIC", "BIO",  "LUNCH", "ENG",       "CRE",   "CSL",   "FREE"],
        "Tuesday":   ["FREE", "C.P",   "TEA BREAK", "PE",    "ENG",    "BREAK", "CH/ FREN COMP S/BST/ AGRIC", "KIS",  "LUNCH", "CRE BIO CSL","FREE",  "MAT HS","FREE"],
        "Wednesday": ["FREE", "MAT HS","TEA BREAK", "CRE",   "C.P",    "BREAK", "CH/ FREN COMP S/BST/ AGRIC", "CHEM", "LUNCH", "BIO",        "PHY",   "CHEM",  "MAT HS"],
        "Thursday":  ["FREE", "MAT HS","TEA BREAK", "CRE",   "KIS",    "BREAK", "CH/ FREN COMP S/BST/ AGRIC", "ICT",  "LUNCH", "FREE",       "C.P",   "CSL ENG","FREE"],
        "Friday":    ["FREE", "PE",    "TEA BREAK", "ICT",   "CH/ FREN COMP S/BST/ AGRIC","BREAK","MAT HS","BIO","LUNCH","FREE",  "CRE",   "C.P",   "ENG"],
    },

    # ── PAGE 2 ── GRADE 10 SOCIAL SCIENCE ─────────────────────
    "10 Social Science": {
        "Monday":    ["FREE", "PPI",    "TEA BREAK", "AYK IE", "GE O/HI STO", "BREAK", "MAT HS", "ICT",  "LUNCH", "ENG",       "KIS",  "PE",    "FREE"],
        "Tuesday":   ["FREE", "KIS",    "TEA BREAK", "B.P",    "MAT HS",      "BREAK", "AYK IE", "CRE ENG","LUNCH","GE O/HI STO","CSL", "PE",    "FREE"],
        "Wednesday": ["FREE", "CSL",    "TEA BREAK", "MAT HS", "KIS",         "BREAK", "ENG",    "CRE",  "LUNCH", "GE O/HI STO","ENG",  "PE",    "FREE"],
        "Thursday":  ["FREE", "MAT HS", "TEA BREAK", "AYK IE", "GE O/HI STO", "BREAK", "B.P",    "FREE", "LUNCH", "ENG",       "CRE",  "G.S",   "FREE"],
        "Friday":    ["FREE", "CRE",    "TEA BREAK", "GE O/HI STO","ICT",     "BREAK", "MAT HS", "B.P",  "LUNCH", "AYK IE",    "ENG",  "CSL",   "FREE"],
    },

    # ── PAGE 3 ── FORM 3S ──────────────────────────────────────
    "3S": {
        "Monday":    ["MAT HS", "PHY",  "TEA BREAK", "KIS",           "CHE M",  "BREAK", "HISTO GEO",       "ENG",   "LUNCH", "CRE",   "LS",    "BIO",   "PHY"],
        "Tuesday":   ["MAT HS", "ENG",  "TEA BREAK", "HISTO GEO",     "ENG",    "BREAK", "AGRIC S/BST/ FREN CH COMP","KIS","LUNCH","CRE","CHEM", "FREE",  "FREE"],
        "Wednesday": ["ENG",    "MAT HS","TEA BREAK", "AGRIC S/BST/ FREN CH COMP","KIS","BREAK","ENG",  "MAT HS","LUNCH","CHE M",  "HISTO GEO","BIO",  "FREE"],
        "Thursday":  ["MAT HS", "HISTO GEO","TEA BREAK","AGRIC S/BST/ FREN CH COMP","ENG","BREAK","MAT HS","ENG","LUNCH","BIO",   "CHEM",  "PHY",   "MAT HS"],
        "Friday":    ["CHE M",  "ENG",  "TEA BREAK", "HISTO GEO",     "AGRIC S/BST/ FREN CH COMP","BREAK","ENG","P.E","LUNCH","HISTO GEO","KIS","BIO",  "HISTO GEO"],
    },

    # ── PAGE 4 ── FORM 3M ──────────────────────────────────────
    "3M": {
        "Monday":    ["BIO",    "PHY",  "TEA BREAK", "MAT HS",        "ENG",    "BREAK", "P.E",    "BIO",   "LUNCH", "KIS",       "HISTO GEO","CHE M", "ENG"],
        "Tuesday":   ["BIO",    "MAT HS","TEA BREAK", "MAT HS",       "AGRIC S/BST/ FREN CH COMP","BREAK","CRE","KIS","LUNCH","PHY","MAT HS",  "ENG",   "HISTO GEO"],
        "Wednesday": ["MAT HS", "LS",   "TEA BREAK", "AGRIC S/BST/ FREN CH COMP","KIS","BREAK","ENG","MAT HS","LUNCH","CRE", "BIO",    "CHEM",  "MAT HS"],
        "Thursday":  ["ENG",    "HISTO GEO","TEA BREAK","AGRIC S/BST/ FREN CH COMP","MAT HS","BREAK","AGRIC S/BST/ FREN CH COMP","ENG","LUNCH","MAT HS","BIO","CHEM","PHY"],
        "Friday":    ["MAT HS", "ENG",  "TEA BREAK", "HISTO GEO",     "AGRIC S/BST/ FREN CH COMP","BREAK","AGRIC S/BST/ FREN CH COMP","KIS","LUNCH","HISTO GEO","ENG","MAT HS","PHY"],
    },

    # ── PAGE 5 ── FORM 4S ──────────────────────────────────────
    "4S": {
        "Monday":    ["HISTO GEO","CRE", "TEA BREAK", "CHE M",        "AGRIC S/BST/ FREN CH COMP","BREAK","MAT HS","KIS","LUNCH","ENG",     "PHY",   "BIO",   "FREE"],
        "Tuesday":   ["MAT HS",  "ENG",  "TEA BREAK", "AGRIC S/BST/ FREN CH COMP","MAT HS","BREAK","PHY","BIO","LUNCH","FREE",     "ENG",   "KIS",   "FREE"],
        "Wednesday": ["HISTO GEO","PHY", "TEA BREAK", "AGRIC S/BST/ FREN CH COMP","AGRIC S/BST/ FREN CH COMP","BREAK","MAT HS","BIO","LUNCH","ENG CRE","CHEM","FREE","FREE"],
        "Thursday":  ["LS",      "HISTO GEO","TEA BREAK","PHY ENG",   "AGRIC S/BST/ FREN CH COMP","BREAK","ENG","FREE","LUNCH","B.P",  "FREE",  "CRE",   "FREE"],
        "Friday":    ["MAT HS",  "HISTO GEO","TEA BREAK","HISTO GEO", "MAT HS",  "BREAK", "ENG",    "ENG",   "LUNCH", "KIS",       "BIO",   "PHY",   "CHE M"],
    },

    # ── PAGE 6 ── FORM 4M ──────────────────────────────────────
    "4M": {
        "Monday":    ["HISTO GEO","MAT HS","TEA BREAK","CRE",         "AGRIC S/BST/ FREN CH COMP","BREAK","ENG","BIO","LUNCH","KIS",       "PHY",   "CHE M", "FREE"],
        "Tuesday":   ["ENG",     "MAT HS","TEA BREAK", "MAT HS",      "AGRIC S/BST/ FREN CH COMP","BREAK","CRE PHY","KIS","LUNCH","CHEM","BIO",    "FREE",  "FREE"],
        "Wednesday": ["HISTO GEO","PHY",  "TEA BREAK", "HISTO GEO",   "AGRIC S/BST/ FREN CH COMP","BREAK","MAT HS","MAT HS","LUNCH","ENG","KIS",   "BIO",   "CHEM"],
        "Thursday":  ["ENG",     "HISTO GEO","TEA BREAK","AGRIC S/BST/ FREN CH COMP","MAT HS","BREAK","PHY","ENG","LUNCH","MAT HS","BIO",  "CHEM",  "KIS"],
        "Friday":    ["ENG",     "HISTO GEO","TEA BREAK","AGRIC S/BST/ FREN CH COMP","MAT HS","BREAK","AGRIC S/BST/ FREN CH COMP","CHE M","LUNCH","ENG","KIS","BIO","FREE"],
    },
}

# ---------------------------------------------------------------
# CHANGE 4: Add new subjects to the subject assignment dropdown
# In the Teachers & Assignments view, update the assign_sub selectbox
# to include "C.P", "G.S", "PPI" if not already present.
# Replace the existing list:
#
#   ["MAT","ENG","KIS","CRE","HIS","HISTO","GEO","ICT","PE","CSL",
#    "BIO","CHEM","PHY","COMP","AGRIC","PPI","B.P","G.S"]
#
# With:
# ---------------------------------------------------------------
SUBJECT_LIST = [
    "MAT", "ENG", "KIS", "CRE", "HIS", "HISTO", "GEO", "ICT", "PE", "CSL",
    "BIO", "CHEM", "PHY", "COMP", "AGRIC", "PPI", "B.P", "G.S", "C.P", "LS",
    "P.E", "CHE M", "MAT HS", "HISTO GEO"
]

# ---------------------------------------------------------------
# CHANGE 5: Add teacher fallback assignments for new subjects
# Replace or extend teacher_fallbacks to include:
# ---------------------------------------------------------------
teacher_fallbacks = [
    ("MAT", "T.6"),    ("ENG", "T.5"),    ("KIS", "T.4"),    ("BIO", "T.15"),
    ("CHEM", "T.2"),   ("PHY", "T.18"),   ("CRE", "T.10"),   ("HIS", "T.13"),
    ("PE", "T.11"),    ("P.E", "T.11"),   ("ICT", "T.17"),   ("CSL", "T.16"),
    ("LS", "T.1"),     ("HISTO GEO", "T.13"), ("GE STO", "T.12"),
    ("HISTO", "T.5"),  ("COMP", "T.17"),  ("AGRIC", "T.1"),  ("PPI", "T.1"),
    ("B.P", "T.15"),   ("G.S", "T.16"),   ("C.P", "T.17"),   ("MAT HS", "T.6"),
    ("CHE M", "T.2"),  ("GEO", "T.12"),   ("PPI", "T.1"),
]
