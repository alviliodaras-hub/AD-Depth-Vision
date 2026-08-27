# 🎬 Panduan Penulisan Script & Template SceneFlow

Dokumen ini berisi panduan lengkap, aturan penulisan, dan template naskah yang siap Anda gunakan untuk fitur **SceneFlow (Script-to-Video Synchronization)** di AD-Depth Vision.

---

## 📌 1. Struktur Dasar Naskah

Naskah dibagi menjadi baris-baris terpisah. Setiap baris mewakili 1 kejadian atau aksi (*cue*).

```text
[LOKASI / SUASANA]
[INSTRUKSI KAMERA / FRAMING]
[AKSI TOKOH / NARASI]
[NAMA TOKOH]: "[KALIMAT DIALOG]"
[EFEK SUARA / EFEK VISUAL]
[TRANSISI]
```

---

## 🎨 2. Aturan Format 8 Kategori Cue

Sistem mengenali 8 kategori berikut secara otomatis berdasarkan awalan atau kata kunci:

### 1. ⚪ Environment (Lokasi & Suasana)
Gunakan format slugline standar film.
- **Awalan**: `INT.` (ruang tertutup/indoor), `EXT.` (ruang terbuka/outdoor), `INT/EXT.`, atau `SCENE [nomor]:`
- **Contoh**:
  ```text
  INT. RUANG INTEROGASI - MALAM
  EXT. JALAN RAYA SUDIRMAN - SIANG HUJAN
  SCENE 1: GUDANG TUA TERBENGKALAI
  ```

### 2. 🟡 Dialogue (Dialog Tokoh)
Gunakan nama karakter diikuti titik dua (`:`) dan tanda kutip `"` untuk kalimat yang diucapkan.
- **Format Dasar**: `NAMA: "Kalimat dialog"`
- **Format Emosi / Parenthetical**: `NAMA (emosi): "Kalimat dialog"`
- **Contoh**:
  ```text
  KAI: "Sistem alarm berhasil kita matikan, masuk sekarang!"
  DARA (berbisik panik): "Tunggu, aku melihat ada sensor laser di lorong itu."
  ALVI: "Biar aku yang nonaktifkan dari sini."
  ```

### 3. 🔵 Action (Aksi Fisik & Narasi)
Tuliskan aksi pergerakan fisik karakter atau peristiwa di adegan secara langsung tanpa awalan khusus.
- **Contoh**:
  ```text
  Kai melompat melewati barikade dan bersembunyi di balik pilar beton.
  Dara mengeluarkan laptopnya dan mulai meretas terminal keamanan.
  Alvi menekan tombol darurat di panel dinding.
  ```

### 4. 🟢 Camera (Gerakan Kamera)
Tuliskan arah atau jenis pergerakan kamera. Boleh menggunakan kurung siku `[CAMERA: ...]` atau langsung menuliskan `CAMERA:`.
- **Kata kunci**: `CAMERA:`, `PAN LEFT`, `PAN RIGHT`, `TILT UP`, `TILT DOWN`, `DOLLY IN`, `DOLLY OUT`, `ZOOM IN`, `ZOOM OUT`, `TRACKING SHOT`
- **Contoh**:
  ```text
  [CAMERA: SLOW PAN LEFT MENGIKUTI LANGKAH KAKI KAI]
  CAMERA: DOLLY IN CEPAT KE ARAH WAJAH DARA
  [CAMERA: TILT UP MEMPERLIHATKAN TINGGINYA MENARA KONTROL]
  ```

### 5. 🟣 Shot (Framing / Jarak Bidik)
Tentukan sudut framing dan ukuran gambar.
- **Kata kunci**: `WIDE SHOT`, `CLOSE UP`, `MEDIUM SHOT`, `EXTREME CLOSE UP`, `CU`, `MCU`, `WS`, `POV`
- **Contoh**:
  ```text
  WIDE SHOT pemandangan kota futuristik di malam hari.
  [SHOT: CLOSE UP PADA JARI DARA YANG MENGETIK CEPAT]
  MEDIUM SHOT kedua karakter berdiri saling berhadapan.
  ```

### 6. 🟠 Audio / SFX (Efek Suara & Musik)
Tuliskan suara latar, musik, atau efek suara.
- **Awalan**: `SFX:`, `SOUND:`, `AUDIO:`, `MUSIC:`, atau dalam kurung `[SFX: ...]`
- **Contoh**:
  ```text
  [SFX: SUARA SIRENE KEAMANAN MENGERUNG KERAS]
  SFX: Dentuman langkah kaki penjaga mendekat dari kejauhan.
  [AUDIO: MUSIK LATAR SUSPENSE MENEGANGKAN]
  ```

### 7. 🔷 VFX (Efek Visual & CGI)
Tuliskan efek grafis komputer atau visual khusus.
- **Awalan**: `VFX:`, `CGI:`, `EFFECT:`, atau dalam kurung `[VFX: ...]`
- **Contoh**:
  ```text
  [VFX: HOLOGRAM BIRU MUNCUL BERPUTAR DI TENGAH RUANGAN]
  VFX: Kilatan percikan listrik merah menyambar kabel di dinding.
  [VFX: PARTIKEL CAHAYA EMAS MENYELIMUTI SENJATA]
  ```

### 8. 🩷 Transition (Perpindahan Adegan)
Tuliskan transisi pemotongan adegan di akhir skrip atau antar-adegan.
- **Kata kunci**: `CUT TO:`, `FADE IN:`, `FADE OUT:`, `DISSOLVE TO:`, `MATCH CUT:`, `SMASH CUT:`
- **Contoh**:
  ```text
  CUT TO:
  FADE OUT.
  MATCH CUT:
  ```

---

## 📋 3. Template Siap Pakai (Tinggal Ganti Isi)

### 🔹 Template 1: Adegan Aksi / Kejar-kejaran (Action Scene)
```text
EXT. ATAP GEDUNG PENCAKAR LANGIT - MALAM

[CAMERA: TRACKING SHOT MENGIKUTI LANGKAH BERLARI]

KAI (terengah-engah): "Mereka sudah mengepung pintu darurat di lantai bawah!"

Kai melompati celah antar gedung dan mendarat di atas ventilasi.

[SFX: SUARA BALING-BALING HELIKOPTER MENDEKAT]

[VFX: LAMPU SOROT DRONE MENEMBUS KABUT MALAM]

DARA: "Jangan berhenti, meluncur ke pipa darurat sekarang!"

[SHOT: CLOSE UP WAJAH KAI YANG TEGANG]

Kai menarik napas panjang lalu meluncur turun.

FADE OUT.
```

---

### 🔹 Template 2: Adegan Percakapan / Investigasi (Dialogue / Sci-Fi Scene)
```text
INT. RUANG LABORATORIUM RAHASIA - MALAM

WIDE SHOT ruangan serba putih dengan tabung eksperimen menyala di tengah.

[CAMERA: SLOW PAN LEFT KE ARAH MEJA KERJA]

DR. ARIS: "Data sinkronisasi gelombang otak sudah mencapai kestabilan penuh."

SARAH (ragu-ragu): "Tapi apakah kamu yakin tidak akan ada lonjakan daya seperti kemarin?"

[VFX: DATA HOLOGRAFIK BERKEDIP DENGAN PARTIKEL BIRU NEON]

Dr. Aris menekan tombol aktivasi pada keyboard hologram.

[SFX: SUARA DENGUNG ENERGI TINGGI DARI REAKTOR]

DR. ARIS: "Lihat angkanya sendiri. Akurasinya sempurna."

[SHOT: CLOSE UP REAKSI MATA SARAH YANG TERKEJUT]

SARAH: "Ini... luar biasa. Kita berhasil mengubah masa depan."

CUT TO:
```

---

### 🔹 Template 3: Adegan Drama / Sinematik Emosional (Cinematic Drama)
```text
INT. RUANG TAMU GELAP - SORE

[CAMERA: STATIC SHOT DENGAN PENCAHAYAAN TINGKAP TIPIS]

Rian duduk terdiam memandangi sebuah foto lama di tangannya.

[SFX: SUARA DETIK JAM DINDING YANG SUNYI]

ELENA: "Kamu tidak bisa terus menyalahkan dirimu atas apa yang terjadi."

[SHOT: MEDIUM SHOT RIAN MENARIK NAPAS DALAM-DALAM]

RIAN: "Seandainya aku sampai lima menit lebih awal..."

Elena melangkah mendekat dan meletakkan tangannya di pundak Rian.

ELENA (lembut): "Waktu tidak bisa diulang, tapi kita masih punya hari esok."

[CAMERA: SLOW ZOOM OUT MENINGGALKAN RUANGAN]

FADE OUT.
```

---

## 💡 4. Tips Agar Hasil Audio Alignment Paling Akurat
1. **Sertakan tanda kutip `"` pada dialog**: Contoh `KAI: "Kita harus pergi sekarang!"`. Ini memastikan algoritma audio mencocokkan gelombang suara secara tepat dengan kata-kata tersebut.
2. **Pisahkan baris per kalimat/kejadian**: Setiap baris baru akan menjadi 1 kartu cue terpisah yang bisa diklik untuk navigasi video (*Click-to-Seek*).
3. **Gunakan tombol Edit Timecodes jika ingin fine-tuning**: Setelah sinkronisasi otomatis selesai, Anda bisa menggeser detik start/end di editor jika ingin presisi milidetik khusus.
