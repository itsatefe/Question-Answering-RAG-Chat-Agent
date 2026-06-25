"use client";

export interface Message {
  role: "user" | "assistant";
  text: string;
  artifacts: string[];
}

interface ChatMessageProps {
  message: Message;
  onArtifactClick?: (html: string) => void;
}

export function ChatMessage({ message, onArtifactClick }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-3xl w-full ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {message.text && (
          <div
            className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
              isUser
                ? "bg-blue-600 text-white rounded-br-sm ml-12"
                : "bg-white border border-gray-200 text-gray-800 rounded-bl-sm mr-12"
            }`}
          >
            {message.text}
          </div>
        )}

        {message.artifacts.map((html, i) => (
          <button
            key={i}
            onClick={() => onArtifactClick?.(html)}
            className="mt-2 flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-200 bg-gray-50 hover:bg-gray-100 text-xs text-gray-600 transition-colors"
          >
            <span>📊</span>
            <span>Artifact {message.artifacts.length > 1 ? i + 1 : ""}</span>
            <span className="text-gray-400">— click to view</span>
          </button>
        ))}
      </div>
    </div>
  );
}
