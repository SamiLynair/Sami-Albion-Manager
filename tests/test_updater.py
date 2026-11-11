"""Update metadata, download integrity, and version checks without network."""

from __future__ import annotations

from hashlib import sha256
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from samialbion import __version__
from samialbion import updater

NEXT_VERSION = f"v{updater.parse_version(__version__)[0]}.{updater.parse_version(__version__)[1]}.{updater.parse_version(__version__)[2] + 1}"


class FakeResponse(io.BytesIO):
    status = 200

    def __init__(self, data, url):
        super().__init__(data)
        self._url = url

    def geturl(self):
        return self._url


class UpdaterTests(unittest.TestCase):
    @staticmethod
    def release_info(*, version=NEXT_VERSION, digest=None, url=None, size=13):
        return {
            "tag_name": version, "draft": False, "prerelease": False,
            "body": "Correctifs", "assets": [{
                "name": updater.RELEASE_ASSET,
                "size": size,
                "digest": digest or "sha256:" + "a" * 64,
                "browser_download_url": url or
                    f"https://github.com/SamiLynair/Sami-Albion-Manager/releases/download/{version}/Sami-Albion-Manager-Windows.exe",
            }],
        }

    def test_version_comparison_and_same_version(self):
        self.assertEqual(updater.parse_version("v0.3.2"), (0, 3, 2))
        self.assertEqual(updater.parse_version("0.3.12"), (0, 3, 12))
        self.assertIsNone(updater.parse_release(self.release_info(version=f"v{__version__}")))
        self.assertIsNotNone(updater.parse_release(self.release_info()))
        self.assertIsNone(updater.parse_release(self.release_info(version="v0.0.0")))
        with self.assertRaises(updater.UpdateError):
            updater.parse_version("0.3.3-beta")

    def test_rejects_untrusted_release_urls_and_missing_digests(self):
        with self.assertRaisesRegex(updater.UpdateError, "Adresse"):
            updater.parse_release(self.release_info(url="https://example.org/app.exe"))
        with self.assertRaisesRegex(updater.UpdateError, "SHA-256"):
            updater.parse_release(self.release_info(digest="sha256:invalid"))
        with self.assertRaisesRegex(updater.UpdateError, "taille"):
            updater.parse_release(self.release_info(size=0))

    def test_download_verifies_checksum_and_cleans_bad_files(self):
        payload = b"Not a real EXE"
        digest = sha256(payload).hexdigest()
        release = updater.parse_release(self.release_info(
            digest="sha256:" + digest, size=len(payload),
        ))
        self.assertIsNotNone(release)
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            with patch.object(updater, "staging_directory", return_value=folder):
                with patch.object(updater, "urlopen",
                                  side_effect=lambda *_a, **_k: FakeResponse(
                                      payload, "https://release-assets.githubusercontent.com/download")):
                    progress = []
                    downloaded = updater.download_release(release, report_progress=
                                                          lambda completed, total: progress.append((completed, total)))
                    self.assertEqual(downloaded.read_bytes(), payload)
                    self.assertEqual(progress[-1], (len(payload), len(payload)))
                    downloaded.unlink()
                    bad_release = updater.parse_release(self.release_info(
                        digest="sha256:" + "f" * 64, size=len(payload),
                    ))
                    with self.assertRaisesRegex(updater.UpdateError, "sécurité"):
                        updater.download_release(bad_release)
                    self.assertEqual(list(folder.iterdir()), [])

    def test_no_release_yet_is_not_an_error(self):
        from urllib.error import HTTPError
        with patch.object(updater, "urlopen", side_effect=HTTPError(
                updater.RELEASES_ENDPOINT, 404, "Not Found", None, None)):
            self.assertIsNone(updater.check_latest_release())

    def test_source_mode_cannot_replace_a_windows_exe(self):
        with self.assertRaises(updater.UpdateError):
            updater.start_windows_install(Path("does-not-exist.exe"),
                                          updater.parse_release(self.release_info()))

    def test_windows_helper_replaces_exe_only_after_parent_exits(self):
        old_bytes = b"Old compiled EXE"
        new_bytes = b"New compiled EXE"
        digest = sha256(new_bytes).hexdigest()
        release = updater.parse_release(self.release_info(
            digest="sha256:" + digest, size=len(new_bytes),
        ))
        with TemporaryDirectory() as directory:
            base = Path(directory)
            installed = base / "Sami Albion Manager.exe"
            downloaded = base / "downloaded.exe"
            installed.write_bytes(old_bytes)
            downloaded.write_bytes(new_bytes)
            with patch.object(updater.sys, "platform", "win32"), \
                 patch.object(updater.sys, "frozen", True, create=True), \
                 patch.object(updater.sys, "executable", str(installed)), \
                 patch.object(updater, "staging_directory", return_value=base), \
                 patch.object(updater.subprocess, "Popen") as subprocess_mock:
                updater.start_windows_install(downloaded, release)
                plan_path = next(base.glob("sami_update_plan_*.json"))
                self.assertEqual(installed.read_bytes(), old_bytes)
                with patch.object(updater, "_wait_for_old_exe_exit") as wait_mock:
                    updater.apply_update_plan(plan_path)
                    wait_mock.assert_called_once()
                self.assertEqual(installed.read_bytes(), new_bytes)
                self.assertEqual(len(list(base.glob("*.bak"))), 1)
                self.assertEqual(next(base.glob("*.bak")).read_bytes(), old_bytes)
                self.assertEqual(subprocess_mock.call_count, 2)

    def test_github_downloaded_exe_name_is_installable(self):
        self.assertIn(updater.RELEASE_ASSET.casefold(), updater.INSTALLABLE_EXE_NAMES)
        self.assertIn("sami albion manager.exe", updater.INSTALLABLE_EXE_NAMES)


if __name__ == "__main__":
    unittest.main()
