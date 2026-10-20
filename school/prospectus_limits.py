"""Limits shared by the web form and the isolated PDF rendering worker."""
MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PAGES = 40
MAX_PAGE_PIXELS = 3_000_000
MAX_TEXT_CHARS = 20_000
RENDER_TIMEOUT = 30
