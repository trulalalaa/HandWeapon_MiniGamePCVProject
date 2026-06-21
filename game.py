import time
import random
import os
import audio

# --- Konstanta game ---
WIN_SCORE       = 7
WEBCAM_WIDTH    = 480
PADDLE_WIDTH    = 0.20

class Game:
    def __init__(self):
        self.round = 1
        self.difficulty_stars = 4.0
        
        _base = os.path.dirname(__file__)
        self.ball_sound_path = os.path.join(_base, "asset", "ball_sound.mp3")
        self.crowd_sound_path = os.path.join(_base, "asset", "crowd.mp3")
        self._ball_snd_counter = 0
        
        self.reset()

    def apply_difficulty(self, stars: float):
        self.difficulty_stars = stars
        self._set_speed_by_difficulty()

    # --- Rumus kecepatan bola berdasarkan difficulty ---
    def _set_speed_by_difficulty(self):
        self.ball_speed = 0.7 + ((self.difficulty_stars - 3.0) / 2.0) * 0.7

    # --- Reset state game (posisi bola, skor, dll) ---
    def reset(self):
        self.ball_x  = 0.5
        self.ball_z  = 0.5
        self.ball_speed = 1.0
        self._set_speed_by_difficulty()
        self.ball_vx = random.choice([-1, 1]) * 0.015 * self.ball_speed
        self.ball_vz = -0.025 * self.ball_speed

        self.player_x = 0.5
        self.ai_x     = 0.5
        self._prev_player_x = 0.5
        self.player_dx = 0.0

        self.player_score = 0
        self.ai_score     = 0

        self.state          = 'waiting'
        self.winner         = None
        self._hand_seen_since = None
        self._point_timer     = 0.0
        self._point_scorer    = None

        self.score_flash      = 0
        self.shake_frames     = 0
        self.frames           = 0

    # --- Reset posisi bola setelah point ---
    def _reset_ball(self, toward_player: bool):
        self.ball_x  = 0.5
        self.ball_z  = 0.5
        self.ball_vx = random.choice([-1, 1]) * 0.015 * self.ball_speed
        self.ball_vz = -0.025 * self.ball_speed if toward_player else 0.025 * self.ball_speed

    def _play_ball_sound(self):
        self._ball_snd_counter = (self._ball_snd_counter + 1) % 4
        alias = f'ball{self._ball_snd_counter}'
        audio.play(alias, self.ball_sound_path)

    # --- Sistem scoring & cek menang ---
    def _trigger_point(self, scorer: str):
        if scorer == 'PLAYER':
            self.player_score += 1
            self.ball_speed = min(2.5, self.ball_speed + 0.15)
            self._point_scorer = 'PLAYER'
        else:
            self.ai_score += 1
            self._point_scorer = 'AI'

        self.score_flash  = 8
        self._point_timer = time.time()
        
        audio.play('crowd', self.crowd_sound_path)

        if self.player_score >= WIN_SCORE or self.ai_score >= WIN_SCORE:
            self.state = 'game_over'
            self.winner = 'PLAYER' if self.player_score >= WIN_SCORE else 'AI'
            audio.play('crowd', self.crowd_sound_path, loop=True)
        else:
            self.state = 'point_scored'

    # --- Game loop utama (dipanggil tiap frame) ---
    def update(self, centroid):
        self.frames += 1

        if self.score_flash > 0: self.score_flash -= 1
        if self.shake_frames > 0: self.shake_frames -= 1

        if self.state == 'game_over':
            return

        if self.state == 'point_scored':
            if time.time() - self._point_timer > 1.5:
                self.state = 'playing'
                audio.stop('crowd')
                self.round += 1
                self._reset_ball(toward_player=(self._point_scorer == 'AI'))
            return

        if self.state == 'waiting':
            if not audio.is_playing('crowd'):
                audio.play('crowd', self.crowd_sound_path, loop=True)
                
            if centroid is not None:
                if self._hand_seen_since is None:
                    self._hand_seen_since = time.time()
                elif time.time() - self._hand_seen_since > 1.5:
                    self.state = 'playing'
                    audio.stop('crowd')
                    self._reset_ball(toward_player=True)
            else:
                self._hand_seen_since = None
            return

        # --- Pergerakan paddle player (dari posisi tangan webcam) ---
        if centroid is not None:
            cx, cy = centroid
            self._prev_player_x = self.player_x
            
            normalized_cx = (cx - (0.2 * WEBCAM_WIDTH)) / (0.6 * WEBCAM_WIDTH)
            self.player_x = max(0.0, min(1.0, normalized_cx))
            self.player_dx = self.player_x - self._prev_player_x

        # --- Pergerakan paddle AI (mengejar bola) ---
        ai_speed_mult = 0.01 + ((self.difficulty_stars - 3.0) / 2.0) * 0.025
        ai_speed = ai_speed_mult * self.ball_speed
        diff = self.ball_x - self.ai_x
        self.ai_x += max(-ai_speed, min(ai_speed, diff))
        self.ai_x = max(0.0, min(1.0, self.ai_x))

        # --- Update posisi bola & pantulan dinding samping ---
        prev_z = self.ball_z
        self.ball_x += self.ball_vx
        self.ball_z += self.ball_vz

        if self.ball_x < 0.0:
            self.ball_x = 0.0
            self.ball_vx *= -1
            self._play_ball_sound()
        elif self.ball_x > 1.0:
            self.ball_x = 1.0
            self.ball_vx *= -1
            self._play_ball_sound()

        # --- Deteksi tabrakan bola dengan paddle player ---
        if prev_z >= 0.0 and self.ball_z < 0.0:
            if abs(self.ball_x - self.player_x) <= PADDLE_WIDTH / 2.0:
                self.ball_z = 0.0
                self.ball_vz *= -1.05
                swing_impact = self.player_dx * 0.6
                pos_impact = (self.ball_x - self.player_x) * 0.05
                self.ball_vx = pos_impact + swing_impact
                self._play_ball_sound()
            else:
                self._trigger_point('AI')
                return

        # --- Deteksi tabrakan bola dengan paddle AI ---
        if prev_z <= 1.0 and self.ball_z > 1.0:
            if abs(self.ball_x - self.ai_x) <= PADDLE_WIDTH / 2.0:
                self.ball_z = 1.0
                self.ball_vz *= -1.05
                
                if self.player_x < 0.5:
                    target_x = random.uniform(0.6, 0.9)
                else:
                    target_x = random.uniform(0.1, 0.4)
                    
                if self.difficulty_stars <= 3.5 and random.random() < 0.5:
                    target_x = self.ball_x + random.uniform(-0.2, 0.2)
                
                frames_to_reach = 1.0 / abs(self.ball_vz)
                self.ball_vx = (target_x - self.ball_x) / frames_to_reach
                
                self.ball_vx = max(-0.04, min(0.04, self.ball_vx))
                
                self._play_ball_sound()
            else:
                self._trigger_point('PLAYER')
                return
