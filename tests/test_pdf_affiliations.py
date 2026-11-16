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


if __name__ == "__main__":
    unittest.main()
