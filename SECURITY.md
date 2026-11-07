# Security and privacy

TableTrail runs locally and contains no outbound network, telemetry, account, or upload code. Its example data is synthetic inventory. It is not a hosted service and is not designed to execute untrusted contracts.

- Reports contain observed cell values, frequent values, and issue excerpts. Treat them like the source CSV; HTML also includes the full report as embedded JSON for export.
- Temporary SQLite files contain trimmed observed values. They are cleaned up on ordinary success and exceptions, but this is not secure erasure, and a process crash can leave temporary files behind.
- Regex rules are trusted configuration. Python's regular expression engine has no per-pattern timeout here; hostile patterns can consume excessive CPU.
- Huge files, field widths, column counts, and storage exhaustion can consume significant local resources. Use bounded, trusted inputs. The standard CSV field-size limit applies.
- Atomic replacement protects individual report writes, not the whole pair of JSON/HTML files. Do not reuse an output path that you need to preserve.
- The HTML renderer escapes input and blocks external sources with a content security policy. Reports still disclose their data to anyone to whom you give the files.

Report reproducible non-sensitive bugs through the repository issue tracker. For a security issue, avoid posting private data, secrets, or exploit details publicly; use GitHub's private vulnerability reporting if available on the repository. No response-time commitment or security audit is claimed.
