# LKM (Loadable Kernel Module) untuk ingres

Setiap folder di sini (`lkm/<nama>/`) adalah satu modul kernel out-of-tree.
Folder harus berisi `Kbuild` (atau `Makefile`) dengan `obj-m := <nama>.o` beserta source-nya.

Workflow `build_ingres.yml` (pilihan **lkm**) membangun semua modul di sini **bersama kernelnya**:
tree, `.config`, clang, dan nama versi kernel (vermagic) sama, dan CRC simbol diambil dari
`vmlinux.symvers` kernel itu sendiri. Kernel ini memakai `CONFIG_MODVERSIONS=y`, jadi modul
**hanya bisa dimuat di kernel dari build yang sama**. Flash dulu zip kernel dari rilis yang sama,
baru muat `.ko`-nya.

## Memuat dan melepas (root)

```
insmod /sdcard/Download/hello_ingres.ko
```

```
cat /proc/hello_ingres; dmesg | grep hello_ingres
```

```
rmmod hello_ingres
```

## Kalau `insmod` gagal

Lihat alasannya di `dmesg | tail`:

- `disagrees about version of symbol` → `.ko` dari build lain, bukan dari kernel yang sedang jalan.
- `version magic ... should be ...` → nama/versi kernel berbeda, sama artinya.
- `Unknown symbol` → modul memakai fungsi yang tidak diekspor kernel (`EXPORT_SYMBOL`).
