#!/usr/bin/env python3
"""
CDN Content Generator for Mushroom Tracker
Generates WebP images, thumbnails, and metadata for GitHub CDN hosting.

Usage:
    python3 generate_cdn_content.py [--dry-run] [--output-dir OUTPUT_DIR]
"""

import os
import sys
import json
import csv
import hashlib
import argparse
import requests
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

try:
    from PIL import Image, ImageEnhance
except ImportError:
    print("❌ Pillow not installed. Install with: pip install Pillow")
    sys.exit(1)

# Configuration
SCRIPT_DIR = Path(__file__).parent
CACHE_FILE = SCRIPT_DIR / "mo_dataset_cache.csv"
SPECIES_LIST_FILE = SCRIPT_DIR / "species.txt"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR.parent.parent / "mushroom-tracker-data-cdn"

# Image settings for CDN (per spec)
THUMBNAIL_SIZE = (200, 200)
FULL_IMAGE_SIZE = (800, 800)  # Changed from 1200x1200 to match spec
WEBP_QUALITY = 85
WEBP_METHOD = 6  # 0-6, higher = better compression but slower

def load_species_list(filepath: Path = SPECIES_LIST_FILE) -> List[str]:
    """Load species list from species.txt file"""
    species = []
    if not filepath.exists():
        print(f"⚠️  Species list file not found: {filepath}")
        print(f"⚠️  Using default MVP species list")
        return [
            "Morchella esculenta",
            "Morchella americana",
            "Cantharellus formosus",
            "Armillaria mellea",
            "Tricholoma matsutake",
            "Laetiporus gilbertsonii",
            "Grifola frondosa",
            "Calvatia gigantea",
            "Craterellus cornucopioides",
            "Sparassis crispa"
        ]

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                species.append(line)

    return species

# Load species from species.txt file
MVP_SPECIES = load_species_list()

# Common names mapping
COMMON_NAMES = {
    "Morchella esculenta": "Common Morel",
    "Morchella americana": "American Morel",
    "Cantharellus formosus": "Pacific Golden Chanterelle",
    "Armillaria mellea": "Honey Mushroom",
    "Tricholoma matsutake": "Matsutake",
    "Laetiporus gilbertsonii": "Western Chicken of the Woods",
    "Grifola frondosa": "Maitake",
    "Calvatia gigantea": "Giant Puffball",
    "Craterellus cornucopioides": "Black Trumpet",
    "Sparassis crispa": "Cauliflower Mushroom"
}

# Commercial-friendly licenses ONLY
ACCEPTABLE_LICENSES = [
    'creativecommons.org/licenses/by/',
    'creativecommons.org/licenses/by-sa/',
    'creativecommons.org/licenses/by/3.0',
    'creativecommons.org/licenses/by/4.0',
    'creativecommons.org/licenses/by-sa/3.0',
    'creativecommons.org/licenses/by-sa/4.0',
    'creativecommons.org/publicdomain/',
    'public domain',
    'cc-by',
    'cc0'
]

# Patterns to exclude (non-mushroom images)
EXCLUDED_PATTERNS = [
    'note', 'notes', 'habitat', 'context', 'landscape',
    'environment', 'field', 'clipboard', 'paper', 'ruler', 'scale'
]

@dataclass
class CDNImage:
    """Represents a processed CDN image"""
    index: int
    source_url: str
    photographer: str
    license_url: str
    observation_date: str
    file_size_bytes: int
    width: int
    height: int
    sha256: str

@dataclass
class CDNSpecies:
    """Represents a species entry for CDN"""
    mushroom_id: str
    scientific_name: str
    common_name: str
    edibility: str
    description: str
    habitat: str
    season: str
    regions: List[str]
    lookalikes: List[str]
    thumbnail: Optional[CDNImage]  # Thumbnail metadata
    images: List[CDNImage]
    total_size_bytes: int

class CDNContentGenerator:
    """Generates CDN content from Mushroom Observer dataset"""

    def __init__(self, output_dir: Path, dry_run: bool = False):
        self.output_dir = Path(output_dir)
        self.dry_run = dry_run
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MushroomTracker-CDN/1.0 (Educational App)'
        })

        print(f"🍄 CDN Content Generator")
        print(f"📁 Output directory: {self.output_dir}")
        print(f"{'🏃 DRY RUN MODE' if dry_run else '✅ Live mode'}\n")

        if not dry_run:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "species").mkdir(exist_ok=True)

    def generate_mushroom_id(self, scientific_name: str) -> str:
        """Generate short ID from scientific name"""
        parts = scientific_name.split()
        if len(parts) >= 2:
            return f"{parts[0][:3]}{parts[1][:3]}".lower()
        return scientific_name[:6].lower()

    def validate_license(self, license_url: str) -> bool:
        """Check if license is commercial-friendly"""
        if not license_url:
            return False

        license_url = license_url.lower()

        # Exclude BY-NC explicitly
        if 'by-nc' in license_url or 'noncommercial' in license_url:
            return False

        # Check if matches acceptable patterns
        return any(pattern in license_url for pattern in ACCEPTABLE_LICENSES)

    def is_valid_mushroom_image(self, image_url: str) -> bool:
        """Check if filename suggests it's a mushroom photo (not habitat/notes)"""
        url_lower = image_url.lower()
        return not any(pattern in url_lower for pattern in EXCLUDED_PATTERNS)

    def load_dataset(self) -> List[Dict]:
        """Load Mushroom Observer dataset from cache"""
        print(f"📊 Loading dataset from {CACHE_FILE}...")

        if not CACHE_FILE.exists():
            print(f"❌ Cache file not found: {CACHE_FILE}")
            sys.exit(1)

        # Handle duplicate 'license' column headers
        dataset = []
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Get headers

            # CSV has: image, name, created, license (URL), license (photographer)
            # We need to rename the duplicate columns
            for row in reader:
                if len(row) >= 5:
                    record = {
                        'image': row[0],
                        'name': row[1],
                        'created': row[2],
                        'license_url': row[3],        # First license = URL
                        'photographer': row[4]  # Second license = photographer
                    }
                    dataset.append(record)

        print(f"✅ Loaded {len(dataset)} records\n")
        return dataset

    def filter_species_records(self, dataset: List[Dict]) -> Dict[str, List[Dict]]:
        """Filter dataset for MVP species with commercial licenses"""
        print("🎯 Filtering for MVP species with commercial licenses...")

        species_records = {}
        license_stats = {
            'total': 0,
            'commercial_ok': 0,
            'non_commercial': 0,
            'no_license': 0,
            'invalid_image': 0
        }

        for record in dataset:
            species_name = record.get('name', '').strip()

            # Check if this is one of our MVP species
            if species_name not in MVP_SPECIES:
                continue

            license_stats['total'] += 1

            # Check license
            license_url = record.get('license_url', '')
            if not license_url:
                license_stats['no_license'] += 1
                continue

            if not self.validate_license(license_url):
                license_stats['non_commercial'] += 1
                continue

            # Check if image URL looks valid
            image_url = record.get('image', '')
            if not image_url:
                license_stats['invalid_image'] += 1
                continue

            if not self.is_valid_mushroom_image(image_url):
                license_stats['invalid_image'] += 1
                continue

            license_stats['commercial_ok'] += 1

            # Add to species records
            if species_name not in species_records:
                species_records[species_name] = []
            species_records[species_name].append(record)

        print(f"📊 License filtering stats:")
        print(f"  Total records for MVP species: {license_stats['total']}")
        print(f"  ✅ Commercial-friendly: {license_stats['commercial_ok']}")
        print(f"  ❌ Non-commercial (excluded): {license_stats['non_commercial']}")
        print(f"  ⚠️  No license info: {license_stats['no_license']}")
        print(f"  ⚠️  Invalid/excluded images: {license_stats['invalid_image']}\n")

        print(f"🎯 Found commercial-friendly images for {len(species_records)} species:")
        for species, records in sorted(species_records.items()):
            print(f"  📋 {species}: {len(records)} images")
        print()

        return species_records

    def curate_images(self, records: List[Dict], max_images: int = 2) -> List[Dict]:
        """Select best images from available records"""
        # Sort by date (newest first)
        sorted_records = sorted(
            records,
            key=lambda x: x.get('created', ''),
            reverse=True
        )

        # Take the most recent max_images
        return sorted_records[:max_images]

    def download_and_process_image(
        self,
        image_url: str,
        species_dir: Path,
        index: int
    ) -> Optional[Tuple[Path, Path, dict]]:
        """Download image and create WebP thumbnail + full image"""

        if self.dry_run:
            print(f"  🏃 [DRY RUN] Would download and process: {image_url}")
            return None

        try:
            # Download original image
            print(f"  🔽 Downloading image {index}...")
            response = self.session.get(image_url, timeout=30, stream=True)
            response.raise_for_status()

            # Save temporary file
            temp_path = species_dir / f"temp_{index}.jpg"
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Open and process image
            with Image.open(temp_path) as img:
                # Convert to RGB
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        rgb_img.paste(img, mask=img.split()[-1])
                    else:
                        rgb_img.paste(img)
                    img = rgb_img

                # Generate thumbnail (200x200) - ONLY for first image (index 0)
                thumb_path = None
                thumb_size = 0
                thumb_width = 0
                thumb_height = 0
                thumb_sha256 = None

                if index == 0:
                    thumb_img = img.copy()
                    thumb_img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                    thumb_path = species_dir / "thumb.webp"
                    thumb_img.save(thumb_path, 'WEBP', quality=WEBP_QUALITY, method=WEBP_METHOD)
                    thumb_size = thumb_path.stat().st_size
                    thumb_width, thumb_height = thumb_img.size

                # Generate full image (800x800)
                full_img = img.copy()
                full_img.thumbnail(FULL_IMAGE_SIZE, Image.Resampling.LANCZOS)
                full_path = species_dir / f"image_{index}.webp"
                full_img.save(full_path, 'WEBP', quality=WEBP_QUALITY, method=WEBP_METHOD)

                # Calculate metrics
                full_size = full_path.stat().st_size
                width, height = full_img.size

            # Clean up temp file
            temp_path.unlink()

            # Calculate SHA-256 for full image
            with open(full_path, 'rb') as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()

            # Calculate thumbnail SHA-256 (only if thumbnail was created)
            if index == 0 and thumb_path:
                with open(thumb_path, 'rb') as f:
                    thumb_sha256 = hashlib.sha256(f.read()).hexdigest()

            print(f"  ✅ Processed image {index}: {full_size} bytes ({width}x{height})")

            return (thumb_path, full_path, {
                'thumb_size': thumb_size,
                'thumb_width': thumb_width,
                'thumb_height': thumb_height,
                'thumb_sha256': thumb_sha256,
                'full_size': full_size,
                'width': width,
                'height': height,
                'sha256': sha256
            })

        except Exception as e:
            print(f"  ❌ Failed to process image {index}: {e}")
            return None

    def generate_species_metadata(
        self,
        species_name: str,
        mushroom_id: str,
        images: List[CDNImage]
    ) -> dict:
        """Generate metadata.json for a species"""

        common_name = COMMON_NAMES.get(species_name, species_name)

        # Generate basic content (would be enhanced with actual data in production)
        metadata = {
            "mushroom_id": mushroom_id,
            "scientific_name": species_name,
            "common_name": common_name,
            "edibility": "E",  # All MVP species are edible
            "description": f"{common_name} ({species_name}) is a prized edible mushroom. Proper identification is essential before consumption.",
            "habitat": "Various forest environments. Specific habitat depends on the species and region.",
            "season": "Seasonal availability varies by location and species.",
            "regions": ["North America"],
            "lookalikes": ["Various species - expert identification recommended"],
            "safety_notes": "Always verify identification with multiple sources before consuming wild mushrooms.",
            "images": [asdict(img) for img in images],
            "content_version": "1.0",
            "last_updated": datetime.now().isoformat()
        }

        return metadata

    def process_species(
        self,
        species_name: str,
        records: List[Dict]
    ) -> Optional[CDNSpecies]:
        """Process a single species: download images, generate metadata"""

        print(f"\n🍄 Processing: {species_name}")
        print(f"  Available images: {len(records)}")

        mushroom_id = self.generate_mushroom_id(species_name)
        common_name = COMMON_NAMES.get(species_name, species_name)
        species_dir = self.output_dir / "species" / mushroom_id

        if not self.dry_run:
            species_dir.mkdir(parents=True, exist_ok=True)

        # Curate best images (max 2)
        selected_records = self.curate_images(records, max_images=2)
        print(f"  Selected {len(selected_records)} images for processing")

        # Process images
        processed_images = []
        thumbnail_image = None
        total_size = 0

        for idx, record in enumerate(selected_records):
            image_url = record.get('image', '')
            result = self.download_and_process_image(image_url, species_dir, idx)

            if result:
                thumb_path, full_path, metrics = result

                # Create thumbnail CDNImage (only for first image)
                if idx == 0:
                    thumbnail_image = CDNImage(
                        index=-1,  # Special index for thumbnail
                        source_url=image_url,
                        photographer=record.get('photographer', 'Unknown'),
                        license_url=record.get('license_url', ''),
                        observation_date=record.get('created', ''),
                        file_size_bytes=metrics['thumb_size'],
                        width=metrics['thumb_width'],
                        height=metrics['thumb_height'],
                        sha256=metrics['thumb_sha256']
                    )

                # Create full image CDNImage
                cdn_image = CDNImage(
                    index=idx,
                    source_url=image_url,
                    photographer=record.get('photographer', 'Unknown'),
                    license_url=record.get('license_url', ''),
                    observation_date=record.get('created', ''),
                    file_size_bytes=metrics['full_size'],
                    width=metrics['width'],
                    height=metrics['height'],
                    sha256=metrics['sha256']
                )

                processed_images.append(cdn_image)
                total_size += metrics['thumb_size'] + metrics['full_size']

        if not processed_images or not thumbnail_image:
            print(f"  ❌ No images successfully processed for {species_name}")
            return None

        # Generate metadata.json
        metadata = self.generate_species_metadata(species_name, mushroom_id, processed_images)

        if not self.dry_run:
            metadata_path = species_dir / "metadata.json"
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            print(f"  ✅ Generated metadata.json")

        print(f"  ✅ Total size: {total_size:,} bytes ({total_size/1024:.1f} KB)")

        return CDNSpecies(
            mushroom_id=mushroom_id,
            scientific_name=species_name,
            common_name=common_name,
            edibility="E",
            description=metadata['description'],
            habitat=metadata['habitat'],
            season=metadata['season'],
            regions=metadata['regions'],
            lookalikes=metadata['lookalikes'],
            thumbnail=thumbnail_image,
            images=processed_images,
            total_size_bytes=total_size
        )

    def generate_manifest(self, species_list: List[CDNSpecies]) -> dict:
        """Generate manifest.json with all species"""

        # GitHub CDN base URL
        BASE_URL = "https://raw.githubusercontent.com/jrowinski3d/mushroom-tracker-data-cdn/main/"

        manifest = {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "total_species": len(species_list),
            "total_size_bytes": sum(s.total_size_bytes for s in species_list),
            "species": []
        }

        for species in species_list:
            # Convert edibility code to full word
            edibility_map = {"E": "edible", "P": "poisonous", "T": "toxic", "U": "unknown", "I": "inedible"}
            edibility_full = edibility_map.get(species.edibility, "unknown")

            # All MVP species are choice edible
            safety_level = "choice_edible"

            # Calculate content SHA for this species (hash of metadata)
            species_content = f"{species.mushroom_id}{species.scientific_name}{species.common_name}"
            content_sha = hashlib.sha256(species_content.encode()).hexdigest()

            # Build thumbnail CDNImage object
            thumbnail_obj = {
                "filename": "thumb.webp",
                "url": f"{BASE_URL}species/{species.mushroom_id}/thumb.webp",
                "size_bytes": species.thumbnail.file_size_bytes,
                "width": species.thumbnail.width,
                "height": species.thumbnail.height
            }

            # Build images array with CDNImage objects
            images_array = []
            for img in species.images:
                images_array.append({
                    "filename": f"image_{img.index}.webp",
                    "url": f"{BASE_URL}species/{species.mushroom_id}/image_{img.index}.webp",
                    "size_bytes": img.file_size_bytes,
                    "width": img.width,
                    "height": img.height
                })

            manifest["species"].append({
                "mushroom_id": species.mushroom_id,
                "scientific_name": species.scientific_name,
                "common_name": species.common_name,
                "edibility": edibility_full,
                "safety_level": safety_level,
                "image_count": len(species.images),
                "total_size_bytes": species.total_size_bytes,
                "thumbnail": thumbnail_obj,
                "images": images_array,
                "metadata_url": f"{BASE_URL}species/{species.mushroom_id}/metadata.json",
                "content_sha": content_sha
            })

        # Calculate SHA-256 of manifest content (excluding the sha256 field itself)
        manifest_str = json.dumps(manifest, sort_keys=True)
        manifest_sha = hashlib.sha256(manifest_str.encode()).hexdigest()
        manifest["sha256"] = manifest_sha

        return manifest

    def run(self):
        """Main execution flow"""

        # Load dataset
        dataset = self.load_dataset()

        # Filter for MVP species with commercial licenses
        species_records = self.filter_species_records(dataset)

        if not species_records:
            print("❌ No species found with commercial-friendly licenses!")
            sys.exit(1)

        # Process each species
        processed_species = []
        for species_name in MVP_SPECIES:
            if species_name in species_records:
                result = self.process_species(species_name, species_records[species_name])
                if result:
                    processed_species.append(result)
            else:
                print(f"\n⚠️  No commercial images found for: {species_name}")

        if not processed_species:
            print("\n❌ No species successfully processed!")
            sys.exit(1)

        # Generate manifest.json
        print(f"\n📋 Generating manifest.json...")
        manifest = self.generate_manifest(processed_species)

        if not self.dry_run:
            manifest_path = self.output_dir / "manifest.json"
            with open(manifest_path, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
            print(f"✅ Manifest generated: {manifest_path}")

        # Summary
        print(f"\n{'='*60}")
        print(f"🎉 CDN Content Generation {'Summary (DRY RUN)' if self.dry_run else 'Complete!'}")
        print(f"{'='*60}")
        print(f"📊 Species processed: {len(processed_species)}/{len(MVP_SPECIES)}")
        print(f"🖼️  Total images: {sum(len(s.images) for s in processed_species)}")
        print(f"💾 Total size: {manifest['total_size_bytes']:,} bytes ({manifest['total_size_bytes']/1024/1024:.2f} MB)")
        print(f"📁 Output directory: {self.output_dir}")

        if not self.dry_run:
            print(f"\n✅ Next steps:")
            print(f"  1. Review generated content in: {self.output_dir}")
            print(f"  2. Create GitHub repository: mushroom-data-cdn")
            print(f"  3. Push content to repository")
            print(f"  4. Verify raw URLs are accessible")

        print(f"{'='*60}\n")

def main():
    parser = argparse.ArgumentParser(description='Generate CDN content for Mushroom Tracker')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without creating files')
    parser.add_argument('--output-dir', type=str, default=str(DEFAULT_OUTPUT_DIR),
                       help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})')

    args = parser.parse_args()

    generator = CDNContentGenerator(
        output_dir=Path(args.output_dir),
        dry_run=args.dry_run
    )

    generator.run()

if __name__ == '__main__':
    main()
