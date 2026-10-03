"""Check bilingual page coverage and repository-local Markdown/HTML links.

No network requests or model downloads. Does not assess translation quality.
"""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def main():
    errors = []
    english = {p.name for p in (ROOT / "docs/en").glob("*.md")}
    chinese = {p.name for p in (ROOT / "docs/zh-CN").glob("*.md")}
    if english != chinese:
        errors.append(f"Missing guide counterparts: {sorted(english ^ chinese)}")
    for name in ("README", "CONTRIBUTING", "SECURITY", "CHANGELOG"):
        for suffix in (".md", ".zh-CN.md"):
            if not (ROOT / (name + suffix)).is_file():
                errors.append(f"Missing policy page: {name}{suffix}")
    pages = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").rglob("*.md"))
    for page in pages:
        content = page.read_text()
        # Fenced code is example text, not navigable Markdown.
        content = re.sub(r"```.*?```", "", content, flags=re.S)
        links = re.findall(r"\]\(([^\s)]+)\)", content)
        links += re.findall(r'(?:src|href)="([^"]+)"', content)
        for link in links:
            target = urlsplit(link)
            if target.scheme or target.netloc or not target.path:
                continue
            path = (page.parent / unquote(target.path)).resolve()
            if not path.is_relative_to(ROOT) or not path.exists():
                errors.append(f"{page.relative_to(ROOT)}: broken local link {link}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"Checked {len(pages)} documentation pages; locales and local links are consistent.")


if __name__ == "__main__":
    main()
