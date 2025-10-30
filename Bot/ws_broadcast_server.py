# ws_broadcast_server.py
# Menjalankan WebSocket server (port 8765) DAN HTTP server (port 8766)
# untuk menerima data spawn dari game server.

import asyncio
import json
import websockets
import threading
import time
from aiohttp import web  # Dependensi baru untuk server HTTP
import requests        # Dependensi baru untuk simulator
import random          # <--- Import baru untuk spawn acak

# Set untuk menyimpan semua koneksi client yang aktif
CONNECTED = set()

async def handler(websocket): # <--- PERUBAHAN DI SINI: Argumen 'path' dihapus
    """Menangani koneksi WebSocket baru."""
    CONNECTED.add(websocket)
    print(f"Client connected: {websocket.remote_address}. Total clients: {len(CONNECTED)}")
    try:
        async for msg in websocket:
            # Opsional: menangani pesan dari client (mis. registrasi, update viewport)
            # Saat ini kita hanya menerima pesan, tapi tidak melakukan apa-apa
            try:
                data = json.loads(msg)
                print(f"Received message from client: {data}")
                # Contoh: client mengirimkan info viewport/player_pos
                # if data.get("type") == "viewport_update":
                #     # Simpan data ini per client jika diperlukan
                #     pass
            except json.JSONDecodeError:
                print(f"Received non-JSON message: {msg}")
    except websockets.ConnectionClosed as e:
        print(f"Client disconnected: {websocket.remote_address} (Code: {e.code}, Reason: {e.reason})")
    except Exception as e:
        print(f"An error occurred with client {websocket.remote_address}: {e}")
    finally:
        CONNECTED.remove(websocket)
        print(f"Client removed. Total clients: {len(CONNECTED)}")

async def broadcast(data: dict):
# ... (sisa kode tidak berubah) ...
    """Mengirimkan data JSON ke semua client yang terhubung."""
    if not CONNECTED:
        return
    
    msg = json.dumps(data)
    
    # Buat salinan set untuk menghindari masalah jika set berubah saat iterasi
    clients = set(CONNECTED)
    
    # Kirim pesan ke semua client secara concurrent
    tasks = [ws.send(msg) for ws in clients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Opsional: logging jika ada error pengiriman
    for result, ws in zip(results, clients):
        if isinstance(result, Exception):
            print(f"Failed to send message to {ws.remote_address}: {result}")

# --- NEW HTTP Endpoint Handler ---
async def handle_http_spawn(request):
    """
    Menerima POST request dari game server dan broadcast via WebSocket.
    Endpoint: [POST] /spawn
    """
    try:
        data = await request.json()
        if not isinstance(data, dict):
            print(f"[HTTP 400] Invalid JSON: must be an object. Got: {data}")
            return web.Response(text="Invalid JSON: must be an object.", status=400)
        
        print(f"[HTTP 200] Received spawn data via POST: {data}")
        
        # Panggil fungsi broadcast yang sudah ada.
        # Kita bisa 'await' langsung karena kita berada di event loop yang sama.
        await broadcast(data) 
        
        return web.Response(text="OK", status=200)
    except json.JSONDecodeError:
        print("[HTTP 400] Invalid JSON format.")
        return web.Response(text="Invalid JSON format.", status=400)
    except Exception as e:
        print(f"[HTTP 500] Error handling request: {e}")
        return web.Response(text="Internal server error.", status=500)

# --- Helper untuk Game Server (Thread-safe) ---
# Fungsi ini masih berguna jika Anda punya *thread* lain di app ini
# yang perlu broadcast, tapi simulator kita akan pakai HTTP.
def broadcast_spawn_sync(loop, mob_id, x, y, map_id, extra=None):
    """
    Fungsi helper yang bisa dipanggil dari thread game server Anda (yang mungkin non-async).
    Ini akan menjadwalkan coroutine broadcast di event loop WebSocket secara thread-safe.
    """
    data = {"type": "spawn", "mob_id": mob_id, "x": x, "y": y, "map_id": map_id}
    if extra:
        data.update(extra)
    
    # Menjadwalkan coroutine broadcast di event loop yang sedang berjalan
    asyncio.run_coroutine_threadsafe(broadcast(data), loop)
    print(f"Scheduled broadcast for mob {mob_id} at ({x},{y})")

# --- Fungsi untuk menjalankan server ---
# Hapus 'async def main()' dan 'def start_server_in_thread()'
# Kita akan ganti dengan 'async def run_servers()' yang baru

# --- Contoh penggunaan untuk testing ---
def game_server_simulator():
    """
    Simulasi game server yang spawn mob setiap 10 detik.
    Sekarang menggunakan HTTP POST ke endpoint /spawn.
    """
    mob_counter = 0
    http_endpoint = "http://127.0.0.1:8766/spawn"
    
    # --- PERUBAHAN DI SINI ---
    # Gunakan posisi player Anda sebagai basis spawn untuk tes
    PLAYER_BASE_X = 178
    PLAYER_BASE_Y = 115
    SPAWN_RADIUS = 20 # Seberapa jauh mob akan spawn dari player (dalam unit world)
    
    print(f"[Simulator] Started. Will POST to {http_endpoint} every 10s.")
    print(f"[Simulator] Spawning mobs around ({PLAYER_BASE_X}, {PLAYER_BASE_Y})")
    
    while True:
        time.sleep(10)
        mob_counter += 1
        mob_id = f"mob_{mob_counter}"
        
        # Hasilkan koordinat acak di sekitar player
        x_offset = random.randint(-SPAWN_RADIUS, SPAWN_RADIUS)
        y_offset = random.randint(-SPAWN_RADIUS, SPAWN_RADIUS)
        
        x = PLAYER_BASE_X + x_offset
        y = PLAYER_BASE_Y + y_offset
        map_id = "prontera"
        
        data = {
            "type": "spawn", 
            "mob_id": mob_id, 
            "x": x, 
            "y": y, 
            "map_id": map_id,
            "hp": 100
        }
        
        print(f"\n[Game Sim] Spawning {mob_id}. Sending POST request...")
        try:
            # Kirim data ke endpoint HTTP server kita
            response = requests.post(http_endpoint, json=data, timeout=2)
            if response.status_code == 200:
                print(f"[Game Sim] POST successful.")
            else:
                print(f"[Game Sim] POST failed! Status: {response.status_code}, Resp: {response.text}")
        except requests.exceptions.ConnectionError:
            print("[Game Sim] POST failed! Connection refused. Is server running?")
        except Exception as e:
            print(f"[Game Sim] POST failed! Error: {e}")

async def run_servers():
    """
    Menjalankan WebSocket server dan aiohttp HTTP server secara bersamaan.
    """
    # 1. Setup HTTP Server (aiohttp)
    http_app = web.Application()
    http_app.router.add_post('/spawn', handle_http_spawn) # Definisikan endpoint
    
    runner = web.AppRunner(http_app)
    await runner.setup()
    http_site = web.TCPSite(runner, '0.0.0.0', 8766)
    
    # 2. Setup WebSocket Server (websockets)
    ws_server = await websockets.serve(handler, "0.0.0.0", 8765)
    
    print("===================================================")
    print("WebSocket server running on ws://0.0.0.0:8765")
    print("HTTP endpoint running on http://0.0.0.0:8766/spawn")
    print("===================================================")
    
    # 3. Mulai kedua server
    await http_site.start()
    
    # Biarkan server berjalan selamanya
    await asyncio.Future()

if __name__ == "__main__":
    # Jalankan simulator di thread terpisah
    # daemon=True berarti thread akan otomatis berhenti saat program utama berhenti
    
    # --- LANGKAH 3: Matikan simulator ---
    # Setelah Game Server asli Anda terintegrasi, komentari baris di bawah ini
    # agar tidak ada data spawn palsu yang dikirim.
    
    # simulator_thread = threading.Thread(target=game_server_simulator, daemon=True)
    # simulator_thread.start()
    print("===================================================")
    print("[PRODUCTION MODE] Simulator dinonaktifkan.")
    print("Menunggu data spawn asli dari Game Server di HTTP port 8766...")
    print("===================================================")


    # Jalankan server async utama
    try:
        asyncio.run(run_servers())
    except KeyboardInterrupt:
        print("\nShutting down servers...")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Servers stopped.")


