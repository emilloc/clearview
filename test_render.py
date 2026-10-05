"""Run: python3 -m unittest discover -s clearview -p 'test_*.py'"""
import json
from pathlib import Path
import tempfile
import unittest

from render import render, render_detail


class SmokeTest(unittest.TestCase):
    def test_sheet_rejects_thumbnail_and_prose_cells(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            image = base / 'flow.svg'
            image.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 2000"><style>text {font-size:16px}</style></svg>')
            data = {'title':'Example','summary':'Short','sections':[], 'panels':[
                {'title':'Flow','diagram':{'path':'flow.svg','alt':'Long flow'}}]}
            with self.assertRaisesRegex(ValueError, 'too small'):
                render_detail(data, base)
            image.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 200"><style>text {font-size:16px}</style></svg>')
            self.assertIn('data:image/svg+xml', render_detail(data, base))
            data['panels'] = [{'title':'Table','table':{'headers':['Meaning'], 'rows':[['long ' * 20]]}}]
            with self.assertRaisesRegex(ValueError, 'Table cell'):
                render_detail(data, base)
            data['panels'] = [{'title':'Example','span':4,'anatomy':[{'value':'<queued>','label':'Waiting'}]}]
            self.assertIn('&lt;queued&gt;', render_detail(data, base))
            data['panels'][0]['span'] = '4; color:red'
            with self.assertRaisesRegex(ValueError, 'span'):
                render_detail(data, base)

    def test_sheet_content_and_validation(self):
        data = {"title": "Jobs", "summary": "Example", "sections": [], "panels": [
            {"title": "Steps", "steps": ["Submit <job>", "Save result"]},
            {"title": "States", "table": {"headers": ["State", "Means"], "rows": [["Queued", "Waiting"]]}}
        ]}
        result = render_detail(data, Path('.'))
        self.assertIn('class="panels"', result)
        self.assertIn('Submit &lt;job&gt;', result)
        self.assertIn('<td>Waiting</td>', result)
        self.assertNotIn('<details', result)
        data['panels'][1]['table']['rows'][0].append('extra')
        with self.assertRaises(ValueError):
            render_detail(data, Path('.'))
        data['panels'] = [{"title": "Ambiguous", "steps": ["One"], "diagram": {"path": "x.svg", "alt": "x"}}]
        with self.assertRaises(ValueError):
            render_detail(data, Path('.'))

    def test_offline_output_and_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "diagram.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            data = {"title": "<script>bad()</script>", "summary": "A & B",
                    "diagram": {"path": "diagram.svg", "alt": 'A "quoted" label'},
                    "sections": [{"title": "Behavior", "text": "First\n\nSecond"}]}
            source, output = base / "detail.json", base / "detail.html"
            source.write_text(json.dumps(data))
            render(source, output)
            result = output.read_text()
            self.assertIn("data:image/svg+xml;base64,", result)
            self.assertIn("&lt;script&gt;", result)
            self.assertNotIn("<script>", result)
            self.assertIn("<details", result)
            self.assertNotIn('src="http', result)
            self.assertNotIn('href=', result)
            self.assertNotIn(str(base), result)
            (base / "diagram.svg").unlink()
            self.assertEqual(output.read_text(), result)  # Output retains the image.
            data["diagram"]["path"] = "../outside.svg"
            source.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                render(source, output)
            self.assertEqual(output.read_text(), result)  # Failure preserves prior output.
            del data["diagram"]
            self.assertNotIn("<img", render_detail(data, base))
            data["sections"] = "invalid"
            with self.assertRaises(ValueError):
                render_detail(data, base)


if __name__ == "__main__":
    unittest.main()
