"""Regatul Partiturilor – citește partituri pentru nevăzători: în cuvinte și în Braille muzical.
Fereastra folosește controale Windows obișnuite, ca NVDA să le citească bine.
"""
import json
import os
import shutil
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nucleu import VERSIUNE, actualizare, auz, braille, captura, claviatura, cuprins, cuvinte, partitura, recunoastere, redare, scriere, voce  # noqa: E402

NUME = 'Regatul Partiturilor'
INDEMN = 'Nicio partitură deschisă. Deschide o partitură cu Control O.'
DIR_SETARI = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), NUME)
FIS_SETARI = os.path.join(DIR_SETARI, 'setari.json')
OCTAVE = [('fara', 'Fără octavă'), ('numere', 'Octava cu număr (do 4)'), ('nume', 'Octava cu nume (do din octava întâi)')]
FILTRU = ('Toate partiturile|' + ';'.join('*' + e for e in partitura.TOATE_FORMATELE) +
          '|MusicXML (*.musicxml, *.xml, *.mxl)|*.musicxml;*.xml;*.mxl|MIDI (*.mid)|*.mid;*.midi|MuseScore (*.mscz)|*.mscz;*.mscx'
          '|PDF și imagini|*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff|Toate fișierele|*.*')
SCURTATURI = """Scurtături în Regatul Partiturilor

Control plus O: deschide o partitură.
L (sau Alt plus săgeată dreapta): măsura următoare.
J (sau Alt plus săgeată stânga): măsura anterioară.
Control plus G: mergi la o anumită măsură.
Control plus 1: textul în cuvinte.
Control plus 2: textul în Braille.
Control plus 3: claviatura (cânți pe tastatură); Escape te scoate din ea.
Control plus L: lista de măsuri.
Control plus S: salvează textul în cuvinte.
Control plus B: salvează Braille pentru imprimantă (fișier BRF).
Control plus Shift plus B: din PDF în Braille, într-un singur pas (alegi PDF-ul, primești fișierul BRF în folderul Recunoscute, în subfolderul cu numele PDF-ului).
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
Control plus 4: fila Scrie o partitură (scrii tu notele, pentru mâna dreaptă și stânga, apoi asculți și salvezi ca MusicXML sau BRF).
În câmpurile mâinilor: Control plus Enter ascultă măsura pe care ești (ambele mâini), F2 spune pe ce măsură ești.
Control plus 5: exerciții de auz (programul cântă o notă, un interval sau un acord și tu alegi ce ai auzit).
Acolo: Enter în lista Răspunsuri răspunde, F3 ascultă din nou, F4 exercițiu nou.
Control plus 6: fila Setări (metronomul pornit sau oprit, volumul lui, instrumentul claviaturii, unde sunt programele de recunoaștere).

Citește din fereastră (pentru aplicațiile editurilor, din care nu se poate descărca):
Control plus Alt plus P, apăsat din aplicația editurii: citește pagina afișată acum.
Control plus Shift plus F: alegi fereastra dintr-o listă.
Nu se salvează nimic: poza paginii se șterge imediat după recunoaștere.

Claviatura (Control plus 3), cât stai în ea celelalte taste nu mai fac nimic:
Rândul de jos, de la Shift stânga la 3 de pe blocul numeric: do, re, mi, fa, sol, la, si, do și tot așa, două octave.
Deasupra, de la Tab: do diez, re diez, W gol, fa diez, sol diez, la diez, Y gol, și tot așa.
Săgeată dreapta sau stânga: o octavă mai sus sau mai jos (NVDA spune doar numărul octavei).
Săgeată sus sau jos: alt instrument.
Control plus săgeată dreapta sau stânga: transpui cu un semiton (ce era do se aude do diez).
Escape sau Control plus 1: ieși din claviatură. Instrumentul se poate alege și din fila Setări (Control plus 6).

F1: această listă.

În lista de măsuri poți selecta mai multe măsuri deodată cu Shift și săgețile. Primul rând este Despre piesă, al doilea Toată piesa.
Ce citesc alegi din lista Portative: toate, sau doar mâna dreaptă, sau doar mâna stângă."""


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
        super().__init__(None, title=NUME, size=(1000, 720))
        self.P = None
        self.setari = citeste_setari()
        recunoastere.SETARI['audiveris'] = self.setari.get('audiveris', '')
        recunoastere.SETARI['musescore'] = self.setari.get('musescore', '')
        recunoastere.SETARI['homr'] = self.setari.get('homr', '')
        self.redare = redare.Redare()
        self.redare.la_sfarsit = lambda: wx.CallAfter(self.SetStatusText, 'Redarea s-a terminat.')
        self.procent = int(self.setari.get('tempo', 100))
        self.metronom = bool(self.setari.get('metronom', False))
        self.volum_metronom = int(self.setari.get('metronom_volum', 60))
        self.sint = claviatura.Sintetizator()
        self.instrument = int(self.setari.get('instrument', 0)) % len(claviatura.INSTRUMENTE)
        self.do_clav = int(self.setari.get('octava_claviatura', 60))
        self.transpunere = int(self.setari.get('transpunere', 0))
        self._apasate = {}                   # tasta fizică -> nota care sună
        self._midi_cache = (None, None, None)  # (selecția, MIDI la 100%, bătăile): nu se mai face din nou la fiecare tempo
        self._redat = None                   # (selecția, procentul, metronomul) cu care se cântă acum
        self._tempo_amanat = None
        self._ocupat_recunoastere = False
        self._braille_id = 0
        self._meniuri()
        self._interfata()
        self._aplica_setari()
        self._sincronizeaza_setari()
        self.CreateStatusBar()
        self.SetStatusText('Deschide o partitură cu Control plus O.')
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
        if actualizare.instalat() and fisier != '--autotest':
            wx.CallLater(1500, self._anunta_versiunea_noua)
            wx.CallLater(1500, self.verifica_actualizari, False)

    # ---------------- interfață ----------------
    def _meniuri(self):
        mb = wx.MenuBar()
        f = wx.Menu()
        self._m(f, 'Deschide partitura...\tCtrl+O', self.cere_fisier)
        self._m(f, 'Din PDF în Braille, într-un pas...\tCtrl+Shift+B', self.pdf_in_braille)
        self._m(f, 'Citește din fereastră (aplicația editurii)...\tCtrl+Shift+F', self.alege_fereastra)
        f.AppendSeparator()
        self._m(f, 'Salvează textul în cuvinte...\tCtrl+S', self.salveaza_cuvinte)
        self._m(f, 'Salvează Braille pentru imprimantă (BRF)...\tCtrl+B', lambda e: self.salveaza_braille(True))
        self._m(f, 'Salvează Braille ca text Unicode...', lambda e: self.salveaza_braille(False))
        self._m(f, 'Salvează selecția ca MusicXML...', self.salveaza_musicxml)
        f.AppendSeparator()
        self._m(f, 'Ieșire\tAlt+F4', lambda e: self.Close())
        mb.Append(f, '&Fișier')
        n = wx.Menu()
        # L și J se prind direct din tastatură (vezi _taste); Alt și săgețile merg în continuare
        self._m(n, 'Măsura următoare (L)\tAlt+Right', lambda e: self.muta(1))
        self._m(n, 'Măsura anterioară (J)\tAlt+Left', lambda e: self.muta(-1))
        self._m(n, 'Mergi la măsura...\tCtrl+G', self.mergi_la)
        self._m(n, 'Următoarea măsură de verificat\tCtrl+U', lambda e: self.la_nesigura(1))
        self._m(n, 'Măsura de verificat anterioară\tCtrl+Shift+U', lambda e: self.la_nesigura(-1))
        n.AppendSeparator()
        self._m(n, 'Textul în cuvinte\tCtrl+1', lambda e: self.arata(0))
        self._m(n, 'Textul în Braille\tCtrl+2', lambda e: self.arata(1))
        self._m(n, 'Claviatura (cânți pe tastatură)\tCtrl+3', lambda e: self.arata(2))
        self._m(n, 'Scrie o partitură\tCtrl+4', lambda e: self.arata(3))
        self._m(n, 'Exerciții de auz\tCtrl+5', lambda e: self.arata(4))
        self._m(n, 'Setările\tCtrl+6', lambda e: self.arata(5))
        self._m(n, 'Lista de măsuri\tCtrl+L', lambda e: self.lista.SetFocus())
        mb.Append(n, '&Navigare')
        r = wx.Menu()
        # K, Shift K, tempoul și volumul metronomului se prind direct din tastatură (vezi _taste): în meniu doar se afișează
        self._m(r, 'Redă, oprește sau continuă (K)', lambda e: self.reda_sau_pauza())
        self._m(r, 'Reia de la început (Shift K)', lambda e: self.reda(False))
        self._m(r, 'Redă de la măsura aleasă până la final (I)', lambda e: self.reda(True))
        r.AppendSeparator()
        self._m(r, 'Mai rar cu 5 la sută (Shift 1)', lambda e: self.schimba_tempo(-5))
        self._m(r, 'Mai repede cu 5 la sută (Shift 2)', lambda e: self.schimba_tempo(5))
        self._m(r, 'Tempoul scris în piesă (Shift 3)', lambda e: self.schimba_tempo(0))
        self.m_bucla = r.AppendCheckItem(wx.ID_ANY, 'Redare în buclă\tCtrl+R')
        self.Bind(wx.EVT_MENU, self.comuta_bucla, self.m_bucla)
        r.AppendSeparator()
        self.m_metronom = r.AppendCheckItem(wx.ID_ANY, 'Metronom\tCtrl+Shift+M')
        self.m_metronom.Check(self.metronom)
        self.Bind(wx.EVT_MENU, lambda e: self.comuta_metronom(self.m_metronom.IsChecked()), self.m_metronom)
        self._m(r, 'Metronomul mai tare cu 1 la sută (Shift plus)', lambda e: self.schimba_volum_metronom(1))
        self._m(r, 'Metronomul mai încet cu 1 la sută (Shift minus)', lambda e: self.schimba_volum_metronom(-1))
        self._m(r, 'Metronomul mai tare cu 5 la sută (Control Shift plus)', lambda e: self.schimba_volum_metronom(5))
        self._m(r, 'Metronomul mai încet cu 5 la sută (Control Shift minus)', lambda e: self.schimba_volum_metronom(-5))
        mb.Append(r, '&Redare')
        a = wx.Menu()
        self._m(a, 'Scurtături\tF1', lambda e: self.mesaj(SCURTATURI, 'Scurtături'))
        self._m(a, 'Caută actualizări', lambda e: self.verifica_actualizari(True))
        self._m(a, 'Despre', lambda e: self.mesaj(f'{NUME}, versiunea {VERSIUNE}.\nCitește partituri în cuvinte și în Braille muzical.\n'
                                                  'Folosește music21 pentru note, Braille și sunet; homr și Audiveris pentru recunoașterea PDF-urilor, '
                                                  'comparate măsură cu măsură; MuseScore pentru fișierele .mscz.', 'Despre'))
        mb.Append(a, '&Ajutor')
        self.SetMenuBar(mb)

    def _m(self, meniu, text, fn):
        it = meniu.Append(wx.ID_ANY, text)
        self.Bind(wx.EVT_MENU, fn, it)
        return it

    def _interfata(self):
        p = wx.Panel(self)
        st = wx.BoxSizer(wx.VERTICAL)
        stg = wx.BoxSizer(wx.VERTICAL)
        stg.Add(wx.StaticText(p, label='&Măsuri'), 0, wx.ALL, 4)
        self.lista = wx.ListBox(p, style=wx.LB_EXTENDED, size=(230, -1), name='Măsuri')
        stg.Add(self.lista, 1, wx.EXPAND | wx.ALL, 4)
        stg.Add(wx.StaticText(p, label='&Portative'), 0, wx.ALL, 4)
        self.portative = wx.Choice(p, name='Portative')
        stg.Add(self.portative, 0, wx.EXPAND | wx.ALL, 4)

        box = wx.StaticBoxSizer(wx.VERTICAL, p, 'Opțiuni pentru textul în cuvinte')
        sb = box.GetStaticBox()
        self.c_ritm = wx.CheckBox(sb, label='Cu &ritm (durata notelor)')
        box.Add(self.c_ritm, 0, wx.ALL, 3)
        box.Add(wx.StaticText(sb, label='&Octava'), 0, wx.LEFT | wx.TOP, 3)
        self.c_octava = wx.Choice(sb, choices=[x[1] for x in OCTAVE], name='Octava')
        box.Add(self.c_octava, 0, wx.EXPAND | wx.ALL, 3)
        self.c_scurt = wx.CheckBox(sb, label='Scriere &scurtă (do4 p, mi4 o)')
        self.c_dig = wx.CheckBox(sb, label='Cu &digitație')
        self.c_nuante = wx.CheckBox(sb, label='Cu &nuanțe, articulații și tempo')
        self.c_voci = wx.CheckBox(sb, label='&Voci separate în aceeași mână')
        for c in (self.c_scurt, self.c_dig, self.c_nuante, self.c_voci):
            box.Add(c, 0, wx.ALL, 3)
        stg.Add(box, 0, wx.EXPAND | wx.ALL, 4)

        self.carte = wx.Notebook(p, name='Rezultat')
        pc = wx.Panel(self.carte)
        sc = wx.BoxSizer(wx.VERTICAL)
        sc.Add(wx.StaticText(pc, label='Textul în cuvinte'), 0, wx.ALL, 2)
        self.t_cuvinte = wx.TextCtrl(pc, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, name='Textul în cuvinte')
        sc.Add(self.t_cuvinte, 1, wx.EXPAND | wx.ALL, 2)
        pc.SetSizer(sc)
        pb = wx.Panel(self.carte)
        sbz = wx.BoxSizer(wx.VERTICAL)
        sbz.Add(wx.StaticText(pb, label='Textul în Braille'), 0, wx.ALL, 2)
        self.t_braille = wx.TextCtrl(pb, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.HSCROLL, name='Textul în Braille')
        self.t_braille.SetFont(wx.Font(16, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL, faceName='Segoe UI Symbol'))
        sbz.Add(self.t_braille, 1, wx.EXPAND | wx.ALL, 2)
        pb.SetSizer(sbz)
        pk = wx.Panel(self.carte)
        sk = wx.BoxSizer(wx.VERTICAL)
        sk.Add(wx.StaticText(pk, label='Claviatura'), 0, wx.ALL, 2)
        self.t_clav = wx.TextCtrl(pk, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_PROCESS_TAB | wx.TE_PROCESS_ENTER, name='Claviatura')
        self.t_clav.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sk.Add(self.t_clav, 1, wx.EXPAND | wx.ALL, 2)
        pk.SetSizer(sk)
        self.carte.AddPage(pc, 'În cuvinte')
        self.carte.AddPage(pb, 'Braille')
        self.carte.AddPage(pk, 'Claviatura')
        self._fila_scriere()
        self._fila_auz()
        # fila Setări (ultima): metronomul, instrumentul claviaturii, unde sunt programele de recunoaștere
        self.p_setari = ps = wx.Panel(self.carte)
        ss = wx.BoxSizer(wx.VERTICAL)
        self.s_metronom = wx.CheckBox(ps, label='Metronom pornit (cântă odată cu piesa, în tempoul ei)')
        ss.Add(self.s_metronom, 0, wx.ALL, 6)
        ss.Add(wx.StaticText(ps, label='Volumul metronomului, în procente (0 – 100)'), 0, wx.LEFT | wx.TOP, 6)
        self.s_volum = wx.SpinCtrl(ps, min=0, max=100, initial=60, name='Volumul metronomului, în procente')
        ss.Add(self.s_volum, 0, wx.ALL, 6)
        ss.Add(wx.StaticText(ps, label='Instrumentul claviaturii'), 0, wx.LEFT | wx.TOP, 6)
        self.s_instrument = wx.Choice(ps, choices=[x[0] for x in claviatura.INSTRUMENTE], name='Instrumentul claviaturii')
        ss.Add(self.s_instrument, 0, wx.ALL, 6)
        for cheie, text in (('audiveris', 'Unde e instalat Audiveris (pentru PDF și poze)...'),
                            ('musescore', 'Unde e instalat MuseScore (pentru fișiere MuseScore)...'),
                            ('homr', 'Unde e instalat homr (al doilea program de recunoaștere)...')):
            b = wx.Button(ps, label=text)
            b.Bind(wx.EVT_BUTTON, lambda e, c=cheie: self.alege_program(c))
            ss.Add(b, 0, wx.ALL, 6)
        ps.SetSizer(ss)
        self.carte.AddPage(ps, 'Setări')
        self.s_metronom.Bind(wx.EVT_CHECKBOX, lambda e: self.comuta_metronom(self.s_metronom.GetValue()))
        self.s_volum.Bind(wx.EVT_SPINCTRL, lambda e: self._volum_din_setari())
        self.s_volum.Bind(wx.EVT_TEXT, lambda e: self._volum_din_setari())
        self.s_instrument.Bind(wx.EVT_CHOICE, lambda e: self.schimba_instrument(index=self.s_instrument.GetSelection()))
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
        self.lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.arata(0))
        self.lista.Bind(wx.EVT_KEY_DOWN, self._tasta_lista)
        self.portative.Bind(wx.EVT_CHOICE, lambda e: self.actualizeaza())
        for c in (self.c_ritm, self.c_scurt, self.c_dig, self.c_nuante, self.c_voci):
            c.Bind(wx.EVT_CHECKBOX, lambda e: self.actualizeaza(salveaza=True))
        self.c_octava.Bind(wx.EVT_CHOICE, lambda e: self.actualizeaza(salveaza=True))
        self.carte.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, lambda e: (self.actualizeaza_braille(), e.Skip()))

    def _tasta_lista(self, e):
        if e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self.arata(0)
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
        with wx.FileDialog(self, 'Deschide partitura', defaultDir=self.setari.get('folder', ''), wildcard=FILTRU,
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
        self.SetStatusText('Caut piesele din carte. Prima dată poate dura un minut sau două; apoi se ține minte.')
        self.t_cuvinte.SetValue('Caut piesele din carte (unde începe fiecare studiu sau piesă), te rog așteaptă.')
        self.t_cuvinte.SetFocus()

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
        optiuni = [f'Toată cartea ({n} pagini)'] + [cuprins.eticheta(p) for p in piese] + ['Alte pagini, le scriu eu...']
        text = (f'Am găsit {len(piese)} piese în carte. Alege ce deschizi.' if piese else
                'Nu am găsit sigur unde încep piesele. Poți deschide toată cartea sau scrie paginile.')
        if c and c.get('probleme') and not c.get('verificat'):
            text += ' Atenție: ' + ' '.join(c['probleme'][:3])
        if eroare:
            text += f' (Eroare la căutarea pieselor: {eroare})'
        self.t_cuvinte.SetValue(INDEMN)
        d = wx.SingleChoiceDialog(self, text, 'Ce deschizi din carte?', optiuni)
        if len(optiuni) > 2:
            d.SetSelection(1)
        if d.ShowModal() != wx.ID_OK:
            d.Destroy()
            self.SetStatusText('Nu am deschis nimic.')
            return
        k = d.GetSelection()
        d.Destroy()
        baza_carte = os.path.splitext(os.path.basename(cale))[0]
        if k == 0:
            self.deschide(cale, brf=brf, fara_cuprins=True)
            return
        if k == len(optiuni) - 1:
            t = wx.TextEntryDialog(self, f'Ce pagini? De exemplu 3-4, sau 5 pentru o singură pagină. Cartea are {n} pagini.',
                                   'Alte pagini')
            ok = t.ShowModal() == wx.ID_OK
            val = t.GetValue()
            t.Destroy()
            if not ok:
                return
            pg = cuprins.citeste_pagini(val, n)
            if not pg:
                self.mesaj(f'Paginile nu sunt scrise bine. Scrie de exemplu 3-4. Cartea are {n} pagini.', 'Alte pagini')
                return
            de_la, pana_la = pg
            nume = f'paginile {de_la}-{pana_la}' if de_la != pana_la else f'pagina {de_la}'
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
            self.mesaj(f'Nu am putut scoate paginile din carte. Eroare: {ex}', 'Ce deschizi din carte?')
            shutil.rmtree(d_tmp, ignore_errors=True)
            return
        self.deschide(tmp, titlu=f'{baza_carte}, {nume}', brf=brf, baza=baza, folder=os.path.dirname(cale), original=cale,
                      dupa=lambda: shutil.rmtree(d_tmp, ignore_errors=True), fara_cuprins=True)

    def deschide(self, cale, pastreaza=True, titlu=None, dupa=None, brf=False, baza=None, folder=None, original=None,
                 fara_cuprins=False):
        """Deschide o partitură. pastreaza=False: nu se salvează nimic (pagini din aplicațiile editurilor);
        titlu: numele afișat; dupa: funcție chemată la final (de exemplu ștergerea pozei); brf: salvează și BRF în Recunoscute\\<nume PDF>."""
        if self._ocupat_recunoastere:
            self.mesaj('Încă se recunoaște partitura de dinainte. Așteaptă să se termine.', 'Ocupat')
            if dupa:
                dupa()
            return
        e_imagine = os.path.splitext(cale)[1].lower() in partitura.FORMATE_IMAGINE
        if (not fara_cuprins and pastreaza and cale.lower().endswith('.pdf')
                and self._pagini(cale) > 2):
            self.deschide_carte(cale, brf=brf)
            return
        if pastreaza:
            self.setari['folder'] = os.path.dirname(cale)
            scrie_setari(self.setari)
        self.redare.opreste()
        self.SetStatusText('Se deschide ' + (titlu or os.path.basename(cale)) + '...')
        self.t_cuvinte.SetValue('Se recunoaște partitura cu două programe și se compară măsură cu măsură. Poate dura câteva minute; '
                                'te anunț când e gata.' if e_imagine else 'Se deschide partitura, te rog așteaptă.')
        self.t_braille.SetValue('')
        self.t_cuvinte.SetFocus()
        self._ocupat = wx.BusyInfo('Se deschide partitura...', self) if not e_imagine else None
        self._ocupat_recunoastere = e_imagine

        def lucru():
            cale_l, original_l, baza_l, d_rot = cale, original, baza, None
            try:
                # PDF scanat cu paginile culcate: lucrăm pe o copie cu paginile îndreptate
                if pastreaza and original is None and cale.lower().endswith('.pdf'):
                    rot = cuprins.rotatii(cale)
                    if any(rot):
                        wx.CallAfter(self.SetStatusText, 'Paginile sunt scanate culcate; le îndrept.')
                        d_rot = tempfile.mkdtemp(prefix='regatul-drept-')
                        cale_l = os.path.join(d_rot, os.path.basename(cale))
                        cuprins.extrage_pagini(cale, 1, len(rot), cale_l)
                        original_l = cale
                        baza_l = baza or os.path.splitext(os.path.basename(cale))[0]
                P = partitura.incarca(cale_l, progres=lambda m: wx.CallAfter(self.SetStatusText, m), pastreaza=pastreaza,
                                      baza=baza_l, folder=folder, original=original_l)
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
                wx.CallAfter(self._deschisa, None, f'Nu am putut deschide partitura. Eroare: {ex}')
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
            self.SetStatusText('Partitura nu s-a deschis.')
            self.mesaj(eroare, 'Nu s-a deschis')
            return
        self.P = P
        self._midi_cache = (None, None, None)
        self.SetTitle(f'{P.titlu} – {NUME}')
        self.lista.Set(['Despre piesă', 'Toată piesa'] + [('Anacruza' if n == 0 else f'Măsura {n}') + (', de verificat' if n in P.nesigure else '')
                                                          for n in P.numere])
        self.portative.Set(['Toate portativele'] + [p.nume for p in P.portative])
        self.portative.SetSelection(0)
        self.lista.SetSelection(0)
        self.actualizeaza()
        self.SetStatusText(f'Deschisă: {P.titlu}. {len(P.numere)} măsuri.')
        self.lista.SetFocus()
        if fis_brf:
            self.mesaj(f'Gata. Fișierul Braille e salvat în folderul Recunoscute, la {os.path.basename(os.path.dirname(fis_brf))}, '
                       f'cu numele {os.path.basename(fis_brf)}.\n\n' +
                       (f'Măsuri de verificat: {len(P.nesigure)} (' + ', '.join(str(n) for n in P.nesigure) + '). '
                        'Lista lor cu motivele e în același folder, în fișierul „de verificat”.' if P.nesigure
                        else 'Toate măsurile au fost citite la fel de ambele programe.'), 'Din PDF în Braille')
        elif recunoscuta:
            self.mesaj(P.descriere_generala(), 'Partitura e gata')

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
                self.t_cuvinte.SetValue(self.P.descrie(s[0], s[1], s[2], self.optiuni()) or 'Nicio notă aici.')
            except Exception as ex:
                traceback.print_exc()
                self.t_cuvinte.SetValue(f'Nu am putut descrie măsurile acestea. Eroare: {ex}')
        self.t_cuvinte.SetInsertionPoint(0)
        self.t_braille.SetValue('')
        self.actualizeaza_braille()

    def actualizeaza_braille(self):
        if not self.P or self.carte.GetSelection() != 1 or self.t_braille.GetValue():
            return
        s = self.selectie()
        if s is None:
            s = (self.P.numere[0], self.P.numere[-1], list(range(len(self.P.portative))))
        self._braille_id += 1
        nr = self._braille_id
        self.t_braille.SetValue('Se pregătește Braille...')

        def lucru():
            try:
                txt = braille.din_scor(self.P.extrage(*s), final=s[1] == self.P.numere[-1])
            except Exception as ex:
                traceback.print_exc()
                txt = f'Nu am putut face Braille pentru selecția aceasta. Eroare: {ex}'
            wx.CallAfter(self._braille_gata, nr, txt)
        threading.Thread(target=lucru, daemon=True).start()

    def _braille_gata(self, nr, txt):
        if nr == self._braille_id:
            self.t_braille.SetValue(txt)
            self.t_braille.SetInsertionPoint(0)

    def arata(self, pagina):
        self.carte.SetSelection(pagina)
        (self.t_cuvinte, self.t_braille, self.t_clav, self.w_titlu, self.a_ex, self.s_metronom)[pagina].SetFocus()
        if pagina == 1:
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
        self.arata(self.carte.GetSelection())

    def mergi_la(self, e=None):
        if not self.P:
            return
        d = wx.TextEntryDialog(self, 'Numărul măsurii (sau două numere, de exemplu 5-8):', 'Mergi la măsura')
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
                self.arata(self.carte.GetSelection())
            except Exception:
                self.mesaj('Nu există măsura aceasta.', 'Mergi la măsura')
        d.Destroy()

    def la_nesigura(self, pas):
        if not self.P:
            return
        if not self.P.nesigure:
            self.SetStatusText('Nu există măsuri de verificat.')
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
                self.arata(0)
                return
        self.SetStatusText('Nu mai sunt măsuri de verificat în direcția asta.')
        wx.Bell()

    # ---------------- redare cu sunet ----------------
    def reda(self, pana_la_final):
        if not self.P:
            return
        s = self.selectie() or (self.P.numere[0], self.P.numere[-1], self._portative_alese())
        prima, ultima, port = s
        if pana_la_final:
            ultima = self.P.numere[-1]
        try:
            sel = (id(self.P), prima, ultima, tuple(port))
            self._porneste(sel)
            unde = f'măsura {prima}' if prima == ultima else f'măsurile {prima}-{ultima}'
            self.SetStatusText(f'Se cântă {unde}, tempo {self.procent} la sută' + (', în buclă.' if self.redare.bucla else '.'))
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(f'Nu am putut reda. Eroare: {ex}', 'Redare')

    def _porneste(self, sel, de_la_ms=0, in_pauza=False):
        """Cântă selecția la tempoul de acum. MIDI-ul de bază se face o singură dată pentru o selecție."""
        if self._midi_cache[0] != sel:
            _, prima, ultima, port = sel
            bucata = self.P.extrage(prima, ultima, list(port))
            try:
                batai = redare.batai(bucata)
            except Exception:
                traceback.print_exc()
                batai = []
            self._midi_cache = (sel, redare.midi_octeti(bucata), batai)
        self.sint.inchide()                  # sintetizatorul îl folosește acum redarea piesei
        date = self._midi_cache[1]
        metronom = self.volum_metronom if self.metronom else 0
        if metronom:
            date = redare.cu_metronom(date, self._midi_cache[2], metronom)
        date = redare.schimba_tempo_midi(date, self.procent)
        self.redare.bucla = self.m_bucla.IsChecked()
        self.redare.canta(redare.scrie_temporar(date), de_la_ms, in_pauza)
        self._redat = (sel, self.procent, metronom)

    def _portative_alese(self):
        k = self.portative.GetSelection()
        return list(range(len(self.P.portative))) if k <= 0 else [k - 1]

    def reda_sau_pauza(self):
        """K: dacă nu se cântă nimic, redă selecția; altfel oprește sau continuă de unde a rămas."""
        if self.redare.stare == 'oprit':
            self.reda(False)
        else:
            self.pauza()

    def pauza(self, e=None):
        try:
            st = self.redare.pauza_continua()
            self.SetStatusText({'pauza': 'Pauză.', 'canta': 'Continuă.', 'oprit': 'Nu se cântă nimic.'}[st])
        except Exception as ex:
            self.SetStatusText(f'Eroare la pauză: {ex}')

    def opreste(self, e=None):
        self.redare.opreste()
        self.SetStatusText('Oprit.')

    def schimba_tempo(self, pas):
        vechi = self.procent
        self.procent = 100 if pas == 0 else min(200, max(20, self.procent + pas))
        if pas and self.procent == vechi:
            text = 'Tempoul e deja cel mai ' + ('rar' if pas < 0 else 'repede') + f', {self.procent} la sută.'
        else:
            text = f'Tempo {self.procent} la sută.'
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)
        self._amana_aplicarea()

    def comuta_metronom(self, pornit=None):
        self.metronom = (not self.metronom) if pornit is None else bool(pornit)
        self.m_metronom.Check(self.metronom)
        self._sincronizeaza_setari()
        text = 'Metronom pornit.' if self.metronom else 'Metronom oprit.'
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)
        self._amana_aplicarea()

    def schimba_volum_metronom(self, pas):
        vechi = self.volum_metronom
        self.volum_metronom = min(100, max(0, self.volum_metronom + pas))
        if self.volum_metronom == vechi:
            text = f'Metronomul e deja cel mai {"tare" if pas > 0 else "încet"}, {self.volum_metronom} la sută.'
        else:
            text = f'Metronom {self.volum_metronom} la sută.'
        self._sincronizeaza_setari()
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)
        self._amana_aplicarea()

    def _sincronizeaza_setari(self):
        """Fila Setări arată mereu ce e acum (și după scurtături)."""
        self.s_metronom.SetValue(self.metronom)
        if self.s_volum.GetValue() != self.volum_metronom:
            self.s_volum.SetValue(self.volum_metronom)
        self.s_instrument.SetSelection(self.instrument)

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
        metronom = self.volum_metronom if self.metronom else 0
        if self.redare.stare in ('canta', 'pauza') and self._redat and self._redat[1:] != (self.procent, metronom):
            sel, vechi, _ = self._redat
            # același loc din muzică: la tempo nou, aceeași notă cade la alt moment
            poz = self.redare.pozitie() * vechi / self.procent
            try:
                self._porneste(sel, poz, in_pauza=(self.redare.stare == 'pauza'))
            except Exception as ex:
                traceback.print_exc()
                self.SetStatusText(f'Nu am putut schimba tempoul. Eroare: {ex}')

    # ---------------- scrie o partitură ----------------
    def _fila_scriere(self):
        self.p_scriere = pw = wx.Panel(self.carte)
        sw = wx.BoxSizer(wx.VERTICAL)

        def eticheta(text):
            sw.Add(wx.StaticText(pw, label=text), 0, wx.LEFT | wx.TOP, 4)

        eticheta('Titlu')
        self.w_titlu = wx.TextCtrl(pw, name='Titlu')
        sw.Add(self.w_titlu, 0, wx.EXPAND | wx.ALL, 3)
        eticheta('Compozitor')
        self.w_comp = wx.TextCtrl(pw, name='Compozitor')
        sw.Add(self.w_comp, 0, wx.EXPAND | wx.ALL, 3)
        eticheta('Măsura')
        self.w_masura = wx.Choice(pw, choices=scriere.MASURI, name='Măsura')
        sw.Add(self.w_masura, 0, wx.ALL, 3)
        eticheta('Tonalitatea (armura)')
        self.w_ton = wx.Choice(pw, choices=[t[1] for t in scriere.TONALITATI], name='Tonalitatea')
        sw.Add(self.w_ton, 0, wx.ALL, 3)
        eticheta('Tempo, pătrimi pe minut (0 = fără tempo)')
        self.w_tempo = wx.SpinCtrl(pw, min=0, max=300, initial=0, name='Tempo, pătrimi pe minut')
        sw.Add(self.w_tempo, 0, wx.ALL, 3)
        self.w_ana = wx.CheckBox(pw, label='Prima măsură e anacruză')
        sw.Add(self.w_ana, 0, wx.ALL, 3)
        eticheta('Mâna dreaptă, câte o măsură pe rând')
        self.w_dr = wx.TextCtrl(pw, style=wx.TE_MULTILINE | wx.TE_RICH2, size=(-1, 110), name='Mâna dreaptă, câte o măsură pe rând')
        sw.Add(self.w_dr, 1, wx.EXPAND | wx.ALL, 3)
        eticheta('Mâna stângă, câte o măsură pe rând (gol = doar mâna dreaptă)')
        self.w_st = wx.TextCtrl(pw, style=wx.TE_MULTILINE | wx.TE_RICH2, size=(-1, 110), name='Mâna stângă, câte o măsură pe rând')
        sw.Add(self.w_st, 1, wx.EXPAND | wx.ALL, 3)
        rand = wx.WrapSizer()
        for text, fn in (('Verifică', self.scriere_verifica),
                         ('Ascultă tot', lambda e: self.scriere_asculta(False)),
                         ('Deschide pentru citit (În cuvinte, Braille, redare)', self.scriere_deschide),
                         ('Salvează ca MusicXML...', lambda e: self.scriere_salveaza(False)),
                         ('Salvează ca BRF...', lambda e: self.scriere_salveaza(True)),
                         ('Cum se scrie', lambda e: self.mesaj(scriere.AJUTOR.strip(), 'Cum se scrie')),
                         ('Partitură nouă', self.scriere_noua)):
            b = wx.Button(pw, label=text)
            b.Bind(wx.EVT_BUTTON, fn)
            rand.Add(b, 0, wx.ALL, 3)
        sw.Add(rand, 0, wx.EXPAND)
        pw.SetSizer(sw)
        self.carte.AddPage(pw, 'Scrie o partitură')
        self._ciorna_amanata = None
        self._scriere_incarca_ciorna()
        for c in (self.w_titlu, self.w_comp, self.w_dr, self.w_st):
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
                'dreapta': self.w_dr.GetValue(), 'stanga': self.w_st.GetValue()}

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

    def _scriere_incarca_ciorna(self):
        try:
            with open(self._FIS_CIORNA, encoding='utf-8') as f:
                self._scriere_pune(json.load(f))
        except Exception:
            self._scriere_pune({})

    def _ciorna_schimbata(self, e=None):
        # ce scrii se păstrează singur (și după ce închizi programul), la o secundă după ultima tastă
        if self._ciorna_amanata:
            self._ciorna_amanata.Stop()
        self._ciorna_amanata = wx.CallLater(1000, self._salveaza_ciorna)
        if e:
            e.Skip()

    def _salveaza_ciorna(self):
        self._ciorna_amanata = None
        try:
            os.makedirs(DIR_SETARI, exist_ok=True)
            with open(self._FIS_CIORNA, 'w', encoding='utf-8') as f:
                json.dump(self._scriere_date(), f, ensure_ascii=False, indent=1)
        except Exception:
            pass

    def _scriere_scor(self, arata_erori=True):
        """(scor, probleme) sau (None, None) dacă textul are greșeli care nu se pot citi."""
        d = self._scriere_date()
        try:
            return scriere.construieste(d['dreapta'], d['stanga'], d['titlu'], d['compozitor'], d['masura'],
                                        d['alteratii'], d['tempo'], d['anacruza'])
        except scriere.EroareScriere as ex:
            if arata_erori:
                self.mesaj(str(ex), 'Greșeală în scriere')
            return None, None
        except Exception as ex:
            traceback.print_exc()
            if arata_erori:
                self.mesaj(f'Nu am putut face partitura. Eroare: {ex}', 'Greșeală în scriere')
            return None, None

    def scriere_verifica(self, e=None):
        scor, probleme = self._scriere_scor()
        if scor is None:
            return
        n = len(scor.parts[0].getElementsByClass('Measure'))
        if probleme:
            self.mesaj('\n'.join(probleme), 'Verificare')
        else:
            self.mesaj(f'Totul e în regulă: {n} măsuri, fiecare cu timpii potriviți.', 'Verificare')

    def _masura_cursorului(self):
        """(numărul măsurii, mâna) pentru rândul pe care e cursorul."""
        c = wx.Window.FindFocus()
        if c not in (self.w_dr, self.w_st):
            c = self.w_dr
        ok, x, y = c.PositionToXY(c.GetInsertionPoint())
        rand = y if ok else c.GetValue()[:c.GetInsertionPoint()].count('\n')
        nr = rand if self.w_ana.GetValue() else rand + 1
        return nr, ('mâna dreaptă' if c is self.w_dr else 'mâna stângă')

    def scriere_spune_masura(self):
        nr, mana = self._masura_cursorului()
        text = ('Anacruza' if nr == 0 else f'Măsura {nr}') + f', {mana}.'
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)

    def scriere_asculta(self, masura=False):
        scor, _ = self._scriere_scor()
        if scor is None:
            return
        try:
            bucata = scor
            if masura:
                nr, _ = self._masura_cursorului()
                P = partitura.Partitura(scor, 'scriere.musicxml')
                if nr not in P.numere:
                    voce.spune('Măsura asta e goală.', intrerupe=True)
                    return
                bucata = P.extrage(nr, nr, list(range(len(P.portative))))
            date = redare.midi_octeti(bucata)
            if self.metronom:
                date = redare.cu_metronom(date, redare.batai(bucata), self.volum_metronom)
            date = redare.schimba_tempo_midi(date, self.procent)
            self.sint.inchide()
            self._redat = None
            self.redare.bucla = False
            self.redare.canta(redare.scrie_temporar(date))
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(f'Nu am putut reda. Eroare: {ex}', 'Redare')

    def scriere_deschide(self, e=None):
        scor, probleme = self._scriere_scor()
        if scor is None:
            return
        titlu = self.w_titlu.GetValue().strip() or 'Fără titlu'
        try:
            P = partitura.Partitura(scor, titlu + '.musicxml', avertismente=probleme)
        except Exception as ex:
            self.mesaj(f'Nu am putut deschide partitura. Eroare: {ex}', 'Scrie o partitură')
            return
        self.redare.opreste()
        self._deschisa(P, None)

    def scriere_salveaza(self, brf):
        scor, probleme = self._scriere_scor()
        if scor is None:
            return
        if probleme and wx.MessageBox('Unele măsuri nu au timpii potriviți:\n' + '\n'.join(probleme[:5]) +
                                      '\n\nSalvez totuși?', 'Salvare', wx.YES_NO | wx.ICON_WARNING, self) != wx.YES:
            return
        titlu = self.w_titlu.GetValue().strip() or 'Partitura mea'
        nume = ''.join(ch for ch in titlu if ch not in '\\/:*?"<>|') + ('.brf' if brf else '.musicxml')
        filtru = 'Braille pentru imprimantă (*.brf)|*.brf' if brf else 'MusicXML (*.musicxml)|*.musicxml'
        with wx.FileDialog(self, 'Salvează ca BRF' if brf else 'Salvează ca MusicXML',
                           defaultDir=self.setari.get('folder_scriere', self.setari.get('folder', '')), defaultFile=nume,
                           wildcard=filtru, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as d:
            if d.ShowModal() != wx.ID_OK:
                return
            cale = d.GetPath()
        try:
            if brf:
                with open(cale, 'w', encoding='ascii', errors='replace', newline='') as f:
                    f.write(braille.la_brf(braille.din_scor(scor)))
            else:
                scor.write('musicxml', fp=cale)
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(f'Nu am putut salva. Eroare: {ex}', 'Salvare')
            return
        self.setari['folder_scriere'] = os.path.dirname(cale)
        scrie_setari(self.setari)
        self.SetStatusText('Salvat: ' + cale)
        voce.spune('Salvat.', intrerupe=True)

    def scriere_noua(self, e=None):
        if (self.w_dr.GetValue().strip() or self.w_st.GetValue().strip()) and wx.MessageBox(
                'Ștergi tot ce ai scris și începi o partitură nouă?', 'Partitură nouă', wx.YES_NO | wx.NO_DEFAULT, self) != wx.YES:
            return
        self._scriere_pune({})
        self._salveaza_ciorna()
        self.w_titlu.SetFocus()

    # ---------------- exerciții de auz ----------------
    def _fila_auz(self):
        d = self.setari.get('auz', {})
        try:
            self.auz_set = auz.Setari(**{k: v for k, v in d.items() if k in auz.Setari.__dataclass_fields__})
        except Exception:
            self.auz_set = auz.Setari()
        self.auz_ses = auz.Sesiune(self.auz_set)
        self._auz_gen = 0
        self.p_auz = pa = wx.Panel(self.carte)
        sa = wx.BoxSizer(wx.VERTICAL)

        def eticheta(text):
            t = wx.StaticText(pa, label=text)
            sa.Add(t, 0, wx.LEFT | wx.TOP, 4)
            return t

        eticheta('Exercițiul')
        self.a_ex = wx.Choice(pa, choices=auz.EXERCITII, name='Exercițiul')
        sa.Add(self.a_ex, 0, wx.ALL, 3)
        eticheta('Numele notelor')
        self.a_nume = wx.Choice(pa, choices=['Do Re Mi', 'C D E'], name='Numele notelor')
        sa.Add(self.a_nume, 0, wx.ALL, 3)
        eticheta('Octavele (bifezi cu spațiu)')
        self.a_oct = ListaBife(pa, choices=[f'Octava {o}' for o in range(2, 7)], name='Octavele', size=(-1, 70))
        sa.Add(self.a_oct, 0, wx.EXPAND | wx.ALL, 3)
        eticheta('Cât de des apar cele bifate mai jos')
        self.a_izol = wx.Choice(pa, choices=auz.IZOLARE, name='Cât de des apar cele bifate')
        sa.Add(self.a_izol, 0, wx.ALL, 3)
        self.a_e_note = eticheta('Notele exersate')
        self.a_note = ListaBife(pa, choices=auz.SOLFEGIU, name='Notele exersate', size=(-1, 90))
        sa.Add(self.a_note, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_int = eticheta('Intervalele exersate')
        self.a_int = ListaBife(pa, choices=auz.INTERVALE, name='Intervalele exersate', size=(-1, 90))
        sa.Add(self.a_int, 0, wx.EXPAND | wx.ALL, 3)
        self.a_e_red = eticheta('Cum se cântă intervalul')
        self.a_red = wx.Choice(pa, choices=auz.REDARE_INTERVAL, name='Cum se cântă intervalul')
        sa.Add(self.a_red, 0, wx.ALL, 3)
        self.a_e_ac = eticheta('Acordurile exersate')
        self.a_ac = ListaBife(pa, choices=[a[0] for a in auz.ACORDURI], name='Acordurile exersate', size=(-1, 90))
        sa.Add(self.a_ac, 0, wx.EXPAND | wx.ALL, 3)
        self.a_rast = wx.CheckBox(pa, label='Întreabă și răsturnarea')
        sa.Add(self.a_rast, 0, wx.ALL, 3)
        self.a_fund = wx.CheckBox(pa, label='Întreabă și fundamentala')
        sa.Add(self.a_fund, 0, wx.ALL, 3)
        eticheta('Câte greșeli până îți arăt răspunsul')
        self.a_gres = wx.SpinCtrl(pa, min=1, max=5, initial=2, name='Câte greșeli până îți arăt răspunsul')
        sa.Add(self.a_gres, 0, wx.ALL, 3)
        eticheta('Întrebarea')
        self.a_intreb = wx.TextCtrl(pa, style=wx.TE_READONLY, value='Alege exercițiul și apasă F4 sau Exercițiu nou.', name='Întrebarea')
        sa.Add(self.a_intreb, 0, wx.EXPAND | wx.ALL, 3)
        eticheta('Răspunsuri (Enter răspunde)')
        self.a_rasp = wx.ListBox(pa, name='Răspunsuri', size=(-1, 110))
        sa.Add(self.a_rasp, 1, wx.EXPAND | wx.ALL, 3)
        rand = wx.WrapSizer()
        for text, fn in (('Exercițiu nou (F4)', lambda e: self.auz_nou()), ('Ascultă din nou (F3)', lambda e: self.auz_asculta()),
                         ('Scorul', lambda e: self._auz_spune(self.auz_ses.scor.text())),
                         ('Scorul de la zero', lambda e: self._auz_scor_zero())):
            b = wx.Button(pa, label=text)
            b.Bind(wx.EVT_BUTTON, fn)
            rand.Add(b, 0, wx.ALL, 3)
        sa.Add(rand, 0, wx.EXPAND)
        pa.SetSizer(sa)
        self.carte.AddPage(pa, 'Exerciții de auz')
        # valorile salvate
        s = self.auz_set
        self.a_ex.SetSelection(s.exercitiu)
        self.a_nume.SetSelection(1 if s.litere else 0)
        for o in s.octave:
            if 2 <= o <= 6:
                self.a_oct.Check(o - 2)
        self.a_izol.SetSelection(s.izolare)
        for lista, bif in ((self.a_note, s.note_bifate), (self.a_int, s.intervale_bifate), (self.a_ac, s.acorduri_bifate)):
            for i in bif:
                if 0 <= i < lista.GetCount():
                    lista.Check(i)
        self.a_red.SetSelection(s.redare_interval)
        self.a_rast.SetValue(s.rasturnari)
        self.a_fund.SetValue(s.fundamentala)
        self.a_gres.SetValue(s.greseli_pana_la_raspuns)
        self._auz_arata_ce_trebuie()
        for c in (self.a_ex, self.a_nume, self.a_izol, self.a_red):
            c.Bind(wx.EVT_CHOICE, self._auz_schimbat)
        for c in (self.a_oct, self.a_note, self.a_int, self.a_ac):
            c.Bind(wx.EVT_LIST_ITEM_CHECKED, self._auz_schimbat)
            c.Bind(wx.EVT_LIST_ITEM_UNCHECKED, self._auz_schimbat)
        for c in (self.a_rast, self.a_fund):
            c.Bind(wx.EVT_CHECKBOX, self._auz_schimbat)
        self.a_gres.Bind(wx.EVT_SPINCTRL, self._auz_schimbat)
        self.a_rasp.Bind(wx.EVT_LISTBOX_DCLICK, lambda e: self.auz_raspunde())

    def _auz_arata_ce_trebuie(self):
        ex = self.a_ex.GetSelection()
        for ctrl, cand in ((self.a_e_note, 0), (self.a_note, 0), (self.a_e_int, 1), (self.a_int, 1), (self.a_e_red, 1),
                           (self.a_red, 1), (self.a_e_ac, 2), (self.a_ac, 2), (self.a_rast, 2), (self.a_fund, 2)):
            ctrl.Show(ex == cand)
        nume = auz.nume_note(self.a_nume.GetSelection() == 1)
        for i, n in enumerate(nume):
            self.a_note.SetString(i, n)
        self.p_auz.Layout()

    def _auz_schimbat(self, e=None):
        s = self.auz_set
        vechi_ex = s.exercitiu
        s.exercitiu = max(0, self.a_ex.GetSelection())
        s.litere = self.a_nume.GetSelection() == 1
        s.octave = [i + 2 for i in self.a_oct.GetCheckedItems()] or [4]
        s.izolare = max(0, self.a_izol.GetSelection())
        s.note_bifate = list(self.a_note.GetCheckedItems())
        s.intervale_bifate = list(self.a_int.GetCheckedItems())
        s.acorduri_bifate = list(self.a_ac.GetCheckedItems())
        s.redare_interval = max(0, self.a_red.GetSelection())
        s.rasturnari = self.a_rast.GetValue()
        s.fundamentala = self.a_fund.GetValue()
        s.greseli_pana_la_raspuns = self.a_gres.GetValue()
        self.setari['auz'] = dict(s.__dict__)
        scrie_setari(self.setari)
        self._auz_arata_ce_trebuie()
        if s.exercitiu != vechi_ex:
            self.auz_ses.ex = None
            self.a_rasp.Clear()
            self.a_intreb.SetValue('Apasă F4 sau Exercițiu nou.')
        if e:
            e.Skip()

    def _auz_spune(self, text):
        self.SetStatusText(text)
        voce.spune(text, intrerupe=True)

    def _auz_scor_zero(self):
        self.auz_ses.scor = auz.Scor()
        self._auz_spune('Scorul a pornit de la zero.')

    def _auz_arata_intrebarea(self):
        q = self.auz_ses.intrebare
        if q is None:
            return
        self.a_intreb.SetValue(q.text)
        self.a_rasp.Set(q.optiuni)
        self.a_rasp.SetSelection(0)

    def auz_nou(self):
        self._auz_schimbat()
        self.auz_ses.nou()
        self._auz_arata_intrebarea()
        self.a_rasp.SetFocus()
        self.auz_asculta()

    def auz_asculta(self):
        ex = self.auz_ses.ex
        if ex is None:
            self.auz_nou()
            return
        self.redare.opreste()
        try:
            self.sint.program = claviatura.INSTRUMENTE[self.instrument][1]
            self.sint.deschide()
        except Exception as exc:
            self._auz_spune(str(exc))
            return
        self._auz_gen += 1
        gen = self._auz_gen

        def canta():
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
        threading.Thread(target=canta, daemon=True).start()

    def auz_raspunde(self):
        i = self.a_rasp.GetSelection()
        if i < 0 or self.auz_ses.ex is None:
            return
        mesaj, gata = self.auz_ses.raspunde(i)
        self._auz_spune(mesaj)
        self.a_intreb.SetValue(mesaj)
        if not gata and self.auz_ses.intrebare and self.auz_ses.pas > 0 and mesaj.startswith('Corect'):
            q = self.auz_ses.intrebare
            self.a_rasp.Set(q.optiuni)
            self.a_rasp.SetSelection(0)
        if gata:
            # următorul exercițiu vine singur; după un răspuns arătat, mai târziu, ca să apuci să-l auzi
            wx.CallLater(1500 if mesaj.startswith('Răspuns corect') else 4000, self._auz_urmatorul, self.auz_ses.ex)

    def _auz_urmatorul(self, ex_vechi):
        if self.auz_ses.ex is ex_vechi and self.carte.GetSelection() == 4:
            self.auz_nou()

    # ---------------- claviatura ----------------
    def _clav_text(self):
        nume = claviatura.INSTRUMENTE[self.instrument][0]
        o = claviatura.nume_octava(self.do_clav)
        tr = f'transpus {self.transpunere:+d} semitonuri' if self.transpunere else 'netranspus'
        self.t_clav.SetValue(f'Claviatura. Instrument: {nume}. Shift stânga e do {o}, {tr}.\n'
                             'Rândul de jos, de la Shift stânga la 3 de pe blocul numeric: do, re, mi și tot așa, două octave. '
                             'Deasupra, de la Tab: do diez, re diez, W gol, fa diez, sol diez, la diez, Y gol, și tot așa.\n'
                             'Săgeată dreapta sau stânga: octava. Săgeată sus sau jos: instrumentul. '
                             'Control săgeată dreapta sau stânga: transpui cu un semiton. Escape: ieși.')
        self.t_clav.SetInsertionPoint(0)

    def _clav_intra(self, e):
        self.redare.opreste()            # sintetizatorul e folosit acum de claviatură
        try:
            self.sint.program = claviatura.INSTRUMENTE[self.instrument][1]
            self.sint.deschide()
        except Exception as ex:
            self.SetStatusText(str(ex))
            voce.spune(str(ex))
        e.Skip()

    def _clav_iese(self, e):
        self._apasate.clear()
        self.sint.inchide()              # eliberează sintetizatorul pentru redarea piesei
        e.Skip()

    def _clav_apasa(self, e):
        """O tastă apăsată cât ești în claviatură. Celelalte scurtături nu mai fac nimic aici."""
        k = e.GetKeyCode()
        if e.AltDown() or (wx.WXK_F1 <= k <= wx.WXK_F24):
            e.Skip()
            return
        sageata = {wx.WXK_LEFT: -1, wx.WXK_RIGHT: 1, wx.WXK_UP: 'sus', wx.WXK_DOWN: 'jos'}.get(k)
        if sageata is not None and self._sc_numeric(e):
            sageata = None               # 2 de pe blocul numeric fără Num Lock e notă (si), nu săgeată
        if e.ControlDown():
            if sageata in (-1, 1):
                self.transpune(sageata)
                return
            e.Skip()                     # Control 1, Control O și celelalte merg în continuare
            return
        if k == wx.WXK_ESCAPE:
            self.arata(0)
            return
        if sageata in (-1, 1):
            self.do_clav = min(84, max(24, self.do_clav + 12 * sageata))
            self.setari['octava_claviatura'] = self.do_clav
            scrie_setari(self.setari)
            text = str(claviatura.nume_octava(self.do_clav))
            self.SetStatusText(f'Octava {text}.')
            voce.spune(text, intrerupe=True)
            self._clav_text()
            return
        if sageata in ('sus', 'jos'):
            self.schimba_instrument(1 if sageata == 'jos' else -1)
            return
        sc = self._sc(e)
        if sc in claviatura.TASTE and sc not in self._apasate:
            nota = self.do_clav + claviatura.TASTE[sc] + self.transpunere
            self._apasate[sc] = nota
            if not self.sint.deschis():
                try:
                    self.sint.program = claviatura.INSTRUMENTE[self.instrument][1]
                    self.sint.deschide()
                except Exception as ex:
                    self.SetStatusText(str(ex))
            self.sint.apasa(nota)
        # orice altă tastă (litere, cifre, Tab, Enter...) nu face nimic aici

    def _clav_ridica(self, e):
        sc = self._sc(e)
        nota = self._apasate.pop(sc, None)
        if nota is not None:
            self.sint.ridica(nota)
        if e.GetKeyCode() == wx.WXK_SHIFT:   # la Shift, Windows nu spune mereu care dintre ele: le oprim pe amândouă
            for t in (0x2A, 0x36):
                n2 = self._apasate.pop(t, None)
                if n2 is not None:
                    self.sint.ridica(n2)

    @staticmethod
    def _sc(e):
        """Codul fizic al tastei (fără bitul de tastă extinsă: Shift dreapta și cel stâng diferă prin cod)."""
        if os.name != 'nt':
            return 0
        f = e.GetRawKeyFlags()
        sc = (f >> 16) & 0xFF
        if e.GetKeyCode() == wx.WXK_SHIFT and sc not in (0x2A, 0x36):
            sc = 0x2A
        if f & (1 << 24) and sc in (0x4F, 0x50, 0x51):
            return 0                     # End, săgeata jos, Page Down de lângă săgeți, nu cele de pe blocul numeric
        return sc

    def _sc_numeric(self, e):
        """Adevărat dacă tasta e 3 de pe blocul numeric fără Num Lock (aceeași cu Page Down): e notă, nu octavă."""
        return os.name == 'nt' and not (e.GetRawKeyFlags() & (1 << 24)) and ((e.GetRawKeyFlags() >> 16) & 0xFF) in claviatura.TASTE

    def transpune(self, pas):
        self.transpunere = min(12, max(-12, self.transpunere + pas))
        self.setari['transpunere'] = self.transpunere
        scrie_setari(self.setari)
        text = f'{self.transpunere:+d}' if self.transpunere else '0'
        self.SetStatusText(f'Transpus {text} semitonuri.')
        voce.spune(text.replace('+', 'plus ').replace('-', 'minus '), intrerupe=True)
        self._clav_text()

    def schimba_instrument(self, pas=0, index=None):
        n = len(claviatura.INSTRUMENTE)
        self.instrument = (self.instrument + pas) % n if index is None else index % n
        nume, prog = claviatura.INSTRUMENTE[self.instrument]
        self.sint.schimba_instrument(prog)
        self.setari['instrument'] = self.instrument
        scrie_setari(self.setari)
        self._sincronizeaza_setari()
        self.SetStatusText(f'Instrument: {nume}.')
        voce.spune(nume, intrerupe=True)
        self._clav_text()

    def _taste(self, e):
        """Tastele de redare, prinse direct din tastatură (după tasta fizică, oricare ar fi aranjarea tastaturii):
        Shift 1 / 2 / 3 tempoul; K redă, oprește, continuă; Shift K de la început; L și J măsura următoare și anterioară;
        Shift plus / minus volumul metronomului cu 1, cu Control cu 5. Nu se prind când scrii într-un câmp."""
        foc = wx.Window.FindFocus()
        if foc is self.t_clav:
            self._clav_apasa(e)
            return
        if foc in (self.w_dr, self.w_st):
            if e.ControlDown() and e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.scriere_asculta(masura=True)
                return
            if e.GetKeyCode() == wx.WXK_F2:
                self.scriere_spune_masura()
                return
        if foc is not None and foc.GetParent() is self.p_auz:
            if e.GetKeyCode() == wx.WXK_F3:
                self.auz_asculta(); return
            if e.GetKeyCode() == wx.WXK_F4:
                self.auz_nou(); return
            if foc is self.a_rasp and e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.auz_raspunde(); return
        if foc is not None and foc.GetParent() in (self.p_setari, self.p_scriere, self.p_auz):
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
        self.SetStatusText('Redare în buclă pornită.' if self.redare.bucla else 'Redare în buclă oprită.')

    # ---------------- din PDF în Braille ----------------
    def pdf_in_braille(self, e=None):
        with wx.FileDialog(self, 'Alege PDF-ul sau poza cu partitura', defaultDir=self.setari.get('folder', ''),
                           wildcard='PDF și imagini|*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff|Toate partiturile|' +
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
            self.mesaj('Nu găsesc alte ferestre deschise. Deschide partitura în aplicația editurii și încearcă din nou.', 'Citește din fereastră')
            return
        d = wx.SingleChoiceDialog(self, 'Alege fereastra cu partitura. Mărește pagina cât poți în aplicația aceea, '
                                  'ca recunoașterea să fie mai bună. Data viitoare poți apăsa Control Alt P direct din ea.',
                                  'Citește din fereastră', [t for _, t in lista])
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
            self.mesaj(f'Nu am putut face poza paginii. {ex}', 'Citește din fereastră')
            return
        self.Raise()
        self.deschide(cale, pastreaza=False, titlu=f'Pagina din {titlu}', dupa=lambda: captura.sterge(cale))

    # ---------------- salvare ----------------
    def _cere_salvare(self, titlu, nume, filtru):
        with wx.FileDialog(self, titlu, defaultDir=self.setari.get('folder', ''), defaultFile=nume, wildcard=filtru,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as d:
            return d.GetPath() if d.ShowModal() == wx.ID_OK else None

    def _interzis_salvare(self):
        if getattr(self.P, 'fara_salvare', False):
            self.mesaj('Pagina aceasta e citită din aplicația editurii, așa că nu se salvează. O poți citi aici în cuvinte și în Braille.',
                       'Nu se salvează')
            return True
        return False

    def _baza(self):
        return self.P.titlu if self.P else 'partitura'

    def salveaza_cuvinte(self, e=None):
        if not self.P or self._interzis_salvare():
            return
        cale = self._cere_salvare('Salvează textul în cuvinte', self._baza() + '.txt', 'Text (*.txt)|*.txt')
        if cale:
            with open(cale, 'w', encoding='utf-8-sig') as f:
                f.write(self.P.descriere_generala() + '\n\n' + self.t_cuvinte.GetValue())
            self.SetStatusText('Salvat: ' + cale)

    def salveaza_braille(self, brf):
        if not self.P or self._interzis_salvare():
            return
        cale = self._cere_salvare('Salvează Braille', self._baza() + ('.brf' if brf else ' braille.txt'),
                                  'Braille pentru imprimantă (*.brf)|*.brf' if brf else 'Text Unicode (*.txt)|*.txt')
        if not cale:
            return
        s = self.selectie() or (self.P.numere[0], self.P.numere[-1], list(range(len(self.P.portative))))
        wait = wx.BusyInfo('Se pregătește Braille...', self)
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
        self.SetStatusText('Salvat: ' + cale)

    def salveaza_musicxml(self, e=None):
        if not self.P or self._interzis_salvare():
            return
        cale = self._cere_salvare('Salvează ca MusicXML', self._baza() + '.musicxml', 'MusicXML (*.musicxml)|*.musicxml')
        if cale:
            s = self.selectie() or (self.P.numere[0], self.P.numere[-1], list(range(len(self.P.portative))))
            self.P.extrage(*s).write('musicxml', fp=cale)
            self.SetStatusText('Salvat: ' + cale)

    # ---------------- altele ----------------
    def alege_program(self, care):
        nume = {'audiveris': 'Audiveris', 'musescore': 'MuseScore', 'homr': 'homr'}[care]
        with wx.FileDialog(self, f'Unde e {nume}.exe', wildcard='Programe (*.exe;*.bat)|*.exe;*.bat', style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as d:
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
            self.SetStatusText(f'Regatul Partiturilor s-a actualizat la versiunea {VERSIUNE}.')
            voce.spune('100 la sută. Actualizare terminată.')
        if vechi != VERSIUNE:
            self.setari['versiune_vazuta'] = VERSIUNE
            scrie_setari(self.setari)

    def verifica_actualizari(self, manual=False):
        if not actualizare.instalat():
            if manual:
                self.mesaj('Actualizarea automată merge doar la programul instalat cu RegatulPartiturilor-Setup.exe.', 'Actualizări')
            return
        if getattr(self, '_actualizare_in_curs', False):
            if manual:
                voce.spune('Actualizarea e deja în curs.')
            return

        def lucru():
            try:
                v = actualizare.versiune_noua()
                if not v:
                    if manual:
                        wx.CallAfter(self.mesaj, f'Ai deja ultima versiune, {VERSIUNE}.', 'Actualizări')
                    return
                self._actualizare_in_curs = True
                voce.spune('Se actualizează.')
                wx.CallAfter(self._arata_progres, v, 'Se actualizează.')
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
                        voce.spune(f'{zece} la sută.')

                cale = actualizare.descarca_setup(v, progres)
                wx.CallAfter(self._instaleaza, v, cale)
            except Exception as ex:
                self._actualizare_in_curs = False
                wx.CallAfter(self._inchide_progres)
                if manual or getattr(self, '_dlg_progres', None) is not None:
                    voce.spune('Actualizarea nu a reușit.')
                    wx.CallAfter(self.mesaj, f'Nu am putut descărca actualizarea. Verifică internetul. ({ex})', 'Actualizări')
        threading.Thread(target=lucru, daemon=True).start()

    def _arata_progres(self, v, text):
        self._dlg_progres = DialogProgres(self, f'Actualizare la versiunea {v}', text)
        self._dlg_progres.Show()
        self.SetStatusText(text)

    def _progres(self, procent):
        text = f'Se actualizează: {procent} la sută.'
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
            self.Close()
            # dacă ceva ține programul deschis, îl închidem de tot, ca instalarea să poată înlocui fișierele
            t = threading.Timer(4.0, os._exit, [0])
            t.daemon = True
            t.start()
        except Exception as ex:
            self._actualizare_in_curs = False
            self.mesaj(f'Nu am putut porni actualizarea: {ex}', 'Actualizări')

    def la_inchidere(self, e):
        self.redare.opreste()
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
        e.Skip()


ID_TASTA_GLOBALA = 0x5250


class ListaBife(wx.ListCtrl):
    """Listă cu căsuțe de bifat (controlul listă din Windows: NVDA spune „bifat” / „nebifat”, bifezi cu spațiu)."""
    def __init__(self, parinte, choices, name, size=(-1, -1)):
        super().__init__(parinte, style=wx.LC_REPORT | wx.LC_NO_HEADER | wx.LC_SINGLE_SEL, size=size, name=name)
        self.AppendColumn(name, width=320)
        self.EnableCheckBoxes(True)
        for c in choices:
            self.Append([c])
        if choices:
            self.Focus(0)

    def GetCount(self):
        return self.GetItemCount()

    def Check(self, i, bifat=True):
        self.CheckItem(i, bifat)

    def GetCheckedItems(self):
        return [i for i in range(self.GetItemCount()) if self.IsItemChecked(i)]

    def SetString(self, i, text):
        self.SetItemText(i, text)


class DialogText(wx.Dialog):
    """Mesaj citibil rând cu rând (un câmp de text), cu buton OK."""
    def __init__(self, parinte, titlu, text):
        super().__init__(parinte, title=titlu, size=(640, 420))
        s = wx.BoxSizer(wx.VERTICAL)
        s.Add(wx.StaticText(self, label=titlu), 0, wx.ALL, 6)
        t = wx.TextCtrl(self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, name=titlu)
        s.Add(t, 1, wx.EXPAND | wx.ALL, 6)
        b = wx.Button(self, wx.ID_OK, 'OK')
        s.Add(b, 0, wx.ALIGN_RIGHT | wx.ALL, 6)
        self.SetSizer(s)
        self.SetEscapeId(wx.ID_OK)
        t.SetFocus()


class DialogProgres(wx.Dialog):
    """Fereastră cu progresul actualizării: un text citibil și o bară de progres."""
    def __init__(self, parinte, titlu, text):
        super().__init__(parinte, title=titlu, size=(520, 200), style=wx.CAPTION | wx.STAY_ON_TOP)
        s = wx.BoxSizer(wx.VERTICAL)
        self.t = wx.TextCtrl(self, value=text, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_NO_VSCROLL, name='Progresul actualizării')
        s.Add(self.t, 1, wx.EXPAND | wx.ALL, 8)
        self.g = wx.Gauge(self, range=100, name='Progresul actualizării')
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
        rez.append('SCRIERE LITERE ' + str(len(scriere.construieste('c4p d e f\nbb4d c#5d', '')[0].parts[0].recurse().notes)))
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
        rez.append('CUPRINS in Recunoscute: ' + str(os.path.isfile(os.path.join(d_pdf, 'Recunoscute', 'carte', 'cuprins.json'))))
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
