This project is provided under GPL-3.0 (see LICENSE).

Calculation logic in printer.py (and its browser port, web/printer.js) is adapted from kwsch/ItemPrinterDeGacha:
https://github.com/kwsch/ItemPrinterDeGacha

The unmodified item and ball lottery tables in web/data come from that project's
ItemPrinterDeGacha.Core/Resources directory. English item names are keyed by
national item ID. The upstream application credits PKHeX for item localization
and its xoroshiro128+ implementation, under GPLv3.

The browser interface, LAN server, clock tracking, and launch scripts were added
in this workspace. No connection to a Nintendo console is made.

Artwork downloaded by artwork.py comes from the original ItemPrinterDeGacha
repository, with missing sprites from kwsch/PKHeX (Big Items or Artwork Items, via GitHub or
the jsDelivr mirror). All source image files
are retained in the reference gallery, with their source paths in references.json.
Pokémon character/item designs and game artwork belong to their respective owners
(Nintendo, Creatures, and GAME FREAK). No generated replacement artwork is used.
