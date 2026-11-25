"""Lecture des dessins en calques (trame/dessin.py).

Pas de vrais fichiers des étudiants pour l'instant : chaque test fabrique un fichier qui
reproduit la façon d'exporter d'un logiciel (Inkscape, Illustrator, AutoCAD, Rhino).
"""

import io
import math

import ezdxf
import pytest

from trame.dessin import lire_dessin, placer_dessin


def noms(dessin):
    return [c["nom"] for c in dessin["calques"]]


def calque(dessin, nom):
    return next(c for c in dessin["calques"] if c["nom"] == nom)


def taille(courbes):
    xs = [p[0] for c in courbes for p in c]
    ys = [p[1] for c in courbes for p in c]
    return max(xs) - min(xs), max(ys) - min(ys)


# --- SVG d'Inkscape -------------------------------------------------------------------

INKSCAPE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"
     id="svg8" width="400mm" height="300mm" viewBox="0 0 400 300">
  <g inkscape:groupmode="layer" id="layer1" inkscape:label="calque 10">
    <path d="M 0,150 L 400,150" fill="none" stroke="#000"/>
  </g>
  <g inkscape:groupmode="layer" id="layer2" inkscape:label="calque 2">
    <path d="M 200,0 C 250,100 150,200 200,300" fill="none" stroke="#000"/>
    <text x="10" y="10">légende</text>
  </g>
  <g inkscape:groupmode="layer" id="layer3" inkscape:label="Esquisse" style="display:none">
    <circle cx="200" cy="150" r="50" fill="none" stroke="#000"/>
  </g>
  <g inkscape:groupmode="layer" id="layer4" inkscape:label="Palette">
    <rect x="0" y="0" width="400" height="300" fill="none" stroke="#000"/>
  </g>
</svg>"""


def test_inkscape_calques_et_ordre_naturel():
    d = lire_dessin(INKSCAPE, "trame.svg")
    # ordre alphabétique « naturel » : calque 2 avant calque 10
    assert noms(d) == ["calque 2", "calque 10", "Esquisse", "Palette"]
    assert calque(d, "calque 10")["imprime"] and calque(d, "calque 2")["imprime"]
    # calque masqué dans Inkscape : lu, mais pas imprimé au départ
    assert not calque(d, "Esquisse")["imprime"] and calque(d, "Esquisse")["courbes"]
    # cadre du gabarit : pas imprimé au départ
    assert not calque(d, "Palette")["imprime"]
    # unités en mm : la ligne fait 400 mm ; le texte est ignoré
    assert taille(calque(d, "calque 10")["courbes"])[0] == pytest.approx(400)
    assert len(calque(d, "calque 2")["courbes"]) == 1


# --- SVG d'Illustrator ----------------------------------------------------------------

ILLUSTRATOR = """<?xml version="1.0" encoding="utf-8"?>
<!-- Generator: Adobe Illustrator 24.0.0, SVG Export Plug-In . SVG Version: 6.00 Build 0)  -->
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" [
  <!ENTITY ns_extend "http://ns.adobe.com/Extensibility/1.0/">
  <!ENTITY ns_ai "http://ns.adobe.com/AdobeIllustrator/10.0/">
]>
<svg version="1.1" xmlns:x="&ns_extend;" xmlns:i="&ns_ai;" xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink" x="0px" y="0px" viewBox="0 0 841.9 595.3" xml:space="preserve">
<style type="text/css">.st0{fill:none;stroke:#E30613;}.st1{fill:none;stroke:#1D71B8;}</style>
<switch>
  <foreignObject requiredExtensions="&ns_ai;" x="0" y="0" width="1" height="1"></foreignObject>
  <g i:extraneous="self">
    <g id="Trame_B" data-name="Trame B"><line class="st1" x1="0" y1="0" x2="0" y2="720"/></g>
    <g id="Trame_A" data-name="Trame A"><polyline class="st0" points="0,0 720,0 720,72"/></g>
  </g>
</switch>
</svg>"""


def test_illustrator_calques_et_echelle():
    d = lire_dessin(ILLUSTRATOR, "trame.svg")
    assert noms(d) == ["Trame A", "Trame B"]
    # Illustrator compte en points (72 par pouce) : 720 pt = 254 mm (et pas 190,5)
    assert taille(calque(d, "Trame A")["courbes"]) == pytest.approx((254, 25.4))
    assert taille(calque(d, "Trame B")["courbes"])[1] == pytest.approx(254)
    assert calque(d, "Trame A")["couleur"] == "#e30613"


ILLUSTRATOR_EXPORT = """<?xml version="1.0" encoding="UTF-8"?>
<svg id="Calque_1" data-name="Calque 1" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 720">
  <defs><style>.cls-1{fill:none;stroke:#000;}.cls-2{fill:none;stroke:#e30613;}</style></defs>
  <path class="cls-1" d="M0,360H720"/>
  <path class="cls-2" d="M360,0V720"/>
  <path class="cls-2" d="M100,0V720"/>
</svg>"""


def test_illustrator_un_seul_calque_separe_par_couleur():
    # « Exporter sous » d'Illustrator : un seul calque, deux couleurs -> deux calques
    d = lire_dessin(ILLUSTRATOR_EXPORT, "trame.svg")
    assert noms(d) == ["Couleur #000000", "Couleur #e30613"]
    assert len(calque(d, "Couleur #e30613")["courbes"]) == 2
    assert taille(calque(d, "Couleur #000000")["courbes"])[0] == pytest.approx(254)


def test_svg_sans_calque_une_couleur():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M0 0 L 100 0" stroke="#000"/></svg>'
    d = lire_dessin(svg, "trait.svg")
    assert noms(d) == ["trait"]                                   # un seul calque : le nom du fichier
    assert d["calques"][0]["imprime"]


def test_traits_vectorises_signales():
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
           '<rect x="0" y="0" width="100" height="2" fill="#000"/></svg>')
    assert "remplie" in lire_dessin(svg, "trait.svg")["message"]


# --- DXF d'AutoCAD et de Rhino --------------------------------------------------------


def texte_dxf(doc):
    flux = io.StringIO()
    doc.write(flux)
    return flux.getvalue()


def test_autocad_calques_blocs_et_unites():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 1                      # pouces
    msp = doc.modelspace()
    doc.layers.add("Vagues", color=1)
    doc.layers.add("Lignes", color=5)
    doc.layers.add("Repères").off()                  # calque éteint dans AutoCAD
    # polyligne avec un arc (renflement) : une seule ligne
    msp.add_lwpolyline([(0, 0, 0), (10, 0, 1), (10, 10, 0)], format="xyb", dxfattribs={"layer": "Vagues"})
    # bloc : ce qui est sur le calque 0 prend le calque du bloc
    bloc = doc.blocks.new("TRAIT")
    bloc.add_line((0, 0), (1, 0), dxfattribs={"layer": "0"})
    msp.add_blockref("TRAIT", (0, 5), dxfattribs={"layer": "Lignes", "xscale": 10})
    msp.add_line((0, 0), (5, 5), dxfattribs={"layer": "Repères"})
    msp.add_line((0, 0), (5, 5), dxfattribs={"layer": "Defpoints"})
    msp.add_text("cartouche", dxfattribs={"layer": "Vagues"})
    d = lire_dessin(texte_dxf(doc), "plan.dxf")
    assert noms(d) == ["Lignes", "Repères", "Vagues"]          # Defpoints jamais lu
    assert not calque(d, "Repères")["imprime"]
    assert calque(d, "Lignes")["courbes"] and taille(calque(d, "Lignes")["courbes"])[0] == pytest.approx(254)
    # l'arc de la polyligne est suivi (plusieurs points), en mm
    vagues = calque(d, "Vagues")["courbes"]
    assert len(vagues) == 1 and len(vagues[0]) > 10
    assert taille(vagues)[0] == pytest.approx(254 + 127, abs=1)  # 10 pouces + l'arc qui déborde de 5


def test_rhino_sous_calques_et_courbes():
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for nom in ("Motif$A spirale", "Motif$B vagues", "X$C", "Y$C"):
        doc.layers.add(nom)
    spirale = [(50 * t / 6 * math.cos(t), 50 * t / 6 * math.sin(t)) for t in [k / 10 for k in range(120)]]
    msp.add_spline(fit_points=spirale, dxfattribs={"layer": "Motif$A spirale"})
    msp.add_line((-100, 0), (100, 0), dxfattribs={"layer": "Motif$B vagues"})
    msp.add_circle((0, 0), 20, dxfattribs={"layer": "X$C"})
    msp.add_circle((0, 0), 30, dxfattribs={"layer": "Y$C"})
    d = lire_dessin(texte_dxf(doc), "rhino.dxf")
    # sous-calques (« Parent$Enfant » : les DXF refusent « :: ») -> « Enfant » ; deux enfants du même nom gardent leur nom complet
    assert noms(d) == ["A spirale", "B vagues", "X$C", "Y$C"]
    spirale_lue = calque(d, "A spirale")["courbes"][0]
    assert math.dist(spirale_lue[0], spirale_lue[-1]) > 50       # courbe ouverte, suivie en entier
    cercle = calque(d, "X$C")["courbes"][0]
    assert math.dist(cercle[0], cercle[-1]) < 0.01                # cercle : courbe fermée


def test_erreurs_en_francais():
    with pytest.raises(ValueError, match="Format non reconnu"):
        lire_dessin("", "dessin.pdf")
    with pytest.raises(ValueError, match="Aucune ligne"):
        lire_dessin('<svg xmlns="http://www.w3.org/2000/svg"><text>titre</text></svg>', "vide.svg")
    with pytest.raises(ValueError, match="illisible"):
        lire_dessin("<svg", "casse.svg")


# --- placement ------------------------------------------------------------------------


def test_placement_au_centre_taille_reelle():
    place = placer_dessin([[[(0, 0), (300, 0)]], [[(0, 0), (0, 200)]]], marge=20)
    assert place["rotation"] == 0 and place["echelle"] == 1
    (a,), (b,) = place["courbes"]
    # le dessin (300 × 200) est centré sur la palette (1200 × 800)
    assert a[0] == pytest.approx((450, 300)) and a[1] == pytest.approx((750, 300))
    assert b[1] == pytest.approx((450, 500))
    assert "taille réelle" in place["message"]


def test_placement_tourne_ou_reduit():
    haut = placer_dessin([[[(0, 0), (0, 1000)]], [[(0, 0), (100, 0)]]], marge=20)
    assert haut["rotation"] == 90 and haut["echelle"] == 1 and "tourné" in haut["message"]
    grand = placer_dessin([[[(0, 0), (3000, 0)], [(0, 0), (0, 1000)]]], marge=20)
    assert grand["echelle"] == pytest.approx(1160 / 3000) and "réduit" in grand["message"]
    choisi = placer_dessin([[[(0, 0), (300, 0)], [(0, 0), (0, 200)]]], marge=20, taille=0.5)
    assert choisi["taille"] == pytest.approx(0.5)


def test_gabarits():
    # le gabarit de la palette : seul son cadre a des lignes, et il n'est pas imprimé
    import pathlib
    dossier = pathlib.Path(__file__).resolve().parent.parent / "gabarits"
    for nom in ("gabarit_palette.svg", "gabarit_palette.dxf"):
        d = lire_dessin((dossier / nom).read_text(encoding="utf-8"), nom)
        assert [(c["nom"], c["imprime"]) for c in d["calques"]] == [("palette", False)]
        assert taille(d["calques"][0]["courbes"]) == pytest.approx((1200, 800))


# --- plusieurs fichiers (un calque par fichier, ou plusieurs) --------------------------

from trame.dessin import lire_dessins


def dxf_d_une_ligne(debut, fin, calque="0"):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    if calque != "0":
        doc.layers.add(calque)
    doc.modelspace().add_line(debut, fin, dxfattribs={"layer": calque})
    return texte_dxf(doc)


def test_un_calque_par_fichier():
    # deux fichiers exportés depuis le même plan, chacun avec son calque « 0 »
    d = lire_dessins([(dxf_d_une_ligne((0, 100), (400, 100)), "A vagues.dxf"),
                      (dxf_d_une_ligne((200, 0), (200, 300)), "dossier/B lignes.dxf")])
    assert noms(d) == ["A vagues", "B lignes"]                    # le nom du fichier, sans extension
    assert [c["fichier"] for c in d["calques"]] == ["A vagues.dxf", "dossier/B lignes.dxf"]
    # les fichiers sont superposés tels quels : le croisement reste en (200, 100)
    a, b = calque(d, "A vagues")["courbes"][0], calque(d, "B lignes")["courbes"][0]
    assert a == [(0, 100), (400, 100)] and b == [(200, 0), (200, 300)]
    assert d["message"] == "2 fichiers, 2 calques"
    # un seul fichier d'un seul calque : le même nom (il ne change pas si l'on ajoute un fichier)
    assert noms(lire_dessins([(dxf_d_une_ligne((0, 0), (10, 0)), "A vagues.dxf")])) == ["A vagues"]


def test_un_svg_et_un_dxf_se_superposent():
    # la même page de 1200 × 800 mm : un trait à 700 mm du haut en SVG = à 100 mm du bas en DXF
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="1200mm" height="800mm" viewBox="0 0 1200 800">'
           '<path d="M 100 700 L 500 700" stroke="#000"/></svg>')
    d = lire_dessins([(svg, "a.svg"), (dxf_d_une_ligne((100, 100), (500, 300)), "b.dxf")])
    assert calque(d, "a")["courbes"][0][0] == pytest.approx((100, 100), abs=0.01)
    assert calque(d, "b")["courbes"][0][0] == (100, 100)


def test_meme_nom_de_calque_dans_deux_fichiers():
    def deux_calques(decalage):
        doc = ezdxf.new("R2010")
        for nom in ("A", "B"):
            doc.layers.add(nom)
            doc.modelspace().add_line((0, decalage), (100, decalage + 50), dxfattribs={"layer": nom})
        return texte_dxf(doc)
    d = lire_dessins([(deux_calques(0), "essai1.dxf"), (deux_calques(10), "essai2.dxf")])
    assert noms(d) == ["A (essai1)", "A (essai2)", "B (essai1)", "B (essai2)"]


def test_fichier_qui_ne_recouvre_aucun_autre():
    # exporté avec une autre page (par exemple « exporter la sélection ») : il est signalé
    d = lire_dessins([(dxf_d_une_ligne((0, 0), (100, 100)), "a.dxf"),
                      (dxf_d_une_ligne((5000, 0), (5100, 100)), "b.dxf")])
    assert "« b.dxf » ne recouvre aucun autre fichier" in d["message"]
    assert "ne recouvre" not in lire_dessins([(dxf_d_une_ligne((0, 0), (100, 100)), "a.dxf"),
                                              (dxf_d_une_ligne((0, 100), (100, 0)), "b.dxf")])["message"]


def test_gabarit_et_dessin_dans_deux_fichiers():
    import pathlib
    gabarit = (pathlib.Path(__file__).resolve().parent.parent / "gabarits" / "gabarit_palette.dxf").read_text()
    d = lire_dessins([(gabarit, "gabarit_palette.dxf"), (dxf_d_une_ligne((100, 100), (900, 600)), "trame.dxf")])
    # le cadre garde son nom « palette » et n'est pas imprimé
    assert [(c["nom"], c["imprime"]) for c in d["calques"]] == [("palette", False), ("trame", True)]


def test_erreur_dans_un_des_fichiers():
    with pytest.raises(ValueError, match="« vide.svg »"):
        lire_dessins([(dxf_d_une_ligne((0, 0), (1, 1)), "a.dxf"),
                      ('<svg xmlns="http://www.w3.org/2000/svg"><text>x</text></svg>', "vide.svg")])
