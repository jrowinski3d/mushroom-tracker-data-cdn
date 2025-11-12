#!/usr/bin/env python3
"""
Image Quality Scorer for Mushroom CDN Images

This script analyzes images using multiple quality metrics:
1. Blur detection (Laplacian variance)
2. Brightness/contrast analysis
3. Color distribution analysis
4. Overall quality score (normalized 0-100, higher is better)

Usage:
    python3 scripts/image_quality_scorer.py
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Tuple
import sys


class ImageQualityScorer:
    """Analyzes image quality using OpenCV-based metrics."""

    def __init__(self):
        # Thresholds for quality assessment
        self.BLUR_THRESHOLD = 100  # Laplacian variance threshold
        self.MIN_BRIGHTNESS = 40
        self.MAX_BRIGHTNESS = 215
        self.MIN_CONTRAST = 30

    def calculate_blur_score(self, image: np.ndarray) -> Tuple[float, str]:
        """
        Calculate sharpness using Laplacian variance.
        Higher values = sharper image.

        Returns:
            (score, rating) where score is the variance and rating is a string
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

        if laplacian_var > 500:
            rating = "excellent"
        elif laplacian_var > 200:
            rating = "good"
        elif laplacian_var > self.BLUR_THRESHOLD:
            rating = "fair"
        else:
            rating = "poor"

        return laplacian_var, rating

    def calculate_brightness_contrast(self, image: np.ndarray) -> Dict:
        """
        Analyze brightness and contrast.

        Returns:
            Dict with mean_brightness, contrast, and ratings
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        mean_brightness = np.mean(gray)
        contrast = np.std(gray)

        # Brightness rating
        if self.MIN_BRIGHTNESS <= mean_brightness <= self.MAX_BRIGHTNESS:
            brightness_rating = "good"
        elif mean_brightness < self.MIN_BRIGHTNESS:
            brightness_rating = "too_dark"
        else:
            brightness_rating = "too_bright"

        # Contrast rating
        if contrast > 50:
            contrast_rating = "excellent"
        elif contrast > self.MIN_CONTRAST:
            contrast_rating = "good"
        else:
            contrast_rating = "poor"

        return {
            "mean_brightness": float(mean_brightness),
            "brightness_rating": brightness_rating,
            "contrast": float(contrast),
            "contrast_rating": contrast_rating
        }

    def calculate_color_distribution(self, image: np.ndarray) -> Dict:
        """
        Analyze color distribution to detect artificial elements.
        Plastic bags, rulers, etc. often have unnatural color distributions.

        Returns:
            Dict with color_variance and rating
        """
        # Calculate color variance in each channel
        b, g, r = cv2.split(image)

        color_variance = np.mean([
            np.var(b),
            np.var(g),
            np.var(r)
        ])

        # Higher variance typically indicates more natural, diverse colors
        if color_variance > 2000:
            rating = "excellent"
        elif color_variance > 1000:
            rating = "good"
        elif color_variance > 500:
            rating = "fair"
        else:
            rating = "poor"

        return {
            "color_variance": float(color_variance),
            "rating": rating
        }

    def detect_white_regions(self, image: np.ndarray) -> Dict:
        """
        Detect large white regions (potential plastic bags, paper, etc.).

        Returns:
            Dict with white_pixel_ratio and rating
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Threshold for white pixels (values > 220)
        _, white_mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
        white_pixel_ratio = np.sum(white_mask > 0) / white_mask.size

        if white_pixel_ratio < 0.1:
            rating = "good"
        elif white_pixel_ratio < 0.25:
            rating = "fair"
        else:
            rating = "poor"  # Likely has plastic bag or white background

        return {
            "white_pixel_ratio": float(white_pixel_ratio),
            "rating": rating
        }

    def calculate_overall_score(self, metrics: Dict) -> int:
        """
        Calculate overall quality score (0-100, higher is better).

        Weights:
        - Blur: 35%
        - Brightness/Contrast: 25%
        - Color Distribution: 25%
        - White Region Detection: 15%
        """
        # Blur score (normalize to 0-100)
        blur_score = min(100, (metrics["blur"]["score"] / 1000) * 100)
        blur_weight = 0.35

        # Brightness score
        brightness = metrics["brightness"]["mean_brightness"]
        if self.MIN_BRIGHTNESS <= brightness <= self.MAX_BRIGHTNESS:
            brightness_score = 100
        else:
            # Penalize images too dark or too bright
            if brightness < self.MIN_BRIGHTNESS:
                brightness_score = max(0, (brightness / self.MIN_BRIGHTNESS) * 100)
            else:
                brightness_score = max(0, 100 - ((brightness - self.MAX_BRIGHTNESS) / 40 * 100))

        # Contrast score (normalize to 0-100)
        contrast_score = min(100, (metrics["brightness"]["contrast"] / 70) * 100)

        # Combined brightness/contrast score
        light_score = (brightness_score * 0.5 + contrast_score * 0.5)
        light_weight = 0.25

        # Color distribution score (normalize to 0-100)
        color_score = min(100, (metrics["color"]["color_variance"] / 3000) * 100)
        color_weight = 0.25

        # White region score (inverse - more white = lower score)
        white_score = max(0, 100 - (metrics["white_regions"]["white_pixel_ratio"] * 200))
        white_weight = 0.15

        # Calculate weighted average
        overall = (
            blur_score * blur_weight +
            light_score * light_weight +
            color_score * color_weight +
            white_score * white_weight
        )

        return int(round(overall))

    def analyze_image(self, image_path: Path) -> Dict:
        """
        Perform complete image quality analysis.

        Returns:
            Dict with all metrics and overall score
        """
        try:
            # Read image
            image = cv2.imread(str(image_path))
            if image is None:
                return {"error": "Failed to load image"}

            # Calculate all metrics
            blur_score, blur_rating = self.calculate_blur_score(image)
            brightness_metrics = self.calculate_brightness_contrast(image)
            color_metrics = self.calculate_color_distribution(image)
            white_region_metrics = self.detect_white_regions(image)

            metrics = {
                "blur": {
                    "score": blur_score,
                    "rating": blur_rating
                },
                "brightness": brightness_metrics,
                "color": color_metrics,
                "white_regions": white_region_metrics
            }

            # Calculate overall score
            overall_score = self.calculate_overall_score(metrics)

            return {
                "file_path": str(image_path),
                "metrics": metrics,
                "overall_score": overall_score,
                "dimensions": {
                    "width": image.shape[1],
                    "height": image.shape[0]
                }
            }

        except Exception as e:
            return {
                "file_path": str(image_path),
                "error": str(e)
            }


def analyze_species_images(species_dir: Path, scorer: ImageQualityScorer) -> List[Dict]:
    """Analyze all images for a single species."""
    results = []

    # Find all image files
    image_files = sorted([
        f for f in species_dir.glob("*.webp")
        if f.name in ["thumb.webp", "image_0.webp", "image_1.webp"]
    ])

    for image_file in image_files:
        result = scorer.analyze_image(image_file)
        result["mushroom_id"] = species_dir.name
        result["image_type"] = image_file.stem  # 'thumb', 'image_0', 'image_1'
        results.append(result)

    return results


def main():
    """Main execution function."""
    print("=" * 70)
    print("MUSHROOM IMAGE QUALITY SCORER")
    print("=" * 70)

    # Initialize scorer
    scorer = ImageQualityScorer()

    # Find all species directories
    species_base = Path("species")
    if not species_base.exists():
        print("\n❌ Error: 'species' directory not found!")
        sys.exit(1)

    species_dirs = sorted([d for d in species_base.iterdir() if d.is_dir()])
    print(f"\nFound {len(species_dirs)} species directories")
    print("Analyzing images...\n")

    # Analyze all images
    all_results = []
    for i, species_dir in enumerate(species_dirs, 1):
        print(f"[{i}/{len(species_dirs)}] Processing {species_dir.name}...", end="\r")
        results = analyze_species_images(species_dir, scorer)
        all_results.extend(results)

    print()  # New line after progress

    # Generate statistics
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)

    total_images = len(all_results)
    images_with_errors = len([r for r in all_results if "error" in r])

    print(f"\nTotal images analyzed: {total_images}")
    print(f"Images with errors: {images_with_errors}")
    print(f"Successfully analyzed: {total_images - images_with_errors}")

    # Score distribution
    scores = [r["overall_score"] for r in all_results if "overall_score" in r]
    if scores:
        print(f"\nOverall Score Statistics:")
        print(f"  Average: {np.mean(scores):.1f}")
        print(f"  Median: {np.median(scores):.1f}")
        print(f"  Min: {min(scores)}")
        print(f"  Max: {max(scores)}")

        # Score distribution
        excellent = len([s for s in scores if s >= 80])
        good = len([s for s in scores if 60 <= s < 80])
        fair = len([s for s in scores if 40 <= s < 60])
        poor = len([s for s in scores if s < 40])

        print(f"\nScore Distribution:")
        print(f"  Excellent (80-100): {excellent} images")
        print(f"  Good (60-79): {good} images")
        print(f"  Fair (40-59): {fair} images")
        print(f"  Poor (0-39): {poor} images")

    # Find worst images (potential candidates for replacement)
    worst_images = sorted(
        [r for r in all_results if "overall_score" in r],
        key=lambda x: x["overall_score"]
    )[:20]

    print(f"\n{'=' * 70}")
    print("TOP 20 LOWEST QUALITY IMAGES (Candidates for Replacement)")
    print("=" * 70)
    for i, img in enumerate(worst_images, 1):
        mushroom_id = img["mushroom_id"]
        image_type = img["image_type"]
        score = img["overall_score"]
        blur = img["metrics"]["blur"]["rating"]
        brightness = img["metrics"]["brightness"]["brightness_rating"]

        print(f"{i:2d}. {mushroom_id}/{image_type:8s} - Score: {score:2d} | "
              f"Blur: {blur:10s} | Brightness: {brightness}")

    # Save detailed results to JSON
    output_file = Path("scripts/image_quality_report.json")
    output_file.parent.mkdir(exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"📄 Detailed report saved to: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
