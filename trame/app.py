"""Point d'entrée appelé par la page web : motif + réglages -> résultat JSON.

Étape 2 : seulement verifier(), qui montre que Python, shapely, ezdxf et
svgelements fonctionnent dans le navigateur. Le vrai calcul arrive à l'étape 7.
"""

import json
import sys


def verifier():
    """Renvoie un texte JSON avec les versions trouvées et un petit calcul shapely."""
    import ezdxf
    import shapely
    import svgelements
    from shapely.geometry import LineString

    # deux lignes qui se croisent au point (50, 50)
    a = LineString([(0, 0), (100, 100)])
    b = LineString([(0, 100), (100, 0)])
    croisement = a.intersection(b)

    resultat = {
        "ok": True,
        "python": sys.version.split()[0],
        "shapely": shapely.__version__,
        "ezdxf": ezdxf.__version__,
        "svgelements": svgelements.SVGELEMENTS_VERSION,
        "croisement": [croisement.x, croisement.y],
    }
    return json.dumps(resultat)
