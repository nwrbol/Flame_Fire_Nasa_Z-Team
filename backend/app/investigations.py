"""Local NASA investigation catalogue. No experimental measurements."""

OVERVIEW = (
    "https://www.nasa.gov/missions/station/"
    "studying-combustion-and-fire-safety/"
)
SAFFIRE = (
    "https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/"
    "20170000230.pdf"
)
SAME = (
    "https://science.nasa.gov/physical-sciences-informatics-psi/"
    "nasa-psi-research-opportunity/"
)
PSI = "https://psi.nasa.gov/physci/repo/data/investigations/"


def entry(identifier, name, series, description, source_url, candidate=None):
    item = {
        "id": identifier,
        "name": name,
        "series": series,
        "description": description,
        "source_url": source_url,
        "data_status": "description_only_csv_not_connected",
    }

    if candidate:
        item["provided_source_url"] = PSI + candidate
        item["provided_source_status"] = "name_mapping_unverified"

    return item


INVESTIGATIONS = [
    entry(
        "flex",
        "FLEX",
        "FLEX",
        "Study of liquid fuel droplet combustion and the effectiveness "
        "of gaseous fire suppressants in microgravity.",
        PSI + "PSI-69",
    ),
    entry(
        "flex-2",
        "FLEX-2",
        "FLEX",
        "Study of droplet combustion, soot formation, and evaporation "
        "of liquid fuel mixtures in microgravity.",
        OVERVIEW,
        "PSI-68",
    ),
    entry(
        "saffire-i",
        "Saffire-I",
        "Saffire",
        "Study of large-scale flame spread in low gravity aboard "
        "an uncrewed Cygnus spacecraft.",
        PSI + "PSI-98",
    ),
    entry(
        "saffire-ii",
        "Saffire-II",
        "Saffire",
        "A Saffire experiment investigating material flammability "
        "and spacecraft fire safety.",
        SAFFIRE,
        "PSI-99",
    ),
    entry(
        "saffire-iii",
        "Saffire-III",
        "Saffire",
        "A Saffire experiment investigating flame growth and material "
        "flammability in low gravity.",
        SAFFIRE,
        "PSI-100",
    ),
    entry(
        "bass",
        "BASS",
        "BASS",
        "Study of solid fuel combustion and suppression in microgravity.",
        OVERVIEW,
    ),
    entry(
        "bass-ii",
        "BASS-II",
        "BASS",
        "Study of the combustion of different fuel samples in microgravity "
        "and comparison with normal gravity.",
        OVERVIEW,
        "PSI-25",
    ),
    entry(
        "acme",
        "ACME",
        "ACME",
        "A series of gaseous flame studies in microgravity examining "
        "combustion efficiency, pollutant emissions, and fire safety.",
        "https://science.nasa.gov/mission/acme/",
    ),
    entry(
        "same",
        "SAME",
        "SAME",
        "Smoke Aerosol Measurement Experiment: a study of smoke aerosols.",
        SAME,
    ),
    entry(
        "same-r",
        "SAME-R",
        "SAME",
        "A reflight of SAME studying smoke aerosol particle sizes in low "
        "gravity and their relationship to smoke generation and "
        "transport conditions.",
        PSI + "PSI-101",
    ),
]

