#!/usr/bin/env python3
"""
Mushroom Observer Image Finder

This script helps find high-quality replacement images from Mushroom Observer:
1. Downloads CSV data from Mushroom Observer (observations, images, names)
2. Searches for observations of a specific species
3. Downloads candidate images and scores them using our quality scorer
4. Recommends the best images to use as replacements

Usage:
    python3 scripts/mushroom_observer_image_finder.py --species "Agaricus arvensis"
    python3 scripts/mushroom_observer_image_finder.py --species-id agaarv --top 10
"""

import argparse
import csv
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse
import urllib.request
import tempfile

from image_quality_scorer import ImageQualityScorer


class MushroomObserverClient:
    """Client for interacting with Mushroom Observer CSV data."""

    BASE_URL = "https://mushroomobserver.org"
    CACHE_DIR = Path("scripts/.cache")

    # Commercial-friendly licenses
    ALLOWED_LICENSES = [
        "Creative Commons Attribution-ShareAlike 3.0",
        "Creative Commons Attribution 3.0",
        "Creative Commons Zero v1.0",
        "Public Domain",
        "Creative Commons Wikipedia Compatible v3.0"
    ]

    def __init__(self):
        self.CACHE_DIR.mkdir(exist_ok=True, parents=True)
        self.names_cache = {}
        self.observations_cache = {}
        self.images_cache = {}

    def download_csv(self, filename: str, force_refresh: bool = False) -> Path:
        """Download CSV file from Mushroom Observer with caching."""
        cache_file = self.CACHE_DIR / filename

        if cache_file.exists() and not force_refresh:
            print(f"Using cached {filename}")
            return cache_file

        print(f"Downloading {filename} from Mushroom Observer...")
        url = f"{self.BASE_URL}/{filename}"

        try:
            urllib.request.urlretrieve(url, cache_file)
            print(f"✓ Downloaded {filename}")
            return cache_file
        except Exception as e:
            print(f"✗ Failed to download {filename}: {e}")
            sys.exit(1)

    def load_names(self, force_refresh: bool = False) -> Dict:
        """Load names.csv and build lookup dict."""
        if self.names_cache and not force_refresh:
            return self.names_cache

        names_file = self.download_csv("names.csv", force_refresh)

        print("Loading species names...")
        with open(names_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                name_id = int(row['id'])
                self.names_cache[name_id] = {
                    'text_name': row['text_name'],
                    'author': row['author'],
                    'deprecated': row['deprecated'] == '1',
                    'rank': row['rank']
                }

        print(f"✓ Loaded {len(self.names_cache)} species names")
        return self.names_cache

    def find_species_by_name(self, species_name: str) -> Optional[int]:
        """Find species name_id by scientific name."""
        if not self.names_cache:
            self.load_names()

        # Exact match first
        for name_id, data in self.names_cache.items():
            if data['text_name'].lower() == species_name.lower():
                return name_id

        # Partial match
        species_lower = species_name.lower()
        for name_id, data in self.names_cache.items():
            if species_lower in data['text_name'].lower():
                print(f"Found partial match: {data['text_name']}")
                return name_id

        return None

    def load_observations(self, force_refresh: bool = False) -> Dict:
        """Load observations.csv."""
        if self.observations_cache and not force_refresh:
            return self.observations_cache

        obs_file = self.download_csv("observations.csv", force_refresh)

        print("Loading observations (this may take a moment)...")
        with open(obs_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                obs_id = int(row['id'])
                self.observations_cache[obs_id] = {
                    'name_id': int(row['name_id']) if row['name_id'] != 'NULL' else None,
                    'when': row['when'],
                    'location_id': row['location_id'],
                    'vote_cache': float(row['vote_cache']) if row['vote_cache'] != 'NULL' else 0.0,
                    'thumb_image_id': int(row['thumb_image_id']) if row['thumb_image_id'] != 'NULL' else None
                }

        print(f"✓ Loaded {len(self.observations_cache)} observations")
        return self.observations_cache

    def load_images(self, force_refresh: bool = False) -> Dict:
        """Load images.csv."""
        if self.images_cache and not force_refresh:
            return self.images_cache

        images_file = self.download_csv("images.csv", force_refresh)

        print("Loading images...")
        with open(images_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                image_id = int(row['id'])
                self.images_cache[image_id] = {
                    'content_type': row['content_type'],
                    'copyright_holder': row['copyright_holder'],
                    'license': row['license'],
                    'ok_for_export': row['ok_for_export'] == '1',
                    'diagnostic': row['diagnostic'] == '1'
                }

        print(f"✓ Loaded {len(self.images_cache)} images")
        return self.images_cache

    def find_observations_for_species(self, name_id: int, min_vote: float = 2.0) -> List[Dict]:
        """Find all observations for a given species with good confidence."""
        if not self.observations_cache:
            self.load_observations()

        matches = []
        for obs_id, obs_data in self.observations_cache.items():
            if obs_data['name_id'] == name_id and obs_data['vote_cache'] >= min_vote:
                matches.append({
                    'observation_id': obs_id,
                    'image_id': obs_data['thumb_image_id'],
                    'date': obs_data['when'],
                    'vote_cache': obs_data['vote_cache']
                })

        return sorted(matches, key=lambda x: x['vote_cache'], reverse=True)

    def get_image_info(self, image_id: int) -> Optional[Dict]:
        """Get image metadata."""
        if not self.images_cache:
            self.load_images()

        if image_id not in self.images_cache:
            return None

        img_data = self.images_cache[image_id]

        # Check if license is allowed
        if img_data['license'] not in self.ALLOWED_LICENSES:
            return None

        # Check if ok for export
        if not img_data['ok_for_export']:
            return None

        return {
            'image_id': image_id,
            'url': f"{self.BASE_URL}/images/640/{image_id}.jpg",
            'original_url': f"{self.BASE_URL}/{image_id}",
            'photographer': img_data['copyright_holder'],
            'license': img_data['license'],
            'diagnostic': img_data['diagnostic']
        }

    def download_image(self, image_url: str, output_path: Path) -> bool:
        """Download an image from URL with rate limiting."""
        try:
            # Rate limiting: 1 request every 5 seconds
            time.sleep(5)

            urllib.request.urlretrieve(image_url, output_path)
            return True
        except Exception as e:
            print(f"✗ Failed to download {image_url}: {e}")
            return False


def find_replacement_images(species_name: str, top_n: int = 10, min_score: int = 70):
    """
    Find high-quality replacement images for a species.

    Args:
        species_name: Scientific name (e.g., "Agaricus arvensis")
        top_n: Number of top candidates to download and score
        min_score: Minimum quality score to recommend (0-100)
    """
    print("=" * 70)
    print(f"FINDING REPLACEMENT IMAGES FOR: {species_name}")
    print("=" * 70)

    # Initialize clients
    mo_client = MushroomObserverClient()
    scorer = ImageQualityScorer()

    # Step 1: Find species ID
    print(f"\n1. Searching for species: {species_name}")
    name_id = mo_client.find_species_by_name(species_name)

    if not name_id:
        print(f"✗ Species '{species_name}' not found in Mushroom Observer database")
        return

    print(f"✓ Found species with ID: {name_id}")

    # Step 2: Find observations
    print(f"\n2. Finding observations...")
    observations = mo_client.find_observations_for_species(name_id, min_vote=2.0)

    if not observations:
        print(f"✗ No observations found for {species_name}")
        return

    print(f"✓ Found {len(observations)} observations with good confidence (vote ≥ 2.0)")

    # Step 3: Filter for images with commercial-friendly licenses
    print(f"\n3. Filtering for commercial-friendly licenses...")
    candidates = []

    for obs in observations[:top_n * 3]:  # Check 3x top_n to account for filtering
        if obs['image_id'] is None:
            continue

        img_info = mo_client.get_image_info(obs['image_id'])
        if img_info:
            candidates.append({
                **obs,
                **img_info
            })

        if len(candidates) >= top_n:
            break

    print(f"✓ Found {len(candidates)} images with commercial-friendly licenses")

    if not candidates:
        print(f"✗ No images found with commercial-friendly licenses")
        return

    # Step 4: Download and score images
    print(f"\n4. Downloading and scoring top {len(candidates)} candidate images...")
    print("   (Rate limited to 1 request per 5 seconds)\n")

    scored_images = []
    temp_dir = Path(tempfile.mkdtemp())

    for i, candidate in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] Image {candidate['image_id']}...", end=" ")

        temp_file = temp_dir / f"{candidate['image_id']}.jpg"

        # Download image
        if not mo_client.download_image(candidate['url'], temp_file):
            print("✗ Download failed")
            continue

        # Score image
        result = scorer.analyze_image(temp_file)

        if "error" in result:
            print(f"✗ Scoring failed: {result['error']}")
            continue

        score = result['overall_score']
        blur_rating = result['metrics']['blur']['rating']

        print(f"Score: {score} ({blur_rating})")

        scored_images.append({
            **candidate,
            'quality_score': score,
            'blur_rating': blur_rating,
            'brightness_rating': result['metrics']['brightness']['brightness_rating'],
            'metrics': result['metrics']
        })

    # Cleanup temp files
    import shutil
    shutil.rmtree(temp_dir)

    # Step 5: Recommend best images
    print("\n" + "=" * 70)
    print("RECOMMENDED IMAGES")
    print("=" * 70)

    # Sort by quality score
    scored_images.sort(key=lambda x: x['quality_score'], reverse=True)

    # Filter by minimum score
    recommended = [img for img in scored_images if img['quality_score'] >= min_score]

    if not recommended:
        print(f"\n⚠️  No images scored above {min_score}. Showing all results:\n")
        recommended = scored_images

    print(f"\nTop {len(recommended)} images:\n")
    print(f"{'Rank':<6} {'Score':<7} {'Blur':<12} {'Brightness':<12} {'Image ID':<10} {'Observation Date'}")
    print("-" * 70)

    for i, img in enumerate(recommended, 1):
        print(f"{i:<6} {img['quality_score']:<7} {img['blur_rating']:<12} "
              f"{img['brightness_rating']:<12} {img['image_id']:<10} {img['date']}")

    if recommended:
        best = recommended[0]
        print(f"\n{'=' * 70}")
        print("BEST IMAGE DETAILS")
        print("=" * 70)
        print(f"Image ID: {best['image_id']}")
        print(f"Quality Score: {best['quality_score']}/100")
        print(f"URL: {best['url']}")
        print(f"Page: {best['original_url']}")
        print(f"Photographer: {best['photographer']}")
        print(f"License: {best['license']}")
        print(f"Observation Date: {best['date']}")
        print(f"Vote Confidence: {best['vote_cache']:.2f}")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Find high-quality replacement images from Mushroom Observer"
    )
    parser.add_argument(
        "--species",
        type=str,
        help='Scientific name (e.g., "Agaricus arvensis")'
    )
    parser.add_argument(
        "--species-id",
        type=str,
        help="Species ID from your CDN (e.g., agaarv) - will look up scientific name from metadata"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of candidate images to evaluate (default: 10)"
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=70,
        help="Minimum quality score to recommend (default: 70)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh of cached CSV data"
    )

    args = parser.parse_args()

    # Determine species name
    species_name = args.species

    if args.species_id:
        # Look up scientific name from metadata
        metadata_file = Path(f"species/{args.species_id}/metadata.json")
        if metadata_file.exists():
            import json
            with open(metadata_file) as f:
                metadata = json.load(f)
                species_name = metadata['scientific_name']
                print(f"Looking up: {species_name} (from {args.species_id})")
        else:
            print(f"✗ Species {args.species_id} not found in CDN")
            sys.exit(1)

    if not species_name:
        parser.print_help()
        sys.exit(1)

    find_replacement_images(species_name, top_n=args.top, min_score=args.min_score)


if __name__ == "__main__":
    main()
