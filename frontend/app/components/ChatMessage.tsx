"use client";

import { Artifact } from "./Artifact";

export interface Message {
  role: "user" | "assistant";
  text: string;
  artifacts: string[]; // list of raw HTML strings
}

export function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div className={`max-w-3xl w-full ${isUser ? "items-end" : "items-start"} flex flex-col`}>
        {/* Text bubble */}
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

        {/* Artifacts rendered below the text bubble */}
        {message.artifacts.map((html, i) => (
          <Artifact key={i} html={html} />
        ))}
      </div>
    </div>
  );
}
