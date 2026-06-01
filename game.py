import time
import random
import os
import pygame

# ─────────────────────────────────────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
WIN_SCORE       = 7       # first to this score wins
WEBCAM_WIDTH    = 480     # left-panel width used to normalize centroid
PADDLE_WIDTH    = 0.20    # reduced to match visual width of the paddle

# ─────────────────────────────────────────────────────────────────────────────
#  GAME CLASS
# ─────────────────────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        self.round = 1
        self.difficulty_stars = 4.0
        
        try:
            self.snd_ball = pygame.mixer.Sound(os.path.join("asset", "ball_sound.mp3"))
            self.snd_crowd = pygame.mixer.Sound(os.path.join("asset", "crowd.mp3"))
        except Exception:
            self.snd_ball = None
            self.snd_crowd = None
            
        self.crowd_channel = pygame.mixer.Channel(1)
        
        self.reset()

    def apply_difficulty(self, stars: float):
        self.difficulty_stars = stars
        self._set_speed_by_difficulty()

    def _set_speed_by_difficulty(self):
        # 3.0 stars = 0.7 speed, 5.0 stars = 1.4 speed
        self.ball_speed = 0.7 + ((self.difficulty_stars - 3.0) / 2.0) * 0.7

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

    def _reset_ball(self, toward_player: bool):
        self.ball_x  = 0.5
        self.ball_z  = 0.5
        self.ball_vx = random.choice([-1, 1]) * 0.015 * self.ball_speed
        self.ball_vz = -0.025 * self.ball_speed if toward_player else 0.025 * self.ball_speed

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
        
        if self.snd_crowd:
            self.crowd_channel.play(self.snd_crowd)

        if self.player_score >= WIN_SCORE or self.ai_score >= WIN_SCORE:
            self.state = 'game_over'
            self.winner = 'PLAYER' if self.player_score >= WIN_SCORE else 'AI'
            if self.snd_crowd:
                self.crowd_channel.play(self.snd_crowd, loops=-1)
        else:
            self.state = 'point_scored'

    def update(self, centroid):
        self.frames += 1

        if self.score_flash > 0: self.score_flash -= 1
        if self.shake_frames > 0: self.shake_frames -= 1

        # State: GAME OVER
        if self.state == 'game_over':
            return

        # State: POINT SCORED (Pause before next round)
        if self.state == 'point_scored':
            if time.time() - self._point_timer > 1.5:
                self.state = 'playing'
                self.crowd_channel.stop()
                self.round += 1
                self._reset_ball(toward_player=(self._point_scorer == 'AI'))
            return

        # State: WAITING FOR HAND
        if self.state == 'waiting':
            if not self.crowd_channel.get_busy() and self.snd_crowd:
                self.crowd_channel.play(self.snd_crowd, loops=-1)
                
            if centroid is not None:
                if self._hand_seen_since is None:
                    self._hand_seen_since = time.time()
                elif time.time() - self._hand_seen_since > 1.5:
                    self.state = 'playing'
                    self.crowd_channel.stop()
                    self._reset_ball(toward_player=True)
            else:
                self._hand_seen_since = None
            return

        # State: PLAYING
        # 1. Update Player position
        if centroid is not None:
            cx, cy = centroid
            self._prev_player_x = self.player_x
            
            # Sensitivity Boost: Map the middle 60% of the webcam to the full table width.
            # This means you don't have to move your hand all the way to the edge of the camera.
            normalized_cx = (cx - (0.2 * WEBCAM_WIDTH)) / (0.6 * WEBCAM_WIDTH)
            self.player_x = max(0.0, min(1.0, normalized_cx))
            # EMA smoothing could be done here, but simple delta is fine
            self.player_dx = self.player_x - self._prev_player_x

        # 2. Update AI position
        # AI speed scaled by stars (3.0 -> 0.01, 5.0 -> 0.035)
        ai_speed_mult = 0.01 + ((self.difficulty_stars - 3.0) / 2.0) * 0.025
        ai_speed = ai_speed_mult * self.ball_speed
        diff = self.ball_x - self.ai_x
        self.ai_x += max(-ai_speed, min(ai_speed, diff))
        self.ai_x = max(0.0, min(1.0, self.ai_x))

        # 3. Move Ball
        prev_z = self.ball_z
        self.ball_x += self.ball_vx
        self.ball_z += self.ball_vz

        # 4. Wall Bounce (X-axis)
        if self.ball_x < 0.0:
            self.ball_x = 0.0
            self.ball_vx *= -1
            if self.snd_ball: self.snd_ball.play()
        elif self.ball_x > 1.0:
            self.ball_x = 1.0
            self.ball_vx *= -1
            if self.snd_ball: self.snd_ball.play()

        # 5. Paddle Hit Detection (Z-axis)
        # Player Hit (Z crosses 0)
        if prev_z >= 0.0 and self.ball_z < 0.0:
            if abs(self.ball_x - self.player_x) <= PADDLE_WIDTH / 2.0:
                self.ball_z = 0.0
                self.ball_vz *= -1.05  # slight speedup
                # Combine position impact (where on bat) + swing impact (hand movement direction)
                swing_impact = self.player_dx * 0.6
                pos_impact = (self.ball_x - self.player_x) * 0.05
                self.ball_vx = pos_impact + swing_impact
                if self.snd_ball: self.snd_ball.play()
            else:
                self._trigger_point('AI')
                return

        # AI Hit (Z crosses 1)
        if prev_z <= 1.0 and self.ball_z > 1.0:
            if abs(self.ball_x - self.ai_x) <= PADDLE_WIDTH / 2.0:
                self.ball_z = 1.0
                self.ball_vz *= -1.05
                
                # AI Target Logic: Aim at the empty side
                if self.player_x < 0.5:
                    target_x = random.uniform(0.6, 0.9)
                else:
                    target_x = random.uniform(0.1, 0.4)
                    
                # Chance to make a mistake on lower difficulty
                if self.difficulty_stars <= 3.5 and random.random() < 0.5:
                    target_x = self.ball_x + random.uniform(-0.2, 0.2)
                
                # Calculate vx to reach target_x
                # Time = distance_z / speed_z = 1.0 / abs(ball_vz)
                frames_to_reach = 1.0 / abs(self.ball_vz)
                self.ball_vx = (target_x - self.ball_x) / frames_to_reach
                
                # Cap the speed
                self.ball_vx = max(-0.04, min(0.04, self.ball_vx))
                
                if self.snd_ball: self.snd_ball.play()
            else:
                self._trigger_point('PLAYER')
                return
