from flask import Blueprint, render_template

from liga.game.chemistry import FUNCTIONS

bp = Blueprint("study", __name__)

HYDROCARBON = {
    "title": "Hidrocarboneto",
    "struct": "  H\n  |\nH–C–H\n  |\n  H",
    "note": "Metano, CH₄. Só carbono e hidrogênio. As funções do dominó nascem quando entra oxigênio.",
}


@bp.route("/revisao")
def review():
    return render_template("study/review.html", functions=FUNCTIONS, hydrocarbon=HYDROCARBON)
