
```md
# Prod Schedule Gereja

Project ini digunakan untuk:
- 🔬 **Development & eksplorasi data** menggunakan **Jupyter Notebook**
- ⚙️ **Menjalankan script Python** (server-like) menggunakan **Docker**, menyerupai environment Linux + venv

Docker dipakai untuk memastikan environment **konsisten** antara Windows, WSL, dan Linux server.

---

## 🧱 Teknologi
- Python 3.11
- Docker & Docker Compose
- Jupyter Notebook
- Google Sheets API (gspread)
- Pandas

---

## 📁 Struktur Project (ringkas)
```

.
├── helpers/                 # helper modules (connection, auth, dll)
├── scripts/
│   └── generate_organist_schedule.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yaml
├── README.md

````

---

## 🚀 Cara Menjalankan

### 1️⃣ Build Docker Image (sekali atau saat ada perubahan dependency)
```bash
docker compose build
````

---

## 🧪 Mode 1 — Jupyter Notebook (Development)

Digunakan untuk:

* eksplorasi data
* testing logic
* debugging manual

### Jalankan:

```bash
docker compose up jupyter
```

### Akses di browser:

```
http://localhost:8889
```

Gunakan token sesuai environment:

```env
JUPYTER_TOKEN=myfixedtoken123
```

📌 Folder project di host akan termount ke `/app` di container.

---

## ⚙️ Mode 2 — Run Script (Server-like / Production Style)

Digunakan untuk:

* menjalankan script seperti di Linux server
* simulasi `venv + python script.py`

### Jalankan:

```bash
docker compose run --rm runner
```

Ini setara dengan:

```bash
source venv/bin/activate
python scripts/generate_organist_schedule.py
```

📌 Tidak menggunakan `venv` di Docker
📌 Dependency diambil dari `requirements.txt`
📌 Environment Linux murni

---


## 🔁 Rebuild Jika Ada Perubahan

Jika mengubah:

* `requirements.txt`
* `Dockerfile`

Lakukan:

```bash
docker compose build
```

---

## 🧹 Stop Container

```bash
docker compose down
```

---

## 🎯 Kenapa Pakai Docker?

* Konsisten dengan Linux server
* Tidak tergantung OS host (Windows / WSL / Linux)
* Tidak ada konflik Python / venv
* Mudah dipindahkan ke CI / production

---

## 👤 Author

Vincent