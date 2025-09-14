# Decisions

Architectural Decision Records (ADRs) documenting project choices.

## ADR-0001: Adopt a Single Source of Truth for planning
- Status: Accepted
- Context: Planning information scattered across tools leads to confusion.
- Decision: `/docs/backlog.md` is the authoritative backlog.
- Consequences: All planning updates require PRs modifying the backlog.

## ADR-0002: Track decisions in version control
- Status: Accepted
- Context: Decisions should be reviewable and traceable.
- Decision: Maintain this ADR log in `/docs/decisions.md`.
- Consequences: Each significant decision adds a new ADR entry.
