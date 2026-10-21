"""Sunete adevărate pentru claviatură și exercițiile de auz: FluidSynth (libfluidsynth-3.dll) cu banca de sunete
GeneralUser GS (GeneralUser-GS.sf2, 261 de instrumente și 13 seturi de tobe, gratuită și voie de redistribuit).
Fișierele stau în folderul „sunete” de lângă program (le pune acolo compilarea de pe GitHub).
Dacă lipsesc, programul folosește sintetizatorul din Windows (claviatura.Sintetizator), cu lista General MIDI.

Instrumentele sunt împărțite pe categorii (piane, corzi, suflători...) după numărul programului General MIDI;
un instrument e (bancă, program), ca să încapă și variantele (mai multe piane, orgi, chitare...)."""
import ctypes
import os
import struct
import sys
import threading

from . import limba
from .limba import _

DLL = 'libfluidsynth-3.dll'
SF2 = 'GeneralUser-GS.sf2'
BANCA_TOBE = 128
CANAL_TOBE = 9


def folder_sunete():
    """Folderul „sunete”: lângă exe în programul instalat, lângă cod când rulează din Python."""
    if getattr(sys, 'frozen', False):
        baza = os.path.dirname(sys.executable)
    else:
        baza = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(baza, 'sunete')


def exista():
    d = folder_sunete()
    return os.name == 'nt' and os.path.isfile(os.path.join(d, DLL)) and os.path.isfile(os.path.join(d, SF2))


# ---------------- categoriile ----------------
CATEGORII = [  # (numele, primul program, ultimul program)
    (_('Piane și clavecin'), 0, 7),
    (_('Clopoței, celestă și percuție melodică'), 8, 15),
    (_('Orgi și acordeoane'), 16, 23),
    (_('Chitare'), 24, 31),
    (_('Chitare bas'), 32, 39),
    (_('Corzi'), 40, 47),
    (_('Ansambluri de coarde și coruri'), 48, 55),
    (_('Alămuri'), 56, 63),
    (_('Suflători de lemn (ancii)'), 64, 71),
    (_('Flaute și fluiere'), 72, 79),
    (_('Sintetizatoare'), 80, 103),
    (_('Instrumente populare'), 104, 111),
    (_('Percuție'), 112, 119),
    (_('Efecte sonore'), 120, 127),
]
CATEGORIE_TOBE = _('Seturi de tobe (pe toată claviatura)')

# numele General MIDI în engleză (când nu e banca de sunete) și în română
GM_EN = ['Grand Piano', 'Bright Grand Piano', 'Electric Grand Piano', 'Honky-Tonk Piano', 'Electric Piano 1', 'Electric Piano 2',
         'Harpsichord', 'Clavinet', 'Celesta', 'Glockenspiel', 'Music Box', 'Vibraphone', 'Marimba', 'Xylophone', 'Tubular Bells',
         'Dulcimer', 'Drawbar Organ', 'Percussive Organ', 'Rock Organ', 'Church Organ', 'Reed Organ', 'Accordion', 'Harmonica',
         'Bandoneon', 'Nylon Guitar', 'Steel Guitar', 'Jazz Guitar', 'Clean Guitar', 'Muted Guitar', 'Overdrive Guitar',
         'Distortion Guitar', 'Guitar Harmonics', 'Acoustic Bass', 'Finger Bass', 'Pick Bass', 'Fretless Bass', 'Slap Bass 1',
         'Slap Bass 2', 'Synth Bass 1', 'Synth Bass 2', 'Violin', 'Viola', 'Cello', 'Double Bass', 'Tremolo Strings',
         'Pizzicato Strings', 'Orchestral Harp', 'Timpani', 'String Ensemble 1', 'String Ensemble 2', 'Synth Strings 1',
         'Synth Strings 2', 'Choir Aahs', 'Voice Oohs', 'Synth Voice', 'Orchestra Hit', 'Trumpet', 'Trombone', 'Tuba',
         'Muted Trumpet', 'French Horn', 'Brass Section', 'Synth Brass 1', 'Synth Brass 2', 'Soprano Sax', 'Alto Sax', 'Tenor Sax',
         'Baritone Sax', 'Oboe', 'English Horn', 'Bassoon', 'Clarinet', 'Piccolo', 'Flute', 'Recorder', 'Pan Flute', 'Bottle Blow',
         'Shakuhachi', 'Whistle', 'Ocarina', 'Square Lead', 'Saw Lead', 'Calliope', 'Chiff Lead', 'Charang', 'Voice Lead',
         'Fifths Lead', 'Bass and Lead', 'New Age Pad', 'Warm Pad', 'Polysynth', 'Choir Pad', 'Bowed Glass', 'Metallic Pad',
         'Halo Pad', 'Sweep Pad', 'Rain', 'Soundtrack', 'Crystal', 'Atmosphere', 'Brightness', 'Goblins', 'Echoes', 'Sci-Fi',
         'Sitar', 'Banjo', 'Shamisen', 'Koto', 'Kalimba', 'Bagpipe', 'Fiddle', 'Shanai', 'Tinkle Bell', 'Agogo', 'Steel Drums',
         'Woodblock', 'Taiko Drum', 'Melodic Tom', 'Synth Drum', 'Reverse Cymbal', 'Guitar Fret Noise', 'Breath Noise',
         'Seashore', 'Bird Tweet', 'Telephone Ring', 'Helicopter', 'Applause', 'Gunshot']
GM_RO = ['Pian de concert', 'Pian luminos', 'Pian electric de concert', 'Pian de bar (honky-tonk)', 'Pian electric 1',
         'Pian electric 2', 'Clavecin', 'Clavinet', 'Celestă', 'Glockenspiel', 'Cutie muzicală', 'Vibrafon', 'Marimba', 'Xilofon',
         'Clopote tubulare', 'Țambal', 'Orgă electrică', 'Orgă percutantă', 'Orgă rock', 'Orgă de biserică', 'Armoniu', 'Acordeon',
         'Muzicuță', 'Bandoneon', 'Chitară clasică', 'Chitară acustică', 'Chitară de jazz', 'Chitară electrică curată',
         'Chitară electrică surdinizată', 'Chitară cu overdrive', 'Chitară cu distorsiune', 'Armonice de chitară',
         'Contrabas acustic', 'Chitară bas cu degetele', 'Chitară bas cu pana', 'Chitară bas fără taste', 'Bas slap 1',
         'Bas slap 2', 'Bas de sintetizator 1', 'Bas de sintetizator 2', 'Vioară', 'Violă', 'Violoncel', 'Contrabas',
         'Corzi în tremolo', 'Corzi pizzicato', 'Harpă', 'Timpane', 'Ansamblu de coarde 1', 'Ansamblu de coarde 2',
         'Coarde de sintetizator 1', 'Coarde de sintetizator 2', 'Cor', 'Voci (oo)', 'Voce de sintetizator', 'Lovitură de orchestră',
         'Trompetă', 'Trombon', 'Tubă', 'Trompetă cu surdină', 'Corn', 'Secție de alămuri', 'Alămuri de sintetizator 1',
         'Alămuri de sintetizator 2', 'Saxofon sopran', 'Saxofon alto', 'Saxofon tenor', 'Saxofon bariton', 'Oboi', 'Corn englez',
         'Fagot', 'Clarinet', 'Piccolo', 'Flaut', 'Blockflöte', 'Nai', 'Suflat în sticlă', 'Shakuhachi', 'Fluierat', 'Ocarină',
         'Sintetizator pătrat', 'Sintetizator dinte de fierăstrău', 'Calliope', 'Sintetizator chiff', 'Charang', 'Voce sintetizată',
         'Sintetizator în cvinte', 'Bas și solo', 'Pad New Age', 'Pad cald', 'Polisintetizator', 'Pad de cor', 'Sticlă cu arcuș',
         'Pad metalic', 'Pad aureolă', 'Pad măturat', 'Ploaie', 'Coloană sonoră', 'Cristal', 'Atmosferă', 'Strălucire', 'Spiriduși',
         'Ecouri', 'Științifico-fantastic', 'Sitar', 'Banjo', 'Shamisen', 'Koto', 'Kalimba', 'Cimpoi', 'Lăută populară (fiddle)',
         'Shehnai', 'Clopoțel', 'Agogo', 'Tobe de oțel', 'Tobă de lemn', 'Tobă taiko', 'Tom melodic', 'Tobă de sintetizator',
         'Cinel invers', 'Zgomot de corzi de chitară', 'Respirație', 'Valuri de mare', 'Ciripit de păsări', 'Sonerie de telefon',
         'Elicopter', 'Aplauze', 'Împușcătură']


def nume_instrument(banca, program, nume_sf=None):
    if limba.LIMBA == 'ro' and banca == 0 and 0 <= program < 128:
        return GM_RO[program]
    if nume_sf:
        return nume_sf
    if 0 <= program < 128:
        return GM_RO[program] if limba.LIMBA == 'ro' else GM_EN[program]
    return str(program)


def presetari_sf2(cale):
    """Lista (bancă, program, nume) din fișierul SoundFont (bucata „phdr”), fără FluidSynth."""
    with open(cale, 'rb') as f:
        d = f.read(12)
        if d[:4] != b'RIFF' or d[8:12] != b'sfbk':
            return []
        while True:
            h = f.read(8)
            if len(h) < 8:
                return []
            cid, n = h[:4], struct.unpack('<I', h[4:])[0]
            if cid == b'LIST' and f.read(4) == b'pdta':
                sfarsit = f.tell() + n - 4
                while f.tell() < sfarsit:
                    sh = f.read(8)
                    sid, sn = sh[:4], struct.unpack('<I', sh[4:])[0]
                    if sid == b'phdr':
                        date = f.read(sn)
                        out = []
                        for i in range(0, sn - 38, 38):       # ultima înregistrare e „EOP”
                            nume = date[i:i + 20].split(b'\0')[0].decode('latin-1').strip()
                            program, banca = struct.unpack('<HH', date[i + 20:i + 24])
                            out.append((banca, program, nume))
                        return out
                    f.seek(sn + (sn & 1), 1)
                return []
            elif cid == b'LIST':
                f.seek(n - 4 + (n & 1), 1)
            else:
                f.seek(n + (n & 1), 1)


def catalog():
    """Categoriile cu instrumentele lor: [(nume categorie, [(nume, (bancă, program)), ...]), ...].
    Din banca de sunete dacă există; altfel cele 128 de instrumente General MIDI ale Windows."""
    pres = []
    if exista():
        try:
            pres = presetari_sf2(os.path.join(folder_sunete(), SF2))
        except Exception:
            pres = []
    if not pres:
        pres = [(0, p, GM_EN[p]) for p in range(128)]
    out = []
    for nume_cat, a, b in CATEGORII:
        inst = sorted((p, bc, nm) for bc, p, nm in pres if a <= p <= b and bc < 120)
        if inst:
            out.append((nume_cat, [(nume_instrument(bc, p, nm), (bc, p)) for p, bc, nm in inst]))
    tobe = sorted((p, nm) for bc, p, nm in pres if bc == BANCA_TOBE)
    if tobe:
        out.append((CATEGORIE_TOBE, [(nm, (BANCA_TOBE, p)) for p, nm in tobe]))
    return out


# ---------------- FluidSynth ----------------
class SintetizatorFluid:
    """Aceeași folosire ca claviatura.Sintetizator, dar cu FluidSynth și banca de sunete.
    Rămâne deschis cât merge programul (nu ocupă sintetizatorul MIDI al Windows, deci redarea piesei merge în paralel)."""
    exclusiv = False

    def __init__(self):
        self.program = (0, 0)
        self._temporar = None       # instrumentul pus pentru o clipă (exercițiile de auz, melodia de la pornire)
        self._f = None
        self._settings = self._synth = self._driver = None
        self._sfid = -1
        self._lacat = threading.Lock()

    def deschis(self):
        return self._driver is not None

    def _incarca_dll(self):
        d = folder_sunete()
        if hasattr(os, 'add_dll_directory'):
            self._dir = os.add_dll_directory(d)
        f = ctypes.CDLL(os.path.join(d, DLL))
        vp, ci, cs, cd = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_double
        for nume, res, args in (('new_fluid_settings', vp, []), ('delete_fluid_settings', None, [vp]),
                                ('fluid_settings_setstr', ci, [vp, cs, cs]), ('fluid_settings_setint', ci, [vp, cs, ci]),
                                ('fluid_settings_setnum', ci, [vp, cs, cd]),
                                ('new_fluid_synth', vp, [vp]), ('delete_fluid_synth', None, [vp]),
                                ('fluid_synth_sfload', ci, [vp, cs, ci]),
                                ('fluid_synth_program_select', ci, [vp, ci, ci, ci, ci]),
                                ('fluid_synth_noteon', ci, [vp, ci, ci, ci]), ('fluid_synth_noteoff', ci, [vp, ci, ci]),
                                ('fluid_synth_cc', ci, [vp, ci, ci, ci]), ('fluid_synth_all_notes_off', ci, [vp, ci]),
                                ('new_fluid_audio_driver', vp, [vp, vp]), ('delete_fluid_audio_driver', None, [vp])):
            fn = getattr(f, nume)
            fn.restype = res
            fn.argtypes = args
        return f

    def pregateste(self, cu_sunet=True):
        """Încarcă FluidSynth și banca de sunete; cu_sunet=False doar pentru probe (fără placă de sunet)."""
        with self._lacat:
            self._pregateste(cu_sunet)

    def _pregateste(self, cu_sunet):
        if self._synth is None:
            f = self._incarca_dll()
            s = f.new_fluid_settings()
            f.fluid_settings_setnum(s, b'synth.gain', 0.7)
            f.fluid_settings_setint(s, b'synth.polyphony', 256)
            f.fluid_settings_setint(s, b'audio.period-size', 128)     # întârziere foarte mică între tastă și sunet (~9 ms)
            f.fluid_settings_setint(s, b'audio.periods', 3)
            synth = f.new_fluid_synth(s)
            sfid = f.fluid_synth_sfload(synth, os.path.join(folder_sunete(), SF2).encode('mbcs' if os.name == 'nt' else 'utf-8'), 1)
            if sfid < 0:
                f.delete_fluid_synth(synth)
                f.delete_fluid_settings(s)
                raise RuntimeError(_('Banca de sunete nu s-a putut încărca.'))
            self._f, self._settings, self._synth, self._sfid = f, s, synth, sfid
        if cu_sunet and self._driver is None:
            f, s = self._f, self._settings
            for drv in (b'wasapi', b'dsound', b'waveout'):
                f.fluid_settings_setstr(s, b'audio.driver', drv)
                self._driver = f.new_fluid_audio_driver(s, self._synth)
                if self._driver:
                    break
            if not self._driver:
                raise RuntimeError(_('Placa de sunet nu se poate folosi pentru claviatură.'))
        self.schimba_instrument(self.program)

    def deschide(self):
        self.pregateste(True)

    def _canal(self, prog=None):
        banca, _p = prog or self._temporar or self.program
        return CANAL_TOBE if banca == BANCA_TOBE else 0

    def _selecteaza(self, prog):
        if self._synth is None:
            return
        banca, program = prog
        self._f.fluid_synth_program_select(self._synth, self._canal(prog), self._sfid, banca, program)
        for c in (0, CANAL_TOBE):
            self._f.fluid_synth_cc(self._synth, c, 7, 127)

    def schimba_instrument(self, prog):
        if isinstance(prog, int):
            prog = (0, prog)
        self.liniste()
        self.program = tuple(prog)
        self._selecteaza(self.program)

    def program_temporar(self, prog):
        self._temporar = (0, prog) if isinstance(prog, int) else tuple(prog)
        self._selecteaza(self._temporar)

    def program_inapoi(self):
        self._temporar = None
        self._selecteaza(self.program)

    def apasa(self, nota, tarie=110):
        if self._synth is not None and 0 <= nota <= 127:
            self._f.fluid_synth_noteon(self._synth, self._canal(), nota, tarie)

    def ridica(self, nota):
        if self._synth is not None and 0 <= nota <= 127:
            self._f.fluid_synth_noteoff(self._synth, self._canal(), nota)

    def liniste(self):
        if self._synth is not None:
            for c in (0, CANAL_TOBE):
                self._f.fluid_synth_all_notes_off(self._synth, c)

    def elibereaza(self):
        """Nu ocupă nimic altceva, deci rămâne deschis; doar oprește notele."""
        self.liniste()

    def inchide(self):
        if self._f is None:
            return
        try:
            self.liniste()
            if self._driver:
                self._f.delete_fluid_audio_driver(self._driver)
            if self._synth:
                self._f.delete_fluid_synth(self._synth)
            if self._settings:
                self._f.delete_fluid_settings(self._settings)
        except Exception:
            pass
        self._driver = self._synth = self._settings = None


def sintetizator():
    """Cel mai bun sintetizator care merge: FluidSynth cu banca de sunete, altfel cel din Windows."""
    if exista():
        return SintetizatorFluid()
    from .claviatura import Sintetizator
    return Sintetizator()
