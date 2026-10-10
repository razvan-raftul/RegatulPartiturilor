"""Regatul Partiturilor – citește partituri pentru nevăzători: în cuvinte și în Braille muzical.
Fereastra folosește controale Windows obișnuite, ca NVDA să le citească bine.
"""
import json
import os
import sys
import threading
import traceback

# În programul instalat (fără consolă) nu există stdout/stderr; unele biblioteci scriu acolo și s-ar opri cu eroare.
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w', encoding='utf-8')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w', encoding='utf-8')

import wx  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nucleu import VERSIUNE, actualizare, braille, cuvinte, partitura, recunoastere  # noqa: E402

NUME = 'Regatul Partiturilor'
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
        if actualizare.instalat() and fisier != '--autotest':
            wx.CallLater(1500, self.verifica_actualizari, False)

    # ---------------- interfață ----------------
    def _meniuri(self):
        mb = wx.MenuBar()
        f = wx.Menu()
        self._m(f, 'Deschide partitura...\tCtrl+O', self.cere_fisier)
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
        n.AppendSeparator()
        self._m(n, 'Textul în cuvinte\tCtrl+1', lambda e: self.arata(0))
        self._m(n, 'Textul în Braille\tCtrl+2', lambda e: self.arata(1))
        self._m(n, 'Lista de măsuri\tCtrl+L', lambda e: self.lista.SetFocus())
        mb.Append(n, '&Navigare')
        s = wx.Menu()
        self._m(s, 'Unde e instalat Audiveris (pentru PDF și poze)...', lambda e: self.alege_program('audiveris'))
        self._m(s, 'Unde e instalat MuseScore (pentru fișiere MuseScore)...', lambda e: self.alege_program('musescore'))
        mb.Append(s, '&Setări')
        a = wx.Menu()
        self._m(a, 'Scurtături\tF1', lambda e: self.mesaj(SCURTATURI, 'Scurtături'))
        self._m(a, 'Caută actualizări', lambda e: self.verifica_actualizari(True))
        self._m(a, 'Despre', lambda e: self.mesaj(f'{NUME}, versiunea {VERSIUNE}.\nCitește partituri în cuvinte și în Braille muzical.\n'
                                                  'Folosește music21 pentru note și Braille și Audiveris pentru recunoașterea PDF-urilor.', 'Despre'))
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

    def deschide(self, cale):
        self.setari['folder'] = os.path.dirname(cale)
        scrie_setari(self.setari)
        self.SetStatusText('Se deschide ' + os.path.basename(cale) + '...')
        self.t_cuvinte.SetValue('Se deschide partitura, te rog așteaptă.')
        self.t_cuvinte.SetFocus()
        self._ocupat = wx.BusyInfo('Se deschide partitura...', self) if os.path.splitext(cale)[1].lower() not in partitura.FORMATE_IMAGINE else None

        def lucru():
            try:
                P = partitura.incarca(cale, progres=lambda m: wx.CallAfter(self.SetStatusText, m))
                wx.CallAfter(self._deschisa, P, None)
            except (partitura.EroarePartitura, recunoastere.LipsaProgram) as ex:
                wx.CallAfter(self._deschisa, None, str(ex))
            except Exception as ex:
                traceback.print_exc()
                wx.CallAfter(self._deschisa, None, f'Nu am putut deschide partitura. Eroare: {ex}')
        threading.Thread(target=lucru, daemon=True).start()

    def _deschisa(self, P, eroare):
        self._ocupat = None
        if eroare:
            self.t_cuvinte.SetValue(eroare)
            self.SetStatusText('Partitura nu s-a deschis.')
            self.mesaj(eroare, 'Nu s-a deschis')
            return
        self.P = P
        self.SetTitle(f'{P.titlu} – {NUME}')
        self.lista.Set(['Despre piesă', 'Toată piesa'] + [('Anacruza' if n == 0 else f'Măsura {n}') for n in P.numere])
        self.portative.Set(['Toate portativele'] + [p.nume for p in P.portative])
        self.portative.SetSelection(0)
        self.lista.SetSelection(0)
        self.actualizeaza()
        self.SetStatusText(f'Deschisă: {P.titlu}. {len(P.numere)} măsuri.')
        self.lista.SetFocus()

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

    # ---------------- salvare ----------------
    def _cere_salvare(self, titlu, nume, filtru):
        with wx.FileDialog(self, titlu, defaultDir=self.setari.get('folder', ''), defaultFile=nume, wildcard=filtru,
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as d:
            return d.GetPath() if d.ShowModal() == wx.ID_OK else None

    def _baza(self):
        return self.P.titlu if self.P else 'partitura'

    def salveaza_cuvinte(self, e=None):
        if not self.P:
            return
        cale = self._cere_salvare('Salvează textul în cuvinte', self._baza() + '.txt', 'Text (*.txt)|*.txt')
        if cale:
            with open(cale, 'w', encoding='utf-8-sig') as f:
                f.write(self.P.descriere_generala() + '\n\n' + self.t_cuvinte.GetValue())
            self.SetStatusText('Salvat: ' + cale)

    def salveaza_braille(self, brf):
        if not self.P:
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
        if not self.P:
            return
        cale = self._cere_salvare('Salvează ca MusicXML', self._baza() + '.musicxml', 'MusicXML (*.musicxml)|*.musicxml')
        if cale:
            s = self.selectie() or (self.P.numere[0], self.P.numere[-1], list(range(len(self.P.portative))))
            self.P.extrage(*s).write('musicxml', fp=cale)
            self.SetStatusText('Salvat: ' + cale)

    # ---------------- altele ----------------
    def alege_program(self, care):
        nume = 'Audiveris' if care == 'audiveris' else 'MuseScore'
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

    def verifica_actualizari(self, manual=False):
        if not actualizare.instalat():
            if manual:
                self.mesaj('Actualizarea automată merge doar la programul instalat cu RegatulPartiturilor-Setup.exe.', 'Actualizări')
            return

        def lucru():
            try:
                v = actualizare.versiune_noua()
                if not v:
                    if manual:
                        wx.CallAfter(self.mesaj, f'Ai deja ultima versiune, {VERSIUNE}.', 'Actualizări')
                    return
                wx.CallAfter(self.SetStatusText, f'Se descarcă versiunea nouă, {v}...')
                cale = actualizare.descarca_setup(v)
                wx.CallAfter(self._instaleaza, v, cale)
            except Exception as ex:
                if manual:
                    wx.CallAfter(self.mesaj, f'Nu am putut verifica actualizările. Verifică internetul. ({ex})', 'Actualizări')
        threading.Thread(target=lucru, daemon=True).start()

    def _instaleaza(self, v, cale):
        wx.MessageBox(f'Am descărcat versiunea nouă, {v}. După ce apeși OK se instalează și programul se redeschide singur.',
                      'Versiune nouă', wx.OK | wx.ICON_INFORMATION, self)
        try:
            actualizare.porneste_setup(cale)
            self.Close()
        except Exception as ex:
            self.mesaj(f'Nu am putut porni actualizarea: {ex}', 'Actualizări')

    def la_inchidere(self, e):
        self.setari['optiuni'] = self.optiuni().__dict__
        scrie_setari(self.setari)
        e.Skip()


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
        f.Destroy()
        app.Destroy()
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
    app = wx.App(False)
    app.SetAppName(NUME)
    fisier = sys.argv[1] if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) else None
    Fereastra(fisier).Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
