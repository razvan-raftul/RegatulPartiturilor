"""Cuprinsul unei cărți de partituri (PDF): unde începe fiecare piesă (studiu, invențiune...).

Cum recunoaște începutul unei piese, la orice carte tipărită obișnuit:
- primul rând (sistem) al unei piese e retras spre dreapta față de celelalte rânduri, ca să încapă numărul sau titlul;
- piesa dinainte se termină cu bara dublă de final (o linie subțire și una groasă).
O piesă e „sigură” când are amândouă semnele. Dacă are doar unul, e marcată „nesigur” și programul spune unde să verifici,
în loc să ghicească. Cuprinsul găsit se salvează în Recunoscute\\<nume PDF>\\cuprins.json și se folosește direct data viitoare;
un cuprins verificat de om (verificat: true) are întâietate.
"""
import json
import os
import subprocess
import tempfile

import numpy as np

DPI = 150


# ---------------------------------------------------------------- pagini ca imagini


def numar_pagini(cale_pdf: str) -> int:
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(cale_pdf)
        try:
            return len(pdf)
        finally:
            pdf.close()
    except ImportError:
        out = subprocess.run(['pdfinfo', cale_pdf], capture_output=True, text=True).stdout
        for linie in out.splitlines():
            if linie.startswith('Pages:'):
                return int(linie.split()[1])
        return 0


def pagini_gri(cale_pdf: str, dpi=DPI):
    """Generator: (număr pagină de la 1, imagine numpy în tonuri de gri)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        pdfium = None
    if pdfium is not None:
        pdf = pdfium.PdfDocument(cale_pdf)
        try:
            for i in range(len(pdf)):
                img = pdf[i].render(scale=dpi / 72.0, grayscale=True).to_pil().convert('L')
                yield i + 1, np.asarray(img)
        finally:
            pdf.close()
        return
    # fără pypdfium2 (doar la probele lui Claude, pe Linux): pdftoppm
    from PIL import Image
    d = tempfile.mkdtemp(prefix='cuprins-')
    subprocess.run(['pdftoppm', '-r', str(dpi), '-gray', '-png', cale_pdf, os.path.join(d, 'p')], check=True)
    fis = sorted(os.listdir(d), key=lambda f: int(f.split('-')[-1].split('.')[0]))
    for k, f in enumerate(fis):
        yield k + 1, np.asarray(Image.open(os.path.join(d, f)).convert('L'))
        os.remove(os.path.join(d, f))
    os.rmdir(d)


def extrage_pagini(cale_pdf: str, prima: int, ultima: int, dest: str):
    """Scrie un PDF nou doar cu paginile prima..ultima (numerotate de la 1)."""
    try:
        import pypdfium2 as pdfium
        src = pdfium.PdfDocument(cale_pdf)
        nou = pdfium.PdfDocument.new()
        try:
            nou.import_pages(src, list(range(prima - 1, ultima)))
            nou.save(dest)
        finally:
            nou.close()
            src.close()
    except ImportError:
        d = tempfile.mkdtemp(prefix='extras-')
        subprocess.run(['pdfseparate', '-f', str(prima), '-l', str(ultima), cale_pdf, os.path.join(d, 'p-%d.pdf')], check=True)
        parti = [os.path.join(d, f'p-{i}.pdf') for i in range(prima, ultima + 1)]
        subprocess.run(['pdfunite'] + parti + [dest], check=True)
        for p in parti:
            os.remove(p)
        os.rmdir(d)


# ---------------------------------------------------------------- portative și rânduri (sisteme)


def _indreapta(neg):
    """Scanările sunt adesea puțin strâmbe; rotim pagina cu unghiul la care liniile portativelor ies cel mai drept."""
    from PIL import Image
    mic = Image.fromarray((neg * 255).astype(np.uint8))
    w0 = mic.width
    mic = mic.resize((w0 // 2, mic.height // 2))
    best, unghi = -1, 0.0
    for u in np.arange(-2.0, 2.01, 0.1):
        r = np.asarray(mic.rotate(u, resample=Image.NEAREST, fillcolor=0)) > 0
        v = float(np.var(r.sum(axis=1)))
        if v > best:
            best, unghi = v, float(u)
    if abs(unghi) < 0.05:
        return neg
    r = Image.fromarray((neg * 255).astype(np.uint8)).rotate(unghi, resample=Image.NEAREST, fillcolor=0)
    return np.asarray(r) > 0


def _cea_mai_lunga(neg):
    """Pentru fiecare rând de pixeli: cea mai lungă porțiune neagră continuă (golurile de 1-2 pixeli se iartă)."""
    h, w = neg.shape
    a = neg.copy()
    a[1:] |= neg[:-1]          # o linie ușor ondulată trece de pe un rând de pixeli pe altul
    a[:-1] |= neg[1:]
    a[:, 1:-1] |= a[:, :-2] & a[:, 2:]
    pad = np.zeros((h, 1), dtype=bool)
    d = np.diff(np.concatenate([pad, a, pad], axis=1).astype(np.int8), axis=1)
    rez = np.zeros(h, dtype=int)
    for y in range(h):
        st = np.where(d[y] == 1)[0]
        if len(st):
            rez[y] = int((np.where(d[y] == -1)[0] - st).max())
    return rez


def _portative(neg):
    """Găsește portativele (5 linii orizontale egal depărtate). neg: matrice bool (True = cerneală).
    Întoarce listă de dict: sus, jos, stanga, dreapta, spatiu."""
    h, w = neg.shape
    # o linie de portativ e o porțiune neagră lungă, fără întreruperi; grinzile notelor sunt scurte
    cand = np.where(_cea_mai_lunga(neg) > 0.25 * w)[0]
    linii = []
    grup = []
    for y in cand:
        if grup and y - grup[-1] > 1:
            linii.append(grup); grup = []
        grup.append(y)
    if grup:
        linii.append(grup)
    centre = [int(round(np.mean(g))) for g in linii]
    port = []
    folosite = set()
    cs = set(centre)

    srt = sorted(centre)

    def langa(y, tol):
        best = None
        for c in srt:
            if c not in folosite and abs(c - y) <= tol and (best is None or abs(c - y) < abs(best - y)):
                best = c
        return best
    for a0 in srt:
        if a0 in folosite:
            continue
        gasit = None
        for e in srt:
            dd = (e - a0) / 4.0
            if dd < 4 or e in folosite:
                continue
            if dd > 0.03 * h:
                break
            tol = max(1.5, 0.22 * dd)
            ys = [a0]
            for k in (1, 2, 3):
                y = langa(a0 + k * dd, tol)
                if y is None:
                    break
                ys.append(y)
            if len(ys) == 4:
                gasit = ys + [e]
                break
        if not gasit:
            continue
        d = np.diff(gasit)
        col = np.zeros(w, dtype=int)
        for y in gasit:
            col += neg[max(0, y - 1):y + 2].any(axis=0)
        xs = np.where(col >= 3)[0]
        if len(xs) < 0.2 * w:
            continue
        # începutul portativului: prima coloană de unde liniile merg aproape continuu mai departe
        pline = col >= 3
        L = max(10, int(3 * d.mean()))
        cums = np.r_[0, np.cumsum(pline)]
        stanga = None
        for x in xs:
            if x + L < w and cums[x + L] - cums[x] >= 0.7 * L:
                stanga = int(x)
                break
        dreapta = int(xs[-1])
        if stanga is None or dreapta - stanga < 0.25 * w:
            continue
        starturi, capete, k = [stanga], [dreapta], 0
        folosite.update(gasit)
        port.append({'sus': gasit[0], 'jos': gasit[4], 'stanga': starturi[k], 'dreapta': capete[k],
                     'spatiu': float(np.mean(d))})
    return port


def _sisteme(neg, port):
    """Grupează portativele în rânduri (sisteme): portative care încep în același loc și sunt unite de linia din stânga."""
    port = sorted(port, key=lambda p: p['sus'])
    sist = []
    for p in port:
        if sist:
            ult = sist[-1][-1]
            if abs(p['stanga'] - ult['stanga']) <= max(4, 0.6 * p['spatiu']) and p['sus'] - ult['jos'] < 12 * p['spatiu']:
                x = min(p['stanga'], ult['stanga'])
                fereastra = neg[ult['jos']:p['sus'], max(0, x - 3):x + 4]
                if fereastra.size and fereastra.any(axis=1).mean() > 0.85:
                    sist[-1].append(p)
                    continue
        sist.append([p])
    return sist


def _bara_finala(neg, sistem) -> bool:
    """Adevărat dacă rândul se termină cu bara dublă de final (o linie groasă în capătul din dreapta)."""
    sus, jos = sistem[0]['sus'], sistem[-1]['jos']
    dr = max(p['dreapta'] for p in sistem)
    sp = sistem[0]['spatiu']
    zona = neg[sus:jos + 1, max(0, dr - int(2.5 * sp)):dr + 2]
    if zona.size == 0:
        return False
    plina = zona.mean(axis=0) > 0.9          # coloane negre pe toată înălțimea rândului
    # cea mai lată porțiune de coloane pline = grosimea barei
    best = cur = 0
    for v in plina:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best >= max(3, 0.28 * sp)


def _verticale_lungi(neg, x0, x1, minlen):
    """Porțiunile verticale negre lungi din coloanele x0..x1: listă (x, y0, y1)."""
    sub = neg[:, x0:x1]
    pad = np.zeros((1, sub.shape[1]), dtype=bool)
    d = np.diff(np.concatenate([pad, sub, pad]).astype(np.int8), axis=0)
    out = []
    for j in range(sub.shape[1]):
        st = np.where(d[:, j] == 1)[0]
        en = np.where(d[:, j] == -1)[0]
        for a, b in zip(st, en):
            if b - a >= minlen:
                out.append((x0 + j, int(a), int(b)))
    return out


def _sisteme_pian(neg):
    """Rândurile cu două (sau mai multe) portative unite: le găsim după linia verticală lungă de la începutul lor,
    care leagă portativele. Întoarce listă de (x început, y sus, y jos)."""
    h, w = neg.shape
    a = neg.copy()
    a[:, 1:] |= neg[:, :-1]                      # bara poate fi ușor înclinată
    r = _verticale_lungi(a, 0, int(0.45 * w), int(0.055 * h))
    r.sort(key=lambda t: t[1])
    grupuri = []
    for x, y0, y1 in r:
        for g in grupuri:
            if min(y1, g['y1']) - max(y0, g['y0']) > 0.5 * min(y1 - y0, g['y1'] - g['y0']):
                g['xs'].append((x, y1 - y0))
                g['y0'] = min(g['y0'], y0)
                g['y1'] = max(g['y1'], y1)
                break
        else:
            grupuri.append({'y0': y0, 'y1': y1, 'xs': [(x, y1 - y0)]})
    rez = []
    for g in grupuri:
        L = max(l for _, l in g['xs'])
        # bara de început a rândului e cea mai din stânga linie lungă (barele de măsură sunt mai la dreapta)
        # (acolada din fața ei nu are liniile portativului în dreapta ei imediat; bara de început are)
        cand = sorted(set(x for x, l in g['xs'] if l >= 0.85 * L))
        ales = None
        for x in cand:
            fasie = neg[g['y0']:g['y1'], x + 2:x + 14]
            if fasie.size and (fasie.mean(axis=1) > 0.9).sum() >= 5:
                ales = x
                break
        x = ales if ales is not None else cand[0]
        rez.append((_inceput_linii(neg, g['y0'], g['y1'], x), g['y0'], g['y1']))
    return sorted(rez, key=lambda t: t[1])


def _inceput_linii(neg, y0, y1, x):
    """Unde încep de fapt liniile portativelor rândului: mergem spre stânga de la x cât timp liniile continuă.
    (Dacă bara de început e ștearsă la scanare, x poate fi o bară de măsură din mijlocul rândului.)"""
    banda = neg[y0:y1 + 1, :x + 1]
    if banda.size == 0:
        return x
    linii = banda.sum(axis=0) >= 7          # coloane în care se văd liniile celor două portative
    c = x
    gol = 0
    while c > 0:
        if linii[c - 1]:
            gol = 0
        else:
            gol += 1
            if gol > 3:
                break
        c -= 1
    return c + gol


def _bara_finala_rand(neg, y0, y1) -> bool:
    """Bara dublă de final: o bară groasă, pe toată înălțimea rândului, cea mai din dreapta."""
    h, w = neg.shape
    zona = neg[y0 + 2:y1 - 2, int(0.6 * w):]
    if zona.size == 0:
        return False
    plina = zona.mean(axis=0) > 0.85
    xs = np.where(plina)[0]
    if not len(xs):
        return False
    # ultima grupă de coloane pline (cea mai din dreapta) și grosimea ei
    grosime = 1
    for i in range(len(xs) - 1, 0, -1):
        if xs[i] - xs[i - 1] == 1:
            grosime += 1
        else:
            break
    return grosime >= max(4, int(0.0035 * w))


def analizeaza_pagina(img):
    neg = _indreapta(img < 160)
    rez = []
    h, w = neg.shape
    sist = _sisteme_pian(neg)
    if sist:
        # rânduri scăpate (fără bară lungă la început, de obicei primul de pe pagină): le căutăm după portative
        port = [p for p in _portative(neg)
                if not any(y0 - 5 <= (p['sus'] + p['jos']) // 2 <= y1 + 5 for _, y0, y1 in sist)]
        i = 0
        while i + 1 < len(port):
            a, b = port[i], port[i + 1]
            ha = a['jos'] - a['sus']
            if b['sus'] - a['jos'] < 4 * ha:
                xm = int(0.5 * w)
                sist.append((_inceput_linii(neg, a['sus'], b['jos'], xm), a['sus'], b['jos']))
                i += 2
            else:
                i += 1
        sist.sort(key=lambda t: t[1])
    for x, y0, y1 in sist:
        # numărul piesei („12.”, „IV.”) stă în marginea din stânga rândului, înaintea acoladei
        marg = neg[y0:y1, max(0, x - int(0.075 * w)):max(0, x - int(0.018 * w))]
        numar = bool(marg.size) and 0.004 < float(marg.mean()) < 0.12
        rez.append({'stanga': x, 'sus': y0, 'jos': y1, 'final': _bara_finala_rand(neg, y0, y1), 'numar': numar})
    if rez:
        return rez
    # partituri cu un singur portativ pe rând (melodie, vioară...): după portative
    for s in _sisteme(neg, _portative(neg)):
        rez.append({'stanga': min(p['stanga'] for p in s), 'sus': s[0]['sus'], 'jos': s[-1]['jos'],
                    'final': _bara_finala(neg, s)})
    return rez


# ---------------------------------------------------------------- cuprinsul


def gaseste(cale_pdf: str, progres=None) -> dict:
    """Analizează toată cartea și întoarce cuprinsul (dict, gata de salvat ca JSON)."""
    n = numar_pagini(cale_pdf)
    pagini = []
    for nr, img in pagini_gri(cale_pdf):
        if progres and (nr == 1 or nr % 10 == 0):
            progres(f'Caut începutul pieselor: pagina {nr} din {n}.')
        pagini.append((nr, img.shape[1], img.shape[0], analizeaza_pagina(img)))
    # marginea stângă obișnuită a rândurilor (în fracțiune din lățimea paginii, ca să nu conteze scanarea)
    stangi = [s['stanga'] / w for _, w, _, ss in pagini for s in ss]
    if not stangi:
        return {'fisier': os.path.basename(cale_pdf), 'pagini': n, 'piese': [], 'probleme': ['Nu am găsit portative în PDF.']}
    obisnuit = float(np.median(stangi))
    rânduri = []
    for nr, w, h, ss in pagini:
        stangi_pag = [s['stanga'] / w for s in ss]
        # paginile din stânga și din dreapta pot avea margini diferite: comparăm întâi cu rândurile de pe aceeași pagină
        ref = float(np.median(stangi_pag)) if len(stangi_pag) >= 3 else obisnuit
        for s in ss:
            dif = s['stanga'] / w - ref
            if dif > 0.15:
                continue        # început de rând găsit greșit (bara de început ștearsă la scanare): îl ignorăm
            rânduri.append({'pagina': nr, 'retras': dif > 0.025, 'numar': s.get('numar', False), 'final': s['final'],
                            'sus': s['sus'] / h, 'jos': s['jos'] / h})
    piese = []
    probleme = []
    for i, r in enumerate(rânduri):
        inainte_final = i == 0 or rânduri[i - 1]['final']
        semne = int(r['retras']) + int(r['numar'])
        if i == 0 or semne:
            # sigur: rând retras și cu număr în față, sau unul din ele plus bara de final a piesei dinainte
            sigur = i == 0 or semne == 2 or inainte_final
            p = {'nr': len(piese) + 1, 'de_la': r['pagina'], 'sigur': bool(sigur), 'taie_sus': None, 'taie_jos': None}
            # dacă piesa începe la jumătatea paginii, tăiem ce e deasupra ei (sfârșitul piesei dinainte)
            if i > 0 and rânduri[i - 1]['pagina'] == r['pagina']:
                p['taie_sus'] = round((rânduri[i - 1]['jos'] + r['sus']) / 2, 4)
            piese.append(p)
        elif inainte_final and i + 1 < len(rânduri):
            # bară de final urmată de un rând fără niciun semn: poate o piesă nouă, poate un „Fine” din mijlocul piesei
            probleme.append(f'Pagina {r["pagina"]}: după o bară de final urmează un rând fără număr și neretras. '
                            'Dacă acolo începe o piesă nouă, nu am numărat-o.')
    for k, p in enumerate(piese):
        if k + 1 < len(piese):
            urm = piese[k + 1]
            if urm['taie_sus'] is not None:
                # piesa următoare începe la jumătatea paginii: pagina e comună, iar noi ne oprim deasupra ei
                p['pana_la'] = urm['de_la']
                p['taie_jos'] = urm['taie_sus']
            else:
                p['pana_la'] = urm['de_la'] - 1
        else:
            p['pana_la'] = max(r['pagina'] for r in rânduri)
        p['pana_la'] = max(p['pana_la'], p['de_la'])
        if not p['sigur']:
            probleme.append(f'Piesa {p["nr"]} (pagina {p["de_la"]}): are doar un semn de început de piesă. '
                            'Verifică dacă e chiar o piesă nouă.')
    return {'fisier': os.path.basename(cale_pdf), 'pagini': n, 'piese': piese, 'probleme': probleme, 'verificat': False}


def cale_cuprins(cale_pdf: str) -> str:
    """Cuprinsul stă în Recunoscute\\<numele PDF-ului>\\cuprins.json."""
    d = os.path.dirname(os.path.abspath(cale_pdf))
    return os.path.join(d, 'Recunoscute', os.path.splitext(os.path.basename(cale_pdf))[0], 'cuprins.json')


def _cale_veche(cale_pdf: str) -> str:
    return os.path.splitext(cale_pdf)[0] + '.cuprins.json'


def incarca_sau_gaseste(cale_pdf: str, progres=None) -> dict:
    c = cale_cuprins(cale_pdf)
    if not os.path.isfile(c) and os.path.isfile(_cale_veche(cale_pdf)):
        # cuprins din versiunile vechi (lângă PDF): îl copiem la locul nou; pe cel vechi îl poți șterge
        try:
            os.makedirs(os.path.dirname(c), exist_ok=True)
            with open(_cale_veche(cale_pdf), encoding='utf-8') as f:
                d = json.load(f)
            d['fisier'] = os.path.basename(cale_pdf)
            with open(c, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            os.utime(c, (os.path.getmtime(_cale_veche(cale_pdf)),) * 2)
        except (OSError, ValueError):
            pass
    if os.path.isfile(c):
        try:
            with open(c, encoding='utf-8') as f:
                d = json.load(f)
            # un cuprins verificat de om rămâne valabil; unul găsit automat, doar dacă PDF-ul nu s-a schimbat de atunci
            proaspat = d.get('verificat') or os.path.getmtime(c) >= os.path.getmtime(cale_pdf) - 1
            if proaspat and d.get('pagini') == numar_pagini(cale_pdf):
                return d
        except Exception:
            pass
    d = gaseste(cale_pdf, progres)
    try:
        os.makedirs(os.path.dirname(c), exist_ok=True)
        with open(c, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return d


def eticheta(p: dict) -> str:
    nume = p.get('nume') or f'Piesa {p["nr"]}'
    pag = f'pagina {p["de_la"]}' if p['de_la'] == p['pana_la'] else f'paginile {p["de_la"]}-{p["pana_la"]}'
    extra = ', ' + p['descriere'] if p.get('descriere') else ''
    return f'{nume}, {pag}{extra}' + ('' if p.get('sigur', True) else ', de verificat')


def pregateste_pdf(cale_pdf: str, de_la: int, pana_la: int, dest: str, taie_sus=None, taie_jos=None, dpi=300):
    """Face un PDF doar cu paginile alese; pe paginile comune cu altă piesă, partea care nu e a piesei se albește,
    ca recunoașterea să nu citească și bucăți din piesa vecină."""
    if taie_sus is None and taie_jos is None:
        extrage_pagini(cale_pdf, de_la, pana_la, dest)
        return dest
    from PIL import Image
    imagini = []
    for nr, img in _pagini_alese(cale_pdf, de_la, pana_la, dpi):
        im = Image.fromarray(img).convert('L')
        h = im.height
        if nr == de_la and taie_sus is not None:
            im.paste(255, (0, 0, im.width, int(taie_sus * h)))
        if nr == pana_la and taie_jos is not None:
            im.paste(255, (0, int(taie_jos * h), im.width, h))
        imagini.append(im)
    imagini[0].save(dest, 'PDF', resolution=dpi, save_all=True, append_images=imagini[1:])
    return dest


def _pagini_alese(cale_pdf, de_la, pana_la, dpi):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        pdfium = None
    if pdfium is not None:
        pdf = pdfium.PdfDocument(cale_pdf)
        try:
            for i in range(de_la - 1, pana_la):
                yield i + 1, np.asarray(pdf[i].render(scale=dpi / 72.0, grayscale=True).to_pil().convert('L'))
        finally:
            pdf.close()
        return
    from PIL import Image
    d = tempfile.mkdtemp(prefix='pagini-')
    subprocess.run(['pdftoppm', '-r', str(dpi), '-gray', '-png', '-f', str(de_la), '-l', str(pana_la), cale_pdf,
                    os.path.join(d, 'p')], check=True)
    for f in sorted(os.listdir(d), key=lambda f: int(f.split('-')[-1].split('.')[0])):
        yield int(f.split('-')[-1].split('.')[0]), np.asarray(Image.open(os.path.join(d, f)).convert('L'))
        os.remove(os.path.join(d, f))
    os.rmdir(d)


def citeste_pagini(text: str, n: int):
    """„3-4”, „5”, „3 - 6” -> (prima, ultima), sau None dacă nu e scris bine."""
    t = text.replace(' ', '').replace('–', '-')
    try:
        parti = [int(x) for x in t.split('-') if x]
    except ValueError:
        return None
    if not parti or len(parti) > 2:
        return None
    a, b = parti[0], parti[-1]
    if a < 1 or b > n or b < a:
        return None
    return a, b
