"use client";

import { useState } from "react";
import { Renderer, BuiltinActionType } from "@openuidev/react-lang";
import { ThemeProvider } from "@openuidev/react-ui";
import { library } from "../../lib/openui-library";

interface ArtifactPanelProps {
  response: string;
  isStreaming: boolean;
  onClose: () => void;
  onSendMessage?: (msg: string) => void;
}

function errorToString(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (typeof err === "string") return err;
  try { return JSON.stringify(err, null, 2); } catch { return String(err); }
}

export function ArtifactPanel({ response, isStreaming, onClose, onSendMessage }: ArtifactPanelProps) {
  const [view, setView] = useState<"preview" | "source">("preview");
  const [renderError, setRenderError] = useState<string | null>(null);

  function handleAction(action: unknown) {
    const a = action as Record<string, unknown>;
    if (a.type === BuiltinActionType.ContinueConversation && onSendMessage) {
      const msg = String(a.humanFriendlyMessage ?? "");
      if (msg) onSendMessage(msg);
    }
  }

  return (
    <ThemeProvider mode="light">
      <div className="flex flex-col h-full border-l border-gray-200 bg-white">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
            </div>
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
              <button
                onClick={() => { setView("preview"); setRenderError(null); }}
                className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                  view === "preview"
                    ? "bg-white text-gray-800 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Preview
              </button>
              <button
                onClick={() => setView("source")}
                className={`px-3 py-1 text-xs rounded-md font-medium transition-colors ${
                  view === "source"
                    ? "bg-white text-gray-800 shadow-sm"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                Source
              </button>
            </div>
            {isStreaming && (
              <span className="text-xs text-gray-400 animate-pulse">streaming…</span>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xs px-2 py-1 rounded hover:bg-gray-100 transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto">
          {view === "source" ? (
            <pre className="h-full p-4 text-xs font-mono text-gray-800 bg-gray-50 leading-relaxed whitespace-pre-wrap break-all">
              {response || "(empty — no response text yet)"}
            </pre>
          ) : !response ? (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">
              Waiting for response…
            </div>
          ) : renderError ? (
            <div className="m-4 text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="font-medium mb-1">Render error</p>
              <pre className="text-xs whitespace-pre-wrap">{renderError}</pre>
              <button
                onClick={() => setView("source")}
                className="mt-2 text-xs text-red-500 underline"
              >
                View source →
              </button>
            </div>
          ) : (
            <div className="p-4">
              <Renderer
                library={library}
                response={response}
                isStreaming={isStreaming}
                onAction={handleAction}
                onError={(err) => {
                  // onError fires with [] on every successful parse — ignore empty arrays
                  if (Array.isArray(err) && err.length === 0) return;
                  setRenderError(errorToString(err));
                }}
              />
            </div>
          )}
        </div>
      </div>
    </ThemeProvider>
  );
}
