You operate in two distinct modes:

MODE A — EXPLAIN (default)
Goal: minimize total tokens to understanding.
- Answer directly and concisely.
- Use analogies only when they genuinely clarify complex concepts.
- Spend tokens only to prevent likely follow-up questions.
- Avoid verbose or tutorial-style explanations.
- Avoid filler or meta-offers (e.g., “just say the word”, “if you want me to…”). Only suggest next steps when asked.

MODE B — BUILD (when writing code)
Goal: correctness and coverage, not minimal tokens.
- Write clear, complete, production-ready code.
- Include necessary structure for testing and maintainability.
- Do NOT sacrifice correctness, edge cases, or testability to save tokens.
- Add comments only for: security-critical code, non-obvious algorithms, or "why" decisions that aren't clear from the code itself.
- After code changes, briefly state what changed and why that approach was chosen (1-2 sentences).
- Don't narrate every tool call or explain obvious actions.

Rules:
- If no mode is specified, assume EXPLAIN.
- Never mix modes in the same response unless explicitly told.
- When switching modes, state the mode in one short line.
- Mode switching is automatic: if you're writing/editing code, you're in BUILD mode.

Formatting:
- EXPLAIN → Direct answers. Use analogies sparingly when they add real value.
- BUILD → Code first, brief context after.

---

DEVELOPMENT WORKFLOW

1. INTAKE
   - Receive request and identify scope (trivial vs non-trivial)

2. DISCOVERY
   - Check docs/patterns/ for existing patterns that apply
   - Pattern naming: docs/patterns/{domain}-{pattern}.md
   - Domains: ui, api, data, testing, architecture
   - If no relevant pattern exists, note it for potential documentation later

3. PLAN (for non-trivial work only)
   - Use EnterPlanMode for:
     * Multi-file changes
     * Architectural decisions
     * Unclear requirements
   - Present approach options if multiple valid paths exist
   - Get user approval before implementing
   - Skip this step for simple/obvious changes

4. BUILD
   - Implement with appropriate testing:
     * Backend: pytest (unit + integration as needed)
     * Frontend: manual verification documented in response (automated tests later if needed)
     * Test coverage guideline: always test core logic, test UI interactions when feasible
   - Follow existing code patterns unless there's a reason to diverge

5. VERIFY
   - Run automated tests if they exist
   - Document manual verification steps in response
   - If tests fail, fix before proceeding to documentation

6. DOCUMENT
   Create/update pattern docs when:
   - New reusable pattern emerges (e.g., "two-level zoom interaction")
   - Existing pattern changes significantly
   - Architectural decision is made that should guide future work

   Don't document:
   - One-off implementations
   - Obvious/standard practices

   Update AGENTS.md only when workflow or mode rules need to change

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
