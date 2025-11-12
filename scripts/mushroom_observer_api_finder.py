#!/usr/bin/env python3
"""
Mushroom Observer API Image Finder

This script finds high-quality replacement images from Mushroom Observer using their API:
1. Searches for observations of a specific species via API
2. Downloads candidate images and scores them using our quality scorer
3. Recommends the best images to use as replacements

Usage:
    python3 scripts/mushroom_observer_api_finder.py --species "Exidia glandulosa"
    python3 scripts/mushroom_observer_api_finder.py --species-id exigla --top 10
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
import urllib.request
import urllib.parse
import tempfile

from image_quality_scorer import ImageQualityScorer


class MushroomObserverAPI:
    """Client for Mushroom Observer API v2."""

    BASE_URL = "https://mushroomobserver.org"
    API_BASE = f"{BASE_URL}/api2"

    # Commercial-friendly licenses
    ALLOWED_LICENSES = [
        "Creative Commons Attribution-ShareAlike 3.0",
        "Creative Commons Attribution 3.0",
        "Creative Commons Zero v1.0",
        "Public Domain",
        "Creative Commons Wikipedia Compatible v3.0"
    ]

    def __init__(self):
        self.request_count = 0
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limit: 1 request per 5 seconds."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < 5:
            sleep_time = 5 - time_since_last
            print(f"   Rate limiting... waiting {sleep_time:.1f}s")
            time.sleep(sleep_time)

        self.last_request_time = time.time()
        self.request_count += 1

    def _make_request(self, endpoint: str, params: Dict) -> Dict:
        """Make API request with rate limiting."""
        self._rate_limit()

        query_string = urllib.parse.urlencode(params)
        url = f"{self.API_BASE}/{endpoint}?{query_string}"

        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            print(f"✗ HTTP Error {e.code}: {e.reason}")
            print(f"   URL: {url}")
            return {}
        except Exception as e:
            print(f"✗ Request failed: {e}")
            return {}

    def search_observations(self, species_name: str, has_images: bool = True) -> List[Dict]:
        """
        Search for observations by species name.

        Args:
            species_name: Scientific name (e.g., "Exidia glandulosa")
            has_images: Only return observations with images

        Returns:
            List of observation records
        """
        print(f"Searching for observations of '{species_name}'...")

        # First, get observation IDs
        params = {
            'name': species_name,
            'detail': 'high',
            'format': 'json'
        }

        if has_images:
            params['has_images'] = 'yes'

        result = self._make_request('observations', params)

        if not result or 'results' not in result:
            return []

        observations = result['results']
        print(f"✓ Found {len(observations)} observations")

        return observations

    def get_image_details(self, image_id: int) -> Optional[Dict]:
        """Get detailed information about a specific image."""
        params = {
            'detail': 'high',
            'format': 'json'
        }

        result = self._make_request(f'images/{image_id}', params)

        if not result or 'results' not in result or not result['results']:
            return None

        return result['results'][0]

    def download_image(self, image_url: str, output_path: Path) -> bool:
        """Download an image from URL with rate limiting."""
        try:
            self._rate_limit()
            urllib.request.urlretrieve(image_url, output_path)
            return True
        except Exception as e:
            print(f"✗ Failed to download {image_url}: {e}")
            return False

    def extract_images_from_observations(self, observations: List[Dict]) -> List[Dict]:
        """Extract image information from observations."""
        images = []

        for obs in observations:
            if 'images' not in obs or not obs['images']:
                continue

            # Get primary image
            for img in obs['images']:
                if 'id' in img:
                    images.append({
                        'observation_id': obs.get('id'),
                        'image_id': img['id'],
                        'date': obs.get('date'),
                        'vote_cache': obs.get('consensus', {}).get('id', 0),
                        'location': obs.get('location')
                    })

        return images


def find_replacement_images(species_name: str, top_n: int = 10, min_score: int = 70):
    """
    Find high-quality replacement images for a species using the API.

    Args:
        species_name: Scientific name (e.g., "Exidia glandulosa")
        top_n: Number of top candidates to download and score
        min_score: Minimum quality score to recommend (0-100)
    """
    print("=" * 70)
    print(f"FINDING REPLACEMENT IMAGES FOR: {species_name}")
    print("=" * 70)

    # Initialize clients
    api_client = MushroomObserverAPI()
    scorer = ImageQualityScorer()

    # Step 1: Search for observations
    print(f"\n1. Searching Mushroom Observer API...")
    observations = api_client.search_observations(species_name, has_images=True)

    if not observations:
        print(f"✗ No observations found for '{species_name}'")
        print("\nTip: Try checking the scientific name spelling or use alternate names")
        return

    print(f"✓ Found {len(observations)} observations with images")

    # Step 2: Extract images
    print(f"\n2. Extracting image information...")
    images = api_client.extract_images_from_observations(observations)

    if not images:
        print(f"✗ No images found in observations")
        return

    print(f"✓ Found {len(images)} images")

    # Limit to top_n
    images = images[:min(top_n, len(images))]

    # Step 3: Get detailed image info and filter by license
    print(f"\n3. Checking image licenses...")
    candidates = []

    for img in images:
        img_details = api_client.get_image_details(img['image_id'])

        if not img_details:
            continue

        # Check license
        license_info = img_details.get('license', {})
        license_name = license_info.get('name', '') if isinstance(license_info, dict) else str(license_info)
        if license_name not in api_client.ALLOWED_LICENSES:
            print(f"   Skipping image {img['image_id']}: Non-commercial license ({license_name})")
            continue

        # Get image URL (640px version)
        image_url = None
        if 'files' in img_details:
            for file_info in img_details['files']:
                if isinstance(file_info, dict) and file_info.get('size') == 'medium':  # 640px
                    image_url = file_info.get('url')
                    break

        # Fallback: try to construct URL directly from image ID
        if not image_url:
            image_url = f"{api_client.BASE_URL}/images/640/{img['image_id']}.jpg"

        # Get license URL
        license_url = license_info.get('url', '') if isinstance(license_info, dict) else ''

        candidates.append({
            **img,
            'url': image_url,
            'original_url': f"{api_client.BASE_URL}/images/{img['image_id']}",
            'photographer': img_details.get('owner', 'Unknown'),
            'license': license_name,
            'license_url': license_url,
            'notes': img_details.get('notes', '')
        })

    print(f"✓ Found {len(candidates)} images with commercial-friendly licenses")

    if not candidates:
        print(f"✗ No images with commercial-friendly licenses found")
        return

    # Step 4: Download and score images
    print(f"\n4. Downloading and scoring {len(candidates)} candidate images...")
    print("   (Rate limited to 1 request per 5 seconds)\n")

    scored_images = []
    temp_dir = Path(tempfile.mkdtemp())

    for i, candidate in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] Image {candidate['image_id']}...", end=" ")

        temp_file = temp_dir / f"{candidate['image_id']}.jpg"

        # Download image
        if not api_client.download_image(candidate['url'], temp_file):
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

    if not recommended:
        print("\n✗ No images were successfully scored")
        return

    print(f"\nTop {len(recommended)} images:\n")
    print(f"{'Rank':<6} {'Score':<7} {'Blur':<12} {'Brightness':<12} {'Image ID':<10} {'Date'}")
    print("-" * 70)

    for i, img in enumerate(recommended, 1):
        print(f"{i:<6} {img['quality_score']:<7} {img['blur_rating']:<12} "
              f"{img['brightness_rating']:<12} {img['image_id']:<10} {img.get('date', 'N/A')}")

    if recommended:
        best = recommended[0]
        print(f"\n{'=' * 70}")
        print("BEST IMAGE DETAILS")
        print("=" * 70)
        print(f"Image ID: {best['image_id']}")
        print(f"Quality Score: {best['quality_score']}/100")
        print(f"Download URL: {best['url']}")
        print(f"Page URL: {best['original_url']}")
        print(f"Photographer: {best['photographer']}")
        print(f"License: {best['license']}")
        print(f"License URL: {best['license_url']}")
        print(f"Observation Date: {best.get('date', 'N/A')}")

        print(f"\n{'=' * 70}")
        print("TO USE THIS IMAGE:")
        print("=" * 70)
        print(f"1. Visit: {best['original_url']}")
        print(f"2. Download and verify image quality")
        print(f"3. Update species metadata with attribution:")
        print(f"   - photographer: {best['photographer']}")
        print(f"   - license_url: {best['license_url']}")
        print(f"   - source_url: {best['original_url']}")
        print(f"   - observation_date: {best.get('date', 'N/A')}")
        print("=" * 70)

    print(f"\nTotal API requests made: {api_client.request_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Find high-quality replacement images from Mushroom Observer API"
    )
    parser.add_argument(
        "--species",
        type=str,
        help='Scientific name (e.g., "Exidia glandulosa")'
    )
    parser.add_argument(
        "--species-id",
        type=str,
        help="Species ID from your CDN (e.g., exigla) - will look up scientific name from metadata"
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

    args = parser.parse_args()

    # Determine species name
    species_name = args.species

    if args.species_id:
        # Look up scientific name from metadata
        metadata_file = Path(f"species/{args.species_id}/metadata.json")
        if metadata_file.exists():
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
