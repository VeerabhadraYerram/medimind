# MediMind Agent 

MediMind Agent is a document-grounded AI assistant built using **FastAPI**, **LangGraph**, and **Groq LLMs**.  
It answers user questions strictly based on the provided documents, ensuring **no hallucinations**.

---

## Key Features

- Document-grounded question answering
- LangGraph-based agent workflow:
  - Plan step
  - Retrieve step
  - Answer step
- Clean ChatGPT-like frontend UI
- Fast inference using Groq LLMs

---

## Tech Stack

### Backend
- **FastAPI** – API server
- **LangChain** – LLM orchestration
- **LangGraph** – Agent planning & execution
- **Groq** – Ultra-fast LLM inference

### Frontend
- **React (Vite)** – UI
- **Fetch API** – Backend communication
- **Custom CSS** – ChatGPT-style layout

---

## Project Structure

synaptix-track1/
├── backend/
│   └── api.py              # Production FastAPI + LangGraph agent
├── frontend/               
│   ├── src/                
│   │   ├── App.jsx         # React chat UI
│   │   └── App.css
│   ├── package.json
│   └── vite.config.js              
├── data/
│   └── documents.txt       # Grounding documents
├── scripts/
│   └── agent_app.py        # CLI testing agent (dev-only)
├── experiments/
│   └── live_pathway_app.py # Pathway streaming demo
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md

## Additional Scripts

- `scripts/agent_app.py`  
  CLI-based LLM agent used during development for rapid testing.

- `experiments/live_pathway_app.py`  
  Demonstrates Pathway’s real-time streaming capabilities on document ingestion.


