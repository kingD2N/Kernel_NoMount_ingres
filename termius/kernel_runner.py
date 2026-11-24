#!/usr/bin/env python3
"""Build kernel ingres di server (Termius) dengan workflow GitHub yang sama.

Membaca .github/workflows/build_ingres.yml dari salinan kingD2N/Kernel_NoMount_ingres
(diambil kernel-menu.sh ke ~/kernel-ingres/workflow) lalu menjalankan langkah-langkahnya
satu per satu di server biasa, seperti runner GitHub: ekspresi ${{ inputs.* / env.* }}
diisi, GITHUB_ENV diteruskan antar langkah, kondisi `if:` dihitung. Yang khusus GitHub
dilewati (sudo apt, cache GitHub, artifact, release). LLVM terbaru disimpan sekali di
~/.cache/kernel-ingres/llvm-<versi> dan dipakai ulang; ~/.cache/kernel-ingres/bin berisi
wget dengan cache unduhan (NDK, bpftool) dan pengganti ccache / filterdiff kalau server
belum punya. Jadi daftar pilihan di menu dan semua perbaikan workflow otomatis ikut.

  kernel_runner.py options --repo DIR                 daftar pilihan (JSON)
  kernel_runner.py menu    --repo DIR --out FILE      tanya pilihan di terminal, simpan ke FILE
  kernel_runner.py build   --repo DIR --inputs FILE   build dengan pilihan di FILE
"""
import argparse, io, json, os, re, shutil, subprocess, sys, tarfile, time, urllib.request

HOME = os.path.expanduser("~")
CACHE = os.path.join(HOME, ".cache", "kernel-ingres")
BIN = os.path.join(CACHE, "bin")
WS = os.environ.get("KERNEL_WS", os.path.join(HOME, "kernel-ingres", "work"))
HASIL = os.environ.get("KERNEL_HASIL", os.path.join(HOME, "hasil-kernel"))
WF = ".github/workflows/build_ingres.yml"
ACTOR = "kingD2N"
PYYAML_TAG = "6.0.2"

# Langkah yang hanya berlaku di runner GitHub (sudo / cache / release GitHub).
SKIP = {
    "Free up disk space": "khusus runner GitHub",
    "Install build dependencies": "paket server diperiksa di awal (tanpa sudo)",
    "Purge old ccache (on refresh)": "ccache di server tersimpan di ~/.ccache_ingres",
    "Create GitHub Release": "hasil disalin ke ~/hasil-kernel lalu diupload ke GoFile",
}

C = {"ok": "\033[1;32m", "in": "\033[1;34m", "wr": "\033[1;33m", "er": "\033[1;31m", "dm": "\033[2m", "0": "\033[0m"}
def say(kind, msg, file=None):
    tag = {"ok": "[OK]", "in": "[..]", "wr": "[PERINGATAN]", "er": "[GAGAL]"}[kind]
    print(f"{C[kind]}{tag}{C['0']} {msg}", flush=True, file=file or sys.stdout)
def die(msg):
    say("er", msg)
    sys.exit(1)


# --------------------------------------------------------------------------- YAML
def load_yaml_module():
    try:
        import yaml  # noqa: F401
        return yaml
    except ImportError:
        pass
    d = os.path.join(CACHE, f"pyyaml-{PYYAML_TAG}")
    if not os.path.isfile(os.path.join(d, "yaml", "__init__.py")):
        say("in", "Python di server belum punya PyYAML - mengunduh versi pure-python (sekali saja)", sys.stderr)
        data, errs = None, []
        try:   # PyPI (sdist), cadangan: arsip GitHub
            meta = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/PyYAML/{PYYAML_TAG}/json", timeout=60))
            urls = [u["url"] for u in meta["urls"] if u.get("packagetype") == "sdist"]
        except Exception as e:
            urls, errs = [], [str(e)]
        urls.append(f"https://github.com/yaml/pyyaml/archive/refs/tags/{PYYAML_TAG}.tar.gz")
        for url in urls:
            try:
                data = urllib.request.urlopen(url, timeout=120).read()
                break
            except Exception as e:
                errs.append(f"{url}: {e}")
        if data is None:
            die("Gagal unduh PyYAML (" + "; ".join(errs) + "). Minta pemilik server memasang python3-yaml.")
        tmp = d + ".part"
        shutil.rmtree(tmp, ignore_errors=True)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            for m in tf.getmembers():
                k = m.name.find("/lib/yaml/")
                if m.isfile() and k > 0 and m.name.endswith(".py") and m.name.count("/") == 3:
                    out = os.path.join(tmp, "yaml", m.name[k + 10:])
                    os.makedirs(os.path.dirname(out), exist_ok=True)
                    with open(out, "wb") as f:
                        f.write(tf.extractfile(m).read())
        if not os.path.isfile(os.path.join(tmp, "yaml", "__init__.py")):
            die("Arsip PyYAML tidak berisi lib/yaml")
        shutil.rmtree(d, ignore_errors=True)
        os.rename(tmp, d)
    sys.path.insert(0, d)
    import yaml
    return yaml


def read_workflow(repo):
    yaml = load_yaml_module()
    d = yaml.safe_load(open(os.path.join(repo, WF), encoding="utf-8").read())
    on = d.get(True) or d.get("on")
    inputs = on["workflow_dispatch"]["inputs"]
    job = d["jobs"][next(iter(d["jobs"]))]
    return inputs, job


def source_map(job, inputs):
    """kernel_source label -> (repo URL, default branch), from the Clone step's case."""
    run = next(s["run"] for s in job["steps"] if s.get("name") == "Clone Kernel Source")
    found = {}
    for m in re.finditer(r'^\s*(?:"([^"\n]+)"|(\*))\)\s*\n\s*URL=(\S+?);\s*DEF=(\S*?);', run, re.M):
        found[m.group(1) or m.group(2)] = (m.group(3), m.group(4))
    out = {}
    for lab in inputs["kernel_source"]["options"]:
        out[lab] = found.get(lab) or found.get("*") or ("", "")
    return out


def options(repo):
    inputs, job = read_workflow(repo)
    return {"inputs": inputs, "sources": source_map(job, inputs)}


# ------------------------------------------------------------------- expressions
def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return "" if v is None else str(v)


class Ctx:
    def __init__(self, inputs, env, ws):
        self.inputs, self.env, self.ws = inputs, env, ws

    def ref(self, name):
        if name.startswith("inputs."):
            return self.inputs.get(name[7:], "")
        if name.startswith("env."):
            return self.env.get(name[4:], "")
        return {"github.actor": ACTOR, "github.repository_owner": ACTOR, "github.workspace": self.ws,
                "github.repository": "kingD2N/Kernel_NoMount_ingres", "github.token": "",
                "github.event_name": "workflow_dispatch", "runner.os": "Linux",
                "runner.temp": os.path.join(self.ws, ".runner")}.get(name, "")

    def evaluate(self, expr):
        """Small evaluator for workflow expressions: refs, literals, == != ! && || ( )."""
        toks = re.findall(r"'(?:[^']|'')*'|\|\||&&|==|!=|!|\(|\)|[A-Za-z_][\w.\-]*\(\)|[A-Za-z_][\w.\-]*|-?\d+(?:\.\d+)?", expr)
        py = []
        for t in toks:
            if t.startswith("'"):
                py.append(repr(t[1:-1].replace("''", "'")))
            elif t == "||":
                py.append(" or ")
            elif t == "&&":
                py.append(" and ")
            elif t == "!":
                py.append(" not ")
            elif t in ("==", "!=", "(", ")"):
                py.append(t)
            elif t in ("always()", "success()", "!cancelled()", "cancelled()") or t.endswith("()"):
                py.append("True" if t in ("always()", "success()") else "False")
            elif t == "true":
                py.append("True")
            elif t == "false":
                py.append("False")
            elif re.fullmatch(r"-?\d+(?:\.\d+)?", t):
                py.append(t)
            else:
                v = self.ref(t)
                py.append(repr(v) if isinstance(v, bool) else repr(fmt(v)))
        src = " ".join(py)
        # GitHub compares a boolean input with 'true' loosely; make that work here too
        src = re.sub(r"(True|False)\s*==\s*'(true|false)'", lambda m: m.group(1) + "==" + ("True" if m.group(2) == "true" else "False"), src)
        return eval(src, {"__builtins__": {}}, {})

    def subst(self, text):
        def f(m):
            e = m.group(1).strip()
            if re.fullmatch(r"(inputs|env|github|runner|secrets)\.[\w.\-]+", e):
                return fmt(self.ref(e))
            return fmt(self.evaluate(e))
        return re.sub(r"\$\{\{(.*?)\}\}", f, text, flags=re.S)

    def cond(self, c):
        if c is None:
            return True
        if isinstance(c, bool):
            return c
        c = str(c).strip()
        m = re.fullmatch(r"\$\{\{(.*)\}\}", c, re.S)
        r = self.evaluate(m.group(1) if m else c)
        return bool(r) and r != "false"


def parse_env_file(path):
    env = {}
    if not os.path.isfile(path):
        return env
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    i = 0
    while i < len(lines):
        l = lines[i]
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)<<(.+)$", l)
        if m:
            k, delim, buf = m.group(1), m.group(2), []
            i += 1
            while i < len(lines) and lines[i] != delim:
                buf.append(lines[i]); i += 1
            env[k] = "\n".join(buf)
        elif "=" in l:
            k, v = l.split("=", 1)
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k):
                env[k] = v
        i += 1
    return env


# ------------------------------------------------------------------ server tools
SHIMS = {
"wget": r'''#!/usr/bin/env bash
# wget dengan cache unduhan (~/.cache/kernel-ingres/dl): LLVM / NDK cukup diunduh sekali.
out=""; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -O) out="$2"; shift ;;
    -O*) out="${1#-O}" ;;
    -q|-nv|--quiet|-c|--continue) ;;
    -*) ;;
    *) url="$1" ;;
  esac
  shift
done
[ -n "$url" ] || { echo "wget (server): URL kosong" >&2; exit 1; }
[ -n "$out" ] || out="$(basename "${url%%\?*}")"
d="$HOME/.cache/kernel-ingres/dl"; mkdir -p "$d"
key="$(printf '%s' "$url" | sha1sum | cut -c1-12)-$(basename "${url%%\?*}")"
if [ ! -s "$d/$key" ]; then
  curl -fsSL --retry 3 --retry-delay 5 -o "$d/$key.part" "$url" || { rm -f "$d/$key.part"; exit 8; }
  mv -f "$d/$key.part" "$d/$key"
  # simpan hanya 6 unduhan terbaru
  ls -1t "$d" | grep -v '\.part$' | tail -n +7 | while read -r f; do rm -f "$d/$f"; done
fi
[ "$out" = "-" ] && exec cat "$d/$key"
ln -f "$d/$key" "$out" 2>/dev/null || cp -f "$d/$key" "$out"
''',
"ccache": r'''#!/usr/bin/env bash
# Server belum punya ccache: jalankan compiler langsung, abaikan opsi ccache sendiri.
case "${1:-}" in ""|-*) exit 0 ;; esac
exec "$@"
''',
"filterdiff": r'''#!/usr/bin/env python3
# Pengganti filterdiff (patchutils) untuk -x / -i: buang / ambil file tertentu dari patch.
import fnmatch, re, sys
inc, exc, files = [], [], []
a = sys.argv[1:]; i = 0
while i < len(a):
    if a[i] in ("-x", "--exclude"): exc.append(a[i + 1]); i += 2
    elif a[i] in ("-i", "--include"): inc.append(a[i + 1]); i += 2
    elif a[i].startswith("-x"): exc.append(a[i][2:]); i += 1
    elif a[i].startswith("-i"): inc.append(a[i][2:]); i += 1
    else: files.append(a[i]); i += 1
text = "".join(open(f, encoding="utf-8", errors="surrogateescape").read() for f in files) if files else sys.stdin.read()
lines = text.splitlines(keepends=True)
starts = [n for n, l in enumerate(lines) if l.startswith("diff ")]
if not starts:
    starts = [n for n, l in enumerate(lines) if l.startswith("--- ") and n + 1 < len(lines) and lines[n + 1].startswith("+++ ")]
out = lines[:starts[0]] if starts and (inc or exc) else []  # sama seperti filterdiff asli
starts.append(len(lines))
for s, e in zip(starts, starts[1:]):
    sec = lines[s:e]; path = ""
    for l in sec:
        if l.startswith("+++ "):
            path = l[4:].split("\t")[0].strip()
            if path == "/dev/null":
                path = next((x[4:].split("\t")[0].strip() for x in sec if x.startswith("--- ")), path)
            break
    keep = (not inc or any(fnmatch.fnmatch(path, p) for p in inc)) and not any(fnmatch.fnmatch(path, p) for p in exc)
    if keep: out.extend(sec)
sys.stdout.write("".join(out))
''',
}


def setup_tools(need_pahole):
    os.makedirs(BIN, exist_ok=True)
    have = lambda t: shutil.which(t, path=os.environ["PATH"]) is not None
    shims = ["wget"]                            # selalu: cache unduhan NDK / bpftool
    if not have("ccache"):
        shims.append("ccache"); say("wr", "ccache tidak ada di server - build tetap jalan tanpa cache (lebih lama)")
    if not have("filterdiff"):
        shims.append("filterdiff"); say("in", "filterdiff tidak ada - memakai pengganti bawaan menu")
    jobs = os.environ.get("KERNEL_JOBS", "").strip()
    for n in os.listdir(BIN):
        os.remove(os.path.join(BIN, n))
    for n in shims:
        p = os.path.join(BIN, n)
        with open(p, "w") as f:
            f.write(SHIMS[n])
        os.chmod(p, 0o755)
    if jobs.isdigit() and int(jobs) > 0:
        # batasi jumlah core untuk make -j$(nproc) (server dipakai bersama)
        p = os.path.join(BIN, "nproc")
        with open(p, "w") as f:
            f.write(f"#!/bin/sh\necho {int(jobs)}\n")
        os.chmod(p, 0o755)
        say("in", f"KERNEL_JOBS={jobs}: build memakai {jobs} core")

    miss = [t for t in ("git", "curl", "python3", "make", "bc", "bison", "flex", "zip", "unzip", "tar", "xz",
                        "perl", "cpio", "patch", "gzip", "sha1sum", "awk", "sed", "find") if not have(t)]
    hdr = {"openssl (libssl-dev)": ["openssl/opensslv.h"], "libelf (libelf-dev)": ["libelf.h", "gelf.h"]}
    dirs = ["/usr/include", "/usr/include/x86_64-linux-gnu", "/usr/local/include"]
    for name, files in hdr.items():
        if not any(os.path.isfile(os.path.join(d, f)) for d in dirs for f in files):
            miss.append(name)
    if need_pahole and not have("pahole"):
        miss.append("pahole (dwarves) - dibutuhkan Re-Kernel eBPF; atau matikan rekernel_ebpf")
    if miss:
        die("Alat belum terpasang di server: " + ", ".join(miss) + "  (minta pemilik server memasangnya)")


# -------------------------------------------------------------------------- LLVM
LLVM_STEP = "Download LLVM (latest stable release)"


def llvm_step(envfile):
    """Sama dengan langkah LLVM workflow (rilis stabil terbaru llvm/llvm-project), tapi hasil
    ekstrak disimpan di ~/.cache/kernel-ingres/llvm-<versi> dan dipakai ulang."""
    tc = os.path.join(WS, "toolchains")
    os.makedirs(tc, exist_ok=True)
    own = os.environ.get("KERNEL_LLVM_DIR", "").strip()
    if own:
        d = os.path.abspath(own)
        out = subprocess.run([os.path.join(d, "bin", "clang"), "--version"], capture_output=True, text=True).stdout
        m = re.search(r"clang version (\d+\.\d+\.\d+)", out)
        if not m:
            die(f"KERNEL_LLVM_DIR={own}: bin/clang tidak bisa dijalankan")
        ver = m.group(1)
        say("in", f"Memakai LLVM sendiri dari KERNEL_LLVM_DIR ({ver})")
    else:
        r = subprocess.run(["git", "ls-remote", "--tags", "--refs", "https://github.com/llvm/llvm-project", "llvmorg-*"],
                           capture_output=True, text=True, timeout=300)
        vers = sorted({tuple(map(int, m.groups())) for m in re.finditer(r"refs/tags/llvmorg-(\d+)\.(\d+)\.(\d+)$", r.stdout, re.M)},
                      reverse=True)
        if not vers:
            die("Tidak bisa membaca daftar rilis LLVM dari GitHub")
        ver = url = None
        for v in vers[:4]:   # tag terbaru kadang belum punya tarball Linux
            vs = ".".join(map(str, v))
            u = f"https://github.com/llvm/llvm-project/releases/download/llvmorg-{vs}/LLVM-{vs}-Linux-X64.tar.xz"
            if subprocess.run(["curl", "-fsIL", "--max-time", "60", "-o", "/dev/null", u]).returncode == 0:
                ver, url = vs, u
                break
        if not ver:
            die("Rilis LLVM terbaru belum punya tarball Linux-X64")
        print(f"==> Latest LLVM release: llvmorg-{ver} (version {ver})", flush=True)
        d = os.path.join(CACHE, f"llvm-{ver}")
        if not os.path.isfile(os.path.join(d, "bin", "clang")):
            tmp = os.path.join(CACHE, "llvm-download.tar.xz")
            say("in", f"Unduh LLVM {ver} (sekali saja, ~2 GB)")
            if subprocess.run(["curl", "-fL", "--retry", "3", "--retry-delay", "5", "-o", tmp, url]).returncode != 0:
                die(f"Gagal unduh {url}")
            shutil.rmtree(d + ".part", ignore_errors=True)
            os.makedirs(d + ".part")
            say("in", "Ekstrak LLVM")
            if subprocess.run(["tar", "-xf", tmp, "-C", d + ".part", "--strip-components=1"]).returncode != 0:
                die("Gagal ekstrak LLVM")
            os.rename(d + ".part", d)
            os.remove(tmp)
        for old in os.listdir(CACHE):   # simpan hanya versi yang dipakai
            if old.startswith("llvm-") and os.path.join(CACHE, old) != d and os.path.isdir(os.path.join(CACHE, old)):
                shutil.rmtree(os.path.join(CACHE, old), ignore_errors=True)
    link = os.path.join(tc, "llvm")
    if os.path.lexists(link):
        os.remove(link)
    os.symlink(d, link)
    with open(envfile, "a") as f:
        f.write(f"LLVM_VERSION={ver}\n")
    say("ok", f"LLVM {ver}: {d}")


# ------------------------------------------------------------------------- build
def run_build(repo, inputs_file, stop_after=None):
    chosen = json.load(open(inputs_file))
    t0 = time.time()

    try:
        free = shutil.disk_usage(HOME).free // 2**30
    except OSError:
        free = 999
    say("in", f"Ruang disk kosong: {free} GB")
    if free < 30 and os.environ.get("SKIP_DISK_CHECK") != "1":
        die("Ruang disk kurang dari 30 GB (kernel + LLVM + NDK + ccache). Hapus hasil lama dulu.")
    if os.path.isdir(WS):
        shutil.rmtree(WS)
    # folder kerja baru = salinan repo workflow (seperti actions/checkout)
    subprocess.run(["git", "clone", "-q", repo, WS], check=True)
    rev = subprocess.run(["git", "-C", WS, "log", "-1", "--format=%h %s"], capture_output=True, text=True).stdout.strip()
    say("ok", f"Workflow: {rev}")

    inputs_def, job = read_workflow(WS)
    inputs = {k: v.get("default", "" if v.get("type") != "boolean" else False) for k, v in inputs_def.items()}
    unknown = [k for k in chosen if k not in inputs]
    for k in unknown:
        say("wr", f"pilihan '{k}' sudah tidak ada di workflow - diabaikan")
    for k, v in chosen.items():
        if k in inputs:
            inputs[k] = (v if isinstance(v, bool) else str(v).lower() == "true") if inputs_def[k].get("type") == "boolean" else v
    for k, d in inputs_def.items():
        if d.get("type") == "choice" and str(inputs[k]) not in [str(o) for o in d["options"]]:
            die(f"'{inputs[k]}' bukan pilihan {k} yang valid lagi: {', '.join(map(str, d['options']))}")

    rundir = os.path.join(WS, ".runner")
    os.makedirs(rundir, exist_ok=True)
    envfile = os.path.join(rundir, "github_env")
    open(envfile, "w").close()
    setup_tools(bool(inputs.get("rekernel_ebpf")) and inputs.get("kernel_source", "").find("ORI") < 0)

    base = dict(os.environ)
    base["PATH"] = BIN + os.pathsep + base["PATH"]
    base.update({"GITHUB_WORKSPACE": WS, "GITHUB_ENV": envfile, "GITHUB_ACTOR": ACTOR,
                 "GITHUB_OUTPUT": os.path.join(rundir, "github_output"),
                 "GITHUB_STEP_SUMMARY": os.path.join(rundir, "step_summary"),
                 "RUNNER_TEMP": rundir, "RUNNER_OS": "Linux", "CI": "true"})
    for k, v in (("GIT_AUTHOR_NAME", "kingD2N"), ("GIT_COMMITTER_NAME", "kingD2N"),
                 ("GIT_AUTHOR_EMAIL", "114895723+kingD2N@users.noreply.github.com"),
                 ("GIT_COMMITTER_EMAIL", "114895723+kingD2N@users.noreply.github.com")):
        base.setdefault(k, v)
    ctx = Ctx(inputs, {}, WS)
    for k, v in (job.get("env") or {}).items():
        base[k] = ctx.subst(str(v))

    steps = [s for s in job["steps"] if not s.get("uses") and s.get("name") not in SKIP and s.get("run")]
    say("in", "Pilihan build: " + ", ".join(f"{k}={fmt(inputs[k])}" for k in chosen if k in inputs))
    for n, s in enumerate(steps, 1):
        fileenv = parse_env_file(envfile)
        ctx.env = {**{k: v for k, v in base.items()}, **fileenv}
        name = s.get("name", f"langkah {n}")
        if not ctx.cond(s.get("if")):
            print(f"{C['dm']}--- [{n}/{len(steps)}] {name}: dilewati (kondisi tidak terpenuhi){C['0']}", flush=True)
            continue
        print(f"\n{C['in']}▶ [{n}/{len(steps)}] {name}{C['0']}", flush=True)
        if name == LLVM_STEP:
            llvm_step(envfile)
            continue
        script = os.path.join(rundir, f"step{n:02d}.sh")
        with open(script, "w") as f:
            f.write(ctx.subst(s["run"]))
        env = {**base, **fileenv}
        for k, v in (s.get("env") or {}).items():
            env[k] = ctx.subst(str(v))
        ts = time.time()
        cwd = os.path.join(WS, ctx.subst(str(s["working-directory"]))) if s.get("working-directory") else WS
        p = subprocess.Popen(["bash", "--noprofile", "--norc", "-eo", "pipefail", script], cwd=cwd, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for raw in iter(p.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").rstrip("\n")
            m = re.match(r"^::(error|warning|notice)(?: [^:]*)?::(.*)$", line)
            if m:
                k = {"error": "er", "warning": "wr", "notice": "in"}[m.group(1)]
                say(k, m.group(2))
            elif line.startswith("::group::"):
                print(f"{C['dm']}== {line[9:]} =={C['0']}", flush=True)
            elif line.startswith("::endgroup::"):
                continue
            else:
                print(line, flush=True)
        rc = p.wait()
        dur = int(time.time() - ts)
        if rc != 0 and ctx.cond(s.get("continue-on-error", False)):
            say("wr", f"Langkah '{name}' gagal (kode {rc}) tapi boleh gagal (continue-on-error) - lanjut")
            continue
        if rc != 0:
            die(f"Langkah '{name}' gagal (kode {rc}) setelah {dur // 60}m{dur % 60:02d}s. Kirim log ini (~/build-kernel.log) untuk diperbaiki.")
        say("ok", f"{name} ({dur // 60}m{dur % 60:02d}s)")
        if stop_after and name == stop_after:
            say("wr", f"berhenti setelah '{name}' (--stop-after)")
            return

    # 2. Kumpulkan hasil
    env = parse_env_file(envfile)
    zips = sorted(f for f in os.listdir(WS) if f.endswith(".zip"))
    if not zips:
        die("Build selesai tapi zip AnyKernel3 tidak ditemukan")
    stamp = time.strftime("%Y%m%d_%H%M", time.gmtime())
    out = os.path.join(HASIL, f"{env.get('KERNEL_NAME', 'kernel')}-{stamp}")
    os.makedirs(out, exist_ok=True)
    files = [os.path.join(WS, z) for z in zips]
    for k in ("BAKASU_MANAGER_APK", "KSUN_MANAGER_APK"):
        if env.get(k):
            files.append(os.path.join(WS, env[k]))
    if fmt(env.get("FEAT_REKERNEL_EBPF")) == "true":
        files += [os.path.join(WS, "rekernel-ebpf-out", f) for f in ("rekernel.bpf.o", "rekerneld_aarch64")]
    files += [os.path.join(WS, "lkm-out", f) for f in env.get("LKM_KO", "").split()]
    for f in files:
        if os.path.isfile(f):
            shutil.copy2(f, out)
    feats = ", ".join(f"{k[5:].lower()}={env.get(k, '')}" for k in sorted(env) if k.startswith("FEAT_"))
    info = [f"Kernel      : {env.get('KERNEL_NAME', '')}",
            f"Source      : {env.get('KERNEL_SOURCE_URL', '')} @ {env.get('KERNEL_BRANCH', '')}",
            f"Kernel base : {env.get('KERNEL_BASE', '')}",
            f"KernelSU    : {env.get('FEAT_KSU_TYPE', '')}" + (f" @ {env['BAKASU_COMMIT']}" if env.get("BAKASU_COMMIT") else ""),
            f"Fitur       : {feats}",
            f"Manager APK : {env.get('BAKASU_MANAGER_INFO') or env.get('KSUN_MANAGER_INFO') or 'tidak dilampirkan'}",
            f"LLVM        : {env.get('LLVM_VERSION', '')}",
            f"Workflow    : {rev}",
            f"Dibuat      : {time.strftime('%Y-%m-%d %H:%M %Z')} di server ({os.uname().nodename})"]
    with open(os.path.join(out, "info-build.txt"), "w") as f:
        f.write("\n".join(info) + "\n")
    subprocess.run(f"cd '{out}' && sha256sum *.zip > sha256.txt", shell=True)
    with open(os.path.join(HASIL, ".terakhir"), "w") as f:
        f.write(out + "\n")
    dur = int(time.time() - t0)
    print()
    say("ok", f"Kernel selesai dalam {dur // 60} menit. Hasil: {out}")
    for l in info:
        print("   " + l)
    for f in sorted(os.listdir(out)):
        print(f"   - {f}")


# ------------------------------------------------------------------- menu (tanya)
DESC_SRC = {
    "Melt": "Melt-MIX untuk ROM AOSP (kernel utama)",
    "LineageOS 24": "kernel stock LineageOS 5.10 (ROM A16 & A17)",
    "LineageOS 24 (ORI)": "kernel LineageOS asli, tanpa tambahan apa pun",
    "Stock HyperOS": "Melt untuk HyperOS stock",
    "Avalon": "Avalon (ruik3z), LineageOS 23.2 + NetHunter",
    "Linux 6.6": "kernel 6.6 - hanya untuk ROM yang dibangun dengan 6.6",
}
FEATURES = [
    ("susfs", "SuSFS - sembunyikan root dari aplikasi bank/game"),
    ("BBG", "Baseband-guard - lindungi partisi penting"),
    ("rekernel_netlink", "Re-Kernel netlink - untuk aplikasi pembeku (NoActive dll.)"),
    ("rekernel_ebpf", "Re-Kernel eBPF - versi eBPF (butuh pahole di server)"),
    ("droidspaces", "DroidSpaces - container Linux"),
    ("nomount", "NoMount - module tanpa mount"),
]


def ask(prompt, default=""):
    try:
        v = input(f"{prompt}{f' [{default}]' if default != '' else ''}: ").strip()
    except EOFError:
        v = ""
    return v or default


def pick(title, items, default_idx=0, labels=None):
    print(f"\n{C['in']}== {title} =={C['0']}")
    for i, it in enumerate(items, 1):
        mark = f" {C['ok']}(bawaan){C['0']}" if i - 1 == default_idx else ""
        print(f"  {i:2d}) {labels[i - 1] if labels else it}{mark}")
    while True:
        v = ask("Nomor", str(default_idx + 1))
        if v.isdigit() and 1 <= int(v) <= len(items):
            return items[int(v) - 1]
        print("  Nomor tidak ada, coba lagi.")


def heads(url):
    try:
        r = subprocess.run(["git", "ls-remote", "--heads", url], capture_output=True, text=True, timeout=60)
        return sorted(l.split("refs/heads/", 1)[1] for l in r.stdout.splitlines() if "refs/heads/" in l)
    except Exception:
        return []


def run_menu(repo, out_file):
    o = options(repo)
    I, src = o["inputs"], o["sources"]
    sel = {}

    srcs = I["kernel_source"]["options"]
    lab = [f"{s:<20} {C['dm']}{DESC_SRC.get(s, '')}{C['0']}" for s in srcs]
    sel["kernel_source"] = pick("Pilih kernel", srcs, srcs.index(I["kernel_source"]["default"]), lab)
    url, dflt = src.get(sel["kernel_source"], ("", ""))
    ori = "ORI" in sel["kernel_source"]

    # hanya branch yang ada di daftar workflow DAN benar-benar ada di repo source ini
    hs = heads(url) if url else []
    allowed = [str(b) for b in I["kernel_branch"]["options"] if b != "auto" and str(b) in hs]
    if allowed:
        lab = [f"auto  {C['dm']}(= {dflt or 'branch default repo'}){C['0']}"] + allowed
        sel["kernel_branch"] = pick(f"Branch {url.rsplit('/', 1)[-1]}", ["auto"] + allowed, 0, lab)
    else:
        sel["kernel_branch"] = "auto"

    if ori:
        print(f"\n{C['wr']}{sel['kernel_source']}: KernelSU dan semua fitur tambahan otomatis mati.{C['0']}")
    else:
        ks = I["ksu_type"]["options"]
        sel["ksu_type"] = pick("Pilih KernelSU", ks, ks.index(I["ksu_type"]["default"]))
        st = {k: bool(I[k].get("default", False)) for k, _ in FEATURES if k in I}
        if not shutil.which("pahole") and st.get("rekernel_ebpf"):
            st["rekernel_ebpf"] = False
            say("wr", "pahole (dwarves) tidak ada di server - Re-Kernel eBPF dimatikan otomatis")
        while True:
            print(f"\n{C['in']}== Fitur tambahan =={C['0']}  (ketik nomor untuk menyalakan/mematikan, Enter = lanjut)")
            keys = [k for k, _ in FEATURES if k in st]
            for i, k in enumerate(keys, 1):
                d = dict(FEATURES)[k]
                print(f"  {i}) [{C['ok'] + 'x' + C['0'] if st[k] else ' '}] {d}")
            v = ask("Nomor (bisa beberapa, mis. 2 4)", "")
            if not v:
                break
            for t in re.split(r"[\s,]+", v):
                if t.isdigit() and 1 <= int(t) <= len(keys):
                    k = keys[int(t) - 1]
                    st[k] = not st[k]
                    if k == "rekernel_ebpf" and st[k] and not shutil.which("pahole"):
                        st[k] = False
                        say("wr", "pahole (dwarves) tidak ada di server - Re-Kernel eBPF tidak bisa dinyalakan")
        sel.update(st)

    names = I["custom_name"]["options"]
    sel["custom_name"] = pick("Nama kernel", names, names.index(I["custom_name"]["default"]))

    print(f"\n{C['in']}== Ringkasan =={C['0']}")
    for k, v in sel.items():
        print(f"  {k:<16} {fmt(v)}")
    with open(out_file, "w") as f:
        json.dump(sel, f, indent=1)
    if ask("Mulai build sekarang? (Y/n)", "Y").lower().startswith("n"):
        say("in", f"Pilihan disimpan ({out_file}), build tidak dimulai.")
        sys.exit(3)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    o = sp.add_parser("options"); o.add_argument("--repo", required=True)
    m = sp.add_parser("menu"); m.add_argument("--repo", required=True); m.add_argument("--out", required=True)
    b = sp.add_parser("build"); b.add_argument("--repo", required=True); b.add_argument("--inputs", required=True)
    b.add_argument("--stop-after")
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    if a.cmd == "options":
        print(json.dumps(options(repo), indent=1, default=str))
    elif a.cmd == "menu":
        run_menu(repo, a.out)
    else:
        run_build(repo, a.inputs, a.stop_after)


if __name__ == "__main__":
    main()
