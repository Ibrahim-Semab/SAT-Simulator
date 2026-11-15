"""Render the drawn pieces (equations) of a PDF page to small transparent WebPs, black ink on alpha.
The page is rendered once at high resolution and every piece is cut out of that bitmap."""
import hashlib, os
import numpy as np
from PIL import Image

SCALE = 4.0          # 4x = 288 dpi: vector maths stays sharp at any zoom the app uses
PAD = 0.7

class PageRaster:
    def __init__(self, page):
        self.page = page; self.W, self.H = page.get_size(); self.a = None
    def rgb(self):
        if getattr(self, '_rgb', None) is None: self._rgb = self.page.render(scale=SCALE).to_pil().convert('RGB')
        return self._rgb
    def alpha(self):
        if self.a is None:
            self.a = 255 - np.array(self.rgb().convert('L')); self.a[self.a < 12] = 0          # drop paper noise
        return self.a

def render_piece(pr, box, out_dir):
    x0, y0, x1, y1 = box
    c0 = max(0, int((x0 - PAD) * SCALE)); r0 = max(0, int((y0 - PAD) * SCALE))
    c1 = min(pr.alpha().shape[1], int(round((x1 + PAD) * SCALE))); r1 = min(pr.alpha().shape[0], int(round((y1 + PAD) * SCALE)))
    a = pr.alpha()[r0:r1, c0:c1]
    key = hashlib.sha1(a.tobytes() + repr(a.shape).encode()).hexdigest()[:12]
    path = os.path.join(out_dir, key + '.webp')
    if not os.path.exists(path):
        rgba = np.zeros(a.shape + (4,), np.uint8); rgba[..., 3] = a
        Image.fromarray(rgba, 'RGBA').save(path, lossless=True, quality=100, method=4)
    return key, a.shape[1] / SCALE, a.shape[0] / SCALE, (r0 / SCALE, r1 / SCALE)   # key, width pt, height pt, vertical extent
