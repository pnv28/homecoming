"""Render uploads in memory. No API key or applicant document is written to disk."""
import base64
import io
import threading
from pypdf import PdfReader
import pypdfium2 as pdfium

from homecoming.services import deepseek
from homecoming.settings import MAX_PDF_BYTES, MAX_PDF_PAGES

PDF_LOCK = threading.Lock()


def content_from_pdf(data):
    if len(data)>MAX_PDF_BYTES or not data.lstrip().startswith(b'%PDF-'):
        raise ValueError('Upload a PDF smaller than 15 MB.')
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('Please upload an unlocked PDF.')
        count = len(reader.pages)
        if not 1<=count<=MAX_PDF_PAGES:
            raise ValueError('Use a PDF with 1–12 pages.')
        text = [(p.extract_text() or '') for p in reader.pages]
    except ValueError:
        raise
    except Exception:
        raise ValueError('This PDF could not be opened. Please export a new copy.')
    standard = count==4 and 'HD300E' in text[0] and 'Part 5' in text[1]
    selected = [0,1] if standard else list(range(count))
    content = [dict(type='text',text='Read the entered form fields. Pages shown below retain their original page numbers. Do not infer values from blank printed labels.')]
    # PDFium is not thread-safe, including across different documents.
    with PDF_LOCK:
        document = pdfium.PdfDocument(data)
        try:
            for index in selected:
                page = document[index]
                # Two overlapping vertical crops keep small handwriting readable
                # under the provider's image downsampling. Omit financial/declaration
                # areas on the recognised standard form.
                width,height=page.get_size()
                if min(width,height)<=0:
                    raise ValueError('This PDF contains an invalid page size.')
                bitmap = page.render(scale=min(2,3000/max(width,height)))
                image = bitmap.to_pil().convert('RGB')
                if standard and index==0:
                    boxes = [(0,int(image.height*.20),image.width,int(image.height*.50)),
                             (0,int(image.height*.44),image.width,int(image.height*.73))]
                elif standard and index==1:
                    boxes = [(0,int(image.height*.78),image.width,image.height)]
                else:
                    boxes = [(0,0,image.width,int(image.height*.56)),
                             (0,int(image.height*.44),image.width,image.height)]
                for part, bounds in enumerate(boxes):
                    crop = image.crop(bounds)
                    output = io.BytesIO(); crop.save(output,'PNG')
                    content += [dict(type='text',text='Original page {}, region {}.'.format(index+1,part+1)),
                                dict(type='image_url',image_url=dict(url='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode(),detail='original'))]
                    crop.close()
                image.close(); bitmap.close(); page.close()
        finally:
            document.close()
    return content


def extract_pdf(data,key):
    return deepseek.extract(key,content_from_pdf(data))
