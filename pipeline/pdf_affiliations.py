#!/usr/bin/env python3
"""Extract per-author affiliations from the first page of a final proceedings PDF.

The publisher PDF is the version of record, so its author block is paper-specific
affiliation evidence for every byline author it names. The publisher byline
(from the membership list) is authoritative for who the authors are and in what
order; this module only finds each of those authors on the page and reads the
affiliation text attached to them. Nothing here invents an author.

Text comes from poppler's `pdftotext -layout` (a system binary, not a pip
install). Layout mode keeps the side-by-side author columns in reading order;
plain mode scrambles them.

Two layouts cover ICLR-style headers:

  columns   Name / affiliation lines / email stacked in side-by-side columns.
            Several names in one block over one affiliation is the shared form.
  markers   Names carry superscript marks ("Lu1,3,*", "Ye1†"), followed by an
            affiliation list keyed by the same marks ("1 Tencent AI Lab 2 Peking
            University"). pdftotext often puts a mark on its own line above the
            text it labels.
            Variants read: marks lifted onto the line above the names,
            "1." keys, marks at the end of each entry, a legend set in two
            columns, and one institution printed once below keyed departments.

Each result carries a confidence: "high" when every byline author is anchored
and has at least one affiliation, "partial" when some are, "none" otherwise.
Anything below "high" belongs in a review queue, not in automatic credit.
"""
from __future__ import annotations

import re
import subprocess
import unicodedata

PDFTOTEXT = "pdftotext"
# Bump when extraction logic changes; harvest_ml re-extracts stored text.
EXTRACTOR_VERSION = 4


_ABSTRACT = re.compile(r"^\s*A\s*B\s*S\s*T\s*R\s*A\s*C\s*T\b", re.I)
# Any "@" marks an address line, except an all-caps name such as "CNRS@CREATE".
_EMAIL = re.compile(r"@(?![A-Z]{2,}(?![\w.]))|^\s*[eE]-?mail")
_NOISE = re.compile(r"(equal contribution|corresponding author|project page|code is available|https?://|github\.com|work done|denotes|∗ ?equal|contributed equally|equally contribut|project lead|\bintern(?:ship)?\b|correspondence)", re.I)
# Superscript marks as pdftotext renders them. 'B' is the envelope glyph that
# many templates use for corresponding authors; it never labels an affiliation.
_SYMBOLS = "†‡§¶*∗♣♠♡♢♦♥⋆★☆◦•‖#°♯♮♭↿⇂⊥⊤⊣⊢∇△▽◇◆□■○●⋄⊕⊗※¤"
_SYM = re.escape(_SYMBOLS)
# A repeated symbol is its own mark: "††" labels a different affiliation
# from "†". Matched with finditer; group(0) is the whole mark.
_MARK_TOKEN = re.compile(r"\d{1,2}|([" + _SYM + r"])\1*|B(?![A-Za-z])")
_MARK = r"(?:\d{1,2}|[" + _SYM + r"]+|B(?![A-Za-z]))"
_MARK_RUN = re.compile(r"^[\s,]*(" + _MARK + r"(?:[\s,]*" + _MARK + r")*)")
# A legend entry's mark: "1 Tencent", "1. Shanghai", "† École". Capitals
# include accented ones.
_AFFIL_MARK = re.compile(r"(?:(?<=\s)|^)(\d{1,2}|([" + _SYM + r"])\2*)[.)]?\s+(?=[A-ZÀ-ÖØ-Þ])")
# One whitespace-free run of marks ("1,2†"), as on a line of lifted superscripts.
_MARK_GROUP = re.compile(r"^" + _MARK + r"(?:,?" + _MARK + r")*,?$")
_DANGLING_MARK = re.compile(r"\s(\d{1,2}|([" + _SYM + r"])\2*)\s*$")
_TRAILING_MARK = re.compile(r"(?<=[^\W\d_).])\s?(\d{1,2}|[" + _SYM + r"])(?:\s*[,;&]\s*|\s+|$)")
_SUBUNIT = re.compile(r"(?:graduate\s+)?(?:departments?|depts?|schools?|faculty|division|college|institute\s+(?:for|of)|"
                      r"cent(?:er|re)|lab(?:oratory)?|program(?:me)?|group)\b", re.I)
_ORG = re.compile(r"universi|institut|college|academy|polytechni|\b[eé]cole\b|\bhochschule\b", re.I)
_CONJ = re.compile(r"\s+(?:&|and)\s+(?=[A-ZÀ-ÖØ-Þ])")
_FIELD = re.compile(r"(?:science|engineering|architecture|mathematics|statistics|physics|chemistry|biology|"
                    r"informatics|medicine|economics|linguistics|psychology)s?$", re.I)
_SEGMENT_GAP = re.compile(r"\s{3,}")


def first_page_text(pdf_path, timeout=60):
    """Layout-mode text of page 1, or '' when the PDF has no extractable text."""
    result = subprocess.run([PDFTOTEXT, "-f", "1", "-l", "1", "-layout", str(pdf_path), "-"],
                            capture_output=True, timeout=timeout)
    return result.stdout.decode("utf8", "replace") if result.returncode == 0 else ""


def fold(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def header_lines(text):
    """Lines above the Abstract heading, minus the running header."""
    lines = []
    for line in text.splitlines():
        if _ABSTRACT.match(line):
            return lines, True
        lines.append(line.rstrip())
    return lines, False


def segments(line):
    """Split a layout line into (start, end, text) column segments."""
    out, pos = [], 0
    for part in _SEGMENT_GAP.split(line):
        start = line.find(part, pos) if part else pos
        if part.strip():
            lead = len(part) - len(part.lstrip())
            out.append((start + lead, start + len(part.rstrip()), part.strip()))
        pos = start + len(part)
    return out


def _name_pattern(name):
    """Regex for an author name on the page: tokens in order, flexible gaps.

    Falls back to the surname alone because listings and PDFs disagree on
    middle names and particles ("Tiago Silva" vs "Tiago da Silva")."""
    toks = fold(name).split()
    if not toks:
        return None, None
    full = r"\b" + r"\W+(?:\w+\W+){0,2}?".join(map(re.escape, toks)) + r"\b"
    return re.compile(full), re.compile(r"\b" + re.escape(toks[-1]) + r"\b")


def _folded_with_map(text):
    """fold() that also returns, per folded char, its index in the source."""
    out, index = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKD", ch):
            if unicodedata.combining(c):
                continue
            for sub_c in c.casefold():
                # Digits become gaps: superscripts are glued to names ("Lu1,3").
                if not re.match(r"[a-z]", sub_c):
                    sub_c = " "
                out.append(sub_c)
                index.append(i)
    return "".join(out), index


def locate_authors(lines, authors, start_line=0):
    """Find each byline author's (line, col_start, col_end), in byline order."""
    found = [None] * len(authors)
    cursor = (start_line, 0)
    for k, name in enumerate(authors):
        full, surname = _name_pattern(name)
        if not full:
            continue
        for pattern in (full, surname):
            hit = None
            for li in range(cursor[0], len(lines)):
                folded, index = _folded_with_map(lines[li])
                begin = cursor[1] if li == cursor[0] else 0
                fbegin = next((j for j, src in enumerate(index) if src >= begin), len(folded))
                m = pattern.search(folded, fbegin)
                if m:
                    hit = (li, index[m.start()], index[m.end() - 1] + 1)
                    break
            if hit:
                found[k] = hit
                cursor = (hit[0], hit[2])
                break
    return found


def _clean_affiliation(text):
    text = re.sub(r"\b(?:https?://|www\.)\S+", " ", text)
    text = re.sub(r"[\s,.]+\b(?:corre\b|corre-|correspond\w*|e-?mail)\b.*$", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,;.")
    # Marks of the next entry left dangling at the end ("...of China 1 3").
    text = re.sub(r"(?:[\s,]+(?:\d{1,2}|[" + _SYM + r"]+))+$", "", text).strip(" ,;.")
    text = re.sub(r"^(and|&)\s+", "", text, flags=re.I)
    text = re.sub(r"[\s,]+(and|&)$", "", text, flags=re.I).strip(" ,;.")
    return text



def _marks_above(lines, found, inline):
    """Marks that pdftotext lifted onto the line above the names.

    "    1      1,2†     3" over "Zecheng Li , Wengang Zhou , Hezhen Hu": one
    group per author on the name line that has no mark of its own, in order.
    Returns {author_index: marks text}.
    """
    out = {}
    by_line = {}
    for k, f in enumerate(found):
        if f and not inline.get(k):
            by_line.setdefault(f[0], []).append(k)
    for li, ks in by_line.items():
        groups = lines[li - 1].split() if li else []
        if len(groups) == len(ks) and all(_MARK_GROUP.match(g) for g in groups):
            out.update(zip(ks, groups))
    return out


def _author_marks(lines, found):
    def marks(text):
        m = _MARK_RUN.match(text)
        return [t.group(0) for t in _MARK_TOKEN.finditer(m.group(1)) if t.group(0) != "B"] if m else []

    inline = {}
    for k, f in enumerate(found):
        if not f:
            continue
        li, _, end = f
        # The PDF byline may carry name tokens the listing omits before the
        # marks ("Dung Nguyen Manh†"); skip up to two of them. Letters only:
        # a mark glued to the token ("Feng1,2") is not part of the name.
        tail = re.sub(r"^(?:\s*[A-Z](?:[^\W\d_]|[.'’-])*(?=[\s\d" + _SYM + r",]|$)){0,2}", "", lines[li][end:])
        inline[k] = marks(tail)
    for k, text in _marks_above(lines, found, inline).items():
        inline[k] = marks(text)
    return inline


def _legend(lines, start, name_lines, used):
    """Read the keyed affiliation list below line `start`.

    Returns (entries, last_line). An entry is {"mark", "parts", "col", "own",
    "noise"}: `parts` is its text in reading order, `own` the unmarked full
    lines that followed it. Columns matter twice: a mark alone on a line labels
    the text that starts under it, and a row of unmarked text under a row of
    entries continues each entry above it.
    """
    entries, row, pending = [], [], []
    blanks, last, muted, row_line, seen_text = 0, start, False, None, False
    numbered = any(m.isdigit() for m in used)

    def is_mark(mark):
        # A number is a key only where the names carry numbers; otherwise it
        # is part of an address ("21 Nanyang Link", "1 Create Way").
        return numbered or not mark.isdigit()

    for li in range(start + 1, len(lines)):
        line = lines[li]
        if not line.strip():
            blanks += 1
            # A wide gap after the affiliation list ends the author block;
            # what follows is a teaser figure or its caption.
            if blanks >= 2 and seen_text:
                break
            continue
        blanks = 0
        if li in name_lines:
            # A later group of authors starts its own block.
            if entries:
                break
            continue
        if _EMAIL.search(line):
            continue
        seen_text = True
        tokens = line.split()
        if all(_MARK_GROUP.match(t) for t in tokens):
            pending = [(_MARK_TOKEN.match(t).group(0), line.find(t)) for t in tokens
                       if _MARK_TOKEN.match(t).group(0) != "B"]
            continue
        # A mark left at the end of a line labels the text below it.
        dangling = _DANGLING_MARK.search(line)
        if dangling:
            line = line[:dangling.start()]
        segs = segments(line)
        starts = []
        for mark, col in pending if segs else ():
            seg = min(segs, key=lambda s: (s[0] < col - 2, abs(s[0] - col)))
            starts.append((seg[0], seg[0], mark))
        pending = []
        for hit in _AFFIL_MARK.finditer(line):
            if is_mark(hit.group(1)):
                starts.append((hit.start(), hit.end(), hit.group(1)))
        starts.sort()
        lead = line[:starts[0][0]] if starts else line
        if lead.strip():
            if _NOISE.search(lead):
                muted = True
            elif muted or not entries:
                pass
            elif not starts and len(segs) >= 2 and len(segs) == len(row) and row_line == li - 1:
                for (_, _, text), entry in zip(segs, row):
                    entry["parts"].append(", " + text)
            else:
                entries[-1]["parts"].append(" " + lead.strip())
                if not starts:
                    entries[-1]["own"].append(lead.strip())
            last = li
        fresh = []
        for n, (_, begin, mark) in enumerate(starts):
            stop = starts[n + 1][0] if n + 1 < len(starts) else len(line)
            text = line[begin:stop].strip()
            # Footnotes share lines ("5 CIFAR, ∗ Equal contribution † Project
            # lead"): everything from the first one on is not an affiliation.
            noise = bool(_NOISE.search(text)) or bool(fresh and fresh[-1]["noise"])
            fresh.append({"mark": mark, "parts": [text], "col": begin, "own": [], "noise": noise})
        if fresh:
            entries.extend(fresh)
            row, row_line, muted, last = fresh, li, fresh[-1]["noise"], li
        if dangling and is_mark(dangling.group(1)):
            pending = [(dangling.group(1), dangling.start(1))]
        elif dangling and entries and not muted:
            entries[-1]["parts"].append(dangling.group(0).rstrip())
    return entries, last


def _trailing_legend(lines, start, name_lines, used):
    """A legend that carries each mark at the end of its text.

    "..., Adelaide, AU1" per line, or "KAIST1 , Polymerize2 , AITRICS3" in a
    row. Every piece must end in a mark some name uses, or nothing is read. A
    repeated mark continues its entry ("EECS1 , Psychiatry2 / DGIST1 ,
    Stanford University2").
    """
    entries, last = {}, start
    for li in range(start + 1, len(lines)):
        line = lines[li].strip()
        if li in name_lines or not line or _EMAIL.search(line) or _NOISE.search(line):
            if entries:
                break
            continue
        pieces = _TRAILING_MARK.split(line)
        if len(pieces) < 3 or pieces[-1].strip() or not all(m in used for m in pieces[1::2]):
            if entries:
                break
            return [], start
        for text, mark in zip(pieces[0::2], pieces[1::2]):
            entries.setdefault(mark, []).append(text.strip(" ,;"))
        last = li
    return [{"mark": mark, "parts": [", ".join(parts)], "col": 0, "own": [], "noise": False}
            for mark, parts in entries.items()], last


def _share_parent(entries):
    """Give every sub-unit the institution printed once below the list.

    "1 Architecture 2 Computer Science 3 Civil Engineering / Princeton
    University": the unmarked last line belongs to all three, not to "3".
    Only when every keyed entry is a bare sub-unit, so a wrapped final entry
    ("2 Shanghai AI / Laboratory") is left alone.
    """
    if len(entries) < 2 or not entries[-1]["own"] or any(e["own"] for e in entries[:-1]):
        return
    last = entries[-1]
    head = "".join(last["parts"][:len(last["parts"]) - len(last["own"])])
    heads = ["".join(e["parts"]) for e in entries[:-1]] + [head]
    if not all(_bare_subunit(h) for h in heads) or _SUBUNIT.match(last["own"][0]) or not _ORG.search(last["own"][0]):
        return
    parent = ", ".join(last["own"])
    for entry, text in zip(entries, heads):
        entry["parts"] = [_clean_affiliation(text) + ", " + parent]


def _bare_subunit(text):
    text = _clean_affiliation(text)
    if re.search(r"[,;]\s*$", text) or "," in text:
        return False
    return bool(_SUBUNIT.match(text)) or bool(_FIELD.search(text) and not _ORG.search(text))


def _footnote_legend(all_lines, used):
    """Extract keyed affiliation entries from a bottom-of-column footnote (e.g. ICML PMLR)."""
    proc_idx = None
    for i, l in enumerate(all_lines):
        if re.search(r"Proceedings of.*?Machine Learning|PMLR \d+|Copyright \d{4} by the author", l, re.I):
            proc_idx = i
            break
    if proc_idx is None:
        proc_idx = len(all_lines)

    col1 = []
    for j in range(max(0, proc_idx - 25), proc_idx):
        line = all_lines[j]
        segs = segments(line)
        c1 = ""
        if segs and segs[0][0] < 20:
            if len(segs) > 1:
                c1 = line[:segs[1][0]].rstrip()
            else:
                if segs[0][1] < 68 or "Correspondence to" in segs[0][2] or any(m in segs[0][2] for m in used):
                    c1 = segs[0][2]
        col1.append((j, c1))

    fn_start = None
    for idx in range(len(col1) - 1, -1, -1):
        _, text = col1[idx]
        stripped = text.strip()
        if not stripped:
            continue
        if re.match(r"^\d+\.?\s*(?:Introduction|Background|Preliminaries)\b", stripped, re.I):
            break
        is_mark_start = any(re.match(r"^" + re.escape(m) + r"(\b|[.)\s])", stripped) for m in used | {"*", "†"})
        is_note_start = bool(re.match(r"^(?:Equal contribution|Work done|Preprint)", stripped, re.I))
        if is_mark_start or is_note_start:
            fn_start = idx

    if fn_start is None:
        return []

    cleaned_fn = []
    for _, text in col1[fn_start:]:
        if not text.strip():
            continue
        c = re.sub(r"\s*\b(?:Correspondence(?:\s+to)?|E-?mail):?.*$", "", text, flags=re.I)
        if re.match(r"^\s*to:\s*", c, re.I):
            continue
        if c.strip():
            cleaned_fn.append(c)


    dummy = [""] + cleaned_fn
    entries, _ = _legend(dummy, 0, set(), used)
    entries = [e for e in entries if not e["noise"]]
    _share_parent(entries)
    return entries


def parse_markers(lines, authors, found, all_lines=None):
    """Superscript layout. Returns ({author_index: [affiliation, ...]}, last
    legend line) or (None, None)."""
    located = [f for f in found if f]
    if not located:
        return None, None
    marks_by_author = _author_marks(lines, found)
    marked = [k for k, v in marks_by_author.items() if v]
    if len(marked) < max(1, len(located) // 2):
        return None, None
    name_lines = {f[0] for f in located}
    start = max(found[k][0] for k in marked) if marked else max(f[0] for f in located)
    used = {m for marks in marks_by_author.values() for m in marks}
    entries, last = _legend(lines, start, name_lines, used)
    entries = [e for e in entries if not e["noise"]]
    if not entries:
        entries, last = _trailing_legend(lines, start, name_lines, used)
    if not entries and all_lines:
        entries = _footnote_legend(all_lines, used)
        last = len(lines)
    _share_parent(entries)
    affiliations = {}
    for entry in entries:
        value = _clean_affiliation("".join(entry["parts"]).split(";")[0])
        if value and len(value) > 2:
            affiliations.setdefault(entry["mark"], value)
    if not affiliations:
        return None, None
    result = {}
    for k, marks in marks_by_author.items():
        values = [affiliations[m] for m in marks if m in affiliations]
        if values:
            result[k] = list(dict.fromkeys(values))
    # One affiliation, no marks on names: everyone shares it.
    if not result and len(affiliations) == 1:
        only = next(iter(affiliations.values()))
        result = {k: [only] for k in marks_by_author}
    return result, last



def parse_columns(lines, authors, found):
    """Column-block layout. Returns {author_index: [affiliation, ...]}."""
    result = {}
    name_lines = {f[0] for f in found if f}
    for k, f in enumerate(found):
        if not f:
            continue
        li, start, end = f
        # The author's column is the segment containing the name.
        seg = next(((s, e, t) for s, e, t in segments(lines[li]) if s <= start < e + 1), None)
        if not seg:
            continue
        col = (seg[0], seg[1])
        collected = []
        for lj in range(li + 1, min(len(lines), li + 8)):
            line = lines[lj]
            if not line.strip():
                if collected:
                    break
                continue
            # A segment belongs to this column when at least half of the
            # narrower of the two overlaps; a long string from the next
            # column that merely touches it does not.
            hits = [(s, e, t) for s, e, t in segments(line)
                    if min(e, col[1]) - max(s, col[0]) >= 0.5 * max(1, min(e - s, col[1] - col[0]))]
            if not hits:
                continue
            text = " ".join(t for _, _, t in hits)
            if _EMAIL.search(text):
                break
            # Another author's name in this column starts the next block.
            if lj in name_lines and any(g and g[0] == lj and g[1] < col[1] + 2 and g[2] > col[0] - 2 for g in found):
                break
            if _NOISE.search(text):
                continue
            collected.append(text)
        # A block that opens with a bare mark, or holds several, is a keyed
        # list the marker parser could not read, not this author's own lines.
        bare = [bool(_MARK_GROUP.match(t)) for t in collected]
        if collected and (bare[0] or sum(bare) > 1):
            continue
        values = [v for v in (_clean_affiliation(v) for v in _split_block(collected)) if v]
        if values:
            result[k] = values
    return result


def _split_block(block_lines):
    """One author's block of lines -> its affiliations.

    The lines read as one affiliation ("Department of Computer Science /
    Goethe University Frankfurt") unless a conjunction introduces another
    institution: "& University of Bristol" on its own line, or "FAIR at Meta
    and Carnegie Mellon University". Stacked lines without one stay together:
    "Kempner Institute / Harvard University" is a single place.
    """
    out = []
    for line in block_lines:
        pieces = [line]
        m = _CONJ.search(line)
        if m and _standalone(line[:m.start()].split(",")[-1], named=False) and _standalone(line[m.end():].split(",")[0]):
            pieces = [line[:m.start()], line[m.end():]]
        lead = re.match(r"(?:&|and)\s+", pieces[0])
        if out and not (lead and _standalone(pieces[0][lead.end():].split(",")[0])):
            out[-1] += ", " + pieces.pop(0)
        out.extend(pieces)
    return out


def _standalone(text, named=True):
    """Is this an institution by itself, not a sub-unit or a fragment of a name?

    `named` also requires a word such as University or Institute.
    """
    text = text.strip()
    if not text or not text[0].isupper() or _SUBUNIT.match(text):
        return False
    return bool(_ORG.search(text)) or not named


def extract(text, authors):
    """Map byline authors to affiliation strings from first-page layout text.

    Returns {"layout", "confidence", "affiliations": [[str, ...] per author],
             "anchored": n, "reason"}.
    """
    lines, saw_abstract = header_lines(text)
    out = {"layout": None, "confidence": "none", "affiliations": [[] for _ in authors],
           "anchored": 0, "reason": None}
    if not text.strip():
        out["reason"] = "no extractable text (image-only PDF?)"
        return out
    if not saw_abstract:
        out["reason"] = "abstract heading not found"
        return out
    found = locate_authors(lines, authors)
    out["anchored"] = sum(1 for f in found if f)
    if not out["anchored"]:
        out["reason"] = "no byline author found on page"
        return out
    (mapping, legend_end), layout = parse_markers(lines, authors, found, all_lines=text.splitlines()), "markers"
    if not mapping:
        mapping, layout = parse_columns(lines, authors, found), "columns"
    elif any(f and f[0] > legend_end and k not in mapping for k, f in enumerate(found)):
        # A block of authors below the keyed list carries its own affiliation
        # lines ("See-Kiong Ng & Bryan Low / Department of ...").
        below = parse_columns(lines, authors, [f if f and f[0] > legend_end else None for f in found])
        mapping.update({k: v for k, v in below.items() if k not in mapping})
    out["layout"] = layout
    for k, values in (mapping or {}).items():
        # A stray mark or digit is not an affiliation.
        values = [v for v in values if re.search(r"[A-Za-z]{3}", v)]
        if values:
            out["affiliations"][k] = values
    covered = sum(1 for v in out["affiliations"] if v)
    if covered == len(authors) and out["anchored"] == len(authors):
        out["confidence"] = "high"
    elif covered:
        out["confidence"] = "partial"
        out["reason"] = f"{covered}/{len(authors)} authors with affiliations, {out['anchored']} anchored"
    else:
        out["reason"] = "authors anchored but no affiliation text attached"
    return out


# Generic words that say nothing about which institution a string names.
_GENERIC = set("""university univ of the and for in at department dept school college institute
institution lab laboratory labs center centre research inc ltd llc co corp company group national
key state science sciences technology engineering computer electrical faculty division program
graduate usa us uk china germany france japan korea canada india singapore""".split())


def strings_agree(left, right):
    """Do two lists of affiliation strings plausibly name the same place?

    True on an exact folded match or any shared distinctive token. Used to flag
    PDF-vs-OpenAlex conflicts for review, never to decide credit.
    """
    lf, rf = {fold(x) for x in left if x}, {fold(x) for x in right if x}
    if lf & rf:
        return True
    tokens = lambda xs: {t for x in xs for t in fold(x).split() if len(t) >= 3 and t not in _GENERIC}  # noqa: E731
    return bool(tokens(left) & tokens(right))
