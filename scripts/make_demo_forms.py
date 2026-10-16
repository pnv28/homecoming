"""Create synthetic typed/scanned forms for the hackathon, with no personal data."""
from pathlib import Path
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject,NameObject,DecodedStreamObject
import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[1]


def main():
    destination=ROOT/'assets/samples'
    writer=PdfWriter();page=writer.add_blank_page(width=595,height=842)
    font=DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})
    page[NameObject('/Resources')]=DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
    lines=[(22,790,'HOMECOMING - SYNTHETIC DEMONSTRATION FORM'),
           (11,762,'Fictional information for testing only. Not an official housing application.'),
           (16,711,'Part 1 - Applicant and household'),
           (13,675,'Applicant surname: CHAN'),(13,648,'Applicant given name: ALEX'),
           (13,621,'Number of household members: 2'),
           (12,577,'Applicant disability codes: none selected'),
           (12,550,'Family member: PARENT CHAN'),
           (12,523,'Family member disability code 1: [X]'),
           (11,495,'Code 1: non-temporary indoor dependence on wheelchair for mobility.'),
           (11,468,'Other disability codes: [ ] 2  [ ] 3  [ ] 4  [ ] 5  [ ] 6'),
           (16,400,'Part 5 - Choice of housing allocation area'),
           (13,360,'[X] Urban'),(13,332,'[ ] Extended Urban'),
           (13,304,'[ ] New Territories'),(13,276,'[ ] Islands'),
           (11,214,'Preferred hospital: not specified. The operator may choose in the app.'),
           (11,155,'The operator must review extracted values and press Yes, search.'),
           (10,90,'This example should prefill Alex Chan, household 2, Urban, wheelchair routes.')]
    commands=['0.12 0.25 0.21 rg']
    for size,y,label in lines:
        label=label.replace('\\','\\\\').replace('(','\\(').replace(')','\\)')
        commands.append('BT /F1 {} Tf 42 {} Td ({}) Tj ET'.format(size,y,label))
    stream=DecodedStreamObject();stream.set_data('\n'.join(commands).encode('ascii'))
    page[NameObject('/Contents')]=writer._add_object(stream)
    typed=destination/'synthetic-typed.pdf'
    with typed.open('wb') as output:writer.write(output)
    document=pdfium.PdfDocument(typed);rendered=document[0].render(scale=2)
    image=rendered.to_pil().convert('RGB')
    image.save(destination/'synthetic-scanned.pdf','PDF',resolution=144)
    image.close();rendered.close();document.close()
    print('Created synthetic-typed.pdf and synthetic-scanned.pdf')


if __name__=='__main__':main()
