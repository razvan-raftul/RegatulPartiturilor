"""Music Box (fostul Regatul Partiturilor) – citește partituri pentru nevăzători: în cuvinte și în Braille muzical.
Fereastra folosește controale Windows obișnuite, ca NVDA să le citească bine.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback

# În programul instalat (fără consolă) nu există stdout/stderr; unele biblioteci scriu acolo și s-ar opri cu eroare.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

import wx  # noqa: E402
import wx.lib.scrolledpanel as scrolled  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nucleu import limba  # noqa: E402
from nucleu.limba import _  # noqa: E402
from nucleu import VERSIUNE, actualizare, auz, auz_absolut, fisiere_audio, inregistrare, midi_in, braille, captura, claviatura, cuprins, cuvinte, partitura, recunoastere, redare, scriere, sunet_iesire, sunet_pornire, sunete, voce  # noqa: E402

NUME = 'Music Box'
INDEMN = _('Nicio partitură deschisă. Deschide o partitură cu Control O.')
# setările: %APPDATA%\\Music Box (folderul vechi „Regatul Partiturilor” se redenumește singur, vezi limba.folder_setari)
DIR_SETARI = limba.DIR_SETARI
FIS_SETARI = os.path.join(DIR_SETARI, 'setari.json')
OCTAVE = [('fara', _('Fără octavă')), ('numere', _('Octava cu număr (do 4)')), ('nume', _('Octava cu nume (do din octava întâi)'))]
FILTRU = (_('Toate partiturile|') + ';'.join('*' + e for e in partitura.TOATE_FORMATELE) +
          _('|MusicXML (*.musicxml, *.xml, *.mxl)|*.musicxml;*.xml;*.mxl|MIDI (*.mid)|*.mid;*.midi|MuseScore (*.mscz)|*.mscz;*.mscx'
          '|PDF și imagini|*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff|Toate fișierele|*.*') +
          '|Braille (*.brl, *.brf)|*.brl;*.brf')
SCURTATURI = _("""Scurtături în Music Box

Control plus O: deschide o partitură.
L (sau Alt plus săgeată dreapta): măsura următoare.
J (sau Alt plus săgeată stânga): măsura anterioară.
Control plus G: mergi la o anumită măsură.
Control plus 1: textul în cuvinte.
Control plus 2: playerul (toată piesa; J și L derulează câte 5 secunde).
Control plus 3: textul în Braille.
Control plus 4: claviatura (cânți pe tastatură); Escape te scoate din ea.
Control plus L: lista de măsuri.
Control plus S: salvează textul în cuvinte.
Control plus B: salvează Braille pentru imprimantă (fișier BRF).
Control plus Shift plus B: din PDF în Braille, într-un singur pas (alegi PDF-ul, primești fișierul BRF în Documente, în folderul Music Box, în subfolderul cu numele PDF-ului).
La o carte cu multe pagini (de exemplu o culegere de studii), programul găsește singur unde începe fiecare piesă
și te întreabă pe care o deschizi: Studiul 2, paginile 3-4, și așa mai departe. Poți alege și toată cartea
sau scrie tu paginile. Se recunosc doar paginile alese, deci durează mult mai puțin.
Control plus U: următoarea măsură de verificat (la partiturile recunoscute din PDF).
Control plus Shift plus U: măsura de verificat anterioară.

Redare cu sunet (se cântă măsurile și portativele alese):
K: redă selecția; apăsat în timp ce se cântă, oprește; apăsat din nou, continuă de unde ai rămas.
Shift plus K: reia selecția de la început.
I: redă de la măsura aleasă până la final.
Shift plus 1: mai rar cu 5 la sută. Shift plus 2: mai repede cu 5 la sută. Shift plus 3: tempoul scris în piesă. Dacă piesa se cântă, se schimbă pe loc și continuă de unde a ajuns.
Control plus R: redare în buclă, pornită sau oprită.

Metronomul (cântă bătăile măsurii odată cu piesa, mereu în tempoul ei):
Control plus Shift plus M: metronomul pornit sau oprit.
Shift plus plus: metronomul mai tare cu 1 la sută. Shift plus minus: mai încet cu 1 la sută.
Control plus Shift plus plus: mai tare cu 5 la sută. Control plus Shift plus minus: mai încet cu 5 la sută.
Control plus 5: fila Scrie o partitură (scrii tu notele, pentru mâna dreaptă și stânga, apoi asculți și salvezi ca MusicXML sau BRF).
În câmpurile mâinilor: Control plus Enter ascultă măsura pe care ești (ambele mâini), Control plus F2 spune pe ce măsură ești.
Control plus 6: exerciții de auz (programul cântă o notă, un interval sau un acord și tu alegi ce ai auzit).
Acolo: Alt plus E te duce la lista Răspunsuri, Enter răspunde, virgulă ascultă din nou, punct dă un exercițiu nou.
Control plus 7: fila Setări (limba, metronomul și volumul lui, instrumentul claviaturii, clapa MIDI, întârzierea sunetului, unde sunt programele de recunoaștere).
O clapă MIDI legată la calculator cântă cu sunetele programului, cu instrumentul claviaturii.

Citește din fereastră (pentru aplicațiile editurilor, din care nu se poate descărca):
Control plus Alt plus P, apăsat din aplicația editurii: citește pagina afișată acum.
Control plus Shift plus F: alegi fereastra dintr-o listă.
Nu se salvează nimic: poza paginii se șterge imediat după recunoaștere.

Claviatura (Control plus 4), cât stai în ea celelalte taste nu mai fac nimic:
Rândul de jos, de la Z la 3 de pe blocul numeric: do, re, mi, fa, sol, la, si, do și tot așa, două octave.
Diezii sunt pe rândul de deasupra, cu o tastă mai la dreapta: S do diez, D re diez, F gol, G fa diez, H sol diez, J la diez, K gol, și tot așa.
La fel, cu o octavă mai jos: rândul de la Tab (până la 6 de pe blocul numeric) sunt notele, iar diezii sunt pe cifre, de la 1 (3, 7 și 0 sunt goale).
Shift stânga e bender: cât îl ții apăsat, nota tremură.
Săgeată dreapta sau stânga: o octavă mai sus sau mai jos (NVDA spune doar numărul octavei).
Săgeată sus sau jos: alt instrument.
Control plus săgeată dreapta sau stânga: transpui cu un semiton (ce era do se aude do diez).
Escape sau Control plus 1: ieși din claviatură. Instrumentul se poate alege și din fila Setări (Control plus 7).

Tab și Shift plus Tab trec doar prin elementele filei deschise.
F1: această listă.

În lista de măsuri poți selecta mai multe măsuri deodată cu Shift și săgețile. Primul rând este Despre piesă, al doilea Toată piesa.
Ce citesc alegi din lista Portative: toate, sau doar mâna dreaptă, sau doar mâna stângă.""")


def _SCURTATURI_FILE():
    """Textul de la F1 cu numerele filelor de acum (Muzică 1, Claviatura 2, Partituri 3, Scrie 4, Auz 5, Setări 6),
    în orice limbă: textul vechi avea 1 cuvinte, 2 player, 3 Braille, 4 claviatura, 5 scrie, 6 auz, 7 setări."""
    import re
    noi = {'1': '3', '2': '3', '3': '3', '4': '2', '5': '4', '6': '5', '7': '6'}
    return re.sub(r'((?:Control|Contrôle|Strg|Ctrl)\s+(?:plus|más|più)\s+)([1-7])\b',
                  lambda m: m.group(1) + noi[m.group(2)], SCURTATURI)


def citeste_setari():
    try:
        with open(FIS_SETARI, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def scrie_setari(d):
    try:
        os.makedirs(DIR_SETARI, exist_ok=True)
        with open(FIS_SETARI, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except Exception:
        pass


class Fereastra(wx.Frame):
    def __init__(self, fisier=None):
        super().__init__(None, title=NUME, size=(1180, 820))
        self.SetMinSize((820, 600))
        self.P = None
        self.setari = citeste_setari()
        recunoastere.SETARI['audiveris'] = self.setari.get('audiveris', '')
        recunoastere.SETARI['musescore'] = self.setari.get('musescore', '')
        recunoastere.SETARI['homr'] = self.setari.get('homr', '')
        self.redare = redare.Redare()
        self.redare.la_sfarsit = lambda: wx.CallAfter(self.SetStatusText, _('Redarea s-a terminat.'))
        self.procent = int(self.setari.get('tempo', 100))
        self.metronom = bool(self.setari.get('metronom', False))
        self.volum_metronom = int(self.setari.get('metronom_volum', 60))
        self.sint = sunete.sintetizator()
        if hasattr(self.sint, 'latenta'):
            self.sint.latenta = self.setari.get('latenta', 'normala')
        self.midi = midi_in.IntrareMidi(self.sint, transpunere=lambda: self.transpunere)
        # instrumentele, pe categorii; lista „plată” e pentru săgeată sus/jos din claviatură
        self.catalog = sunete.catalog()
        self.instrumente = [(cat, nume, prog) for cat, inst in self.catalog for nume, prog in inst]
        salvat = self.setari.get('instrument_bp')
        if salvat is None and isinstance(self.setari.get('instrument_prog'), int):
            salvat = [0, self.setari['instrument_prog']]
        progs = [tuple(x[2]) for x in self.instrumente]
        self.instrument = progs.index(tuple(salvat)) if salvat and tuple(salvat) in progs else 0
        self.sint.program = self.instrumente[self.instrument][2]
        self.do_clav = int(self.setari.get('octava_claviatura', 60))
        self.transpunere = int(self.setari.get('transpunere', 0))
        self._apasate = {}                   # tasta fizică -> nota care sună
        self._vibrato = claviatura.Vibrato(self.sint)
        self._bender_apasat = False
        self.player_audio = inregistrare.PlayerAudio()
        self._midi_cache = (None, None, None, [])  # (selecția, MIDI la 100%, bătăile, măsurile): nu se mai face din nou la fiecare tempo
        self._redat = None                   # (selecția, procentul, metronomul) cu care se cântă acum
        self._tempo_amanat = None
        self._ocupat_recunoastere = False
        self._braille_id = 0
        self._meniuri()
        self._interfata()
        self._aplica_setari()
        self._sincronizeaza_setari()
        self.CreateStatusBar()
        self.SetStatusText(_('Deschide o partitură cu Control plus O.'))
        self.SetDropTarget(Picurare(self))
        self.Bind(wx.EVT_CLOSE, self.la_inchidere)
        self.Bind(wx.EVT_CHAR_HOOK, self._taste)
        self.Centre()
        try:
            baza = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            if os.path.isfile(os.path.join(baza, 'icon.ico')):
                self.SetIcon(wx.Icon(os.path.join(baza, 'icon.ico'), wx.BITMAP_TYPE_ICO))
        except Exception:
            pass
        if fisier:
            wx.CallAfter(self.deschide, fisier)
        self._tasta_globala()
        # la pornire, cursorul stă pe fila „În cuvinte”, nu pe lista de măsuri (cerut de Răzvan)
        wx.CallAfter(self.carte.SetFocus)
        wx.CallLater(300, self.cutie_muzicala)
        wx.CallLater(3500, self._preincarca_sunete)
        if actualizare.instalat() and fisier != '--autotest':
            wx.CallLater(1500, self._anunta_versiunea_noua)
            wx.CallLater(1500, self.verifica_actualizari, False)

    # ---------------- interfață ----------------
    def _meniuri(self):
        mb = wx.MenuBar()
        f = wx.Menu()
        self._m(f, _('Deschide partitura...\tCtrl+O'), self.cere_fisier)
        self._m(f, _('Din PDF în Braille, într-un pas...\tCtrl+Shift+B'), self.pdf_in_braille)
        self._m(f, _('Citește din fereastră (aplicația editurii)...\tCtrl+Shift+F'), self.alege_fereastra)
        f.AppendSeparator()
        self._m(f, _('Salvează textul în cuvinte...\tCtrl+S'), self.salveaza_cuvinte)
        self._m(f, _('Salvează Braille pentru imprimantă (BRF)...\tCtrl+B'), lambda e: self.salveaza_braille(True))
        self._m(f, _('Salvează Braille ca text Unicode...'), lambda e: self.salveaza_braille(False))
        self._m(f, _('Salvează selecția ca MusicXML...'), self.salveaza_musicxml)
        f.AppendSeparator()
        self._m(f, _('Ieșire\tAlt+F4'), lambda e: self.Close())
        mb.Append(f, _('&Fișier'))
        n = wx.Menu()
        # L și J se prind direct din tastatură (vezi _taste); Alt și săgețile merg în continuare
        self._m(n, _('Măsura următoare (L)\tAlt+Right'), lambda e: self.muta(1))
        self._m(n, _('Măsura anterioară (J)\tAlt+Left'), lambda e: self.muta(-1))
        self._m(n, _('Mergi la măsura...\tCtrl+G'), self.mergi_la)
        self._m(n, _('Următoarea măsură de verificat\tCtrl+U'), lambda e: self.la_nesigura(1))
        self._m(n, _('Măsura de verificat anterioară\tCtrl+Shift+U'), lambda e: self.la_nesigura(-1))
        n.AppendSeparator()
        self._m(n, _('Muzică: fișierele audio din folderul tău\tCtrl+1'), lambda e: self.arata(0))
        self._m(n, _('Claviatura (cânți pe tastatură)\tCtrl+2'), lambda e: self.arata(1))
        self._m(n, _('Partituri: în cuvinte, Braille, player (încă o dată: următoarea)\tCtrl+3'), lambda e: self.arata(2, True))
        self._m(n, _('Textul în cuvinte'), lambda e: self.arata_sub(0))
        self._m(n, _('Textul în Braille'), lambda e: self.arata_sub(1))
        self._m(n, _('Player: toată piesa, derulezi cu J și L'), lambda e: self.arata_sub(2))
        self._m(n, _('Metronom'), lambda e: self.arata_sub(3))
        self._m(n, _('Scrie o partitură\tCtrl+4'), lambda e: self.arata(3))
        self._m(n, _('Exerciții de auz\tCtrl+5'), lambda e: self.arata(4))
        self._m(n, _('Setările\tCtrl+6'), lambda e: self.arata(5))
        self._m(n, _('Lista de măsuri\tCtrl+L'), lambda e: self.lista.SetFocus())
        mb.Append(n, _('&Navigare'))
        r = wx.Menu()
        # K, Shift K, tempoul și volumul metronomului se prind direct din tastatură (vezi _taste): în meniu doar se afișează
        self._m(r, _('Redă, oprește sau continuă (K)'), lambda e: self.reda_sau_pauza())
        self._m(r, _('Reia de la început (Shift K)'), lambda e: self.reda(False))
        self._m(r, _('Redă de la măsura aleasă până la final (I)'), lambda e: self.reda(True))
        r.AppendSeparator()
        self._m(r, _('Mai rar cu 5 la sută (Shift 1)'), lambda e: self.schimba_tempo(-5))
        self._m(r, _('Mai repede cu 5 la sută (Shift 2)'), lambda e: self.schimba_tempo(5))
        self._m(r, _('Tempoul scris în piesă (Shift 3)'), lambda e: self.schimba_tempo(0))
        self.m_bucla = r.AppendCheckItem(wx.ID_ANY, _('Redare în buclă\tCtrl+R'))
        self.Bind(wx.EVT_MENU, self.comuta_bucla, self.m_bucla)
        r.AppendSeparator()
        self.m_metronom = r.AppendCheckItem(wx.ID_ANY, _('Metronom\tCtrl+Shift+M'))
        self.m_metronom.Check(self.metronom)
        self.Bind(wx.EVT_MENU, lambda e: self.comuta_metronom(self.m_metronom.IsChecked()), self.m_metronom)
        self._m(r, _('Metronomul mai tare cu 1 la sută (Shift plus)'), lambda e: self.schimba_volum_metronom(1))
        self._m(r, _('Metronomul mai încet cu 1 la sută (Shift minus)'), lambda e: self.schimba_volum_metronom(-1))
        self._m(r, _('Metronomul mai tare cu 5 la sută (Control Shift plus)'), lambda e: self.schimba_volum_metronom(5))
        self._m(r, _('Metronomul mai încet cu 5 la sută (Control Shift minus)'), lambda e: self.schimba_volum_metronom(-5))
        self._m(r, _('Metronomul mai tare cu 5 la sută (Control Home)'), lambda e: self.schimba_volum_metronom(5))
        self._m(r, _('Metronomul mai încet cu 5 la sută (Control End)'), lambda e: self.schimba_volum_metronom(-5))
        mb.Append(r, _('&Redare'))
        a = wx.Menu()
        self._m(a, _('Scurtături\tF1'), lambda e: self.mesaj(_SCURTATURI_FILE() + '\n\n' + _('Filele: Control 1 Muzică, Control 2 Claviatura, Control 3 Partituri, Control 4 Scrie o partitură, Control 5 Exerciții de auz, Control 6 Setări. Partituri are patru subfile: În cuvinte, Braille, Player și Metronom; apasă Control 3 din nou ca să treci la următoarea (sau Control Tab).') + '\n\n' + _('Metronom (a patra subfilă din Partituri): un metronom de sine stătător. K sau spațiu îl pornesc și îl opresc; săgeata sus și jos schimbă tempoul cu 1, Page Up și Page Down cu 5; săgeata dreapta și stânga schimbă câți timpi are măsura (primul timp se aude mai tare); Home și End volumul; I spune tempoul, timpii și volumul.') + '\n\n' + _('Player (Control 3, a treia subfilă din Partituri): cântă toată piesa, de la prima măsură până la capăt. K pornește, pune pauză și continuă; L derulează înainte 5 secunde, J înapoi 5 secunde, ca pe YouTube; I spune minutul și secunda la care ești și măsura; Home o ia de la început; Escape oprește. Tempoul (Shift 1, 2, 3) și metronomul (Control Shift M, Shift plus și minus) merg și în player.') + ' ' + _('M alege ce auzi: ambele mâini, doar mâna dreaptă sau doar mâna stângă.') + '\n\n' + _('Muzică (Control 1): alegi un folder de pe calculator; fiecare folder din el e un loc la Tab. Acolo, săgeata stânga și dreapta trec prin folder și subfolderele lui; săgețile sus și jos trec prin fișiere și fiecare se aude imediat, fără să fie citit. Spațiu spune numele fișierului și al câtelea e. K pune pauză și continuă, Shift K o ia de la capăt, L înainte 5 secunde, J înapoi 5 secunde, I spune unde ești, R alege ce se întâmplă la sfârșit: repetă piesa, se oprește sau trece la următoarea. Escape oprește.') + ' ' + _('Control Home și Control End: volumul, mai tare și mai încet.') + '\n\n' + _('F2: ajutorul la taste. Cât e pornit, orice tastă apeși îți spune ce face în fila în care ești, fără s-o facă. F2 sau Escape ies.'), _('Scurtături')))
        self._m(a, _('Caută actualizări'), lambda e: self.verifica_actualizari(True))
        self._m(a, _('Despre'), lambda e: self.mesaj(_('{0}, versiunea {1}.\nCitește partituri în cuvinte și în Braille muzical.\nFolosește music21 pentru note, Braille și sunet; homr și Audiveris pentru recunoașterea PDF-urilor, comparate măsură cu măsură; MuseScore pentru fișierele .mscz.', NUME, VERSIUNE), _('Despre')))
        mb.Append(a, _('&Ajutor'))
        self.SetMenuBar(mb)

    def _m(self, meniu, text, fn):
        it = meniu.Append(wx.ID_ANY, text)
        self.Bind(wx.EVT_MENU, fn, it)
        return it

    def _interfata(self):
        p = wx.Panel(self)
        st = wx.BoxSizer(wx.VERTICAL)
        stg = wx.BoxSizer(wx.VERTICAL)
        stg.Add(wx.StaticText(p, label=_('&Măsuri')), 0, wx.ALL, 4)
        self.lista = wx.ListBox(p, style=wx.LB_EXTENDED, size=(230, -1), name=_('Măsuri'))
        stg.Add(self.lista, 1, wx.EXPAND | wx.ALL, 4)
        stg.Add(wx.StaticText(p, label=_('&Portative')), 0, wx.ALL, 4)
        self.portative = wx.Choice(p, name=_('Portative'))
        stg.Add(self.portative, 0, wx.EXPAND | wx.ALL, 4)

        box = wx.StaticBoxSizer(wx.VERTICAL, p, _('Opțiuni pentru textul în cuvinte'))
        sb = box.GetStaticBox()
        self.c_ritm = wx.CheckBox(sb, label=_('Cu &ritm (durata notelor)'))
        box.Add(self.c_ritm, 0, wx.ALL, 3)
        box.Add(wx.StaticText(sb, label=_('&Octava')), 0, wx.LEFT | wx.TOP, 3)
        self.c_octava = wx.Choice(sb, choices=[x[1] for x in OCTAVE], name=_('Octava'))
        box.Add(self.c_octava, 0, wx.EXPAND | wx.ALL, 3)
        self.c_scurt = wx.CheckBox(sb, label=_('Scriere &scurtă (do4 p, mi4 o)'))
        self.c_dig = wx.CheckBox(sb, label=_('Cu &digitație'))
        self.c_nuante = wx.CheckBox(sb, label=_('Cu &nuanțe, articulații și tempo'))
        self.c_voci = wx.CheckBox(sb, label=_('&Voci separate în aceeași mână'))
        for c in (self.c_scurt, self.c_dig, self.c_nuante, self.c_voci):
            box.Add(c, 0, wx.ALL, 3)
        stg.Add(box, 0, wx.EXPAND | wx.ALL, 4)

        self.carte = wx.Notebook(p, name=_('Rezultat'))
        # Partituri: o filă cu trei subfile (În cuvinte, Braille, Player)
        self.p_partituri = wx.Panel(self.carte)
        self.carte_p = wx.Notebook(self.p_partituri, name=_('Partituri'))
        _sp = wx.BoxSizer(wx.VERTICAL)
        _sp.Add(self.carte_p, 1, wx.EXPAND)
        self.p_partituri.SetSizer(_sp)
        pc = wx.Panel(self.carte_p)
        sc = wx.BoxSizer(wx.VERTICAL)
        sc.Add(wx.StaticText(pc, label=_('Textul în cuvinte')), 0, wx.ALL, 2)
        self.t_cuvinte = wx.TextCtrl(pc, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, name=_('Textul în cuvinte'))
        sc.Add(self.t_cuvinte, 1, wx.EXPAND | wx.ALL, 2)
        pc.SetSizer(sc)
        pb = wx.Panel(self.carte_p)
        sbz = wx.BoxSizer(wx.VERTICAL)
        sbz.Add(wx.StaticText(pb, label=_('Textul în Braille')), 0, wx.ALL, 2)
        self.t_braille = wx.TextCtrl(pb, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL, name=_('Textul în Braille'))
        self.t_braille.SetFont(wx.Font(16, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName='Segoe UI Symbol'))
        sbz.Add(self.t_braille, 1, wx.EXPAND | wx.ALL, 2)
        pb.SetSizer(sbz)
        pk = wx.Panel(self.carte)
        sk = wx.BoxSizer(wx.VERTICAL)
        sk.Add(wx.StaticText(pk, label=_('Claviatura')), 0, wx.ALL, 2)
        self.t_clav = wx.TextCtrl(pk, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_PROCESS_TAB | wx.TE_PROCESS_ENTER, name=_('Claviatura'))
        self.t_clav.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sk.Add(self.t_clav, 1, wx.EXPAND | wx.ALL, 2)
        pk.SetSizer(sk)
        self.p_cuvinte = pc
        self.carte_p.AddPage(pc, _('În cuvinte'))
        self.p_braille = pb
        self.carte_p.AddPage(pb, _('Braille'))
        self.p_player = PaginaPlayer(self.carte_p, self)
        self.carte_p.AddPage(self.p_player, _('Player'))
        self.p_metronom = PaginaMetronom(self.carte_p, self)
        self.carte_p.AddPage(self.p_metronom, _('Metronom'))
        self.p_fisiere = PaginaFisiere(self.carte, self)
        self.carte.AddPage(self.p_fisiere, _('Muzică'))
        self.p_clav = pk
        self.carte.AddPage(pk, _('Claviatura'))
        self.carte.AddPage(self.p_partituri, _('Partituri'))
        self._fila_scriere()
        self._fila_auz()
        # fila Setări (ultima): metronomul, instrumentul claviaturii, unde sunt programele de recunoaștere
        self.p_setari = ps = scrolled.ScrolledPanel(self.carte)
        ss = wx.BoxSizer(wx.VERTICAL)
        eticheta_limba = _('Limba')
        if eticheta_limba != 'Language':
            eticheta_limba += ' (Language)'
        ss.Add(wx.StaticText(ps, label=eticheta_limba), 0, wx.LEFT | wx.TOP, 6)
        self.s_limba = wx.Choice(ps, choices=[n for c, n in limba.LIMBI], name=eticheta_limba)
        self.s_limba.SetSelection([c for c, n in limba.LIMBI].index(limba.LIMBA))
        ss.Add(self.s_limba, 0, wx.ALL, 6)
        self.s_sunet = wx.CheckBox(ps, label=_('Melodie de celestă la pornire'))
        self.s_sunet.SetValue(bool(self.setari.get('sunet_pornire', True)))
        ss.Add(self.s_sunet, 0, wx.ALL, 6)
        self.s_sunet_iesire = wx.CheckBox(ps, label=_('Sunet de celestă la ieșire'))
        self.s_sunet_iesire.SetValue(bool(self.setari.get('sunet_iesire', True)))
        ss.Add(self.s_sunet_iesire, 0, wx.ALL, 6)
        self.s_metronom = wx.CheckBox(ps, label=_('Metronom pornit (cântă odată cu piesa, în tempoul ei)'))
        ss.Add(self.s_metronom, 0, wx.ALL, 6)
        ss.Add(wx.StaticText(ps, label=_('Volumul metronomului, în procente (0 – 100)')), 0, wx.LEFT | wx.TOP, 6)
        self.s_volum = wx.SpinCtrl(ps, min=0, max=100, initial=60, name=_('Volumul metronomului, în procente'))
        ss.Add(self.s_volum, 0, wx.ALL, 6)
        ss.Add(wx.StaticText(ps, label=_('Instrumentul claviaturii')), 0, wx.LEFT | wx.TOP, 6)
        # arbore: categoriile sunt „foldere”; spațiu le deschide și le închide, spațiu sau Enter pe un instrument îl alege
        self.s_instrument, self._noduri_instr = self._arbore_instrumente(ps, _('Instrumentul claviaturii'))
        ss.Add(self.s_instrument, 0, wx.EXPAND | wx.ALL, 6)
        ss.Add(wx.StaticText(ps, label=_('Clapa MIDI (cânți pe ea cu sunetele programului)')), 0, wx.LEFT | wx.TOP, 6)
        self.s_midi = wx.Choice(ps, name=_('Clapa MIDI'))
        ss.Add(self.s_midi, 0, wx.EXPAND | wx.ALL, 6)
        b_midi = wx.Button(ps, label=_('Caută din nou clapele MIDI'))
        b_midi.Bind(wx.EVT_BUTTON, lambda e: self._umple_midi(anunta=True))
        ss.Add(b_midi, 0, wx.ALL, 6)
        ss.Add(wx.StaticText(ps, label=_('Întârzierea sunetului')), 0, wx.LEFT | wx.TOP, 6)
        self._latente = ['mica', 'normala', 'sigura']
        self.s_latenta = wx.Choice(ps, name=_('Întârzierea sunetului'),
                                   choices=[_('Mică (se poate auzi un mic pârâit)'), _('Normală'), _('Mare (fără pârâit, și pe calculatoare încete)')])
        self.s_latenta.SetSelection(self._latente.index(self.setari.get('latenta', 'normala')) if self.setari.get('latenta') in self._latente else 1)
        ss.Add(self.s_latenta, 0, wx.ALL, 6)
        for cheie, text in (('audiveris', _('Unde e instalat Audiveris (pentru PDF și poze)...')),
                            ('musescore', _('Unde e instalat MuseScore (pentru fișiere MuseScore)...')),
                            ('homr', _('Unde e instalat homr (al doilea program de recunoaștere)...'))):
            b = wx.Button(ps, label=text)
            b.Bind(wx.EVT_BUTTON, lambda e, c=cheie: self.alege_program(c))
            ss.Add(b, 0, wx.ALL, 6)
        ps.SetSizer(ss)
        ps.SetupScrolling(scroll_x=False)
        self.carte.AddPage(ps, _('Setări'))
        self.s_limba.Bind(wx.EVT_CHOICE, self._schimba_limba)
        self.s_midi.Bind(wx.EVT_CHOICE, lambda e: self._alege_midi())
        self.s_latenta.Bind(wx.EVT_CHOICE, lambda e: self._alege_latenta())
        self._umple_midi()
        self.s_sunet.Bind(wx.EVT_CHECKBOX, self._sunet_pornire_schimbat)
        self.s_sunet_iesire.Bind(wx.EVT_CHECKBOX, self._sunet_iesire_schimbat)
        self.s_metronom.Bind(wx.EVT_CHECKBOX, lambda e: self.comuta_metronom(self.s_metronom.GetValue()))
        self.s_volum.Bind(wx.EVT_SPINCTRL, lambda e: self._volum_din_setari())
        self.s_volum.Bind(wx.EVT_TEXT, lambda e: self._volum_din_setari())
        self.s_instrument.Bind(wx.EVT_KEY_DOWN, lambda e: self._tasta_arbore(e, self.s_instrument, self._alege_din_arbore))
        self.s_instrument.Bind(wx.EVT_TREE_ITEM_ACTIVATED, lambda e: self._alege_din_arbore(e.GetItem()))
        self.t_clav.Bind(wx.EVT_KEY_UP, self._clav_ridica)
        self.t_clav.Bind(wx.EVT_SET_FOCUS, self._clav_intra)
        self.t_clav.Bind(wx.EVT_KILL_FOCUS, self._clav_iese)
        self._clav_text()
        self.t_cuvinte.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.t_cuvinte.SetValue(INDEMN)
        self.t_braille.SetValue(INDEMN)

        st.Add(stg, 0, wx.EXPAND)
        st2 = wx.BoxSizer(wx.HORIZONTAL)
        st2.Add(st, 0, wx.EXPAND)
        st2.Add(self.carte, 1, wx.EXPAND | wx.ALL, 4)
        p.SetSizer(st2)

        self.lista.Bind(wx.EVT_LISTBOX, lambda e: self.actualizeaza())
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.arata_sub(0))
        self.lista.Bind(wx.EVT_KEY_DOWN, self._tasta_lista)
        self.portative.Bind(wx.EVT_CHOICE, lambda e: self.actualizeaza())
        for c in (self.c_ritm, self.c_scurt, self.c_dig, self.c_nuante, self.c_voci):
            c.Bind(wx.EVT_CHECKBOX, lambda e: self.actualizeaza(salveaza=True))
        self.c_octava.Bind(wx.EVT_CHOICE, lambda e: self.actualizeaza(salveaza=True))
        self.carte.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, lambda e: (self.actualizeaza_braille(), e.Skip()))
        self.carte_p.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, lambda e: (self.actualizeaza_braille(), e.Skip()))

    def _tasta_lista(self, e):
        if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.arata_sub(0)
        else:
            e.Skip()

    def _aplica_setari(self):
        o = self.setari.get('optiuni', {})
        self.c_ritm.SetValue(o.get('ritm', True))
        self.c_octava.SetSelection([x[0] for x in OCTAVE].index(o.get('octava', 'numere')) if o.get('octava', 'numere') in [x[0] for x in OCTAVE] else 1)
        self.c_scurt.SetValue(o.get('scurt', False))
        self.c_dig.SetValue(o.get('digitatie', True))
        self.c_nuante.SetValue(o.get('nuante', True))
        # din 17 oct. 2026 vocile se spun implicit puse într-una (v2 = setarea a fost salvată după schimbare)
        self.c_voci.SetValue(bool(o.get('voci', False)) if o.get('v2') else False)

    def optiuni(self) -> cuvinte.Optiuni:
        return cuvinte.Optiuni(ritm=self.c_ritm.GetValue(), octava=OCTAVE[max(0, self.c_octava.GetSelection())][0], scurt=self.c_scurt.GetValue(),
                               digitatie=self.c_dig.GetValue(), nuante=self.c_nuante.GetValue(), voci=self.c_voci.GetValue())

    # ---------------- deschidere ----------------
    def cere_fisier(self, e=None):
        with wx.FileDialog(self, _('Deschide partitura'), defaultDir=self.setari.get('folder', ''), wildcard=FILTRU,
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as d:
            if d.ShowModal() == wx.ID_OK:
                self.deschide(d.GetPath())

    def _pagini(self, cale):
        try:
            return cuprins.numar_pagini(cale)
        except Exception:
            return 0

    # ---------------- cărți întregi: alegi piesa ----------------
    def deschide_carte(self, cale, brf=False):
        """Un PDF cu mai multe pagini: găsim unde începe fiecare piesă și te întrebăm ce deschizi."""
        self.SetStatusText(_('Caut piesele din carte. Prima dată poate dura un minut sau două; apoi se ține minte.'))
        self.t_cuvinte.SetValue(_('Caut piesele din carte (unde începe fiecare studiu sau piesă), te rog așteaptă.'))
        self.arata_sub(0)

        def lucru():
            try:
                c = cuprins.incarca_sau_gaseste(cale, progres=lambda m: wx.CallAfter(self.SetStatusText, m))
                wx.CallAfter(self._alege_din_carte, cale, c, brf)
            except Exception as ex:
                traceback.print_exc()
                wx.CallAfter(self._alege_din_carte, cale, None, brf, str(ex))
        threading.Thread(target=lucru, daemon=True).start()

    def _alege_din_carte(self, cale, c, brf, eroare=None):
        n = c['pagini'] if c else cuprins.numar_pagini(cale)
        piese = c['piese'] if c else []
        optiuni = [_('Toată cartea ({0} pagini)', n)] + [cuprins.eticheta(p) for p in piese] + [_('Alte pagini, le scriu eu...')]
        text = (_('Am găsit {0} piese în carte. Alege ce deschizi.', len(piese)) if piese else
                _('Nu am găsit sigur unde încep piesele. Poți deschide toată cartea sau scrie paginile.'))
        if c and c.get('probleme') and not c.get('verificat'):
            text += _(' Atenție: ') + ' '.join(c['probleme'][:3])
        if eroare:
            text += _(' (Eroare la căutarea pieselor: {0})', eroare)
        self.t_cuvinte.SetValue(INDEMN)
        d = wx.SingleChoiceDialog(self, text, _('Ce deschizi din carte?'), optiuni)
        if len(optiuni) > 2:
            d.SetSelection(1)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            self.SetStatusText(_('Nu am deschis nimic.'))
            return
        k = d.GetSelection()
        d.Destroy()
        baza_carte = os.path.splitext(os.path.basename(cale))[0]
        if k == 0:
            self.deschide(cale, brf=brf, fara_cuprins=True)
            return
        if k == len(optiuni) - 1:
            t = wx.TextEntryDialog(self, _('Ce pagini? De exemplu 3-4, sau 5 pentru o singură pagină. Cartea are {0} pagini.', n),
                                   _('Alte pagini'))
            ok = t.ShowModal() == wx.ID_OK
            val = t.GetValue()
            t.Destroy()
            if not ok:
                return
            pg = cuprins.citeste_pagini(val, n)
            if not pg:
                self.mesaj(_('Paginile nu sunt scrise bine. Scrie de exemplu 3-4. Cartea are {0} pagini.', n), _('Alte pagini'))
                return
            de_la, pana_la = pg
            nume = f'paginile {de_la}-{pana_la}' if de_la != pana_la else f'pagina {de_la}'   # nume de fișier: rămâne în română
            taie_sus = taie_jos = None
        else:
            p = piese[k - 1]
            de_la, pana_la, taie_sus, taie_jos = p['de_la'], p['pana_la'], p.get('taie_sus'), p.get('taie_jos')
            nume = p.get('nume') or f'Piesa {p["nr"]}'
        baza = f'{baza_carte} - {nume}'
        d_tmp = tempfile.mkdtemp(prefix='regatul-carte-')
        tmp = os.path.join(d_tmp, baza + '.pdf')
        try:
            cuprins.pregateste_pdf(cale, de_la, pana_la, tmp, taie_sus, taie_jos)
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(_('Nu am putut scoate paginile din carte. Eroare: {0}', ex), _('Ce deschizi din carte?'))
            shutil.rmtree(d_tmp, ignore_errors=True)
            return
        self.deschide(tmp, titlu=f'{baza_carte}, {nume}', brf=brf, baza=baza, folder=os.path.dirname(cale), original=cale,
                      dupa=lambda: shutil.rmtree(d_tmp, ignore_errors=True), fara_cuprins=True)

    def deschide(self, cale, pastreaza=True, titlu=None, dupa=None, brf=False, baza=None, folder=None, original=None,
                 fara_cuprins=False, piesa=None):
        """Deschide o partitură. pastreaza=False: nu se salvează nimic (pagini din aplicațiile editurilor);
        titlu: numele afișat; dupa: funcție chemată la final (de exemplu ștergerea pozei); brf: salvează și BRF în Documente\\Music Box\\<nume PDF>."""
        if self._ocupat_recunoastere:
            self.mesaj(_('Încă se recunoaște partitura de dinainte. Așteaptă să se termine.'), _('Ocupat'))
            if dupa:
                dupa()
            return
        e_imagine = os.path.splitext(cale)[1].lower() in partitura.FORMATE_IMAGINE
        if os.path.splitext(cale)[1].lower() in partitura.FORMATE_BRAILLE and piesa is None:
            # un fișier Braille cu mai multe piese (de ex. o culegere de solfegii): alegi piesa
            try:
                from nucleu import din_braille
                tt = din_braille.titluri(cale)
            except Exception:
                tt = []
            if len(tt) > 1:
                with wx.SingleChoiceDialog(self, _('Fișierul are {0} piese. Pe care o deschizi?', len(tt)),
                                           _('Alege piesa'), tt) as d:
                    if d.ShowModal() != wx.ID_OK:
                        return
                    piesa = d.GetSelection()
                    titlu = titlu or tt[piesa]
        if (not fara_cuprins and pastreaza and cale.lower().endswith('.pdf')
                and self._pagini(cale) > 2):
            self.deschide_carte(cale, brf=brf)
            return
        if pastreaza:
            self.setari['folder'] = os.path.dirname(cale)
            scrie_setari(self.setari)
        self.redare.opreste()
        self.SetStatusText(_('Se deschide ') + (titlu or os.path.basename(cale)) + '...')
        self.t_cuvinte.SetValue(_('Se recunoaște partitura cu două programe și se compară măsură cu măsură. Poate dura câteva minute; '
                                'te anunț când e gata.') if e_imagine else _('Se deschide partitura, te rog așteaptă.'))
        self.t_braille.SetValue('')
        self.arata_sub(0)
        self._ocupat = wx.BusyInfo(_('Se deschide partitura...'), self) if not e_imagine else None
        self._ocupat_recunoastere = e_imagine

        def lucru():
            cale_l, original_l, baza_l, d_rot = cale, original, baza, None
            try:
                # PDF scanat cu paginile culcate: lucrăm pe o copie cu paginile îndreptate
                if pastreaza and original is None and cale.lower().endswith('.pdf'):
                    rot = cuprins.rotatii(cale)
                    if any(rot):
                        wx.CallAfter(self.SetStatusText, _('Paginile sunt scanate culcate; le îndrept.'))
                        d_rot = tempfile.mkdtemp(prefix='regatul-drept-')
                        cale_l = os.path.join(d_rot, os.path.basename(cale))
                        cuprins.extrage_pagini(cale, 1, len(rot), cale_l)
                        original_l = cale
                        baza_l = baza or os.path.splitext(os.path.basename(cale))[0]
                P = partitura.incarca(cale_l, progres=lambda m: wx.CallAfter(self.SetStatusText, m), pastreaza=pastreaza,
                                      baza=baza_l, folder=folder, original=original_l, piesa=piesa)
                if titlu and P.scor.metadata is not None:
                    P.scor.metadata.title = titlu
                P.fara_salvare = not pastreaza
                fis_brf = None
                if brf:
                    sursa = original_l or cale
                    dir_brf = recunoastere.folder_rezultate(sursa)
                    os.makedirs(dir_brf, exist_ok=True)
                    fis_brf = os.path.join(dir_brf, recunoastere.nume_scurt(baza_l or os.path.splitext(os.path.basename(cale))[0], sursa) + '.brf')
                    txt = braille.din_scor(P.extrage(P.numere[0], P.numere[-1], list(range(len(P.portative)))))
                    with open(fis_brf, 'w', encoding='ascii', errors='replace', newline='') as f:
                        f.write(braille.la_brf(txt))
                wx.CallAfter(self._deschisa, P, None, fis_brf)
            except (partitura.EroarePartitura, recunoastere.LipsaProgram) as ex:
                wx.CallAfter(self._deschisa, None, str(ex))
            except Exception as ex:
                traceback.print_exc()
                wx.CallAfter(self._deschisa, None, _('Nu am putut deschide partitura. Eroare: {0}', ex))
            finally:
                if d_rot:
                    shutil.rmtree(d_rot, ignore_errors=True)
                if dupa:
                    dupa()
        threading.Thread(target=lucru, daemon=True).start()

    def _deschisa(self, P, eroare, fis_brf=None):
        self._ocupat = None
        recunoscuta = self._ocupat_recunoastere
        self._ocupat_recunoastere = False
        if recunoscuta:
            self.Raise()
            wx.Bell()
        if eroare:
            self.t_cuvinte.SetValue(eroare)
            self.SetStatusText(_('Partitura nu s-a deschis.'))
            self.mesaj(eroare, _('Nu s-a deschis'))
            return
        self.P = P
        self._midi_cache = (None, None, None, [])
        self.SetTitle(f'{P.titlu} – {NUME}')
        self.lista.Set([_('Despre piesă'), _('Toată piesa')] + [(_('Anacruza') if n == 0 else _('Măsura {0}', n)) + (_(', de verificat') if n in P.nesigure else '')
                                                          for n in P.numere])
        self.portative.Set([_('Toate portativele')] + [p.nume for p in P.portative])
        self.portative.SetSelection(0)
        self.lista.SetSelection(0)
        self.actualizeaza()
        self.SetStatusText(_('Deschisă: {0}. {1} măsuri.', P.titlu, len(P.numere)))
        self.p_player.reimprospateaza()
        self.p_player.pregateste()
        self.lista.SetFocus()
        if fis_brf:
            self.mesaj(_('Gata. Fișierul Braille e salvat în Documente, în folderul Music Box, la {0}, cu numele {1}.\n\n', os.path.basename(os.path.dirname(fis_brf)), os.path.basename(fis_brf)) +
                       (_('Măsuri de verificat: {0} (', len(P.nesigure)) + ', '.join(str(n) for n in P.nesigure) + _('). '
                        'Lista lor cu motivele e în același folder, în fișierul „de verificat”.') if P.nesigure
                        else _('Toate măsurile au fost citite la fel de ambele programe.')), _('Din PDF în Braille'))
        elif recunoscuta:
            self.mesaj(P.descriere_generala(), _('Partitura e gata'))

    # ---------------- afișare ----------------
    def selectie(self):
        """(prima, ultima, portative) pentru ce e selectat; None dacă e „Despre piesă”."""
        if not self.P:
            return None
        sel = list(self.lista.GetSelections())
        if not sel or sel == [0]:
            return None
        k = self.portative.GetSelection()
        port = list(range(len(self.P.portative))) if k <= 0 else [k - 1]
        if 1 in sel:
            return self.P.numere[0], self.P.numere[-1], port
        nr = [self.P.numere[i - 2] for i in sel if i >= 2]
        return min(nr), max(nr), port

    def actualizeaza(self, salveaza=False):
        if salveaza:
            o = self.optiuni()
            self.setari['optiuni'] = {**o.__dict__, 'v2': True}
            scrie_setari(self.setari)
        if not self.P:
            return
        s = self.selectie()
        if s is None:
            self.t_cuvinte.SetValue(self.P.descriere_generala())
        else:
            try:
                self.t_cuvinte.SetValue(self.P.descrie(s[0], s[1], s[2], self.optiuni()) or _('Nicio notă aici.'))
            except Exception as ex:
                traceback.print_exc()
                self.t_cuvinte.SetValue(_('Nu am putut descrie măsurile acestea. Eroare: {0}', ex))
        self.t_cuvinte.SetInsertionPoint(0)
        self.t_braille.SetValue('')
        self.actualizeaza_braille()

    def actualizeaza_braille(self):
        if not self.P or self._pagina() is not self.p_braille or self.t_braille.GetValue():
            return
        s = self.selectie()
        if s is None:
            s = (self.P.numere[0], self.P.numere[-1], list(range(len(self.P.portative))))
        self._braille_id += 1
        nr = self._braille_id
        self.t_braille.SetValue(_('Se pregătește Braille...'))

        def lucru():
            try:
                txt = braille.din_scor(self.P.extrage(*s), final=s[1] == self.P.numere[-1])
            except Exception as ex:
                traceback.print_exc()
                txt = _('Nu am putut face Braille pentru selecția aceasta. Eroare: {0}', ex)
            wx.CallAfter(self._braille_gata, nr, txt)
        threading.Thread(target=lucru, daemon=True).start()

    def _braille_gata(self, nr, txt):
        if nr == self._braille_id:
            self.t_braille.SetValue(txt)
            self.t_braille.SetInsertionPoint(0)

    def _pagina(self):
        """Fila deschisă; la Partituri, subfila deschisă (În cuvinte, Braille sau Player)."""
        p = self.carte.GetCurrentPage()
        return self.carte_p.GetCurrentPage() if p is self.p_partituri else p

    def arata(self, pagina, ciclu=False):
        """Filele: 0 Muzică, 1 Claviatura, 2 Partituri, 3 Scrie, 4 Exerciții de auz, 5 Setări.
        ciclu: Control 3 apăsat când ești deja în Partituri trece la subfila următoare."""
        if pagina == 2:
            k = self.carte_p.GetSelection()
            if ciclu and self.carte.GetCurrentPage() is self.p_partituri:
                k = (k + 1) % self.carte_p.GetPageCount()
            self.arata_sub(max(0, k))
            return
        self.carte.SetSelection(pagina)
        {0: self.p_fisiere.de_focus(), 1: self.t_clav, 3: self.w_lista, 4: self.a_ex, 5: self.s_limba}[pagina].SetFocus()

    def arata_sub(self, k):
        """Partituri: 0 În cuvinte, 1 Braille, 2 Player, 3 Metronom."""
        self.carte.SetSelection(self.carte.FindPage(self.p_partituri))
        self.carte_p.SetSelection(k)
        (self.t_cuvinte, self.t_braille, self.p_player.t, self.p_metronom.t)[k].SetFocus()
        if k == 1:
            self.actualizeaza_braille()

    def muta(self, pas):
        if not self.P:
            return
        sel = list(self.lista.GetSelections())
        cur = max(sel) if pas > 0 and sel else (min(sel) if sel else 1)
        nou = min(max(2, cur + pas if cur >= 2 else 2), self.lista.GetCount() - 1)
        for i in sel:
            self.lista.Deselect(i)
        self.lista.SetSelection(nou)
        self.lista.EnsureVisible(nou)
        self.actualizeaza()
        # cursorul rămâne unde e; NVDA spune doar măsura
        if self._pagina() is self.p_braille:
            self.actualizeaza_braille()
        voce.spune(self.lista.GetString(nou), intrerupe=True)
        if self.redare.stare == 'canta':
            self.reda(False)             # se cânta: cântă de acum măsura nouă (cerut de Răzvan)

    def mergi_la(self, e=None):
        if not self.P:
            return
        d = wx.TextEntryDialog(self, _('Numărul măsurii (sau două numere, de exemplu 5-8):'), _('Mergi la măsura'))
        if d.ShowModal() == wx.ID_OK:
            t = d.GetValue().replace(' ', '')
            try:
                parti = [int(x) for x in t.split('-') if x]
                a, b = parti[0], parti[-1]
                for i in self.lista.GetSelections():
                    self.lista.Deselect(i)
                gasit = False
                for idx, n in enumerate(self.P.numere):
                    if min(a, b) <= n <= max(a, b):
                        self.lista.SetSelection(idx + 2); gasit = True
                if not gasit:
                    raise ValueError
                self.actualizeaza()
                self.arata_sub(max(0, self.carte_p.GetSelection()))
            except Exception:
                self.mesaj(_('Nu există măsura aceasta.'), _('Mergi la măsura'))
        d.Destroy()

    def la_nesigura(self, pas):
        if not self.P:
            return
        if not self.P.nesigure:
            self.SetStatusText(_('Nu există măsuri de verificat.'))
            wx.Bell()
            return
        sel = list(self.lista.GetSelections())
        cur = (max(sel) if sel else 1) if pas > 0 else (min(sel) if sel else self.lista.GetCount())
        idx = range(cur + 1, self.lista.GetCount()) if pas > 0 else range(cur - 1, 1, -1)
        for i in idx:
            if self.P.numere[i - 2] in self.P.nesigure:
                for j in sel:
                    self.lista.Deselect(j)
                self.lista.SetSelection(i)
                self.lista.EnsureVisible(i)
                self.actualizeaza()
                self.arata_sub(0)
                return
        self.SetStatusText(_('Nu mai sunt măsuri de verificat în direcția asta.'))
        wx.Bell()

    # ---------------- redare cu sunet ----------------
    def reda(self, pana_la_final):
        if not self.P:
            return
        s = self.selectie() or (self.P.numere[0], self.P.numere[-1], self._portative_alese())
        self._sel_k = self._selectia_k()
        prima, ultima, port = s
        if pana_la_final:
            ultima = self.P.numere[-1]
        try:
            sel = (id(self.P), prima, ultima, tuple(port))
            self._porneste(sel)
            unde = _('măsura {0}', prima) if prima == ultima else _('măsurile {0}-{1}', prima, ultima)
            self.SetStatusText(_('Se cântă {0}, tempo {1} la sută', unde, self.procent) + (_(', în buclă.') if self.redare.bucla else '.'))
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(_('Nu am putut reda. Eroare: {0}', ex), _('Redare'))

    def _porneste(self, sel, de_la_ms=0, in_pauza=False):
        """Cântă selecția la tempoul de acum. MIDI-ul de bază se face o singură dată pentru o selecție."""
        if self.player_audio.stare == 'canta':
            self.player_audio.pauza_continua()       # playerul cu înregistrare tace cât cânți din fila 1
        if self.p_fisiere.melodie.stare == 'canta':
            self.p_fisiere.melodie.pauza_continua()
        self._midi_pentru(sel)
        self.sint.elibereaza()               # la sintetizatorul Windows: îl folosește acum redarea piesei
        date = self._midi_cache[1]
        metronom = self.volum_metronom if self.metronom else 0
        if metronom:
            date = redare.cu_metronom(date, self._midi_cache[2], metronom)
        date = redare.schimba_tempo_midi(date, self.procent)
        self.redare.bucla = self.m_bucla.IsChecked()
        self.redare.canta(redare.scrie_temporar(date), de_la_ms, in_pauza)
        self._redat = (sel, self.procent, metronom)
        # unde începe fiecare măsură în ce se cântă (pentru J și L în timpul redării, ca la un player)
        try:
            masuri = self._midi_cache[3]
            self._harta = list(zip(redare.milisecunde(date, [q for q, _n in masuri]), [n for _q, n in masuri]))
        except Exception:
            self._harta = []

    def _midi_pentru(self, sel):
        """(MIDI la 100%, bătăile, măsurile) pentru selecție, făcute o singură dată."""
        if self._midi_cache[0] != sel:
            _x, prima, ultima, port = sel
            bucata = self.P.extrage(prima, ultima, list(port))
            if (prima, ultima) != (self.P.numere[0], self.P.numere[-1]):
                bucata = redare.fara_repetitii(bucata)      # doar o parte aleasă: se cântă exact ce e ales, o dată, în ordinea scrisă
            try:
                batai = redare.batai(bucata)
            except Exception:
                traceback.print_exc()
                batai = []
            try:
                masuri = redare.masuri(bucata)
            except Exception:
                traceback.print_exc()
                masuri = []
            self._midi_cache = (sel, redare.midi_octeti(bucata), batai, masuri)
        return self._midi_cache[1:]

    def _portative_alese(self):
        k = self.portative.GetSelection()
        return list(range(len(self.P.portative))) if k <= 0 else [k - 1]

    def _selectia_k(self):
        """Ce e ales acum (măsurile și portativele), ca să știm dacă s-a schimbat de la ultimul K."""
        if not self.P:
            return None
        return (id(self.P), tuple(self.lista.GetSelections()), self.portative.GetSelection())

    def reda_sau_pauza(self):
        """K: dacă nu se cântă nimic, redă selecția; altfel oprește sau continuă de unde a rămas.
        Dacă între timp ai ales altă măsură, K o ia de la capăt, de la măsura aleasă (cerut de Răzvan)."""
        if not self.redare.terminat() and getattr(self, '_sel_k', None) != self._selectia_k():
            self.redare.opreste()
            self.reda(False)
            return
        if self.redare.terminat():
            # s-a terminat (sau nu se cântă nimic): K o ia de la începutul selecției, ca Shift K
            self.redare.opreste()
            self.reda(False)
        else:
            self.pauza()

    def pauza(self, e=None):
        try:
            st = self.redare.pauza_continua()
            self.SetStatusText({'pauza': _('Pauză.'), 'canta': _('Continuă.'), 'oprit': _('Nu se cântă nimic.')}[st])
        except Exception as ex:
            self.SetStatusText(_('Eroare la pauză: {0}', ex))

    def opreste(self, e=None):
        self.redare.opreste()
        self.SetStatusText(_('Oprit.'))

    def schimba_tempo(self, pas):
        vechi = self.procent
        self.procent = 100 if pas == 0 else min(200, max(20, self.procent + pas))
        if pas and self.procent == vechi:
            text = (_('Tempoul e deja cel mai rar, {0} la sută.', self.procent) if pas < 0 else
                    _('Tempoul e deja cel mai repede, {0} la sută.', self.procent))
        else:
            text = _('Tempo {0} la sută.', self.procent)
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)
        self._amana_aplicarea()

    def comuta_metronom(self, pornit=None):
        self.metronom = (not self.metronom) if pornit is None else bool(pornit)
        self.m_metronom.Check(self.metronom)
        self._sincronizeaza_setari()
        text = _('Metronom pornit.') if self.metronom else _('Metronom oprit.')
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)
        self._amana_aplicarea()

    def schimba_volum_metronom(self, pas):
        vechi = self.volum_metronom
        self.volum_metronom = min(100, max(0, self.volum_metronom + pas))
        if self.volum_metronom == vechi:
            text = (_('Metronomul e deja cel mai tare, {0} la sută.', self.volum_metronom) if pas > 0 else
                    _('Metronomul e deja cel mai încet, {0} la sută.', self.volum_metronom))
        else:
            text = _('Metronom {0} la sută.', self.volum_metronom)
        self._sincronizeaza_setari()
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)
        self._amana_aplicarea()

    def _sincronizeaza_setari(self):
        """Fila Setări arată mereu ce e acum (și după scurtături)."""
        self.s_metronom.SetValue(self.metronom)
        if self.s_volum.GetValue() != self.volum_metronom:
            self.s_volum.SetValue(self.volum_metronom)
        self._selecteaza_in_arbore(self.s_instrument, self._noduri_instr, self.instrument)

    def _sunet_pornire_schimbat(self, e=None):
        self.setari['sunet_pornire'] = self.s_sunet.GetValue()
        scrie_setari(self.setari)

    def _schimba_limba(self, e=None):
        noua = limba.LIMBI[max(0, self.s_limba.GetSelection())][0]
        if noua == limba.LIMBA:
            return
        self.setari['limba'] = noua
        scrie_setari(self.setari)
        veche = limba.LIMBA
        limba.seteaza(noua)             # întrebarea apare deja în limba nouă
        intrebare, titlu = _('Limba se schimbă după repornirea programului. Repornesc acum?'), _('Limba')
        limba.seteaza(veche)
        if wx.MessageBox(intrebare, titlu, wx.YES_NO | wx.YES_DEFAULT, self) == wx.YES:
            self._reporneste()

    def _reporneste(self):
        try:
            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable], close_fds=True)
            else:
                subprocess.Popen([sys.executable, os.path.abspath(__file__)], close_fds=True)
        except Exception as ex:
            self.mesaj(str(ex), _('Limba'))
            return
        self.Close()

    def cutie_muzicala(self):
        """La pornire: o melodie scurtă (cam 3 secunde) de celestă; dacă nu merge, cutia muzicală din sintetizatorul MIDI."""
        if not self.setari.get('sunet_pornire', True) or '--actualizat' in sys.argv:
            return
        if sunet_pornire.canta():          # celesta înregistrată (sintetizată), sună mai frumos decât MIDI
            return
        try:
            self.sint.deschide()
        except Exception:
            return

        def canta():
            claviatura.melodie_cutie(self.sint)
            if wx.Window.FindFocus() is not self.t_clav:
                wx.CallAfter(self._inchide_sint_daca_liber)
        threading.Thread(target=canta, daemon=True).start()

    def _preincarca_sunete(self):
        """Banca de sunete (32 MB) se încarcă în fundal, ca prima notă din claviatură să nu întârzie."""
        if self.sint.exclusiv:
            return

        def lucru():
            try:
                self.sint.pregateste(True)
            except Exception:
                traceback.print_exc()
            wx.CallAfter(self._porneste_midi)
        threading.Thread(target=lucru, daemon=True).start()

    # ---------------- clapa MIDI și întârzierea ----------------
    def _umple_midi(self, anunta=False):
        nume = midi_in.dispozitive()
        self._midi_nume = nume
        self.s_midi.Set([_('Fără clapă MIDI')] + nume)
        dorit = self.setari.get('midi_clapa')          # None = prima găsită; '' = fără
        if self.midi.deschisa() and self.midi.nume in nume:
            self.s_midi.SetSelection(nume.index(self.midi.nume) + 1)
        elif dorit is None and nume:
            self.s_midi.SetSelection(1)
        elif dorit in nume:
            self.s_midi.SetSelection(nume.index(dorit) + 1)
        else:
            self.s_midi.SetSelection(0)
        if anunta:
            text = _('Clape MIDI găsite: {0}.', len(nume)) if nume else _('Nu e legată nicio clapă MIDI.')
            self.SetStatusText(text)
            voce.spune(text, intrerupe=True)
            self._porneste_midi()

    def _porneste_midi(self):
        """Deschide clapa MIDI aleasă (sau prima, dacă nu ai ales), după ce sunetele sunt gata."""
        k = self.s_midi.GetSelection()
        if k <= 0 or k - 1 >= len(self._midi_nume):
            self.midi.inchide()
            return
        nume = self._midi_nume[k - 1]
        if self.midi.deschisa() and self.midi.nume == nume:
            return
        try:
            self.sint.deschide()
        except Exception as ex:
            self.SetStatusText(str(ex))
            return
        if self.midi.deschide(nume):
            self.SetStatusText(_('Clapa MIDI: {0}.', nume))
        else:
            self.SetStatusText(_('Clapa MIDI {0} nu s-a putut deschide. Poate o folosește alt program.', nume))

    def _alege_midi(self):
        k = self.s_midi.GetSelection()
        self.setari['midi_clapa'] = '' if k <= 0 else self._midi_nume[k - 1]
        scrie_setari(self.setari)
        self._porneste_midi()
        if k <= 0:
            voce.spune(_('Fără clapă MIDI.'), intrerupe=True)
        elif self.midi.deschisa():
            voce.spune(_('Clapa MIDI: {0}.', self.midi.nume), intrerupe=True)

    def _alege_latenta(self):
        lat = self._latente[max(0, self.s_latenta.GetSelection())]
        self.setari['latenta'] = lat
        scrie_setari(self.setari)
        if hasattr(self.sint, 'seteaza_latenta'):
            try:
                self.sint.seteaza_latenta(lat)
            except Exception as ex:
                self.SetStatusText(str(ex))

    def _inchide_sint_daca_liber(self):
        if wx.Window.FindFocus() is not self.t_clav and self._pagina() is not self.p_auz:
            self.sint.elibereaza()

    def _volum_din_setari(self):
        v = self.s_volum.GetValue()
        if v != self.volum_metronom:
            self.volum_metronom = v
            self._amana_aplicarea()

    def _amana_aplicarea(self):
        # se aplică după o pauză scurtă: la mai multe apăsări la rând, sunetul se schimbă o singură dată
        if self._tempo_amanat:
            self._tempo_amanat.Stop()
        self._tempo_amanat = wx.CallLater(250, self._aplica_tempo)

    def _aplica_tempo(self):
        """Salvează tempoul și metronomul; dacă se cântă, continuă din același loc al muzicii cu noile setări."""
        self._tempo_amanat = None
        self.setari['tempo'] = self.procent
        self.setari['metronom'] = self.metronom
        self.setari['metronom_volum'] = self.volum_metronom
        scrie_setari(self.setari)
        self.p_player.aplica()                   # playerul cu înregistrare: tempoul și metronomul se schimbă pe loc
        metronom = self.volum_metronom if self.metronom else 0
        if self.redare.stare in ('canta', 'pauza') and self._redat and self._redat[1:] != (self.procent, metronom):
            sel, vechi, _x = self._redat
            # același loc din muzică: la tempo nou, aceeași notă cade la alt moment
            poz = self.redare.pozitie() * vechi / self.procent
            try:
                self._porneste(sel, poz, in_pauza=(self.redare.stare == 'pauza'))
            except Exception as ex:
                traceback.print_exc()
                self.SetStatusText(_('Nu am putut schimba tempoul. Eroare: {0}', ex))

    # ---------------- scrie o partitură ----------------
    def _fila_scriere(self):
        self.p_scriere = pw = scrolled.ScrolledPanel(self.carte)
        sw = wx.BoxSizer(wx.VERTICAL)

        def eticheta(text):
            sw.Add(wx.StaticText(pw, label=text), 0, wx.LEFT | wx.TOP, 4)

        eticheta(_('Partiturile mele (săgeți sus și jos: alegi; Control S: salvezi)'))
        self.w_lista = wx.ListBox(pw, name=_('Partiturile mele'), size=(-1, 110))
        sw.Add(self.w_lista, 0, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Titlu'))
        self.w_titlu = wx.TextCtrl(pw, name=_('Titlu'))
        sw.Add(self.w_titlu, 0, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Compozitor'))
        self.w_comp = wx.TextCtrl(pw, name=_('Compozitor'))
        sw.Add(self.w_comp, 0, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Măsura'))
        self.w_masura = wx.Choice(pw, choices=scriere.MASURI, name=_('Măsura'))
        sw.Add(self.w_masura, 0, wx.ALL, 3)
        eticheta(_('Tonalitatea (armura)'))
        self.w_ton = wx.Choice(pw, choices=[t[1] for t in scriere.TONALITATI], name=_('Tonalitatea'))
        sw.Add(self.w_ton, 0, wx.ALL, 3)
        eticheta(_('Tempo, pătrimi pe minut (0 = fără tempo)'))
        self.w_tempo = wx.SpinCtrl(pw, min=0, max=300, initial=0, name=_('Tempo, pătrimi pe minut'))
        sw.Add(self.w_tempo, 0, wx.ALL, 3)
        self.w_ana = wx.CheckBox(pw, label=_('Prima măsură e anacruză'))
        sw.Add(self.w_ana, 0, wx.ALL, 3)
        eticheta(_('Mâna dreaptă, câte o măsură pe rând'))
        self.w_dr = wx.TextCtrl(pw, style=wx.TE_MULTILINE | wx.TE_RICH2, size=(-1, 110), name=_('Mâna dreaptă, câte o măsură pe rând'))
        sw.Add(self.w_dr, 1, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Mâna stângă, câte o măsură pe rând (gol = doar mâna dreaptă)'))
        self.w_st = wx.TextCtrl(pw, style=wx.TE_MULTILINE | wx.TE_RICH2, size=(-1, 110), name=_('Mâna stângă, câte o măsură pe rând'))
        sw.Add(self.w_st, 1, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Versuri: cuvintele prin spații, silabele prin cratimă (Ma-mă dra-gă); câte o silabă pe fiecare notă a mâinii drepte'))
        self.w_vers = wx.TextCtrl(pw, style=wx.TE_MULTILINE | wx.TE_RICH2, size=(-1, 70), name=_('Versuri'))
        sw.Add(self.w_vers, 0, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Sunetul partiturii (spațiu deschide o categorie, Enter alege)'))
        self.w_instr, self._noduri_scriere = self._arbore_instrumente(pw, _('Sunetul partiturii'))
        sw.Add(self.w_instr, 0, wx.EXPAND | wx.ALL, 3)
        rand = wx.WrapSizer()
        for text, fn in ((_('Verifică'), self.scriere_verifica),
                         (_('Ascultă tot (Control Shift Enter)'), lambda e: self.scriere_asculta(False)),
                         (_('Deschide pentru citit (În cuvinte, Braille, redare)'), self.scriere_deschide),
                         (_('Salvează ca MusicXML...'), lambda e: self.scriere_salveaza(False)),
                         (_('Salvează ca BRF...'), lambda e: self.scriere_salveaza(True)),
                         (_('Cum se scrie'), lambda e: self.mesaj(scriere.AJUTOR.strip(), _('Cum se scrie'))),
                         (_('Partitură nouă'), self.scriere_noua)):
            b = wx.Button(pw, label=text)
            b.Bind(wx.EVT_BUTTON, fn)
            rand.Add(b, 0, wx.ALL, 3)
        sw.Add(rand, 0, wx.EXPAND)
        pw.SetSizer(sw)
        pw.SetupScrolling(scroll_x=False)
        self.carte.AddPage(pw, _('Scrie o partitură'))
        self._ciorna_amanata = None
        self._w_instrument = (0, 0)
        self._scriere_incarca_ciorna()
        self.w_lista.Bind(wx.EVT_LISTBOX, lambda e: self._scriere_alege_din_lista())
        self.w_instr.Bind(wx.EVT_TREE_ITEM_ACTIVATED, lambda e: self._alege_sunet_scriere(e.GetItem()))
        for c in (self.w_titlu, self.w_comp, self.w_dr, self.w_st, self.w_vers):
            c.Bind(wx.EVT_TEXT, self._ciorna_schimbata)
        for c in (self.w_masura, self.w_ton):
            c.Bind(wx.EVT_CHOICE, self._ciorna_schimbata)
        self.w_tempo.Bind(wx.EVT_SPINCTRL, self._ciorna_schimbata)
        self.w_ana.Bind(wx.EVT_CHECKBOX, self._ciorna_schimbata)

    _FIS_CIORNA = os.path.join(DIR_SETARI, 'ciorna-partitura.json')

    def _scriere_date(self):
        return {'titlu': self.w_titlu.GetValue(), 'compozitor': self.w_comp.GetValue(),
                'masura': scriere.MASURI[max(0, self.w_masura.GetSelection())],
                'alteratii': scriere.TONALITATI[max(0, self.w_ton.GetSelection())][0],
                'tempo': self.w_tempo.GetValue(), 'anacruza': self.w_ana.GetValue(),
                'dreapta': self.w_dr.GetValue(), 'stanga': self.w_st.GetValue(), 'versuri': self.w_vers.GetValue(),
                'instrument': list(self._w_instrument)}

    def _scriere_pune(self, d):
        self.w_titlu.ChangeValue(d.get('titlu', ''))
        self.w_comp.ChangeValue(d.get('compozitor', ''))
        m = d.get('masura', '4/4')
        self.w_masura.SetSelection(scriere.MASURI.index(m) if m in scriere.MASURI else 0)
        alt = [t[0] for t in scriere.TONALITATI]
        self.w_ton.SetSelection(alt.index(d.get('alteratii', 0)) if d.get('alteratii', 0) in alt else 0)
        self.w_tempo.SetValue(int(d.get('tempo', 0)))
        self.w_ana.SetValue(bool(d.get('anacruza', False)))
        self.w_dr.ChangeValue(d.get('dreapta', ''))
        self.w_st.ChangeValue(d.get('stanga', ''))
        self.w_vers.ChangeValue(d.get('versuri', ''))
        self._w_instrument = tuple(d.get('instrument', (0, 0)))
        progs = [tuple(x[2]) for x in self.instrumente]
        if self._w_instrument in progs:
            self._selecteaza_in_arbore(self.w_instr, self._noduri_scriere, progs.index(self._w_instrument))

    _DIR_PARTITURI = os.path.join(DIR_SETARI, 'Partiturile mele')

    def _scriere_fisiere(self):
        """Partiturile mele: fișierele .json din %APPDATA%\\Music Box\\Partiturile mele, cele mai noi întâi."""
        try:
            n = [f[:-5] for f in os.listdir(self._DIR_PARTITURI) if f.endswith('.json')]
        except OSError:
            n = []
        return sorted(n, reverse=True)

    def _scriere_citeste(self, id_):
        try:
            with open(os.path.join(self._DIR_PARTITURI, id_ + '.json'), encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _scriere_id_nou(self):
        return time.strftime('%Y%m%d-%H%M%S') + f'-{int(time.time() * 1000) % 1000:03d}'

    def _scriere_reface_lista(self):
        self._ids = self._scriere_fisiere()
        nume = []
        for i in self._ids:
            d = self._scriere_citeste(i) if i != self._curenta else self._scriere_date()
            nume.append((d.get('titlu') or '').strip() or _('Fără titlu'))
        self.w_lista.Set(nume)
        if self._curenta in self._ids:
            self.w_lista.SetSelection(self._ids.index(self._curenta))

    def _scriere_incarca_ciorna(self):
        os.makedirs(self._DIR_PARTITURI, exist_ok=True)
        ids = self._scriere_fisiere()
        if not ids:
            # prima dată: ciorna veche devine prima partitură din listă
            try:
                with open(self._FIS_CIORNA, encoding='utf-8') as f:
                    d = json.load(f)
            except Exception:
                d = {}
            id_ = self._scriere_id_nou()
            with open(os.path.join(self._DIR_PARTITURI, id_ + '.json'), 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            ids = [id_]
        cur = self.setari.get('scriere_curenta')
        self._curenta = cur if cur in ids else ids[0]
        self._scriere_pune(self._scriere_citeste(self._curenta))
        self._scriere_reface_lista()

    def _scriere_alege_din_lista(self):
        k = self.w_lista.GetSelection()
        if k < 0 or k >= len(self._ids) or self._ids[k] == self._curenta:
            return
        self._salveaza_ciorna()
        self._curenta = self._ids[k]
        self.setari['scriere_curenta'] = self._curenta
        scrie_setari(self.setari)
        self._scriere_pune(self._scriere_citeste(self._curenta))

    def _ciorna_schimbata(self, e=None):
        # ce scrii se păstrează singur (și după ce închizi programul), la o secundă după ultima tastă
        if self._ciorna_amanata:
            self._ciorna_amanata.Stop()
        self._ciorna_amanata = wx.CallLater(1000, self._salveaza_ciorna)
        if e:
            e.Skip()

    def _salveaza_ciorna(self, spune=False):
        """Partitura la care lucrezi se scrie în Partiturile mele (singură, la o secundă după ce te oprești,
        și cu Control S)."""
        if self._ciorna_amanata:
            self._ciorna_amanata.Stop()
        self._ciorna_amanata = None
        try:
            os.makedirs(self._DIR_PARTITURI, exist_ok=True)
            with open(os.path.join(self._DIR_PARTITURI, self._curenta + '.json'), 'w', encoding='utf-8') as f:
                json.dump(self._scriere_date(), f, ensure_ascii=False, indent=1)
            k = self._ids.index(self._curenta) if self._curenta in getattr(self, '_ids', []) else -1
            nume = self.w_titlu.GetValue().strip() or _('Fără titlu')
            if k >= 0 and self.w_lista.GetString(k) != nume:
                self.w_lista.SetString(k, nume)
            if spune:
                voce.spune(_('Salvat: {0}.', nume), intrerupe=True)
        except Exception as ex:
            if spune:
                voce.spune(_('Nu am putut salva. Eroare: {0}', ex), intrerupe=True)

    def _scriere_scor(self, arata_erori=True):
        """(scor, probleme) sau (None, None) dacă textul are greșeli care nu se pot citi."""
        d = self._scriere_date()
        try:
            return scriere.construieste(d['dreapta'], d['stanga'], d['titlu'], d['compozitor'], d['masura'],
                                        d['alteratii'], d['tempo'], d['anacruza'], d.get('versuri', ''))
        except scriere.EroareScriere as ex:
            if arata_erori:
                self.mesaj(str(ex), _('Greșeală în scriere'))
            return None, None
        except Exception as ex:
            traceback.print_exc()
            if arata_erori:
                self.mesaj(_('Nu am putut face partitura. Eroare: {0}', ex), _('Greșeală în scriere'))
            return None, None

    def scriere_verifica(self, e=None):
        scor, probleme = self._scriere_scor()
        if scor is None:
            return
        n = len(scor.parts[0].getElementsByClass('Measure'))
        if probleme:
            self.mesaj('\n'.join(probleme), _('Verificare'))
        else:
            self.mesaj(_('Totul e în regulă: {0} măsuri, fiecare cu timpii potriviți.', n), _('Verificare'))

    def _masura_cursorului(self):
        """(numărul măsurii, mâna) pentru rândul pe care e cursorul."""
        c = wx.Window.FindFocus()
        if c not in (self.w_dr, self.w_st):
            c = self.w_dr
        ok, x, y = c.PositionToXY(c.GetInsertionPoint())
        rand = y if ok else c.GetValue()[:c.GetInsertionPoint()].count('\n')
        nr = rand if self.w_ana.GetValue() else rand + 1
        return nr, (_('mâna dreaptă') if c is self.w_dr else _('mâna stângă'))

    def scriere_spune_masura(self):
        nr, mana = self._masura_cursorului()
        text = (_('Anacruza') if nr == 0 else _('Măsura {0}', nr)) + f', {mana}.'
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)

    def scriere_asculta(self, masura=False):
        scor, _x = self._scriere_scor()
        if scor is None:
            return
        try:
            bucata = scor
            if masura:
                nr, _x = self._masura_cursorului()
                P = partitura.Partitura(scor, 'scriere.musicxml')
                if nr not in P.numere:
                    voce.spune(_('Măsura asta e goală.'), intrerupe=True)
                    return
                bucata = P.extrage(nr, nr, list(range(len(P.portative))))
            date = redare.cu_program(redare.midi_octeti(bucata), self._w_instrument)
            if self.metronom:
                date = redare.cu_metronom(date, redare.batai(bucata), self.volum_metronom)
            date = redare.schimba_tempo_midi(date, self.procent)
            self.sint.elibereaza()
            self._redat = None
            self.redare.bucla = False
            self.redare.canta(redare.scrie_temporar(date))
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(_('Nu am putut reda. Eroare: {0}', ex), _('Redare'))

    def scriere_deschide(self, e=None):
        scor, probleme = self._scriere_scor()
        if scor is None:
            return
        titlu = self.w_titlu.GetValue().strip() or _('Fără titlu')
        try:
            P = partitura.Partitura(scor, titlu + '.musicxml', avertismente=probleme)
        except Exception as ex:
            self.mesaj(_('Nu am putut deschide partitura. Eroare: {0}', ex), _('Scrie o partitură'))
            return
        self.redare.opreste()
        self._deschisa(P, None)

    def scriere_salveaza(self, brf):
        scor, probleme = self._scriere_scor()
        if scor is None:
            return
        if probleme and wx.MessageBox(_('Unele măsuri nu au timpii potriviți:\n') + '\n'.join(probleme[:5]) +
                                      _('\n\nSalvez totuși?'), 'Salvare', wx.YES_NO | wx.ICON_WARNING, self) != wx.YES:
            return
        titlu = self.w_titlu.GetValue().strip() or _('Partitura mea')
        nume = ''.join(ch for ch in titlu if ch not in '\\/:*?"<>|') + ('.brf' if brf else '.musicxml')
        filtru = _('Braille pentru imprimantă (*.brf)|*.brf') if brf else _('MusicXML (*.musicxml)|*.musicxml')
        cale = self._cere_salvare(_('Salvează ca BRF') if brf else _('Salvează ca MusicXML'), nume, filtru)
        try:
            if brf:
                with open(cale, 'w', encoding='ascii', errors='replace', newline='') as f:
                    f.write(braille.la_brf(braille.din_scor(scor)))
            else:
                scor.write('musicxml', fp=cale)
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(_('Nu am putut salva. Eroare: {0}', ex), _('Salvare'))
            return
        self._anunta_salvat(cale)

    def scriere_noua(self, e=None):
        """O partitură nouă în Partiturile mele; cele vechi rămân în listă."""
        self._salveaza_ciorna()
        self._curenta = self._scriere_id_nou()
        self._scriere_pune({})
        self._salveaza_ciorna()
        self.setari['scriere_curenta'] = self._curenta
        scrie_setari(self.setari)
        self._scriere_reface_lista()
        self.w_titlu.SetFocus()

    def _alege_sunet_scriere(self, it):
        if not it.IsOk() or self.w_instr.ItemHasChildren(it):
            return
        k = self.w_instr.GetItemData(it)
        if not isinstance(k, int):
            return
        _cat, nume, prog = self.instrumente[k]
        self._w_instrument = tuple(prog)
        self._ciorna_schimbata()
        voce.spune(_('Sunetul partiturii: {0}.', nume), intrerupe=True)

    def _scriere_masura_plina(self, c):
        """Spațiu la capătul unui rând: dacă rândul are deja toți timpii măsurii, cursorul trece singur
        pe rândul următor (ca Enter). Întoarce True dacă a trecut."""
        pos = c.GetInsertionPoint()
        txt = c.GetValue()
        dupa = txt[pos:]
        if dupa.split('\n', 1)[0].strip():
            return False                     # nu ești la capătul rândului
        rest = dupa.split('\n', 1)[1] if '\n' in dupa else ''
        if '\n' in dupa and rest.split('\n', 1)[0].strip():
            return False                     # rândul următor e deja scris: nu mai adaug altul
        inainte = txt[:pos]
        index = inainte.count('\n')
        if index == 0 and self.w_ana.GetValue():
            return False                     # anacruza nu are toți timpii
        oct0 = 4 if c is self.w_dr else 3
        alt = scriere.TONALITATI[max(0, self.w_ton.GetSelection())][0]
        r = scriere.timpi_rand(inainte, index, scriere.MASURI[max(0, self.w_masura.GetSelection())], alt, oct0)
        if not r or r[0] <= 0 or abs(r[0] - r[1]) > 1e-6:
            return False
        if '\n' in dupa:
            c.SetInsertionPoint(pos + len(dupa.split('\n', 1)[0]) + 1)
        else:
            c.WriteText('\n')
        nr = index + 1 if self.w_ana.GetValue() else index + 2
        voce.spune(_('Măsura {0}', nr), intrerupe=True)
        return True

    def _scriere_sageata_dreapta(self, c):
        """La capătul din dreapta al rândului NVDA spune „spațiu gol”; „linie nouă” doar când treci pe rândul următor."""
        pos = c.GetInsertionPoint()
        txt = c.GetValue()
        if pos >= len(txt):
            return
        if txt[pos] == '\n':
            wx.CallLater(60, voce.spune, _('linie nouă'), True)
        elif pos + 1 == len(txt) or txt[pos + 1] == '\n':
            wx.CallLater(60, voce.spune, _('spațiu gol'), True)

    # ---------------- exerciții de auz ----------------
    def _fila_auz(self):
        d = self.setari.get('auz', {})
        try:
            self.auz_set = auz.Setari(**{k: v for k, v in d.items() if k in auz.Setari.__dataclass_fields__})
        except Exception:
            self.auz_set = auz.Setari()
        self.auz_ses = auz.Sesiune(self.auz_set)
        self._auz_gen = 0
        self.p_auz = pa = scrolled.ScrolledPanel(self.carte)
        sa = wx.BoxSizer(wx.VERTICAL)

        def eticheta(text):
            t = wx.StaticText(pa, label=text)
            sa.Add(t, 0, wx.LEFT | wx.TOP, 4)
            return t

        eticheta(_('Exercițiul'))
        self.a_ex = wx.Choice(pa, choices=auz.EXERCITII, name=_('Exercițiul'))
        sa.Add(self.a_ex, 0, wx.ALL, 3)
        eticheta(_('Numele notelor'))
        self.a_nume = wx.Choice(pa, choices=[_('Do Re Mi'), 'C D E'], name=_('Numele notelor'))
        sa.Add(self.a_nume, 0, wx.ALL, 3)
        self.a_e_instr = eticheta(_('Sunetul exercițiilor (spațiu deschide o categorie, Enter alege)'))
        self.a_instr, self._noduri_auz = self._arbore_instrumente(pa, _('Sunetul exercițiilor'))
        sa.Add(self.a_instr, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_oct = eticheta(_('Octavele'))
        self.a_oct = ListaBife(pa, choices=[_('Octava {0}', o) for o in range(1, 8)], name=_('Octavele'), size=(-1, 90),
                               la_schimbare=self._auz_schimbat)
        sa.Add(self.a_oct, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_izol = eticheta(_('Cât de des apar cele bifate mai jos'))
        self.a_izol = wx.Choice(pa, choices=auz.IZOLARE, name=_('Cât de des apar cele bifate'))
        sa.Add(self.a_izol, 0, wx.ALL, 3)
        self.a_e_note = eticheta(_('Notele exersate'))
        self.a_note = ListaBife(pa, choices=auz.SOLFEGIU, name=_('Notele exersate'), size=(-1, 90), la_schimbare=self._auz_schimbat)
        sa.Add(self.a_note, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_int = eticheta(_('Intervalele exersate'))
        self.a_int = ListaBife(pa, choices=auz.INTERVALE, name=_('Intervalele exersate'), size=(-1, 90), la_schimbare=self._auz_schimbat)
        sa.Add(self.a_int, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_red = eticheta(_('Cum se cântă intervalul'))
        self.a_red = wx.Choice(pa, choices=auz.REDARE_INTERVAL, name=_('Cum se cântă intervalul'))
        sa.Add(self.a_red, 0, wx.ALL, 3)
        self.a_e_ac = eticheta(_('Acordurile exersate'))
        self.a_ac = ListaBife(pa, choices=[a[0] for a in auz.ACORDURI], name=_('Acordurile exersate'), size=(-1, 90),
                              la_schimbare=self._auz_schimbat)
        sa.Add(self.a_ac, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_ce = eticheta(_('La acorduri, ce spui'))
        self.a_tip = wx.CheckBox(pa, label=_('Tipul acordului (major, minor, micșorat, mărit...)'))
        sa.Add(self.a_tip, 0, wx.ALL, 3)
        self.a_rast = wx.CheckBox(pa, label=_('Răsturnarea'))
        sa.Add(self.a_rast, 0, wx.ALL, 3)
        self.a_fund = wx.CheckBox(pa, label=_('Ce acord e (fundamentala)'))
        sa.Add(self.a_fund, 0, wx.ALL, 3)
        self.a_e_dur = eticheta(_('Duratele exersate'))
        self.a_dur = ListaBife(pa, choices=[f'{n} ({c})' for n, _b, c in auz.DURATE], name=_('Duratele exersate'), size=(-1, 90),
                               la_schimbare=self._auz_schimbat)
        sa.Add(self.a_dur, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_nr = eticheta(_('Câte sunete'))
        self.a_nr = wx.SpinCtrl(pa, min=1, max=8, initial=3, name=_('Câte sunete'))
        sa.Add(self.a_nr, 0, wx.ALL, 3)
        self.a_e_tempo = eticheta(_('Tempoul duratelor (pătrimi pe minut)'))
        self.a_tempo = wx.SpinCtrl(pa, min=40, max=200, initial=80, name=_('Tempoul duratelor'))
        sa.Add(self.a_tempo, 0, wx.ALL, 3)
        self.a_e_gres = eticheta(_('Câte greșeli până îți arăt răspunsul'))
        self.a_gres = wx.SpinCtrl(pa, min=1, max=5, initial=2, name=_('Câte greșeli până îți arăt răspunsul'))
        sa.Add(self.a_gres, 0, wx.ALL, 3)
        eticheta(_('Întrebarea'))
        self.a_intreb = wx.TextCtrl(pa, style=wx.TE_READONLY, value=_('Alege exercițiul și apasă punct pentru un exercițiu nou.'), name=_('Întrebarea'))
        sa.Add(self.a_intreb, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_rasp = eticheta(_('Răspunsuri (Alt E te aduce aici, Enter răspunde)'))
        self.a_rasp = wx.ListBox(pa, name=_('Răspunsuri'), size=(-1, 110))
        sa.Add(self.a_rasp, 1, wx.EXPAND | wx.ALL, 3)
        self.a_e_text = eticheta(_('Scrie duratele auzite, cu cifre sau în cuvinte (Alt E te aduce aici, Enter răspunde)'))
        self.a_text = wx.TextCtrl(pa, style=wx.TE_PROCESS_ENTER, name=_('Duratele auzite'))
        sa.Add(self.a_text, 0, wx.EXPAND | wx.ALL, 3)
        rand = wx.WrapSizer()
        self.a_but = []
        for text, fn in ((_('Exercițiu nou (punct)'), lambda e: self.auz_nou()), (_('Ascultă din nou (virgulă)'), lambda e: self.auz_asculta()),
                         (_('Scorul'), lambda e: self._auz_spune(self.auz_ses.scor.text())),
                         (_('Scorul de la zero'), lambda e: self._auz_scor_zero())):
            b = wx.Button(pa, label=text)
            b.Bind(wx.EVT_BUTTON, fn)
            rand.Add(b, 0, wx.ALL, 3)
            self.a_but.append(b)
        sa.Add(rand, 0, wx.EXPAND)
        # auz absolut, ca în studiul din 2025 (nucleu\auz_absolut.py)
        self.ap = auz_absolut.Antrenament(self.setari.get('auz_absolut'), self.auz_set.litere)
        self._ap_r = None              # runda care merge acum
        self._ap_gen = 0
        self.a_e_ap = eticheta(_('Unde ești la auz absolut'))
        self.a_ap = wx.TextCtrl(pa, style=wx.TE_READONLY | wx.TE_MULTILINE, size=(-1, 150), name=_('Unde ești la auz absolut'))
        sa.Add(self.a_ap, 0, wx.EXPAND | wx.ALL, 3)
        self.a_ap_lim = wx.CheckBox(pa, label=_('Limită de timp pentru răspuns, ca în studiu'))
        self.a_ap_lim.SetValue(self.setari.get('auz_absolut_limita', True))
        self.a_ap_lim.Bind(wx.EVT_CHECKBOX, lambda e: (self.setari.__setitem__('auz_absolut_limita', self.a_ap_lim.GetValue()),
                                                       scrie_setari(self.setari)))
        sa.Add(self.a_ap_lim, 0, wx.ALL, 3)
        rand = wx.WrapSizer()
        self.a_ap_but = []
        for text, fn in ((_('Începe nivelul (punct)'), lambda e: self.ap_incepe()),
                         (_('Ascultă notele învățate'), lambda e: self.ap_asculta_invatate()),
                         (_('Testul din studiu (144 de note)'), lambda e: self.ap_incepe(test=True)),
                         (_('Cum merge antrenamentul'), lambda e: self.mesaj(auz_absolut.explicatie(), _('Auz absolut'))),
                         (_('Antrenamentul de la zero'), lambda e: self.ap_de_la_zero())):
            b = wx.Button(pa, label=text)
            b.Bind(wx.EVT_BUTTON, fn)
            rand.Add(b, 0, wx.ALL, 3)
            self.a_ap_but.append(b)
        sa.Add(rand, 0, wx.EXPAND)
        pa.SetSizer(sa)
        pa.SetupScrolling(scroll_x=False)
        self.carte.AddPage(pa, _('Exerciții de auz'))
        # valorile salvate
        s = self.auz_set
        self.a_ex.SetSelection(s.exercitiu)
        self.a_nume.SetSelection(1 if s.litere else 0)
        for o in s.octave:
            if 1 <= o <= 7:
                self.a_oct.Check(o - 1)
        self.a_izol.SetSelection(s.izolare)
        for lista, bif in ((self.a_note, s.note_bifate), (self.a_int, s.intervale_bifate), (self.a_ac, s.acorduri_bifate)):
            for i in bif:
                if 0 <= i < lista.GetCount():
                    lista.Check(i)
        self.a_red.SetSelection(s.redare_interval)
        self.a_tip.SetValue(s.intreaba_tipul)
        self.a_rast.SetValue(s.rasturnari)
        self.a_fund.SetValue(s.fundamentala)
        self.a_gres.SetValue(s.greseli_pana_la_raspuns)
        for i in s.durate_bifate:
            if 0 <= i < self.a_dur.GetCount():
                self.a_dur.Check(i)
        self.a_nr.SetValue(max(1, min(8, int(s.numar_durate or 3))))
        self.a_tempo.SetValue(max(40, min(200, int(s.tempo_durate or 80))))
        for c in (self.a_nr, self.a_tempo):
            c.Bind(wx.EVT_SPINCTRL, self._auz_schimbat)
            c.Bind(wx.EVT_TEXT, self._auz_schimbat)
        progs = [tuple(x[2]) for x in self.instrumente]
        k = progs.index(tuple(s.instrument)) if tuple(s.instrument) in progs else 0
        self._selecteaza_in_arbore(self.a_instr, self._noduri_auz, k)
        self._auz_arata_ce_trebuie()
        for c in (self.a_ex, self.a_nume, self.a_izol, self.a_red):
            c.Bind(wx.EVT_CHOICE, self._auz_schimbat)
        for c in (self.a_tip, self.a_rast, self.a_fund):
            c.Bind(wx.EVT_CHECKBOX, self._auz_schimbat)
        self.a_gres.Bind(wx.EVT_SPINCTRL, self._auz_schimbat)
        self.a_gres.Bind(wx.EVT_TEXT, self._auz_schimbat)
        self.a_instr.Bind(wx.EVT_KEY_DOWN, lambda e: self._tasta_arbore(e, self.a_instr, self._alege_sunet_auz))
        self.a_instr.Bind(wx.EVT_TREE_ITEM_ACTIVATED, lambda e: self._alege_sunet_auz(e.GetItem()))
        self.a_rasp.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.auz_raspunde())

    def _auz_arata_ce_trebuie(self):
        ex = self.a_ex.GetSelection()
        for ctrl, cand in ((self.a_e_note, 0), (self.a_note, 0), (self.a_e_int, 1), (self.a_int, 1), (self.a_e_red, 1),
                           (self.a_red, 1), (self.a_e_ac, 2), (self.a_ac, 2), (self.a_e_ce, 2), (self.a_tip, 2), (self.a_rast, 2),
                           (self.a_fund, 2), (self.a_e_dur, 3), (self.a_dur, 3), (self.a_e_nr, 3), (self.a_nr, 3),
                           (self.a_e_tempo, 3), (self.a_tempo, 3), (self.a_e_text, 3), (self.a_text, 3)):
            ctrl.Show(ex == cand)
        for ctrl in (self.a_e_rasp, self.a_rasp):           # la durate răspunsul se scrie, nu se alege
            ctrl.Show(ex != 3)
        ap = ex == 4
        for ctrl in [self.a_e_ap, self.a_ap, self.a_ap_lim] + self.a_ap_but:
            ctrl.Show(ap)
        for ctrl in [self.a_e_instr, self.a_instr, self.a_e_oct, self.a_oct, self.a_e_izol, self.a_izol,
                     self.a_e_gres, self.a_gres] + self.a_but:
            ctrl.Show(not ap)
        if ap:
            self.ap.litere = self.a_nume.GetSelection() == 1
            self.a_ap.SetValue(self.ap.descriere())
            if self._ap_r is None:
                self.a_intreb.SetValue(_('Apasă punct ca să începi nivelul. Răspunzi cu tastele claviaturii, rândul de jos: Z do, S do diez, X re, D re diez, C mi, V fa, G fa diez, B sol, H sol diez, N la, J la diez, M si; spațiu: în afara grupului. Când nu merge un nivel, aceleași taste îți cântă nota, dacă e învățată. Virgulă: unde ești. Escape oprește.'))
                self.a_rasp.Set([t for t, _v in self.ap.urmatoarea().optiuni])
        nume = auz.nume_note(self.a_nume.GetSelection() == 1)
        for i, n in enumerate(nume):
            self.a_note.SetString(i, n)
        self.p_auz.Layout()

    def _auz_schimbat(self, e=None):
        s = self.auz_set
        vechi_ex = s.exercitiu
        s.exercitiu = max(0, self.a_ex.GetSelection())
        s.litere = self.a_nume.GetSelection() == 1
        s.octave = [i + 1 for i in self.a_oct.GetCheckedItems()] or [4]
        s.izolare = max(0, self.a_izol.GetSelection())
        s.note_bifate = list(self.a_note.GetCheckedItems())
        s.intervale_bifate = list(self.a_int.GetCheckedItems())
        s.acorduri_bifate = list(self.a_ac.GetCheckedItems())
        s.redare_interval = max(0, self.a_red.GetSelection())
        s.intreaba_tipul = self.a_tip.GetValue()
        s.rasturnari = self.a_rast.GetValue()
        s.fundamentala = self.a_fund.GetValue()
        s.greseli_pana_la_raspuns = self.a_gres.GetValue()
        s.durate_bifate = list(self.a_dur.GetCheckedItems())
        s.numar_durate = self.a_nr.GetValue()
        s.tempo_durate = self.a_tempo.GetValue()
        self.setari['auz'] = dict(s.__dict__)
        scrie_setari(self.setari)
        self._auz_arata_ce_trebuie()
        if s.exercitiu != vechi_ex:
            self.ap_opreste(tacut=True)
            self.auz_ses.ex = None
            self.a_rasp.Clear()
            self.a_intreb.SetValue(_('Apasă punct pentru un exercițiu nou.'))
        if e:
            e.Skip()

    def _alege_sunet_auz(self, it):
        if not it.IsOk() or self.a_instr.ItemHasChildren(it):
            return
        k = self.a_instr.GetItemData(it)
        if not isinstance(k, int):
            return
        _cat, nume, prog = self.instrumente[k]
        self.auz_set.instrument = list(prog)
        self._auz_schimbat()
        self._auz_spune(_('Sunetul exercițiilor: {0}.', nume))

    def _auz_spune(self, text):
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)

    def _auz_scor_zero(self):
        self.auz_ses.scor = auz.Scor()
        self._auz_spune(_('Scorul a pornit de la zero.'))

    def _auz_arata_intrebarea(self):
        q = self.auz_ses.intrebare
        if q is None:
            return
        self.a_intreb.SetValue(q.text)
        self.a_rasp.Set(q.optiuni)
        if q.optiuni:
            self.a_rasp.SetSelection(0)
        self.a_text.SetValue('')

    def auz_nou(self):
        self._auz_schimbat()
        self.auz_ses.nou()
        self._auz_arata_intrebarea()
        self.auz_asculta()                 # cursorul rămâne unde e; la răspunsuri te duci tu, cu Alt E

    def auz_asculta(self):
        ex = self.auz_ses.ex
        if ex is None:
            self.auz_nou()
            return
        self.redare.opreste()
        try:
            self.sint.program = self.instrumente[self.instrument][2]
            self.sint.deschide()
        except Exception as exc:
            self._auz_spune(str(exc))
            return
        self._auz_gen += 1
        gen = self._auz_gen
        sunet = tuple(self.auz_set.instrument)        # sunetul exercițiilor, separat de cel al claviaturii

        def canta():
            self.sint.program_temporar(sunet)
            try:
                for note_, durata, pauza in ex.pasi:
                    if gen != self._auz_gen:
                        break
                    for n in note_:
                        self.sint.apasa(n, 100)
                    time.sleep(durata / 1000)
                    for n in note_:
                        self.sint.ridica(n)
                    if pauza:
                        time.sleep(pauza / 1000)
            finally:
                if gen == self._auz_gen:
                    self.sint.program_inapoi()
        threading.Thread(target=canta, daemon=True).start()

    def auz_raspunde(self):
        i = self.a_rasp.GetSelection()
        if i < 0 or self.auz_ses.ex is None:
            return
        mesaj, gata = self.auz_ses.raspunde(i)
        self._auz_spune(mesaj)
        self.a_intreb.SetValue(mesaj)
        if not gata and self.auz_ses.intrebare and self.auz_ses.ultimul == 'urmatoarea':
            q = self.auz_ses.intrebare
            self.a_rasp.Set(q.optiuni)
            self.a_rasp.SetSelection(0)
        if gata:
            # următorul exercițiu vine singur; după un răspuns arătat, mai târziu, ca să apuci să-l auzi
            wx.CallLater(3000, self._auz_urmatorul, self.auz_ses.ex)      # următorul exercițiu, după 3 secunde

    def auz_raspunde_text(self):
        """Exercițiul de durate: răspunsul scris în câmp (2, 1/2 sau doime, optime)."""
        if self.auz_ses.ex is None:
            self.auz_nou()
            return
        mesaj, gata = self.auz_ses.raspunde_text(self.a_text.GetValue())
        self._auz_spune(mesaj)
        self.a_intreb.SetValue(mesaj)
        if gata:
            wx.CallLater(3000, self._auz_urmatorul, self.auz_ses.ex)
        else:
            self.a_text.SelectAll()

    def _auz_urmatorul(self, ex_vechi):
        if self.auz_ses.ex is ex_vechi and self._pagina() is self.p_auz:
            self.auz_nou()


    # ---------------- auz absolut (ca în studiul din 2025) ----------------
    TASTE_NOTE = {0x2C: 0, 0x1F: 1, 0x2D: 2, 0x20: 3, 0x2E: 4, 0x2F: 5, 0x22: 6, 0x30: 7, 0x23: 8, 0x31: 9, 0x24: 10, 0x32: 11}
    LITERE_NOTE = {'Z': 0, 'S': 1, 'X': 2, 'D': 3, 'C': 4, 'V': 5, 'G': 6, 'B': 7, 'H': 8, 'N': 9, 'J': 10, 'M': 11}

    def _ap_salveaza(self):
        self.setari['auz_absolut'] = self.ap.stare()
        scrie_setari(self.setari)
        self.a_ap.SetValue(self.ap.descriere())

    def _ap_canta(self, note_, instrument, pauza=0.0, la_pornire=None):
        """Cântă notele una după alta (800 ms fiecare) cu instrumentul dat; la_pornire() se cheamă când începe prima."""
        self.redare.opreste()
        try:
            self.sint.program = self.instrumente[self.instrument][2]
            self.sint.deschide()
        except Exception as exc:
            self._auz_spune(str(exc))
            return False
        self._auz_gen += 1
        gen = self._auz_gen

        def canta():
            self.sint.program_temporar(tuple(instrument))
            try:
                for i, n in enumerate(note_):
                    if gen != self._auz_gen:
                        break
                    self.sint.apasa(n, 100)
                    if i == 0 and la_pornire:
                        la_pornire()
                    time.sleep(auz_absolut.DURATA_NOTA / 1000)
                    self.sint.ridica(n)
                    if pauza:
                        time.sleep(pauza)
            finally:
                if gen == self._auz_gen:
                    self.sint.program_inapoi()
        threading.Thread(target=canta, daemon=True).start()
        return True

    def ap_incepe(self, test=False):
        if self._ap_r is not None:
            self._auz_spune(_('Merge deja. Escape oprește.'))
            return
        self._auz_schimbat()
        self.ap.litere = self.auz_set.litere
        r = self.ap.runda_test() if test else self.ap.urmatoarea()
        self._ap_r, self._ap_i = r, 0
        self._ap_gen += 1
        gen = self._ap_gen
        r.inceput = time.monotonic()
        self.a_rasp.Set([t for t, _v in r.optiuni])
        self.a_rasp.SetSelection(0)
        if r.tip == 'test':
            intro = _('Testul: 144 de note, întâi la pian, apoi la chitară, fără răspuns spus, 5 secunde fiecare. Răspunzi doar cu numele notei.')
        elif r.tip == 'slab1':
            intro = _('Exercițiu pentru nota {0}: 12 note. E nota {0} sau altă notă? Tasta notei pentru da, spațiu pentru altă notă. Cu răspuns spus.', self.ap.nume(r.nota_slaba))
        elif r.tip == 'slab2':
            intro = _('Al doilea exercițiu pentru nota {0}: 22 de note, fără răspuns spus.', self.ap.nume(r.nota_slaba))
        else:
            n, l = auz_absolut.nota_si_nivel(r.nivel)
            intro = _('Nivelul {0}. {1} de note, trebuie {2} la sută.', r.nivel, len(r.incercari), auz_absolut.prag(l)) + ' ' + \
                (_('Cu răspunsul spus.') if r.cu_raspuns else _('Fără răspuns spus.'))
        self.a_intreb.SetValue(intro)
        if r.shepard:
            self._auz_spune(intro + ' ' + _('Întâi 20 de secunde de sunet care coboară, ca să uiți notele ascultate.'))
            try:
                import winsound
                cale = os.path.join(tempfile.gettempdir(), 'MusicBox-shepard.wav')
                if not os.path.isfile(cale):
                    auz_absolut.shepard_wav(cale)
                wx.CallLater(2500, lambda: gen == self._ap_gen and winsound.PlaySound(cale, winsound.SND_FILENAME | winsound.SND_ASYNC))
                wx.CallLater(23500, self._ap_urmatoarea, gen)
                return
            except Exception:
                pass
        else:
            self._auz_spune(intro)
        wx.CallLater(4500 if r.tip != 'nivel' else 3000, self._ap_urmatoarea, gen)

    def _ap_urmatoarea(self, gen):
        r = self._ap_r
        if gen != self._ap_gen or r is None:
            return
        if self._pagina() is not self.p_auz:
            self.ap_opreste()
            return
        if self._ap_i >= len(r.incercari):
            minute = (time.monotonic() - r.inceput) / 60
            self._ap_r = None
            nivel_vechi, gata_vechi = self.ap.nivel, self.ap.trecut_288
            mesaj = self.ap.incheie(r, minute)
            if r.tip == 'test' or self.ap.trecut_288 > gata_vechi:
                self._ap_sunet('gata')
            elif r.tip != 'nivel':
                self._ap_sunet('trecut')
            elif self.ap.nivel > nivel_vechi:
                nou = auz_absolut.nota_si_nivel(self.ap.nivel)[0] > auz_absolut.nota_si_nivel(nivel_vechi)[0]
                self._ap_sunet('nota_noua' if nou else 'trecut')
            else:
                self._ap_sunet('picat')
            self._ap_salveaza()
            self.a_intreb.SetValue(mesaj)
            self._auz_spune(mesaj)
            self.a_rasp.Set([t for t, _v in self.ap.urmatoarea().optiuni])
            return
        inc = r.incercari[self._ap_i]
        self._ap_asteapta = False
        self._ap_t0 = time.monotonic()

        def pornit():
            self._ap_t0 = time.monotonic()
            self._ap_asteapta = True
        self._ap_canta([inc.midi], r.instrument(self._ap_i), la_pornire=pornit)
        if self.a_ap_lim.GetValue() or r.tip == 'test':
            i = self._ap_i
            wx.CallLater(r.fereastra + 150, lambda: gen == self._ap_gen and self._ap_i == i and self._ap_r is r
                         and self._ap_raspuns(None))

    # sunetele de la sfârșitul unui nivel: doar percuție (fără o înălțime clară, ca să nu-ți dea o notă de reper)
    SUNETE_AP = {
        'trecut': [(81, 0), (81, 140), (84, 300)],                    # triunghi, triunghi, clopoței
        'nota_noua': [(81, 0), (81, 120), (81, 240), (84, 380), (49, 380)],   # plus țimbal
        'gata': [(84, 0), (49, 0), (84, 700), (57, 700)],
        'picat': [(77, 0), (77, 260)],                                 # wood block, încet
    }

    def _ap_sunet(self, tip):
        if getattr(self.sint, 'exclusiv', False):
            return                       # sintetizatorul Windows nu are tobe pe canalul nostru; tăcem
        pasi = self.SUNETE_AP.get(tip, [])
        self._auz_gen += 1
        gen = self._auz_gen

        def canta():
            try:
                self.sint.program_temporar((128, 0))
                t0 = time.monotonic()
                for nota, ms in pasi:
                    asteapta = ms / 1000 - (time.monotonic() - t0)
                    if asteapta > 0:
                        time.sleep(asteapta)
                    if gen != self._auz_gen:
                        return
                    self.sint.apasa(nota, 70 if tip == 'picat' else 95)
                time.sleep(1.2)
                for nota, _ms in pasi:
                    self.sint.ridica(nota)
            except Exception:
                pass
            finally:
                if gen == self._auz_gen:
                    self.sint.program_inapoi()
        threading.Thread(target=canta, daemon=True).start()

    def _ap_raspuns(self, valoare):
        """valoare: nota (0–11), AFARA, sau None (a trecut timpul)."""
        r = self._ap_r
        if r is None or not getattr(self, '_ap_asteapta', False):
            return
        self._ap_asteapta = False
        timp = (time.monotonic() - self._ap_t0) * 1000
        if not self.a_ap_lim.GetValue() and r.tip != 'test' and valoare is not None:
            timp = min(timp, r.fereastra)          # fără limită de timp: răspunsul lent nu e greșeală
        inc = r.incercari[self._ap_i]
        bine = r.raspunde(self._ap_i, valoare, timp)
        self._ap_i += 1
        pauza = 700
        if r.cu_raspuns:
            if bine:
                spus = _('Da.')
            else:
                era = self.ap.nume_raspuns(inc.tinta) if r.tip == 'nivel' else \
                    (self.ap.nume(inc.tinta) if inc.tinta != auz_absolut.AFARA else _('altă notă'))
                spus = (_('Prea târziu.') if valoare is None or timp > r.fereastra else _('Nu.')) + ' ' + _('Era {0}.', era)
            self._auz_spune(spus)
            pauza = 900 if bine else 1800
        wx.CallLater(pauza, self._ap_urmatoarea, self._ap_gen)

    def ap_opreste(self, tacut=False):
        if self._ap_r is None:
            return
        self._ap_r = None
        self._ap_gen += 1
        self._auz_gen += 1
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except Exception:
            pass
        if not tacut:
            self._auz_spune(_('Oprit. Runda nu s-a numărat.'))
        self.a_intreb.SetValue(_('Oprit. Apasă punct ca să începi din nou.'))

    def ap_asculta_nota(self, pc):
        if pc not in self.ap.invatate():
            self._auz_spune(_('{0} nu e încă învățată.', self.ap.nume(pc)))
            return
        self._ap_canta(self.ap.mostre(pc), auz_absolut.PIAN, pauza=0.25)
        self.setari['auz_absolut'] = self.ap.stare()
        scrie_setari(self.setari)

    def ap_asculta_invatate(self):
        if self._ap_r is not None:
            return
        note_ = []
        for pc in sorted(self.ap.invatate()):
            note_ += self.ap.mostre(pc)
        self._auz_spune(_('Notele învățate, de jos în sus, fiecare în trei octave: {0}.', ', '.join(self.ap.nume(pc) for pc in sorted(self.ap.invatate()))))
        wx.CallLater(2500, lambda: self._ap_canta(note_, auz_absolut.PIAN, pauza=0.25))
        self.setari['auz_absolut'] = self.ap.stare()
        scrie_setari(self.setari)

    def ap_de_la_zero(self):
        if wx.MessageBox(_('Ștergi tot progresul la auz absolut și o iei de la nivelul 1? Testele făcute rămân.'), _('Auz absolut'),
                         wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
            return
        self.ap_opreste(tacut=True)
        teste = self.ap.teste
        self.ap = auz_absolut.Antrenament({'teste': teste}, self.auz_set.litere)
        self._ap_salveaza()
        self._auz_arata_ce_trebuie()
        self._auz_spune(_('Ai pornit de la nivelul 1.'))

    def _ap_tasta(self, e, foc, sc):
        """Tastele în exercițiul de auz absolut. Întoarce True dacă tasta a fost folosită."""
        if e.ControlDown() or e.AltDown():
            return False
        k = e.GetKeyCode()
        scrie = isinstance(foc, wx.TextCtrl) and foc.IsEditable() or isinstance(foc, wx.SpinCtrl)
        if scrie:
            return False
        if k == wx.WXK_ESCAPE and self._ap_r is not None:
            self.ap_opreste()
            return True
        if k == ord('.') or sc == 0x34:
            self.ap_incepe()
            return True
        if k == ord(',') or sc == 0x33:
            self._auz_spune(self.ap.descriere())
            return True
        nota = self.TASTE_NOTE.get(sc) if os.name == 'nt' and sc else None
        if nota is None and 0 < k < 256:
            nota = self.LITERE_NOTE.get(chr(k).upper())
        if self._ap_r is not None:
            if k == wx.WXK_SPACE:
                self._ap_raspuns(auz_absolut.AFARA)
                return True
            if nota is not None:
                self._ap_raspuns(nota)           # o notă neînvățată e răspuns greșit
                return True
            if foc is self.a_rasp and k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                i = self.a_rasp.GetSelection()
                if 0 <= i < len(self._ap_r.optiuni):
                    self._ap_raspuns(self._ap_r.optiuni[i][1])
                return True
            return False
        if nota is not None and isinstance(foc, (wx.ListBox, wx.Button, wx.CheckBox, wx.TextCtrl)):
            self.ap_asculta_nota(nota)
            return True
        return False

    # ---------------- claviatura ----------------
    def _clav_text(self):
        nume = self.instrumente[self.instrument][1]
        o = claviatura.nume_octava(self.do_clav)
        tr = _('transpus {0:+d} semitonuri', self.transpunere) if self.transpunere else 'netranspus'
        self.t_clav.SetValue(_('Claviatura. Instrument: {0}. Z e do {1}, {2}.\nRândul de jos, de la Z la 3 de pe blocul numeric: do, re, mi și tot așa, două octave. Diezii sunt deasupra, cu o tastă mai la dreapta: S do diez, D re diez, F gol, G fa diez, și tot așa. Rândul de la Tab și cifrele de la 1 sunt la fel, cu o octavă mai jos. Shift stânga face nota să tremure.\nSăgeată dreapta sau stânga: octava. Săgeată sus sau jos: instrumentul. Control săgeată dreapta sau stânga: transpui cu un semiton. Escape: ieși.', nume, o, tr)
                             + '\n' + _('Spațiu: deschide sau închide categoria de instrumente.'))
        self.t_clav.SetInsertionPoint(0)

    def _clav_intra(self, e):
        self.redare.opreste()            # sintetizatorul e folosit acum de claviatură
        try:
            self.sint.program = self.instrumente[self.instrument][2]
            self.sint.deschide()
        except Exception as ex:
            self.SetStatusText(str(ex))
            voce.spune(str(ex))
        e.Skip()

    def _clav_iese(self, e):
        self._apasate.clear()
        if self._bender_apasat:
            self._bender_apasat = False
            self._vibrato.opreste()
        self.sint.elibereaza()           # eliberează sintetizatorul Windows pentru redarea piesei
        e.Skip()

    def _clav_apasa(self, e):
        """O tastă apăsată cât ești în claviatură. Celelalte scurtături nu mai fac nimic aici."""
        k = e.GetKeyCode()
        if e.AltDown() or (wx.WXK_F1 <= k <= wx.WXK_F24):
            e.Skip()
            return
        sageata = {wx.WXK_LEFT: -1, wx.WXK_RIGHT: 1, wx.WXK_UP: 'sus', wx.WXK_DOWN: 'jos'}.get(k)
        if sageata is not None and self._sc_numeric(e):
            sageata = None               # 4, 6, 2 de pe blocul numeric fără Num Lock sunt note, nu săgeți
        if e.ControlDown():
            if sageata in (-1, 1):
                self.transpune(sageata)
                return
            e.Skip()                     # Control 1, Control O și celelalte merg în continuare
            return
        if k == wx.WXK_ESCAPE:
            self.arata_sub(0)
            return
        if sageata in (-1, 1):
            self.do_clav = min(84, max(24, self.do_clav + 12 * sageata))
            self.setari['octava_claviatura'] = self.do_clav
            scrie_setari(self.setari)
            text = str(claviatura.nume_octava(self.do_clav))
            self.SetStatusText(_('Octava {0}.', text))
            voce.spune(text, intrerupe=True)
            self._clav_text()
            return
        if sageata in ('sus', 'jos'):
            self._clav_foldere_pas(1 if sageata == 'jos' else -1)
            return
        if k == wx.WXK_SPACE and not e.ShiftDown():          # Enter e notă (re diez sus), deci doar spațiul
            self._clav_foldere_spatiu()
            return
        sc = self._sc(e)
        if sc == claviatura.TASTA_BENDER:
            if not self._bender_apasat:            # Shift stânga: nota tremură cât îl ții (fără repetări)
                self._bender_apasat = True
                self._vibrato.porneste()
            return
        if sc in claviatura.TASTE and sc not in self._apasate:
            nota = self.do_clav + claviatura.TASTE[sc] + self.transpunere
            if not self.sint.deschis():
                try:
                    self.sint.program = self.instrumente[self.instrument][2]
                    self.sint.deschide()
                except Exception as ex:
                    self.SetStatusText(str(ex))
            # se ține minte nota și canalul: dacă schimbi octava sau instrumentul cât ții tasta, nota sună până o ridici
            self._apasate[sc] = (nota, self.sint.apasa(nota))
        # orice altă tastă (litere, cifre, Tab, Enter...) nu face nimic aici

    def _clav_ridica(self, e):
        sc = self._sc(e)
        tinuta = self._apasate.pop(sc, None)
        if tinuta is not None:
            self.sint.ridica(*tinuta)
        if e.GetKeyCode() == wx.WXK_SHIFT:   # la Shift, Windows nu spune mereu care dintre ele: le oprim pe amândouă
            if self._bender_apasat and sc != 0x36:
                self._bender_apasat = False
                self._vibrato.opreste()
            for t in (0x2A, 0x36):
                n2 = self._apasate.pop(t, None)
                if n2 is not None:
                    self.sint.ridica(*n2)

    @staticmethod
    def _sc(e):
        """Codul fizic al tastei (fără bitul de tastă extinsă: Shift dreapta și cel stâng diferă prin cod)."""
        if os.name != 'nt':
            return 0
        f = e.GetRawKeyFlags()
        sc = (f >> 16) & 0xFF
        if e.GetKeyCode() == wx.WXK_SHIFT and sc not in (0x2A, 0x36):
            sc = 0x2A
        if f & (1 << 24) and sc in claviatura.BLOC_NUMERIC:
            return 0                     # săgețile, End, Page Down de lângă săgeți, nu tastele de pe blocul numeric
        return sc

    def _sc_numeric(self, e):
        """Adevărat dacă tasta e 3 de pe blocul numeric fără Num Lock (aceeași cu Page Down): e notă, nu octavă."""
        return os.name == 'nt' and not (e.GetRawKeyFlags() & (1 << 24)) and ((e.GetRawKeyFlags() >> 16) & 0xFF) in claviatura.TASTE

    def transpune(self, pas):
        self.transpunere = min(12, max(-12, self.transpunere + pas))
        self.setari['transpunere'] = self.transpunere
        scrie_setari(self.setari)
        text = f'{self.transpunere:+d}' if self.transpunere else '0'
        self.SetStatusText(_('Transpus {0} semitonuri.', text))
        voce.spune(text.replace('+', 'plus ').replace('-', 'minus '), intrerupe=True)
        self._clav_text()

    def _proba_instrument(self):
        """Un acord scurt, ca să auzi instrumentul ales din Setări."""
        try:
            self.sint.deschide()
        except Exception as ex:
            self.SetStatusText(str(ex))
            return

        def canta():
            for n in (60, 64, 67):
                self.sint.apasa(n, 100)
            time.sleep(0.9)
            for n in (60, 64, 67):
                self.sint.ridica(n)
            if self.sint.exclusiv:
                wx.CallAfter(self._inchide_sint_daca_liber)
        threading.Thread(target=canta, daemon=True).start()

    def _arbore_instrumente(self, parinte, nume):
        """Arborele cu instrumente: categoriile sunt „foldere”, în ele instrumentele. Întoarce (arbore, {indice: nod})."""
        arb = wx.TreeCtrl(parinte, size=(-1, 220), name=nume,
                          style=wx.TR_HIDE_ROOT | wx.TR_HAS_BUTTONS | wx.TR_SINGLE | wx.TR_LINES_AT_ROOT)
        radacina = arb.AddRoot('')
        noduri = {}
        k = 0
        for cat, inst in self.catalog:
            nod = arb.AppendItem(radacina, _('{0} ({1} instrumente)', cat, len(inst)))
            for nume_i, _prog in inst:
                it = arb.AppendItem(nod, nume_i)
                arb.SetItemData(it, k)
                noduri[k] = it
                k += 1
        return arb, noduri

    @staticmethod
    def _selecteaza_in_arbore(arb, noduri, k):
        it = noduri.get(k)
        if it is not None and arb.GetSelection() != it:
            arb.EnsureVisible(it)
            arb.SelectItem(it)

    def _tasta_arbore(self, e, arb, alege):
        """Spațiu pe o categorie o deschide sau o închide; spațiu sau Enter pe un instrument îl alege."""
        k = e.GetKeyCode()
        it = arb.GetSelection()
        if k in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and it.IsOk():
            if arb.ItemHasChildren(it):
                if k == wx.WXK_SPACE:
                    arb.Toggle(it)
                    return
            else:
                alege(it)
                return
        e.Skip()

    def _alege_din_arbore(self, it):
        if not it.IsOk() or self.s_instrument.ItemHasChildren(it):
            return
        k = self.s_instrument.GetItemData(it)
        if isinstance(k, int):
            self.schimba_instrument(index=k, proba=True)

    # instrumentele din claviatură sunt în foldere (categorii): săgețile sus și jos merg prin ce e vizibil,
    # spațiul deschide sau închide categoria; o singură categorie e deschisă odată
    def _clav_categorii(self):
        inceput, i = [], 0
        for cat, inst in self.catalog:
            inceput.append((cat, i, len(inst)))
            i += len(inst)
        return inceput

    def _clav_cat_a(self, index):
        for ci, (cat, start, n) in enumerate(self._clav_categorii()):
            if start <= index < start + n:
                return ci
        return 0

    def _clav_vizibile(self):
        deschisa = getattr(self, '_clav_deschisa', self._clav_cat_a(self.instrument))
        rez = []
        for ci, (cat, start, n) in enumerate(self._clav_categorii()):
            rez.append(('cat', ci))
            if ci == deschisa:
                rez += [('inst', start + j) for j in range(n)]
        return rez

    def _clav_pozitia(self):
        poz = getattr(self, '_clav_cursor', None)
        if poz is None or (poz[0] == 'inst' and poz[1] != self.instrument):   # instrumentul s-a schimbat din Setări
            self._clav_deschisa = self._clav_cat_a(self.instrument)
            poz = ('inst', self.instrument)
        return poz

    def _clav_spune_categoria(self, ci, cu_nume=True):
        cat = self._clav_categorii()[ci][0]
        stare = _('extins') if getattr(self, '_clav_deschisa', None) == ci else _('restrâns')
        text = f'{cat}, {stare}' if cu_nume else stare
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)

    def _clav_foldere_pas(self, pas):
        poz = self._clav_pozitia()
        viz = self._clav_vizibile()
        i = viz.index(poz) if poz in viz else 0
        poz = viz[(i + pas) % len(viz)]
        self._clav_cursor = poz
        if poz[0] == 'inst':
            cat, start, n = self._clav_categorii()[self._clav_cat_a(poz[1])]
            nume = self.instrumente[poz[1]][1]
            self.schimba_instrument(index=poz[1], anunt=_('{0}, {1} din {2}', nume, poz[1] - start + 1, n))
        else:
            self._clav_spune_categoria(poz[1])

    def _clav_foldere_spatiu(self):
        tip, val = self._clav_pozitia()
        if tip == 'inst':
            ci = self._clav_cat_a(val)          # pe un instrument: se închide categoria lui și cursorul urcă pe ea
            self._clav_deschisa = None
        else:
            ci = val
            self._clav_deschisa = None if getattr(self, '_clav_deschisa', None) == ci else ci
        self._clav_cursor = ('cat', ci)
        self._clav_spune_categoria(ci, cu_nume=False)      # la spațiu se spune doar „extins” sau „restrâns”

    def schimba_instrument(self, pas=0, index=None, proba=False, anunt=None):
        n = len(self.instrumente)
        self.instrument = (self.instrument + pas) % n if index is None else index % n
        _cat, nume, prog = self.instrumente[self.instrument]
        self.sint.schimba_instrument(prog)
        if proba:
            self._proba_instrument()
        self.setari['instrument_bp'] = list(prog)
        self.setari.pop('instrument_prog', None)
        self.setari.pop('instrument', None)
        scrie_setari(self.setari)
        self._sincronizeaza_setari()
        self.SetStatusText(_('Instrument: {0}.', nume))
        voce.spune(anunt or nume, intrerupe=True)
        self._clav_text()

    @staticmethod
    def _e_in(w, parinte):
        while w is not None:
            if w is parinte:
                return True
            w = w.GetParent()
        return False

    # controalele prin care trece Tab; panourile (și cele care se derulează) doar se parcurg, nu primesc ele cursorul
    _TIPURI_TAB = (wx.TextCtrl, wx.ListBox, wx.Choice, wx.CheckBox, wx.Button, wx.SpinCtrl, wx.TreeCtrl, wx.ListCtrl,
                   wx.ComboBox, wx.RadioButton, wx.Slider)

    def _tab_in_pagina(self, pag, foc, inapoi):
        """Tab în fila deschisă: de la un element la următorul, iar de la ultimul înapoi la primul."""
        elemente = []

        def aduna(w):
            for c in w.GetChildren():
                if not c.IsShown():
                    continue
                if isinstance(c, self._TIPURI_TAB):
                    if c.IsEnabled():
                        elemente.append(c)
                elif isinstance(c, (wx.Panel, wx.StaticBox, wx.ScrolledWindow)):
                    aduna(c)
        aduna(pag)
        if not elemente:
            return
        cur = foc
        while cur is not None and not any(cur is x for x in elemente):
            cur = cur.GetParent()
        i = next((k for k, x in enumerate(elemente) if x is cur), -1)
        urm = elemente[(i + (-1 if inapoi else 1)) % len(elemente)]
        if urm is foc or len(elemente) == 1:
            # un singur element în filă: cursorul rămâne, dar spunem unde e, ca să nu pară că nu s-a întâmplat nimic
            voce.spune(urm.GetName(), intrerupe=True)
        urm.SetFocus()
        if isinstance(pag, scrolled.ScrolledPanel):
            pag.ScrollChildIntoView(urm)

    _NUME_TASTE = {wx.WXK_SPACE: 'spațiu', wx.WXK_RETURN: 'Enter', wx.WXK_NUMPAD_ENTER: 'Enter', wx.WXK_ESCAPE: 'Escape',
                   wx.WXK_TAB: 'Tab', wx.WXK_BACK: 'Backspace', wx.WXK_DELETE: 'Delete', wx.WXK_HOME: 'Home', wx.WXK_END: 'End',
                   wx.WXK_LEFT: 'săgeată stânga', wx.WXK_RIGHT: 'săgeată dreapta', wx.WXK_UP: 'săgeată sus',
                   wx.WXK_DOWN: 'săgeată jos', wx.WXK_PAGEUP: 'Page Up', wx.WXK_PAGEDOWN: 'Page Down', wx.WXK_INSERT: 'Insert',
                   wx.WXK_SHIFT: 'Shift', wx.WXK_CONTROL: 'Control', wx.WXK_ALT: 'Alt'}

    def _nume_tasta(self, e):
        k = e.GetKeyCode()
        parti = []
        if e.ControlDown() and k != wx.WXK_CONTROL:
            parti.append('Control')
        if e.AltDown() and k != wx.WXK_ALT:
            parti.append('Alt')
        if e.ShiftDown() and k != wx.WXK_SHIFT:
            parti.append('Shift')
        if k in self._NUME_TASTE:
            nume = self._NUME_TASTE[k]
            nume = {'spațiu': _('spațiu'), 'săgeată stânga': _('săgeată stânga'), 'săgeată dreapta': _('săgeată dreapta'),
                    'săgeată sus': _('săgeată sus'), 'săgeată jos': _('săgeată jos')}.get(nume, nume)
        elif wx.WXK_F1 <= k <= wx.WXK_F24:
            nume = f'F{k - wx.WXK_F1 + 1}'
        elif k == ord(',') or k == ord('.'):
            nume = _('virgulă') if k == ord(',') else _('punct')
        elif 32 < k < 127:
            nume = chr(k).upper()
        else:
            u = e.GetUnicodeKey()
            nume = chr(u).upper() if u and u > 32 else str(k)
        return ' '.join(parti + [nume])

    def _acceleratori(self):
        """Scurtăturile din meniuri („Ctrl+Shift+B” -> textul comenzii), pentru ajutorul la taste."""
        if getattr(self, '_acc', None) is None:
            self._acc = {}
            mb = self.GetMenuBar()
            for i in range(mb.GetMenuCount()):
                for it in mb.GetMenu(i).GetMenuItems():
                    eticheta = it.GetItemLabel()
                    if '\t' in eticheta:
                        text, acc = eticheta.split('\t', 1)
                        parti = [x.strip().lower() for x in acc.split('+')]
                        self._acc[(frozenset(parti[:-1]), parti[-1])] = text.replace('&', '').rstrip('. ')
        return self._acc

    def _descrie_tasta(self, e, foc):
        """Ce face tasta apăsată acum, în fila deschisă (pentru ajutorul la taste)."""
        k = e.GetKeyCode()
        sc = (e.GetRawKeyFlags() >> 16) & 0xFF if os.name == 'nt' else 0
        tasta = self._nume_tasta(e)
        ctrl, alt, shift = e.ControlDown(), e.AltDown(), e.ShiftDown()

        def zi(text):
            return f'{tasta}: {text}'
        if k == wx.WXK_F1:
            return zi(_('scurtăturile, în cuvinte.'))
        # scurtăturile din meniuri (Control 1, Control O, Control Shift B...)
        mods = frozenset(m for m, da in (('ctrl', ctrl), ('alt', alt), ('shift', shift)) if da)
        if wx.WXK_F1 <= k <= wx.WXK_F24:
            cheie = f'f{k - wx.WXK_F1 + 1}'
        elif k in (wx.WXK_LEFT, wx.WXK_RIGHT):
            cheie = 'left' if k == wx.WXK_LEFT else 'right'
        elif 32 < k < 127:
            cheie = chr(k).lower()
        else:
            cheie = None
        if cheie and mods:
            text = self._acceleratori().get((mods, cheie))
            if text:
                return zi(text)
        pag = self._pagina()
        # claviatura
        if foc is self.t_clav:
            if k == wx.WXK_ESCAPE:
                return zi(_('ieși din claviatură.'))
            if k in (wx.WXK_LEFT, wx.WXK_RIGHT):
                if ctrl:
                    return zi(_('transpui cu un semiton în sus.') if k == wx.WXK_RIGHT else _('transpui cu un semiton în jos.'))
                return zi(_('octava mai sus.') if k == wx.WXK_RIGHT else _('octava mai jos.'))
            if k in (wx.WXK_UP, wx.WXK_DOWN):
                return zi(_('instrumentul următor.') if k == wx.WXK_DOWN else _('instrumentul anterior.'))
            if k == wx.WXK_SPACE:
                return zi(_('deschide sau închide categoria de instrumente.'))
            if sc == claviatura.TASTA_BENDER:
                return zi(_('nota tremură cât ții tasta.'))
            if sc in claviatura.TASTE:
                n = self.do_clav + claviatura.TASTE[sc] + self.transpunere
                return zi(_('nota {0} {1}.', auz.SOLFEGIU[n % 12].lower(), n // 12 - 1))
            return zi(_('nu face nimic în claviatură.'))
        # fișiere audio
        if pag is self.p_fisiere and ctrl and not (alt or shift) and k in (wx.WXK_HOME, wx.WXK_END):
            return zi(_('volumul mai tare cu 10 la sută.') if k == wx.WXK_HOME else _('volumul mai încet cu 10 la sută.'))
        if foc in self.p_fisiere.locuri and not (ctrl or alt):
            for kk, sck in ((ord('K'), 0x25), (ord('L'), 0x26), (ord('J'), 0x24), (ord('I'), 0x17), (ord('R'), 0x13)):
                if sc == sck:
                    k = kk
            d = {ord('K'): _('o ia de la capăt.') if shift else _('pune pauză și continuă.'), ord('L'): _('înainte 5 secunde.'),
                 ord('J'): _('înapoi 5 secunde.'), ord('I'): _('spune minutul și secunda la care ești.'),
                 ord('R'): _('alege ce se întâmplă la sfârșit: repetă, se oprește sau trece la următoarea.'),
                 wx.WXK_ESCAPE: _('oprește.'), wx.WXK_UP: _('fișierul de deasupra, se aude imediat.'),
                 wx.WXK_DOWN: _('fișierul de dedesubt, se aude imediat.'), wx.WXK_RIGHT: _('subfolderul următor.'),
                 wx.WXK_LEFT: _('subfolderul anterior.'), wx.WXK_SPACE: _('spune numele fișierului și al câtelea e.')}
            if k in d:
                return zi(d[k])
        # metronomul
        if pag is self.p_metronom and not (ctrl or alt):
            d = {ord('K'): _('pornește sau oprește metronomul.'), wx.WXK_SPACE: _('pornește sau oprește metronomul.'),
                 wx.WXK_UP: _('tempoul cu 1 mai repede.'), wx.WXK_DOWN: _('tempoul cu 1 mai rar.'),
                 wx.WXK_PAGEUP: _('tempoul cu 5 mai repede.'), wx.WXK_PAGEDOWN: _('tempoul cu 5 mai rar.'),
                 wx.WXK_RIGHT: _('un timp în plus în măsură.'), wx.WXK_LEFT: _('un timp în minus în măsură.'),
                 ord('I'): _('spune tempoul, timpii și volumul.'), wx.WXK_HOME: _('volumul mai tare cu 10 la sută.'),
                 wx.WXK_END: _('volumul mai încet cu 10 la sută.'), wx.WXK_TAB: _('rămâi în metronom.')}
            if sc == 0x25:
                k = ord('K')
            if sc == 0x17:
                k = ord('I')
            if k in d:
                return zi(d[k])
        # player
        if pag is self.p_player and not (ctrl or alt or shift):
            d = {ord('K'): _('pornește, pune pauză și continuă.'), wx.WXK_SPACE: _('pornește, pune pauză și continuă.'),
                 ord('L'): _('înainte 5 secunde.'), ord('J'): _('înapoi 5 secunde.'),
                 ord('I'): _('spune minutul și secunda la care ești și măsura.'), wx.WXK_HOME: _('de la început.'),
                 ord('M'): _('ce auzi: ambele mâini, doar dreapta sau doar stânga.'),
                 wx.WXK_ESCAPE: _('oprește.'), wx.WXK_TAB: _('rămâi în player.')}
            for kk, sck in ((ord('K'), 0x25), (ord('L'), 0x26), (ord('J'), 0x24), (ord('I'), 0x17), (ord('M'), 0x32)):
                if sc == sck:
                    k = kk
            if k in d:
                return zi(d[k])
        # scrie o partitură
        if pag is self.p_scriere:
            if ctrl and shift and k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                return zi(_('asculți toată partitura.'))
            if ctrl and not shift and (k == ord('S') or sc == 0x1F):
                return zi(_('salvezi partitura în Partiturile mele.'))
            if foc is self.w_tempo or (foc is not None and foc.GetParent() is self.w_tempo):
                if k in (wx.WXK_PAGEUP, wx.WXK_PAGEDOWN):
                    return zi(_('tempoul cu 5 mai repede.') if k == wx.WXK_PAGEUP else _('tempoul cu 5 mai rar.'))
                if k in (wx.WXK_UP, wx.WXK_DOWN):
                    return zi(_('tempoul cu 1 mai repede.') if k == wx.WXK_UP else _('tempoul cu 1 mai rar.'))
        if foc in (self.w_dr, self.w_st):
            if ctrl and k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                return zi(_('asculți măsura pe care ești, cu ambele mâini.'))
            if k == wx.WXK_SPACE and not (ctrl or alt or shift):
                return zi(_('spațiu; când măsura e plină, treci singur pe rândul următor.'))
            if ctrl and k == wx.WXK_F2:
                return zi(_('spune pe ce măsură ești.'))
            return zi(_('scrii notele în câmp.'))
        # exerciții de auz
        if pag is self.p_auz and self.auz_set.exercitiu == 4 and not (ctrl or alt):
            if k == ord('.') or sc == 0x34:
                return zi(_('începe nivelul.'))
            if k == ord(',') or sc == 0x33:
                return zi(_('spune unde ești.'))
            if k == wx.WXK_SPACE:
                return zi(_('răspunde: în afara grupului.'))
            if k == wx.WXK_ESCAPE:
                return zi(_('oprește runda.'))
            n = self.TASTE_NOTE.get(sc) if sc else None
            if n is not None:
                return zi(_('răspunde {0}; când nu merge nicio rundă, îți cântă nota.', self.ap.nume(n)))
        if pag is self.p_auz:
            if alt and (k == ord('E') or sc == 0x12):
                return zi(_('mergi la răspunsuri.'))
            if foc in (self.a_rasp, self.a_text) and k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                return zi(_('răspunde.'))
            if not (ctrl or alt) and (k == ord(',') or sc == 0x33):
                return zi(_('ascultă din nou.'))
            if not (ctrl or alt) and (k == ord('.') or sc == 0x34):
                return zi(_('exercițiu nou.'))
        # într-un câmp în care scrii, literele se scriu
        if isinstance(foc, (wx.TextCtrl, wx.SpinCtrl)) and (not isinstance(foc, wx.TextCtrl) or foc.IsEditable()):
            return zi(_('scrie în câmp.'))
        # tastele de redare (în celelalte file)
        if pag not in (self.p_player, self.p_setari, self.p_scriere, self.p_auz, self.p_fisiere) or foc is self.lista:
            for kk, sck in ((ord('K'), 0x25), (ord('L'), 0x26), (ord('J'), 0x24), (ord('I'), 0x17)):
                if sc == sck:
                    k = kk
            if not ctrl and not alt:
                if k == ord('K'):
                    return zi(_('Reia de la început (Shift K)') if shift else _('Redă, oprește sau continuă (K)'))
                if k == ord('I') and not shift:
                    return zi(_('Redă de la măsura aleasă până la final (I)'))
                if k == ord('L') and not shift:
                    return zi(_('Măsura următoare (L)\tAlt+Right').split('\t')[0])
                if k == ord('J') and not shift:
                    return zi(_('Măsura anterioară (J)\tAlt+Left').split('\t')[0])
        r = e.GetRawKeyCode() if os.name == 'nt' else 0
        if shift and not alt:
            if not ctrl and (k == ord('1') or r == 0x31):
                return zi(_('Mai rar cu 5 la sută (Shift 1)'))
            if not ctrl and (k == ord('2') or r == 0x32):
                return zi(_('Mai repede cu 5 la sută (Shift 2)'))
            if not ctrl and (k in (ord('3'), ord('0')) or r in (0x33, 0x30)):
                return zi(_('Tempoul scris în piesă (Shift 3)'))
            plus = sc in (0x0D, 0x4E) or k in (wx.WXK_NUMPAD_ADD, ord('+'), ord('='))
            minus = sc in (0x0C, 0x4A) or k in (wx.WXK_NUMPAD_SUBTRACT, ord('-'), ord('_'))
            if plus:
                return zi(_('Metronomul mai tare cu 5 la sută (Control Shift plus)') if ctrl else _('Metronomul mai tare cu 1 la sută (Shift plus)'))
            if minus:
                return zi(_('Metronomul mai încet cu 5 la sută (Control Shift minus)') if ctrl else _('Metronomul mai încet cu 1 la sută (Shift minus)'))
        if ctrl and k == wx.WXK_TAB:
            return zi(_('fila anterioară.') if shift else _('fila următoare.'))
        if k == wx.WXK_TAB:
            return zi(_('elementul anterior.') if shift else _('elementul următor.'))
        return zi(_('nu face nimic aici.'))

    def _taste(self, e):
        """Tastele de redare, prinse direct din tastatură (după tasta fizică, oricare ar fi aranjarea tastaturii):
        Shift 1 / 2 / 3 tempoul; K redă, oprește, continuă; Shift K de la început; L și J măsura următoare și anterioară;
        Shift plus / minus volumul metronomului cu 1, cu Control cu 5. Nu se prind când scrii într-un câmp."""
        foc = wx.Window.FindFocus()
        # F2: ajutorul la taste; cât e pornit, orice tastă spune ce face (în fila deschisă), fără s-o facă
        if e.GetKeyCode() == wx.WXK_F2 and not e.ControlDown() and not e.AltDown() and not e.ShiftDown():
            self._ajutor_taste = not getattr(self, '_ajutor_taste', False)
            voce.spune(_('Ajutor la taste pornit. Apasă orice tastă și îți spun ce face. F2 sau Escape ies.') if self._ajutor_taste
                       else _('Ajutor la taste oprit.'), intrerupe=True)
            return
        if getattr(self, '_ajutor_taste', False):
            if e.GetKeyCode() == wx.WXK_ESCAPE:
                self._ajutor_taste = False
                voce.spune(_('Ajutor la taste oprit.'), intrerupe=True)
                return
            if e.GetKeyCode() in (wx.WXK_SHIFT, wx.WXK_CONTROL, wx.WXK_ALT, wx.WXK_WINDOWS_LEFT, wx.WXK_WINDOWS_RIGHT) and \
                    not (os.name == 'nt' and ((e.GetRawKeyFlags() >> 16) & 0xFF) == claviatura.TASTA_BENDER and foc is self.t_clav):
                return
            voce.spune(self._descrie_tasta(e, foc), intrerupe=True)
            return
        if foc is self.t_clav:
            self._clav_apasa(e)
            return
        if self._pagina() is self.p_fisiere and self.p_fisiere.volum(e):
            return
        # Control Home / Control End: volumul metronomului redării (cu câte 5), afară de câmpurile de text,
        # unde rămân „începutul” și „sfârșitul” textului
        if e.ControlDown() and not e.AltDown() and not e.ShiftDown() and e.GetKeyCode() in (wx.WXK_HOME, wx.WXK_END) \
                and not (isinstance(foc, wx.TextCtrl) and foc is not self.p_player.t) and self._pagina() is not self.p_metronom:
            self.schimba_volum_metronom(5 if e.GetKeyCode() == wx.WXK_HOME else -5)
            return
        if foc in self.p_fisiere.locuri:
            if not self.p_fisiere.tasta(e, foc):
                e.Skip()                         # Tab și celelalte merg ca de obicei
            return
        if self._pagina() is self.p_player and foc is not None and self._e_in(foc, self.p_player) \
                and self.p_player.tasta(e):
            return
        if self._pagina() is self.p_metronom and foc is not None and self._e_in(foc, self.p_metronom) \
                and self.p_metronom.tasta(e):
            return
        # arborii de instrumente: spațiu deschide sau închide o categorie, spațiu sau Enter alege un instrument
        # (prins aici, pentru că tasta nu ajunge sigur la arbore pe Windows)
        if foc is not None and foc in (self.s_instrument, self.a_instr) and not e.AltDown() and not e.ControlDown() \
                and e.GetKeyCode() in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            alege = self._alege_din_arbore if foc is self.s_instrument else self._alege_sunet_auz
            it = foc.GetSelection()
            if it.IsOk():
                if foc.ItemHasChildren(it):
                    if foc.IsExpanded(it):
                        foc.Collapse(it)
                    else:
                        foc.Expand(it)
                else:
                    alege(it)
            return
        # Tab și Shift Tab: le lasă pe seama Windows, ca la început (cerut de Răzvan)
        if e.GetKeyCode() == wx.WXK_TAB:
            # din textul în cuvinte sau în Braille, Tab duce înapoi la lista de măsuri
            # (căsuța de text nu dă singură cursorul mai departe), Shift Tab la ultima opțiune din stânga
            if foc in (self.t_cuvinte, self.t_braille, self.p_player.t) and not e.ControlDown() and not e.AltDown():
                (self.c_voci if e.ShiftDown() else self.lista).SetFocus()
                return
            e.Skip()
            return
        if self._pagina() is self.p_scriere and foc is not None and self._e_in(foc, self.p_scriere):
            kc = e.GetKeyCode()
            if e.ControlDown() and not e.AltDown() and not e.ShiftDown() and (kc == ord('S') or
                                                                             (os.name == 'nt' and e.GetRawKeyCode() == 0x53)):
                self._salveaza_ciorna(spune=True)            # Control S: salvează partitura (nu textul în cuvinte)
                return
            if e.ControlDown() and e.ShiftDown() and kc in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.scriere_asculta(False)                    # Control Shift Enter: ascultă tot
                return
            if (foc is self.w_tempo or foc.GetParent() is self.w_tempo) and kc in (wx.WXK_PAGEUP, wx.WXK_PAGEDOWN) \
                    and not e.ControlDown():
                v = max(0, min(300, self.w_tempo.GetValue() + (5 if kc == wx.WXK_PAGEUP else -5)))
                self.w_tempo.SetValue(v)
                self._ciorna_schimbata()
                voce.spune(str(v), intrerupe=True)
                return
            if foc is self.w_instr and not e.AltDown() and not e.ControlDown() and kc in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                it = foc.GetSelection()
                if it.IsOk():
                    if foc.ItemHasChildren(it):
                        foc.Collapse(it) if foc.IsExpanded(it) else foc.Expand(it)
                    else:
                        self._alege_sunet_scriere(it)
                return
        if foc in (self.w_dr, self.w_st):
            if e.ControlDown() and e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.scriere_asculta(masura=True)
                return
            simplu = not (e.ControlDown() or e.AltDown() or e.ShiftDown())
            if simplu and e.GetKeyCode() == wx.WXK_SPACE and self._scriere_masura_plina(foc):
                return
            if simplu and e.GetKeyCode() == wx.WXK_RIGHT:
                self._scriere_sageata_dreapta(foc)
            if e.GetKeyCode() == wx.WXK_F2 and e.ControlDown():
                self.scriere_spune_masura()          # Control F2 (F2 singur e ajutorul la taste)
                return
        if self._pagina() is self.p_auz and (foc is None or self._e_in(foc, self.p_auz) or foc is self.carte):
            sc = (e.GetRawKeyFlags() >> 16) & 0xFF if os.name == 'nt' else 0
            if self.auz_set.exercitiu == 4 and self._ap_tasta(e, foc, sc):
                return
            if e.AltDown() and not e.ControlDown() and (e.GetKeyCode() == ord('E') or sc == 0x12):
                # Alt E: la răspunsuri (la durate, la câmpul în care le scrii)
                (self.a_text if self.auz_set.exercitiu == 3 else self.a_rasp).SetFocus(); return
            scrie = isinstance(foc, wx.TextCtrl) and foc.IsEditable() or isinstance(foc, wx.SpinCtrl) or \
                (foc is not None and isinstance(foc.GetParent(), wx.SpinCtrl))
            if not scrie and not e.AltDown() and not e.ControlDown():
                if e.GetKeyCode() == ord(',') or sc == 0x33:
                    self.auz_asculta(); return            # virgulă: ascultă din nou
                if e.GetKeyCode() == ord('.') or sc == 0x34:
                    self.auz_nou(); return                # punct: exercițiu nou
            if foc is self.a_rasp and e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.auz_raspunde(); return
            if foc is self.a_text and e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.auz_raspunde_text(); return
        if foc is not None and foc.GetParent() in (self.p_setari, self.p_scriere, self.p_auz, self.p_fisiere):
            e.Skip()                     # în fila Setări tastele lucrează normal (bife, câmpuri, butoane)
            return
        if isinstance(foc, (wx.TextCtrl, wx.SpinCtrl)) and (not isinstance(foc, wx.TextCtrl) or foc.IsEditable()) or e.AltDown():
            e.Skip()
            return
        k = e.GetKeyCode()
        r = e.GetRawKeyCode() if os.name == 'nt' else 0          # codul tastei virtuale
        sc = (e.GetRawKeyFlags() >> 16) & 0xFF if os.name == 'nt' else 0   # codul fizic al tastei
        shift, ctrl = e.ShiftDown(), e.ControlDown()
        minus = sc in (0x0C, 0x4A) or r in (0xBD, 0x6D) or k in (wx.WXK_NUMPAD_SUBTRACT, ord('_')) or (k == ord('-') and not r)
        plus = sc in (0x0D, 0x4E) or r in (0xBB, 0x6B) or k in (wx.WXK_NUMPAD_ADD, ord('+')) or (k == ord('=') and not r)
        if shift and (minus or plus):
            self.schimba_volum_metronom((5 if ctrl else 1) * (1 if plus else -1))
            return
        if not ctrl:
            if shift and (k == ord('1') or r == 0x31):
                self.schimba_tempo(-5); return
            if shift and (k == ord('2') or r == 0x32):
                self.schimba_tempo(5); return
            if shift and (k in (ord('3'), ord('0')) or r in (0x33, 0x30)):
                self.schimba_tempo(0); return
            if k == ord('K') or r == 0x4B:
                if shift:
                    self.reda(False)
                else:
                    self.reda_sau_pauza()
                return
            if not shift and (k == ord('I') or r == 0x49):
                self.reda(True); return
            if not shift and (k == ord('L') or r == 0x4C):
                self.muta(1); return
            if not shift and (k == ord('J') or r == 0x4A):
                self.muta(-1); return
        e.Skip()

    def comuta_bucla(self, e=None):
        self.redare.bucla = self.m_bucla.IsChecked()
        self.SetStatusText(_('Redare în buclă pornită.') if self.redare.bucla else _('Redare în buclă oprită.'))

    # ---------------- din PDF în Braille ----------------
    def pdf_in_braille(self, e=None):
        with wx.FileDialog(self, _('Alege PDF-ul sau poza cu partitura'), defaultDir=self.setari.get('folder', ''),
                           wildcard=_('PDF și imagini|*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff|Toate partiturile|') +
                           ';'.join('*' + x for x in partitura.TOATE_FORMATELE),
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as d:
            if d.ShowModal() == wx.ID_OK:
                self.deschide(d.GetPath(), brf=True)

    # ---------------- citește din fereastră ----------------
    def _tasta_globala(self):
        """Control+Alt+P funcționează din orice aplicație: citește pagina din fereastra din față."""
        if os.name != 'nt':
            return
        try:
            if self.RegisterHotKey(ID_TASTA_GLOBALA, wx.MOD_CONTROL | wx.MOD_ALT, ord('P')):
                self.Bind(wx.EVT_HOTKEY, self._la_tasta_globala, id=ID_TASTA_GLOBALA)
        except Exception:
            pass

    def _la_tasta_globala(self, e):
        hwnd, titlu = captura.fereastra_din_fata()
        if not hwnd or hwnd == self.GetHandle():
            self.alege_fereastra()
            return
        self.citeste_fereastra(hwnd, titlu, deja_in_fata=True)

    def alege_fereastra(self, e=None):
        lista = [(h, t) for h, t in captura.ferestre() if h != self.GetHandle()]
        if not lista:
            self.mesaj(_('Nu găsesc alte ferestre deschise. Deschide partitura în aplicația editurii și încearcă din nou.'), _('Citește din fereastră'))
            return
        d = wx.SingleChoiceDialog(self, _('Alege fereastra cu partitura. Mărește pagina cât poți în aplicația aceea, '
                                  'ca recunoașterea să fie mai bună. Data viitoare poți apăsa Control Alt P direct din ea.'),
                                  _('Citește din fereastră'), [t for _, t in lista])
        if d.ShowModal() == wx.ID_OK:
            h, t = lista[d.GetSelection()]
            d.Destroy()
            self.citeste_fereastra(h, t)
        else:
            d.Destroy()

    def citeste_fereastra(self, hwnd, titlu, deja_in_fata=False):
        if not deja_in_fata:
            captura.aduce_in_fata(hwnd)
            wx.MilliSleep(700)
        try:
            cale = captura.poza(hwnd)
        except Exception as ex:
            self.Raise()
            self.mesaj(_('Nu am putut face poza paginii. {0}', ex), _('Citește din fereastră'))
            return
        self.Raise()
        self.deschide(cale, pastreaza=False, titlu=_('Pagina din {0}', titlu), dupa=lambda: captura.sterge(cale))

    # ---------------- salvare ----------------
    def _cere_salvare(self, titlu, nume, filtru):
        """Tot ce exporți merge singur în Documente\\Music Box, fără fereastră de salvare (cerut de Răzvan).
        Un fișier cu același nume se înlocuiește, ca să fie mereu ultima variantă."""
        nume = ''.join(ch for ch in nume if ch not in '\\/:*?"<>|')
        return os.path.join(limba.folder_documente(), nume)

    def _anunta_salvat(self, cale):
        self.SetStatusText(_('Salvat: ') + cale)
        voce.spune(_('Salvat în Documente, în folderul Music Box: {0}.', os.path.basename(cale)), intrerupe=True)

    def _interzis_salvare(self):
        if getattr(self.P, 'fara_salvare', False):
            self.mesaj(_('Pagina aceasta e citită din aplicația editurii, așa că nu se salvează. O poți citi aici în cuvinte și în Braille.'),
                       _('Nu se salvează'))
            return True
        return False

    def _baza(self):
        return self.P.titlu if self.P else 'partitura'

    def salveaza_cuvinte(self, e=None):
        if self._pagina() is self.p_scriere:
            self._salveaza_ciorna(spune=True)           # în fila Scrie, Control S salvează partitura la care lucrezi
            return
        if not self.P or self._interzis_salvare():
            return
        cale = self._cere_salvare(_('Salvează textul în cuvinte'), self._baza() + '.txt', _('Text (*.txt)|*.txt'))
        if cale:
            with open(cale, 'w', encoding='utf-8-sig') as f:
                f.write(self.P.descriere_generala() + '\n\n' + self.t_cuvinte.GetValue())
            self._anunta_salvat(cale)

    def salveaza_braille(self, brf):
        if not self.P or self._interzis_salvare():
            return
        cale = self._cere_salvare(_('Salvează Braille'), self._baza() + ('.brf' if brf else ' braille.txt'),
                                  _('Braille pentru imprimantă (*.brf)|*.brf') if brf else _('Text Unicode (*.txt)|*.txt'))
        if not cale:
            return
        s = self.selectie() or (self.P.numere[0], self.P.numere[-1], list(range(len(self.P.portative))))
        wait = wx.BusyInfo(_('Se pregătește Braille...'), self)
        try:
            txt = braille.din_scor(self.P.extrage(*s), final=s[1] == self.P.numere[-1])
        finally:
            del wait
        if brf:
            with open(cale, 'w', encoding='ascii', errors='replace', newline='') as f:
                f.write(braille.la_brf(txt))
        else:
            with open(cale, 'w', encoding='utf-8') as f:
                f.write(txt)
        self._anunta_salvat(cale)

    def salveaza_musicxml(self, e=None):
        if not self.P or self._interzis_salvare():
            return
        cale = self._cere_salvare(_('Salvează ca MusicXML'), self._baza() + '.musicxml', _('MusicXML (*.musicxml)|*.musicxml'))
        if cale:
            s = self.selectie() or (self.P.numere[0], self.P.numere[-1], list(range(len(self.P.portative))))
            self.P.extrage(*s).write('musicxml', fp=cale)
            self._anunta_salvat(cale)


    # ---------------- altele ----------------
    def alege_program(self, care):
        nume = {'audiveris': 'Audiveris', 'musescore': 'MuseScore', 'homr': 'homr'}[care]
        with wx.FileDialog(self, _('Unde e {0}.exe', nume), wildcard=_('Programe (*.exe;*.bat)|*.exe;*.bat'), style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as d:
            if d.ShowModal() == wx.ID_OK:
                self.setari[care] = d.GetPath()
                recunoastere.SETARI[care] = d.GetPath()
                scrie_setari(self.setari)
                self.SetStatusText(f'{nume}: {d.GetPath()}')

    def mesaj(self, text, titlu):
        d = DialogText(self, titlu, text)
        d.ShowModal()
        d.Destroy()

    def _anunta_versiunea_noua(self):
        """După o actualizare, la prima pornire, spune versiunea nouă."""
        vechi = self.setari.get('versiune_vazuta')
        if (vechi and vechi != VERSIUNE) or '--actualizat' in sys.argv:
            self.SetStatusText(_('{0} s-a actualizat la versiunea {1}.', NUME, VERSIUNE))
            voce.spune(_('100 la sută. Actualizare terminată.'))
        if vechi != VERSIUNE:
            self.setari['versiune_vazuta'] = VERSIUNE
            scrie_setari(self.setari)

    def verifica_actualizari(self, manual=False):
        if not actualizare.instalat():
            if manual:
                self.mesaj(_('Actualizarea automată merge doar la programul instalat cu programul de instalare.'), _('Actualizări'))
            return
        if getattr(self, '_actualizare_in_curs', False):
            if manual:
                voce.spune(_('Actualizarea e deja în curs.'))
            return

        def lucru():
            try:
                v = actualizare.versiune_noua()
                if not v:
                    if manual:
                        wx.CallAfter(self.mesaj, _('Ai deja ultima versiune, {0}.', VERSIUNE), _('Actualizări'))
                    return
                if not actualizare.doar_eu():
                    # programul e deschis și în altă fereastră, care face deja actualizarea
                    if manual:
                        voce.spune(_('Actualizarea e deja în curs.'))
                    return
                self._actualizare_in_curs = True
                voce.spune(_('Se actualizează.'))
                wx.CallAfter(self._arata_progres, v, _('Se actualizează.'))
                ultimul = [0]

                # NVDA spune doar procentul total, din 10 în 10: descărcarea e prima jumătate (0–50),
                # instalarea (spusă de programul de instalare) a doua (50–100).
                def progres(descarcat, total):
                    if total <= 0:
                        return
                    procent = min(50, descarcat * 50 // total)
                    wx.CallAfter(self._progres, procent)
                    zece = procent // 10 * 10
                    if zece > ultimul[0]:
                        ultimul[0] = zece
                        voce.spune(_('{0} la sută.', zece))

                cale = actualizare.descarca_setup(v, progres)
                wx.CallAfter(self._instaleaza, v, cale)
            except Exception as ex:
                self._actualizare_in_curs = False
                wx.CallAfter(self._inchide_progres)
                if manual or getattr(self, '_dlg_progres', None) is not None:
                    voce.spune(_('Actualizarea nu a reușit.'))
                    wx.CallAfter(self.mesaj, _('Nu am putut descărca actualizarea. Verifică internetul. ({0})', ex), _('Actualizări'))
        threading.Thread(target=lucru, daemon=True).start()

    def _arata_progres(self, v, text):
        self._dlg_progres = DialogProgres(self, _('Actualizare la versiunea {0}', v), text)
        self._dlg_progres.Show()
        self.SetStatusText(text)

    def _progres(self, procent):
        text = _('Se actualizează: {0} la sută.', procent)
        self.SetStatusText(text)
        d = getattr(self, '_dlg_progres', None)
        if d:
            d.arata(procent, text)

    def _inchide_progres(self):
        d = getattr(self, '_dlg_progres', None)
        self._dlg_progres = None
        if d:
            d.Destroy()

    def _instaleaza(self, v, cale):
        # fără întrebări: programul se închide, instalarea continuă procentele și îl redeschide
        self._inchide_progres()
        try:
            actualizare.porneste_setup(cale)
            self._inchis_pentru_actualizare = True
            self.Close()
            # dacă ceva ține programul deschis, îl închidem de tot, ca instalarea să poată înlocui fișierele
            t = threading.Timer(4.0, os._exit, [0])
            t.daemon = True
            t.start()
        except Exception as ex:
            self._actualizare_in_curs = False
            self.mesaj(_('Nu am putut porni actualizarea: {0}', ex), _('Actualizări'))

    def _sunet_iesire_schimbat(self, e=None):
        self.setari['sunet_iesire'] = self.s_sunet_iesire.GetValue()
        scrie_setari(self.setari)

    def la_inchidere(self, e):
        self.redare.opreste()
        self.player_audio.opreste()
        self.p_fisiere.melodie.opreste()
        self.p_metronom.opreste(tacut=True)
        self.midi.inchide()
        self.sint.inchide()
        if getattr(self, '_ciorna_amanata', None):
            self._ciorna_amanata.Stop()
            self._salveaza_ciorna()
        if os.name == 'nt':
            try:
                self.UnregisterHotKey(ID_TASTA_GLOBALA)
            except Exception:
                pass
        self.setari['optiuni'] = {**self.optiuni().__dict__, 'v2': True}
        scrie_setari(self.setari)
        # sunetul de ieșire: fereastra dispare întâi, apoi se aude melodia (nu și la închiderea pentru actualizare)
        if self.setari.get('sunet_iesire', True) and not getattr(self, '_inchis_pentru_actualizare', False) \
                and '--autotest' not in sys.argv:
            self.Hide()
            sunet_iesire.canta()
        e.Skip()


ID_TASTA_GLOBALA = 0x5250


class ListaBife(wx.ListCtrl):
    """Listă cu căsuțe de bifat (controlul listă din Windows: NVDA spune „bifat” / „nebifat”, bifezi cu spațiu).
    Primul rând e „Toate”: bifat, le bifează pe toate; debifat, le debifează. Indicii (Check, GetCheckedItems,
    SetString) sunt ai elementelor adevărate, fără „Toate”. la_schimbare() se cheamă după fiecare bifă."""
    def __init__(self, parinte, choices, name, size=(-1, -1), la_schimbare=None):
        super().__init__(parinte, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL, size=size, name=name)
        self.AppendColumn(name, width=320)
        self.EnableCheckBoxes(True)
        self.Append([_('Toate')])
        for c in choices:
            self.Append([c])
        self.Focus(0)
        self._ocupat = False
        self.la_schimbare = la_schimbare
        self.Bind(wx.EVT_LIST_ITEM_CHECKED, self._bifat)
        self.Bind(wx.EVT_LIST_ITEM_UNCHECKED, self._bifat)

    def _bifat(self, e):
        if self._ocupat:
            return
        self._ocupat = True
        try:
            i = e.GetIndex()
            n = self.GetItemCount()
            if i == 0:
                stare = self.IsItemChecked(0)
                for k in range(1, n):
                    self.CheckItem(k, stare)
            else:
                self.CheckItem(0, all(self.IsItemChecked(k) for k in range(1, n)))
        finally:
            self._ocupat = False
        if self.la_schimbare:
            self.la_schimbare()

    def GetCount(self):
        return self.GetItemCount() - 1

    def Check(self, i, bifat=True):
        self._ocupat = True
        try:
            self.CheckItem(i + 1, bifat)
            n = self.GetItemCount()
            self.CheckItem(0, n > 1 and all(self.IsItemChecked(k) for k in range(1, n)))
        finally:
            self._ocupat = False

    def GetCheckedItems(self):
        return [i - 1 for i in range(1, self.GetItemCount()) if self.IsItemChecked(i)]

    def SetString(self, i, text):
        self.SetItemText(i + 1, text)


class DialogText(wx.Dialog):
    """Mesaj citibil rând cu rând (un câmp de text), cu buton OK."""
    def __init__(self, parinte, titlu, text):
        super().__init__(parinte, title=titlu, size=(640, 420))
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(self, label=titlu), 0, wx.ALL, 6)
        t = wx.TextCtrl(self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, name=titlu)
        s.Add(t, 1, wx.EXPAND | wx.ALL, 6)
        b = wx.Button(self, wx.ID_OK, _('OK'))
        s.Add(b, 0, wx.ALIGN_RIGHT | wx.ALL, 6)
        self.SetSizer(s)
        self.SetEscapeId(wx.ID_OK)
        t.SetFocus()


class PaginaPlayer(wx.Panel):
    """Fila Player: toată piesa de la prima măsură până la capăt, ca pe YouTube.
    K pornește, pune pauză, continuă; J și L derulează câte 5 secunde; Home de la început; Escape oprește."""
    PAS = 5000

    def __init__(self, carte, fereastra):
        super().__init__(carte)
        self.f = fereastra
        s = wx.BoxSizer(wx.VERTICAL)
        # un singur rând, fără etichetă: NVDA spune doar piesa (scurtăturile sunt la F1)
        self.t = wx.TextCtrl(self, style=wx.TE_READONLY, name='', value=_('Nicio piesă deschisă.'))
        self._inreg = {'cheie': None, 'gata': False, 'procent': 0, 'eroare': None}
        self._porneste_dupa = False
        self._terminat = False
        self._harta_audio = []
        s.Add(self.t, 0, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(s)

    def reimprospateaza(self):
        """Arată piesa deschisă (sau că nu e niciuna)."""
        P = self.f.P
        self.t.SetValue(P.titlu if P else _('Nicio piesă deschisă.'))

    @property
    def sel(self):
        P = self.f.P
        return (id(P), P.numere[0], P.numere[-1], tuple(range(len(P.portative))))

    def _al_meu(self):
        """Ce se cântă acum e piesa întreagă pornită din player (nu o măsură pornită cu K din altă filă)."""
        return self.f.redare.stare != 'oprit' and self.f._redat and self.f._redat[0] == self.sel

    def _porneste(self, ms, in_pauza=False):
        try:
            self.f._porneste(self.sel, ms, in_pauza)
            self._lung = self._lungime()
        except Exception as ex:
            traceback.print_exc()
            self.t.SetValue(_('Nu am putut reda. Eroare: {0}', ex))

    def _lungime(self):
        """Cât durează piesa, în milisecunde (ținută minte, ca să se știe și după ce s-a terminat)."""
        try:
            n = int(self.f.redare._mci(f'status {redare._ALIAS} length') or 0) if self.f.redare.stare != 'oprit' else 0
        except Exception:
            n = 0
        return n or getattr(self, '_lung', 0)

    @staticmethod
    def _timp(ms):
        sec = max(0, int(ms // 1000))
        return f'{sec // 60}:{sec % 60:02d}'

    def _unde(self, ms, spune=False):
        """„1:05 din 3:20, măsura 12”: scris în player; NVDA îl spune doar la I."""
        text = _('{0} din {1}', self._timp(ms), self._timp(self._lungime()))
        harta = getattr(self.f, '_harta', [])
        nr = [n for t, n in harta if t <= ms + 50]
        if nr:
            text += ', ' + (_('Anacruza') if nr[-1] == 0 else _('Măsura {0}', nr[-1]).lower())
        self.t.SetValue(text)
        if spune:
            voce.spune(text, intrerupe=True)

    def tasta(self, e):
        """Tastele playerului; întoarce True dacă a folosit tasta."""
        k = e.GetKeyCode()
        sc = (e.GetRawKeyFlags() >> 16) & 0xFF if os.name == 'nt' else 0
        if k == wx.WXK_TAB and not e.ControlDown() and not e.AltDown():
            # în player nu e nimic altceva de ales: Tab rămâne aici (nu trece la măsuri și opțiuni)
            voce.spune(self.t.GetValue(), intrerupe=True)
            return True
        if e.ControlDown() or e.AltDown() or e.ShiftDown():
            return False
        if not self.f.P:
            if k in (ord('K'), ord('J'), ord('L'), wx.WXK_SPACE) or sc in (0x25, 0x24, 0x26):
                voce.spune(_('Deschide întâi o partitură.'), intrerupe=True)
                return True
            return False
        if self._audio():
            return self._tasta_audio(k, sc)
        r = self.f.redare
        if r.stare != 'oprit' and not self._al_meu():
            r.opreste()                           # se cânta altceva (o măsură): playerul pornește piesa întreagă
        if k == wx.WXK_ESCAPE:
            if r.stare != 'oprit':
                r.opreste()
                voce.spune(_('Oprit.'), intrerupe=True)
                return True
            return False
        if k == ord('K') or sc == 0x25 or k == wx.WXK_SPACE:
            terminat_inainte = r.stare != 'oprit' and r.terminat()
            if r.stare == 'oprit' or terminat_inainte:
                self._porneste(0)
            else:
                r.pauza_continua()             # fără să spună nimic (cerut de Răzvan)
            return True
        if k == ord('I') or sc == 0x17:
            # I: unde ești (minutul și secunda din cât ține piesa, și măsura)
            self._unde(r.pozitie() if r.stare != 'oprit' else 0, spune=True)
            return True
        if k in (ord('J'), ord('L')) or sc in (0x24, 0x26):
            inainte = k == ord('L') or sc == 0x26
            terminat = r.terminat()
            poz = r.pozitie() if not terminat else (0 if inainte else getattr(self, '_lung', 0))
            if r.stare == 'oprit':
                self._porneste(0, in_pauza=True)       # piesa se pregătește în pauză; K o pornește
            lung = self._lungime()
            nou = poz + (self.PAS if inainte else -self.PAS)
            nou = max(0, min(nou, max(0, lung - 200)))
            r.sari(nou)
            self._unde(nou)
            return True
        if k == wx.WXK_HOME:
            if r.stare == 'oprit':
                self._porneste(0)
            else:
                r.sari(0)
            self._unde(0)
            return True
        return False


    # ---------------- playerul cu înregistrare (nucleu\inregistrare.py) ----------------
    def _audio(self):
        """Înregistrarea se poate face doar cu FluidSynth și banca de sunete; altfel playerul merge ca înainte."""
        return os.name == 'nt' and sunete.exista()

    def pregateste(self):
        """La deschiderea unei partituri: face înregistrarea piesei întregi, în fundal."""
        self.f.player_audio.incarca(None)
        self._inreg = {'cheie': None, 'gata': False, 'procent': 0, 'eroare': None}
        self._porneste_dupa = False
        self._terminat = False
        if not self.f.P or not self._audio():
            return
        cheie = self.sel
        self._inreg['cheie'] = cheie
        wx.CallLater(300, self._pregateste_midi, cheie)

    def _pregateste_midi(self, cheie):
        if not self.f.P or self.sel != cheie or self._inreg['cheie'] != cheie:
            return
        try:
            date, batai, masuri = self.f._midi_pentru(cheie)
            ms_batai = redare.milisecunde(date, [q for q, _p in batai]) if batai else []
            momente = list(zip(ms_batai, [p for _q, p in batai]))
            harta = list(zip(redare.milisecunde(date, [q for q, _n in masuri]), [n for _q, n in masuri])) if masuri else []
            # fiecare mână (portativ) separat, ca să poți asculta doar una (tasta M)
            pe_maini = []
            if len(cheie[3]) > 1:
                for i in cheie[3]:
                    pe_maini.append(self.f._midi_pentru((cheie[0], cheie[1], cheie[2], (i,)))[0])
                self.f._midi_pentru(cheie)            # cache-ul rămâne la piesa întreagă
        except Exception as ex:
            traceback.print_exc()
            self._inreg['eroare'] = str(ex)
            return

        def progres(p):
            self._inreg['procent'] = p

        def lucru():
            try:
                oprit = lambda: self._inreg.get('cheie') != cheie
                piste = []
                if pe_maini:
                    for k, d in enumerate(pe_maini):
                        x = inregistrare.randeaza(d, lambda q, k=k: progres(int((k * 100 + q) / len(pe_maini))), oprit=oprit,
                                                  normalizeaza=False)
                        if x is None:
                            return
                        piste.append(x)
                    sunet, piste = inregistrare.pe_maini(piste)
                else:
                    sunet = inregistrare.randeaza(date, progres, oprit=oprit)
                met = inregistrare.pista_metronom(len(sunet), momente) if sunet is not None else None
                wx.CallAfter(self._gata, cheie, sunet, met, harta, None, piste)
            except Exception as ex:
                traceback.print_exc()
                wx.CallAfter(self._gata, cheie, None, None, harta, str(ex), [])
        threading.Thread(target=lucru, daemon=True).start()

    def _gata(self, cheie, sunet, met, harta, eroare, piste=()):
        if self._inreg.get('cheie') != cheie:
            return
        if eroare or sunet is None:
            self._inreg['eroare'] = eroare or ''
            return
        pa = self.f.player_audio
        pa.incarca(sunet, met, list(piste))
        pa.la_sfarsit = lambda: setattr(self, '_terminat', True)
        self._harta_audio = harta
        self._inreg['gata'] = True
        self.aplica()
        if self._porneste_dupa:
            self._porneste_dupa = False
            if self.f._pagina() is self:
                self.f.redare.opreste()
                pa.canta(0)

    def aplica(self):
        """Tempoul (Shift 1, 2, 3) și metronomul (Control Shift M, volumul) se schimbă pe loc în înregistrare."""
        pa = self.f.player_audio
        pa.viteza = max(0.2, self.f.procent / 100)
        pa.volum_metronom = (self.f.volum_metronom / 100) if self.f.metronom else 0.0

    def _unde_audio(self, ms, spune=False):
        """Timpul spus e cel adevărat, la tempoul de acum (la 50%, piesa ține de două ori mai mult)."""
        pa = self.f.player_audio
        v = pa.viteza or 1.0
        text = _('{0} din {1}', self._timp(ms / v), self._timp(pa.lungime() / v))
        nr = [n for t, n in getattr(self, '_harta_audio', []) if t <= ms + 50]
        if nr:
            text += ', ' + (_('Anacruza') if nr[-1] == 0 else _('Măsura {0}', nr[-1]).lower())
        self.t.SetValue(text)
        if spune:
            voce.spune(text, intrerupe=True)

    def _tasta_audio(self, k, sc):
        pa = self.f.player_audio
        inreg = getattr(self, '_inreg', None) or {}
        taste_player = k in (ord('K'), ord('J'), ord('L'), ord('I'), ord('M'), wx.WXK_SPACE, wx.WXK_HOME, wx.WXK_ESCAPE) or \
            sc in (0x25, 0x24, 0x26, 0x17, 0x32)
        if not taste_player:
            return False
        if k == wx.WXK_ESCAPE:
            self._porneste_dupa = False
            if pa.stare != 'oprit':
                pa.opreste()
                voce.spune(_('Oprit.'), intrerupe=True)
                return True
            return False
        if not inreg.get('gata'):
            if inreg.get('eroare') is not None:
                voce.spune(_('Înregistrarea piesei nu s-a putut face. Eroare: {0}', inreg['eroare']), intrerupe=True)
                return True
            if inreg.get('cheie') is None:
                self.pregateste()
            if k == ord('K') or sc == 0x25 or k == wx.WXK_SPACE:
                self._porneste_dupa = True
            voce.spune(_('Se pregătește înregistrarea piesei, {0} la sută. Pornește singură când e gata.', inreg.get('procent', 0))
                       if self._porneste_dupa else _('Se pregătește înregistrarea piesei, {0} la sută.', inreg.get('procent', 0)),
                       intrerupe=True)
            return True
        self.f.redare.opreste()                    # dacă se cânta ceva din fila 1
        self.aplica()
        if k == ord('M') or sc == 0x32:
            # M: ce se aude — toate mâinile, apoi fiecare mână (portativ) pe rând
            if not pa.piste:
                voce.spune(_('Partitura are un singur portativ.'), intrerupe=True)
                return True
            pa.alese = 0 if pa.alese is None else (pa.alese + 1 if pa.alese + 1 < len(pa.piste) else None)
            P = self.f.P
            if pa.alese is None:
                text = _('Ambele mâini.') if len(pa.piste) == 2 else _('Toate portativele.')
            else:
                text = (P.portative[pa.alese].nume if P and pa.alese < len(P.portative) else str(pa.alese + 1)) + '.'
            voce.spune(text, intrerupe=True)
            return True
        if k == ord('K') or sc == 0x25 or k == wx.WXK_SPACE:
            if pa.stare == 'oprit':
                self._terminat = False
                pa.canta(0)
            else:
                pa.pauza_continua()                # fără să spună nimic
            return True
        if k == ord('I') or sc == 0x17:
            ms = pa.pozitie() if pa.stare != 'oprit' else (pa.lungime() if self._terminat else 0)
            self._unde_audio(ms, spune=True)
            return True
        if k in (ord('J'), ord('L')) or sc in (0x24, 0x26):
            inainte = k == ord('L') or sc == 0x26
            if pa.stare == 'oprit':
                poz = pa.lungime() if (self._terminat and not inainte) else 0
                self._terminat = False
                pa.canta(poz, in_pauza=True)
            else:
                poz = pa.pozitie()
            pas = self.PAS * pa.viteza                 # 5 secunde adevărate, la tempoul de acum
            nou = poz + (pas if inainte else -pas)
            nou = int(max(0, min(nou, max(0, pa.lungime() - 200))))
            pa.sari(nou)
            self._unde_audio(nou)
            return True
        if k == wx.WXK_HOME:
            if pa.stare == 'oprit':
                self._terminat = False
                pa.canta(0)
            else:
                pa.sari(0)
            self._unde_audio(0)
            return True
        return False


class PaginaFisiere(scrolled.ScrolledPanel):
    """Fila Fișiere audio. Fiecare folder de sus e un loc la Tab (NVDA spune doar numele lui). Acolo:
    săgeata stânga/dreapta trece prin folder și subfolderele lui (NVDA spune numele), săgeata jos/sus prin fișiere,
    fără ca NVDA să spună ceva (fișierul doar se aude, imediat); spațiu spune numele și „2 din 15”."""
    NUME_MOD = {'urmatoarea': _('La sfârșit trece la următoarea.'), 'repeta': _('La sfârșit repetă piesa.'),
                'opreste': _('La sfârșit se oprește.')}

    def __init__(self, carte, fereastra):
        super().__init__(carte)
        self.f = fereastra
        self.melodie = fisiere_audio.Melodie()
        self.melodie.la_sfarsit = lambda: wx.CallAfter(self._sfarsit)
        self.melodie.volum = int(fereastra.setari.get('volum_muzica', 100))
        self.mod = fereastra.setari.get('mod_audio', 'urmatoarea')
        if self.mod not in fisiere_audio.MODURI:
            self.mod = 'urmatoarea'
        self.s = wx.BoxSizer(wx.VERTICAL)
        self.zona = wx.BoxSizer(wx.VERTICAL)
        self.s.Add(self.zona, 0, wx.EXPAND)
        self.b_folder = wx.Button(self, label=_('Alege folderul...'))
        self.b_folder.Bind(wx.EVT_BUTTON, lambda e: self.alege())
        self.s.Add(self.b_folder, 0, wx.ALL, 3)
        self.t = wx.TextCtrl(self, style=wx.TE_READONLY, name=_('Starea'))
        self.s.Add(self.t, 0, wx.EXPAND | wx.ALL, 3)
        self.SetSizer(self.s)
        self.SetupScrolling(scroll_x=False)
        self.butoane = []          # câte un buton pentru fiecare folder de sus
        self.locuri = {}           # buton -> {'foldere': [(nume, cale, fișiere)], 'f': indice folder, 'i': indice fișier}
        self._amanat = None
        self._canta_buton = None
        self.umple(fereastra.setari.get('folder_audio', ''))

    def de_focus(self):
        return self.butoane[0] if self.butoane else self.b_folder

    # ---- folderele ----
    def umple(self, folder):
        self.melodie.opreste()
        self.zona.Clear()
        for b in self.butoane:
            b.Destroy()
        self.butoane, self.locuri = [], {}
        self.folder = folder if folder and os.path.isdir(folder) else ''
        if not self.folder:
            self.t.SetValue(_('Niciun folder ales. Apasă Alege folderul.'))
            self.Layout()
            return
        dirs, fis = fisiere_audio.continut(self.folder)
        sus = ([self.folder] if fis else []) + dirs
        for d in sus:
            foldere = fisiere_audio.cu_subfoldere(d)
            b = wx.Button(self, label=os.path.basename(d) or d, name=os.path.basename(d) or d)
            b.Bind(wx.EVT_BUTTON, lambda e: None)          # spațiul și Enter le prinde fereastra
            self.zona.Add(b, 0, wx.EXPAND | wx.ALL, 2)
            b.MoveBeforeInTabOrder(self.b_folder)         # folderele întâi la Tab, apoi Alege folderul
            self.butoane.append(b)
            self.locuri[b] = {'foldere': foldere, 'f': 0, 'i': -1}
        self.t.SetValue(_('Folderul: {0}.', self.folder) + ' ' + self.NUME_MOD[self.mod])
        self.Layout()
        self.SetupScrolling(scroll_x=False, scrollToTop=False)

    def alege(self):
        dlg = wx.DirDialog(self, _('Alege folderul cu fișiere audio'), self.folder or os.path.expanduser('~'))
        if dlg.ShowModal() == wx.ID_OK:
            self.f.setari['folder_audio'] = dlg.GetPath()
            scrie_setari(self.f.setari)
            self.umple(dlg.GetPath())
            self.de_focus().SetFocus()
        dlg.Destroy()

    def _loc(self, b):
        loc = self.locuri[b]
        nume, cale, fisiere = loc['foldere'][loc['f']]
        return loc, nume, fisiere

    # ---- sunetul ----
    def _canta(self, b):
        self._amanat = None
        loc, _n, fisiere = self._loc(b)
        if not (0 <= loc['i'] < len(fisiere)):
            return
        cale = fisiere[loc['i']]
        self.f.redare.opreste()                         # dacă se cânta ceva din fila 1
        if self.f.player_audio.stare == 'canta':
            self.f.player_audio.pauza_continua()
        try:
            self.melodie.deschide_si_canta(cale)
            self._canta_buton = b
            self.t.SetValue(os.path.basename(cale))
        except Exception as ex:
            self.t.SetValue(_('Fișierul nu se poate cânta: {0}', ex))
            voce.spune(_('Nu se poate cânta.'), intrerupe=True)

    def _muta(self, b, pas):
        loc, _n, fisiere = self._loc(b)
        if not fisiere:
            voce.spune(_('Niciun fișier audio aici.'), intrerupe=True)
            return
        nou = loc['i'] + pas if loc['i'] >= 0 else (0 if pas > 0 else len(fisiere) - 1)
        if not (0 <= nou < len(fisiere)):
            return                                       # la capăt: rămâne unde e, fără să spună nimic
        loc['i'] = nou
        if self._amanat:
            self._amanat.Stop()
        self._amanat = wx.CallLater(90, self._canta, b)   # la săgeata ținută apăsată nu pornește fiecare

    def _spune(self, b):
        loc, nume, fisiere = self._loc(b)
        if 0 <= loc['i'] < len(fisiere):
            n = os.path.splitext(os.path.basename(fisiere[loc['i']]))[0]
            voce.spune(_('{0}, {1} din {2}', n, loc['i'] + 1, len(fisiere)), intrerupe=True)
        else:
            voce.spune(_('{0}: {1} fișiere.', nume, len(fisiere)), intrerupe=True)

    def _schimba_folder(self, b, pas):
        loc = self.locuri[b]
        n = len(loc['foldere'])
        loc['f'] = (loc['f'] + pas) % n
        loc['i'] = -1
        _l, nume, fisiere = self._loc(b)
        b.SetLabel(nume)
        voce.spune(nume, intrerupe=True)

    def _sfarsit(self):
        b = self._canta_buton
        if b is None or b not in self.locuri:
            return
        if self.mod == 'repeta':
            try:
                self.melodie.de_la_capat()
            except Exception:
                pass
        elif self.mod == 'urmatoarea':
            loc, _n, fisiere = self._loc(b)
            if loc['i'] + 1 < len(fisiere):
                loc['i'] += 1
                self._canta(b)

    def volum(self, e):
        """Control Home mai tare, Control End mai încet, cu câte 10 la sută. Întoarce True dacă a folosit tasta."""
        if e.ControlDown() and not e.AltDown() and not e.ShiftDown() and e.GetKeyCode() in (wx.WXK_HOME, wx.WXK_END):
            v = self.melodie.schimba_volum(10 if e.GetKeyCode() == wx.WXK_HOME else -10)
            self.f.setari['volum_muzica'] = v
            scrie_setari(self.f.setari)
            voce.spune(_('Volum {0} la sută.', v), intrerupe=True)
            return True
        return False

    def tasta(self, e, b):
        """Tastele pe un folder; întoarce True dacă a folosit tasta."""
        if self.volum(e):
            return True
        if e.ControlDown() or e.AltDown():
            return False
        k = e.GetKeyCode()
        sc = (e.GetRawKeyFlags() >> 16) & 0xFF if os.name == 'nt' else 0
        m = self.melodie
        try:
            if k in (wx.WXK_DOWN, wx.WXK_UP) and not e.ShiftDown():
                self._muta(b, 1 if k == wx.WXK_DOWN else -1)
                return True
            if k in (wx.WXK_LEFT, wx.WXK_RIGHT) and not e.ShiftDown():
                self._schimba_folder(b, 1 if k == wx.WXK_RIGHT else -1)
                return True
            if k == wx.WXK_SPACE and not e.ShiftDown():
                self._spune(b)
                return True
            if k in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                return True                              # Enter nu „apasă” butonul
            if k == ord('K') or sc == 0x25:
                if e.ShiftDown():
                    if m.cale:
                        m.de_la_capat()
                    else:
                        self._canta(b)
                elif m.stare == 'oprit':
                    loc, _n, fisiere = self._loc(b)
                    if loc['i'] < 0 and fisiere:
                        loc['i'] = 0
                    self._canta(b)
                else:
                    m.pauza_continua()
                return True
            if e.ShiftDown():
                return False
            if k in (ord('L'), ord('J')) or sc in (0x26, 0x24):
                if m.stare != 'oprit':
                    inainte = k == ord('L') or sc == 0x26
                    lung = m.lungime()
                    nou = m.pozitie() + (5000 if inainte else -5000)
                    m.sari(max(0, min(nou, max(0, lung - 200))))
                return True
            if k == ord('I') or sc == 0x17:
                t = PaginaPlayer._timp
                voce.spune(_('{0} din {1}', t(m.pozitie()), t(m.lungime())) if m.stare != 'oprit' else _('Nu se cântă nimic.'),
                           intrerupe=True)
                return True
            if k == ord('R') or sc == 0x13:
                ordine = ['repeta', 'opreste', 'urmatoarea']
                self.mod = ordine[(ordine.index(self.mod) + 1) % 3] if self.mod in ordine else 'urmatoarea'
                self.f.setari['mod_audio'] = self.mod
                scrie_setari(self.f.setari)
                voce.spune(self.NUME_MOD[self.mod], intrerupe=True)
                return True
            if k == wx.WXK_ESCAPE and m.stare != 'oprit':
                m.opreste()
                voce.spune(_('Oprit.'), intrerupe=True)
                return True
        except Exception as ex:
            self.t.SetValue(str(ex))
            return True
        return False


class PaginaMetronom(wx.Panel):
    """Subfila Metronom din Partituri: un metronom de sine stătător (nu ține de partitură).
    K sau spațiu îl pornesc și îl opresc; săgeata sus/jos tempoul cu 1, Page Up/Down cu 5; săgeata dreapta/stânga
    câți timpi are măsura (primul timp se aude mai tare); Home/End volumul; I spune tot."""

    def __init__(self, carte, fereastra):
        super().__init__(carte)
        self.f = fereastra
        d = fereastra.setari.get('metronom_singur', {})
        self.tempo = int(d.get('tempo', 80))
        self.timpi = int(d.get('timpi', 4))
        self.volum = int(d.get('volum', 70))
        self.merge = False
        self._amanat = None
        self._fisier = None
        s = wx.BoxSizer(wx.VERTICAL)
        self.t = wx.TextCtrl(self, style=wx.TE_READONLY, name='')
        s.Add(self.t, 0, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(s)
        self._scrie_text()

    def _text(self):
        return _('Metronom {0}. {1} bătăi pe minut, {2} timpi în măsură, volum {3} la sută.',
                 _('pornit') if self.merge else _('oprit'), self.tempo, self.timpi, self.volum)

    def _scrie_text(self):
        self.t.SetValue(self._text())

    def _salveaza(self):
        self.f.setari['metronom_singur'] = {'tempo': self.tempo, 'timpi': self.timpi, 'volum': self.volum}
        scrie_setari(self.f.setari)

    def _wav(self):
        """O măsură de clicuri (primul timp mai tare), ca fișier WAV; se cântă în buclă."""
        import wave
        import numpy as np
        rata = inregistrare.RATA
        bata = int(round(60.0 / self.tempo * rata))
        sunet = np.zeros(bata * self.timpi, np.float32)
        for k in range(self.timpi):
            c = inregistrare._clic(k == 0) * (1.0 if k == 0 else 0.75)
            j = min(len(sunet), k * bata + len(c))
            sunet[k * bata:j] += c[:j - k * bata]
        date = (np.clip(sunet * (self.volum / 100.0) * 0.9, -1, 1) * 32767).astype('<i2')
        cale = os.path.join(tempfile.gettempdir(), f'MusicBox-metronom-{self.tempo}-{self.timpi}-{self.volum}.wav')
        if not os.path.isfile(cale):
            with wave.open(cale, 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(rata)
                w.writeframes(date.tobytes())
        return cale

    def _canta(self):
        try:
            import winsound
            winsound.PlaySound(self._wav(), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        except Exception as ex:
            self.merge = False
            self.t.SetValue(str(ex))

    def porneste(self):
        self.f.redare.opreste()
        self.merge = True
        self._canta()
        self._scrie_text()

    def opreste(self, tacut=False):
        if not self.merge:
            return
        self.merge = False
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except Exception:
            pass
        self._scrie_text()

    def _schimbat(self, spus):
        """Tempoul, timpii sau volumul s-au schimbat: NVDA spune valoarea, iar sunetul se schimbă după o clipă."""
        self._salveaza()
        self._scrie_text()
        voce.spune(spus, intrerupe=True)
        if self.merge:
            if self._amanat:
                self._amanat.Stop()
            self._amanat = wx.CallLater(250, self._canta)

    def tasta(self, e):
        k = e.GetKeyCode()
        sc = (e.GetRawKeyFlags() >> 16) & 0xFF if os.name == 'nt' else 0
        if k == wx.WXK_TAB and not e.ControlDown() and not e.AltDown():
            voce.spune(self.t.GetValue(), intrerupe=True)        # nu e nimic altceva de ales aici
            return True
        if e.ControlDown() or e.AltDown() or e.ShiftDown():
            return False
        if k == ord('K') or sc == 0x25 or k == wx.WXK_SPACE:
            if self.merge:
                self.opreste()
                voce.spune(_('Oprit.'), intrerupe=True)
            else:
                self.porneste()
                voce.spune(_('Pornit.'), intrerupe=True)
            return True
        if k == ord('I') or sc == 0x17:
            voce.spune(self._text(), intrerupe=True)
            return True
        pas = {wx.WXK_UP: 1, wx.WXK_DOWN: -1, wx.WXK_PAGEUP: 5, wx.WXK_PAGEDOWN: -5}.get(k)
        if pas:
            self.tempo = max(20, min(300, self.tempo + pas))
            self._schimbat(_('{0} bătăi pe minut.', self.tempo))
            return True
        if k in (wx.WXK_RIGHT, wx.WXK_LEFT):
            self.timpi = max(1, min(12, self.timpi + (1 if k == wx.WXK_RIGHT else -1)))
            self._schimbat(_('{0} timpi.', self.timpi))
            return True
        if k in (wx.WXK_HOME, wx.WXK_END):
            self.volum = max(10, min(100, self.volum + (10 if k == wx.WXK_HOME else -10)))
            self._schimbat(_('Volum {0} la sută.', self.volum))
            return True
        if k == wx.WXK_ESCAPE and self.merge:
            self.opreste()
            voce.spune(_('Oprit.'), intrerupe=True)
            return True
        return False


class DialogProgres(wx.Dialog):
    """Fereastră cu progresul actualizării: un text citibil și o bară de progres."""
    def __init__(self, parinte, titlu, text):
        super().__init__(parinte, title=titlu, size=(520, 200), style=wx.CAPTION | wx.STAY_ON_TOP)
        s = wx.BoxSizer(wx.VERTICAL)
        self.t = wx.TextCtrl(self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_NO_VSCROLL, name=_('Progresul actualizării'))
        s.Add(self.t, 1, wx.EXPAND | wx.ALL, 8)
        self.g = wx.Gauge(self, range=100, name=_('Progresul actualizării'))
        s.Add(self.g, 0, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(s)
        self.Centre()

    def arata(self, procent, text):
        self.g.SetValue(procent)
        self.t.SetValue(text)


class Picurare(wx.FileDropTarget):
    def __init__(self, f):
        super().__init__()
        self.f = f

    def OnDropFiles(self, x, y, fisiere):
        if fisiere:
            self.f.deschide(fisiere[0])
        return True


def autotest(fisier, iesire):
    """Probă fără fereastră vizibilă, folosită la compilarea pe GitHub: partitură, cuvinte, Braille, fereastră."""
    rez = []
    try:
        P = partitura.incarca(fisier)
        rez.append('VERSIUNE ' + VERSIUNE)
        rez.append(P.descriere_generala())
        rez.append(P.descrie(P.numere[0], P.numere[0] + 1, list(range(len(P.portative))), cuvinte.Optiuni()))
        rez.append(braille.din_scor(P.extrage(P.numere[0], P.numere[0] + 3, list(range(len(P.portative)))), final=False))
        app = wx.App(False)
        f = Fereastra()
        f._deschisa(P, None)
        f.lista.SetSelection(3)
        f.actualizeaza()
        rez.append('FEREASTRA ' + f.t_cuvinte.GetValue()[:200])
        cale_midi = redare.fa_midi(P.extrage(P.numere[0], P.numere[0] + 3, [0]), 50)
        rez.append(f'MIDI {os.path.getsize(cale_midi)} octeti')
        os.remove(cale_midi)
        baza_midi = redare.midi_octeti(P.extrage(P.numere[0], P.numere[0] + 3, [0]))
        t0 = time.time()
        rapid = redare.schimba_tempo_midi(baza_midi, 150)
        rez.append(f'TEMPO RAPID {len(rapid) == len(baza_midi) and rapid != baza_midi} {int((time.time() - t0) * 1000)} ms')
        sc_s, pr_s = scriere.construieste('do5 p mi sol do6\n[do5 mi5 sol5] î', 'do3 d sol2\ndo3+sol3 î', 'Proba', '', '4/4', 1, 90)
        rez.append(f'SCRIERE {len(partitura.Partitura(sc_s, "p.musicxml").numere)} masuri, probleme {len(pr_s)}, braille {len(braille.din_scor(sc_s))}')
        ses = auz.Sesiune(auz.Setari(exercitiu=2, rasturnari=True, fundamentala=True))
        ses.nou()
        rez.append(f'AUZ {len(ses.ex.intrebari)} intrebari, raspuns: {ses.raspunde(ses.intrebare.corect)[0]}')
        _sd = auz.Sesiune(auz.Setari(exercitiu=3)); _ed = _sd.nou()
        _ap = auz_absolut.Antrenament()
        _r = _ap.urmatoarea()
        for _i, _inc in enumerate(_r.incercari):
            _r.raspunde(_i, _inc.tinta, 500)
        rez.append(f'AUZ ABSOLUT {_ap.incheie(_r, 1)} test {len(_ap.runda_test().incercari)} note')
        rez.append(f'AUZ DURATE {len(_ed.durate)} sunete, {len(_ed.pasi)} pasi, citit {auz.citeste_durate("2, 1/2")}, raspuns: {_sd.raspunde_text(", ".join(str(b) for b in _ed.durate))[0]}')
        rez.append('SCRIERE LITERE ' + str(len(scriere.construieste('c4p d e f\nbb4d c#5d', '')[0].parts[0].recurse().notes)))
        _sv, _pv = scriere.construieste('do4 p re mi fa', '', versuri='Ma-mă dra-gă')
        rez.append(f'VERSURI {[ly.text for n in _sv.recurse().notes for ly in n.lyrics]} TIMPI {scriere.timpi_rand("do4 s re mi fa sol la si do5 do si4 la sol fa mi re do", 0)}')
        try:
            from nucleu import din_braille
            _tb = os.path.join(tempfile.gettempdir(), 'proba-din-braille.brf')
            with open(_tb, 'w', encoding='ascii', errors='replace', newline='') as _fh:
                _fh.write(braille.la_brf(braille.din_scor(P.extrage(P.numere[0], P.numere[-1], list(range(len(P.portative)))))))
            _rb = din_braille.din_fisier(_tb)
            rez.append(f'DIN BRAILLE {len(_rb)} piese, de verificat {len(_rb[0][2])}, note {len(list(_rb[0][1].recurse().notes))} din {len(list(P.scor.recurse().notes))}')
        except Exception as ex:
            rez.append(f'DIN BRAILLE eroare: {ex}')
        try:
            rez.append(f'METRONOM SINGUR {os.path.getsize(f.p_metronom._wav())} octeti, subfile {f.carte_p.GetPageCount()}')
        except Exception as ex:
            rez.append(f'METRONOM SINGUR eroare: {ex}')
        rez.append(f'PARTITURILE MELE {len(f._ids)} fisiere, curenta {f._curenta}; FOLDERE AUDIO {len(f.p_fisiere.butoane)}')
        try:
            sf = sunete.SintetizatorFluid()
            sf.pregateste(cu_sunet=False)
            sf.schimba_instrument((0, 57))
            rez.append(f'SUNETE exista={sunete.exista()} instrumente={sum(len(i) for _c, i in sunete.catalog())} sfid={sf._sfid}')
            sf.inchide()
        except Exception as ex:
            rez.append(f'SUNETE eroare: {ex} exista={sunete.exista()}')
        try:
            t0 = time.time()
            _snd = inregistrare.randeaza(baza_midi)
            _pa = inregistrare.PlayerAudio()
            _pa.incarca(_snd, inregistrare.pista_metronom(len(_snd), [(0, True), (500, False)]))
            _pa.volum_metronom = 0.5
            _it = inregistrare.Intinzator(_pa._sursa, len(_snd))
            _n = 0
            while not _it.gata():
                _it.bloc(0.6)
                _n += 1
            rez.append(f'INREGISTRARE {len(_snd) / inregistrare.RATA:.1f} s, varf {int(abs(_snd.astype("int32")).max())}, '
                       f'{int((time.time() - t0) * 1000)} ms, la 60%: {_n * inregistrare.HOP / inregistrare.RATA:.1f} s')
        except Exception as ex:
            rez.append(f'INREGISTRARE eroare: {ex}')
        rez.append(f'MIDI clape {len(midi_in.dispozitive())}, setari {DIR_SETARI}')
        from nucleu import traduceri
        rez.append(f'LIMBA {limba.LIMBA}, traduceri {len(traduceri.T)}, en: {traduceri.T["Setări"]["en"]}')
        b_met = redare.batai(P.extrage(P.numere[0], P.numere[0] + 3, [0]))
        cu_met = redare.cu_metronom(baza_midi, b_met, 60)
        rez.append(f'METRONOM {len(b_met)} batai, piste {len(redare._citeste(baza_midi)[2])} -> {len(redare._citeste(cu_met)[2])}')
        from music21 import tempo as m21tempo
        rez.append('TEMPO OPTIMI ' + ', '.join(cuvinte.text_tempo(m21tempo.MetronomeMark(number=138, referent='eighth'))))
        f.la_nesigura(1)
        # cărțile PDF: pypdfium2 trebuie să fie în program (citește și taie pagini)
        from PIL import Image
        d_pdf = tempfile.mkdtemp(prefix='autotest-')
        carte = os.path.join(d_pdf, 'carte.pdf')
        pag = [Image.new('L', (850, 1100), 255) for _ in range(3)]
        pag[0].save(carte, 'PDF', resolution=100, save_all=True, append_images=pag[1:])
        bucata = cuprins.pregateste_pdf(carte, 2, 3, os.path.join(d_pdf, 'bucata.pdf'), 0.3, None, dpi=50)
        rez.append(f'PDF pagini {cuprins.numar_pagini(carte)} -> {cuprins.numar_pagini(bucata)}; cuprins: '
                   + str(len(cuprins.gaseste(carte)['piese'])) + ' piese')
        cuprins.incarca_sau_gaseste(carte)
        # pagină culcată: portative desenate orizontal, apoi pagina întoarsă
        from PIL import ImageDraw
        dreapta = Image.new('L', (850, 1100), 255)
        dr = ImageDraw.Draw(dreapta)
        for k in range(8):
            for l in range(5):
                y = 120 + k * 120 + l * 10
                dr.line([(80, y), (780, y)], fill=0, width=2)
            dr.rectangle([82, 120 + k * 120 - 15, 110, 120 + k * 120 + 55], fill=0)    # „cheia” la început
        culcata = os.path.join(d_pdf, 'culcata.pdf')
        dreapta.rotate(90, expand=True).save(culcata, 'PDF', resolution=100)
        rez.append('PAGINA CULCATA rotatii: ' + str(cuprins.rotatii(culcata)))
        rez.append('CUPRINS in Documente Music Box: ' + str(os.path.isfile(os.path.join(limba.folder_documente(), 'carte', 'cuprins.json'))))
        from nucleu import verificare
        rez.append('MAINI impartite in exemplu: ' + str(verificare.imparte_mainile(P.scor)))
        shutil.rmtree(d_pdf, ignore_errors=True)
        # regulile de braille din manual: titlu fără etichete englezești, bara finală
        tb = braille.la_brf(braille.din_scor(P.scor))
        rez.append('BRAILLE REGULI bara finala=' + str(tb.rstrip().endswith('<K')) + ' fara Composer=' + str('COMPOSER' not in tb))
        rez.append('COMPONENTE homr=' + str(recunoastere.gaseste_homr()) + ' audiveris=' + str(recunoastere.gaseste_audiveris())
                   + ' musescore=' + str(recunoastere.gaseste_musescore()))
        f.Destroy()
        app.Destroy()
        rez.append('VOCE dll=' + str(bool(voce._incarca())) + ' nvda=' + str(voce.nvda_porneste()))
        rez.append('AUTOTEST OK')
    except Exception:
        rez.append('AUTOTEST EROARE\n' + traceback.format_exc())
    with open(iesire, 'w', encoding='utf-8') as fo:
        fo.write('\n'.join(rez))


def jurnal_erori(tip, val, tb):
    """Orice eroare neprevăzută se scrie în %APPDATA%\\Regatul Partiturilor\\erori.txt, ca s-o putem repara."""
    try:
        os.makedirs(DIR_SETARI, exist_ok=True)
        with open(os.path.join(DIR_SETARI, 'erori.txt'), 'a', encoding='utf-8') as f:
            f.write(f'--- versiunea {VERSIUNE}\n' + ''.join(traceback.format_exception(tip, val, tb)) + '\n')
    except Exception:
        pass
    sys.__excepthook__(tip, val, tb)


def main():
    sys.excepthook = jurnal_erori
    if len(sys.argv) >= 4 and sys.argv[1] == '--autotest':
        autotest(sys.argv[2], sys.argv[3])
        return
    captura.dpi_constient()
    if os.name == 'nt':
        # semn pentru programul de instalare: cât timp există, programul e încă deschis (vezi installer.iss)
        try:
            import ctypes
            global _SEMN_RULEAZA
            _SEMN_RULEAZA = ctypes.windll.kernel32.CreateMutexW(None, False, 'RegatulPartiturilorRuleaza')
        except Exception:
            pass
    app = wx.App(False)
    app.SetAppName(NUME)
    fisier = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    Fereastra(fisier).Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
