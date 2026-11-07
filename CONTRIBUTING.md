# Contributing

TableTrail is a new project and small, well-tested improvements are welcome. Check the roadmap before starting a larger change.

```bash
python -m venv .venv
# Activate the environment using the instructions in README.md.
python -m pip install -e .
python -m unittest discover -s tests -v
```

Use synthetic fixtures. Do not commit private datasets, generated reports from private data, credentials, virtual environments, or temporary SQLite databases. Regression tests should verify user-visible behavior, including failure cases and exact-threshold boundaries.

Keep CLI exit codes stable. Treat the `report_version` JSON structure as a public interface. Update the contract reference when rules change, and regenerate examples with the CLI rather than editing their output by hand. Disclose material AI assistance in the change description and review generated code before submitting it.
