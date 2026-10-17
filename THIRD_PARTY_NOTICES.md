# Third-party notices and upstream audit

Audit date: 2026-10-17 WIB. All seven repositories were shallow-cloned into a temporary audit workspace; commits below were read from local Git HEAD. LICENSE/README/CLI exports/package requirements and output schemas were inspected. V2 adapts selected public-profile parsing logic from User Scanner; see the attribution below.

| Upstream | Pinned audit commit | License inspected | Integration |
|---|---|---|---|
| [kaifcodec/user-scanner](https://github.com/kaifcodec/user-scanner) | `b85d470b48f7fb9d5ccff85080a882bf70049ed7` | MIT, Copyright (c) 2025 Kaif | Adapted Instagram public metadata / TikTok userInfo parsers; optional isolated CLI |
| [sherlock-project/sherlock](https://github.com/sherlock-project/sherlock) | `e40a45ec2a074b90703b3b4b842c8a3adbd6ada3` | MIT | Optional isolated process, CSV adapter |
| [soxoj/maigret](https://github.com/soxoj/maigret) | `eaf820666d15bfd545129f3223e2261c27191e74` | MIT | Optional isolated process, CSV adapter |
| [lanmaster53/recon-ng](https://github.com/lanmaster53/recon-ng) | `32b08fe7b6993ca1f2d8f76ba8f5d23c7f34a11d` | GPL-3.0 | Workspace architecture reference only |
| [smicallef/spiderfoot](https://github.com/smicallef/spiderfoot) | `0f815a203afebf05c98b605dba5cf0475a0ee5fd` | MIT | Event/provenance reference only |
| [laramies/theHarvester](https://github.com/laramies/theHarvester) | `49a38f8d33c32336bbf6a111ea723ea223116265` | GPL-2.0 | Reference only; HEAD requires Python >=3.14 |
| [exiftool/exiftool](https://github.com/exiftool/exiftool) | `2200871d9cef988051d2a99d67df3bda6cbb30a8` | Perl Artistic or GPL (README; LICENSE file is GPL-3.0) | Optional external command, read-only JSON |
| [blacklanternsecurity/bbot](https://github.com/blacklanternsecurity/bbot) | `a6fb827bb144cdb85b52e142a4d6e14ed5f94b69` | AGPL-3.0 | Extensibility reference only; no AGPL code copied |

## Changes and copyright

V2 `osintcli/fusion.py` adapts the public HTML/JSON extraction approach from User Scanner Instagram and TikTok modules (Copyright (c) 2025 Kaif, MIT). Changes: own bounded transport, exact handle checks, JSONDecoder parsing for escaped braces, public GET only, no signup/recovery fallback, bounded graph traversal and provenance. The full license is in `docs/licenses/user-scanner-LICENSE.txt`. CLI adapters for other tools were independently authored against observed public CSV/JSON contracts. Runtime installs optional tools at audited commit hashes; their package dependencies retain upstream licenses. No rebranding of upstream code as R_HMT work. Recon-ng/SpiderFoot/BBOT/theHarvester are not distributed runtime components. This separation is not a blanket legal opinion about GPL/AGPL combinations; any future source incorporation requires a fresh assessment.

Sherlock: Sherlock Project contributors (created by Siddharth Dushantha). Maigret: Alexey “soxoj” and contributors. ExifTool: Phil Harvey and contributors. Recon-ng: Tim Tomes/contributors. SpiderFoot: Steve Micallef/contributors. theHarvester: project contributors. BBOT: Black Lantern Security/contributors. Exact copyright terms remain in included upstream license texts.

## Python and bundled assets

| Component | Use | License / notes |
|---|---|---|
| python-docx | Editable Word reports | MIT |
| lxml | DOCX XML processing | BSD-style |
| ReportLab | Deterministic PDF/vector charts | BSD-style, installed dependency |
| Pillow | Local image metadata, PNG chart, icon conversion | HPND-style PIL license, installed dependency |
| pypdf | Local PDF metadata/test extraction | BSD-3-Clause |
| arabic-reshaper | Arabic report shaping | MIT |
| python-bidi 0.4.2 | Pure Python bidi display | LGPL family; separately installed dependency, no source copying |
| six | Dependency compatibility | MIT |
| charset-normalizer | ReportLab dependency | MIT |
| DejaVu Sans regular/bold | Embedded PDF font, distributed TTF | Bitstream Vera license + DejaVu public-domain changes; full notice included |
| README banner | Provided project artwork | Owner-provided generated reference; no third-party upstream branding claim |

Direct report dependencies are pinned in requirements-reports.txt. Linux resolver results and upstream installation snapshots are in docs/validation/. These are observational environment locks, not universal Android binary locks. Security advisory audit status is recorded in TEST-REPORT.md; no unsupported claim that all dependencies are vulnerability-free.
