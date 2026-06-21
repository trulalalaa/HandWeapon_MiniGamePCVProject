import cv2
import numpy as np
import os
import audio
from hand_detector import HandDetector
from game import Game
from renderer import Renderer

GAME_H = 720
GAME_W = 800

def main():
    # --- Setup webcam ---
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        print("[ERROR] Cannot open webcam. Check camera index.")
        return

    # --- Inisialisasi detektor tangan, game, dan renderer ---
    detector = HandDetector()
    game     = Game()
    renderer = Renderer()

    # --- State awal menu & konfigurasi ---
    app_state = 'SPLASH'
    player_team = 'INA'
    enemy_team = 'BRA'
    arena_theme = 'CHENGDU'
    bat_color = 'RED'

    _base = os.path.dirname(__file__)
    themesong_path = os.path.join(_base, "asset", "themesong.mp3")
    music_playing = False

    fail_count = 0
    MAX_FAILS  = 30
    
    start_hold_start_time = None

    print("[TABLE PONG FPP] Starting...")

    while True:
        try:
            ret, frame = cap.read()
            if not ret:
                fail_count += 1
                if fail_count >= MAX_FAILS:
                    print("[ERROR] Camera stopped delivering frames. Exiting.")
                    break
                continue
            fail_count = 0

            frame = cv2.flip(frame, 1)

            # --- Deteksi tangan dari frame webcam ---
            centroid, gesture, debug_frame = detector.process(frame)

            # --- Konversi posisi tangan ke koordinat layar game ---
            cursor_pos = None
            if centroid is not None:
                cx, cy = centroid
                cursor_pos = (int((cx / 640.0) * GAME_W), int((cy / 480.0) * GAME_H))

            # --- Kontrol musik tema (play di menu, stop di game) ---
            if app_state in ('SPLASH', 'TEAM_SELECT', 'CUSTOMIZE'):
                if not music_playing:
                    audio.play('theme', themesong_path, loop=True)
                    music_playing = True
            else:
                if music_playing:
                    audio.stop('theme')
                    music_playing = False

            # --- Render layar sesuai state (splash/menu/game) ---
            if app_state == 'SPLASH':
                game_canvas = renderer.draw_splash_screen()
                key_check = cv2.waitKey(1)
                if key_check == 32:
                    app_state = 'TEAM_SELECT'
                    continue
            elif app_state == 'GAME':
                game.update(centroid)
                game_canvas = renderer.draw(game, arena_theme, bat_color)
            elif app_state == 'TEAM_SELECT':
                game_canvas = renderer.draw_team_select_screen(player_team, enemy_team, cursor_pos, gesture)
                # --- Seleksi tim via gesture tangan ---
                if cursor_pos and gesture == 'FIST':
                    cx, cy = cursor_pos
                    if 50 <= cx <= 350:
                        if 150 <= cy <= 200: player_team = 'INA'
                        elif 220 <= cy <= 270: player_team = 'IND'
                        elif 290 <= cy <= 340: player_team = 'JPN'
                        elif 360 <= cy <= 410: player_team = 'BRA'
                        elif 430 <= cy <= 480: player_team = 'CHN'
                    elif 450 <= cx <= 750:
                        if 150 <= cy <= 200: enemy_team = 'INA'
                        elif 220 <= cy <= 270: enemy_team = 'IND'
                        elif 290 <= cy <= 340: enemy_team = 'JPN'
                        elif 360 <= cy <= 410: enemy_team = 'BRA'
                        elif 430 <= cy <= 480: enemy_team = 'CHN'
                    elif 300 <= cx <= 500 and 550 <= cy <= 610:
                        app_state = 'CUSTOMIZE'
            elif app_state == 'CUSTOMIZE':
                # --- Hold gesture untuk start game ---
                hold_progress = 0.0
                if cursor_pos and gesture == 'FIST':
                    cx, cy = cursor_pos
                    if 500 <= cy <= 560 and 250 <= cx <= 550:
                        import time
                        if start_hold_start_time is None:
                            start_hold_start_time = time.time()
                        
                        hold_progress = min(1.0, (time.time() - start_hold_start_time) / 3.0)
                        
                        if hold_progress >= 1.0:
                            stars = {'INA':3.0, 'IND':3.5, 'JPN':4.0, 'BRA':4.5, 'CHN':5.0}.get(enemy_team, 4.0)
                            
                            game = Game()
                            game.apply_difficulty(stars)
                            game.player_team = player_team
                            game.enemy_team = enemy_team
                            
                            app_state = 'GAME'
                            start_hold_start_time = None
                    else:
                        start_hold_start_time = None
                        
                    if 220 <= cy <= 270:
                        if 130 <= cx <= 280: arena_theme = 'CHENGDU'
                        elif 310 <= cx <= 460: arena_theme = 'TOKYO'
                        elif 490 <= cx <= 640: arena_theme = 'VIENNA'
                    elif 370 <= cy <= 420:
                        if 130 <= cx <= 280: bat_color = 'RED'
                        elif 310 <= cx <= 460: bat_color = 'BLUE'
                        elif 490 <= cx <= 640: bat_color = 'BLACK'
                else:
                    start_hold_start_time = None

                game_canvas = renderer.draw_customize_screen(arena_theme, bat_color, cursor_pos, gesture, hold_progress)

            cv2.imshow('TABLE PONG', game_canvas)
            cv2.imshow('HAND DETECTION', debug_frame)

        except Exception as e:
            print(f"[ERROR] Runtime exception: {e}")
            import traceback
            traceback.print_exc()
            break

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:
            break

        # --- Keyboard shortcut untuk navigasi menu & game ---
        if app_state == 'SPLASH':
            if key == 13 or key == 32:
                app_state = 'TEAM_SELECT'
        elif app_state == 'TEAM_SELECT':
            if key == 13 or key == 32:
                app_state = 'CUSTOMIZE'

        elif app_state == 'CUSTOMIZE':
            if key == ord('1'): arena_theme = 'CHENGDU'
            elif key == ord('2'): arena_theme = 'TOKYO'
            elif key == ord('3'): arena_theme = 'VIENNA'
            elif key == ord('4'): bat_color = 'RED'
            elif key == ord('5'): bat_color = 'BLUE'
            elif key == ord('6'): bat_color = 'BLACK'
            
            elif key == 13 or key == 32:
                stars = {'INA':3.0, 'IND':3.5, 'JPN':4.0, 'BRA':4.5, 'CHN':5.0}.get(enemy_team, 4.0)
                game = Game()
                game.apply_difficulty(stars)
                game.player_team = player_team
                game.enemy_team = enemy_team
                app_state = 'GAME'

        elif app_state == 'GAME':
            if key == ord('r'):
                old_round = game.round
                stars = {'INA':3.0, 'IND':3.5, 'JPN':4.0, 'BRA':4.5, 'CHN':5.0}.get(enemy_team, 4.0)
                pt, et = game.player_team, game.enemy_team
                game = Game()
                game.apply_difficulty(stars)
                game.player_team = pt
                game.enemy_team = et
                game.round = old_round + 1
            elif key == ord('m'):
                app_state = 'SPLASH'

    cap.release()
    cv2.destroyAllWindows()
    print("[TABLE PONG FPP] Goodbye!")

if __name__ == '__main__':
    main()
