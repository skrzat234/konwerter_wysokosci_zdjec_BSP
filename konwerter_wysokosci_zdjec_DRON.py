import os
import shutil
import piexif
import numpy as np
from scipy.interpolate import RegularGridInterpolator

# --- Folder ze zdjęciami (oryginalny) ---
img_folder = r"C:\FIRMA\MATRICE 4E\FOTOGRAMETRIA\test2"

# --- Nowy folder: katalog wyżej + "_converted_H" ---
parent_folder = os.path.dirname(img_folder)
folder_name = os.path.basename(img_folder)
converted_folder = os.path.join(parent_folder, f"{folder_name}_converted_H")

# --- Tworzymy folder, jeśli nie istnieje ---
os.makedirs(converted_folder, exist_ok=True)

# --- Kopiujemy tylko pliki .JPG do nowego folderu ---
for f in os.listdir(img_folder):
    if f.lower().endswith(".jpg"):
        src = os.path.join(img_folder, f)
        dst = os.path.join(converted_folder, f)
        shutil.copy2(src, dst)

print(f"Skopiowano pliki JPG do: {converted_folder}")

# --- Wczytanie modelu geoidy ---
geoid_file = r"C:\coding_VSC\11_konwerterWysokosci_elipsodal-NH\model obowiazujacej quasi-geoidy PL-geoid2021 w ukladzie PL-EVRF2007-NH.txt"
data = np.loadtxt(geoid_file, skiprows=1)

lats_unique = np.unique(data[:,0])
lons_unique = np.unique(data[:,1])
zeta_grid = data[:,2].reshape(len(lats_unique), len(lons_unique))

geoid_interp = RegularGridInterpolator((lats_unique, lons_unique), zeta_grid)

# --- Funkcje pomocnicze ---
def dms_to_deg(dms, ref):
    deg = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1]
    seconds = dms[2][0] / dms[2][1]
    dec = deg + minutes/60 + seconds/3600
    if ref in ['S', 'W']:
        dec = -dec
    return dec

def read_gps(exif_dict):
    gps_ifd = exif_dict.get('GPS', {})
    lat, lon, alt = None, None, None

    if piexif.GPSIFD.GPSLatitude in gps_ifd and piexif.GPSIFD.GPSLatitudeRef in gps_ifd:
        lat = dms_to_deg(
            gps_ifd[piexif.GPSIFD.GPSLatitude],
            gps_ifd[piexif.GPSIFD.GPSLatitudeRef].decode()
        )

    if piexif.GPSIFD.GPSLongitude in gps_ifd and piexif.GPSIFD.GPSLongitudeRef in gps_ifd:
        lon = dms_to_deg(
            gps_ifd[piexif.GPSIFD.GPSLongitude],
            gps_ifd[piexif.GPSIFD.GPSLongitudeRef].decode()
        )

    if piexif.GPSIFD.GPSAltitude in gps_ifd:
        num, den = gps_ifd[piexif.GPSIFD.GPSAltitude]
        alt = num / den

    return lat, lon, alt

# --- Lista zdjęć ---
img_files = [f for f in os.listdir(converted_folder) if f.lower().endswith('.jpg')]

# --- Jeden plik wynikowy ---
txt_output = os.path.join(converted_folder, "0_metadane_konwersji_wysokosci.txt")

with open(txt_output, 'w') as f_out:
    f_out.write("filename,latitude,longitude,H_ellipsoidal,H_evrf2007,diff_H\n")

    for img_file in img_files:
        img_path = os.path.join(converted_folder, img_file)
        exif_dict = piexif.load(img_path)

        lat, lon, alt_ell = read_gps(exif_dict)
        if lat is None or lon is None or alt_ell is None:
            print(f"Brak GPS w {img_file}, pomijam.")
            continue

        alt_geoid = geoid_interp([[lat, lon]])[0]
        alt_evrf = alt_ell - alt_geoid
        diff_h = alt_ell - alt_evrf

        f_out.write(f"{img_file},{lat},{lon},{alt_ell:.3f},{alt_evrf:.3f},{diff_h:.3f}\n")

        gps_ifd = exif_dict.get('GPS', {})
        gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 0
        gps_ifd[piexif.GPSIFD.GPSAltitude] = (int(alt_evrf*1000), 1000)

        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, img_path)

print("Gotowe! Jeden plik TXT zapisany + EXIF zaktualizowany.")
