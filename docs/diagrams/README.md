# Diagrams

Excalidraw source for the framework's architecture diagrams. Each
`.excalidraw` file is the authoritative source; the matching `.png`
is exported from it and embedded in the documentation.

## Files

| File | Where it's embedded | Purpose |
|---|---|---|
| `authoring-loop.excalidraw` / `.png` | `README.md`, top of `HOW_IT_WORKS.md` | High-level five-station assembly-line overview. Henry-Ford framing. For the curious / casual reader. |
| `framework-internals.excalidraw` / `.png` | Deeper in `HOW_IT_WORKS.md` (between "What lives where" and the rest) | All 16 agents, lanes, file destinations, both build pipelines, three output paths, codification loop. For the fork-and-extend reader. |

## Editing

1. Open the `.excalidraw` file at <https://excalidraw.com/> — File →
   Open → select the file.
2. Edit. Keep the industrial palette (factory floor `#f4f4f5`, header
   black `#111827`, hazard yellow `#fbbf24`, station colors from the
   existing entries) and `roughness: 0` (sharp lines, no hand-drawn
   feel).
3. Save back to `.excalidraw`.
4. Export to PNG: File → Export image → PNG → save over the existing
   `.png` at the same path.
5. Commit both files together.

## Why two diagrams

The overview answers "what is this?" — anyone who lands on the README
should be able to grok the assembly-line metaphor in five seconds. It
sells the concept.

The detailed one answers "how do I extend / debug / fork this?" — it
shows lanes, file destinations, and the codification loop in enough
detail that a forker can find their way around without reading
`CLAUDE.md` first.

Don't bloat the overview with detail; don't oversimplify the internals
diagram. They're tuned for different readers.
