from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os, json, time
from pathlib import Path
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

from backend.file_parsers import detect_and_parse_file
from backend.clinical_extractor import extract_clinical_data
from backend.patient_extractor import PatientDataExtractor
from backend.medical_standards import get_lab_reference_range, get_vital_reference_range

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# --------------------
# App
# --------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

# --------------------
# Models
# --------------------
class Query(BaseModel):
    question: str

# --------------------
# LLM
# --------------------
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise ValueError("GROQ_API_KEY not found in environment variables. Please check your .env file.")

llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=api_key,
)

# --------------------
# Helpers
# --------------------
def load_documents():
    """Load all documents from the data directory with proper source tracking and parsing."""
    docs = []
    file_info = []
    
    for f in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, f)
        if os.path.isfile(path) and not f.startswith('.'):
            try:
                # Read file as bytes first to allow parsing
                with open(path, "rb") as file:
                    content_bytes = file.read()
                
                # Parse file based on its format (HL7, EHR, JSON, XML, etc.)
                parsed_content = detect_and_parse_file(f, content_bytes)
                
                if parsed_content and parsed_content.strip():  # Only include non-empty files
                    docs.append(f"[Source: {f}]\n{parsed_content}")
                    file_info.append(f)
            except Exception as e:
                print(f"Error reading {f}: {e}")
                continue
    
    combined_docs = "\n\n---\n\n".join(docs)
    return combined_docs, file_info

def format_documents_for_analysis(documents: str, file_list: List[str]) -> str:
    """Format documents with clear file separation and analysis instructions."""
    if len(file_list) == 0:
        return "No documents available."
    
    if len(file_list) == 1:
        return f"DOCUMENT:\n{documents}"
    
    # Multiple files - format for cross-file analysis
    file_count = len(file_list)
    header = f"=== {file_count} DOCUMENTS LOADED ===\n"
    header += f"Files: {', '.join(file_list)}\n"
    header += "=" * 50 + "\n\n"
    header += "You have access to multiple documents. When answering:\n"
    header += "1. Compare information across different files\n"
    header += "2. Identify trends, patterns, or relationships between documents\n"
    header += "3. Note any contradictions or complementary information\n"
    header += "4. Cite which file(s) your answer comes from\n\n"
    header += "DOCUMENTS:\n" + documents
    
    return header

# --------------------
# Routes
# --------------------
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.get("/files")
def list_files():
    """Get list of all uploaded files."""
    files = []
    for f in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, f)
        if os.path.isfile(path) and not f.startswith('.'):
            try:
                size = os.path.getsize(path)
                files.append({
                    "name": f,
                    "size": size,
                    "size_kb": round(size / 1024, 2)
                })
            except:
                pass
    return {"files": files, "count": len(files)}

def load_files_data():
    """Helper to load and parse all files."""
    files_data = {}
    for f in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, f)
        if os.path.isfile(path) and not f.startswith('.'):
            try:
                with open(path, "rb") as file:
                    content_bytes = file.read()
                parsed_content = detect_and_parse_file(f, content_bytes)
                if parsed_content and parsed_content.strip():
                    files_data[f] = parsed_content
            except Exception as e:
                print(f"Error reading {f}: {e}")
                continue
    return files_data

@app.get("/patient-data")
def get_patient_data():
    """Extract and return all patient demographic and identification data."""
    try:
        files_data = load_files_data()
        
        if not files_data:
            return {
                "name": None,
                "age": None,
                "date_of_birth": None,
                "gender": None,
                "patient_id": None,
                "address": None,
                "phone": None,
                "email": None,
                "vital_signs": {},
                "message": "No files uploaded"
            }
        
        # Extract patient data
        extractor = PatientDataExtractor()
        patient_data = extractor.extract_patient_data(files_data)
        return patient_data
        
    except Exception as e:
        return {
            "error": str(e),
            "name": None,
            "age": None,
            "date_of_birth": None,
            "gender": None
        }

@app.get("/clinical-data")
def get_clinical_data():
    """Extract and return structured clinical data from uploaded files."""
    try:
        files_data = load_files_data()
        
        if not files_data:
            return {
                "events": [],
                "labs": [],
                "medications": [],
                "red_flags": [],
                "sections": {},
                "patient_data": {},
                "summary": {
                    "total_events": 0,
                    "total_labs": 0,
                    "abnormal_labs": 0,
                    "total_medications": 0,
                    "total_red_flags": 0,
                },
                "message": "No files uploaded"
            }
        
        # Extract clinical data
        clinical_data = extract_clinical_data(files_data)
        
        # Extract patient data
        extractor = PatientDataExtractor()
        patient_data = extractor.extract_patient_data(files_data)
        clinical_data["patient_data"] = patient_data
        
        # Enhance labs with reference ranges
        gender = patient_data.get("gender", "").upper() if patient_data.get("gender") else None
        for lab in clinical_data.get("labs", []):
            test_name = lab.get("test_name", "")
            if test_name:
                ref_range = get_lab_reference_range(test_name, gender)
                if ref_range and "normal" in ref_range:
                    if not lab.get("reference_range") or lab.get("reference_range") == "Not specified":
                        lab["reference_range"] = ref_range.get("normal", "Not specified")
                        if ref_range.get("units"):
                            lab["units"] = ref_range.get("units", lab.get("units", ""))
        
        return clinical_data
        
    except Exception as e:
        return {
            "error": str(e),
            "events": [],
            "labs": [],
            "medications": [],
            "red_flags": [],
            "sections": {},
            "patient_data": {}
        }

@app.post("/upload")
async def upload(files: List[UploadFile] = File(...)):
    """Upload one or multiple files at once. Supports .txt, .hl7, .json, .xml, .ehr, .fhir, .ccda, .cda files."""
    uploaded = []
    errors = []
    
    # Allowed file extensions
    allowed_extensions = {'.txt', '.hl7', '.hl7v2', '.hl7v3', '.json', '.xml', '.ehr', '.fhir', '.ccda', '.cda', '.pdf'}
    
    # FastAPI automatically collects files with the same field name into a list
    for file in files:
        try:
            content = await file.read()
            # Sanitize filename
            filename = file.filename
            if not filename:
                filename = f"upload_{int(time.time())}.txt"
            
            # Remove any path components for security
            filename = os.path.basename(filename)
            
            # Get file extension
            ext = Path(filename).suffix.lower()
            
            # If no extension or extension not in allowed list, default to .txt
            if not ext or ext not in allowed_extensions:
                # Try to detect format from content
                try:
                    content_str = content.decode('utf-8', errors='ignore')[:100]
                    if content_str.strip().startswith('MSH|'):
                        ext = '.hl7'
                    elif content_str.strip().startswith('{') or content_str.strip().startswith('['):
                        ext = '.json'
                    elif content_str.strip().startswith('<'):
                        ext = '.xml'
                    else:
                        ext = '.txt'
                except:
                    ext = '.txt'
                
                filename = filename.rsplit('.', 1)[0] + ext
            
            path = os.path.join(DATA_DIR, filename)
            
            # If file exists, append with timestamp
            if os.path.exists(path):
                base, ext = os.path.splitext(filename)
                filename = f"{base}_{int(time.time())}{ext}"
                path = os.path.join(DATA_DIR, filename)
            
            # Save file as binary to preserve format
            with open(path, "wb") as f:
                f.write(content)
            
            uploaded.append(filename)
        except Exception as e:
            file_name = file.filename if hasattr(file, 'filename') and file.filename else "unknown"
            errors.append({"file": file_name, "error": str(e)})
    
    return {
        "status": "uploaded",
        "files": uploaded,
        "count": len(uploaded),
        "errors": errors if errors else None
    }

@app.delete("/files/{filename}")
def delete_file(filename: str):
    """Delete a specific file."""
    # Security: prevent path traversal
    if '..' in filename or '/' in filename or '\\' in filename:
        return {"status": "error", "message": "Invalid filename"}
    
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
        return {"status": "deleted", "file": filename}
    return {"status": "error", "message": "File not found"}

@app.post("/ask")
def ask(query: Query):
    """Enhanced query endpoint that analyzes across all documents."""
    documents, file_list = load_documents()
    
    if not documents or len(file_list) == 0:
        def stream_error():
            yield f"data: {json.dumps({'error': 'No documents available. Please upload files first.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(stream_error(), media_type="text/event-stream")
    
    # Format documents with cross-file analysis instructions
    formatted_docs = format_documents_for_analysis(documents, file_list)
    
    # Extract patient data for context
    files_data = {}
    for f in sorted(os.listdir(DATA_DIR)):
        path = os.path.join(DATA_DIR, f)
        if os.path.isfile(path) and not f.startswith('.'):
            try:
                with open(path, "rb") as file:
                    content_bytes = file.read()
                parsed_content = detect_and_parse_file(f, content_bytes)
                if parsed_content and parsed_content.strip():
                    files_data[f] = parsed_content
            except:
                continue
    
    extractor = PatientDataExtractor()
    patient_data = extractor.extract_patient_data(files_data)
    
    # Check if question is about patient data
    question_lower = query.question.lower()
    is_patient_question = any(term in question_lower for term in [
        'patient', 'name', 'age', 'gender', 'date of birth', 'dob', 'demographics', 
        'who is', 'what is the patient', 'patient details', 'patient information'
    ])
    
    # Enhanced prompt with validation and error handling
    prompt = f"""You are a medical document analysis assistant. You MUST answer questions using ONLY the information explicitly provided in the documents below.

CRITICAL RULES - YOU MUST FOLLOW THESE STRICTLY:
1. USE ONLY INFORMATION FROM THE DOCUMENTS PROVIDED - DO NOT use any prior knowledge, medical knowledge, assumptions, or general information
2. If information is NOT in the documents, you MUST respond: "This information is not available in the uploaded files"
3. DO NOT make assumptions, inferences, or add information that is not explicitly stated
4. DO NOT provide general medical advice or knowledge that is not in the documents
5. If asked about something not mentioned in the files, explicitly state: "This information is not found in the uploaded documents"
6. For out-of-context questions unrelated to medical/patient data, respond: "This question is not related to the medical documents provided. Please ask about information from the uploaded files."
7. For inappropriate requests, respond: "I cannot answer that question. Please ask about information from the uploaded medical files."

DATA VALIDATION RULES:
- Patient names should contain only letters and spaces (no numbers or special characters in names)
- Ages should be numeric values
- Dates should be in standard formats (YYYY-MM-DD, MM/DD/YYYY)
- If data doesn't match expected format, state the data as found but note any format issues

EXTRACTED PATIENT DATA (from uploaded files):
Patient Name: {patient_data.get('name') or 'Not found in files'}
Age: {patient_data.get('age') or 'Not found in files'}
Date of Birth: {patient_data.get('date_of_birth') or 'Not found in files'}
Gender: {patient_data.get('gender') or 'Not found in files'}
Patient ID: {patient_data.get('patient_id') or 'Not found in files'}
Address: {patient_data.get('address') or 'Not found in files'}
Phone: {patient_data.get('phone') or 'Not found in files'}
Email: {patient_data.get('email') or 'Not found in files'}
Vital Signs: {patient_data.get('vital_signs') or 'Not found in files'}

IMPORTANT: When asked about patient information (name, age, gender, etc.), use the EXTRACTED PATIENT DATA above first. 
If the data is found above, provide it directly. If not found above, then search in the documents below.
List ALL available patient information when asked for patient details.

{formatted_docs}

QUESTION: {query.question}

STRICT ANSWERING RULES:
- Answer using ONLY the exact information present in the documents above
- You are FORBIDDEN from using any knowledge outside of these documents
- Quote or reference the specific information from the documents
- Cite which file(s) contain the information you're using
- If the question cannot be answered from the documents, say: "This information is not available in the uploaded files"
- If the question is out-of-context or inappropriate, use the appropriate response from rules above
- DO NOT supplement with general knowledge or assumptions
- DO NOT make inferences beyond what is explicitly stated
- DO NOT provide information that is not in the documents, even if you know it
- If information is insufficient, state exactly what is missing from the files
- For medical reports (HL7, EHR), extract and summarize only what is explicitly recorded
- Your answers must be 100% based on the uploaded reports - nothing else
- When listing patient data (name, age, etc.), list ALL available information from the files
- Format: For names, ensure they contain only letters (validate format)
- Format: For ages, ensure they are numeric
- If data format is incorrect (e.g., numbers in name), note it but report what is in the files

ANSWER (using ONLY information from the documents above - no other knowledge allowed):"""

    def stream():
        try:
            # Single LLM call for comprehensive analysis
            answer = llm.invoke([HumanMessage(content=prompt)]).content

            # Stream tokens
            for word in answer.split():
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                time.sleep(0.02)

            # Final metadata with file info
            yield f"data: {json.dumps({'final': {'answer': answer, 'files_analyzed': file_list, 'file_count': len(file_list)}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

