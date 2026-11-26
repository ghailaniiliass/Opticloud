import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from apps.core.legacy import dumpparser as dp
from apps.core.tests.helpers import FIXTURE


class SplitStatementsTests(SimpleTestCase):
    def test_semicolon_and_comment_markers_inside_strings_are_kept(self):
        sql = "-- commentaire\nINSERT INTO `t` (`a`) VALUES ('x;y -- z');\nSELECT 1; # fin"
        stmts = dp.split_statements(sql)
        self.assertEqual(stmts, ["INSERT INTO `t` (`a`) VALUES ('x;y -- z')", "SELECT 1"])

    def test_block_comments_are_ignored(self):
        self.assertEqual(dp.split_statements("/* a ; b */ SELECT 1;"), ["SELECT 1"])

    def test_escaped_and_doubled_quotes_do_not_end_the_string(self):
        stmts = dp.split_statements(r"SELECT 'a\'b;c', 'd''e;f';SELECT 2;")
        self.assertEqual(len(stmts), 2)


class ParseValuesTests(SimpleTestCase):
    def test_escapes_null_numbers_and_empty_string(self):
        rows = dp.parse_values(r"('a\'b','c''d','e\\f','g\nh',NULL,-2.50,'')")
        self.assertEqual(rows, [["a'b", "c'd", "e\\f", "g\nh", None, "-2.50", ""]])

    def test_percent_and_underscore_keep_their_backslash(self):
        self.assertEqual(dp.parse_values(r"('\%\_')"), [["\\%\\_"]])

    def test_several_rows(self):
        self.assertEqual(len(dp.parse_values("(1,'a'),\n(2,'b'),\n(3,NULL)")), 3)

    def test_unsupported_tokens_raise(self):
        for bad in ("(0x41)", "(NOW())", "(1+1)"):
            with self.subTest(bad):
                with self.assertRaises(dp.DumpParseError):
                    dp.parse_values(bad)

    def test_unterminated_string_raises(self):
        with self.assertRaises(dp.DumpParseError):
            dp.parse_values("('abc)")


class StructureTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dump = dp.parse_dump_file(FIXTURE)

    def test_nine_tables(self):
        self.assertEqual(sorted(self.dump.tables), ["categorie", "client", "fournisseur", "lentille", "marque",
                                                    "monture", "ordonnance", "patient", "verre"])

    def test_tables_without_primary_key_use_their_unique_key_as_effective_key(self):
        for name, col in (("categorie", "id_categorie"), ("client", "id_client")):
            t = self.dump.tables[name]
            self.assertEqual(t.primary_key, [])
            self.assertEqual(t.key_columns, [col])

    def test_enum_values_decimal_defaults_and_auto_increment(self):
        cols = {c.name: c for c in self.dump.tables["lentille"].columns}
        self.assertEqual(cols["type"].enum_values, ("journalière", "hebdomadaire", "mensuelle", "annuelle"))
        self.assertEqual((cols["diametre"].precision, cols["diametre"].scale), (4, 1))
        self.assertEqual(cols["stock"].default, "0")
        pat = {c.name: c for c in self.dump.tables["patient"].columns}
        self.assertTrue(pat["id"].auto_increment)
        self.assertEqual(pat["date_creation"].default, "CURRENT_TIMESTAMP")
        self.assertFalse(pat["nom"].nullable)
        self.assertEqual(self.dump.tables["fournisseur"].auto_increment, 8)

    def test_no_foreign_keys(self):
        self.assertTrue(all(not t.foreign_keys for t in self.dump.tables.values()))

    def test_typed_values(self):
        pat = self.dump.tables["patient"].typed_rows()[0]
        self.assertEqual(pat[3], date(1992, 5, 14))
        self.assertEqual(pat[13], datetime(2026, 4, 24, 9, 41, 53))
        self.assertEqual(self.dump.tables["monture"].typed_rows()[0][6], Decimal("2800.00"))

    def test_special_characters_are_read_exactly(self):
        marque = {r[0]: r for r in self.dump.tables["marque"].typed_rows()}
        self.assertEqual(marque["M004"][3], "C:\\opti\\fichier\nsuite ; avec point-virgule -- et tirets")
        self.assertEqual(marque["M003"][3], "Marque c\u00ef\u00bf\u00bdl\u00ef\u00bf\u00bdbre")   # séquence corrompue conservée


class RobustnessTests(SimpleTestCase):
    def test_wrong_number_of_values_raises(self):
        sql = "CREATE TABLE `t` (`a` int(11) NOT NULL, `b` int(11) default NULL, PRIMARY KEY (`a`)) ENGINE=InnoDB;\nINSERT INTO `t` (`a`, `b`) VALUES (1);"
        with self.assertRaises(dp.DumpParseError):
            dp.parse_dump_text(sql)

    def test_unknown_column_type_raises(self):
        with self.assertRaises(dp.DumpParseError):
            dp.parse_dump_text("CREATE TABLE `t` (`a` geometry NOT NULL) ENGINE=InnoDB;")

    def test_insert_on_undeclared_table_raises(self):
        with self.assertRaises(dp.DumpParseError):
            dp.parse_dump_text("INSERT INTO `x` (`a`) VALUES (1);")

    def test_non_utf8_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.sql"
            p.write_bytes("CREATE TABLE `t` (`a` int);\n-- é".encode("latin-1"))
            with self.assertRaisesMessage(dp.DumpParseError, "UTF-8"):
                dp.parse_dump_file(p)

    def test_bom_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.sql"
            p.write_bytes(b"\xef\xbb\xbfSELECT 1;")
            with self.assertRaisesMessage(dp.DumpParseError, "BOM"):
                dp.parse_dump_file(p)

    def test_parsing_never_modifies_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "d.sql"
            p.write_bytes(FIXTURE.read_bytes())
            p.chmod(0o444)
            before = p.stat().st_mtime_ns
            dp.parse_dump_file(p)
            self.assertEqual(p.stat().st_mtime_ns, before)
