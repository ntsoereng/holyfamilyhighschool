import nh3
from django.core.exceptions import ValidationError
from PIL import Image

def client_ip(request):
    # Never trust caller-supplied forwarding headers.
    return request.META.get('REMOTE_ADDR', '127.0.0.1')

def clean_html(value):
    import re
    def attribute_filter(tag, attribute, content):
        if tag == 'img' and attribute == 'src':
            # Only images uploaded through the staff editor can be embedded.
            return content if re.fullmatch(r'/media/editor/[a-f0-9]{32}\.(?:jpg|png|webp)', content) else None
        if attribute in {'width', 'height', 'colspan', 'rowspan'}:
            return content if content.isdigit() and 0 < int(content) <= 2000 else None
        return content
    return nh3.clean(value, tags={'p','br','strong','em','ul','ol','li','h2','h3','h4','blockquote','a',
        'img','figure','figcaption','table','thead','tbody','tr','th','td','hr'},
        attributes={'a': {'href', 'title'}, 'img': {'src','alt','width','height'},
                    'td': {'colspan','rowspan'}, 'th': {'colspan','rowspan','scope'}},
        attribute_filter=attribute_filter, url_schemes={'https','http','mailto'})


def validate_image(value):
    from pathlib import Path
    if Path(value.name).suffix.lower() not in {'.jpg', '.jpeg', '.png', '.webp'}:
        raise ValidationError('Use a .jpg, .jpeg, .png or .webp filename.')
    if value.size > 5 * 1024 * 1024:
        raise ValidationError('Please choose an image smaller than 5 MB.')
    try:
        image = Image.open(value)
        if image.format not in {'JPEG', 'PNG', 'WEBP'} or image.width * image.height > 20000000:
            raise ValueError()
        image.verify()
    except Exception:
        raise ValidationError('Upload a valid JPEG, PNG or WebP image (up to 20 megapixels).')
    finally:
        value.seek(0)


GOOGLE_MAPS_EMBED_ORIGINS = ('https://www.google.com', 'https://google.com', 'https://maps.google.com')


def validate_google_maps_embed(value):
    """Accept iframe URLs, not arbitrary links, HTML or redirect endpoints."""
    from urllib.parse import urlsplit, parse_qs
    if not value:
        return
    message = ('Paste the HTTPS Google Maps embed URL from the src attribute under Share → Embed a map. '
               'Short share links and full iframe HTML are not supported.')
    try:
        parsed = urlsplit(value)
        valid_origin = f'{parsed.scheme}://{parsed.netloc}' in GOOGLE_MAPS_EMBED_ORIGINS
        embed_path = parsed.path == '/maps/embed' or parsed.path.startswith('/maps/embed/')
        legacy_embed = parsed.path in {'/maps', '/maps/'} and parse_qs(parsed.query).get('output') == ['embed']
        if not valid_origin or not (embed_path or legacy_embed) or parsed.fragment:
            raise ValueError
    except ValueError:
        raise ValidationError(message, code='invalid_map_embed')


def normalize_google_maps_embed(value):
    """Extract one copied iframe's trusted embed URL; never retain its HTML."""
    from html.parser import HTMLParser

    value = value.strip()
    message = ('Paste a Google Maps HTTPS embed URL or one complete iframe from Share → Embed a map. '
               'Other HTML, short share links and non-Google embeds are not supported.')
    if not value or not value.startswith('<'):
        try:
            if '<' in value or '>' in value:
                raise ValidationError(message, code='invalid_map_embed')
            validate_google_maps_embed(value)
        except ValidationError:
            raise ValidationError(message, code='invalid_map_embed')
        return value

    class EmbedParser(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.started = False
            self.ended = False
            self.src = None

        def reject(self):
            raise ValidationError(message, code='invalid_map_embed')

        def handle_starttag(self, tag, attrs):
            if tag != 'iframe' or self.started:
                self.reject()
            sources = [content for name, content in attrs if name == 'src']
            if len(sources) != 1 or not sources[0]:
                self.reject()
            self.started = True
            self.src = sources[0]

        def handle_endtag(self, tag):
            if tag != 'iframe' or not self.started or self.ended:
                self.reject()
            self.ended = True

        def handle_startendtag(self, tag, attrs):
            self.reject()

        def handle_data(self, data):
            if data.strip():
                self.reject()

        def handle_comment(self, data):
            self.reject()

        def handle_decl(self, decl):
            self.reject()

        def handle_pi(self, data):
            self.reject()

        def unknown_decl(self, data):
            self.reject()

    parser = EmbedParser()
    try:
        parser.feed(value)
        parser.close()
    except (ValueError, AssertionError):
        raise ValidationError(message, code='invalid_map_embed')
    if not parser.started or not parser.ended:
        raise ValidationError(message, code='invalid_map_embed')
    try:
        validate_google_maps_embed(parser.src)
    except ValidationError:
        raise ValidationError(message, code='invalid_map_embed')
    return parser.src
