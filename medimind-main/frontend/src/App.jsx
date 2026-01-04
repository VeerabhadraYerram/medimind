import { useState, useRef, useEffect } from "react";
import "./App.css";
import ClinicalVisualizations from "./ClinicalVisualizations";
import "./ClinicalVisualizations.css";

const API_URL = "http://127.0.0.1:8000";

export default function AppEnhanced() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [activeTab, setActiveTab] = useState("chat"); // "chat" or "clinical"
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

      // Check if response is ok
      if (!res.ok) {
        throw new Error(`HTTP error! status: ${res.status}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let hasError = false;

      while (true) {
        const { value, done } = await reader.read();
        if (done) {
          if (!hasError) {
            setLoading(false);
          }
          break;
        }

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n");

        for (const line of lines) {
          if (!line.startsWith("data:")) continue;

          const payload = line.replace("data:", "").trim();
          if (!payload || payload === "[DONE]") {
            if (!hasError) {
              setLoading(false);
            }
            continue;
          }

          try {
            const parsed = JSON.parse(payload);

            // Error handling - check first
            if (parsed.error) {
              hasError = true;
              let errorMessage = parsed.error;
              
              // Handle rate limit errors specifically
              if (typeof parsed.error === 'string') {
                if (parsed.error.includes('429') || parsed.error.includes('Rate limit') || parsed.error.includes('rate limit')) {
                  errorMessage = "⚠️ Rate limit reached. The API has exceeded its token limit. Please wait 30-60 seconds and try again.";
                } else if (parsed.error.includes('Error code: 429')) {
                  errorMessage = "⚠️ Rate limit reached. Please wait 30-60 seconds and try again.";
                }
              }
              
              setMessages((prev) => {
                const updated = [...prev];
                updated[updated.length - 1] = {
                  role: "assistant",
                  answer: errorMessage,
                  streaming: false,
                };
                return updated;
              });
              setLoading(false);
              break; // Exit the loop on error
            }

            // Status messages for chunking progress
            if (parsed.status) {
              setMessages((prev) => {
                const updated = [...prev];
                if (updated.length > 0) {
                  // Update status message - append or replace based on status
                  const statusMsg = parsed.message || '';
                  const currentAnswer = updated[updated.length - 1].answer || '';
                  
                  // For chunk status, show progress; for others, update message
                  if (parsed.status === 'chunking') {
                    updated[updated.length - 1].answer = `📄 ${statusMsg}\n`;
                  } else if (parsed.status === 'processing') {
                    updated[updated.length - 1].answer = `📄 Document is large. Processing in chunks...\n🔄 ${statusMsg}\n`;
                  } else if (parsed.status === 'chunk') {
                    // Show progress: "Processing chunk X of Y..."
                    const progressMsg = `📝 ${statusMsg}`;
                    // Keep previous status messages and add new one
                    if (!currentAnswer.includes('📝 Summarizing chunk')) {
                      updated[updated.length - 1].answer = currentAnswer + progressMsg + '\n';
                    } else {
                      // Update the chunk progress line
                      const lines = currentAnswer.split('\n');
                      const newLines = lines.filter(l => !l.includes('📝 Summarizing chunk'));
                      newLines.push(progressMsg);
                      updated[updated.length - 1].answer = newLines.join('\n') + '\n';
                    }
                  } else if (parsed.status === 'combining') {
                    updated[updated.length - 1].answer = currentAnswer + `🔗 ${statusMsg}\n`;
                  } else if (parsed.status === 'finalizing') {
                    updated[updated.length - 1].answer = currentAnswer + `✨ ${statusMsg}\n`;
                  } else if (parsed.status === 'error') {
                    updated[updated.length - 1].answer = currentAnswer + `⚠️ ${statusMsg}\n`;
                  }
                  updated[updated.length - 1].streaming = true;
                }
                return updated;
              });
            }

            // Streaming token - when tokens arrive, clear status messages and show answer
            if (parsed.token) {
              setMessages((prev) => {
                const updated = [...prev];
                if (updated.length > 0) {
                  const currentAnswer = updated[updated.length - 1].answer || '';
                  // If this is the first token and we have status messages, clear them
                  if (currentAnswer.includes('📄') || currentAnswer.includes('🔄') || currentAnswer.includes('📝')) {
                    // Check if this is the start of actual content (not just status)
                    if (!currentAnswer.includes(parsed.token.trim())) {
                      // Clear status messages when real content starts
                      updated[updated.length - 1].answer = parsed.token;
                    } else {
                      updated[updated.length - 1].answer += parsed.token;
                    }
                  } else {
                    updated[updated.length - 1].answer += parsed.token;
                  }
                  updated[updated.length - 1].streaming = true;
                }
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
              setLoading(false);
            }
          } catch (e) {
            // Skip invalid JSON, but log for debugging
            console.warn("Failed to parse JSON:", e, "Payload:", payload);
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
          {uploading ? "Uploading..." : "Upload Files"}
          <input
            type="file"
            accept=".txt,.hl7,.hl7v2,.hl7v3,.json,.xml,.ehr,.fhir,.ccda,.cda,.pdf"
            multiple
            hidden
            disabled={uploading}
            onChange={(e) => uploadFiles(e.target.files)}
          />
        </label>

        {uploadedFiles.length > 0 && (
          <div className="uploaded-files" style={{ marginTop: "20px" }}>
            <h3 style={{ fontSize: "14px", marginBottom: "10px", color: "#e0e0e0", fontWeight: "600" }}>
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
                    padding: "10px 12px",
                    marginBottom: "8px",
                    backgroundColor: "#2a2a2a",
                    border: "1px solid #444",
                    borderRadius: "6px",
                    fontSize: "13px",
                    color: "#e0e0e0",
                    transition: "all 0.2s ease",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = "#333";
                    e.currentTarget.style.borderColor = "#555";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "#2a2a2a";
                    e.currentTarget.style.borderColor = "#444";
                  }}
                >
                  <span 
                    style={{ 
                      flex: 1, 
                      overflow: "hidden", 
                      textOverflow: "ellipsis", 
                      whiteSpace: "nowrap",
                      color: "#e0e0e0",
                      fontWeight: "500",
                    }}
                    title={file}
                  >
                    📄 {file}
                  </span>
                  <button
                    onClick={() => deleteFile(file)}
                    style={{
                      marginLeft: "10px",
                      padding: "4px 10px",
                      fontSize: "14px",
                      backgroundColor: "#ff4444",
                      color: "white",
                      border: "none",
                      borderRadius: "4px",
                      cursor: "pointer",
                      fontWeight: "bold",
                      transition: "background-color 0.2s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = "#ff6666";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = "#ff4444";
                    }}
                    title="Delete file"
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

      {/* Main Content with Tabs */}
      <main className="chat">
        {/* Tabs */}
        <div className="tabs-container">
          <button
            className={`tab-button ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => setActiveTab("chat")}
          >
            💬 Chat
          </button>
          <button
            className={`tab-button ${activeTab === "clinical" ? "active" : ""}`}
            onClick={() => setActiveTab("clinical")}
          >
            📊 Clinical Dashboard
          </button>
        </div>

        {/* Chat Tab */}
        {activeTab === "chat" && (
          <>
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
        </>
        )}

        {/* Clinical Dashboard Tab */}
        {activeTab === "clinical" && (
          <div className="clinical-dashboard-container">
            <ClinicalVisualizations />
          </div>
        )}
      </main>
    </div>
  );
}

