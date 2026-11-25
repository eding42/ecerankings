# Faculty context vision and roadmap

Show the number of **ECE-affiliated faculty**, including official courtesy and
joint appointments and announced incoming professors,
alongside the institution's research
output, with the university's own website defining who belongs to ECE. Readers
should be able to inspect the names, appointment categories, and official sources
behind a count. Begin with five US schools and expand after the process works.

## Current decisions

- **Official EE/ECE membership is authoritative.** Use the university's designated
  EE/ECE faculty roster and official appointment profiles. Publishing in an ECE
  venue does not establish an ECE appointment.
- **Combined departments need an EE boundary.** Use an official EE track/list or
  an explicit EE/ECE appointment. CS-only professors stay out of the faculty
  context feature even if they publish in included venues. A genuine joint EE
  and CS appointment qualifies, including an explicit courtesy EE appointment.
- **Count official professorial affiliations, including courtesy appointments.** Include
  regular, in-residence, affiliated/below-the-line, courtesy and joint/secondary EE/ECE professors, counting
  each person once per school. Include officially announced incoming professors
  in those categories;
  retain incoming status, announced start dates and a separate incoming subtotal.
  A future start does not imply that the professor is already employed there.
  Keep generic lab affiliates, teaching/practice, research-only, adjunct, visiting,
  emeritus, and retired-but-working appointments outside this count. Preserve
  explicit courtesy designations and use `joint_secondary` when the more specific
  regular-versus-courtesy subtype is not established. Use a specific current
  official appointment when a directory card only names an administrative role.
- **Use the university's classification.** Do not invent a research-topic test,
  infer faculty status from papers, or let an undated personal page override an
  official departmental appointment. Flag genuine conflicts between official
  sources for review. Counts describe an observed university roster, not an HR
  payroll census or FTE estimate.
- **Current counts come first.** A count has an observation date and is independent
  of the publication-year or area filters. Historical school faculty lists and
  historical faculty counts are later work.
- **Preserve ranking meaning.** This roster scope applies to faculty context and
  its verified contributor links. It does not remove CS authors from the existing
  institution-level publication scores, reassign past papers, or introduce
  per-faculty scoring.

## Delivery roadmap

### School queue and professor records

Maintain a versioned queue of candidate US institutions rather than selecting
the next school ad hoc. Existing ECE publication activity can prioritize discovery,
but does not establish that an institution has an eligible EE/ECE unit. Each school
progresses through `discovery_pending`, `source_ready`, `collecting`,
`review_required`, and `verified`. A verified school can enter `needs_update`;
failed collection is `blocked`, and a confirmed absence of an in-scope unit is
`out_of_scope`. Retain the reason and observation behind every transition.

Each professor has a local identity record containing official names and variants,
profile links, external identifiers with their sources, appointments, individual
paper links, and claim-level evidence. Evidence can come from the department,
central university profiles, a professor's site/CV, ORCID assertions, and publisher
metadata. Store which source supports which claim and whether the claim is
corroborated, disputed, or unresolved. Sources that copy the same assertion are
not independent confirmations.

For each school, compare its roster with central appointment records, new-hire or
departure announcements, professor profiles, and publication-driven candidate
discovery. Review omissions and cross-department candidates against the official
EE/ECE boundary. Missing from one directory is a review lead, not automatic proof
of exclusion. Keep collection coverage separate from verified-person and
paper-matching coverage.

### Phase 1 Current counts for five US schools

- [x] Apply the agreed membership and appointment policy to Berkeley EE, Illinois
  ECE, Stanford EE, UT Austin ECE, and Georgia Tech ECE.
- [x] Record an inclusion, exclusion, or unresolved decision for every collected
  entry, with official-source evidence and a policy version.
- [x] Cross-check combined-department and courtesy cases, inspect unresolved
  administrative titles, and independently audit decisions.
- [x] Produce validated current counts, a readable roster for review, and explicit
  completeness status. Unresolved entries must not silently become exclusions.
- [x] Add optional faculty context to the shared frontend and package all three
  discipline configurations locally. Offline checks pass; browser layout QA
  remains unrun because the optional browser dependency is unavailable.
- [ ] Publish the reviewed change through the existing release process and its
  authorization rules. No commit, push, or deployment is authorized yet.

The [current status](faculty-current-status.md) contains the observed counts,
important decisions, validation limits, and the next collection batch.

### Phase 2 Maintain and expand the US directory

- [x] Implement the user-approved `us-ece-affiliated-v5` scope in policy, audit
  instructions, validation, export and the shared display. Preserve earlier
  observations and individual paper links under their original policies.
- [ ] Upgrade source coverage for courtesy appointments at the five pilot
  schools and re-review USC under v5. Resolve eligibility and omissions with a
  fresh independent audit; the previous narrower counts and rejected USC review
  are not approval of the broader population. The queue records `needs_update`
  and withholds broader counts until the gate passes.
- [x] Build a reusable single-school observation/refresh command with configurable
  school and observation date. Collect into a candidate observation, preserve
  permitted evidence, review a roster diff, and retain accepted data on failure.
  Proved with same-day second live observations of Berkeley and Georgia Tech,
  including a rejected timeout candidate and a successful retry. New schools
  still need configuration, source discovery and a suitable layout adapter.
- [x] Require a recorded independent agent audit on every future acceptance.
  Collection automatically launches the configured reviewer with a blind brief.
  New schools get a full audit; refreshes review all changes and a reproducible
  sample of unchanged entries. Reconcile findings before acceptance; missing,
  stale or incomplete reviews retain the prior count. Tested with a fresh Astra
  USC audit whose incomplete coverage correctly blocked acceptance.
- Establish a broader US institution/unit inventory using official national
  education and program directories, with explicit additions for eligible units
  outside any one accreditation list. Reconcile it with the publication-derived
  discovery queue. The initial 909 candidates are not a complete US census.
- Work in batches of ten. For each school: establish the EE/ECE boundary;
  enumerate every directory page and category; compare another official source;
  investigate missing or conflicting people using profiles, announcements,
  personal sites and bibliographic leads; decide every inclusion; reconcile a
  second review; validate and export only the accepted current count.
- Check official incoming-faculty and new-hire announcements as well as the
  current directory, since an announced professor may not yet have a roster card.
  Verify the future appointment type and EE/ECE boundary before inclusion.
- Track official roster coverage, reviewed entries, unresolved decisions, source
  failures, and next action per school. Track matched-paper coverage separately.
  Keep a discovery lead even when its name is absent from the main directory.
- Compare each new official-site observation with the last accepted one. Review
  additions, removals, appointment changes, source failures, and changed schemas.
- Retain the previous accepted observation when collection fails. Record what was
  observed and when, independently of any known appointment start/end dates.
- Expand US school coverage, measuring review time and auditing false inclusions
  and omissions. Keep person-to-paper matching separate from roster eligibility.
- Aim to review accepted school rosters every 90 days and when a material change
  is discovered. The queue records a due date; no scheduled automation has been
  created. A failed refresh retains the last accepted count with its actual date.

#### US top-50 roster expansion

Use the 2016–2025 US ECE publication ranking with all 18 default areas to
select schools. The public export covers the original ranks 1–20 plus the
accepted additions below. Collect ranks 21–50 in batches of ten using the same
affiliated-faculty policy. The links below are discovery leads. Before acceptance, each school needs a complete
candidate observation, corroborating official sources and a reconciled
independent audit.

| Rank | School | Official directory or discovery lead |
| ---: | --- | --- |
| 21 | Maryland–College Park | [ECE directory](https://ece.umd.edu/clark/facultydir) and [affiliate filter](https://ece.umd.edu/clark/facultydir?drfilter=4) |
| 22 | Wisconsin–Madison | [ECE people](https://engineering.wisc.edu/departments/electrical-computer-engineering/people/) and the [supplemental ECE directory](https://directory.engr.wisc.edu/ece/) cover affiliates inside and outside Engineering. Cross-check [college appointment announcements](https://engineering.wisc.edu/blog/college-faculty-reach-career-milestones/) and [department hiring news](https://engineering.wisc.edu/departments/electrical-computer-engineering/news/). |
| 23 | NC State | [Primary](https://ece.ncsu.edu/faculty/) and [supporting faculty](https://ece.ncsu.edu/supporting-faculty/). Resolve appointment types within the mixed supporting list. |
| 24 | Duke | [Paginated ECE faculty](https://ece.duke.edu/people/?group=faculty) and [department report](https://ece.duke.edu/impact/report-2025/). Reconcile appointments at profile level. |
| 25 | Washington | [ECE faculty](https://www.ece.uw.edu/faculty/) |
| 26 | UC Santa Barbara | [ECE directory](https://www.ece.ucsb.edu/people) and [affiliated faculty](https://www.ece.ucsb.edu/people/affiliated) |
| 27 | UT Dallas | [ECE people](https://ece.utdallas.edu/people/) and [affiliated faculty](https://ece.utdallas.edu/people/affiliated-faculty/) |
| 28 | Northeastern | [ECE directory](https://ece.northeastern.edu/fac/faculty-directory/) and [affiliated research and part-time faculty](https://ece.northeastern.edu/fac/part-time-faculty/). Resolve roles within the mixed list. |
| 29 | Ohio State | [ECE faculty directory](https://ece.osu.edu/directory/faculty) |
| 30 | UC Irvine | [EECS faculty](https://engineering.uci.edu/dept/eecs/people/faculty.php) and [affiliates](https://engineering.uci.edu/dept/eecs/people/affiliated.php). Establish the EE/ECE boundary from official appointments. |
| 31 | Florida | [ECE faculty](https://ece.ufl.edu/people/faculty/) |
| 32 | NYU | [Tandon ECE people](https://engineering.nyu.edu/academics/departments/electrical-and-computer-engineering/people) |
| 33 | Caltech | [EE faculty](https://www.ee.caltech.edu/people/faculty) |
| 34 | Harvard | [SEAS electrical engineering people](https://seas.harvard.edu/electrical-engineering/people) |
| 35 | Penn | [Electrical and Systems Engineering appointments](https://directory.engineering.upenn.edu/electrical-and-systems-engineering/), including incoming and emeritus entries |
| 36 | UCF | [ECE faculty](https://www.ece.ucf.edu/faculty-directory/) and [affiliated faculty](https://www.ece.ucf.edu/affiliated-faculty/) |
| 37 | Northwestern | [ECE faculty](https://www.mccormick.northwestern.edu/electrical-computer/people/faculty.html), with core EE and CE lists for cross-checking |
| 38 | UC Davis | [Paginated ECE faculty](https://ece.ucdavis.edu/person-type/faculty) |
| 39 | Virginia | [ECE faculty](https://engineering.virginia.edu/department/electrical-and-computer-engineering/faculty) and [computer engineering program faculty](https://engineering.virginia.edu/offices-programs/computer-engineering-program/faculty) for cross-checking |
| 40 | Colorado Boulder | [ECEE faculty](https://www.colorado.edu/ecee/faculty) |
| 41 | Michigan State | [Engineering ECE directory](https://engineering.msu.edu/directory/ece) |
| 42 | UC Riverside | [ECE department](https://www.ece.ucr.edu/) and [university profiles](https://profiles.ucr.edu/app/home/browse/group/4108) for cross-checking |
| 43 | Rice | [ECE faculty](https://eceweb.rice.edu/people/faculty) |
| 44 | Boston University | [ECE people](https://www.bu.edu/eng/academics/departments-and-divisions/electrical-and-computer-engineering/people/) |
| 45 | Notre Dame | [EE faculty](https://ee.nd.edu/faculty/) |
| 46 | Yale | [ECE faculty](https://engineering.yale.edu/academic-study/departments/electrical-and-computer-engineering/faculty) |
| 47 | Utah | [ECE faculty](https://www.ece.utah.edu/faculty/) |
| 48 | Rutgers | [Full-time ECE faculty](https://ece.rutgers.edu/full_time_faculty). Locate other appointment categories. |
| 49 | Iowa State | The [university faculty catalog](https://catalog.iastate.edu/faculty/) is a corroboration lead. The department site rejected the roster lookup. |
| 50 | University at Buffalo | [ECE faculty directory](https://engineering.buffalo.edu/electrical-and-computer-engineering/faculty/faculty_directory.html) |

Collection checkpoint (24 November 2026): **35 accepted counts exported; all 50 target schools configured.** Fifteen school counts remain pending.

- Duke: verified **78** (77 current, one incoming). The revised directory
  observation includes the announced July 15, 2027 appointment of Suman
  Datta. [Accepted observation](../data/faculty/observations/duke/fd2173b6d25e5c239c654999a70d33b2b4d8da5bccf7455abd1bc295e96a03e1.json)
- UC Santa Barbara: verified **55**. The review resolved contrasting
  directory titles and category placements for emeritus and adjunct faculty.
  [Accepted observation](../data/faculty/observations/ucsb/12bb400e704413f9bab04eb7fdf3e8631c1932b37068123a7719596da29f94eb.json)
- UT Dallas: verified **62** (42 regular and 20 affiliates). The review
  resolved two broken or incorrect profile links and excluded a research-only
  appointment. [Accepted observation](../data/faculty/observations/ut-dallas/82208189542d85ff08e677f13edf3e10c5839bd70b51f809e9d176095af4b0f0.json)
- Maryland: 151 candidate entries after adding Xiaodi Wu and Ian Appelbaum.
  The [revised audit](../data/faculty/audits/results/fce0ff6e5da8e563305d2f82786d0fb373fd802b3ea3cdfea90f051efcfbe4c0.json)
  confirmed Wu’s affiliation and still needs corroboration of Appelbaum’s
  current EE/ECE appointment and complete independent coverage.
- Wisconsin: verified **80** (50 regular and 30 affiliates). The follow-up
  independently retrieved all 33 profiles missed in the original audit.
  [Accepted observation](../data/faculty/observations/wisconsin/0f5979fe454850f2f36fc4bf9be11636eb70f51614ebe92ee11ad23da765f0de.json)
- NC State: 158 candidates including Yuchen Liu’s official courtesy
  appointment. The [revised audit](../data/faculty/audits/results/71adad0dee0b28c4ee53efc44b1213045f8146bda27411bc8c0ebe4f13e987f9.json)
  has 10 unresolved records and found stale supporting-directory entries.
- Washington: verified **173**. The revised review reconciled Banghua Zhu’s
  appointment, Mani Soma’s emeritus designation, same-name identities and
  explicit affiliate professorships.
  [Accepted observation](../data/faculty/observations/washington/c37c62f32a725a795f74de198cc81c6dc015b7e0f7cacecd4826cd58e291369d.json)
- Ohio State: a paced retry retrieved 95 candidates across the faculty and
  emeritus lists with zero failures. Department announcements identify
  Subhanshu Gupta and February 2027 incoming hire Daniel Zhou, both absent
  from the directory candidates.
  [Recovered observation](../data/faculty/observations/ohio-state/ced241941411d92266d9d24fefe3036b791eb7fd13c8d4ab641abe90f9e3a087.json)
  The independent audit confirmed both omissions and found conflicting
  research-track descriptions on Matilde D'Arpino's profile. An expanded
  observation retrieved 97 candidates, including both hiring announcements,
  with zero source failures. Its independent audit is pending.
  [Incomplete audit](../data/faculty/audits/results/49778f38e8dc9d740373a0a7e1148fabc55c02d364c945bc0e258d3e6d574667.json)
  [Expanded observation](../data/faculty/observations/ohio-state/83fc92d3a25507393d2aaba4c76b0472178f7176820b2de47b1a610172be8d12.json)
- UC Irvine: 78 candidate entries retrieved. The
  [independent audit](../data/faculty/audits/results/b402ca2a668323142dfa6ad0a4efd0aa08ff4e48f677260f6c0417ddcc3c42d9.json)
  could not establish the EE boundary within EECS.
- Florida: verified **68** (55 regular and 13 affiliates). The review
  reconciled stale faculty titles against a retirement announcement and
  dated evidence of departure.
  [Accepted observation](../data/faculty/observations/florida/c0f48bb6e499188d47021e441e3ab9ec1560b3d8e6f1d488d6e662e0f5731131.json)
- Caltech: verified **20**, including explicit EE courtesy and joint
  appointments, with teaching and emeritus roles excluded.
  [Accepted observation](../data/faculty/observations/caltech/0e3481aa8a4e270056ad0c521262aa1ba6154fad2a4c4cb9f2b410ae35fca171.json)
- NYU: fresh collection retrieved 92 entries and every profile. The
  [latest independent audit](../data/faculty/audits/results/c51ff0deaa0a4ee3573560a8b5de3d72b4224a9305b3702d5253736f36c667b1.json)
  retains four unresolved appointment types: three Distinguished Industry
  Professors and one Presidential Fellow. Tandon's continuing-contract guidelines
  establish the Industry Professor series as primarily teaching; the precise
  applicability to the distinguished appointments remains under review. Global
  Network Faculty designations can establish ECE affiliation, while specific
  research-only titles remain excluded. No count accepted.
  For reconciliation, [Ettenberg's official profile](https://engineering.nyu.edu/michael-ettenberg)
  lists only Presidential Fellow, which gives no professorial rank. Treat his
  record as a proposed exclusion pending reconciliation. [Marzetta's official profile](https://engineering.nyu.edu/faculty/thomas-marzetta)
  confirms the exact ECE title and his NYU WIRELESS directorship. The directorship
  does not establish whether his appointment falls into an excluded track.
- Northeastern: recovered the view-all roster (245 entries) and affiliated and
  part-time list (20 entries). The individual profile host timed out, leaving
  236 profile checks incomplete.
  [Partial observation](../data/faculty/observations/northeastern/3b92d831a02b60216cd630942b5a2b20db39d0aee03733b618f2c68d20e85a7e.json)

Latest top-50 additions and pending collection:

- Penn: verified **50** (49 current and one incoming in Fall 2027).
  [Accepted observation](../data/faculty/observations/penn/093240612ca55b82368c85e1466736db499b524724027fc564b62eb9a267bc44.json)
- UCF: verified **76** (47 regular and 29 affiliates). Reconciled the
  president’s ECE professorship, practice-role exclusion and an emeritus
  affiliate whose directory title was generic.
  [Accepted observation](../data/faculty/observations/ucf/b68c382c11c3edf17d29e94b9e017fa5bda5745f8c000793807f88e771861240.json)
- Harvard: expanded to 107 candidates from the EE people and Faculty & Research
  lists. The second list recovered Yue Lu, H.T. Kung, and Donhee Ham. Review its
  research-area entries against official appointment and affiliation evidence.
  A fresh independent audit retrieved the available pages and verified the
  explicit EE professorships of H.T. Kung and Yue Lu. It left 26 records
  unresolved, principally where Harvard lists professors by research topic
  without identifying an EE appointment or affiliate designation.
  [Expanded observation](../data/faculty/observations/harvard/9123803a8d7d9fd06942ecd22b2b848a9dd1143b27cdcabce77e2c41d8e21bd3.json)
  [Incomplete audit](../data/faculty/audits/results/ace8e49d89d0eccee85c68b1e80a11636fcdfee3a9cd4d7059b03ff9c254181d.json)
- Northwestern: the expanded observation includes main faculty, affiliated
  faculty and both EE and CE track lists. The independent review covers
  59 candidates and flags conflicting courtesy/adjunct titles for Daniel Kim.
  Fresh ECE and BME rosters both specify courtesy appointments. Feinberg lists
  school-level McCormick adjunct status and also lists a Radiology adjunct
  title. The date of any appointment change remains unverified.
  [Focused audit](../data/faculty/audits/results/00d1a5acb34058d31dbe8dc242cf541df670d410dd324b544b0051fbea8ce533.json)
- Notre Dame: verified **37** (32 regular and five joint/secondary professors).
  Reconciled four concurrent EE appointments absent from the main departmental
  roster using the university catalog and official CSE/AME profiles. Fourteen
  emeritus, research-only and teaching appointments remain excluded.
  [Accepted observation](../data/faculty/observations/notre-dame/43a2e4003850e363b49817a84be8ff46eee8fba6c4b9c7075ab12f3992bbdb7a.json)
- Utah: verified **32**, all current appointments.
  [Accepted observation](../data/faculty/observations/utah/591fa0714f6df0edea43e2b3f2e1dc05bcef898c878a4be725be001f05502561.json)
- Buffalo: verified **28**, including Saroj Chand's January 2027 incoming
  appointment and the official Volunteer Professor affiliation.
  [Accepted observation](../data/faculty/observations/buffalo/acc788f10d6bdb4792ba0ebc586adf4048f7b817e1b90224fb890378cc8b16b5.json)
- Boston University: verified **80** (53 regular, 25 officially affiliated and
  two joint/secondary professors). All 118 entries across 14 department-filtered
  directory pages and their profiles were reconciled, including practice,
  research, emeritus and staff exclusions.
  [Accepted observation](../data/faculty/observations/boston/8b0517e4720b0121729b6ca6ef66c704300831333ee7d922d0ba619e47865947.json)
- Michigan State: verified **52** (43 primary and nine secondary ECE professors).
  The specific ECE adjunct appointment on Mahmoodul Haq's profile overrides
  the generic Professor label in the college directory. Non-professorial scholars
  remain excluded. Department and recent hiring-announcement checks found no
  additional eligible entries.
  [Accepted observation](../data/faculty/observations/michigan-state/7f4ebc25668ae564c9a720173164963d9f10aa13d670e02696a2bef2479bf8ca.json)
- UC Riverside: verified **45** (31 regular and 14 cooperating professors).
  Reconciled 68 people across tenure-track, cooperating, adjunct, emeritus,
  lecturer and research groups. Official teaching and adjunct titles take
  precedence over generic group names.
  [Accepted observation](../data/faculty/observations/riverside/9a0ca995e62c300c7b6494d9b5744d02e397ddbb579f643382194321994e9f3e.json)
- Rice: expanded to **145 candidate entries** with eight catalog leads and
  zero retrieval failures. The
  [latest independent audit](../data/faculty/audits/results/85c498c95ba0b8b5b2801591cc3d113866d9049e51e2d0aa9b3d10ac9db74514.json)
  identifies duplicate linked/unlinked identities and conflicting appointment
  designations, including adjunct-list entries with generic professorial titles
  elsewhere. Preserve and reconcile the distinct claims before any count is
  accepted. Additional catalog-only emeritus, lecturer and research-role leads
  are retained in `discovery-leads.json`.
- Yale: expanded to 33 candidates, including announced January 2027 hire Na Li,
  five potential joint appointments and an emeritus record. Independent review
  must reconcile the catalog and profile discrepancies, including conflicting
  evidence about Steven Schiff's current ECE status.
  [Expanded observation](../data/faculty/observations/yale/75b1c80120b13ead42efc63ebcc006017292e6b75c1b322cc4f0e88ba54ad393.json)
  [Incomplete audit](../data/faculty/audits/results/34111e5b81d42c073bda35c08d6d9b986021d0841275d2cb482a2be299001926.json)
  The import normalized blank categories to the policy's unresolved value
  on six already-unresolved records. The original result is retained in scratch.
- Iowa State: expanded to 112 candidates after adding two courtesy appointment
  leads. The department directory returns a request-rejected document despite
  HTTP 200. The provost lists Jennifer Newman as retired in 2024, and the catalog
  specifies emerita status in both Mathematics and ECE. The institute now lists Lizhi
  Wang at Oklahoma State. His former Iowa State courtesy appointment still needs
  a decision supported by current appointment evidence.
  [Expanded observation](../data/faculty/observations/iowa-state/07339df66343f74c0bf596ae93819242e3a56403a2bc8391aa5afbf722fbdba1.json)
  [Incomplete audit](../data/faculty/audits/results/f092b7e8dd9333a8cea26aadb84ca9443f9e854da1987040f1ca3a8a2169e90c.json)
- Colorado Boulder: 83 catalog candidates, with profile failures. The
  [independent audit](../data/faculty/audits/results/87ca0e3929c235b4fdad92cd73d40a471bfd7993490522963e7901089c2cc61b.json)
  found missing 2026 hires and stale or incomplete appointment information.
  The departmental `/faculty` URL is a news-tag archive, not a roster.
- Rutgers: expanded to 45 candidates, including four professors whose official
  profiles were matched to abbreviated entries in the ECE graduate faculty list.
  The 62 graduate and 13 emeritus entries remain available for cross-checking.
  The independent audit verified the source captures and left the four added
  appointments and additional graduate-list identities pending.
  [Expanded audit](../data/faculty/audits/results/201222ce5fafb217785ced1363eb46382bfee07acf1ebf38a02799b3d5fbfd4d.json)
  A follow-up matched more graduate-list names to official profiles. It found
  retired and non-professorial members and a personal CV claiming a separate ECE
  affiliate appointment for Ruo-Qian Wang. The official program bylaws allow
  multiple graduate membership categories, so a separate review is needed to
  establish which current appointments qualify.
  [Expanded observation](../data/faculty/observations/rutgers/b3c8c31225268ceae8f7e6c53c15fc7f07f1364ad28d3ca24afb4e8b62680be0.json)
- UC Davis: browser-rendered directory captured **89 candidate entries** across
  faculty, graduate-program, adjunct/visiting, research and emeritus categories.
  Individual profile requests remain blocked. Capture provenance distinguishes
  the actual DOM hash from an unavailable HTTP-response hash.
  [Candidate observation](../data/faculty/observations/davis/afc98e137a768b3d2b6c91b320fc612ec1fb1bf53adcd5308dedf4564ec8ef15.json)
- Virginia: browser-rendered ECE directory captured **55 candidate entries**,
  including explicit appointment titles. Individual profile access remains
  blocked, so the count is pending.
  [Candidate observation](../data/faculty/observations/virginia/853c0abd1686d82158c8cbeb7ba9889f2df6185853387bf188ea2aa913bca647.json)

### Phase 3 Historical faculty snapshots

Support the faculty list of a particular school at a particular point in time.
Retain immutable observations and decision history now, so this remains possible.
A capture date alone does not establish an employment interval. Historical
reconstruction will need archived official rosters, appointment dates, explicit
coverage, and rules for moves and joint appointments. Do not back-project today's
roster into earlier publication windows.

### Later decisions

International titles, Biology/hospital boundaries, Earth & Space research
institutes, historical faculty attribution, and any per-faculty metric require
their own policy and validation. They are outside the current-count milestone.

## Architecture and status

The [software architecture](faculty-software-architecture.md) uses offline
collectors, versioned JSON/CSV observations and decisions, and small optional JSON
exports for the existing static site. The current pilot needs no database.
The [pilot checklist](faculty-pilot-checklist.md) and
[pilot findings](faculty-pilot-results.md) preserve the initial feasibility work.
The current-count milestone applies the official-membership policy above; its
review state is separate from the completed feasibility experiment.
