# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

This is a **static CDN repository** for the Mushroom Tracker mobile app, serving mushroom species images and metadata via GitHub's raw URLs. Content is delivered to the React Native app without requiring App Store updates.

**Important:** This is NOT a code repository with build/test/lint commands. It's a data-only CDN containing JSON metadata and WebP images.

## Repository Structure

```
mushroom-tracker-data-cdn/
├── manifest.json              # Master index of all species (includes SHA-256 for change detection)
└── species/
    ├── {mushroom_id}/         # 6-char species code (e.g., "moresc", "canfor")
    │   ├── metadata.json      # Species details + image attribution
    │   ├── thumb.webp         # 200×200 thumbnail (9-15 KB)
    │   ├── image_0.webp       # 640×640 full image (14-122 KB)
    │   └── image_1.webp       # 640×640 full image
```

### Species ID Format
- 6-character codes derived from scientific names
- Format: First 3 letters of genus + first 3 letters of species
- Examples: `moresc` (Morchella esculenta), `canfor` (Cantharellus formosus)

## Key Architecture Concepts

### Content Delivery Model
The app checks `manifest.json` on launch, compares the `sha256` field to detect changes, then downloads new species content via in-app modal. This enables catalog expansion without App Store review.

### Manifest Schema
`manifest.json` contains:
- **version**: Semantic version for manifest schema
- **generated_at**: ISO 8601 timestamp
- **total_species**: Count of available species
- **total_size_bytes**: Aggregate content size
- **sha256**: Hash of all content (triggers app updates when changed)
- **species[]**: Array with per-species metadata including URLs, sizes, and content SHA

### Metadata Schema
Each `species/{id}/metadata.json` contains:
- Species identification (scientific name, common name, edibility)
- Educational content (description, habitat, season, regions, lookalikes, safety notes)
- **Critical:** Full image attribution (photographer, license_url, source_url, observation_date)
- Image technical details (SHA-256, dimensions, file size)
- Content versioning (content_version, last_updated)

### License Compliance Requirements
**All images MUST use commercial-friendly licenses:**
- ✅ CC BY, CC BY-SA, CC0, Public Domain
- ❌ CC BY-NC (non-commercial), CC BY-ND (no derivatives)

This is enforced because the mobile app may include monetization features.

## CDN URLs

Content is accessed via GitHub raw URLs:

**Base:** `https://raw.githubusercontent.com/jrowinski3d/mushroom-tracker-data-cdn/main/`

**Manifest:** `{base}/manifest.json`

**Species metadata:** `{base}/species/{mushroom_id}/metadata.json`

**Images:** `{base}/species/{mushroom_id}/thumb.webp` or `image_0.webp`

## Adding New Species

When adding species content:

1. Create directory: `species/{mushroom_id}/`
2. Add files: `metadata.json`, `thumb.webp`, `image_0.webp`, `image_1.webp`
3. Update `manifest.json` with new species entry
4. **Critical:** Verify all images have commercial-friendly licenses
5. **Critical:** Include complete photographer attribution in metadata
6. Update manifest `sha256` hash (this triggers app updates)
7. Commit and push to main branch

Note: There's a Python script referenced at `scripts/generate_cdn_content.py` (not in repo) that automates this process.

## Image Specifications

### Thumbnails
- Dimensions: 200×200 pixels (may vary aspect ratio)
- Format: WebP (quality=85)
- Purpose: Fast loading in list views

### Full Images
- Max dimensions: 640×640 pixels (maintains aspect ratio)
- Format: WebP (quality=85)
- Count: 2 per species
- Purpose: Detail views for identification

## Data Source

All content sourced from [Mushroom Observer](https://mushroomobserver.org), a collaborative community database with 370,110+ mushroom observation images. Attribution metadata preserves photographer credits and license compliance.

## Related Repository

Main mobile app: [mushroom-tracker](https://github.com/jasonstrowbridge/mushroom-tracker) (React Native)
