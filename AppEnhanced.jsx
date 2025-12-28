import { useState, useRef, useEffect } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

export default function AppEnhanced() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    // Load list of files on mount
    loadFiles();
  }, []);

  async function loadFiles() {
    try {
      const res = await fetch(`${API_URL}/files`);
      const data = await res.json();
      if (data.files) {
        setUploadedFiles(data.files.map(f => f.name));
      }
    } catch (e) {
      console.error("Error loading files:", e);
    }
  }

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
        streaming: true,
      },
    ]);

    try {
      const res = await fetch(`${API_URL}/ask`, {
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

          try {
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
                  filesAnalyzed: parsed.final.files_analyzed || [],
                  fileCount: parsed.final.file_count || 0,
                  streaming: false,
                };
                return updated;
              });
            }

            // Error handling
            if (parsed.error) {
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  answer: `Error: ${parsed.error}`,
                  streaming: false,
                };
                return updated;
              });
              setLoading(false);
            }
          } catch (e) {
            // Skip invalid JSON
            continue;
          }
        }
      }
    } catch (e) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          answer: "Error connecting to backend. Make sure the server is running.",
          streaming: false,
        };
        return updated;
      });
      setLoading(false);
    }
  }

  async function uploadFiles(files) {
    if (!files || files.length === 0) return;

    setUploading(true);
    const formData = new FormData();
    
    // Append all selected files with the correct field name
    // FastAPI expects the parameter name to match
    Array.from(files).forEach((file) => {
      formData.append("files", file);
    });

    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: "POST",
        body: formData,
      });

      const data = await res.json();
      
      if (data.files && data.files.length > 0) {
        // Reload file list
        await loadFiles();
        alert(`Successfully uploaded ${data.count} file(s): ${data.files.join(", ")}`);
      } else {
        alert("Upload failed. Please try again.");
      }
    } catch (e) {
      alert("Error uploading files. Please try again.");
      console.error("Upload error:", e);
    } finally {
      setUploading(false);
    }
  }

  async function deleteFile(filename) {
    if (!confirm(`Delete ${filename}?`)) return;

    try {
      const res = await fetch(`${API_URL}/files/${filename}`, {
        method: "DELETE",
      });

      const data = await res.json();
      if (data.status === "deleted") {
        await loadFiles();
        alert(`Deleted ${filename}`);
      }
    } catch (e) {
      alert("Error deleting file.");
      console.error("Delete error:", e);
    }
  }

  return (
    <div className="app">
      {/* Sidebar */}
      <aside className="sidebar">
        <h1>MediMind Agent</h1>
        <p>Multi-file document analysis</p>

        <label className="upload-btn" style={{ cursor: uploading ? "wait" : "pointer" }}>
          {uploading ? "Uploading..." : "Upload .txt Files"}
          <input
            type="file"
            accept=".txt"
            multiple
            hidden
            disabled={uploading}
            onChange={(e) => uploadFiles(e.target.files)}
          />
        </label>

        {uploadedFiles.length > 0 && (
          <div className="uploaded-files" style={{ marginTop: "20px" }}>
            <h3 style={{ fontSize: "14px", marginBottom: "10px", color: "#666" }}>
              Uploaded Files ({uploadedFiles.length})
            </h3>
            <div style={{ maxHeight: "300px", overflowY: "auto" }}>
              {uploadedFiles.map((file, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "8px",
                    marginBottom: "5px",
                    backgroundColor: "#f5f5f5",
                    borderRadius: "4px",
                    fontSize: "12px",
                  }}
                >
                  <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {file}
                  </span>
                  <button
                    onClick={() => deleteFile(file)}
                    style={{
                      marginLeft: "8px",
                      padding: "2px 8px",
                      fontSize: "11px",
                      backgroundColor: "#ff4444",
                      color: "white",
                      border: "none",
                      borderRadius: "3px",
                      cursor: "pointer",
                    }}
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {uploadedFiles.length === 0 && (
          <div style={{ marginTop: "20px", fontSize: "12px", color: "#999", fontStyle: "italic" }}>
            No files uploaded yet. Upload files to start analyzing.
          </div>
        )}
      </aside>

      {/* Chat */}
      <main className="chat">
        <div className="messages">
          {messages.length === 0 && (
            <div className="empty">
              {uploadedFiles.length === 0
                ? "Upload files first, then ask questions to analyze them."
                : `You have ${uploadedFiles.length} file(s) loaded. Ask questions to analyze them, or ask about trends across multiple files.`}
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="bubble">
                {msg.role === "assistant" ? (
                  <>
                    <div className="answer-text">{msg.answer}</div>
                    
                    {msg.filesAnalyzed && msg.filesAnalyzed.length > 0 && (
                      <details className="trace" style={{ marginTop: "10px" }}>
                        <summary>Files Analyzed ({msg.fileCount || msg.filesAnalyzed.length})</summary>
                        <div style={{ padding: "8px", fontSize: "12px" }}>
                          {msg.filesAnalyzed.map((file, idx) => (
                            <div key={idx} style={{ marginBottom: "4px" }}>• {file}</div>
                          ))}
                        </div>
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
              <div className="bubble thinking">Analyzing across {uploadedFiles.length} file(s)…</div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="input-bar">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
            placeholder={
              uploadedFiles.length > 1
                ? `Ask about trends across ${uploadedFiles.length} files...`
                : "Ask a question about your documents..."
            }
            disabled={uploadedFiles.length === 0}
          />
          <button onClick={sendMessage} disabled={uploadedFiles.length === 0 || loading}>
            Send
          </button>
        </div>
      </main>
    </div>
  );
}

