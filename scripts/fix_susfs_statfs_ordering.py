#!/usr/bin/env python3
"""
Fix for susfs4ksu's SUS_KSTAT/statfs.c refactor (introduced 10 Sept 2026,
still unresolved upstream as of susfs4ksu@dd94c3a / gki-android12-5.10).

Bug: the patch declares
    extern int susfs_sus_kstat_spoof_vfs_statfs(...);
    extern bool susfs_is_inode_sus_kstat(...);
AFTER vfs_get_fsid(), but susfs_statfs_by_dentry() -- defined BEFORE
vfs_get_fsid() -- already calls susfs_sus_kstat_spoof_vfs_statfs().
C requires declare-before-use, so this fails under -Werror with:
    error: implicit declaration of function 'susfs_sus_kstat_spoof_vfs_statfs'
Independently confirmed at github.com/Numbersf/Action-Build#269.

Fix: hoist the two extern lines to right before susfs_statfs_by_dentry(),
which is also where they lived pre-refactor. No logic is touched.

Usage: python3 fix_susfs_statfs_ordering.py <path-to-statfs.c>
Exit codes: 0 = fixed, or nothing to do (pattern absent -> assume already
            fixed upstream / shape changed; this is a soft no-op, not a
            failure, so a build never gets blocked on this heuristic).
"""
import sys
import pathlib

def main():
    if len(sys.argv) != 2:
        print("usage: fix_susfs_statfs_ordering.py <path-to-statfs.c>", file=sys.stderr)
        return 2

    target = pathlib.Path(sys.argv[1])
    src = target.read_text()

    misplaced_tail = (
        "EXPORT_SYMBOL(vfs_get_fsid);\n"
        "\n"
        "#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
        "extern bool susfs_is_inode_sus_kstat(struct inode *inode, bool *out_is_fuse);\n"
        "extern int susfs_sus_kstat_spoof_vfs_statfs(struct inode *inode, struct kstatfs *buf, bool *is_fuse);\n"
        "#endif // #ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
        "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
    )
    fixed_tail = (
        "EXPORT_SYMBOL(vfs_get_fsid);\n"
        "\n"
        "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
    )
    fn_header = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
        "static int susfs_statfs_by_dentry(struct dentry *dentry, struct kstatfs *buf, bool *is_fuse)\n"
    )
    fixed_fn_header = (
        "#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
        "extern bool susfs_is_inode_sus_kstat(struct inode *inode, bool *out_is_fuse);\n"
        "extern int susfs_sus_kstat_spoof_vfs_statfs(struct inode *inode, struct kstatfs *buf, bool *is_fuse);\n"
        "static int susfs_statfs_by_dentry(struct dentry *dentry, struct kstatfs *buf, bool *is_fuse)\n"
    )

    if misplaced_tail not in src or fn_header not in src:
        print("::notice::susfs statfs.c ordering-bug pattern not found -- "
              "either upstream already fixed it, or the patch shape changed. "
              "Skipping (soft no-op); if the build then fails with an "
              "implicit-declaration error in fs/statfs.c, the fix needs updating.")
        return 0

    if src.count(misplaced_tail) != 1 or src.count(fn_header) != 1:
        print("::warning::susfs statfs.c ordering pattern matched more than "
              "once -- refusing to guess, skipping the automatic fix. Check "
              "fs/statfs.c by hand.")
        return 0

    src = src.replace(misplaced_tail, fixed_tail, 1)
    src = src.replace(fn_header, fixed_fn_header, 1)
    target.write_text(src)
    print("::notice::Applied fs/statfs.c declare-before-use fix for susfs4ksu's "
          "SUS_KSTAT refactor (see Numbersf/Action-Build#269).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
