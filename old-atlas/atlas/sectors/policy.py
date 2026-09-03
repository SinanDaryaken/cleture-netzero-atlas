# ruff: noqa: RUF001
from __future__ import annotations

from dataclasses import dataclass

SECTOR_REGISTRY_VERSION = "1.0.0"


@dataclass(frozen=True)
class SectorDefinition:
    code: str
    name_en: str
    name_tr: str
    description: str


@dataclass(frozen=True)
class SectorCategoryDefinition:
    code: str
    sector_code: str
    name_en: str
    name_tr: str


@dataclass(frozen=True)
class SectorAssignment:
    sector_code: str
    category_code: str
    confidence: int
    rule_code: str
    mapping_version: str = SECTOR_REGISTRY_VERSION


SECTOR_REGISTRY: tuple[SectorDefinition, ...] = (
    SectorDefinition(
        "consumer_goods_services",
        "Consumer Goods and Services",
        "Tüketici Ürünleri ve Hizmetleri",
        "Food, purchased goods, commerce, professional and public services.",
    ),
    SectorDefinition(
        "materials_manufacturing",
        "Materials and Manufacturing",
        "Malzemeler ve İmalat",
        "Raw materials, mining, manufacturing and industrial processes.",
    ),
    SectorDefinition("energy", "Energy", "Enerji", "Electricity, fuels, heat and utilities."),
    SectorDefinition(
        "restaurants_accommodation",
        "Restaurants and Accommodation",
        "Restoranlar ve Konaklama",
        "Accommodation and food-service activities.",
    ),
    SectorDefinition("transport", "Transport", "Ulaşım", "Passenger and freight transport."),
    SectorDefinition(
        "buildings_infrastructure",
        "Buildings and Infrastructure",
        "Binalar ve Altyapı",
        "Construction products, buildings, real estate and infrastructure.",
    ),
    SectorDefinition(
        "agriculture_forestry_fishing",
        "Agriculture / Hunting / Forestry / Fishing",
        "Tarım / Avcılık / Ormancılık / Balıkçılık",
        "Agriculture, hunting, forestry and fishing activities.",
    ),
    SectorDefinition("land_use", "Land Use", "Arazi Kullanımı", "Land-use and land-use change."),
    SectorDefinition("waste", "Waste", "Atık", "Waste collection, treatment and disposal."),
    SectorDefinition("water", "Water", "Su", "Water supply, use and treatment."),
    SectorDefinition(
        "cross_sector",
        "Cross-sector / General",
        "Sektörler Arası / Genel",
        "Methodologies, refrigerants and records that are intentionally cross-sector.",
    ),
)

SECTOR_CATEGORIES: tuple[SectorCategoryDefinition, ...] = (
    SectorCategoryDefinition(
        "food_beverages", "consumer_goods_services", "Food and Beverages", "Gıda ve İçecek"
    ),
    SectorCategoryDefinition(
        "purchased_goods", "consumer_goods_services", "Purchased Goods", "Satın Alınan Ürünler"
    ),
    SectorCategoryDefinition("services", "consumer_goods_services", "Services", "Hizmetler"),
    SectorCategoryDefinition("commerce", "consumer_goods_services", "Commerce", "Ticaret"),
    SectorCategoryDefinition(
        "other_consumer",
        "consumer_goods_services",
        "Other Consumer Goods and Services",
        "Diğer Tüketici Ürünleri ve Hizmetleri",
    ),
    SectorCategoryDefinition("materials", "materials_manufacturing", "Materials", "Malzemeler"),
    SectorCategoryDefinition("manufacturing", "materials_manufacturing", "Manufacturing", "İmalat"),
    SectorCategoryDefinition("mining", "materials_manufacturing", "Mining", "Madencilik"),
    SectorCategoryDefinition(
        "industrial_processes",
        "materials_manufacturing",
        "Industrial Processes",
        "Endüstriyel Prosesler",
    ),
    SectorCategoryDefinition("electricity", "energy", "Electricity", "Elektrik"),
    SectorCategoryDefinition("fuels", "energy", "Fuels", "Yakıtlar"),
    SectorCategoryDefinition("heat_cooling", "energy", "Heat and Cooling", "Isı ve Soğutma"),
    SectorCategoryDefinition("energy_utilities", "energy", "Energy Utilities", "Enerji Hizmetleri"),
    SectorCategoryDefinition(
        "accommodation", "restaurants_accommodation", "Accommodation", "Konaklama"
    ),
    SectorCategoryDefinition(
        "food_services", "restaurants_accommodation", "Food Services", "Yeme İçme Hizmetleri"
    ),
    SectorCategoryDefinition(
        "passenger_transport", "transport", "Passenger Transport", "Yolcu Taşımacılığı"
    ),
    SectorCategoryDefinition(
        "freight_transport", "transport", "Freight Transport", "Yük Taşımacılığı"
    ),
    SectorCategoryDefinition(
        "transport_services", "transport", "Transport Services", "Ulaşım Hizmetleri"
    ),
    SectorCategoryDefinition(
        "construction_products",
        "buildings_infrastructure",
        "Construction Products",
        "Yapı Ürünleri",
    ),
    SectorCategoryDefinition("construction", "buildings_infrastructure", "Construction", "İnşaat"),
    SectorCategoryDefinition(
        "buildings_real_estate",
        "buildings_infrastructure",
        "Buildings and Real Estate",
        "Binalar ve Gayrimenkul",
    ),
    SectorCategoryDefinition(
        "agriculture", "agriculture_forestry_fishing", "Agriculture and Hunting", "Tarım ve Avcılık"
    ),
    SectorCategoryDefinition(
        "forestry_fishing",
        "agriculture_forestry_fishing",
        "Forestry and Fishing",
        "Ormancılık ve Balıkçılık",
    ),
    SectorCategoryDefinition("land_use", "land_use", "Land Use", "Arazi Kullanımı"),
    SectorCategoryDefinition("waste_treatment", "waste", "Waste Treatment", "Atık İşleme"),
    SectorCategoryDefinition(
        "water_supply_treatment", "water", "Water Supply and Treatment", "Su Temini ve Arıtma"
    ),
    SectorCategoryDefinition("refrigerants", "cross_sector", "Refrigerants", "Soğutucu Akışkanlar"),
    SectorCategoryDefinition("methodology", "cross_sector", "Methodology", "Metodoloji"),
    SectorCategoryDefinition("general", "cross_sector", "General", "Genel"),
)


class SectorPolicy:
    """Versioned, source-neutral projection from canonical taxonomy to business sector."""

    version = SECTOR_REGISTRY_VERSION

    def classify(self, taxonomy_code: str | None) -> SectorAssignment:
        taxonomy = (taxonomy_code or "atlas.unmapped").casefold().strip()
        if taxonomy.startswith("atlas."):
            taxonomy = taxonomy[6:]

        if taxonomy.startswith("spend.economic_sector."):
            return self._classify_spend(taxonomy.rsplit(".", 1)[-1])
        if taxonomy.startswith("construction_product"):
            return self._assignment(
                "buildings_infrastructure", "construction_products", "taxonomy.construction_product"
            )
        if taxonomy.startswith("food"):
            return self._assignment("consumer_goods_services", "food_beverages", "taxonomy.food")
        if taxonomy.startswith("energy"):
            if ".electricity" in taxonomy:
                category = "electricity"
            elif any(token in taxonomy for token in ("heat", "cooling")):
                category = "heat_cooling"
            else:
                category = "fuels"
            return self._assignment("energy", category, f"taxonomy.energy.{category}")
        if taxonomy.startswith("material"):
            return self._assignment("materials_manufacturing", "materials", "taxonomy.material")
        if taxonomy.startswith("transport"):
            category = (
                "freight_transport"
                if "freight" in taxonomy
                else "passenger_transport"
                if "passenger" in taxonomy
                else "transport_services"
            )
            return self._assignment("transport", category, f"taxonomy.transport.{category}")
        if taxonomy.startswith("agriculture"):
            return self._assignment(
                "agriculture_forestry_fishing", "agriculture", "taxonomy.agriculture"
            )
        if taxonomy.startswith("waste"):
            return self._assignment("waste", "waste_treatment", "taxonomy.waste")
        if taxonomy.startswith("industrial_processes"):
            return self._assignment(
                "materials_manufacturing", "industrial_processes", "taxonomy.industrial_processes"
            )
        if taxonomy.startswith("services"):
            return self._assignment("consumer_goods_services", "services", "taxonomy.services")
        if taxonomy.startswith("land_use"):
            return self._assignment("land_use", "land_use", "taxonomy.land_use")
        if taxonomy.startswith("water"):
            return self._assignment("water", "water_supply_treatment", "taxonomy.water")
        if taxonomy.startswith("refrigerants"):
            return self._assignment("cross_sector", "refrigerants", "taxonomy.refrigerants")
        if taxonomy.startswith("methodology"):
            return self._assignment("cross_sector", "methodology", "taxonomy.methodology")
        if taxonomy.startswith("emep_eea.nfr.1_a_3"):
            return self._assignment(
                "transport", "transport_services", "taxonomy.emep_eea.transport"
            )
        if taxonomy.startswith("emep_eea.nfr.1_a_2"):
            return self._assignment(
                "materials_manufacturing", "manufacturing", "taxonomy.emep_eea.manufacturing"
            )
        if taxonomy.startswith("emep_eea.nfr.1_a_4_c"):
            return self._assignment(
                "agriculture_forestry_fishing", "agriculture", "taxonomy.emep_eea.agriculture"
            )
        if taxonomy.startswith(("emep_eea.nfr.1_a_4_a", "emep_eea.nfr.1_a_4_b")):
            return self._assignment(
                "buildings_infrastructure", "buildings_real_estate", "taxonomy.emep_eea.buildings"
            )
        return SectorAssignment("cross_sector", "general", 70, "taxonomy.explicit_fallback")

    def _classify_spend(self, code: str) -> SectorAssignment:
        compact = "".join(character for character in code if character.isdigit())
        if compact.startswith("11"):
            return self._assignment("agriculture_forestry_fishing", "agriculture", "spend.naics.11")
        if compact.startswith("21"):
            return self._assignment("materials_manufacturing", "mining", "spend.naics.21")
        if compact.startswith(("31", "32", "33")):
            return self._assignment("materials_manufacturing", "manufacturing", "spend.naics.31_33")
        if compact.startswith("2213"):
            return self._assignment("water", "water_supply_treatment", "spend.naics.2213")
        if compact.startswith("22"):
            return self._assignment("energy", "energy_utilities", "spend.naics.22")
        if compact.startswith("23"):
            return self._assignment("buildings_infrastructure", "construction", "spend.naics.23")
        if compact.startswith("531"):
            return self._assignment(
                "buildings_infrastructure", "buildings_real_estate", "spend.naics.531"
            )
        if compact.startswith(("48", "49")):
            return self._assignment("transport", "transport_services", "spend.naics.48_49")
        if compact.startswith("721"):
            return self._assignment("restaurants_accommodation", "accommodation", "spend.naics.721")
        if compact.startswith("722"):
            return self._assignment("restaurants_accommodation", "food_services", "spend.naics.722")
        if compact.startswith("562"):
            return self._assignment("waste", "waste_treatment", "spend.naics.562")
        return self._assignment("consumer_goods_services", "other_consumer", "spend.naics.other")

    def _assignment(self, sector: str, category: str, rule: str) -> SectorAssignment:
        return SectorAssignment(sector, category, 100, rule)
