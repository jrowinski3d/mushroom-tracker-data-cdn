#!/usr/bin/env python3
"""
Artifact Image Replacer

Replaces images with severe artifacts (plastic bags, rulers, etc.) with clean images.

Usage:
    python3 scripts/replace_artifact_images.py [--dry-run] [--min-artifact-score 50]
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
from artifact_detector import ArtifactDetector


class ArtifactImageReplacer:
    """Replaces artifact-heavy images with clean ones from MO cache."""

    WEBP_QUALITY = 85
    WEBP_METHOD = 6
    FULL_IMAGE_SIZE = (640, 640)
    THUMBNAIL_SIZE = (200, 200)

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.scorer = ImageQualityScorer()
        self.detector = ArtifactDetector()
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
        records = []
        with open(self.cache_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)

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

        return records

    def download_and_evaluate_image(self, image_url: str) -> Optional[Dict]:
        """Download image, score quality AND artifact level."""
        try:
            time.sleep(1)

            response = self.session.get(image_url, timeout=30)
            response.raise_for_status()

            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_file.write(response.content)
            temp_file.close()
            temp_path = Path(temp_file.name)

            # Score both quality and artifacts
            quality_result = self.scorer.analyze_image(temp_path)
            artifact_result = self.detector.detect_artifacts(temp_path)

            temp_path.unlink()

            if 'overall_score' in quality_result and 'artifact_score' in artifact_result:
                return {
                    'quality_score': quality_result['overall_score'],
                    'artifact_score': artifact_result['artifact_score'],
                    'blur': quality_result['metrics']['blur']['rating'],
                    'flags': artifact_result.get('flags', [])
                }

        except Exception as e:
            pass

        return None

    def process_image(self, source_url: str, output_path: Path, is_thumbnail: bool = False) -> Optional[Dict]:
        """Download and process image to WebP."""
        try:
            response = self.session.get(source_url, timeout=30)
            response.raise_for_status()

            temp_path = output_path.parent / f"temp_{output_path.name}"
            with open(temp_path, 'wb') as f:
                f.write(response.content)

            with Image.open(temp_path) as img:
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        rgb_img.paste(img, mask=img.split()[-1])
                    else:
                        rgb_img.paste(img)
                    img = rgb_img

                size = self.THUMBNAIL_SIZE if is_thumbnail else self.FULL_IMAGE_SIZE
                img.thumbnail(size, Image.Resampling.LANCZOS)
                img.save(output_path, 'WEBP', quality=self.WEBP_QUALITY, method=self.WEBP_METHOD)

                width, height = img.size

            temp_path.unlink()

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

                from datetime import datetime
                metadata['last_updated'] = datetime.now().isoformat()

                if not self.dry_run:
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)

                return True

        except Exception as e:
            print(f"    ✗ Error updating metadata: {e}")

        return False

    def find_and_replace_image(self, species_id: str, image_index: int,
                               current_artifact_score: int, current_quality: int) -> bool:
        """Find and replace an artifact-heavy image."""
        print(f"\n🔧 Replacing {species_id}/image_{image_index}.webp")
        print(f"   Current: artifact={current_artifact_score}, quality={current_quality}")

        metadata_path = self.species_base / species_id / "metadata.json"
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
                scientific_name = metadata['scientific_name']
        except:
            print(f"  ✗ Failed to load metadata")
            return False

        records = self.load_species_from_cache(scientific_name)

        if not records:
            print(f"  ⚠️  No images found in cache")
            return False

        print(f"  Found {len(records)} candidates in cache")
        print(f"  Evaluating up to 15 candidates for quality AND artifacts...")

        scored_candidates = []

        for i, record in enumerate(records[:15], 1):
            print(f"    [{i:2d}/15] Checking...", end=" ", flush=True)

            result = self.download_and_evaluate_image(record['image'])
            if result:
                # Combined score: prioritize low artifacts, then high quality
                combined_score = (100 - result['artifact_score']) + result['quality_score']

                print(f"Q:{result['quality_score']:2d} A:{result['artifact_score']:2d} Combined:{combined_score:3d}")

                scored_candidates.append({
                    **record,
                    **result,
                    'combined_score': combined_score
                })
            else:
                print("Failed")

            time.sleep(0.5)

        if not scored_candidates:
            print(f"  ✗ No candidates could be evaluated")
            return False

        # Sort by combined score (low artifacts + high quality)
        scored_candidates.sort(key=lambda x: x['combined_score'], reverse=True)
        best = scored_candidates[0]

        improvement_artifact = current_artifact_score - best['artifact_score']
        improvement_quality = best['quality_score'] - current_quality

        print(f"\n  Best candidate:")
        print(f"    Quality: {best['quality_score']} (was {current_quality}, {improvement_quality:+d})")
        print(f"    Artifacts: {best['artifact_score']} (was {current_artifact_score}, {improvement_artifact:+d})")
        print(f"    Combined score: {best['combined_score']}")
        print(f"    Photographer: {best['photographer']}")

        if best.get('flags'):
            print(f"    Flags: {', '.join(best['flags'][:2])}")

        # Only replace if significantly better
        if best['artifact_score'] >= current_artifact_score - 10:
            print(f"  ⚠️  Not significantly better, skipping")
            return False

        if self.dry_run:
            print(f"  🏃 [DRY RUN] Would replace with this image")
            return True

        # Backup and replace
        image_path = self.species_base / species_id / f"image_{image_index}.webp"
        backup_path = image_path.with_suffix('.webp.backup')
        if image_path.exists():
            shutil.copy2(image_path, backup_path)

        print(f"  Downloading and processing new image...")
        new_data = self.process_image(best['image'], image_path)

        if not new_data:
            if backup_path.exists():
                shutil.copy2(backup_path, image_path)
            return False

        print(f"  ✓ Processed: {new_data['width']}×{new_data['height']}, {new_data['file_size_bytes']:,} bytes")

        if self.update_metadata(species_id, image_index, new_data, best):
            print(f"  ✓ Updated metadata")

        if backup_path.exists():
            backup_path.unlink()

        self.replaced_count += 1
        return True

    def run(self, min_artifact_score: int = 50):
        """Main execution."""
        print("=" * 70)
        print("ARTIFACT IMAGE REPLACER")
        print("=" * 70)
        if self.dry_run:
            print("🏃 DRY RUN MODE - No changes will be made")
        print()

        if not self.cache_file.exists():
            print(f"✗ Cache file not found: {self.cache_file}")
            return

        # Load artifact report
        artifact_report = Path("scripts/artifact_report.json")
        if not artifact_report.exists():
            print("✗ Artifact report not found. Run artifact_detector.py first.")
            return

        with open(artifact_report) as f:
            all_artifacts = json.load(f)

        # Filter for severe cases, excluding thumbnails
        severe_artifacts = [
            a for a in all_artifacts
            if a['artifact_score'] >= min_artifact_score and a['image_type'] != 'thumb'
        ]

        if not severe_artifacts:
            print(f"✓ No images found with artifact score >= {min_artifact_score}")
            return

        print(f"Found {len(severe_artifacts)} images with severe artifacts (score >= {min_artifact_score}):\n")

        for item in sorted(severe_artifacts, key=lambda x: x['artifact_score'], reverse=True):
            print(f"  • {item['species_id']}/{item['image_type']} - "
                  f"Artifact: {item['artifact_score']}, Quality: {item['quality_score']}")

        if self.dry_run:
            print(f"\n🏃 DRY RUN - Would process these images")
            return

        print()
        response = input(f"Replace {len(severe_artifacts)} images? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

        # Process each image
        print("\n" + "=" * 70)
        print("PROCESSING")
        print("=" * 70)

        for item in sorted(severe_artifacts, key=lambda x: x['artifact_score'], reverse=True):
            species_id = item['species_id']
            image_type = item['image_type']
            image_index = int(image_type.split('_')[1]) if '_' in image_type else 0

            self.find_and_replace_image(
                species_id,
                image_index,
                item['artifact_score'],
                item['quality_score']
            )

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"✓ Replaced {self.replaced_count}/{len(severe_artifacts)} images")

        if self.replaced_count > 0:
            print(f"\n⚠️  Next steps:")
            print(f"  1. Regenerate thumbnails for affected species")
            print(f"  2. Run quality scorer to verify improvements")
            print(f"  3. Run artifact detector to verify artifact reduction")
            print(f"  4. Regenerate manifest.json")
            print(f"  5. Commit and push changes")

        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Replace artifact-heavy images")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes")
    parser.add_argument("--min-artifact-score", type=int, default=50,
                       help="Minimum artifact score to replace (default: 50)")
    args = parser.parse_args()

    replacer = ArtifactImageReplacer(dry_run=args.dry_run)
    replacer.run(min_artifact_score=args.min_artifact_score)


if __name__ == "__main__":
    main()
