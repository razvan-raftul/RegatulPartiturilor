"""Antrenament de auz absolut, după studiul Wong, Cheung, Ngan și Wong (2025), „Learning fast and accurate
absolute pitch judgment in adulthood”, Psychonomic Bulletin & Review.

Ce e ca în studiu:
- 288 de niveluri, câte 24 pentru fiecare notă nouă. Se începe cu fa; notele se adaugă pe rând, o dată sub,
  o dată deasupra: fa, mi, fa diez, mi bemol, sol, re, sol diez, do diez, la, do, si bemol, si.
- Pragul de trecere crește în cele 24 de niveluri ale unei note de la 20% la 90%.
- Fereastra de răspuns se scurtează; la ultimul nivel al fiecărei note e între 1183 ms (o notă) și 2028 ms (12 note).
  Răspunsul dat prea târziu e greșit; la fel nota greșită cu un semiton.
- Sunetul: pian, 800 ms, o notă la întâmplare din octavele 4, 5, 6.
- Sunetele „din afara grupului”: două semitonuri deasupra celei mai înalte note învățate și două sub cea mai joasă;
  le recunoști spunând „în afara grupului”. Dispar când nu mai e nicio notă neînvățată lângă grup.
- Întâi niveluri cu răspunsul spus, apoi fără.
- Înainte de un nivel poți asculta notele învățate, în cele trei octave, în ordine la întâmplare. Dacă le-ai ascultat,
  înainte de un nivel fără răspuns spus se aude 20 de secunde un sunet care coboară mereu (Shepard),
  ca să nu poți ține minte nota.
- Dacă treci un nivel cu o notă mai mare decât îți trebuia, sari direct la nivelul cu pragul acela (nu peste 23).
- De la 5 note învățate, după fiecare 15 niveluri încercate: două exerciții pentru nota cea mai slabă din ultimele
  15 niveluri (12 încercări cu răspuns spus, apoi 22 fără): e nota aceea sau alta?
- Ținta: 25 de ore în 8 săptămâni, cel puțin 2 ore pe săptămână. Zilele la rând se pierd după mai mult de 2 zile pauză.
- Testul: 144 de note, fără răspuns spus, 5 secunde fiecare: 12 note x 3 octave (4–6) x 2, întâi la pian, apoi
  la chitară (sunet pe care nu l-ai exersat); două note la rând sunt mereu la mai mult de o octavă una de alta.

Ce nu spune studiul și am ales noi: 20 de încercări pe nivel; nivelurile 1–16 ale fiecărei note au răspunsul spus,
17–24 nu; fereastra pornește cu 2 secunde mai lungă la primul nivel al unei note. După 10 încercări picate
la același nivel, cobori singur un nivel (în studiu se făcea prin cercetător).
"""
import datetime
import random
from dataclasses import dataclass, field

from .limba import _

ORDINE = [5, 4, 6, 3, 7, 2, 8, 1, 9, 0, 10, 11]   # fa, mi, fa diez, mi bemol, sol, re, sol diez, do diez, la, do, si bemol, si
NIVELURI_PE_NOTA = 24
NIVELURI = 12 * NIVELURI_PE_NOTA
INCERCARI = 20
CU_RASPUNS_PANA_LA = 16           # nivelurile 1..16 din fiecare notă au răspunsul spus
OCTAVE = [4, 5, 6]
DURATA_NOTA = 800                 # ms
FEREASTRA_TEST = 5000
AFARA = -1                        # răspunsul „în afara grupului” / „altă notă”
PIAN = (0, 0)
CHITARA = (0, 24)                 # chitară cu corzi de nailon
ORE_TINTA = 25
ORE_PE_SAPTAMANA = 2


def explicatie():
    return _(__doc__)


def nota_si_nivel(nivel):
    """Nivelul 1..288 -> (câte note sunt în grup, nivelul 1..24 al notei)."""
    nivel = max(1, min(NIVELURI, int(nivel)))
    return (nivel - 1) // NIVELURI_PE_NOTA + 1, (nivel - 1) % NIVELURI_PE_NOTA + 1


def prag(nivel_in_nota):
    """Câte procente trebuie la nivelul acesta (20 la primul, 90 la al 24-lea)."""
    return round(20 + 70 * (nivel_in_nota - 1) / (NIVELURI_PE_NOTA - 1))


def fereastra(nr_note, nivel_in_nota):
    """Timpul de răspuns în ms, de la începutul notei."""
    final = 1183 + (2028 - 1183) * (nr_note - 1) / 11
    return int(final + 2000 * (NIVELURI_PE_NOTA - nivel_in_nota) / (NIVELURI_PE_NOTA - 1))


def cu_raspuns(nivel_in_nota):
    return nivel_in_nota <= CU_RASPUNS_PANA_LA


def grup(nr_note):
    return ORDINE[:nr_note]


def din_afara(nr_note):
    """Notele (clasele 0–11) din afara grupului: +1 și +2 peste cea mai înaltă, −1 și −2 sub cea mai joasă,
    doar cele neînvățate."""
    if nr_note >= 12:
        return []
    g = grup(nr_note)
    jos, sus = min(g), max(g)          # grupul e mereu o bucată cromatică întreagă (do..si nu se rupe)
    rez = []
    for x in (sus + 1, sus + 2, jos - 1, jos - 2):
        pc = x % 12
        if pc not in g and pc not in rez:
            rez.append(pc)
    return rez


@dataclass
class Incercare:
    midi: int
    tinta: int                    # clasa notei (0–11) sau AFARA, la fel ca răspunsul corect
    raspuns: object = None        # ce ai răspuns (None = prea târziu)
    corect: bool = False
    timp: int = 0                 # ms


@dataclass
class Runda:
    tip: str                      # nivel, slab1, slab2, test
    incercari: list
    fereastra: int
    cu_raspuns: bool
    optiuni: list                 # (eticheta, valoarea răspunsului)
    nivel: int = 0
    nota_slaba: int = -1
    shepard: bool = False         # înainte se aude sunetul care coboară
    timbre: list = field(default_factory=list)   # la test: instrumentul fiecărei încercări
    inceput: float = 0.0

    def instrument(self, i):
        return self.timbre[i] if self.timbre else PIAN

    def raspunde(self, i, raspuns, timp_ms):
        """raspuns: clasa notei (0–11), AFARA, sau None (prea târziu). Întoarce True dacă e corect."""
        inc = self.incercari[i]
        inc.raspuns, inc.timp = raspuns, int(timp_ms)
        if raspuns is not None and self.tip in ('slab1', 'slab2') and raspuns != self.nota_slaba:
            raspuns = AFARA               # orice altă notă înseamnă „nu e nota aceea”
        inc.corect = raspuns is not None and raspuns == inc.tinta and timp_ms <= self.fereastra
        return inc.corect

    def procent(self):
        return round(100 * sum(i.corect for i in self.incercari) / max(1, len(self.incercari)))


def _test_ordine(rnd):
    """72 de note pe instrument (12 x 3 octave x 2), două la rând mereu la mai mult de 12 semitonuri."""
    note = [12 * (o + 1) + pc for pc in range(12) for o in OCTAVE for _r in range(2)]
    for _incercare in range(2000):
        ramase = note[:]
        rnd.shuffle(ramase)
        rez = []
        while ramase:
            bune = [n for n in ramase if not rez or abs(n - rez[-1]) > 12]
            if not bune:
                break
            # întâi notele din mijloc (octava 5), care au cele mai puține vecine bune
            bune.sort(key=lambda n: (abs(n - 78), rnd.random()))
            n = bune[0] if rnd.random() < 0.5 else rnd.choice(bune)
            rez.append(n)
            ramase.remove(n)
        if not ramase:
            return rez
    raise RuntimeError('ordinea testului')


class Antrenament:
    """Starea se ține într-un dicționar (se scrie în setari.json)."""

    def __init__(self, stare=None, litere=False):
        s = dict(stare or {})
        self.nivel = int(s.get('nivel', 1))
        self.picate = int(s.get('picate', 0))                  # încercări picate la nivelul curent
        self.incercate = int(s.get('incercate', 0))            # niveluri încercate în total
        self.ultimele = list(s.get('ultimele', []))[-15:]      # pe ultimele 15 niveluri: {nota: [corecte, total]}
        self.slab_de_facut = list(s.get('slab_de_facut', []))  # ['slab1', 'slab2'] când e rândul lor
        self.minute = dict(s.get('minute', {}))                 # 'AAAA-LL-ZZ' -> minute
        self.ascultat = bool(s.get('ascultat', False))
        self.trecut_288 = int(s.get('trecut_288', 0))
        self.teste = list(s.get('teste', []))
        self.litere = litere

    def stare(self):
        return {'nivel': self.nivel, 'picate': self.picate, 'incercate': self.incercate, 'ultimele': self.ultimele,
                'slab_de_facut': self.slab_de_facut, 'minute': self.minute, 'ascultat': self.ascultat,
                'trecut_288': self.trecut_288, 'teste': self.teste[-30:]}

    # ---- nume ----
    def nume(self, pc):
        from .auz import nume_note
        return nume_note(self.litere)[pc].lower()

    def nume_raspuns(self, v):
        return _('în afara grupului') if v == AFARA else self.nume(v)

    # ---- runde ----
    def urmatoarea(self, rnd=random):
        """Runda care urmează: exercițiile pentru nota slabă, dacă e rândul lor, altfel nivelul."""
        if self.slab_de_facut:
            return self._runda_slaba(self.slab_de_facut[0], rnd)
        return self._runda_nivel(rnd)

    def _runda_nivel(self, rnd):
        n, l = nota_si_nivel(self.nivel)
        g, afara = grup(n), din_afara(n)
        posibile = g + afara
        incercari = []
        for _i in range(INCERCARI):
            pc = rnd.choice(posibile)
            incercari.append(Incercare(12 * (rnd.choice(OCTAVE) + 1) + pc, pc if pc in g else AFARA))
        optiuni = [(self.nume(pc), pc) for pc in sorted(g)]
        if afara:
            optiuni.append((_('în afara grupului'), AFARA))
        cr = cu_raspuns(l)
        return Runda('nivel', incercari, fereastra(n, l), cr, optiuni, nivel=self.nivel,
                     shepard=(not cr and self.ascultat))

    def nota_slaba(self):
        g = grup(nota_si_nivel(self.nivel)[0])
        total = {pc: [0, 0] for pc in g}
        for d in self.ultimele:
            for k, (c, t) in d.items():
                pc = int(k)
                if pc in total:
                    total[pc][0] += c
                    total[pc][1] += t
        cu_date = [pc for pc in g if total[pc][1]]
        if not cu_date:
            return g[-1]
        return min(cu_date, key=lambda pc: total[pc][0] / total[pc][1])

    def _runda_slaba(self, tip, rnd):
        n, l = nota_si_nivel(self.nivel)
        tinta = self.nota_slaba()
        alte = [pc for pc in range(12) if pc != tinta]
        nr = 12 if tip == 'slab1' else 22
        incercari = []
        for _i in range(nr):
            pc = tinta if rnd.random() < 0.5 else rnd.choice(alte)
            incercari.append(Incercare(12 * (rnd.choice(OCTAVE) + 1) + pc, tinta if pc == tinta else AFARA))
        optiuni = [(self.nume(tinta), tinta), (_('altă notă'), AFARA)]
        return Runda(tip, incercari, fereastra(n, l), tip == 'slab1', optiuni, nota_slaba=tinta)

    def runda_test(self, rnd=random):
        incercari, timbre = [], []
        for instr in (PIAN, CHITARA):
            for m in _test_ordine(rnd):
                incercari.append(Incercare(m, m % 12))
                timbre.append(instr)
        optiuni = [(self.nume(pc), pc) for pc in range(12)]
        return Runda('test', incercari, FEREASTRA_TEST, False, optiuni, timbre=timbre)

    def mostre(self, pc, rnd=random):
        """Nota în cele trei octave, în ordine la întâmplare (doar notele învățate)."""
        self.ascultat = True
        o = OCTAVE[:]
        rnd.shuffle(o)
        return [12 * (x + 1) + pc for x in o]

    def invatate(self):
        return grup(nota_si_nivel(self.nivel)[0])

    # ---- încheierea unei runde ----
    def adauga_minute(self, minute, zi=None):
        zi = (zi or datetime.date.today()).isoformat()
        self.minute[zi] = round(self.minute.get(zi, 0) + minute, 2)

    def incheie(self, r: Runda, minute=0.0, zi=None):
        """Socotește runda; întoarce ce spune programul."""
        if minute:
            self.adauga_minute(minute, zi)
        p = r.procent()
        if r.tip == 'test':
            return self._incheie_test(r, zi)
        if r.tip in ('slab1', 'slab2'):
            if self.slab_de_facut and self.slab_de_facut[0] == r.tip:
                self.slab_de_facut.pop(0)
            urm = _(' Urmează al doilea exercițiu pentru ea, fără răspuns spus.') if self.slab_de_facut else ''
            return _('Exercițiul pentru {0}: {1} la sută corecte.', self.nume(r.nota_slaba), p) + urm
        # nivel
        self.ascultat = False
        stat = {}
        for inc in r.incercari:
            if inc.tinta != AFARA:
                c = stat.setdefault(str(inc.tinta), [0, 0])
                c[1] += 1
                c[0] += int(inc.corect)
        self.ultimele = (self.ultimele + [stat])[-15:]
        self.incercate += 1
        n, l = nota_si_nivel(self.nivel)
        trebuia = prag(l)
        if p >= trebuia:
            self.picate = 0
            if self.nivel == NIVELURI:
                self.trecut_288 += 1
                mesaj = _('Nivelul 288 trecut, cu {0} la sută. Ai învățat toate cele 12 note. Acum fă testul.', p)
            elif l == NIVELURI_PE_NOTA:
                self.nivel += 1
                nou = grup(n + 1)[-1]
                mesaj = _('Nivel trecut, cu {0} la sută. Notă nouă: {1}. Ascult-o de câteva ori înainte de nivelul următor.', p, self.nume(nou))
            else:
                tinta = l + 1
                while tinta < NIVELURI_PE_NOTA - 1 and prag(tinta + 1) <= p:
                    tinta += 1                     # sari la nivelul pe care l-ai fi trecut oricum (nu peste 23)
                sarit = tinta - (l + 1)
                self.nivel += tinta - l
                mesaj = _('Nivel trecut, cu {0} la sută.', p)
                if sarit:
                    mesaj += _(' Sari {0} niveluri.', sarit)
                mesaj += _(' Urmează nivelul {0}.', self.nivel)
        else:
            self.picate += 1
            mesaj = _('Nivelul nu e trecut: {0} la sută, trebuia {1}. Mai încearcă.', p, trebuia)
            if self.picate >= 10 and l > 1:
                self.nivel -= 1
                self.picate = 0
                mesaj = _('Nivelul nu e trecut: {0} la sută, trebuia {1}. După 10 încercări cobori un nivel, la {2}.', p, trebuia, self.nivel)
        if n >= 5 and self.incercate % 15 == 0 and not self.slab_de_facut:
            self.slab_de_facut = ['slab1', 'slab2']
            mesaj += _(' Acum două exerciții pentru nota ta cea mai slabă: {0}.', self.nume(self.nota_slaba()))
        return mesaj

    def _incheie_test(self, r, zi):
        pe_nota = {pc: [0, 0] for pc in range(12)}
        pe_instr = {'pian': [0, 0], 'chitara': [0, 0]}
        for i, inc in enumerate(r.incercari):
            pe_nota[inc.tinta][1] += 1
            pe_nota[inc.tinta][0] += int(inc.corect)
            k = 'pian' if r.instrument(i) == PIAN else 'chitara'
            pe_instr[k][1] += 1
            pe_instr[k][0] += int(inc.corect)
        sigure = [pc for pc in range(12) if pe_nota[pc][1] and pe_nota[pc][0] / pe_nota[pc][1] >= 0.9]
        rez = {'zi': (zi or datetime.date.today()).isoformat(), 'procent': r.procent(),
               'pian': round(100 * pe_instr['pian'][0] / max(1, pe_instr['pian'][1])),
               'chitara': round(100 * pe_instr['chitara'][0] / max(1, pe_instr['chitara'][1])),
               'note': {str(pc): pe_nota[pc] for pc in range(12)}, 'sigure': sigure}
        self.teste.append(rez)
        return self.text_test(rez)

    def text_test(self, rez):
        sig = ', '.join(self.nume(pc) for pc in rez['sigure']) or _('niciuna')
        return _('Testul: {0} la sută corecte. La pian {1}, la chitară {2}. Note recunoscute sigur (90 la sută): {3}, adică {4} din 12.',
                 rez['procent'], rez['pian'], rez['chitara'], sig, len(rez['sigure']))

    # ---- ce spune programul despre progres ----
    def minute_total(self):
        return sum(self.minute.values())

    def minute_saptamana(self, azi=None):
        azi = azi or datetime.date.today()
        luni = azi - datetime.timedelta(days=azi.weekday())
        return sum(m for z, m in self.minute.items() if luni <= datetime.date.fromisoformat(z) <= azi)

    def zile_la_rand(self, azi=None):
        """Zilele cu antrenament din șirul de acum; șirul se rupe după mai mult de 2 zile fără antrenament."""
        azi = azi or datetime.date.today()
        zile = sorted({datetime.date.fromisoformat(z) for z, m in self.minute.items() if m > 0}, reverse=True)
        if not zile or (azi - zile[0]).days > 3:
            return 0
        n = 1
        for a, b in zip(zile, zile[1:]):
            if (a - b).days > 3:
                break
            n += 1
        return n

    def text_timp(self, minute):
        minute = int(round(minute))
        o, m = divmod(minute, 60)
        if o and m:
            return _('{0} ore și {1} minute', o, m)
        if o:
            return _('{0} ore', o)
        return _('{0} minute', m)

    def descriere(self, azi=None):
        n, l = nota_si_nivel(self.nivel)
        g = grup(n)
        rand = [_('Nivelul {0} din 288: nota {1} din 12, nivelul {2} din 24.', self.nivel, n, l),
                _('Note învățate: {0}.', ', '.join(self.nume(pc) for pc in g))]
        afara = din_afara(n)
        if self.slab_de_facut:
            rand.append(_('Urmează exercițiul pentru nota cea mai slabă: {0}.', self.nume(self.nota_slaba())))
        else:
            rand.append(_('Ca să treci: {0} de note, cel puțin {1} la sută corecte, răspunsul în {2} secunde.',
                          INCERCARI, prag(l), str(round(fereastra(n, l) / 1000, 1)).replace('.', ',')))
            rand.append(_('Cu răspunsul spus după fiecare notă.') if cu_raspuns(l) else _('Fără răspuns spus.'))
            if afara:
                rand.append(_('Se aud și note din afara grupului: {0}.', ', '.join(self.nume(pc) for pc in sorted(afara))))
        if self.picate:
            rand.append(_('Încercări picate la nivelul acesta: {0}.', self.picate))
        rand.append(_('Timp de antrenament: {0} din {1} de ore. Săptămâna aceasta: {2}, ținta e cel puțin {3} ore.',
                      self.text_timp(self.minute_total()), ORE_TINTA, self.text_timp(self.minute_saptamana(azi)), ORE_PE_SAPTAMANA))
        rand.append(_('Zile la rând: {0}.', self.zile_la_rand(azi)))
        if self.teste:
            rand.append(_('Ultimul test, din {0}: ', self.teste[-1]['zi']) + self.text_test(self.teste[-1]))
        return '\n'.join(rand)


def shepard_wav(cale, secunde=20, rata=22050):
    """Sunetul care coboară mereu (Shepard–Risset), scris ca WAV. Se aude înainte de un nivel fără răspuns spus,
    dacă ai ascultat notele înainte, ca să nu poți ține nota minte."""
    import wave
    import numpy as np
    t = np.arange(int(secunde * rata)) / rata
    semnal = np.zeros_like(t)
    octave = 8
    perioada = 10.0                                   # în câte secunde coboară o octavă
    f_min = 27.5
    centru, latime = np.log2(f_min) + octave / 2, octave / 6
    for k in range(octave):
        poz = (k - t / perioada) % octave             # poziția în octave, coboară
        faza = 2 * np.pi * np.cumsum(f_min * 2 ** poz) / rata
        amp = np.exp(-0.5 * ((np.log2(f_min) + poz - centru) / latime) ** 2)
        semnal += amp * np.sin(faza)
    semnal /= np.max(np.abs(semnal))
    rampa = int(0.5 * rata)
    semnal[:rampa] *= np.linspace(0, 1, rampa)
    semnal[-rampa:] *= np.linspace(1, 0, rampa)
    date = (semnal * 0.35 * 32767).astype('<i2')
    with wave.open(cale, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rata)
        w.writeframes(date.tobytes())
    return cale
