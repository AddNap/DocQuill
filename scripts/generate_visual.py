#!/usr/bin/env python3
"""Generate visual comparison between PDF compiler output and LibreOffice reference."""

from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image
import numpy as np
from skimage.metrics import structural_similarity

# Paths
output_pdf = Path('output/Zapytanie_Ofertowe_pdfcompiler.pdf')
reference_pdf = Path('output/Zapytanie_Ofertowe_libre.pdf')

print("Converting PDFs to images...")
try:
    output_pages = convert_from_path(str(output_pdf), dpi=150)
    reference_pages = convert_from_path(str(reference_pdf), dpi=150)
except Exception as e:
    print(f"Error converting PDFs: {e}")
    exit(1)

print(f"Output PDF: {len(output_pages)} pages")
print(f"Reference PDF: {len(reference_pages)} pages")

# Compare first page (with footer images) in detail
print("\n=== Detailed Page 1 Comparison ===")
ref_img = reference_pages[0]
out_img = output_pages[0]

# Resize if needed
try:
    RESAMPLE_LANCZOS = Image.Resampling.LANCZOS
except AttributeError:
    RESAMPLE_LANCZOS = Image.LANCZOS

if ref_img.size != out_img.size:
    out_img = out_img.resize(ref_img.size, resample=RESAMPLE_LANCZOS)

# Convert to grayscale
gray_ref = ref_img.convert("L")
gray_out = out_img.convert("L")

# Calculate SSIM
arr_ref = np.array(gray_ref)
arr_out = np.array(gray_out)

score, diff = structural_similarity(arr_ref, arr_out, full=True)

print(f"Page 1 SSIM score: {score:.4f}")
print(f"Image size: {ref_img.size}")

# Save diff image highlighting differences
diff_map = (1.0 - diff) * 255.0
diff_img = Image.fromarray(diff_map.astype("uint8"), mode="L").convert("RGB")
diff_path = Path('output/visual_diff_page1.png')
diff_img.save(diff_path)
print(f"Detailed diff saved to: {diff_path}")

# Save side-by-side comparison
combined = Image.new('RGB', (ref_img.width * 2, ref_img.height))
combined.paste(ref_img, (0, 0))
combined.paste(out_img, (ref_img.width, 0))
combined_path = Path('output/visual_comparison_page1.png')
combined.save(combined_path)
print(f"Side-by-side comparison saved to: {combined_path}")

# Check footer area specifically (bottom 25% of page)
footer_start = int(ref_img.height * 0.75)
footer_ref = arr_ref[footer_start:, :]
footer_out = arr_out[footer_start:, :]

footer_score, _ = structural_similarity(footer_ref, footer_out, full=True)
print(f"\nFooter area (bottom 25%) SSIM: {footer_score:.4f}")

if footer_score < 0.99:
    print("⚠️  Footer area differs - checking image positions")
else:
    print("✓ Footer area matches well")

# Compare all pages
print("\n=== All Pages Comparison ===")
for idx in range(min(len(reference_pages), len(output_pages))):
    ref_img = reference_pages[idx]
    out_img = output_pages[idx]
    
    if ref_img.size != out_img.size:
        out_img = out_img.resize(ref_img.size, resample=RESAMPLE_LANCZOS)
    
    gray_ref = ref_img.convert("L")
    gray_out = out_img.convert("L")
    
    arr_ref = np.array(gray_ref)
    arr_out = np.array(gray_out)
    
    score, _ = structural_similarity(arr_ref, arr_out, full=True)
    
    print(f"Page {idx+1}: SSIM = {score:.4f}", end="")
    if score < 0.99:
        print(" ⚠️")
    else:
        print(" ✓")

print("\n=== Comparison complete ===")
print(f"Diff images saved:")
print(f"  - {diff_path}")
print(f"  - {combined_path}")

