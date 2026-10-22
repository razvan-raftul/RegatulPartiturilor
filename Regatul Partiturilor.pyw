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
from nucleu import VERSIUNE, actualizare, auz, midi_in, braille, captura, claviatura, cuprins, cuvinte, partitura, recunoastere, redare, scriere, sunet_iesire, sunet_pornire, sunete, voce  # noqa: E402

NUME = 'Music Box'
INDEMN = _('Nicio partitură deschisă. Deschide o partitură cu Control O.')
# setările: %APPDATA%\\Music Box (folderul vechi „Regatul Partiturilor” se redenumește singur, vezi limba.folder_setari)
DIR_SETARI = limba.DIR_SETARI
FIS_SETARI = os.path.join(DIR_SETARI, 'setari.json')
OCTAVE = [('fara', _('Fără octavă')), ('numere', _('Octava cu număr (do 4)')), ('nume', _('Octava cu nume (do din octava întâi)'))]
FILTRU = (_('Toate partiturile|') + ';'.join('*' + e for e in partitura.TOATE_FORMATELE) +
          _('|MusicXML (*.musicxml, *.xml, *.mxl)|*.musicxml;*.xml;*.mxl|MIDI (*.mid)|*.mid;*.midi|MuseScore (*.mscz)|*.mscz;*.mscx'
          '|PDF și imagini|*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff|Toate fișierele|*.*'))
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
În câmpurile mâinilor: Control plus Enter ascultă măsura pe care ești (ambele mâini), F2 spune pe ce măsură ești.
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
        self._m(n, _('Textul în cuvinte\tCtrl+1'), lambda e: self.arata(0))
        self._m(n, _('Player: toată piesa, derulezi cu J și L\tCtrl+2'), lambda e: self.arata(1))
        self._m(n, _('Textul în Braille\tCtrl+3'), lambda e: self.arata(2))
        self._m(n, _('Claviatura (cânți pe tastatură)\tCtrl+4'), lambda e: self.arata(3))
        self._m(n, _('Scrie o partitură\tCtrl+5'), lambda e: self.arata(4))
        self._m(n, _('Exerciții de auz\tCtrl+6'), lambda e: self.arata(5))
        self._m(n, _('Setările\tCtrl+7'), lambda e: self.arata(6))
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
        mb.Append(r, _('&Redare'))
        a = wx.Menu()
        self._m(a, _('Scurtături\tF1'), lambda e: self.mesaj(SCURTATURI + '\n\n' + _('Player (Control 2): cântă toată piesa, de la prima măsură până la capăt. K pornește, pune pauză și continuă; L derulează înainte 5 secunde, J înapoi 5 secunde, ca pe YouTube; I spune minutul și secunda la care ești și măsura; Home o ia de la început; Escape oprește. Tempoul (Shift 1, 2, 3) și metronomul (Control Shift M, Shift plus și minus) merg și în player.'), _('Scurtături')))
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
        pc = wx.Panel(self.carte)
        sc = wx.BoxSizer(wx.VERTICAL)
        sc.Add(wx.StaticText(pc, label=_('Textul în cuvinte')), 0, wx.ALL, 2)
        self.t_cuvinte = wx.TextCtrl(pc, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, name=_('Textul în cuvinte'))
        sc.Add(self.t_cuvinte, 1, wx.EXPAND | wx.ALL, 2)
        pc.SetSizer(sc)
        pb = wx.Panel(self.carte)
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
        self.carte.AddPage(pc, _('În cuvinte'))
        self.p_player = PaginaPlayer(self.carte, self)
        self.carte.AddPage(self.p_player, _('Player'))
        self.p_braille = pb
        self.carte.AddPage(pb, _('Braille'))
        self.carte.AddPage(pk, _('Claviatura'))
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
                 fara_cuprins=False):
        """Deschide o partitură. pastreaza=False: nu se salvează nimic (pagini din aplicațiile editurilor);
        titlu: numele afișat; dupa: funcție chemată la final (de exemplu ștergerea pozei); brf: salvează și BRF în Documente\\Music Box\\<nume PDF>."""
        if self._ocupat_recunoastere:
            self.mesaj(_('Încă se recunoaște partitura de dinainte. Așteaptă să se termine.'), _('Ocupat'))
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
        self.SetStatusText(_('Se deschide ') + (titlu or os.path.basename(cale)) + '...')
        self.t_cuvinte.SetValue(_('Se recunoaște partitura cu două programe și se compară măsură cu măsură. Poate dura câteva minute; '
                                'te anunț când e gata.') if e_imagine else _('Se deschide partitura, te rog așteaptă.'))
        self.t_braille.SetValue('')
        self.t_cuvinte.SetFocus()
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
        if not self.P or self.carte.GetCurrentPage() is not self.p_braille or self.t_braille.GetValue():
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

    def arata(self, pagina):
        self.carte.SetSelection(pagina)
        (self.t_cuvinte, self.p_player.t, self.t_braille, self.t_clav, self.w_titlu, self.a_ex, self.s_limba)[pagina].SetFocus()
        if self.carte.GetPage(pagina) is self.p_braille:
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
        if self.carte.GetCurrentPage() is self.p_braille:
            self.actualizeaza_braille()
        voce.spune(self.lista.GetString(nou), intrerupe=True)

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
                self.arata(self.carte.GetSelection())
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
                self.arata(0)
                return
        self.SetStatusText(_('Nu mai sunt măsuri de verificat în direcția asta.'))
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
            unde = _('măsura {0}', prima) if prima == ultima else _('măsurile {0}-{1}', prima, ultima)
            self.SetStatusText(_('Se cântă {0}, tempo {1} la sută', unde, self.procent) + (_(', în buclă.') if self.redare.bucla else '.'))
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(_('Nu am putut reda. Eroare: {0}', ex), _('Redare'))

    def _porneste(self, sel, de_la_ms=0, in_pauza=False):
        """Cântă selecția la tempoul de acum. MIDI-ul de bază se face o singură dată pentru o selecție."""
        if self._midi_cache[0] != sel:
            _x, prima, ultima, port = sel
            bucata = self.P.extrage(prima, ultima, list(port))
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

    def _portative_alese(self):
        k = self.portative.GetSelection()
        return list(range(len(self.P.portative))) if k <= 0 else [k - 1]

    def reda_sau_pauza(self):
        """K: dacă nu se cântă nimic, redă selecția; altfel oprește sau continuă de unde a rămas."""
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
        if wx.Window.FindFocus() is not self.t_clav and self.carte.GetCurrentPage() is not self.p_auz:
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
        rand = wx.WrapSizer()
        for text, fn in ((_('Verifică'), self.scriere_verifica),
                         (_('Ascultă tot'), lambda e: self.scriere_asculta(False)),
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
            date = redare.midi_octeti(bucata)
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
        eticheta(_('Sunetul exercițiilor (spațiu deschide o categorie, Enter alege)'))
        self.a_instr, self._noduri_auz = self._arbore_instrumente(pa, _('Sunetul exercițiilor'))
        sa.Add(self.a_instr, 0, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Octavele'))
        self.a_oct = ListaBife(pa, choices=[_('Octava {0}', o) for o in range(1, 8)], name=_('Octavele'), size=(-1, 90),
                               la_schimbare=self._auz_schimbat)
        sa.Add(self.a_oct, 0, wx.EXPAND | wx.ALL, 3)
        eticheta(_('Cât de des apar cele bifate mai jos'))
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
        eticheta(_('Câte greșeli până îți arăt răspunsul'))
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
        for text, fn in ((_('Exercițiu nou (punct)'), lambda e: self.auz_nou()), (_('Ascultă din nou (virgulă)'), lambda e: self.auz_asculta()),
                         (_('Scorul'), lambda e: self._auz_spune(self.auz_ses.scor.text())),
                         (_('Scorul de la zero'), lambda e: self._auz_scor_zero())):
            b = wx.Button(pa, label=text)
            b.Bind(wx.EVT_BUTTON, fn)
            rand.Add(b, 0, wx.ALL, 3)
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
        if self.auz_ses.ex is ex_vechi and self.carte.GetCurrentPage() is self.p_auz:
            self.auz_nou()

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
            self.arata(0)
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

    def _taste(self, e):
        """Tastele de redare, prinse direct din tastatură (după tasta fizică, oricare ar fi aranjarea tastaturii):
        Shift 1 / 2 / 3 tempoul; K redă, oprește, continuă; Shift K de la început; L și J măsura următoare și anterioară;
        Shift plus / minus volumul metronomului cu 1, cu Control cu 5. Nu se prind când scrii într-un câmp."""
        foc = wx.Window.FindFocus()
        if foc is self.t_clav:
            self._clav_apasa(e)
            return
        if self.carte.GetCurrentPage() is self.p_player and foc is not None and self._e_in(foc, self.p_player) \
                and self.p_player.tasta(e):
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
        if foc in (self.w_dr, self.w_st):
            if e.ControlDown() and e.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                self.scriere_asculta(masura=True)
                return
            if e.GetKeyCode() == wx.WXK_F2:
                self.scriere_spune_masura()
                return
        if self.carte.GetCurrentPage() is self.p_auz and (foc is None or self._e_in(foc, self.p_auz) or foc is self.carte):
            sc = (e.GetRawKeyFlags() >> 16) & 0xFF if os.name == 'nt' else 0
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
        s.Add(wx.StaticText(self, label=_('Player')), 0, wx.ALL, 2)
        self.t = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, name=_('Player'),
                             value=_('Player. K pornește și pune pauză, L înainte 5 secunde, J înapoi 5 secunde, I spune unde ești, Home de la început, Escape oprește. Tempoul (Shift 1, 2, 3) și metronomul (Control Shift M) merg și aici.'))
        s.Add(self.t, 1, wx.EXPAND | wx.ALL, 2)
        self.SetSizer(s)

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
        if e.ControlDown() or e.AltDown() or e.ShiftDown():
            return False
        if not self.f.P:
            if k in (ord('K'), ord('J'), ord('L'), wx.WXK_SPACE) or sc in (0x25, 0x24, 0x26):
                voce.spune(_('Deschide întâi o partitură.'), intrerupe=True)
                return True
            return False
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
        rez.append(f'AUZ DURATE {len(_ed.durate)} sunete, {len(_ed.pasi)} pasi, citit {auz.citeste_durate("2, 1/2")}, raspuns: {_sd.raspunde_text(", ".join(str(b) for b in _ed.durate))[0]}')
        rez.append('SCRIERE LITERE ' + str(len(scriere.construieste('c4p d e f\nbb4d c#5d', '')[0].parts[0].recurse().notes)))
        try:
            sf = sunete.SintetizatorFluid()
            sf.pregateste(cu_sunet=False)
            sf.schimba_instrument((0, 57))
            rez.append(f'SUNETE exista={sunete.exista()} instrumente={sum(len(i) for _c, i in sunete.catalog())} sfid={sf._sfid}')
            sf.inchide()
        except Exception as ex:
            rez.append(f'SUNETE eroare: {ex} exista={sunete.exista()}')
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
