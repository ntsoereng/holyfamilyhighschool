"""Discourage basic address harvesting without changing stored contact details."""
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import parse_qs, unquote, urlsplit

from django import template
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.urls import reverse
from django.utils.safestring import mark_safe

register = template.Library()
EMAIL_PATTERN = re.compile(r"[\w.!#$%&'*+/=?^`{|}~+-]+@(?:[\w-]+\.)+[\w-]+", re.UNICODE)


@register.filter(is_safe=True)
def obfuscate_email(value):
    return str(value or '').replace('@', ' [at] ')


@register.filter(is_safe=True)
def protect_email_text(value):
    return EMAIL_PATTERN.sub(lambda m: obfuscate_email(m[0]), str(value or ''))


@register.inclusion_tag('components/protected_email.html')
def protected_email(email, link_class='', icon=False, label='', subject=''):
    return {'address': obfuscate_email(email), 'link_class': link_class,
            'show_icon': icon, 'email_label': label, 'subject': subject}


@register.filter
def protect_email_html(value):
    """For already-sanitised rich content: protect text and mailto links alike."""
    class EmailHTML(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.output = []

        def handle_starttag(self, tag, attrs):
            attributes = dict(attrs)
            href = attributes.get('href') or ''
            if tag == 'a' and href.lower().startswith('mailto:'):
                parsed = urlsplit(href)
                address = unquote(parsed.path)
                try:
                    validate_email(address)
                except ValidationError:
                    attributes.pop('href', None)
                else:
                    attributes['href'] = reverse('contact')
                    attributes['data-email-address'] = obfuscate_email(address)
                    subject = parse_qs(parsed.query).get('subject', [''])[0]
                    if subject:
                        attributes['data-email-subject'] = subject
            rendered = ''.join(' ' + key + ('="' + escape(EMAIL_PATTERN.sub(lambda m: obfuscate_email(m[0]), val), quote=True) + '"'
                                           if val is not None else '') for key, val in attributes.items())
            self.output.append(f'<{tag}{rendered}>')

        def handle_startendtag(self, tag, attrs):
            self.handle_starttag(tag, attrs)

        def handle_endtag(self, tag):
            self.output.append(f'</{tag}>')

        def handle_data(self, data):
            self.output.append(escape(EMAIL_PATTERN.sub(lambda m: obfuscate_email(m[0]), data)))

        def handle_comment(self, data):
            pass  # Do not expose addresses hidden in editorial comments.

    parser = EmailHTML()
    parser.feed(str(value or ''))
    parser.close()
    return mark_safe(''.join(parser.output))
