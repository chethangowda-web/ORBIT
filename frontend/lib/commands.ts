/** Pure command-palette model: what can be run, and how a query ranks it. */

export interface Command {
  id: string;
  label: string;
  group: "Navigate" | "Actions" | "Tasks" | "Ask ORBIT";
  /** Extra words that should match the command but are not shown. */
  keywords?: string[];
  hint?: string;
  run: () => void;
}

/**
 * Score a command against a query. Higher is better; 0 means no match.
 * Prefix and word-start matches beat scattered substring matches.
 */
export function scoreCommand(command: Pick<Command, "label" | "keywords">, query: string): number {
  const q = query.trim().toLowerCase();
  if (!q) return 1;
  const label = command.label.toLowerCase();
  if (label === q) return 100;
  if (label.startsWith(q)) return 80;
  const words = label.split(/\s+/);
  if (words.includes(q)) return 70;
  if (words.some((word) => word.startsWith(q))) return 60;
  if (label.includes(q)) return 40;
  if ((command.keywords ?? []).some((k) => k.toLowerCase().includes(q))) return 20;
  return 0;
}

export function filterCommands<T extends Pick<Command, "label" | "keywords" | "group">>(commands: T[], query: string): T[] {
  return commands
    .map((command, index) => ({ command, index, score: scoreCommand(command, query) }))
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.index - b.index)
    .map((entry) => entry.command);
}

/** Next/previous highlighted index with wrap-around. */
export function moveIndex(current: number, delta: 1 | -1, length: number): number {
  if (length === 0) return 0;
  return (current + delta + length) % length;
}
