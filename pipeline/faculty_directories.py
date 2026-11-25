"""University-specific public-directory layouts; factual extraction only."""
import html
import json
import re
import urllib.parse

from faculty_pilot import Tree, compact


def _scoped_entry(name, title, url, canonical_url, entry_id):
    return dict(
        name=name,
        title=title,
        profile_url=canonical_url(url),
        entry_id=entry_id,
        profile_kind='official_directory_entry',
    )


def _strip_tags(html_text):
    return compact(re.sub(r'<[^>]+>', ' ', html_text))


def _br_chunks(node, skip_links=False):
    chunks, cur = [], []
    for child in node.children:
        if getattr(child, 'tag', None) == 'br':
            s = compact(' '.join(cur))
            if s:
                chunks.append(s)
            cur = []
        elif skip_links and getattr(child, 'tag', None) == 'a':
            continue
        elif isinstance(child, str):
            cur.append(child)
        else:
            t = child.text()
            if t:
                cur.append(t)
    if cur:
        s = compact(' '.join(cur))
        if s:
            chunks.append(s)
    return chunks


def _parse_asu(body, url, canonical_url):
    data = json.loads(body.decode('utf-8', errors='replace'))
    rows = []
    for item in data.get('results', []):
        emp_cls = (item.get('primary_simplified_empl_class') or {}).get('raw') or []
        if isinstance(emp_cls, str):
            emp_cls = [emp_cls]
        if any(c in ('University Staff', 'Graduate Assistant/Associate') for c in emp_cls):
            continue
        name = compact((item.get('display_name') or {}).get('raw') or '')
        aid = compact((item.get('asurite_id') or {}).get('raw') or '')
        if not name or not aid:
            continue
        prim_titles = (item.get('primary_title') or {}).get('raw') or []
        all_titles = [t for t in ((item.get('titles') or {}).get('raw') or []) if t]
        dept = compact((item.get('primary_department') or {}).get('raw') or '')
        rank_raw = (item.get('faculty_rank') or {}).get('raw') or ''
        rank = compact(', '.join(str(x) for x in rank_raw) if isinstance(rank_raw, list) else str(rank_raw))
        cls_txt = ', '.join(emp_cls) if emp_cls else 'Unclassified'
        title_parts = []
        if prim_titles:
            title_parts.append(', '.join(str(t) for t in prim_titles if t))
        for t in all_titles:
            if t not in title_parts:
                title_parts.append(str(t))
        if rank and rank not in title_parts:
            title_parts.append(f'rank:{rank}')
        title = '; '.join(p for p in title_parts if p)
        if dept:
            title = f'{title} [{dept}; {cls_txt}]' if title else f'{cls_txt} [{dept}]'
        elif not title:
            title = cls_txt
        rows.append(_scoped_entry(name, title, url, canonical_url, f'asu-ecee-api:{aid}'))
    if not rows:
        raise ValueError('No ASU ECEE directory entries parsed from API payload')
    return rows, 0


def _parse_tamu(body, url, canonical_url):
    data = json.loads(body.decode('utf-8', errors='replace'))
    rows = []
    for item in data:
        tags = [str(t).strip() for t in (item.get('tag') or []) if str(t).strip()]
        tag_sets = item.get('tagSets') or []
        ece_roles = []
        for ts in tag_sets:
            parts = [str(t).strip() for t in ts if str(t).strip()]
            if any(p.lower() == 'electrical' for p in parts):
                for p in parts:
                    if p.lower() != 'electrical' and p not in ece_roles:
                        ece_roles.append(p)
        if not ece_roles and any(t.lower() == 'electrical' for t in tags):
            ece_roles = [t for t in tags if t.lower() != 'electrical']
        if not ece_roles:
            continue
        non_staff_tags = [t for t in ece_roles if t.lower() != 'staff']
        if not non_staff_tags:
            continue
        name = compact(item.get('name') or '')
        link = compact(item.get('link') or '')
        titles = [compact(str(t)) for t in (item.get('titles') or []) if compact(str(t))]
        if not name or not link:
            continue
        role_tags = ', '.join(non_staff_tags)
        title = '; '.join(titles)
        if role_tags:
            title = f'{role_tags}: {title}' if title else role_tags
        rows.append(dict(
            name=name,
            title=title or 'TAMU ECE Directory Entry',
            profile_url=canonical_url(urllib.parse.urljoin('https://engineering.tamu.edu/', link)),
        ))
    if not rows:
        raise ValueError('No TAMU ECE entries parsed from profile-data.json')
    return rows, 0


def _parse_vt(body, url, canonical_url):
    html = body.decode('utf-8', errors='replace')
    rows = []
    seen_urls = set()
    scoped_by_name = {}

    def add_scoped(name, title, entry_id):
        key = name.lower()
        if key in scoped_by_name:
            entry = scoped_by_name[key]
            if title not in entry['title']:
                entry['title'] = entry['title'] + '; ' + title
        else:
            entry = _scoped_entry(name, title, url, canonical_url, entry_id)
            scoped_by_name[key] = entry
            rows.append(entry)

    panels = re.split(r'<h2 class="vt-accordion-title">(.*?)</h2>', html, flags=re.S)
    for i in range(1, len(panels), 2):
        heading = _strip_tags(panels[i])
        panel_html = panels[i + 1]
        if heading == 'Alphabetical Faculty Listing':
            tree = Tree(panel_html).root
            for card in tree.all(cls='vt-list-item-row'):
                a = card.first('a', cls='vt-list-item-title-link')
                if not a:
                    continue
                name = compact(re.sub(r',\s*bio\s*$', '', a.text(), flags=re.I))
                href = a.attrs.get('href', '')
                if not name or not href:
                    continue
                pu = canonical_url(urllib.parse.urljoin(url, href))
                if pu not in seen_urls:
                    seen_urls.add(pu)
                    rows.append(dict(
                        name=name,
                        title='ECE Faculty Directory (rank on profile)',
                        profile_url=pu,
                    ))
        elif heading == 'Courtesy Appointments':
            body_html = panel_html.split('<footer')[0].split('id="vtctalink_')[0]
            tree = Tree(body_html).root
            for text_div in tree.all(cls='vt-text'):
                p = text_div.first('p')
                if not p:
                    continue
                chunks = _br_chunks(p)
                if not chunks:
                    continue
                name = chunks[0]
                role_parts = [c for c in chunks[1:] if '@' not in c]
                title = 'Courtesy Appointment: ' + ('; '.join(role_parts) or 'Courtesy Faculty')
                add_scoped(name, title, f'vt-ece-courtesy:{name}')
        elif heading in ('Emeritus Faculty', 'Research Faculty', 'Adjunct Faculty'):
            body_html = panel_html.split('<footer')[0].split('id="vtctalink_')[0]
            tree = Tree(body_html).root
            key = heading.split()[0].lower()
            for node in list(tree.all('p')) + list(tree.all('li')):
                if any(getattr(c, 'tag', None) in ('p', 'li') for c in node.children):
                    continue
                name = compact(node.text())
                if not name or 'Copyright' in name or 'See All Locations' in name:
                    continue
                add_scoped(name, heading, f'vt-ece-{key}:{name}')
    for a in Tree(html).root.all('a'):
        href = (a.attrs.get('href') or '').strip()
        if '/people/profile/' not in href or not href.endswith('.html'):
            continue
        pu = canonical_url(urllib.parse.urljoin(url, href))
        if urllib.parse.urlsplit(pu).hostname != 'ece.vt.edu' or '/content/ece_vt_edu/' in pu:
            continue
        if pu in seen_urls:
            continue
        name = compact(re.sub(r',\s*bio\s*$', '', a.text(), flags=re.I))
        if not name:
            continue
        seen_urls.add(pu)
        rows.append(dict(
            name=name,
            title='ECE Faculty Directory (research-area profile; rank on profile)',
            profile_url=pu,
        ))
    if not rows:
        raise ValueError('No VT ECE directory entries parsed')
    return rows, 0


def _parse_cmu(body, url, canonical_url):
    html = body.decode('utf-8', errors='replace')
    rows = []
    pre, sep, post = html.partition('id="emeritus"')
    tree_pre = Tree(pre).root
    list_slug = 'courtesy' if 'courtesy' in url else ('adjunct' if 'adjunct' in url else 'faculty')
    for div in tree_pre.all('div'):
        h2s = [c for c in div.children if getattr(c, 'tag', '') == 'h2']
        h3s = [c for c in div.children if getattr(c, 'tag', '') == 'h3']
        if len(h2s) != 1 or not h3s:
            continue
        name = compact(h2s[0].text())
        title = compact(h3s[0].text())
        a = h2s[0].first('a')
        href = (a.attrs.get('href') or '').strip() if a else ''
        if not name or not title:
            continue
        if href:
            safe_href = href.replace(' ', '%20')
            rows.append(dict(
                name=name,
                title=title,
                profile_url=canonical_url(urllib.parse.urljoin(url, safe_href)),
            ))
        else:
            rows.append(_scoped_entry(name, title, url, canonical_url, f'cmu-ece-{list_slug}:{name}'))
    if sep:
        tree_post = Tree(post).root
        for h2 in tree_post.all('h2'):
            name = compact(h2.text())
            if name:
                rows.append(_scoped_entry(name, 'Emeritus faculty', url, canonical_url, f'cmu-ece-emeritus:{name}'))
    if not rows:
        raise ValueError('No CMU ECE directory entries parsed')
    return rows, 0


def _parse_princeton(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for block in tree.all(cls='block-ps-people-list'):
        h2 = block.first('h2', cls='content-list-title')
        section = compact(h2.text()) if h2 else 'Core'
        for item in block.all(cls='content-list-item'):
            title_span = item.first(cls='field--name-title')
            a = title_span.first('a') if title_span else None
            if not a:
                continue
            name = compact(a.text())
            href = (a.attrs.get('href') or '').strip()
            if not name or not href:
                continue
            pos = item.first(cls='field--name-field-ps-people-position')
            role = item.first(cls='field--name-field-ps-people-role')
            pos_txt = compact(pos.text()) if pos else ''
            role_txt = compact(role.text()) if role else ''
            detail = '; '.join(x for x in (pos_txt, role_txt) if x)
            title = f'{section}: {detail}' if detail else section
            if section in ('Core', 'Emeritus Faculty'):
                rows.append(_scoped_entry(name, title, url, canonical_url, f'princeton-ece:{href}'))
            else:
                rows.append(dict(
                    name=name,
                    title=title,
                    profile_url=canonical_url(urllib.parse.urljoin(url, href)),
                ))
    if not rows:
        raise ValueError('No Princeton ECE directory entries parsed')
    return rows, 0


def _parse_cornell(body, url, canonical_url):
    html = body.decode('utf-8', errors='replace')
    parts = re.split(r'(<h2[^>]*>.*?</h2>)', html, flags=re.S)
    rows = []
    allowed_sections = {'Core Faculty', 'Graduate Field Faculty', 'Emeriti Faculty', 'Research and Teaching Professionals'}
    for i in range(1, len(parts), 2):
        sec = _strip_tags(parts[i])
        if sec not in allowed_sections:
            continue
        tree = Tree(parts[i + 1]).root
        for card in tree.all(cls='ce-block__people-list-titles'):
            a = card.first('a', cls='ce-block__people-list-item-link')
            if not a:
                continue
            name = compact(a.text())
            href = (a.attrs.get('href') or '').strip()
            title_p = card.first('p', cls='ce-block__people-list-person-title')
            dept_p = card.first('p', cls='ce-block__people-list-person-departments')
            t_txt = compact(title_p.text()) if title_p else ''
            d_txt = compact(dept_p.text()) if dept_p else ''
            detail = '; '.join(x for x in (t_txt, d_txt) if x)
            if not name or not href:
                continue
            rows.append(dict(
                name=name,
                title=f'{sec}: {detail}' if detail else sec,
                profile_url=canonical_url(urllib.parse.urljoin(url, href)),
            ))
    if not rows:
        raise ValueError('No Cornell ECE directory entries parsed')
    return rows, 0


def _parse_columbia(body, url, canonical_url):
    html = body.decode('utf-8', errors='replace')
    rows = []
    if '/academic-departments-programs/electrical-engineering' in url:
        m = re.search(r'<div id="facultytextcontainer"[^>]*>(.*?)</div>\s*<div id="coursestextcontainer"', html, re.S)
        if not m:
            raise ValueError('Columbia EE Bulletin missing facultytextcontainer')
        sec_html = m.group(1)
        parts = re.split(r'(<h2[^>]*>.*?</h2>)', sec_html, flags=re.S)
        skip_secs = {'Chair', 'Vice Chair', 'Director of Finance and Administration'}
        for i in range(1, len(parts), 2):
            sec = _strip_tags(parts[i])
            if sec in skip_secs:
                continue
            tree = Tree(parts[i + 1]).root
            for p in tree.all('p'):
                for entry in _br_chunks(p):
                    # e.g. "Alexander Gaeta, Applied Physics and Materials Science"
                    name = compact(entry.split(',')[0])
                    if not name:
                        continue
                    title = f'{sec} ({entry})' if ',' in entry else sec
                    rows.append(_scoped_entry(name, title, url, canonical_url, f'columbia-ee-bulletin:{name}'))
    else:
        tree = Tree(html).root
        is_emeriti = 'emeriti' in url
        for p in tree.all('p'):
            text = compact(p.text())
            if 'electrical engineering' not in text.lower():
                continue
            # CourseLeaf faculty directory paragraphs start with <strong>Name</strong><br/>Title
            strong = p.first('strong')
            if not strong:
                # Emeriti or fallback: split on Professor / comma / title
                m_em = re.match(r'^(.+?)\s+(?:[A-Z].*?(?:Professor\s+Emerit\w+|Lecturer|Scientist).*)$', text)
                if not m_em:
                    continue
                name = compact(m_em.group(1).rstrip(','))
                title = text
            else:
                name = compact(strong.text())
                title = compact(text[len(name):].strip(' ,;-')) or text
            if not name or len(name.split()) > 6:
                continue
            tag = 'emeriti' if is_emeriti else 'seas'
            rows.append(_scoped_entry(name, title, url, canonical_url, f'columbia-ee-{tag}:{name}'))
    if not rows:
        raise ValueError('No Columbia EE entries parsed from Bulletin')
    return rows, 0


def _parse_umn(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    if 'affiliate-faculty' in url:
        for wc in tree.all(cls='widget-content'):
            h2 = wc.first('h2')
            p = wc.first('p')
            if not h2 or not p:
                continue
            name = compact(h2.text())
            if not name:
                continue
            chunks = []
            for div in wc.children:
                if getattr(div, 'tag', None) == 'div':
                    t = compact(div.text())
                    if t:
                        chunks.append(t)
            chunks.extend(_br_chunks(p, skip_links=True))
            title = 'Affiliate Faculty: ' + ('; '.join(chunks) or 'Affiliate')
            rows.append(_scoped_entry(name, title, url, canonical_url, f'umn-ece-affiliate:{name}'))
    else:
        for card in tree.all(cls='views-row'):
            title_div = card.first(cls='people-title')
            a = title_div.first('a') if title_div else None
            job_div = card.first(cls='people-jobroles')
            if not a:
                continue
            name = compact(a.text())
            href = (a.attrs.get('href') or '').strip()
            title = compact(job_div.text()) if job_div else ''
            if not name or not href or not title:
                continue
            rows.append(dict(
                name=name,
                title=title,
                profile_url=canonical_url(urllib.parse.urljoin(url, href)),
            ))
    if not rows:
        raise ValueError('No UMN ECE entries parsed')
    return rows, 0


def _parse_psu(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all(cls='results-individual-revised'):
        name_p = card.first('p', cls='name')
        a = name_p.first('a') if name_p else None
        title_p = card.first('p', cls='title')
        if not a:
            continue
        name = compact(a.text())
        href = (a.attrs.get('href') or '').strip()
        title = compact(title_p.text()) if title_p else ''
        if not name or not href:
            continue
        rows.append(dict(
            name=name,
            title=title or 'PSU EECS Directory Entry',
            profile_url=canonical_url(urllib.parse.urljoin(url, href)),
        ))
    if not rows:
        raise ValueError('No PSU EECS entries parsed')
    return rows, 0


def _parse_wisconsin(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    if urllib.parse.urlsplit(url).hostname == 'directory.engr.wisc.edu':
        faculty_groups = {
            'Teaching Professors and Teaching Faculty',
            'Faculty Affiliates from Outside the College of Engineering',
            'Active Emeriti Faculty',
            'Additional Professors Emeriti',
            'Adjunct Professors',
        }
        seen_groups = set()
        category = ''
        for node in tree.all():
            if node.tag == 'h3' and 'listing' in node.attrs.get('class', '').split():
                category = node.text()
            if category not in faculty_groups or 'profileDisplay' not in node.attrs.get('class', '').split():
                continue
            heading = node.first('h3', cls='display')
            link = heading.first('a') if heading else None
            detail = node.first('p', cls='title')
            rows.append(_wisconsin_entry(link, detail, category, url, canonical_url))
            seen_groups.add(category)
        if seen_groups != faculty_groups:
            raise ValueError('Wisconsin supplemental directory has missing faculty categories')
    else:
        categories = {
            'tenure-track and tenured faculty': ('acf-person-card', 'title'),
            'faculty affiliates from within the college of engineering': ('acf-person-list', 'titles'),
        }
        seen_groups = set()
        for section in tree.all(cls='wp-block-acf-person-listing-with-facets'):
            heading = section.first('h2')
            category = heading.text() if heading else ''
            if category.casefold() not in categories:
                continue
            card_class, title_class = categories[category.casefold()]
            for card in section.all(cls=card_class):
                name = card.first(cls='name')
                link = name.first('a') if name else None
                rows.append(_wisconsin_entry(link, card.first(cls=title_class), category, url, canonical_url))
                seen_groups.add(category.casefold())
        if seen_groups != categories.keys():
            raise ValueError('Wisconsin primary directory has missing faculty categories')
    return rows, 0


def _wisconsin_entry(link, detail, category, url, canonical_url):
    if not link or not link.text() or not link.attrs.get('href'):
        raise ValueError('Wisconsin directory entry lacks a name or profile')
    title = detail.text() if detail else ''
    return dict(
        name=link.text(),
        title=f'{title}; {category}' if title else category,
        profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href'])),
    )


def _parse_washington(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    groups = {'faculty': 'Faculty', 'affiliate': 'Affiliate Faculty', 'adjunct': 'Adjunct Faculty',
              'emeritus': 'Emeritus Faculty'}
    group = groups[urllib.parse.urlsplit(url).path.strip('/')]
    for card in tree.all(cls='stafftemplate--entry'):
        name = card.first(cls='stafftemplate--name')
        title = card.first(cls='stafftemplate--title')
        if not name or not name.text():
            raise ValueError('Washington directory entry lacks name or appointment field')
        title_text = '; '.join(part for part in (title.text() if title else '', group) if part)
        link = name.first('a')
        profile = urllib.parse.urljoin(url, link.attrs.get('href', '')) if link else ''
        host = urllib.parse.urlsplit(profile).hostname or ''
        if profile and profile != url and (host == 'uw.edu' or host.endswith('.uw.edu') or host == 'washington.edu' or host.endswith('.washington.edu')):
            rows.append(dict(name=name.text(), title=title_text, profile_url=canonical_url(profile)))
        else:
            rows.append(_scoped_entry(name.text(), title_text, url, canonical_url,
                                      'uw-ece-directory:' + name.text()))
    if not rows:
        raise ValueError('No Washington ECE directory entries')
    return rows, 0


def _parse_ucsb(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    if urllib.parse.urlsplit(url).path.rstrip('/') == '/people':
        for cell in tree.all('td'):
            if cell.attrs.get('headers') != 'view-title-table-column':
                continue
            link = cell.first('a')
            if not link or not link.attrs.get('href'):
                raise ValueError('UC Santa Barbara directory entry lacks a profile')
            profile = urllib.parse.urljoin(url, link.attrs['href'])
            if not urllib.parse.urlsplit(profile).path.startswith('/people/faculty/'):
                continue
            parts = _br_chunks(cell, skip_links=True)
            rows.append(dict(name=link.text(), title='; '.join(parts) or 'Academic title not supplied by directory',
                             profile_url=canonical_url(profile)))
    else:
        for card in tree.all(cls='group-second'):
            heading = card.first('h3')
            link = heading.first('a') if heading else None
            if not link or not link.text() or not link.attrs.get('href'):
                raise ValueError('UC Santa Barbara directory entry lacks name or profile')
            title = next((compact(child) for child in card.children
                          if isinstance(child, str) and re.search(r'professor|faculty|lecturer|emerit|adjunct', child, re.I)),
                         'Academic title not supplied by directory')
            rows.append(dict(name=link.text(), title=title,
                             profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if not rows:
        raise ValueError('No UC Santa Barbara ECE directory entries')
    return rows, 0


def _parse_ohio_state(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all('article', cls='directory-item'):
        name = card.first(cls='directory-grid-name')
        path = card.attrs.get('about', '')
        appointments = [node.text() for node in card.all(cls='appointment-name') if node.text()]
        categories = [node.text() for node in card.all(cls='directory-category') if node.text()]
        if not name or not name.text() or not path.startswith('/people/'):
            raise ValueError('Ohio State directory entry lacks name or university profile')
        rows.append(dict(name=name.text(), title='; '.join(appointments + categories),
                         profile_url=canonical_url(urllib.parse.urljoin(url, path))))
    if not rows:
        raise ValueError('No Ohio State ECE directory entries')
    pager = tree.first('nav', cls='pager')
    pages = {0}
    if pager:
        for link in pager.all('a'):
            target = urllib.parse.urljoin(url, link.attrs.get('href', ''))
            parsed = urllib.parse.urlsplit(target)
            if parsed.netloc == urllib.parse.urlsplit(url).netloc and parsed.path == urllib.parse.urlsplit(url).path:
                pages.update(int(page) for page in urllib.parse.parse_qs(parsed.query).get('page', []) if page.isdigit())
    return rows, max(pages)


def _parse_ut_dallas(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    directory = tree.first(cls='faculty-no-arrows')
    group = urllib.parse.urlsplit(url).path.strip('/').split('/')[-1].replace('-', ' ')
    rows = []
    if directory:
        for card in directory.all('ul', cls='wp-block-list'):
            items = list(card.all('li'))
            if len(items) < 2 or not items[0].text() or not items[1].text():
                raise ValueError('UT Dallas directory entry lacks a name or title')
            name = items[0].text()
            title = f'{items[1].text()}; {group}'
            link = items[0].first('a')
            profile = urllib.parse.urljoin(url, link.attrs['href']) if link and link.attrs.get('href') else ''
            # The tenure roster has linked Dutta's card to Fahimi's profile.
            if name == 'Dutta, Sourav' and canonical_url(profile) == 'https://ece.utdallas.edu/fahimi-babk':
                profile = 'https://ece.utdallas.edu/people/tenure-system-faculty/dutta-sourav/'
            host = urllib.parse.urlsplit(profile).hostname or ''
            if profile and (host == 'utdallas.edu' or host.endswith('.utdallas.edu')):
                rows.append(dict(name=name, title=title, profile_url=canonical_url(profile)))
            else:
                rows.append(_scoped_entry(name, title, url, canonical_url, 'utd-ece-directory:' + name))
    if not rows:
        raise ValueError('No UT Dallas ECE directory entries')
    return rows, 0


def _parse_uc_irvine(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    group = urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1].removesuffix('.php')
    rows = []
    if group == 'faculty':
        entries = [(next((h for h in card.all('h4') if h.text()), None),
                    next((detail for detail in card.all('p') if detail.text()), None))
                   for card in tree.all(cls='showcase-grid') if card.text()]
    else:
        content = next((node for node in tree.all(cls='col-lg-8') if node.first('h5')), None)
        entries = []
        if content:
            for title in content.all('h5'):
                following = title.parent.children[title.parent.children.index(title) + 1:]
                detail = next((node for node in following if getattr(node, 'tag', '') in ('h5', 'p')), None)
                if not detail or detail.tag != 'p':
                    detail = title.first('p')
                entries.append((title, detail))
    for heading, detail in entries:
        if not heading or not detail:
            raise ValueError('UC Irvine directory entry lacks name or appointment')
        link = heading.first('a')
        name = link.text() if link else heading.text()
        title = next(iter(_br_chunks(detail)), '')
        if not name or not title:
            raise ValueError('UC Irvine directory entry lacks name or appointment')
        title = f'{title}; official EECS {group} listing'
        profile = urllib.parse.urljoin(url, link.attrs.get('href', '')) if link else ''
        host = urllib.parse.urlsplit(profile).hostname or ''
        if profile and profile != url and (host == 'uci.edu' or host.endswith('.uci.edu')):
            rows.append(dict(name=name, title=title, profile_url=canonical_url(profile)))
        else:
            rows.append(_scoped_entry(name, title, url, canonical_url, 'uci-eecs-directory:' + name))
    if not rows:
        raise ValueError('No UC Irvine EECS directory entries')
    return rows, 0


def _parse_northeastern(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    if urllib.parse.urlsplit(url).path.rstrip('/').endswith('/part-time-faculty'):
        content = tree.first(cls='main__content')
        group = ''
        if content:
            for node in content.children:
                if getattr(node, 'tag', '') == 'h2':
                    group = node.text()
                if getattr(node, 'tag', '') == 'ul' and group in ('Affiliated Research Faculty', 'Part-Time Faculty'):
                    for item in node.all('li'):
                        name = item.text()
                        if not name:
                            raise ValueError('Northeastern supplemental directory entry lacks a name')
                        rows.append(_scoped_entry(name, group, url, canonical_url, 'neu-ece-directory:' + name))
    else:
        for link in tree.all('a', cls='contact__name'):
            card = link.parent.parent
            title = card.first('div', cls='caption')
            departments = [node.text() for node in card.all(cls='contact__title') if node.text()]
            if not link.text() or not link.attrs.get('href'):
                raise ValueError('Northeastern directory entry lacks a name or profile')
            facts = ([title.text().rstrip(',')] if title and title.text() else []) + departments
            rows.append(dict(name=link.text(), title='; '.join(facts) or 'Academic title not supplied by directory',
                             profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
        if any('page-numbers' in a.attrs.get('class', '').split() and '/page/' in a.attrs.get('href', '')
               for a in tree.all('a')):
            raise ValueError('Northeastern view-all request returned a paginated roster')
    if not rows:
        raise ValueError('No Northeastern ECE directory entries')
    return rows, 0


def _parse_florida(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    groups = {'faculty', 'affiliate-faculty', 'emeritus-faculty', 'research-faculty'}
    for card in tree.all(cls='vcard'):
        classes = groups.intersection(card.attrs.get('class', '').split())
        if not classes:
            continue
        name = card.first(cls='fn')
        title = card.first(cls='title')
        link = next((node for node in card.all('a') if node.text() == 'View Profile'), None)
        if not name or not name.text() or not title or not link or not link.attrs.get('href'):
            raise ValueError('Florida ECE directory entry lacks a name, title or profile')
        category = '; '.join(group.replace('-', ' ') for group in sorted(classes))
        rows.append(dict(name=name.text(), title=f'{title.text()}; {category}',
                         profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if not rows:
        raise ValueError('No Florida ECE directory entries')
    return rows, 0


def _parse_caltech(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for section in tree.all(cls='person-list'):
        heading = section.first(cls='person-list__title')
        if not heading or heading.text() not in ('Faculty', 'Emeritus'):
            continue
        for card in section.all(cls='person-teaser'):
            link = card.first('a', cls='person-teaser__link')
            name = card.first(cls='person-teaser__title')
            title = card.first(cls='person-teaser__job-title')
            if not link or not link.attrs.get('href') or not name or not name.text() or not title:
                raise ValueError('Caltech EE directory entry lacks a name, title or profile')
            rows.append(dict(name=name.text(), title=f'{title.text()}; {heading.text()}',
                             profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if not rows:
        raise ValueError('No Caltech EE directory entries')
    return rows, 0


def _parse_nyu(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = {}
    for card in tree.all(cls='node--type-profile'):
        heading = card.first('h3')
        link = heading.first('a') if heading else None
        title = card.first(cls='field--name-field-title')
        if not link or not link.text() or not link.attrs.get('href'):
            raise ValueError('NYU ECE directory entry lacks a name or profile')
        profile = canonical_url(urllib.parse.urljoin(url, link.attrs['href']))
        row = dict(name=link.text(), title=title.text() if title else 'Academic title not supplied by directory',
                   profile_url=profile)
        if profile in rows and rows[profile] != row:
            raise ValueError('NYU ECE roster repeats a profile with conflicting facts')
        rows[profile] = row
    if not rows:
        raise ValueError('No NYU ECE directory entries')
    return list(rows.values()), 0


def _parse_penn(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all(cls='SingleStaffList'):
        name = card.first(cls='StaffListName')
        link = name.first('a') if name else None
        title = card.first(cls='StaffListTitles')
        status = card.first(cls='StaffListSpecialTitle')
        if not link or not link.text() or not link.attrs.get('href') or not title:
            raise ValueError('Penn ESE directory entry lacks a name, title or profile')
        categories = [c.removeprefix('ft-') for c in card.attrs.get('class', '').split() if c.startswith('ft-')]
        parts = [title.text(), status.text() if status else '', 'Directory categories: ' + ', '.join(categories)]
        rows.append(dict(name=link.text(), title='; '.join(part for part in parts if part),
                         profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if not rows:
        raise ValueError('No Penn ESE directory entries')
    return rows, 0


def _parse_ucf(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    affiliate = 'affiliated-faculty' in urllib.parse.urlsplit(url).path
    for card in tree.all(cls='eael-filterable-gallery-item-wrap'):
        content = card.first(cls='fg-layout-3-item-content')
        link = content.first('a') if content else None
        detail = card.first(cls='fg-item-content')
        if not link or not link.text() or not detail:
            raise ValueError('UCF directory entry lacks a name, title or profile')
        title = next(iter(_br_chunks(detail.first('p') or detail, skip_links=True)), '')
        title += '; ' + ('Affiliated Faculty' if affiliate else (card.attrs.get('data-search-categories') or 'Faculty directory'))
        if link.attrs.get('href') and canonical_url(urllib.parse.urljoin(url, link.attrs['href'])) != canonical_url(url):
            rows.append(dict(name=link.text(), title=title,
                             profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
        else:
            rows.append(_scoped_entry(link.text(), title, url, canonical_url, 'ucf-ece-directory:' + link.text()))
    if not rows:
        raise ValueError('No UCF ECE directory entries')
    return rows, 0


def _parse_northwestern(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all(cls='faculty'):
        name = card.first('h3')
        link = name.first('a') if name else None
        detail = card.first(cls='faculty-info')
        if not link or not link.text() or not link.attrs.get('href') or not detail:
            raise ValueError('Northwestern directory entry lacks a name or profile')
        titles = []
        for paragraph in detail.all('p'):
            if paragraph.first('a', cls='mail_link'):
                continue
            if paragraph.text():
                titles.append(paragraph.text())
        rows.append(dict(name=link.text(), title='; '.join(titles) or 'Academic title not supplied by directory',
                         profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if not rows:
        raise ValueError('No Northwestern ECE directory entries')
    return rows, 0


def _parse_harvard(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    if urllib.parse.urlsplit(url).path.rstrip('/') == '/electrical-engineering/faculty-research':
        heading = next((node for node in tree.all('h2')
                        if node.text() == 'Electrical & Computer Engineering Faculty'), None)
        rows = {}
        section = heading.parent.parent if heading and heading.parent else None
        if section and 'view-content' in section.attrs.get('class', '').split():
            for link in section.all('a'):
                href = link.attrs.get('href', '')
                if not href.startswith('/person/') or not link.text():
                    continue
                profile = canonical_url(urllib.parse.urljoin(url, href))
                rows[profile] = dict(name=link.text(), profile_url=profile,
                                     title='Listed under Electrical & Computer Engineering Faculty')
        if not rows:
            raise ValueError('No Harvard EE faculty research profiles')
        return list(rows.values()), 0
    rows = []
    for card in tree.all(cls='person__detailed'):
        heading = card.first(cls='person__detailed-name')
        link = heading.first('a') if heading else None
        title = card.first(cls='person-directory__primary-title')
        if not heading or not heading.text():
            raise ValueError('Harvard directory entry lacks a name')
        title_text = title.text() if title else 'Academic title not supplied by directory'
        if link and link.attrs.get('href'):
            rows.append(dict(name=link.text(), title=title_text,
                             profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
        else:
            base = urllib.parse.urlunsplit(urllib.parse.urlsplit(url)._replace(query=''))
            rows.append(_scoped_entry(heading.text(), title_text, base, canonical_url,
                                      'harvard-ee-directory:' + heading.text()))
    if not rows:
        raise ValueError('No Harvard EE directory entries')
    pages = {0}
    for link in tree.all('a'):
        target = urllib.parse.urlsplit(urllib.parse.urljoin(url, link.attrs.get('href','')))
        if target.netloc != urllib.parse.urlsplit(url).netloc or target.path != urllib.parse.urlsplit(url).path:
            continue
        for value in urllib.parse.parse_qs(target.query).get('page', []):
            match = re.fullmatch(r',(\d+)', value)
            if match:
                pages.add(int(match[1]))
    return rows, max(pages)


def _parse_notre_dame(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all(cls='results-list__item--faculty'):
        link = card.first('a', cls='card-link')
        content = card.first(cls='card-body')
        paragraphs = list(content.all('p')) if content else []
        title = next((node.text() for node in paragraphs if 'card-title' not in node.attrs.get('class', '').split()), '')
        if not link or not link.text() or not link.attrs.get('href') or not title:
            raise ValueError('Notre Dame EE directory entry lacks a name, title or profile')
        rows.append(dict(name=link.text(), title=title,
                         profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if not rows:
        raise ValueError('No Notre Dame EE directory entries')
    return rows, 0


def _parse_utah(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all(cls='person-container'):
        heading = card.first('h2', cls='t-entry-title')
        detail = card.first('h3', cls='t-entry-meta')
        if not heading or not heading.text() or not detail:
            raise ValueError('Utah ECE directory entry lacks a name or title')
        title_parts = []
        for part in detail.children:
            if getattr(part, 'tag', '') == 'hr':
                break
            value = compact(part) if isinstance(part, str) else part.text()
            if value:
                title_parts.append(value)
        title = '; '.join(title_parts)
        if not title:
            raise ValueError('Utah ECE directory entry lacks an appointment')
        rows.append(_scoped_entry(heading.text(), title, url, canonical_url, 'utah-ece-directory:' + heading.text()))
    if not rows:
        raise ValueError('No Utah ECE directory entries')
    return rows, 0


def _parse_buffalo(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all(cls='profileinfo-teaser'):
        name = card.first(cls='profileinfo-teaser-name')
        link = name.first('a') if name else None
        titles = [node.text() for node in card.all(cls='profileinfo-teaser-dept') if node.text()]
        if not name or not titles:
            raise ValueError('Buffalo ECE directory entry lacks a name or title')
        if link and link.text() and link.attrs.get('href'):
            rows.append(dict(name=link.text(), title='; '.join(titles),
                             profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
        else:
            label = name.first('b')
            if not label or not label.text():
                raise ValueError('Buffalo ECE unlinked entry lacks a name')
            display_name = label.text().rstrip(' ,')
            rows.append(_scoped_entry(display_name, '; '.join(titles), url, canonical_url,
                                      'buffalo-ece-directory:' + display_name))
    if not rows:
        raise ValueError('No Buffalo ECE directory entries')
    return rows, 0


def _parse_yale(body, url, canonical_url):
    data = json.loads(body.decode('utf-8'))
    pages = data.get('pages')
    if not isinstance(pages, dict):
        raise ValueError('Yale faculty response lacks appointment groups')
    rows = []
    for group in pages.values():
        for person in group['facultyMembers']:
            name = compact(person.get('name', ''))
            profile = person.get('url', '')
            title = compact(person.get('fullTitle') or person.get('title') or '')
            if not name or not profile or not title:
                raise ValueError('Yale directory entry lacks a name, title or profile')
            rows.append(dict(name=name, title=f'{title}; {group["name"]}',
                             profile_url=canonical_url(urllib.parse.urljoin(url, profile))))
    if not rows:
        raise ValueError('No Yale ECE directory entries')
    return rows, 0


def _parse_rice(body, url, canonical_url):
    rows = []
    if urllib.parse.urlsplit(url).hostname == 'web-api2.rice.edu':
        data = json.loads(body.decode('utf-8'))
        group = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('tag', [''])[0]
        if not group.startswith('ECE - '):
            raise ValueError('Rice faculty collection requires an explicit ECE tag')
        for person in data.get('data', []):
            name = compact(' '.join([person.get('fname', ''), person.get('lname', '')]))
            profile = person.get('profile_url', '')
            title = _strip_tags(person.get('title', ''))
            if not name or not profile or not title:
                raise ValueError('Rice ECE API entry lacks a name, title or profile')
            rows.append(dict(name=name, title=f'{title}; {group}', profile_url=canonical_url(profile)))
    else:
        tree = Tree(body.decode('utf-8', errors='replace')).root
        block = next((node for node in tree.all() if node.attrs.get('id') == 'block-adjunctfacultylist'), None)
        if block:
            for name in block.all('strong'):
                if name.text():
                    rows.append(_scoped_entry(name.text(), 'Adjunct Faculty', url, canonical_url,
                                              'rice-ece-directory:' + name.text()))
    if not rows:
        raise ValueError('No Rice ECE directory entries')
    return rows, 0


def _parse_boston(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    control = next((node for node in tree.all('select') if node.attrs.get('name') == 'filter_by_department'), None)
    selected = [o.attrs.get('value') for o in control.all('option') if 'selected' in o.attrs] if control else []
    if selected != ['electrical-computer-engineering']:
        raise ValueError('Boston University directory did not apply the ECE department filter')
    rows = []
    for card in tree.all('li', cls='bu-filtering-result-item'):
        heading = card.first('h4', cls='bu-filtering-result-item-title')
        link = heading.first('a') if heading else None
        title = card.first('div', cls='bu-filtering-result-item-title')
        if not link or not link.text() or not link.attrs.get('href') or not title:
            raise ValueError('Boston ECE directory entry lacks a name, title or profile')
        rows.append(dict(name=link.text(), title=title.text(),
                         profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if not rows:
        raise ValueError('No Boston University ECE directory entries')
    pages = {0}
    for link in tree.all('a', cls='page-numbers'):
        target = urllib.parse.urlsplit(urllib.parse.urljoin(url, link.attrs.get('href', '')))
        if target.netloc != urllib.parse.urlsplit(url).netloc or target.path.rstrip('/') != urllib.parse.urlsplit(url).path.rstrip('/'):
            continue
        pages.update(int(value) - 1 for value in urllib.parse.parse_qs(target.query).get('num', []) if value.isdigit() and int(value) > 0)
    return rows, max(pages)


def _parse_michigan_state(body, url, canonical_url):
    data = json.loads(body.decode('utf-8'))
    if not isinstance(data.get('people'), list):
        raise ValueError('Michigan State directory response lacks people')
    rows = []
    department = 'Electrical and Computer Engineering'
    for person in data['people']:
        primary = person.get('primary') or {}
        others = person.get('others') or []
        is_primary = primary.get('name') == department
        ece_titles = [item.get('title', '') for item in others if item.get('name') == department]
        if not is_primary and not ece_titles:
            continue
        name, profile = person.get('name', ''), person.get('url', '')
        if not name or not profile:
            raise ValueError('Michigan State ECE entry lacks a name or profile')
        title = person.get('position') or 'Academic title not supplied by directory'
        parts = [title, person.get('employment', ''), 'Primary department: ' + primary.get('name', '')]
        parts.extend('ECE appointment: ' + title for title in ece_titles)
        rows.append(dict(name=name, title='; '.join(part for part in parts if part),
                         profile_url=canonical_url(urllib.parse.urljoin(url, profile))))
    if not rows:
        raise ValueError('No Michigan State ECE entries')
    return rows, 0


def _parse_iowa_state(body, url, canonical_url):
    if '/wp-json/wp/v2/profile' in url:
        dept = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('department', [''])[0]
        groups = {
            '1121': 'ECpE Faculty',
            '1122': 'ECpE Affiliate Faculty',
            '1123': 'ECpE Adjunct Faculty',
            '1124': 'ECpE Courtesy Appointments',
            '1259': 'ECpE Emeritus and Retired Faculty',
        }
        group_label = groups.get(dept, 'ECpE Directory')
        data = json.loads(body.decode('utf-8', errors='replace'))
        if not isinstance(data, list):
            raise ValueError('Iowa State WP profile API response is not a list')
        rows = []
        for item in data:
            raw_name = (item.get('title') or {}).get('rendered') or ''
            name = compact(html.unescape(raw_name))
            pid = item.get('id')
            if not name or not pid:
                raise ValueError('Iowa State WP profile lacks name or id')
            titles = [compact(html.unescape(item.get(k) or '')) for k in ('isu_title', 'user_title')]
            titles = [t for t in titles if t]
            full_title = '; '.join(list(dict.fromkeys(titles)) + [group_label])
            rows.append(_scoped_entry(name, full_title, url, canonical_url, f'isu-ecpe-wp:{pid}'))
        if not rows:
            raise ValueError('No Iowa State WP ECpE entries')
        return rows, 0
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for heading in tree.all('h4'):
        following = heading.parent.children[heading.parent.children.index(heading) + 1:]
        detail = next((node for node in following if getattr(node, 'tag', '') in ('h4', 'p')), None)
        if not detail or detail.tag != 'p' or 'Electrical and Computer Engineering' not in detail.text():
            continue
        name = heading.text()
        title = detail.text().split('. Ph.D.')[0]
        if not name:
            raise ValueError('Iowa State catalog appointment lacks a name')
        rows.append(_scoped_entry(name, title, url, canonical_url, 'iowa-ece-catalog:' + name))
    if not rows:
        raise ValueError('No Iowa State ECE catalog appointments')
    return rows, 0


def _parse_boulder(body, url, canonical_url):
    if '/jsonapi/node/ucb_person' in url:
        data = json.loads(body.decode('utf-8', errors='replace'))
        inc = {x['id']: compact((x.get('attributes') or {}).get('name') or '')
               for x in data.get('included', []) if x.get('type') == 'taxonomy_term--ucb_person_job_type'}
        rows = []
        for item in data.get('data', []):
            attrs = item.get('attributes') or {}
            if not attrs.get('status'):
                continue
            name = compact(attrs.get('title') or '')
            rels = ((item.get('relationships') or {}).get('field_ucb_person_job_type') or {}).get('data') or []
            jtypes = [inc.get(r['id'], '') for r in rels if inc.get(r['id'], '')]
            ptitles = [compact(t) for t in (attrs.get('field_ucb_person_title') or []) if compact(t)]
            title = '; '.join(list(dict.fromkeys(ptitles + jtypes))) or 'Academic title not supplied'
            alias = ((attrs.get('path') or {}).get('alias') or '').strip()
            profile = canonical_url(f'https://www.colorado.edu/ecee{alias}') if alias else canonical_url(url)
            if not name:
                raise ValueError('Colorado ECEE JSON:API entry lacks a name')
            rows.append(dict(name=name, title=title, profile_url=profile))
        if not rows:
            raise ValueError('No Colorado ECEE JSON:API entries')
        return rows, 0
    tree = Tree(body.decode('utf-8', errors='replace')).root
    section = next((node for node in tree.all() if node.attrs.get('id') == 'facultytextcontainer'), None)
    rows = []
    if section:
        for card in section.all('p', cls='keeptogether'):
            link = card.first('a')
            title = '; '.join(_br_chunks(card, skip_links=True))
            if link and link.text() and link.attrs.get('href'):
                if not title:
                    raise ValueError('Colorado ECEE catalog entry lacks a title')
                rows.append(dict(name=link.text(), title=title.split('; PhD')[0],
                                 profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
            else:
                parts = _br_chunks(card)
                if len(parts) != 2:
                    raise ValueError('Colorado ECEE unlinked entry lacks a name or title')
                rows.append(_scoped_entry(parts[0], parts[1].split('; PhD')[0], url, canonical_url,
                                          'boulder-ecee-catalog:' + parts[0]))
    if not rows:
        raise ValueError('No Colorado ECEE catalog entries')
    return rows, 0


def _parse_riverside(body, url, canonical_url):
    groups = {'4108': 'Tenure Track Faculty', '4035': 'Cooperating Faculty',
              '4080': 'Adjunct Faculty', '65515': 'Emeriti',
              '135209': 'Lecturers', '22361': 'Research Faculty'}
    group = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('groupId', [''])[0]
    if group not in groups:
        raise ValueError('UC Riverside collection requires a registered ECE group')
    data = json.loads(body.decode('utf-8'))
    if not isinstance(data, list):
        raise ValueError('UC Riverside faculty response is not a profile list')
    rows = []
    for person in data:
        name = person.get('displayName') or person.get('name')
        netid = person.get('netId')
        titles = [person.get('title')] + (person.get('otherTitles') or [])
        titles = list(dict.fromkeys(compact(t) for t in titles if t))
        if not name or not netid or not titles:
            raise ValueError('UC Riverside ECE entry lacks a name, title or identifier')
        # Entries without a university department can retain a public group
        # biography while their individual profile endpoint is unavailable.
        # Keep the official group entry as evidence and preserve netID identity.
        profile = 'https://profiles.ucr.edu/api/profile/' + netid if person.get('department') else url
        rows.append(_scoped_entry(compact(name), '; '.join(titles) + '; ECE ' + groups[group],
                                  profile, canonical_url, 'riverside-ece-api:' + netid))
    if not rows:
        raise ValueError('No UC Riverside ECE entries')
    return rows, 0


def _parse_rutgers(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all('div', cls='c--person-card'):
        heading = card.first('h3')
        title = card.first('p', cls='title')
        link = next((a for a in card.all('a') if a.text().casefold() == 'view full profile'), None)
        if not heading or not title or not link or not link.attrs.get('href'):
            raise ValueError('Rutgers faculty card lacks a name, title or profile')
        rows.append(dict(name=heading.text(), title=title.text(),
                         profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
    if rows:
        return rows, 0
    # Graduate and emeritus listings are coverage cross-checks. Preserve their
    # factual name/appointment fields without contact or research-interest text.
    for block in tree.all('div', cls='c--rich-text'):
        for paragraph in block.all('p'):
            name = paragraph.first('strong')
            if not name:
                continue
            chunks = _br_chunks(paragraph)
            if len(chunks) < 2 or chunks[0] != name.text():
                raise ValueError('Rutgers coverage entry lacks a department or title')
            title = chunks[1]
            if '@' in title:
                title = chunks[2] if len(chunks) > 2 else ''
            if not title or '@' in title:
                raise ValueError('Rutgers coverage entry lacks an appointment field')
            statuses = [part for part in chunks[2:] if re.match(r'^(Retired|Deceased)\b', part)]
            if statuses:
                title += '; ' + '; '.join(statuses)
            rows.append(_scoped_entry(name.text(), title, url, canonical_url,
                                      'rutgers-ece-coverage:' + name.text()))
    if not rows:
        raise ValueError('No Rutgers ECE faculty entries')
    return rows, 0


def _parse_davis(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = {}
    allowed = {'Faculty', 'Adjunct and Visiting Faculty', 'Graduate Program Faculty',
               'Professional Researcher', 'Emeriti Faculty'}
    for block in tree.all('div', cls='view-content'):
        group = None
        for node in block.children:
            if getattr(node, 'tag', '') == 'h3':
                group = node.text()
            elif getattr(node, 'tag', '') == 'article' and group in allowed:
                heading = node.first('h3', cls='vm-teaser__title')
                link = heading.first('a') if heading else None
                position = node.first('ul', cls='vm-teaser__position')
                if not link or not position or not link.attrs.get('href'):
                    raise ValueError('UC Davis faculty entry lacks a name, title or profile')
                profile = canonical_url(urllib.parse.urljoin(url, link.attrs['href']))
                title = position.text() + '; Directory category: ' + group
                if profile in rows:
                    rows[profile]['title'] += '; ' + title
                else:
                    rows[profile] = dict(name=link.text(), title=title, profile_url=profile)
    if not rows:
        raise ValueError('No UC Davis faculty directory entries')
    return list(rows.values()), 0


def _parse_virginia(body, url, canonical_url):
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    for card in tree.all('div', cls='people_list_item_header'):
        link = card.first('a', cls='contact_block_name_link')
        name = link.first('span', cls='contact_block_name_link_label') if link else card.first('h2', cls='people_list_item_name')
        titles = [n.text() for n in card.all('span', cls='people_list_item_title')]
        if not name or not name.text() or not titles:
            raise ValueError('Virginia faculty entry lacks a name, title or profile')
        if link and link.attrs.get('href'):
            rows.append(dict(name=name.text(), title='; '.join(titles),
                             profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href']))))
        else:
            rows.append(_scoped_entry(name.text(), '; '.join(titles), url, canonical_url,
                                      'virginia-ece-directory:' + name.text()))
    if not rows:
        raise ValueError('No Virginia faculty directory entries')
    return rows, 0


def _walk(node):
    for child in node.children:
        if hasattr(child, 'tag'):
            yield child
            yield from _walk(child)


def _has_class(node, spec):
    """Whole-class match; a spec starting with '^' matches a class prefix (for hashed build classes)."""
    tokens = (node.attrs.get('class') or '').split()
    if spec.startswith('^'):
        return any(t.startswith(spec[1:]) for t in tokens)
    return spec in tokens


def _by_class(node, specs):
    specs = [specs] if isinstance(specs, str) else list(specs or [])
    return (n for n in _walk(node) if any(_has_class(n, sp) for sp in specs))


def _useful_link(card, name, exclude=()):
    for scope in (name, card):
        for link in _walk(scope):
            href = link.attrs.get('href') if link.tag == 'a' else None
            if href and not href.startswith(('#', 'mailto:', 'tel:')) and 'email-protection' not in href \
                    and not any(pattern in href for pattern in exclude):
                return link
    return None


def _decode_js_html(body):
    """Concatenate the string literals of `page_html += "..."` statements (a script that document.write()s the page)."""
    text = body.decode('utf-8', errors='replace')
    parts = re.findall(r'page_html\s*\+=\s*"((?:[^"\\]|\\.)*)"\s*;', text)
    if not parts:
        raise ValueError('No page_html string statements found in script')
    simple = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}

    def unescape(match):
        token = match.group(1)
        if token[0] in 'ux' and len(token) > 1:
            return chr(int(token[1:], 16))
        return simple.get(token, token)

    decoded = [re.sub(r'\\(u[0-9a-fA-F]{4}|x[0-9a-fA-F]{2}|.)', unescape, part) for part in parts]
    return ''.join(decoded).encode('utf-8')


def _parse_json_list(body, url, canonical_url, options):
    """Directory JSON: {list_key: [records]} with configured name/title/link fields."""
    options = options or {}
    label = options.get('school_label', 'json')
    try:
        data = json.loads(body.decode('utf-8', errors='replace'))
    except ValueError as exc:
        raise ValueError(f'{label} directory response is not JSON') from exc
    items = data.get(options.get('list_key', 'list')) if isinstance(data, dict) else data
    if not isinstance(items, list) or not options.get('name'):
        raise ValueError(f'{label} directory JSON lacks its record list or name field')
    rows = []
    for item in items:
        name = ' '.join(str(item.get(options['name']) or '').split())
        if options.get('title_join'):
            # Keep every configured field (lists flattened) so a record's category tags stay in the title.
            parts = []
            for key in options.get('title', []):
                value = item.get(key)
                for part in (value if isinstance(value, list) else [value]):
                    part = ' '.join(str(part or '').split())
                    if part and part not in parts:
                        parts.append(part)
            title = '; '.join(parts)
        else:
            title = next((' '.join(str(item.get(k) or '').split()) for k in options.get('title', []) if item.get(k)), '')
        if options.get('title_prefix'):
            title = '; '.join([options['title_prefix']] + ([title] if title else []))
        if not name or (not title and not options.get('title_optional')):
            raise ValueError(f'{label} directory record lacks a name or title')
        href = item.get(options['link']) if options.get('link') else None
        if href:
            rows.append(dict(name=name, title=title, profile_url=canonical_url(urllib.parse.urljoin(url, href))))
        else:
            rows.append(_scoped_entry(name, title, url, canonical_url, f'{label}-directory:{name}'))
    if not rows:
        raise ValueError(f'No {label} directory records')
    return rows, max(int(options.get('pages', 1)) - 1, 0)


def _parse_cards(body, url, canonical_url, options):
    """Config-driven card or table layout; options name the page structure.

    options: card (class, '^prefix' class, or list) or card_tag='tr'; name (class) or
    name_tag or name_cell; title (class), title_tag or title_cell (optional with
    title_optional); title_attrs (card attributes prefixed to the title, e.g. data-degree);
    heading (tag whose latest text is prefixed to each title so sections such as
    'Emeritus' are preserved); scope (class of the container to read, e.g. to skip a
    footer); decode_js (the page is a script of `page_html += "..."` statements; decode it first); name_split_br (name element holds 'Name,<br>Title': split at the br); column_lists (true: a table whose header cells name the categories and whose cells hold <li> names); title_prefix (constant prefix such as 'Affiliated Faculty' for a page section without a heading tag); where ({class, contains} or a list of them: keep only cards where any descendant of that class contains the text);
    pages (number of ?page=N result pages); title_sep; school_label.
    Missing names or titles fail visibly instead of becoming an empty roster.
    """
    options = options or {}
    if options.get('decode_js'):
        body = _decode_js_html(body)
    table = options.get('card_tag') == 'tr'
    card_specs = [options['card']] if isinstance(options.get('card'), str) else list(options.get('card') or [])
    name_ok = options.get('name') or options.get('name_tag') or options.get('name_cell') is not None
    plain = options.get('column_lists') or options.get('li_after_heading') or options.get('strong_lines_after_heading')
    if not (card_specs or table or plain) or not (name_ok or plain):
        raise ValueError('cards adapter requires a card selector and a name selector')
    if not (options.get('title') or options.get('title_tag') or options.get('title_cell') is not None
            or options.get('title_optional') or options.get('heading') or plain):
        raise ValueError('cards adapter requires a title selector, heading or title_optional')
    tree = Tree(body.decode('utf-8', errors='replace')).root
    label = options.get('school_label', 'cards')
    if options.get('scope'):
        roots = list(_by_class(tree, options['scope']))
        if not roots:
            raise ValueError(f'{label} directory scope container not found')
        nodes = (n for root in roots for n in _walk(root))
    else:
        nodes = _walk(tree)
    rows, heading = [], ''
    if options.get('strong_lines_after_heading'):
        # Plain <div><strong>Name</strong>, Rank, degree...</div> lines under a heading containing the given text.
        spec = options['strong_lines_after_heading']
        active = False
        for node in _walk(tree):
            if node.tag == spec.get('tag', 'h2'):
                active = spec['contains'].lower() in node.text().lower()
            elif active and node.tag in ('div', 'p'):
                kids = [c for c in node.children if hasattr(c, 'tag')]
                if not kids or any(k.tag in ('div', 'p') for k in kids):
                    continue
                entries, current = [], None
                for child in node.children:
                    if hasattr(child, 'tag') and child.tag == 'strong':
                        current = [' '.join(child.text().replace('\xa0', ' ').strip(' ,\xa0').split()), []]
                        entries.append(current)
                    elif hasattr(child, 'tag') and child.tag == 'br':
                        current = None
                    elif current is not None:
                        current[1].append(child.text() if hasattr(child, 'tag') else str(child))
                for name_text, bits in entries:
                    rest = ' '.join(' '.join(bits).replace('\xa0', ' ').split()).strip(' ,')
                    rank = rest.split(',')[0].strip()
                    if not name_text:
                        continue
                    title = '; '.join([spec.get('title_prefix', spec['contains'])] + ([rank] if rank else []))
                    rows.append(_scoped_entry(name_text, title, url, canonical_url, f'{label}-directory:{name_text}'))
        if not rows:
            raise ValueError(f'No {label} directory entries')
        return rows, 0
    if options.get('li_after_heading'):
        # Plain <ul><li>Last, First, Rank</li></ul> lists that follow a heading containing the given text.
        spec = options['li_after_heading']
        active = False
        for node in _walk(tree):
            if node.tag == spec.get('tag', 'h3'):
                active = spec['contains'].lower() in node.text().lower()
            elif active and node.tag == 'ul':
                for item in node.all('li'):
                    text = ' '.join(item.text().split())
                    if not text:
                        continue
                    name_text, _, rank = text.rpartition(', ')
                    if not name_text:
                        name_text, rank = text, ''
                    title = '; '.join([spec.get('title_prefix', spec['contains'])] + ([rank] if rank else []))
                    link = item.first('a')
                    href = link.attrs.get('href') if link else None
                    if href and href.startswith('http'):
                        rows.append(dict(name=name_text, title=title, profile_url=canonical_url(urllib.parse.urljoin(url, href))))
                    else:
                        rows.append(_scoped_entry(name_text, title, url, canonical_url, f'{label}-directory:{name_text}'))
                active = False
        if not rows:
            raise ValueError(f'No {label} directory entries')
        return rows, 0
    if options.get('column_lists'):
        # A table whose header row names the categories and whose cells hold <li> names.
        for table_node in tree.all('table'):
            headers = [th.text() for th in table_node.all('th')]
            if not headers:
                continue
            for tr in table_node.all('tr'):
                cells = [c for c in tr.children if hasattr(c, 'tag') and c.tag == 'td']
                for index, cell in enumerate(cells):
                    category = headers[index] if index < len(headers) else ''
                    for item in cell.all('li'):
                        parts = []
                        for child in item.children:
                            if hasattr(child, 'tag') and child.tag == 'br':
                                break
                            parts.append(child.text() if hasattr(child, 'tag') else str(child))
                            if hasattr(child, 'tag') and child.tag == 'a':
                                parts.pop()
                                break
                        name_text = ' '.join(' '.join(parts).split())
                        if not name_text:
                            continue
                        detail = ' '.join(item.text().split())
                        title = '; '.join([category] + ([detail[len(name_text):].strip()] if detail != name_text and detail[len(name_text):].strip() else []))
                        rows.append(_scoped_entry(name_text, title, url, canonical_url, f'{label}-directory:{name_text}'))
        if not rows:
            raise ValueError(f'No {label} directory entries')
        return rows, 0
    for node in nodes:
        if options.get('heading') and node.tag == options['heading']:
            heading = node.text()
            continue
        if options.get('only_under_heading') and options['only_under_heading'].lower() not in heading.lower():
            continue
        if table:
            if node.tag != 'tr':
                continue
            cells = [c for c in node.children if hasattr(c, 'tag') and c.tag in ('td', 'th')]
            if not cells or all(c.tag == 'th' for c in cells):
                continue
            name = cells[options['name_cell']] if len(cells) > options['name_cell'] else None
            titles = [cells[options['title_cell']].text()] if options.get('title_cell') is not None and len(cells) > options['title_cell'] else []
            card = node
        else:
            if not any(_has_class(node, sp) for sp in card_specs):
                continue
            card = node
            where = options.get('where')
            conditions = [where] if isinstance(where, dict) else list(where or [])
            if conditions and not any(c['contains'].lower() in n.text().lower() for c in conditions for n in _by_class(card, c['class'])):
                continue
            if options.get('name'):
                name = next(_by_class(card, options['name']), None)
            else:
                tags = [options['name_tag']] if isinstance(options['name_tag'], str) else list(options['name_tag'])
                name = next((found for tag in tags for found in [card.first(tag)] if found and found.text()), None)
            if options.get('title'):
                titles = [n.text() for n in _by_class(card, options['title'])]
            elif options.get('title_tag'):
                titles = [n.text() for n in card.all(options['title_tag'])]
            else:
                titles = []
        titles = [t for t in titles if t]
        for attr in reversed(options.get('title_attrs') or []):
            if card.attrs.get(attr):
                titles = [card.attrs[attr]] + titles
        if options.get('heading') and heading:
            titles = [heading] + titles
        if options.get('title_prefix'):
            titles = [options['title_prefix']] + titles
        if not name or not name.text() or (not titles and not options.get('title_optional') and not options.get('name_split_br')):
            raise ValueError(f'{label} directory entry lacks a name or title')
        link = _useful_link(card, name, options.get('link_exclude') or ())
        href = link.attrs.get('href') if link else None
        name_text = name.text()
        if options.get('name_split_br'):
            before, after, seen = [], [], False
            for child in name.children:
                if hasattr(child, 'tag') and child.tag == 'br':
                    seen = True
                    continue
                (after if seen else before).append(child.text() if hasattr(child, 'tag') else str(child))
            if seen:
                name_text = ' '.join(' '.join(before).split()).rstrip(' ,')
                tail = ' '.join(' '.join(after).split())
                if tail:
                    titles = titles + [tail]
        title = options.get('title_sep', '; ').join(titles)
        if href:
            rows.append(dict(name=name_text, title=title, profile_url=canonical_url(urllib.parse.urljoin(url, href))))
        else:
            rows.append(_scoped_entry(name_text, title, url, canonical_url, f'{label}-directory:{name_text}'))
    if not rows:
        raise ValueError(f'No {label} directory entries')
    # One person listed under several headings stays one entry; every title is kept.
    merged = {}
    for row in rows:
        key = row.get('entry_id') or row['profile_url']
        if key in merged:
            if row['title'] not in merged[key]['title'].split(' | '):
                merged[key]['title'] += ' | ' + row['title']
        else:
            merged[key] = row
    return list(merged.values()), max(0, int(options.get('pages', 1)) - 1)


def parse(body, url, adapter, canonical_url, options=None):
    if adapter == 'cards':
        return _parse_cards(body, url, canonical_url, options)
    if adapter == 'json_list':
        return _parse_json_list(body, url, canonical_url, options)
    handlers = {
        'asu': _parse_asu,
        'tamu': _parse_tamu,
        'vt': _parse_vt,
        'cmu': _parse_cmu,
        'princeton': _parse_princeton,
        'cornell': _parse_cornell,
        'columbia': _parse_columbia,
        'umn': _parse_umn,
        'psu': _parse_psu,
        'wisconsin': _parse_wisconsin,
        'washington': _parse_washington,
        'ucsb': _parse_ucsb,
        'ohio-state': _parse_ohio_state,
        'ut-dallas': _parse_ut_dallas,
        'uc-irvine': _parse_uc_irvine,
        'northeastern': _parse_northeastern,
        'florida': _parse_florida,
        'caltech': _parse_caltech,
        'nyu': _parse_nyu,
        'penn': _parse_penn,
        'ucf': _parse_ucf,
        'northwestern': _parse_northwestern,
        'harvard': _parse_harvard,
        'notre-dame': _parse_notre_dame,
        'utah': _parse_utah,
        'buffalo': _parse_buffalo,
        'yale': _parse_yale,
        'rice': _parse_rice,
        'boston': _parse_boston,
        'michigan-state': _parse_michigan_state,
        'iowa-state': _parse_iowa_state,
        'boulder': _parse_boulder,
        'riverside': _parse_riverside,
        'rutgers': _parse_rutgers,
        'davis': _parse_davis,
        'virginia': _parse_virginia,
    }
    if adapter in handlers:
        return handlers[adapter](body, url, canonical_url)
    tree = Tree(body.decode('utf-8', errors='replace')).root
    rows = []
    if adapter == 'michigan':
        for card in tree.all(cls='eecs_person_wrapper'):
            name = card.first(cls='eecs_person_name')
            titles = [n.text() for n in card.all(cls='person_title_section')]
            if not name or not titles:
                raise ValueError('Michigan directory entry lacks name or appointment')
            image = card.first('img')
            official_id = ((image.attrs.get('src') if image else '') or '') + '#name=' + name.text()
            # An entry ID is a local key anchored to the university's portrait
            # identifier/name, not an invented individual-profile URL.
            entry_id = 'umich-ece-directory:' + official_id
            ece_titles = [s for s in titles if re.search(r'electrical\s*(?:and\s*)?computer\s*engineering', s, re.I)]
            rows.append(dict(
                name=name.text(),
                title='; '.join(ece_titles or titles),
                all_appointment_titles=titles,
                profile_url=canonical_url(url),
                entry_id=entry_id,
                profile_kind='official_directory_entry',
            ))
        if not rows:
            raise ValueError('No Michigan directory entries; challenge/error pages are not rosters')
        return rows, 0
    selectors = {'mit': 'people-entry', 'purdue': 'list-name',
                 'ucsd': 'faculty-member', 'ucla': 'et_pb_post',
                 'maryland': 'faculty_row', 'duke': 'faculty-overview__info'}
    if adapter == 'ncstate':
        selectors[adapter] = ('profile-tile' if urllib.parse.urlsplit(url).path.rstrip('/') == '/supporting-faculty'
                              else 'staff-list')
    for card in tree.all(cls=selectors[adapter]):
        if adapter == 'mit':
            name = card.first('h5')
            title = next((n for n in card.children if getattr(n, 'tag', None) in ('p', 'div')
                          and 'people-research' not in n.attrs.get('class', '').split()), None)
            link = card.first('a')
            title = title.text() if title else ''
        elif adapter == 'purdue':
            link, title_node = card.first('a'), card.first(cls='short-title')
            name = link
            title = title_node.text() if title_node else ''
            group = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get('show_group', [''])[0]
            if not title and group in ('visiting-faculty', 'retired-faculty'):
                title = group.replace('-', ' ') + ' (academic rank not supplied by directory)'
        elif adapter == 'duke':
            name = card.first('h3')
            link = name.first('a') if name else None
            detail = card.first('p')
            title = detail.text() if detail else ''
        elif adapter == 'ncstate':
            name = card.first(cls='faculty-list-name')
            if name:
                link = name.parent
                detail = card.first(cls='faculty-list-title')
                title = detail.text() if detail else ''
            else:
                heading = card.first('h2')
                link = heading.first('a') if heading else None
                name = link
                title = next((compact(part) for part in card.children if isinstance(part, str) and part.strip()), '')
        elif adapter == 'maryland':
            card_details = card.first(cls='field-directory-name-title-wrapper')
            link = card_details.first('a') if card_details else None
            name = link
            title_node = card_details.first(cls='title-wrapper') if card_details else None
            title = '; '.join(node.text() for node in title_node.all('h3') if node.text()) if title_node else ''
            if not title:
                title = 'Academic title not supplied by directory'
        elif adapter == 'ucsd':
            name = card.first('h2') or card.first('h3')
            link = name.first('a') if name else None
            paragraph = card.first('p')
            parts = []
            if paragraph:
                for child in paragraph.children:
                    if getattr(child, 'tag', None) == 'a':
                        break
                    if isinstance(child, str):
                        parts.append(child)
            title = compact(' '.join(parts))
            if name and not link and title:
                rows.append(dict(
                    name=name.text(),
                    title=title,
                    profile_url=canonical_url(url),
                    entry_id='ucsd-ece-directory:' + name.text(),
                    profile_kind='official_directory_entry',
                ))
                continue
        else:
            name = card.first('h2', cls='entry-title')
            link = name.first('a') if name else None
            groups = sorted(c.removeprefix('seas_department-') for c in card.attrs.get('class', '').split()
                            if c.startswith('seas_department-'))
            # The archive supplies taxonomy, not rank. Profiles must resolve rank.
            title = 'Official faculty directory categories: ' + ', '.join(groups)
        if not name or not link or not link.attrs.get('href') or not name.text() or not title:
            raise ValueError('Directory layout changed: missing name, appointment or profile')
        rows.append(dict(
            name=name.text(),
            title=title,
            profile_url=canonical_url(urllib.parse.urljoin(url, link.attrs['href'])),
        ))
    if not rows:
        raise ValueError('No directory entries; failed parsing is not an empty school')
    pages = {0}
    for link in tree.all('a'):
        target = urllib.parse.urlsplit(urllib.parse.urljoin(url, link.attrs.get('href', '')))
        origin = urllib.parse.urlsplit(url)
        if target.netloc != origin.netloc:
            continue
        if adapter in ('ucla', 'duke'):
            if adapter == 'duke' and target.query != origin.query:
                continue
            base_path = re.sub(r'/page/\d+/?$', '', origin.path.rstrip('/'))
            match = re.fullmatch(re.escape(base_path) + r'/page/(\d+)/?', target.path)
            if match:
                pages.add(int(match[1]) - 1)
        elif target.path == origin.path:
            pages.update(int(v) for v in urllib.parse.parse_qs(target.query).get('page', []) if v.isdigit())
    return rows, max(pages)


def page_url(url, page, adapter):
    if adapter in ('harvard', 'boston'):
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if adapter == 'harvard':
            query['page'] = [f',{page}']
        else:
            query['num'] = [str(page + 1)]
        return urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query, doseq=True)))
    if adapter not in ('ucla', 'duke'):
        raise ValueError('Unsupported path pagination adapter')
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(parsed._replace(path=parsed.path.rstrip('/') + f'/page/{page + 1}/'))
