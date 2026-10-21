"""Citește din fereastră: face o poză doar în memorie și într-un fișier temporar la pagina afișată
de altă aplicație (de exemplu Henle Library sau nkoda), ca s-o recunoască. Poza se șterge imediat.
Doar pentru Windows; folosește wx pentru poză și funcțiile Windows pentru lista ferestrelor."""
import ctypes
import os
import tempfile

import wx
from .limba import _


def dpi_constient():
    """Coordonatele ferestrelor să fie în pixeli reali (altfel, cu ecranul mărit, poza iese tăiată)."""
    if os.name != 'nt':
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def ferestre():
    """Ferestrele vizibile cu titlu: listă de (hwnd, titlu)."""
    if os.name != 'nt':
        return []
    user32 = ctypes.windll.user32
    rez = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def f(hwnd, _x):
        if user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            n = user32.GetWindowTextLengthW(hwnd)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                user32.GetWindowTextW(hwnd, b, n + 1)
                if b.value.strip() and b.value not in ('Program Manager',):
                    rez.append((hwnd, b.value))
        return True
    user32.EnumWindows(PROC(f), 0)
    return rez


def fereastra_din_fata():
    if os.name != 'nt':
        return None, ''
    user32 = ctypes.windll.user32
    h = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(h)
    b = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(h, b, n + 1)
    return h, b.value


def aduce_in_fata(hwnd):
    user32 = ctypes.windll.user32
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)


class _RECT(ctypes.Structure):
    _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long), ('r', ctypes.c_long), ('b', ctypes.c_long)]


def dreptunghi(hwnd):
    r = _RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.l, r.t, r.r - r.l, r.b - r.t


def poza(hwnd) -> str:
    """Poza ferestrei (care trebuie să fie în față), mărită de două ori dacă e mică. Întoarce calea unui PNG temporar."""
    x, y, w, h = dreptunghi(hwnd)
    if w < 50 or h < 50:
        raise RuntimeError(_('Fereastra e prea mică sau e ascunsă.'))
    ecran = wx.ScreenDC()
    bmp = wx.Bitmap(w, h)
    mem = wx.MemoryDC(bmp)
    mem.Blit(0, 0, w, h, ecran, x, y)
    mem.SelectObject(wx.NullBitmap)
    img = bmp.ConvertToImage()
    if _aproape_uniforma(img):
        raise RuntimeError(_('Poza a ieșit goală sau neagră. Probabil aplicația aceasta nu permite poze ale ecranului.'))
    if h < 2000:
        img = img.Scale(w * 2, h * 2, wx.IMAGE_QUALITY_HIGH)
    d = tempfile.mkdtemp(prefix='regatul-fereastra-')
    cale = os.path.join(d, 'pagina.png')
    img.SaveFile(cale, wx.BITMAP_TYPE_PNG)
    return cale


def _aproape_uniforma(img) -> bool:
    """Adevărat dacă aproape toată poza are aceeași culoare (poză neagră sau goală)."""
    w, h = img.GetWidth(), img.GetHeight()
    numar = {}
    total = 0
    for i in range(0, w, max(1, w // 120)):
        for j in range(0, h, max(1, h // 120)):
            c = (img.GetRed(i, j) // 16, img.GetGreen(i, j) // 16, img.GetBlue(i, j) // 16)
            numar[c] = numar.get(c, 0) + 1
            total += 1
    return max(numar.values()) > 0.998 * total


def sterge(cale):
    try:
        os.remove(cale)
        os.rmdir(os.path.dirname(cale))
    except OSError:
        pass
