"""Animal records: finding one animal by name across the whole register.

Story MSD426GXUST3-42. An animal is recorded against one client, so the
register can be read two ways: down a client's page to the animals that
household or business owns, or across the register by the animal-s own name.

The second way is the one the front desk needs when the person asking is not
the client on file: a neighbour ringing about a dog that has wandered, a stock
agent chasing a horse, somebody who has changed their number since the last
visit. So the search never asks who the owner is and never stops at the first
match. It returns every animal whose name matches, wherever it sits in the
register, and each match carries the owner it belongs to and the number to
ring back.

The name matching rule lives in app.services.records so it can be unit tested
on its own; this module is the HTTP layer that turns the search box into a
query and a list of matches.
"""
from flask import Blueprint, render_template, request

from app.models import Animal, Client, db
from app.services.records import animal_name_pattern, clean

animals_bp = Blueprint("animals", __name__, url_prefix="/animals")


def _matches(pattern):
    """Every animal whose name matches, with its owner, in name order.

    An animal that has been taken off the books is still returned: a search is
    a lookup, not an offer of work, and a name that has quietly stopped
    appearing on a client's page should not read as a name that never existed.
    The list says which ones are no longer on the books.
    """
    return (
        Animal.query.join(Client)
        .filter(Animal.name.ilike(pattern, escape="\\"))
        .order_by(db.func.lower(Animal.name), db.func.lower(Client.name))
        .all()
    )


@animals_bp.get("/search")
def search_animals():
    """Search the register by animal name, across every client."""
    term = clean(request.args.get("name"))
    pattern = animal_name_pattern(term)
    return render_template(
        "animals/search.html",
        term=term,
        searched=pattern is not None,
        matches=[] if pattern is None else _matches(pattern),
    )
