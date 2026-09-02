"""Shared chrome for kit report HTML.

Pin a light color-scheme so dark-mode browsers do not invert table cells
into empty-looking blocks. UI chrome may be bilingual; fact columns
(VB_Name, filenames, procedure names) stay as in the source.
"""

LIGHT_THEME_CSS = """
:root { color-scheme: light; }
html, body { background: #ffffff; color: #222222; }
table { background: #ffffff; }
th, td { color: #222222; }
""".strip()

COLOR_SCHEME_META = '<meta name="color-scheme" content="light">'
