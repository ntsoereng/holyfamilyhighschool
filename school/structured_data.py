"""School identity from public settings, safely encoded as JSON-LD."""
import json

from django.templatetags.static import static
from .seo import absolute_url, canonical_origin, plain_description, school_for_request


def metadata(request):
    match = request.resolver_match
    origin = canonical_origin()
    if not match or match.url_name != 'home' or not origin:
        return {}
    school = school_for_request(request)
    data = {
        '@context': 'https://schema.org', '@type': 'School',
        '@id': origin + '/#school', 'url': origin + '/', 'name': school.name,
        'description': plain_description(school.footer_text),
        'logo': absolute_url(school.logo.url if school.logo else static('images/holy-family-favicon-512.png')),
    }
    for name, value in [('address', school.address), ('telephone', school.phone), ('email', school.email)]:
        if value:
            data[name] = value
    if school.facebook_url:
        data['sameAs'] = [school.facebook_url]
    encoded = json.dumps(data, ensure_ascii=True).replace('<', '\\u003C').replace('>', '\\u003E').replace('&', '\\u0026')
    return {'school_json_ld': encoded}
