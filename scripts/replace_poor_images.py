#!/usr/bin/env python3
"""
Poor Image Replacer

Finds and replaces images scoring < 40 with better images from MO dataset cache.

Usage:
    python3 scripts/replace_poor_images.py [--dry-run]
"""

import argparse
import csv
import json
import hashlib
import requests
import time
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image
import tempfile
import shutil

from image_quality_scorer import ImageQualityScorer


class ImageReplacer:
    """Replaces poor quality images with better ones from MO cache."""

    WEBP_QUALITY = 85
    WEBP_METHOD = 6
    FULL_IMAGE_SIZE = (640, 640)  # Per spec
    THRESHOLD_SCORE = 40

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.scorer = ImageQualityScorer()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MushroomTracker-CDN/1.0 (Educational App)'
        })
        self.species_base = Path("species")
        self.cache_file = Path("scripts/mo_dataset_cache.csv")
        self.replaced_count = 0

    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def load_species_from_cache(self, scientific_name: str) -> List[Dict]:
        """Load all images for a species from MO cache."""
        print(f"  Loading images from cache for {scientific_name}...")

        records = []
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)  # Skip header

            for row in reader:
                if len(row) >= 5:
                    name = row[1]
                    if name == scientific_name:
                        records.append({
                            'image': row[0],
                            'name': row[1],
                            'created': row[2],
                            'license_url': row[3],
                            'photographer': row[4]
                        })

        print(f"  Found {len(records)} images in cache")
        return records

    def download_and_score_image(self, image_url: str) -> Optional[Dict]:
        """Download image and score it."""
        try:
            # Rate limiting
            time.sleep(1)

            # Download to temp file
            response = self.session.get(image_url, timeout=30)
            response.raise_for_status()

            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_file.write(response.content)
            temp_file.close()

            # Score image
            result = self.scorer.analyze_image(Path(temp_file.name))

            # Clean up
            Path(temp_file.name).unlink()

            if 'overall_score' in result:
                return {
                    'score': result['overall_score'],
                    'blur': result['metrics']['blur']['rating'],
                    'brightness': result['metrics']['brightness']['brightness_rating']
                }

        except Exception as e:
            print(f"    ✗ Error: {e}")

        return None

    def process_image(self, source_url: str, output_path: Path) -> Optional[Dict]:
        """Download and process image to WebP."""
        try:
            # Download
            response = self.session.get(source_url, timeout=30)
            response.raise_for_status()

            # Save temporary
            temp_path = output_path.parent / f"temp_{output_path.name}"
            with open(temp_path, 'wb') as f:
                f.write(response.content)

            # Process with PIL
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

                # Resize
                img.thumbnail(self.FULL_IMAGE_SIZE, Image.Resampling.LANCZOS)

                # Save as WebP
                img.save(output_path, 'WEBP', quality=self.WEBP_QUALITY, method=self.WEBP_METHOD)

                # Get dimensions
                width, height = img.size

            # Clean up temp
            temp_path.unlink()

            # Calculate hash and size
            sha256 = self.calculate_sha256(output_path)
            file_size = output_path.stat().st_size

            return {
                'width': width,
                'height': height,
                'file_size_bytes': file_size,
                'sha256': sha256
            }

        except Exception as e:
            print(f"    ✗ Error processing: {e}")
            return None

    def update_metadata(self, species_id: str, image_index: int, new_data: Dict, source_record: Dict) -> bool:
        """Update metadata.json with new image info."""
        metadata_path = self.species_base / species_id / "metadata.json"

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Update image data
            if image_index < len(metadata['images']):
                metadata['images'][image_index].update({
                    'source_url': source_record['image'],
                    'photographer': source_record['photographer'],
                    'license_url': source_record['license_url'],
                    'observation_date': source_record['created'],
                    'file_size_bytes': new_data['file_size_bytes'],
                    'width': new_data['width'],
                    'height': new_data['height'],
                    'sha256': new_data['sha256']
                })

                # Update last_updated
                from datetime import datetime
                metadata['last_updated'] = datetime.now().isoformat()

                # Save
                if not self.dry_run:
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)

                return True

        except Exception as e:
            print(f"    ✗ Error updating metadata: {e}")

        return False

    def find_and_replace_image(self, species_id: str, image_index: int, current_score: int) -> bool:
        """Find and replace a single poor quality image."""
        print(f"\n🔧 Replacing {species_id}/image_{image_index}.webp (score: {current_score})")

        # Load metadata to get scientific name
        metadata_path = self.species_base / species_id / "metadata.json"
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
                scientific_name = metadata['scientific_name']
        except:
            print(f"  ✗ Failed to load metadata")
            return False

        # Load candidates from cache
        records = self.load_species_from_cache(scientific_name)

        if not records:
            print(f"  ⚠️  No images found in cache")
            return False

        # Score candidates (limit to 10 to save time)
        print(f"  Scoring up to 10 candidate images...")
        scored_candidates = []

        for i, record in enumerate(records[:10], 1):
            print(f"    [{i}/10] {record['image'][:50]}...", end=" ")

            score_data = self.download_and_score_image(record['image'])
            if score_data:
                print(f"Score: {score_data['score']}")
                scored_candidates.append({
                    **record,
                    **score_data
                })
            else:
                print("Failed")

            # Don't hammer the server
            time.sleep(1)

        if not scored_candidates:
            print(f"  ✗ No candidates could be scored")
            return False

        # Find best candidate
        scored_candidates.sort(key=lambda x: x['score'], reverse=True)
        best = scored_candidates[0]

        print(f"\n  Best candidate: Score {best['score']} (was {current_score}, +{best['score'] - current_score})")
        print(f"  URL: {best['image'][:60]}...")
        print(f"  Photographer: {best['photographer']}")

        if best['score'] <= current_score:
            print(f"  ⚠️  Best candidate isn't better than current image, skipping")
            return False

        if self.dry_run:
            print(f"  🏃 [DRY RUN] Would replace with this image")
            return True

        # Backup current image
        image_path = self.species_base / species_id / f"image_{image_index}.webp"
        backup_path = image_path.with_suffix('.webp.backup')
        if image_path.exists():
            shutil.copy2(image_path, backup_path)

        # Download and process new image
        print(f"  Downloading and processing new image...")
        new_data = self.process_image(best['image'], image_path)

        if not new_data:
            # Restore backup
            if backup_path.exists():
                shutil.copy2(backup_path, image_path)
            return False

        print(f"  ✓ Processed: {new_data['width']}×{new_data['height']}, {new_data['file_size_bytes']:,} bytes")

        # Update metadata
        if self.update_metadata(species_id, image_index, new_data, best):
            print(f"  ✓ Updated metadata")

        # Remove backup
        if backup_path.exists():
            backup_path.unlink()

        self.replaced_count += 1
        return True

    def run(self):
        """Main execution."""
        print("=" * 70)
        print("POOR IMAGE REPLACER")
        print("=" * 70)
        if self.dry_run:
            print("🏃 DRY RUN MODE - No changes will be made")
        print()

        # Check cache exists
        if not self.cache_file.exists():
            print(f"✗ Cache file not found: {self.cache_file}")
            print(f"  Please ensure MO dataset cache is available")
            return

        # Find poor images
        print("Finding images scoring < 40...")
        poor_images = []

        for species_dir in sorted(self.species_base.iterdir()):
            if not species_dir.is_dir():
                continue

            species_id = species_dir.name

            for idx in range(2):
                img_path = species_dir / f"image_{idx}.webp"
                if not img_path.exists():
                    continue

                result = self.scorer.analyze_image(img_path)
                if 'overall_score' in result:
                    score = result['overall_score']
                    if score < self.THRESHOLD_SCORE:
                        poor_images.append({
                            'species_id': species_id,
                            'image_index': idx,
                            'score': score
                        })

        if not poor_images:
            print(f"✓ No images found scoring below {self.THRESHOLD_SCORE}")
            return

        print(f"\nFound {len(poor_images)} images needing replacement:\n")

        for img in poor_images:
            print(f"  • {img['species_id']}/image_{img['image_index']}.webp - Score: {img['score']}")

        if self.dry_run:
            print(f"\n🏃 DRY RUN - Would process these images")
            return

        print()
        response = input(f"Replace {len(poor_images)} images? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

        # Process each image
        print("\n" + "=" * 70)
        print("PROCESSING")
        print("=" * 70)

        for img in poor_images:
            self.find_and_replace_image(img['species_id'], img['image_index'], img['score'])

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"✓ Replaced {self.replaced_count}/{len(poor_images)} images")

        if self.replaced_count > 0:
            print(f"\n⚠️  Next steps:")
            print(f"  1. Run quality scorer to verify improvements")
            print(f"  2. Regenerate thumbnails for affected species")
            print(f"  3. Regenerate manifest.json")
            print(f"  4. Commit and push changes")

        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Replace poor quality images with better ones")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    replacer = ImageReplacer(dry_run=args.dry_run)
    replacer.run()


if __name__ == "__main__":
    main()
