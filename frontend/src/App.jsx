import { useState, useRef, useEffect } from "react";
import "./App.css";

export default function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(questionText = "") {
    if (loading) return;

    setLoading(true);

    // Add user message only if question exists
    if (questionText) {
      setMessages((prev) => [
        ...prev,
        { role: "user", content: questionText },
      ]);
    }

    // Add placeholder assistant message
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: "",
        streaming: true,
      },
    ]);

    try {
      const res = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: questionText || null, // IMPORTANT
        }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;

          const payload = line.replace("data:", "").trim();
          if (!payload || payload === "[DONE]") {
            setLoading(false);
            continue;
          }

          const parsed = JSON.parse(payload);

          if (parsed.token) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1].content += parsed.token;
              return updated;
            });
          }

          if (parsed.final) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                role: "assistant",
                content: parsed.final.answer,
                streaming: false,
              };
              return updated;
            });
          }
        }
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Error connecting to backend.",
          streaming: false,
        },
      ]);
      setLoading(false);
    }
  }

  async function uploadFile(file) {
    const formData = new FormData();
    formData.append("file", file);

    await fetch("http://127.0.0.1:8000/upload", {
      method: "POST",
      body: formData,
    });

    setUploadedFile(file.name);

    // AUTO-RUN INTAKE AFTER UPLOAD
    sendMessage("");
  }

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <h1>MediMind</h1>
        <p>Clinical Patient Intake Assistant</p>

        <label className="upload-btn">
          Upload Patient Record (.txt)
          <input
            type="file"
            accept=".txt"
            hidden
            onChange={(e) => uploadFile(e.target.files[0])}
          />
        </label>

        {uploadedFile && (
          <div className="uploaded">
            Uploaded: <strong>{uploadedFile}</strong>
          </div>
        )}
      </aside>

      {/* Main Chat */}
      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              Upload a patient record to generate intake summary.
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="bubble">
                {msg.content}
                {msg.streaming && <span className="cursor">▌</span>}
              </div>
            </div>
          ))}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="input-bar">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && input.trim()) {
                sendMessage(input.trim());
                setInput("");
              }
            }}
            placeholder="Ask about the patient (e.g., medications, red flags)"
            disabled={!uploadedFile}
          />
          <button
            onClick={() => {
              if (input.trim()) {
                sendMessage(input.trim());
                setInput("");
              }
            }}
            disabled={!uploadedFile || loading}
          >
            Send
          </button>
        </div>
      </main>
    </div>
  );
}
