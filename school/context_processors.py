from .seo import school_for_request

def school_settings(request):
    return {'school': school_for_request(request)}
