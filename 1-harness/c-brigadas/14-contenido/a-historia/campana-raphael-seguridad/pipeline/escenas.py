# -*- coding: utf-8 -*-
"""Escenas animadas por caso y seccion. Iconos y personajes: OpenMoji (CC BY-SA 4.0), https://openmoji.org
Tipos: ("flow", [a, b(, c)], paquete) = personajes en fila con un paquete que viaja entre ellos;
       ("versus", [a, b]) = enfrentados con un rayo; ("hero", [centro], [orbitan x3]) = protagonista con iconos alrededor."""
DEV, OFI, HACK, ROBOT, DETEC, MASK = "1F9D1-200D-1F4BB", "1F9D1-200D-1F4BC", "1F977", "1F916", "1F575", "1F3AD"
MAIL, PHONE, MONEY, BAG, LOCK, UNLOCK, KEY = "1F4E7", "1F4DE", "1F4B8", "1F4B0", "1F512", "1F513", "1F511"
SHIELD, CHECK, CROSS, WARN, BUG, PACK, DB = "1F6E1", "2705", "274C", "26A0", "1F41B", "1F4E6", "1F5C4"
CLOUD, EYES, CAR, PLANE, BANK, CHAT, TRASH = "2601", "1F440", "1F697", "2708", "1F3E6", "1F4AC", "1F5D1"
FIRE, BOMB, VIDEO, BURGER, BALLOT, GOV, GLOBE = "1F525", "1F4A3", "1F4F9", "1F354", "1F5F3", "1F3DB", "1F310"
LINK, DOC, MIC, PC, SKULL, GHOST, SEARCH = "1F517", "1F4C4", "1F3A4", "1F4BB", "1F480", "1F47B", "1F50D"
HOUR, HAND, NOENT, ZAP, TARGET, SCALE, HOSP = "231B", "1F91D", "26D4", "26A1", "1F3AF", "2696", "1F3E5"
FACT, BELL, BOOK, HERO = "1F3ED", "1F514", "1F516", "1F9B8"
MASCOTA = HERO
ESCENAS = {
 1: dict(gancho=("flow", [DEV, ROBOT], DOC), caso=("flow", [DEV, ROBOT, CLOUD], DOC), problema=("hero", [CLOUD], [EYES, DOC, WARN]), solucion=("hero", [SHIELD], [LOCK, PC, CHECK])),
 2: dict(gancho=("hero", [VIDEO], [MASK, MASK, MONEY]), caso=("flow", [MASK, OFI, BANK], MONEY), problema=("versus", [OFI, MASK]), solucion=("hero", [SHIELD], [PHONE, KEY, CHECK])),
 3: dict(gancho=("versus", [ROBOT, PLANE]), caso=("flow", [OFI, ROBOT], CHAT), problema=("hero", [ROBOT], [WARN, CROSS, DOC]), solucion=("hero", [SCALE], [DOC, OFI, CHECK])),
 4: dict(gancho=("flow", [MAIL, ROBOT, HACK], KEY), caso=("flow", [HACK, MAIL, ROBOT], BUG), problema=("hero", [ROBOT], [EYES, MAIL, WARN]), solucion=("hero", [SHIELD], [LOCK, OFI, CHECK])),
 5: dict(gancho=("versus", [HACK, ROBOT]), caso=("flow", [HACK, ROBOT, GOV], BUG), problema=("hero", [ROBOT], [ZAP, TARGET, HOUR]), solucion=("hero", [SHIELD], [ROBOT, SEARCH, CHECK])),
 6: dict(gancho=("versus", [ROBOT, CAR]), caso=("flow", [DEV, ROBOT], CHAT), problema=("hero", [ROBOT], [WARN, HAND, CROSS]), solucion=("hero", [SHIELD], [ROBOT, OFI, CHECK])),
 7: dict(gancho=("hero", [DB], [KEY, DOC, FIRE]), caso=("flow", [DEV, LINK, GLOBE], DOC), problema=("hero", [KEY], [UNLOCK, HOUR, WARN]), solucion=("hero", [SHIELD], [LOCK, HOUR, SEARCH])),
 8: dict(gancho=("flow", [ROBOT, PACK, DEV], BUG), caso=("flow", [ROBOT, GHOST, HACK], PACK), problema=("hero", [PACK], [BUG, SKULL, WARN]), solucion=("hero", [SHIELD], [SEARCH, LOCK, CHECK])),
 9: dict(gancho=("hero", [DB], [UNLOCK, CHAT, KEY]), caso=("flow", [DETEC, DB], KEY), problema=("hero", [UNLOCK], [GLOBE, EYES, WARN]), solucion=("hero", [SHIELD], [LOCK, KEY, CHECK])),
 10: dict(gancho=("versus", [BUG, ROBOT]), caso=("flow", [PACK, PC, ROBOT], BUG), problema=("hero", [ROBOT], [KEY, SKULL, WARN]), solucion=("hero", [SHIELD], [KEY, LOCK, CHECK])),
 11: dict(gancho=("hero", [ROBOT], [DB, TRASH, FIRE]), caso=("flow", [ROBOT, DB, TRASH], DOC), problema=("hero", [NOENT], [ROBOT, CROSS, WARN]), solucion=("hero", [OFI], [CHECK, SHIELD, LOCK])),
 12: dict(gancho=("flow", [HACK, ROBOT], BOMB), caso=("flow", [HACK, DOC, ROBOT], BOMB), problema=("hero", [PACK], [BUG, EYES, WARN]), solucion=("hero", [SHIELD], [SEARCH, KEY, CHECK])),
 13: dict(gancho=("flow", [CHAT, ROBOT, HACK], LOCK), caso=("flow", [HACK, DOC, ROBOT], BUG), problema=("hero", [ROBOT], [KEY, UNLOCK, GLOBE]), solucion=("hero", [SHIELD], [KEY, OFI, CHECK])),
 14: dict(gancho=("flow", [ROBOT, PHONE, OFI], MIC), caso=("flow", [MIC, ROBOT, PHONE], BALLOT), problema=("hero", [MASK], [MIC, BALLOT, WARN]), solucion=("hero", [GOV], [SCALE, PHONE, CHECK])),
 15: dict(gancho=("hero", [BURGER], [UNLOCK, KEY, DOC]), caso=("flow", [DETEC, ROBOT, DB], KEY), problema=("hero", [DB], [DOC, EYES, WARN]), solucion=("hero", [SHIELD], [LOCK, KEY, CHECK])),
 16: dict(gancho=("flow", [CHAT, ROBOT, HACK], KEY), caso=("flow", [HACK, CHAT, ROBOT], BUG), problema=("hero", [ROBOT], [LOCK, CHAT, WARN]), solucion=("hero", [SHIELD], [KEY, LOCK, CHECK])),
 17: dict(gancho=("hero", [KEY], [CLOUD, DB, FIRE]), caso=("flow", [HACK, KEY, CLOUD], DOC), problema=("hero", [HAND], [KEY, UNLOCK, WARN]), solucion=("hero", [SHIELD], [SEARCH, KEY, CHECK])),
 18: dict(gancho=("versus", [HACK, ROBOT]), caso=("flow", [HACK, ROBOT, HOSP], KEY), problema=("hero", [HACK], [ROBOT, MONEY, TARGET]), solucion=("hero", [SHIELD], [KEY, DB, SEARCH])),
 19: dict(gancho=("flow", [CHAT, SEARCH, GLOBE], DOC), caso=("flow", [OFI, LINK, GLOBE], CHAT), problema=("hero", [EYES], [CHAT, GLOBE, WARN]), solucion=("hero", [SHIELD], [TRASH, LOCK, CHECK])),
 20: dict(gancho=("flow", [PHONE, OFI], MIC), caso=("flow", [OFI, BANK, GLOBE], MONEY), problema=("hero", [MASK], [MIC, HOUR, WARN]), solucion=("hero", [SHIELD], [PHONE, KEY, CHECK])),
}
CTA = ("hero", [HERO], [BELL, CHAT, BOOK])
VILLANOS = {HACK, MASK, BUG, SKULL, BOMB, GHOST}
def codigos():
    s = {MASCOTA, ZAP}
    for e in list(ESCENAS.values()):
        for v in e.values():
            s.update(v[1]); s.update(v[2] if len(v) > 2 and isinstance(v[2], list) else ([v[2]] if len(v) > 2 else []))
    s.update(CTA[1]); s.update(CTA[2])
    return sorted(s)
