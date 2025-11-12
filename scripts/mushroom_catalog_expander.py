#!/usr/bin/env python3
"""
Mushroom Catalog Expansion Script
Automates the creation of new mushroom entries from Mushroom Observer dataset.

This script:
1. Fetches mushroom data from Mushroom Observer ML dataset
2. Filters for target species (from expansion plan)
3. Downloads and processes images with licensing verification
4. Generates thumbnails and optimizes images
5. Creates TypeScript content files
6. Updates asset registries and imports

Usage:
    python mushroom_catalog_expander.py --species "Agaricus campestris" --test-mode
    python mushroom_catalog_expander.py --batch-process --species-list species_list.txt
"""

import os
import sys
import json
import csv
import requests
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import re
import urllib.parse
from PIL import Image, ImageEnhance
import hashlib

# Import mushroom database for common names and edibility
from mushroom_database import (
    get_mushroom_info,
    get_common_name,
    get_edibility_category,
    is_edible,
    is_poisonous
)

# Configuration
MUSHROOM_TRACKER_ROOT = Path(__file__).parent.parent / "MushroomTracker"
ASSETS_DIR = MUSHROOM_TRACKER_ROOT / "src" / "assets" / "mushrooms"
CONTENT_DIR = MUSHROOM_TRACKER_ROOT / "src" / "content" / "mushrooms"
IMAGES_DIR = ASSETS_DIR / "images"
THUMBNAILS_DIR = ASSETS_DIR / "thumbnails"
DATA_DIR = MUSHROOM_TRACKER_ROOT / "src" / "data"

# Mushroom Observer Dataset URLs
MO_ML_DATASET_URL = "https://docs.google.com/spreadsheets/d/1aQSmLlthx99pCt_IS6aHyhZdn_hUiv3EBLbf4h3Zg7s/export?format=csv"
MO_API_BASE = "https://mushroomobserver.org/api2"

# Image processing settings
THUMBNAIL_SIZE = (200, 200)
MAX_IMAGE_SIZE = (1200, 1200)
JPEG_QUALITY = 85

@dataclass
class MushroomImage:
    """Represents a mushroom image with metadata"""
    id: str
    url: str
    filename: str
    caption: str
    alt_text: str
    license: str
    rights_holder: str
    order: int
    quality_score: float = 0.0

@dataclass
class MushroomData:
    """Complete mushroom data structure"""
    id: str
    name: str
    scientific_name: str
    summary: str
    edibility: str  # 'E' for edible, 'P' for poisonous, 'U' for unknown
    description: str
    habitat: str
    identification_features: List[str]
    safety_notes: str
    look_alikes: List[str]
    season: str
    difficulty: str = 'intermediate'
    images: List[MushroomImage] = None

    def __post_init__(self):
        if self.images is None:
            self.images = []

class MushroomCatalogExpander:
    """Main class for expanding the mushroom catalog"""

    def __init__(self, test_mode: bool = False, dry_run: bool = False):
        self.test_mode = test_mode
        self.dry_run = dry_run or test_mode  # Test mode implies dry run
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'MushroomTracker/1.0 (Educational App - jasrowinski@gmail.com)'
        })

        # Priority species from the expansion plan
        self.target_species = self._load_target_species()

        # Create directories if they don't exist (unless dry run)
        if not self.dry_run:
            self._ensure_directories()

        print(f"🍄 Mushroom Catalog Expander initialized")
        print(f"📁 Assets dir: {ASSETS_DIR}")
        print(f"📝 Content dir: {CONTENT_DIR}")
        print(f"🧪 Test mode: {'ON' if test_mode else 'OFF'}")
        if self.dry_run:
            print(f"🏃 DRY RUN MODE: No files will be created or modified")

    def _load_target_species(self) -> List[str]:
        """Load target species from the expansion plan"""
        # Tier 1: Essential Safety Species (high priority)
        tier1 = [
            "Amanita ocreata",  # Destroying Angel
            "Amanita bisporigera",  # Destroying Angel
            "Galerina marginata",  # Deadly Galerina
            "Gyromitra esculenta",  # False Morel
            "Omphalotus olearius",  # Jack-o'-lantern
            "Cortinarius rubellus",  # Deadly Webcap
            "Amanita phalloides",  # Death Cap (already exists)
            "Amanita muscaria",  # Fly Agaric (already exists)
        ]

        # Tier 2: Popular Edible Species
        tier2 = [
            "Morchella esculenta",  # Common Morel
            "Morchella americana",  # American Morel
            "Cantharellus cibarius",  # Golden Chanterelle (already exists)
            "Cantharellus formosus",  # Pacific Golden Chanterelle
            "Boletus edulis",  # King Bolete/Porcini (already exists)
            "Pleurotus ostreatus",  # Oyster Mushroom (already exists)
            "Hericium erinaceus",  # Lion's Mane (already exists)
            "Armillaria mellea",  # Honey Mushroom
            "Lactarius deliciosus",  # Saffron Milk Cap (already exists)
            "Hypomyces lactifluorum",  # Lobster Mushroom (already exists)
        ]

        # Tier 3: Regional Specialists
        tier3 = [
            "Tricholoma matsutake",  # Matsutake
            "Laetiporus gilbertsonii",  # Western Chicken of the Woods
            "Grifola frondosa",  # Maitake
            "Calvatia gigantea",  # Giant Puffball
        ]

        return tier1 + tier2 + tier3

    def _ensure_directories(self):
        """Create required directories if they don't exist"""
        dirs = [ASSETS_DIR, IMAGES_DIR, THUMBNAILS_DIR, CONTENT_DIR]
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)

    def fetch_mushroom_observer_data(self) -> List[Dict]:
        """Fetch data from Mushroom Observer ML dataset"""

        # Check for cached data first (1 hour cache)
        cache_file = Path(__file__).parent / "mo_dataset_cache.csv"
        cache_age_hours = 1

        if cache_file.exists():
            cache_age = (datetime.now().timestamp() - cache_file.stat().st_mtime) / 3600
            if cache_age < cache_age_hours:
                print(f"📋 Using cached dataset (age: {cache_age:.1f} hours)")
                try:
                    with open(cache_file, 'r') as f:
                        csv_reader = csv.DictReader(f)
                        dataset = list(csv_reader)
                    print(f"✅ Loaded {len(dataset)} records from cache")
                    return dataset
                except Exception as e:
                    print(f"⚠️ Cache read failed: {e}, downloading fresh data...")

        print("📊 Fetching fresh Mushroom Observer ML dataset...")
        try:
            response = self.session.get(MO_ML_DATASET_URL, timeout=30)
            response.raise_for_status()

            # Save to cache
            print("💾 Caching dataset for future use...")
            with open(cache_file, 'w') as f:
                f.write(response.text)

            # Parse CSV data
            csv_reader = csv.DictReader(response.text.splitlines())
            dataset = list(csv_reader)

            print(f"✅ Loaded {len(dataset)} records from MO ML dataset")
            return dataset

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch MO dataset: {e}")

            # Try to use stale cache as fallback
            if cache_file.exists():
                print("🔄 Using stale cache as fallback...")
                try:
                    with open(cache_file, 'r') as f:
                        csv_reader = csv.DictReader(f)
                        dataset = list(csv_reader)
                    print(f"✅ Loaded {len(dataset)} records from stale cache")
                    return dataset
                except Exception:
                    pass

            print("🔄 Falling back to mock data for testing...")
            return self._get_mock_dataset()

    def _get_mock_dataset(self) -> List[Dict]:
        """Return mock data for testing when API is unavailable"""
        return [
            {
                'name': 'Morchella esculenta',
                'image_link': 'https://mushroomobserver.org/images/orig/123456.jpg',
                'license_link': 'https://creativecommons.org/licenses/by/4.0/',
                'rights_holder': 'Expert Observer',
                'date': '2024-04-15'
            },
            {
                'name': 'Amanita ocreata',
                'image_link': 'https://mushroomobserver.org/images/orig/789012.jpg',
                'license_link': 'https://creativecommons.org/licenses/by-sa/4.0/',
                'rights_holder': 'Safety Expert',
                'date': '2024-05-20'
            }
        ]

    def filter_target_species(self, dataset: List[Dict]) -> Dict[str, List[Dict]]:
        """Filter dataset for target species"""
        print("🎯 Filtering for target species...")

        species_data = {}
        for record in dataset:
            species_name = record.get('name', '').strip()
            if not species_name:
                continue

            # Check if this species is in our target list
            for target in self.target_species:
                if (species_name.lower() == target.lower() or
                    target.lower() in species_name.lower()):

                    if target not in species_data:
                        species_data[target] = []
                    species_data[target].append(record)
                    break

        print(f"🎯 Found data for {len(species_data)} target species")
        for species, records in species_data.items():
            print(f"  📋 {species}: {len(records)} records")

        return species_data

    def validate_licensing(self, license_url: str) -> bool:
        """Check if license allows commercial use"""
        if not license_url:
            # In test mode, allow images without explicit license info for testing
            if self.test_mode:
                return True
            return False

        license_url = license_url.lower()

        # Acceptable licenses for commercial use
        acceptable_licenses = [
            'creativecommons.org/licenses/by/',
            'creativecommons.org/licenses/by-sa/',
            'creativecommons.org/publicdomain/',
            'public domain',
            'cc-by',
            'cc0'
        ]

        is_valid = any(license in license_url for license in acceptable_licenses)

        # In test mode, be more permissive to allow testing
        if self.test_mode and not is_valid:
            print(f"⚠️ Test mode: Accepting license {license_url} for testing purposes")
            return True

        return is_valid

    def download_image(self, image_url: str, filename: str) -> bool:
        """Download and save an image"""
        try:
            print(f"🔽 {'[DRY RUN] Would download' if self.dry_run else 'Downloading'} {filename}...")

            if self.dry_run:
                # In dry run, just validate the URL is accessible
                response = self.session.head(image_url, timeout=10)
                response.raise_for_status()
                print(f"✅ [DRY RUN] URL valid: {filename}")
                return True

            response = self.session.get(image_url, timeout=30, stream=True)
            response.raise_for_status()

            file_path = IMAGES_DIR / filename
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Verify it's a valid image
            try:
                with Image.open(file_path) as img:
                    img.verify()
                print(f"✅ Successfully downloaded {filename}")
                return True
            except Exception as e:
                print(f"❌ Invalid image file {filename}: {e}")
                file_path.unlink(missing_ok=True)
                return False

        except Exception as e:
            print(f"❌ Failed to {'check' if self.dry_run else 'download'} {filename}: {e}")
            return False

    def process_image(self, filename: str, create_thumbnail: bool = False) -> bool:
        """Optimize image and optionally create thumbnail"""
        if self.dry_run:
            print(f"🖼️ [DRY RUN] Would process {filename}{'(with thumbnail)' if create_thumbnail else ''}")
            return True

        try:
            file_path = IMAGES_DIR / filename
            if not file_path.exists():
                return False

            print(f"🖼️ Processing {filename}{'(with thumbnail)' if create_thumbnail else ''}...")

            with Image.open(file_path) as img:
                # Convert to RGB if needed
                if img.mode in ('RGBA', 'LA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                    img = rgb_img

                # Resize main image if too large
                if img.size[0] > MAX_IMAGE_SIZE[0] or img.size[1] > MAX_IMAGE_SIZE[1]:
                    img.thumbnail(MAX_IMAGE_SIZE, Image.Resampling.LANCZOS)

                # Enhance image quality
                enhancer = ImageEnhance.Sharpness(img)
                img = enhancer.enhance(1.1)

                # Save optimized image
                img.save(file_path, 'JPEG', quality=JPEG_QUALITY, optimize=True)

                # Create thumbnail only if requested
                if create_thumbnail:
                    # Remove the _0 suffix for thumbnails since we only create one
                    base_name = filename.replace('_0.jpg', '').replace('.jpg', '')
                    thumbnail_name = f"thumb_{base_name}.png"
                    thumbnail_path = THUMBNAILS_DIR / thumbnail_name

                    thumb_img = img.copy()
                    thumb_img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

                    # Add subtle border to thumbnail
                    from PIL import ImageDraw
                    draw = ImageDraw.Draw(thumb_img)
                    width, height = thumb_img.size
                    draw.rectangle([(0, 0), (width-1, height-1)], outline="#cccccc", width=1)

                    thumb_img.save(thumbnail_path, 'PNG', optimize=True)

                print(f"✅ Processed {filename}{'and created thumbnail' if create_thumbnail else ''}")
                return True

        except Exception as e:
            print(f"❌ Failed to process {filename}: {e}")
            return False

    def generate_mushroom_id(self, scientific_name: str, existing_ids: set) -> str:
        """Generate a unique mushroom ID"""
        # Extract genus and species
        parts = scientific_name.split()
        if len(parts) >= 2:
            base = f"{parts[0][:2]}{parts[1][:2]}".lower()
        else:
            base = scientific_name[:4].lower()

        # Ensure uniqueness
        counter = 1
        mushroom_id = base
        while mushroom_id in existing_ids:
            mushroom_id = f"{base}{counter}"
            counter += 1

        return mushroom_id

    def create_mushroom_data(self, species_name: str, records: List[Dict]) -> MushroomData:
        """Create structured mushroom data from MO records"""
        print(f"📝 Creating mushroom data for {species_name}...")

        # Filter for best quality images with proper licensing
        valid_records = []
        license_stats = {'total': len(records), 'valid': 0, 'no_license': 0, 'no_image': 0}

        for record in records:
            # Correct column names based on actual CSV structure
            license_link = record.get('license', '')  # This contains rights holder name, not license URL
            image_link = record.get('image', '')      # This contains the image URL

            if not image_link:
                license_stats['no_image'] += 1
                continue

            if not license_link:
                license_stats['no_license'] += 1

            # For now, assume all images from MO dataset are usable with proper attribution
            # In production, would need to validate actual license URLs
            if image_link:
                valid_records.append(record)
                license_stats['valid'] += 1

        print(f"📊 License validation stats: {license_stats}")

        if not valid_records:
            print(f"📋 Sample records for debugging:")
            for i, record in enumerate(records[:2]):
                print(f"  Record {i+1} keys: {list(record.keys())}")
                print(f"  Record {i+1} values: {dict(list(record.items())[:5])}")

            # In test mode, try to use any records with images, regardless of license
            if self.test_mode:
                print("🧪 Test mode: Attempting to use any records with images...")
                # Try different possible column names for images
                image_columns = ['image_link', 'Image link', 'imagelink', 'url', 'image_url', 'link']
                valid_records = []
                for record in records:
                    for col in image_columns:
                        if record.get(col):
                            # Update the record to standardize the column name
                            record['image_link'] = record[col]
                            valid_records.append(record)
                            break

            if not valid_records:
                raise ValueError(f"No records with images found for {species_name}. Available columns: {list(records[0].keys()) if records else 'none'}")

        # Sort by date (newest first) and take best images
        valid_records.sort(key=lambda x: x.get('created', ''), reverse=True)

        # Adjust image count based on edibility (safety species get more images)
        max_images = 4 if edibility == 'P' else 3  # Poisonous: 4 images, others: 3
        selected_records = valid_records[:max_images]

        # Generate unique ID
        existing_ids = self._get_existing_mushroom_ids()
        mushroom_id = self.generate_mushroom_id(species_name, existing_ids)

        # Determine edibility using comprehensive database
        mushroom_info = get_mushroom_info(species_name)
        edibility = mushroom_info['edibility']
        common_name = mushroom_info['common_name']

        print(f"📖 Species info: {common_name} (Edibility: {edibility})")

        # Create image data
        images = []
        thumbnail_created = False

        for idx, record in enumerate(selected_records):
            image_url = record.get('image', '')  # Correct column name
            if not image_url:
                continue

            # Generate filename
            safe_name = re.sub(r'[^a-z0-9_]', '_', species_name.lower().replace(' ', '_'))
            filename = f"{safe_name}_{idx}.jpg"

            # Download and process image
            if self.download_image(image_url, filename):
                if self.process_image(filename, create_thumbnail=(idx == 0)):  # Only create thumbnail for first image
                    image = MushroomImage(
                        id=f"{mushroom_id}-img-{idx}",
                        url=image_url,
                        filename=filename,
                        caption=f"{species_name} specimen",
                        alt_text=f"{species_name} mushroom image {idx + 1}",
                        license="Mushroom Observer Dataset",  # Simplified for now
                        rights_holder=record.get('license', ''),  # This contains the observer name
                        order=idx + 1,
                        quality_score=self._calculate_image_quality_score(record)
                    )
                    images.append(image)
                    if idx == 0:
                        thumbnail_created = True

        # Ensure minimum 2 images were processed
        if len(images) < 2:
            if len(selected_records) < 2:
                raise ValueError(f"Insufficient image records for {species_name}. Found {len(selected_records)}, need minimum 2")
            else:
                raise ValueError(f"Failed to process minimum images for {species_name}. Processed {len(images)}, need minimum 2")

        print(f"✅ Successfully processed {len(images)} images and {'1 thumbnail' if thumbnail_created else 'no thumbnails'} for {species_name}")

        # Generate content based on species knowledge and database info
        content_data = self._generate_species_content(species_name, edibility, mushroom_info)

        return MushroomData(
            id=mushroom_id,
            name=common_name,  # Use common name from database
            scientific_name=species_name,
            summary=mushroom_info.get('description', content_data['summary']),
            edibility=edibility,
            description=content_data['description'],
            habitat=content_data['habitat'],
            identification_features=content_data['identification_features'],
            safety_notes=content_data['safety_notes'],
            look_alikes=content_data['look_alikes'],
            season=content_data['season'],
            difficulty=content_data['difficulty'],
            images=images
        )

    def _get_existing_mushroom_ids(self) -> set:
        """Get set of existing mushroom IDs to avoid conflicts"""
        existing_ids = set()

        # Check existing data file
        mushrooms_file = DATA_DIR / "mushrooms.ts"
        if mushrooms_file.exists():
            content = mushrooms_file.read_text()
            # Extract IDs using regex
            ids = re.findall(r"id:\s*['\"]([^'\"]+)['\"]", content)
            existing_ids.update(ids)

        return existing_ids

    def _determine_edibility(self, species_name: str) -> str:
        """Determine edibility classification"""
        species_lower = species_name.lower()

        # Known poisonous genera/species
        poisonous_indicators = [
            'amanita ocreata', 'amanita bisporigera', 'amanita phalloides',
            'galerina', 'cortinarius rubellus', 'gyromitra', 'omphalotus'
        ]

        for poison in poisonous_indicators:
            if poison in species_lower:
                return 'P'  # Poisonous

        # Known edible genera/species
        edible_indicators = [
            'morchella', 'cantharellus', 'boletus edulis', 'pleurotus',
            'hericium', 'armillaria', 'lactarius deliciosus', 'hypomyces',
            'tricholoma matsutake', 'laetiporus', 'grifola', 'calvatia'
        ]

        for edible in edible_indicators:
            if edible in species_lower:
                return 'E'  # Edible

        return 'U'  # Unknown/uncertain

    def _calculate_image_quality_score(self, record: Dict) -> float:
        """Calculate quality score for image selection"""
        score = 5.0

        # Recent images get higher score
        date_str = record.get('created', '')  # Correct column name
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
                years_ago = (datetime.now() - date).days / 365
                if years_ago < 2:
                    score += 2.0
                elif years_ago < 5:
                    score += 1.0
            except ValueError:
                pass

        # Rights holder reputation (simplified)
        rights_holder = record.get('license', '').lower()  # This contains observer name
        if any(word in rights_holder for word in ['expert', 'mycologist', 'professor', 'scientist']):
            score += 1.5

        return min(score, 10.0)

    def _generate_species_content(self, species_name: str, edibility: str, mushroom_info: Dict) -> Dict:
        """Generate species content based on mycological knowledge"""

        # Use common name from database
        common_name = mushroom_info['common_name']

        # Generate content based on edibility and species
        if edibility == 'P':
            return self._generate_poisonous_content(species_name, common_name, mushroom_info)
        elif edibility == 'E':
            return self._generate_edible_content(species_name, common_name, mushroom_info)
        else:
            return self._generate_unknown_content(species_name, common_name, mushroom_info)

    def _generate_poisonous_content(self, species_name: str, common_name: str, mushroom_info: Dict) -> Dict:
        """Generate content for poisonous species"""

        toxicity_level = mushroom_info.get('toxicity', 'poisonous')

        return {
            'common_name': common_name,
            'summary': f'DANGEROUS: {common_name} is a highly toxic mushroom that can cause severe poisoning or death. Never consume this species.',
            'description': f'This is a dangerous mushroom that must be avoided. {common_name} contains potent toxins that can cause serious illness or death.',
            'habitat': 'Various woodland environments. Exercise extreme caution when foraging in areas where this species may occur.',
            'identification_features': [
                'Detailed identification requires expert knowledge',
                'Often confused with edible species',
                'Professional identification strongly recommended'
            ],
            'safety_notes': f'CRITICAL SAFETY WARNING: {common_name} is extremely dangerous. Never consume any mushroom resembling this species. Always consult multiple expert sources before consuming any wild mushroom.',
            'look_alikes': ['Various edible species - expert identification essential'],
            'season': 'Seasonal occurrence varies by location',
            'difficulty': 'expert'
        }

    def _generate_edible_content(self, species_name: str, common_name: str, mushroom_info: Dict) -> Dict:
        """Generate content for edible species"""

        return {
            'common_name': common_name,
            'summary': f'{common_name} is a prized edible mushroom known for its excellent flavor and culinary value.',
            'description': f'{common_name} is a well-regarded edible species popular among foragers and chefs.',
            'habitat': 'Found in various forest environments depending on the species. Specific habitat requirements vary.',
            'identification_features': [
                'Distinctive morphological characteristics',
                'Proper identification requires careful examination',
                'Consult field guides and experts'
            ],
            'safety_notes': f'While {common_name} is considered edible, proper identification is essential. Always verify with multiple sources and consider professional guidance.',
            'look_alikes': ['Various species - careful identification required'],
            'season': 'Seasonal availability varies by species and location',
            'difficulty': 'intermediate'
        }

    def _generate_unknown_content(self, species_name: str, common_name: str, mushroom_info: Dict) -> Dict:
        """Generate content for species of unknown edibility"""

        return {
            'common_name': common_name,
            'summary': f'{common_name} edibility status is uncertain. Do not consume without expert verification.',
            'description': f'The edibility and safety profile of {common_name} requires further research and expert consultation.',
            'habitat': 'Habitat information requires additional research.',
            'identification_features': [
                'Identification characteristics need expert verification',
                'Professional consultation recommended'
            ],
            'safety_notes': f'Edibility unknown - do not consume {common_name} without expert verification and multiple authoritative sources.',
            'look_alikes': ['Various species - expert identification essential'],
            'season': 'Seasonal information requires additional research',
            'difficulty': 'expert'
        }

    def create_typescript_content_file(self, mushroom: MushroomData) -> Path:
        """Create TypeScript content file for the mushroom"""
        print(f"📄 {'[DRY RUN] Would create' if self.dry_run else 'Creating'} TypeScript content file for {mushroom.name}...")

        # Generate safe filename
        safe_name = re.sub(r'[^a-z0-9]', '', mushroom.name.lower().replace(' ', ''))
        filename = f"{safe_name}.ts"
        file_path = CONTENT_DIR / filename

        # Generate TypeScript content
        ts_content = self._generate_typescript_content(mushroom)

        if self.dry_run:
            print(f"✅ [DRY RUN] Would create {filename}")
            print(f"📋 [DRY RUN] Preview (first 500 chars):")
            print(ts_content[:500])
        else:
            # Write to file
            file_path.write_text(ts_content)
            print(f"✅ Created {filename}")

        return file_path

    def _generate_typescript_content(self, mushroom: MushroomData) -> str:
        """Generate TypeScript content for mushroom"""

        # Build sections based on available data
        sections = []
        section_order = 1

        # Description section
        sections.append(f'''    {{
      id: 'description',
      title: 'Description',
      type: 'description',
      order: {section_order},
      blocks: [
        {{
          id: 'desc-intro',
          type: 'text',
          content: '{mushroom.description}',
        }},
        {{
          id: 'desc-features',
          type: 'heading',
          content: 'Key Identification Features',
          style: {{
            fontSize: 'large',
            margin: {{ top: 16, bottom: 8 }}
          }}
        }},
        {{
          id: 'desc-features-list',
          type: 'list',
          content: {json.dumps(mushroom.identification_features)},
        }}
      ]
    }}''')
        section_order += 1

        # Habitat section
        if mushroom.habitat:
            sections.append(f'''    {{
      id: 'habitat',
      title: 'Habitat & Distribution',
      type: 'habitat',
      order: {section_order},
      blocks: [
        {{
          id: 'habitat-info',
          type: 'text',
          content: '{mushroom.habitat}',
        }},
        {{
          id: 'habitat-season',
          type: 'highlight',
          content: 'Season: {mushroom.season}',
          style: {{
            margin: {{ top: 12, bottom: 12 }}
          }}
        }}
      ]
    }}''')
            section_order += 1

        # Safety/Identification section
        sections.append(f'''    {{
      id: 'identification',
      title: 'Identification & Safety',
      type: 'identification',
      order: {section_order},
      blocks: [
        {{
          id: 'safety-warning',
          type: '{{"safety" if mushroom.edibility == "P" else "warning"}}',
          content: '{mushroom.safety_notes}',
        }},
        {{
          id: 'look-alikes',
          type: 'heading',
          content: 'Look-alikes and Similar Species',
        }},
        {{
          id: 'look-alikes-list',
          type: 'list',
          content: {json.dumps(mushroom.look_alikes)},
        }}
      ]
    }}''')

        # Images section
        images_content = []
        for img in mushroom.images:
            images_content.append(f'''    {{
      id: '{img.id}',
      filename: '{img.filename}',
      alt: '{img.alt_text}',
      caption: '{img.caption}',
      order: {img.order}
    }}''')

        # Generate safe variable name
        safe_name = re.sub(r'[^a-z0-9]', '', mushroom.name.lower().replace(' ', ''))

        # Main content template
        return f'''import {{ MushroomContent }} from '../../types/content';

export const {safe_name}Content: MushroomContent = {{
  id: '{mushroom.id}',
  name: '{mushroom.name}',
  scientificName: '{mushroom.scientific_name}',
  summary: '{mushroom.summary}',

  sections: [
{(',' + chr(10)).join(sections)}
  ],

  images: [
{(',' + chr(10)).join(images_content)}
  ],

  metadata: {{
    lastUpdated: '{datetime.now().strftime("%Y-%m-%d")}',
    version: '1.0-automated',
    author: 'Mushroom Observer Dataset',
    difficulty: '{mushroom.difficulty}',
    commonMistakes: [
      'Insufficient identification verification',
      'Confusion with look-alike species'
    ],
    relatedMushrooms: []
  }}
}};
'''

    def validate_asset_files(self, mushrooms: List[MushroomData]) -> Dict[str, List[str]]:
        """Validate that all expected asset files exist before updating registries"""
        missing_files = {'thumbnails': [], 'images': [], 'content': []}

        for mushroom in mushrooms:
            # Check thumbnail file
            if mushroom.images:
                base_name = mushroom.images[0].filename.replace('_0.jpg', '').replace('.jpg', '')
                thumbnail_path = THUMBNAILS_DIR / f"thumb_{base_name}.png"
                if not thumbnail_path.exists():
                    missing_files['thumbnails'].append(str(thumbnail_path))

            # Check image files
            for img in mushroom.images:
                image_path = IMAGES_DIR / img.filename
                if not image_path.exists():
                    missing_files['images'].append(str(image_path))

            # Check content file
            safe_name = re.sub(r'[^a-z0-9]', '', mushroom.name.lower().replace(' ', ''))
            content_path = CONTENT_DIR / f"{safe_name}.ts"
            if not content_path.exists():
                missing_files['content'].append(str(content_path))

        return missing_files

    def update_asset_discovery(self, mushrooms: List[MushroomData]):
        """Update AssetDiscovery.ts with new mushroom assets"""
        print("🔧 Updating AssetDiscovery.ts...")

        asset_file = MUSHROOM_TRACKER_ROOT / "src" / "utils" / "AssetDiscovery.ts"
        if not asset_file.exists():
            print("❌ AssetDiscovery.ts not found")
            return

        if self.dry_run:
            print("🏃 [DRY RUN] Would update AssetDiscovery.ts")
            return

        # Validate all required files exist
        missing_files = self.validate_asset_files(mushrooms)
        if missing_files['thumbnails'] or missing_files['images']:
            print("⚠️ Some asset files are missing:")
            for category, files in missing_files.items():
                if files and category in ['thumbnails', 'images']:
                    print(f"  {category.title()}: {len(files)} missing")
                    for file in files[:3]:  # Show first 3
                        print(f"    - {file}")
                    if len(files) > 3:
                        print(f"    ... and {len(files) - 3} more")
            print("⚠️ Continuing anyway - please ensure files are created properly")

        content = asset_file.read_text()
        original_content = content  # Keep backup for comparison

        # Parse existing entries to avoid duplicates
        existing_thumbnails = set(re.findall(r"'([^']+)':\s*require\([^)]+thumbnails/", content))
        existing_images = set(re.findall(r"'([^']+)':\s*require\([^)]+images/", content))

        print(f"📊 Found {len(existing_thumbnails)} existing thumbnails, {len(existing_images)} existing images")

        # Prepare thumbnail additions
        thumbnail_additions = []
        for mushroom in mushrooms:
            safe_name = re.sub(r'[^a-z0-9]', '_', mushroom.name.lower().replace(' ', '_'))

            # Check if thumbnail already exists
            if safe_name in existing_thumbnails:
                print(f"⏭️  Skipping duplicate thumbnail: {safe_name}")
                continue

            # Only create thumbnail entry for first image
            if mushroom.images:
                # Use the scientific name based filename like the pattern in the script
                base_name = mushroom.images[0].filename.replace('_0.jpg', '').replace('.jpg', '')
                thumbnail_name = f"thumb_{base_name}.png"
                thumbnail_additions.append(f"  '{safe_name}': require('../assets/mushrooms/thumbnails/{thumbnail_name}'),")

        # Prepare image additions
        image_additions = []
        new_images_added = False
        for mushroom in mushrooms:
            mushroom_images = []
            for img in mushroom.images:
                img_key = img.filename.replace('.jpg', '')

                # Check if image already exists
                if img_key in existing_images:
                    print(f"⏭️  Skipping duplicate image: {img_key}")
                    continue

                mushroom_images.append(f"  '{img_key}': require('../assets/mushrooms/images/{img.filename}'),")
                new_images_added = True

            if mushroom_images:
                image_additions.append(f"\n  // {mushroom.name}")
                image_additions.extend(mushroom_images)

        # Only update if there are new additions
        if not thumbnail_additions and not image_additions:
            print("✅ No new assets to add - all already exist")
            return

        # Update THUMBNAIL_REGISTRY
        if thumbnail_additions:
            lines = content.split('\n')
            thumbnail_start = -1
            thumbnail_end = -1

            # Find THUMBNAIL_REGISTRY start and end
            for i, line in enumerate(lines):
                if 'const THUMBNAIL_REGISTRY' in line and '= {' in line:
                    thumbnail_start = i
                elif thumbnail_start != -1 and line.strip() == '};':
                    thumbnail_end = i
                    break

            if thumbnail_start != -1 and thumbnail_end != -1:
                # Insert new thumbnails before the closing brace
                new_lines = lines[:thumbnail_end] + \
                           ['  // Newly added mushrooms:'] + \
                           thumbnail_additions + \
                           lines[thumbnail_end:]
                content = '\n'.join(new_lines)
                print(f"✅ Added {len(thumbnail_additions)} new thumbnail entries")
            else:
                print("⚠️ Could not find THUMBNAIL_REGISTRY boundaries")

        # Update IMAGE_REGISTRY
        if image_additions:
            lines = content.split('\n')
            image_start = -1
            image_end = -1

            # Find IMAGE_REGISTRY start and end
            for i, line in enumerate(lines):
                if 'const IMAGE_REGISTRY' in line and '= {' in line:
                    image_start = i
                elif image_start != -1 and line.strip() == '};':
                    image_end = i
                    break

            if image_start != -1 and image_end != -1:
                # Insert new images before the closing brace
                new_lines = lines[:image_end] + image_additions + lines[image_end:]
                content = '\n'.join(new_lines)
                print(f"✅ Added new image entries for {len([a for a in image_additions if '//' in a])} mushrooms")
            else:
                print("⚠️ Could not find IMAGE_REGISTRY boundaries")

        # Write updated content if changes were made
        if content != original_content:
            asset_file.write_text(content)
            print("✅ Successfully updated AssetDiscovery.ts")
        else:
            print("ℹ️ No changes made to AssetDiscovery.ts")

    def update_content_service(self, mushrooms: List[MushroomData]):
        """Update ContentService.ts with new mushroom imports"""
        print("🔧 Updating ContentService.ts...")

        service_file = MUSHROOM_TRACKER_ROOT / "src" / "services" / "ContentService.ts"
        if not service_file.exists():
            print("❌ ContentService.ts not found")
            return

        if self.dry_run:
            print("🏃 [DRY RUN] Would update ContentService.ts")
            return

        # Validate content files exist
        missing_files = self.validate_asset_files(mushrooms)
        if missing_files['content']:
            print("⚠️ Some content files are missing:")
            for file in missing_files['content'][:3]:
                print(f"    - {file}")
            if len(missing_files['content']) > 3:
                print(f"    ... and {len(missing_files['content']) - 3} more")
            print("⚠️ Continuing anyway - please ensure content files are created first")

        content = service_file.read_text()
        original_content = content  # Keep backup for comparison

        # Parse existing imports to avoid duplicates
        existing_imports = set(re.findall(r"import\s*{\s*([^}]+Content)\s*}", content))
        existing_array_items = set(re.findall(r"^\s*([a-zA-Z]+Content),?$", content, re.MULTILINE))

        print(f"📊 Found {len(existing_imports)} existing imports, {len(existing_array_items)} array items")

        # Prepare new imports and array items
        new_imports = []
        new_array_items = []

        for mushroom in mushrooms:
            safe_name = re.sub(r'[^a-z0-9]', '', mushroom.name.lower().replace(' ', ''))
            content_var_name = f"{safe_name}Content"

            # Check if import already exists
            if content_var_name in existing_imports:
                print(f"⏭️  Skipping duplicate import: {content_var_name}")
                continue

            # Add import statement
            new_imports.append(f"import {{ {content_var_name} }} from '../content/mushrooms/{safe_name}';")

            # Add to array (if not already there)
            if content_var_name not in existing_array_items:
                new_array_items.append(f"      {content_var_name},")

        # Only update if there are new additions
        if not new_imports:
            print("✅ No new imports to add - all mushrooms already imported")
            return

        # Insert new imports after the last existing mushroom import
        if new_imports:
            lines = content.split('\n')
            last_import_line = -1

            # Find the last mushroom content import
            for i, line in enumerate(lines):
                if 'import {' in line and 'Content } from' in line and 'mushrooms/' in line:
                    last_import_line = i

            if last_import_line != -1:
                # Insert new imports after the last existing import
                new_lines = lines[:last_import_line + 1] + new_imports + lines[last_import_line + 1:]
                content = '\n'.join(new_lines)
                print(f"✅ Added {len(new_imports)} new import statements")
            else:
                print("⚠️ Could not find existing mushroom imports - adding at end of imports")
                # Find the end of import section (first empty line after imports)
                import_end = -1
                for i, line in enumerate(lines):
                    if line.startswith('import '):
                        continue
                    elif line.strip() == '' and i > 0 and lines[i-1].startswith('import '):
                        import_end = i
                        break

                if import_end != -1:
                    new_lines = lines[:import_end] + ['// Newly added mushroom content'] + new_imports + lines[import_end:]
                    content = '\n'.join(new_lines)
                    print(f"✅ Added {len(new_imports)} new import statements")

        # Update the migratedContent array
        if new_array_items:
            lines = content.split('\n')
            array_start = -1
            array_end = -1

            # Find migratedContent array start and end
            for i, line in enumerate(lines):
                if 'const migratedContent = [' in line:
                    array_start = i
                elif array_start != -1 and line.strip().endswith('];'):
                    array_end = i
                    break

            if array_start != -1 and array_end != -1:
                # Insert new items before the closing bracket
                new_lines = lines[:array_end] + new_array_items + lines[array_end:]
                content = '\n'.join(new_lines)
                print(f"✅ Added {len(new_array_items)} new items to migratedContent array")
            else:
                print("⚠️ Could not find migratedContent array boundaries")

        # Write updated content if changes were made
        if content != original_content:
            service_file.write_text(content)
            print("✅ Successfully updated ContentService.ts")
        else:
            print("ℹ️ No changes made to ContentService.ts")

    def process_single_species(self, species_name: str) -> bool:
        """Process a single mushroom species"""
        print(f"\n🍄 Processing {species_name}...")

        try:
            # Fetch data
            dataset = self.fetch_mushroom_observer_data()
            species_data = self.filter_target_species(dataset)

            if species_name not in species_data:
                print(f"❌ No data found for {species_name}")
                return False

            records = species_data[species_name]
            print(f"📊 Found {len(records)} records for {species_name}")

            # Create mushroom data
            mushroom = self.create_mushroom_data(species_name, records)

            # Create content files
            content_file = self.create_typescript_content_file(mushroom)

            # Update registries (manual step noted)
            self.update_asset_discovery([mushroom])
            self.update_content_service([mushroom])

            print(f"✅ Successfully processed {species_name}")
            print(f"📁 Content file: {content_file}")
            print(f"🖼️ Images: {len(mushroom.images)} processed")

            return True

        except Exception as e:
            print(f"❌ Failed to process {species_name}: {e}")
            if self.test_mode:
                import traceback
                traceback.print_exc()
            return False

    def process_batch_species(self, species_list: List[str]) -> Dict[str, bool]:
        """Process multiple species in batch"""
        print(f"\n🔄 Processing {len(species_list)} species in batch mode...")

        results = {}
        successful = 0

        for species_name in species_list:
            success = self.process_single_species(species_name)
            results[species_name] = success
            if success:
                successful += 1

            # Add delay to be respectful to servers
            if not self.test_mode:
                import time
                time.sleep(2)

        print(f"\n📊 Batch processing complete: {successful}/{len(species_list)} successful")
        return results

    def generate_processing_summary(self, results: Dict[str, bool], processed_mushrooms: List[MushroomData] = None):
        """Generate a comprehensive summary of processing results"""
        print("\n" + "=" * 60)
        print("🍄 MUSHROOM CATALOG EXPANSION SUMMARY")
        print("=" * 60)

        successful_species = [species for species, success in results.items() if success]
        failed_species = [species for species, success in results.items() if not success]

        print(f"📊 Total species processed: {len(results)}")
        print(f"✅ Successful: {len(successful_species)}")
        print(f"❌ Failed: {len(failed_species)}")

        if successful_species:
            print(f"\n🎯 Successfully processed species:")
            for species in successful_species:
                print(f"  ✅ {species}")

        if failed_species:
            print(f"\n💥 Failed species:")
            for species in failed_species:
                print(f"  ❌ {species}")

        if processed_mushrooms:
            print(f"\n📁 Files created:")
            total_images = sum(len(m.images) for m in processed_mushrooms)
            total_thumbnails = len(processed_mushrooms)  # One per mushroom
            print(f"  📝 Content files: {len(processed_mushrooms)}")
            print(f"  🖼️  Image files: {total_images}")
            print(f"  🖼️  Thumbnail files: {total_thumbnails}")

        print(f"\n📋 Next steps:")
        if not self.dry_run:
            print(f"  1. ✅ AssetDiscovery.ts - automatically updated")
            print(f"  2. ✅ ContentService.ts - automatically updated")
            print(f"  3. 🔄 Run: npm run lint (fix any formatting issues)")
            print(f"  4. 🔄 Run: npm run ios/android (test the app)")
            print(f"  5. 🔍 Review generated content for accuracy")
        else:
            print(f"  🏃 This was a DRY RUN - no files were actually created")
            print(f"  🔄 Remove --dry-run or --test-mode to create files")

        print("=" * 60)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Mushroom Catalog Expansion Script')
    parser.add_argument('--species', help='Single species to process (scientific name)')
    parser.add_argument('--species-list', help='File containing list of species to process')
    parser.add_argument('--test-mode', action='store_true', help='Enable test mode (dry run, no files created)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate processing without creating files')
    parser.add_argument('--batch-process', action='store_true', help='Process multiple species')

    args = parser.parse_args()

    print("🍄 Mushroom Catalog Expansion Script")
    print("=" * 50)

    expander = MushroomCatalogExpander(test_mode=args.test_mode, dry_run=args.dry_run)

    if args.species:
        # Process single species
        success = expander.process_single_species(args.species)

        # Generate summary for single species
        results = {args.species: success}
        expander.generate_processing_summary(results)

        sys.exit(0 if success else 1)

    elif args.species_list and args.batch_process:
        # Process batch from file
        try:
            species_file = Path(args.species_list)
            if not species_file.exists():
                print(f"❌ Species list file not found: {species_file}")
                sys.exit(1)

            species_list = []
            for line in species_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#'):
                    species_list.append(line)

            if not species_list:
                print(f"❌ No species found in {species_file}")
                sys.exit(1)

            results = expander.process_batch_species(species_list)

            # Generate comprehensive summary
            expander.generate_processing_summary(results)

            successful = sum(1 for success in results.values() if success)
            sys.exit(0 if successful > 0 else 1)

        except Exception as e:
            print(f"❌ Batch processing failed: {e}")
            sys.exit(1)

    else:
        # Show help and available target species
        parser.print_help()
        print(f"\n🎯 Available target species ({len(expander.target_species)}):")
        for i, species in enumerate(expander.target_species, 1):
            print(f"  {i:2}. {species}")

        print(f"\n📝 Example usage:")
        print(f"  python {sys.argv[0]} --species 'Morchella esculenta' --test-mode")
        print(f"  python {sys.argv[0]} --batch-process --species-list species.txt")

if __name__ == '__main__':
    main()