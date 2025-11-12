"""
Mushroom Database with Common Names and Edibility Information
This provides comprehensive mushroom data for accurate catalog expansion.
"""

# Comprehensive mushroom database with common names and edibility
MUSHROOM_DATABASE = {
    # Poisonous/Deadly Species (P)
    "Amanita ocreata": {
        "common_name": "Western Destroying Angel",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "One of the most deadly mushrooms in North America"
    },
    "Amanita bisporigera": {
        "common_name": "Eastern Destroying Angel",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "Extremely toxic, causes liver and kidney failure"
    },
    "Amanita phalloides": {
        "common_name": "Death Cap",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "Responsible for most mushroom poisoning deaths worldwide"
    },
    "Amanita muscaria": {
        "common_name": "Fly Agaric",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Iconic red and white mushroom, psychoactive and toxic"
    },
    "Amanita virosa": {
        "common_name": "European Destroying Angel",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "Deadly poisonous, contains amatoxins"
    },
    "Galerina marginata": {
        "common_name": "Deadly Galerina",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "Contains same toxins as Death Cap, grows on wood"
    },
    "Gyromitra esculenta": {
        "common_name": "False Morel",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Contains gyromitrin, converts to rocket fuel component"
    },
    "Omphalotus olearius": {
        "common_name": "Jack O'Lantern",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Bioluminescent, often confused with chanterelles"
    },
    "Omphalotus illudens": {
        "common_name": "Eastern Jack O'Lantern",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Glows in the dark, causes severe GI distress"
    },
    "Cortinarius rubellus": {
        "common_name": "Deadly Webcap",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "Contains orellanine, causes kidney failure"
    },
    "Cortinarius orellanus": {
        "common_name": "Fool's Webcap",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "Deadly kidney toxin, symptoms delayed for days"
    },
    "Lepiota brunneoincarnata": {
        "common_name": "Deadly Dapperling",
        "edibility": "P",
        "toxicity": "deadly",
        "description": "Contains amatoxins, small but deadly"
    },
    "Paxillus involutus": {
        "common_name": "Brown Roll Rim",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Causes cumulative poisoning over time"
    },
    "Entoloma sinuatum": {
        "common_name": "Livid Entoloma",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Causes severe gastrointestinal poisoning"
    },
    "Hypholoma fasciculare": {
        "common_name": "Sulfur Tuft",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Bitter taste, grows in clusters on wood"
    },
    "Clitocybe dealbata": {
        "common_name": "Ivory Funnel",
        "edibility": "P",
        "toxicity": "poisonous",
        "description": "Contains muscarine, causes sweating and salivation"
    },

    # Edible Species (E)
    "Morchella esculenta": {
        "common_name": "Common Morel",
        "edibility": "E",
        "toxicity": "none",
        "description": "Highly prized spring edible with honeycomb cap"
    },
    "Morchella americana": {
        "common_name": "Yellow Morel",
        "edibility": "E",
        "toxicity": "none",
        "description": "American morel species, excellent edible"
    },
    "Morchella elata": {
        "common_name": "Black Morel",
        "edibility": "E",
        "toxicity": "none",
        "description": "Dark colored morel, highly sought after"
    },
    "Cantharellus cibarius": {
        "common_name": "Golden Chanterelle",
        "edibility": "E",
        "toxicity": "none",
        "description": "Golden yellow with false gills, apricot aroma"
    },
    "Cantharellus formosus": {
        "common_name": "Pacific Golden Chanterelle",
        "edibility": "E",
        "toxicity": "none",
        "description": "West Coast chanterelle variety"
    },
    "Cantharellus lateritius": {
        "common_name": "Smooth Chanterelle",
        "edibility": "E",
        "toxicity": "none",
        "description": "Eastern North American chanterelle"
    },
    "Craterellus cornucopioides": {
        "common_name": "Black Trumpet",
        "edibility": "E",
        "toxicity": "none",
        "description": "Funnel-shaped, excellent flavor when dried"
    },
    "Boletus edulis": {
        "common_name": "King Bolete",
        "edibility": "E",
        "toxicity": "none",
        "description": "Porcini, one of the best edible mushrooms"
    },
    "Pleurotus ostreatus": {
        "common_name": "Oyster Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Shelf-like growth on trees, mild flavor"
    },
    "Hericium erinaceus": {
        "common_name": "Lion's Mane",
        "edibility": "E",
        "toxicity": "none",
        "description": "White, shaggy appearance, medicinal properties"
    },
    "Hericium americanum": {
        "common_name": "Bear's Head Tooth",
        "edibility": "E",
        "toxicity": "none",
        "description": "Branched version of Lion's Mane"
    },
    "Armillaria mellea": {
        "common_name": "Honey Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Grows in clusters, must be well-cooked"
    },
    "Lactarius deliciosus": {
        "common_name": "Saffron Milk Cap",
        "edibility": "E",
        "toxicity": "none",
        "description": "Orange mushroom with orange milk"
    },
    "Hypomyces lactifluorum": {
        "common_name": "Lobster Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Parasitic fungus that transforms other mushrooms"
    },
    "Tricholoma matsutake": {
        "common_name": "Matsutake",
        "edibility": "E",
        "toxicity": "none",
        "description": "Highly valued in Japanese cuisine, spicy aroma"
    },
    "Laetiporus sulphureus": {
        "common_name": "Chicken of the Woods",
        "edibility": "E",
        "toxicity": "none",
        "description": "Bright orange/yellow brackets, chicken-like texture"
    },
    "Laetiporus gilbertsonii": {
        "common_name": "Western Chicken of the Woods",
        "edibility": "E",
        "toxicity": "none",
        "description": "West Coast variant growing on eucalyptus and oak"
    },
    "Grifola frondosa": {
        "common_name": "Maitake",
        "edibility": "E",
        "toxicity": "none",
        "description": "Hen of the Woods, grows at base of oaks"
    },
    "Calvatia gigantea": {
        "common_name": "Giant Puffball",
        "edibility": "E",
        "toxicity": "none",
        "description": "Can grow soccer ball sized, edible when young and white"
    },
    "Lycoperdon perlatum": {
        "common_name": "Common Puffball",
        "edibility": "E",
        "toxicity": "none",
        "description": "Small puffball with spiny surface"
    },
    "Coprinus comatus": {
        "common_name": "Shaggy Mane",
        "edibility": "E",
        "toxicity": "none",
        "description": "Tall white mushroom that dissolves into ink"
    },
    "Agaricus campestris": {
        "common_name": "Meadow Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Wild relative of button mushroom"
    },
    "Agaricus arvensis": {
        "common_name": "Horse Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Large white mushroom with anise smell"
    },
    "Macrolepiota procera": {
        "common_name": "Parasol Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Tall mushroom with snakeskin pattern on stem"
    },
    "Sparassis crispa": {
        "common_name": "Cauliflower Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Brain-like or cauliflower appearance"
    },
    "Hydnum repandum": {
        "common_name": "Hedgehog Mushroom",
        "edibility": "E",
        "toxicity": "none",
        "description": "Has spines instead of gills under cap"
    },
    "Auricularia auricula-judae": {
        "common_name": "Wood Ear",
        "edibility": "E",
        "toxicity": "none",
        "description": "Jelly fungus, popular in Asian cuisine"
    },

    # Conditionally Edible or Uncertain (U)
    "Leccinum versipelle": {
        "common_name": "Orange Birch Bolete",
        "edibility": "U",
        "toxicity": "caution",
        "description": "Edible but may cause illness if undercooked"
    },
    "Coprinopsis atramentaria": {
        "common_name": "Ink Cap",
        "edibility": "U",
        "toxicity": "caution",
        "description": "Edible but toxic with alcohol"
    },
    "Agaricus placomyces": {
        "common_name": "Eastern Flat-topped Agaricus",
        "edibility": "U",
        "toxicity": "caution",
        "description": "May cause gastrointestinal upset in some"
    },
}

def get_mushroom_info(scientific_name: str) -> dict:
    """Get mushroom information by scientific name"""
    # Try exact match first
    if scientific_name in MUSHROOM_DATABASE:
        return MUSHROOM_DATABASE[scientific_name]

    # Try partial match (for subspecies or variations)
    for key, value in MUSHROOM_DATABASE.items():
        if scientific_name.lower() in key.lower() or key.lower() in scientific_name.lower():
            return value

    # Default if not found
    return {
        "common_name": scientific_name.split()[-1].title(),  # Use species name as fallback
        "edibility": "U",  # Unknown by default for safety
        "toxicity": "unknown",
        "description": f"Information pending for {scientific_name}"
    }

def is_edible(scientific_name: str) -> bool:
    """Check if a mushroom is edible"""
    info = get_mushroom_info(scientific_name)
    return info["edibility"] == "E"

def is_poisonous(scientific_name: str) -> bool:
    """Check if a mushroom is poisonous"""
    info = get_mushroom_info(scientific_name)
    return info["edibility"] == "P"

def get_common_name(scientific_name: str) -> str:
    """Get common name for a mushroom"""
    info = get_mushroom_info(scientific_name)
    return info["common_name"]

def get_edibility_category(scientific_name: str) -> str:
    """Get edibility category (E/P/U)"""
    info = get_mushroom_info(scientific_name)
    return info["edibility"]