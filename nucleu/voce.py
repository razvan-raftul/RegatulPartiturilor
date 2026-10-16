"""Vorbește prin NVDA (NVDA Controller Client), ca utilizatorul să audă ce face programul
chiar dacă fereastra nu are focusul (de exemplu progresul actualizării).
Dacă NVDA nu rulează sau biblioteca lipsește, nu face nimic."""
import ctypes
import os
import sys
import threading

NUME_DLL = 'nvdaControllerClient.dll'
_dll = None
_lacat = threading.Lock()


def _incarca():
    global _dll
    if _dll is not None:
        return _dll or None
    _dll = False
    if os.name != 'nt':
        return None
    foldere = [os.path.dirname(sys.executable), getattr(sys, '_MEIPASS', ''),
               os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    for d in foldere:
        cale = os.path.join(d, NUME_DLL) if d else ''
        if cale and os.path.isfile(cale):
            try:
                dll = ctypes.WinDLL(cale)
                dll.nvdaController_speakText.argtypes = [ctypes.c_wchar_p]
                _dll = dll
                break
            except (OSError, AttributeError):
                pass
    return _dll or None


def nvda_porneste() -> bool:
    d = _incarca()
    try:
        return bool(d) and d.nvdaController_testIfRunning() == 0
    except Exception:
        return False


def spune(text: str, intrerupe: bool = False) -> bool:
    """Spune textul prin NVDA. Întoarce True dacă a mers."""
    with _lacat:
        d = _incarca()
        if not d:
            return False
        try:
            if d.nvdaController_testIfRunning() != 0:
                return False
            if intrerupe:
                d.nvdaController_cancelSpeech()
            return d.nvdaController_speakText(text) == 0
        except Exception:
            return False
