# Historical release verification — OsintCLI 1.0.0

**Superseded for current online functionality by [LIVE-VERIFICATION.md](LIVE-VERIFICATION.md), release 1.0.1.** This file preserves the original 1.0.0 results and limitations; current regression count is 90.

Date: 17 October 2026, Asia/Jakarta. Runtime timestamps use UTC. Environment: Linux x86_64, Python 3.12.14. Physical Android/Termux was not available.

## Results

| Check | Observed result | Evidence |
|---|---|---|
| Automated tests | **71 passed**, no failures | validation/tests-final.log |
| Fresh full Linux installation | Installer + new isolated venv + executable outside repo + demo report verified | validation/release-install-summary.json |
| SQLite | Bootstrap, FK, source-aware dedup, recovery, delete, narrative invalidation, lock tested | Automated tests |
| CLI widths | 32,40,60,80,120 columns; noninteractive fallback | Automated tests |
| Real interactive session | 40-column Linux PTY; history, evidence, report and exit | screenshots/terminal-demo.cast and .gif |
| Sherlock | Audited commit installed; actual public `octocat` query; 2 candidate records normalized | validation/adapter-integration.json; tests/fixtures/sherlock-live.csv |
| Maigret | Audited commit installed; 2 candidates, 1 unverified negative, 1 failed source; case PARTIAL | validation/adapter-integration.json; tests/fixtures/maigret-live.csv |
| ExifTool | Actual command version 13.59; 19 local metadata observations; PDF export successful | validation/adapter-integration.json |
| Direct built-in live scan | Runtime system DNS restriction correctly recorded as FAILED/PARTIAL, without false success | validation/builtin-live.log |
| Public source transport probes | DNS, RDAP and CT returned parseable JSON over environment HTTPS proxy | validation/live-source-probes.json |
| Nexray live | HTTP 200 with HTML “Site Unavailable”; **not a usable API success** | validation/live-source-probes.json |
| AI contracts | Success fixture, missing/empty/false/HTML responses, timeout/offline, encoding, overflow, consent, numeric/injection checks | Automated tests |
| Reports | 0/106 records, Unicode/Arabic, 1500+ character URL, no-AI, metadata-only, formulas/HTML escaping | Automated tests |
| PDF render | Example pages visually inspected; 106-record PDF 30 pages, no text blocks outside page margins | validation/pdf-bounds.json |
| Source safety | private/mixed DNS rejected, DNS pinning, redirect revalidation, size caps, subprocess no-shell/cancel | Automated tests |
| Report dependency audit | **0 known advisories** in the resolved seven report packages at audit time | validation/dependency-audit-final.json |
| Optional tool environment audit | 0 advisories in captured environments after standalone pip upgrade; runtime dependency versions constrained | validation/*-dependency-audit-final.json |
| Physical Termux/Android | **NOT RUN**; installer and storage flow supplied, device acceptance pending | No claim of device success |
| GitHub CI/push | Workflow/source prepared; **not pushed or remotely executed** | .github/workflows/tests.yml |

## Findings fixed during implementation

- Report reader initially used pypdf 6.10.0. Advisory scan identified 49 known entries affecting that version. Updated to **6.19.0**; all report dependency audit entries are now empty. Tests repeated against the updated version.
- Maigret's JSON output only includes claimed records. Runtime adapter uses CSV so unavailable/error sources are retained, rather than disappearing from the evidence register.
- A source reporting HTTP 200 is classified as candidate, not identity verification. Captured Sherlock/Maigret disagreement demonstrates why this distinction is necessary.
- PDF evidence headings are kept with the beginning of their observation table; text/long URL wrapping and Arabic shaping were visually checked.
- AI retry disabled to prevent duplicate submissions; prompt URLs are not logged. Missing provider availability does not affect deterministic reporting.

## Remaining test boundaries

- HTTP transport probes used the environment's HTTPS proxy, not the core pinned-IP transport. Do not call them successful end-to-end core scans. Core networking was exercised through fixtures and failure handling here, and needs a live run on an unrestricted device network.
- Fresh Python virtual environments in this build bootstrap pip 25.0.1. An audit flagged package-manager advisories; a tested isolated update cleared the advisory metadata, but another clean-environment update showed an import incompatibility. The release therefore **does not forcibly upgrade pip**, and it does not claim that the bootstrap package manager is advisory-free. Installer dependencies must be maintained with the OS/Python distribution; Termux's system pip is never upgraded by this project. App report dependencies are audited separately as shown above.
- No unit test can prove an LLM will never fabricate facts. Numeric/injection guards cover specific negative cases; user review is required and AI never changes numeric report data.
- No complete security audit of every upstream implementation was performed. Repositories/licenses/requirements/contracts were inspected, optional dependency advisories checked, and adapters tested. No blanket claim of vulnerability-free code is made.
- Native ARM builds and fonts in Android PDF viewers remain untested. CJK/emoji coverage is outside this release's embedded-font guarantee.

Run `python3 -m unittest discover -s tests -v` after changing dependencies. Run `osintcli doctor`, a scoped public-domain scan, an offline report, then Android export on the actual device to complete device acceptance.
