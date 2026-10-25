# Specs

Living contracts for each subsystem: behaviour, data contracts, invariants and decided points. Read the relevant spec **before** changing a subsystem, whether you are a person or an AI session, so you inherit decisions instead of re-deriving or reopening them.

One kebab-case file per subsystem. No dates in filenames: git history is the changelog.

## Lifecycle

- **Drafted before the subsystem is built** and marked _Draft_ until the code matches it.
- **Updated in the same commit** that changes pinned behaviour. A spec that lags the code it pins is worse than no spec.
- **The status line sits directly under the title:** `> _Draft_ · Last verified against code: not yet`, then `> Last verified against code: YYYY-MM-DD` once the code matches. If that date is more than a month old, spot-check two or three invariants against the code before trusting the rest. The `spec-auditor` agent does this on request, and before any commit that changes pinned behaviour.

## What does not live here

- **Plans and working notes.** They stay out of the repository. A spec is what remains of a plan once the work is done.
- **Cross-cutting decisions.** They live in the Decisions table in [`docs/architecture.md`](../docs/architecture.md). A decision local to one subsystem lives in that spec's _Invariants & decided points_, with the alternative it rejected.
- **Facts the code states better.** Package versions (lockfiles), keyword word lists and test inventories (tests), generated schemas (`frontend/openapi.json`). Specs link to these rather than copying them, because copies drift.

## Section template

Each spec uses these sections, omitting any that would be empty:

1. **Purpose**: what the subsystem is for, in a paragraph.
2. **Key files**: entry points and load-bearing modules.
3. **Behaviour contract**: what a user or consumer can rely on happening.
4. **Data contract**: shapes on the wire and in caches.
5. **Invariants & decided points**: what must stay true, and decisions already made with their reasons.
6. **Fixture/mock semantics**: what fakes and mocks deliberately model, and where they diverge from the real thing.
7. **Deferred / open**: known gaps and consciously deferred work, so that "missing" can be told apart from "forgotten".

## Index

| Spec | Subsystem |
|---|---|
| [api-contract.md](./api-contract.md) | HTTP API: endpoints, the Dataset shape, problem+json errors, validation, OpenAPI and codegen |
| [curation.md](./curation.md) | AI curation: provider selection, the Claude request and prompt, normalisation, failures, the keyword mock |
| [datasets-ui.md](./datasets-ui.md) | The catalogue page: form, list, delete, feedback, focus, accessibility |
| [styling.md](./styling.md) | Design principles, Tailwind v4 tokens and contrast, the variant pattern |
| [quality-gates.md](./quality-gates.md) | Scripts, test layers, coverage gates, git hooks, CI, the E2E harness, Claude-in-Chrome verification |
