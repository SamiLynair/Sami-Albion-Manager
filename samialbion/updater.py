"""GitHub Releases updater, with a separate process for replacing Windows EXEs.

All gameplay data remains offline. Only this module contacts GitHub, and only
when checking for or downloading a requested application update.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from . import __version__

REPOSITORY = "SamiLynair/Sami-Albion-Manager"
RELEASES_ENDPOINT = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RELEASE_ASSET = "Sami-Albion-Manager-Windows.exe"
INSTALLABLE_EXE_NAMES = {"sami albion manager.exe", RELEASE_ASSET.casefold()}
UPDATE_HELPER_FLAG = "--sami-apply-update"
MAX_RELEASE_BYTES = 400 * 1024 * 1024
USER_AGENT = f"Sami-Albion-Manager/{__version__}"
VERSION_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$", re.IGNORECASE)
SHA256_PATTERN = re.compile(r"^sha256:([0-9a-f]{64})$", re.IGNORECASE)


class UpdateError(Exception):
    """An update cannot be safely downloaded or installed."""


@dataclass(frozen=True)
class Release:
    version: str
    notes: str
    download_url: str
    sha256_digest: str
    size: int


def parse_version(value: str) -> tuple[int, int, int]:
    match = VERSION_PATTERN.fullmatch(value.strip())
    if match is None:
        raise UpdateError(f"Numéro de version non reconnu : {value!r}")
    return tuple(int(part) for part in match.groups())


def parse_release(info: dict, *, current_version: str = __version__) -> Release | None:
    """Only accept a newer, published version with our exact Windows asset."""
    if not isinstance(info, dict) or info.get("draft") or info.get("prerelease"):
        return None
    tag = str(info.get("tag_name", ""))
    if parse_version(tag) <= parse_version(current_version):
        return None
    assets = info.get("assets", [])
    if not isinstance(assets, list):
        raise UpdateError("La liste des fichiers de cette version est invalide.")
    asset = next((x for x in assets if isinstance(x, dict) and
                  x.get("name") == RELEASE_ASSET), None)
    if asset is None:
        raise UpdateError("Cette version ne contient pas encore le programme Windows.")
    url = str(asset.get("browser_download_url", ""))
    expected_prefix = f"/{REPOSITORY}/releases/download/"
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "github.com" or not parts.path.startswith(expected_prefix):
        raise UpdateError("Adresse de téléchargement non reconnue.")
    digest_match = SHA256_PATTERN.fullmatch(str(asset.get("digest", "")))
    if digest_match is None:
        raise UpdateError("L'empreinte de sécurité SHA-256 est absente ou invalide.")
    size = asset.get("size", 0)
    if not isinstance(size, int) or not (0 < size <= MAX_RELEASE_BYTES):
        raise UpdateError("La taille du programme à télécharger est invalide.")
    return Release(tag.lstrip("vV"), str(info.get("body") or ""), url,
                   digest_match.group(1).lower(), size)


def check_latest_release(*, current_version: str = __version__) -> Release | None:
    request = Request(RELEASES_ENDPOINT, headers={
        "Accept": "application/vnd.github+json", "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urlopen(request, timeout=12) as response:
            if response.status != 200:
                raise UpdateError(f"GitHub a répondu avec le code {response.status}.")
            content = response.read(1024 * 1024)
            if response.read(1):
                raise UpdateError("La réponse de GitHub est trop volumineuse.")
            data = json.loads(content)
    except HTTPError as exc:
        if exc.code == 404:
            # A brand-new public repository may not have any releases yet.
            return None
        raise UpdateError(f"GitHub a répondu avec le code {exc.code}.") from exc
    except (OSError, ValueError) as exc:
        raise UpdateError(f"Impossible de vérifier les mises à jour : {exc}") from exc
    return parse_release(data, current_version=current_version)


def staging_directory() -> Path:
    base = Path(os.getenv("LOCALAPPDATA") or tempfile.gettempdir())
    target = base / "SamiAlbionManager" / "updates"
    target.mkdir(parents=True, exist_ok=True)
    return target


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download_release(release: Release, *, report_progress=None, is_cancelled=None) -> Path:
    """Stream a release to a temporary .part file; verify hash before use."""
    target_dir = staging_directory()
    destination = target_dir / f"Sami-Albion-Manager-{release.version}-{uuid4().hex}.exe"
    partial = destination.with_suffix(".part")
    hash_state = sha256()
    completed = 0
    request = Request(release.download_url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=20) as response, partial.open("xb") as output:
            final_url = urlsplit(response.geturl())
            # GitHub release downloads redirect to its own asset CDN.
            if final_url.scheme != "https" or final_url.hostname not in {
                "github.com", "release-assets.githubusercontent.com",
                "objects.githubusercontent.com",
            }:
                raise UpdateError("Redirection du téléchargement non reconnue.")
            while True:
                if is_cancelled and is_cancelled():
                    raise UpdateError("Téléchargement annulé.")
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                completed += len(chunk)
                if completed > MAX_RELEASE_BYTES or completed > release.size:
                    raise UpdateError("Le fichier reçu dépasse la taille annoncée.")
                output.write(chunk)
                hash_state.update(chunk)
                if report_progress:
                    report_progress(completed, release.size)
        if completed != release.size or hash_state.hexdigest() != release.sha256_digest:
            raise UpdateError("Vérification de sécurité échouée : fichier incomplet ou modifié.")
        partial.replace(destination)
        return destination
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def start_windows_install(downloaded: Path, release: Release) -> None:
    """Start a second copy of the *old* exe to replace this exe after exit."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise UpdateError("L'installation automatique nécessite la version Windows .exe.")
    target = Path(sys.executable).resolve()
    if target.name.casefold() not in INSTALLABLE_EXE_NAMES:
        raise UpdateError("Nom de l'application installée inattendu.")
    if not downloaded.is_file() or file_sha256(downloaded) != release.sha256_digest:
        raise UpdateError("Le fichier téléchargé n'a pas passé la vérification de sécurité.")
    token = uuid4().hex
    stage = staging_directory()
    helper = stage / f"sami_update_helper_{token}.exe"
    plan = stage / f"sami_update_plan_{token}.json"
    try:
        shutil.copy2(target, helper)
        plan.write_text(json.dumps({
            "parent_pid": os.getpid(),
            "target": str(target),
            "downloaded": str(downloaded.resolve()),
            "expected_sha256": release.sha256_digest,
            "backup": str(target.with_name(f"{target.stem}.before-{release.version}-{token}.bak")),
        }), encoding="utf-8")
        subprocess.Popen([str(helper), UPDATE_HELPER_FLAG, str(plan)],
                         cwd=str(stage), close_fds=True,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, ValueError) as exc:
        plan.unlink(missing_ok=True)
        helper.unlink(missing_ok=True)
        raise UpdateError(f"Impossible de préparer l'installation : {exc}") from exc


def _wait_for_old_exe_exit(pid: int, timeout_ms: int = 90000) -> None:
    if sys.platform != "win32":
        return
    import ctypes
    SYNCHRONIZE = 0x00100000
    WAIT_TIMEOUT = 0x00000102
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
    if handle:
        try:
            result = kernel32.WaitForSingleObject(handle, timeout_ms)
            if result == WAIT_TIMEOUT:
                raise UpdateError("L'ancienne application ne s'est pas fermée à temps.")
            if result != 0:
                raise UpdateError("Impossible de surveiller la fermeture de l'application.")
        finally:
            kernel32.CloseHandle(handle)


def apply_update_plan(plan_path: Path) -> None:
    """Runs from a copied helper EXE. Never runs inside the installed EXE."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise UpdateError("Ce programme de mise à jour est réservé à Windows.")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    target = Path(plan["target"]).resolve()
    downloaded = Path(plan["downloaded"]).resolve()
    backup = Path(plan["backup"]).resolve()
    if target.name.casefold() not in INSTALLABLE_EXE_NAMES or target == backup:
        raise UpdateError("Destination de mise à jour refusée.")
    if not downloaded.is_file() or not re.fullmatch(r"[0-9a-f]{64}", str(plan["expected_sha256"])):
        raise UpdateError("Fichier de mise à jour non conforme.")
    if file_sha256(downloaded) != plan["expected_sha256"]:
        raise UpdateError("L'empreinte SHA-256 ne correspond plus au téléchargement.")
    _wait_for_old_exe_exit(int(plan["parent_pid"]))
    # Antivirus software may keep the old .exe briefly locked after exit.
    for attempt in range(60):
        try:
            target.replace(backup)
            break
        except PermissionError:
            if attempt == 59:
                raise
            time.sleep(0.5)
    try:
        downloaded.replace(target)
        subprocess.Popen([str(target)], cwd=str(target.parent), close_fds=True)
    except Exception:
        # Keep the previous executable recoverable if installation fails.
        if target.exists() and backup.exists():
            target.unlink()
        if backup.exists():
            backup.replace(target)
        raise
    finally:
        plan_path.unlink(missing_ok=True)


def maybe_run_update_helper(argv: list[str]) -> bool:
    if len(argv) != 2 or argv[0] != UPDATE_HELPER_FLAG:
        return False
    try:
        apply_update_plan(Path(argv[1]))
    except Exception as exc:
        # The app is windowed; leave an error report next to its update plan.
        error_log = Path(argv[1]).with_suffix(".error.txt")
        error_log.write_text(f"Échec de la mise à jour : {exc}", encoding="utf-8")
        raise SystemExit(1) from exc
    return True
