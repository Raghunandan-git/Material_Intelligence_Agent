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
from reportlab.platypus import Image as ReportLabImage
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
    report_data = await generate_report_data(session.get("history", []))
    
    # 2. Generate PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = styles['Title']
    story.append(Paragraph("Material Intelligence Agent - Engineering Report", title_style))
    story.append(Spacer(1, 12))

    # Metadata
    normal_style = styles['Normal']
    story.append(Paragraph(f"<b>Date:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    story.append(Paragraph(f"<b>Session ID:</b> {session_id}", normal_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f"<b>Project:</b> {session.get('title', 'Untitled Project')}", normal_style))
    story.append(Spacer(1, 24))

    # Constraints
    story.append(Paragraph("<b>1. Design Constraints</b>", styles['Heading2']))
    if report_data.get("constraints"):
        for constraint in report_data["constraints"]:
            story.append(Paragraph(f"• {constraint}", normal_style))
    else:
        story.append(Paragraph("No specific constraints identified.", normal_style))
    story.append(Spacer(1, 12))

    # Matches Table
    story.append(Paragraph("<b>2. Material Matches & Comparison</b>", styles['Heading2']))
    matches = report_data.get("matches", [])
    if matches:
        table_data = [['Material', 'Properties']]
        for match in matches:
            props = ", ".join([f"{k}: {v}" for k, v in match.get("properties", {}).items()])
            table_data.append([match.get("name", "Unknown"), props])
        
        t = Table(table_data, colWidths=[150, 300])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No specific material matches found yet.", normal_style))
    story.append(Spacer(1, 12))

    # Visualizations
    story.append(Paragraph("<b>3. Material Property Visualizations</b>", styles['Heading2']))
    
    # Generate charts
    charts = generate_charts(report_data)
    
    if charts:
        if 'tensile' in charts:
            story.append(Paragraph("Tensile Strength Comparison", styles['Heading3']))
            img = ReportLabImage(charts['tensile'], width=400, height=250)
            story.append(img)
            story.append(Spacer(1, 12))
            
        if 'density' in charts:
            story.append(Paragraph("Density Comparison", styles['Heading3']))
            img = ReportLabImage(charts['density'], width=400, height=250)
            story.append(img)
            story.append(Spacer(1, 12))

        if 'radar' in charts:
            story.append(Paragraph("Performance Radar Chart", styles['Heading3']))
            img = ReportLabImage(charts['radar'], width=400, height=400)
            story.append(img)
            story.append(Spacer(1, 12))
    else:
        story.append(Paragraph("Not enough data to generate charts.", normal_style))
    story.append(Spacer(1, 12))

    # Explanation
    story.append(Paragraph("<b>4. AI Analysis</b>", styles['Heading2']))
    story.append(Paragraph(report_data.get("explanation", "No explanation available."), normal_style))
    story.append(Spacer(1, 12))

    # Recommendation
    story.append(Paragraph("<b>5. Final Recommendation</b>", styles['Heading2']))
    story.append(Paragraph(f"<b>{report_data.get('recommendation', 'Pending')}</b>", styles['Heading3']))
    story.append(Spacer(1, 12))

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
