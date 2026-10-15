"""Explicit parent links; return destinations never come from arbitrary URLs."""
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.urls import reverse


def writing_return_url(request, route, posts, category=None):
    query = {}
    if category and request.GET.get('category') == category:
        posts = posts.filter(category=category)
        query['category'] = category
    value = request.GET.get('page', '')
    page = Paginator(posts, 9).get_page(value if len(value) <= 8 else '1').number
    if page > 1:
        query['page'] = page
    return reverse(route) + ('?' + urlencode(query) if query else '')
