# Diagrams

Excalidraw source for the framework's architecture diagrams. Each
`.excalidraw` file is the authoritative source; the matching `.png`
is exported from it and embedded in the documentation.

## Files

| File | Where it's embedded | Audience |
|---|---|---|
| `intro-flow.excalidraw` / `.svg` | `README.md` | Newcomer. Three nodes — Ask → Build → Ship. Sells the concept in five seconds. |
| `authoring-loop.excalidraw` / `.svg` | Top of `HOW_IT_WORKS.md` | Curious reader. Five-station assembly-line overview with the agents called out. Henry-Ford framing. |
| `framework-internals.excalidraw` / `.svg` | Deeper in `HOW_IT_WORKS.md` (just before "What lives where") | Fork-and-extend reader. All 16 agents, lanes, file destinations, both build pipelines, three output paths, codification loop. |

## Editing

1. Open the `.excalidraw` file at <https://excalidraw.com/> — File →
   Open → select the file.
2. Edit. Keep the industrial palette (factory floor `#f4f4f5`, header
   black `#111827`, hazard yellow `#fbbf24`, station colors from the
   existing entries) and `roughness: 0` (sharp lines, no hand-drawn
   feel).
3. Save back to `.excalidraw`.
4. Regenerate the SVG:

   ```
   python3 scripts/excalidraw_to_svg.py diagrams/<name>.excalidraw
   ```

   The converter handles the shape subset we use (rectangle, ellipse,
   diamond, text, arrow, line). If you add a shape it doesn't know
   about, extend `scripts/excalidraw_to_svg.py`.
5. Commit both `.excalidraw` and `.svg` together.

## Why three diagrams

Each is tuned for a different reader and a different question:

- **`intro-flow`** answers "what does this do?" — three nodes,
  almost no detail, gives the user-level mental model.
- **`authoring-loop`** answers "how does that work, roughly?" —
  the assembly-line metaphor with stations and the agent crew
  surfaced.
- **`framework-internals`** answers "where do I make changes?" —
  every agent named, every output path traced, every code-path
  surface visible.

The graduation from README → HOW_IT_WORKS overview → HOW_IT_WORKS
internals is intentional. Don't bloat `intro-flow` with detail;
don't oversimplify `framework-internals`. They're not redundant —
they're a zoom progression.
