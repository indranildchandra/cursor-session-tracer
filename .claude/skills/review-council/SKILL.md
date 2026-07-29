---
name: review-council
description: Multi-persona council for architecture and design reviews. Independent expert subagents review, debate, and converge on a verdict with human input, then distil the decision into an ADR (docs/adr/) that the implementation trace links back to. Invoked by /design-review.
disable-model-invocation: true
---

# Review Council Protocol

## Token budget — read this first

**Load personas on demand, never all at once.**
- There are 20+ persona files. Loading all of them would consume the entire context window.
- In Phase 2 you select 3–6 personas. Load **only those files** — nothing else.
- Each persona subagent receives **only**: its own persona file + domain profile + scope brief. No other context.
- Subagents run in isolation — they do not inherit the parent session's full context.
- Persona outputs returned to the parent are compressed (max 300 words each).
- If you find yourself loading more than 6 persona files, stop and reduce the council size.

## Overview

The council reviews code, architecture, or design decisions using independent expert personas that debate, challenge each other, and converge on a verdict. The human engineer is an active participant, not a passive recipient.

The council produces **two artifacts**: the full debate transcript (`docs/design-review.md`) and — its point — a distilled **ADR** (`docs/adr/ADR-NNNN-*.md`). The ADR is the plan-of-record; a later implementation trace (cursor-session-tracer) links back to it via `adr_id`, and `audit_trace.py` checks the implementation stayed faithful to the ADR's declared scope. This is the "ADR formulated through adversarial review" half of the plan-vs-path model.

**Minimum council size:** 3 personas.
**Council size by complexity:**
- `simple` (single component, low risk): 3 personas
- `medium` (cross-cutting feature, moderate risk): 4–5 personas
- `complex` (system-level, high risk, multiple teams): 5–6 personas

**Always include at least one of:** `staff-engineer`, `cloud-cost-architect`, `appsec-architect` — cost and security angles must be represented in every council.

---

## Phase 0 — Scope + Early Human Input

1. If `/design-review` was called with a scope argument, use it as-is.
2. If no argument: run a quick repo scan (1 Haiku subagent, `gitnexus ctx_search` or file glob) to identify the highest-risk or most recently changed area. Propose this as scope.
3. **Present to human and ask:**
   - "Does this scope look right, or do you want to focus elsewhere?"
   - "What concerns you most about this? Any known constraints (deadline, regulatory, performance budget)?"
   - "Any personas you want added or removed from the council?"
4. Record answers verbatim as the **Phase 0 Human Brief** — this shapes everything downstream.
5. If the user requests a persona not in `standard-personas/`: generate it using the schema in `user-generated-personas/README.md`, save it to `user-generated-personas/<name>.md` globally, then use it in this session.

---

## Phase 1 — Domain Fingerprinting *(1 Haiku subagent)*

**Input:** scope from Phase 0
**Task:** Analyse the scoped code/design and output:
- Tech stack and architectural patterns
- Key risk areas
- Scale characteristics (current and anticipated)
- **Complexity rating:** `simple` | `medium` | `complex`

**Output format (compressed, ~200 words):**
```
Domain: <primary domain tags>
Stack: <languages, frameworks, key dependencies>
Patterns: <architectural patterns in use>
Risk areas: <2-3 highest-risk aspects>
Scale: <current and anticipated>
Complexity: simple | medium | complex
```

---

## Phase 2 — Persona Selection *(main context)*

1. From Phase 1 domain profile + Phase 0 human input, select personas from `standard-personas/`.
2. Load **only** the selected persona files — do not load all 20.
3. Apply council size rule from complexity rating.
4. Ensure at least one of: `staff-engineer`, `cloud-cost-architect`, `appsec-architect`.
5. Add any user-requested custom personas.
6. Present the council lineup to the human: "Council will be: [list]. Proceed?"

---

## Phase 3 — Independent Review *(N parallel subagents)*

**One subagent per persona.** Model is specified in each persona file's frontmatter.

**Each subagent receives ONLY:**
- The persona file (defines their role and review lens)
- The domain profile from Phase 1
- The scope brief and Phase 0 Human Brief

**Subagents are isolated** — they cannot see each other's output.

**Each subagent returns this compressed structure (max 300 words):**
```
## [Persona Name]
**Stance:** proceed | caution | block
**Top findings:**
- <finding 1>
- <finding 2>
- <finding 3>
**Blocker (if any):** <description, or "none">
**Questions to council:**
- <question 1>
- <question 2>
```

---

## Phase 4 — Council Session *(main context)*

1. Present all Phase 3 outputs together.
2. For each persona, write a brief response (2-4 sentences) to the key challenges raised by the others that affect their domain.
3. Identify from the debate:
   - **Converged concerns** — issues ≥2 personas flagged independently (highest signal)
   - **Blocking concerns** — issues that must be resolved before proceeding
     - Rule: 1 persona to raise a blocker, 2 personas to dismiss it
     - Human can unilaterally override any blocker — override is recorded explicitly with rationale
   - **Domain opinions** — valid tradeoffs that don't block
   - **Open questions** — cannot be resolved without more information or human input

---

## Phase 5 — Human Input *(interactive pause)*

Present to the human:
- Summary of converged concerns (max 3 bullets)
- Any blocking concerns
- 2–3 pointed questions the council cannot resolve without human input (priorities, constraints, risk tolerance, product decisions)

Wait for human response. Record verbatim.

**If human overrides a blocker:** Record: *"[Human] overrode blocker raised by [Persona]: [blocker]. Stated rationale: [rationale]."*

---

## Phase 6 — Synthesis *(main context)*

1. Incorporate Phase 5 human input into the council's conclusions.
2. Resolve open questions where possible given human input.
3. State the final verdict clearly:
   - `Proceed as-is` — no material concerns
   - `Proceed with modifications` — list specific modifications required
   - `Redesign required` — list blocking concerns that must be addressed first
4. Produce action items with owners (persona domain or "human").

---

## Phase 7 — Record the review *(writes files)*

1. If the `aidlc-tracking` skill is available, invoke its `formats.md` for the exact
   `docs/design-review.md` template. If it is not available (e.g. this repo only
   vendors `review-council`), use the inline format below.
2. Append the **full council session** (all persona findings, the debate, converged
   concerns, blockers, human overrides, verdict, action items) → `docs/design-review.md`,
   newest entry at the top. This is the transcript — the complete argument.
   Inline header + entry format if `aidlc-tracking` is absent:
   ```markdown
   # Design Review Log
   <!-- Append-only. Newest at TOP. Generated by /design-review + review-council. -->

   ---
   ## YYYY-MM-DD HH:MM:SS — <what was reviewed>
   ### Scope / Phase 0 Human Brief / Council Composition / Round 1 / Round 2 /
   ### Converged Concerns / Blocking Concerns / Phase 5 Human Input /
   ### Final Synthesis / Decision / Action Items
   ```
3. Append one-liner → `tasks/tracker.md` (only if that file / the aidlc-tracking
   convention exists in the repo):
   ```
   ## YYYY-MM-DD HH:MM:SS — Design review: <scope summary>
   **Type:** task-complete
   **Outcome:** <verdict>. <N> personas. <N> blockers. Key finding: <top converged concern>.
   **Files changed:** docs/design-review.md
   ```

---

## Phase 8 — Distil the ADR *(the planning artifact)*

The `design-review.md` entry is the *transcript*. The **ADR is the distilled
decision** the council converged on — the permanent, quotable "what we planned and
why." This is how an ADR gets *formulated through adversarial review*: the debate
happens in Phases 3–6, and its conclusion is crystallised here.

Write it **only** when the verdict is `Proceed as-is` or `Proceed with
modifications` (a `Redesign required` verdict has no decision to record yet — loop
back instead).

1. Determine the next ADR number: the highest `ADR-NNNN` in `docs/adr/` + 1
   (zero-padded to 4 digits). Slug = kebab-case of the decision title.
2. Copy `docs/adr/TEMPLATE.md` → `docs/adr/ADR-<NNNN>-<slug>.md` and fill it in
   from the council's output:
   - **Context / Decision** — from Phase 6 synthesis
   - **Scope (files)** — the concrete files the decision will touch. This list is a
     **machine contract**: `audit_trace.py` parses it to flag implementation drift,
     so make it precise, not aspirational.
   - **Alternatives Considered** — the options the council weighed and rejected
   - **Consequences** — trade-offs + `Risks flagged by council` = the converged
     concerns and any blockers/overrides
   - **Council Verdict** — the Phase 6 verdict, persona count, top converged concern
   - **Review record** — point back to the `docs/design-review.md` entry timestamp
3. Tell the human the new `adr_id` and instruct: *"When you (or the agent) start
   implementing, pass `adr_id=\"ADR-<NNNN>\"` to `start_trace` so the trace links back
   to this plan. Afterwards, `python audit_trace.py --session <date>/<id>` checks the
   path stayed faithful to it."*

This closes the loop: **ADR = plan (this phase) → trace = path (implementation) →
`audit_trace.py` = the faithfulness check between them.**

---

## Token budget guidelines

- Phase 1 subagent output: ~200 words (Haiku, fast)
- Phase 3 persona outputs: ~300 words each (Haiku or Sonnet per persona file)
- Phase 4 debate: in-context, keep each persona response to 3-4 sentences
- Total target: council fits within parent context window; typical session ~8-15k tokens
- If complexity is `simple`, Phase 4 debate can be abbreviated — personas may agree quickly

---

## Persona library

Standard personas are in `standard-personas/` — load only the files selected in Phase 2.
User-defined personas are in `user-generated-personas/` — same loading rule.
