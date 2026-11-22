"""Atualizações a partir dos releases do GitHub (sem dependência de GTK).

Fluxo:
  1. fetch_latest() consulta a API do GitHub e devolve o último release
     (rascunhos e pré-lançamentos são ignorados pela própria API).
  2. A versão do release vem do nome do pacote anexado
     (msensor-tester-<pkgver>-<pkgrel>-any.pkg.tar.zst); se não houver pacote,
     usa a tag (v1.2.0 ou 1.2.0). is_newer() compara com installed_version(),
     que pergunta ao pacman o que está de fato instalado.
  3. download() baixa o pacote para ~/.cache/msensor-tester/updates e confere o
     tamanho e o SHA-256 informados pelo GitHub.
  4. install() instala com "pkexec pacman -U", que pede a senha numa janela
     do sistema (polkit).
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import APP_SLUG, APP_VERSION
from .debuglog import log
from .i18n import _

REPO = "narayanls/msensor-tester"
API_LATEST = os.environ.get("MSENSOR_UPDATE_URL",  # permite testar com outro servidor
                            f"https://api.github.com/repos/{REPO}/releases/latest")
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
INSTALL_DIR = Path("/usr/share") / APP_SLUG
TIMEOUT = 20
CHUNK = 64 * 1024

PACKAGE_RE = re.compile(
    r"^msensor-tester-(?P<pkgver>[^-]+)-(?P<pkgrel>[^-]+)-any\.pkg\.tar\.(?:zst|xz)$")


class UpdateError(Exception):
    """Falha com mensagem pronta para mostrar ao usuário."""


class UpdateCancelled(Exception):
    pass


@dataclass
class Release:
    version: str          # pkgver, para exibir (ex.: 1.2.0)
    full_version: str     # pkgver-pkgrel quando há pacote, para comparar (ex.: 1.2.0-1)
    page_url: str
    notes: str
    asset_name: str | None = None
    asset_url: str | None = None
    asset_size: int = 0
    sha256: str | None = None


# ------------------------------------------------------------------ versões
def parse_version(value: str) -> tuple[tuple[int, ...], int | None]:
    """'v1.10.2' -> ((1, 10, 2), None); '1.10.2-3' -> ((1, 10, 2), 3)."""
    value = value.strip().lstrip("vV").split(":")[-1]  # ignora a época do pacman
    ver, _sep, rel = value.partition("-")
    numbers = tuple(int(n) for n in re.findall(r"\d+", ver))
    rel_match = re.match(r"\d+", rel)
    return numbers, int(rel_match.group()) if rel_match else None


def is_newer(remote: str, local: str) -> bool:
    """O pkgrel só desempata quando as duas versões o informam."""
    (r_ver, r_rel), (l_ver, l_rel) = parse_version(remote), parse_version(local)
    if r_ver != l_ver:
        return r_ver > l_ver
    return r_rel is not None and l_rel is not None and r_rel > l_rel


def installed_version() -> str:
    """Versão instalada segundo o pacman (ex.: '1.2.0-1').

    É a fonte confiável: não depende do código já carregado na memória.
    Rodando pelo código-fonte (ou sem pacman), usa a constante APP_VERSION.
    """
    if install_support() != "source" and shutil.which("pacman"):
        try:
            result = subprocess.run(["pacman", "-Q", APP_SLUG],
                                    capture_output=True, text=True, timeout=10)
            parts = result.stdout.split()
            if result.returncode == 0 and len(parts) == 2:
                return parts[1]
        except (OSError, subprocess.TimeoutExpired):
            pass
    return APP_VERSION


def display_version(full: str) -> str:
    """'1.2.0-1' -> '1.2.0' (o pkgrel só interessa para comparar)."""
    return full.split(":")[-1].split("-")[0]


# ------------------------------------------------------------------ consulta
def _open(url: str, accept: str):
    req = urllib.request.Request(url, headers={
        "Accept": accept,
        "User-Agent": f"{APP_SLUG}/{APP_VERSION}",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    return urllib.request.urlopen(req, timeout=TIMEOUT)


def fetch_latest() -> Release:
    try:
        with _open(API_LATEST, "application/vnd.github+json") as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as exc:
        log.debug("atualização: HTTP %s em %s", exc.code, API_LATEST)
        if exc.code == 404:
            raise UpdateError(_("No release has been published yet.")) from exc
        if exc.code in (403, 429):
            raise UpdateError(_("GitHub is limiting requests right now. Try again later.")) from exc
        raise UpdateError(_("Could not check for updates (HTTP {code}).").format(code=exc.code)) from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.debug("atualização: falha ao consultar %s: %r", API_LATEST, exc)
        raise UpdateError(
            _("Could not check for updates. Check your internet connection.")) from exc

    tag_version = str(data.get("tag_name") or "").lstrip("vV")
    release = Release(
        version=tag_version,
        full_version=tag_version,
        page_url=str(data.get("html_url") or RELEASES_PAGE),
        notes=str(data.get("body") or "").strip(),
    )
    for asset in data.get("assets") or []:
        match = PACKAGE_RE.match(str(asset.get("name", "")))
        if not match:
            continue
        digest = str(asset.get("digest") or "")
        release.version = match["pkgver"]
        release.full_version = f'{match["pkgver"]}-{match["pkgrel"]}'
        release.asset_name = asset["name"]
        release.asset_url = asset.get("browser_download_url")
        release.asset_size = int(asset.get("size") or 0)
        release.sha256 = digest[7:].lower() if digest.startswith("sha256:") else None
        break
    if not release.version:
        raise UpdateError(_("The latest release has no version number."))
    log.debug("atualização: último release %s (pacote: %s)", release.full_version, release.asset_name)
    return release


# --------------------------------------------------------------- instalação
def install_support() -> str:
    """'ok' ou o motivo de não poder instalar: 'source', 'pacman', 'pkexec'."""
    here = Path(__file__).resolve().parent.parent
    if here != INSTALL_DIR:
        return "source"
    if not shutil.which("pacman"):
        return "pacman"
    if not shutil.which("pkexec"):
        return "pkexec"
    return "ok"


def _download_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(Path.home(), ".cache")
    return Path(base) / APP_SLUG / "updates"


def download(release: Release, progress=None, cancel: threading.Event | None = None) -> Path:
    """Baixa o pacote. progress(fração 0..1 ou None) é chamado na thread atual."""
    if not release.asset_url or not release.asset_name:
        raise UpdateError(_("This release has no package to install."))

    directory = _download_dir()
    shutil.rmtree(directory, ignore_errors=True)  # sobras de tentativas antigas
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / release.asset_name
    partial = target.with_name(target.name + ".part")

    sha = hashlib.sha256()
    received = 0
    try:
        with _open(release.asset_url, "application/octet-stream") as resp, open(partial, "wb") as fh:
            total = release.asset_size or int(resp.headers.get("Content-Length") or 0)
            while True:
                if cancel is not None and cancel.is_set():
                    raise UpdateCancelled()
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                fh.write(chunk)
                sha.update(chunk)
                received += len(chunk)
                if progress:
                    progress(received / total if total else None)
    except UpdateCancelled:
        partial.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        log.debug("atualização: download falhou: %r", exc)
        raise UpdateError(_("The download failed. Check your internet connection.")) from exc

    if release.asset_size and received != release.asset_size:
        partial.unlink(missing_ok=True)
        raise UpdateError(_("The download is incomplete. Try again."))
    if release.sha256 and sha.hexdigest() != release.sha256:
        partial.unlink(missing_ok=True)
        raise UpdateError(_("The downloaded file is corrupted (checksum mismatch). Try again."))
    partial.rename(target)
    return target


def install(package: Path) -> None:
    """Instala o pacote com pacman, pedindo a senha de administrador via polkit."""
    pkexec, pacman = shutil.which("pkexec"), shutil.which("pacman")
    if not pkexec or not pacman:
        raise UpdateError(_("Automatic installation requires pacman and pkexec."))
    try:
        try:
            result = subprocess.run([pkexec, pacman, "-U", "--noconfirm", str(package)],
                                    capture_output=True, text=True)
        except OSError as exc:
            raise UpdateError(str(exc)) from exc
        if result.returncode in (126, 127):
            # 126: janela de senha cancelada; 127: não autorizado / sem agente polkit
            detail = result.stderr.strip()
            raise UpdateError(_("Authorization was not granted.") + (f"\n{detail}" if detail else ""))
        if result.returncode != 0:
            output = (result.stderr.strip() or result.stdout.strip()).splitlines()
            raise UpdateError(_("pacman could not install the update:") + "\n" + "\n".join(output[-6:]))
    finally:
        package.unlink(missing_ok=True)
