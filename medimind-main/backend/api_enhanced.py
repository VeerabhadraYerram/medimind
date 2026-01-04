from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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

def chunk_document(content: str, chunk_size: int = 3000, overlap: int = 200) -> List[str]:
    """Split a document into chunks with overlap for context preservation."""
    if len(content) <= chunk_size:
        return [content]
    
    chunks = []
    lines = content.split('\n')
    current_chunk = []
    current_length = 0
    
    for line in lines:
        line_length = len(line) + 1  # +1 for newline
        
        if current_length + line_length > chunk_size and current_chunk:
            # Save current chunk
            chunks.append('\n'.join(current_chunk))
            
            # Start new chunk with overlap (last few lines)
            overlap_lines = current_chunk[-overlap//50:] if len(current_chunk) > overlap//50 else current_chunk[-5:]
            current_chunk = overlap_lines + [line]
            current_length = sum(len(l) + 1 for l in current_chunk)
        else:
            current_chunk.append(line)
            current_length += line_length
    
    # Add final chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks

def summarize_chunk(chunk: str, chunk_num: int, total_chunks: int, question: str) -> str:
    """Summarize a single chunk of the document."""
    prompt = f"""You are summarizing a portion ({chunk_num} of {total_chunks}) of a medical document.

Original question: {question}

Document chunk:
{chunk}

Provide a concise summary of this portion focusing on:
- Key medical findings, test results, or observations
- Important dates, values, or measurements
- Any critical information relevant to the question

Summary:"""
    
    try:
        response = llm.invoke([HumanMessage(content=prompt)]).content
        return response.strip()
    except Exception as e:
        return f"[Error summarizing chunk {chunk_num}: {str(e)}]"

@app.post("/ask")
def ask(query: Query):
    """Enhanced query endpoint that analyzes across all documents."""
    documents, file_list = load_documents()
    
    if not documents or len(file_list) == 0:
        def stream_error():
            yield f"data: {json.dumps({'error': 'No documents available. Please upload files first.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(stream_error(), media_type="text/event-stream")
    
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
    
    # Check if this is a summarization request and document is large
    is_summary_request = any(term in question_lower for term in [
        'summarize', 'summary', 'summarise', 'overview', 'brief', 'key points', 'main points'
    ])
    
    # Check document size (rough token estimate: ~4 chars per token)
    # Account for prompt overhead (~1500-2000 tokens for instructions, patient data, etc.)
    doc_length = len(documents)
    doc_tokens_estimate = doc_length // 4
    PROMPT_OVERHEAD = 2000  # Estimated tokens for prompt instructions
    MAX_TOKENS_FOR_SINGLE_PASS = 2000  # Lower threshold to account for prompt overhead
    USE_CHUNKING = is_summary_request and (doc_tokens_estimate > MAX_TOKENS_FOR_SINGLE_PASS or doc_length > 8000)
    
    def stream():
        try:
            if USE_CHUNKING:
                # Chunk-based summarization for large documents
                yield f"data: {json.dumps({'status': 'chunking', 'message': f'Document is large ({doc_length:,} chars). Processing in chunks...'})}\n\n"
                time.sleep(0.1)  # Small delay to ensure message is sent
                
                # Split document into chunks
                chunks = chunk_document(documents, chunk_size=2500, overlap=200)
                total_chunks = len(chunks)
                
                yield f"data: {json.dumps({'status': 'processing', 'message': f'Processing {total_chunks} chunks...', 'total': total_chunks})}\n\n"
                time.sleep(0.1)
                
                chunk_summaries = []
                for i, chunk in enumerate(chunks, 1):
                    status_msg = f"Summarizing chunk {i} of {total_chunks}..."
                    yield f"data: {json.dumps({'status': 'chunk', 'message': status_msg, 'current': i, 'total': total_chunks})}\n\n"
                    time.sleep(0.1)
                    
                    try:
                        chunk_summary = summarize_chunk(chunk, i, total_chunks, query.question)
                        chunk_summaries.append(f"=== Chunk {i} Summary ===\n{chunk_summary}")
                    except Exception as e:
                        error_msg = f"Error summarizing chunk {i}: {str(e)}"
                        yield f"data: {json.dumps({'status': 'error', 'message': error_msg})}\n\n"
                        chunk_summaries.append(f"=== Chunk {i} Summary ===\n[Error: Could not summarize this chunk]")
                
                # Combine summaries
                if not chunk_summaries:
                    yield f"data: {json.dumps({'error': 'Failed to summarize any chunks'})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                
                yield f"data: {json.dumps({'status': 'combining', 'message': 'Combining summaries...'})}\n\n"
                time.sleep(0.1)
                
                combined_summaries = "\n\n".join(chunk_summaries)
                
                # Final summary of summaries - limit size to avoid token issues
                if len(combined_summaries) > 8000:
                    # If combined summaries are too long, summarize them first
                    yield f"data: {json.dumps({'status': 'finalizing', 'message': 'Summarizing chunk summaries...'})}\n\n"
                    time.sleep(0.1)
                    
                    summary_chunks = chunk_document(combined_summaries, chunk_size=4000, overlap=200)
                    summarized_chunks = []
                    for j, sum_chunk in enumerate(summary_chunks, 1):
                        try:
                            sum_summary = summarize_chunk(sum_chunk, j, len(summary_chunks), "Summarize this summary of summaries")
                            summarized_chunks.append(sum_summary)
                        except:
                            summarized_chunks.append(sum_chunk[:500] + "...")
                    combined_summaries = "\n\n".join(summarized_chunks)
                
                # Final summary of summaries
                final_prompt = f"""You are creating a comprehensive summary from multiple chunk summaries of a medical document.

Original question: {query.question}

Chunk summaries:
{combined_summaries}

Create a comprehensive, well-organized summary that:
1. Answers the original question: {query.question}
2. Integrates information from all chunks
3. Organizes findings logically (e.g., by test type, chronology, or importance)
4. Highlights key findings, abnormal values, and important observations
5. Maintains accuracy - only use information from the summaries above

Comprehensive Summary:"""
                
                yield f"data: {json.dumps({'status': 'finalizing', 'message': 'Creating final summary...'})}\n\n"
                time.sleep(0.1)
                
                try:
                    final_answer = llm.invoke([HumanMessage(content=final_prompt)]).content
                except Exception as e:
                    # If final summary fails, return combined summaries
                    yield f"data: {json.dumps({'status': 'error', 'message': f'Error creating final summary: {str(e)}. Returning chunk summaries...'})}\n\n"
                    final_answer = combined_summaries[:2000] + "\n\n[Note: This is a combination of chunk summaries. Full summary generation encountered an error.]"
                
                # Stream the final answer
                for word in final_answer.split():
                    yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                    time.sleep(0.01)
                
                yield f"data: {json.dumps({'final': {'answer': final_answer, 'files_analyzed': file_list, 'file_count': len(file_list)}})}\n\n"
                yield "data: [DONE]\n\n"
            else:
                # Standard single-pass processing for smaller documents or non-summary requests
                # Format documents with cross-file analysis instructions
                formatted_docs = format_documents_for_analysis(documents, file_list)
                
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
            error_msg = str(e)
            # Extract rate limit message if present
            if '429' in error_msg or 'rate limit' in error_msg.lower():
                error_msg = "Rate limit reached. The API has exceeded its token limit. Please wait a moment and try again."
            elif 'Error code: 429' in error_msg:
                # Try to extract a cleaner message
                try:
                    import json as json_module
                    if 'error' in error_msg:
                        error_msg = "Rate limit reached. Please wait a moment and try again."
                except:
                    pass
            
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

