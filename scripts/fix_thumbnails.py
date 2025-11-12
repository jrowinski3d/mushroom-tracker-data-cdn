#!/usr/bin/env python3
"""
Thumbnail Fixer

Automatically fixes thumbnails by using the highest-quality existing image.
This script processes species where a better image is available to use as thumbnail.

Usage:
    python3 scripts/fix_thumbnails.py [--dry-run]
"""

import argparse
import json
import hashlib
import shutil
from pathlib import Path
from typing import Dict, List
from PIL import Image

from image_quality_scorer import ImageQualityScorer


class ThumbnailFixer:
    """Fixes thumbnails by selecting best quality existing image."""

    THUMBNAIL_SIZE = (200, 200)
    WEBP_QUALITY = 85
    WEBP_METHOD = 6

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.scorer = ImageQualityScorer()
        self.fixed_count = 0
        self.species_base = Path("species")

    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def score_species_images(self, species_id: str) -> Dict:
        """Score all images for a species and return results."""
        species_dir = self.species_base / species_id

        if not species_dir.exists():
            return {}

        results = {}
        for img_file in ["thumb.webp", "image_0.webp", "image_1.webp"]:
            img_path = species_dir / img_file
            if img_path.exists():
                result = self.scorer.analyze_image(img_path)
                if "overall_score" in result:
                    results[img_file] = {
                        "score": result["overall_score"],
                        "path": img_path,
                        "blur_rating": result["metrics"]["blur"]["rating"],
                        "brightness_rating": result["metrics"]["brightness"]["brightness_rating"]
                    }

        return results

    def find_best_image(self, species_id: str) -> Dict:
        """Find the best quality image for a species."""
        scores = self.score_species_images(species_id)

        if not scores:
            return {}

        # Find best image (excluding current thumb)
        best_score = 0
        best_image = None
        thumb_score = scores.get("thumb.webp", {}).get("score", 0)

        for img_name, data in scores.items():
            if img_name != "thumb.webp" and data["score"] > best_score:
                best_score = data["score"]
                best_image = img_name

        if not best_image:
            return {}

        improvement = best_score - thumb_score

        return {
            "species_id": species_id,
            "current_thumb_score": thumb_score,
            "best_image": best_image,
            "best_score": best_score,
            "improvement": improvement,
            "best_image_path": scores[best_image]["path"]
        }

    def create_thumbnail(self, source_path: Path, output_path: Path) -> Dict:
        """Create thumbnail from source image."""
        try:
            with Image.open(source_path) as img:
                # Convert to RGB if needed
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    if img.mode in ('RGBA', 'LA'):
                        rgb_img.paste(img, mask=img.split()[-1])
                    else:
                        rgb_img.paste(img)
                    img = rgb_img

                # Create thumbnail
                img.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
                img.save(output_path, 'WEBP', quality=self.WEBP_QUALITY, method=self.WEBP_METHOD)

                return {
                    "width": img.size[0],
                    "height": img.size[1],
                    "file_size_bytes": output_path.stat().st_size,
                    "sha256": self.calculate_sha256(output_path)
                }

        except Exception as e:
            print(f"  ✗ Error creating thumbnail: {e}")
            return {}

    def update_metadata(self, species_id: str, source_image: str, thumb_data: Dict) -> bool:
        """Update metadata.json with new thumbnail information."""
        metadata_path = self.species_base / species_id / "metadata.json"

        if not metadata_path.exists():
            print(f"  ⚠️  metadata.json not found")
            return False

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Find source image index
            source_index = int(source_image.split('_')[1].split('.')[0])

            # Get source image data
            if "images" not in metadata or source_index >= len(metadata["images"]):
                print(f"  ⚠️  Source image data not found in metadata")
                return False

            source_img_data = metadata["images"][source_index]

            # Note: We keep the same photographer/license as the source image
            # since the thumbnail is derived from that image

            # Update last_updated timestamp
            from datetime import datetime
            metadata["last_updated"] = datetime.now().isoformat()

            # Save updated metadata
            if not self.dry_run:
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

            return True

        except Exception as e:
            print(f"  ✗ Error updating metadata: {e}")
            return False

    def fix_thumbnail(self, species_id: str) -> bool:
        """Fix thumbnail for a single species."""
        print(f"\n🔧 Processing {species_id}...")

        # Find best image
        best = self.find_best_image(species_id)

        if not best:
            print(f"  ⚠️  No better image found")
            return False

        improvement = best["improvement"]

        # Only fix if improvement is significant (>10 points)
        if improvement < 10:
            print(f"  ℹ️  Improvement too small ({improvement:.0f} points), skipping")
            return False

        print(f"  Current thumb score: {best['current_thumb_score']}")
        print(f"  Best image: {best['best_image']} (score: {best['best_score']})")
        print(f"  Improvement: +{improvement:.0f} points")

        if self.dry_run:
            print(f"  🏃 [DRY RUN] Would replace thumbnail with {best['best_image']}")
            return True

        # Create backup
        species_dir = self.species_base / species_id
        thumb_path = species_dir / "thumb.webp"
        backup_path = species_dir / "thumb.webp.backup"

        if thumb_path.exists():
            shutil.copy2(thumb_path, backup_path)

        # Create new thumbnail from best image
        thumb_data = self.create_thumbnail(best["best_image_path"], thumb_path)

        if not thumb_data:
            # Restore backup
            if backup_path.exists():
                shutil.copy2(backup_path, thumb_path)
            return False

        print(f"  ✓ Created new thumbnail: {thumb_data['width']}×{thumb_data['height']}, "
              f"{thumb_data['file_size_bytes']:,} bytes")

        # Update metadata
        if self.update_metadata(species_id, best['best_image'], thumb_data):
            print(f"  ✓ Updated metadata.json")

        # Remove backup
        if backup_path.exists():
            backup_path.unlink()

        self.fixed_count += 1
        return True

    def find_species_needing_fixes(self, min_improvement: int = 10) -> List[str]:
        """Find all species where thumbnail can be improved."""
        print("🔍 Scanning all species for thumbnail improvements...\n")

        needs_fixing = []

        for species_dir in sorted(self.species_base.iterdir()):
            if not species_dir.is_dir():
                continue

            species_id = species_dir.name
            best = self.find_best_image(species_id)

            if best and best["improvement"] >= min_improvement:
                needs_fixing.append({
                    "species_id": species_id,
                    "improvement": best["improvement"],
                    "current_score": best["current_thumb_score"],
                    "new_score": best["best_score"]
                })

        return sorted(needs_fixing, key=lambda x: x["improvement"], reverse=True)

    def run(self):
        """Main execution."""
        print("=" * 70)
        print("THUMBNAIL FIXER")
        print("=" * 70)
        if self.dry_run:
            print("🏃 DRY RUN MODE - No changes will be made")
        print()

        # Find species needing fixes
        species_list = self.find_species_needing_fixes(min_improvement=10)

        if not species_list:
            print("✓ No species found needing thumbnail improvements (>10 points)")
            return

        print(f"Found {len(species_list)} species with improvable thumbnails:\n")
        print(f"{'Species':<10} {'Current':<9} {'New':<9} {'Improvement'}")
        print("-" * 70)

        for item in species_list:
            print(f"{item['species_id']:<10} "
                  f"{item['current_score']:<9.0f} "
                  f"{item['new_score']:<9.0f} "
                  f"+{item['improvement']:.0f}")

        print()

        if self.dry_run:
            print("🏃 DRY RUN - Would process these species")
            return

        # Confirm with user
        response = input(f"\nProcess {len(species_list)} species? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled.")
            return

        # Process each species
        print("\n" + "=" * 70)
        print("PROCESSING")
        print("=" * 70)

        for item in species_list:
            self.fix_thumbnail(item["species_id"])

        # Summary
        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"✓ Fixed thumbnails for {self.fixed_count}/{len(species_list)} species")

        if self.fixed_count > 0:
            print(f"\n⚠️  Next steps:")
            print(f"  1. Run quality scorer to verify improvements")
            print(f"  2. Regenerate manifest.json with updated SHA-256 hashes")
            print(f"  3. Commit and push changes")

        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Fix thumbnails using best quality images")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    args = parser.parse_args()

    fixer = ThumbnailFixer(dry_run=args.dry_run)
    fixer.run()


if __name__ == "__main__":
    main()
