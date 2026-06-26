"use client";

import type { ArtifactData } from "./ChatMessage";

interface ArtifactProps {
  artifact: ArtifactData;
}

function extractReactParts(raw: string): { extraStyles: string; code: string } {
  // Pull out any <style> blocks the agent may have wrapped around the code
  const styleRe = /<style[^>]*>([\s\S]*?)<\/style>/gi;
  const extraStyles = [...raw.matchAll(styleRe)].map((m) => m[1]).join("\n");

  // Pull code out of any <script> tags the agent may have added
  const scriptRe = /<script[^>]*>([\s\S]*?)<\/script>/gi;
  const scriptMatches = [...raw.matchAll(scriptRe)];

  let code: string;
  if (scriptMatches.length > 0) {
    code = scriptMatches.map((m) => m[1]).join("\n");
  } else {
    // No script wrapper — raw code as-is, just strip stray style tags
    code = raw.replace(styleRe, "").trim();
  }

  return { extraStyles, code };
}

function buildReactShell(raw: string): string {
  const { extraStyles, code } = extractReactParts(raw);

  // JSON.stringify handles all escaping (newlines, quotes, backslashes).
  // Also escape </ so the string value can't accidentally close the <script> tag.
  const jsonSrc = JSON.stringify(
    code +
      "\nReactDOM.createRoot(document.getElementById('root')).render(React.createElement(App));"
  ).replace(/<\//g, "<\\/");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
  <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
  <script src="https://unpkg.com/recharts@2/umd/Recharts.js"></script>
  <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
  <style>
    *, *::before, *::after { box-sizing: border-box; }
    body { margin: 0; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #fff; }
    #root { min-height: 100vh; }
    ${extraStyles}
  </style>
</head>
<body>
  <div id="root"></div>
  <div id="__err__" style="display:none;color:#b91c1c;padding:16px;font-family:monospace;font-size:12px;white-space:pre-wrap;background:#fef2f2;border-left:3px solid #f87171;margin:12px;border-radius:4px;"></div>
  <script>
    window.onerror = function (msg, _src, _line, _col, err) {
      var el = document.getElementById('__err__');
      if (el) { el.textContent = 'Runtime error: ' + (err ? err.message : msg); el.style.display = 'block'; }
      return true;
    };
    (function () {
      var src = ${jsonSrc};
      try {
        /* Explicit classic runtime so Babel uses React.createElement (global)
           instead of trying to import react/jsx-runtime as an ES module. */
        var out = Babel.transform(src, { presets: [['react', { runtime: 'classic' }]] });
        var s = document.createElement('script');
        s.textContent = out.code;
        document.head.appendChild(s);
      } catch (e) {
        var el = document.getElementById('__err__');
        el.textContent = 'Transform error: ' + (e && e.message ? e.message : String(e));
        el.style.display = 'block';
      }
    }());
  </script>
</body>
</html>`;
}

function buildHtmlShell(html: string): string {
  if (html.startsWith("<!DOCTYPE") || html.startsWith("<html")) return html;
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; background: #fff; }
  </style>
</head>
<body>${html}</body>
</html>`;
}

export function Artifact({ artifact }: ArtifactProps) {
  const srcDoc =
    artifact.type === "react"
      ? buildReactShell(artifact.content)
      : buildHtmlShell(artifact.content);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 border-b border-gray-200 flex-shrink-0">
        <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
        <span className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
        <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
        <span className="text-xs text-gray-500 ml-2 font-mono">
          {artifact.type === "react" ? "⚛ react" : "artifact"}
        </span>
      </div>
      <iframe
        srcDoc={srcDoc}
        sandbox="allow-scripts"
        className="flex-1 w-full border-none block"
        title="Generated artifact"
      />
    </div>
  );
}
