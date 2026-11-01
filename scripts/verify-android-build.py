"""Check the built debug package itself; this does not install or launch it."""
import hashlib
from html import unescape
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
apk = root / "artifacts/android/modu-yuga-debug.apk"
digest = hashlib.sha256(apk.read_bytes()).hexdigest()
assert digest == (apk.parent / "apk-sha256.txt").read_text().strip().lower()
with zipfile.ZipFile(apk) as archive:
    assert {"AndroidManifest.xml", "classes.dex"} <= set(archive.namelist())
    html = unescape(archive.read("assets/public/index.html").decode("utf-8"))
    assert 0 <= html.index('http-equiv="Content-Security-Policy"') < html.index("<script")
    assert "script-src 'self'" in html and "unsafe-eval" not in html
    # Verify the shipped brand files, not only the source tree.
    for asset in ("symbol.svg", "wordmark.png"):
        assert archive.read("assets/public/brand/" + asset) == (root / "frontend/public/brand" / asset).read_bytes()
    assert "모두의 육아 - 육아템 공동구매,핫딜" in html
    config = json.loads(archive.read("assets/capacitor.config.json"))
    assert config["appId"] == "kr.moduyuga.app" and config["appName"] == "모두의 육아 - 육아템 공동구매,핫딜"
result = {"sha256": digest, "bytes": apk.stat().st_size, "cspPrecedesScript": True,
          "name": config["appName"], "packageId": config["appId"], "brandAssetsMatchSource": True,
          "scope": "debug package contents only; Android runtime not verified"}
(apk.parent / "package-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("ANDROID_PACKAGE_CHECK_PASS")
print(json.dumps(result, ensure_ascii=False))
