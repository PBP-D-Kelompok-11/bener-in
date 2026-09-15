# ♻️ bener.in

## Application Overview

bener.in adalah platform web yang mempertemukan pemilik barang rusak dengan mitra reparasi, sehingga pengguna dapat menemukan mitra, mengajukan permintaan perbaikan, dan memantau proses reparasi sampai barang selesai diperbaiki. Mengusung tema Sustainable Living dengan sub-tema Waste Management, bener.in mendorong prinsip "repair before replace" yang mana memperbaiki barang yang masih punya masa guna alih-alih langsung membuang dan menggantinya, sehingga membantu mengurangi timbunan sampah rumah tangga.

## Public API yang akan digunakan

- **OpenStreetMap / Overpass API**: https://overpass-api.de/ || https://www.openstreetmap.org/

Digunakan untuk mendapatkan data geografis/lokasi yang relevan bagi fitur pencarian dan penemuan mitra reparasi (Modul Repair Location & Discovery). Data mitra bener.in sendiri tetap berasal dari database Django; OpenStreetMap digunakan sebagai sumber data eksternal untuk konteks lokasi.

## Daftar Modul dan Pembagian

- **Modul (A) = Autentikasi & Profil Pengguna** : Register/login untuk Customer dan Mitra, kelola data profil, role-based access. — [Hisyam]
- **Modul (B) = Repair Request & Tracking** : Customer membuat, melihat, mengubah, dan menghapus Repair Request; status reparasi diperbarui mitra (Pending → Accepted → In Repair → Completed). — [Akmal]
- **Modul (C) = Mitra Repairer** : CRUD profil mitra reparasi (nama, layanan, lokasi, kontak). — [Hafizh]
- **Modul (D) = Repair Location & Discovery** : Pencarian dan penyimpanan mitra berdasarkan lokasi, terintegrasi dengan OpenStreetMap/Overpass API. — [Dave]
- **Modul (E) = Repair Review & Impact Tracker** : Customer memberi dan mengelola review/rating terhadap mitra setelah repair selesai, serta melihat dashboard "Impact Tracker" berupa progress bar/badge yang bertambah setiap kali sebuah repair berhasil diselesaikan, merepresentasikan jumlah barang yang "diselamatkan" dari sampah. — [Aufa]

## Role Pengguna

- **Customer**: Mencari mitra reparasi, melihat profil dan lokasi mitra, mengajukan Repair Request, memantau status reparasi, memberi review setelah repair selesai.
- **Mitra Reparasi**: Mendaftar sebagai mitra, membuat profil (lokasi, kontak, layanan), menerima Repair Request, memperbarui status reparasi.
- **Admin**: Mengelola data pengguna, mitra, dan aktivitas aplikasi.

## Anggota Kelompok

Karya Kelompok 11 PBP-D:
- 2506548295 - MUHAMMAD AKMAL HAQQANI
- 2506656500 - AUFA NURCAHYO
- 2506614763 - HISYAM PRASETYO
- 2506656785 - HAFIZH ZUHDI HARTANTO
- 2506656601 - DAVE WESLEY TJOENG
