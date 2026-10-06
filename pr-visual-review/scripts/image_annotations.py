"""Deterministic screenshot annotations. Pillow is optional until PNG export."""
import copy
import hashlib
import json
import math
from pathlib import Path

COLORS = {'change': '#1767bd', 'issue': '#c13928', 'reference': '#596979'}


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


def fingerprint(case, side, root):
    selected = marks(case, side)
    metadata = {'version': 1, 'side': side, 'marks': selected,
                'issues': [case['issues'][a['issue_index']] for a in selected if a['kind'] == 'issue']}
    source = (Path(root) / case[side]['image']).read_bytes()
    return hashlib.sha256(source + json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def verify_derivative(case, side, root):
    capture = case[side]
    require(isinstance(capture.get('annotated_image'), str), 'Run annotate and upload its PNG before rendering annotated Markdown')
    require(capture.get('annotation_fingerprint') == fingerprint(case, side, root),
            'Stale annotation: source/regions changed; run annotate again')
    path = (Path(root) / capture['annotated_image']).resolve()
    require(path.is_relative_to(Path(root).resolve()) and path.is_file(), 'annotation file missing or outside report directory')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == capture.get('annotated_sha256'),
            'Annotation PNG changed; run annotate again')


def export(report, root):
    """Input paths/cases must already have passed the report validator."""
    result = copy.deepcopy(report)
    if not any(case.get('annotations') for case in result['cases']):
        return result
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
    except ImportError as error:
        raise RuntimeError('PNG annotation export needs Pillow: python3 -m pip install -r /PATH/TO/SKILL/requirements-annotations.txt') from error
    root = Path(root).resolve()
    output = root / 'annotated'
    require(not output.is_symlink(), 'annotation output directory must not be a symlink')
    output.mkdir(exist_ok=True)
    for case in result['cases']:
        for side in ('before', 'after'):
            capture = case[side]
            for key in ('annotated_image', 'annotated_sha256', 'annotation_fingerprint', 'annotated_url'):
                capture.pop(key, None)
            selected = marks(case, side)
            if not selected:
                continue
            with Image.open(root / capture['image']) as original:
                require(original.format in ('PNG', 'JPEG', 'WEBP'), 'unsupported annotation source format')
                image = ImageOps.exif_transpose(original).convert('RGBA')
                image.info.clear()
            width, height = image.size
            require(width >= 40 and height >= 40, 'annotation screenshot too small')
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
            stamp = fingerprint(case, side, root)
            destination = output / f"{case['id']}-{side}-{stamp[:16]}.png"
            require(not destination.is_symlink(), 'annotation output file must not be a symlink')
            require(destination.resolve() != (root / capture['image']).resolve(), 'refusing to overwrite an original screenshot')
            image.save(destination, format='PNG')
            capture.update(annotated_image=destination.relative_to(root).as_posix(),
                           annotated_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
                           annotation_fingerprint=stamp)
    return result
