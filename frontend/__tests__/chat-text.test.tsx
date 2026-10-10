import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { ChatText, tokenizeChatText } from "@/lib/chat-text";

describe("tokenizeChatText", () => {
  it("splits bold, italic and code from plain text", () => {
    expect(tokenizeChatText("Created *Deploy API* with `HIGH` _soon_")).toEqual([
      { type: "text", value: "Created " },
      { type: "bold", value: "Deploy API" },
      { type: "text", value: " with " },
      { type: "code", value: "HIGH" },
      { type: "text", value: " " },
      { type: "italic", value: "soon" },
    ]);
  });

  it("leaves unmatched markers alone", () => {
    expect(tokenizeChatText("2 * 3 = 6")).toEqual([{ type: "text", value: "2 * 3 = 6" }]);
  });

  it("returns nothing for an empty line", () => {
    expect(tokenizeChatText("")).toEqual([]);
  });
});

describe("ChatText", () => {
  it("renders formatting as elements", () => {
    const { container } = render(<ChatText text={"*Done* `x`"} />);
    expect(container.querySelector("strong")?.textContent).toBe("Done");
    expect(container.querySelector("code")?.textContent).toBe("x");
  });

  it("preserves line breaks", () => {
    const { container } = render(<ChatText text={"line one\nline two"} />);
    expect(container.querySelectorAll("br")).toHaveLength(1);
  });

  it("never turns task text into live HTML", () => {
    const hostile = '*<img src=x onerror="window.__pwned=1">* <script>window.__pwned=1</script>';
    const { container } = render(<ChatText text={hostile} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>");
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  });
});
