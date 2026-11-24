// SPDX-License-Identifier: GPL-2.0
/*
 * hello_ingres - contoh LKM pertama untuk POCO F4 GT (ingres).
 *
 * insmod : menulis pesan ke dmesg dan membuat /proc/hello_ingres
 * rmmod  : menghapus /proc/hello_ingres
 *
 * Dibangun oleh workflow build_ingres.yml bersama kernelnya, jadi hanya bisa
 * dimuat di kernel dari build yang sama (vermagic + CRC simbol harus cocok).
 */
#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt

#include <linux/init.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/utsname.h>

static unsigned long loaded_at;
static struct proc_dir_entry *entry;

static int hello_show(struct seq_file *m, void *v)
{
	seq_puts(m, "Halo dari LKM ingres!\n");
	seq_printf(m, "kernel : %s\n", utsname()->release);
	seq_printf(m, "aktif  : %u detik\n",
		   jiffies_to_msecs(jiffies - loaded_at) / 1000);
	return 0;
}

static int hello_open(struct inode *inode, struct file *file)
{
	return single_open(file, hello_show, NULL);
}

static const struct proc_ops hello_proc_ops = {
	.proc_open	= hello_open,
	.proc_read	= seq_read,
	.proc_lseek	= seq_lseek,
	.proc_release	= single_release,
};

static int __init hello_init(void)
{
	loaded_at = jiffies;
	entry = proc_create("hello_ingres", 0444, NULL, &hello_proc_ops);
	if (!entry)
		return -ENOMEM;
	pr_info("dimuat di kernel %s\n", utsname()->release);
	return 0;
}

static void __exit hello_exit(void)
{
	proc_remove(entry);
	pr_info("dilepas\n");
}

module_init(hello_init);
module_exit(hello_exit);

MODULE_LICENSE("GPL");
MODULE_AUTHOR("kingD2N");
MODULE_DESCRIPTION("Contoh LKM untuk POCO F4 GT (ingres)");
