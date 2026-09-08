from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CanonicalEntity:
    entity_id: str
    entity_type: str
    label: str
    aliases: tuple[str, ...]


CANONICAL_ENTITIES: tuple[CanonicalEntity, ...] = (
    CanonicalEntity("BDI", "index", "Baltic Dry Index", ("baltic dry", "badi", "baltic exchange dry")),
    CanonicalEntity("BCI", "index", "Baltic Capesize Index", ("capesize index", "baltic capesize")),
    CanonicalEntity("BPI", "index", "Baltic Panamax Index", ("panamax index", "baltic panamax")),
    CanonicalEntity("BSI", "index", "Baltic Supramax Index", ("supramax index", "ultramax")),
    CanonicalEntity("BHSI", "index", "Baltic Handysize Index", ("handysize index",)),
    CanonicalEntity("capesize", "vessel_class", "Capesize", ("cape ", "capesizes")),
    CanonicalEntity("panamax", "vessel_class", "Panamax", ("kamsarmax",)),
    CanonicalEntity("supramax", "vessel_class", "Supramax", ("ultramax",)),
    CanonicalEntity("handysize", "vessel_class", "Handysize", ("handy ",)),
    CanonicalEntity("iron_ore", "commodity", "Iron ore", ("62% fe", "fines", "simandou")),
    CanonicalEntity("coal", "commodity", "Coal", ("thermal coal", "met coal", "coking coal")),
    CanonicalEntity("wheat", "commodity", "Wheat", ("hrw", "srw", "grain")),
    CanonicalEntity("corn", "commodity", "Corn", ("maize",)),
    CanonicalEntity("soybeans", "commodity", "Soybeans", ("soy", "soybean meal")),
    CanonicalEntity("bauxite", "commodity", "Bauxite", ("alumina",)),
    CanonicalEntity("china", "country", "China", ("chinese", "prc")),
    CanonicalEntity("brazil", "country", "Brazil", ("brazilian",)),
    CanonicalEntity("australia", "country", "Australia", ("australian", "pilbara")),
    CanonicalEntity("guinea", "country", "Guinea", ("simandou",)),
)


ENTITY_BY_ID = {entity.entity_id: entity for entity in CANONICAL_ENTITIES}


def entity_type(entity_id: str) -> str | None:
    entity = ENTITY_BY_ID.get(entity_id)
    return entity.entity_type if entity else None
