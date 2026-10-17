# Verifikasi nyata — OsintCLI 1.0.1

**Kesimpulan: fungsi inti menghasilkan data daring dan laporan nyata. Belum semua sumber/lingkungan dapat dinyatakan berfungsi penuh.** Pengujian ini dilakukan setelah pemilik proyek meminta pembuktian di luar tes fixture. Bukti mentah, hasil JSON/CSV, PDF, log CLI, dan ringkasan mesin ada di [live-verification/](live-verification/).

Pengujian pada 17 Oktober 2026 WIB, Linux Python 3.12.14, menggunakan subprocess CLI asli. Setiap scan menulis kasus/evidence ke SQLite, lalu perintah `report` membaca kembali evidence dan membuat ekspor. **Tidak ada mock transport, client injection, atau demo seed untuk data daring.** Gambar metadata adalah file kontrol lokal yang sengaja dibuat dan diberi label; hash/dimensi/Artist-nya dibandingkan dengan nilai yang diketahui.

Jaringan pengujian mewajibkan proxy. Versi 1.0.0 hanya mempunyai koneksi langsung dan karena itu gagal pada DNS lingkungan ini. Perbaikan 1.0.1 menyediakan transport proxy eksplisit dengan batas hostname yang disetujui. Batas ini dijelaskan dalam [PROXY.md](PROXY.md). Tidak ada penonaktifan TLS validation atau perubahan gateway jaringan.

| Pengujian nyata | Hasil terakhir | Bukti terukur |
|---|---|---|
| Domain `example.com`, DNS/RDAP/CT | **LULUS**, case DONE, 22 evidence | 9 observasi DNS, 6 RDAP, 7 nama CT; ldhName cocok `EXAMPLE.COM` |
| IP `1.1.1.1`, RDAP/ASN | **LULUS**, case DONE, 11 evidence | Network RDAP tersedia; jawaban Team Cymru berisi **ASN 13335**, prefix `1.1.1.0/24` |
| Email `test@example.com` | **LULUS untuk sintaks/DNS**, 5 evidence | MX `0 .`, SPF `v=spf1 -all`, DMARC `p=reject`; ini domain yang tidak menerima email, bukan klaim mailbox ada |
| Website `example.com` | **LULUS**, 3 observasi | Halaman utama HTTP 200 dan HTML Example Domain; robots/sitemap HTTP 404 dicatat sebagai observasi, bukan file ditemukan |
| GitHub `octocat` | **LULUS dengan gap sumber lain** | API GitHub mengembalikan login `octocat`, ID **583231**, URL profil yang cocok |
| Kontrol negatif username acak | **LULUS untuk GitHub/GitLab** | GitHub API HTTP 404, GitLab API daftar kosong; tidak ada kandidat profil dari kedua sumber itu |
| Reddit API | **BELUM TERSEDIA** | HTTP 403 pada kontrol positif/negatif; FAILED_SOURCE dipertahankan, bukan dianggap akun tidak ada |
| Metadata bawaan | **LULUS**, 3 observasi | JPEG **137 × 83**, SHA-256 persis cocok, Artist `OSINTCLI controlled metadata test` |
| Sherlock terintegrasi | **LULUS alur**, 3 catatan | Proses upstream nyata; CSV berisi GitHub/Reddit Claimed dan GitLab Available; kandidat GitHub cocok dengan pengecekan API terpisah |
| Maigret terintegrasi | **LULUS dengan gap**, 4 catatan | GitHub/Gist kandidat, GitLab hasil negatif belum terverifikasi, Reddit sumber gagal; case PARTIAL |
| ExifTool terintegrasi | **LULUS**, 24 metadata | Dimensi dan Artist cocok dengan file kontrol; seluruhnya disimpan/di-export |
| PDF dari evidence domain nyata | **LULUS**, 9 halaman | Bukan PDF demo. Cover menyebut example.com; jumlah 22, sumber, tabel, charts, case ID/digest konsisten |
| JSON/CSV/HTML/PNG | **LULUS** | Dibuat dari scan domain/IP/file kontrol yang sama; semua command export exit 0 |
| Paket terinstal, dijalankan dari luar repo | **LULUS** | Versi 1.0.1, DNS example.com menghasilkan 9 observasi; PDF/JSON/CSV berhasil; scan/report exit 0 |
| Nexray GET `text=Hai` | **GAGAL / PROVIDER UNAVAILABLE** | HTTP 200 tetapi Content-Type text/html, isi “Site Unavailable”; tidak ada klaim AI live sukses |
| Sertifikat TLS origin langsung | **BELUM TERVERIFIKASI** | Jaringan langsung dibatasi. Mode proxy mengembalikan DIRECT_REQUIRED agar sertifikat proxy tidak dianggap sertifikat origin |
| Android/Termux fisik | **BELUM DIUJI** | Tidak ada klaim penerimaan perangkat Android |
| Regresi setelah perbaikan | **90 tes LULUS** | Termasuk proxy redirect/allowlist, sanitasi rahasia, structured profile API, negative control, dan galat interpreter tool |

## Masalah nyata yang ditemukan dan diperbaiki

1. **Transport tidak cocok dengan lingkungan proxy.** Sebelumnya kegagalan DNS menghentikan koleksi inti. Kini perintah scan yang sama dapat mengambil sumber publik melalui proxy yang sudah dikonfigurasi secara eksplisit, menulis evidence, dan membuat laporan.
2. **HTTP 200 bukan bukti halaman akun.** Percobaan awal nama acak pada Reddit menunjukkan halaman HTTP 200 bisa menjadi kandidat palsu. Pemeriksaan bawaan kini menggunakan API terstruktur GitHub/GitLab/Reddit dan memerlukan identifier yang cocok. Reddit API yang menolak akses ditandai gagal sumber. Kontrol negatif terbaru tidak melaporkan profil GitHub/GitLab untuk nama acak tersebut.
3. **Output Sherlock dapat menyembunyikan hasil non-claimed.** Adapter sekarang memakai `--print-all`, sehingga negatif/galat sumber ikut disimpan. Timeout mengambil pengaturan aplikasi; pada tes mentah, GitHub membutuhkan sekitar 16,7 detik. Ini menjelaskan hasil kosong/parsial saat batas lama 12 detik dipakai.
4. **Virtual environment tool di workspace pengujian kehilangan interpreter setelah pemulihan lingkungan.** Proses awal gagal diluncurkan. Environment pengujian dibuat ulang, lalu tool benar-benar dijalankan. Adapter sekarang memberi kode TOOL_LAUNCH dengan instruksi perbaikan bila executable/interpreter hilang. Source ZIP tidak menyertakan venv atau executable upstream yang rusak.

Catatan awal yang gagal tetap disimpan di `live-verification/attempts/`; `summary.json` menunjukkan run terakhir yang menjadi dasar tiap hasil. Perbaikan tidak menghapus kegagalan dari riwayat lalu mengklaim seluruh proses selalu berhasil.

## Menjalankan ulang

```bash
# Jaringan normal: koneksi langsung
python3 scripts/verify-live.py --out ./hasil-uji --include-tools

# Hanya jika jaringan memang memakai proxy sah yang sudah dikonfigurasi:
python3 scripts/verify-live.py --out ./hasil-uji --transport proxy --include-tools
```

Script memakai target publik terbatas: example.com, IP DNS publik Cloudflare, akun contoh GitHub octocat, nama kontrol acak, dan file metadata lokal. `--only domain,ip` membatasi subset. Tidak ada scan aktif/rekursif, probing SMTP, atau pengiriman evidence ke AI; smoke AI hanya greeting `Hai`.

Exit **2** berarti ada sumber/bagian yang gagal atau belum tersedia, termasuk provider opsional; baca summary per modul. Tidak ada status “semua berfungsi” hanya karena file laporan dibuat. Pada jaringan proxy, origin TLS memang tidak dapat dicertifikasi oleh pengujian ini. Repeat run dapat menghasilkan jumlah berbeda karena sumber publik mutable/rate-limited.

## Batas kesimpulan

Bukti ini menunjukkan aplikasi mengoleksi dan mengekspor data nyata, bukan UI dengan hasil yang dibuat-buat. Bukti ini **tidak** membuktikan kebenaran semua hasil upstream, akses ke semua platform, identitas pemilik akun, atau kompatibilitas semua perangkat Android. Sherlock/Maigret tetap sumber kandidat yang memerlukan review. Nexray saat ini tidak dapat dipakai dari lingkungan pengujian; PDF lokal tidak bergantung padanya.
