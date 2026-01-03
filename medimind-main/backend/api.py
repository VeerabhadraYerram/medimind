from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, json, time
from pathlib import Path
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

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
    docs = []
    for f in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, f)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as file:
                docs.append(f"[Source: {f}]\n{file.read()}")
    return "\n\n".join(docs)

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

    prompt = f"""
You MUST answer using ONLY the information below.
If insufficient, respond exactly:
"Insufficient information."

INFORMATION:
{documents}

QUESTION:
{query.question}
"""

    def stream():
        try:
            # 🔥 ONE LLM CALL ONLY
            answer = llm.invoke([HumanMessage(content=prompt)]).content

            # 🔥 Token streaming (safe)
            for word in answer.split():
                yield f"data: {json.dumps({'token': word + ' '})}\n\n"
                time.sleep(0.02)

            # 🔥 Final metadata
            yield f"data: {json.dumps({'final': {'answer': answer}})}\n\n"
            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
