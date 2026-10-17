<p align="center"><img src="osintcli/assets/banner-readme.png" alt="OSINTCLI — by R_HMT" width="100%"></p>

# OsintCLI

Toolkit OSINT terminal **by R_HMT**. Satu menu untuk sumber publik, engine username open-source, metadata lokal, evidence bersumber, riwayat SQLite, dan laporan yang bisa dibuat tanpa AI.

**Repository tujuan:** `rahmat-369/OsintCLI`. Paket ini siap diunggah; repository belum dibuat/dipush oleh pembuat paket.

## Mulai dalam tiga langkah

```bash
git clone https://github.com/rahmat-369/OsintCLI.git
cd OsintCLI
bash install.sh
bash start.sh
```

URL clone berlaku **setelah Anda membuat dan mengisi repository tersebut**. Dari ZIP: ekstrak, masuk ke folder `OsintCLI`, lalu jalankan dua perintah terakhir. Installer membuat virtual environment dan database secara otomatis. Tidak perlu akun database, VPS, API key, atau root.

**Termux:** pasang `git` dan `python` terlebih dahulu (`pkg update && pkg install git python`). Jalankan proyek di direktori home Termux, bukan storage bersama Android. **Linux:** Python 3.11+ dan modul `venv` diperlukan. Pada Debian/Ubuntu, pasang `python3-venv` bila belum ada. Tidak ada script download-and-execute melalui pipe.

Perintah `osintcli` terpasang otomatis di PATH Termux. Linux: `export PATH="$HOME/.local/bin:$PATH"`; `bash start.sh` selalu bisa dipakai dari folder repo. `bash install.sh --core-only` memasang CLI dengan standard library saja; PDF/PNG dan parsing image/PDF memerlukan instalasi penuh.

## Gabungkan tools open-source

Instal hanya engine yang ingin dipakai; masing-masing dipisahkan dalam virtual environment untuk menghindari benturan dependensi.

```bash
bash scripts/install-tools.sh sherlock
bash scripts/install-tools.sh maigret
bash scripts/install-tools.sh exiftool
osintcli doctor
```

Pada Linux Debian/Ubuntu, perintah ExifTool menampilkan instruksi `sudo apt-get install libimage-exiftool-perl` agar pemasangan paket sistem tetap eksplisit. Pada Termux, script memakai `pkg install exiftool`. Untuk format yang didukung, metadata bawaan tetap berfungsi tanpa ExifTool.

Sherlock dan Maigret dihubungkan sebagai **engine nyata**, hasil CSV dinormalisasi, disimpan bersama provenance, dan masuk ke laporan yang sama. Upstream tidak diganti mereknya atau diklaim sebagai karya R_HMT. Setiap kasus username memilih satu engine agar tidak mengirim kueri duplikat. Default dibatasi GitHub/GitLab/Reddit; database Maigret yang diaudit juga menyertakan GitHub Gist sebagai sumber turunan GitHub. Sherlock dapat melewati situs yang dikecualikan upstream. Tidak ada scan seluruh daftar situs secara otomatis.

## Menu

```text
[01] Auto Investigation
[02] Username Intelligence
[03] Domain / Website
[04] IP / Network
[05] Email Intelligence
[06] Metadata Forensics
[07] Evidence & History
[08] AI Narration (optional)
[09] Generate Report
[10] Settings / Modules
[00] Exit
```

Menu berbahasa Indonesia, nomor + Enter, satu kolom, dukungan 32/40/60/80/120 kolom, ikon ANSI RGB/256 warna dan fallback teks. `NO_COLOR=1 osintcli` mematikan warna. Semua teks sumber dibersihkan dari kontrol terminal.

## Fitur dan status

| Bagian | Perilaku implementasi | Validasi rilis |
|---|---|---|
| DNS/domain | A, AAAA, MX, NS, TXT lewat Google Public DNS; RDAP; CT maksimal 100 nama | Parser/galat diuji; sumber publik diprobe HTTP |
| IP/ASN | RDAP publik + Team Cymru lewat DNS TXT | Fixture kontrak; koneksi langsung dibatasi lingkungan build |
| Website | Header, robots.txt, sitemap.xml, TLS; hanya ketika dipilih | Kontrak HTTP, redirect, TLS/timeout diuji |
| Username bawaan | Tiga URL publik; HTTP 200 hanya kandidat | Fixture dan alur penanganan galat |
| Sherlock / Maigret | Proses terpisah, pin commit, hasil CSV masuk evidence | Instalasi Linux dan output live diuji |
| Metadata | SHA-256, image/EXIF, PDF, OOXML; ExifTool eksternal | File lokal dan ExifTool nyata diuji |
| Kasus/job | SQLite otomatis, deduplikasi per sumber, cancel, resume, hapus | Pengujian otomatis |
| Laporan | PDF, JSON, CSV aman formula, HTML escaped, PNG chart | 0/106 record; font Arab/Latin; render PDF diperiksa |
| AI Nexray | Preview, consent, batas URL, schema parser, draft/review | Tes positif/negatif; endpoint live memberi HTML “Site Unavailable” |
| Android Termux | Installer tanpa root, library ringan, export Download berizin | **Belum diuji pada perangkat Android fisik** |

Status `VERIFIED` berarti **observasi cocok dengan respons sumber**, bukan verifikasi seseorang, kepemilikan akun, atau kebenaran isi sumber. `CANDIDATE` perlu pemeriksaan manual. `FAILED_SOURCE` menunjukkan keterbatasan cakupan. Nol hasil bukan bukti target tidak ada.

## Contoh terminal

```bash
# Scope preview tanpa koneksi
osintcli scan example.com

# Jalankan scope yang Anda izinkan
osintcli scan example.com --yes
osintcli scan example.com --modules dns,rdap,web,tls --yes
osintcli scan 1.1.1.1 --yes
osintcli scan user@example.com --kind email --yes
osintcli scan octocat --kind username --modules sherlock --yes
osintcli scan octocat --kind username --modules maigret --yes
osintcli scan ./foto.jpg --kind metadata --modules metadata,exiftool --yes

osintcli history
osintcli show CASE_ID
osintcli resume CASE_ID --yes
osintcli report CASE_ID --out ./hasil
osintcli report CASE_ID --formats pdf,json,csv --summary
osintcli delete CASE_ID --yes

# Demo offline berlabel jelas, bukan temuan internet
osintcli demo --count 12 --report --out ./demo
```

Untuk username yang mengandung titik, gunakan `--kind username`; deteksi otomatis memperlakukan teks dengan titik sebagai domain. Input URL dinormalisasi ke hostname; jalur URL bukan scope crawl. Exit code: `0` selesai/preview, `2` galat atau hasil parsial, `130` pembatalan di luar job manager. Saat scan dibatalkan, kasus disimpan `CANCELLED` dan kode keluar `2`.

`Ctrl+C` meminta pembatalan kooperatif; request yang sedang menunggu respons bisa selesai sampai timeout. Proses tool eksternal dihentikan sebagai satu process group. `resume` mengulang adapter yang belum selesai; evidence lama tetap tersimpan dan duplikat identik tidak ditambahkan. Tidak ada recursive expansion atau brute force.

## AI opsional

```bash
osintcli ai CASE_ID                         # preview saja
osintcli ai CASE_ID --limit 1 --send --yes  # consent per pengiriman
osintcli review CASE_ID                    # baca draft
osintcli review CASE_ID --approve          # setelah verifikasi manual
osintcli report CASE_ID --include-ai
```

Preset: `https://api.nexray.eu.cc/ai/claude`, GET parameter `text`, field respons `result`, sukses `status=true`. **Tidak membutuhkan API key yang dibuat-buat.** Pada pengujian rilis, endpoint mengembalikan HTML “Site Unavailable”; aplikasi menolaknya. PDF tetap bisa dibuat tanpa AI. Ketersediaan provider tidak dapat dijamin oleh kode ini.

GET menempatkan prompt pada URL/log provider. Default hanya mengirim satu evidence kecil yang telah difilter; profil, email, file mentah, dan EXIF tidak dikirim otomatis. `--include-sensitive` adalah opt-in tambahan, dan masih membutuhkan preview/consent. Prompt terlalu panjang ditolak sebelum pengiriman tanpa pemotongan diam-diam. Angka tambahan yang tidak ada di prompt ditolak, tetapi pemeriksaan itu bukan jaminan bahwa narasi benar: selalu lakukan review manual. Perubahan dataset membatalkan penggunaan narasi reviewed yang lama.

```bash
osintcli config custom_instructions 'Tulis ringkas. Bedakan observasi dan keterbatasan.'
osintcli config timeout_seconds 20
osintcli config endpoint 'https://provider-anda.example/endpoint'
osintcli config method POST
```

POST tersedia sebagai transport JSON untuk provider lain; **dukungan POST Nexray tidak diklaim**. Lihat [konfigurasi provider](docs/AI.md). Bukti dikirim hanya melalui aksi AI eksplisit, tidak saat scan/report.

## Hasil dan privasi

- Database: `~/.local/share/osintcli/osintcli.db`.
- Reports: `~/.local/share/osintcli/reports/CASE_ID/`.
- Config: `~/.config/osintcli/config.toml`.
- Optional secrets: `~/.config/osintcli/secrets.toml`, mode `0600`.
- Data/config bisa dipindahkan dengan `OSINTCLI_DATA_DIR` dan `OSINTCLI_CONFIG_DIR`.

Android: jalankan `termux-setup-storage`, beri izin, lalu pilih `android` pada folder export di menu laporan. Aplikasi tidak meminta storage untuk sekadar scan. Hapus kasus juga menghapus laporan canonical lokal, tetapi tidak salinan yang sudah diekspor. Database lokal tidak dienkripsi; lindungi perangkat Anda.

## Bukti pengujian dan demo

[Catatan pengujian](docs/TEST-REPORT.md) • [Batas yang diketahui](docs/LIMITATIONS.md) • [Arsitektur](docs/ARCHITECTURE.md) • [Audit upstream](THIRD_PARTY_NOTICES.md) • [Laporan contoh](docs/samples/)

![Actual 40-column Linux CLI recording, offline fixture](docs/screenshots/terminal-demo.gif)

GIF di atas dirender dari rekaman output aplikasi yang benar-benar dijalankan pada pseudo-terminal Linux 40 kolom. **Bukan screenshot Android/Termux, dan data berlabel fixture.** File `.cast` dan teks rekamannya tersedia di folder yang sama.

```bash
python3 -m unittest discover -s tests -v
python3 scripts/make-ansi.py
```

CI GitHub menjalankan tes pada Python 3.11–3.13; konfigurasi CI disertakan, tetapi hasil remote baru ada setelah repository dipush. Versi yang diuji langsung saat paket dibangun: Linux Python 3.12.14.

## Push ke GitHub

Buat repo kosong `rahmat-369/OsintCLI` (tanpa menambahkan README lain), lalu dari folder hasil ekstraksi:

```bash
git init -b main
git add .
git commit -m "Build OsintCLI v1.0.0"
git remote add origin https://github.com/rahmat-369/OsintCLI.git
git push -u origin main
```

Gunakan login GitHub biasa/credential manager saat diminta. Jangan menaruh token pada kode, URL remote, README, atau chat.

## Kredit

Dikembangkan dan dikurasi untuk **R_HMT** — [GitHub](https://github.com/rahmat-369) · [Website](https://rhmt.biz.id).

Kode orchestration OsintCLI: MIT. Sherlock, Maigret, ExifTool, pustaka Python, dan font mempertahankan lisensi masing-masing. Detail pin, lisensi, batas reuse, dan atribusi terdapat di [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Banner adalah aset referensi yang disediakan pemilik proyek; ikon globe/lens dibuat khusus sebagai vector source yang dapat diedit. Tidak ada klaim afiliasi resmi dengan proyek upstream.
