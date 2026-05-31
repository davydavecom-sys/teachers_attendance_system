import streamlit as st
import sqlite3
import os
import datetime

# ReportLab imports for generating clean physical weekly documents
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ---------------------------------------------------------
# DATABASE STRUCTURAL INITIALIZATION
# ---------------------------------------------------------
def init_database():
    conn = sqlite3.connect("tlar_school.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    cursor.execute("CREATE TABLE IF NOT EXISTS teachers (tsc_no TEXT PRIMARY KEY, name TEXT NOT NULL)")
    cursor.execute("CREATE TABLE IF NOT EXISTS classes (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)")
    
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS subject_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER,
            subject_name TEXT,
            teacher_tsc TEXT,
            FOREIGN KEY(class_id) REFERENCES classes(id),
            FOREIGN KEY(teacher_tsc) REFERENCES teachers(tsc_no),
            UNIQUE(class_id, subject_name)
        )"""
    )
    
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS timetable (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            class_id INTEGER, 
            day_of_week TEXT, 
            lesson_number INTEGER, 
            subject TEXT,
            FOREIGN KEY(class_id) REFERENCES classes(id),
            UNIQUE(class_id, day_of_week, lesson_number)
        )"""
    )
    
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS attendance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            timetable_id INTEGER, 
            date TEXT, 
            subject_name TEXT,
            time_in TEXT, 
            time_out TEXT, 
            assignment_given TEXT, 
            status TEXT, 
            reason_absent TEXT,
            FOREIGN KEY(timetable_id) REFERENCES timetable(id),
            UNIQUE(timetable_id, date, subject_name)
        )"""
    )
    conn.commit()
    return conn, cursor

conn, cursor = init_database()

ELECTIVE_SPLITS = {
    "HIST/COMP/AGR": ["HISTO", "COMP", "AGRIC"],
    "CRE CSL": ["CRE", "CSL"],
    "CRE BIO CSL": ["CRE", "BIO", "CSL"],
    "HIS MAT": ["HIS", "MAT"],
    "GE STO": ["GEO", "HIS"],
    "PHY KIS": ["PHY", "KIS"],
    "CRE BIO": ["CRE", "BIO"],
    "CHE M": ["CHEM", "MAT"],
    "M CHE": ["MAT", "CHEM"],
    "HISTO GEO": ["HISTO", "GEO"],
    "PHY CRE": ["PHY", "CRE"],
    "PE ICT": ["PE", "ICT"],
    "CSL ENG": ["CSL", "ENG"],
    "CH/FREN": ["CHEM", "CRE"]
}

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

def get_dates_for_week(target_date):
    start_of_week = target_date - datetime.timedelta(days=target_date.weekday())
    return {WEEKDAYS[i]: (start_of_week + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)}

# ---------------------------------------------------------
# WEB DASHBOARD INTERFACE
# ---------------------------------------------------------
st.set_page_config(page_title="TSC TLAR Dashboard", layout="wide")
st.title("🏫 TSC TLAR - School Management Web Application")

menu = st.sidebar.radio("Navigation Menu", ["Attendance Log", "Teachers & Assignments", "System Data Importer", "Print & Export Sheets"])

# --- VIEW 1: ATTENDANCE LOG VIEW ---
if menu == "Attendance Log":
    st.subheader("📝 Daily Lesson Attendance Logging and Updates")
    st.write("Displaying structured lessons. Elective splits automatically expand below to log teachers individually.")
    
    cursor.execute("SELECT name FROM classes ORDER BY name")
    classes_list = [r[0] for r in cursor.fetchall()]
    
    if not classes_list:
        st.info("No classes found. Go to the 'System Data Importer' tab to set up default school structures.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            selected_class = st.selectbox("Select Target Class/Grade", classes_list)
        with col2:
            selected_date = st.date_input("Target Date", datetime.date.today())
            
        day_name = selected_date.strftime("%A")
        date_str = selected_date.strftime("%Y-%m-%d")
        
        if day_name in ["Saturday", "Sunday"]:
            st.error(f"⚠️ Selected date falls on a weekend ({day_name}). Official registers are maintained Monday through Friday.")
        else:
            cursor.execute(
                """SELECT t.id, t.lesson_number, t.subject FROM timetable t
                   JOIN classes c ON t.class_id = c.id 
                   WHERE c.name = ? AND t.day_of_week = ? ORDER BY t.lesson_number""",
                (selected_class, day_name)
            )
            slots = cursor.fetchall()
            
            if not slots:
                st.warning(f"No master timetable entries found for {day_name} in this class.")
            else:
                st.write(f"### Grid View for {day_name}, {date_str}")
                form_payloads = {}
                
                for (tt_id, lesson_num, raw_subject) in slots:
                    active_subjects = ELECTIVE_SPLITS.get(raw_subject, [raw_subject])
                    is_split = len(active_subjects) > 1
                    
                    header_label = f"⏰ Lesson {lesson_num}: {raw_subject}"
                    if raw_subject in ["BREAK", "LUNCH", "FREE", "TEA BREAK"]:
                        header_label = f"☕ {raw_subject} — (Rest Block — Lesson {lesson_num})"
                    elif is_split:
                        header_label = f"🔀 Lesson {lesson_num}: {raw_subject} — [Parallel Elective Split Group]"
                        
                    with st.expander(header_label, expanded=True):
                        for sub in active_subjects:
                            cursor.execute(
                                """SELECT t.name FROM subject_assignments sa 
                                   JOIN teachers t ON sa.teacher_tsc = t.tsc_no
                                   JOIN classes c ON sa.class_id = c.id
                                   WHERE c.name = ? AND sa.subject_name = ?""", (selected_class, sub)
                            )
                            t_row = cursor.fetchone()
                            display_teacher = t_row[0] if t_row else "No Instructor Assigned"
                            
                            cursor.execute(
                                """SELECT time_in, time_out, assignment_given, status, reason_absent 
                                   FROM attendance_log WHERE timetable_id = ? AND date = ? AND subject_name = ?""", 
                                (tt_id, date_str, sub)
                            )
                            existing = cursor.fetchone()
                            
                            d_status = existing[3] if existing else "Unmarked"
                            d_in = existing[0] if existing else ""
                            d_out = existing[1] if existing else ""
                            d_assg = existing[2] if existing else "No"
                            d_reason = existing[4] if existing else ""
                            
                            st.markdown(f"**Track: {sub}** (Teacher: *{display_teacher}*)")
                            c1, c2, c3, c4, c5 = st.columns(5)
                            with c1:
                                status = st.selectbox("Status", ["Present", "Absent", "Recovered", "Unmarked"], index=["Present", "Absent", "Recovered", "Unmarked"].index(d_status), key=f"status_{tt_id}_{sub}")
                            with c2:
                                time_in = st.text_input("Time In", value=d_in, placeholder="e.g. 08:20", key=f"in_{tt_id}_{sub}")
                            with c3:
                                time_out = st.text_input("Time Out", value=d_out, placeholder="e.g. 09:00", key=f"out_{tt_id}_{sub}")
                            with c4:
                                assg = st.selectbox("Assignment Given", ["No", "Yes"], index=["No", "Yes"].index(d_assg), key=f"assg_{tt_id}_{sub}")
                            with c5:
                                reason = st.text_input("Reason / Notes", value=d_reason, placeholder="Absent Reason/Notes", key=f"reason_{tt_id}_{sub}")
                                
                            form_payloads[(tt_id, sub)] = (status, time_in, time_out, assg, reason)
                            if is_split:
                                st.markdown("---")
                                
                if st.button("Save / Update Day's Lesson Entries", type="primary"):
                    records_saved = 0
                    for (tt_id, sub), (status, time_in, time_out, assg, reason) in form_payloads.items():
                        cursor.execute(
                            """INSERT INTO attendance_log (timetable_id, date, subject_name, time_in, time_out, assignment_given, status, reason_absent)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                               ON CONFLICT(timetable_id, date, subject_name) DO UPDATE SET
                                  time_in = excluded.time_in,
                                  time_out = excluded.time_out,
                                  assignment_given = excluded.assignment_given,
                                  status = excluded.status,
                                  reason_absent = excluded.reason_absent""",
                            (tt_id, date_str, sub, time_in.strip(), time_out.strip(), assg, status, reason.strip())
                        )
                        records_saved += 1
                    conn.commit()
                    st.success(f"Successfully synchronized {records_saved} lesson tracks for {date_str}!")
                    st.rerun()

# --- VIEW 2: TEACHERS & ASSIGNMENTS PANEL ---
elif menu == "Teachers & Assignments":
    st.subheader("👥 Teacher Registrations & Active Assignments")
    col1, col2 = st.columns([2, 3])
    
    with col1:
        st.markdown("#### Register New Teacher")
        new_tsc = st.text_input("Short Code / TSC No:", placeholder="e.g., T.4")
        new_name = st.text_input("Full Name:", placeholder="e.g., MRS. RUTTO")
        
        if st.button("Register Teacher"):
            if new_tsc.strip() and new_name.strip():
                try:
                    cursor.execute("INSERT INTO teachers (tsc_no, name) VALUES (?, ?)", (new_tsc.strip(), new_name.strip()))
                    conn.commit()
                    st.success(f"Registered {new_name}")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Registration Conflict: Code already exists.")
            else:
                st.warning("Please fill out all fields.")
                
        st.markdown("---")
        st.markdown("#### Assign Subject Teacher Role")
        
        cursor.execute("SELECT id, name FROM classes ORDER BY name")
        classes_mapping = cursor.fetchall()
        cursor.execute("SELECT tsc_no, name FROM teachers ORDER BY name")
        teachers_mapping = cursor.fetchall()
        
        if classes_mapping and teachers_mapping:
            c_options = {name: cid for cid, name in classes_mapping}
            t_options = {f"{name} ({tsc})": tsc for tsc, name in teachers_mapping}
            
            assign_class = st.selectbox("Target Class", list(c_options.keys()))
            assign_sub = st.selectbox("Subject Name", ["MAT", "ENG", "KIS", "CRE", "HIS", "HISTO", "GEO", "ICT", "PE", "CSL", "BIO", "CHEM", "PHY", "COMP", "AGRIC"])
            assign_tea = st.selectbox("Assign Teacher", list(t_options.keys()))
            
            if st.button("Commit Subject Assignment", type="primary"):
                cursor.execute(
                    """INSERT INTO subject_assignments (class_id, subject_name, teacher_tsc) VALUES (?, ?, ?)
                       ON CONFLICT(class_id, subject_name) DO UPDATE SET teacher_tsc = excluded.teacher_tsc""",
                    (c_options[assign_class], assign_sub, t_options[assign_tea])
                )
                conn.commit()
                st.success("Assigned role successfully.")
                st.rerun()

    with col2:
        st.markdown("#### Current Class Subject Matrix Assignments")
        cursor.execute(
            """SELECT c.name, sa.subject_name, t.name FROM subject_assignments sa
               JOIN classes c ON sa.class_id = c.id JOIN teachers t ON sa.teacher_tsc = t.tsc_no
               ORDER BY c.name, sa.subject_name"""
        )
        matrix_data = cursor.fetchall()
        if matrix_data:
            import pandas as pd
            df = pd.DataFrame(matrix_data, columns=["Class / Form", "Subject Name", "Assigned Teacher"])
            st.dataframe(df, use_container_width=True, hide_index=True)

# --- VIEW 3: AUTOMATED DATA IMPORTER ---
elif menu == "System Data Importer":
    st.subheader("⚙️ Automated System Structural Setup Panel")
    st.write("Inject verified schedules containing composite standard elective blocks from Timetable.pdf.")
    
    if st.button("Import School Staff Roster (Teacher numbers list)", use_container_width=True):
        teachers_list = [
            ("T.1", "DOROTHY"), ("T.2", "ONDIEKI"), ("T.12", "CHERUIYOT"), ("T.11", "WEKESA"),
            ("T.3", "AGESAH"), ("T.5", "NATEMBEYA"), ("T.13", "EMMANUEL"), ("T.16", "KIPNGETICH"),
            ("T.17", "MUNIALO"), ("T.9", "KORIR"), ("T.15", "TUWEI"), ("T.6", "ROTICH"),
            ("T.7", "CHEBERYON"), ("T.14", "LINDA"), ("T.10", "KEMEI"), ("T.4", "MRS. RUTTO"),
            ("T.18", "LEAH CHEPCHIRCHIR"), ("T.19", "DAISY")
        ]
        for short_code, name in teachers_list:
            cursor.execute("INSERT OR REPLACE INTO teachers (tsc_no, name) VALUES (?, ?)", (short_code, name))
        conn.commit()
        st.success("Master Roster records synchronization safely completed.")
        
    st.write(" ")
    
    if st.button("Import Complete 10-Lesson Multi-Class Timetable Grid", use_container_width=True):
        target_classes = ["4M", "4S", "3M", "3S", "10 Social Science", "10 Stem"]
        
        master_grids = {
            "10 Stem": {
                "Monday":    ["MAT", "MAT", "TEA BREAK", "KIS", "BIO", "BREAK", "HIS", "KIS", "LUNCH", "CRE CSL"],
                "Tuesday":   ["PE", "ENG", "TEA BREAK", "MAT", "MAT", "BREAK", "KIS", "HIS", "LUNCH", "CRE BIO CSL"],
                "Wednesday": ["MAT", "MAT", "TEA BREAK", "CRE", "ENG", "BREAK", "KIS", "HIS", "LUNCH", "BIO"],
                "Thursday":  ["MAT", "MAT", "TEA BREAK", "CRE", "ENG", "BREAK", "KIS", "HIS", "LUNCH", "ENG"],
                "Friday":    ["PE ICT", "PE ICT", "TEA BREAK", "ENG", "KIS", "BREAK", "HIS", "MAT", "LUNCH", "BIO"]
            },
            "10 Social Science": {
                "Monday":    ["PPI", "KIS", "TEA BREAK", "CSL", "MAT", "BREAK", "HIS MAT", "GE STO", "LUNCH", "PE"],
                "Tuesday":   ["GE STO", "CRE", "TEA BREAK", "HIS MAT", "KIS", "BREAK", "ICT", "ENG", "LUNCH", "PE"],
                "Wednesday": ["GE STO", "KIS", "TEA BREAK", "HIS MAT", "ICT", "BREAK", "ENG", "GE STO", "LUNCH", "PE"],
                "Thursday":  ["KIS", "ENG", "TEA BREAK", "GE STO", "CSL", "BREAK", "B.P", "B.P", "LUNCH", "G.S"],
                "Friday":    ["CRE", "ENG", "TEA BREAK", "ENG", "KIS", "BREAK", "B.P", "B.P", "LUNCH", "CSL"]
            },
            "3S": {
                "Monday":    ["MAT", "MAT", "TEA BREAK", "PHY KIS", "ENG", "BREAK", "HISTO GEO", "HISTO GEO", "LUNCH", "ENG"],
                "Tuesday":   ["ENG", "CRE", "TEA BREAK", "MAT", "MAT", "BREAK", "LS", "CRE BIO", "LUNCH", "P.E"],
                "Wednesday": ["MAT", "MAT", "TEA BREAK", "CHEM", "PHY", "BREAK", "CRE", "MAT", "LUNCH", "CHE M"],
                "Thursday":  ["HISTO GEO", "HISTO GEO", "TEA BREAK", "ENG", "KIS", "BREAK", "ENG", "P.E", "LUNCH", "BIO"],
                "Friday":    ["ENG", "BIO", "TEA BREAK", "HISTO GEO", "PHY KIS", "BREAK", "BIO", "PHY CRE", "LUNCH", "HISTO GEO"]
            },
            "3M": {
                "Monday":    ["BIO", "PHY", "TEA BREAK", "MAT", "ENG", "BREAK", "P.E", "CRE", "LUNCH", "ENG"],
                "Tuesday":   ["BIO", "MAT", "TEA BREAK", "HISTO GEO", "ENG", "BREAK", "CRE", "CHEM", "LUNCH", "PHY"],
                "Wednesday": ["MAT", "LS", "TEA BREAK", "HISTO GEO", "KIS", "BREAK", "ENG", "PHY", "LUNCH", "CRE"],
                "Thursday":  ["ENG", "ENG", "TEA BREAK", "HIST/COMP/AGR", "MAT", "BREAK", "MAT", "BIO", "LUNCH", "CHEM"],
                "Friday":    ["MAT", "ENG", "TEA BREAK", "CHEM", "HIST/COMP/AGR", "BREAK", "BIO", "KIS", "LUNCH", "HISTO GEO"]
            },
            "4S": {
                "Monday":    ["HISTO GEO", "CHE M", "TEA BREAK", "CRE", "MAT", "BREAK", "ENG", "KIS", "LUNCH", "PHY"],
                "Tuesday":   ["MAT", "HISTO GEO", "TEA BREAK", "ST", "LS", "BREAK", "ENG", "KIS", "LUNCH", "BIO"],
                "Wednesday": ["MAT", "ENG", "TEA BREAK", "PHY", "HS MAT", "BREAK", "BIO", "M CHE", "LUNCH", "BIO"],
                "Thursday":  ["ENG", "PHY", "TEA BREAK", "HIST/COMP/AGR", "ENG", "BREAK", "CHEM", "KIS", "LUNCH", "CRE"],
                "Friday":    ["ENG", "KIS", "TEA BREAK", "KIS", "KIS", "BREAK", "P.E", "CRE", "LUNCH", "M CHE"]
            },
            "4M": {
                "Monday":    ["HISTO GEO", "MAT", "TEA BREAK", "CRE", "ENG", "BREAK", "BIO", "KIS", "LUNCH", "PHY"],
                "Tuesday":   ["ENG", "MAT", "TEA BREAK", "PHY", "HISTO GEO", "BREAK", "KIS", "ENG", "LUNCH", "CHEM"],
                "Wednesday": ["HISTO GEO", "PHY", "TEA BREAK", "MAT", "ENG", "BREAK", "MAT", "P.E", "LUNCH", "BIO"],
                "Thursday":  ["MAT", "ENG", "TEA BREAK", "HIST/COMP/AGR", "CRE", "BREAK", "MAT", "ENG", "LUNCH", "BIO"],
                "Friday":    ["ENG", "MAT", "TEA BREAK", "MAT", "ENG", "BREAK", "M CHE", "KIS", "LUNCH", "BIO"]
            }
        }
        
        teacher_fallbacks = [
            ("MAT", "T.6"), ("ENG", "T.5"), ("KIS", "T.4"), ("BIO", "T.15"),
            ("CHEM", "T.2"), ("PHY", "T.18"), ("CRE", "T.10"), ("HIS", "T.13"),
            ("PE", "T.11"), ("ICT", "T.17"), ("CSL", "T.16"), ("LS", "T.1"),
            ("HISTO GEO", "T.13"), ("GE STO", "T.12"), ("HISTO", "T.5"), 
            ("COMP", "T.17"), ("AGRIC", "T.1")
        ]
        
        total_slots_inserted = 0
        for c_name in target_classes:
            cursor.execute("INSERT OR IGNORE INTO classes (name) VALUES (?)", (c_name,))
            conn.commit()
            
            cursor.execute("SELECT id FROM classes WHERE name = ?", (c_name,))
            class_id = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM attendance_log WHERE timetable_id IN (SELECT id FROM timetable WHERE class_id = ?)", (class_id,))
            cursor.execute("DELETE FROM timetable WHERE class_id = ?", (class_id,))
            cursor.execute("DELETE FROM subject_assignments WHERE class_id = ?", (class_id,))
            
            for sub, tsc in teacher_fallbacks:
                cursor.execute("INSERT OR REPLACE INTO subject_assignments (class_id, subject_name, teacher_tsc) VALUES (?, ?, ?)", (class_id, sub, tsc))
            
            class_grid = master_grids.get(c_name, master_grids["10 Stem"])
            for day in WEEKDAYS:
                lessons = class_grid[day]
                for index, sub_name in enumerate(lessons):
                    cursor.execute("INSERT INTO timetable (class_id, day_of_week, lesson_number, subject) VALUES (?, ?, ?, ?)", (class_id, day, index + 1, sub_name))
                    total_slots_inserted += 1
                    
        conn.commit()
        st.success(f"Successfully processed all school grids! Deployed {total_slots_inserted} lesson entries securely.")

# --- VIEW 4: PRINT ENGINE AND EXPORT VIEW (STRICT TWO-PAGE REPORT ENGINE) ---
elif menu == "Print & Export Sheets":
    st.subheader("🖨️ Generate Official 2-Page Weekly Registers")
    st.write("This generation profile compresses all data inputs precisely into an official two-page verification format.")
    
    cursor.execute("SELECT name FROM classes ORDER BY name")
    classes_list = [r[0] for r in cursor.fetchall()]
    
    if not classes_list:
        st.info("No school classes discovered to export sheets from.")
    else:
        col_c, col_d = st.columns(2)
        with col_c:
            exp_class = st.selectbox("Select Target Class", classes_list, key="exp_class")
        with col_d:
            exp_date = st.date_input("Select Week Date", datetime.date.today(), key="exp_date")
        
        week_dates = get_dates_for_week(exp_date)
        mon_date_str = week_dates["Monday"]
        fri_date_str = week_dates["Friday"]
        
        st.markdown("---")
        st.markdown(f"### 📋 Weekly Dashboard Preview for **{exp_class}** ({mon_date_str} to {fri_date_str})")
        
        date_placeholders = list(week_dates.values())
        cursor.execute(
            f"""SELECT 
                    tea.name AS teacher_name,
                    COUNT(CASE WHEN a.status = 'Present' THEN 1 END) AS classes_attended,
                    COUNT(CASE WHEN a.status = 'Absent' AND COALESCE(a.reason_absent, '') != '' THEN 1 END) AS missed_with_permission,
                    COUNT(CASE WHEN a.status = 'Absent' AND COALESCE(a.reason_absent, '') = '' THEN 1 END) AS missed_without_permission,
                    COUNT(CASE WHEN a.status = 'Recovered' THEN 1 END) AS classes_recovered
               FROM teachers tea
               LEFT JOIN subject_assignments sa ON tea.tsc_no = sa.teacher_tsc
               LEFT JOIN classes c ON sa.class_id = c.id AND c.name = ?
               LEFT JOIN timetable t ON c.id = t.class_id
               LEFT JOIN attendance_log a ON t.id = a.timetable_id 
                    AND a.subject_name = sa.subject_name 
                    AND a.date IN ({','.join(['?']*5)})
               GROUP BY tea.tsc_no
               ORDER BY tea.name""",
            (exp_class, *date_placeholders)
        )
        weekly_teacher_metrics = cursor.fetchall()
        
        if weekly_teacher_metrics:
            import pandas as pd
            st.markdown("**Cumulative Weekly Teacher Evaluation Matrix Summary**")
            df_metrics = pd.DataFrame(weekly_teacher_metrics, columns=["Teacher Name", "Total Lessons Attended", "Missed (With Permission)", "Missed (Without Permission)", "Recovered Lessons"])
            st.dataframe(df_metrics, use_container_width=True, hide_index=True)
            
        if st.button("Generate Official Two-Page W-TLAR PDF", type="primary", use_container_width=True):
            filename = f"Weekly_2Page_TLAR_{exp_class}_{mon_date_str}.pdf".replace(" ", "_")
            
            doc = SimpleDocTemplate(filename, pagesize=(792, 612), rightMargin=20, leftMargin=20, topMargin=20, bottomMargin=20)
            story = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=11, leading=13, alignment=1, textColor=colors.HexColor("#1A237E"))
            section_style = ParagraphStyle('SectionTitle', parent=styles['Heading2'], fontSize=9, leading=11, spaceBefore=4, spaceAfter=3, textColor=colors.HexColor("#1A237E"))
            meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontSize=8, leading=10)
            grid_text_style = ParagraphStyle('GridText', parent=styles['Normal'], fontSize=6, leading=8, alignment=0)
            summary_text_style = ParagraphStyle('SummaryText', parent=styles['Normal'], fontSize=7, leading=9)
            
            # -----------------------------------------------------------------
            # PAGE 1: TITLE META AND SECTION A ATTENDANCE LOG GRID
            # -----------------------------------------------------------------
            story.append(Paragraph("<b>TEACHERS SERVICE COMMISSION</b>", title_style))
            story.append(Paragraph("<b>WEEKLY TEACHER LESSON ATTENDANCE REGISTER (W-TLAR)</b>", title_style))
            story.append(Spacer(1, 4))
            
            meta_text = [
                [Paragraph(f"<b>Institution/Campus:</b> St. Michael Senior School - Kipsombe", meta_style), Paragraph("<b>Form Reference:</b> TSC/QAS/TPAD/W-TLAR/2026/V4", meta_style)],
                [Paragraph(f"<b>Class / Stream Group:</b> {exp_class}", meta_style), Paragraph(f"<b>Weekly Log Period:</b> {mon_date_str} to {fri_date_str}", meta_style)]
            ]
            meta_table = Table(meta_text, colWidths=[376, 376])
            meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
            story.append(meta_table)
            
            story.append(Paragraph("<b>SECTION A: WEEKLY LESSON TRACKING MATRIX WITH VERIFIED TRACK TIMINGS</b>", section_style))
            
            grid_headers = ["Lesson Slot", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            grid_data = [grid_headers]
            
            for l_num in range(1, 11):
                row_cells = [f"Lesson {l_num}"]
                for day in WEEKDAYS:
                    d_str = week_dates[day]
                    
                    cursor.execute(
                        """SELECT t.id, t.subject FROM timetable t
                           JOIN classes c ON t.class_id = c.id
                           WHERE c.name = ? AND t.day_of_week = ? AND t.lesson_number = ?""",
                        (exp_class, day, l_num)
                    )
                    t_slot = cursor.fetchone()
                    
                    if not t_slot:
                        row_cells.append(Paragraph("<font color='grey'>- Rest Break -</font>", grid_text_style))
                    else:
                        tt_id, raw_sub = t_slot
                        active_subs = ELECTIVE_SPLITS.get(raw_sub, [raw_sub])
                        
                        status_flags = []
                        for sub in active_subs:
                            cursor.execute(
                                """SELECT status, time_in, time_out, assignment_given FROM attendance_log 
                                   WHERE timetable_id = ? AND date = ? AND subject_name = ?""",
                                (tt_id, d_str, sub)
                            )
                            log_row = cursor.fetchone()
                            
                            if log_row:
                                status_val, ti, to, asg = log_row
                                ti_str = ti if ti.strip() else "--:--"
                                to_str = to if to.strip() else "--:--"
                                status_flags.append(f"<b>{sub}</b>: {status_val} | ⏱️ {ti_str}-{to_str} | 📝 Asg: {asg}")
                            else:
                                status_flags.append(f"<b>{sub}</b>: Unmarked | ⏱️ --:-- | 📝 Asg: No")
                                
                        cell_markup = "<br/>".join(status_flags)
                        row_cells.append(Paragraph(cell_markup, grid_text_style))
                        
                grid_data.append(row_cells)
                
            matrix_table = Table(grid_data, colWidths=[65, 137, 137, 137, 137, 137])
            matrix_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EEEEEE")),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('ALIGN', (1,1), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('FONTSIZE', (0,0), (-1,-1), 6),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(matrix_table)
            
            story.append(PageBreak())
            
            # -----------------------------------------------------------------
            # PAGE 2: TITLE META AND SECTION B STAFF SUMMARY MATRIX WITH SIGNATURES
            # -----------------------------------------------------------------
            story.append(Paragraph("<b>TEACHERS SERVICE COMMISSION</b>", title_style))
            story.append(Paragraph("<b>WEEKLY TEACHER LESSON ATTENDANCE REGISTER (W-TLAR)</b>", title_style))
            story.append(Spacer(1, 4))
            story.append(meta_table) 
            
            story.append(Paragraph("<b>SECTION B: CUMULATIVE MASTER TEACHER PERFORMANCE SUMMARY REGISTER (ALL STAFF)</b>", section_style))
            
            summary_headers = [[
                Paragraph("<b>Master Roster Teacher Name</b>", summary_text_style), 
                Paragraph("<b>Classes Attended</b>", summary_text_style), 
                Paragraph("<b>Missed (With Permission)</b>", summary_text_style), 
                Paragraph("<b>Missed (Without Permission)</b>", summary_text_style), 
                Paragraph("<b>Recovered Lessons</b>", summary_text_style)
            ]]
            
            for metric in weekly_teacher_metrics:
                summary_headers.append([
                    Paragraph(metric[0], summary_text_style), 
                    Paragraph(str(metric[1]), summary_text_style), 
                    Paragraph(str(metric[2]), summary_text_style), 
                    Paragraph(str(metric[3]), summary_text_style), 
                    Paragraph(str(metric[4]), summary_text_style)
                ])
                
            summary_table = Table(summary_headers, colWidths=[272, 120, 120, 120, 120])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E0F2F1")),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('TOPPADDING', (0,0), (-1,-1), 1.5),  
                ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 6))
            
            sig_style = ParagraphStyle('SigLine', parent=styles['Normal'], fontSize=7.5, leading=10)
            sig_text = [
                [Paragraph("<b>Compiled By:</b> Class Secretary Monitor<br/>Sign: _______________________", sig_style),
                 Paragraph("<b>Verified By:</b> Deputy Head of Institution<br/>Sign: _______________________", sig_style)],
                [Paragraph("Date: _______________________", sig_style), Paragraph("Date: _______________________", sig_style)],
                [Paragraph("<br/><b>Confirmed By:</b> Head of Institution<br/>Sign: _______________________<br/>Date: _______________________", sig_style),
                 Paragraph("<br/><b>Official Institution Stamp Check:</b><br/>[ Place Stamp Box Here ]", sig_style)]
            ]
            sig_table = Table(sig_text, colWidths=[376, 376])
            sig_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
            story.append(sig_table)
            
            doc.build(story)
            
            with open(filename, "rb") as pdf_file:
                st.download_button(
                    label="📥 Download Official 2-Page Weekly PDF Report Matrix",
                    data=pdf_file,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )
