"""Deterministic screenshot annotations and Before/After/Diff composites. Pillow is optional until export."""
import copy
import difflib
import hashlib
import json
import math
from pathlib import Path

COLORS = {'change': '#1767bd', 'issue': '#c13928', 'reference': '#596979'}
# Composite layout and diff colors.
PANEL_GAP, PANEL_PAD, PANEL_HEAD, GUTTER = 24, 24, 44, 14
PANEL_BG, PANEL_INK, PANEL_LINE = (246, 248, 250), (38, 52, 69), (203, 213, 225)
DIFF_CHANGED, DIFF_INSERTED, DIFF_REMOVED = (214, 40, 64), (23, 103, 189), (140, 140, 140)
HORIZONTAL_MAX_WIDTH = 600   # wider captures stack vertically so GitHub does not shrink them to thumbnails
MIN_BAND = 6                 # inserted/removed bands shorter than this are treated as in-place pixel changes
DIFF_THRESHOLD = 24          # per-channel difference (0..255) that counts as a changed pixel


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
    metadata = {'version': 1, 'marks': case.get('annotations', []), 'issues': case.get('issues', [])}
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


def _row_keys(image, step=8, levels=8):
    """Coarse per-row signatures so a one-pixel anti-aliasing shift does not break row matching."""
    from PIL import Image
    small = image.convert('L').resize((max(1, image.width // step), image.height), Image.BOX)
    quantized = small.point(lambda v: v * levels // 256)
    data, width = quantized.tobytes(), quantized.width
    return [data[y * width:(y + 1) * width] for y in range(quantized.height)]


def align_rows(before, after):
    """Return (before_range, after_range) blocks to compare in place, plus inserted/removed row bands in After coordinates.

    Rows are matched with difflib. Short equal runs between differences are merged into the surrounding
    change so that slightly shifted text becomes an in-place pixel diff instead of a false inserted band.
    """
    opcodes = difflib.SequenceMatcher(None, _row_keys(before), _row_keys(after), autojunk=False).get_opcodes()
    merged = []
    for tag, i1, i2, j1, j2 in opcodes:
        if tag == 'equal' and i2 - i1 < MIN_BAND and merged and merged[-1][0] != 'equal':
            tag = 'change'
        elif tag == 'equal':
            merged.append(['equal', i1, i2, j1, j2])
            continue
        if merged and merged[-1][0] == 'change':
            merged[-1][2], merged[-1][4] = i2, j2
        else:
            merged.append(['change', i1, i2, j1, j2])
    compare, inserted, removed = [], [], []
    for tag, i1, i2, j1, j2 in merged:
        if tag == 'equal':
            compare.append(((i1, i2), (j1, j2)))
            continue
        overlap = min(i2 - i1, j2 - j1)
        if overlap:
            compare.append(((i1, i1 + overlap), (j1, j1 + overlap)))
        if (j2 - j1) - overlap >= MIN_BAND:
            inserted.append((j1 + overlap, j2))
        if (i2 - i1) - overlap >= MIN_BAND:
            removed.append(j2)
    return compare, inserted, removed


def diff_panel(before, after):
    """After-based panel: faded After, red where matched rows differ, blue bands for inserted rows."""
    from PIL import Image, ImageChops, ImageFilter
    before_rgb, after_rgb = before.convert('RGB'), after.convert('RGB')
    compare, inserted, removed = align_rows(before_rgb, after_rgb)
    mask = Image.new('L', after_rgb.size, 0)
    width = min(before_rgb.width, after_rgb.width)
    for (i1, i2), (j1, j2) in compare:
        rows = i2 - i1
        delta = ImageChops.difference(after_rgb.crop((0, j1, width, j1 + rows)), before_rgb.crop((0, i1, width, i1 + rows)))
        delta = delta.convert('L').point(lambda v: 255 if v > DIFF_THRESHOLD else 0)
        mask.paste(delta, (0, j1))
        if after_rgb.width > width:  # columns that only exist in After
            mask.paste(255, (width, j1, after_rgb.width, j1 + rows))
    mask = mask.filter(ImageFilter.MaxFilter(5))
    faded = Image.blend(after_rgb.convert('L').convert('RGB'), Image.new('RGB', after_rgb.size, 'white'), 0.6)
    panel = Image.composite(Image.new('RGB', after_rgb.size, DIFF_CHANGED), faded, mask)
    for y1, y2 in inserted:
        band = after_rgb.crop((0, y1, after_rgb.width, y2))
        panel.paste(Image.blend(band, Image.new('RGB', band.size, DIFF_INSERTED), 0.18), (0, y1))
    return panel.convert('RGBA'), inserted, removed


def compose(before, after, case):
    """Before | After | Diff in one image. Frames are drawn on Before/After; Diff stays clean."""
    from PIL import Image, ImageDraw, ImageFont
    size = (max(before.width, after.width), max(before.height, after.height))
    diff, inserted, removed = diff_panel(before, after)

    def pad(image):
        canvas = Image.new('RGBA', size, (255, 255, 255, 255))
        canvas.paste(image, (0, 0))
        return canvas
    panels = [('Before', pad(draw_marks(before, marks(case, 'before'), 'before')), False),
              ('After', pad(draw_marks(after, marks(case, 'after'), 'after')), False),
              ('Diff', pad(diff), True)]
    horizontal = size[0] <= HORIZONTAL_MAX_WIDTH
    panel_w = size[0] + GUTTER
    if horizontal:
        canvas_size = (PANEL_PAD * 2 + panel_w * 3 + PANEL_GAP * 2, PANEL_PAD * 2 + PANEL_HEAD + size[1])
    else:
        canvas_size = (PANEL_PAD * 2 + panel_w, PANEL_PAD * 2 + (PANEL_HEAD + size[1]) * 3 + PANEL_GAP * 2)
    out = Image.new('RGBA', canvas_size, PANEL_BG + (255,))
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default(size=20)
    x = y = PANEL_PAD
    for label, image, is_diff in panels:
        draw.text((x + GUTTER, y + 8), label, fill=PANEL_INK, font=font)
        top = y + PANEL_HEAD
        out.alpha_composite(image, (x + GUTTER, top))
        draw.rectangle((x + GUTTER, top, x + GUTTER + size[0] - 1, top + size[1] - 1), outline=PANEL_LINE)
        if is_diff:
            for y1, y2 in inserted:
                draw.rectangle((x, top + y1, x + GUTTER - 4, top + y2 - 1), fill=DIFF_INSERTED)
            for yy in removed:
                draw.polygon([(x, top + yy - 6), (x + GUTTER - 4, top + yy), (x, top + yy + 6)], fill=DIFF_REMOVED)
        if horizontal:
            x += panel_w + PANEL_GAP
        else:
            y += PANEL_HEAD + size[1] + PANEL_GAP
    return out


def _save(image, destination, root, originals):
    require(not destination.is_symlink(), 'annotation output file must not be a symlink')
    require(all(destination.resolve() != (root / original).resolve() for original in originals),
            'refusing to overwrite an original screenshot')
    image.save(destination, format='PNG')
    return destination.relative_to(root).as_posix(), hashlib.sha256(destination.read_bytes()).hexdigest()


def export(report, root):
    """Write one Before/After/Diff composite per case with both captures (frames included), and a
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
