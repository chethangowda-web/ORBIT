import React from "react";

/**
 * Render the agent's Google-Chat-flavoured text (*bold*, _italic_, `code`) as React
 * nodes. Output is built from text nodes only, never HTML strings, so task titles or
 * other user-controlled content in a reply cannot inject markup.
 */
type Token = { type: "text" | "bold" | "italic" | "code"; value: string };

const INLINE = /(\*[^*\n]+\*|_[^_\n]+_|`[^`\n]+`)/g;

export function tokenizeChatText(line: string): Token[] {
  const tokens: Token[] = [];
  let last = 0;
  for (const match of line.matchAll(INLINE)) {
    const index = match.index ?? 0;
    if (index > last) tokens.push({ type: "text", value: line.slice(last, index) });
    const raw = match[0];
    const inner = raw.slice(1, -1);
    const type = raw.startsWith("*") ? "bold" : raw.startsWith("_") ? "italic" : "code";
    tokens.push({ type, value: inner });
    last = index + raw.length;
  }
  if (last < line.length) tokens.push({ type: "text", value: line.slice(last) });
  return tokens;
}

export function ChatText({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, i) => (
        <React.Fragment key={i}>
          {tokenizeChatText(line).map((token, j) => {
            switch (token.type) {
              case "bold":
                return (
                  <strong key={j} className="font-semibold text-fg">
                    {token.value}
                  </strong>
                );
              case "italic":
                return <em key={j}>{token.value}</em>;
              case "code":
                return (
                  <code key={j} className="num rounded bg-surface-3 px-1 text-[11px]">
                    {token.value}
                  </code>
                );
              default:
                return <React.Fragment key={j}>{token.value}</React.Fragment>;
            }
          })}
          {i < lines.length - 1 && <br />}
        </React.Fragment>
      ))}
    </>
  );
}
