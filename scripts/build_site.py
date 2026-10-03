#!/usr/bin/env python3
"""Build the dependency-free, bilingual GitHub Pages site."""

import argparse
import json
import shutil
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site"
REPO_URL = "https://github.com/yeshan333/tingsub"


def build(output: Path, site_url: str) -> None:
    """Render pages; write only named site files, never delete an output tree."""
    site_url = site_url.rstrip("/")
    parsed = urlsplit(site_url)
    if parsed.scheme != "https" or not parsed.netloc or parsed.query or parsed.fragment:
        raise ValueError("--site-url must be an absolute HTTPS URL without query or fragment")
    content = json.loads((SOURCE / "content.json").read_text())
    template = Template((SOURCE / "index.html").read_text())
    assets = output / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ("style.css", "site.js", "icon.svg", "coast.svg"):
        shutil.copyfile(SOURCE / name, assets / name)
    for path in (ROOT / "docs/assets/screenshots").glob("*.png"):
        shutil.copyfile(path, assets / path.name)
    for lang, data in content.items():
        page = output if lang == "zh-CN" else output / "en"
        page.mkdir(parents=True, exist_ok=True)
        values = {
            key: escape(value, quote=True) for key, value in data.items() if isinstance(value, str)
        }
        for key in ("product_title", "workspace_title", "setup_title", "end_title"):
            values[f"{key}_html"] = values[key].replace("\n", "<br>")
        values.update(
            lang=lang,
            other_lang="en" if lang == "zh-CN" else "zh-CN",
            prefix="" if lang == "zh-CN" else "../",
            home="./",
            language_url="en/" if lang == "zh-CN" else "../",
            site_url=escape(site_url),
            canonical=escape(site_url + ("/" if lang == "zh-CN" else "/en/")),
        )
        for key, filename in {
            "install": "installation",
            "distribution": "distribution",
            "docs": "README",
            "privacy": "privacy",
            "models": "models",
        }.items():
            values[f"{key}_url"] = f"{REPO_URL}/blob/main/docs/{lang}/{filename}.md"
        values["facts_html"] = "".join(
            f'<div class="fact"><strong>{escape(item["value"])}</strong>'
            f"<p>{escape(item['label'])}</p></div>"
            for item in data["facts"]
        )
        values["features_html"] = "".join(
            f'<article class="feature"><span class="feature-number">{escape(item["number"])}</span>'
            f"<div><h3>{escape(item['title'])}</h3><p>{escape(item['body'])}</p></div></article>"
            for item in data["features"]
        )
        values["requirements_html"] = "".join(
            f"<li>{escape(item)}</li>" for item in data["requirements"]
        )
        values["steps_html"] = "".join(
            f"<li><h3>{escape(item['title'])}</h3><p>{escape(item['body'])}</p></li>"
            for item in data["steps"]
        )
        values["faq_html"] = "".join(
            f"<details><summary>{escape(item['q'])}</summary><p>{escape(item['a'])}</p></details>"
            for item in data["faq"]
        )
        (page / "index.html").write_text(template.substitute(values), encoding="utf-8")
    (output / ".nojekyll").touch()
    (output / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{escape(site_url)}/</loc></url>"
        f"<url><loc>{escape(site_url)}/en/</loc></url></urlset>\n",
        encoding="utf-8",
    )
    print(f"Built Chinese and English pages in {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/site")
    parser.add_argument("--site-url", default="https://yeshan333.github.io/tingsub")
    args = parser.parse_args()
    build(args.output, args.site_url)
