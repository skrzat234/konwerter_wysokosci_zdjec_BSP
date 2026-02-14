
from PIL import Image
import piexif

img_path = r"C:\FIRMA\MATRICE 4E\FOTOGRAMETRIA\test112m\testtest\DJI_20251025145114_0001_V.JPG"

exif_dict = piexif.load(img_path)

for ifd_name in exif_dict:
    print(f"\n--- {ifd_name} ---")
    for tag_id, value in exif_dict[ifd_name].items():
        tag_name = piexif.TAGS[ifd_name].get(tag_id, {}).get("name", f"Unknown({tag_id})")
        print(f"{tag_name}: {value}")
