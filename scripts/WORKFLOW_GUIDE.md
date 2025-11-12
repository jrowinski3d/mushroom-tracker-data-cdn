# Complete Workflow Guide: Finding and Replacing Poor Quality Images

This guide explains the complete workflow for identifying poor quality images and finding high-quality replacements from Mushroom Observer.

## Overview

The workflow consists of three main steps:

1. **Analyze Existing Images** - Score all images and identify problems
2. **Find Replacement Candidates** - Search Mushroom Observer for better images
3. **Replace Images** - Update CDN with new images using existing tools

## Scripts Available

### 1. Image Quality Analysis

**`image_quality_scorer.py`** - Analyzes all images in your CDN and generates quality reports

```bash
# Run quality analysis on all 455 images
python3 scripts/image_quality_scorer.py
```

**Output:**
- `scripts/image_quality_report.json` - Detailed JSON with all metrics
- `scripts/QUALITY_RECOMMENDATIONS.md` - Human-readable action plan
- Console summary with lowest-scoring images

**Quality Metrics:**
- Blur detection (Laplacian variance)
- Brightness/contrast analysis
- Color distribution
- White region detection (for plastic bags, paper, etc.)
- Overall score: 0-100 (higher is better)

### 2. Finding Replacement Images

**Your existing scripts handle this:**

The `generate_cdn_content.py` script already:
- Filters images by commercial-friendly licenses
- Downloads images from Mushroom Observer
- Processes them into WebP format
- Generates all metadata

### 3. Integration: Quality-Based Image Selection

Create a new enhanced version that integrates quality scoring into your existing workflow.

## Complete Workflow Example

### Step 1: Identify Problem Images

```bash
# Run quality analysis
python3 scripts/image_quality_scorer.py
```

Review `scripts/QUALITY_RECOMMENDATIONS.md` to see:
- 19 species with poor thumbnails (should use different image)
- 6 species that need entirely new images
- Top 20 lowest quality images

### Step 2: Find Your Source Data

Your existing `generate_cdn_content.py` expects:
- `scripts/mo_dataset_cache.csv` - Mushroom Observer dataset cache
- `scripts/species.txt` - List of species to process

The CSV should have these columns:
```
image, name, created, license_url, photographer
```

### Step 3: Enhance Your Workflow

Add quality scoring to `generate_cdn_content.py` by modifying the `curate_images()` method:

```python
def curate_images_with_quality(self, records: List[Dict], max_images: int = 2) -> List[Dict]:
    """Select best images using quality scores"""
    from image_quality_scorer import ImageQualityScorer
    import tempfile

    scorer = ImageQualityScorer()
    scored_records = []

    for record in records[:max_images * 3]:  # Check 3x to account for poor quality
        # Download temp image
        temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
        response = self.session.get(record['image'], timeout=30)
        temp_file.write(response.content)
        temp_file.close()

        # Score image
        result = scorer.analyze_image(Path(temp_file.name))
        if 'overall_score' in result:
            record['quality_score'] = result['overall_score']
            scored_records.append(record)

        Path(temp_file.name).unlink()

    # Sort by quality, take best images
    scored_records.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
    return scored_records[:max_images]
```

### Step 4: For Quick Fixes (Thumbnail Swaps)

For the 19 species where a different existing image would be better as thumbnail:

```bash
# Example for agaaug (thumb: 73, image_1: 97)
cp species/agaaug/image_1.webp species/agaaug/thumb.webp

# Resize to 200x200
python3 << EOF
from PIL import Image
img = Image.open('species/agaaug/thumb.webp')
img.thumbnail((200, 200), Image.Resampling.LANCZOS)
img.save('species/agaaug/thumb.webp', 'WEBP', quality=85)
EOF
```

Then regenerate manifest with updated SHA-256 hashes.

## Recommended Priority

### Urgent (Score < 40)
1. **phosqu** - thumb: 31 (too bright)
2. **exigla** - All images poor quality (avg: 42)
3. **pleost** - image_0: 36 (very blurry)

### High Priority (Significant thumbnail issues, +20 points available)
4. **trefuc** - +32 point improvement available
5. **cancal** - +25 point improvement available
6. **cantex** - +25 point improvement available
7. **agaaug** - +24 point improvement available (plastic bag in thumb)
8. **morsny** - +20 point improvement available

### Medium Priority (All images poor)
9. **ruscla** - avg: 44.3
10. **calvis** - avg: 49.7
11. **canapp** - avg: 49.7

## Automated Batch Processing

For processing multiple species with new images from Mushroom Observer:

1. Update `scripts/species.txt` with species needing new images:
```
Exidia glandulosa
Russula claroflava
Clavariadelphus pistillaris
```

2. Update your `mo_dataset_cache.csv` with fresh data from Mushroom Observer

3. Run the enhanced generator:
```bash
python3 scripts/generate_cdn_content.py --species-file scripts/problem_species.txt
```

## Quality Score Interpretation

- **80-100 (Excellent)**: 332 images (73%) - No action needed
- **60-79 (Good)**: 92 images (20%) - Consider improvement
- **40-59 (Fair)**: 27 images (6%) - Should replace
- **0-39 (Poor)**: 4 images (1%) - Must replace urgently

## Tips for Best Results

1. **License Verification**: Always verify commercial-friendly licenses:
   - ✅ CC BY, CC BY-SA, CC0, Public Domain
   - ❌ CC BY-NC, CC BY-ND

2. **Image Quality Checks**:
   - Laplacian variance > 200 (good sharpness)
   - Brightness 40-215 (well-lit)
   - Contrast > 30 (good dynamic range)
   - White pixel ratio < 0.25 (no plastic bags)

3. **Manual Review**: Always manually review top-scored images before committing

4. **Manifest Updates**: After any image changes:
   - Update SHA-256 hashes for changed files
   - Update manifest's overall SHA-256 (triggers app updates)
   - Verify file sizes are accurate

## Next Steps

After running quality analysis, you now have:
- ✅ Complete quality report for all 455 images
- ✅ Prioritized list of 19 species with thumbnail issues
- ✅ List of 6 species needing entirely new images
- ✅ Existing tools to download and process new images

**Recommended Action**: Start with the quick wins (thumbnail swaps) for the 19 species, then source new images for the 6 species with consistently poor quality.
