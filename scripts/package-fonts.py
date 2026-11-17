#!/usr/bin/env python3
"""Verify Punchcutter output and assemble the repository fonts and release ZIPs."""

import base64
import json
import re
from pathlib import Path
from shutil import copy2
from zipfile import ZIP_DEFLATED, ZipFile

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
RELEASES = BUILD / "releases"
VERSION = "1.0.0"
LICENSE = ROOT / "OFL.txt"
REQUIRED = set(map(ord, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789àèéìòùæœß"))
CARDS = [
    ("trivulzio-quill", "Leonardo da Vinci", "Disegno, misura e prospettiva", "TRIVULZIANUS  /  FOLIO 30r", "#f1e3cb", "#38271d"),
    ("chawton-script", "Jane Austen", "A letter for the morning", "LADY SUSAN  /  PAGE 28", "#e9dedf", "#422636"),
    ("arles-letter", "Vincent van Gogh", "La lumière de la chambre", "ARLES  /  16 OCTOBER 1888", "#eadfa8", "#3f3a21"),
    ("monticello-draft", "Thomas Jefferson", "Life, liberty & happiness", "ROUGH DRAFT  /  JUNE 1776", "#e1e6de", "#2c453f"),
]


def require(condition, message):
    if not condition:
        raise SystemExit(message)


def verify_binary(path, family):
    with TTFont(path) as font:
        cmap = font.getBestCmap()
        require(REQUIRED <= set(cmap), f"Incomplete Latin character map: {path}")
        require(font["name"].getBestFamilyName() == family, f"Wrong family name: {path}")
        require(font["name"].getDebugName(13) and "SIL OPEN FONT LICENSE" in font["name"].getDebugName(13),
                f"Missing embedded OFL: {path}")
        require(font["name"].getDebugName(14) == "https://openfontlicense.org/", f"Missing OFL URL: {path}")
        require("Qiaomu Fonts contributors" in (font["name"].getDebugName(0) or ""), f"Missing copyright: {path}")
        require({"GPOS", "GSUB"} <= set(font.keys()), f"Missing OpenType tables: {path}")
        head, metrics = font["head"], font["OS/2"]
        require(metrics.usWinAscent >= head.yMax and metrics.usWinDescent >= -head.yMin,
                f"Clipped vertical metrics: {path}")
        return cmap


def set_text(canvas, text, xy, size, max_width, ink, font_path=None):
    draw = ImageDraw.Draw(canvas)
    if font_path is None:
        font = ImageFont.load_default(size=size)
    else:
        font = ImageFont.truetype(font_path, size)
        while font.getlength(text) > max_width:
            size -= 1
            font = ImageFont.truetype(font_path, size)
    left, top, _, _ = font.getbbox(text)
    draw.text((xy[0] - left, xy[1] - top), text, fill=ink, font=font)


def specimen(card, font_path, compact=False):
    slug, author, sample, source, paper, ink = card
    width, height = (620, 286) if compact else (1400, 800)
    canvas = Image.new("RGB", (width, height), paper)
    draw = ImageDraw.Draw(canvas)
    left = 40 if compact else 80
    max_width = width - left * 2
    set_text(canvas, source, (left, 29 if compact else 53), 15 if compact else 23, max_width, ink)
    set_text(canvas, author, (left, 69 if compact else 132), 93 if compact else 155, max_width, ink, font_path)
    draw.line((left, 177 if compact else 325, width - left, 177 if compact else 325), fill=ink, width=1)
    set_text(canvas, sample, (left, 205 if compact else 374), 58 if compact else 99, max_width, ink, font_path)
    if not compact:
        set_text(canvas, "Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm", (left, 526), 73, max_width, ink, font_path)
        set_text(canvas, "Nn Oo Pp Qq Rr Ss Tt Uu Vv Ww Xx Yy Zz", (left, 602), 73, max_width, ink, font_path)
        set_text(canvas, "0123456789   À É È Ô Ù   à è é ô ù   Æ æ Œ œ", (left, 691), 58, max_width, ink, font_path)
    return canvas


def read_build(card):
    slug = card[0]
    src = ROOT / "sources" / slug
    build = BUILD / slug
    family = json.loads((src / "spec.json").read_text())["family"]
    files = sorted(path for path in (build / "fonts").glob("*/*") if path.suffix in {".ttf", ".otf", ".woff2"})
    require(len(files) == 3 and {path.suffix for path in files} == {".ttf", ".otf", ".woff2"},
            f"Expected TTF, OTF and WOFF2: {family}")
    maps = [verify_binary(path, family) for path in files]
    require(maps[0] == maps[1] == maps[2], f"Unicode coverage differs between formats: {family}")
    report = (build / "report.md").read_text()
    require(re.search(r"25 checks on 2 files: 25 pass, 0 warn, 0 fail", report) is not None,
            f"Punchcutter checks failed: {family}")
    print(f"{family}: {len(maps[0])} mapped characters in each of three files, 25 checks passed")
    return slug, src, build, files


def package(card, verified):
    slug, src, build, files = verified
    target = ROOT / "fonts" / slug
    css = next((build / "fonts").glob("*.css"))
    for path in [*files, css]:
        destination = target / path.relative_to(build / "fonts")
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(path, destination)

    ttf = next(path for path in files if path.suffix == ".ttf")
    proof = ROOT / "specimens" / f"{slug}.png"
    specimen(card, ttf).save(proof, optimize=True)
    zip_path = RELEASES / f"{slug}.zip"
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        def add(path, entry):
            archive.write(path, f"{slug}/{entry}")

        for path in [*files, css, build / "fonts/studio.html", build / "fonts/README.md"]:
            add(path, path.relative_to(build))
        for path in [LICENSE, proof, build / "proof.png", build / "report.md"]:
            add(path, path.name)
        add(ROOT / "docs/sources.md", "docs/sources.md")
        for path in (build / "sources").rglob("*"):
            if path.is_file():
                add(path, path.relative_to(build))
        for path in src.iterdir():
            if path.suffix in {".json", ".py"}:
                add(path, Path("sources") / slug / path.name)
        add(ROOT / "sources/pen_paths.py", "sources/pen_paths.py")
        if slug == "trivulzio-quill":
            template_path = src / "mirror.html.in"
            add(template_path, Path("sources") / slug / template_path.name)
            template = template_path.read_text()
            require(template.count("__WOFF2__") == 1, "Expected one webfont slot in mirror template")
            woff = next(path for path in files if path.suffix == ".woff2")
            payload = base64.b64encode(woff.read_bytes()).decode()
            archive.writestr(f"{slug}/mirror.html", template.replace("__WOFF2__", payload))
    with ZipFile(zip_path) as archive:
        require(archive.testzip() is None, f"Corrupt ZIP: {zip_path}")
    return specimen(card, ttf, compact=True), zip_path


def main():
    verified = [read_build(card) for card in CARDS]
    RELEASES.mkdir(parents=True, exist_ok=True)
    gallery = Image.new("RGB", (1280, 640), "#edeae3")
    family_archives = []
    for index, (card, built) in enumerate(zip(CARDS, verified)):
        tile, archive = package(card, built)
        gallery.paste(tile, (16 + 628 * (index % 2), 30 + 294 * (index // 2)))
        family_archives.append(archive)
    gallery.save(ROOT / "specimens/collection.png", optimize=True)

    combined = RELEASES / f"qiaomu-fonts-v{VERSION}.zip"
    with ZipFile(combined, "w", ZIP_DEFLATED) as archive:
        archive.write(LICENSE, LICENSE.name)
        archive.write(ROOT / "README.md", "README.md")
        archive.write(ROOT / "docs/sources.md", "docs/sources.md")
        for proof in sorted((ROOT / "specimens").glob("*.png")):
            archive.write(proof, proof.relative_to(ROOT))
        for family_zip in family_archives:
            with ZipFile(family_zip) as family:
                for entry in family.namelist():
                    archive.writestr(entry, family.read(entry))
    with ZipFile(combined) as archive:
        require(archive.testzip() is None, f"Corrupt ZIP: {combined}")


if __name__ == "__main__":
    main()
