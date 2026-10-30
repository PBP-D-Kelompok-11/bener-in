# ♻️ bener.in

## Application Overview

bener.in adalah platform web yang mempertemukan pemilik barang rusak dengan mitra reparasi, sehingga pengguna dapat menemukan mitra, mengajukan permintaan perbaikan, dan memantau proses reparasi sampai barang selesai diperbaiki. Mengusung tema Sustainable Living dengan sub-tema Waste Management, bener.in mendorong prinsip "repair before replace" yang mana memperbaiki barang yang masih punya masa guna alih-alih langsung membuang dan menggantinya, sehingga membantu mengurangi timbunan sampah rumah tangga.

## Fitur Utama

bener.in menyediakan beberapa fitur utama untuk mendukung proses reparasi barang:

- **Authentication & User Management:** Registrasi dan login untuk Customer dan Mitra Reparasi dengan hak akses berdasarkan role.
- **Mitra Management:** Pengelolaan informasi dan layanan mitra reparasi.
- **Repair Location & Discovery:** Pencarian lokasi reparasi menggunakan data geografis dari OpenStreetMap.
- **Repair Request & Tracking:** Customer dapat membuat dan mengelola permintaan reparasi. Mitra dapat menerima permintaan dan memperbarui status pengerjaan.
- **Review & Rating:** Customer dapat memberikan penilaian terhadap layanan reparasi setelah proses selesai.
- **Impact Tracker:** Menampilkan progres jumlah barang yang berhasil diperbaiki sebagai representasi kontribusi terhadap pengurangan sampah.

## Teknologi yang Digunakan

| Komponen | Teknologi |
|---|---|
| Programming Language | Python, JavaScript |
| Backend Framework | Django |
| Frontend | HTML, CSS, JavaScript |
| Database | PostgreSQL |
| Geographic Data | OpenStreetMap, Overpass API |
| Environment Configuration | python-dotenv |
| Version Control | Git, GitHub |
| Deployment | PWS CSUI |

Versi masing-masing dependency mengikuti konfigurasi pada `requirements.txt`.

## Setup dan Instalasi Lokal

Ikuti langkah berikut untuk menjalankan bener.in pada lingkungan pengembangan lokal.

### Prerequisites

Pastikan perangkat sudah memiliki:

- Python sesuai versi yang didukung proyek.
- pip.
- Git.
- PostgreSQL.
- Virtual environment.

### 1. Clone Repository

```bash
git clone https://github.com/PBP-D-Kelompok-11/bener-in.git
cd bener-in
```

### 2. Buat Virtual Environment

Windows:

```powershell
python -m venv env
env\Scripts\Activate.ps1
```

Linux / macOS:

```bash
python3 -m venv env
source env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment Variables

Buat file `.env` pada root project.

Isi file tersebut menggunakan konfigurasi yang sesuai dengan kebutuhan aplikasi dan variabel yang dibaca oleh `benerin/settings.py`.

Konfigurasi umumnya mencakup:

- Django secret key.
- Debug mode.
- Allowed hosts.
- Database name.
- Database username.
- Database password.
- Database host dan port.

Pastikan database PostgreSQL sudah tersedia dan kredensialnya sesuai dengan konfigurasi aplikasi.

Jangan mengunggah file `.env` atau informasi rahasia ke repository publik.

### 5. Jalankan Database Migration

```bash
python manage.py migrate
```

### 6. Buat Superuser (Opsional)

Untuk mengakses Django Admin:

```bash
python manage.py createsuperuser
```

### 7. Jalankan Development Server

```bash
python manage.py runserver
```

Buka aplikasi melalui:

http://127.0.0.1:8000/

## Menjalankan Testing

Untuk menjalankan automated tests:

```bash
python manage.py test
```

Untuk memeriksa konfigurasi Django:

```bash
python manage.py check
```

Untuk memeriksa konsistensi migration:

```bash
python manage.py makemigrations --check --dry-run
```

## Deployment

bener.in menggunakan PWS CSUI sebagai platform deployment.

Secara umum, proses deployment mencakup beberapa tahap:

1. Menyiapkan environment variables pada konfigurasi deployment.
2. Memastikan konfigurasi database production sudah tersedia.
3. Menginstal dependencies dari `requirements.txt`.
4. Menjalankan database migrations.
5. Mengumpulkan static files menggunakan Django `collectstatic`.
6. Memastikan aplikasi menggunakan konfigurasi production yang sesuai.
7. Melakukan deployment melalui Git remote yang disediakan PWS.

Contoh perintah deployment apabila remote PWS telah dikonfigurasi dengan nama `pws` dan branch deployment adalah `master`:

```bash
git push pws HEAD:master
```

Setelah proses push berhasil, periksa status build dan deployment melalui dashboard PWS.

Pastikan konfigurasi production menggunakan `DEBUG=False` dan pengaturan `ALLOWED_HOSTS` serta `CSRF_TRUSTED_ORIGINS` sesuai domain deployment.

## Public API yang akan digunakan

- **OpenStreetMap / Overpass API**: https://overpass-api.de/ || https://www.openstreetmap.org/

Digunakan untuk mendapatkan data geografis/lokasi yang relevan bagi fitur pencarian dan penemuan mitra reparasi (Modul Repair Location & Discovery). Data mitra bener.in sendiri tetap berasal dari database Django; OpenStreetMap digunakan sebagai sumber data eksternal untuk konteks lokasi.

## Daftar Modul dan Pembagian

- **Modul (A) = Autentikasi & Profil Pengguna** : Register/login untuk Customer dan Mitra, kelola data profil, role-based access. — [Hisyam]
- **Modul (B) = Repair Request & Tracking:** Customer dapat membuat, melihat, mengubah, dan membatalkan Repair Request. Mitra dapat menerima atau menolak permintaan serta memperbarui status pengerjaan melalui alur Pending → Accepted → In Progress → Completed, dengan status alternatif Rejected, Cancelled, dan Unable to Repair. — [Akmal]
- **Modul (C) = Mitra Repairer** : CRUD profil mitra reparasi (nama, layanan, lokasi, kontak). — [Hafizh]
- **Modul (D) = Repair Location & Discovery** : Pencarian dan penyimpanan mitra berdasarkan lokasi, terintegrasi dengan OpenStreetMap/Overpass API. — [Dave]
- **Modul (E) = Repair Review & Impact Tracker** : Customer memberi dan mengelola review/rating terhadap mitra setelah repair selesai, serta melihat dashboard "Impact Tracker" berupa progress bar/badge yang bertambah setiap kali sebuah repair berhasil diselesaikan, merepresentasikan jumlah barang yang "diselamatkan" dari sampah. — [Aufa]

## Role Pengguna

- **Customer**: Mencari mitra reparasi, melihat profil dan lokasi mitra, mengajukan Repair Request, memantau status reparasi, memberi review setelah repair selesai.
- **Mitra Reparasi**: Mendaftar sebagai mitra, membuat profil (lokasi, kontak, layanan), menerima Repair Request, memperbarui status reparasi.

## AI Disclosure

Dalam proses pengembangan bener.in, tim menggunakan AI sebagai alat bantu untuk mendukung proses pembelajaran dan pengembangan aplikasi.

### AI Tools

- **ChatGPT:** Membantu memahami konsep teknis, menganalisis error, menyusun solusi terhadap permasalahan implementasi, serta memberikan masukan terhadap dokumentasi dan desain aplikasi.
- **OpenAI Codex/Claude Code/Antigravity:** Membantu menganalisis struktur repository, memberikan rekomendasi implementasi kode, membantu debugging, Membantu percepatan proses develop produk, serta melakukan pemeriksaan terhadap perubahan kode.


### Areas of AI Assistance

Penggunaan AI mencakup beberapa aktivitas:

1. **Code Understanding:** Membantu memahami struktur proyek, alur aplikasi, dan implementasi Django.
2. **Debugging:** Membantu menganalisis error dan memberikan alternatif solusi.
3. **Code Development:** Memberikan saran implementasi dan perbaikan kode pada fitur backend maupun frontend, serta mempercepat proses develop produk.
4. **Testing:** Membantu menyusun skenario pengujian dan mengidentifikasi potensi edge cases.
5. **UI/UX Development:** Memberikan masukan mengenai layout, responsive design, dan interaksi antarmuka.

### Human Verification and Responsibility

AI digunakan sebagai alat bantu, bukan sebagai pengganti proses pengambilan keputusan dan pemahaman anggota tim.
Setiap rekomendasi atau kode yang dihasilkan dengan bantuan AI perlu ditinjau dan disesuaikan dengan kebutuhan proyek. Tim bertanggung jawab terhadap keputusan implementasi, integrasi antar-modul, serta pengujian aplikasi.

Pengujian dilakukan melalui automated tests dan pemeriksaan manual untuk memastikan implementasi sesuai dengan kebutuhan proyek.

## Anggota Kelompok

Karya Kelompok 11 PBP-D:
- 2506548295 - MUHAMMAD AKMAL HAQQANI
- 2506656500 - AUFA NURCAHYO
- 2506614763 - HISYAM PRASETYO
- 2506656785 - HAFIZH ZUHDI HARTANTO
- 2506656601 - DAVE WESLEY TJOENG


Figma Design System : https://www.figma.com/design/SlrTDgk61cUD1ifEvUEPfL/bener.in-%7C-Web-Design-System?node-id=44-4102&t=mHMXzn0DzWxaxftT-1
