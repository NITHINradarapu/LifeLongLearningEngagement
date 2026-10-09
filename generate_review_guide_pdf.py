import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
    ListFlowable,
    ListItem
)

def build_pdf():
    pdf_filename = "Project_Review_Preparation_Guide.pdf"
    doc = SimpleDocTemplate(
        pdf_filename,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E1B4B'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#4F46E5'),
        spaceAfter=12
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#1E1B4B'),
        spaceBefore=14,
        spaceAfter=6
    )

    sub_heading = ParagraphStyle(
        'SubHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor('#312E81'),
        spaceBefore=8,
        spaceAfter=4
    )

    body = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=5
    )

    body_bold = ParagraphStyle(
        'CustomBodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#1E293B')
    )

    pitch_style = ParagraphStyle(
        'PitchText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13.5,
        textColor=colors.HexColor('#1F2937')
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
        alignment=0
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#1E293B')
    )

    table_cell_highlight = ParagraphStyle(
        'TableCellHighlight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#312E81')
    )

    elements = []

    # --- Title Banner Block ---
    banner_data = [
        [
            Paragraph("<b>ACADEMIC REVIEW &amp; VIVA DEFENSE PREPARATION GUIDE</b>", ParagraphStyle('BLabel', fontName='Helvetica-Bold', fontSize=8, textColor=colors.HexColor('#C7D2FE'))),
        ],
        [
            Paragraph("The Impact of Online Platforms on Lifelong Learning Engagement", ParagraphStyle('BTitle', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=colors.white))
        ],
        [
            Paragraph("<b>Platform:</b> AdaptiveLearn &nbsp;|&nbsp; <b>Tech Stack:</b> Python (Flask), SQLite, Google Gemini 2.0 AI, Chart.js &nbsp;|&nbsp; <b>Domain:</b> Adaptive Learning Systems", ParagraphStyle('BSub', fontName='Helvetica', fontSize=8, leading=11, textColor=colors.HexColor('#E0E7FF')))
        ]
    ]
    banner_table = Table(banner_data, colWidths=[522])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#1E1B4B')),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('CORNERPAD', (0, 0), (-1, -1), 6),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 10))

    # --- QUESTION 1 ---
    elements.append(Paragraph("1. Explain Your Title in Detail", section_heading))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceBefore=2, spaceAfter=6))

    pitch_data = [
        [
            Paragraph("<b>60-Second Elevator Pitch to Faculty:</b><br/>"
                      "<i>\"Respected panel members, our project investigates and tackles the core problem in digital education: <b>sustaining long-term learner engagement</b>. "
                      "While online education democratizes access, conventional platforms suffer from an industry-wide <b>85% to 95% dropout rate</b> due to passive video watching and rigid, non-personalized content.<br/><br/>"
                      "Our project demonstrates how an intelligent web platform—incorporating <b>Active In-Video Checkpoints, Generative AI Assessments, Topic-Level Mastery Diagnostics, and Gamified Habit Loops</b>—transforms learner engagement across behavioral, cognitive, and affective dimensions throughout lifelong education.\"</i>",
                      pitch_style)
        ]
    ]
    pitch_table = Table(pitch_data, colWidths=[522])
    pitch_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('LINEBEFORE', (0, 0), (0, -1), 3.5, colors.HexColor('#4F46E5')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(pitch_table)
    elements.append(Spacer(1, 6))

    q1_breakdown = [
        [
            Paragraph("<b>Key Term</b>", table_header),
            Paragraph("<b>Detailed Academic &amp; Technical Defense</b>", table_header)
        ],
        [
            Paragraph("<b>Online Platforms</b>", table_cell_highlight),
            Paragraph("Beyond static video libraries (like YouTube), this represents an active full-stack web ecosystem (Flask + SQLite + Gemini AI) that senses learner interaction in real time, intervenes at points of difficulty, and personalizes the educational trajectory.", table_cell)
        ],
        [
            Paragraph("<b>Lifelong Learning</b>", table_cell_highlight),
            Paragraph("Addresses self-directed, post-formal continuous upskilling (working professionals, career transitioners, higher-ed students). These learners lack physical classroom discipline and require flexible, bite-sized, autonomous pacing.", table_cell)
        ],
        [
            Paragraph("<b>Engagement (3 Dimensions)</b>", table_cell_highlight),
            Paragraph("<b>1. Behavioral:</b> Daily study streaks, target minutes, login consistency.<br/><b>2. Cognitive:</b> Active in-video retrieval checkpoints and conceptual mastery.<br/><b>3. Affective/Motivational:</b> Milestone points, gamification badges, transparent progress.", table_cell)
        ],
        [
            Paragraph("<b>The Impact (Hypothesis)</b>", table_cell_highlight),
            Paragraph("Quantifies the measurable shift: transitioning from passive, isolated content consumption (high attrition) to active, AI-guided adaptive learning that demonstrably sustains retention, completion rates, and subject-matter mastery.", table_cell)
        ]
    ]
    q1_table = Table(q1_breakdown, colWidths=[120, 402])
    q1_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#312E81')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(q1_table)
    elements.append(Spacer(1, 10))

    # --- QUESTION 2 ---
    elements.append(Paragraph("2. What Are the New Features That You Have Added in Your Project?", section_heading))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceBefore=2, spaceAfter=6))

    features_data = [
        [
            Paragraph("<b>#</b>", table_header),
            Paragraph("<b>Feature Name &amp; Module</b>", table_header),
            Paragraph("<b>Technical Implementation in Codebase</b>", table_header),
            Paragraph("<b>Impact on Learner Engagement</b>", table_header)
        ],
        [
            Paragraph("<b>1</b>", table_cell_highlight),
            Paragraph("<b>In-Video Active Checkpoints</b>", table_cell_highlight),
            Paragraph("Tables: <code>checkpoints</code>, <code>checkpoint_attempts</code>.<br/>Video event listeners trigger interactive questions at designated timestamps.", table_cell),
            Paragraph("Breaks passive video consumption; enforces active retrieval practice and real-time comprehension verification.", table_cell)
        ],
        [
            Paragraph("<b>2</b>", table_cell_highlight),
            Paragraph("<b>Generative AI Adaptive Assessments</b>", table_cell_highlight),
            Paragraph("Engine: <b>Google Gemini 2.0 Flash</b>.<br/>Validation: Pydantic schemas (<code>AIQuiz</code>, <code>AIQuestion</code>) with structured explanations and objective mapping.", table_cell),
            Paragraph("Generates fresh, objective-aligned diagnostic assessments on the fly; eliminates static rote memorization and question leaks.", table_cell)
        ],
        [
            Paragraph("<b>3</b>", table_cell_highlight),
            Paragraph("<b>Granular Topic-Level Mastery Tracking</b>", table_cell_highlight),
            Paragraph("Table: <code>learner_topic_performance</code>.<br/>Calculates accuracy per sub-topic, classifying into <i>Developing</i>, <i>Proficient</i>, or <i>Mastered</i>.", table_cell),
            Paragraph("Replaces vague overall course percentages with actionable cognitive diagnostics, pinpointing exact knowledge gaps.", table_cell)
        ],
        [
            Paragraph("<b>4</b>", table_cell_highlight),
            Paragraph("<b>Goal-Aligned Dynamic Learning Paths</b>", table_cell_highlight),
            Paragraph("Table: <code>learning_path_items</code>.<br/>Priority queue recommendations filtered by student career targets and baseline skill level.", table_cell),
            Paragraph("Prevents catalog paralysis; provides a personalized step-by-step roadmap tailored to each learner's aspirations.", table_cell)
        ],
        [
            Paragraph("<b>5</b>", table_cell_highlight),
            Paragraph("<b>Daily Habit Formation &amp; Gamification</b>", table_cell_highlight),
            Paragraph("Tables: <code>daily_learning_goals</code>, <code>gamification_events</code>, <code>users.streak</code>.<br/>Tracks daily minutes and checkpoint quotas.", table_cell),
            Paragraph("Applies habit-loop behavioral psychology (streaks, points, achievements) to sustain continuous daily engagement.", table_cell)
        ],
        [
            Paragraph("<b>6</b>", table_cell_highlight),
            Paragraph("<b>Instructor Analytics &amp; AI Audit Observability</b>", table_cell_highlight),
            Paragraph("Tables: <code>ai_generation_logs</code>, <code>messages</code>, <code>notifications</code>.<br/>Detailed student inspection &amp; prompt audit log.", table_cell),
            Paragraph("Gives educators early warning on at-risk learners while ensuring complete transparency and zero AI hallucination risk.", table_cell)
        ]
    ]
    feat_table = Table(features_data, colWidths=[20, 115, 195, 192])
    feat_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E1B4B')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(feat_table)
    elements.append(Spacer(1, 10))

    # --- QUESTION 3 ---
    elements.append(Paragraph("3. How Can You Differentiate Your Project with Existing Projects?", section_heading))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceBefore=2, spaceAfter=6))

    diff_data = [
        [
            Paragraph("<b>Dimension</b>", table_header),
            Paragraph("<b>Commercial MOOCs<br/>(Coursera, Udemy)</b>", table_header),
            Paragraph("<b>Video Sites / LMS<br/>(YouTube, Moodle)</b>", table_header),
            Paragraph("<b>Our Platform (AdaptiveLearn)</b>", table_header)
        ],
        [
            Paragraph("<b>Video Mode</b>", table_cell_highlight),
            Paragraph("Passive linear streaming with rare optional end-of-module quizzes.", table_cell),
            Paragraph("Completely passive video watching with zero cognitive validation.", table_cell),
            Paragraph("<b>Active In-Video Checkpoints:</b> Pauses playback at target timestamps for verified retrieval.", table_cell_highlight)
        ],
        [
            Paragraph("<b>Assessments</b>", table_cell_highlight),
            Paragraph("Static, pre-written question banks that never adapt.", table_cell),
            Paragraph("Manual instructor upload; questions are easily leaked.", table_cell),
            Paragraph("<b>Dynamic GenAI Engine:</b> Gemini 2.0 generates fresh, objective-based quizzes with structured reasoning.", table_cell_highlight)
        ],
        [
            Paragraph("<b>Analytics Depth</b>", table_cell_highlight),
            Paragraph("Coarse aggregate progress bar &amp; final exam grade.", table_cell),
            Paragraph("Simple view count or submission timestamps.", table_cell),
            Paragraph("<b>Cognitive Diagnostics:</b> Micro-topic breakdown classifying skills into Developing vs. Mastered.", table_cell_highlight)
        ],
        [
            Paragraph("<b>Adaptability</b>", table_cell_highlight),
            Paragraph("One-size-fits-all rigid curriculum sequence.", table_cell),
            Paragraph("Unstructured playlist or manual assignment drop.", table_cell),
            Paragraph("<b>Dynamic Career Pathways:</b> Course sequence tailored to self-declared career targets and skill deficits.", table_cell_highlight)
        ],
        [
            Paragraph("<b>Habit Loops</b>", table_cell_highlight),
            Paragraph("Generic automated email reminders.", table_cell),
            Paragraph("Deadline warnings and penalties only.", table_cell),
            Paragraph("<b>Positive Habit Mechanics:</b> Daily study targets, consecutive-day streaks, and milestone gamification.", table_cell_highlight)
        ],
        [
            Paragraph("<b>Auditability</b>", table_cell_highlight),
            Paragraph("Proprietary closed-source algorithms.", table_cell),
            Paragraph("Basic server access logs.", table_cell),
            Paragraph("<b>AI Observability Log:</b> Full prompt and response tracking via <code>ai_generation_logs</code>.", table_cell_highlight)
        ]
    ]
    diff_table = Table(diff_data, colWidths=[70, 140, 140, 172])
    diff_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#312E81')),
        ('BACKGROUND', (3, 1), (3, -1), colors.HexColor('#EEF2FF')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(diff_table)
    elements.append(Spacer(1, 10))

    # --- BONUS SECTION: VIVA QUICK DEFENSE ---
    elements.append(Paragraph("Bonus: Rapid-Fire Defense Cheatsheet for Your Team", section_heading))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceBefore=2, spaceAfter=6))

    viva_qa = [
        [
            Paragraph("<b>Frequently Asked Panel Question</b>", table_header),
            Paragraph("<b>Precise Technical Answer &amp; Code Justification</b>", table_header)
        ],
        [
            Paragraph("<b>How do you measure engagement quantitatively?</b>", table_cell_highlight),
            Paragraph("Through 3 quantitative parameters: <b>(1) Frequency &amp; Habit:</b> consecutive streak days and daily target minutes in <code>daily_learning_goals</code>. <b>(2) Active Interaction:</b> checkpoint attempt ratio during video playback. <b>(3) Cognitive Accuracy:</b> topic accuracy trajectory stored in <code>learner_topic_performance</code>.", table_cell)
        ],
        [
            Paragraph("<b>How do you safeguard against Generative AI hallucinations?</b>", table_cell_highlight),
            Paragraph("We enforce strict schema validation using <b>Pydantic models</b> (<code>AIQuiz</code> and <code>AIQuestion</code>) with Google GenAI SDK. If the AI output fails schema parsing or option count checks, the transaction rejects and logs to <code>ai_generation_logs</code>, guaranteeing error-free data in SQLite.", table_cell)
        ],
        [
            Paragraph("<b>Why SQLite instead of MongoDB or PostgreSQL?</b>", table_cell_highlight),
            Paragraph("SQLite provides immediate ACID compliance, relational foreign keys with cascading constraints (<code>ON DELETE CASCADE</code>), and zero-configuration portability for academic evaluation. Our schema design easily migrates to PostgreSQL for high-concurrency production deployments.", table_cell)
        ],
        [
            Paragraph("<b>What is the planned future scope?</b>", table_cell_highlight),
            Paragraph("Training a supervised Machine Learning model (Random Forest / Logistic Regression) on learner metrics (streak decay, quiz latency, checkpoint attempts) to compute an automated <b>Early Dropout Risk Score (0–100%)</b> that alerts teachers before a student disengages.", table_cell)
        ]
    ]
    viva_table = Table(viva_qa, colWidths=[170, 352])
    viva_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E1B4B')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F8FAFC')])
    ]))
    elements.append(viva_table)

    # Footer note
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<font color='#64748B' size='7.5'><i>Generated for Team Review &amp; Viva Defense • Project: The Impact of Online Platforms on Lifelong Learning Engagement • AdaptiveLearn System</i></font>", ParagraphStyle('Footer', alignment=1)))

    doc.build(elements)
    print(f"PDF successfully built: {os.path.abspath(pdf_filename)}")

if __name__ == "__main__":
    build_pdf()
