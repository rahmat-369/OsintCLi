# Konfigurasi AI HTTP

Default `config.toml` otomatis dibuat. Key yang didukung:

| Key | Default / fungsi |
|---|---|
| endpoint | https://api.nexray.eu.cc/ai/claude |
| method | GET; POST untuk provider JSON yang Anda uji sendiri |
| input_parameter | text |
| response_text_path | result; mendukung dotted dictionary path |
| success_path | status; nilai harus boolean true; kosong untuk provider tanpa field sukses |
| ai_timeout_seconds | 25 |
| max_url_length | 1800; terlalu panjang ditolak sebelum request |
| custom_instructions | Instruksi pengguna, terpisah dari evidence |
| provider | Label tersimpan dalam riwayat narasi |

GET memakai percent encoding. POST memakai objek JSON `{input_parameter: prompt}`. Tidak ada redirect AI dan retry otomatis (mencegah pengiriman ganda). Respons maksimal 32 KB; teks maksimal 12.000 karakter, hanya JSON, bukan HTML/empty. Jika `result` memuat JSON teks, harus mempunyai summary, key_findings, limitations, conclusion; nilainya string atau daftar string. Freeform diperlakukan sebagai draft yang wajib direview.

Header opsional di `~/.config/osintcli/secrets.toml`:

```toml
[headers]
Authorization = "Bearer ISI_SECARA_LOKAL"
```

`chmod 600 ~/.config/osintcli/secrets.toml`. Jangan commit file ini. Tidak diperlukan untuk preset Nexray. Jangan masukkan secrets pada config umum/URL.

Pembatasan default subset: DNS, status DNS, ASN, CT, TLS, RDAP, source observation. Email pattern disamarkan; metadata/profil tidak dimasukkan kecuali opt-in tambahan. Evidence >500 karakter ditolak, tidak dipotong diam-diam. Beberapa pola prompt injection eksplisit ditolak; ini bukan perlindungan sempurna terhadap prompt injection atau hallucination. Nilai `status=VERIFIED` dalam evidence bukan jaminan isi sumber benar.

Ketersediaan live pada 17 Oktober 2026 WIB: GET `text=Hai` memberikan HTTP 200 tetapi `text/html`, halaman “Site Unavailable”. Tidak ada bukti respons narasi berhasil dari endpoint saat paket ini dibangun. Adapter diuji menggunakan fixture valid dan berbagai kegagalan. Laporan tidak bergantung pada provider.
