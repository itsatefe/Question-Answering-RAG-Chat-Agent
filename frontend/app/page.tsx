"use client";

import { useState, useEffect, useRef, useCallback, FormEvent, ChangeEvent } from "react";
import { ChatMessage, Message } from "./components/ChatMessage";
import { ArtifactPanel } from "./components/ArtifactPanel";

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarWidth, setSidebarWidth] = useState(256);
  // active panel: index of the assistant message shown in the right panel
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const [panelWidth, setPanelWidth] = useState(45); // right panel % of total width
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isDragging = useRef<"panel" | "sidebar" | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const activeMessage = activeIndex !== null ? messages[activeIndex] : null;

  function handleStop() {
    abortControllerRef.current?.abort();
  }

  useEffect(() => {
    fetch("/api/session", { method: "POST" })
      .then((r) => r.json())
      .then((d) => setSessionId(d.session_id))
      .catch(console.error);
    fetchDocuments();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSidebarDividerMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = "sidebar";
    e.preventDefault();
  }, []);

  const handlePanelDividerMouseDown = useCallback((e: React.MouseEvent) => {
    isDragging.current = "panel";
    e.preventDefault();
  }, []);

  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!isDragging.current) return;
      if (isDragging.current === "sidebar") {
        setSidebarWidth(Math.min(480, Math.max(160, e.clientX)));
      } else if (isDragging.current === "panel") {
        const pct = ((window.innerWidth - e.clientX) / window.innerWidth) * 100;
        setPanelWidth(Math.min(75, Math.max(25, pct)));
      }
    }
    function onMouseUp() {
      isDragging.current = null;
    }
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  async function fetchDocuments() {
    try {
      const r = await fetch("/api/documents");
      const d = await r.json();
      setDocuments(d.documents ?? []);
    } catch {
      // silently ignore — backend may not be running yet
    }
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith(".pdf")) {
      alert("Only PDF files are supported.");
      return;
    }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const r = await fetch("/api/documents", { method: "POST", body: form });
      if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        alert(err.detail ?? "Upload failed.");
      } else {
        await fetchDocuments();
      }
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(filename: string) {
    if (!confirm(`Delete "${filename}" from the library?`)) return;
    await fetch(`/api/documents/${encodeURIComponent(filename)}`, { method: "DELETE" });
    await fetchDocuments();
  }

  async function sendMessage(userMessage: string) {
    if (!userMessage.trim() || !sessionId || loading) return;
    setInput("");
    setLoading(true);

    // Index of the assistant message we're about to add
    const assistantIndex = messages.length + 1;

    setMessages((prev) => [
      ...prev,
      { role: "user", text: userMessage },
      { role: "assistant", text: "", isStreaming: true },
    ]);
    setActiveIndex(assistantIndex);

    setLoading(true);

    const abort = new AbortController();
    abortControllerRef.current = abort;

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMessage }),
        signal: abort.signal,
      });

      if (!response.body) throw new Error("No response body");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw || raw === "[DONE]") continue;

          let event: Record<string, unknown>;
          try {
            event = JSON.parse(raw);
          } catch {
            continue;
          }

          // Session reset (non-standard event from our backend)
          if (event.type === "session_reset" && typeof event.session_id === "string") {
            setSessionId(event.session_id);
            continue;
          }

          // OpenAI-compatible chunk
          const choices = event.choices as Array<{ delta?: { content?: string } }> | undefined;
          const content = choices?.[0]?.delta?.content;
          if (content) {
            setMessages((prev) => {
              const updated = [...prev];
              const last = { ...updated[updated.length - 1] };
              last.text = (last.text ?? "") + content;
              updated[updated.length - 1] = last;
              return updated;
            });
          }
        }
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === "AbortError") {
        // user stopped — keep partial text as-is
      } else {
        console.error(err);
        setMessages((prev) => {
          const updated = [...prev];
          const last = { ...updated[updated.length - 1] };
          last.text = "Something went wrong. Please try again.";
          updated[updated.length - 1] = last;
          return updated;
        });
      }
    } finally {
      abortControllerRef.current = null;
      setLoading(false);
      setMessages((prev) => {
        const updated = [...prev];
        const last = { ...updated[updated.length - 1] };
        if (last.role === "assistant") {
          last.isStreaming = false;
          updated[updated.length - 1] = last;
        }
        return updated;
      });
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    sendMessage(input.trim());
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Left block: sidebar + chat ── */}
      <div
        className="flex flex-shrink-0 min-w-0"
        style={{ width: activeMessage ? `${100 - panelWidth}%` : "100%" }}
      >
        {/* Sidebar */}
        {sidebarOpen && (
          <aside
            className="flex-shrink-0 border-r border-gray-200 flex flex-col bg-gray-50 relative"
            style={{ width: sidebarWidth }}
          >
            <div className="p-4 border-b border-gray-200">
              <h2 className="text-sm font-semibold text-gray-700">Document Library</h2>
              <p className="text-xs text-gray-400 mt-0.5">
                {documents.length} document{documents.length !== 1 ? "s" : ""}
              </p>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-1">
              {documents.length === 0 ? (
                <p className="text-xs text-gray-400 text-center mt-6">No documents yet.</p>
              ) : (
                documents.map((name) => (
                  <div
                    key={name}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 group"
                  >
                    <span className="text-gray-400 text-sm">📄</span>
                    <span className="flex-1 text-xs text-gray-700 truncate" title={name}>
                      {name}
                    </span>
                    <button
                      onClick={() => handleDelete(name)}
                      className="text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                      title={`Delete ${name}`}
                    >
                      ✕
                    </button>
                  </div>
                ))
              )}
            </div>

            <div className="p-3 border-t border-gray-200">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                className="hidden"
                onChange={handleUpload}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="w-full text-xs bg-blue-600 text-white rounded-lg px-3 py-2 font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {uploading ? "Uploading…" : "+ Upload PDF"}
              </button>
            </div>

            <div
              onMouseDown={handleSidebarDividerMouseDown}
              className="absolute top-0 right-0 w-1 h-full hover:bg-blue-400 active:bg-blue-500 cursor-col-resize transition-colors"
              title="Drag to resize"
            />
          </aside>
        )}

        {/* Chat */}
        <div className="flex flex-col flex-1 min-w-0">
          <header className="py-4 px-6 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen((o) => !o)}
                className="text-gray-400 hover:text-gray-600 transition-colors p-1 rounded"
                title={sidebarOpen ? "Hide sidebar" : "Show sidebar"}
              >
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <rect x="1" y="1" width="16" height="16" rx="2" />
                  <line x1="6" y1="1" x2="6" y2="17" />
                </svg>
              </button>
              <div>
                <h1 className="text-lg font-semibold">Research Q&A Agent</h1>
                <p className="text-xs text-gray-500">
                  Ask questions about your documents — or request any visual
                </p>
              </div>
            </div>
            {sessionId && (
              <span className="text-xs text-gray-400 font-mono">{sessionId.slice(0, 8)}…</span>
            )}
          </header>

          <div className="flex-1 overflow-y-auto py-6 px-6">
            {messages.length === 0 && (
              <div className="text-center text-gray-400 mt-20 text-sm">
                <p className="text-2xl mb-2">📄</p>
                <p>Upload a PDF in the sidebar, then ask questions here.</p>
                <p className="mt-2 text-xs">
                  Try: <em>"Summarize the key findings"</em> or{" "}
                  <em>"Create an interactive dashboard of the results"</em>
                </p>
              </div>
            )}
            {messages.map((m, i) => (
              <ChatMessage
                key={i}
                message={m}
                isActive={i === activeIndex}
                onViewClick={() => setActiveIndex(i)}
              />
            ))}
            <div ref={bottomRef} />
          </div>

          <form
            onSubmit={handleSubmit}
            className="py-4 px-6 border-t border-gray-200 flex gap-2 flex-shrink-0"
          >
            <input
              className="flex-1 rounded-xl border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="Ask a question or request a dashboard…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!sessionId || loading}
            />
            {loading ? (
              <button
                type="button"
                onClick={handleStop}
                className="bg-red-500 text-white rounded-xl px-5 py-2.5 text-sm font-medium hover:bg-red-600 transition-colors flex items-center gap-2"
              >
                <span className="w-2.5 h-2.5 rounded-sm bg-white inline-block" />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!sessionId || !input.trim()}
                className="bg-blue-600 text-white rounded-xl px-5 py-2.5 text-sm font-medium disabled:opacity-40 hover:bg-blue-700 transition-colors"
              >
                Send
              </button>
            )}
          </form>
        </div>
      </div>

      {/* ── Drag divider ── */}
      {activeMessage && (
        <div
          onMouseDown={handlePanelDividerMouseDown}
          className="w-1 flex-shrink-0 bg-gray-200 hover:bg-blue-400 active:bg-blue-500 cursor-col-resize transition-colors"
          title="Drag to resize"
        />
      )}

      {/* ── Right panel: OpenUI renderer ── */}
      {activeMessage && (
        <div className="flex-1 min-w-0 flex flex-col" style={{ width: `${panelWidth}%` }}>
          <ArtifactPanel
            response={activeMessage.text}
            isStreaming={activeMessage.isStreaming ?? false}
            onClose={() => setActiveIndex(null)}
            onSendMessage={sendMessage}
          />
        </div>
      )}
    </div>
  );
}
