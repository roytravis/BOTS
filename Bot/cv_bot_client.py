# cv_bot_client.py
# Bot yang menggunakan Computer Vision (OpenCV) untuk mendeteksi monster di layar.
# Versi 5: Mode Asisten Peringatan Suara (100% Aman dari Anti-Cheat)

import cv2
import numpy as np
import mss
import pygetwindow as gw
import time
import winsound  # <- Ditambahkan untuk peringatan suara

# --- KONFIGURASI ---
GAME_WINDOW_TITLE = "MYRO | Gepard Shield 3.0 (^-_-^)" # Sesuaikan dengan judul jendela game Anda
MONSTER_TEMPLATE_PATH = "image_a15c12.png" # Nama file gambar monster Anda
ALERT_COOLDOWN = 5  # Waktu (detik) untuk menunggu setelah peringatan, sebelum mencari lagi
SEARCH_INTERVAL = 0.5 # Waktu (detik) antar pencarian jika tidak ada yang ditemukan
MIN_MATCH_COUNT = 20 # Jumlah minimum fitur yang harus cocok (coba ubah antara 10 dan 30)
ORB_FEATURES = 1000  # Jumlah fitur yang dideteksi. Naikkan jika deteksi gagal.

# --- Konfigurasi Suara ---
BEEP_FREQUENCY = 1000  # Frekuensi suara (Hz)
BEEP_DURATION = 500   # Durasi suara (milidetik)

# --- Logika Input Ctypes (Pengganti pydirectinput) ---
# ... SEMUA KODE ctypes DIHAPUS ...
# ... KARENA KITA TIDAK LAGI MENGIRIM INPUT ...
    
# --- Akhir Logika Input Ctypes ---


def find_and_alert_monster_orb(sct, window, orb, template_kp, template_des, template_img):
    """
    Mencari template monster menggunakan ORB (Feature Matching) dan memainkan suara peringatan.
    """
    try:
        # 1. Tentukan area tangkapan layar (seluruh jendela game)
        window_rect = {
            "left": window.left,
            "top": window.top,
            "width": window.width,
            "height": window.height
        }
        
        # 2. Ambil screenshot dan konversi ke Grayscale untuk OpenCV
        sct_img = sct.grab(window_rect)
        screen_img_bgr = np.array(sct_img)
        screen_img_gray = cv2.cvtColor(screen_img_bgr, cv2.COLOR_BGRA2GRAY)

        # 3. Temukan keypoints dan descriptors di screenshot
        screen_kp, screen_des = orb.detectAndCompute(screen_img_gray, None)

        if screen_des is None:
            print("Mencari... (Tidak ada fitur di layar)", end="\r")
            return False

        # 4. Cocokkan fitur template dengan fitur di layar
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(template_des, screen_des)
        matches = sorted(matches, key=lambda x: x.distance)

        print(f"Mencari... Kecocokan fitur ditemukan: {len(matches)}", end="\r")

        # 5. Periksa apakah kita punya *cukup* kecocokan
        if len(matches) > MIN_MATCH_COUNT:
            good_matches = matches[:MIN_MATCH_COUNT]
            
            # 6. Temukan lokasi objek di layar (Homography)
            src_pts = np.float32([template_kp[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([screen_kp[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
            
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            if M is None:
                return False

            print(f"\nMonster ditemukan! (Kecocokan: {len(good_matches)})")

            # 7. Dapatkan koordinat tengah dari objek yang ditemukan
            center_x_rel = np.mean(dst_pts[:, 0, 0])
            center_y_rel = np.mean(dst_pts[:, 0, 1])
            
            # 8. Konversi ke koordinat layar absolut
            screen_x_abs = int(window.left + center_x_rel)
            screen_y_abs = int(window.top + center_y_rel)
            
            # 9. Mainkan suara peringatan (MENGGANTIKAN CTYPES)
            print(f"  -> Monster terdeteksi di sekitar ({screen_x_abs}, {screen_y_abs}). Memainkan suara peringatan...")
            # ctypes_click(screen_x_abs, screen_y_abs) # <- DIHAPUS
            winsound.Beep(BEEP_FREQUENCY, BEEP_DURATION) # <- FUNGSI BARU
            
            return True
        else:
            return False

    except cv2.error as e:
        print(f"Error OpenCV: {e}", end="\r")
        return False
    except Exception as e:
        print(f"Error saat mencari monster: {e}")
        return False

def main_loop():
    """Loop utama bot."""
    print("Memulai Bot Asisten (Mode Peringatan Suara)...") # Diperbarui
    print(f"Mencari jendela game dengan judul: '{GAME_WINDOW_TITLE}'")

    try:
        window = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]
        if not window:
            print(f"Error: Jendela game '{GAME_WINDOW_TITLE}' tidak ditemukan.")
            return
        
        print(f"Jendela game ditemukan: {window.title} [Posisi: {window.left},{window.top}]")
    except IndexError:
        print(f"Error: Jendela game '{GAME_WINDOW_TITLE}' tidak ditemukan. Pastikan game berjalan dan judulnya cocok.")
        return

    try:
        # Muat gambar template monster (dalam mode grayscale)
        template_img = cv2.imread(MONSTER_TEMPLATE_PATH, cv2.IMREAD_GRAYSCALE)
        if template_img is None:
            print(f"Error: Tidak bisa memuat gambar template '{MONSTER_TEMPLATE_PATH}'.")
            print("Pastikan file gambar berada di folder yang sama dengan script ini.")
            return
        print(f"Gambar template '{MONSTER_TEMPLATE_PATH}' berhasil dimuat (Grayscale).")

        # --- Inisialisasi ORB ---
        orb = cv2.ORB_create(nfeatures=ORB_FEATURES)
        template_kp, template_des = orb.detectAndCompute(template_img, None)
        
        if template_des is None:
            print("Error: Tidak ada fitur yang terdeteksi di gambar template.")
            print("Coba gunakan gambar template yang lebih jelas atau lebih besar.")
            return
            
        print(f"Template di-proses: {len(template_kp)} fitur terdeteksi.")

    except Exception as e:
        print(f"Error saat memuat template: {e}")
        return

    # Inisialisasi mss (untuk screenshot cepat)
    with mss.mss() as sct:
        print("Bot sedang berjalan. Tekan Ctrl+C di terminal ini untuk berhenti.")
        while True:
            try:
                if not window.visible or not window.title == GAME_WINDOW_TITLE:
                    print("Jendela game tidak lagi terlihat atau judulnya berubah. Mencari kembali...")
                    window = gw.getWindowsWithTitle(GAME_WINDOW_TITLE)[0]

                # Fungsi diganti namanya untuk kejelasan
                found_monster = find_and_alert_monster_orb(
                    sct, window, orb, template_kp, template_des, template_img
                )
                
                if found_monster:
                    print(f"  -> Peringatan diberikan. Cooldown selama {ALERT_COOLDOWN} detik...")
                    time.sleep(ALERT_COOLDOWN) # Menggunakan ALERT_COOLDOWN
                else:
                    time.sleep(SEARCH_INTERVAL)
            
            except gw.PyGetWindowException:
                print("Error: Jendela game ditutup. Bot berhenti.")
                break
            except KeyboardInterrupt:
                print("\nBot dihentikan oleh pengguna (Ctrl+C).")
                break
            except Exception as e:
                print(f"Error tak terduga di loop utama: {e}")
                time.sleep(2)

if __name__ == "__main__":
    main_loop()

