import os
import shutil
import threading
import tkinter as tk
from queue import Queue, Empty
from tkinter import filedialog, messagebox, ttk

import numpy as np
import piexif
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator, RegularGridInterpolator


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GEOIDS = {
    "EVRF2007 (PL-geoid2021)": os.path.join(
        BASE_DIR,
        "1_model obowiazujacej quasi-geoidy PL-geoid2021 w ukladzie PL-EVRF2007-NH.txt",
    ),
    "KRON86 (gugik-geoid2011)": os.path.join(
        BASE_DIR,
        "2_gugik-geoid2011-PL-KRON86-NH.txt",
    ),
}


def dms_to_deg(dms, ref):
    deg = dms[0][0] / dms[0][1]
    minutes = dms[1][0] / dms[1][1]
    seconds = dms[2][0] / dms[2][1]
    dec = deg + minutes / 60 + seconds / 3600
    if ref in ("S", "W"):
        dec = -dec
    return dec


def read_gps(exif_dict):
    gps_ifd = exif_dict.get("GPS", {})
    lat, lon, alt = None, None, None

    if (
        piexif.GPSIFD.GPSLatitude in gps_ifd
        and piexif.GPSIFD.GPSLatitudeRef in gps_ifd
    ):
        lat_ref = gps_ifd[piexif.GPSIFD.GPSLatitudeRef]
        lat_ref = lat_ref.decode() if isinstance(lat_ref, bytes) else lat_ref
        lat = dms_to_deg(gps_ifd[piexif.GPSIFD.GPSLatitude], lat_ref)

    if (
        piexif.GPSIFD.GPSLongitude in gps_ifd
        and piexif.GPSIFD.GPSLongitudeRef in gps_ifd
    ):
        lon_ref = gps_ifd[piexif.GPSIFD.GPSLongitudeRef]
        lon_ref = lon_ref.decode() if isinstance(lon_ref, bytes) else lon_ref
        lon = dms_to_deg(gps_ifd[piexif.GPSIFD.GPSLongitude], lon_ref)

    if piexif.GPSIFD.GPSAltitude in gps_ifd:
        num, den = gps_ifd[piexif.GPSIFD.GPSAltitude]
        alt = num / den
        alt_ref = gps_ifd.get(piexif.GPSIFD.GPSAltitudeRef, 0)
        if alt_ref == 1:
            alt = -alt

    return lat, lon, alt


def load_geoid_interpolator(geoid_file):
    data = np.loadtxt(geoid_file, skiprows=1)
    lats_unique = np.unique(data[:, 0])
    lons_unique = np.unique(data[:, 1])
    if len(lats_unique) * len(lons_unique) == data.shape[0]:
        zeta_grid = data[:, 2].reshape(len(lats_unique), len(lons_unique))
        regular_interp = RegularGridInterpolator(
            (lats_unique, lons_unique),
            zeta_grid,
            bounds_error=False,
            fill_value=np.nan,
        )
        return regular_interp, "regular_grid"

    points = data[:, :2]
    values = data[:, 2]
    linear_interp = LinearNDInterpolator(points, values, fill_value=np.nan)
    nearest_interp = NearestNDInterpolator(points, values)
    lat_min, lat_max = np.min(points[:, 0]), np.max(points[:, 0])
    lon_min, lon_max = np.min(points[:, 1]), np.max(points[:, 1])

    def scattered_interp(query_points):
        query_points = np.asarray(query_points, dtype=float)
        result = np.asarray(linear_interp(query_points), dtype=float)
        nan_mask = np.isnan(result)
        if np.any(nan_mask):
            nan_points = query_points[nan_mask]
            inside_bbox = (
                (nan_points[:, 0] >= lat_min)
                & (nan_points[:, 0] <= lat_max)
                & (nan_points[:, 1] >= lon_min)
                & (nan_points[:, 1] <= lon_max)
            )
            if np.any(inside_bbox):
                fill_points = nan_points[inside_bbox]
                filled = np.asarray(nearest_interp(fill_points), dtype=float)
                result_idx = np.where(nan_mask)[0][inside_bbox]
                result[result_idx] = filled
        return result

    return scattered_interp, "scattered_points"


def infer_conversion_target(geoid_file):
    name = os.path.basename(geoid_file).lower()
    if "evrf" in name:
        return "elipsoidalne->EVRF2007"
    if "kron86" in name or "kron" in name:
        return "elipsoidalne->KRON86"
    return "elipsoidalne->NIEZNANY_UKLAD"


def infer_output_suffix(conversion_target):
    if conversion_target.endswith("EVRF2007"):
        return "converted_to_evrf2007"
    if conversion_target.endswith("KRON86"):
        return "converted_to_kron86"
    return "converted_to_unknown"


class HeightConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Konwerter wysokosci EXIF (dron)")
        self.root.geometry("840x500")

        self.worker_thread = None
        self.queue = Queue()

        self.img_folder_var = tk.StringVar()
        self.geoid_choice_var = tk.StringVar(value=list(DEFAULT_GEOIDS.keys())[0])
        self.geoid_file_var = tk.StringVar(value=DEFAULT_GEOIDS[self.geoid_choice_var.get()])
        self.progress_var = tk.IntVar(value=0)
        self.status_var = tk.StringVar(value="Gotowe do pracy")

        self._build_ui()
        self.root.after(100, self._process_queue)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Folder ze zdjeciami (.jpg/.jpeg):").grid(
            row=0, column=0, sticky="w", pady=(0, 4)
        )
        img_row = ttk.Frame(main)
        img_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))
        img_row.columnconfigure(0, weight=1)
        self.img_entry = ttk.Entry(img_row, textvariable=self.img_folder_var)
        self.img_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.img_btn = ttk.Button(img_row, text="Wybierz folder", command=self.pick_img_folder)
        self.img_btn.grid(row=0, column=1)

        ttk.Label(main, text="Model geoidy:").grid(row=2, column=0, sticky="w", pady=(0, 4))
        self.geoid_combo = ttk.Combobox(
            main,
            textvariable=self.geoid_choice_var,
            values=list(DEFAULT_GEOIDS.keys()),
            state="readonly",
        )
        self.geoid_combo.grid(row=3, column=0, sticky="ew", padx=(0, 8))
        self.geoid_combo.bind("<<ComboboxSelected>>", self.on_geoid_choice_changed)

        self.preset_btn = ttk.Button(main, text="Uzyj presetu", command=self.apply_geoid_preset)
        self.preset_btn.grid(row=3, column=1, sticky="w", padx=(0, 8))
        self.geoid_btn = ttk.Button(main, text="Wybierz plik geoidy", command=self.pick_geoid_file)
        self.geoid_btn.grid(row=3, column=2, sticky="w")

        ttk.Label(main, text="Sciezka pliku geoidy (.txt):").grid(
            row=4, column=0, sticky="w", pady=(10, 4)
        )
        self.geoid_entry = ttk.Entry(main, textvariable=self.geoid_file_var)
        self.geoid_entry.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        self.start_btn = ttk.Button(main, text="Start", command=self.start_conversion)
        self.start_btn.grid(row=6, column=0, sticky="w", pady=(0, 10))

        self.progress = ttk.Progressbar(
            main, orient="horizontal", mode="determinate", variable=self.progress_var
        )
        self.progress.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, 6))

        self.status_label = ttk.Label(main, textvariable=self.status_var)
        self.status_label.grid(row=8, column=0, columnspan=3, sticky="w", pady=(0, 8))

        ttk.Label(main, text="Log:").grid(row=9, column=0, sticky="w")
        self.log_box = tk.Text(main, height=14, wrap="word")
        self.log_box.grid(row=10, column=0, columnspan=3, sticky="nsew")

        main.columnconfigure(0, weight=1)
        main.rowconfigure(10, weight=1)

    def on_geoid_choice_changed(self, _event=None):
        self.apply_geoid_preset()

    def apply_geoid_preset(self):
        chosen = self.geoid_choice_var.get()
        preset_path = DEFAULT_GEOIDS.get(chosen)
        if preset_path:
            self.geoid_file_var.set(preset_path)

    def pick_img_folder(self):
        selected = filedialog.askdirectory(title="Wybierz folder ze zdjeciami")
        if selected:
            self.img_folder_var.set(selected)

    def pick_geoid_file(self):
        selected = filedialog.askopenfilename(
            title="Wybierz plik geoidy",
            filetypes=[("Pliki tekstowe", "*.txt"), ("Wszystkie pliki", "*.*")],
        )
        if selected:
            self.geoid_file_var.set(selected)

    def set_ui_busy(self, busy):
        state = "disabled" if busy else "normal"
        combo_state = "disabled" if busy else "readonly"
        self.img_entry.configure(state=state)
        self.img_btn.configure(state=state)
        self.geoid_combo.configure(state=combo_state)
        self.preset_btn.configure(state=state)
        self.geoid_entry.configure(state=state)
        self.geoid_btn.configure(state=state)
        self.start_btn.configure(state=state)

    def log(self, text):
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")

    def build_final_report(self, processed, conversion_target):
        return (
            "Przetwarzanie zakonczone z powodzeniem.\n"
            "\n"
            f"Zdjecia przetworzone z powodzeniem: {processed}\n"
            f"Postprocessing: {conversion_target}"
        )

    def start_conversion(self):
        img_folder = self.img_folder_var.get().strip()
        geoid_file = self.geoid_file_var.get().strip()

        if not img_folder or not os.path.isdir(img_folder):
            messagebox.showerror("Blad", "Wskaz poprawny folder ze zdjeciami.")
            return
        if not geoid_file or not os.path.isfile(geoid_file):
            messagebox.showerror("Blad", "Wskaz poprawny plik geoidy (.txt).")
            return
        if self.worker_thread and self.worker_thread.is_alive():
            messagebox.showwarning("Info", "Przetwarzanie juz trwa.")
            return

        self.log_box.delete("1.0", "end")
        self.progress_var.set(0)
        self.progress.configure(maximum=1)
        self.status_var.set("Start przetwarzania...")
        self.set_ui_busy(True)

        self.worker_thread = threading.Thread(
            target=self.run_conversion,
            args=(img_folder, geoid_file),
            daemon=True,
        )
        self.worker_thread.start()

    def run_conversion(self, img_folder, geoid_file):
        try:
            geoid_interp, interp_mode = load_geoid_interpolator(geoid_file)
            self.queue.put(("log", f"Model geoidy: {geoid_file}"))
            self.queue.put(("log", f"Tryb interpolacji: {interp_mode}"))
            conversion_target = infer_conversion_target(geoid_file)

            parent_folder = os.path.dirname(img_folder)
            folder_name = os.path.basename(img_folder.rstrip("\\/"))
            output_suffix = infer_output_suffix(conversion_target)
            converted_folder = os.path.join(parent_folder, f"{folder_name}_{output_suffix}")
            os.makedirs(converted_folder, exist_ok=True)
            self.queue.put(("log", f"Folder wynikowy: {converted_folder}"))

            img_files = [
                f for f in os.listdir(img_folder) if f.lower().endswith((".jpg", ".jpeg"))
            ]
            total = len(img_files)
            if total == 0:
                self.queue.put(("done_error", "Brak plikow JPG/JPEG w wybranym folderze."))
                return

            self.queue.put(("progress_max", total))
            self.queue.put(("status", f"Kopiowanie {total} zdjec..."))

            for index, file_name in enumerate(img_files, start=1):
                src = os.path.join(img_folder, file_name)
                dst = os.path.join(converted_folder, file_name)
                shutil.copy2(src, dst)
                self.queue.put(("progress", index))

            self.queue.put(("status", "Przeliczanie wysokosci i aktualizacja EXIF..."))
            txt_output = os.path.join(converted_folder, "0_lista_H_oryg_i_conv.txt")

            processed = 0
            skipped = 0

            with open(txt_output, "w", encoding="utf-8") as f_out:
                f_out.write(f"# konwersja: {conversion_target}\n")
                f_out.write(f"# model_geoidy: {os.path.basename(geoid_file)}\n")
                f_out.write(
                    "filename,latitude,longitude,H_elipsoidalne,H_wynikowe,roznica_H\n"
                )

                for index, img_file in enumerate(img_files, start=1):
                    img_path = os.path.join(converted_folder, img_file)
                    exif_dict = piexif.load(img_path)

                    lat, lon, alt_ell = read_gps(exif_dict)
                    if lat is None or lon is None or alt_ell is None:
                        skipped += 1
                        self.queue.put(("log", f"Brak GPS w {img_file}; pomijam."))
                        self.queue.put(("progress", index))
                        continue

                    alt_geoid = float(geoid_interp([[lat, lon]])[0])
                    if np.isnan(alt_geoid):
                        skipped += 1
                        self.queue.put(
                            (
                                "log",
                                f"Punkt poza zakresem modelu geoidy dla {img_file}; pomijam.",
                            )
                        )
                        self.queue.put(("progress", index))
                        continue

                    alt_wyn = alt_ell - alt_geoid
                    diff_h = alt_ell - alt_wyn

                    f_out.write(
                        f"{img_file},{lat:.8f},{lon:.8f},{alt_ell:.3f},{alt_wyn:.3f},{diff_h:.3f}\n"
                    )

                    gps_ifd = exif_dict.get("GPS", {})
                    gps_ifd[piexif.GPSIFD.GPSAltitudeRef] = 1 if alt_wyn < 0 else 0
                    gps_ifd[piexif.GPSIFD.GPSAltitude] = (int(round(abs(alt_wyn) * 1000)), 1000)
                    exif_dict["GPS"] = gps_ifd

                    exif_bytes = piexif.dump(exif_dict)
                    piexif.insert(exif_bytes, img_path)

                    processed += 1
                    self.queue.put(("progress", index))

            self.queue.put(
                (
                    "done_ok",
                    (
                        total,
                        processed,
                        skipped,
                        conversion_target,
                        geoid_file,
                        txt_output,
                        converted_folder,
                    ),
                )
            )
        except Exception as exc:
            self.queue.put(("done_error", f"Wystapil blad: {exc}"))

    def _process_queue(self):
        try:
            while True:
                kind, payload = self.queue.get_nowait()

                if kind == "log":
                    self.log(payload)
                elif kind == "status":
                    self.status_var.set(payload)
                elif kind == "progress":
                    self.progress_var.set(payload)
                elif kind == "progress_max":
                    self.progress.configure(maximum=payload)
                    self.progress_var.set(0)
                elif kind == "done_ok":
                    total, processed, skipped, conversion_target, geoid_file, txt_output, converted_folder = payload
                    report = self.build_final_report(processed, conversion_target)
                    self.status_var.set(
                        f"Gotowe. Przetworzone: {processed}/{total}, pominiete: {skipped}."
                    )
                    self.log(
                        f"Podsumowanie: przetworzone={processed}, pominiete={skipped}, "
                        f"postprocessing={conversion_target}, model={os.path.basename(geoid_file)}"
                    )
                    self.log(f"Raport TXT: {txt_output}")
                    self.log(f"Folder wynikowy: {converted_folder}")
                    self.set_ui_busy(False)
                    messagebox.showinfo("Koniec", report)
                elif kind == "done_error":
                    self.status_var.set("Przerwano przez blad.")
                    self.log(payload)
                    self.set_ui_busy(False)
                    messagebox.showerror("Blad", payload)
        except Empty:
            pass
        finally:
            self.root.after(100, self._process_queue)


def main():
    root = tk.Tk()
    app = HeightConverterApp(root)
    app.apply_geoid_preset()
    root.mainloop()


if __name__ == "__main__":
    main()
