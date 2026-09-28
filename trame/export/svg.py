"""Export SVG (vue de dessus) : un calque par série, calque des liaisons, palette.

Le dessin est à l'échelle 1 (unités en mm). Les calques s'ouvrent comme calques dans
Inkscape et comme groupes dans Illustrator. Les sommets des bosses sont des petits
cercles, d'autant plus grands que la bosse est haute.
"""

from trame.export.commun import LETTRES, reperes_palette, separer_liaisons, sommets_des_bosses

COULEURS = ["#6b7280", "#2563eb", "#16a34a", "#9333ea", "#d97706"]


def exporter_svg(resultat, contour, palette, lane, amp):
    lx, ly = palette
    waves = resultat["waves"]
    lignes, liaisons = separer_liaisons(waves, contour, lane)

    def pts(poly):
        # y de la palette vers le haut, y du SVG vers le bas
        return " ".join("%.2f,%.2f" % (p[0], ly - p[1]) for p in poly)

    def calque(ident, nom, contenu):
        return ('<g id="%s" inkscape:groupmode="layer" inkscape:label="%s">\n%s\n</g>'
                % (ident, nom, "\n".join(contenu)))

    morceaux = []
    palette_svg = ['<rect x="0" y="0" width="%g" height="%g" fill="none" stroke="#000" stroke-width="1"/>'
                   % (lx, ly),
                   '<path d="M0,%g h100 M0,%g v-100" stroke="#000" stroke-width="1"/>' % (ly, ly),
                   '<text x="105" y="%g" font-size="15">X</text>' % (ly + 5),
                   '<text x="-5" y="%g" font-size="15">Y</text>' % (ly - 105)]
    for nom, (x, y) in reperes_palette(palette):
        palette_svg.append('<circle cx="%g" cy="%g" r="8" fill="none" stroke="#000"/>' % (x, ly - y))
        palette_svg.append('<text x="%g" y="%g" font-size="12">%s</text>' % (x + 12, ly - y - 12, nom))
    morceaux.append(calque("palette", "Palette", palette_svg))

    morceaux.append(calque("contour", "Contour", [
        '<polygon points="%s" fill="none" stroke="#000" stroke-width="1" stroke-dasharray="6 4"/>'
        % pts(contour.exterior.coords)]))

    for i, serie in enumerate(lignes):
        couleur = COULEURS[i % len(COULEURS)]
        morceaux.append(calque("serie_%s" % LETTRES[i], "Série %s" % LETTRES[i], [
            '<polyline points="%s" fill="none" stroke="%s" stroke-width="2"/>' % (pts(p), couleur)
            for p in serie]))

    morceaux.append(calque("liaisons", "Liaisons", [
        '<polyline points="%s" fill="none" stroke="#e11d48" stroke-width="1"/>' % pts(p)
        for p in liaisons]))

    morceaux.append(calque("bosses", "Sommets des bosses", [
        '<circle cx="%.2f" cy="%.2f" r="%.1f" fill="#000"><title>%.1f mm</title></circle>'
        % (x, ly - y, 1.5 * max(z / amp, 1) if amp > 0 else 1.5, z)
        for x, y, z in sommets_des_bosses(waves)]))

    if resultat["jumps"]:
        morceaux.append(calque("sauts", "Sauts", [
            '<polyline points="%s" fill="none" stroke="#000" stroke-dasharray="4 4"/>' % pts(j)
            for j in resultat["jumps"]]))

    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
            'width="%gmm" height="%gmm" viewBox="-60 -60 %g %g">\n%s\n</svg>\n'
            % (lx + 120, ly + 120, lx + 120, ly + 120, "\n".join(morceaux)))
