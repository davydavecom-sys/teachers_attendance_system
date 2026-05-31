import streamlit as st
import sqlite3
import os
import datetime

# ReportLab imports for generating physical printouts
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
            id INTEGER PRIMARY KEY AUTOINCREMENT, timetable_id INTEGER, date TEXT, 
            time_in TEXT, time_out TEXT, assignment_given TEXT, status TEXT, reason_absent TEXT,
            FOREIGN KEY(timetable_id) REFERENCES timetable(id),
            UNIQUE(timetable_id, date)
        )"""
    )
    conn.commit()
    return conn, cursor

conn, cursor = init_database()

# ---------------------------------------------------------
# WEB DASHBOARD INTERFACE
# ---------------------------------------------------------
st.set_page_config(page_title="TSC TLAR Dashboard", layout="wide")
st.title("🏫 TSC TLAR - School Management Web Application")

# Sidebar Application Routing
menu = st.sidebar.radio("Navigation Menu", ["Attendance Log", "Teachers & Assignments", "System Data Importer", "Print & Export Sheets"])

# --- VIEW 1: ATTENDANCE LOG VIEW ---
if menu == "Attendance Log":
    st.subheader("📝 Daily Lesson Attendance Logging and Updates")
    st.write("Displaying a fixed structure of 10 systematic lessons mapped to the master school schedule.")
    
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
        
        # Guard clause check for weekends since schedule is strictly Monday-Friday
        if day_name in ["Saturday", "Sunday"]:
            st.error(f"⚠️ Selected date falls on a weekend ({day_name}). Official registers are only maintained Monday through Friday.")
        else:
            # Fetch all 10 slots for the selected day
            cursor.execute(
                """SELECT t.id, t.lesson_number, t.subject, tea.name FROM timetable t
                   JOIN classes c ON t.class_id = c.id 
                   LEFT JOIN subject_assignments sa ON c.id = sa.class_id AND t.subject = sa.subject_name
                   LEFT JOIN teachers tea ON sa.teacher_tsc = tea.tsc_no
                   WHERE c.name = ? AND t.day_of_week = ? ORDER BY t.lesson_number""",
                (selected_class, day_name)
            )
            slots = cursor.fetchall()
            
            if not slots:
                st.warning(f"No master timetable entries found for {day_name} in this class. Please generate them via the 'System Data Importer' panel first.")
            else:
                st.write(f"### Grid View for {day_name}, {date_str} — (Showing 10 Structured Periods)")
                
                form_payloads = {}
                
                for (tt_id, lesson_num, subject, teacher_name) in slots:
                    display_teacher = teacher_name if teacher_name else "No Instructor Tied"
                    
                    # Pull existing logged record if any
                    cursor.execute(
                        "SELECT time_in, time_out, assignment_given, status, reason_absent FROM attendance_log WHERE timetable_id = ? AND date = ?", 
                        (tt_id, date_str)
                    )
                    existing = cursor.fetchone()
                    
                    # Establish defaults if not populated
                    d_status = existing[3] if existing else "Present"
                    d_in = existing[0] if existing else ""
                    d_out = existing[1] if existing else ""
                    d_assg = existing[2] if existing else "No"
                    d_reason = existing[4] if existing else ""
                    
                    # Distinguish empty periods or breaks visually
                    header_label = f"⏰ Period {lesson_num}: {subject} — Assigned Teacher: {display_teacher}"
                    if subject in ["BREAK", "LUNCH", "FREE"]:
                        header_label = f"☕ Period {lesson_num}: {subject} — (Self-Directed/Rest Period)"
                    
                    with st.expander(header_label, expanded=True):
                        c1, c2, c3, c4, c5 = st.columns(5)
                        with c1:
                            status = st.selectbox("Status", ["Present", "Absent", "N/A"], index=["Present", "Absent", "N/A"].index(d_status), key=f"status_{tt_id}")
                        with c2:
                            time_in = st.text_input("Time In", value=d_in, placeholder="e.g. 08:20", key=f"in_{tt_id}")
                        with c3:
                            time_out = st.text_input("Time Out", value=d_out, placeholder="e.g. 09:00", key=f"out_{tt_id}")
                        with c4:
                            assg = st.selectbox("Assignment (Y/N)", ["No", "Yes"], index=["No", "Yes"].index(d_assg), key=f"assg_{tt_id}")
                        with c5:
                            reason = st.text_input("If Absent: Reason", value=d_reason, placeholder="Reason notes", key=f"reason_{tt_id}")
                            
                    form_payloads[tt_id] = (status, time_in, time_out, assg, reason)
                    
                if st.button("Save / Update Day's 10 Grid Entries", type="primary"):
                    records_saved = 0
                    for tt_id, (status, time_in, time_out, assg, reason) in form_payloads.items():
                        cursor.execute(
                            """INSERT INTO attendance_log (timetable_id, date, time_in, time_out, assignment_given, status, reason_absent)
                               VALUES (?, ?, ?, ?, ?, ?, ?)
                               ON CONFLICT(timetable_id, date) DO UPDATE SET
                                  time_in = excluded.time_in,
                                  time_out = excluded.time_out,
                                  assignment_given = excluded.assignment_given,
                                  status = excluded.status,
                                  reason_absent = excluded.reason_absent""",
                            (tt_id, date_str, time_in.strip(), time_out.strip(), assg, status, reason.strip())
                        )
                        records_saved += 1
                    conn.commit()
                    st.success(f"Successfully synchronized all {records_saved} periods to database for {date_str}!")
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
                    st.error("Registration Conflict: This Short Code already exists.")
            else:
                st.warning("Please fill out all teacher metrics.")
                
        st.markdown("---")
        st.markdown("#### Assign Subject Teacher Role")
        
        cursor.execute("SELECT id, name FROM classes ORDER BY name")
        classes_mapping = cursor.fetchall()
        cursor.execute("SELECT tsc_no, name FROM teachers ORDER BY name")
        teachers_mapping = cursor.fetchall()
        
        if not classes_mapping or not teachers_mapping:
            st.info("Ensure both classes and teachers are registered before linking roles.")
        else:
            c_options = {name: cid for cid, name in classes_mapping}
            t_options = {f"{name} ({tsc})": tsc for tsc, name in teachers_mapping}
            
            assign_class = st.selectbox("Target Class", list(c_options.keys()))
            assign_sub = st.selectbox("Subject Name", ["MAT", "ENG", "KIS", "CRE", "GE", "ICT", "PE", "CSL", "BIO", "CHEM", "PHY", "HIST", "BREAK", "LUNCH", "FREE"])
            assign_tea = st.selectbox("Assign Teacher", list(t_options.keys()))
            
            if st.button("Commit Subject Assignment", type="primary"):
                cursor.execute(
                    """INSERT INTO subject_assignments (class_id, subject_name, teacher_tsc) VALUES (?, ?, ?)
                       ON CONFLICT(class_id, subject_name) DO UPDATE SET teacher_tsc = excluded.teacher_tsc""",
                    (c_options[assign_class], assign_sub, t_options[assign_tea])
                )
                conn.commit()
                st.success(f"Assigned role successfully.")
                st.rerun()

    with col2:
        st.markdown("#### Current Class Subject Matrix Assignments")
        cursor.execute(
            """SELECT c.name, sa.subject_name, t.name FROM subject_assignments sa
               JOIN classes c ON sa.class_id = c.id JOIN teachers t ON sa.teacher_tsc = t.tsc_no
               ORDER BY c.name, sa.subject_name"""
        )
        matrix_data = cursor.fetchall()
        if not matrix_data:
            st.info("No active teacher structural assignments discovered.")
        else:
            import pandas as pd
            df = pd.DataFrame(matrix_data, columns=["Class / Form", "Subject Name", "Assigned Teacher"])
            st.dataframe(df, use_container_width=True)

# --- VIEW 3: AUTOMATED DATA IMPORTER ---
elif menu == "System Data Importer":
    st.subheader("⚙️ Automated System Structural Setup Panel")
    st.write("Inject structural profiles and 10 daily lesson matrices for all 6 official school classes.")
    
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
    
    if st.button("Import Complete 10-Period Multi-Class Timetable Grid", use_container_width=True):
        # Definition of all 6 target classes
        target_classes = ["4M", "4S", "3M", "3S", "10 Social Science", "10 Stem"]
        
        # Standardize standard assignment rules to save repetitive manual clicks
        base_assignments = [
            ("GE", "T.12"), ("CRE", "T.10"), ("MAT", "T.6"), ("ICT", "T.17"),
            ("KIS", "T.4"), ("ENG", "T.9"), ("CSL", "T.16"), ("PE", "T.11"),
            ("BIO", "T.1"), ("CHEM", "T.2"), ("PHY", "T.3"), ("HIST", "T.5")
        ]
        
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        
        # 10 daily period timetable layouts mapped for standard variants
        science_day_template = {
            "Monday":    ["MAT", "MAT", "BREAK", "CHEM", "ENG", "LUNCH", "KIS", "PHY", "FREE", "FREE"],
            "Tuesday":   ["BIO", "BIO", "BREAK", "KIS", "KIS", "LUNCH", "MAT", "ENG", "FREE", "FREE"],
            "Wednesday": ["PHY", "MAT", "BREAK", "ENG", "CHEM", "LUNCH", "BIO", "PE", "FREE", "FREE"],
            "Thursday":  ["CHEM", "PHY", "BREAK", "KIS", "BIO", "LUNCH", "MAT", "HIST", "FREE", "FREE"],
            "Friday":    ["MAT", "HIST", "BREAK", "PE", "CHEM", "LUNCH", "ENG", "KIS", "FREE", "FREE"]
        }
        
        social_day_template = {
            "Monday":    ["MAT", "MAT", "BREAK", "CRE", "ENG", "LUNCH", "KIS", "GE", "FREE", "FREE"],
            "Tuesday":   ["GE", "ICT", "BREAK", "KIS", "KIS", "LUNCH", "MAT", "ENG", "FREE", "FREE"],
            "Wednesday": ["CSL", "MAT", "BREAK", "ENG", "CRE", "LUNCH", "GE", "PE", "FREE", "FREE"],
            "Thursday":  ["GE", "GE", "BREAK", "KIS", "ICT", "LUNCH", "MAT", "CSL", "FREE", "FREE"],
            "Friday":    ["MAT", "GE", "BREAK", "PE", "CSL", "LUNCH", "ENG", "KIS", "FREE", "FREE"]
        }
        
        total_slots_inserted = 0
        
        for c_name in target_classes:
            # Step 1: Ensure class is safely initialized
            cursor.execute("INSERT OR IGNORE INTO classes (name) VALUES (?)", (c_name,))
            conn.commit()
            
            cursor.execute("SELECT id FROM classes WHERE name = ?", (c_name,))
            class_id = cursor.fetchone()[0]
            
            # Step 2: Clear old records for clean replacement
            cursor.execute("DELETE FROM timetable WHERE class_id = ?", (class_id,))
            cursor.execute("DELETE FROM subject_assignments WHERE class_id = ?", (class_id,))
            
            # Step 3: Seed teacher matrix mappings for this specific class
            for sub, tsc in base_assignments:
                cursor.execute(
                    "INSERT OR REPLACE INTO subject_assignments (class_id, subject_name, teacher_tsc) VALUES (?, ?, ?)",
                    (class_id, sub, tsc)
                )
            
            # Step 4: Pick appropriate template map based on class style type
            if "Stem" in c_name or "S" in c_name or "M" in c_name and c_name != "3M" and c_name != "4M":
                active_template = science_day_template
            else:
                active_template = social_day_template
                
            # Alternative layout split for M-streams just to make data diverse
            if "M" in c_name:
                active_template = social_day_template
                
            # Step 5: Seed all 50 slots (10 lessons x 5 weekdays) for this class
            for day in weekdays:
                subjects = active_template[day]
                for index, sub_name in enumerate(subjects):
                    lesson_number = index + 1
                    cursor.execute(
                        """INSERT OR REPLACE INTO timetable (class_id, day_of_week, lesson_number, subject) 
                           VALUES (?, ?, ?, ?)""", 
                        (class_id, day, lesson_number, sub_name)
                    )
                    total_slots_inserted += 1
                    
        conn.commit()
        st.success(f"Successfully processed all 6 classes! Deployed {total_slots_inserted} clean entries into the 10-period matrix layout.")

# --- VIEW 4: PRINT ENGINE AND EXPORT VIEW ---
elif menu == "Print & Export Sheets":
    st.subheader("🖨️ Generate Official Registers for Endorsement")
    
    cursor.execute("SELECT name FROM classes ORDER BY name")
    classes_list = [r[0] for r in cursor.fetchall()]
    
    if not classes_list:
        st.info("No school classes discovered to export sheets from.")
    else:
        exp_class = st.selectbox("Select Target Class", classes_list, key="exp_class")
        exp_date = st.date_input("Select Target Date", datetime.date.today(), key="exp_date")
        
        date_str = exp_date.strftime("%Y-%m-%d")
        day_name = exp_date.strftime("%A")
        
        if st.button("Generate Official TLAR 10-Lesson PDF Document"):
            cursor.execute(
                """SELECT t.lesson_number, t.subject, tea.name, COALESCE(a.status, 'N/A'), 
                          COALESCE(a.time_in, ''), COALESCE(a.time_out, ''), COALESCE(a.assignment_given, ''), COALESCE(a.reason_absent, '')
                   FROM timetable t
                   JOIN classes c ON t.class_id = c.id
                   LEFT JOIN subject_assignments sa ON c.id = sa.class_id AND t.subject = sa.subject_name
                   LEFT JOIN teachers tea ON sa.teacher_tsc = tea.tsc_no
                   LEFT JOIN attendance_log a ON t.id = a.timetable_id AND a.date = ?
                   WHERE c.name = ? AND t.day_of_week = ?
                   ORDER BY t.lesson_number""",
                (date_str, exp_class, day_name)
            )
            records = cursor.fetchall()
            
            if not records:
                st.error(f"No scheduled records discovered for {exp_class} on {day_name} ({date_str}). Ensure master setup data is populated.")
            else:
                filename = f"TLAR_{exp_class}_{date_str}.pdf".replace(" ", "_")
                
                doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
                story = []
                styles = getSampleStyleSheet()
                
                title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontSize=13, leading=15, alignment=1, textColor=colors.HexColor("#1A237E"))
                meta_style = ParagraphStyle('DocMeta', parent=styles['Normal'], fontSize=9, leading=13)
                
                story.append(Paragraph("<b>TEACHERS SERVICE COMMISSION</b>", title_style))
                story.append(Paragraph("<b>TEACHER LESSON ATTENDANCE REGISTER (TLAR)</b>", title_style))
                story.append(Spacer(1, 10))
                
                meta_text = [
                    [Paragraph("<b>School/Institution:</b> St. Michael Senior School - Kipsombe", meta_style), Paragraph("<b>Form Ref:</b> TSC/QAS/TPAD/TLAR/01/REV.2", meta_style)],
                    [Paragraph(f"<b>Class/Grade/Form:</b> {exp_class}", meta_style), Paragraph(f"<b>Date / Day:</b> {date_str} ({day_name})", meta_style)]
                ]
                meta_table = Table(meta_text, colWidths=[280, 280])
                meta_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
                story.append(meta_table)
                story.append(Spacer(1, 10))
                
                table_data = [["Period", "Subject Matter", "Assigned Teacher", "Status", "In", "Out", "Assg", "Remarks / Reasons"]]
                for r in records:
                    t_name = r[2] if r[2] else "N/A"
                    table_data.append([f"P{r[0]}", r[1], t_name, r[3], r[4], r[5], r[6], r[7]])
                    
                attendance_table = Table(table_data, colWidths=[40, 85, 115, 50, 45, 45, 40, 140])
                attendance_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EEEEEE")),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('ALIGN', (1,1), (2,-1), 'LEFT'),
                    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0,0), (-1,-1), 8.5),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ]))
                story.append(attendance_table)
                story.append(Spacer(1, 15))
                
                sig_style = ParagraphStyle('SigLine', parent=styles['Normal'], fontSize=8.5, leading=13)
                sig_text = [
                    [Paragraph("<b>Compiled By:</b> Class Secretary/Monitor<br/><br/>Sign: _______________________", sig_style),
                     Paragraph("<b>Verified By:</b> Deputy Head of Institution<br/><br/>Sign: _______________________", sig_style)],
                    [Paragraph("<br/>Date: _______________________", sig_style),
                     Paragraph("<br/>Date: _______________________", sig_style)],
                    [Paragraph("<br/><br/><b>Confirmed By:</b> Head of Institution<br/><br/>Sign: _______________________", sig_style),
                     Paragraph("<br/><br/><b>Official Institution Stamp Check:</b><br/><br/>[ Place Stamp Box Here ]", sig_style)]
                ]
                sig_table = Table(sig_text, colWidths=[280, 280])
                sig_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
                story.append(sig_table)
                
                doc.build(story)
                
                with open(filename, "rb") as pdf_file:
                    st.download_button(
                        label="📥 Download Official 10-Period PDF Report",
                        data=pdf_file,
                        file_name=filename,
                        mime="application/pdf",
                        use_container_width=True
                    )
