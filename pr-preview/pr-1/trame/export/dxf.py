"""Export DXF (3D) : un calque par série, calque des liaisons, chemin complet, palette.

Les hauteurs (z) sont les vraies hauteurs des bosses, en mm, sans exagération.
"""

import io

import ezdxf

from trame.export.commun import LETTRES, reperes_palette, separer_liaisons, sommets_des_bosses

# couleurs AutoCAD (ACI) : gris, bleu, vert, magenta, orange — comme l'aperçu
COULEURS = [8, 5, 3, 6, 30]


def exporter_dxf(resultat, contour, palette, lane):
    """Texte DXF du résultat de calculer_chemin, pour les étudiants ingénieurs."""
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4            # millimètres
    msp = doc.modelspace()
    waves = resultat["waves"]
    lignes, liaisons = separer_liaisons(waves, contour, lane)

    def calque(nom, couleur, type_trait="Continuous"):
        doc.layers.add(nom, color=couleur, linetype=type_trait)
        return {"layer": nom}

    # palette : cadre, origine, axes, repères de calibration
    lx, ly = palette
    attributs = calque("PALETTE", 7)
    msp.add_lwpolyline([(0, 0), (lx, 0), (lx, ly), (0, ly)], close=True, dxfattribs=attributs)
    msp.add_line((0, 0), (100, 0), dxfattribs=attributs)
    msp.add_line((0, 0), (0, 100), dxfattribs=attributs)
    msp.add_text("X", height=15, dxfattribs=attributs).set_placement((105, -5))
    msp.add_text("Y", height=15, dxfattribs=attributs).set_placement((-5, 105))
    for nom, (x, y) in reperes_palette(palette):
        msp.add_circle((x, y), 8, dxfattribs=attributs)
        msp.add_text(nom, height=12, dxfattribs=attributs).set_placement((x + 12, y + 12))
    msp.add_text("Palette EPAL %g x %g mm - origine (0, 0) en bas a gauche" % (lx, ly),
                 height=15, dxfattribs=attributs).set_placement((0, -40))

    attributs = calque("CONTOUR", 7, "DASHED")
    msp.add_lwpolyline(list(contour.exterior.coords), close=True, dxfattribs=attributs)

    # une série par calque, dans l'ordre d'impression
    for i, morceaux in enumerate(lignes):
        attributs = calque("SERIE_%s" % LETTRES[i], COULEURS[i % len(COULEURS)])
        for poly in morceaux:
            msp.add_polyline3d(poly, dxfattribs=attributs)

    attributs = calque("LIAISONS", 1)
    for poly in liaisons:
        msp.add_polyline3d(poly, dxfattribs=attributs)

    attributs = calque("BOSSES", 2)
    for x, y, z in sommets_des_bosses(waves):
        msp.add_point((x, y, z), dxfattribs=attributs)

    # le chemin complet, d'un seul tenant, dans l'ordre d'impression
    if resultat["path"]:
        msp.add_polyline3d(resultat["path"], dxfattribs=calque("CHEMIN", 7))
    if resultat["jumps"]:
        attributs = calque("SAUTS", 1, "DASHED")
        for saut in resultat["jumps"]:
            msp.add_polyline3d(saut, dxfattribs=attributs)

    texte = io.StringIO()
    doc.write(texte)
    return texte.getvalue()
