"""Conservative, offline PDF text preparation for a text-only assistant.

PDF content-stream order can preserve paragraphs while scrambling table cells.
The library's existing ``pdftotext -layout`` extraction preserves printed column
positions, but does not prove which wrapped cells form a row. Never join a label
to its nearest number: that manufactures evidence when rows wrap or prose sits
beside a table. Keep the original layout and expose uncertainty instead.

This module reads no index, changes no library files, and makes no connections.
The caller validates catalog paths and serializes PDFium access as needed.
"""
from collections import Counter
from dataclasses import dataclass, replace
import re


LAYOUT_WARNING = (
    'LAYOUT-SENSITIVE SOURCE: Printed spacing and line breaks are preserved below. '
    'This page may contain columns, a table, or wrapped cells. Row/column '
    'associations have NOT been verified. Do not infer a quantity, unit, threshold '
    'or instruction by attaching nearby cells or mixing columns. If the needed '
    'association is not explicit in a complete sentence, abstain from interpreting '
    'the values. Inspect the original page image when image input is available '
    'or ask the reader to open the linked original page.'
)
MISSING_LAYOUT_WARNING = (
    'LAYOUT UNAVAILABLE: The text below follows PDF content-stream order, not '
    'verified printed row/column order. It does not establish table-cell '
    'associations. Do not derive quantities or instructions from adjacent cells. '
    'If the needed association is not explicit in a complete sentence, abstain '
    'from interpreting the values. Inspect the original page image when image '
    'input is available or ask the reader to open the linked original page.'
)
TRUNCATION_WARNING = (
    'SOURCE OMITTED: The complete page exceeds this text budget. No partial '
    'paragraph, table row or warning has been supplied. Do not infer omitted '
    'quantities, conditions or instructions. Ask the reader to open the linked '
    'original page, or request the page with a larger text budget.'
)


@dataclass(frozen=True)
class PageText:
    """Prepared evidence plus uncertainty flags; these are not accuracy guarantees."""
    text: str
    layout_sensitive: bool = False
    layout_available: bool = False
    unavailable: bool = False
    truncated: bool = False
    warnings: tuple[str, ...] = ()

    def bounded(self, max_chars):
        """Return complete evidence or an explicitly flagged whole-page omission."""
        if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 512:
            raise ValueError('source text budget must be an integer of at least 512 characters')
        if len(self.render()) > max_chars:
            return replace(self, text='', truncated=True, warnings=(TRUNCATION_WARNING,))
        return self

    def render(self, max_chars=None):
        """Render evidence without silently cutting a cell or source warning.

        The limit includes notices. Cutting a layout page at a character/line
        boundary can separate a wrapped label, condition or footnote from its
        value; dropping the whole page is safer than inventing a complete row.
        The same conservative rule prevents silently clipped prose warnings.
        """
        if max_chars is not None:
            return self.bounded(max_chars).render()
        notice = '\n'.join('[' + warning + ']' for warning in self.warnings)
        return (notice + ('\n\n' if self.text else '') if notice else '') + self.text


def _normalise(text):
    # Keep horizontal spacing, paragraph breaks, fractions, units and punctuation.
    # Expand tabs consistently rather than letting a model/viewer invent tab stops.
    return str(text or '').replace('\r\n', '\n').replace('\r', '\n').expandtabs(8).strip('\n\f')


def layout_sensitive(text):
    """Conservatively flag spatial text; do not attempt to recognize its subject.

    Two lines with separated cells, or recurring widely separated left edges,
    indicate that simple content-stream order cannot establish reading order.
    This may also flag code, indented quotations or multi-column prose. A flag
    means uncertainty, never that a table was reliably detected or reconstructed.
    """
    lines = [line for line in _normalise(text).splitlines() if line.strip()]
    separated = sum(bool(re.search(r'\S[ \t]{3,}\S', line)) for line in lines)
    if separated >= 2:
        return True
    starts = Counter(len(line) - len(line.lstrip()) for line in lines)
    recurring = [start for start, count in starts.items() if count >= 2]
    return bool(recurring and max(recurring) - min(recurring) >= 8)


def prepare_page(paragraph_text, layout_text=None):
    """Use paragraph order for ordinary prose; retain layout when spatial.

    Both inputs must describe the same original page. ``layout_text`` is the
    immutable library extraction, never a flattened search snippet. An absent
    layout is explicitly unverified, not evidence that a page has no tables.
    """
    paragraphs = _normalise(paragraph_text)
    layout = _normalise(layout_text)
    if not paragraphs.strip() and not layout.strip():
        return PageText('', unavailable=True, warnings=(
            'SOURCE TEXT UNAVAILABLE: No extractable text on this page. Do not '
            'infer its content. Inspect the image when image input is available '
            'or ask the reader to open the linked original page.',))
    if not layout.strip():
        return PageText(paragraphs, layout_sensitive=True,
                        warnings=(MISSING_LAYOUT_WARNING,))
    spatial = layout_sensitive(layout)
    if spatial or not paragraphs.strip():
        return PageText(layout, layout_sensitive=True, layout_available=True,
                        warnings=(LAYOUT_WARNING,))
    return PageText(paragraphs, layout_available=True)


def extract_pdf_page(path, number, layout_text=None):
    """Read a one-based page using the already-shipped PDFium dependency.

    Errors remain explicit and contain no filesystem paths or diagnostic data.
    No OCR, network request, subprocess, extra dependency or document mutation.
    """
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ValueError('page number must be a positive integer')
    try:
        import pypdfium2
        pdf = pypdfium2.PdfDocument(str(path))
        try:
            page = pdf[number - 1]
            try:
                textpage = page.get_textpage()
                try:
                    paragraphs = textpage.get_text_range()
                finally:
                    textpage.close()
            finally:
                page.close()
        finally:
            pdf.close()
    except Exception:
        return PageText('', unavailable=True, warnings=(
            'ORIGINAL SOURCE UNAVAILABLE: Page extraction failed. Do not infer '
            'its content. Ask the reader to open the linked original page.',))
    return prepare_page(paragraphs, layout_text)
