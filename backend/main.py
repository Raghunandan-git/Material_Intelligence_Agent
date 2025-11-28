#main.py
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.models import ChatRequest, ChatResponse, ChatSession
from backend.agent import process_chat, generate_report_data
from backend.charts import generate_charts
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as ReportLabImage, Frame, PageTemplate, NextPageTemplate
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from datetime import datetime

app = FastAPI(title="Material Intelligence Agent")

MONGO_URI = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_URI)
db = client.material_db
sessions_collection = db.sessions

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/sessions", response_model=List[ChatSession])
async def get_sessions():
    sessions = []
    async for session in sessions_collection.find().sort("created_at", -1):
        session["_id"] = str(session["_id"])
        sessions.append(session)
    return sessions

@app.post("/api/sessions", response_model=ChatSession)
async def create_session():
    new_session = {
        "title": "New Chat",
        "history": [],
        "created_at": datetime.now().isoformat()
    }
    result = await sessions_collection.insert_one(new_session)
    new_session["_id"] = str(result.inserted_id)
    return new_session

@app.get("/api/sessions/{session_id}", response_model=ChatSession)
async def get_session(session_id: str):
    try:
        session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
        if session:
            session["_id"] = str(session["_id"])
            return session
        raise HTTPException(status_code=404, detail="Session not found")
    except:
        raise HTTPException(status_code=404, detail="Invalid Session ID")

@app.post("/api/chat/{session_id}", response_model=ChatResponse)
async def chat_endpoint(session_id: str, request: ChatRequest):
    try:
        session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
        if not session:
             raise HTTPException(status_code=404, detail="Session not found")
    except:
        raise HTTPException(status_code=404, detail="Invalid Session ID")

    current_history = session.get("history", [])
    current_history.append({"role": "user", "content": request.message})
    
    update_fields = {"history": current_history}
    if len(current_history) == 1:
        update_fields["title"] = request.message[:30] + "..." if len(request.message) > 30 else request.message

    await sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": update_fields}
    )

    response_text = await process_chat(request.message, current_history[:-1]) # Send history excluding current msg as agent might append it internally or we handle it here. 
    
    current_history.append({"role": "assistant", "content": response_text})
    await sessions_collection.update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"history": current_history}}
    )

    return ChatResponse(response=response_text)

@app.get("/api/generate-report/{session_id}")
async def generate_report(session_id: str):
    try:
        session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
    except:
        raise HTTPException(status_code=404, detail="Invalid Session ID")

    # 1. Get Data from AI
    report_data = session.get("report_data")
    if not report_data:
        report_data = await generate_report_data(session.get("history", []))
        await sessions_collection.update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"report_data": report_data}}
        )
    
    # 2. Generate PDF
    buffer = BytesIO()
    
    # Document Setup
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter,
        rightMargin=0.8*inch, 
        leftMargin=0.8*inch, 
        topMargin=0.8*inch, 
        bottomMargin=0.8*inch
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'ReportTitle',
        parent=styles['Title'],
        fontSize=24,
        leading=30,
        alignment=TA_CENTER,
        spaceAfter=20,
        textColor=colors.HexColor('#2c3e50')
    )
    
    subtitle_style = ParagraphStyle(
        'ReportSubtitle',
        parent=styles['Heading2'],
        fontSize=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#7f8c8d'),
        spaceAfter=40
    )
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=18,
        leading=22,
        spaceBefore=20,
        spaceAfter=12,
        textColor=colors.HexColor('#2c3e50'),
        borderPadding=5,
        borderWidth=0,
        borderColor=colors.HexColor('#2c3e50')
    )
    
    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Heading3'],
        fontSize=14,
        spaceBefore=12,
        spaceAfter=8,
        textColor=colors.HexColor('#34495e')
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6
    )

    # Page Templates
    def cover_page(canvas, doc):
        canvas.saveState()
        # Accent Bar
        canvas.setFillColor(colors.HexColor('#2c3e50'))
        canvas.rect(0, 0, 0.3*inch, 11*inch, fill=1)
        canvas.restoreState()

    def later_pages(canvas, doc):
        canvas.saveState()
        # Header
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.grey)
        canvas.drawString(0.8*inch, 10.5*inch, "Material Intelligence Report")
        canvas.drawRightString(7.7*inch, 10.5*inch, datetime.now().strftime('%Y-%m-%d'))
        canvas.line(0.8*inch, 10.4*inch, 7.7*inch, 10.4*inch)
        
        # Footer
        canvas.drawString(0.8*inch, 0.5*inch, f"Session ID: {session_id}")
        canvas.drawRightString(7.7*inch, 0.5*inch, f"Page {doc.page}")
        canvas.restoreState()

    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id='normal')
    doc.addPageTemplates([
        PageTemplate(id='Cover', frames=frame, onPage=cover_page),
        PageTemplate(id='Normal', frames=frame, onPage=later_pages)
    ])

    story = []

    # --- COVER PAGE ---
    story.append(Spacer(1, 2*inch))
    story.append(Paragraph("Material Intelligence Agent", title_style))
    story.append(Paragraph("Engineering Report", title_style))
    story.append(Paragraph("AI-Powered Material Selection System", subtitle_style))
    
    story.append(Spacer(1, 1*inch))
    
    # Metadata Table for Cover
    meta_data = [
        ["Project Title:", session.get('title', 'Untitled Project')],
        ["Date:", datetime.now().strftime('%B %d, %Y')],
        ["Session ID:", session_id],
        ["Generated By:", "Material Intelligence Agent v1.0"]
    ]
    
    t_meta = Table(meta_data, colWidths=[2*inch, 3.5*inch])
    t_meta.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#2c3e50')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(t_meta)
    
    story.append(NextPageTemplate('Normal'))
    story.append(PageBreak())

    # --- CONTENT PAGES ---

    # 1. Design Constraints
    story.append(Paragraph("1. Design Constraints", heading_style))
    story.append(Paragraph("The following constraints were identified based on the user requirements:", normal_style))
    story.append(Spacer(1, 12))
    
    constraints = report_data.get("constraints", [])
    if constraints:
        # Format as table
        c_data = [["No.", "Constraint Description"]]
        for i, c in enumerate(constraints, 1):
            c_data.append([str(i), c])
            
        t_const = Table(c_data, colWidths=[0.5*inch, 5.5*inch])
        t_const.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ecf0f1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9f9f9')])
        ]))
        story.append(t_const)
    else:
        story.append(Paragraph("No specific constraints identified.", normal_style))
    
    story.append(Spacer(1, 20))

    # 2. Material Comparison
    story.append(Paragraph("2. Material Comparison", heading_style))
    matches = report_data.get("matches", [])
    if matches:
        table_data = [['Material Candidate', 'Key Properties']]
        for match in matches:
            # Format properties nicely
            props_list = []
            for k, v in match.get("properties", {}).items():
                props_list.append(f"<b>{k}:</b> {v}")
            props_str = "<br/>".join(props_list)
            
            table_data.append([Paragraph(f"<b>{match.get('name', 'Unknown')}</b>", normal_style), Paragraph(props_str, normal_style)])
        
        t_mat = Table(table_data, colWidths=[2*inch, 4*inch])
        t_mat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f2f6f8')])
        ]))
        story.append(t_mat)
    else:
        story.append(Paragraph("No specific material matches found yet.", normal_style))
    
    story.append(Spacer(1, 20))
    story.append(PageBreak())

    # 3. Visualizations
    story.append(Paragraph("3. Material Property Visualizations", heading_style))
    
    charts = generate_charts(report_data)
    
    if charts:
        # Helper to add chart with border
        def add_chart(key, title):
            if key in charts:
                story.append(Paragraph(title, subheading_style))
                img = ReportLabImage(charts[key], width=6*inch, height=3.6*inch)
                # Add a border around the image? ReportLab images don't have borders easily.
                # We can put it in a table cell with a border.
                t_img = Table([[img]], colWidths=[6.2*inch])
                t_img.setStyle(TableStyle([
                    ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#bdc3c7')),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ]))
                story.append(t_img)
                story.append(Spacer(1, 15))

        add_chart('tensile', "Tensile Strength Analysis")
        add_chart('density', "Density Comparison")
        
        if 'radar' in charts:
             story.append(PageBreak())
             story.append(Paragraph("3. Material Property Visualizations (Cont.)", heading_style))
             add_chart('radar', "Multi-Factor Performance Analysis")

    else:
        story.append(Paragraph("Not enough data to generate charts.", normal_style))
    
    story.append(Spacer(1, 20))

    # 4. AI Analysis
    story.append(Paragraph("4. AI Reasoning", heading_style))
    story.append(Paragraph(report_data.get("explanation", "No explanation available."), normal_style))
    story.append(Spacer(1, 20))

    # 5. Recommendation
    story.append(Paragraph("5. Final Recommendation", heading_style))
    
    rec_text = report_data.get('recommendation', 'Pending')
    
    # Highlight box for recommendation
    rec_table = Table([[Paragraph(f"<b>RECOMMENDED MATERIAL:</b><br/><br/>{rec_text}", 
                                  ParagraphStyle('RecStyle', parent=normal_style, fontSize=14, alignment=TA_CENTER, textColor=colors.HexColor('#27ae60')))]], 
                      colWidths=[6*inch])
    rec_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#27ae60')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#eafaf1')),
        ('TOPPADDING', (0, 0), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(rec_table)

    doc.build(story)
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=material_report.pdf"})

@app.get("/api/charts/{chart_type}/{session_id}")
async def get_chart(chart_type: str, session_id: str):
    try:
        session = await sessions_collection.find_one({"_id": ObjectId(session_id)})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # We need report data to generate charts. 
        # Ideally we cache this, but for now we regenerate or fetch if we saved it.
        # To avoid re-calling AI every time, let's assume the report generation 
        # saves it or we just re-generate (it's a few seconds).
        # Optimization: Check if 'report_data' is in session, if not generate and save.
        
        report_data = session.get("report_data")
        if not report_data:
            report_data = await generate_report_data(session.get("history", []))
            await sessions_collection.update_one(
                {"_id": ObjectId(session_id)},
                {"$set": {"report_data": report_data}}
            )
            
        charts = generate_charts(report_data)
        
        if chart_type in charts:
            return StreamingResponse(charts[chart_type], media_type="image/png")
        else:
            # Return empty image or 404? 404 is better.
            raise HTTPException(status_code=404, detail="Chart not available")
            
    except Exception as e:
        print(f"Error generating chart: {e}")
        raise HTTPException(status_code=500, detail=str(e))

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    print(f"Frontend directory not found at {frontend_path}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
