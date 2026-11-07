# Contract reference

Contracts are JSON objects with `version: 1` and a non-empty `columns` object. Duplicate JSON keys and unknown rule names are errors. The CLI reads UTF-8 (with an optional BOM).

## Dataset options

| Option | Default | Meaning |
| --- | --- | --- |
| `name` | `Untitled contract` | Display name |
| `allow_extra_columns` | `false` | Permit fields not declared in the contract |
| `unique_rows` | `false` | Fail each repeated record after its first occurrence |
| `unique_keys` | `[]` | Arrays of column names defining composite unique keys |
| `null_values` | `[""]` | Exact strings treated as missing after trimming the CSV value |

Every declared column must exist in the CSV header, even when its `required` rule is false. `required` describes cell values, not header presence. Columns are matched by exact, case-sensitive header names; headers are not renamed or trimmed. Blank header names and duplicate headers are input errors.

## Column rules

| Rule | Values / meaning |
| --- | --- |
| `type` | `string` (default), `integer`, `number`, `boolean`, `date` |
| `required` | Boolean; reject missing values |
| `unique` | Boolean; reject repeated non-missing values |
| `min`, `max` | Inclusive JSON numeric bounds; numeric types only |
| `enum` | Non-empty list of allowed strings; compared with the CSV text |
| `pattern` | Python regular expression, matched against the whole value |
| `min_length`, `max_length` | Inclusive character counts, measured after trimming |

Missing cells skip other column rules. Composite keys with any missing component skip uniqueness; add `required` rules when all components must be present. Uniqueness compares trimmed strings, so `1` and `1.0` are distinct lexical values. Full-row duplicates also compare trimmed cells. Composite keys are JSON-encoded tuples, so embedded separators cannot cause concatenation collisions.

Integers accept an optional sign and ASCII digits, without redundant leading zeroes. Numbers accept decimals and scientific notation, reject NaN/infinity, and are limited to 1024 input characters and nonzero base-10 exponents from -1000 to 1000. Numeric calculations use Decimal's 28-digit default precision. JSON reports store numeric min/max/mean as strings to avoid binary-float conversion. Boolean checks accept case-insensitive `true` and `false`; dates require a real calendar date in exactly `YYYY-MM-DD` form.

Patterns are trusted local configuration. Avoid pathological regular expressions, and never run user-supplied contracts as a hosted service without additional limits.

## CSV behavior

Default encoding is `utf-8-sig`, which also accepts UTF-8 without a BOM. Use `--encoding cp1252` for an appropriately encoded legacy file. The delimiter defaults to a comma; `--delimiter tab` selects TSV. Quoted commas, quotes, and multiline fields use Python's standard CSV parser in strict mode. Empty physical records are skipped. The standard CSV parser's field-size limit applies (typically 128 KiB per field). Incorrect record widths, unclosed quotes, undecodable bytes, and bad headers stop the run with exit code 2; no new report is written for that run.

Record numbers start at 1 for the header and count CSV records, including skipped empty records. `line` is the physical line on which a record ends; a multiline record can span several lines. Dataset/header findings have `record: null` and `line: null`.

## Comparison thresholds

```bash
tabletrail compare before.csv after.csv --null-threshold 0.05 --mean-threshold 0.25 --row-threshold 0.5
```

- Missing fractions must **increase by more than** 0.05 (five percentage points) to be flagged.
- Numeric means must change by more than 25% relative to the absolute baseline mean. This applies only when both inferred column types are numeric.
- Record counts must change by more than 50% relative to the baseline count.
- Any mean change from a zero baseline, or any records added to an empty baseline, is flagged.
- Schema additions/removals and inferred type changes are always reported.

These are configurable heuristics, not hypothesis tests. Reordered columns do not count as schema changes. Value-distribution and quantile comparisons are future work.

## Output and errors

`--max-issues 200` limits stored examples, not total issues or failed-record counts. A record may violate several rules. `issue_count` includes header failures; `failed_records` counts data records only. Reports use basenames rather than full input paths. JSON keys are versioned with `report_version: 1`; no timestamp is included, so rerunning the same input and options produces the same result.

CLI report destinations cannot equal a source or contract path, or one another. Each file is atomically replaced after a successful analysis; a pair of JSON/HTML outputs is not one cross-file transaction. Input files are never rewritten or cleaned automatically.
