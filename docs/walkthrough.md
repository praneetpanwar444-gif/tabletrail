# Understand and extend TableTrail

This is a new, AI-assisted personal project. Use the walkthrough to understand the implementation and make your own changes. Describe your actual involvement and current progress accurately.

## Run the whole workflow

1. Run `python -m unittest discover -s tests -v` from the project root.
2. Run `python -m tabletrail profile examples/inventory.csv --html reports/profile.html` and open the HTML file.
3. Validate the deliberately broken file using the command in the README. Inspect the 12 findings. Trace the negative quantity to `violations()` in `engine.py`.
4. Find the repeated `(warehouse, sku)` pair. Read how `Counts.add()` returns the first record number, and how JSON encoding keeps multi-column keys unambiguous.
5. Compare the two clean inventory versions. Find which thresholds produced the four changes, then raise `--mean-threshold` and rerun.
6. Draft a contract with `init`, edit a rule, and see how the validation outcome changes.

## Questions to investigate in the code

- Why do missing cells skip type and uniqueness checks?
- Why is a missing column different from a missing cell?
- Why does a repeated row count once after its first occurrence, yet sometimes produce two rule violations?
- Why is a SKU such as `00123` inferred as a string?
- What happens to comparison percentages when the baseline mean is zero or negative?
- Why does issue capping not change `issue_count` or `failed_records`?
- Which memory stays in Python, and which state is stored on disk?
- How does the renderer prevent an HTML-looking CSV value from executing?

## A small first contribution

Add an optional `max_null_rate` dataset rule per column:

1. Define its JSON semantics, valid range, and whether it combines with `required`.
2. Add strict parsing in `contracts.py`.
3. Evaluate it after scanning all records.
4. Emit a dataset-level issue with no record number.
5. Test empty datasets, exact-threshold equality, a failing example, and invalid configuration.
6. Update the contract reference and regenerate the example report.

That is meaningful development work because it adds a real feature across parsing, analysis, tests, and documentation.

## Accurate project description

> TableTrail is my new personal open-source Python project for local CSV profiling, data-contract validation, and dataset comparison. Its initial implementation was created with Codex assistance. It includes a CLI, an offline HTML report, a SQLite-backed exact duplicate index, synthetic inventory examples, and automated tests. The current focus is improving validation rules, usability, and performance.

Only claim changes, testing, or design work that you have personally performed. This description is a starting point for a project survey, not a claim of professional experience or a substitute for an interview.
