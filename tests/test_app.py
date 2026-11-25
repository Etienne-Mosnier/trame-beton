"""Point d'entrée de la page web (trame/app.py)."""

import json

import pytest
import pathlib

from trame import app

RACINE = pathlib.Path(__file__).resolve().parent.parent
DESSINS = RACINE / "dessins"


def test_reglages_moteur_en_francais():
    reglages = json.loads(app.reglages_moteur())
    assert set(reglages) == {"largeur_cordon", "hauteur_couche", "couches"}
    assert all(r["aide"] for r in reglages.values())


def test_bilan_texte():
    from trame.bilan import bilan
    texte = bilan(DESSINS / "vagues.svg")
    assert "Calques imprimés, dans l'ordre : A vagues, B lignes" in texte
    assert "OK        Sur la palette" in texte


def test_moteur_deduit_du_cordon():
    assert app.reglages_du_moteur({"largeur_cordon": 12, "hauteur_couche": 6, "couches": 2}) == \
        {"amp": 6, "d": 12, "couches": 2}
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"moteur": {"largeur_cordon": 12, "hauteur_couche": 6}}),
                                texte, "vagues.svg"))
    assert r["beton"]["largeur_cordon"] == 12 and r["amp"] == 6
    assert max(p[2] for serie in r["waves"] for w in serie for p in w) == 6     # un cordon de 6 mm croisé
    assert "hauteur de couche (6 mm)" in json.loads(app.exporter("script"))["texte"]


@pytest.mark.parametrize("largeur", [10, 25, 40])
def test_cordon_toujours_sur_la_palette(largeur):
    # plus le cordon est large, plus la marge grandit : le bord du cordon reste à 20 mm du bord
    # de la palette ou plus (le dessin est réduit s'il le faut)
    texte = (DESSINS / "spirales.dxf").read_text()
    r = json.loads(app.calculer(json.dumps({"moteur": {"largeur_cordon": largeur}}), texte, "spirales.dxf"))
    beton = [p for serie in r["waves"] for w in serie for p in w]
    demi = largeur / 2
    assert min(p[0] for p in beton) - demi >= 20 - 0.5 and max(p[0] for p in beton) + demi <= 1180 + 0.5
    assert min(p[1] for p in beton) - demi >= 20 - 0.5 and max(p[1] for p in beton) + demi <= 780 + 0.5


# --- dessin importé, en calques ------------------------------------------------------


def test_lire_calques():
    r = json.loads(app.lire_calques((DESSINS / "spirales.dxf").read_text(), "spirales.dxf"))
    assert [c["nom"] for c in r["calques"]] == ["1 spirale", "2 boucles", "3 vagues"]
    assert all(c["imprime"] and c["lignes"] == 1 and c["longueur"] > 1000 for c in r["calques"])
    assert r["message"] == "3 calques"


def test_lire_calques_erreur_en_francais():
    r = json.loads(app.lire_calques("<svg", "casse.svg"))
    assert "illisible" in r["erreur"]


def test_calculer_dessin():
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"moteur": {"hauteur_couche": 4}}), texte, "vagues.svg"))
    assert "erreur" not in r
    assert r["calques"] == ["A vagues", "B lignes"]           # ordre alphabétique au départ
    assert len(r["waves"]) == 2 and r["jumps"] == []
    beton = [p for serie in r["waves"] for w in serie for p in w]
    assert max(p[2] for p in beton) == 4                       # B passe par-dessus A
    assert "taille réelle" in r["message_dessin"]
    assert {c["statut"] for c in r["controles"]} == {"ok"}
    # le dessin reste sur la palette, à la marge près ; départ et fin aussi
    xs, ys = [p[0] for p in beton], [p[1] for p in beton]
    assert min(xs) >= 20 and max(xs) <= 1180 and min(ys) >= 20 and max(ys) <= 780
    for bout in (r["depart"], r["fin"]):
        assert 0 < bout["point"][0] < 1200 and 0 < bout["point"][1] < 800
    for format_fichier in ("dxf", "svg", "script"):
        e = json.loads(app.exporter(format_fichier))
        assert "erreur" not in e and e["nom"] == "trame_vagues." + format_fichier
    assert "Dessin : vagues.svg" in json.loads(app.exporter("script"))["texte"]


def test_calculer_ordre_choisi():
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"calques": ["B lignes", "A vagues"]}), texte, "vagues.svg"))
    assert r["calques"] == ["B lignes", "A vagues"]
    assert max(p[2] for w in r["waves"][0] for p in w) == 0    # B d'abord : à plat
    assert max(p[2] for w in r["waves"][1] for p in w) > 0     # A par-dessus


def test_calculer_dessin_erreurs():
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"calques": []}), texte, "vagues.svg"))
    assert r["erreur"].startswith("Aucun calque à imprimer")
    six = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'>%s</svg>" % "".join(
        "<g id='c%d'><path d='M0 %d L 100 %d' stroke='#000'/></g>" % (k, 10 * k, 10 * k) for k in range(6))
    r = json.loads(app.calculer("{}", six, "six.svg"))
    assert r["erreur"].startswith("6 calques à imprimer : 5 au plus")


def test_calculer_avec_pause():
    import io
    import ezdxf
    texte = (DESSINS / "vagues.svg").read_text()
    r = json.loads(app.calculer(json.dumps({"pauses": ["A vagues"]}), texte, "vagues.svg"))
    assert "erreur" not in r
    assert r["pauses"][0]["calque"] == "A vagues" and r["pauses"][0]["libre"]
    assert len(r["deplacements"]) == 1
    # la buse attend sur la palette, levée de la hauteur d'approche au-dessus du béton
    x, y, z = r["pauses"][0]["point"]
    assert 0 <= x <= 1200 and 0 <= y <= 800 and z >= app.CONFIG["impression"]["hauteur_approche"]
    titres = [c["titre"] for c in r["controles"]]
    assert "Pauses : 1, sans passer au-dessus du béton" in titres
    doc = ezdxf.read(io.StringIO(json.loads(app.exporter("dxf"))["texte"]))
    assert {"DEPLACEMENTS", "PAUSES"} <= {c.dxf.name for c in doc.layers}
    # le programme du robot s'arrête au point d'attente et attend « Continuer »
    script = json.loads(app.exporter("script"))["texte"]
    # avertissement de simulation, départ (démarrer la pompe), la pause, fin (couper la pompe)
    assert script.count("blocking=True") == 4
    assert "Pause 1, apres le calque 'A vagues' (couche 1)" in script
    assert "Demarrer la pompe" in script and "Couper la pompe" in script
    # la maquette s'arrête aux mêmes endroits (clic sur l'écran du WASP)
    maquette = json.loads(app.exporter("gcode", json.dumps({"largeur_essai": 1.5})))["texte"]
    assert maquette.count("\nM0 ") == 3
    # le robot ne dépose pas de cordon pendant le trajet à vide
    bras = json.loads(app.robot())
    assert -1 in bras["series"] and bras["hors_portee"] == []


def test_plusieurs_fichiers():
    # les deux calques de vagues.svg, chacun dans son propre fichier
    import re
    texte = (DESSINS / "vagues.svg").read_text()
    groupes = re.findall(r'<g inkscape:groupmode="layer".*?</g>', texte, re.S)
    entete = texte[:texte.index("<g ")]
    fichiers = [{"nom": "a_vagues.svg", "texte": entete + groupes[0] + "</svg>"},
                {"nom": "b_lignes.svg", "texte": entete + groupes[1] + "</svg>"}]
    lus = json.loads(app.lire_calques(json.dumps(fichiers)))
    assert [c["nom"] for c in lus["calques"]] == ["a_vagues", "b_lignes"]
    assert lus["fichiers"] == ["a_vagues.svg", "b_lignes.svg"] and lus["message"] == "2 fichiers, 2 calques"
    r = json.loads(app.calculer("{}", json.dumps(fichiers)))
    seul = json.loads(app.calculer("{}", texte, "vagues.svg"))
    # même dessin que le fichier unique : mêmes hauteurs, même longueur
    assert r["longueur"] == seul["longueur"]
    assert max(p[2] for serie in r["waves"] for w in serie for p in w) == \
        max(p[2] for serie in seul["waves"] for w in serie for p in w)
    json.loads(app.calculer("{}", json.dumps(fichiers)))
    e = json.loads(app.exporter("script"))
    assert e["nom"] == "trame_a_vagues+b_lignes.script" and "Dessin : a_vagues.svg, b_lignes.svg" in e["texte"]


def test_bilan_de_plusieurs_fichiers(tmp_path):
    from trame.bilan import bilan
    (tmp_path / "a.dxf").write_text((DESSINS / "spirales.dxf").read_text())
    texte = bilan(tmp_path / "a.dxf", DESSINS / "vagues.svg")
    assert "Dessin a.dxf, vagues.svg" in texte and "2 fichiers" in texte
