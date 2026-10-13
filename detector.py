"""Local manga panel detection, polygon editing helpers, and lossless export."""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageOps, ImageDraw


@dataclass
class Panel:
    points: list[list[float]]
    confidence: float = 1.0
    note: str = ""

    @property
    def bounds(self):
        p = np.asarray(self.points)
        return [float(p[:, 0].min()), float(p[:, 1].min()), float(p[:, 0].max()), float(p[:, 1].max())]


def read_image(path):
    with Image.open(path) as original:
        return ImageOps.exif_transpose(original).convert('RGB').copy()


def natural_key(value):
    return [int(s) if s.isdigit() else s.lower() for s in re.split(r'(\d+)', str(value))]


def reading_order(panels):
    """Partial order: vertically separated panels first, overlapping columns right first."""
    b = [p.bounds for p in panels]
    edges = [set() for _ in panels]
    for i, a in enumerate(b):
        for j, c in enumerate(b):
            if i == j:
                continue
            overlap = min(a[3], c[3]) - max(a[1], c[1])
            height = min(a[3] - a[1], c[3] - c[1])
            if a[3] <= c[1] + 4:
                edges[i].add(j)
            elif overlap >= height * .30 and a[0] >= c[2] - 6:
                edges[i].add(j)
    result, remaining = [], set(range(len(panels)))
    while remaining:
        available = [i for i in remaining if not any(i in edges[j] for j in remaining)]
        if not available:
            available = list(remaining)
        index = min(available, key=lambda i: (b[i][1], -b[i][2]))
        result.append(panels[index]); remaining.remove(index)
    return result


def _lines_and_regions(rgb, white_level=225, sensitivity=1.0):
    h, w = rgb.shape[:2]
    white = np.uint8((rgb.min(2) > white_level) & (np.ptp(rgb, axis=2) < 32)) * 255
    _, labels, _, _ = cv2.connectedComponentsWithStats(white)
    ids = np.unique(np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1])))
    exterior = np.uint8(np.isin(labels, ids[ids != 0])) * 255
    distance = cv2.distanceTransform(255 - exterior, cv2.DIST_L2, 3)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    near_dark = cv2.dilate(np.uint8(gray < 90), np.ones((7, 7), np.uint8))
    edges = cv2.Canny(exterior, 50, 100)
    unit = h / 2048
    raw = cv2.HoughLinesP(edges, 1, np.pi / 1800, max(38, int(90 * unit)),
                          minLineLength=max(70, int(170 * unit / sensitivity)),
                          maxLineGap=max(70, int(350 * unit)))
    lines = []
    if raw is not None:
        for x1, y1, x2, y2 in raw[:, 0]:
            length = np.hypot(x2 - x1, y2 - y1)
            xs = np.linspace(x1, x2, max(30, int(length))).astype(int)
            ys = np.linspace(y1, y2, max(30, int(length))).astype(int)
            support = np.mean(distance[ys, xs] < max(4, 6 * unit))
            darkness = np.mean(near_dark[ys, xs])
            if support < .68 or darkness < .65:
                continue
            a, b = np.array((x1, y1), float), np.array((x2, y2), float)
            direction = (b - a) / length
            lines.append([a - direction * 20 * unit, b + direction * 20 * unit])
    # Complete short missing pieces at T junctions. Do not extend a separator
    # across unrelated rows; only join nearby intersections on existing lines.
    originals = [(a.copy(), b.copy()) for a, b in lines]
    for i, (a, b) in enumerate(originals):
        d = b - a
        for j, (c, e) in enumerate(originals):
            if i == j:
                continue
            v = e - c
            den = d[0] * v[1] - d[1] * v[0]
            if abs(den) < 1:
                continue
            z = c - a
            t = (z[0] * v[1] - z[1] * v[0]) / den
            u = (z[0] * d[1] - z[1] * d[0]) / den
            if -.05 <= u <= 1.05:
                p = a + t * d
                if t < 0 and np.linalg.norm(p - a) < 130 * unit:
                    lines[i][0] = p
                elif t > 1 and np.linalg.norm(p - b) < 130 * unit:
                    lines[i][1] = p
    barrier = np.zeros((h, w), np.uint8)
    for a, b in lines:
        cv2.line(barrier, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), 255, max(3, round(5 * unit)))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(255 - barrier)
    candidates = []
    for i in range(1, count):
        x, y, rw, rh, area = stats[i]
        if area < w * h * .012 or min(rw, rh) < min(w, h) * .035:
            continue
        mask = labels == i
        content = np.mean(rgb.min(2)[mask] < 210)
        if content < .20:
            continue
        original_contours, _ = cv2.findContours(mask.astype('uint8'), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        original_contour = max(original_contours, key=cv2.contourArea)
        original_hull = cv2.convexHull(original_contour)
        needs_cleanup = cv2.contourArea(original_hull) > 1.10 * max(1, cv2.contourArea(original_contour))
        # Remove narrow white margin branches before the hull. Otherwise an
        # unclosed outer border can make a hull jump across a neighboring panel.
        kernel_size = max(9, int(w * .09) | 1)
        cleaned = cv2.morphologyEx(mask.astype('uint8'), cv2.MORPH_OPEN,
                                 cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size)))
        contours, _ = cv2.findContours(cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue
        contour = max(contours, key=cv2.contourArea) if needs_cleanup else original_contour
        hull = cv2.convexHull(contour)
        fine = cv2.approxPolyDP(hull, max(1, unit), True).reshape(-1, 2)
        major = []
        for k, a in enumerate(fine):
            b = fine[(k + 1) % len(fine)]
            if np.linalg.norm(b - a) >= w * .09:
                major.append((a.astype(float), b.astype(float)))
        polygon = cv2.approxPolyDP(hull, max(1.3, unit * 2.3), True).reshape(-1, 2)
        if needs_cleanup and len(major) >= 3:
            corners = []
            for k, (a, b) in enumerate(major):
                c, e = major[k - 1]; d, v = b - a, e - c
                den = d[0] * v[1] - d[1] * v[0]
                if abs(den) < 1:
                    continue
                z = c - a; t = (z[0] * v[1] - z[1] * v[0]) / den
                corners.append(a + t * d)
            if len(corners) >= 3:
                corners = np.asarray(corners)
                corners[:, 0] = np.clip(corners[:, 0], 0, w - 1)
                corners[:, 1] = np.clip(corners[:, 1], 0, h - 1)
                if cv2.isContourConvex(corners.astype(np.float32)):
                    polygon = corners
        if len(polygon) < 3:
            continue
        confidence = .92
        note = ''
        if area > w * h * .43:
            confidence, note = .48, 'Khung lớn: kiểm tra chữ hiệu ứng nối qua viền hoặc panel bị dính.'
        if len(polygon) > 8:
            confidence, note = .58, 'Viền nhiều góc: kiểm tra đường cắt.'
        candidates.append(Panel(polygon.astype(float).tolist(), confidence, note))
    for i, panel in enumerate(candidates):
        for other in candidates[i + 1:]:
            pa, pb = np.asarray(panel.points, np.float32), np.asarray(other.points, np.float32)
            overlap, _ = cv2.intersectConvexConvex(pa, pb)
            if overlap > .02 * min(cv2.contourArea(pa), cv2.contourArea(pb)):
                panel.confidence = other.confidence = .40
                panel.note = other.note = 'Đường cắt chồng nhau: kiểm tra panel và kéo góc để sửa.'
    return candidates, len(lines)


def detect_panels(image, sensitivity=1.0):
    image = image.convert('RGB')
    scale = min(1.0, 2048 / max(image.size))
    small = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    candidates, line_count = _lines_and_regions(np.array(small), sensitivity=sensitivity)
    if not candidates or line_count < 3:
        # Conservative fallback rather than silently destroying borderless art.
        candidates = [Panel([[0, 0], [small.width - 1, 0], [small.width - 1, small.height - 1], [0, small.height - 1]],
                            .25, 'Chưa đủ viền rõ; thêm hoặc chia đa giác trên ảnh.')]
    for panel in candidates:
        panel.points = [[round(x / scale, 2), round(y / scale, 2)] for x, y in panel.points]
    return reading_order(candidates)


def split_polygon(points, a, b):
    """Clip a convex polygon against the two half-planes of an arbitrary cut."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    def side(p):
        d = b - a; p = np.asarray(p) - a
        return d[0] * p[1] - d[1] * p[0]
    outputs = []
    for sign in (1, -1):
        out = []
        for i, q in enumerate(points):
            p = points[i - 1]; sp, sq = sign * side(p), sign * side(q)
            if (sp >= 0) != (sq >= 0):
                t = sp / (sp - sq)
                out.append((np.asarray(p) + t * (np.asarray(q) - p)).tolist())
            if sq >= 0:
                out.append(list(q))
        if len(out) >= 3 and abs(cv2.contourArea(np.array(out, np.float32))) > 100:
            outputs.append(out)
    return outputs


def make_crop(image, panel, background='white'):
    points = np.round(panel.points).astype(np.int32)
    mask = np.zeros((image.height, image.width), np.uint8)
    cv2.fillPoly(mask, [points], 255)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError('Panel không có diện tích.')
    bounds = (max(0, int(xs.min())), max(0, int(ys.min())), min(image.width, int(xs.max()) + 1), min(image.height, int(ys.max()) + 1))
    rgb = image.crop(bounds); alpha = Image.fromarray(mask).crop(bounds)
    rgba = rgb.copy(); rgba.putalpha(alpha)
    white = Image.new('RGB', rgb.size, 'white'); white.paste(rgb, (0, 0), alpha)
    return white, rgba, bounds


def export_page(image, panels, source, destination):
    root = Path(destination)
    flat = root / 'Flow_JPG'
    flat.mkdir(parents=True, exist_ok=True)
    destination = root / Path(source).stem
    destination.mkdir(parents=True, exist_ok=True)
    manifest = {'source': str(source), 'size': list(image.size), 'reading_order': 'top-to-bottom, right-to-left', 'panels': []}
    preview = image.copy(); draw = ImageDraw.Draw(preview)
    for number, panel in enumerate(panels, 1):
        white, rgba, bounds = make_crop(image, panel)
        name = f'panel_{number:02d}'
        white.save(destination / f'{name}.jpg', quality=97, subsampling=0)
        white.save(flat / f'{Path(source).stem}_{name}.jpg', quality=97, subsampling=0)
        rgba.save(destination / f'{name}_alpha.png')
        points = [tuple(p) for p in panel.points]
        draw.line(points + [points[0]], fill='#ff4757', width=max(3, image.width // 220))
        draw.text(points[0], str(number), fill='yellow', stroke_width=2, stroke_fill='black')
        manifest['panels'].append({'index': number, 'polygon': panel.points, 'bounds': bounds, 'confidence': panel.confidence, 'note': panel.note, 'flow_image': f'{name}.jpg', 'transparent_image': f'{name}_alpha.png'})
    preview.thumbnail((1300, 1800)); preview.save(destination / 'duong_cat.jpg', quality=92)
    (destination / 'panels.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return destination


def save_session(entries, destination):
    data = []
    for entry in entries:
        data.append({'source': str(entry['path']), 'panels': [vars(p) for p in entry['panels']]})
    Path(destination).write_text(json.dumps({'version': 1, 'pages': data}, ensure_ascii=False, indent=2), encoding='utf-8')


def load_session(path):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    return [{'path': Path(e['source']), 'image': read_image(e['source']), 'panels': [Panel(**p) for p in e['panels']]} for e in raw['pages']]
