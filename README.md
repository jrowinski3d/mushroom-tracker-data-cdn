# Mushroom Tracker Data CDN

Public CDN for progressive mushroom species content delivery to the Mushroom Tracker mobile app.

## Overview

This repository serves as a free CDN hosting mushroom species images and metadata for the [Mushroom Tracker](https://github.com/jasonstrowbridge/mushroom-tracker) React Native application. Content is delivered via GitHub's raw URLs, enabling app catalog expansion without App Store updates.

**Current Content:** 10 edible mushroom species with commercial-friendly licenses
**Total Size:** 1.6 MB (40 WebP images + metadata)
**License:** All images sourced from [Mushroom Observer](https://mushroomobserver.org) under CC BY or CC BY-SA licenses

## Repository Structure

```
mushroom-tracker-data-cdn/
├── manifest.json              # Master index of all species
└── species/
    ├── armmel/                # Armillaria mellea (Honey Mushroom)
    │   ├── metadata.json      # Species metadata + attribution
    │   ├── thumb.webp         # 200×200 thumbnail
    │   ├── image_0.webp       # 800×800 full image
    │   └── image_1.webp       # 800×800 full image
    ├── calgig/                # Calvatia gigantea (Giant Puffball)
    ├── canfor/                # Cantharellus formosus (Pacific Golden Chanterelle)
    ├── cracor/                # Craterellus cornucopioides (Black Trumpet)
    ├── grifro/                # Grifola frondosa (Maitake)
    ├── laegil/                # Laetiporus gilbertsonii (Western Chicken of the Woods)
    ├── morame/                # Morchella americana (American Morel)
    ├── moresc/                # Morchella esculenta (Common Morel)
    ├── spacri/                # Sparassis crispa (Cauliflower Mushroom)
    └── trimat/                # Tricholoma matsutake (Matsutake)
```

## CDN URLs

Content is accessed via GitHub raw URLs:

**Base URL:** `https://raw.githubusercontent.com/{username}/mushroom-tracker-data-cdn/main/`

### Manifest
```
https://raw.githubusercontent.com/{username}/mushroom-tracker-data-cdn/main/manifest.json
```

### Species Content
```
https://raw.githubusercontent.com/{username}/mushroom-tracker-data-cdn/main/species/{mushroom_id}/metadata.json
https://raw.githubusercontent.com/{username}/mushroom-tracker-data-cdn/main/species/{mushroom_id}/thumb.webp
https://raw.githubusercontent.com/{username}/mushroom-tracker-data-cdn/main/species/{mushroom_id}/image_0.webp
```

Example (Common Morel):
```
https://raw.githubusercontent.com/{username}/mushroom-tracker-data-cdn/main/species/moresc/thumb.webp
```

## Manifest Schema

`manifest.json` provides a master index of all available species:

```json
{
  "version": "1.0.0",
  "generated_at": "2025-11-05T20:00:00.250238",
  "total_species": 10,
  "total_size_bytes": 1568290,
  "sha256": "780a778ed6a16bcdd54be8beeba04afa95773b24af3cb2089b148aa19e730e9d",
  "species": [
    {
      "mushroom_id": "moresc",
      "scientific_name": "Morchella esculenta",
      "common_name": "Common Morel",
      "edibility": "E",
      "thumbnail_url": "species/moresc/thumb.webp",
      "image_count": 2,
      "total_size_bytes": 125796,
      "content_version": "1.0"
    }
  ]
}
```

### Fields

- **version:** Semantic versioning for manifest schema
- **generated_at:** ISO 8601 timestamp of generation
- **total_species:** Count of species in CDN
- **total_size_bytes:** Aggregate size of all content
- **sha256:** Hash for change detection (triggers app updates)
- **species:** Array of species metadata

## Metadata Schema

Each species has a `metadata.json` file with complete information:

```json
{
  "mushroom_id": "moresc",
  "scientific_name": "Morchella esculenta",
  "common_name": "Common Morel",
  "edibility": "E",
  "description": "Common Morel (Morchella esculenta) is a prized edible mushroom...",
  "habitat": "Various forest environments...",
  "season": "Seasonal availability varies by location and species.",
  "regions": ["North America"],
  "lookalikes": ["Various species - expert identification recommended"],
  "safety_notes": "Always verify identification with multiple sources before consuming wild mushrooms.",
  "images": [
    {
      "index": 0,
      "source_url": "https://mushroomobserver.org/images/640/1329025.jpg",
      "photographer": "Betty Green",
      "license_url": "http://creativecommons.org/licenses/by-sa/3.0/",
      "observation_date": "2021-05-15",
      "file_size_bytes": 49674,
      "width": 640,
      "height": 480,
      "sha256": "793f73a5d86bf33ec577e898cc6c501f08ecda5975bcbca73fd4ac8b1396369c"
    }
  ],
  "content_version": "1.0",
  "last_updated": "2025-11-05T19:59:56.673097"
}
```

### Image Attribution

All images include full attribution metadata:
- **photographer:** Photographer name from Mushroom Observer
- **license_url:** Creative Commons license URL (CC BY or CC BY-SA)
- **source_url:** Original image URL on Mushroom Observer
- **observation_date:** Date mushroom was observed/photographed

## Image Specifications

### Thumbnails (`thumb.webp`)
- **Dimensions:** 200×200 pixels
- **Format:** WebP (quality=85, method=6)
- **Size:** 9-15 KB average
- **Purpose:** Fast UI loading, list views

### Full Images (`image_N.webp`)
- **Dimensions:** 800×800 pixels (max)
- **Format:** WebP (quality=85, method=6)
- **Size:** 14-122 KB average
- **Count:** 2 per species
- **Purpose:** Detail views, identification

## License Compliance

All content uses commercial-friendly licenses:

**Accepted Licenses:**
- Creative Commons Attribution (CC BY)
- Creative Commons Attribution-ShareAlike (CC BY-SA)
- Creative Commons Zero (CC0)
- Public Domain

**Excluded Licenses:**
- CC BY-NC (Non-Commercial) - incompatible with app monetization
- CC BY-ND (No Derivatives) - incompatible with image processing
- All Rights Reserved

## Content Updates

The app checks for new content by comparing the manifest SHA-256 hash:

1. App fetches `manifest.json` on launch
2. Compares `sha256` to cached version
3. If changed, prompts user: "New species available for download"
4. User downloads new content via in-app modal

**Update Frequency:** As needed (no App Store review required)

## Content Generation

Content is generated using the Python script at:
`scripts/generate_cdn_content.py`

**Source Dataset:** [Mushroom Observer](https://mushroomobserver.org) (370,110+ images)

**Processing Pipeline:**
1. Filter for commercial-friendly licenses
2. Validate image URLs (exclude habitat shots, field notes)
3. Download original images
4. Convert to WebP format
5. Generate 200×200 thumbnails
6. Generate 800×800 full images
7. Calculate SHA-256 hashes
8. Create metadata with attribution

## Contributing Species

To add new species:

1. Run `generate_cdn_content.py` with updated species list
2. Verify all images have commercial licenses
3. Test generated content locally
4. Commit to repository
5. App will auto-detect changes via SHA-256

## Safety Disclaimer

This content is for educational and identification assistance purposes only.

**WARNING:** Never consume wild mushrooms without expert verification. Misidentification can cause serious illness or death. Always consult multiple sources and local mycological experts before consuming any wild mushroom.

## Attribution

Image data sourced from [Mushroom Observer](https://mushroomobserver.org), a collaborative community database of mushroom observations.

Special thanks to all photographers who contributed images under open licenses.

## Contact

For issues with CDN content or licensing questions, please open an issue in this repository.

---

**App Repository:** [mushroom-tracker](https://github.com/jasonstrowbridge/mushroom-tracker)
**Generated:** 2025-11-05
**Version:** 1.0.0
