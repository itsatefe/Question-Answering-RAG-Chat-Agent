"use client";

import { useState, useEffect, useRef, FormEvent, ChangeEvent } from "react";
import { ChatMessage, Message } from "./components/ChatMessage";

export default function Page() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<string[]>([]);
  const [uploading, setUploading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
      // reset so the same file can be re-uploaded after deletion
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(filename: string) {
    if (!confirm(`Delete "${filename}" from the library?`)) return;
    await fetch(`/api/documents/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
    await fetchDocuments();
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || !sessionId || loading) return;

    const userMessage = input.trim();
    setInput("");
    setLoading(true);

    setMessages((prev) => [
      ...prev,
      { role: "user", text: userMessage, artifacts: [] },
    ]);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", text: "", artifacts: [] },
    ]);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMessage }),
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
          if (!raw) continue;

          const event = JSON.parse(raw) as {
            type: "text" | "artifact" | "done";
            content?: string;
          };

          if (event.type === "text") {
            setMessages((prev) => {
              const updated = [...prev];
              const last = { ...updated[updated.length - 1] };
              last.text = (last.text ?? "") + event.content;
              updated[updated.length - 1] = last;
              return updated;
            });
          }

          if (event.type === "artifact") {
            setMessages((prev) => {
              const updated = [...prev];
              const last = { ...updated[updated.length - 1] };
              last.artifacts = [...last.artifacts, event.content ?? ""];
              updated[updated.length - 1] = last;
              return updated;
            });
          }
        }
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) => {
        const updated = [...prev];
        const last = { ...updated[updated.length - 1] };
        last.text = "Something went wrong. Please try again.";
        updated[updated.length - 1] = last;
        return updated;
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 border-r border-gray-200 flex flex-col bg-gray-50">
        <div className="p-4 border-b border-gray-200">
          <h2 className="text-sm font-semibold text-gray-700">Document Library</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            {documents.length} document{documents.length !== 1 ? "s" : ""}
          </p>
        </div>

        {/* Document list */}
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
                <span
                  className="flex-1 text-xs text-gray-700 truncate"
                  title={name}
                >
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

        {/* Upload */}
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
      </aside>

      {/* Main chat area */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Header */}
        <header className="py-4 px-6 border-b border-gray-200 flex items-center justify-between flex-shrink-0">
          <div>
            <h1 className="text-lg font-semibold">Research Q&A Agent</h1>
            <p className="text-xs text-gray-500">
              Ask questions about your documents — or ask for a chart
            </p>
          </div>
          {sessionId && (
            <span className="text-xs text-gray-400 font-mono">
              {sessionId.slice(0, 8)}…
            </span>
          )}
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto py-6 px-6">
          {messages.length === 0 && (
            <div className="text-center text-gray-400 mt-20 text-sm">
              <p className="text-2xl mb-2">📄</p>
              <p>Upload a PDF in the sidebar, then ask questions here.</p>
              <p className="mt-2 text-xs">
                Try: <em>"Summarize the key findings"</em> or{" "}
                <em>"Generate a bar chart of the results table"</em>
              </p>
            </div>
          )}
          {messages.map((m, i) => (
            <ChatMessage key={i} message={m} />
          ))}
          {loading && (
            <div className="flex justify-start mb-4">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-gray-400">
                Thinking…
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form
          onSubmit={handleSubmit}
          className="py-4 px-6 border-t border-gray-200 flex gap-2 flex-shrink-0"
        >
          <input
            className="flex-1 rounded-xl border border-gray-300 px-4 py-2.5 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
            placeholder="Ask a question or request a chart…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={!sessionId || loading}
          />
          <button
            type="submit"
            disabled={!sessionId || loading || !input.trim()}
            className="bg-blue-600 text-white rounded-xl px-5 py-2.5 text-sm font-medium disabled:opacity-40 hover:bg-blue-700 transition-colors"
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
