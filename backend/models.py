# models.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class MaterialProperties(BaseModel):
    tensile_strength: Optional[str] = ""
    yield_strength: Optional[str] = ""
    density: Optional[str] = ""
    melting_point: Optional[str] = ""
    thermal_limit: Optional[str] = ""
    pressure_limit: Optional[str] = ""
    corrosion_resistance: Optional[str] = ""
    hardness: Optional[str] = ""
    electrical_conductivity: Optional[str] = ""
    thermal_conductivity: Optional[str] = ""
    cost: Optional[str] = ""
    recyclability: Optional[str] = ""
    sustainability_rating: Optional[str] = ""

class Material(BaseModel):
    name: str
    category: Optional[str] = ""
    properties: MaterialProperties
    applications: List[str] = []
    source: str = "pdf"

class ChatRequest(BaseModel):
    message: str
    history: List[Dict[str, str]] = [] 

class ChatResponse(BaseModel):
    response: str
    data: Optional[Dict[str, Any]] = None 

class ChatSession(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    title: str = "New Chat"
    history: List[Dict[str, str]] = []
    created_at: Optional[str] = None

