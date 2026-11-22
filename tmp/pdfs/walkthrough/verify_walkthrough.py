from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
import pypdfium2 as pdfium
root=Path('tmp/pdfs/walkthrough')
pdf=pdfium.PdfDocument('output/pdf/report-module-testing-walkthrough.pdf')
assert len(pdf)==24
texts=[]
for i,page in enumerate(pdf):
    textpage=page.get_textpage()
    text=textpage.get_text_range()
    texts.append(text)
    assert f'{i+1} / 24' in text, (i,'Missing footer')
    assert '\ufffd' not in text, (i,'Replacement glyph')
    if 5 <= i <= 19:
        n=(i-5)*2+1
        for scenario in [f'T{n:02d}',f'T{n+1:02d}']:
            assert scenario in text,(i,scenario)
        assert text.count('Evidence / issue reference / actual difference:')==2,(i,'Scenario split')
    textpage.close()
    page.close()
Path('tmp/pdfs/walkthrough/extracted.txt').write_text('\n\f\n'.join(texts))
for group in range(4):
    contact=Image.new('RGB',(1260,1220),'#dfe5e0')
    draw=ImageDraw.Draw(contact)
    for j in range(6):
        page_no=group*6+j+1
        pic=Image.open(root/f'page-{page_no:02d}.png').convert('RGB')
        pic.thumbnail((400,570))
        x=10+(j%3)*420;y=30+(j//3)*600
        draw.text((x,y-20),f'PAGE {page_no}',fill='black')
        contact.paste(pic,(x,y))
    contact.save(root/f'contact-{group+1}.png')
print('Verified: 24 pages, correct footers, 30 complete scenarios, no replacement glyphs.')
print('PDF bytes:',Path('output/pdf/report-module-testing-walkthrough.pdf').stat().st_size)
pdf.close()
