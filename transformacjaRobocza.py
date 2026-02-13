import numpy as np
from scipy.interpolate import griddata

# Wczytanie pliku z geoidą
data = np.loadtxt("C:\\coding_VSC\\11_konwerterWysokosci_elipsodal-NH\\Model_quasi-geoidy-PL-geoid2021-PL-EVRF2007-NH.txt", skiprows=1)  # pomijamy nagłówek
lats = data[:,0]
lons = data[:,1]
zeta = data[:,2]  # geoid height

# Funkcja interpolująca
def geoid_height(lat, lon):
    return griddata(
        points=np.column_stack((lats, lons)),
        values=zeta,
        xi=(lat, lon),
        method='linear'
    )

# Przykładowy punkt WGS84
lat = 53.17328627777778
lon = 23.209174083333334
h_ell = 296.770

# Normalna wysokość EVRF2007-NH
h_normal = h_ell - geoid_height(lat, lon)
print(f"WGS84 ellipsoidal: {h_ell} m --> EVRF2007-NH: {h_normal:.3f} m")
