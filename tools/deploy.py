"""Mirror dist/ to the robotmonaco.com web root over FTPS.

    FTP_HOST=... FTP_USER=... FTP_PASS=... python3 tools/deploy.py [--dry]

Server-side files we must not touch are listed in PROTECTED. Outside the directories in SWEPT,
anything on the server that is not in dist/ is left alone; inside them it is deleted, because those
directories are generated whole from the repository and a file dropped from the build should stop
being reachable rather than linger at its old URL.
"""
import ftplib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
PROTECTED = set()      # this site ships its own send.php, so nothing on the server is left alone
# Directories build.py writes in full. Nothing else puts files here, so a remote file that the build
# no longer produces is a leftover, not somebody's upload.
SWEPT = ("assets/photos", "assets/models", "assets/img")
DRY = "--dry" in sys.argv


def main():
    # .strip(): a credential pasted into a secrets field often carries a trailing newline or space
    host, user, pw = (os.environ[k].strip() for k in ("FTP_HOST", "FTP_USER", "FTP_PASS"))
    ftp = ftplib.FTP_TLS(host, timeout=60)
    try:
        ftp.login(user, pw)
    except (EOFError, ftplib.error_temp, ConnectionResetError) as ex:
        # The server hung up instead of answering PASS: usually brute-force protection after failed logins.
        raise SystemExit(f"FTP login was cut off by {host} ({type(ex).__name__}). The account is most likely "
                         "temporarily blocked after failed attempts; wait, or ask the host to unblock it.") from ex
    ftp.prot_p()
    ftp.set_pasv(True)
    known_dirs = {""}

    def ensure_dir(rel):
        if rel in known_dirs:
            return
        parent = rel.rsplit("/", 1)[0] if "/" in rel else ""
        ensure_dir(parent)
        try:
            ftp.mkd(rel)
        except ftplib.error_perm:
            pass                                   # exists
        known_dirs.add(rel)

    def remote_size(rel):
        try:
            return ftp.size(rel)
        except ftplib.error_perm:
            return None

    files = [p for p in DIST.rglob("*") if p.is_file() and p.name != ".DS_Store"]
    up = skip = 0
    total = 0
    for p in sorted(files):
        rel = p.relative_to(DIST).as_posix()
        if rel in PROTECTED:
            print("protected, skipped:", rel)
            continue
        size = p.stat().st_size
        # sitemaps and robots.txt go up under a temporary name and are renamed into place, so a crawler
        # fetching mid-deploy never sees a half-written file ("Sitemap could not be read" in Search Console)
        atomic = rel.endswith(".xml") or rel == "robots.txt"
        # Equal size means unchanged for content files, but the sitemap index rewrites only its <lastmod>
        # dates, which leaves the byte count identical, so these few small files always go up.
        if not atomic and remote_size(rel) == size:
            skip += 1
            continue
        if "/" in rel:
            ensure_dir(rel.rsplit("/", 1)[0])
        if not DRY:
            target = rel + ".part" if atomic else rel
            with open(p, "rb") as fh:
                ftp.storbinary(f"STOR {target}", fh)
            if atomic:
                try:
                    ftp.delete(rel)
                except ftplib.error_perm:
                    pass
                ftp.rename(target, rel)
        up += 1
        total += size
        print(("would upload" if DRY else "uploaded"), rel, f"{size / 1024:.0f} kB")

    # Sweep the generated directories, so a photo taken out of the gallery stops answering at its URL.
    shipped = {p.relative_to(DIST).as_posix() for p in files}
    gone = 0
    for d in SWEPT:
        try:
            remote = ftp.nlst(d)
        except ftplib.error_perm:
            continue                                # the directory does not exist on the server yet
        for entry in remote:
            rel = entry.split("/", 1)[1] if entry.startswith("/") else entry
            rel = rel if rel.startswith(d) else f"{d}/{rel.rsplit('/', 1)[-1]}"
            if rel in shipped or rel in PROTECTED or remote_size(rel) is None:
                continue                            # still built, protected, or a subdirectory
            if not DRY:
                try:
                    ftp.delete(rel)
                except ftplib.error_perm as ex:
                    print("could not delete", rel, ex)
                    continue
            gone += 1
            print(("would delete" if DRY else "deleted"), rel)

    ftp.quit()
    print(f"done: {up} uploaded ({total / 1e6:.1f} MB), {skip} unchanged, {gone} deleted, "
          f"{len(files)} files in dist")


if __name__ == "__main__":
    main()
