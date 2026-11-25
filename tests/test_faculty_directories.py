"""Coverage and factual extraction for university faculty directory layouts."""
from pathlib import Path
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
from faculty_refresh import parse_directory, request_spec
from faculty_directories import page_url
from faculty_registry import classify_role


class DirectoryTests(unittest.TestCase):
    def test_mit_rank_div_does_not_become_a_research_topic_or_drop_www(self):
        body=b'''<div class="people-entry"><a href="https://www.eecs.mit.edu/people/ada/">Photo</a>
        <h5>Ada Example</h5><div>Assistant Professor [CS, EE]</div>
        <div class="people-research"><p>Computer Architecture</p></div></div>'''
        rows,_=parse_directory(body,'https://www.eecs.mit.edu/role/faculty-ee/','mit')
        self.assertEqual(rows[0]['title'],'Assistant Professor [CS, EE]')
        self.assertEqual(rows[0]['profile_url'],'https://www.eecs.mit.edu/people/ada')
        self.assertEqual(request_spec({'url':'http://www.eecs.mit.edu/people/ada/'}),rows[0]['profile_url'])

    def test_purdue_retired_roster_without_rank_retains_the_explicit_category(self):
        body=b'<div class="list-name"><a href="/ECE/People/ptProfile?resource_id=1">Ada Example</a></div>'
        rows,_=parse_directory(body,'https://engineering.purdue.edu/ECE/People/Faculty?show_group=retired-faculty','purdue')
        self.assertIn('retired faculty',rows[0]['title'])
        with self.assertRaisesRegex(ValueError,'missing'):
            parse_directory(body,'https://engineering.purdue.edu/ECE/People/Faculty','purdue')

    def test_ucsd_uses_the_appointment_before_contact_or_lab_links(self):
        body=b'''<div class="faculty-member"><h2><a href="https://jacobsschool.ucsd.edu/people/profile/ada">Ada Example</a></h2>
        <p>Teaching Professor<br><a href="mailto:ada@example.edu">Email</a><a href="https://lab.example.edu">Professor research</a></p></div>'''
        rows,_=parse_directory(body,'https://ece.ucsd.edu/people/faculty','ucsd')
        self.assertEqual(rows[0]['title'],'Teaching Professor')
        self.assertEqual(classify_role(rows[0]['title']),'teaching')

    def test_ucla_reads_taxonomy_and_wordpress_pagination_without_inventing_rank(self):
        body=b'''<article class="et_pb_post seas_department-ece seas_department-joint-ece">
        <h2 class="entry-title"><a href="/people/ada/">Ada Example</a></h2></article>
        <a href="/seas_department/ece/page/9/?et_blog">Last Page</a>'''
        rows,last=parse_directory(body,'https://samueli.ucla.edu/seas_department/ece/','ucla')
        self.assertEqual(last,8)
        self.assertIn('joint-ece',rows[0]['title'])
        self.assertNotIn('Professor',rows[0]['title'])
        self.assertEqual(page_url('https://samueli.ucla.edu/seas_department/ece/',8,'ucla'),
                         'https://samueli.ucla.edu/seas_department/ece/page/9/')

    def test_ohio_state_preserves_multiple_titles_and_reads_directory_pager(self):
        body = b'''<article class="directory-item" about="/people/example.1">
            <h2 class="directory-grid-name">Example, Ada</h2>
            <div class="appointment-name">Professor, Computer Science</div>
            <div class="appointment-name">Joint Professor, Electrical Engineering</div>
        </article>
        <nav class="pager"><a href="?page=2">Last</a></nav>'''
        url = 'https://ece.osu.edu/directory/faculty'
        rows, last = parse_directory(body, url, 'ohio-state')
        self.assertEqual(last, 2)
        self.assertEqual(rows[0]['profile_url'], 'https://ece.osu.edu/people/example.1')
        self.assertEqual(rows[0]['title'], 'Professor, Computer Science; Joint Professor, Electrical Engineering')

    def test_cards_adapter_reads_configured_classes_and_fails_visibly(self):
        body = b'''<div class="personbox"><a href="/people/ada"><div class="field-title">Ada Example</div></a>
            <div class="position">Professor</div></div>
            <div class="personbox"><div class="field-title">Bo Unlinked</div><div class="position">Lecturer</div></div>'''
        options = {'card': 'personbox', 'name': 'field-title', 'title': 'position', 'school_label': 'Example'}
        rows, last = parse_directory(body, 'https://example.edu/people', 'cards', options=options)
        self.assertEqual(last, 0)
        self.assertEqual(rows[0]['profile_url'], 'https://example.edu/people/ada')
        self.assertEqual(rows[1]['title'], 'Lecturer')
        self.assertEqual(rows[1]['profile_kind'], 'official_directory_entry')
        with self.assertRaises(ValueError):
            parse_directory(b'<div class="x"></div>', 'https://example.edu/people', 'cards', options=options)
        with self.assertRaises(ValueError):
            parse_directory(body, 'https://example.edu/people', 'cards', options=None)

    def test_ut_dallas_repairs_the_misdirected_roster_link(self):
        body = b'''<div class="faculty-no-arrows">
            <ul class="wp-block-list">
                <li><a href="/fahimi-babk/">Dutta, Sourav</a></li>
                <li>Assistant Professor</li>
            </ul>
            <ul class="wp-block-list">
                <li><a href="/fahimi-babk/">Fahimi, Babak</a></li>
                <li>Professor</li>
            </ul>
        </div>'''
        url = 'https://ece.utdallas.edu/people/tenure-system-faculty/'
        rows, last = parse_directory(body, url, 'ut-dallas')
        self.assertEqual(last, 0)
        self.assertEqual([row['profile_url'] for row in rows], [
            'https://ece.utdallas.edu/people/tenure-system-faculty/dutta-sourav',
            'https://ece.utdallas.edu/fahimi-babk',
        ])

    def test_harvard_comma_pagination_and_unlinked_entries(self):
        body = b'''<div class="person__detailed">
            <h2 class="person__detailed-name">Ada Example</h2>
            <div class="person-directory__primary-title">Postdoctoral Fellow</div>
        </div><a href="?page=%2C3">Last</a>'''
        url = 'https://seas.harvard.edu/electrical-engineering/people'
        rows, last = parse_directory(body, url, 'harvard')
        self.assertEqual(last, 3)
        self.assertEqual(rows[0]['entry_id'], 'harvard-ee-directory:Ada Example')
        self.assertEqual(rows[0]['profile_url'], url)
        self.assertEqual(page_url(url, 1, 'harvard'), url + '?page=%2C1')

    def test_ucf_unlinked_people_keep_distinct_identities_and_titles(self):
        body = b'''<div class="eael-filterable-gallery-item-wrap">
            <div class="fg-layout-3-item-content"><a>Ada Example</a></div>
            <div class="fg-item-content"><p>Professor Emeritus<br>
            <a href="mailto:private@example.edu">private@example.edu</a></p></div>
        </div><div class="eael-filterable-gallery-item-wrap">
            <div class="fg-layout-3-item-content"><a href="/faculty-directory">Bob Example</a></div>
            <div class="fg-item-content"><p>Professor Emeritus</p></div>
        </div>'''
        url = 'https://www.ece.ucf.edu/faculty-directory'
        rows, _ = parse_directory(body, url, 'ucf')
        self.assertEqual(len({r['entry_id'] for r in rows}), 2)
        self.assertEqual({r['profile_url'] for r in rows}, {url})
        self.assertTrue(all('@' not in r['title'] for r in rows))

    def test_maryland_retains_people_without_a_directory_title(self):
        body = b'''<div class="faculty_row">
            <div class="field-directory-name-title-wrapper">
                <a href="/clark/faculty/123/Ada-Example">Example, Ada</a>
                <div class="title-wrapper"></div>
            </div>
        </div>'''
        rows, _ = parse_directory(body, 'https://ece.umd.edu/clark/facultydir?drfilter=5', 'maryland')
        self.assertEqual(rows[0]['title'], 'Academic title not supplied by directory')
        self.assertEqual(rows[0]['profile_url'], 'https://ece.umd.edu/clark/faculty/123/Ada-Example')

    def test_duke_pagination_preserves_department_faculty_filter(self):
        body = b'''<div class="faculty-overview__info">
            <h3><a href="/people/ada/">Ada Example</a></h3><p>Assistant Professor</p>
        </div>
        <a href="/people/page/3/?group=faculty">3</a>
        <a href="/people/page/8/?group=staff">8</a>'''
        start = 'https://ece.duke.edu/people/?group=faculty'
        next_page = page_url(start, 1, 'duke')
        self.assertEqual(next_page, 'https://ece.duke.edu/people/page/2/?group=faculty')
        rows, last = parse_directory(body, next_page, 'duke')
        self.assertEqual(last, 2)
        self.assertEqual(rows[0]['title'], 'Assistant Professor')

    def test_boston_filter_and_trailing_slash_pagination(self):
        url = 'https://www.bu.edu/eng/people?department=electrical-computer-engineering'
        body = b'''<select name="filter_by_department"><option selected value="electrical-computer-engineering">ECE</option></select>
            <li class="bu-filtering-result-item"><h4 class="bu-filtering-result-item-title"><a href="/eng/profile/ada/">Ada</a></h4>
            <div class="bu-filtering-result-item-title">Professor (ECE)</div></li>
            <a class="page-numbers" href="/eng/people/?num=14">14</a>'''
        rows, last = parse_directory(body, url, 'boston')
        self.assertEqual(last, 13)
        self.assertEqual(rows[0]['name'], 'Ada')
        self.assertEqual(page_url(url, 1, 'boston'), url + '&num=2')
        with self.assertRaisesRegex(ValueError, 'did not apply'):
            parse_directory(body.replace(b'selected ', b''), url, 'boston')

    def test_msu_preserves_explicit_secondary_ece_boundary(self):
        body = json.dumps({'people': [
            {'name': 'Secondary', 'url': '/secondary', 'position': 'Professor',
             'primary': {'name': 'Computer Science'}, 'others': [
                 {'name': 'Electrical and Computer Engineering', 'title': 'Assistant Professor'}]},
            {'name': 'CS Only', 'url': '/cs', 'position': 'Professor',
             'primary': {'name': 'Computer Science'}, 'others': []}]}).encode()
        rows, _ = parse_directory(body, 'https://engineering.msu.edu/directory/data', 'michigan-state')
        self.assertEqual(len(rows), 1)
        self.assertIn('ECE appointment: Assistant Professor', rows[0]['title'])

    def test_yale_requires_group_payload_not_empty_get_response(self):
        with self.assertRaisesRegex(ValueError, 'lacks appointment groups'):
            parse_directory(b'{"pages":null}', 'https://engineering.yale.edu/faculty', 'yale')
        body = json.dumps({'pages': {'secondary': {'name': 'Secondary Faculty',
            'facultyMembers': [{'name': 'Ada', 'url': '/ada', 'fullTitle': 'Professor of Physics'}]}}}).encode()
        rows, _ = parse_directory(body, 'https://engineering.yale.edu/faculty', 'yale')
        self.assertIn('Secondary Faculty', rows[0]['title'])

    def test_riverside_preserves_teaching_title_in_tenure_track_group(self):
        body = json.dumps([{'netId': 'ada', 'name': 'Ada', 'title': None,
            'otherTitles': ['Assistant Professor of Teaching'], 'email': 'private@example.edu'}]).encode()
        rows, _ = parse_directory(body, 'https://profiles.ucr.edu/api/profile?groupId=4108', 'riverside')
        self.assertEqual(classify_role(rows[0]['title']), 'teaching')
        self.assertNotIn('private', str(rows))
        with self.assertRaisesRegex(ValueError, 'registered ECE group'):
            parse_directory(body, 'https://profiles.ucr.edu/api/profile?groupId=123', 'riverside')

    def test_harvard_ee_research_list_deduplicates_profiles_across_topics(self):
        body = b'''<div class="view-content"><div><h2>Electrical &amp; Computer Engineering Faculty</h2></div>
            <a href="/person/ada">Ada Example</a><a href="/person/ada">Ada Example</a>
            <a href="/research">Research overview</a></div>
            <div><a href="/person/other">Other section</a></div>'''
        rows, last = parse_directory(body, 'https://seas.harvard.edu/electrical-engineering/faculty-research', 'harvard')
        self.assertEqual([row['profile_url'] for row in rows], ['https://seas.harvard.edu/person/ada'])
        self.assertEqual(last, 0)

    def test_rutgers_coverage_preserves_retirement_without_contact_details(self):
        body = b'''<div class="c--rich-text"><p><strong>Ada</strong><br>
            ada@example.edu<br>Professor Emeritus<br>Retired 2024</p></div>'''
        rows, _ = parse_directory(body, 'https://ece.rutgers.edu/faculty-emereti', 'rutgers')
        self.assertEqual(rows[0]['title'], 'Professor Emeritus; Retired 2024')
        self.assertNotIn('@', str(rows))

    def test_davis_grouped_directory_keeps_graduate_faculty_and_excludes_staff(self):
        body = b'''<div class="view-content"><h3>Graduate Program Faculty</h3>
            <article><h3 class="vm-teaser__title"><a href="/directory/ada">Ada</a></h3>
            <ul class="vm-teaser__position"><li>Professor</li><li>Computer Science</li></ul>
            <a href="mailto:ada@example.edu">ada@example.edu</a></article>
            <h3>Staff</h3><article><h3 class="vm-teaser__title"><a href="/staff">Staff</a></h3></article></div>'''
        rows, _ = parse_directory(body, 'https://ece.ucdavis.edu/directory', 'davis')
        self.assertEqual(len(rows), 1)
        self.assertIn('Directory category: Graduate Program Faculty', rows[0]['title'])
        self.assertNotIn('@', str(rows))

    def test_virginia_titles_preserve_each_appointment_and_unlinked_staff(self):
        body = b'''<div class="people_list_item_header"><h2 class="people_list_item_name">
            <a class="contact_block_name_link" href="/faculty/ada"><span class="contact_block_name_link_label">Ada</span><span>arrow</span></a></h2>
            <span class="people_list_item_title">Professor, Physics</span>
            <span class="people_list_item_title">Professor, ECE (by courtesy)</span></div>
            <div class="people_list_item_header"><h2 class="people_list_item_name">Staff Member</h2>
            <span class="people_list_item_title">Administrative Manager</span></div>'''
        rows, _ = parse_directory(body, 'https://engineering.virginia.edu/ece/faculty', 'virginia')
        self.assertEqual(rows[0]['name'], 'Ada')
        self.assertEqual(rows[0]['title'], 'Professor, Physics; Professor, ECE (by courtesy)')
        self.assertEqual(rows[1]['profile_kind'], 'official_directory_entry')

    def test_retired_faculty_and_retired_administrative_offices_are_distinct(self):
        self.assertEqual(classify_role('Professor Post-Tenure [EE]'),'retired_working')
        self.assertEqual(classify_role('MIT President Emeritus; Professor of EECS'),'regular')
        self.assertEqual(classify_role('Distinguished Professor of ECE/Dean Emerita of Engineering'),'regular')
        self.assertEqual(classify_role('Dean Emeritus; Professor Emeritus of ECE'),'emeritus')

    def test_asu_tamu_cornell_and_princeton_adapters(self):
        asu_body=b'{"results":[{"display_name":{"raw":"Ada Lovelace"},"asurite_id":{"raw":"alovelac"},"primary_simplified_empl_class":{"raw":["Faculty"]},"primary_title":{"raw":["Professor"]},"primary_department":{"raw":"School of Electrical, Computer and Energy Engineering"}},{"display_name":{"raw":"Staff Person"},"asurite_id":{"raw":"staffp"},"primary_simplified_empl_class":{"raw":["University Staff"]}}]}'
        rows,_=parse_directory(asu_body,'https://search.asu.edu/api/v1/webdir-profiles/faculty-staff/filtered?dept_ids=1663&size=200','asu')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['entry_id'],'asu-ecee-api:alovelac')
        tamu_body=b'[{"name":"Sam Houston","tag":["electrical","Faculty"],"titles":["Professor"],"link":"/electrical/profiles/shouston.html"},{"name":"Aff Prof","tag":["mechanical","Faculty"],"tagSets":[["Faculty","mechanical"],["Affiliated Faculty","electrical"]],"titles":["Professor, Mechanical Engineering"],"link":"/mechanical/profiles/aff.html"},{"name":"Staff Only","tag":["electrical","Staff"],"titles":["Advisor"],"link":"/electrical/profiles/staff.html"}]'
        rows,_=parse_directory(tamu_body,'https://engineering.tamu.edu/profile-data.json','tamu')
        self.assertEqual([r['name'] for r in rows],['Sam Houston','Aff Prof'])
        cornell_body=b'<h2 class="ce-block__people-list-title">Core Faculty</h2><div class="ce-block__people-list-titles"><p class="ce-block__people-list-person-name"><a class="ce-block__people-list-item-link" href="/people/ada/">Ada</a></p><p class="ce-block__people-list-person-title"><span>Professor</span></p></div><h2 class="ce-block__people-list-title">Staff</h2><div class="ce-block__people-list-titles"><a class="ce-block__people-list-item-link" href="/people/s/">Staff</a></div>'
        rows,_=parse_directory(cornell_body,'https://www.duffield.cornell.edu/ece/faculty-staff/','cornell')
        self.assertEqual(len(rows),1)
        self.assertIn('Core Faculty',rows[0]['title'])
        princeton_body=b'<div class="block-ps-people-list"><h2 class="content-list-title">Associated Faculty</h2><div class="content-list-item"><span class="field--name-title"><a href="/people/alex">Alex</a></span></div></div>'
        rows,_=parse_directory(princeton_body,'https://ece.princeton.edu/people-list/faculty','princeton')
        self.assertEqual(rows[0]['title'],'Associated Faculty')

    def test_vt_cmu_columbia_umn_and_psu_adapters(self):
        vt_body=b'<h2 class="vt-accordion-title">Alphabetical Faculty Listing</h2><li class="vt-list-item-row"><a class="vt-list-item-title-link" href="/people/profile/ada.html">Ada<span>, bio</span></a></li><h2 class="vt-accordion-title">Research Areas</h2><p><a href="https://ece.vt.edu/people/profile/grace.html">Grace</a></p><h2 class="vt-accordion-title">Courtesy Appointments</h2><div class="vt-text"><p>Bob<br>Professor<br>bob@vt.edu</p></div>'
        rows,_=parse_directory(vt_body,'https://ece.vt.edu/people/faculty.html','vt')
        self.assertEqual(len(rows),3)
        cmu_body=b'<div><h2><a href="bios/ada.html">Ada</a></h2><h3>Special Faculty</h3></div><div id="emeritus"><h2>Em</h2></div>'
        rows,_=parse_directory(cmu_body,'https://www.ece.cmu.edu/directory/faculty.html','cmu')
        self.assertEqual([r['name'] for r in rows],['Ada','Em'])
        col_body=b'<div id="facultytextcontainer"><h2>Professors</h2><p>Ada<br/>Bob, <em>Computer Science</em></p></div><div id="coursestextcontainer"></div>'
        rows,_=parse_directory(col_body,'https://bulletin.columbia.edu/columbia-engineering/academic-departments-programs/electrical-engineering/','columbia')
        self.assertEqual([r['name'] for r in rows],['Ada','Bob'])
        umn_body=b'<div class="widget-content"><h2><strong>Ada</strong></h2><p>Professor<br>Mech Eng<br><a href="https://x">Research Site</a></p></div>'
        rows,_=parse_directory(umn_body,'https://cse.umn.edu/ece/affiliate-faculty','umn')
        self.assertIn('Mech Eng',rows[0]['title'])
        psu_body=b'<div class="results-individual-revised"><p class="name"><a href="directory-detail-g.aspx?q=A1">Ada</a></p><p class="title">Professor</p></div>'
        rows,_=parse_directory(psu_body,'https://www.eecs.psu.edu/departments/faculty-staff-list.aspx','psu')
        self.assertEqual(rows[0]['profile_url'],'https://www.eecs.psu.edu/departments/directory-detail-g.aspx?q=A1')

    def test_iowa_state_wp_and_boulder_jsonapi_adapters(self):
        isu_body=b'[{"id":42,"title":{"rendered":"Ada, Grace &amp; Co"},"isu_title":"Professor [E CPE]","user_title":"Professor"}]'
        rows,_=parse_directory(isu_body,'https://www.engineering.iastate.edu/people/wp-json/wp/v2/profile?per_page=100&department=1121','iowa-state')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['name'],'Ada, Grace & Co')
        self.assertEqual(rows[0]['entry_id'],'isu-ecpe-wp:42')
        self.assertIn('ECpE Faculty',rows[0]['title'])
        boulder_body=b'{"data":[{"attributes":{"status":true,"title":"Emily Jensen","field_ucb_person_title":["Assistant Professor"],"path":{"alias":"/emily-jensen"}},"relationships":{"field_ucb_person_job_type":{"data":[{"id":"t1"}]}}},{"attributes":{"status":false,"title":"Unpublished","field_ucb_person_title":["Professor"],"path":{"alias":"/unpub"}},"relationships":{}}],"included":[{"type":"taxonomy_term--ucb_person_job_type","id":"t1","attributes":{"name":"Tenure-Track Faculty"}}]}'
        rows,_=parse_directory(boulder_body,'https://www.colorado.edu/ecee/jsonapi/node/ucb_person?page[limit]=50&page[offset]=0','boulder')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['name'],'Emily Jensen')
        self.assertEqual(rows[0]['profile_url'],'https://www.colorado.edu/ecee/emily-jensen')
        self.assertIn('Tenure-Track Faculty',rows[0]['title'])

    def test_json_list_joins_fields_and_pages_and_plain_emeritus_lines(self):
        body = b'{"results":[{"name":"Ada","title":"Professor","type":["Faculty"],"department":["ECE","CS"],"profileUrl":"/a/"}]}'
        cfg = {'list_key': 'results', 'name': 'name', 'title': ['type', 'title', 'department'], 'title_join': True, 'link': 'profileUrl', 'pages': 5}
        rows, last = parse_directory(body, 'https://x.edu/api/faculty', 'json_list', options=cfg)
        self.assertEqual(rows[0]['title'], 'Faculty; Professor; ECE; CS')
        self.assertEqual(last, 4)
        html = (b'<h2>Emeritus Faculty</h2><div><strong>Ada Lee</strong>, Professor Emeritus, Ph.D.</div>'
                b'<p><strong>Bob Ray</strong>, Professor Emeritus, Ph.D.<br><strong>Cy Fox, </strong>Professor Emeritus, Ph.D.</p>')
        rows, _ = parse_directory(html, 'https://x.edu/faculty?section=emeritus', 'cards',
                                  options={'strong_lines_after_heading': {'contains': 'Emeritus Faculty', 'tag': 'h2'}})
        self.assertEqual([r['name'] for r in rows], ['Ada Lee', 'Bob Ray', 'Cy Fox'])
        self.assertTrue(all(r['title'] == 'Emeritus Faculty; Professor Emeritus' for r in rows))
        spec = request_spec(dict(url='https://x.edu/api/faculty', referer='https://x.edu/dept/'))
        self.assertEqual(spec['referer'], 'https://x.edu/dept/')
        self.assertIsInstance(request_spec(dict(url='https://x.edu/api/faculty')), str)


if __name__ == '__main__':
    unittest.main()
