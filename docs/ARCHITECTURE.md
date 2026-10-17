# Arsitektur dan kontrak

`cli/ui -> engine -> registry -> adapter -> normalized evidence/raw payload -> SQLite -> reports/optional AI`.

- `core.py`: config TOML, validasi target, control-character sanitization, atomic write.
- `net.py`: koneksi HTTP(S) ke IP hasil resolusi yang telah divalidasi, TLS hostname validation, no proxy inheritance, redirect validation, per-host pacing, retry bounded dan circuit breaker.
- `adapters.py`: DNS/CT/RDAP/ASN/HTTP/TLS/email/username/local metadata. Adapter adalah generator observation; satu sumber gagal tidak menghapus evidence sumber lain.
- `external.py`: Sherlock/Maigret CSV dan ExifTool JSON, `Popen` tanpa shell, timeout/output cap dan process-group cancellation. Maigret source mirrors dapat menambah GitHub Gist ke tiga situs dasar; tidak ada recursive account traversal.
- `db.py`: schema version 1, foreign keys, WAL, startup migration. Migration berikutnya wajib backup dan transaksi. Raw payload disimpan terpisah; digest dataset mencakup data normalized+raw.
- `engine.py`: scope depth 1, maksimum 4 worker (default 3), process lock untuk scan/recovery. State: QUEUED, RUNNING, DONE, PARTIAL, FAILED (job), CANCELLED, INTERRUPTED. Resume melanjutkan adapter gagal/parsial; tidak mengulang yang DONE.
- `ai.py`: preview, consent, limited subset, no raw file upload; draft disimpan dan review terikat digest dataset. AI tidak mengubah evidence/statistik.
- `reports.py`: satu snapshot data untuk lima format. File diganti secara atomik; jika satu format gagal, evidence tetap ada dan format sebelumnya tetap dapat dipakai.

## Schema

`cases(id,target,kind,created_at,state,scope)`; `jobs(id,case_id,adapter,state,started_at,ended_at,error_code,message,version)`; `evidence(id,case_id,entity_type,normalized_value,title,source_url,source_name,adapter_id,collected_at,scope_id,status,verification_reason,confidence_basis,digest,error_code)`; `raw_evidence(evidence_id,raw_json)`; `narratives(id,case_id,created_at,provider,instructions,prompt_digest,text,reviewed,dataset_digest)`.

Deduplikasi menggunakan isi normalized + provenance + alasan/status; sumber berbeda tidak digabung menjadi satu tanpa jejak. Raw payload bukan credential vault. Aplikasi tidak mengambil contact vCard dari RDAP atau mengirim cookie/token pengguna.

## Threat model

Untrusted: input target, URL/redirect, HTTP payload, metadata file, output tool, AI response. Mitigasi: target allowlist grammar, IP global check termasuk multicast/reserved, DNS pinning, HTTPS validation, ukuran respons/file, subprocess argv, timeout, escaping HTML/PDF/CSV, terminal control stripping. Custom provider hanya HTTPS; rahasia header di file 0600.

Batas: third-party tools mempunyai network stack sendiri dan tidak mewarisi guard HTTP OsintCLI. Scope dipersempit ke database/situs upstream yang diaudit; tidak ada kemampuan bypass/cookie yang diaktifkan. Parser metadata native/third-party tetap memerlukan pembaruan keamanan. Tidak mengklaim sandbox process atau perlindungan terhadap semua file berbahaya. System DNS lookup mengikuti timeout resolver OS. Tidak ada bypass jaringan, CAPTCHA, login, brute force, exploit, atau pemindaian port.

## Perubahan yang disengaja dari PRD

Grafik menggunakan ReportLab vector dan Pillow, bukan dependensi wajib Matplotlib. Keputusan ini mengurangi build native yang berat di Termux; grafik tetap dihitung deterministik dari snapshot SQLite, dan PNG mencatat data sumber lewat JSON companion. Arsitektur diperpendek menjadi modul Python yang terpisah per tanggung jawab, bukan folder kosong. Diagram hubungan hanya sumber → observasi ber-ID; advanced identity correlation P2 tidak diimplementasikan. Lisensi upstream tertentu dipakai sebagai referensi, bukan semua repo dijadikan runtime wajib.
