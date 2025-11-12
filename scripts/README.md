# Mushroom Tracker CDN Scripts

Complete toolset for managing mushroom species images and metadata in the CDN.

## Scripts Overview

### Core Generation & Management

#### `generate_cdn_content.py`
**Main content generation script** - Processes species from Mushroom Observer and generates CDN-ready content.

```bash
# Generate content for species in species.txt
python3 scripts/generate_cdn_content.py

# Dry run to preview
python3 scripts/generate_cdn_content.py --dry-run

# Custom output directory
python3 scripts/generate_cdn_content.py --output-dir /path/to/output
```

**Features:**
- Downloads images from Mushroom Observer dataset cache
- Filters for commercial-friendly licenses only
- Generates WebP thumbnails (200x200) and full images (800x800)
- Creates metadata.json for each species
- Generates master manifest.json with SHA-256 hashes
- Excludes non-mushroom images (habitat notes, rulers, etc.)

**Requirements:**
- `scripts/mo_dataset_cache.csv` - Mushroom Observer data
- `scripts/species.txt` - List of species to process
- Pillow library: `pip install Pillow`

#### `mushroom_database.py`
Database interface for managing mushroom species information and queries.

#### `mushroom_catalog_expander.py`
Tools for expanding the catalog with additional species.

### Quality Assessment

#### `image_quality_scorer.py`
**Analyzes all images** in the CDN and generates quality reports.

```bash
# Score all images in the repository
python3 scripts/image_quality_scorer.py
```

**Outputs:**
- `scripts/image_quality_report.json` - Detailed metrics for every image
- Console summary with statistics and problem areas

**Quality Metrics:**
- **Blur Detection**: Laplacian variance (higher = sharper)
  - Excellent: > 500
  - Good: > 200
  - Fair: > 100
  - Poor: ≤ 100

- **Brightness/Contrast**: Proper exposure and dynamic range
  - Good brightness: 40-215
  - Good contrast: > 30

- **Color Distribution**: Natural vs artificial
  - Excellent: variance > 2000
  - Good: variance > 1000

- **White Region Detection**: Identifies plastic bags, paper
  - Good: < 10% white pixels
  - Poor: > 25% white pixels

- **Overall Score**: 0-100 (weighted average of all metrics)

**Current Results (455 images analyzed):**
- Average score: 85.7
- Excellent (80-100): 332 images (73%)
- Good (60-79): 92 images (20%)
- Fair (40-59): 27 images (6%)
- Poor (0-39): 4 images (1%)

**Problem Areas Identified:**
- 19 species with suboptimal thumbnails (better image available)
- 6 species need entirely new images
- 4 images scoring below 40 (urgent replacement needed)

### Image Finding & Replacement

#### `mushroom_observer_image_finder.py`
Downloads Mushroom Observer CSV data and searches for replacement images.

**Note:** CSV downloads currently blocked by MO (403 Forbidden). Use API version instead.

#### `mushroom_observer_api_finder.py`
**API-based image finder** - Searches Mushroom Observer and scores candidate images.

```bash
# Search by scientific name
python3 scripts/mushroom_observer_api_finder.py --species "Exidia glandulosa"

# Search by species ID (looks up name from your metadata)
python3 scripts/mushroom_observer_api_finder.py --species-id exigla

# Customize search
python3 scripts/mushroom_observer_api_finder.py \
  --species "Russula claroflava" \
  --top 15 \              # Evaluate 15 candidates
  --min-score 80          # Only show images scoring 80+
```

**Features:**
- Searches Mushroom Observer API for observations
- Filters for commercial-friendly licenses only
- Downloads candidate images (rate-limited to API requirements)
- Scores images using quality scorer
- Recommends best images with full attribution details

**Rate Limiting:**
- Respects MO's 1 request per 5 seconds limit
- Shows progress and estimated completion time

## Complete Workflow

### 1. Analyze Current Images

```bash
python3 scripts/image_quality_scorer.py
```

Review the generated `QUALITY_RECOMMENDATIONS.md` file to identify:
- Species with poor thumbnails
- Species needing new images
- Specific images to replace

### 2. Find Replacement Images

For species needing new images:

```bash
# Example: Find replacements for Exidia glandulosa (low quality)
python3 scripts/mushroom_observer_api_finder.py --species-id exigla --top 10
```

The script will:
1. Search Mushroom Observer
2. Filter by commercial licenses
3. Download and score candidates
4. Show you the best options with attribution

### 3. Update Content

Once you have identified better source images:

1. Update `scripts/mo_dataset_cache.csv` with new image URLs
2. Run `generate_cdn_content.py` to regenerate affected species
3. Verify new images with quality scorer
4. Update manifest SHA-256 (triggers app updates)

### Quick Wins: Thumbnail Swaps

For species where a different existing image would be better as thumbnail:

```bash
# List from QUALITY_RECOMMENDATIONS.md shows 19 species
# Example: agaaug (thumb: 73 vs image_1: 97)

cp species/agaaug/image_1.webp species/agaaug/thumb.webp

# Resize to proper thumbnail size
python3 << EOF
from PIL import Image
img = Image.open('species/agaaug/thumb.webp')
img.thumbnail((200, 200), Image.Resampling.LANCZOS)
img.save('species/agaaug/thumb.webp', 'WEBP', quality=85, method=6)
EOF
```

Then update manifest with new SHA-256 hash.

## Data Files

### `species.txt`
List of species scientific names to process (one per line):
```
Morchella esculenta
Cantharellus formosus
Armillaria mellea
```

Comments start with `#` and are ignored.

### `mo_dataset_cache.csv`
Mushroom Observer dataset cache with columns:
```
image,name,created,license_url,photographer
```

Example:
```csv
https://mushroomobserver.org/images/640/12345.jpg,Morchella esculenta,2023-04-15,https://creativecommons.org/licenses/by-sa/3.0/,John Doe
```

## License Compliance

All scripts enforce commercial-friendly licenses:

**✅ Allowed:**
- Creative Commons Attribution (CC BY)
- Creative Commons Attribution-ShareAlike (CC BY-SA)
- Creative Commons Zero (CC0)
- Public Domain

**❌ Rejected:**
- CC BY-NC (Non-Commercial)
- CC BY-ND (No Derivatives)
- All rights reserved

This ensures the mobile app can include monetization features.

## Installation

```bash
# Install required dependencies
pip install Pillow requests

# Verify scripts work
python3 scripts/image_quality_scorer.py --help
python3 scripts/mushroom_observer_api_finder.py --help
```

## Output Structure

Generated content follows this structure:

```
mushroom-tracker-data-cdn/
├── manifest.json              # Master index with SHA-256
└── species/
    ├── moresc/                # 6-char species ID
    │   ├── metadata.json      # Full species details
    │   ├── thumb.webp         # 200×200 thumbnail
    │   ├── image_0.webp       # 800×800 full image
    │   └── image_1.webp       # 800×800 full image
    └── canfor/
        └── ...
```

## Current Status

- **Total Species**: 152
- **Total Images**: 455 (303 full images + 152 thumbnails)
- **Total Size**: 24.4 MB
- **Average Quality Score**: 85.7/100

**Action Items:**
1. 🔴 Urgent: Replace 4 images scoring < 40
2. 🟡 High Priority: Fix 19 thumbnail issues (quick wins)
3. 🟢 Medium Priority: Source new images for 6 species

See `QUALITY_RECOMMENDATIONS.md` for detailed action plan.

## Additional Documentation

- `WORKFLOW_GUIDE.md` - Step-by-step workflow examples
- `QUALITY_RECOMMENDATIONS.md` - Generated quality analysis report
- `image_quality_report.json` - Raw quality metrics data

## Support

For issues or questions about these scripts, refer to the main repository README or file an issue on GitHub.
