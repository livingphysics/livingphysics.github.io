#!/usr/bin/env python3
"""Convert the 'Cell Learning' Notion export into a Quarto website.

- main doc            -> index.qmd
- People <id>.md      -> people/index.qmd
- People/<x>.md       -> people/<slug>.qmd   (Author Template excluded)
- References/<x>.md   -> references/<slug>.qmd
- References <id>.csv -> references/index.qmd (rendered table)
- *.pdf               -> files/   (the "included files" folder)
- *.png               -> images/
- raw export          -> _notion_source/ (kept as backup, ignored by Quarto)

Inline links are rewritten: page->page links become .qmd links with correct
relative paths; reference-database links point at references/index; image and
PDF links point at the new asset folders. Self-links (Notion placeholders) are
flattened to plain text.
"""
import os, re, csv, json, glob, shutil, urllib.parse

ROOT   = "/home/davidjordan/docs/quarto/cell_learning"
# Raw Notion export, relocated under a '_'-prefixed dir so Quarto ignores it.
SRC    = os.path.join(ROOT, "_notion_source")
if not os.path.isdir(SRC):                       # fall back to the original name
    SRC = os.path.join(ROOT, "Private & Shared")
CL     = os.path.join(SRC, "Cell Learning")
MAIN   = glob.glob(os.path.join(SRC, "Cell Learning *.md"))[0]

FILES  = os.path.join(ROOT, "files")
IMAGES = os.path.join(ROOT, "images")
PEOPLE = os.path.join(ROOT, "people")
REFS   = os.path.join(ROOT, "references")
for d in (FILES, IMAGES, PEOPLE, REFS):
    os.makedirs(d, exist_ok=True)

NOTION_ID = re.compile(r" [0-9a-f]{32}$")
EXCLUDE_PEOPLE = {"Author Template"}
IMAGE_RENAME = {"Untitled.png": "repeat-expansion.png",
                "Untitled 1.png": "learning-modes.png"}

def strip_id(stem):           # stem = filename without extension
    return NOTION_ID.sub("", stem).strip()

def slugify(s):
    s = strip_id(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")

def yaml_str(s):              # JSON is a valid YAML scalar; handles quotes/colons
    return json.dumps(s, ensure_ascii=False)

def clean_title(s):           # drop BibTeX case-protection braces for display
    return (s or "").replace("{", "").replace("}", "").strip()

# ---------------------------------------------------------------- path map
# absolute source path -> new site-relative path (posix)
path_map = {}

path_map[os.path.normpath(MAIN)] = "index.qmd"

people_index = glob.glob(os.path.join(CL, "People *.md"))
if people_index:
    path_map[os.path.normpath(people_index[0])] = "people/index.qmd"

person_srcs = []
for p in sorted(glob.glob(os.path.join(CL, "People", "*.md"))):
    stem = os.path.splitext(os.path.basename(p))[0]
    if strip_id(stem) in EXCLUDE_PEOPLE:
        continue
    path_map[os.path.normpath(p)] = f"people/{slugify(stem)}.qmd"
    person_srcs.append(p)

ref_srcs = []
ref_slugs = set()
for p in sorted(glob.glob(os.path.join(CL, "References", "*.md"))):
    stem = os.path.splitext(os.path.basename(p))[0]
    if strip_id(stem) == "Untitled":
        continue
    slug = slugify(stem)
    path_map[os.path.normpath(p)] = f"references/{slug}.qmd"
    ref_srcs.append(p)
    ref_slugs.add(slug)

for c in glob.glob(os.path.join(CL, "References *.csv")):
    path_map[os.path.normpath(c)] = "references/index.qmd"

# --------------------------------------------------------------- assets
def move_asset(src, dest_dir, new_name):
    dst = os.path.join(dest_dir, new_name)
    if os.path.exists(src) and not os.path.exists(dst):
        shutil.copy2(src, dst)          # copy now; source relocated to backup later
    return new_name

for pdf in glob.glob(os.path.join(CL, "*.pdf")):
    move_asset(pdf, FILES, os.path.basename(pdf))
for png in glob.glob(os.path.join(CL, "*.png")):
    base = os.path.basename(png)
    move_asset(png, IMAGES, IMAGE_RENAME.get(base, slugify(os.path.splitext(base)[0]) + ".png"))

ASSET_PREFIXES = ("files/", "images/", "people/", "references/", "http://",
                  "https://", "mailto:", "#")

unmapped = []

def rewrite_target(target, src_abs, new_path):
    """Return rewritten link target, or None to flatten the link to text."""
    if target.startswith(ASSET_PREFIXES):
        return target
    if "://" in target or target.startswith("mailto:"):
        return target
    frag = ""
    if "#" in target:
        target, frag = target.split("#", 1)
        frag = "#" + frag
    dec = urllib.parse.unquote(target)
    ext = os.path.splitext(dec)[1].lower()

    if ext in (".png", ".jpg", ".jpeg", ".gif", ".svg"):
        base = os.path.basename(dec)
        name = IMAGE_RENAME.get(base, slugify(os.path.splitext(base)[0]) + ext)
        return os.path.relpath(os.path.join(IMAGES, name),
                               os.path.dirname(os.path.join(ROOT, new_path)))

    abspath = os.path.normpath(os.path.join(os.path.dirname(src_abs), dec))

    if ext == ".pdf":
        return os.path.relpath(os.path.join(FILES, os.path.basename(dec)),
                               os.path.dirname(os.path.join(ROOT, new_path)))

    if abspath in path_map:
        tgt_new = path_map[abspath]
        if tgt_new == new_path:                 # self-link -> flatten
            return None
        rel = os.path.relpath(os.path.join(ROOT, tgt_new),
                              os.path.dirname(os.path.join(ROOT, new_path)))
        return rel + frag

    unmapped.append((new_path, target))
    return None                                  # unknown -> flatten to text

LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)]+)\)")

def rewrite_links(body, src_abs, new_path):
    def repl(m):
        bang, text, target = m.group(1), m.group(2), m.group(3).strip()
        if bang == "!":                          # image
            nt = rewrite_target(target, src_abs, new_path)
            return f"![{text}]({nt})" if nt else text
        nt = rewrite_target(target, src_abs, new_path)
        return f"[{text}]({nt})" if nt else text
    return LINK_RE.sub(repl, body)

def split_h1(text):
    """Return (title, body-without-leading-H1-and-dividers)."""
    lines = text.splitlines()
    title = None
    out = []
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].startswith("# "):
        title = lines[i][2:].strip()
        i += 1
    # drop leading blank lines and '---' divider artifacts
    while i < len(lines) and (lines[i].strip() == "" or re.fullmatch(r"-{3,}", lines[i].strip())):
        i += 1
    out = lines[i:]
    return title, "\n".join(out).rstrip() + "\n"

def aside_to_callout(body):
    pat = re.compile(r"<aside>\s*(?:<img[^>]*>)?\s*(.*?)\s*</aside>", re.DOTALL)
    return pat.sub(lambda m: "::: {.callout-note}\n" + m.group(1).strip() + "\n:::", body)

def write_page(new_path, title, body, subtitle=None):
    fm = ["---", f"title: {yaml_str(title)}"]
    if subtitle:
        fm.append(f"subtitle: {yaml_str(subtitle)}")
    fm += ["---", "", ""]
    with open(os.path.join(ROOT, new_path), "w") as f:
        f.write("\n".join(fm) + body)

# --------------------------------------------------------------- main doc
raw = open(MAIN).read()
# replace the two figures (long Notion alt text -> clean image; caption stays as following paragraph)
raw = re.sub(r"!\[.*?\]\(Cell%20Learning/Untitled\.png\)",
             "![](images/repeat-expansion.png)", raw)
raw = re.sub(r"!\[.*?\]\(Cell%20Learning/Untitled%201\.png\)",
             "![](images/learning-modes.png)", raw)
title, body = split_h1(raw)
body = aside_to_callout(body)
body = rewrite_links(body, os.path.normpath(MAIN), "index.qmd")
write_page("index.qmd", title or "Cell Learning", body)

# --------------------------------------------------------------- people pages
def person_csv_table(person_src, new_path):
    stem = os.path.splitext(os.path.basename(person_src))[0]
    data_dir = os.path.join(os.path.dirname(person_src), strip_id(stem))  # folder has no id
    cands = glob.glob(os.path.join(data_dir, "*.csv"))
    if not cands:
        return ""
    rows = list(csv.DictReader(open(cands[0], newline="", encoding="utf-8-sig")))
    rows = [r for r in rows if (r.get("Name") or "").strip()]
    # Notion export glitch: a few person pages inherited the *entire* reference
    # database (57 rows). Skip those dumps and empty tables; keep real lists.
    if not (0 < len(rows) <= 20):
        return ""
    out = ["", "## Related references", "", "| Reference | Title |", "| --- | --- |"]
    for r in rows:
        name = r["Name"].strip()
        slug = slugify(name)
        title = clean_title(r.get("Title")).replace("|", "\\|")
        rel = os.path.relpath(os.path.join(REFS, slug + ".qmd"),
                              os.path.dirname(os.path.join(ROOT, new_path)))
        cell = f"[{name}]({rel})" if slug in ref_slugs else name
        out.append(f"| {cell} | {title} |")
    return "\n".join(out) + "\n"

for p in person_srcs:
    new_path = path_map[os.path.normpath(p)]
    title, body = split_h1(open(p).read())
    # drop the trailing '[Untitled](.../*.csv)' sub-database link line
    body = re.sub(r"^\[[^\]]*\]\([^)]*\.csv\)\s*$", "", body, flags=re.MULTILINE)
    body = rewrite_links(body, os.path.normpath(p), new_path)
    body = body.rstrip() + "\n" + person_csv_table(p, new_path)
    write_page(new_path, title, body)

# people index
people_links = []
for p in person_srcs:
    np = path_map[os.path.normpath(p)]
    name = strip_id(os.path.splitext(os.path.basename(p))[0])
    people_links.append(f"- [{name}]({os.path.basename(np)})")
write_page("people/index.qmd", "People",
           "People and labs whose work informs this proposal.\n\n" + "\n".join(people_links) + "\n")

# --------------------------------------------------------------- reference pages
FIELD_RE = re.compile(r"^([A-Za-z][A-Za-z ]*?):\s?(.*)$")

def parse_reference(text):
    lines = text.splitlines()
    key = lines[0][2:].strip() if lines and lines[0].startswith("# ") else ""
    fields, i = {}, 1
    while i < len(lines):
        line = lines[i]
        m = FIELD_RE.match(line)
        if m:
            name, val = m.group(1).strip(), m.group(2)
            if name == "Bibtex":
                buf = [val]
                i += 1
                while i < len(lines) and lines[i].strip() != "}":
                    buf.append(lines[i]); i += 1
                if i < len(lines):
                    buf.append(lines[i])           # closing '}'
                fields["Bibtex"] = "\n".join(buf).strip()
            else:
                fields[name] = val.strip()
        i += 1
    return key, fields

for p in ref_srcs:
    new_path = path_map[os.path.normpath(p)]
    key, f = parse_reference(open(p).read())
    title = clean_title(f.get("Title")) or key
    parts = []
    meta = " · ".join(x for x in [f.get("Journal"), f.get("Year")] if x)
    if meta:
        parts.append(f"*{meta}*")
    if f.get("Tags"):
        parts.append("**Tags:** " + f["Tags"])
    if f.get("PDF"):
        pdf = os.path.basename(urllib.parse.unquote(f["PDF"]))
        parts.append(f"[📄 Download PDF](../files/{urllib.parse.quote(pdf)})")
    if f.get("URL"):
        parts.append(f"[🔗 Link]({f['URL']})")
    if f.get("Summary"):
        parts.append(f["Summary"])
    if f.get("Bibtex"):
        parts.append("```bibtex\n" + f["Bibtex"] + "\n```")
    body = "\n\n".join(parts) + "\n"
    write_page(new_path, title, body, subtitle=f"Citation key: {key}" if key else None)

# --------------------------------------------------------------- references index (database table)
csv_simple = glob.glob(os.path.join(CL, "References *.csv"))
csv_simple = [c for c in csv_simple if not c.endswith("_all.csv")][0]
rows = list(csv.DictReader(open(csv_simple, newline="", encoding="utf-8-sig")))
rows.sort(key=lambda r: (r.get("Name") or "").lower())
tbl = ["| Reference | Title | Year | Journal | Tags | PDF |",
       "| --- | --- | --- | --- | --- | --- |"]
for r in rows:
    name = (r.get("Name") or "").strip()
    if not name:
        continue
    slug = slugify(name)
    ref = f"[{name}]({slug}.qmd)" if slug in ref_slugs else name
    title = clean_title(r.get("Title")).replace("|", "\\|")
    tags  = (r.get("Tags") or "").replace("|", "\\|").strip()
    pdf_link = ""
    if (r.get("PDF") or "").strip():
        pdf = os.path.basename(urllib.parse.unquote(r["PDF"]))
        pdf_link = f"[📄](../files/{urllib.parse.quote(pdf)})"
    tbl.append(f"| {ref} | {title} | {(r.get('Year') or '').strip()} | "
               f"{(r.get('Journal') or '').strip()} | {tags} | {pdf_link} |")
write_page("references/index.qmd", "References",
           "The reference library backing this proposal. "
           "Each entry links to its detail page and PDF.\n\n" + "\n".join(tbl) + "\n")

print(f"Pages written: index + {len(person_srcs)} people + {len(ref_srcs)} references + 2 indexes")
print(f"PDFs in files/: {len(glob.glob(os.path.join(FILES, '*.pdf')))}")
print(f"Images in images/: {len(glob.glob(os.path.join(IMAGES, '*')))}")
if unmapped:
    print("UNMAPPED LINKS (flattened to text):")
    for np, t in unmapped:
        print(f"  [{np}] {t}")
else:
    print("No unmapped links.")
