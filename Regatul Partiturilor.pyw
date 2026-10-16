"""Regatul Partiturilor – citește partituri pentru nevăzători: în cuvinte și în Braille muzical.
Fereastra folosește controale Windows obișnuite, ca NVDA să le citească bine.
"""
import json
import os
import shutil
import sys
import tempfile
import threading
import traceback

# În programul instalat (fără consolă) nu există stdout/stderr; unele biblioteci scriu acolo și s-ar opri cu eroare.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

import wx  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nucleu import VERSIUNE, actualizare, braille, captura, cuprins, cuvinte, partitura, recunoastere, redare, voce  # noqa: E402

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
Alt plus săgeată dreapta: măsura următoare.
Alt plus săgeată stânga: măsura anterioară.
Control plus G: mergi la o anumită măsură.
Control plus 1: textul în cuvinte.
Control plus 2: textul în Braille.
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
F5: redă selecția. Shift plus F5: redă de la măsura aleasă până la final.
F6: pauză sau continuă. F7: oprește.
Control plus minus: mai încet. Control plus plus (egal): mai repede. Control plus 0: tempoul scris.
Control plus R: redare în buclă, pornită sau oprită.

Citește din fereastră (pentru aplicațiile editurilor, din care nu se poate descărca):
Control plus Alt plus P, apăsat din aplicația editurii: citește pagina afișată acum.
Control plus Shift plus F: alegi fereastra dintr-o listă.
Nu se salvează nimic: poza paginii se șterge imediat după recunoaștere.

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
        self._ocupat_recunoastere = False
        self._braille_id = 0
        self._meniuri()
        self._interfata()
        self._aplica_setari()
        self.CreateStatusBar()
        self.SetStatusText('Deschide o partitură cu Control plus O.')
        self.SetDropTarget(Picurare(self))
        self.Bind(wx.EVT_CLOSE, self.la_inchidere)
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
        self._m(n, 'Măsura următoare\tAlt+Right', lambda e: self.muta(1))
        self._m(n, 'Măsura anterioară\tAlt+Left', lambda e: self.muta(-1))
        self._m(n, 'Mergi la măsura...\tCtrl+G', self.mergi_la)
        self._m(n, 'Următoarea măsură de verificat\tCtrl+U', lambda e: self.la_nesigura(1))
        self._m(n, 'Măsura de verificat anterioară\tCtrl+Shift+U', lambda e: self.la_nesigura(-1))
        n.AppendSeparator()
        self._m(n, 'Textul în cuvinte\tCtrl+1', lambda e: self.arata(0))
        self._m(n, 'Textul în Braille\tCtrl+2', lambda e: self.arata(1))
        self._m(n, 'Lista de măsuri\tCtrl+L', lambda e: self.lista.SetFocus())
        mb.Append(n, '&Navigare')
        r = wx.Menu()
        self._m(r, 'Redă selecția\tF5', lambda e: self.reda(False))
        self._m(r, 'Redă de aici până la final\tShift+F5', lambda e: self.reda(True))
        self._m(r, 'Pauză sau continuă\tF6', self.pauza)
        self._m(r, 'Oprește\tF7', self.opreste)
        r.AppendSeparator()
        self._m(r, 'Mai încet\tCtrl+-', lambda e: self.schimba_tempo(-10))
        self._m(r, 'Mai repede\tCtrl+=', lambda e: self.schimba_tempo(10))
        self._m(r, 'Tempoul scris\tCtrl+0', lambda e: self.schimba_tempo(0))
        self.m_bucla = r.AppendCheckItem(wx.ID_ANY, 'Redare în buclă\tCtrl+R')
        self.Bind(wx.EVT_MENU, self.comuta_bucla, self.m_bucla)
        mb.Append(r, '&Redare')
        s = wx.Menu()
        self._m(s, 'Unde e instalat Audiveris (pentru PDF și poze)...', lambda e: self.alege_program('audiveris'))
        self._m(s, 'Unde e instalat MuseScore (pentru fișiere MuseScore)...', lambda e: self.alege_program('musescore'))
        self._m(s, 'Unde e instalat homr (al doilea program de recunoaștere)...', lambda e: self.alege_program('homr'))
        mb.Append(s, '&Setări')
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
        self.carte.AddPage(pc, 'În cuvinte')
        self.carte.AddPage(pb, 'Braille')
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
        self.c_voci.SetValue(o.get('voci', True))

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
            try:
                P = partitura.incarca(cale, progres=lambda m: wx.CallAfter(self.SetStatusText, m), pastreaza=pastreaza,
                                      baza=baza, folder=folder, original=original)
                if titlu and P.scor.metadata is not None:
                    P.scor.metadata.title = titlu
                P.fara_salvare = not pastreaza
                fis_brf = None
                if brf:
                    sursa = original or cale
                    dir_brf = recunoastere.folder_rezultate(sursa)
                    os.makedirs(dir_brf, exist_ok=True)
                    fis_brf = os.path.join(dir_brf, recunoastere.nume_scurt(baza or os.path.splitext(os.path.basename(cale))[0], sursa) + '.brf')
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
            self.setari['optiuni'] = o.__dict__
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
                txt = braille.din_scor(self.P.extrage(*s))
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
        (self.t_cuvinte if pagina == 0 else self.t_braille).SetFocus()
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
            cale = redare.fa_midi(self.P.extrage(prima, ultima, port), self.procent)
            self.redare.bucla = self.m_bucla.IsChecked()
            self.redare.canta(cale)
            unde = f'măsura {prima}' if prima == ultima else f'măsurile {prima}-{ultima}'
            self.SetStatusText(f'Se cântă {unde}, tempo {self.procent} la sută' + (', în buclă.' if self.redare.bucla else '.'))
        except Exception as ex:
            traceback.print_exc()
            self.mesaj(f'Nu am putut reda. Eroare: {ex}', 'Redare')

    def _portative_alese(self):
        k = self.portative.GetSelection()
        return list(range(len(self.P.portative))) if k <= 0 else [k - 1]

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
        self.procent = 100 if pas == 0 else min(200, max(20, self.procent + pas))
        self.setari['tempo'] = self.procent
        scrie_setari(self.setari)
        self.SetStatusText(f'Tempo: {self.procent} la sută din cel scris. Se aplică la următoarea redare (F5).')

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
            txt = braille.din_scor(self.P.extrage(*s))
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
        except Exception as ex:
            self._actualizare_in_curs = False
            self.mesaj(f'Nu am putut porni actualizarea: {ex}', 'Actualizări')

    def la_inchidere(self, e):
        self.redare.opreste()
        if os.name == 'nt':
            try:
                self.UnregisterHotKey(ID_TASTA_GLOBALA)
            except Exception:
                pass
        self.setari['optiuni'] = self.optiuni().__dict__
        scrie_setari(self.setari)
        e.Skip()


ID_TASTA_GLOBALA = 0x5250


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
        rez.append(braille.din_scor(P.extrage(P.numere[0], P.numere[0] + 3, list(range(len(P.portative))))))
        app = wx.App(False)
        f = Fereastra()
        f._deschisa(P, None)
        f.lista.SetSelection(3)
        f.actualizeaza()
        rez.append('FEREASTRA ' + f.t_cuvinte.GetValue()[:200])
        cale_midi = redare.fa_midi(P.extrage(P.numere[0], P.numere[0] + 3, [0]), 50)
        rez.append(f'MIDI {os.path.getsize(cale_midi)} octeti')
        os.remove(cale_midi)
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
        rez.append('CUPRINS in Recunoscute: ' + str(os.path.isfile(os.path.join(d_pdf, 'Recunoscute', 'carte', 'cuprins.json'))))
        from nucleu import verificare
        rez.append('MAINI impartite in exemplu: ' + str(verificare.imparte_mainile(P.scor)))
        shutil.rmtree(d_pdf, ignore_errors=True)
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
    app = wx.App(False)
    app.SetAppName(NUME)
    fisier = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    Fereastra(fisier).Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
