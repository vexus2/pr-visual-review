"""Deterministic screenshot annotations and Before | After composites. Pillow is optional until export."""
import copy
import hashlib
import json
import math
from pathlib import Path

COLORS = {'change': '#1767bd', 'issue': '#c13928', 'reference': '#596979'}
# Composite layout: two panels side by side, each with a label above it.
PANEL_GAP, PANEL_PAD, PANEL_HEAD = 24, 24, 44
PANEL_BG, PANEL_INK, PANEL_LINE = (246, 248, 250), (38, 52, 69), (203, 213, 225)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def marks(case, side):
    return [a for a in case.get('annotations', []) if side in a]


def validate(case):
    annotations = case.get('annotations', [])
    require(isinstance(annotations, list) and len(annotations) <= 20, 'annotations must be an array of at most 20 regions')
    seen = set()
    for a in annotations:
        require(isinstance(a, dict) and set(a).issubset({'id', 'kind', 'label', 'before', 'after', 'issue_index'}),
                'invalid annotation fields')
        require(type(a.get('id')) is int and 1 <= a['id'] <= 99 and a['id'] not in seen, 'annotation IDs must be unique integers 1..99')
        seen.add(a['id'])
        require(a.get('kind') in ('change', 'issue'), 'annotation kind must be change or issue')
        require(isinstance(a.get('label'), str) and 0 < len(a['label'].strip()) <= 300, 'annotation label required (maximum 300 characters)')
        require('before' in a or 'after' in a, 'annotation must point to a captured side')
        require(case['result'] != 'unverified', 'unverified cases cannot carry visual annotations')
        if a['kind'] == 'change':
            require(case['result'] != 'unchanged', 'unchanged cases cannot claim a changed region')
            require('issue_index' not in a, 'change annotations must not reference an issue')
        else:
            index = a.get('issue_index')
            require(type(index) is int and 0 <= index < len(case.get('issues', [])), 'issue annotation requires a valid issue_index')
        for side in ('before', 'after'):
            if side not in a:
                continue
            require(case[side]['state'] == 'captured', 'annotations require a captured image')
            box = a[side]
            require(isinstance(box, dict) and set(box) == {'x', 'y', 'width', 'height'}, 'annotation box requires x/y/width/height')
            require(all(type(v) in (int, float) and math.isfinite(v) for v in box.values()), 'annotation coordinates must be finite numbers')
            require(0 <= box['x'] <= 1 and 0 <= box['y'] <= 1 and box['width'] > 0 and box['height'] > 0
                    and box['x'] + box['width'] <= 1 and box['y'] + box['height'] <= 1,
                    'annotation box must fit within the original image (normalized 0..1 coordinates)')


def composable(case):
    """A composite needs real captures on both sides."""
    return case['before']['state'] == 'captured' and case['after']['state'] == 'captured'


def fingerprint(case, side, root):
    selected = marks(case, side)
    metadata = {'version': 1, 'side': side, 'marks': selected,
                'issues': [case['issues'][a['issue_index']] for a in selected if a['kind'] == 'issue']}
    source = (Path(root) / case[side]['image']).read_bytes()
    return hashlib.sha256(source + json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def composite_fingerprint(case, root):
    # version 2: side-by-side layout without the Diff panel
    metadata = {'version': 2, 'marks': case.get('annotations', []), 'issues': case.get('issues', [])}
    sources = b''.join((Path(root) / case[side]['image']).read_bytes() for side in ('before', 'after'))
    return hashlib.sha256(sources + json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _check_file(root, relative, expected_sha, message):
    path = (Path(root) / relative).resolve()
    require(path.is_relative_to(Path(root).resolve()) and path.is_file(), message)
    require(hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha, message)


def verify_derivative(case, side, root):
    capture = case[side]
    require(isinstance(capture.get('annotated_image'), str), 'Run annotate and upload its PNG before rendering annotated Markdown')
    require(capture.get('annotation_fingerprint') == fingerprint(case, side, root),
            'Stale annotation: source/regions changed; run annotate again')
    _check_file(root, capture['annotated_image'], capture.get('annotated_sha256'), 'Annotation PNG missing or changed; run annotate again')


def verify_composite(case, root):
    require(isinstance(case.get('composite_image'), str), 'composite_image must be a path written by annotate')
    require(case.get('composite_fingerprint') == composite_fingerprint(case, root),
            'Stale composite: source images or regions changed; run annotate again')
    _check_file(root, case['composite_image'], case.get('composite_sha256'), 'Composite PNG missing or changed; run annotate again')


def _load(path):
    from PIL import Image, ImageOps
    with Image.open(path) as original:
        require(original.format in ('PNG', 'JPEG', 'WEBP'), 'unsupported annotation source format')
        image = ImageOps.exif_transpose(original).convert('RGBA')
        image.info.clear()
    require(image.width >= 40 and image.height >= 40, 'annotation screenshot too small')
    return image


def draw_marks(image, selected, side):
    """Draw numbered frames on a copy of `image`. Before frames are gray references."""
    from PIL import ImageDraw, ImageFont
    image = image.copy()
    width, height = image.size
    draw = ImageDraw.Draw(image)
    stroke = max(2, min(5, round(min(width, height) / 160)))
    font = ImageFont.load_default(size=max(13, min(22, round(width / 50))))
    for a in selected:
        box = a[side]
        x0, y0 = round(box['x'] * (width - 1)), round(box['y'] * (height - 1))
        x1 = min(width - 1, round((box['x'] + box['width']) * (width - 1)))
        y1 = min(height - 1, round((box['y'] + box['height']) * (height - 1)))
        color = COLORS['reference' if side == 'before' else a['kind']]
        draw.rectangle((x0, y0, x1, y1), outline=color, width=stroke)
        tag = f"{a['id']} " + ('REF' if side == 'before' else a['kind'].upper())
        bounds = draw.textbbox((0, 0), tag, font=font)
        tag_w, tag_h = bounds[2] - bounds[0] + 12, bounds[3] - bounds[1] + 10
        # Keep the badge inside the image even for regions near an edge.
        tx, ty = max(0, min(x0, width - tag_w)), max(0, min(y0, height - tag_h))
        draw.rectangle((tx, ty, tx + tag_w, ty + tag_h), fill=color)
        draw.text((tx + 6 - bounds[0], ty + 5 - bounds[1]), tag, fill='white', font=font)
    return image


def compose(before, after, case):
    """Before | After side by side at the same scale, frames included, so the reader compares one image."""
    from PIL import Image, ImageDraw, ImageFont
    size = (max(before.width, after.width), max(before.height, after.height))

    def pad(image):
        canvas = Image.new('RGBA', size, (255, 255, 255, 255))
        canvas.paste(image, (0, 0))
        return canvas
    panels = [('Before', pad(draw_marks(before, marks(case, 'before'), 'before'))),
              ('After', pad(draw_marks(after, marks(case, 'after'), 'after')))]
    out = Image.new('RGBA', (PANEL_PAD * 2 + size[0] * 2 + PANEL_GAP, PANEL_PAD * 2 + PANEL_HEAD + size[1]), PANEL_BG + (255,))
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=20)
    x, top = PANEL_PAD, PANEL_PAD + PANEL_HEAD
    for label, image in panels:
        draw.text((x, PANEL_PAD + 8), label, fill=PANEL_INK, font=font)
        out.alpha_composite(image, (x, top))
        draw.rectangle((x, top, x + size[0] - 1, top + size[1] - 1), outline=PANEL_LINE)
        x += size[0] + PANEL_GAP
    return out


def _save(image, destination, root, originals):
    require(not destination.is_symlink(), 'annotation output file must not be a symlink')
    require(all(destination.resolve() != (root / original).resolve() for original in originals),
            'refusing to overwrite an original screenshot')
    image.save(destination, format='PNG')
    return destination.relative_to(root).as_posix(), hashlib.sha256(destination.read_bytes()).hexdigest()


def export(report, root):
    """Write one Before | After composite per case with both captures (frames included), and a
    per-side annotated PNG only for marked sides of cases that have a single capture.

    Input paths/cases must already have passed the report validator.
    """
    result = copy.deepcopy(report)
    needed = any(case.get('annotations') or composable(case) for case in result['cases'])
    if not needed:
        return result
    try:
        import PIL  # noqa: F401
    except ImportError as error:
        raise RuntimeError('PNG export needs Pillow: python3 -m pip install -r /PATH/TO/SKILL/requirements-annotations.txt') from error
    root = Path(root).resolve()
    output = root / 'annotated'
    require(not output.is_symlink(), 'annotation output directory must not be a symlink')
    output.mkdir(exist_ok=True)
    for case in result['cases']:
        for key in ('composite_image', 'composite_sha256', 'composite_fingerprint', 'composite_url'):
            case.pop(key, None)
        originals = [case[side]['image'] for side in ('before', 'after') if case[side]['state'] == 'captured']
        images = {}
        for side in ('before', 'after'):
            capture = case[side]
            for key in ('annotated_image', 'annotated_sha256', 'annotation_fingerprint', 'annotated_url'):
                capture.pop(key, None)
            if capture['state'] == 'captured':
                images[side] = _load(root / capture['image'])
            selected = marks(case, side)
            if not selected or composable(case):
                continue
            stamp = fingerprint(case, side, root)
            relative, digest = _save(draw_marks(images[side], selected, side), output / f"{case['id']}-{side}-{stamp[:16]}.png",
                                     root, originals)
            capture.update(annotated_image=relative, annotated_sha256=digest, annotation_fingerprint=stamp)
        if composable(case):
            stamp = composite_fingerprint(case, root)
            relative, digest = _save(compose(images['before'], images['after'], case),
                                     output / f"{case['id']}-composite-{stamp[:16]}.png", root, originals)
            case.update(composite_image=relative, composite_sha256=digest, composite_fingerprint=stamp)
    return result
