# Architecture and decisions

```text
CLI / Python API
      |
      +-- Strict contract parser
      |
CSV reader --> One-pass analysis --> Versioned JSON report --> Offline HTML renderer
                    |
                    +-- Temporary SQLite counts and first-occurrence index

Baseline analysis + Current analysis --> Explicit drift rules --> Comparison report
```

## Separation of concerns

- `reader.py`: input decoding, header validation, quoted/multiline records, record width checks.
- `contracts.py`: immutable rule objects; rejects unknown fields, duplicate JSON keys, invalid bounds, and malformed patterns.
- `engine.py`: per-record checks and incremental column summaries. Public `analyze` returns plain JSON-compatible dictionaries.
- `storage.py`: an exact frequency and first-occurrence index in a temporary SQLite database; keys are bound parameters.
- `compare.py`: compares two profiles and returns ordered changes under explicit thresholds.
- `report.py`, `report.css`, `report.js`: render an HTML artifact from the report dictionary. No network, build step, or frontend framework.
- `cli.py`: argument parsing, exit codes, overwrite checks, and atomic file writes.

## Why SQLite instead of Python sets?

A set of every unique SKU can grow with the whole dataset. SQLite moves that index to temporary disk, with a 4 MiB page-cache target, while the Python layer holds the current row, per-column aggregates, and a capped list of issues. Distinct counts and frequent values remain exact. SQL values use parameters, and compound keys use JSON arrays rather than joined strings.

The tradeoff is more disk I/O and per-value SQL calls. This implementation prioritizes understandable correctness over throughput. Batching inserts, adding a row-only validation mode, and better disk-space controls are useful next steps. Python's memory footprint is bounded by columns, row width, retained examples, and report summaries; SQLite and OS caches are additional native memory. Temporary storage grows with distinct values and is removed when analysis exits normally or raises an exception.

## Why deterministic reports?

Reports contain no wall-clock timestamps or absolute input paths. Finding order follows input order; frequency ties sort by encoded value, and comparison changes sort by column and code. This makes reports easy to diff and suitable for regression fixtures.

## Why no auto-cleaning?

A negative quantity might be a typo or a legitimate adjustment. Silently rewriting it would confuse a domain decision with a formatting fix. The current tool reports evidence and preserves the input. Any future cleaning command should require explicit transformations and write a separate output.

## Security boundaries

All text inserted into HTML is escaped. Embedded JSON also escapes `<`, `>`, and `&`, preventing a CSV value containing `</script>` from ending the data block. JavaScript filters rows using `textContent`; it does not render user input through `innerHTML`. A restrictive content security policy blocks external requests. Contract regexes are trusted local code-like input and are not safe for arbitrary multi-tenant execution.

## What the project does not establish

Passing checks does not establish business correctness. Inferred types describe observations, and a contract generated from a small sample can be wrong. The tool has no authentication, network service, model training, or production deployment. It is intended for local CSV workflows with data the operator has permission to inspect.
