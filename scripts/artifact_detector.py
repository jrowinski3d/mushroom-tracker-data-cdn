#!/usr/bin/env python3
"""
Artifact Detector

Detects images with plastic bags, rulers, hands, paper, and other non-mushroom artifacts.
Uses multiple detection methods to identify problematic images.

Usage:
    python3 scripts/artifact_detector.py [--replace]
"""

import argparse
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List
import json

from image_quality_scorer import ImageQualityScorer


class ArtifactDetector:
    """Detects artifacts in mushroom images."""

    def __init__(self):
        self.scorer = ImageQualityScorer()
        self.species_base = Path("species")

    def detect_artifacts(self, image_path: Path) -> Dict:
        """
        Detect various artifacts in an image.

        Returns dict with artifact scores and flags.
        """
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                return {"error": "Failed to load image"}

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 1. White region detection (plastic bags, paper)
            _, white_mask = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY)
            white_ratio = np.sum(white_mask > 0) / white_mask.size

            # 2. Extremely bright regions (overexposed, flash on plastic)
            _, extreme_white = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)
            extreme_white_ratio = np.sum(extreme_white > 0) / extreme_white.size

            # 3. Check for low color saturation (washed out, in bags)
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            saturation = hsv[:, :, 1]
            low_sat_ratio = np.sum(saturation < 30) / saturation.size

            # 4. Check for rectangular edges (rulers, paper, clipboards)
            edges = cv2.Canny(gray, 50, 150)
            # Use Hough line detection
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=50, minLineLength=50, maxLineGap=10)
            has_many_lines = lines is not None and len(lines) > 20

            # 5. Check for very uniform regions (solid backgrounds)
            # Calculate local standard deviation
            kernel_size = 15
            mean = cv2.blur(gray.astype(float), (kernel_size, kernel_size))
            sqr_mean = cv2.blur((gray.astype(float))**2, (kernel_size, kernel_size))
            variance = sqr_mean - mean**2
            std_dev = np.sqrt(np.abs(variance))
            uniform_ratio = np.sum(std_dev < 10) / std_dev.size

            # 6. Color distribution (bags often have limited colors)
            color_variance = np.mean([
                np.var(image[:, :, 0]),
                np.var(image[:, :, 1]),
                np.var(image[:, :, 2])
            ])

            # Calculate artifact score (0-100, higher = more artifacts)
            artifact_score = 0
            flags = []

            if white_ratio > 0.25:
                artifact_score += 30
                flags.append(f"HIGH white regions ({white_ratio:.1%})")
            elif white_ratio > 0.15:
                artifact_score += 15
                flags.append(f"MODERATE white regions ({white_ratio:.1%})")

            if extreme_white_ratio > 0.1:
                artifact_score += 20
                flags.append(f"Extreme brightness ({extreme_white_ratio:.1%})")

            if low_sat_ratio > 0.4:
                artifact_score += 20
                flags.append(f"Low saturation ({low_sat_ratio:.1%})")

            if has_many_lines:
                artifact_score += 15
                flags.append(f"Many straight lines (ruler/paper?)")

            if uniform_ratio > 0.5:
                artifact_score += 10
                flags.append(f"Uniform background ({uniform_ratio:.1%})")

            if color_variance < 500:
                artifact_score += 10
                flags.append(f"Limited colors ({color_variance:.0f})")

            return {
                "artifact_score": min(artifact_score, 100),
                "flags": flags,
                "metrics": {
                    "white_ratio": white_ratio,
                    "extreme_white_ratio": extreme_white_ratio,
                    "low_saturation_ratio": low_sat_ratio,
                    "has_many_lines": has_many_lines,
                    "uniform_ratio": uniform_ratio,
                    "color_variance": color_variance
                }
            }

        except Exception as e:
            return {"error": str(e)}

    def scan_all_images(self, min_artifact_score: int = 30) -> List[Dict]:
        """Scan all images and find those with artifacts."""
        print("=" * 70)
        print("ARTIFACT DETECTOR")
        print("=" * 70)
        print()

        problematic = []
        total_scanned = 0

        for species_dir in sorted(self.species_base.iterdir()):
            if not species_dir.is_dir():
                continue

            species_id = species_dir.name

            # Check all images
            for img_name in ["thumb.webp", "image_0.webp", "image_1.webp"]:
                img_path = species_dir / img_name
                if not img_path.exists():
                    continue

                total_scanned += 1

                # Run both quality scorer and artifact detector
                quality_result = self.scorer.analyze_image(img_path)
                artifact_result = self.detect_artifacts(img_path)

                if "error" in artifact_result:
                    continue

                artifact_score = artifact_result["artifact_score"]
                quality_score = quality_result.get("overall_score", 100)

                # Flag if high artifacts OR (moderate artifacts AND low quality)
                is_problematic = (
                    artifact_score >= min_artifact_score or
                    (artifact_score >= 20 and quality_score < 70)
                )

                if is_problematic:
                    # Load metadata for scientific name
                    try:
                        with open(species_dir / "metadata.json") as f:
                            metadata = json.load(f)
                            sci_name = metadata['scientific_name']
                    except:
                        sci_name = "Unknown"

                    problematic.append({
                        "species_id": species_id,
                        "scientific_name": sci_name,
                        "image_type": img_name.replace(".webp", ""),
                        "artifact_score": artifact_score,
                        "quality_score": quality_score,
                        "flags": artifact_result["flags"],
                        "path": str(img_path)
                    })

        print(f"Scanned {total_scanned} images")
        print(f"Found {len(problematic)} images with artifacts (score >= {min_artifact_score})\n")

        return sorted(problematic, key=lambda x: x["artifact_score"], reverse=True)

    def generate_report(self, problematic: List[Dict]):
        """Generate a detailed report of problematic images."""
        if not problematic:
            print("✓ No problematic images found!")
            return

        print("=" * 70)
        print(f"PROBLEMATIC IMAGES ({len(problematic)} found)")
        print("=" * 70)
        print()

        # Group by severity
        severe = [p for p in problematic if p["artifact_score"] >= 50]
        moderate = [p for p in problematic if 30 <= p["artifact_score"] < 50]
        mild = [p for p in problematic if p["artifact_score"] < 30]

        if severe:
            print(f"🔴 SEVERE ({len(severe)} images) - Likely plastic bags/paper:")
            print("-" * 70)
            for p in severe[:10]:
                print(f"\n{p['species_id']}/{p['image_type']}")
                print(f"  Scientific name: {p['scientific_name']}")
                print(f"  Artifact score: {p['artifact_score']}")
                print(f"  Quality score: {p['quality_score']}")
                print(f"  Flags: {', '.join(p['flags'])}")
            if len(severe) > 10:
                print(f"\n  ... and {len(severe) - 10} more severe cases")

        if moderate:
            print(f"\n🟡 MODERATE ({len(moderate)} images) - May have artifacts:")
            print("-" * 70)
            for p in moderate[:5]:
                print(f"  • {p['species_id']}/{p['image_type']} - Score: {p['artifact_score']}, Quality: {p['quality_score']}")
            if len(moderate) > 5:
                print(f"  ... and {len(moderate) - 5} more moderate cases")

        if mild:
            print(f"\n🟢 MILD ({len(mild)} images) - Minor issues:")
            print(f"  {len(mild)} images with minor artifact indicators")

        # Group by species
        by_species = {}
        for p in problematic:
            sid = p['species_id']
            if sid not in by_species:
                by_species[sid] = []
            by_species[sid].append(p)

        multi_image_species = {k: v for k, v in by_species.items() if len(v) >= 2}

        if multi_image_species:
            print(f"\n" + "=" * 70)
            print(f"SPECIES WITH MULTIPLE PROBLEMATIC IMAGES ({len(multi_image_species)})")
            print("=" * 70)
            for species_id, images in sorted(multi_image_species.items(),
                                            key=lambda x: len(x[1]), reverse=True):
                print(f"\n{species_id} ({images[0]['scientific_name']}):")
                for img in images:
                    print(f"  • {img['image_type']}: artifact={img['artifact_score']}, quality={img['quality_score']}")

        # Save detailed report
        report_file = Path("scripts/artifact_report.json")
        with open(report_file, 'w') as f:
            json.dump(problematic, f, indent=2)

        print(f"\n{'=' * 70}")
        print(f"📄 Detailed report saved to: {report_file}")
        print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Detect images with artifacts")
    parser.add_argument("--min-score", type=int, default=30,
                       help="Minimum artifact score to flag (default: 30)")
    parser.add_argument("--replace", action="store_true",
                       help="Replace problematic images (not implemented yet)")

    args = parser.parse_args()

    detector = ArtifactDetector()
    problematic = detector.scan_all_images(min_artifact_score=args.min_score)
    detector.generate_report(problematic)

    if args.replace:
        print("\n⚠️  Replacement feature coming next!")
        print("   Will integrate with replace_poor_images.py")


if __name__ == "__main__":
    main()
