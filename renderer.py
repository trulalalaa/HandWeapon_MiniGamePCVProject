import cv2
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
#  CANVAS & VIRTUAL CAMERA DIMENSIONS
# ─────────────────────────────────────────────────────────────────────────────
W  = 800
H  = 720

# Perspective projection limits (a basic tunnel look)
FAR_LEFT   = (150, 260)
FAR_RIGHT  = (650, 260)
NEAR_LEFT  = (50,  680)
NEAR_RIGHT = (750, 680)

def to_screen(game_x: float, game_z: float) -> tuple:
    # game_z = 0 (near), game_z = 1 (far)
    left_edge  = NEAR_LEFT[0] + game_z * (FAR_LEFT[0] - NEAR_LEFT[0])
    right_edge = NEAR_RIGHT[0] + game_z * (FAR_RIGHT[0] - NEAR_RIGHT[0])
    y_screen   = NEAR_LEFT[1] + game_z * (FAR_LEFT[1] - NEAR_LEFT[1])
    
    x_screen = left_edge + game_x * (right_edge - left_edge)
    return int(x_screen), int(y_screen)

class Renderer:
    def __init__(self):
        # The floor/tunnel polygon
        self.floor = np.array([FAR_LEFT, FAR_RIGHT, NEAR_RIGHT, NEAR_LEFT], dtype=np.int32)
        
        # Load assets
        import os
        base_dir = os.path.dirname(__file__)
        self.flags = {}
        for code, fname in [('INA', 'indonesia'), ('BRA', 'brazil'), ('IND', 'india'), ('JPN', 'japan'), ('CHN', 'china')]:
            path = os.path.join(base_dir, "asset", f"{fname}_round_icon_64.png")
            if os.path.exists(path):
                img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if img is not None:
                    # If RGB, convert to RGBA for consistency in overlay
                    if img.shape[2] == 3: img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
                    self.flags[code] = cv2.resize(img, (40, 40))
                    
        # Load Logo
        logo_path = os.path.join(base_dir, "asset", "Logo.png")
        self.logo_img = None
        if os.path.exists(logo_path):
            lg = cv2.imread(logo_path, cv2.IMREAD_UNCHANGED)
            if lg is not None:
                if lg.shape[2] == 3: lg = cv2.cvtColor(lg, cv2.COLOR_BGR2BGRA)
                self.logo_img = lg
                
        # Crowd setupcompute static crowd positions (above the floor horizon y=260)
        np.random.seed(42)
        self.crowd_x = np.random.randint(0, W, 400)
        self.crowd_y = np.random.randint(20, 250, 400)
        colors = [(200, 50, 50), (50, 200, 50), (50, 50, 200), (200, 200, 50), (200, 200, 200), (255, 200, 0)]
        self.crowd_c = [colors[np.random.randint(0, len(colors))] for _ in range(400)]
        
    def draw(self, game, theme: str, bat_color: str) -> np.ndarray:
        # Determine Venue Colors (Format RGB untuk BGR OpenCV)
        if theme == 'TOKYO':
            # Olympic Blue table, terracotta/reddish-brown background
            bg_col = (40, 40, 100)       
            floor_col = (200, 100, 20)   
            line_col = (255, 255, 255)  
        elif theme == 'VIENNA':
            # Rich Red table, charcoal/slate grey background
            bg_col = (30, 30, 30)       
            floor_col = (40, 30, 150)    
            line_col = (240, 240, 240)  
        else: # CHENGDU (Default)
            # Vibrant Green table, navy/blue-grey background
            bg_col = (90, 50, 30)       
            floor_col = (50, 120, 40)    
            line_col = (255, 255, 255)

        # Determine Bat Color
        if bat_color == 'BLUE':
            p_color = (200, 80, 40)
        elif bat_color == 'GREEN':
            p_color = (40, 200, 40)
        else:
            p_color = (40, 40, 200)

        # Create a vertical gradient for the stadium background to remove flatness
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        b, g, r = bg_col
        
        # Top of the screen will be 40% brightness, bottom (near table) will be 150% brightness
        multipliers = np.linspace(0.4, 1.5, H).reshape(-1, 1)
        col_b = np.clip(b * multipliers, 0, 255)
        col_g = np.clip(g * multipliers, 0, 255)
        col_r = np.clip(r * multipliers, 0, 255)
        gradient_col = np.stack([col_b, col_g, col_r], axis=2).astype(np.uint8)
        canvas[:] = gradient_col
        
        # Draw subtle stadium tiers (horizontal lines) to add depth structure
        tier_col = (int(b*0.5), int(g*0.5), int(r*0.5))
        for y_tier in range(40, int(FAR_LEFT[1]) + 20, 35):
            cv2.line(canvas, (0, y_tier), (W, y_tier), tier_col, 2)
            # Add staggered vertical lines to simulate seating sections
            for x_sec in range((y_tier * 2) % 150, W, 150):
                cv2.line(canvas, (x_sec, y_tier), (x_sec, max(0, y_tier-35)), tier_col, 1)
        
        # Floor
        cv2.fillPoly(canvas, [self.floor], floor_col)
        # Edge lines
        cv2.polylines(canvas, [self.floor], True, line_col, 3)
        # Center line (dashed or solid)
        mid_far = ((FAR_LEFT[0] + FAR_RIGHT[0]) // 2, FAR_LEFT[1])
        mid_near = ((NEAR_LEFT[0] + NEAR_RIGHT[0]) // 2, NEAR_LEFT[1])
        cv2.line(canvas, mid_far, mid_near, line_col, 2)
        
        # Crowd (Draw this before the ball and paddles but after background)
        self._draw_crowd(canvas)
        
        # Draw AI Paddle (Far end)
        self._draw_paddle(canvas, game.ai_x, 1.0, (50, 50, 200), "AI", dx=0.0)
        
        # Draw Ball
        if game.state != 'game_over':
            self._draw_ball(canvas, game.ball_x, game.ball_z, line_col)
            
        # Draw Player Paddle (Near end)
        self._draw_paddle(canvas, game.player_x, 0.0, p_color, "YOU", dx=getattr(game, 'player_dx', 0.0))
        
        # UI overlays
        self._draw_world_cup_scoreboard(canvas, game.player_score, game.ai_score, getattr(game, 'player_team', 'INA'), getattr(game, 'enemy_team', 'BRA'))
        
        if game.state == 'waiting':
            self._draw_waiting(canvas, game)
        elif game.state == 'point_scored':
            self._draw_point_scored(canvas, game)
        elif game.state == 'game_over':
            self._draw_game_over(canvas, game)
            
        return canvas

    def _draw_paddle(self, canvas, px, pz, color, label, dx=0.0):
        import math
        cx, cy = to_screen(px, pz)
        cy -= int(40 * (1-pz*0.6)) # float above floor

        # Size scales with depth
        scale = 1.0 - pz * 0.6
        blade_a = int(45 * scale)
        blade_b = int(55 * scale)

        tilt_deg = max(-35.0, min(35.0, dx * 400.0))
        tilt_rad = math.radians(tilt_deg)
        cos_t = math.cos(tilt_rad)
        sin_t = math.sin(tilt_rad)

        hinge_x = cx
        hinge_y = cy + int(8 * scale)

        def rotate_pt(pt_x, pt_y):
            rx = pt_x * cos_t - pt_y * sin_t
            ry = pt_x * sin_t + pt_y * cos_t
            return (int(hinge_x + rx), int(hinge_y + ry))

        # Handle (Wood)
        hw_top = 12 * scale
        hw_bot = 10 * scale
        h_len = 45 * scale
        h_pts_local = np.array([
            [-hw_top/2, 0], [hw_top/2, 0],
            [hw_bot/2, h_len], [-hw_bot/2, h_len]
        ], dtype=np.float32)

        h_screen = np.array([rotate_pt(p[0], p[1]) for p in h_pts_local], dtype=np.int32)
        cv2.fillPoly(canvas, [h_screen], (43, 90, 139))
        cv2.polylines(canvas, [h_screen], True, (20, 50, 80), max(1, int(1.5*scale)), cv2.LINE_AA)

        # Blade (Red/Blue Rubber)
        cv2.ellipse(canvas, (cx, cy), (blade_a, blade_b), tilt_deg, 0, 360, color, -1)
        # Inner lighter band for rubber texture
        cv2.ellipse(canvas, (cx, cy), (int(blade_a*0.8), int(blade_b*0.8)), tilt_deg, 0, 360, (min(255, color[0]+30), min(255, color[1]+30), min(255, color[2]+30)), -1)
        # Outline
        cv2.ellipse(canvas, (cx, cy), (blade_a, blade_b), tilt_deg, 0, 360, (20, 20, 20), max(1, int(2.5*scale)), cv2.LINE_AA)

        if label == "YOU":
            l_pt = rotate_pt(0, h_len + 15*scale)
            cv2.putText(canvas, label, (l_pt[0]-14, l_pt[1]), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200,200,200), 1, cv2.LINE_AA)

    def _draw_ball(self, canvas, bx, bz, line_col):
        cx, cy = to_screen(bx, bz)
        cy -= int(40 * (1-bz*0.6)) # float above floor
        
        radius = int(24 * (1.0 - bz * 0.6))
        
        cv2.circle(canvas, (cx, cy), radius, (200, 255, 255), -1)
        cv2.circle(canvas, (cx, cy), radius, line_col, 2)
        
    def _draw_crowd(self, canvas):
        import time
        # Draw static audience
        for x, y, c in zip(self.crowd_x, self.crowd_y, self.crowd_c):
            cv2.circle(canvas, (x, y), 2, c, -1)
            
        # Draw dynamic camera flashes
        np.random.seed(int(time.time() * 15) % (2**32))
        flash_count = np.random.randint(0, 4)
        flash_x = np.random.randint(0, W, flash_count)
        flash_y = np.random.randint(20, 250, flash_count)
        for x, y in zip(flash_x, flash_y):
            cv2.circle(canvas, (x, y), 3, (255, 255, 255), -1)
            cv2.circle(canvas, (x, y), 8, (255, 255, 255), 1)


    def _overlay_image(self, bg, fg, x, y):
        # Helper to overlay RGBA image onto BGR canvas
        h, w = fg.shape[:2]
        if y+h > bg.shape[0] or x+w > bg.shape[1] or x < 0 or y < 0:
            return
        
        if fg.shape[2] == 4:
            alpha = fg[:, :, 3] / 255.0
            for c in range(3):
                bg[y:y+h, x:x+w, c] = (alpha * fg[:, :, c] + (1 - alpha) * bg[y:y+h, x:x+w, c])
        else:
            bg[y:y+h, x:x+w] = fg

    def _draw_world_cup_scoreboard(self, canvas, score_p, score_e, pt, et):
        # Center top
        cx = W // 2
        y = 15
        h = 45
        
        # Background bar
        bar_w = 360
        cv2.rectangle(canvas, (cx - bar_w//2, y), (cx + bar_w//2, y + h), (50, 60, 45), -1) # Theme color matches logo
        cv2.rectangle(canvas, (cx - bar_w//2, y), (cx + bar_w//2, y + h), (180, 200, 180), 2)
        
        # Draw flags on left and right side
        if pt in self.flags:
            self._overlay_image(canvas, self.flags[pt], cx - 180 + 10, y + 2)
        if et in self.flags:
            self._overlay_image(canvas, self.flags[et], cx + 180 - 50, y + 2)
            
        # Draw text and scores
        cv2.putText(canvas, pt, (cx - 120, y + 33), cv2.FONT_HERSHEY_DUPLEX, 1.0, (200, 255, 200), 2)
        cv2.putText(canvas, str(score_p), (cx - 40, y + 33), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
        
        cv2.putText(canvas, "-", (cx - 10, y + 33), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
        
        cv2.putText(canvas, str(score_e), (cx + 25, y + 33), cv2.FONT_HERSHEY_DUPLEX, 1.2, (255, 255, 255), 2)
        cv2.putText(canvas, et, (cx + 65, y + 33), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 200, 200), 2)


    def _draw_waiting(self, canvas, game):
        cv2.putText(canvas, "Show your HAND to start!", (160, 330),
                    cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 255, 120), 2)
        if game._hand_seen_since is not None:
            import time
            elapsed = min(1.5, time.time() - game._hand_seen_since)
            bar_w   = int((elapsed / 1.5) * 400)
            cv2.rectangle(canvas, (200, 350), (600, 368), (80, 80, 80), -1)
            cv2.rectangle(canvas, (200, 350), (200 + bar_w, 368), (0, 255, 120), -1)

    def _draw_point_scored(self, canvas, game):
        team_code = getattr(game, 'player_team', 'INA') if game._point_scorer == 'PLAYER' else getattr(game, 'enemy_team', 'BRA')
        team_names = {'INA': 'INDONESIA', 'IND': 'INDIA', 'JPN': 'JAPAN', 'BRA': 'BRAZIL', 'CHN': 'CHINA'}
        name = team_names.get(team_code, "TEAM")
        txt = f"{name} SCORES!"
        
        # Colors: (Inner, Outer) in BGR
        colors = {
            'BRA': ((0, 255, 255), (0, 100, 0)),    # Kuning, outline Hijau
            'IND': ((0, 140, 255), (255, 255, 255)),# Oren, outline Putih
            'CHN': ((0, 0, 255), (0, 0, 100)),      # Merah, outline Merah Tua
            'JPN': ((255, 255, 255), (0, 0, 200)),  # Putih, outline Merah
            'INA': ((0, 0, 255), (255, 255, 255))   # Merah, outline Putih
        }
        inner_col, outer_col = colors.get(team_code, ((255, 255, 255), (0, 0, 0)))
        
        font = cv2.FONT_HERSHEY_DUPLEX
        scale = 1.8
        thick_outer = 9
        thick_inner = 4
        
        ts = cv2.getTextSize(txt, font, scale, thick_outer)[0]
        tx = (W - ts[0]) // 2
        ty = 370
        
        cv2.putText(canvas, txt, (tx, ty), font, scale, outer_col, thick_outer)
        cv2.putText(canvas, txt, (tx, ty), font, scale, inner_col, thick_inner)

    def _draw_game_over(self, canvas, game):
        team_code = getattr(game, 'player_team', 'INA') if game.winner == 'PLAYER' else getattr(game, 'enemy_team', 'BRA')
        team_names = {'INA': 'INDONESIA', 'IND': 'INDIA', 'JPN': 'JAPAN', 'BRA': 'BRAZIL', 'CHN': 'CHINA'}
        name = team_names.get(team_code, "TEAM")
        txt = f"{name} WINS!"
        
        colors = {
            'BRA': ((0, 255, 255), (0, 100, 0)),
            'IND': ((0, 140, 255), (255, 255, 255)),
            'CHN': ((0, 0, 255), (0, 0, 100)),
            'JPN': ((255, 255, 255), (0, 0, 200)),
            'INA': ((0, 0, 255), (255, 255, 255))
        }
        inner_col, outer_col = colors.get(team_code, ((255, 255, 255), (0, 0, 0)))
        
        font = cv2.FONT_HERSHEY_DUPLEX
        scale = 2.2
        thick_outer = 10
        thick_inner = 4
        
        ts = cv2.getTextSize(txt, font, scale, thick_outer)[0]
        tx = (W - ts[0]) // 2
        ty = 300
        
        cv2.putText(canvas, txt, (tx, ty), font, scale, outer_col, thick_outer)
        cv2.putText(canvas, txt, (tx, ty), font, scale, inner_col, thick_inner)
        
        ts1 = cv2.getTextSize("Press  R  to restart", cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1)[0]
        cv2.putText(canvas, "Press  R  to restart", ((W - ts1[0])//2, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (200, 200, 200), 1)
        
        ts2 = cv2.getTextSize("Press  M  for Main Menu", cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1)[0]
        cv2.putText(canvas, "Press  M  for Main Menu", ((W - ts2[0])//2, 500), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (100, 200, 255), 1)

    # ─────────────────────────────────────────────────────────────────────────────
    #  MENU SCREENS
    # ─────────────────────────────────────────────────────────────────────────────
    
    def draw_splash_screen(self) -> np.ndarray:
        # Full screen Logo placeholder (similar to KONAMI screen)
        # Size must be GAME_W (800) by GAME_H (720)
        full_w = W
        full_h = H
        canvas = np.full((full_h, full_w, 3), (40, 50, 40), dtype=np.uint8)
        
        if self.logo_img is not None:
            lh, lw = self.logo_img.shape[:2]
            # Resize logo tepat ke ukuran canvas (full screen, tidak ada margin)
            logo_resized = cv2.resize(self.logo_img, (full_w, full_h))
            # Alpha blend langsung — tidak pakai _overlay_image agar tidak ada offset
            if logo_resized.shape[2] == 4:
                alpha = logo_resized[:, :, 3:4] / 255.0
                fg    = logo_resized[:, :, :3].astype(np.float32)
                bg    = canvas.astype(np.float32)
                canvas = (fg * alpha + bg * (1.0 - alpha)).astype(np.uint8)
            else:
                canvas = logo_resized[:, :, :3].copy()
            
        import time
        if int(time.time() * 2) % 2 == 0:
            cv2.putText(canvas, "Press SPACE to Start", (full_w//2 - 160, full_h - 40), cv2.FONT_HERSHEY_DUPLEX, 0.8, (200, 200, 200), 2)
            
        return canvas

    def draw_title_screen(self, cursor_pos=None, gesture=None) -> np.ndarray:
        # Theme matching Logo.png (Olive/Green-Gray)
        canvas = np.full((H, W, 3), (40, 50, 40), dtype=np.uint8)
        
        cv2.putText(canvas, "SIMPLE 3D PONG", (130, 250), cv2.FONT_HERSHEY_DUPLEX, 2.0, (255, 255, 255), 4)
        cv2.putText(canvas, "First-Person Perspective", (240, 310), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (150, 150, 150), 2)
        
        import time
        if int(time.time() * 2) % 2 == 0:
            cv2.putText(canvas, "Press SPACE or FIST to continue", (180, 450), cv2.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 255), 2)
            
        self._draw_cursor(canvas, cursor_pos, gesture)
        return canvas
        
    def draw_team_select_screen(self, player_team, enemy_team, cursor_pos=None, gesture=None) -> np.ndarray:
        # Background: HIJAU LAPANGAN
        canvas = np.full((H, W, 3), (34, 139, 34), dtype=np.uint8)
        
        # Garis Lapangan Dekorasi (Putih opacity rendah disimulasikan dengan hijau pucat)
        line_col = (100, 180, 100)
        cv2.line(canvas, (W//2, 0), (W//2, H), line_col, 2)
        cv2.rectangle(canvas, (0, H//2 - 150), (100, H//2 + 150), line_col, 2)
        cv2.rectangle(canvas, (W - 100, H//2 - 150), (W, H//2 + 150), line_col, 2)
        
        # HEADER BANNER
        cv2.rectangle(canvas, (0, 0), (W, 90), (180, 60, 20), -1)
        cv2.line(canvas, (0, 90), (W, 90), (0, 215, 255), 3)
        text_size = cv2.getTextSize("SELECT TEAMS", cv2.FONT_HERSHEY_DUPLEX, 1.8, 3)[0]
        cv2.putText(canvas, "SELECT TEAMS", ((W - text_size[0])//2, 65), cv2.FONT_HERSHEY_DUPLEX, 1.8, (0, 215, 255), 3)
        
        # LABELS "PLAYER TEAM" dan "ENEMY TEAM"
        cv2.rectangle(canvas, (80, 110), (320, 140), (0, 100, 0), -1) # Background hijau tua
        ts1 = cv2.getTextSize("PLAYER TEAM", cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
        cv2.putText(canvas, "PLAYER TEAM", (80 + (240 - ts1[0]) // 2, 110 + (30 + ts1[1]) // 2), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 215, 255), 2)
        
        cv2.rectangle(canvas, (480, 110), (720, 140), (180, 60, 20), -1) # Background biru piala dunia
        ts2 = cv2.getTextSize("ENEMY TEAM", cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
        cv2.putText(canvas, "ENEMY TEAM", (480 + (240 - ts2[0]) // 2, 110 + (30 + ts2[1]) // 2), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 215, 255), 2)
        
        teams = [('INA', 'Indonesia', 3.0), ('IND', 'India', 3.5), ('JPN', 'Japan', 4.0), ('BRA', 'Brazil', 4.5), ('CHN', 'China', 5.0)]
        
        for i, (code, name, stars) in enumerate(teams):
            y = 150 + i * 70
            
            # --- PLAYER CARD ---
            cx_p = 50
            if player_team == code:
                cv2.rectangle(canvas, (cx_p, y), (cx_p+300, y+55), (180, 60, 20), -1) # Selected
                cv2.rectangle(canvas, (cx_p, y), (cx_p+300, y+55), (0, 215, 255), 2) # Border
                cv2.line(canvas, (cx_p+285, y), (cx_p+300, y+15), (0, 215, 255), 3) # Corner accent
            else:
                cv2.rectangle(canvas, (cx_p, y), (cx_p+300, y+55), (0, 100, 0), -1) # Normal
                
            if code in self.flags:
                self._overlay_image(canvas, self.flags[code], cx_p+10, y+7)
            cv2.putText(canvas, name, (cx_p+60, y+35), cv2.FONT_HERSHEY_DUPLEX, 0.85, (255, 255, 255), 2)

            # --- ENEMY CARD ---
            cx_e = 450
            if enemy_team == code:
                cv2.rectangle(canvas, (cx_e, y), (cx_e+300, y+55), (180, 60, 20), -1)
                cv2.rectangle(canvas, (cx_e, y), (cx_e+300, y+55), (0, 215, 255), 2)
                cv2.line(canvas, (cx_e+285, y), (cx_e+300, y+15), (0, 215, 255), 3)
            else:
                cv2.rectangle(canvas, (cx_e, y), (cx_e+300, y+55), (0, 100, 0), -1)
                
            if code in self.flags:
                self._overlay_image(canvas, self.flags[code], cx_e+10, y+7)
            cv2.putText(canvas, name, (cx_e+60, y+25), cv2.FONT_HERSHEY_DUPLEX, 0.85, (255, 255, 255), 2)
            
            # --- BINTANG RATING ---
            import math
            star_radius_outer = 7
            star_radius_inner = 3
            spacing = 18
            star_y = y + 40
            for s in range(5):
                star_cx = cx_e + 60 + s * spacing
                points = []
                for j in range(10):
                    angle = j * math.pi / 5 - math.pi / 2
                    r = star_radius_outer if j % 2 == 0 else star_radius_inner
                    points.append((int(star_cx + r * math.cos(angle)), int(star_y + r * math.sin(angle))))
                pts = np.array([points], dtype=np.int32)
                if s < int(stars):
                    cv2.fillPoly(canvas, pts, (0, 215, 255))
                elif s < stars:
                    # Bintang penuh untuk half-star karena outline agak sulit dilihat
                    cv2.fillPoly(canvas, pts, (180, 180, 180)) 
                    mask = np.zeros_like(canvas)
                    cv2.fillPoly(mask, pts, (0, 215, 255))
                    canvas[star_y-8:star_y+8, star_cx-8:star_cx] = np.where(
                        mask[star_y-8:star_y+8, star_cx-8:star_cx] == (0, 215, 255),
                        (0, 215, 255),
                        canvas[star_y-8:star_y+8, star_cx-8:star_cx]
                    )
                    cv2.polylines(canvas, pts, True, (0, 215, 255), 1)
                else:
                    cv2.polylines(canvas, pts, True, (200, 200, 200), 1)
            
        # TOMBOL CONFIRM
        bx, by = 250, 545
        bw, bh = 300, 65
        cv2.rectangle(canvas, (bx, by), (bx+bw, by+bh), (0, 215, 255), -1)
        cv2.rectangle(canvas, (bx, by), (bx+bw, by+bh), (255, 255, 255), 2)
        cv2.circle(canvas, (bx, by), 4, (0, 215, 255), -1)
        cv2.circle(canvas, (bx+bw, by), 4, (0, 215, 255), -1)
        cv2.circle(canvas, (bx, by+bh), 4, (0, 215, 255), -1)
        cv2.circle(canvas, (bx+bw, by+bh), 4, (0, 215, 255), -1)
        ts_btn = cv2.getTextSize("CONFIRM", cv2.FONT_HERSHEY_DUPLEX, 1.2, 3)[0]
        cv2.putText(canvas, "CONFIRM", (bx + (bw - ts_btn[0]) // 2, by + (bh + ts_btn[1]) // 2), cv2.FONT_HERSHEY_DUPLEX, 1.2, (0, 100, 0), 3)
        
        self._draw_cursor(canvas, cursor_pos, gesture)
        return canvas

    def draw_customize_screen(self, arena_theme, bat_color, cursor_pos=None, gesture=None, hold_progress=0.0) -> np.ndarray:
        # Background: HIJAU LAPANGAN
        canvas = np.full((H, W, 3), (34, 139, 34), dtype=np.uint8)
        
        # Garis Lapangan Dekorasi
        line_col = (100, 180, 100)
        cv2.line(canvas, (W//2, 0), (W//2, H), line_col, 2)
        cv2.rectangle(canvas, (0, H//2 - 150), (100, H//2 + 150), line_col, 2)
        cv2.rectangle(canvas, (W - 100, H//2 - 150), (W, H//2 + 150), line_col, 2)
        
        # HEADER BANNER
        cv2.rectangle(canvas, (0, 0), (W, 90), (180, 60, 20), -1)
        cv2.line(canvas, (0, 90), (W, 90), (0, 215, 255), 3)
        text_size = cv2.getTextSize("CUSTOMIZATION", cv2.FONT_HERSHEY_DUPLEX, 1.8, 3)[0]
        cv2.putText(canvas, "CUSTOMIZATION", ((W - text_size[0])//2, 65), cv2.FONT_HERSHEY_DUPLEX, 1.8, (0, 215, 255), 3)
        
        # Section 1: VENUE
        cv2.rectangle(canvas, (90, 180), (310, 210), (0, 80, 0), -1)
        ts_th = cv2.getTextSize("VENUE:", cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]
        cv2.putText(canvas, "VENUE:", (90 + (220 - ts_th[0]) // 2, 180 + (30 + ts_th[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 215, 255), 2)
        
        themes = [("CHENGDU", 'CHENGDU'), ("TOKYO", 'TOKYO'), ("VIENNA", 'VIENNA')]
        for i, (text, key) in enumerate(themes):
            bx = 130 + i*180
            by = 220
            bw_theme = 150
            bh_theme = 55
            if arena_theme == key:
                cv2.rectangle(canvas, (bx, by), (bx+bw_theme, by+bh_theme), (0, 215, 255), -1)
                cv2.rectangle(canvas, (bx, by), (bx+bw_theme, by+bh_theme), (255, 255, 255), 3)
                ts = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 3)[0]
                cv2.putText(canvas, text, (bx + (bw_theme - ts[0]) // 2, by + (bh_theme + ts[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 80, 0), 3)
            else:
                cv2.rectangle(canvas, (bx, by), (bx+bw_theme, by+bh_theme), (0, 100, 0), -1)
                cv2.rectangle(canvas, (bx, by), (bx+bw_theme, by+bh_theme), (255, 255, 255), 1)
                ts = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)[0]
                cv2.putText(canvas, text, (bx + (bw_theme - ts[0]) // 2, by + (bh_theme + ts[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 1)
                
        # Section 2: BAT COLOR
        cv2.rectangle(canvas, (90, 330), (310, 360), (0, 80, 0), -1)
        ts_bc = cv2.getTextSize("BAT COLOR:", cv2.FONT_HERSHEY_SIMPLEX, 0.75, 2)[0]
        cv2.putText(canvas, "BAT COLOR:", (90 + (220 - ts_bc[0]) // 2, 330 + (30 + ts_bc[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 215, 255), 2)
        
        bats = [("RED", 'RED', (0, 0, 200)), ("BLUE", 'BLUE', (200, 80, 40)), ("GREEN", 'GREEN', (40, 200, 40))]
        for i, (text, key, disp_col) in enumerate(bats):
            bx = 130 + i*180
            by = 370
            bw_bat = 150
            bh_bat = 55
            text_area_x = bx + 45
            text_area_w = 105
            if bat_color == key:
                cv2.rectangle(canvas, (bx, by), (bx+bw_bat, by+bh_bat), (0, 215, 255), -1)
                cv2.rectangle(canvas, (bx, by), (bx+bw_bat, by+bh_bat), (255, 255, 255), 3)
                ts = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 3)[0]
                cv2.putText(canvas, text, (text_area_x + (text_area_w - ts[0]) // 2, by + (bh_bat + ts[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 80, 0), 3)
            else:
                cv2.rectangle(canvas, (bx, by), (bx+bw_bat, by+bh_bat), (0, 100, 0), -1)
                cv2.rectangle(canvas, (bx, by), (bx+bw_bat, by+bh_bat), (255, 255, 255), 1)
                ts = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)[0]
                cv2.putText(canvas, text, (text_area_x + (text_area_w - ts[0]) // 2, by + (bh_bat + ts[1]) // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (150, 150, 150), 1)
                
            # Lingkaran karet bat
            cv2.circle(canvas, (bx+25, by+27), 10, disp_col, -1)
            
        # START GAME BUTTON
        bx, by = 225, 500
        bw, bh = 350, 65
        cv2.rectangle(canvas, (bx+4, by+4), (bx+bw+4, by+bh+4), (0, 150, 150), -1) # Shadow
        cv2.rectangle(canvas, (bx, by), (bx+bw, by+bh), (0, 215, 255), -1)
        
        # Draw hold progress fill
        if hold_progress > 0.0:
            fill_w = int(bw * hold_progress)
            cv2.rectangle(canvas, (bx, by), (bx + fill_w, by + bh), (0, 150, 0), -1)
            
        cv2.rectangle(canvas, (bx, by), (bx+bw, by+bh), (255, 255, 255), 2)
        
        # Change text color to white if filling up to maintain contrast, otherwise green
        text_color = (255, 255, 255) if hold_progress > 0.5 else (0, 80, 0)
        ts_start = cv2.getTextSize("START GAME", cv2.FONT_HERSHEY_DUPLEX, 1.2, 3)[0]
        cv2.putText(canvas, "START GAME", (bx + (bw - ts_start[0]) // 2, by + (bh + ts_start[1]) // 2), cv2.FONT_HERSHEY_DUPLEX, 1.2, text_color, 3)
        
        self._draw_cursor(canvas, cursor_pos, gesture)
        return canvas

    def _draw_cursor(self, canvas, cursor_pos, gesture):
        if cursor_pos is not None:
            cx, cy = cursor_pos
            if gesture == 'FIST':
                cv2.circle(canvas, (cx, cy), 12, (0, 255, 0), -1)
                cv2.circle(canvas, (cx, cy), 16, (255, 255, 255), 2)
            else:
                cv2.circle(canvas, (cx, cy), 12, (255, 100, 100), 2)
                cv2.circle(canvas, (cx, cy), 4, (255, 100, 100), -1)

    def _draw_stars(self, canvas, x, y, rating):
        # Draw small star polygons
        import math
        star_radius_outer = 6
        star_radius_inner = 3
        spacing = 15
        for s in range(5):
            cx = x + s * spacing
            cy = y
            points = []
            for i in range(10):
                angle = i * math.pi / 5 - math.pi / 2
                r = star_radius_outer if i % 2 == 0 else star_radius_inner
                points.append((int(cx + r * math.cos(angle)), int(cy + r * math.sin(angle))))
            pts = np.array([points], dtype=np.int32)
            if s < int(rating):
                cv2.fillPoly(canvas, pts, (0, 215, 255)) # Full Yellow star
            elif s < rating:
                # Half star drawing can be tricky, let's just draw outline and half rect
                cv2.fillPoly(canvas, pts, (100, 100, 100))
                # Fill left half
                mask = np.zeros_like(canvas)
                cv2.fillPoly(mask, pts, (0, 215, 255))
                canvas[cy-6:cy+6, cx-6:cx] = np.where(mask[cy-6:cy+6, cx-6:cx] == (0, 215, 255), (0, 215, 255), canvas[cy-6:cy+6, cx-6:cx])
                cv2.polylines(canvas, pts, True, (0, 215, 255), 1)
            else:
                cv2.polylines(canvas, pts, True, (100, 100, 100), 1) # Empty star
