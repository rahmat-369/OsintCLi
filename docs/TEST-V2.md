# Pengujian OsintCLI 2.0.0

Pengujian sumber nyata dilakukan 17 Oktober 2026 (UTC; WIB +7). Alurnya CLI → jaringan → SQLite → ekspor. Tes regresi terpisah memakai fixture/mock untuk kondisi kegagalan yang terkontrol.

## Regresi dan instalasi

**107 tes lulus** pada Python 3.12/Linux. Cakupan: validasi target, alamat publik, redirect, proxy allowlist, pembatalan, kesalahan subprocess, soft-200, metadata, format ekspor, CSV injection, migrasi database beserta backup, siklus/budget graph, provenance, review antar-kasus, invalidasi narasi setelah review, DOCX/JSON konsisten, dan PDF dengan bio penuh newline.

Installer Linux berjalan pada virtual environment baru. Entry point paket diuji dari luar source tree: versi 2.0.0, kasus demonstrasi berlabel, dan enam format export berhasil. Path ekspor dicetak utuh agar dapat disalin.

## Sumber nyata

| Pemeriksaan | Hasil teramati |
| --- | --- |
| Fusion username `octocat` | Profil GitHub dan metadata publik Instagram ditemukan; empat hubungan tercatat. TikTok HTTP 400 pada uji akhir, Reddit 403; kasus PARTIAL. Kesamaan username tidak dianggap satu pemilik. |
| Kontrol username `osintcliqz9x726` | Tidak ada kandidat. GitHub/GitLab memberi hasil negatif; Instagram tidak memberi metadata cocok; TikTok/Reddit gagal. Kegagalan bukan bukti akun tidak ada. |
| URL `https://github.com/octocat` | Mengikuti blog publik → tautan GitHub/Instagram/TikTok; metadata Instagram `github` terbaca. Empat hubungan, sepuluh evidence, batas empat halaman; TikTok 503, kasus PARTIAL. |
| User Scanner CLI | Profil GitHub dan tautan blog berhasil diimpor. TikTok gagal; kasus PARTIAL. Commit upstream dipin. |
| Nomor contoh | Satu record normalisasi format; tidak mengklaim akun WA, nama atau lokasi. |
| `example.com` / DNS, RDAP, CT | DONE, 22 evidence; DNS, registrasi domain dan CT diperiksa. |
| `1.1.1.1` / RDAP, ASN | DONE, 11 evidence; jaringan dan ASN 13335 diperiksa. |
| `test@example.com` / email DNS | DONE, 5 evidence; sintaks, MX, SPF diperiksa. Mailbox tidak diuji. |
| JPEG lokal terkontrol | DONE, 3 evidence; dimensi 137×83, SHA-256 dan EXIF Artist cocok. |

TikTok akun publik `tiktok` juga diuji terpisah dan tetap tidak menghasilkan profil yang dapat dibaca dari lingkungan ini. Dukungan live TikTok belum terbukti berhasil. Sherlock/Maigret/ExifTool memiliki hasil live v1.0.1 dalam dokumentasi historis; adapter regresinya tetap diuji pada v2, tetapi seluruh situs upstream tidak diuji ulang.

Lingkungan ini memerlukan proxy. Native transport memakai allowlist eksplisit; situs baru di luar daftar ditolak dengan PROXY_SCOPE. Hasil ini tidak menjamin ketersediaan sumber dari IP/VPS lain.

## Laporan dan terminal

Kasus URL nyata diekspor ke PDF, DOCX, JSON, CSV, HTML dan PNG. PDF akhir tujuh halaman; DOCX empat halaman. Semua halaman dirender dan diperiksa. Metadata PDF ditata per field, dengan pemenggalan record panjang. Tes regresi juga memeriksa Unicode, URL panjang, banyak evidence dan newline ekstrem.

Menu 40 kolom direkam melalui Linux PTY: startup → history → evidence → report → keluar. Demo menggunakan data sintetis berlabel. Lebar 32/40/60/80/120 kolom dan mode tanpa warna diuji. ASCII asli disimpan; versi ringkas dipilih saat lebar tidak cukup.

**Perangkat Termux fisik belum diuji.** Skrip menyediakan dependensi Android; keberhasilan kompilasi native tergantung arsitektur/paket Termux. Penggunaan Termux sebagai klien SSH ke Ubuntu mengikuti alur VPS.

## Bukti dan reproduksi

- [Log 107 tes](validation-v2/regression-tests.log)
- [Ringkasan Fusion live](validation-v2/fusion-live-summary.json)
- [Ringkasan modul lama live](validation-v2/legacy-live-summary.json)
- [Catatan instalasi](validation-v2/package-install.txt)

```bash
python3 -m unittest discover -s tests -v
python3 scripts/verify-fusion.py --out output/live-v2
python3 scripts/verify-live.py --only domain,ip,email,metadata --out output/live-legacy
```

Tambahkan `--transport proxy` hanya bila diperlukan. `--include-tools` menambahkan uji User Scanner yang sudah dipasang. Verifikasi live keluar dengan kode 2 jika ada sumber tidak tersedia; tidak dipoles menjadi “semua berhasil”. AI tidak diperlukan untuk ekspor ini dan ketersediaan providernya tidak diuji ulang pada v2.
