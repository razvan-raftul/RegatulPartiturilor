"""Desenul partiturii ca pe hârtie (portative, chei, armură, note), pentru cine vede.

Partitura din fila Scrie o partitură (un scor music21) se trece în MusicXML, iar Verovio
(gravare de partituri, gratuit) o desenează ca SVG. Fereastra arată SVG-ul într-o pagină web
(wx.html2), iar butonul „Salvează desenul” îl scrie ca fișier .svg (se deschide în orice browser).
"""
import os
import threading

try:
    import verovio
except Exception:          # programul merge și fără desen
    verovio = None

_tk = None
_lacat = threading.Lock()      # Verovio desenează un singur lucru odată


def disponibil() -> bool:
    return verovio is not None


def _toolkit():
    global _tk
    if _tk is None:
        tk = verovio.toolkit()
        # în programul instalat (PyInstaller) fonturile Verovio stau lângă modul, în folderul data
        date = os.path.join(os.path.dirname(verovio.__file__), 'data')
        if os.path.isdir(date):
            tk.setResourcePath(date)
        _tk = tk
    return _tk


def musicxml(scor) -> str:
    from music21.musicxml.m21ToXml import GeneralObjectExporter
    return GeneralObjectExporter(scor).parse().decode('utf-8')


def svg(scor, latime=2100) -> str:
    """Toată partitura într-un singur SVG (o pagină lungă, rândurile rupte singure după lățime)."""
    if verovio is None:
        raise RuntimeError('Verovio lipsește')
    xml = musicxml(scor)
    with _lacat:
        return _deseneaza(xml, latime)


def _deseneaza(xml, latime):
    tk = _toolkit()
    tk.setOptions({
        'pageWidth': latime,
        'pageHeight': 60000,          # o singură pagină, oricât de lungă
        'adjustPageHeight': True,
        'scale': 45,
        'breaks': 'auto',
        'header': 'auto',
        'footer': 'none',
        'pageMarginTop': 50, 'pageMarginBottom': 50, 'pageMarginLeft': 50, 'pageMarginRight': 50,
    })
    if not tk.loadData(xml):
        raise RuntimeError('Verovio nu a putut citi partitura')
    return tk.renderToSVG(1)


def html(svg_text: str, mesaj: str = '') -> str:
    """Pagina pentru fereastră: fundal alb, desenul pe toată lățimea."""
    corp = svg_text or f'<p style="font-family:Segoe UI,sans-serif;color:#555">{mesaj}</p>'
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<meta http-equiv="X-UA-Compatible" content="IE=edge">'
            '<style>html,body{margin:0;padding:8px;background:#fff}</style>'
            f'</head><body>{corp}</body></html>')
