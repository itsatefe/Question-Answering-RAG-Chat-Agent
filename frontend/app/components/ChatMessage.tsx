"use client";

export interface Message {
  role: "user" | "assistant";
  text: string;
  isStreaming?: boolean;
}

interface ChatMessageProps {
  message: Message;
  onViewClick?: (text: string) => void;
  isActive?: boolean;
}

export function ChatMessage({ message, onViewClick, isActive }: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end mb-4">
        <div className="max-w-3xl px-4 py-3 rounded-2xl rounded-br-sm text-sm leading-relaxed bg-blue-600 text-white ml-12">
          {message.text}
        </div>
      </div>
    );
  }

  if (!message.text && message.isStreaming) {
    return (
      <div className="flex justify-start mb-4">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 text-sm text-gray-400">
          Thinking…
        </div>
      </div>
    );
  }

  if (!message.text) return null;

  return (
    <div className="flex justify-start mb-4">
      <button
        onClick={() => onViewClick?.(message.text)}
        className={`flex items-center gap-3 px-4 py-3 rounded-2xl rounded-bl-sm border text-sm text-left transition-colors max-w-3xl mr-12 ${
          isActive
            ? "bg-blue-50 border-blue-200 text-blue-700"
            : "bg-white border-gray-200 text-gray-700 hover:bg-gray-50"
        }`}
      >
        <span className="text-lg flex-shrink-0">{message.isStreaming ? "⏳" : "✦"}</span>
        <span className="flex-1 min-w-0">
          <span className="font-medium block">
            {message.isStreaming ? "Generating response…" : "Response ready"}
          </span>
          <span className="text-xs text-gray-400 block mt-0.5">
            {message.isStreaming ? "Streaming…" : "Click to view in panel →"}
          </span>
        </span>
      </button>
    </div>
  );
}
