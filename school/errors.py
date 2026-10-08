"""Generic production errors must remain available without a database."""
from django.http import HttpResponseNotFound
from django.template.loader import render_to_string


def page_not_found(request, exception):
    # These standalone templates use no school records or request context processors.
    return HttpResponseNotFound(render_to_string('404.html'))
