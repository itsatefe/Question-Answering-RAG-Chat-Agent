"use client";

interface ArtifactProps {
  html: string;
}

export function Artifact({ html }: ArtifactProps) {
  const srcDoc =
    html.startsWith("<!DOCTYPE") || html.startsWith("<html")
      ? html
      : `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <style>
    body { margin: 0; font-family: system-ui, sans-serif; background: #fff; }
  </style>
</head>
<body>${html}</body>
</html>`;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 border-b border-gray-200 flex-shrink-0">
        <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
        <span className="w-2.5 h-2.5 rounded-full bg-yellow-400" />
        <span className="w-2.5 h-2.5 rounded-full bg-green-400" />
        <span className="text-xs text-gray-500 ml-2 font-mono">artifact</span>
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
