from atlas.sectors import SECTOR_REGISTRY_VERSION, SectorPolicy


def test_source_neutral_taxonomy_roots_cover_business_sectors() -> None:
    policy = SectorPolicy()

    cases = {
        "atlas.food.product": ("consumer_goods_services", "food_beverages"),
        "atlas.material.plastics": ("materials_manufacturing", "materials"),
        "atlas.energy.electricity.grid_mix": ("energy", "electricity"),
        "atlas.transport.freight.road": ("transport", "freight_transport"),
        "atlas.construction_product": ("buildings_infrastructure", "construction_products"),
        "atlas.agriculture.crop": ("agriculture_forestry_fishing", "agriculture"),
        "atlas.land_use": ("land_use", "land_use"),
        "atlas.waste.treatment": ("waste", "waste_treatment"),
        "atlas.water.supply": ("water", "water_supply_treatment"),
        "atlas.refrigerants": ("cross_sector", "refrigerants"),
    }

    for taxonomy, expected in cases.items():
        assignment = policy.classify(taxonomy)
        assert (assignment.sector_code, assignment.category_code) == expected
        assert assignment.mapping_version == SECTOR_REGISTRY_VERSION
        assert assignment.confidence == 100


def test_spend_codes_are_projected_by_economic_activity() -> None:
    policy = SectorPolicy()

    cases = {
        "atlas.spend.economic_sector.111000": "agriculture_forestry_fishing",
        "atlas.spend.economic_sector.334515": "materials_manufacturing",
        "atlas.spend.economic_sector.221300": "water",
        "atlas.spend.economic_sector.221100": "energy",
        "atlas.spend.economic_sector.230000": "buildings_infrastructure",
        "atlas.spend.economic_sector.480000": "transport",
        "atlas.spend.economic_sector.721000": "restaurants_accommodation",
        "atlas.spend.economic_sector.562000": "waste",
        "atlas.spend.economic_sector.541100": "consumer_goods_services",
    }

    for taxonomy, expected_sector in cases.items():
        assert policy.classify(taxonomy).sector_code == expected_sector


def test_unknown_taxonomy_is_explicit_cross_sector_fallback() -> None:
    assignment = SectorPolicy().classify("atlas.unmapped")

    assert assignment.sector_code == "cross_sector"
    assert assignment.category_code == "general"
    assert assignment.confidence == 70
    assert assignment.rule_code == "taxonomy.explicit_fallback"
