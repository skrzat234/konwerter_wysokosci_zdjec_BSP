import os
import piexif
import numpy as np
from scipy.interpolate import RegularGridInterpolator

# --- Folder ze zdjęciami ---
img_folder = r"C:\MATRICE 4E\FOTOGRAMETRIA\test"

# --- Wczytanie modelu geoidy ---
geoid_file = r"C:\coding_VSC\11_konwerterWysokosci_elipsodal-NH\Model_quasi-geoidy-PL-geoid2021-PL-EVRF2007-NH.txt"
data = np.loadtxt(geoid_file, skiprows=1)
lats_unique = np.unique(data[:,0])
lons_unique = np.unique(data[:,1])

# zakładamy, że dane są regularną siatką
zeta_grid = data[:,2].reshape(len(lats_unique), len(lons_unique))

# interpolator RegularGridInterpolator (znacznie szybszy niż griddata)
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
        lat = dms_to_deg(gps_ifd[piexif.GPSIFD.GPSLatitude],
                         gps_ifd[piexif.GPSIFD.GPSLatitudeRef].decode())
    if piexif.GPSIFD.GPSLongitude in gps_ifd and piexif.GPSIFD.GPSLongitudeRef in gps_ifd:
        lon = dms_to_deg(gps_ifd[piexif.GPSIFD.GPSLongitude],
                         gps_ifd[piexif.GPSIFD.GPSLongitudeRef].decode())
    if piexif.GPSIFD.GPSAltitude in gps_ifd:
        num, den = gps_ifd[piexif.GPSIFD.GPSAltitude]
        alt = num / den
    return lat, lon, alt

# --- Lista plików JPG w folderze ---
img_files = [f for f in os.listdir(img_folder) if f.lower().endswith('.jpg')]

# --- Pliki tekstowe ---
txt_original = os.path.join(img_folder, "1_metadane_oryginalne.txt")
txt_new = os.path.join(img_folder, "2_metadane_evfr2007.txt")

with open(txt_original, 'w') as f_orig, open(txt_new, 'w') as f_new:
    f_orig.write("filename,latitude,longitude,alt_ellipsoidal\n")
    f_new.write("filename,latitude,longitude,alt_evrf2007\n")
    
    for img_file in img_files:
        img_path = os.path.join(img_folder, img_file)
        exif_dict = piexif.load(img_path)
        
        # odczyt GPS
        lat, lon, alt_ell = read_gps(exif_dict)
        if lat is None or lon is None or alt_ell is None:
            print(f"Brak GPS w {img_file}, pomijam.")
            continue
        
        # zapis oryginalnych metadanych
        f_orig.write(f"{img_file},{lat},{lon},{alt_ell:.3f}\n")
        
        # interpolacja geoidy przez RegularGridInterpolator
        alt_geoid = geoid_interp([[lat, lon]])[0]
        alt_evrf = alt_ell - alt_geoid
        
        # zapis nowych metadanych
        f_new.write(f"{img_file},{lat},{lon},{alt_evrf:.3f}\n")
        
        # nadpisanie GPSAltitude w zdjęciu (bez zmiany pikseli)
        gps_ifd = exif_dict.get('GPS', {})
        gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 0
        gps_ifd[piexif.GPSIFD.GPSAltitude] = (int(alt_evrf*1000), 1000)
        exif_bytes = piexif.dump(exif_dict)
        piexif.insert(exif_bytes, img_path)

print("Gotowe! Wszystkie zdjęcia przeliczone i metadane zapisane.")
