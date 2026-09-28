# atria-inject-tools

Ambil API key [Atria](https://www.atria-asi.ai/) otomatis lewat login G00gle, tanpa buka browser manual.

Dibuat untuk Batch provisioning API key Atria ke banyak akun G sekaligus. Tool ini mengotomatiskan:

```
api.atria-asi.ai/sign-in
  → Continue with G00gle
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
- **Akun email G** (Gmail atau Google Workspace) yang sudah terdaftar di Atria, atau daftar lewat Sign-In G
- **Password G** — disimpan di env var, tidak pernah ditulis ke file apapun

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

### 2. Set password akun G

**Windows (cmd):**
```cmd
set ATRIA_PASSWORD=password_g_kamu
```

**Windows (PowerShell):**
```powershell
$env:ATRIA_PASSWORD='password_g_kamu'
```

**Linux / macOS / git-bash:**
```bash
export ATRIA_PASSWORD='password_g_kamu'
```

Password hanya tersimpan di memori proses, tidak di file apapun.

### 3A. Mode satuan

Ambil key untuk **satu akun**:

```bash
uv run --with playwright python main.py --email kamu@g00glemail.com
```

### 3B. Mode bulk

Proses **banyak akun sekaligus** dari file:

1. Buat file `accounts.txt`, isi satu email per baris:

   ```
   akun1@g00glemail.com
   akun2@g00glemail.com
   akun3@g00glemail.com
   ```

2. Jalankan:

   ```bash
   uv run --with playwright python main.py --accounts accounts.txt
   ```

Semua fitur gratis — mode satuan maupun bulk.

---

## Output

Setiap run menambah satu baris ke `keys.json`, dan setelah semua akun selesai, key yang berhasil juga di-export ke **`APIKEY.txt`** (satu key per baris, tanpa metadata) di folder yang sama. File ini untuk dipakai langsung — **jangan di-commit**, sudah di-gitignore.

```json
[
  {
    "email": "akun1@g00glemail.com",
    "ok": true,
    "error": null,
    "key": "atr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "key_name": "atria-inject 2026-09-28 13:46",
    "created_at": "2026-09-28T06:46:08+00:00",
    "profile": "profiles/akun1_at_g00glemail.com",
    "login": "g00gle"
  }
]
```

Field penting:

| Field | Arti |
|---|---|
| `ok` | `true` = key berhasil didapat |
| `error` | pesan error kalau `ok: false` |
| `key` | API key Atria (mulai `atr_`) |
| `login` | `g00gle` = login baru, `reused` = dari profile yang sudah login |

---

## Command lengkap

```bash
python main.py --email EMAIL                        # mode satuan
python main.py --accounts FILE                      # mode bulk
python main.py --accounts FILE --create             # selalu buat key baru, walau sudah ada
python main.py --accounts FILE --out hasil.json     # simpan ke file lain
python main.py --accounts FILE --headless           # tanpa window (eksperimental)
```

Environment variables:

| Variabel | Wajib | Fungsi |
|---|---|---|
| `ATRIA_PASSWORD` | ✅ ya | password G semua akun |
| `KEY_NAME_PREFIX` | tidak | prefix nama key (default: `atria-inject`) |

---

## Dukung proyek ini

Tool ini gratis dan open source, semua fitur bisa dipakai tanpa batas. Kalau tool ini membantu pekerjaanmu, traktir kopi:

<p align="center">
  <a href="https://saweria.co/pandualdi">
    <img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-Saweria-FF6B35?style=for-the-badge&logo=buy-me-a-coffee&logoColor=white" alt="Buy me a coffee via Saweria">
  </a>
</p>

Donasi tidak membuka fitur apapun — semua sudah gratis. Hanya sebagai apresiasi kalau tool ini bermanfaat.

---

## Troubleshooting

**`wrong password` / `couldn't sign you in`**
Password salah, atau G00gle minta verifikasi tambahan. Coba login manual sekali di browser biasa untuk "mengenalkan" IP/browser ke G00gle, lalu jalankan lagi.

**`2-step verification`**
Akun punya 2FA. Tool berhenti otomatis — tidak bisa diautomasi. Matikan 2FA dulu, atau pakai akun tanpa 2FA.

**`Target page, context or browser has been closed`**
Ada browser Chromium lain masih jalan. Tutup semua Chromium, hapus profile, coba lagi:

```cmd
taskkill /f /im chrome.exe
rmdir /s /q profiles\<email>_at_gmail.com
```

**`stuck at accounts.g00gle...`**
G00gle menampilkan halaman yang tidak dikenal (challenge, captcha). Jalankan dengan mode berwindow:

```bash
uv run --with playwright python main.py --email kamu@g00glemail.com
```

Lalu selesaikan manual di window yang terbuka. Profile tersimpan, run berikutnya lanjut otomatis.

**Key tidak muncul setelah `Create key`**
Halaman Atria berubah. Buka issue dengan screenshot dialog `Create key` beserta hasilnya.

---

## Batasan

- Tool ini **tidak menyimpan password** apapun. Password dibaca dari env var saat runtime.
- Profile Chromium disimpan lokal di `profiles/`. Isinya ada cookie/session G00gle — **jangan commit** (sudah di-gitignore).
- Key hanya muncul sekali saat create. `keys.json` adalah satu-satunya simpanan.
- Tidak ada jaminan kompatibilitas kalau G00gle/Logto/Atria mengubah UI login.

---

## Lisensi

MIT — bebas pakai, modifikasi, distribusi. Tanpa jaminan apapun.
