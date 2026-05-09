# Cursor Session Tracer

## Agentic Observability for Production Engineering Teams

**Talk + Build Design Document**
Indranil Chandra | Cursor Community Meetup Mumbai | May 2026

---

## 1. Event and Audience Context

### 1.1 Event

- Cursor Community Meetup Mumbai -- second edition, official Cursor community event
- Format: talks + demos from power users, Q&A with Cursor team member, open networking
- Slot: 20 minutes -- talk + live demo

### 1.2 Audience Profile

Based on the prior Mumbai edition and comparable Cursor community meetups globally:

- **Primary:** Senior individual contributors and founding engineers at Mumbai startups who use Cursor daily and have moved past onboarding. Not people learning what Cursor is. They have already run agentic sessions, felt the pain, and have opinions.
- **Secondary:** Technical founders and CTOs evaluating or scaling Cursor adoption across their engineering teams. They care about ROI, team velocity, and governance.
- **Tertiary:** Engineering managers at growth-stage companies (the first Mumbai meetup had speakers from CleverTap, which signals this tier is present). They want something they can take back and justify.

### 1.3 What This Audience Has Already Seen

Assume they have seen: Cursor tips and workflow talks, MCP server demos, rules and notepads walkthroughs, background agent introductions. Do not open with basics. Open with a failure.

### 1.4 What This Audience Has Not Seen

- A systematic treatment of what happens after a large agentic session -- the debugging, the audit, the PR review problem
- A working observability layer built on top of Cursor's own agentic loop using MCP
- The framing of agentic amnesia as a named, architectural problem class -- not just a vague frustration

---

## 2. Talk Design

### 2.1 Title and Thesis

**Title:** When the Agent Drives, Who Holds the Wheel?

**One-line thesis:** Cursor's agentic mode is powerful enough to restructure your codebase in one session. That power creates a new class of debugging problem that your existing mental models -- step debuggers, unit tests, git blame -- were not designed to handle. This talk names that problem and ships a working solution in front of you.

### 2.2 The Core Insight

Git blame tells you what changed and when. The trace tells you why the agent made that sequence of decisions. During a prod incident, the difference between those two is the difference between "I can see line 847 changed" and "I understand that the agent changed line 847 because it misread the auth contract in config.py three steps earlier."

Senior engineers doing PR review currently have no choice but to reverse-engineer agent intent from code output. The trace gives them the reasoning chain upfront. That is a new debugging primitive, not an incremental improvement on existing tooling.

### 2.3 The Named Problem: Agentic Amnesia

The problem is not that the agent makes bad changes. The problem is that there is no decision trace. No record of what the agent read before deciding, what alternatives it considered, what order it modified files in, why it chose approach A over approach B.

A human engineer would have left comments, a PR description, a Slack thread. The agent leaves nothing except the output. We call this **agentic amnesia**. The agent has no memory of its own reasoning by the time you need to investigate.

### 2.4 The Business Framing

This is not just a debugging tool. This is the missing layer between "AI wrote this" and "engineer owns this." Every organisation adopting Cursor at scale will need something like this -- not because they distrust the AI, but because software ownership requires a reasoning trail. Accountability does not disappear when the agent writes the code. It just gets harder to assign.

Teams that instrument their agentic workflows now will have an audit-ready, review-friendly, onboardable codebase. Teams that don't will accumulate **agentic debt** -- code that works but that no one can explain.

---

## 3. Talk Structure -- 20 Minutes

> Each segment has a hard time cap. Do not overrun the framing into the demo. The demo is the credibility.

### Minutes 0 to 3: The Failure Scenario

Open with a real situation, told as a story. No slides required. Talk to the room.

The scenario: you kick off an agentic session in Cursor. The task is meaningful -- something like "refactor all API clients to use the new token-based auth pattern." The agent runs. It reads files, makes decisions, modifies 40-odd files across the codebase. You review the diff, it looks broadly correct, you commit. Forty-eight hours later something breaks in production. Git bisect points you to the agentic commit. The diff is a wall of noise. You have no idea which of the 40 changes introduced the regression, or why the agent made the specific sequencing decision that led to it.

Pause. Ask the room: how many of you have felt exactly this? Let that land for three seconds.

Then say: the problem is not that the agent made a bad change. The problem is that the agent left no reasoning trail. We have a name for this. Agentic amnesia.

### Minutes 3 to 8: The Problem Framing

Introduce the comparison that makes the problem precise:

- **Git history:** what changed, when, by whom
- **Step debugger:** what is executing right now, what is the call stack
- **Unit test failure:** which assertion broke, on which input
- **Agentic session trace:** why did the agent make this decision, given what it had read, at that point in the session

These are different questions. None of the first three answer the fourth. The fourth is new. It exists because agentic coding is a new execution model, not just a faster version of autocomplete.

Then set up the solution: what if every agentic session left behind a structured trace -- a decision log that maps reasoning to file changes, step by step, with parent-child relationships between decisions? What could you do with that?

- Debug a prod regression by walking the trace instead of the diff
- Give a senior engineer the reasoning chain before they open the PR
- Build an org-level knowledge graph of agent behavior across sessions, across engineers, across the codebase -- and start answering which files agents touch most, which decision patterns precede prod failures

### Minutes 8 to 16: The Live Demo

Transition: "Let me show you what this looks like running inside Cursor right now."

**Demo setup (pre-loaded, do not explain setup live):**

- A small demo repo open in Cursor -- a Flask or FastAPI app, ~8 files, with a clear architectural seam to refactor
- MCP server already running locally
- Cursor rule already in `.cursor/rules/`
- VS Code split pane: left is Cursor agent, right is terminal watching the trace file

**What you do live:**

- Open Cursor agent mode, type a meaningful multi-file task -- something the audience recognises as real work, not a toy example
- Show that before the agent starts modifying anything, it calls `start_trace` -- session ID returned, trace file created, visible in the file tree
- Let the agent run 3 to 5 steps -- enough for the trace file to accumulate 4 to 6 events with parent_step_id chains forming
- At a natural pause point, switch to terminal and run `render_trace.py` -- the decision tree prints to stdout, showing the reasoning chain with file references
- End the session with `end_trace`, show the outcome field written
- Pull up the rendered tree again -- walk through one specific decision and show how you would use this during a prod incident or PR review

**What the demo proves:**

- The MCP tool integration works inside Cursor's agentic loop without friction
- The trace file is human-readable in real time, not post-processed
- The reasoning chain is queryable immediately after the session ends
- The whole thing is local, zero-dependency, works in any repo

### Minutes 16 to 20: The Systems-Level Punchline

Pull back from the demo. No more technical detail. Talk to the whole room.

What you just saw is the v0 of something larger. The data model underneath this is a graph -- every decision is a node, every file touch is an edge, every parent-step relationship is a directed dependency. Right now it lives in a JSON file. At org scale, this is a Neo4j graph that lets you query across sessions, across engineers, across the entire history of agent-assisted development in your codebase.

The question this enables -- and this is the question that matters for every team scaling Cursor adoption -- is not "did the agent write correct code." Linters and tests answer that. The question is: "did the agent reason correctly to get there, and can a human engineer follow that reasoning six months from now."

Close: the gap between AI-assisted development and AI-owned development is observability. We have 30 years of tooling for observing what code does at runtime. We have almost nothing for observing how agent reasoning produced that code. That is the problem worth solving. This is a start.

---

## 4. Trace File Schema

### 4.1 Directory Structure

```text
.cursor/traces/
  20260509/
    a1b2c3d4/
      143201_refactor_auth_clients.json
      151432_refactor_auth_clients.json    <- restart, visible by design
```

- **Date directory:** `YYYYMMDD` -- created at `start_trace` call time
- **Session directory:** `uuid4[:8]` -- generated by `start_trace`, returned to agent, passed on all subsequent calls
- **Filename:** `HHMMSS_<slug>.json` -- HHMMSS is wall clock at `start_trace`, slug is auto-generated from `task_description` (first 5 words, lowercased, underscored, punctuation stripped)
- **Multiple files under same session_id:** acceptable by design. Restart artifact. Do not suppress.

### 4.2 Session Header Block

Written once by `start_trace`. `ended_at` and `outcome` are null until `end_trace` is called.

```json
{
  "session": {
    "session_id": "a1b2c3d4",
    "slug": "refactor_auth_clients",
    "task": "Refactor all API clients to use the new token-based auth pattern",
    "started_at": "2026-05-09T14:32:01Z",
    "ended_at": null,
    "outcome": null,
    "repo_snapshot": ["src/auth.py", "src/clients/github.py", "src/middleware.py"]
  },
  "events": []
}
```

### 4.3 Event Object

Each call to `append_trace` appends one object to the `events` array.

```json
{
  "step_id": "step_003",
  "parent_step_id": "step_002",
  "type": "decision",
  "timestamp": "2026-05-09T14:33:45Z",
  "reason": "auth.py uses APIKeyAuth. Rewriting to BearerTokenAuth requires changing header construction in all downstream clients.",
  "files_read": ["src/auth.py"],
  "files_modified": ["src/clients/github.py"],
  "files_created": [],
  "files_deleted": [],
  "notes": ""
}
```

### 4.4 Event Types

- **decision:** Agent is choosing an approach. Most important event type. `reason` field must be specific.
- **file_read:** Agent reads a file to understand structure before acting
- **file_modify:** Agent modifies an existing file
- **file_create:** Agent creates a new file
- **file_delete:** Agent deletes a file
- **tool_call:** Agent invokes an external tool (terminal, search, etc.)
- **checkpoint:** Explicit human-triggered marker mid-session for long-running tasks

### 4.5 Graph Shape of the Schema

The `parent_step_id` field is what makes this graph-shaped even though it is stored as flat JSON. Every event points to what caused it. When migrating to a graph database later:

- Each event object becomes a node
- Each `parent_step_id` reference becomes a directed edge between nodes
- Each file reference (`files_read`, `files_modified`, etc.) becomes a second node type with edges from decision nodes to file nodes
- Cross-session queries become possible: which files are most frequently touched by agents, which decision patterns precede prod failures

---

## 5. MCP Tool Specifications

> Three tools only. More than three increases the probability of the agent making wrong tool choices mid-session.

### 5.1 start_trace

```text
start_trace(task_description: str, files_in_scope: list[str]) -> dict
```

**Returns:**

```json
{ "session_id": "a1b2c3d4", "trace_file_path": ".cursor/traces/20260509/a1b2c3d4/143201_refactor_auth_clients.json" }
```

**Behaviour:**

- Generates `session_id`: `uuid4()[:8]`
- Generates slug: `task_description` split on whitespace, first 5 tokens, lowercased, joined with underscores, non-alphanumeric characters stripped
- Creates date directory and session_id directory if they do not exist
- Writes the session header block with `events: []` to the JSON file
- Returns `session_id` and `trace_file_path`

**Agent instruction:** Agent must store the returned `session_id` and pass it to every subsequent `append_trace` and `end_trace` call.

### 5.2 append_trace

```text
append_trace(
  session_id: str,
  type: str,
  reason: str,
  files_read: list[str],
  files_modified: list[str],
  files_created: list[str],
  files_deleted: list[str],
  parent_step_id: str
) -> dict
```

**Returns:**

```json
{ "step_id": "step_003" }
```

**Behaviour:**

- Resolves the trace file path from `session_id` by scanning `.cursor/traces/**/<session_id>/` for the most recent JSON file
- Generates `step_id`: `'step_'` + zero-padded integer, incrementing from last event in file
- Appends the new event object to the `events` array in the JSON file
- Returns the new `step_id` so the agent can pass it as `parent_step_id` on the next call

**Agent instruction:** Agent must pass the `step_id` returned from each `append_trace` call as `parent_step_id` in the next call. This is what builds the reasoning chain.

### 5.3 end_trace

```text
end_trace(session_id: str, outcome: str) -> dict
```

**Returns:**

```json
{ "trace_file_path": ".cursor/traces/20260509/a1b2c3d4/143201_refactor_auth_clients.json" }
```

**Behaviour:**

- Resolves trace file path from `session_id`
- Writes `ended_at` (ISO timestamp) and `outcome` to the session header block
- Outcome values: `completed`, `partial`, `aborted`
- Returns final trace file path

---

## 6. Cursor Rule

**File location:** `.cursor/rules/session_trace.mdc`

### 6.1 Frontmatter

```text
---
description: Agentic session traceability. Apply during any multi-file or architectural change task.
alwaysApply: false
---
```

### 6.2 Rule Body

At the start of any task involving more than 2 files or any architectural change:

1. Call `start_trace` with the full task description and the list of files you expect to touch. Store the returned `session_id` -- you will need it for every subsequent call.

2. Before each significant decision -- reading a file to understand structure, choosing an implementation approach, modifying a file that other files depend on -- call `append_trace`. The `reason` field must be specific. Not "modified auth.py" but "modified auth.py to replace APIKeyAuth with BearerTokenAuth because downstream clients expect a `.headers` property that the old class does not expose."

3. Pass the `step_id` returned from each `append_trace` call as `parent_step_id` in the next call. This is what builds the reasoning chain.

4. When the task is complete or you are stopping, call `end_trace` with outcome set to `completed`, `partial`, or `aborted`.

Do not call `append_trace` for trivial actions like reading a config file to check syntax. Call it when you are making a decision that affects other files or that a reviewer would want to understand three weeks from now.

---

## 7. Terminal Renderer

### 7.1 Invocation

```bash
python render_trace.py --session <date>/<session_id>
# example
python render_trace.py --session 20260509/a1b2c3d4
```

### 7.2 Behaviour

- Scans `.cursor/traces/<date>/<session_id>/` for all JSON files
- If multiple files exist (restart scenario), renders each one in chronological order with a visible separator between them
- Reconstructs the parent-child tree from `parent_step_id` references
- Walks the tree and prints an indented text tree to stdout

### 7.3 Output Format

```text
SESSION a1b2c3d4 | refactor_auth_clients | started 14:32:01 | completed 15:14:32

step_001 [decision]  14:32:18
  reason: auth.py uses APIKeyAuth. Rewriting to BearerTokenAuth requires
          changing header construction in all downstream clients.
  read:     src/auth.py
  modified: (none)

  step_002 [file_modify]  14:33:45
    reason: Replacing APIKeyAuth class with BearerTokenAuth. .headers
            property now returns Authorization: Bearer <token>.
    read:     src/auth.py
    modified: src/auth.py

    step_003 [file_modify]  14:35:02
      reason: github.py client imports APIKeyAuth directly. Updating
              import and instantiation to use BearerTokenAuth.
      read:     src/clients/github.py
      modified: src/clients/github.py
```

### 7.4 Orphan Node Handling

If an event references a `parent_step_id` that does not exist in the file (agent skipped a call), attach the orphaned node to the session root and prefix its label with `[ORPHAN]` in the terminal output. Do not crash. Do not silently discard.

### 7.5 Flags

- `--verbose` -- print full reason text without truncation
- `--files-only` -- print only the file touch summary, omit reason text. Useful for quick diff review.

---

## 8. Build Order

**Step 1: JSON schema and file writer utility**
Write the file path resolver, slug generator, and the read/write/append utilities as standalone functions before touching MCP. Everything depends on these being correct. Test them with a hardcoded input before moving on.

**Step 2: MCP server with three tools**
Use FastMCP to cut boilerplate. Implement `start_trace`, `append_trace`, `end_trace` in that order. Wire each one to the file utilities from step 1. Test each tool in isolation with a Python test script that calls the functions directly -- do not test through Cursor until all three are working.

**Step 3: Cursor rule file**
Write `.cursor/rules/session_trace.mdc` with the frontmatter and rule body from section 6. Test that Cursor picks it up by opening a new chat and checking the rule appears in context.

**Step 4: End-to-end test run on dummy repo**
Create or clone a small repo (Flask or FastAPI, 6 to 10 files). Give the agent a real multi-file task. Watch the JSON file populate in real time. Check: are the `parent_step_id` chains forming correctly? Is the `reason` field specific or generic? Are file lists accurate? Fix schema gaps before building the renderer.

**Step 5: Terminal renderer**
Implement `render_trace.py` with the tree walk, truncation, orphan handling, and the two flags. Test against the JSON file generated in step 4.

**Step 6: Talk structure and framing slides**
Using slides as visual anchors.

- Slide 1: The failure scenario -- text only, large font, one sentence
- Slide 2: The four question types -- git history / step debugger / unit test / agentic trace -- as a simple two-column comparison
- Slide 3: The data model -- session > events > files, with parent_step_id arrows
- Slide 4: The org-level vision -- JSON today, graph DB at scale, what questions it enables

**Step 7 (stretch): Mermaid renderer**
Only if steps 1 through 6 are complete. See section 9 for caveats before starting.

---

## 9. Mermaid Renderer -- Parked, Stretch Goal Only

> Do not start this unless steps 1 through 6 are complete and you have at least 45 uninterrupted minutes remaining.

### 9.1 What It Would Do

A second mode on `render_trace.py` that walks the same parent-child tree and outputs a `.mermaid` file into the session directory.

```bash
python render_trace.py --session 20260509/a1b2c3d4 --mode mermaid
```

### 9.2 Known Caveats -- Must Handle Before Using

- **Orphan nodes:** renderer must attach orphans to the root node or the diagram has disconnected floating nodes
- **Label length:** reason text must be truncated to 50 characters and quotes/brackets must be escaped or the diagram breaks silently
- **Large sessions:** sessions with 20+ events produce unreadable diagrams. Add a `--max-nodes` flag that caps rendering and appends a truncation note.

### 9.3 Primary Value

The Mermaid output is a PR attachment, not a debugging tool. Its audience is the code reviewer, not the incident responder. Keep it structurally simple: decision flow and file touch points only.

---

## 10. Future Architecture Notes

### 10.1 GraphDB Migration Path

The JSON schema is deliberately graph-shaped. Migrating to Neo4j requires:

- A one-time ingestion script that reads all session JSON files and writes nodes and edges
- A Cypher schema: `(Step)-[:CAUSED]->(Step)`, `(Step)-[:TOUCHED]->(File)`
- A query layer for cross-session analysis

### 10.2 Agentic Debt as a Metric

Once trace data accumulates across an engineering team, agentic debt becomes measurable: sessions where the agent completed the task but the reasoning chain contains orphaned decisions, skipped checkpoints, or decisions that touched files not in the original scope. Leading indicator of future maintenance cost.

### 10.3 Integration Points

- CI pipeline: attach the trace file to the PR automatically as a comment
- Code review tooling: surface the decision chain inline next to the diff
- Incident response runbook: add "pull trace file for relevant sessions" as a step alongside git bisect
