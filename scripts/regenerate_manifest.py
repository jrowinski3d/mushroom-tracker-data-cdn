#!/usr/bin/env python3
"""
Manifest Regenerator

Regenerates manifest.json with updated SHA-256 hashes and file sizes.
Run this after updating any images or metadata.

Usage:
    python3 scripts/regenerate_manifest.py
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List


class ManifestGenerator:
    """Generates manifest.json from current CDN content."""

    BASE_URL = "https://raw.githubusercontent.com/jrowinski3d/mushroom-tracker-data-cdn/main/"

    def __init__(self):
        self.species_base = Path("species")
        self.manifest_path = Path("manifest.json")

    def calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of a file."""
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()

    def get_image_info(self, image_path: Path) -> Dict:
        """Get image dimensions and file info."""
        from PIL import Image

        with Image.open(image_path) as img:
            return {
                "width": img.size[0],
                "height": img.size[1],
                "file_size_bytes": image_path.stat().st_size,
                "sha256": self.calculate_sha256(image_path)
            }

    def process_species(self, species_dir: Path) -> Dict:
        """Process a single species directory."""
        species_id = species_dir.name

        # Load metadata
        metadata_path = species_dir / "metadata.json"
        if not metadata_path.exists():
            print(f"  ⚠️  {species_id}: metadata.json not found")
            return None

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"  ✗ {species_id}: Failed to load metadata: {e}")
            return None

        # Get thumbnail info
        thumb_path = species_dir / "thumb.webp"
        if not thumb_path.exists():
            print(f"  ⚠️  {species_id}: thumb.webp not found")
            return None

        thumb_info = self.get_image_info(thumb_path)

        # Get full images info
        images = []
        total_size = thumb_info["file_size_bytes"]  # Start with thumbnail size
        total_size += metadata_path.stat().st_size  # Add metadata size

        for idx in range(2):  # image_0.webp, image_1.webp
            img_path = species_dir / f"image_{idx}.webp"
            if img_path.exists():
                img_info = self.get_image_info(img_path)
                images.append({
                    "filename": f"image_{idx}.webp",
                    "url": f"{self.BASE_URL}species/{species_id}/image_{idx}.webp",
                    "sha256": img_info["sha256"],
                    "size_bytes": img_info["file_size_bytes"],
                    "width": img_info["width"],
                    "height": img_info["height"]
                })
                total_size += img_info["file_size_bytes"]

        # Edibility mapping
        edibility_map = {"E": "edible", "P": "poisonous", "T": "toxic", "U": "unknown", "I": "inedible"}
        edibility_code = metadata.get("edibility", "U")
        edibility_full = edibility_map.get(edibility_code, "unknown")

        return {
            "mushroom_id": species_id,
            "scientific_name": metadata.get("scientific_name", ""),
            "common_name": metadata.get("common_name", ""),
            "edibility": edibility_full,
            "metadata_url": f"{self.BASE_URL}species/{species_id}/metadata.json",
            "metadata_size_bytes": metadata_path.stat().st_size,
            "thumbnail_url": f"{self.BASE_URL}species/{species_id}/thumb.webp",
            "thumbnail_sha256": thumb_info["sha256"],
            "thumbnail_size_bytes": thumb_info["file_size_bytes"],
            "thumbnail_width": thumb_info["width"],
            "thumbnail_height": thumb_info["height"],
            "images": images,
            "total_size_bytes": total_size
        }

    def generate(self):
        """Generate complete manifest.json."""
        print("=" * 70)
        print("MANIFEST GENERATOR")
        print("=" * 70)
        print()

        if not self.species_base.exists():
            print("✗ species directory not found!")
            return

        # Find all species
        species_dirs = sorted([d for d in self.species_base.iterdir() if d.is_dir()])
        print(f"Found {len(species_dirs)} species directories\n")

        # Process each species
        species_list = []
        total_size = 0

        for species_dir in species_dirs:
            species_data = self.process_species(species_dir)
            if species_data:
                species_list.append(species_data)
                total_size += species_data["total_size_bytes"]
                print(f"  ✓ {species_data['mushroom_id']}: {species_data['total_size_bytes']:,} bytes")

        # Build manifest
        manifest = {
            "version": "1.0.0",
            "generated_at": datetime.now().isoformat(),
            "total_species": len(species_list),
            "total_size_bytes": total_size,
            "species": species_list
        }

        # Calculate manifest SHA-256
        manifest_str = json.dumps(manifest, sort_keys=True)
        manifest_sha = hashlib.sha256(manifest_str.encode()).hexdigest()
        manifest["sha256"] = manifest_sha

        # Save manifest
        with open(self.manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        # Summary
        print()
        print("=" * 70)
        print("MANIFEST GENERATED")
        print("=" * 70)
        print(f"Total species: {len(species_list)}")
        print(f"Total size: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
        print(f"Manifest SHA-256: {manifest_sha[:16]}...")
        print(f"Saved to: {self.manifest_path}")
        print("=" * 70)


def main():
    generator = ManifestGenerator()
    generator.generate()


if __name__ == "__main__":
    main()
