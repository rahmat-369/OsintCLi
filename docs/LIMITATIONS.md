# Known limitations / V2

- This is public-source collection, not exhaustive identity resolution. Same usernames, avatars and display names are not sufficient to merge people.
- Instagram/TikTok/Reddit can block requests or omit public metadata. Login walls/private profiles/challenges are failures, not verified absence. Some APIs have rate limits. Public metadata may change or be spoofed.
- Five native platforms are selected; thousands of upstream modules are not enabled. User Scanner CLI currently selects GitHub/TikTok; Sherlock/Maigret select GitHub/GitLab/Reddit. External tools may have different detection quality from native parsers.
- A website can link to someone else's profile. PUBLIC_LINK / PLATFORM_LINK do not prove common ownership. Review is an operator judgement, not a new source fact.
- Deep mode traverses at most two public-link levels; node budget and response caps truncate collection explicitly. No general web-search index is included. Email input checks syntax/DNS; phone input normalizes format only. Contact identifiers may be recorded when published in observed pages.
- No account-recovery or signup probing, no private-session scraping, no automatic identifier sweeps, no camera discovery. Media URLs are metadata, not fetched evidence.
- DOCX requires python-docx/lxml; Termux compilation may need native packages. Actual Android hardware has not been tested. Linux PTY widths and installer/source tests are documented in TEST-V2.md.
- SQLite v2 migration creates a backup; older OsintCLI versions cannot open v2 directly. Report files copied elsewhere are not removed when deleting a case.
- Resume recollects a failed module within the original Fusion scope; the per-URL traversal queue is not a persistent incremental queue.
- Proxy mode requires explicit approved hostnames; a newly discovered host outside the list produces PROXY_SCOPE. Direct mode validates public IPs itself. External subprocess transport differs from the native client.
- AI remains optional and externally hosted. A prior provider probe returned HTML Site Unavailable; availability is not guaranteed. Reports do not require AI.
- Git history can retain a deleted credential file. Removing it from the latest tree does not revoke the credential or erase past commits.
