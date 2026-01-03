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
  }, [messages]);

  async function sendMessage() {
    if (!input.trim() || loading) return;

    const question = input;
    setInput("");
    setLoading(true);

    // User message
    setMessages((prev) => [
      ...prev,
      { role: "user", content: question },
      {
        role: "assistant",
        answer: "",
        plan: "",
        context: "",
        streaming: true,
      },
    ]);

    try {
      const res = await fetch("http://127.0.0.1:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
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

          // Streaming token
          if (parsed.token) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1].answer += parsed.token;
              return updated;
            });
          }

          // Final structured output
          if (parsed.final) {
            setMessages((prev) => {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...updated[updated.length - 1],
                answer: parsed.final.answer,
                plan: parsed.final.plan || "",
                context: parsed.final.context || "",
                streaming: false,
              };
              return updated;
            });
          }
        }
      }
    } catch (e) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          answer: "Error connecting to backend.",
          plan: "",
          context: "",
          streaming: false,
        };
        return updated;
      });
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
  }

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <h1>Synaptix Agent</h1>
        <p>Grounded AI over your documents</p>

        <label className="upload-btn">
          Upload .txt
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

      {/* Chat */}
      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">Ask a question to get started.</div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="bubble">
                {msg.role === "assistant" ? (
                  <>
                    <div className="answer-text">{msg.answer}</div>

                    {msg.plan && (
                      <details className="trace" open>
                        <summary>Plan</summary>
                        <pre>{msg.plan}</pre>
                      </details>
                    )}

                    {msg.context && (
                      <details className="trace">
                        <summary>Retrieved Context</summary>
                        <pre>{msg.context}</pre>
                      </details>
                    )}
                  </>
                ) : (
                  msg.content
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message assistant">
              <div className="bubble thinking">Thinking…</div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="input-bar">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Message Synaptix Agent…"
          />
          <button onClick={sendMessage}>Send</button>
        </div>
      </main>
    </div>
  );
}
