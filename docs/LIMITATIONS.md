# Known limitations — release 1.0.0

1. No physical Android/Termux installation test is available. Linux Python 3.12.14 fresh install is tested. Treat Android as an implementation target pending device acceptance, not a certified platform.
2. Nexray returned HTML “Site Unavailable” in the release smoke probe. Core reports work without AI. The adapter cannot repair an unavailable external provider.
3. Direct system DNS is restricted in this build environment. Built-in live collection therefore records DNS/NETWORK failures here. Separate HTTPS transport probes reached DNS/RDAP/CT sources; those probes are not claimed as end-to-end built-in live success. Offline contract tests cover parsing, recovery and bounded failures.
4. Sherlock and Maigret may disagree. Their results are candidates, not identities. Site blocks, exclusions, mirrors and soft-404 pages reduce accuracy. No brute-force expansion, bypass, full-page profile dossier, or automatic real-person correlation.
5. Third-party engines are optional and can be heavy on ARM/Termux. Maigret includes native dependencies; failure does not prevent the built-in engine, database, or report export.
6. Public service availability/ToS/rate limits can change. Historical CT and RDAP registration country are not current host availability or precise geolocation.
7. Email validates supported syntax and public domain records, not mailbox existence; it never sends email, probes SMTP, or tests accounts.
8. All data is local but not encrypted. Delete is logical deletion, not guaranteed forensic erasure. Copies exported outside canonical report folders remain after case deletion.
9. HTTP fetching is intentionally bounded to standard ports, public IPs, and selected paths. Core network ignores proxy environment variables to retain IP pinning. Third-party tools have their own network stacks.
10. AI numeric/injection checks are conservative guards, not factual verification. Human review remains required. A user can approve incorrect prose; computed statistics never depend on that prose.
11. PDF fonts support Latin/Arabic; CJK and emoji may need an additional font. No arbitrary “all languages” claim.
12. Recon-ng, SpiderFoot, BBOT, and theHarvester were audited as references; they are not silently installed or included in the runtime. theHarvester audited HEAD requires Python 3.14. No upstream source code is vendored.
13. Installed dependency locks describe one Linux resolver result; they are not universal ABI locks for Android. Read security audit status before claiming dependency safety.
