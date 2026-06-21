import cv2
import numpy as np

# --- Operasi Morfologi Manual (Erode, Dilate, Opening, Closing) ---
def manual_erode(mask: np.ndarray, ksize: int = 3) -> np.ndarray:
    pad = ksize // 2
    padded = np.pad(mask, pad, mode='constant', constant_values=0)
    result = np.ones_like(mask) * 255
    for i in range(ksize):
        for j in range(ksize):
            result = np.minimum(result, padded[i:i + mask.shape[0], j:j + mask.shape[1]])
    return result

def manual_dilate(mask: np.ndarray, ksize: int = 3) -> np.ndarray:
    pad = ksize // 2
    padded = np.pad(mask, pad, mode='constant', constant_values=0)
    result = np.zeros_like(mask)
    for i in range(ksize):
        for j in range(ksize):
            result = np.maximum(result, padded[i:i + mask.shape[0], j:j + mask.shape[1]])
    return result

def manual_opening(mask: np.ndarray, ksize: int = 3) -> np.ndarray:
    return manual_dilate(manual_erode(mask, ksize), ksize)

def manual_closing(mask: np.ndarray, ksize: int = 3) -> np.ndarray:
    return manual_erode(manual_dilate(mask, ksize), ksize)

class HandDetector:

    # --- Threshold warna kulit (HSV) ---
    LOWER_SKIN = np.array([90,  45,  20], dtype=np.uint8)
    UPPER_SKIN = np.array([130, 255, 255], dtype=np.uint8)

    MIN_HAND_AREA = 1500

    def __init__(self):
        self.centroid = None
        self.contour  = None

    def process(self, bgr_frame: np.ndarray):
        h, w = bgr_frame.shape[:2]

        # --- Konversi BGR ke HSV & segmentasi warna kulit ---
        hsv = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2HSV)

        condition = np.all((hsv >= self.LOWER_SKIN) & (hsv <= self.UPPER_SKIN), axis=2)
        mask = np.where(condition, np.uint8(255), np.uint8(0))

        # --- Downscale + morphological cleaning (noise removal) ---
        small = mask[::2, ::2]
        cleaned_small = manual_opening(small, ksize=3)
        cleaned_small = manual_closing(cleaned_small, ksize=3)

        cleaned = np.repeat(np.repeat(cleaned_small, 2, axis=0), 2, axis=1)
        cleaned = cleaned[:h, :w]

        # --- Deteksi kontur tangan ---
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        self.centroid = None
        self.contour  = None

        gesture = "NO_HAND"
        if contours:
            largest = max(contours, key=cv2.contourArea)
            area    = cv2.contourArea(largest)

            if area >= self.MIN_HAND_AREA:
                self.contour = largest
                # --- Hitung centroid (titik pusat tangan) via moments ---
                M = cv2.moments(largest)
                if M['m00'] != 0:
                    cx = int(M['m10'] / M['m00'])
                    cy = int(M['m01'] / M['m00'])
                    self.centroid = (cx, cy)
                
                # --- Gesture recognition via convex hull solidity ---
                hull = cv2.convexHull(largest)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = area / float(hull_area)
                    gesture = "FIST" if solidity > 0.88 else "OPEN"

        # --- Visualisasi debug (kontur, bounding box, centroid) ---
        debug_frame = bgr_frame.copy()

        if self.contour is not None:
            cv2.drawContours(debug_frame, [self.contour], -1, (0, 255, 0), 2)
            x, y, bw, bh = cv2.boundingRect(self.contour)
            cv2.rectangle(debug_frame, (x, y), (x + bw, y + bh), (0, 255, 255), 1)

        if self.centroid is not None:
            cx, cy = self.centroid
            cv2.circle(debug_frame, (cx, cy), 8, (255, 0, 0), -1)
            cv2.line(debug_frame, (0, cy), (w, cy), (255, 255, 255), 1)

        cv2.putText(debug_frame, f"HAND: {gesture}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0) if self.centroid else (0, 0, 255), 2)

        cv2.putText(debug_frame, "LEFT HAND PANEL", (10, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)

        return self.centroid, gesture, debug_frame
