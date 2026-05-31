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
            
            # Using landscape page orientation layout configurations (792 width x 612 height)
            # Margins set defensively to 20pt to maximize printable area
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
                
            # Maximize layout space to completely lock Section A on Page 1
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
            
            # FORCE PAGE BREAK TO GENERATE PAGE 2
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
                ('TOPPADDING', (0,0), (-1,-1), 1.5),  # Ultra tight padding to guarantee 2-page hard ceiling
                ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 6))
            
            # AUTHORIZATION SIGNATURE GRID FOOTER (Optimized leading and padding)
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
