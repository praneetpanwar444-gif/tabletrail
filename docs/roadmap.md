# Roadmap

Version 0.1 implements the core workflow. These are proposed improvements, not implemented features.

## Next: stronger contracts

- Per-column maximum missing fractions, with dataset-level findings.
- Cross-column rules such as `quantity >= reorder_level`, with a small explicit grammar rather than `eval`.
- Optional date and numeric normalization, with clear uniqueness semantics.
- A machine-readable contract JSON Schema and more helpful suggested fixes.

## Then: scalability and integration

- Batch SQLite operations and benchmark 100k / 1m records on multiple machines.
- Add a no-frequency validation mode for lower disk use.
- Configurable temporary directory and disk-space guards.
- JSON Lines input via a shared table-reader interface.
- A pre-commit hook and documented CI quality gate for user-owned data.

## Later: richer comparisons

- Explicit column matching and optional column-order checks.
- Quantile/distribution summaries with documented approximation bounds.
- Categorical distribution comparison, beyond the top-five values.
- Accessible report sorting, pagination, and more keyboard-navigation tests.

## Definition of done for a contribution

Document semantics, implement the behavior, add regression tests for failures and boundaries, run the existing suite, and update examples when output changes. Keep a small reproducible fixture for every bug fix.
