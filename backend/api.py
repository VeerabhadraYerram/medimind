from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json, time

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# --------------------
# App
# --------------------
app = FastAPI(title="MediMind – Clinical Intake Agent")

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
    question: str | None = None  # Doctor may or may not ask a question

# --------------------
# LLM
# --------------------
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=os.environ["GROQ_API_KEY"],
)

# --------------------
# Helpers
# --------------------
def load_documents():
    docs = []
    for f in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, f)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as file:
                docs.append(f"[Source: {f}]\n{file.read()}")
    return "\n\n".join(docs)

# --------------------
# Prompts
# --------------------
CLINICAL_INTAKE_PROMPT = """
Generate a structured clinical patient intake summary using ONLY the data provided.

Return the output STRICTLY in this format:

Patient Summary:
- Age:
- Gender:
- Chief Complaint:

Medical History:
- Chronic conditions:
- Past diagnoses:

Current Admission Findings:
- Symptoms:
- Abnormal lab results:
- Imaging findings:

Procedures / Interventions:
- (List if present, else say "Not mentioned in records")

Medications:
- Current medications:
- Discharge medications:

Red Flags / Critical Observations:
- (Only if explicitly mentioned, else say "None mentioned")

Missing or Unclear Information:
- (List important clinical info not present in records)

If any field is missing, explicitly write: "Not mentioned in records".
"""

QA_PROMPT_TEMPLATE = """
You are MediMind, a clinical assistant for doctors.

Answer the question using ONLY the patient records below.
If the answer is not present, say exactly: "Not mentioned in records".

PATIENT RECORDS:
{documents}

QUESTION:
{question}
"""

# --------------------
# Routes
# --------------------
@app.get("/ping")
def ping():
    return {"status": "ok"}

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    path = os.path.join(DATA_DIR, file.filename)
    with open(path, "wb") as f:
        f.write(content)
    return {"status": "uploaded", "file": file.filename}

@app.post("/ask")
def ask(query: Query):
    documents = load_documents()

    # Auto mode detection
    is_question = bool(query.question and query.question.strip())

    if not is_question:
        final_prompt = f"""
{CLINICAL_INTAKE_PROMPT}

PATIENT RECORDS:
{documents}
"""
    else:
        final_prompt = f"""
You are MediMind, a clinical patient intake assistant for doctors.

Answer the question using ONLY the patient records below.
If the answer is not present, say: "Not mentioned in records".

PATIENT RECORDS:
{documents}

QUESTION:
{query.question}
"""

    def stream():
        try:
            answer = llm.invoke([HumanMessage(content=final_prompt)]).content

            for word in answer.split():
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                time.sleep(0.02)

            yield f"data: {json.dumps({'final': {'answer': answer}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

    # --------------------
    # Streaming response
    # --------------------
    def stream():
        try:
            answer = llm.invoke(
                [HumanMessage(content=final_prompt)]
            ).content

            # Token-style streaming
            for word in answer.split():
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                time.sleep(0.015)

            yield f"data: {json.dumps({'final': {'answer': answer}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
