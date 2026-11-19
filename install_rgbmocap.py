#!/usr/bin/env python3
"""
RGB MoCap - one-click local installer (PixelArtistry)

What it does
  1. Checks your PC (64-bit Windows, NVIDIA GPU, free disk space)
  2. Downloads RGB MoCap by toyxyz (with git if you have it, otherwise as a ZIP)
  3. Runs the official base install (private Python runtimes, Blender, FFmpeg)
  4. Downloads every model file that is public (about 25 GB)
  5. Imports the files you had to register for (SMPL-X, MANO, SAM 3D Body ...)
     from the "gated_downloads" folder or your Downloads folder
  6. Writes the "Run_RGBMoCap" and "Update_RGBMoCap" launchers

Upstream project: https://github.com/toyxyz/toyxyz_RGBMocap  (app code: MIT, models: their own terms)
Run it via "Install_RGBMoCap.bat". Safe to run again: finished parts are skipped.
Only uses the Python standard library, so it runs before anything else is installed.
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT, "toyxyz_RGBMocap")
GATED_DIR = os.path.join(ROOT, "gated_downloads")
LOG = os.path.join(ROOT, "install_log.txt")
REPO_GIT = "https://github.com/toyxyz/toyxyz_RGBMocap.git"
REPO_ZIP = "https://github.com/toyxyz/toyxyz_RGBMocap/archive/refs/heads/main.zip"
ALL_TOOLS = ("exmr", "flowhmr", "gvhmr")
TOOL_LABEL = {"exmr": "ExMR", "flowhmr": "FlowHMR", "gvhmr": "GVHMR"}
RUNTIME_GIB = 33   # upstream asks for about 32.4 GiB free before the models
MODELS_GIB = 30    # public + registered model files for ExMR, FlowHMR and GVHMR
WORKER_PREFIX = "@@MOCAP@@"


# ----------------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------------
def log(msg=""):
    print(msg, flush=True)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass


def step(msg):
    log(f"\n=== {msg} ===")


def clean_env():
    """Environment for upstream tools: nothing from our own uv/venv may leak in."""
    env = dict(os.environ)
    for key in list(env):
        if key.upper().startswith("UV_") or key.upper() in ("VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"):
            env.pop(key)
    return env


def stream(cmd, cwd=None, on_event=None):
    """Run a command, show its output live, keep it in the log. Returns the exit code."""
    log("  > " + " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=cwd, env=clean_env(), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    buf = b""

    def handle(raw, transient):
        text = raw.decode("utf-8", "replace").rstrip()
        if not text:
            return
        if text.startswith(WORKER_PREFIX):
            try:
                event = json.loads(text[len(WORKER_PREFIX):])
            except ValueError:
                return
            if on_event:
                on_event(event)
            return
        if transient:  # progress bars: show, but keep them out of the log
            sys.stdout.write("\r    " + text[:100].ljust(100))
            sys.stdout.flush()
        else:
            log("    " + text)

    while True:
        chunk = proc.stdout.read1(65536)
        if not chunk:
            break
        buf += chunk
        while True:
            m = re.search(rb"[\r\n]", buf)
            if not m:
                break
            seg, sep, buf = buf[:m.start()], buf[m.start():m.end()], buf[m.end():]
            handle(seg, transient=(sep == b"\r" and not buf.startswith(b"\n")))
    handle(buf, False)
    return proc.wait()


def gib(n):
    return n / 1024 ** 3


# ----------------------------------------------------------------------------
# 1. PC check
# ----------------------------------------------------------------------------
def nvidia_gpu():
    exe = shutil.which("nvidia-smi") or os.path.join(
        os.environ.get("SystemRoot", r"C:\Windows"), "System32", "nvidia-smi.exe")
    try:
        out = subprocess.run([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    name, vram, driver = [p.strip() for p in out.stdout.strip().splitlines()[0].split(",")][:3]
    return name, int(float(vram)), driver


def preflight(args):
    if platform.system() != "Windows" or platform.machine().lower() not in ("amd64", "x86_64"):
        sys.exit("RGB MoCap only runs on 64-bit Windows.")
    gpu = nvidia_gpu()
    if gpu:
        name, vram, driver = gpu
        log(f"  GPU: {name}, {vram / 1024:.0f} GB VRAM, driver {driver}")
        if vram < 6000:
            log("  ! Less than 6 GB VRAM. RGB MoCap has a Low Memory mode, but this is untested.")
    elif args.skip_gpu_check:
        log("  ! No NVIDIA GPU found - continuing because of --skip-gpu-check.")
    else:
        sys.exit("No NVIDIA GPU found (nvidia-smi did not answer). RGB MoCap needs an NVIDIA GPU with a\n"
                 "current driver. If you do have one, update the driver and start the installer again.")
    installed = os.path.exists(os.path.join(APP_DIR, "SETUP_RECEIPT.json"))
    free = gib(shutil.disk_usage(ROOT).free)
    need = (0 if installed else RUNTIME_GIB) + (0 if args.no_models else MODELS_GIB)
    log(f"  Install folder: {ROOT}")
    log(f"  Free disk space: {free:.0f} GB (this install needs about {need} GB)")
    if not installed and free < RUNTIME_GIB + 2:
        sys.exit(f"Not enough free space. The program alone needs about {RUNTIME_GIB} GB, the models about\n"
                 f"{MODELS_GIB} GB more. Move this folder to a drive with at least {RUNTIME_GIB + MODELS_GIB} GB free.")
    if free < need:
        log("  ! Space is tight: the program fits, but probably not every model.")
    if len(ROOT) > 70:
        log("  ! This folder path is long. If the install fails, use a short one such as D:\\AI\\RGBMoCap.")


# ----------------------------------------------------------------------------
# 2. Download RGB MoCap
# ----------------------------------------------------------------------------
def download_repo():
    if os.path.exists(os.path.join(APP_DIR, "tools", "git_bootstrap.ps1")):
        log("  RGB MoCap is already downloaded - skipping.")
        return
    if os.path.exists(APP_DIR) and os.listdir(APP_DIR):
        sys.exit(f"The folder {APP_DIR} exists but is not a complete RGB MoCap download.\n"
                 "Rename or delete it and start the installer again.")
    if shutil.which("git"):  # git -> Update_RGBMoCap.bat works later
        if stream(["git", "clone", "--depth", "1", REPO_GIT, APP_DIR]) != 0:
            sys.exit("Could not download RGB MoCap with git. Check your internet connection and try again.")
        return
    log("  git is not installed - downloading a ZIP instead.")
    log("  (Works fine. Only Update_RGBMoCap.bat needs Git for Windows: https://git-scm.com/download/win)")
    zip_path = os.path.join(ROOT, "rgbmocap_main.zip")
    urllib.request.urlretrieve(REPO_ZIP, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        top = z.namelist()[0].split("/")[0]  # toyxyz_RGBMocap-main
        z.extractall(ROOT)
    os.replace(os.path.join(ROOT, top), APP_DIR)
    os.remove(zip_path)


# ----------------------------------------------------------------------------
# 3. Official base install
# ----------------------------------------------------------------------------
def base_install():
    powershell = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"),
                              "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    # Same command as upstream's install.cmd, without its "press any key" pause.
    cmd = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
           "-File", os.path.join(APP_DIR, "tools", "git_bootstrap.ps1")]
    for attempt in (1, 2, 3):
        if stream(cmd, cwd=APP_DIR) == 0:
            return
        if attempt < 3:
            log(f"\n  The install stopped (attempt {attempt} of 3). Finished parts are kept - trying again in 10 s ...")
            time.sleep(10)
    sys.exit("\nThe base install failed three times. Scroll up for the first error, or open install_log.txt.\n"
             "Most common causes: no internet, antivirus blocking downloads, not enough disk space.\n"
             "You can simply start Install_RGBMoCap.bat again - finished parts are kept.")


# ----------------------------------------------------------------------------
# 4 + 5. Models
# ----------------------------------------------------------------------------
def app_python():
    return os.path.join(APP_DIR, "runtime", "python.exe")


# Runs inside RGB MoCap's own Python and asks the app which files each model needs,
# so this list can never drift from what the app's Model Manager shows.
MODEL_QUERY = r'''
import json, sys
sys.path.insert(0, sys.argv[1])
from mocap.models import MODELS_LIST, STAGE_REQUIREMENTS, ready, manual_download_page
from mocap.motion_tools import MOTION_TOOLS
from mocap.flow_hamer import MODEL_KEYS as FLOW_HAMER_KEYS
need = lambda stages: {k for s in stages for k in STAGE_REQUIREMENTS.get(s, ())}
tools = {}
for name in sys.argv[2].split(","):
    tool = MOTION_TOOLS[name]
    core = need((*tool.stages(), "people"))
    every = need((*tool.stages(refine=True, footmr=True, handflow=True), "people"))
    if name == "flowhmr":
        every |= {"flow_metadata", *FLOW_HAMER_KEYS}
        core -= {"flow_vggt"}  # only the moving-camera mode needs it
    tools[name] = dict(core=sorted(core), extra=sorted(every - core))
wanted = {k for t in tools.values() for k in (*t["core"], *t["extra"])}
models = [dict(key=m.key, name=m.name, file=m.path.name, bytes=m.minimum_bytes,
               public=bool(m.drive_id or m.download_url), ready=ready(m), page=manual_download_page(m.key))
          for m in MODELS_LIST if m.key in wanted]
print("PA_JSON:" + json.dumps(dict(tools=tools, models=models)))
'''


def query_models(tools):
    out = subprocess.run([app_python(), "-I", "-X", "utf8", "-B", "-c", MODEL_QUERY, APP_DIR, ",".join(tools)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", env=clean_env())
    for line in out.stdout.splitlines():
        if line.startswith("PA_JSON:"):
            return json.loads(line[8:])
    sys.exit("Could not read the model list from RGB MoCap:\n" + (out.stderr or out.stdout)[-2000:])


def worker(stage, *extra):
    """RGB MoCap's own model worker: it verifies every file (size + SHA-256) before accepting it."""
    state = {"last": 0.0, "error": ""}

    def on_event(event):
        kind = event.get("type")
        if kind == "progress" and event.get("total"):
            now = time.monotonic()
            if now - state["last"] >= 1:
                state["last"] = now
                cur, total = event.get("current", 0), event["total"]
                sys.stdout.write(f"\r    {100 * cur / total:5.1f}%  {cur / 1e9:.2f} / {total / 1e9:.2f} GB".ljust(60))
                sys.stdout.flush()
        elif kind in ("failed", "error"):
            state["error"] = str(event.get("message", ""))
            log("    ! " + state["error"])

    code = stream([app_python(), "-I", "-X", "utf8", os.path.join(APP_DIR, "worker_boot.py"), stage, *extra],
                  cwd=APP_DIR, on_event=on_event)
    sys.stdout.write("\r" + " " * 70 + "\r")
    return code == 0


def download_public(info):
    todo = [m for m in info["models"] if m["public"] and not m["ready"]]
    if not todo:
        log("  All public model files are already there.")
        return []
    total = sum(m["bytes"] for m in todo)
    log(f"  {len(todo)} files, about {total / 1e9:.0f} GB. Every file is checked after download.")
    failed = []
    for i, m in enumerate(todo, 1):
        log(f"\n  [{i}/{len(todo)}] {m['name']}  ({m['bytes'] / 1e9:.2f} GB)")
        ok = worker("download", "--model", m["key"])
        if not ok:  # one retry: most failures are a dropped connection
            log("    Retrying once ...")
            time.sleep(5)
            ok = worker("download", "--model", m["key"])
        log("    OK" if ok else "    FAILED - see the list at the end")
        if not ok:
            failed.append(m)
    return failed


# --- registered ("gated") files ----------------------------------------------
# key -> (plain file name, archive name, path of the file inside that archive)
GATED = {
    "smplx":           ("SMPLX_NEUTRAL.npz", "models_smplx_v1_1.zip", "models/smplx/SMPLX_NEUTRAL.npz"),
    "mano_right":      ("MANO_RIGHT.pkl", "mano_v1_2.zip", "models/MANO_RIGHT.pkl"),
    "smplh":           (None, "smplh.tar.xz", "neutral/model.npz"),
    "flow_sam":        ("model.ckpt", None, None),
    "flow_sam_config": ("model_config.yaml", None, None),
    "flow_mhr":        ("mhr_model.pt", None, None),
    "flow_vggt":       ("vggt_omega_1b_512.pt", None, None),
}
HF_GATED = ("flow_sam", "flow_sam_config", "flow_mhr", "flow_vggt")


def name_matches(filename, wanted):
    """True for "model.ckpt" and browser duplicates such as "model (1).ckpt"."""
    stem, ext = os.path.splitext(wanted)
    return re.fullmatch(re.escape(stem) + r"( \(\d+\))?" + re.escape(ext), filename, re.I) is not None


def search_dirs():
    dirs = [(GATED_DIR, True)]  # (folder, also look into sub-folders)
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(downloads):
        dirs.append((downloads, False))
    return dirs


def find_file(wanted):
    for folder, deep in search_dirs():
        if not os.path.isdir(folder):
            continue
        for base, subdirs, files in os.walk(folder):
            if "_extracted" in subdirs:
                subdirs.remove("_extracted")
            for f in files:
                if name_matches(f, wanted):
                    yield os.path.join(base, f)
            if not deep:
                break


def extract_member(archive, inner, key):
    """Copy one file out of a ZIP / TAR.XZ into gated_downloads/_extracted/<key>/."""
    out_dir = os.path.join(GATED_DIR, "_extracted", key)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, os.path.basename(inner))
    if archive.lower().endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            member = next((n for n in z.namelist() if n.replace("\\", "/").endswith(inner)), None)
            if not member:
                return None
            with z.open(member) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
    else:
        with tarfile.open(archive, "r:*") as t:
            member = next((m for m in t if m.isfile() and m.name.replace("\\", "/").endswith(inner)), None)
            if not member:
                return None
            with t.extractfile(member) as src, open(out, "wb") as dst:
                shutil.copyfileobj(src, dst)
    return out


def local_candidates(m):
    """Files on this PC that could be this model, best guess first."""
    plain, archive, inner = GATED[m["key"]]
    pinned = m["key"] in HF_GATED  # these have one exact size
    if plain:
        for path in find_file(plain):
            size = os.path.getsize(path)
            if size < m["bytes"] or (pinned and size != m["bytes"]):
                continue
            yield path
    if m["key"] == "smplh":  # already-extracted folder: .../smplh/neutral/model.npz
        for path in find_file("model.npz"):
            if os.path.basename(os.path.dirname(path)).lower() == "neutral":
                yield path
    if archive:
        for path in find_file(archive):
            try:
                out = extract_member(path, inner, m["key"])
            except (OSError, zipfile.BadZipFile, tarfile.TarError) as e:
                log(f"    ! Could not open {os.path.basename(path)} ({e.__class__.__name__}) - is the download complete?")
                continue
            if out:
                yield out


def hf_token():
    for var in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        if os.environ.get(var):
            return os.environ[var].strip()
    home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    try:
        with open(os.path.join(home, "token"), encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


class _KeepAuthOnSameHost(urllib.request.HTTPRedirectHandler):
    """Hugging Face redirects to a download server: never send the login there."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            new.headers = {k: v for k, v in new.headers.items() if k.lower() != "authorization"}
        return new


def hf_download(m, token):
    """Fetch a gated Hugging Face file with the user's own login. Returns a path or None."""
    url = m["page"].replace("/blob/", "/resolve/", 1)
    out_dir = os.path.join(GATED_DIR, "hf")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, m["file"])
    if os.path.exists(out) and os.path.getsize(out) == m["bytes"]:
        return out
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "User-Agent": "rgbmocap-installer"})
    opener = urllib.request.build_opener(_KeepAuthOnSameHost)
    try:
        with opener.open(req, timeout=60) as resp, open(out + ".part", "wb") as dst:
            total, done, last = int(resp.headers.get("Content-Length") or 0), 0, 0.0
            while True:
                chunk = resp.read(8 * 1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
                done += len(chunk)
                if total and time.monotonic() - last >= 1:
                    last = time.monotonic()
                    sys.stdout.write(f"\r    {100 * done / total:5.1f}%  {done / 1e9:.2f} / {total / 1e9:.2f} GB".ljust(60))
                    sys.stdout.flush()
        sys.stdout.write("\r" + " " * 70 + "\r")
        os.replace(out + ".part", out)
        return out
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            log("    No access yet: open the model page, sign in and accept the terms, then run Import_Models.bat again.")
        else:
            log(f"    Hugging Face answered with error {e.code}.")
    except (urllib.error.URLError, OSError) as e:
        log(f"    Download failed ({e.__class__.__name__}).")
    return None


def import_gated(info):
    todo = [m for m in info["models"] if not m["public"] and not m["ready"] and m["key"] in GATED]
    if not todo:
        log("  All registered model files are already imported.")
        return
    os.makedirs(GATED_DIR, exist_ok=True)
    token = hf_token()
    for m in todo:
        done = False
        for path in local_candidates(m):
            log(f"\n  {m['name']}: found {path}")
            if worker("import_model", "--model", m["key"], "--video", path):
                log("    Imported.")
                done = True
                break
            log("    Not the right file (wrong version or incomplete) - skipped.")
        if not done and token and m["key"] in HF_GATED:
            log(f"\n  {m['name']}: downloading with your Hugging Face login ({m['bytes'] / 1e9:.2f} GB)")
            path = hf_download(m, token)
            if path and worker("import_model", "--model", m["key"], "--video", path):
                log("    Imported.")


# ----------------------------------------------------------------------------
# 6. Launchers + summary
# ----------------------------------------------------------------------------
def write_launchers():
    files = {
        "Run_RGBMoCap.bat":
            '@echo off\r\ntitle RGB MoCap\r\ncd /d "%~dp0toyxyz_RGBMocap"\r\n'
            'echo Starting RGB MoCap - keep this window open while you use the app.\r\n'
            'call RGBMoCap.cmd %*\r\n',
        "Update_RGBMoCap.bat":
            '@echo off\r\ntitle RGB MoCap - Update\r\ncd /d "%~dp0toyxyz_RGBMocap"\r\n'
            'echo Close RGB MoCap before updating.\r\n'
            'call update.cmd %*\r\n',
    }
    for name, text in files.items():
        with open(os.path.join(ROOT, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)
    os.makedirs(GATED_DIR, exist_ok=True)
    with open(os.path.join(GATED_DIR, "PUT_FILES_HERE.txt"), "w", encoding="utf-8") as f:
        f.write("Put the model files you had to register for into this folder, then double-click\n"
                "Import_Models.bat one folder up. Leave ZIP and TAR.XZ files as they are - no need to unpack.\n\n"
                "  models_smplx_v1_1.zip   (SMPL-X)\n  mano_v1_2.zip           (MANO)\n"
                "  smplh.tar.xz            (SMPL-H, for FlowHMR)\n"
                "  model.ckpt, model_config.yaml, mhr_model.pt   (SAM 3D Body)\n"
                "  vggt_omega_1b_512.pt    (optional, FlowHMR moving camera)\n\n"
                "The README explains where each file comes from.\n")


GATED_HELP = [
    (("smplx",), "SMPL-X body model  -  https://smpl-x.is.tue.mpg.de/download.php",
     ['Register (free), sign in, then under "SMPL-X Model" click',
      '"Download SMPL-X v1.1 (NPZ+PKL, 830 MB)"  ->  models_smplx_v1_1.zip']),
    (("mano_right", "smplh"), "MANO hand model + SMPL-H  -  https://mano.is.tue.mpg.de/download.php",
     ['Register (free), sign in, then under "Models & Code" download',
      '"Models & Code"  ->  mano_v1_2.zip',
      '"Extended SMPL+H model (used in AMASS project)"  ->  smplh.tar.xz   (only FlowHMR needs this one)']),
    (("flow_sam", "flow_sam_config", "flow_mhr"),
     "SAM 3D Body  -  https://huggingface.co/facebook/sam-3d-body-dinov3",
     ["Sign in to Hugging Face, accept the terms on that page and wait for access. Then download",
      "model.ckpt, model_config.yaml and assets/mhr_model.pt - or log in once with",
      '"hf auth login" and Import_Models.bat downloads the three files for you.']),
    (("flow_vggt",), "VGGT-Omega (optional: FlowHMR with a moving camera)  -  https://huggingface.co/facebook/VGGT-Omega",
     ["Same as SAM 3D Body: accept the terms, then download vggt_omega_1b_512.pt."]),
]


def summary(info, failed_public):
    by_key = {m["key"]: m for m in info["models"]}
    step("Result")
    for name, tool in info["tools"].items():
        missing = [by_key[k] for k in tool["core"] if not by_key[k]["ready"]]
        extra = [by_key[k] for k in tool["extra"] if not by_key[k]["ready"]]
        if not missing:
            line = "READY"
            if extra:
                line += "  (optional add-ons missing: " + ", ".join(m["file"] for m in extra) + ")"
        else:
            line = "needs " + ", ".join(m["file"] for m in missing)
        log(f"  {TOOL_LABEL.get(name, name):8} {line}")

    if failed_public:
        log("\n  These public downloads failed (often Google Drive's daily limit):")
        for m in failed_public:
            log(f"    - {m['name']}: {m['page']}")
        log("  Start Import_Models.bat again later, or download them in your browser and use")
        log("  Model Manager > Import inside RGB MoCap.")

    missing_gated = {m["key"] for m in info["models"] if not m["public"] and not m["ready"]}
    if missing_gated:
        log("\n  STILL TO DO - files you have to register for yourself (free, takes a few minutes;")
        log("  the licences do not allow anyone to hand them to you):")
        for keys, title, lines in GATED_HELP:
            if missing_gated & set(keys):
                log(f"\n    {title}")
                for line in lines:
                    log(f"      {line}")
        log(f"\n  Put the files into:  {GATED_DIR}")
        log("  (or just leave them in your Downloads folder) and double-click Import_Models.bat.")
        log("  ZIP and TAR.XZ files can stay packed - the importer takes out what it needs.")
    else:
        log("\n  Everything is in place. Double-click Run_RGBMoCap.bat to start.")


def main():
    parser = argparse.ArgumentParser(description="RGB MoCap one-click installer (PixelArtistry)")
    parser.add_argument("--models-only", action="store_true", help="only download/import model files")
    parser.add_argument("--no-models", action="store_true", help="install the program without model files")
    parser.add_argument("--tools", default=",".join(ALL_TOOLS),
                        help="which motion models to prepare, e.g. exmr or exmr,flowhmr (default: all three)")
    parser.add_argument("--skip-gpu-check", action="store_true")
    args = parser.parse_args()
    tools = [t.strip().lower() for t in args.tools.split(",") if t.strip()]
    unknown = [t for t in tools if t not in ALL_TOOLS]
    if unknown or not tools:
        sys.exit("--tools accepts: " + ", ".join(ALL_TOOLS))

    log("\n" + "=" * 70)
    log("RGB MoCap - one-click installer (PixelArtistry)   " + time.strftime("%Y-%m-%d %H:%M"))
    if args.models_only:
        if not os.path.exists(app_python()):
            sys.exit("RGB MoCap is not installed yet. Run Install_RGBMoCap.bat first.")
    else:
        step("1/5 Checking your PC")
        preflight(args)
        step("2/5 Downloading RGB MoCap")
        download_repo()
        step("3/5 Installing the program (official installer: Python runtimes, Blender, FFmpeg)")
        log("  This downloads about 8 GB and takes 10-30 minutes. No need to do anything.")
        base_install()
        write_launchers()

    if args.no_models:
        log("\nProgram installed. Model files were skipped (--no-models).")
        return
    info = query_models(tools)
    step("4/5 Downloading the public model files")
    failed = download_public(info)
    step("5/5 Importing the files you registered for")
    import_gated(info)
    summary(query_models(tools), failed)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nCancelled. Start the installer again to continue - finished parts are kept.")
