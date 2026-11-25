"""Translate the supplied pacifier vector into Android resources without redrawing it."""
from pathlib import Path
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "frontend/public/brand/symbol.svg"
RES = ROOT / "frontend/android/app/src/main/res"
ANDROID = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", ANDROID)


def attr(**values):
    return {f"{{{ANDROID}}}{key}": str(value) for key, value in values.items()}


def save(path, element):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(element, space="    ")
    ET.ElementTree(element).write(path, encoding="utf-8", xml_declaration=True)


def vector(paths, background=False, monochrome=False):
    root = ET.Element("vector", attr(width="108dp", height="108dp", viewportWidth=108, viewportHeight=108))
    if background:
        ET.SubElement(root, "path", attr(fillColor="#FFF5E7", pathData="M0,0 H108 V108 H0 Z"))
    scale = .07
    group = ET.SubElement(root, "group", attr(scaleX=scale, scaleY=scale, translateX=(108-860*scale)/2, translateY=(108-714*scale)/2))
    for path in paths:
        ET.SubElement(group, "path", attr(fillColor="#4F382E" if monochrome else path.attrib["fill"], pathData=path.attrib["d"]))
    return root


def main():
    source = ET.parse(SOURCE).getroot()
    assert source.attrib["viewBox"] == "0 0 860 714"
    paths = list(source.findall("{http://www.w3.org/2000/svg}path"))
    assert [p.attrib["id"] for p in paths] == ["shield", "connector", "handle"]
    assert len(paths) == 3
    for node in source.iter():
        assert node.tag.split("}")[-1] in {"svg", "title", "desc", "path"}
        assert not any(key.startswith("on") or key.endswith("href") for key in node.attrib)
    save(RES / "drawable/brand_launcher_foreground.xml", vector(paths))
    save(RES / "drawable/brand_monochrome.xml", vector(paths, monochrome=True))
    for name in ("ic_launcher", "ic_launcher_round"):
        save(RES / f"mipmap-anydpi/{name}.xml", vector(paths, background=True))
        for version in (26, 33):
            adaptive = ET.Element("adaptive-icon")
            ET.SubElement(adaptive, "background", attr(drawable="@color/brand_cream"))
            ET.SubElement(adaptive, "foreground", attr(drawable="@drawable/brand_launcher_foreground"))
            if version >= 33:
                ET.SubElement(adaptive, "monochrome", attr(drawable="@drawable/brand_monochrome"))
            save(RES / f"mipmap-anydpi-v{version}/{name}.xml", adaptive)
    splash = ET.Element("layer-list")
    ET.SubElement(splash, "item", attr(drawable="@color/brand_cream"))
    ET.SubElement(splash, "item", attr(drawable="@drawable/brand_launcher_foreground", gravity="center", width="216dp", height="216dp"))
    save(RES / "drawable/brand_splash.xml", splash)
    colors = ET.Element("resources")
    for name, value in {"brand_cream":"#FFF5E7", "brand_coral":"#DC8E85", "brand_cocoa":"#4F382E"}.items():
        ET.SubElement(colors, "color", {"name":name}).text = value
    save(RES / "values/brand_colors.xml", colors)
    out = ROOT / "artifacts/brand"
    out.mkdir(parents=True, exist_ok=True)
    (out / "asset-generation.json").write_text(json.dumps({"symbol_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),"paths":len(paths),"source":"user supplied vector", "wordmark":"original transparent PNG; supplied SVG text truncated"}, indent=2), encoding="utf-8")
    print("BRAND_ASSETS_PASS")


if __name__ == "__main__":
    main()
