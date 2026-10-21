"""Limba programului. Textele sunt scrise în română în cod; _() le traduce în limba aleasă din Setări
(engleză implicit). Limba se citește o dată, la pornire, din setari.json; schimbarea cere repornirea programului."""
import json
import os

LIMBI = [('en', 'English'), ('ro', 'Română'), ('fr', 'Français'), ('de', 'Deutsch'), ('es', 'Español'), ('it', 'Italiano')]
IMPLICIT = 'en'


def folder_setari():
    """%APPDATA%\\Music Box. Dacă există doar folderul vechi (Regatul Partiturilor), îl redenumim; dacă nu se poate, îl folosim pe el."""
    baza = os.environ.get('APPDATA', os.path.expanduser('~'))
    nou, vechi = os.path.join(baza, 'Music Box'), os.path.join(baza, 'Regatul Partiturilor')
    if os.path.isdir(nou):
        return nou
    if os.path.isdir(vechi):
        try:
            os.rename(vechi, nou)
            return nou
        except OSError:
            return vechi
    return nou


DIR_SETARI = folder_setari()
FIS_SETARI = os.path.join(DIR_SETARI, 'setari.json')


def _limba_din_setari():
    try:
        with open(FIS_SETARI, encoding='utf-8') as f:
            l = json.load(f).get('limba', IMPLICIT)
    except Exception:
        l = IMPLICIT
    return l if l in dict(LIMBI) else IMPLICIT


LIMBA = _limba_din_setari()
_T = None


def seteaza(limba):
    """Pentru probe: schimbă limba fără repornire (fereastra deja făcută rămâne în limba veche)."""
    global LIMBA
    LIMBA = limba if limba in dict(LIMBI) else IMPLICIT


def _(s, *a):
    """Textul s (în română) în limba aleasă; {0}, {1}... se completează cu a."""
    global _T
    t = s
    if LIMBA != 'ro':
        if _T is None:
            try:
                from .traduceri import T
            except Exception:
                T = {}
            _T = T
        d = _T.get(s)
        if d:
            t = d.get(LIMBA) or d.get('en') or s
    if a:
        try:
            return t.format(*a)
        except Exception:
            return s.format(*a)
    return t
