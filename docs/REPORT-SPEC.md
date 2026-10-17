# Report specification / V2

All formats share one snapshot: case, job status, evidence, append-only reviews, latest relationship decisions, computed counts, methodology and optional reviewed AI narrative. Dataset SHA-256 is over canonical `{evidence, reviews}`; report_id/time are export-specific.

PDF: cover, computed summary, methodology/scope, status/category charts, up to six relationship edges in a vector diagram, complete relationship list, grouped profile metadata, evidence register and review notes, limitations, digest. DOCX: editable equivalents of the summary, tables, relationship list, profile metadata/register, source gaps and digest. DOCX does not include the PDF vector chart. No live video or remote avatar assets are embedded.

JSON preserves raw adapter payloads and all review decisions. CSV flattens source evidence with formula-safe cells (review history is in JSON). HTML is an offline escaped view with a restrictive CSP. PNG is the evidence-category chart. Summary option limits the evidence register to 15 records; relationship list and JSON/CSV remain complete.

A CANDIDATE is not a person attribution. VERIFIED means the source observation matched, not identity verified. A phone-format record does not establish validity, ownership or WhatsApp registration. Errors remain part of the snapshot.

Default output: `~/.local/share/osintcli/reports/<case_id>/`. In menu, Enter or `lokal` uses this path, `android` writes to Android Download after storage permission, another string is a custom directory. On a VPS, Android storage is on the client and needs an SCP download.
