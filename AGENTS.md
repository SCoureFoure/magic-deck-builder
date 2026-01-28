You operate in distinct modes:

MODE A — EXPLAIN (default)
Goal: minimize total tokens to understanding.
- Answer directly and concisely.
- Use analogies only when they genuinely clarify complex concepts.
- Spend tokens only to prevent likely follow-up questions.
- Avoid verbose or tutorial-style explanations.
- Avoid filler or meta-offers (e.g., “just say the word”, “if you want me to…”). Only suggest next steps when asked.

MODE B — PLAN
Goal: define a clear, approved approach before implementation.
- Use for non-trivial work only (multi-file, architectural, or unclear requirements).
- Present approach options if multiple valid paths exist.
- Get user approval before implementing.
- Skip for simple/obvious changes.

MODE C — DEVELOP (when writing code)
Goal: correctness and coverage, not minimal tokens.
- Write clear, complete, production-ready code.
- Include necessary structure for testing and maintainability.
- Do NOT sacrifice correctness, edge cases, or testability to save tokens.
- Add comments only for: security-critical code, non-obvious algorithms, or "why" decisions that aren't clear from the code itself.
- After code changes, briefly state what changed and why that approach was chosen (1-2 sentences).
- Don't narrate every tool call or explain obvious actions.

MODE D — TEST
Goal: verify correctness and surface failures early.
- Run automated tests if they exist.
- Backend: pytest (unit + integration as needed).
- Frontend: manual verification documented in response (automated tests later if needed).
- If tests fail, return to DEVELOP.

MODE E — DOCUMENT
Goal: capture reusable patterns and architectural decisions.
- Create/update pattern docs when:
  * New reusable pattern emerges (e.g., "two-level zoom interaction")
  * Existing pattern changes significantly
  * Architectural decision is made that should guide future work
- Don't document one-off implementations or obvious/standard practices.

Rules:
- If no mode is specified, assume EXPLAIN.
- Never mix modes in the same response unless explicitly told.
- When switching modes, state the mode in one short line.
- Mode switching is automatic: if you're writing/editing code, you're in DEVELOP mode.

Formatting:
- EXPLAIN → Direct answers. Use analogies sparingly when they add real value.
- PLAN → Short, ordered plan with approval prompt.
- DEVELOP → Code first, brief context after.
- TEST → Test command(s) + results; if not run, state why.
- DOCUMENT → Doc changes first, brief context after.

---

DEVELOPMENT WORKFLOW

| Step | Purpose | Mode |
| --- | --- | --- |
| Intake | Receive request, identify scope (trivial vs non-trivial). | EXPLAIN |
| Discovery | Check `docs/patterns/` for relevant patterns; note gaps. | EXPLAIN |
| Plan | Required for multi-file/architectural/unclear work; present options and get approval. | PLAN |
| Develop | Implement changes following existing patterns. | DEVELOP |
| Test | Run automated tests; if failures, return to Develop. | TEST |
| Iterate | Develop → Test until satisfactory. | DEVELOP / TEST |
| Document | Update pattern docs when needed (see MODE E rules). | DOCUMENT |

Update AGENTS.md only when workflow or mode rules need to change.

---

PATTERN DOCUMENTATION STRUCTURE

Location: docs/patterns/{domain}-{pattern}.md

Template:
```markdown
# {Domain}: {Pattern Name}

## Context
When and why to use this pattern

## Implementation
Code approach with key technical decisions explained

## Trade-offs
What this approach optimizes for and what it sacrifices

## Examples
References to actual implementations (file:line)

## Updated
YYYY-MM-DD: Brief changelog of what changed
```

Deprecated patterns:
- Prefix filename with "DEPRECATED-"
- Add migration path in doc
- Keep for reference, don't delete
