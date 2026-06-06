import streamlit as st
import psycopg2
from psycopg2 import extras
import os
import datetime

# ReportLab layout engine imports optimized for native landscape outputs
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ---------------------------------------------------------
# DATABASE STRUCTURAL INITIALIZATION (SUPABASE / POSTGRES)
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

# Comprehensive non-instructional rest filtering blocks 
REST_BLOCKS = {"BREAK", "LUNCH", "TEA BREAK", "TEA"}

ELECTIVE_SPLITS = {
    "HIST/COMP/AGR": ["HISTO", "COMP", "AGRIC"],
    "CRE CSL": ["CRE", "CSL"],
    "CRE BIO CSL": ["CRE", "BIO", "CSL"],
    "HIS MAT": ["HIS", "MAT"],
    "MAT HS": ["MAT", "HIS"],
    "HS MAT": ["HIS", "MAT"],
    "GE STO": ["GEO", "HIS"],
    "PHY KIS": ["PHY", "KIS"],
    "CRE BIO": ["CRE", "BIO"],
    "CHE M": ["CHEM", "MAT"],
    "M CHE": ["MAT", "CHEM"],
    "HISTO GEO": ["HISTO", "GEO"],
    "PHY CRE": ["PHY", "CRE"],
    "PE ICT": ["PE", "ICT"],
    "CSL ENG": ["CSL", "ENG"],
    "CH/FREN": ["CHEM", "CRE"],
    "CH/ FREN COMP S/BST/ AGRIC": ["CHEM", "CRE", "COMP", "AGRIC"],
    "AGRIC S/BST/ FREN CH COMP": ["AGRIC", "CRE", "CHEM", "COMP"]
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
    st.write("Displaying valid instructional lessons. Non-lesson rest blocks are automatically filtered out.")
    
    cursor.execute("SELECT name FROM classes ORDER BY name;")
    classes_list = [r[0] for r in cursor.fetchall()]
    
    if not classes_list:
        st.info("No classes found. Go to 'System Data Importer' to set up default school structures.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            selected_class = st.selectbox("Select Target Class/Grade", classes_list)
        with col2:
            selected_date = st.date_input("Target Date", datetime.date.today())
            
        day_name = selected_date.strftime("%A")
        date_str = selected_date.strftime("%Y-%m-%d")
        
        if day_name in ["Saturday", "Sunday"]:
            st.error(f"⚠️ Selected date falls on a weekend ({day_name}). Register tracking runs Monday to Friday.")
        else:
            cursor.execute(
                """SELECT t.id, t.lesson_number, t.subject FROM timetable t
                   JOIN classes c ON t.class_id = c.id 
                   WHERE c.name = %s AND t.day_of_week = %s ORDER BY t.lesson_number;""",
                (selected_class, day_name)
            )
            slots = cursor.fetchall()
            
            if not slots:
                st.warning(f"No master timetable entries found for {day_name} in this class. Set it up inside the Importer panel.")
            else:
                st.write(f"### Grid View for {day_name}, {date_str}")
                form_payloads = {}
                academic_lesson_index = 1
                
                for (tt_id, original_num, raw_subject) in slots:
                    if raw_subject.strip().upper() in REST_BLOCKS:
                        continue
                        
                    active_subjects = ELECTIVE_SPLITS.get(raw_subject, [raw_subject])
                    is_split = len(active_subjects) > 1
                    
                    header_label = f"📖 Academic Lesson {academic_lesson_index}: {raw_subject}"
                    if is_split:
                        header_label = f"🔀 Academic Lesson {academic_lesson_index}: {raw_subject} — [Parallel Elective Split Group]"
                        
                    with st.expander(header_label, expanded=True):
                        for sub in active_subjects:
                            cursor.execute(
                                """SELECT t.name FROM subject_assignments sa 
                                   JOIN teachers t ON sa.teacher_tsc = t.tsc_no
                                   JOIN classes c ON sa.class_id = c.id
                                   WHERE c.name = %s AND sa.subject_name = %s;""", (selected_class, sub)
                            )
                            t_row = cursor.fetchone()
                            display_teacher = t_row[0] if t_row else "No Instructor Assigned"
                            
                            cursor.execute(
                                """SELECT time_in, time_out, assignment_given, status, reason_absent 
                                   FROM attendance_log WHERE timetable_id = %s AND date = %s AND subject_name = %s;""", 
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
                    
                    academic_lesson_index += 1
                                
                if st.button("Save / Update Day's Lesson Entries", type="primary"):
                    records_saved = 0
                    for (tt_id, sub), (status, time_in, time_out, assg, reason) in form_payloads.items():
                        cursor.execute(
                            """INSERT INTO attendance_log (timetable_id, date, subject_name, time_in, time_out, assignment_given, status, reason_absent)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                               ON CONFLICT(timetable_id, date, subject_name) DO UPDATE SET
                                  time_in = EXCLUDED.time_in,
                                  time_out = EXCLUDED.time_out,
                                  assignment_given = EXCLUDED.assignment_given,
                                  status = EXCLUDED.status,
                                  reason_absent = EXCLUDED.reason_absent;""",
                            (tt_id, date_str, sub, time_in.strip(), time_out.strip(), assg, status, reason.strip())
                        )
                        records_saved += 1
                    conn.commit()
                    st.success(f"Successfully synchronized {records_saved} instructional tracks for {date_str}!")
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
                    cursor.execute("INSERT INTO teachers (tsc_no, name) VALUES (%s, %s);", (new_tsc.strip(), new_name.strip()))
                    conn.commit()
                    st.success(f"Registered {new_name}")
                    st.rerun()
                except psycopg2.IntegrityError:
                    conn.rollback()
                    st.error("Registration Conflict: Code already exists.")
            else:
                st.warning("Please fill out all fields.")
                
        st.markdown("---")
        st.markdown("#### Assign Subject Teacher Role")
        
        cursor.execute("SELECT id, name FROM classes ORDER BY name;")
        classes_mapping = cursor.fetchall()
        cursor.execute("SELECT tsc_no, name FROM teachers ORDER BY name;")
        teachers_mapping = cursor.fetchall()
        
        if classes_mapping and teachers_mapping:
            c_options = {name: cid for cid, name in classes_mapping}
            t_options = {f"{name} ({tsc})": tsc for tsc, name in teachers_mapping}
            
            assign_class = st.selectbox("Target Class", list(c_options.keys()))
            assign_sub = st.selectbox("Subject Name", ["MAT", "ENG", "KIS", "CRE", "HIS", "HISTO", "GEO", "ICT", "PE", "CSL", "BIO", "CHEM", "PHY", "COMP", "AGRIC", "PPI", "B.P", "G.S"])
            assign_tea = st.selectbox("Assign Teacher", list(t_options.keys()))
            
            if st.button("Commit Subject Assignment", type="primary"):
                cursor.execute(
                    """INSERT INTO subject_assignments (class_id, subject_name, teacher_tsc) VALUES (%s, %s, %s)
                       ON CONFLICT(class_id, subject_name) DO UPDATE SET teacher_tsc = EXCLUDED.teacher_tsc;""",
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
               ORDER BY c.name, sa.subject_name;"""
        )
        matrix_data = cursor.fetchall()
        if matrix_data:
            import pandas as pd
            df = pd.DataFrame(matrix_data, columns=["Class / Form", "Subject Name", "Assigned Teacher"])
            st.dataframe(df, use_container_width=True, hide_index=True)

# --- VIEW 3: AUTOMATED & MANUAL DATA IMPORTER (MANUAL OVERRIDE IMPLEMENTED) ---
elif menu == "System Data Importer":
    st.subheader("⚙️ System Structural Setup Panel")
    st.write("Manage or completely input your school timetable structures below.")
    
    if st.button("Step 1: Initialize Default School Staff Roster", use_container_width=True):
        teachers_list = [
            ("T.1", "DOROTHY"), ("T.2", "ONDIEKI"), ("T.12", "CHERUIYOT"), ("T.11", "WEKESA"),
            ("T.3", "AGESAH"), ("T.5", "NATEMBEYA"), ("T.13", "EMMANUEL"), ("T.16", "KIPNGETICH"),
            ("T.17", "MUNIALO"), ("T.9", "KORIR"), ("T.15", "TUWEI"), ("T.6", "ROTICH"),
            ("T.7", "CHEBERYON"), ("T.14", "LINDA"), ("T.10", "KEMEI"), ("T.4", "MRS. RUTTO"),
            ("T.18", "LEAH CHEPCHIRCHIR"), ("T.19", "DAISY")
        ]
        for short_code, name in teachers_list:
            cursor.execute(
                """INSERT INTO teachers (tsc_no, name) VALUES (%s, %s)
                   ON CONFLICT (tsc_no) DO UPDATE SET name = EXCLUDED.name;""", (short_code, name)
            )
        conn.commit()
        st.success("Master Staff Roster successfully synchronized.")
        
    st.markdown("---")
    st.markdown("### ✍️ Step 2: Interactive Manual Timetable Matrix Input Grid")
    st.write("Select a class stream to modify or enter its sequential 13-slot daily structure. Type `TEA BREAK`, `BREAK`, or `LUNCH` to mark non-instructional intervals.")
    
    # Allow creating a class name dynamically if it doesn't exist
    new_class_input = st.text_input("Add a New Class Stream Name (e.g., '10 Stem', '4M'):")
    if st.button("Create Class Stream Row"):
        if new_class_input.strip():
            cursor.execute("INSERT INTO classes (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;", (new_class_input.strip(),))
            conn.commit()
            st.success(f"Class '{new_class_input.strip()}' created! Refreshing list...")
            st.rerun()

    cursor.execute("SELECT name FROM classes ORDER BY name;")
    available_classes = [r[0] for r in cursor.fetchall()]
    
    if available_classes:
        active_manual_class = st.selectbox("Select Class to Edit / Fill:", available_classes)
        
        cursor.execute("SELECT id FROM classes WHERE name = %s;", (active_manual_class,))
        active_class_id = cursor.fetchone()[0]
        
        # Load any existing data from database into a dictionary map for easy form populating
        existing_grid_map = {}
        cursor.execute("SELECT day_of_week, lesson_number, subject FROM timetable WHERE class_id = %s;", (active_class_id,))
        for day, slot_num, subj in cursor.fetchall():
            existing_grid_map[(day, slot_num)] = subj

        st.markdown(f"#### Fill/Modify 13 Sequential Slots for **{active_manual_class}**")
        
        # Display an explanation of slots to prevent input error
        st.info("💡 **Structure Reference:** Slot 1 (8:00 AM), Slot 2 (8:40 AM), Slot 3 (9:20 AM), Slot 4 (TEA BREAK), Slot 5 (10:20 AM), etc.")
        
        manual_payload = {}
        
        # Create a tab for each day to keep the UI perfectly clean
        day_tabs = st.tabs(WEEKDAYS)
        for i, day in enumerate(WEEKDAYS):
            with day_tabs[i]:
                st.write(f"✍️ Enter full timeline sequence for **{day}**:")
                
                # We show columns for the slots
                cols_1 = st.columns(4)
                cols_2 = st.columns(4)
                cols_3 = st.columns(5)
                all_cols = cols_1 + cols_2 + cols_3
                
                for slot in range(1, 14):
                    default_val = existing_grid_map.get((day, slot), "")
                    
                    # Pre-fill standard intervals if completely empty to save user time
                    if not default_val:
                        if slot == 3 or slot == 4:  # Depends on class, but can be customized
                            if "Science" in active_manual_class:
                                if slot == 3: default_val = "TEA BREAK"
                            else:
                                if slot == 4: default_val = "TEA BREAK"
                        if slot == 6: default_val = "BREAK"
                        if slot == 9: default_val = "LUNCH"
                    
                    with all_cols[slot-1]:
                        val = st.text_input(f"Slot {slot}", value=default_val, key=f"manual_{day}_{slot}", placeholder="e.g. MAT HS")
                        manual_payload[(day, slot)] = val.strip()
                        
        if st.button("Save Manual Timetable Data to Database", type="primary", use_container_width=True):
            # Wipe previous structural entries for this specific class to prevent overlapping conflicts
            cursor.execute("DELETE FROM attendance_log WHERE timetable_id IN (SELECT id FROM timetable WHERE class_id = %s);", (active_class_id,))
            cursor.execute("DELETE FROM timetable WHERE class_id = %s;", (active_class_id,))
            
            # Inject new manually keyed entries
            inserted_count = 0
            for (day, slot), subject_str in manual_payload.items():
                if subject_str:  # Only save if not empty
                    cursor.execute(
                        "INSERT INTO timetable (class_id, day_of_week, lesson_number, subject) VALUES (%s, %s, %s, %s);",
                        (active_class_id, day, slot, subject_str)
                    )
                    inserted_count += 1
            
            # Seed default teacher relationships for newly generated subjects if missing
            teacher_fallbacks = [
                ("MAT", "T.6"), ("ENG", "T.5"), ("KIS", "T.4"), ("BIO", "T.15"),
                ("CHEM", "T.2"), ("PHY", "T.18"), ("CRE", "T.10"), ("HIS", "T.13"),
                ("PE", "T.11"), ("ICT", "T.17"), ("CSL", "T.16"), ("LS", "T.1"),
                ("HISTO GEO", "T.13"), ("GE STO", "T.12"), ("HISTO", "T.5"), 
                ("COMP", "T.17"), ("AGRIC", "T.1"), ("PPI", "T.1"), ("B.P", "T.15"), ("G.S", "T.16")
            ]
            for sub, tsc in teacher_fallbacks:
                cursor.execute(
                    """INSERT INTO subject_assignments (class_id, subject_name, teacher_tsc) 
                       VALUES (%s, %s, %s) ON CONFLICT DO NOTHING;""", (active_class_id, sub, tsc)
                )
                
            conn.commit()
            st.success(f"Successfully saved {inserted_count} timetable slots for {active_manual_class}!")
            st.rerun()

# --- VIEW 4: PRINT ENGINE AND EXPORT VIEW (STRICT TWO-PAGE REPORT ENGINE) ---
elif menu == "Print & Export Sheets":
    st.subheader("🖨️ Generate Official 2-Page Weekly Registers")
    st.write("Outputs a strict 2-page grid containing exactly 10 teachable instructional lines with enhanced text size.")
    
    cursor.execute("SELECT name FROM classes ORDER BY name;")
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
               LEFT JOIN classes c ON sa.class_id = c.id AND c.name = %s
               LEFT JOIN timetable t ON c.id = t.class_id
               LEFT JOIN attendance_log a ON t.id = a.timetable_id 
                    AND a.subject_name = sa.subject_name 
                    AND a.date IN (%s, %s, %s, %s, %s)
               GROUP BY tea.tsc_no, tea.name
               ORDER BY tea.name;""",
            [exp_class] + date_placeholders
        )
        weekly_teacher_metrics = cursor.fetchall()
        
        if weekly_teacher_metrics:
            import pandas as pd
            st.markdown("**Cumulative Weekly Teacher Evaluation Matrix Summary**")
            df_metrics = pd.DataFrame(weekly_teacher_metrics, columns=["Teacher Name", "Total Lessons Attended", "Missed (With Permission)", "Missed (Without Permission)", "Recovered Lessons"])
            st.dataframe(df_metrics, use_container_width=True, hide_index=True)
            
        if st.button("Generate Official Two-Page W-TLAR PDF", type="primary", use_container_width=True):
            filename = f"Weekly_2Page_TLAR_{exp_class}_{mon_date_str}.pdf".replace(" ", "_")
            
            # Explicit Landscape boundaries targeting physical printer configurations
            doc = SimpleDocTemplate(filename, pagesize=landscape(letter), rightMargin=16, leftMargin=16, topMargin=16, bottomMargin=16)
            story = []
            styles = getSampleStyleSheet()
            
            title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=12, leading=14, alignment=1, textColor=colors.HexColor("#1A237E"))
            section_style = ParagraphStyle('SectionTitle', parent=styles['Heading2'], fontSize=10, leading=13, spaceBefore=4, spaceAfter=3, textColor=colors.HexColor("#1A237E"))
            meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontSize=9, leading=12)
            grid_text_style = ParagraphStyle('GridText', parent=styles['Normal'], fontSize=7.5, leading=10, alignment=0)
            summary_text_style = ParagraphStyle('SummaryText', parent=styles['Normal'], fontSize=8, leading=11)
            
            # -----------------------------------------------------------------
            # PAGE 1: TITLE META AND SECTION A ATTENDANCE LOG GRID (10 REAL LESSONS)
            # -----------------------------------------------------------------
            story.append(Paragraph("<b>TEACHERS SERVICE COMMISSION</b>", title_style))
            story.append(Paragraph("<b>WEEKLY TEACHER LESSON ATTENDANCE REGISTER (W-TLAR)</b>", title_style))
            story.append(Spacer(1, 3))
            
            meta_text = [
                [Paragraph(f"<b>Institution:</b> St. Michael Senior School - Kipsombe", meta_style), Paragraph("<b>Form Ref:</b> TSC/QAS/TPAD/W-TLAR/2026/V4", meta_style)],
                [Paragraph(f"<b>Class Stream:</b> {exp_class}", meta_style), Paragraph(f"<b>Log Period:</b> {mon_date_str} to {fri_date_str}", meta_style)]
            ]
            meta_table = Table(meta_text, colWidths=[385, 385])
            meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 1)]))
            story.append(meta_table)
            
            story.append(Paragraph("<b>SECTION A: WEEKLY LESSON TRACKING MATRIX WITH VERIFIED TRACK TIMINGS</b>", section_style))
            
            grid_headers = ["Lesson Slot", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            grid_data = [grid_headers]
            
            # Print exactly 10 teachable rows by programmatically filtering out the rest intervals
            for l_num in range(1, 11):
                row_cells = [f"Lesson {l_num}"]
                for day in WEEKDAYS:
                    d_str = week_dates[day]
                    
                    cursor.execute(
                        """SELECT t.id, t.subject FROM timetable t
                           JOIN classes c ON t.class_id = c.id
                           WHERE c.name = %s AND t.day_of_week = %s ORDER BY t.lesson_number;""",
                        (exp_class, day)
                    )
                    all_day_slots = cursor.fetchall()
                    
                    # Filter out break, tea break, and lunch items from our printed line matrix
                    academic_slots = [slot for slot in all_day_slots if slot[1].strip().upper() not in REST_BLOCKS]
                    
                    if len(academic_slots) < l_num:
                        row_cells.append(Paragraph("<font color='grey'>No Lesson</font>", grid_text_style))
                    else:
                        tt_id, raw_sub = academic_slots[l_num - 1]
                        active_subs = ELECTIVE_SPLITS.get(raw_sub, [raw_sub])
                        
                        status_flags = []
                        for sub in active_subs:
                            cursor.execute(
                                """SELECT status, time_in, time_out, assignment_given FROM attendance_log 
                                   WHERE timetable_id = %s AND date = %s AND subject_name = %s;""",
                                (tt_id, d_str, sub)
                            )
                            log_row = cursor.fetchone()
                            
                            if log_row:
                                status_val, ti, to, asg = log_row
                                ti_str = ti if ti.strip() else "--:--"
                                to_str = to if to.strip() else "--:--"
                                status_flags.append(f"<b>{sub}</b>: {status_val}<br/>⏱️ {ti_str}-{to_str} | 📝 Asg: {asg}")
                            else:
                                status_flags.append(f"<b>{sub}</b>: Unmarked<br/>⏱️ --:-- | 📝 Asg: No")
                                
                        cell_markup = "<br/>".join(status_flags)
                        row_cells.append(Paragraph(cell_markup, grid_text_style))
                        
                grid_data.append(row_cells)
                
            matrix_table = Table(grid_data, colWidths=[65, 141, 141, 141, 141, 141])
            matrix_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EEEEEE")),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('ALIGN', (1,1), (-1,-1), 'LEFT'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('TOPPADDING', (0,0), (-1,-1), 2.5),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
            ]))
            story.append(matrix_table)
            
            story.append(PageBreak())
            
            # -----------------------------------------------------------------
            # PAGE 2: TITLE META AND SECTION B STAFF SUMMARY PERFORMANCE MATRIX
            # -----------------------------------------------------------------
            story.append(Paragraph("<b>TEACHERS SERVICE COMMISSION</b>", title_style))
            story.append(Paragraph("<b>WEEKLY TEACHER LESSON ATTENDANCE REGISTER (W-TLAR)</b>", title_style))
            story.append(Spacer(1, 3))
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
                
            summary_table = Table(summary_headers, colWidths=[290, 120, 120, 120, 120])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E0F2F1")),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                ('TOPPADDING', (0,0), (-1,-1), 1.5),  
                ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 4))
            
            sig_style = ParagraphStyle('SigLine', parent=styles['Normal'], fontSize=8, leading=11)
            sig_text = [
                [Paragraph("<b>Compiled By:</b> Class Secretary Monitor<br/>Sign: _______________________", sig_style),
                 Paragraph("<b>Verified By:</b> Deputy Head of Institution<br/>Sign: _______________________", sig_style)],
                [Paragraph("Date: _______________________", sig_style), Paragraph("Date: _______________________", sig_style)],
                [Paragraph("<br/><b>Confirmed By:</b> Head of Institution<br/>Sign: _______________________<br/>Date: _______________________", sig_style),
                 Paragraph("<br/><b>Official Institution Stamp Check:</b><br/>[ Place Stamp Box Here ]", sig_style)]
            ]
            sig_table = Table(sig_text, colWidths=[385, 385])
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
