"""Bounded PDF-to-images conversion. Run as a separate process, never in WSGI."""
from io import BytesIO
import json
import math
import sys
import unicodedata
from zipfile import ZipFile, ZIP_STORED

from .prospectus_limits import MAX_PDF_BYTES, MAX_PAGES, MAX_PAGE_PIXELS, MAX_TEXT_CHARS


def render(source):
    import pypdfium2 as pdfium
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    if len(source) > MAX_PDF_BYTES or not source.startswith(b'%PDF-'):
        raise ValueError('Invalid PDF')
    pdf = pdfium.PdfDocument(source)
    try:
        if not 1 <= len(pdf) <= MAX_PAGES:
            raise ValueError('Invalid page count')
        flat_stream = BytesIO()
        flat = canvas.Canvas(flat_stream, pageCompression=1)
        flat.setTitle('Holy Family High School prospectus')
        flat.setAuthor('Holy Family High School')
        archive_stream = BytesIO()
        manifest = []
        image_bytes = 0
        with ZipFile(archive_stream, 'w', compression=ZIP_STORED) as archive:
            for index in range(len(pdf)):
                page = pdf[index]
                try:
                    width, height = page.get_size()
                    if not all(math.isfinite(value) and 0 < value <= 5000 for value in (width, height)):
                        raise ValueError('Invalid page dimensions')
                    scale = min(2, math.sqrt(MAX_PAGE_PIXELS / (width * height)))
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil().convert('RGB')
                        try:
                            pixel_width, pixel_height = image.size
                            jpeg_stream = BytesIO()
                            image.save(jpeg_stream, format='JPEG', quality=85)
                            jpeg = jpeg_stream.getvalue()
                        finally:
                            image.close()
                    finally:
                        bitmap.close()
                    image_bytes += len(jpeg)
                    if image_bytes > MAX_PDF_BYTES:
                        raise ValueError('Rendered document is too large')
                    textpage = page.get_textpage()
                    try:
                        text = textpage.get_text_range(count=min(textpage.count_chars(), MAX_TEXT_CHARS))
                        text = ''.join(char for char in text if not unicodedata.category(char).startswith('C') or char in '\n\r\t')
                    finally:
                        textpage.close()
                    manifest.append({'number': index + 1, 'text': text, 'width': pixel_width, 'height': pixel_height})
                    archive.writestr(f'{index + 1}.jpg', jpeg)
                    flat.setPageSize((width, height))
                    flat.drawImage(ImageReader(BytesIO(jpeg)), 0, 0, width=width, height=height)
                    flat.showPage()
                finally:
                    page.close()
            flat.save()
            flattened = flat_stream.getvalue()
            if len(flattened) > MAX_PDF_BYTES:
                raise ValueError('Flattened PDF is too large')
            archive.writestr('document.pdf', flattened)
            archive.writestr('pages.json', json.dumps(manifest))
        return archive_stream.getvalue()
    finally:
        pdf.close()


def main():
    try:
        import resource
        # Bound CPU and virtual memory even for pathological native-parser input.
        for kind, maximum in ((resource.RLIMIT_CPU, 20), (resource.RLIMIT_AS, 768 * 1024 * 1024)):
            existing = resource.getrlimit(kind)
            bound = min([maximum] + [value for value in existing if value != resource.RLIM_INFINITY])
            resource.setrlimit(kind, (bound, bound))
        output = render(sys.stdin.buffer.read(MAX_PDF_BYTES + 1))
    except Exception:
        sys.stderr.write('PDF could not be rendered within the supported limits.\n')
        return 2
    sys.stdout.buffer.write(output)
    return 0


if __name__ == '__main__':
    sys.exit(main())
