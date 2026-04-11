import math
import random
import time
import colorsys

GRID_SIZE = 10
CORNERS   = {(0, 0), (0, 9), (9, 0), (9, 9)}


def empty_grid():
    return [[(0, 0, 0)] * GRID_SIZE for _ in range(GRID_SIZE)]


def scale_color(c, factor):
    return (
        min(255, max(0, int(c[0] * factor))),
        min(255, max(0, int(c[1] * factor))),
        min(255, max(0, int(c[2] * factor))),
    )


# ---------------------------------------------------------------------------
# Animations
# ---------------------------------------------------------------------------

class Vortex:
    """Rotating hypnotic spiral that fills the full 10x10 grid."""
    name = "Vortex"

    def __init__(self, palette):
        self.palette = palette
        self.t = 0.0

    def next_frame(self):
        grid = empty_grid()
        cx, cy = 4.5, 4.5
        n = len(self.palette)
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                dx = col - cx
                dy = row - cy
                dist  = math.sqrt(dx * dx + dy * dy) + 1e-6
                angle = math.atan2(dy, dx)
                phase = (angle / math.pi + dist * 0.35 - self.t * 1.4) % 2.0
                brightness = (math.sin(phase * math.pi) + 1) / 2
                brightness *= max(0.0, 1.0 - dist / 7.2)
                t_idx = (angle / (2 * math.pi) + 0.5 + self.t * 0.12) % 1.0
                idx = int(t_idx * n) % n
                grid[row][col] = scale_color(self.palette[idx], brightness)
        self.t += 0.10
        return grid


class Snake:
    name = "Snake"

    def __init__(self, palette):
        self.palette = palette
        self._reset()

    def _reset(self):
        self.body      = [(5, 5), (5, 4), (5, 3)]
        self.direction = (0, 1)
        self.fades     = {}
        self.step      = 0

    def next_frame(self):
        grid = empty_grid()

        if self.step % 3 == 0:
            head     = self.body[0]
            new_head = (
                (head[0] + self.direction[0]) % GRID_SIZE,
                (head[1] + self.direction[1]) % GRID_SIZE,
            )
            if random.random() < 0.25:
                dirs     = [(0, 1), (0, -1), (1, 0), (-1, 0)]
                opposite = (-self.direction[0], -self.direction[1])
                dirs     = [d for d in dirs if d != opposite]
                self.direction = random.choice(dirs)
            self.body.insert(0, new_head)
            if len(self.body) > 18:
                tail = self.body.pop()
                self.fades[tail] = 1.0

        for pos in list(self.fades):
            self.fades[pos] -= 0.12
            if self.fades[pos] <= 0:
                del self.fades[pos]
            else:
                grid[pos[0]][pos[1]] = scale_color(self.palette[0], self.fades[pos] * 0.5)

        for i, pos in enumerate(self.body):
            brightness = 1.0 - (i / len(self.body)) * 0.75
            idx = i % len(self.palette)
            grid[pos[0]][pos[1]] = scale_color(self.palette[idx], brightness)

        self.step += 1
        return grid


class Ripple:
    name = "Ripple"

    def __init__(self, palette):
        self.palette = palette
        self.t = 0.0

    def next_frame(self):
        grid = empty_grid()
        cx, cy = 4.5, 4.5
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                dist = math.sqrt((row - cx) ** 2 + (col - cy) ** 2)
                wave = (math.sin(dist * 1.6 - self.t * 2.2) + 1) / 2
                brightness = wave * max(0.0, 1.0 - dist / 6.5)
                idx = int(dist) % len(self.palette)
                grid[row][col] = scale_color(self.palette[idx], brightness)
        self.t += 0.2
        return grid


class RainbowFlow:
    name = "Rainbow Flow"

    def __init__(self, palette):
        self.palette = palette
        self.t = 0.0

    def next_frame(self):
        grid = empty_grid()
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                hue = (col / GRID_SIZE + row / (GRID_SIZE * 2) + self.t) % 1.0
                r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
                grid[row][col] = (int(r * 255), int(g * 255), int(b * 255))
        self.t += 0.018
        return grid


class Sparkle:
    name = "Sparkle"

    def __init__(self, palette):
        self.palette = palette
        self.sparks  = {}

    def next_frame(self):
        grid = empty_grid()
        for _ in range(random.randint(1, 4)):
            if random.random() < 0.5:
                r = random.randint(0, GRID_SIZE - 1)
                c = random.randint(0, GRID_SIZE - 1)
                if (r, c) not in CORNERS:
                    self.sparks[(r, c)] = (1.0, random.choice(self.palette))

        for pos in list(self.sparks):
            brightness, color = self.sparks[pos]
            grid[pos[0]][pos[1]] = scale_color(color, brightness)
            new_b = brightness - 0.09
            if new_b <= 0:
                del self.sparks[pos]
            else:
                self.sparks[pos] = (new_b, color)
        return grid


class Aurora:
    """Northern-lights style bands drifting across the full grid."""
    name = "Aurora"

    def __init__(self, palette):
        self.palette = palette
        self.t = 0.0

    def next_frame(self):
        grid = empty_grid()
        n = len(self.palette)
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                w1 = math.sin(row * 0.75 + col * 0.28 + self.t * 0.9)
                w2 = math.sin(row * 0.42 - col * 0.18 + self.t * 0.55 + 2.1)
                w3 = math.sin(row * 1.05 + self.t * 1.05 + 1.0)
                brightness = max(0.0, (w1 + w2 + w3) / 3.0)
                t_idx = (row / (GRID_SIZE - 1) + self.t * 0.06) % 1.0
                idx   = int(t_idx * n) % n
                grid[row][col] = scale_color(self.palette[idx], brightness)
        self.t += 0.07
        return grid


class MatrixRain:
    name = "Matrix Rain"
    TRAIL = 6

    def __init__(self, palette):
        self.palette = palette
        self.drops   = [random.randint(0, GRID_SIZE + self.TRAIL) for _ in range(GRID_SIZE)]

    def next_frame(self):
        grid   = empty_grid()
        bright = self.palette[-1]
        dim    = self.palette[0]

        for col in range(GRID_SIZE):
            head = self.drops[col]
            if 0 <= head < GRID_SIZE:
                grid[head][col] = bright
            for i in range(1, self.TRAIL + 1):
                tr = head - i
                if 0 <= tr < GRID_SIZE:
                    b = 1.0 - i / self.TRAIL
                    grid[tr][col] = scale_color(dim, b * 0.8)
            if random.random() < 0.75:
                self.drops[col] = (self.drops[col] + 1) % (GRID_SIZE + self.TRAIL)
        return grid


# ---------------------------------------------------------------------------
# Plasma
# ---------------------------------------------------------------------------

class Plasma:
    """Classic demoscene plasma — three overlapping sine waves create smooth
    morphing colour blobs across the entire 10x10 grid."""
    name = "Plasma"

    def __init__(self, palette):
        self.palette = palette
        self.t = 0.0

    def next_frame(self):
        grid = empty_grid()
        n = len(self.palette)
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                v  = math.sin(col * 0.6 + self.t)
                v += math.sin(row * 0.5 + self.t * 0.7)
                v += math.sin((col + row) * 0.4 + self.t * 1.1)
                v += math.sin(math.sqrt(col * col + row * row) * 0.5 - self.t)
                # v is in roughly [-4, 4]; normalise to [0, 1]
                v = (v + 4) / 8.0
                # Map to two palette colours and blend
                scaled = v * (n - 1)
                lo     = int(scaled) % n
                hi     = (lo + 1) % n
                frac   = scaled - int(scaled)
                c1, c2 = self.palette[lo], self.palette[hi]
                grid[row][col] = (
                    int(c1[0] + (c2[0] - c1[0]) * frac),
                    int(c1[1] + (c2[1] - c1[1]) * frac),
                    int(c1[2] + (c2[2] - c1[2]) * frac),
                )
        self.t += 0.08
        return grid


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ANIMATIONS = [Vortex, Snake, Ripple, RainbowFlow, Sparkle, Aurora, MatrixRain, Plasma]

PRESETS = {
    "Ocean":      [(0,  20,  80), (0,  80, 180), (0, 180, 255), (100, 230, 255)],
    "Fire":       [(120, 0,   0), (220, 40,   0), (255, 130,  0), (255, 230,  80)],
    "Forest":     [(0,  40,   0), (0, 120,  20), (40, 180,   0), (130, 255,  40)],
    "Neon":       [(255, 0, 100), (0, 255, 150), (150,  0, 255), (255, 200,   0)],
    "Sunset":     [(100, 0,  40), (220, 40,   0), (255, 120,  40), (180,  0, 120)],
    "Ice":        [(80, 150, 255), (160, 210, 255), (230, 245, 255), (255, 255, 255)],
    "Candy":      [(255, 0, 150), (0, 200, 255), (150, 255,   0), (255, 150,   0)],
    "Monochrome": [(30,  30,  30), (90,  90,  90), (180, 180, 180), (255, 255, 255)],
    "Lava":       [(10,  0,   0), (180,  10,  0), (255,  60,  0), (255, 200, 50)],
    "Deep Space":  [(0,   0,  20), (10,   0,  80), (80,   0, 180), (180,  0, 255)],
    "Rose Gold":   [(80,  10, 20), (200,  60, 80), (255, 130, 100), (255, 210, 180)],
    "Toxic":       [(0,  60,   0), (40, 200,   0), (150, 255,  20), (220, 255, 100)],
    "Arctic":      [(0,  30,  60), (0,  100, 140), (0,  200, 220), (200, 240, 255)],
    "Ultraviolet": [(20,  0,  40), (80,   0, 160), (180, 20, 255), (255, 100, 255)],
    "Ember":       [(40,  0,   0), (100,  5,   0), (200,  30,  0), (255, 100,  10)],
    "Cyber":       [(0,  255, 180), (0,  150, 255), (100,  0, 255), (255,  0, 150)],
}
