"""Independent expected results for review counterexamples (synthetic VB6 only)."""
import hashlib
import tempfile
import unittest
import json
import contextlib
import io
from unittest.mock import patch
from pathlib import Path

from tools.extract_vbp import extract
from tools.index_build import StaleInventory, build_index, write_index
from tools.lib.effects import statement_effects
from tools.vb6_inventory import build_report, parse_procedures
from tools import bundle
from tools.lib.vbparse import find_comment_continuations, iter_statements
from tools.lib.show_style import parse_show_calls_in_line, parse_lifetime_calls_in_line
from tools.io_catalog import scan_source_text
from tools.frm_deep_read import extract_events, classify_events
from tools import comprehension_scaffold as cs
from tools.reimpl_excerpt import module_class_surface
from tools import verify_inventory as verify


class ExtractionRegressionTests(unittest.TestCase):
    def test_subdirectory_and_parent_paths_are_read_from_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / 'original'
            src.mkdir()
            (src / 'sub').mkdir()
            (src / 'sub' / 'M.bas').write_text('Public Sub LocalProc()\nEnd Sub\n')
            shared = root / 'Shared.bas'
            shared.write_text('Public Sub SharedProc()\nEnd Sub\n')
            vbp = src / 'P.vbp'
            vbp.write_text('Module=M; sub\\M.bas\nModule=S; ..\\Shared.bas\n')
            out = root / 'copies'
            report = extract(vbp, out, src)
            shared.write_text('Public Sub ChangedOriginal()\nEnd Sub\n')
            data = build_report(out, out / 'P.vbp', use_cache=False)
            self.assertEqual(data['missing_in_extract'], [])
            self.assertEqual([p['name'] for f in data['files'] for p in f['procedures']],
                             ['LocalProc', 'SharedProc'])
            self.assertEqual(len(report['source_map']), 2)

    def test_collision_stops_before_any_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / 'original'
            src.mkdir()
            for sub in ('a', 'b'):
                (src / sub).mkdir()
                (src / sub / 'M.bas').write_text(sub)
            vbp = src / 'P.vbp'
            vbp.write_text('Module=A; a\\M.bas\nModule=B; b\\M.bas\n')
            out = root / 'out'
            with self.assertRaisesRegex(SystemExit, 'collision'):
                extract(vbp, out, src)
            self.assertFalse(out.exists())

    def test_inventory_never_follows_unmapped_parent_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'M.bas').write_text('Public Sub Outside()\nEnd Sub\n')
            out = root / 'out'
            out.mkdir()
            vbp = out / 'P.vbp'
            vbp.write_text('Module=M; ..\\M.bas\n')
            data = build_report(out, vbp, use_cache=False)
            self.assertEqual(data['proc_total'], 0)
            self.assertEqual(data['missing_in_extract'], ['..\\M.bas'])

    def test_missing_files_fail_verification_even_with_no_parsed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv = root / 'p_inventory.json'
            inv.write_text(json.dumps({'stem': 'p', 'extract_dir': str(root),
                                       'files': [], 'missing_in_extract': ['M.bas']}))
            with patch.object(verify, 'reports_root', return_value=root), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(verify.main([str(inv)]), 1)

    def test_manifest_cannot_point_outside_extract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'Outside.bas').write_text('Sub Bad()\nEnd Sub')
            out = root / 'out'
            out.mkdir()
            vbp = out / 'P.vbp'
            vbp.write_text('Module=M; M.bas\n')
            (out / '_extract_report.json').write_text(json.dumps({
                'source_map': [{'reference': 'M.bas', 'copy': '../Outside.bas'}]}))
            self.assertEqual(build_report(out, vbp, use_cache=False)['proc_total'], 0)


class LexingRegressionTests(unittest.TestCase):
    def test_file_channels_are_not_date_literals(self):
        text = 'Get #1, , x: Put #2, , x'
        self.assertEqual([e['kind'] for e in scan_source_text(text, 'M.bas')], ['get', 'put'])

    def test_literal_parenthesis_in_optional_parameter(self):
        procs, _ = parse_procedures(['Function F(Optional ByVal x As String = "(") As Long', 'End Function'])
        self.assertEqual(procs[0]['returns'], 'Long')
        self.assertEqual(procs[0]['params'], 'Optional ByVal x As String = "("')

    def test_comment_line_continuation_follows_ms_vbal(self):
        # [MS-VBAL] comment-body = *(line-continuation / non-line-termination-character):
        # a comment ending in " _" also comments out the next physical line.
        for comment in ("' comment _", 'Rem comment _', "x = 1 ' comment _", 'x = 1: Rem comment _'):
            with self.subTest(comment=comment):
                lines = ['Public Sub Kept()', '    ' + comment, '    Kill "important.dat"', 'End Sub']
                procs, _ = parse_procedures(lines)
                self.assertEqual([(p['name'], p['line_start'], p['line_end']) for p in procs],
                                 [('Kept', 1, 4)])
                self.assertEqual(scan_source_text('\n'.join(lines), 'M.bas'), [])
                self.assertEqual(find_comment_continuations(lines),
                                 [{'line': 2, 'absorbed': [3]}])

    def test_named_argument_and_time_literal_are_not_split(self):
        lines = ['Call F(x:=1): d = #12:30:00#']
        self.assertEqual([s.text for s in iter_statements(lines)],
                         ['Call F(x:=1)', 'd = #12:30:00#'])

    def test_string_keywords_are_not_operations(self):
        self.assertEqual(scan_source_text('MsgBox "Kill the process"', 'M.bas'), [])
        self.assertEqual(parse_show_calls_in_line('MsgBox "Form2.Show vbModal"', 1), [])
        self.assertEqual(parse_lifetime_calls_in_line('MsgBox "Unload Form2"', 1), [])

    def test_apostrophe_in_path_is_preserved(self):
        text = 'Open "C:\\O\'Brien.dat" For Input As #1'
        entries = scan_source_text(text, 'M.bas')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['path_fragment'], "C:\\O'Brien.dat")

    def test_deep_read_uses_same_procedure_spans(self):
        lines = ['Attribute VB_Name = "F"', 'private sub Command1_Click()',
                 'end sub', 'Friend Sub Work( _', 'ByVal x As Long)', 'x = 1: End Sub']
        events = extract_events(lines)
        self.assertEqual([(e['name'], e['start_line'], e['end_line']) for e in events],
                         [('Command1_Click', 2, 3), ('Work', 4, 6)])


class EventAndTickRegressionTests(unittest.TestCase):
    def test_property_cli_keeps_other_accessor_unticked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inventory = root / 'p_inventory.json'
            inventory.write_text(json.dumps({'stem': 'p', 'files': [{'file': 'C.cls', 'procedures': [
                {'name': 'Value', 'kind': 'Property Get'}, {'name': 'Value', 'kind': 'Property Let'}]}]}))
            report = root / 'p.html'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(cs.main(['--inventory', str(inventory), '--out', str(report),
                    '--add-tick', 'Value@C.cls', '--kind', 'Property Get']), 0)
            ticked = cs.load_ticked_targets(report)
            self.assertEqual(ticked, {('C.cls', 'Value|Property Get')})

    def test_custom_withevents_handler_is_not_dead(self):
        code = 'Private WithEvents worker As Widget\nPrivate Sub worker_Completed()\nEnd Sub'
        events = classify_events(extract_events(code.splitlines()), code, '', [], 'F')
        self.assertEqual(events[0]['binding'], 'withevents_candidate')
        self.assertNotEqual(events[0]['status'], 'dead')

    def test_comments_and_strings_do_not_prove_calls(self):
        code = 'Private Sub Worker()\nEnd Sub\n\' Worker()\nMsgBox "Worker()"'
        events = classify_events(extract_events(code.splitlines()), code, '', [], 'F')
        self.assertEqual(events[0]['status'], 'unobserved')

    def test_property_accessors_have_separate_ticks_in_both_reports(self):
        data = {'files': [{'file': 'C.cls', 'type': 'class', 'procedures': [
            {'name': 'Value', 'kind': 'Property Get'},
            {'name': 'Value', 'kind': 'Property Let'}]}]}
        get = cs.find_procedure(data, 'Value', 'C.cls', 'Property Get')
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'c.html'
            report.write_text(cs.render_tick(1, get, 'A'), encoding='utf-8')
            ticked = cs.load_ticked_targets(report)
        self.assertEqual([r['kind'] for r in cs.list_unticked(data, ticked)], ['Property Let'])
        self.assertEqual(module_class_surface(data, ticked)[0]['unticked'], ['Value'])
        # Old notes survive, but cannot mark both accessors understood.
        self.assertEqual(len(cs.list_unticked(data, {('C.cls', 'Value')})), 2)


_SHADOW_BAS = """\
Attribute VB_Name = "M"
Public g As Long
Public Sub Foo(g As Long)
    g = 1
End Sub
Public Sub Bar()
    Dim g As Long
    g = 2
End Sub
Public Sub UsesModule()
    g = 3
End Sub
"""


class FreshnessAndScopeTests(unittest.TestCase):
    def _inventory(self, root: Path, bas: str) -> dict:
        (root / "P.vbp").write_bytes(b"Type=Exe\nModule=M; M.bas\n")
        (root / "M.bas").write_bytes(bas.encode("ascii"))
        return build_report(root, root / "P.vbp", use_cache=False)

    def test_changed_source_is_not_indexed_as_the_old_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv = self._inventory(root, 'Attribute VB_Name = "M"\nPublic Sub Foo()\nEnd Sub\n')
            recorded = inv["input_hashes"]["files"][0]
            self.assertEqual(recorded["file"], "M.bas")
            self.assertEqual(
                recorded["sha256"], hashlib.sha256((root / "M.bas").read_bytes()).hexdigest(),
            )
            (root / "M.bas").write_bytes(b'Attribute VB_Name = "M"\nPublic Sub Bar()\nEnd Sub\n')
            with self.assertRaises(StaleInventory) as caught:
                build_index(inv, root)
            self.assertTrue(any("M.bas" in item for item in caught.exception.problems))

    def test_parameter_and_local_do_not_bind_to_the_module_variable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = build_index(self._inventory(root, _SHADOW_BAS), root)
        var = "M.bas#Variable:g"
        unique = [
            o["in"] for o in data["occurrences"]
            if var in o["candidates"] and o["resolution"] == "unique"
        ]
        self.assertEqual(unique, ["M.bas#Sub:UsesModule"])
        locals_ = [o for o in data["occurrences"] if o["resolution"] == "local"]
        self.assertEqual({o["in"] for o in locals_}, {"M.bas#Sub:Foo", "M.bas#Sub:Bar"})
        self.assertTrue(all(var not in o["candidates"] for o in locals_))
        chunks = {c["id"]: c for c in data["chunks"]}
        self.assertNotIn(var, chunks["chunk:M.bas#Sub:Foo"]["refs"])
        self.assertNotIn(var, chunks["chunk:M.bas#Sub:Bar"]["refs"])
        self.assertIn(var, chunks["chunk:M.bas#Sub:UsesModule"]["refs"])
        self.assertTrue(any("隠す" in note for note in chunks["chunk:M.bas#Sub:Foo"]["notes"]))

    def test_bundle_refuses_when_the_indexed_source_changed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inv = self._inventory(root, _SHADOW_BAS)
            index_dir = root / "index"
            write_index(build_index(inv, root), index_dir)
            (root / "M.bas").write_bytes((root / "M.bas").read_bytes() + b"' changed\n")
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = bundle.main(["Foo@M.bas", "--index", str(index_dir)])
            self.assertEqual(code, 1)
            self.assertIn("M.bas", err.getvalue())


class UnknownFactsStayTests(unittest.TestCase):
    def test_conditional_deftype_is_not_one_type(self) -> None:
        src = (
            'Attribute VB_Name = "M"\n'
            "#Const X = 1\n"
            "#If X Then\n"
            "DefInt A-Z\n"
            "#Else\n"
            "DefStr A-Z\n"
            "#End If\n"
            "Dim n\n"
            "Public Sub Foo(a)\nEnd Sub\n"
        )
        from tools.vb6_inventory import _parse_bytes
        parsed = _parse_bytes(src.encode("ascii"), Path("M.bas"))
        var = parsed["variables"][0]
        self.assertEqual(var["name"], "n")
        self.assertEqual(var["type_source"], "conditional")
        self.assertEqual(var["type"], "unknown")
        self.assertEqual({item["type"] for item in var["type_candidates"]}, {"Integer", "String"})
        param = parsed["procedures"][0]["params_detail"][0]
        self.assertEqual(param["type_source"], "conditional")
        self.assertTrue(any(item["kind"] == "conditional_deftype" for item in parsed["diagnostics"]))

    def test_shared_end_keeps_both_headers(self) -> None:
        from tools.vb6_inventory import _parse_bytes
        src = (
            'Attribute VB_Name = "M"\n'
            "#If X Then\n"
            "Public Sub Foo(a As Long)\n"
            "#Else\n"
            "Public Sub Foo(a As String)\n"
            "#End If\n"
            "    a = 1\n"
            "End Sub\n"
        )
        parsed = _parse_bytes(src.encode("ascii"), Path("M.bas"))
        self.assertEqual(len(parsed["procedures"]), 1)
        param = parsed["procedures"][0]["params_detail"][0]
        self.assertEqual(param["type"], "unknown")
        self.assertEqual(param["type_source"], "conditional")
        self.assertEqual({item["type"] for item in param["type_candidates"]}, {"Long", "String"})

    def test_string_createobject_is_not_a_call(self) -> None:
        text = 's = "CreateObject(""ADODB.Connection"")"'
        self.assertEqual(statement_effects(text), [])
        real = statement_effects('Set cn = CreateObject("ADODB.Connection")')
        self.assertEqual(real, [{"kind": "com.create", "call": "CreateObject", "progid": "ADODB.Connection"}])
        got = statement_effects('Set xl = GetObject("C:\\book.xls", "Excel.Application")')
        self.assertEqual(got, [{
            "kind": "com.get", "call": "GetObject",
            "pathname": "C:\\book.xls", "class": "Excel.Application",
        }])

    def test_missing_frx_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "F.frm").write_text(
                'VERSION 5.00\nBegin VB.Form F\n   Caption         =   $"Other.frx":0000\nEnd\n'
                'Attribute VB_Name = "F"\n',
                encoding="ascii",
            )
            (src / "P.vbp").write_text("Type=Exe\nForm=F.frm\n", encoding="ascii")
            out = root / "out"
            report = extract(src / "P.vbp", out, src)
            self.assertIn("Other.frx", report["missing"])
            self.assertEqual(report["resources"][0]["exists"], False)
            self.assertNotIn("Other.frx", report["copied"])

    def test_property_and_with_stay_visible(self) -> None:
        bas = '''\
Attribute VB_Name = "W"
Public Property Get Value() As Long
End Property
Public Property Let Value(ByVal v As Long)
End Property
Public Sub Touch()
    Value = 1
    n = Value
    With unknownObj
        .Value = 2
    End With
End Sub
'''
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "P.vbp").write_bytes(b"Type=Exe\nClass=W; W.cls\n")
            (root / "W.cls").write_bytes(bas.encode("ascii"))
            data = build_index(build_report(root, root / "P.vbp", use_cache=False), root)
        touch = [o for o in data["occurrences"] if o["in"] == "W.cls#Sub:Touch" and o["name"] == "Value"]
        unique = {(tuple(o["candidates"]), o["resolution"]) for o in touch if o["resolution"] == "unique"}
        self.assertIn((("W.cls#PropertyLet:Value",), "unique"), unique)
        self.assertIn((("W.cls#PropertyGet:Value",), "unique"), unique)
        chunk = next(c for c in data["chunks"] if c["symbol"] == "W.cls#Sub:Touch")
        self.assertIn("W.cls#PropertyLet:Value", chunk["refs"])
        self.assertIn("W.cls#PropertyGet:Value", chunk["refs"])
        self.assertTrue(any(g["basis"] == "with" and g["resolution"] == "unresolved" for g in chunk["ref_gaps"]))
        got = bundle.build_bundle(
            data, bundle.find_target(data["symbols"], "Touch", "W.cls", None), 5000,
        )
        self.assertTrue(got["unresolved"])
        self.assertFalse(got["budget_exceeded"])
        self.assertIn("Unresolved or ambiguous references", [section["title"] for section in got["sections"]])


if __name__ == '__main__':
    unittest.main()
