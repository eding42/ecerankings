import unittest

from pipeline import pdf_affiliations as pa

COLUMNS = """Published as a conference paper at ICLR 2025

T ITLE OF A PAPER

 Rong Tang                                     Lizhen Lin& Yun Yang
 The Hong Kong University of Science and Technology   University of Maryland, College Park
 martang@ust.hk                                {lizhen01,yy84}@umd.edu


                                            A BSTRACT
"""

MARKERS = """Published as a conference paper at ICLR 2025

        T HERMAL G AUSSIAN
Rongfeng Lu1,3,∗,† Hangyu Chen1,∗ Ming Lu2 Le Zhang1 Bo Han1
         1
           Hangzhou Dianzi University 2 Intel Labs China 3 Lishui Institute of Hangzhou Dianzi University




            (a) RGB GT       (b) Thermal GT
        Figure 1: Compared to NeRF-based methods our approach improves quality.

                                                     A BSTRACT
"""

SYMBOL_MARKS = """C ODE MMLU

 Dung Nguyen Manh†∗, Nam Le Hai‡ , Quang Pham♢†
 †
   FPT Software AI Center, Viet Nam,
 ‡
   Hanoi University of Science and Technology,
 ♢
   Independent Researcher

                                              A BSTRACT
"""


ARROW_MARK = """M EMORY M OSAICS

    Jianyu Zhang† ↿ , Niklas Nolte† , Ranajoy Sadhukhan‡ , Léon Bottou† ↿
    †
      FAIR, Meta ‡ Carnegie Mellon University ↿ New York University


                                              A BSTRACT
"""

DOUBLE_DAGGER = """PSA

 Anmol Goel† , Amartya Sanyal††
 †
   Ubiquitous Knowledge Processing Lab (UKP Lab), Technical University of Darmstadt
 www.ukp.tu-darmstadt.de
 ††
   Department of Computer Science, University of Copenhagen, Denmark


                                              A BSTRACT
"""


# Layouts the ICLR 2025 accuracy sample caught the extractor misreading.
MARKS_ABOVE = """U NI -S IGN
                1                 1,2†                 3
 Zecheng Li , Wengang Zhou , Hezhen Hu
 1
   MoE Key Laboratory of Brain-inspired Intelligent Perception and Cognition,
   University of Science and Technology of China
 2
   Institute of Artificial Intelligence, Hefei Comprehensive National Science Center
 3
   University of Texas at Austin
 {lizecheng23, saruka, wukp}@mail.ustc.edu.cn

                                              A BSTRACT
"""

DOTTED_MARKS = """Q UANTUM G RAPH N EURAL N ETWORKS
 Xinyu Ye1 , Ziang Chen2 , Junchi Yan1∗
 1. Shanghai Jiao Tong University, Shanghai, China.
 2. Massachusetts Institute of Technology, Massachusetts, United States.
 ziang@mit.edu,{jiawang,yanjunchi}@sjtu.edu.cn

                                              A BSTRACT
"""

TRAILING_MARKS = """D EEP K ERNEL R ELATIVE T EST
 Yiliao Song1∗ , Zhenqiao Yuan2∗ , Feng Liu 2†∗
 School of Computer and Mathematical Sciences, The University of Adelaide, Adelaide, AU1
 School of Computing and Information Systems, University of Melbourne, Melbourne, AU2
 {yiliao.song,fengliu.ml}@gmail.com

                                              A BSTRACT
"""

TRAILING_MARKS_IN_A_ROW = """S OME PAPER
 Xiang Li1 , Yi Zhou2 , Kun Zhang1,3
 Carnegie Mellon University1 , Adobe Research2 , MBZUAI3

                                              A BSTRACT
"""

SHARED_PARENT = """R EAL - TIME DESIGN OF ARCHITECTURAL STRUCTURES

 Rafael Pastrana1, Eder Medina2, Isabel M. de Oliveira3,
 Sigrid Adriaenssens,3 Ryan P. Adams2
 1
   Architecture 2 Computer Science 3 Civil and Environmental Engineering
 Princeton University
 {arpastrana,em2368,imdo,sadriaen,rpa}@princeton.edu

                                              A BSTRACT
"""

WRAPPED_LAST_ENTRY = """S OME PAPER
 Ann Lee1 , Bo Chen2
 1
   Tsinghua University 2 Shanghai Artificial Intelligence
 Laboratory

                                              A BSTRACT
"""

LEGEND_IN_TWO_COLUMNS = """A R IEMANNIAN F RAMEWORK
 Katharina Friedl1 Noémie Jaquier1, 2 Tamim Asfour2
 1
   Division of Robotics, Perception, and Learning 2 Institute for Anthropomatics and Robotics
         KTH Royal Institute of Technology           Karlsruhe Institute of Technology (KIT)
           {kfriedl,jaquier}@kth.se, asfour@kit.edu

                                              A BSTRACT
"""

MARK_ABOVE_ITS_COLUMN = """H OW G RADIENT DESCENT BALANCES FEATURES

        Zhenyu Zhu† ,              Fanghui Liu‡ ,                        Volkan Cevher†
                                                                ‡
        † École Polytechnique Fédérale de Lausanne                University of Warwick
 †{zhenyu.zhu, volkan.cevher}@epfl.ch                            fanghui.liu@warwick.ac.uk

                                              A BSTRACT
"""

FOOTNOTE_ON_LEGEND_LINE = """M ULTI - AGENT COOPERATION

 Alexander Meulemans1,∗ , Blake A. Richards1,2,3,4 , João Sacramento1
 1
   Google, Paradigms of Intelligence Team, 2 Mila - Quebec AI Institute, 3 Université de Montréal,
 4
   McGill University, ∗ Equal contribution † Project lead
 ameulemans@google.com

                                              A BSTRACT
"""

MARK_AFTER_SURNAME = """VVC-G YM
  Xudong Gong1,2        Dawei Feng1,2∗ Kele Xu2
 1
   College of Computer Science and Technology, National University of Defense Technology,
 Changsha, Hunan, China
 2
   State Key Laboratory of Complex & Critical Software Environment, Changsha, Hunan, China

                                              A BSTRACT
"""

KEYED_GROUP_THEN_BLOCK = """PIED

 Apivich Hemachandra∗† , Gregory Kang Ruey Lau∗†‡ ,
 †
   Department of Computer Science, National University of Singapore, Singapore 117417
 ‡
   CNRS@CREATE, 1 Create Way, #08-01 Create Tower, Singapore 138602
 {apivich,greglau}@comp.nus.edu.sg

 See-Kiong Ng & Bryan Kian Hsiang Low
 Department of Computer Science, National University of Singapore, Singapore 117417
 seekiong@nus.edu.sg, lowkh@comp.nus.edu.sg

                                              A BSTRACT
"""

ADDRESS_NUMBER = """G LOBAL W ELL - POSEDNESS
 Connor Mooney                                                    Zhongjian Wang∗
 Department of Mathematics,                                       Division of Mathematical Sciences,
 University of California at Irvine,                              Nanyang Technological University
 Irvine, CA 92697, USA                                            21 Nanyang Link, 637371, Singapore
 mooneycr@uci.edu                                                 zhongjian.wang@ntu.edu.sg

                                              A BSTRACT
"""

CONJOINED_BLOCKS = """T HE C OMPUTATIONAL C OMPLEXITY
 Federico Adolfi                                  Martina G. Vilas
 ESI Neuroscience, Max-Planck Society             Department of Computer Science
 & University of Bristol                          Goethe University Frankfurt
 fede.adolfi@bristol.ac.uk                        martinagvilas@em.uni-frankfurt.de
 Tian Ye                                          Depen Morwani
 FAIR at Meta and Carnegie Mellon University      Kempner Institute
 tye2@andrew.cmu.edu                              Harvard University

                                              A BSTRACT
"""

UNREAD_KEYED_LIST = """S OME PAPER
 Ann Lee, Bo Chen
 1
 Jilin University
 2
 Shanghai Jiao Tong University

                                              A BSTRACT
"""


class Extract(unittest.TestCase):
    def test_arrow_mark_is_a_mark(self):
        r = pa.extract(ARROW_MARK, ["Jianyu Zhang", "Niklas Nolte", "Ranajoy Sadhukhan", "Leon Bottou"])
        self.assertEqual(r["affiliations"][0], ["FAIR, Meta", "New York University"])
        self.assertEqual(r["affiliations"][2], ["Carnegie Mellon University"])
        self.assertEqual(r["affiliations"][3], ["FAIR, Meta", "New York University"])

    def test_doubled_dagger_is_distinct_from_dagger_and_urls_are_dropped(self):
        r = pa.extract(DOUBLE_DAGGER, ["Anmol Goel", "Amartya Sanyal"])
        self.assertEqual(r["affiliations"][1], ["Department of Computer Science, University of Copenhagen, Denmark"])
        self.assertEqual(r["affiliations"][0], ["Ubiquitous Knowledge Processing Lab (UKP Lab), Technical University of Darmstadt"])

    def test_columns_with_shared_block(self):
        r = pa.extract(COLUMNS, ["Rong Tang", "Lizhen Lin", "Yun Yang"])
        self.assertEqual(r["layout"], "columns")
        self.assertEqual(r["affiliations"][0], ["The Hong Kong University of Science and Technology"])
        self.assertEqual(r["affiliations"][1], ["University of Maryland, College Park"])
        self.assertEqual(r["affiliations"][2], ["University of Maryland, College Park"])
        self.assertEqual(r["confidence"], "high")

    def test_numeric_marks_glued_to_names_and_caption_not_absorbed(self):
        r = pa.extract(MARKERS, ["Rongfeng Lu", "Hangyu Chen", "Ming Lu", "Le Zhang", "Bo Han"])
        self.assertEqual(r["layout"], "markers")
        self.assertEqual(r["affiliations"][0], ["Hangzhou Dianzi University", "Lishui Institute of Hangzhou Dianzi University"])
        self.assertEqual(r["affiliations"][2], ["Intel Labs China"])
        self.assertNotIn("Figure", " ".join(sum(r["affiliations"], [])))
        self.assertEqual(r["confidence"], "high")

    def test_symbol_marks_and_extra_pdf_name_tokens(self):
        r = pa.extract(SYMBOL_MARKS, ["Dung Nguyen", "Nam Le Hai", "Quang Pham"])
        self.assertEqual(r["affiliations"][0], ["FPT Software AI Center, Viet Nam"])
        self.assertEqual(r["affiliations"][1], ["Hanoi University of Science and Technology"])
        self.assertEqual(r["affiliations"][2], ["Independent Researcher", "FPT Software AI Center, Viet Nam"])

    def test_missing_abstract_or_author_is_not_high_confidence(self):
        self.assertEqual(pa.extract("no abstract here", ["A B"])["confidence"], "none")
        r = pa.extract(COLUMNS, ["Rong Tang", "Somebody Else"])
        self.assertNotEqual(r["confidence"], "high")

    def test_dangling_marks_are_stripped(self):
        self.assertEqual(pa._clean_affiliation("University of Science and Technology of China 1 3"),
                         "University of Science and Technology of China")


    def test_marks_lifted_above_the_names(self):
        r = pa.extract(MARKS_ABOVE, ["Zecheng Li", "Wengang Zhou", "Hezhen Hu"])
        ustc = "MoE Key Laboratory of Brain-inspired Intelligent Perception and Cognition, University of Science and Technology of China"
        self.assertEqual(r["affiliations"], [[ustc],
                                             [ustc, "Institute of Artificial Intelligence, Hefei Comprehensive National Science Center"],
                                             ["University of Texas at Austin"]])
        self.assertEqual(r["confidence"], "high")

    def test_numbered_list_with_periods(self):
        r = pa.extract(DOTTED_MARKS, ["Xinyu Ye", "Ziang Chen", "Junchi Yan"])
        self.assertEqual(r["affiliations"][0], ["Shanghai Jiao Tong University, Shanghai, China"])
        self.assertEqual(r["affiliations"][1], ["Massachusetts Institute of Technology, Massachusetts, United States"])

    def test_marks_at_the_end_of_each_entry(self):
        r = pa.extract(TRAILING_MARKS, ["Yiliao Song", "Zhenqiao Yuan", "Feng Liu"])
        self.assertEqual(r["affiliations"][0], ["School of Computer and Mathematical Sciences, The University of Adelaide, Adelaide, AU"])
        self.assertEqual(r["affiliations"][2], ["School of Computing and Information Systems, University of Melbourne, Melbourne, AU"])
        r = pa.extract(TRAILING_MARKS_IN_A_ROW, ["Xiang Li", "Yi Zhou", "Kun Zhang"])
        self.assertEqual(r["affiliations"], [["Carnegie Mellon University"], ["Adobe Research"], ["Carnegie Mellon University", "MBZUAI"]])

    def test_institution_printed_once_below_keyed_departments(self):
        r = pa.extract(SHARED_PARENT, ["Rafael Pastrana", "Eder Medina", "Isabel M. de Oliveira", "Sigrid Adriaenssens", "Ryan P Adams"])
        self.assertEqual(r["affiliations"][0], ["Architecture, Princeton University"])
        self.assertEqual(r["affiliations"][3], ["Civil and Environmental Engineering, Princeton University"])
        self.assertEqual(r["affiliations"][4], ["Computer Science, Princeton University"])

    def test_wrapped_last_entry_is_not_shared(self):
        r = pa.extract(WRAPPED_LAST_ENTRY, ["Ann Lee", "Bo Chen"])
        self.assertEqual(r["affiliations"], [["Tsinghua University"], ["Shanghai Artificial Intelligence Laboratory"]])

    def test_second_row_of_a_two_column_legend(self):
        r = pa.extract(LEGEND_IN_TWO_COLUMNS, ["Katharina Friedl", "Noémie Jaquier", "Tamim Asfour"])
        kth = "Division of Robotics, Perception, and Learning, KTH Royal Institute of Technology"
        kit = "Institute for Anthropomatics and Robotics, Karlsruhe Institute of Technology (KIT)"
        self.assertEqual(r["affiliations"], [[kth], [kth, kit], [kit]])

    def test_mark_alone_on_a_line_labels_the_text_under_it(self):
        r = pa.extract(MARK_ABOVE_ITS_COLUMN, ["Zhenyu Zhu", "Fanghui Liu", "Volkan Cevher"])
        self.assertEqual(r["affiliations"], [["École Polytechnique Fédérale de Lausanne"], ["University of Warwick"],
                                             ["École Polytechnique Fédérale de Lausanne"]])

    def test_footnote_sharing_a_legend_line_keeps_the_entries_before_it(self):
        r = pa.extract(FOOTNOTE_ON_LEGEND_LINE, ["Alexander Meulemans", "Blake A Richards", "Joao Sacramento"])
        self.assertEqual(r["affiliations"][1], ["Google, Paradigms of Intelligence Team", "Mila - Quebec AI Institute",
                                                "Université de Montréal", "McGill University"])
        self.assertEqual(r["affiliations"][0], ["Google, Paradigms of Intelligence Team"])

    def test_mark_glued_to_a_surname_the_listing_puts_first(self):
        r = pa.extract(MARK_AFTER_SURNAME, ["Xudong Gong", "Feng Dawei", "Kele Xu"])
        self.assertEqual(len(r["affiliations"][1]), 2)
        self.assertIn("National University of Defense Technology", r["affiliations"][1][0])

    def test_keyed_group_followed_by_a_block_of_its_own(self):
        r = pa.extract(KEYED_GROUP_THEN_BLOCK, ["Apivich Hemachandra", "Gregory Kang Ruey Lau", "See-Kiong Ng", "Bryan Kian Hsiang Low"])
        nus = "Department of Computer Science, National University of Singapore, Singapore 117417"
        self.assertEqual(r["affiliations"], [[nus], [nus, "CNRS@CREATE, 1 Create Way, #08-01 Create Tower, Singapore 138602"], [nus], [nus]])
        self.assertEqual(r["confidence"], "high")

    def test_street_number_is_not_a_mark(self):
        r = pa.extract(ADDRESS_NUMBER, ["Connor Mooney", "Zhongjian Wang"])
        self.assertIn("21 Nanyang Link", r["affiliations"][1][0])
        self.assertIn("University of California at Irvine", r["affiliations"][0][0])

    def test_conjunction_separates_institutions_but_stacked_lines_do_not(self):
        r = pa.extract(CONJOINED_BLOCKS, ["Federico Adolfi", "Martina G. Vilas", "Tian Ye", "Depen Morwani"])
        self.assertEqual(r["affiliations"], [["ESI Neuroscience, Max-Planck Society", "University of Bristol"],
                                             ["Department of Computer Science, Goethe University Frankfurt"],
                                             ["FAIR at Meta", "Carnegie Mellon University"],
                                             ["Kempner Institute, Harvard University"]])
        self.assertEqual(pa._split_block(["Departments of Statistics and Machine Learning, Carnegie Mellon University"]),
                         ["Departments of Statistics and Machine Learning, Carnegie Mellon University"])
        self.assertEqual(pa._split_block(["State Key Laboratory of Complex & Critical Software Environment"]),
                         ["State Key Laboratory of Complex & Critical Software Environment"])

    def test_keyed_list_the_marker_parser_cannot_read_is_not_broadcast(self):
        r = pa.extract(UNREAD_KEYED_LIST, ["Ann Lee", "Bo Chen"])
        self.assertEqual(r["affiliations"], [[], []])
        self.assertNotEqual(r["confidence"], "high")

    def test_icml_footnote_layout(self):
        footnote_doc = """
          Revisiting Character-level Adversarial Attacks for Language Models


            Elias Abad Rocamora 1 Yongtao Wu 1 Fanghui Liu 2 Grigorios Chrysos 3 Volkan Cevher 1


                          Abstract
       Adversarial attacks in Natural Language Process-
       ing apply perturbations in the character or token
       levels. Token-level attacks, gaining prominence.

1. Introduction
Language Models (LMs) have rapidly become the go-to                  The application of adversarial attacks in LMs is not straight-
tools for Natural Language Processing (NLP) tasks.                   forward due to algorithmic constraints.

   1
     LIONS, École Polytechnique Fédérale de Lausanne, Switzer-       where only input-output access to the model is assumed.
land 2 Department of Computer Science, University of Warwick,
United Kingdom 3 Department of Electrical and Computer Engi-
neering, University of Wisconsin-Madison, USA. Correspondence
to: Yongtao Wu <yongtao.wu@epfl.ch>.

Proceedings of the 41 st International Conference on Machine
Learning, Vienna, Austria. PMLR 235, 2024. Copyright 2024 by
the author(s).
"""
        authors = ["Elias Abad Rocamora", "Yongtao Wu", "Fanghui Liu", "Grigorios Chrysos", "Volkan Cevher"]
        r = pa.extract(footnote_doc, authors)
        self.assertEqual(r["confidence"], "high")
        self.assertEqual(r["layout"], "markers")
        self.assertIn("École Polytechnique Fédérale de Lausanne", r["affiliations"][0][0])
        self.assertIn("École Polytechnique Fédérale de Lausanne", r["affiliations"][1][0])
        self.assertIn("University of Warwick", r["affiliations"][2][0])
        self.assertIn("University of Wisconsin-Madison", r["affiliations"][3][0])
        self.assertIn("École Polytechnique Fédérale de Lausanne", r["affiliations"][4][0])


class OrderNoteIsNotAnAffiliationTest(unittest.TestCase):
    def test_order_note_matches_only_as_the_whole_entry(self):
        for note in ("Alphabetical order", "Authors listed in alphabetical order.", "authors are in alphabetical order"):
            self.assertTrue(pa._ORDER_NOTE.match(note), note)
        for real in ("EPFL, Switzerland. Alphabetical order.", "Alphabetical University"):
            self.assertFalse(pa._ORDER_NOTE.match(real), real)


class KeyedLegendLayoutsTest(unittest.TestCase):
    def test_question_mark_is_an_unrendered_symbol_mark(self):
        # pdftotext prints '?' for a symbol it cannot map (ICLR 2021 ChipNet).
        text = ("Rishabh Tiwari†‡∗ , Udbhav Bamba†‡∗ and Deepak K. Gupta†?∗\n"
                " †\n   Transmute AI Research, The Netherlands\n"
                " ‡\n   Indian Institute of Technology, ISM Dhanbad, India\n"
                " ?\n   Informatics Institute, University of Amsterdam, The Netherlands\n\n\nAbstract\n")
        got = pa.extract(text, ["Rishabh Tiwari", "Udbhav Bamba", "Deepak K. Gupta"])["affiliations"]
        self.assertEqual(got[0], ["Transmute AI Research, The Netherlands", "Indian Institute of Technology, ISM Dhanbad, India"])
        self.assertEqual(got[2], ["Transmute AI Research, The Netherlands",
                                  "Informatics Institute, University of Amsterdam, The Netherlands"])

    def test_each_name_group_reads_its_own_legend(self):
        # names, legend, names, legend (ICML 2016 kanagawa16).
        text = ("Heishiro Kanagawa†        KANAGAWA@TITECH.AC.JP\n"
                "Taiji Suzuki†,‡           SUZUKI@TITECH.AC.JP\n"
                "†\n  Tokyo Institute of Technology, Tokyo, JAPAN\n"
                "‡\n  PRESTO, Japan Science and Technological Agency (JST), JAPAN\n"
                "Hayato Kobayashi?         HAKOBAYA@YAHOO-CORP.JP\n"
                "?\n  Yahoo Japan Corporation, Tokyo, JAPAN\n\n\nAbstract\n")
        got = pa.extract(text, ["Heishiro Kanagawa", "Taiji Suzuki", "Hayato Kobayashi"])["affiliations"]
        self.assertEqual(got, [["Tokyo Institute of Technology, Tokyo, JAPAN"],
                               ["Tokyo Institute of Technology, Tokyo, JAPAN",
                                "PRESTO, Japan Science and Technological Agency (JST), JAPAN"],
                               ["Yahoo Japan Corporation, Tokyo, JAPAN"]])

    def test_footer_tails_and_line_breaks_are_cleaned(self):
        clean = pa._clean_affiliation
        self.assertEqual(clean("Amazon AGI, United States. Cor- Proceedings of the 42 nd International Conference on Machine"),
                         "Amazon AGI, United States")
        self.assertEqual(clean("UC Irvine, USA. Correspon-"), "UC Irvine, USA")
        self.assertEqual(clean("National University of Singapore. Proceedings of the"), "National University of Singapore")
        self.assertEqual(clean("McGill Univer- sity, Montréal"), "McGill University, Montréal")
        self.assertEqual(clean("Institute of Bio- and Geosciences"), "Institute of Bio- and Geosciences")
        self.assertEqual(clean("Cornell University"), "Cornell University")
        self.assertEqual(clean("{dipankar.das,naveen.k.mellempudi"), "")

    def test_mark_ranges_expand(self):
        text = ("David Klindt * 1-3 , Matthias Bethge 1,2,4-5\n"
                "              1\n                 Centre A, University of X\n"
                "      2\n        Center B, University of X\n"
                "                3\n                   Institute C, University of X\n"
                "                  4\n                    Institute D, University of X\n"
                "               5\n                   Institute E, Y\n\n\nAbstract\n")
        got = pa.extract(text, ["David Klindt", "Matthias Bethge"])["affiliations"]
        self.assertEqual(len(got[0]), 3)
        self.assertEqual(len(got[1]), 4)

    def test_glued_single_digit_marks_and_bracketed_keys(self):
        text = ("Erin Grant12 , Chelsea Finn12 , Thomas Griffiths13\n"
                " 1\n   Berkeley AI Research (BAIR), University of California, Berkeley\n"
                " 2\n   Department of EECS, University of California, Berkeley\n"
                " 3\n   Department of Psychology, University of California, Berkeley\n\n\nAbstract\n")
        got = pa.extract(text, ["Erin Grant", "Chelsea Finn", "Thomas Griffiths"])["affiliations"]
        self.assertEqual(got[2], ["Berkeley AI Research (BAIR), University of California, Berkeley",
                                  "Department of Psychology, University of California, Berkeley"])
        text = (" Christopher Roth[1],[2] , and Ila Fiete[2],[3]\n"
                " [1] Department of Physics, University of Texas at Austin\n"
                " [2] Department of Neuroscience, University of Texas at Austin\n"
                " [3] OpenAI, San Francisco CA\n\n\nAbstract\n")
        got = pa.extract(text, ["Christopher Roth", "Ila Fiete"])["affiliations"]
        self.assertEqual(got[1], ["Department of Neuroscience, University of Texas at Austin", "OpenAI, San Francisco CA"])

    def test_pmlr_footnote_marks_over_a_run_together_line(self):
        lines = ["ent grocery stores, and people take outdoor exercises at          To address these issues, we propose THIS-ODE, a novel de-",
                 "   1                                          2",
                 "    School of Computing, University of Utah Scientific Comput-    composition model of temporal high-order interactions. Our",
                 "ing and Imaging (SCI) Institute, University of Utah. Correspon-   model can fully leverage continuous timestamps, flexibly",
                 "dence to: Shandian Zhe <zhe@cs.utah.edu>.                         capture all kinds of complex temporal dynamics within the",
                 "                                                                  interactions, and encode nonlinear temporal relationships",
                 "Proceedings of the 39 th International Conference on Machine      of the participant objects into their representations.",
                 "Learning, Baltimore, Maryland, USA, PMLR 162, 2022. Copy-"]
        entries = pa._footnote_legend(lines, {"1", "2"})
        got = {e["mark"]: pa._clean_affiliation("".join(e["parts"])) for e in entries}
        self.assertEqual(got["1"], "School of Computing, University of Utah")
        self.assertTrue(got["2"].startswith("Scientific Computing and Imaging (SCI) Institute, University of Utah"))

    def test_pmlr_footnote_skips_a_section_number_over_body_text(self):
        text = ("Tighter Bounds\n\n    Tom Rainforth 1 Adam Kosiorek 1 2\n\n\n"
                "                          Abstract                       We provide evidence\n"
                "      We provide theoretical and empirical evidence\n\n"
                "1\n"
                "Variational bounds provide tractable and state-of-the-art ob-\n"
                "jectives for training deep generative models (Kingma &\n"
                "Welling, 2014; Rezende et al., 2014). Typically taking the\n\n"
                "1\n"
                "      Department of Statistics, University of Oxford 2 Department\n"
                "of Engineering, University of Oxford. Correspondence to: Tom\n\n"
                "Proceedings of the 35 th International Conference on Machine\n")
        got = pa.extract(text, ["Tom Rainforth", "Adam Kosiorek"])["affiliations"]
        self.assertEqual(got[0], ["Department of Statistics, University of Oxford"])
        self.assertEqual(got[1], ["Department of Statistics, University of Oxford",
                                  "Department of Engineering, University of Oxford"])

    def test_work_was_done_footnote_is_noise(self):
        self.assertTrue(pa._NOISE.search("Part of his work was done before joining Tencent"))

    def test_pmlr_key_printed_under_its_text_and_raised_first_line(self):
        # ICML 2022 kirchmeyer22a: "1" is raised over the first line, which
        # starts a little in; "2" sits on its own line under "Criteo".
        lines = [" Generalizing to New Physical Systems", "", "                     Matthieu Kirchmeyer 1 2 * Yuan Yin 1 *",
                 "                     Jeremie Dona Rakotomamonjy 2 3", "", "", "x",
                 "   *",
                 "    Equal contribution  1",
                 "                         CNRS-ISIR, Sorbonne University,          tions change with initial conditions",
                 "Paris, France Criteo AI Lab, Paris, France 3 Universite de",
                 "              2",
                 "",
                 "Rouen, LITIS, France. Correspondence to: Matthieu Kirch-          Thus any ML framework",
                 "meyer <matthieu.kirchmeyer@sorbonne-universite.fr>, Yuan          consider other assumptions.",
                 "Proceedings of the 39 th International Conference on Machine      a different distribution.",
                 "Learning, Baltimore, Maryland, USA, PMLR 162, 2022. Copy-"]
        entries = pa._footnote_legend(lines, {"1", "2", "3"})
        got = {e["mark"]: pa._clean_affiliation("".join(e["parts"])) for e in entries}
        self.assertEqual(got["1"], "CNRS-ISIR, Sorbonne University, Paris, France")
        self.assertEqual(got["2"], "Criteo AI Lab, Paris, France")

    def test_one_centred_stack_under_several_names_is_shared(self):
        text = ("    How Deep is the Feature Analysis\n\n\n"
                "                       Sven Eberhardt∗         Jonah Cader∗         Thomas Serre\n"
                "                       Department of Cognitive Linguistic & Psychological Sciences\n"
                "                                   Brown Institute for Brain Sciences\n"
                "                                         Brown University\n"
                "                                        Providence, RI 02818\n"
                "                          {sven2,jonah_cader,thomas_serre}@brown.edu\n\n\n"
                "                                                 Abstract\n")
        got = pa.extract(text, ["Sven Eberhardt", "Jonah Cader", "Thomas Serre"])["affiliations"]
        one = ["Department of Cognitive Linguistic & Psychological Sciences, Brown Institute for Brain Sciences, "
               "Brown University, Providence, RI 02818"]
        self.assertEqual(got, [one, one, one])

    def test_keyed_list_is_not_a_shared_stack(self):
        text = ("   A Title\n\n Yixiang Shan, Zhengbang Zhu, Ting Long\n"
                " 1\n   Jilin University, 2 Shanghai Jiao Tong University\n\n\nAbstract\n")
        self.assertIsNone(pa._shared_block(text.split("\n"), [(3, 1, 14), (3, 16, 30)]))

    def test_legend_columns_continue_under_their_own_entry(self):
        text = ("Contextual semibandits via supervised learning oracles\n\n"
                "       Akshay Krishnamurthy†             Alekh Agarwal‡                 Miroslav Dudík‡\n"
                "       akshay@cs.umass.edu            alekha@microsoft.com           mdudik@microsoft.com\n"
                "            †\n"
                "                College of Information and Computer Sciences         ‡\n"
                "                                                                         Microsoft Research\n"
                "                 University of Massachusetts, Amherst, MA                 New York, NY\n\n\n"
                "                                              Abstract\n")
        got = pa.extract(text, ["Akshay Krishnamurthy", "Alekh Agarwal", "Miroslav Dudik"])["affiliations"]
        self.assertEqual(got[0], ["College of Information and Computer Sciences, University of Massachusetts, Amherst, MA"])
        self.assertEqual(got[1], ["Microsoft Research, New York, NY"])
        self.assertEqual(got[2], ["Microsoft Research, New York, NY"])

    def test_up_arrow_is_a_symbol_mark(self):
        text = ("Coevolutionary Latent Feature Processes\n\n"
                "       Yichen Wang⇧ , Nan Du⇤ , Rakshit Trivedi⇧ , Le Song⇧\n"
                "                  ⇤\n                    Google Research\n"
                "           ⇧\n             College of Computing, Georgia Institute of Technology\n\n\nAbstract\n")
        got = pa.extract(text, ["Yichen Wang", "Nan Du", "Rakshit Trivedi", "Le Song"])["affiliations"]
        self.assertEqual(got[1], ["Google Research"])
        self.assertEqual(got[0], ["College of Computing, Georgia Institute of Technology"])


if __name__ == "__main__":
    unittest.main()
