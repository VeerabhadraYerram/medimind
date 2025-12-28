"""
Development-only CLI agent used for testing Groq + LangChain
before integrating with FastAPI backend.
"""

import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

DATA_DIR = "./data"

def load_live_documents():
    docs = []
    for filename in os.listdir(DATA_DIR):
        path = os.path.join(DATA_DIR, filename)
        if os.path.isfile(path):
            with open(path, "r") as f:
                docs.append(f.read())
    return "\n".join(docs)

def ask_agent(question):
    context = load_live_documents()

    prompt = f"""
You are an intelligent assistant.

You MUST answer using ONLY the information explicitly present in the INFORMATION section.
DO NOT use prior knowledge, assumptions, or general world knowledge.
If the information is insufficient, say exactly what is missing and do NOT add anything else.

INFORMATION:
{context}

QUESTION:
{question}
"""

    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=os.environ["GROQ_API_KEY"]
    )

    response = llm.invoke([HumanMessage(content=prompt)])
    return response.content

if __name__ == "__main__":
    while True:
        q = input("\nAsk a question (or type 'exit'): ")
        if q.lower() == "exit":
            break
        print("\nAnswer:")
        print(ask_agent(q))
