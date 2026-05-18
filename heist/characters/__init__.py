"""Character roster — one module per character.

Each `cNN_<firstname>.py` exports a `CHARACTER` (a `Character` instance) with
the locked mechanical fields (id / name / skills / floor_cost) and the
descriptive profile fields documented in `_TEMPLATE.md`.

This module assembles all 15 into the canonical `ROSTER` list and
`ROSTER_BY_ID` lookup. `heist.content` re-exports both, so existing
imports of `from heist.content import ROSTER` continue to work.
"""

from heist.state import Character

from heist.characters.c01_marcus   import CHARACTER as _c01
from heist.characters.c02_sasha    import CHARACTER as _c02
from heist.characters.c03_eli      import CHARACTER as _c03
from heist.characters.c04_vance    import CHARACTER as _c04
from heist.characters.c05_carla    import CHARACTER as _c05
from heist.characters.c06_big_mike import CHARACTER as _c06
from heist.characters.c07_lin      import CHARACTER as _c07
from heist.characters.c08_theo     import CHARACTER as _c08
from heist.characters.c09_pearl    import CHARACTER as _c09
from heist.characters.c10_rook     import CHARACTER as _c10
from heist.characters.c11_jolene   import CHARACTER as _c11
from heist.characters.c12_nestor   import CHARACTER as _c12
from heist.characters.c13_slim     import CHARACTER as _c13
from heist.characters.c14_margot   import CHARACTER as _c14
from heist.characters.c15_dex      import CHARACTER as _c15

ROSTER: list[Character] = [
    _c01, _c02, _c03, _c04, _c05, _c06, _c07, _c08,
    _c09, _c10, _c11, _c12, _c13, _c14, _c15,
]

ROSTER_BY_ID: dict[int, Character] = {c.id: c for c in ROSTER}
