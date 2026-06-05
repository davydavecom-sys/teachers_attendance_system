import streamlit as st
import psycopg2
from psycopg2 import extras
import os
import datetime

from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ---------------------------------------------------------
# DATABASE INITIALIZATION
# ---------------------------------------------------------
def init_database():
    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url and "SUPABASE_DB_URL" in st.secrets:
        db_url = st.secrets["SUPABASE_DB_URL"]
    if not db_url:
        st.error("❌ Critical: SUPABASE_DB_URL connection credentials string missing.")
        st.stop()

    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    cursor.execute("CREATE TABLE IF NOT EXISTS teachers (tsc_no TEXT PRIMARY KEY, name TEXT NOT NULL);")
    cursor.execute("CREATE TABLE IF NOT EXISTS classes (id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE);")
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS subject_assignments (
            id SERIAL PRIMARY KEY,
            class_id INTEGER REFERENCES classes(id) ON DELETE CASCADE,
            subject_name TEXT,
            teacher_tsc TEXT REFERENCES teachers(tsc_no) ON DELETE SET NULL,
            UNIQUE(class_id, subject_name)
        );"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS timetable (
            id SERIAL PRIMARY KEY,
            class_id INTEGER REFERENCES classes(id) ON DELETE CASCADE,
            day_of_week TEXT,
            lesson_number INTEGER,
            subject TEXT,
            UNIQUE(class_id, day_of_week, lesson_number)
        );"""
    )
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS attendance_log (
            id SERIAL PRIMARY KEY,
            timetable_id INTEGER REFERENCES timetable(id) ON DELETE CASCADE,
            date TEXT,
            subject_name TEXT,
            time_in TEXT,
            time_out TEXT,
            assignment_given TEXT,
            status TEXT,
            reason_absent TEXT,
            UNIQUE(timetable_id, date, subject_name)
        );"""
    )
    conn.commit()
    return conn, cursor

conn, cursor = init_database()

# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------
REST_BLOCKS = {"BREAK", "LUNCH", "TEA BREAK", "TEA", "FREE"}

# Elective split keys → individual subject codes
ELECTIVE_SPLITS = {
    "HIST/COMP/AGR":                    ["HISTO", "COMP", "AGRIC"],
    "CRE CSL":                          ["CRE", "CSL"],
    "CRE BIO CSL":                      ["CRE", "BIO", "CSL"],
    "HIS MAT":                          ["HIS", "MAT"],
    "GE STO":                           ["GEO", "HIS"],
    "PHY KIS":                          ["PHY", "KIS"],
    "CRE BIO":                          ["CRE", "BIO"],
    "CHE M":                            ["CHEM", "MAT"],
    "M CHE":                            ["MAT", "CHEM"],
    "HISTO GEO":                        ["HISTO", "GEO"],
    "PHY CRE":                          ["PHY", "CRE"],
    "PE ICT":                           ["PE", "ICT"],
    "CSL ENG":                          ["CSL", "ENG"],
    "CH/FREN":                          ["CHEM", "CRE"],
    "MAT HS":                           ["MAT", "HIS"],        # Note: in some classes MAT HS = single maths/history subject. Context-dependent.
    "HS MAT":                           ["HIS", "MAT"],
    "GE O/HI STO":                      ["GEO", "HIS"],
    "AYK IE":                           ["COMP", "AGRIC"],
    "CRE PHY":                          ["CRE", "PHY"],
    "ENG CRE":                          ["ENG", "CRE"],
    "CH/ FREN COMP S/BST/ AGRIC":       ["CHEM", "CRE", "COMP", "AGRIC"],
    "AGRIC S/BST/ FREN CH COMP":        ["AGRIC", "CRE", "CHEM", "COMP"],
    "AGRIC S/BST FREN CH COMP":         ["AGRIC", "CRE", "CHEM", "COMP"],
}

# NOTE: "MAT HS" is used in the timetable as a STANDALONE subject label
# (Mathematics / History combined stream), NOT as a split elective.
# Remove it from ELECTIVE_SPLITS so it is treated as a single trackable subject.
# Only add it back if your school actually splits it into two tracked subjects.
del ELECTIVE_SPLITS["MAT HS"]
del ELECTIVE_SPLITS["HS MAT"]

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

def get_dates_for_week(target_date):
    start = target_date - datetime.timedelta(days=target_date.weekday())
    return {WEEKDAYS[i]: (start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)}

# ---------------------------------------------------------
# MASTER TIMETABLE DATA  (synced from Timetable.pdf)
#
# 13 entries per day in this order:
#   slot1, slot2, "TEA BREAK", slot3, slot4, "BREAK",
#   slot5, slot6, "LUNCH", slot7, slot8, slot9, slot10
#
# Lesson times:
#   1=08:00  2=08:40  TEA=10:00  3=09:20  4=10:20
#   BREAK=11:40  5=11:00  6=11:50  LUNCH=13:10
#   7=12:30  8=14:00  9=14:40  10=15:20
#
# "FREE" = no lesson that period (blank in PDF). Filtered like BREAK/LUNCH.
# ---------------------------------------------------------
MASTER_GRIDS = {

    # ── GRADE 10 STEM  (PDF page 1) ──────────────────────────
    "10 Stem": {
        "Monday":    ["FREE",    "PPI",    "TEA BREAK", "G.S",     "MAT HS",  "BREAK",
                      "CH/ FREN COMP S/BST/ AGRIC", "BIO",  "LUNCH", "ENG",    "CRE",    "CSL",    "FREE"],
        "Tuesday":   ["FREE",    "C.P",    "TEA BREAK", "PE",      "ENG",     "BREAK",
                      "CH/ FREN COMP S/BST/ AGRIC", "KIS",  "LUNCH", "CRE BIO CSL", "FREE", "MAT HS", "FREE"],
        "Wednesday": ["FREE",    "MAT HS", "TEA BREAK", "CRE",     "C.P",     "BREAK",
                      "CH/ FREN COMP S/BST/ AGRIC", "CHEM", "LUNCH", "BIO",    "PHY",    "CHEM",   "MAT HS"],
        "Thursday":  ["FREE",    "MAT HS", "TEA BREAK", "CRE",     "KIS",     "BREAK",
                      "CH/ FREN COMP S/BST/ AGRIC", "ICT",  "LUNCH", "FREE",   "C.P",    "CSL ENG","FREE"],
        "Friday":    ["FREE",    "PE",     "TEA BREAK", "ICT",     "CH/ FREN COMP S/BST/ AGRIC", "BREAK",
                      "MAT HS",  "BIO",    "LUNCH",     "FREE",    "CRE",     "C.P",    "ENG"],
    },

    # ── GRADE 10 SOCIAL SCIENCE  (PDF page 2) ────────────────
    "10 Social Science": {
        "Monday":    ["FREE",    "PPI",    "TEA BREAK", "AYK IE",  "GE O/HI STO", "BREAK",
                      "MAT HS",  "ICT",    "LUNCH",     "ENG",     "FREE",    "PE",     "FREE"],
        "Tuesday":   ["FREE",    "KIS",    "TEA BREAK", "B.P",     "MAT HS",  "BREAK",
                      "AYK IE",  "CRE ENG","LUNCH",     "GE O/HI STO", "CSL", "PE",     "FREE"],
        "Wednesday": ["FREE",    "CSL",    "TEA BREAK", "MAT HS",  "KIS",     "BREAK",
                      "ENG",     "CRE",    "LUNCH",     "GE O/HI STO", "ENG", "PE",     "FREE"],
        "Thursday":  ["FREE",    "MAT HS", "TEA BREAK", "AYK IE",  "GE O/HI STO", "BREAK",
                      "B.P",     "FREE",   "LUNCH",     "ENG",     "CRE",    "G.S",    "FREE"],
        "Friday":    ["FREE",    "CRE",    "TEA BREAK", "GE O/HI STO", "ICT", "BREAK",
                      "MAT HS",  "B.P",    "LUNCH",     "AYK IE",  "ENG",    "CSL",    "FREE"],
    },

    # ── FORM 3S  (PDF page 3) ─────────────────────────────────
    "3S": {
        "Monday":    ["MAT HS",  "PHY",    "TEA BREAK", "KIS",     "CHE M",   "BREAK",
                      "HISTO GEO","HISTO GEO","LUNCH",  "ENG",     "CRE",     "LS",     "BIO"],
        "Tuesday":   ["MAT HS",  "ENG",    "TEA BREAK", "HISTO GEO","AGRIC S/BST FREN CH COMP","BREAK",
                      "KIS",     "CRE BIO","LUNCH",     "P.E",     "HIS",     "GEO",    "FREE"],
        "Wednesday": ["ENG",     "MAT HS", "TEA BREAK", "AGRIC S/BST FREN CH COMP","KIS","BREAK",
                      "CHE M",   "MAT HS", "LUNCH",     "HISTO GEO","ENG",    "BIO",    "FREE"],
        "Thursday":  ["MAT HS",  "HISTO GEO","TEA BREAK","AGRIC S/BST FREN CH COMP","ENG","BREAK",
                      "MAT HS",  "ENG",    "LUNCH",     "BIO",     "CHEM",    "PHY",    "MAT HS"],
        "Friday":    ["CHE M",   "ENG",    "TEA BREAK", "HISTO GEO","AGRIC S/BST FREN CH COMP","BREAK",
                      "ENG",     "P.E",    "LUNCH",     "HISTO GEO","KIS",    "BIO",    "HISTO GEO"],
    },

    # ── FORM 3M  (PDF page 4) ─────────────────────────────────
    "3M": {
        "Monday":    ["BIO",     "PHY",    "TEA BREAK", "MAT HS",  "ENG",     "BREAK",
                      "P.E",     "BIO",    "LUNCH",     "KIS",     "HISTO GEO","CHE M", "ENG"],
        "Tuesday":   ["BIO",     "MAT HS", "TEA BREAK", "MAT HS",  "AGRIC S/BST FREN CH COMP","BREAK",
                      "CRE",     "KIS",    "LUNCH",     "PHY",     "MAT HS",  "ENG",    "HISTO GEO"],
        "Wednesday": ["MAT HS",  "LS",     "TEA BREAK", "AGRIC S/BST FREN CH COMP","KIS","BREAK",
                      "ENG",     "MAT HS", "LUNCH",     "CRE",     "BIO",     "CHEM",   "MAT HS"],
        "Thursday":  ["ENG",     "HISTO GEO","TEA BREAK","AGRIC S/BST FREN CH COMP","MAT HS","BREAK",
                      "AGRIC S/BST FREN CH COMP","ENG","LUNCH",   "MAT HS",  "BIO",    "CHEM",   "PHY"],
        "Friday":    ["MAT HS",  "ENG",    "TEA BREAK", "HISTO GEO","AGRIC S/BST FREN CH COMP","BREAK",
                      "AGRIC S/BST FREN CH COMP","KIS","LUNCH",   "HISTO GEO","ENG",   "MAT HS", "PHY"],
    },

    # ── FORM 4S  (PDF page 5) ─────────────────────────────────
    "4S": {
        "Monday":    ["HISTO GEO","CRE",   "TEA BREAK", "CHE M",   "AGRIC S/BST FREN CH COMP","BREAK",
                      "MAT HS",  "KIS",    "LUNCH",     "ENG",     "PHY",     "BIO",    "FREE"],
        "Tuesday":   ["MAT HS",  "ENG",    "TEA BREAK", "AGRIC S/BST FREN CH COMP","MAT HS","BREAK",
                      "PHY",     "BIO",    "LUNCH",     "HISTO GEO","ENG",    "KIS",    "FREE"],
        "Wednesday": ["HISTO GEO","PHY",   "TEA BREAK", "AGRIC S/BST FREN CH COMP","AGRIC S/BST FREN CH COMP","BREAK",
                      "MAT HS",  "BIO",    "LUNCH",     "ENG CRE", "CHEM",   "FREE",   "FREE"],
        "Thursday":  ["LS",      "HISTO GEO","TEA BREAK","PHY",    "AGRIC S/BST FREN CH COMP","BREAK",
                      "ENG",     "FREE",   "LUNCH",     "B.P",     "FREE",    "CRE",    "FREE"],
        "Friday":    ["MAT HS",  "HISTO GEO","TEA BREAK","HISTO GEO","MAT HS","BREAK",
                      "ENG",     "ENG",    "LUNCH",     "KIS",     "BIO",     "PHY",    "CHE M"],
    },

    # ── FORM 4M  (PDF page 6) ─────────────────────────────────
    "4M": {
        "Monday":    ["HISTO GEO","MAT HS","TEA BREAK", "CRE",     "AGRIC S/BST FREN CH COMP","BREAK",
                      "ENG",     "BIO",    "LUNCH",     "KIS",     "PHY",     "CHE M",  "FREE"],
        "Tuesday":   ["ENG",     "MAT HS", "TEA BREAK", "MAT HS",  "AGRIC S/BST FREN CH COMP","BREAK",
                      "CRE PHY", "KIS",    "LUNCH",     "CHEM",    "BIO",     "FREE",   "FREE"],
        "Wednesday": ["HISTO GEO","PHY",   "TEA BREAK", "HISTO GEO","AGRIC S/BST FREN CH COMP","BREAK",
                      "MAT HS",  "MAT HS", "LUNCH",     "ENG",     "KIS",     "BIO",    "CHEM"],
        "Thursday":  ["ENG",     "HISTO GEO","TEA BREAK","AGRIC S/BST FREN CH COMP","MAT HS","BREAK",
                      "PHY",     "ENG",    "LUNCH",     "MAT HS",  "BIO",     "CHEM",   "KIS"],
        "Friday":    ["ENG",     "HISTO GEO","TEA BREAK","AGRIC S/BST FREN CH COMP","MAT HS","BREAK",
                      "AGRIC S/BST FREN CH COMP","CHE M","LUNCH",  "ENG",     "KIS",    "BIO",    "FREE"],
    },
}

# ---------------------------------------------------------
# PER-CLASS SUBJECT → TEACHER ASSIGNMENTS  (synced from PDF)
# For split electives, the primary (first-listed) teacher is stored.
# Individual sub-subjects within a split inherit from subject_assignments.
# ---------------------------------------------------------
CLASS_TEACHER_ASSIGNMENTS = {
    "10 Stem": [
        ("MAT HS",  "T.7"),   ("KIS",     "T.4"),   ("ENG",    "T.5"),
        ("BIO",     "T.15"),  ("PHY",     "T.18"),  ("CRE",    "T.10"),
        ("CHEM",    "T.2"),   ("ICT",     "T.17"),  ("PE",     "T.12"),
        ("CSL",     "T.16"),  ("PPI",     "T.1"),   ("G.S",    "T.7"),
        ("C.P",     "T.6"),   ("COMP",    "T.17"),  ("AGRIC",  "T.1"),
        # Split elective sub-subjects
        ("HISTO",   "T.5"),   ("GEO",     "T.12"),  ("HIS",    "T.13"),
        ("LS",      "T.1"),   ("B.P",     "T.15"),
    ],
    "10 Social Science": [
        ("MAT HS",  "T.6"),   ("KIS",     "T.4"),   ("ENG",    "T.9"),
        ("CRE",     "T.10"),  ("ICT",     "T.17"),  ("PE",     "T.11"),
        ("CSL",     "T.16"),  ("PPI",     "T.1"),   ("B.P",    "T.15"),
        ("G.S",     "T.16"),  ("GEO",     "T.12"),  ("HIS",    "T.14"),
        ("COMP",    "T.9"),   ("AGRIC",   "T.16"),
        # Split sub-subjects
        ("HISTO",   "T.14"),  ("LS",      "T.1"),   ("C.P",    "T.17"),
    ],
    "3S": [
        ("MAT HS",  "T.11"),  ("KIS",     "T.12"),  ("ENG",    "T.3"),
        ("BIO",     "T.19"),  ("PHY",     "T.18"),  ("CRE",    "T.14"),
        ("CHEM",    "T.18"),  ("LS",      "T.11"),  ("HISTO",  "T.11"),
        ("GEO",     "T.10"),  ("CHE M",   "T.18"),  ("P.E",    "T.11"),
        ("HIS",     "T.13"),  ("COMP",    "T.17"),  ("AGRIC",  "T.1"),
        # HISTO GEO split
        ("HISTO GEO","T.11"),
    ],
    "3M": [
        ("MAT HS",  "T.11"),  ("KIS",     "T.12"),  ("ENG",    "T.5"),
        ("BIO",     "T.19"),  ("PHY",     "T.18"),  ("CRE",    "T.10"),
        ("CHEM",    "T.18"),  ("LS",      "T.12"),  ("HISTO",  "T.11"),
        ("GEO",     "T.10"),  ("CHE M",   "T.6"),   ("P.E",    "T.5"),
        ("HIS",     "T.13"),  ("COMP",    "T.17"),  ("AGRIC",  "T.1"),
        ("HISTO GEO","T.11"),
    ],
    "4S": [
        ("MAT HS",  "T.7"),   ("KIS",     "T.9"),   ("ENG",    "T.9"),
        ("BIO",     "T.15"),  ("PHY",     "T.18"),  ("CRE",    "T.2"),
        ("CHEM",    "T.6"),   ("LS",      "T.1"),   ("HISTO",  "T.13"),
        ("GEO",     "T.1"),   ("CHE M",   "T.6"),   ("P.E",    "T.11"),
        ("HIS",     "T.13"),  ("COMP",    "T.16"),  ("AGRIC",  "T.1"),
        ("B.P",     "T.15"),  ("HISTO GEO","T.13"),
    ],
    "4M": [
        ("MAT HS",  "T.7"),   ("KIS",     "T.4"),   ("ENG",    "T.3"),
        ("BIO",     "T.15"),  ("PHY",     "T.18"),  ("CRE",    "T.10"),
        ("CHEM",    "T.6"),   ("HISTO",   "T.13"),  ("GEO",    "T.1"),
        ("CHE M",   "T.6"),   ("P.E",     "T.11"),  ("HIS",    "T.13"),
        ("COMP",    "T.17"),  ("AGRIC",   "T.1"),   ("B.P",    "T.15"),
        ("LS",      "T.1"),   ("HISTO GEO","T.13"),
    ],
}

ALL_SUBJECTS = sorted({
    "MAT", "ENG", "KIS", "CRE", "HIS", "HISTO", "GEO", "ICT", "PE", "P.E", "CSL",
    "BIO", "CHEM", "PHY", "COMP", "AGRIC", "PPI", "B.P", "G.S", "C.P", "LS",
    "CHE M", "MAT HS", "HISTO GEO", "GE O/HI STO", "MAT", "HIS",
})

# ---------------------------------------------------------
# STREAMLIT APP
# ---------------------------------------------------------
st.set_page_config(page_title="TSC TLAR Dashboard", layout="wide")
st.title("🏫 TSC TLAR — School Management Web Application")

menu = st.sidebar.radio(
    "Navigation Menu",
    ["Attendance Log", "Teachers & Assignments", "System Data Importer", "Print & Export Sheets"]
)

# ══════════════════════════════════════════════════════════════
# VIEW 1 — ATTENDANCE LOG
# ══════════════════════════════════════════════════════════════
if menu == "Attendance Log":
    st.subheader("📝 Daily Lesson Attendance Logging and Updates")
    st.write("Displaying valid instructional lessons only. Rest blocks and free periods are filtered automatically.")

    cursor.execute("SELECT name FROM classes ORDER BY name;")
    classes_list = [r[0] for r in cursor.fetchall()]

    if not classes_list:
        st.info("No classes found. Go to 'System Data Importer' to set up the school structure.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            selected_class = st.selectbox("Select Class / Grade", classes_list)
        with col2:
            selected_date = st.date_input("Target Date", datetime.date.today())

        day_name = selected_date.strftime("%A")
        date_str = selected_date.strftime("%Y-%m-%d")

        if day_name in ["Saturday", "Sunday"]:
            st.error(f"⚠️ Selected date falls on a weekend ({day_name}). Register runs Monday to Friday only.")
        else:
            cursor.execute(
                """SELECT t.id, t.lesson_number, t.subject FROM timetable t
                   JOIN classes c ON t.class_id = c.id
                   WHERE c.name = %s AND t.day_of_week = %s ORDER BY t.lesson_number;""",
                (selected_class, day_name)
            )
            slots = cursor.fetchall()

            if not slots:
                st.warning(f"No timetable entries found for {day_name} in {selected_class}.")
            else:
                st.write(f"### {day_name}, {date_str} — {selected_class}")
                form_payloads = {}
                lesson_index = 1

                for (tt_id, original_num, raw_subject) in slots:
                    if raw_subject.strip().upper() in REST_BLOCKS:
                        continue

                    active_subjects = ELECTIVE_SPLITS.get(raw_subject, [raw_subject])
                    is_split = len(active_subjects) > 1

                    header = f"📖 Lesson {lesson_index}: {raw_subject}"
                    if is_split:
                        header = f"🔀 Lesson {lesson_index}: {raw_subject} — [Parallel Elective Split]"

                    with st.expander(header, expanded=True):
                        for sub in active_subjects:
                            cursor.execute(
                                """SELECT t.name FROM subject_assignments sa
                                   JOIN teachers t ON sa.teacher_tsc = t.tsc_no
                                   JOIN classes c ON sa.class_id = c.id
                                   WHERE c.name = %s AND sa.subject_name = %s;""",
                                (selected_class, sub)
                            )
                            t_row = cursor.fetchone()
                            teacher_name = t_row[0] if t_row else "⚠️ No Teacher Assigned"

                            cursor.execute(
                                """SELECT time_in, time_out, assignment_given, status, reason_absent
                                   FROM attendance_log
                                   WHERE timetable_id = %s AND date = %s AND subject_name = %s;""",
                                (tt_id, date_str, sub)
                            )
                            existing = cursor.fetchone()

                            d_status = existing[3] if existing else "Unmarked"
                            d_in     = existing[0] if existing else ""
                            d_out    = existing[1] if existing else ""
                            d_assg   = existing[2] if existing else "No"
                            d_reason = existing[4] if existing else ""

                            st.markdown(f"**{sub}** — Teacher: *{teacher_name}*")
                            c1, c2, c3, c4, c5 = st.columns(5)
                            with c1:
                                status = st.selectbox(
                                    "Status",
                                    ["Present", "Absent", "Recovered", "Unmarked"],
                                    index=["Present", "Absent", "Recovered", "Unmarked"].index(d_status),
                                    key=f"status_{tt_id}_{sub}"
                                )
                            with c2:
                                time_in = st.text_input("Time In", value=d_in, placeholder="e.g. 08:20", key=f"in_{tt_id}_{sub}")
                            with c3:
                                time_out = st.text_input("Time Out", value=d_out, placeholder="e.g. 09:00", key=f"out_{tt_id}_{sub}")
                            with c4:
                                assg = st.selectbox("Assignment", ["No", "Yes"],
                                                    index=["No", "Yes"].index(d_assg),
                                                    key=f"assg_{tt_id}_{sub}")
                            with c5:
                                reason = st.text_input("Notes / Reason", value=d_reason,
                                                       placeholder="Absent reason…", key=f"reason_{tt_id}_{sub}")

                            form_payloads[(tt_id, sub)] = (status, time_in, time_out, assg, reason)
                            if is_split:
                                st.markdown("---")

                    lesson_index += 1

                if st.button("💾 Save / Update Today's Entries", type="primary"):
                    saved = 0
                    for (tt_id, sub), (status, time_in, time_out, assg, reason) in form_payloads.items():
                        cursor.execute(
                            """INSERT INTO attendance_log
                               (timetable_id, date, subject_name, time_in, time_out, assignment_given, status, reason_absent)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                               ON CONFLICT(timetable_id, date, subject_name) DO UPDATE SET
                                  time_in          = EXCLUDED.time_in,
                                  time_out         = EXCLUDED.time_out,
                                  assignment_given = EXCLUDED.assignment_given,
                                  status           = EXCLUDED.status,
                                  reason_absent    = EXCLUDED.reason_absent;""",
                            (tt_id, date_str, sub, time_in.strip(), time_out.strip(), assg, status, reason.strip())
                        )
                        saved += 1
                    conn.commit()
                    st.success(f"✅ Saved {saved} lesson records for {date_str}.")
                    st.rerun()

# ══════════════════════════════════════════════════════════════
# VIEW 2 — TEACHERS & ASSIGNMENTS
# ══════════════════════════════════════════════════════════════
elif menu == "Teachers & Assignments":
    st.subheader("👥 Teacher Registrations & Subject Assignments")
    col1, col2 = st.columns([2, 3])

    with col1:
        st.markdown("#### Register New Teacher")
        new_tsc  = st.text_input("TSC / Short Code:", placeholder="e.g. T.4")
        new_name = st.text_input("Full Name:",        placeholder="e.g. MRS. RUTTO")

        if st.button("Register Teacher"):
            if new_tsc.strip() and new_name.strip():
                try:
                    cursor.execute(
                        "INSERT INTO teachers (tsc_no, name) VALUES (%s, %s);",
                        (new_tsc.strip(), new_name.strip())
                    )
                    conn.commit()
                    st.success(f"Registered {new_name.strip()}")
                    st.rerun()
                except psycopg2.IntegrityError:
                    conn.rollback()
                    st.error("Code already exists in the system.")
            else:
                st.warning("Please fill in both fields.")

        st.markdown("---")
        st.markdown("#### Assign Subject to Teacher")

        cursor.execute("SELECT id, name FROM classes ORDER BY name;")
        classes_mapping = cursor.fetchall()
        cursor.execute("SELECT tsc_no, name FROM teachers ORDER BY name;")
        teachers_mapping = cursor.fetchall()

        if classes_mapping and teachers_mapping:
            c_options = {name: cid for cid, name in classes_mapping}
            t_options = {f"{name} ({tsc})": tsc for tsc, name in teachers_mapping}

            assign_class = st.selectbox("Class", list(c_options.keys()))
            assign_sub   = st.selectbox("Subject", ALL_SUBJECTS)
            assign_tea   = st.selectbox("Teacher", list(t_options.keys()))

            if st.button("Commit Assignment", type="primary"):
                cursor.execute(
                    """INSERT INTO subject_assignments (class_id, subject_name, teacher_tsc)
                       VALUES (%s, %s, %s)
                       ON CONFLICT(class_id, subject_name) DO UPDATE SET teacher_tsc = EXCLUDED.teacher_tsc;""",
                    (c_options[assign_class], assign_sub, t_options[assign_tea])
                )
                conn.commit()
                st.success("Assignment saved.")
                st.rerun()

    with col2:
        st.markdown("#### Current Subject Assignment Matrix")
        cursor.execute(
            """SELECT c.name, sa.subject_name, t.name
               FROM subject_assignments sa
               JOIN classes c ON sa.class_id = c.id
               JOIN teachers t ON sa.teacher_tsc = t.tsc_no
               ORDER BY c.name, sa.subject_name;"""
        )
        matrix = cursor.fetchall()
        if matrix:
            import pandas as pd
            df = pd.DataFrame(matrix, columns=["Class", "Subject", "Teacher"])
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("No assignments yet. Run the importer or assign manually above.")

# ══════════════════════════════════════════════════════════════
# VIEW 3 — SYSTEM DATA IMPORTER
# ══════════════════════════════════════════════════════════════
elif menu == "System Data Importer":
    st.subheader("⚙️ Automated System Setup — Import from Timetable.pdf")
    st.write("Imports the full 13-slot timetable and per-class teacher assignments directly from the PDF source data.")

    # ── Staff Roster ──────────────────────────────────────────
    if st.button("📋 Import School Staff Roster", use_container_width=True):
        teachers_list = [
            ("T.1",  "DOROTHY"),           ("T.2",  "ONDIEKI"),
            ("T.3",  "AGESAH"),            ("T.4",  "MRS. RUTTO"),
            ("T.5",  "NATEMBEYA"),         ("T.6",  "ROTICH"),
            ("T.7",  "CHEBERYON"),         ("T.9",  "KORIR"),
            ("T.10", "KEMEI"),             ("T.11", "WEKESA"),
            ("T.12", "CHERUIYOT"),         ("T.13", "EMMANUEL"),
            ("T.14", "LINDA"),             ("T.15", "TUWEI"),
            ("T.16", "KIPNGETICH"),        ("T.17", "MUNIALO"),
            ("T.18", "LEAH CHEPCHIRCHIR"),("T.19", "DAISY"),
        ]
        for code, name in teachers_list:
            cursor.execute(
                "INSERT INTO teachers (tsc_no, name) VALUES (%s, %s) ON CONFLICT (tsc_no) DO UPDATE SET name = EXCLUDED.name;",
                (code, name)
            )
        conn.commit()
        st.success(f"✅ {len(teachers_list)} staff records synchronised.")

    st.write(" ")

    # ── Full Timetable + Teacher Assignments ──────────────────
    if st.button("📅 Import Full Timetable Grid + Teacher Assignments (PDF-Synced)", use_container_width=True):
        target_classes = list(MASTER_GRIDS.keys())
        total_slots = 0
        total_assignments = 0

        for c_name in target_classes:
            # Upsert class
            cursor.execute(
                "INSERT INTO classes (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;", (c_name,)
            )
            conn.commit()
            cursor.execute("SELECT id FROM classes WHERE name = %s;", (c_name,))
            class_id = cursor.fetchone()[0]

            # Clear old data for this class
            cursor.execute(
                "DELETE FROM attendance_log WHERE timetable_id IN (SELECT id FROM timetable WHERE class_id = %s);",
                (class_id,)
            )
            cursor.execute("DELETE FROM timetable WHERE class_id = %s;",          (class_id,))
            cursor.execute("DELETE FROM subject_assignments WHERE class_id = %s;", (class_id,))

            # Insert per-class subject→teacher assignments from PDF
            assignments = CLASS_TEACHER_ASSIGNMENTS.get(c_name, [])
            for sub, tsc in assignments:
                try:
                    cursor.execute(
                        "INSERT INTO subject_assignments (class_id, subject_name, teacher_tsc) VALUES (%s, %s, %s);",
                        (class_id, sub, tsc)
                    )
                    total_assignments += 1
                except psycopg2.IntegrityError:
                    conn.rollback()

            # Insert timetable slots
            class_grid = MASTER_GRIDS[c_name]
            for day in WEEKDAYS:
                for idx, subject in enumerate(class_grid[day]):
                    cursor.execute(
                        "INSERT INTO timetable (class_id, day_of_week, lesson_number, subject) VALUES (%s, %s, %s, %s);",
                        (class_id, day, idx + 1, subject)
                    )
                    total_slots += 1

        conn.commit()
        st.success(
            f"✅ Import complete — {total_slots} timetable slots and "
            f"{total_assignments} subject assignments loaded across {len(target_classes)} classes."
        )
        st.info(
            "Teacher assignments are now sourced directly from the PDF timetable. "
            "Each class has its own subject→teacher mapping (e.g. MAT HS in 3M = T.11 WEKESA, "
            "MAT HS in 4S = T.7 CHEBERYON)."
        )

# ══════════════════════════════════════════════════════════════
# VIEW 4 — PRINT & EXPORT
# ══════════════════════════════════════════════════════════════
elif menu == "Print & Export Sheets":
    st.subheader("🖨️ Generate Official 2-Page Weekly W-TLAR Register")
    st.write("Produces a landscape PDF with exactly 10 instructional lesson rows per page.")

    cursor.execute("SELECT name FROM classes ORDER BY name;")
    classes_list = [r[0] for r in cursor.fetchall()]

    if not classes_list:
        st.info("No classes found. Run the importer first.")
    else:
        col_c, col_d = st.columns(2)
        with col_c:
            exp_class = st.selectbox("Class", classes_list, key="exp_class")
        with col_d:
            exp_date = st.date_input("Week Date", datetime.date.today(), key="exp_date")

        week_dates    = get_dates_for_week(exp_date)
        mon_date_str  = week_dates["Monday"]
        fri_date_str  = week_dates["Friday"]
        date_list     = list(week_dates.values())

        st.markdown("---")
        st.markdown(f"### 📋 Weekly Preview — **{exp_class}** ({mon_date_str} → {fri_date_str})")

        # Weekly teacher performance summary
        cursor.execute(
            f"""SELECT
                    tea.name,
                    COUNT(CASE WHEN a.status = 'Present'  THEN 1 END),
                    COUNT(CASE WHEN a.status = 'Absent'   AND COALESCE(a.reason_absent,'') != '' THEN 1 END),
                    COUNT(CASE WHEN a.status = 'Absent'   AND COALESCE(a.reason_absent,'') = '' THEN 1 END),
                    COUNT(CASE WHEN a.status = 'Recovered' THEN 1 END)
               FROM teachers tea
               LEFT JOIN subject_assignments sa ON tea.tsc_no = sa.teacher_tsc
               LEFT JOIN classes c  ON sa.class_id = c.id AND c.name = %s
               LEFT JOIN timetable t ON c.id = t.class_id
               LEFT JOIN attendance_log a ON t.id = a.timetable_id
                    AND a.subject_name = sa.subject_name
                    AND a.date IN (%s,%s,%s,%s,%s)
               GROUP BY tea.tsc_no, tea.name
               ORDER BY tea.name;""",
            [exp_class] + date_list
        )
        weekly_metrics = cursor.fetchall()

        if weekly_metrics:
            import pandas as pd
            st.markdown("**Cumulative Weekly Teacher Performance**")
            df_m = pd.DataFrame(
                weekly_metrics,
                columns=["Teacher", "Attended", "Missed (With Permission)", "Missed (No Permission)", "Recovered"]
            )
            st.dataframe(df_m, use_container_width=True, hide_index=True)

        # ── PDF Generation ────────────────────────────────────
        if st.button("📄 Generate Official 2-Page W-TLAR PDF", type="primary", use_container_width=True):
            filename = f"Weekly_TLAR_{exp_class.replace(' ','_')}_{mon_date_str}.pdf"

            doc = SimpleDocTemplate(
                filename, pagesize=landscape(letter),
                rightMargin=16, leftMargin=16, topMargin=16, bottomMargin=16
            )
            story  = []
            styles = getSampleStyleSheet()

            title_style   = ParagraphStyle('T', parent=styles['Heading1'],  fontSize=12, leading=14, alignment=1, textColor=colors.HexColor("#1A237E"))
            section_style = ParagraphStyle('S', parent=styles['Heading2'],  fontSize=10, leading=13, spaceBefore=4, spaceAfter=3, textColor=colors.HexColor("#1A237E"))
            meta_style    = ParagraphStyle('M', parent=styles['Normal'],    fontSize=9,  leading=12)
            grid_style    = ParagraphStyle('G', parent=styles['Normal'],    fontSize=7.5,leading=10)
            sum_style     = ParagraphStyle('U', parent=styles['Normal'],    fontSize=8,  leading=11)
            sig_style     = ParagraphStyle('I', parent=styles['Normal'],    fontSize=8,  leading=11)

            def make_header(class_name, mon, fri):
                elems = []
                elems.append(Paragraph("<b>TEACHERS SERVICE COMMISSION</b>", title_style))
                elems.append(Paragraph("<b>WEEKLY TEACHER LESSON ATTENDANCE REGISTER (W-TLAR)</b>", title_style))
                elems.append(Spacer(1, 3))
                meta_rows = [
                    [Paragraph(f"<b>Institution:</b> St. Michael Senior School — Kipsombe", meta_style),
                     Paragraph("<b>Form Ref:</b> TSC/QAS/TPAD/W-TLAR/2026/V4", meta_style)],
                    [Paragraph(f"<b>Class Stream:</b> {class_name}", meta_style),
                     Paragraph(f"<b>Period:</b> {mon} to {fri}", meta_style)],
                ]
                t = Table(meta_rows, colWidths=[385, 385])
                t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
                elems.append(t)
                return elems

            # PAGE 1 — Lesson grid
            story += make_header(exp_class, mon_date_str, fri_date_str)
            story.append(Paragraph("<b>SECTION A: WEEKLY LESSON TRACKING MATRIX</b>", section_style))

            grid_data = [["Lesson", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]]

            for l_num in range(1, 11):
                row = [f"Lesson {l_num}"]
                for day in WEEKDAYS:
                    d_str = week_dates[day]
                    cursor.execute(
                        """SELECT t.id, t.subject FROM timetable t
                           JOIN classes c ON t.class_id = c.id
                           WHERE c.name = %s AND t.day_of_week = %s ORDER BY t.lesson_number;""",
                        (exp_class, day)
                    )
                    academic = [s for s in cursor.fetchall() if s[1].strip().upper() not in REST_BLOCKS]

                    if len(academic) < l_num:
                        row.append(Paragraph("<font color='grey'>—</font>", grid_style))
                        continue

                    tt_id, raw_sub = academic[l_num - 1]
                    subs = ELECTIVE_SPLITS.get(raw_sub, [raw_sub])
                    lines = []
                    for sub in subs:
                        cursor.execute(
                            """SELECT status, time_in, time_out, assignment_given
                               FROM attendance_log
                               WHERE timetable_id=%s AND date=%s AND subject_name=%s;""",
                            (tt_id, d_str, sub)
                        )
                        log = cursor.fetchone()
                        if log:
                            st_val, ti, to, asg = log
                            ti  = ti if ti and ti.strip() else "--:--"
                            to  = to if to and to.strip() else "--:--"
                            lines.append(f"<b>{sub}</b>: {st_val}<br/>⏱ {ti}–{to} | 📝{asg}")
                        else:
                            lines.append(f"<b>{sub}</b>: Unmarked<br/>⏱ --:-- | 📝No")
                    row.append(Paragraph("<br/>".join(lines), grid_style))

                grid_data.append(row)

            matrix_tbl = Table(grid_data, colWidths=[62, 143, 143, 143, 143, 143])
            matrix_tbl.setStyle(TableStyle([
                ('BACKGROUND', (0,0),(-1,0), colors.HexColor("#EEEEEE")),
                ('FONTNAME',   (0,0),(-1,0), 'Helvetica-Bold'),
                ('ALIGN',      (0,0),(-1,-1),'CENTER'),
                ('ALIGN',      (1,1),(-1,-1),'LEFT'),
                ('VALIGN',     (0,0),(-1,-1),'MIDDLE'),
                ('GRID',       (0,0),(-1,-1), 0.5, colors.grey),
                ('TOPPADDING', (0,0),(-1,-1), 2.5),
                ('BOTTOMPADDING',(0,0),(-1,-1),2.5),
            ]))
            story.append(matrix_tbl)
            story.append(PageBreak())

            # PAGE 2 — Staff summary
            story += make_header(exp_class, mon_date_str, fri_date_str)
            story.append(Paragraph("<b>SECTION B: CUMULATIVE MASTER TEACHER PERFORMANCE SUMMARY</b>", section_style))

            summary_rows = [[
                Paragraph("<b>Teacher Name</b>",              sum_style),
                Paragraph("<b>Lessons Attended</b>",          sum_style),
                Paragraph("<b>Missed (With Permission)</b>",  sum_style),
                Paragraph("<b>Missed (No Permission)</b>",    sum_style),
                Paragraph("<b>Recovered</b>",                 sum_style),
            ]]
            for m in weekly_metrics:
                summary_rows.append([Paragraph(str(x), sum_style) for x in m])

            sum_tbl = Table(summary_rows, colWidths=[290, 120, 120, 120, 120])
            sum_tbl.setStyle(TableStyle([
                ('BACKGROUND',  (0,0),(-1,0), colors.HexColor("#E0F2F1")),
                ('ALIGN',       (0,0),(-1,-1),'CENTER'),
                ('VALIGN',      (0,0),(-1,-1),'MIDDLE'),
                ('GRID',        (0,0),(-1,-1), 0.5, colors.grey),
                ('TOPPADDING',  (0,0),(-1,-1), 1.5),
                ('BOTTOMPADDING',(0,0),(-1,-1),1.5),
            ]))
            story.append(sum_tbl)
            story.append(Spacer(1, 6))

            sig_rows = [
                [Paragraph("<b>Compiled By:</b> Class Secretary Monitor<br/>Sign: _______________________", sig_style),
                 Paragraph("<b>Verified By:</b> Deputy Head of Institution<br/>Sign: _______________________", sig_style)],
                [Paragraph("Date: _______________________", sig_style),
                 Paragraph("Date: _______________________", sig_style)],
                [Paragraph("<br/><b>Confirmed By:</b> Head of Institution<br/>Sign: _______________________<br/>Date: _______________________", sig_style),
                 Paragraph("<br/><b>Official Stamp:</b><br/>[ Place Stamp Here ]", sig_style)],
            ]
            sig_tbl = Table(sig_rows, colWidths=[385, 385])
            sig_tbl.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),1)]))
            story.append(sig_tbl)

            doc.build(story)

            with open(filename, "rb") as f:
                st.download_button(
                    label="📥 Download W-TLAR PDF",
                    data=f,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )
