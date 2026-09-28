# atria-inject-tools

Ambil API key [Atria](https://www.atria-asi.ai/) otomatis lewat login Google, tanpa buka browser manual.

Dibuat untuk Batch provisioning API key Atria ke banyak akun Gmail sekaligus. Tool ini mengotomatiskan:

```
api.atria-asi.ai/sign-in
  → Continue with Google
  → isi email → Enter
  → isi password → Enter
  → consent screen → Continue
  → kembali ke Atria, sudah login
  → /console/keys → Create key → simpan key-nya
```

Setiap akun dapat profile Chromium sendiri (`profiles/<email>`), jadi setelah login sekali, run berikutnya tidak perlu login lagi.

---

## Persyaratan

- **Python 3.10+** — cek: `python --version`
- **uv** — installer: https://docs.astral.sh/uv/ (Windows: `irm https://astral.sh/uv/install.ps1 | iex`)
- **Akun Gmail** yang sudah terdaftar di Atria (atau bisa daftar lewat Google Sign-In)
- **Password Gmail** — disimpan di env var, tidak pernah ditulis ke file apapun

> **Catatan:** akun dengan **2FA/verifikasi 2 langkah** tidak bisa diautomasi. Tool akan berhenti dan memberitahu. Matikan 2FA dulu, atau gunakan akun tanpa 2FA.

---

## Cara pakai

### 1. Siapkan environment

```bash
cd atria-inject-tools

# Install playwright (sekali saja)
uv run --with playwright python -c "from playwright.sync_api import sync_playwright; sync_playwright().start().chromium.launch().close()"

# Atau install dependency manual
uv pip install -r requirements.txt
```

### 2. Set password Gmail

**Windows (cmd):**
```cmd
set ATRIA_PASSWORD=password_gmail_kamu
```

**Windows (PowerShell):**
```powershell
$env:ATRIA_PASSWORD='password_gmail_kamu'
```

**Linux / macOS / git-bash:**
```bash
export ATRIA_PASSWORD='password_gmail_kamu'
```

Password hanya tersimpan di memori proses, tidak di file apapun.

### 3A. Mode satuan (gratis untuk semua)

Ambil key untuk **satu akun**:

```bash
uv run --with playwright python main.py --email kamu@gmail.com
```

### 3B. Mode bulk (butuh password pembuka)

Proses **banyak akun sekaligus** dari file:

1. Buat file `accounts.txt`, isi satu email per baris:

   ```
   akun1@gmail.com
   akun2@gmail.com
   akun3@gmail.com
   ```

2. Set password pembuka:

   ```cmd
   set ATRIA_UNLOCK=kata_pembuka
   ```

3. Jalankan:

   ```bash
   uv run --with playwright python main.py --accounts accounts.txt
   ```

**Mode bulk memerlukan password pembuka** sebagai bentuk dukungannya ke proyek ini.

Cara mendapatkannya:

1. Donasi seikhlasnya di **[https://saweria.co/pandualdi](https://saweria.co/pandualdi)**
2. Hubungi Telegram **[@cybernet3329](https://t.me/cybernet3329)** dengan bukti donasi
3. Kamu akan dapat password pembuka untuk mode bulk

---

## Output

Setiap run menambah satu baris ke `keys.json`:

```json
[
  {
    "email": "akun1@gmail.com",
    "ok": true,
    "error": null,
    "key": "atr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "key_name": "atria-inject 2026-09-28 13:46",
    "created_at": "2026-09-28T06:46:08+00:00",
    "profile": "profiles/akun1_at_gmail.com",
    "login": "google"
  }
]
```

Field penting:

| Field | Arti |
|---|---|
| `ok` | `true` = key berhasil didapat |
| `error` | pesan error kalau `ok: false` |
| `key` | API key Atria (mulai `atr_`) |
| `login` | `google` = login baru, `reused` = dari profile yang sudah login |

---

## Command lengkap

```bash
python main.py --email EMAIL                        # mode satuan
python main.py --accounts FILE                      # mode bulk (perlu password pembuka)
python main.py --accounts FILE --create             # selalu buat key baru, walau sudah ada
python main.py --accounts FILE --out hasil.json     # simpan ke file lain
python main.py --accounts FILE --headless           # tanpa window (eksperimental)
```

Environment variables:

| Variabel | Wajib | Fungsi |
|---|---|---|
| `ATRIA_PASSWORD` | ✅ ya | password Gmail semua akun |
| `ATRIA_UNLOCK` | bulk mode | password pembuka untuk `--accounts` |
| `KEY_NAME_PREFIX` | tidak | prefix nama key (default: `atria-inject`) |

---

## Dukung proyek ini

Tool ini gratis dan open source. Kalau membantu pekerjaanmu, dukung via Saweria:

**[https://saweria.co/pandualdi](https://saweria.co/pandualdi)**

Sesudah donasi, hubungi Telegram **[@cybernet3329](https://t.me/cybernet3329)** untuk dapat **password pembuka** mode bulk. Mode satuan selalu gratis, tanpa donasi.

---

## Troubleshooting

**`wrong password` / `couldn't sign you in`**
Password salah, atau Google minta verifikasi tambahan. Coba login manual sekali di browser biasa untuk "mengenalkan" IP/browser ke Google, lalu jalankan lagi.

**`2-step verification`**
Akun punya 2FA. Tool berhenti otomatis — tidak bisa diautomasi. Matikan 2FA dulu, atau pakai akun tanpa 2FA.

**`Target page, context or browser has been closed`**
Ada browser Chromium lain masih jalan. Tutup semua Chromium, hapus profile, coba lagi:

```cmd
taskkill /f /im chrome.exe
rmdir /s /q profiles\<email>_at_gmail.com
```

**`stuck at accounts.google...`**
Google menampilkan halaman yang tidak dikenal (challenge, captcha). Jalankan dengan mode berwindow:

```bash
uv run --with playwright python main.py --email kamu@gmail.com
```

Lalu selesaikan manual di window yang terbuka. Profile tersimpan, run berikutnya lanjut otomatis.

**Key tidak muncul setelah `Create key`**
Halaman Atria berubah. Buka issue dengan screenshot dialog `Create key` beserta hasilnya.

---

## Batasan

- Tool ini **tidak menyimpan password** apapun. Password dibaca dari env var saat runtime.
- Profile Chromium disimpan lokal di `profiles/`. Isinya ada cookie/session Google — **jangan commit** (sudah di-gitignore).
- Key hanya muncul sekali saat create. `keys.json` adalah satu-satunya simpanan.
- Tidak ada jaminan kompatibilitas kalau Google/Logto/Atria mengubah UI login.

---

## Lisensi

MIT — bebas pakai, modifikasi, distribusi. Tanpa jaminan apapun.
