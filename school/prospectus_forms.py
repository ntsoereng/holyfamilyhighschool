from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, BadZipFile

from django import forms
from django.core.exceptions import ValidationError

from .prospectus_limits import MAX_PDF_BYTES, MAX_PAGES, RENDER_TIMEOUT


def prepare_pdf(upload):
    if Path(upload.name).suffix.lower() != '.pdf' or upload.size > MAX_PDF_BYTES:
        raise ValidationError('Choose a PDF no larger than 8 MB, with at most 40 pages.')
    source = upload.read(MAX_PDF_BYTES + 1)
    if len(source) > MAX_PDF_BYTES or not source.startswith(b'%PDF-'):
        raise ValidationError('Choose a valid PDF document.')
    try:
        process = subprocess.run([sys.executable, '-m', 'school.prospectus_render'], input=source,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=RENDER_TIMEOUT,
            cwd=Path(__file__).resolve().parent.parent, check=True)
        with ZipFile(BytesIO(process.stdout)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 2 * MAX_PDF_BYTES + 2 * 1024 * 1024:
                raise ValueError('Unexpected rendered size')
            pages = json.loads(archive.read('pages.json'))
            if not 1 <= len(pages) <= MAX_PAGES:
                raise ValueError('Unexpected page count')
            prepared = [{'number': index, 'image': archive.read(f'{index}.jpg'), 'text': page['text'],
                         'width': page['width'], 'height': page['height']}
                        for index, page in enumerate(pages, 1)]
            return {'pdf': archive.read('document.pdf'), 'pages': prepared}
    except (subprocess.SubprocessError, OSError, BadZipFile, KeyError, ValueError, TypeError) as exc:
        raise ValidationError('This PDF could not be prepared safely. Use an unlocked PDF with at most 40 pages; reduce large images if needed. The current prospectus has not changed.') from exc


class ProspectusUploadForm(forms.Form):
    pdf = forms.FileField(label='Prospectus PDF', widget=forms.FileInput(attrs={'accept': '.pdf,application/pdf'}))

    def clean_pdf(self):
        return prepare_pdf(self.cleaned_data['pdf'])


class ProspectusActionForm(forms.Form):
    revision = forms.UUIDField()
    action = forms.ChoiceField(choices=[('publish', 'Publish'), ('unpublish', 'Withdraw'), ('delete', 'Delete')])
