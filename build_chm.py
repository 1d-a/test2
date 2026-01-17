from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


DOT_JP = "\u30fb"  # '・' (often shows as '?')
DOT_CN = "\u00b7"  # '·'
CATEGORY_SEP = "\u3001"  # '、'

BOLD_RE = re.compile(r"^\*\*(.+)\*\*$")
SUBCATEGORY_RE = re.compile(r"^(\d+)\.\s*(.+)$")
PAGE_BOLD_NUM_RE = re.compile(r"^\d+$")
SCREENSHOT_RE = re.compile(r"^==Screenshot for page\s*\d+==\s*$")


@dataclass
class Group:
    title: str
    entries: list[str]
    file: str = ""


@dataclass
class Subcategory:
    title: str
    groups: list[Group] = field(default_factory=list)
    file: str = ""


@dataclass
class Category:
    title: str
    subcategories: list[Subcategory] = field(default_factory=list)
    file: str = ""


def _normalize_group_title(title: str) -> str:
    return (
        title.replace(DOT_JP, DOT_CN)
        .replace("?", DOT_CN)
        .replace("\u00a0", " ")
        .strip()
    )


def _normalize_entry(line: str) -> str:
    s = line.strip()
    if not s:
        return ""
    if s.startswith("***"):
        return ""
    if s.startswith("==") and s.endswith("=="):
        return ""
    s = re.sub(r"\s*\d+\s*$", "", s).strip()
    return s


def parse_markdown(path: Path) -> list[Category]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    categories: list[Category] = []
    cur_cat: Category | None = None
    cur_sub: Subcategory | None = None
    cur_group_title: str | None = None
    cur_entries: list[str] = []

    def flush_group() -> None:
        nonlocal cur_group_title, cur_entries, cur_sub
        if cur_group_title and cur_sub:
            cur_sub.groups.append(
                Group(title=_normalize_group_title(cur_group_title), entries=cur_entries)
            )
        cur_group_title = None
        cur_entries = []

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if SCREENSHOT_RE.match(line):
            continue

        m = BOLD_RE.match(line)
        if m:
            title = m.group(1).strip()
            if PAGE_BOLD_NUM_RE.match(title):
                continue

            # Drop top-level numeric headings like "10 分类细目"
            if re.match(r"^\d+\s+", title) and not SUBCATEGORY_RE.match(title):
                flush_group()
                continue

            # Category headings: e.g. "一、人体类"
            if CATEGORY_SEP in title and title.endswith("类") and not SUBCATEGORY_RE.match(title):
                flush_group()
                cur_cat = Category(title=title)
                categories.append(cur_cat)
                cur_sub = None
                continue

            # Subcategory headings: e.g. "1. 手臂动作"
            sm = SUBCATEGORY_RE.match(title)
            if sm:
                flush_group()
                if not cur_cat:
                    # Unexpected structure; create an implicit category to avoid dropping data.
                    cur_cat = Category(title="未分类")
                    categories.append(cur_cat)
                cur_sub = Subcategory(title=f"{sm.group(1)}. {sm.group(2).strip()}")
                cur_cat.subcategories.append(cur_sub)
                continue

            # Group heading
            flush_group()
            cur_group_title = title
            continue

        if cur_group_title:
            normalized = _normalize_entry(line)
            if normalized:
                cur_entries.append(normalized)

    flush_group()
    return categories


def _write_text(path: Path, content: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding=encoding, newline="\r\n")


def build_site(categories: list[Category], out_dir: Path) -> tuple[list[str], list[Category]]:
    site_dir = out_dir / "site"
    site_dir.mkdir(parents=True, exist_ok=True)

    # Assign filenames
    for cat_idx, cat in enumerate(categories, start=1):
        cat.file = f"c{cat_idx:02d}.html"
        for sub_idx, sub in enumerate(cat.subcategories, start=1):
            sub.file = f"c{cat_idx:02d}_s{sub_idx:02d}.html"

    group_id = 0
    for cat in categories:
        for sub in cat.subcategories:
            for group in sub.groups:
                group_id += 1
                group.file = f"g{group_id:04d}.html"

    css = """\
:root { color-scheme: light; }
body { font-family: -apple-system, BlinkMacSystemFont, \"Segoe UI\", Arial, \"Noto Sans SC\", \"Microsoft YaHei\", sans-serif; margin: 20px; line-height: 1.5; }
a { color: #0b57d0; text-decoration: none; }
a:hover { text-decoration: underline; }
h1 { font-size: 22px; margin: 0 0 10px; }
.meta { color: #555; margin: 0 0 14px; }
pre.entries { background: #f6f8fa; border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; white-space: pre-wrap; }
ul { margin: 8px 0 0 18px; }
li { margin: 4px 0; }
"""
    _write_text(site_dir / "style.css", css, encoding="utf-8")

    def page(title: str, body_html: str) -> str:
        return f"""\
<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{html.escape(title)}</title>
  <link rel=\"stylesheet\" href=\"style.css\" />
</head>
<body>
{body_html}
</body>
</html>
"""

    # index.html
    index_items = []
    for cat in categories:
        count = sum(len(sub.groups) for sub in cat.subcategories)
        index_items.append(
            f"<li><a href=\"{html.escape(cat.file)}\">{html.escape(cat.title)}</a>（{count} 组）</li>"
        )
    index_body = f"""\
<h1>分类细目动词词表</h1>
<p class=\"meta\">按左侧目录选择分类，或从下方进入。</p>
<ul>
  {'\\n  '.join(index_items)}
</ul>
"""
    _write_text(site_dir / "index.html", page("分类细目动词词表", index_body), encoding="utf-8")

    # Category & subcategory pages
    for cat in categories:
        sub_items = []
        for sub in cat.subcategories:
            sub_items.append(
                f"<li><a href=\"{html.escape(sub.file)}\">{html.escape(sub.title)}</a>（{len(sub.groups)} 组）</li>"
            )
        cat_body = f"""\
<h1>{html.escape(cat.title)}</h1>
<p class=\"meta\">包含 {len(cat.subcategories)} 个子类。</p>
<ul>
  {'\\n  '.join(sub_items)}
</ul>
"""
        _write_text(site_dir / cat.file, page(cat.title, cat_body), encoding="utf-8")

        for sub in cat.subcategories:
            group_items = []
            for g in sub.groups:
                group_items.append(
                    f"<li><a href=\"{html.escape(g.file)}\">{html.escape(g.title)}</a></li>"
                )
            sub_body = f"""\
<h1>{html.escape(sub.title)}</h1>
<p class=\"meta\">所属：<a href=\"{html.escape(cat.file)}\">{html.escape(cat.title)}</a></p>
<ul>
  {'\\n  '.join(group_items)}
</ul>
"""
            _write_text(site_dir / sub.file, page(sub.title, sub_body), encoding="utf-8")

            for g in sub.groups:
                entries_block = "【" + "\n".join(g.entries) + "】"
                g_body = f"""\
<h1>{html.escape(g.title)}</h1>
<p class=\"meta\">所属：<a href=\"{html.escape(cat.file)}\">{html.escape(cat.title)}</a> / <a href=\"{html.escape(sub.file)}\">{html.escape(sub.title)}</a></p>
<pre class=\"entries\">{html.escape(entries_block)}</pre>
"""
                _write_text(site_dir / g.file, page(g.title, g_body), encoding="utf-8")

    # Collect files for HHP
    files: list[str] = []
    for path in sorted(site_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(out_dir).as_posix().replace("/", "\\")
            files.append(rel)
    return files, categories


def write_hhc(categories: list[Category], out_path: Path, *, encoding: str) -> None:
    def obj(name: str, local: str | None) -> str:
        parts = [f'    <param name=\"Name\" value=\"{html.escape(name)}\">']
        if local:
            parts.append(f'    <param name=\"Local\" value=\"{html.escape(local)}\">')
        return (
            "  <LI> <OBJECT type=\"text/sitemap\">\n"
            + "\n".join(parts)
            + "\n  </OBJECT>\n"
        )

    lines: list[str] = []
    lines.append("<!DOCTYPE HTML PUBLIC \"-//IETF//DTD HTML//EN\">")
    lines.append("<HTML>")
    lines.append("<HEAD>")
    lines.append("<meta name=\"GENERATOR\" content=\"build_chm.py\">")
    lines.append("</HEAD><BODY>")
    lines.append("<OBJECT type=\"text/site properties\">")
    lines.append("  <param name=\"ImageType\" value=\"Folder\">")
    lines.append("</OBJECT>")
    lines.append("<UL>")

    for cat in categories:
        lines.append(obj(cat.title, f"site\\{cat.file}").rstrip("\n"))
        lines.append("  <UL>")
        for sub in cat.subcategories:
            lines.append(obj(sub.title, f"site\\{sub.file}").rstrip("\n"))
            lines.append("    <UL>")
            for g in sub.groups:
                lines.append(obj(g.title, f"site\\{g.file}").rstrip("\n"))
            lines.append("    </UL>")
        lines.append("  </UL>")

    lines.append("</UL>")
    lines.append("</BODY></HTML>")
    _write_text(out_path, "\n".join(lines), encoding=encoding)


def write_hhp(files: list[str], out_path: Path, *, encoding: str) -> None:
    content = []
    content.append("[OPTIONS]")
    content.append("Compatibility=1.1")
    content.append("Compiled file=output.chm")
    content.append("Contents file=contents.hhc")
    content.append("Default topic=site\\index.html")
    content.append("Display compile progress=No")
    content.append("Full-text search=Yes")
    content.append("Language=0x804 Chinese (PRC)")
    content.append("Title=分类细目动词词表")
    content.append("")
    content.append("[FILES]")
    content.extend(files)
    _write_text(out_path, "\n".join(content), encoding=encoding)


def main(argv: list[str]) -> int:
    in_path: Path
    if len(argv) >= 2:
        in_path = Path(argv[1])
    else:
        md_files = sorted(Path(".").glob("*.md"))
        if not md_files:
            print("No .md file found in current directory.", file=sys.stderr)
            return 2
        in_path = md_files[0]

    out_dir = Path("chm_build")
    categories = parse_markdown(in_path)
    files, categories = build_site(categories, out_dir)

    # Write TOC + project in ANSI-compatible encoding for HTML Help Workshop.
    encoding = "mbcs"
    write_hhc(categories, out_dir / "contents.hhc", encoding=encoding)
    write_hhp(files, out_dir / "project.hhp", encoding=encoding)

    total_groups = sum(len(sub.groups) for cat in categories for sub in cat.subcategories)
    print(f"OK: categories={len(categories)} subcategories={sum(len(c.subcategories) for c in categories)} groups={total_groups}")
    print(f"Build dir: {out_dir.resolve()}")
    print(f"Project:   {(out_dir / 'project.hhp').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

