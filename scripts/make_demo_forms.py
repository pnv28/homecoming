"""Fill the original four-page HD300E (Rev 1/2026) with fictional demo data.

The bundled application-form.pdf is byte-identical to the downloaded HD300.pdf.
Overlay entries on that template, then rasterise every page for the scanned copy.
Run with: .venv/bin/python scripts/make_demo_forms.py
"""
from pathlib import Path

from PIL import ImageFilter
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]


def overlay(width, height, entries, ticks):
    """Positions use PDF points from the top left; text positions are baselines."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=width, height=height)
    fonts = {}
    for key, face in [('DemoText', 'Helvetica'), ('DemoSignature', 'Helvetica-Oblique')]:
        font = DictionaryObject({
            NameObject('/Type'): NameObject('/Font'),
            NameObject('/Subtype'): NameObject('/Type1'),
            NameObject('/BaseFont'): NameObject('/' + face),
        })
        fonts[NameObject('/' + key)] = writer._add_object(font)
    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject(fonts),
    })
    commands = ['q', '0.03 0.12 0.30 rg', '0.03 0.12 0.30 RG']
    for x, top, text, size, font in entries:
        text = text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        commands.append(f'BT /{font} {size} Tf {x} {height-top} Td ({text}) Tj ET')
    commands.append('1.1 w 1 J 1 j')
    for x, top, size in ticks:
        commands.append(f'{x+1} {height-top-size*.55} m '
                        f'{x+size*.4} {height-top-size*.9} l '
                        f'{x+size-1} {height-top-1} l S')
    commands.append('Q')
    stream = DecodedStreamObject()
    stream.set_data('\n'.join(commands).encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    return page


def filled_pages():
    # Only two people are entered. The remaining household columns are unused.
    pages = []
    entries, ticks = [], []

    def text(x, y, value, size=9, signature=False):
        entries.append((x, y, value, size, 'DemoSignature' if signature else 'DemoText'))

    def tick(x, y, size=7):
        ticks.append((x, y, size))

    # Part 1: John and his mother Mary; Mary has wheelchair-dependence code 1.
    for x, given, day, month, year, ident in [
        (158, 'JOHN', '14', '06', '1988', 'DEMO001'),
        (248, 'MARY', '03', '02', '1956', 'DEMO002'),
    ]:
        text(x, 223, 'N/A')
        text(x, 242, given, 11)
        text(x, 259, 'DENG', 11)
        text(x, 294, day)
        text(x+23, 294, month)
        text(x+47, 294, year)
        text(x, 374, ident, 8)
        if given == 'MARY':
            text(x, 398, 'N/A', 8)
        text(x, 424, 'N/A', 7)
        text(x+56, 485, 'N/A', 6)
        text(x, 512, 'NO', 8)
        text(x, 538, 'N/A', 8)
    text(248, 312, 'MOTHER')
    tick(164.3, 270.6)  # John: male, unmarried.
    tick(153.5, 320.6)
    tick(292, 270.6)  # Mary: female, widowed.
    tick(285.7, 332.3)
    text(153, 454, 'N/A', 5.5)
    tick(255.3, 445.6)  # Mary's code 1, in her own column.
    text(226, 562, '0000 0000', 9)
    text(442, 559, 'N/A', 8)
    text(442, 572, 'N/A', 8)

    # Part 2: deliberately fictional address and non-dialable contact number.
    text(124, 692, 'JOHN DENG')
    text(124, 711, 'A')
    text(182, 709, '3', 8)
    text(258, 711, 'N/A', 8)
    text(124, 726, 'DEMO HOUSE')
    text(124, 742, 'N/A')
    text(75, 757, '1')
    text(184, 759, 'DEMO STREET')
    text(62, 776, 'SHAM SHUI PO', 8)
    tick(186, 770, 8)
    text(162, 798, 'N/A')
    text(400, 726, 'A')
    text(467, 726, '3', 8)
    text(544, 726, 'N/A', 8)
    text(400, 742, 'DEMO HOUSE')
    text(400, 760, 'N/A')
    text(366, 776, '1')
    text(465, 776, 'DEMO STREET')
    text(340, 798, 'SHAM SHUI PO', 7)
    tick(455.9, 788.2, 8)
    pages.append((entries, ticks))
    entries, ticks = [], []

    # Part 3: the income and asset totals agree with the individual entries.
    for x, name, income, deposits, cash in [
        (225, 'JOHN DENG', '12,000', '30,000', '1,000'),
        (301, 'MARY DENG', '0', '10,000', '500'),
    ]:
        text(x, 91, name, 8)
        text(x+13, 113, income, 9)
        tick(x-3, 137.1)
        for y in (222, 244, 263, 278, 301, 330, 453):
            text(x+10, y, '0')
        text(x+10, 375, deposits)
        text(x+10, 418, cash)
        text(x+13, 487, '31,000' if name == 'JOHN DENG' else '10,500')
    text(366, 129, '12,000')
    text(400, 509, '41,500')

    # Part 4: live with an elderly parent in the same unit. Part 5: Urban.
    tick(30, 611, 10)
    tick(46, 624, 9)
    tick(248.9, 730, 10)
    pages.append((entries, ticks))
    entries, ticks = [], []

    # Part 6: clearly marked demonstration signatures and fictional identifiers.
    for y, name, ident in [(547, 'JOHN DENG', 'DEMO001'), (568, 'MARY DENG', 'DEMO002')]:
        text(140, y, name, 10)
        text(300, y, ident, 9)
        text(445, y, name + ' (DEMO)', 9, signature=True)
    text(169, 650, '18')
    text(203, 650, '10')
    text(241, 650, '2026')
    pages.append((entries, ticks))
    entries, ticks = [], []

    # Part 7: English correspondence; elderly-only relative section is inapplicable.
    tick(353.9, 50, 10)
    text(110, 182, 'N/A', 9)
    text(75, 202, 'N/A', 9)
    pages.append((entries, ticks))
    return pages


def main():
    destination = ROOT / 'assets/samples'
    source = PdfReader(destination / 'application-form.pdf')
    if len(source.pages) != 4 or 'HD300E (Rev 1/2026)' not in source.pages[0].extract_text():
        raise ValueError('Expected the original four-page HD300E (Rev 1/2026) template.')
    writer = PdfWriter()
    for original, (entries, ticks) in zip(source.pages, filled_pages()):
        entries.insert(0, (135, 14, 'FICTIONAL SAMPLE - FOR DEMONSTRATION ONLY - NOT FOR SUBMISSION', 7, 'DemoText'))
        page = writer.add_page(original)
        page.merge_page(overlay(float(page.mediabox.width), float(page.mediabox.height), entries, ticks))
    writer.add_metadata({'/Title': 'HD300 - John Deng - fictional completed sample',
                         '/Subject': 'Two-person household; Urban; mother with disability code 1'})
    typed = destination / 'synthetic-typed.pdf'
    with typed.open('wb') as output:
        writer.write(output)

    # Image-only pages exercise OCR and preserve the complete official form.
    images = []
    document = pdfium.PdfDocument(typed)
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=2)
            try:
                image = bitmap.to_pil().convert('L').filter(ImageFilter.GaussianBlur(.25)).convert('RGB')
                images.append(image)
            finally:
                bitmap.close()
                page.close()
        images[0].save(destination / 'synthetic-scanned.pdf', 'PDF', resolution=144,
                       save_all=True, append_images=images[1:], quality=90,
                       title='HD300 - John Deng - fictional scanned sample')
    finally:
        document.close()
        for image in images:
            image.close()
    print('Created four-page HD300 typed and scanned samples for John Deng.')


if __name__ == '__main__':
    main()
