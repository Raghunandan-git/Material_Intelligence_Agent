# agent.py
import os
import json
import time
import random
import hashlib
import google.generativeai as genai
from typing import List, Dict, Optional, Any

API_KEY = "AIzaSyBVsE5mdfjAOJLl4jgVzGqulXo4HBpvNdM"

generation_config = {
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_mime_type": "text/plain",
}

SYSTEM_INSTRUCTION = """
    You are a Material Intelligence Agent for manufacturing and product design.
    
    Your Goal: Help the user select the best material for their application.
    
    PROTOCOL:
    1. When the user asks for a material (e.g., "I need a metal for..."), do NOT give an answer immediately.
    2. You MUST ask clarifying questions ONE-BY-ONE to narrow down requirements.
    3. Wait for the user's answer before asking the next question.
    
    Questions to ask (adapt based on context, ask only relevant ones):
       - Maximum operating temperature?
       - Required strength or load?
       - Indoor or outdoor environment?
       - Corrosion resistance required?
       - Lightweight or high-strength?
       - Budget limits?
       - Expected lifetime?
       - Conductivity needs?
       - Sustainability or recyclability preference?

    4. Once you have enough information, provide a Final Recommendation.
    
    Final Recommendation Format:
      • Summary of user requirements
      • Matching materials (from your knowledge base)
      • Comparison table
      • Explanation with exact property values (Tensile Strength, Density, etc.)
      • Final recommended material + trade-offs
    
    BEHAVIOR:
    - Be professional, helpful, and concise.
    - If the user asks for code (e.g., "Give me code for..."), ignore the material protocol and provide the code immediately.
    - Do not hallucinate properties. Use standard engineering values.
    - ALWAYS reference applicable standards (ASTM, DIN, EN, ISO) when providing material properties.
    - When recommending a material, cite the specific standard designation (e.g., "AISI 304" or "DIN 1.4301").

    

"""

class GeminiClient:
    def __init__(self, api_key: str, cache_dir: str = ".cache"):
        if not api_key:
            raise ValueError("API Key is required")
        
        genai.configure(api_key=api_key)
        
        self.cache_dir = cache_dir
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
        
        self.available_models = []
        self.current_model_index = 0
        self.model = None
        
        try:
            all_models = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            
            priorities = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro', 'gemini-pro']
            
            for p in priorities:
                for m in all_models:
                    if p in m.name and 'exp' not in m.name: # Avoid experimental if possible
                        if m.name not in [model.model_name for model in self.available_models]:
                             self.available_models.append(self._create_model(m.name))
            
            for m in all_models:
                if m.name not in [model.model_name for model in self.available_models]:
                     if 'exp' not in m.name or not self.available_models:
                        self.available_models.append(self._create_model(m.name))

            if not self.available_models:
                 raise ValueError("No suitable Gemini model found for this API key.")

            self.model = self.available_models[0]
            print(f"Selected initial model: {self.model.model_name}")
            print(f"Available fallback models: {[m.model_name for m in self.available_models[1:]]}")
                
        except Exception as e:
            print(f"Model discovery failed: {e}. Defaulting to gemini-1.5-flash-001")
            self.model = self._create_model('gemini-1.5-flash-001')
            self.available_models = [self.model]

    def _create_model(self, model_name: str):
        return genai.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
            system_instruction=SYSTEM_INSTRUCTION
        )

    def _get_cache_path(self, prompt: str) -> str:
        """Generates a unique filename for the prompt."""
        hash_obj = hashlib.md5(prompt.encode('utf-8'))
        return os.path.join(self.cache_dir, f"{hash_obj.hexdigest()}.json")

    def _read_cache(self, prompt: str) -> Optional[Any]:
        """Reads from cache if exists."""
        cache_path = self._get_cache_path(prompt)
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return None
        return None

    def _write_cache(self, prompt: str, data: Any):
        """Writes response to cache."""
        cache_path = self._get_cache_path(prompt)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

    def _switch_model(self):
        """Switches to the next available model in the list."""
        if len(self.available_models) <= 1:
            print("No other models available to switch to.")
            return False
        
        self.current_model_index = (self.current_model_index + 1) % len(self.available_models)
        self.model = self.available_models[self.current_model_index]
        print(f"Rate limit hit. Switching to model: {self.model.model_name}")
        return True

    def chat_with_retry(self, message: str, history: List[Dict[str, Any]]) -> str:
        """
        Sends a chat message with retry logic and model switching.
        """
        max_retries = 5
        base_delay = 2
        
        gemini_history = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            gemini_history.append({"role": role, "parts": [msg["content"]]})

        for attempt in range(max_retries):
            try:
                chat = self.model.start_chat(history=gemini_history)
                response = chat.send_message(message)
                return response.text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "quota" in error_str.lower():
                    print(f"Rate limit hit on {self.model.model_name}.")
                    
                    if self._switch_model():
                        time.sleep(1) 
                        continue
                    
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        print(f"Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                        continue
                
                if "404" in error_str:
                     print(f"Model {self.model.model_name} not found. Switching...")
                     if self._switch_model():
                         continue

                return f"Error communicating with AI: {str(e)}"
        
        return "Error: All AI models are currently unavailable or rate limited."

client = GeminiClient(api_key=API_KEY)

async def process_chat(message: str, history: List[Dict[str, str]]) -> str:
    return client.chat_with_retry(message, history)

async def generate_report_data(history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Analyzes the chat history to extract structured data for the engineering report.
    """
    prompt = """
    Analyze the following conversation history between a user and a Material Intelligence Agent.
    Extract the following information and return it as a JSON object:
    
    1. "constraints": A list of specific constraints mentioned by the user (e.g., "Temp > 500C", "Cost < $10/kg").
    2. "matches": A list of materials that were discussed or considered. For each, include "name" and a dictionary of "properties" (key-value pairs of properties mentioned).
    3. "explanation": A brief summary (max 100 words) of the AI's reasoning for the final recommendation.
    4. "recommendation": The name of the final recommended material.
    
    If any information is missing or not reached yet, leave it empty or null.
    
    Conversation History:
    """
    
    for msg in history:
        role = "User" if msg["role"] == "user" else "AI"
        prompt += f"\n{role}: {msg['content']}"
        
    prompt += "\n\nReturn ONLY raw JSON."
    
    try:
        response_text = client.chat_with_retry(prompt, [])
        # Clean up potential markdown code blocks
        response_text = response_text.replace("```json", "").replace("```", "").strip()
        data = json.loads(response_text)
        return data
    except Exception as e:
        print(f"Error generating report data: {e}")
        return {
            "constraints": [],
            "matches": [],
            "explanation": "Could not generate explanation due to an error.",
            "recommendation": "Unknown"
        }
