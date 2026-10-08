"""Build browser icon formats from the exact user-supplied transparent crest."""
from pathlib import Path
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'assets/branding/holy-family-favicon-source.png'
DESTINATION = ROOT / 'static/images'


def main():
    DESTINATION.mkdir(parents=True, exist_ok=True)
    with Image.open(SOURCE) as original:
        image = original.convert('RGBA')
        if image.width != image.height:
            raise ValueError('Use a square crest image so icons preserve its proportions.')
        for size in [32, 48, 96, 192, 512]:
            image.resize((size, size), Image.Resampling.LANCZOS).save(
                DESTINATION / f'holy-family-favicon-{size}.png', optimize=True)
        image.resize((180, 180), Image.Resampling.LANCZOS).save(
            DESTINATION / 'holy-family-apple-touch-icon.png', optimize=True)
        image.save(DESTINATION / 'holy-family-favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])


if __name__ == '__main__':
    main()
