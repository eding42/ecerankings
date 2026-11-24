#!/usr/bin/env python3
"""Evidence inside a raw affiliation string that a name match ignores.

A matcher compares names. The string usually says more: the country it ends
with, and whether it describes a company. Ignoring that produced these, all
live in the published rankings on 2026-11-12:

  'Southeast University,Nanjing,China'        -> Southeast University (BD)
  'Korea University,Seoul,Korea'              -> Korea University (JP)
  'Imperial College, ..., London, UK'         -> Imperial Valley College (US)
  'Sony Semiconductor ... Corporation,Kanagawa,Japan' -> Kanagawa University

Shared by the normalizers (to stop producing such rows), adjudication.py check
and verify_global.py (to find them), and fix_country_mismatches.py (to propose
repairs). Python stdlib only.
"""

import html
import re
import unicodedata
from collections import defaultdict
from functools import lru_cache

# Country names as they appear at the end of affiliation strings.
_COUNTRY_PATTERNS = {
    "US": r"USA|U\.S\.A\.?|United States", "GB": r"UK|U\.K\.?|United Kingdom|England|Scotland|(?<!South )Wales",
    "CN": r"China|P\.?R\.? ?China|PRC", "AU": r"Australia", "CA": r"Canada", "DE": r"Germany|Deutschland",
    "FR": r"France", "JP": r"Japan", "KR": r"Korea|South Korea|Republic of Korea", "IN": r"India",
    "IT": r"Italy|Italia", "ES": r"Spain|España", "NL": r"Netherlands", "CH": r"Switzerland",
    "SG": r"Singapore", "TW": r"Taiwan", "HK": r"Hong Kong", "BR": r"Brazil|Brasil", "SE": r"Sweden",
    "IL": r"Israel", "IR": r"Iran", "TR": r"Turkey|Türkiye", "BE": r"Belgium", "AT": r"Austria",
    "DK": r"Denmark", "FI": r"Finland", "NO": r"Norway", "PL": r"Poland", "PT": r"Portugal",
    "GR": r"Greece", "IE": r"Ireland", "BD": r"Bangladesh", "PK": r"Pakistan", "EG": r"Egypt",
    "MX": r"(?<!New )Mexico|México", "SA": r"Saudi Arabia", "AE": r"UAE|United Arab Emirates", "NZ": r"New Zealand",
    "MY": r"Malaysia", "TH": r"Thailand", "VN": r"Viet ?nam", "RU": r"Russia", "ZA": r"South Africa",
    "PH": r"Philippines", "ID": r"Indonesia", "CL": r"Chile", "AR": r"Argentina", "CO": r"Colombia",
}
COUNTRY_RES = {cc: re.compile(rf"\b(?:{pattern})\b") for cc, pattern in _COUNTRY_PATTERNS.items()}
# Strings and records that legitimately name either side of these pairs.
COUNTRY_EQUIVALENT = {frozenset(p) for p in (("CN", "HK"), ("CN", "TW"), ("CN", "MO"), ("GB", "IE"))}
COUNTRY_TAIL = 60            # a country at the end of the string is the author's own

COMPANY_RE = re.compile(
    r"\b(?:Ltd\.?|Limited|Inc\.?|GmbH|Corp\.?|Corporation|Co\.,?|LLC|S\.A\.|AG|B\.V\.|Pte)(?=[\s,.;)]|$)")
ACADEMIC_RE = re.compile(
    r"univ|college|institut|school|academy|polytech|politec|faculty|facult|department|dept|laborator|hochschule",
    re.I)


# Words that mark a string as an academic unit. Generic ones ("laboratory",
# "research", "center") are left out on purpose: companies use them too.
STRONG_ACADEMIC_RE = re.compile(
    r"univ|college|polytech|politec|hochschule|\becole\b|escuela|scuola|daigaku|hogeschool|academ|akadem|"
    r"institute of tech|institut[eo]? (?:of|de|for|di) |institut(?:o)? tecn|school of|faculty|facult|"
    r"departement|dipartimento|departamento|\bcnrs\b|\binria\b")


def fold(text):
    """ASCII, lowercase, single-spaced; HTML entities decoded first."""
    text = unicodedata.normalize("NFKD", html.unescape(text or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def academic_evidence(raw, inst):
    """True when the raw string gives a reason to credit a university: an
    academic word, or the institution's own name, alternative or acronym.

    A string with neither ("Akita Software, Palo Alto, CA") was matched on a
    city or a fragment, not on the institution. `inst` is the index record.
    """
    folded = fold(raw)
    if STRONG_ACADEMIC_RE.search(folded):
        return True
    padded = f" {folded} "
    for name in [inst.get("display_name")] + list(inst.get("alternatives") or []) + list(inst.get("acronyms") or []):
        name = fold(name)
        if len(name) >= 3 and f" {name} " in padded:
            return True
    return False


def institutional_name_evidence(raw, inst, name_index):
    """Require a full indexed name/alias, not academic vocabulary or a city.

    Acronyms must identify one institution in the index; ambiguous acronyms
    need adjudication with paper context. Country never supplies identity.
    """
    padded = " " + fold(raw) + " "
    iid = inst.get("id")
    for name in [inst.get("display_name")] + list(inst.get("alternatives") or []) + list(inst.get("acronyms") or []):
        normalized = fold(name)
        if len(normalized) < 3 or " " + normalized + " " not in padded:
            continue
        owners = name_index.get(normalized, set())
        if len(owners) > 1:
            named = countries_named(raw)
            if len(named) != 1:
                continue
            country = next(iter(named))
            if name_index.get(normalized + "|" + country) != {iid}:
                continue
        # Short aliases must actually be indexed, never inferred from location.
        elif " " not in normalized and len(normalized) <= 6 and owners != {iid}:
            continue
        return True
    return False


def names_other_university(raw, inst, name_index):
    """Conservatively hold compounds naming another education institution.

    Longest spans win so a university system's name contained in its campus
    name is not counted as a second affiliation. This does not split strings
    or assign author markers: that requires paper evidence.
    """
    words = fold(raw).split()
    covered, matches = set(), []
    for width in range(min(16, len(words)), 0, -1):
        for start in range(len(words) - width + 1):
            positions = set(range(start, start + width))
            if positions & covered:
                continue
            name = " ".join(words[start:start + width])
            owners = name_index.get(name, set())
            if len(name) < 3 or not owners:
                continue
            matches.append(owners)
            covered.update(positions)
    iid = inst.get("id")
    return any(iid in owners for owners in matches) and any(iid not in owners for owners in matches)


@lru_cache(maxsize=100000)
def countries_named(raw):
    """Country codes named at the end of a raw affiliation string."""
    start = max(0, len(raw) - COUNTRY_TAIL)
    # Match against the full text: slicing first turns New Mexico into Mexico
    # when the cutoff falls between the two words.
    return frozenset(cc for cc, pattern in COUNTRY_RES.items()
                     if any(m.start() >= start for m in pattern.finditer(raw)))


def country_contradiction(raw, mapped_cc):
    """Return the named countries when they exclude every mapped institution's.

    mapped_cc may be "|"-joined (a joint row); naming any member's country is
    not a contradiction.
    """
    mapped = {cc for cc in str(mapped_cc or "").split("|") if cc}
    if not mapped:
        return None
    named = countries_named(raw)
    if not named or mapped & named:
        return None
    if any(frozenset((m, cc)) in COUNTRY_EQUIVALENT for m in mapped for cc in named):
        return None
    return named


def names_education(raw, name_index):
    """Whether any indexed education name/alias occurs as a complete span.

    This only blocks a company-only proposal; it does not resolve ambiguous
    acronyms or authorize a university assignment.
    """
    words = fold(raw).split()
    return any(name_index.get(" ".join(words[start:start + width]))
               for width in range(1, min(16, len(words)) + 1)
               for start in range(len(words) - width + 1)
               if len(" ".join(words[start:start + width])) >= 3)


def looks_like_company(raw):
    return bool(COMPANY_RE.search(raw)) and not ACADEMIC_RE.search(raw)


def build_name_index(by_id):
    """lowercased name or alternative -> ids of education institutions."""
    index = defaultdict(set)
    for iid, inst in by_id.items():
        if inst.get("type") != "education":
            continue
        for name in [inst.get("display_name")] + list(inst.get("alternatives") or []) + list(inst.get("acronyms") or []):
            if name:
                index[name.strip().lower()].add(iid)
                index[fold(name)].add(iid)
                index[fold(name) + "|" + (inst.get("country_code") or "")].add(iid)
    return index


def same_name_abroad(raw, row, by_id, name_index):
    """The one education institution sharing the matched name in the country
    the string names, or None when there is none or more than one."""
    named = country_contradiction(raw, row.get("country_code", ""))
    if not named:
        return None
    keys = {(row.get("matched_via") or "").strip().lower(), (row.get("institution_name") or "").strip().lower()}
    found = {iid for key in keys if key for iid in name_index.get(key, ())
             if (by_id[iid].get("country_code") or "") in named}
    return by_id[next(iter(found))] if len(found) == 1 else None


def guard_row(raw, row, by_id, name_index):
    """Hold a freshly matched row to the string's own evidence. Mutates and
    returns `row`. Only auto-accepted education matches are touched.

    - Country contradiction, and exactly one same-named education institution
      in the named country: switch to it.
    - Country contradiction otherwise: demote to review.
    - Company string: demote to review.
    - No full institutional name or unambiguous indexed alias: demote to review.
    """
    if row.get("status") != "auto" or row.get("institution_type") != "education":
        return row
    if country_contradiction(raw, row.get("country_code", "")):
        other = same_name_abroad(raw, row, by_id, name_index)
        if other:
            row.update(institution_id=other["id"], institution_name=other["display_name"],
                       institution_type=other.get("type") or "", country_code=other.get("country_code") or "",
                       lineage="|".join(other.get("lineage") or [other["id"]]))
        else:
            row["status"] = "review"
    elif looks_like_company(raw) and not names_education(raw, name_index):
        row["status"] = "review"
    if row.get("status") == "auto":
        inst = by_id.get(row.get("institution_id"))
        if (not inst or not institutional_name_evidence(raw, inst, name_index)
                or names_other_university(raw, inst, name_index)):
            row["status"] = "review"
    return row
