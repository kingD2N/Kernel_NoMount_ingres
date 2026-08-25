#

<img width="512" height="279" alt="image_0c69b253-1d7c-4fda-9f53-08ba18f46a10" src="https://github.com/user-attachments/assets/ba10704d-00c8-45d1-bde0-bd8bdb3618d2" />

| | |
|:---|:---|
| 📱 Device | POCO F4 GT (ingres) • Redmi K50G (ingres) |
| 🟠 ROM Support | Official AOSP |
| 🖥️ Kernel Name | Melt-Rebase |
| 🧬 Kernel Base | android12-5.10.266 |
| 🛠️ Build Scope | ZIP |
| 📦 Source | https://github.com/kingD2N/kernel_source_Melt_xiaomi_ingres |
| ⚔️ Kernel branch | melt-MIX |
| 💻 KSU Manager type | KernelSU-Next |
| 🔧 SuSFS Version | Supported (susfs4ksu@44d9fed) |
| ⚙️ BBG Patch | Supported |
| ⚙️ Re-Kernel (Netlink) | Supported |
| ⚙️ Re-Kernel (eBPF) | Supported (daemon+prog attached as release assets) |
| 🧩 DroidSpaces | Supported |
| 🗂️ NoMount | Supported (research/dev - kingD2N/nomount) |
| 🔨 Compiler | LLVM/Clang 22.1.8 Official |

---

#     ✧ Kernel Melt MIX™ ✧

#   ✧ For POCO F4 GT (ingres) ✧

[![Build](https://img.shields.io/badge/GitHub_Actions-CI_Builder-2088FF?logo=githubactions&logoColor=white)](https://github.com/kingD2N/Kernel_5.10.261_Melt_Ingres_POCOF4GT/actions)
[![KernelSU](https://img.shields.io/badge/KernelSU-Supported-4CAF50?logo=linux&logoColor=white)](https://github.com/tiann/KernelSU)
[![KernelSU-Next](https://img.shields.io/badge/KernelSU--Next-Supported-4CAF50?logo=linux&logoColor=white)](https://github.com/KernelSU-Next/KernelSU-Next)
[![SukiSU Ultra](https://img.shields.io/badge/SukiSU_Ultra-Supported-4CAF50?logo=linux&logoColor=white)](https://github.com/SukiSU-Ultra/SukiSU-Ultra)
[![ReSukiSU](https://img.shields.io/badge/ReSukiSU-Supported-4CAF50?logo=linux&logoColor=white)](https://github.com/ReSukiSU/ReSukiSU)
[![SUSFS](https://img.shields.io/badge/SUSFS-v2.2.0-FF6D00?logo=gitlab&logoColor=white)](https://gitlab.com/simonpunk/susfs4ksu)
[![Device](https://img.shields.io/badge/Device-POCO_F4_GT_%2F_Redmi_K50G-EF5350)](https://github.com/mohdakil2426/android_kernel_xiaomi_marble)
[![ROM](https://img.shields.io/badge/ROM-AOSP_&_HyperOS-FF6900)](https://www.mi.com/global/hyperos/)

## 📖 Apa Itu Kernel Custom?

Kernel adalah lapisan inti (core) sistem operasi Android yang menjadi jembatan komunikasi antara hardware perangkat (CPU, GPU, RAM, sensor, modem, dll) dengan software di atasnya (Android framework dan aplikasi). Kernel Android merupakan turunan Linux kernel yang dimodifikasi oleh Google (AOSP) dan vendor SoC seperti Qualcomm.

**Kernel custom** adalah kernel hasil modifikasi dari kernel stock/bawaan pabrikan (dalam hal ini Xiaomi/POCO), yang dikembangkan ulang oleh developer independen untuk menambah fitur, melakukan optimasi, atau menutupi kekurangan kernel bawaan.

### Fitur Umum yang Dibawa Kernel Custom

- **Root solution** — dukungan KernelSU, KernelSU-Next, SukiSU Ultra, ReSukiSU untuk akses root tanpa mem-patch partisi system
- **SUSFS** — menyamarkan status root dari deteksi aplikasi (Play Integrity, aplikasi perbankan, dll)
- **CPU Governor tambahan** — skema pengaturan clock speed processor (schedutil, performance, powersave, walt, dll)
- **I/O Scheduler tambahan** — mengatur antrian baca/tulis storage (cfq, bfq, kyber, mq-deadline dll.)
- **TCP congestion control** — misalnya BBR untuk optimasi throughput jaringan
- **Tuning thermal & baterai** — kontrol suhu dan penghematan daya yang lebih agresif atau longgar
- **Mode performa gaming** — tweak tambahan seperti penyesuaian refresh rate/FPS
- Patch keamanan tambahan dan perbaikan bug driver

### Kelebihan

- Kontrol lebih besar atas performa dan efisiensi baterai
- Dukungan root modern yang lebih tersembunyi dari deteksi aplikasi
- Fitur networking dan tweak yang tidak tersedia di kernel stock

### Risiko

- Berpotensi bootloop bila kernel tidak cocok dengan base ROM
- Dapat menghilangkan garansi resmi (unlock bootloader umumnya membatalkan garansi)
- Berisiko kehilangan data bila proses flashing gagal tanpa backup
