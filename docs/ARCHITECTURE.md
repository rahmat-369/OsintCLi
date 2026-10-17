# Architecture / V2

CLI numbered menu and commands → target validation → selected engine → bounded HTTP/process execution → SQLite → review → shared report snapshot → PDF/DOCX/JSON/CSV/HTML/PNG.

## Fusion

`fusion.py` contains public profile parsers and a breadth-first queue. Quick/standard/deep select depth 0/1/2; max nodes defaults to 12 (1–30). The visited set canonicalizes supported social profile URLs. Only exact public API/HTML profile identifiers become candidates. Challenge, private or unexpected payloads become source errors. A query URL is not automatically followed.

GitHub social_accounts and website/blog fields are explicit pivots. Website pages expose profile/contact/rel=me links; known hubs can expose outbound pages. Same-site article/navigation crawling is excluded. Contacts are recorded, never messaged or used for registration/recovery. Metadata is one grouped record per profile. Assets such as avatars are URL fields only, not downloaded.

## Persistence

Schema v2 adds append-only `evidence_reviews`, with foreign keys to evidence. Existing v1 databases are backed up once before migration. Evidence remains immutable; accepted/rejected/pending reviews do not rewrite collection status. The dataset digest covers evidence and review history; a changed review invalidates old AI narrative approval. JSON exports use schema_version 2.

Relationships live as typed evidence with from/to/relation/depth, source URL and collected_at. `graph` returns these with the latest operator review. PUBLIC_LINK and PLATFORM_LINK are observations of links, not ownership claims. Profile candidates sharing a username are not silently merged.

## Recovery and transport

Process lock, cancellation, job states, failures, retries and per-host pacing remain from v1. Failed/interrupted modules can be resumed; Fusion restores mode and max-node scope from the case. Resume recollects the failed module within that scope, not an exact durable per-URL queue checkpoint. Duplicate identical evidence is ignored.

Direct transport pins public IPs and validates redirects/TLS. Explicit proxy mode allows owner-approved HTTPS hostnames, relying on the trusted proxy for routing. External tools manage their own transport and do not inherit OsintCLI host validation; only selected upstream modules run, bounded by process timeout/output size. API credentials are not required for default public sources.

## Upstream boundaries

User Scanner public parsers are adapted under MIT with included attribution. Its optional CLI is pinned, isolated and limited to GitHub/TikTok. Sherlock and Maigret remain optional selected-site subprocesses; ExifTool reads local files. Reference-only repos are documented separately and are not claimed as integrated engines.
