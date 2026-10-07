#!/usr/bin/env python3
"""Validate evidence, render Markdown/offline HTML, and upsert an owned PR comment.

Python 3.10+, optional Pillow for annotated PNG export. Does not capture, upload, start apps, or
infer visual findings. `publish` is a dry run unless --execute is supplied.
"""

import argparse
from datetime import datetime
from functools import lru_cache
import html
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote, urlsplit
import image_annotations

RESULTS = {'intended': '変更あり', 'needs-review': '要確認', 'unchanged': '変化なし', 'unverified': '未確認'}
STATES = {'captured', 'absent', 'unverified'}
DEVICES = {'pc': 'PC', 'sp': 'SP'}
ORIGINS = {'introduced': '今回発生', 'worsened': '今回悪化', 'pre-existing': '既存', 'unknown': '原因不明'}
PRIORITIES = {'required': '要対応', 'optional': '任意', 'investigate': '要調査'}
AUTH_MODES = {'existing-session': '既存セッション', 'form': 'フォームログイン',
              'manual': '手動ログイン', 'fixture': '開発用fixture', 'none': 'ログイン不要'}
AUTH_STATES = {'verified': '確認済み', 'unverified': '未確認', 'not-required': '不要'}
# Markdown layout groups. Only `body` cases appear expanded; the rest are collapsed.
GROUPS = ('body', 'unchanged', 'new', 'unverified')
SKILL_DIR = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=None)
def english_labels():
    """Loaded on first use so `--help` and validation do not depend on the asset file."""
    return json.loads((SKILL_DIR / 'assets/labels.en.json').read_text(encoding='utf-8'))


def translate(report, text):
    return english_labels().get(text, text) if report.get('language', 'ja') == 'en' else text


def authentication_text(report):
    t = lambda value: translate(report, value)
    auth = report.get('authentication')
    if auth is None:
        return t('認証の記録なし')
    if auth['mode'] == 'none':
        return f"{t('認証')}: {t(AUTH_MODES['none'])}"
    return (f"{t('認証')}: {t(AUTH_MODES[auth['mode']])} / Before {t(AUTH_STATES[auth['before']])} / "
            f"After {t(AUTH_STATES[auth['after']])} / {t('権限・データ一致')} {t(AUTH_STATES[auth['equivalence']])}")


def validate_authentication(auth):
    require(isinstance(auth, dict) and set(auth) == {'mode', 'before', 'after', 'equivalence'},
            'authentication allows only mode and verification statuses; no credentials or references')
    require(isinstance(auth['mode'], str) and auth['mode'] in AUTH_MODES, 'invalid authentication mode')
    require(all(isinstance(auth[k], str) and auth[k] in AUTH_STATES for k in ('before', 'after', 'equivalence')),
            'invalid authentication status')
    if auth['mode'] == 'none':
        require(all(auth[k] == 'not-required' for k in ('before', 'after', 'equivalence')),
                'public pages must not claim authenticated checks')
    else:
        require(all(auth[k] != 'not-required' for k in ('before', 'after', 'equivalence')),
                'authenticated modes require verified or unverified statuses')
        if auth['equivalence'] == 'verified':
            require(auth['before'] == auth['after'] == 'verified',
                    'equivalence requires verified authentication on both sides')


def validate_scope(report):
    scope = report.get('scope')
    require(isinstance(scope, dict), 'v2 requires scope')
    devices = scope.get('devices')
    require(isinstance(devices, list) and bool(devices)
            and all(isinstance(d, str) and d in DEVICES for d in devices), 'scope.devices must contain pc and/or sp')
    require(len(devices) == len(set(devices)), 'duplicate scope device')
    require(scope.get('basis') in ('explicit', 'default'), 'scope.basis must be explicit or default')
    text_field(scope, 'note')


def validate_case_v2(case, devices):
    require(case.get('device') in devices, 'case device is outside requested scope')
    viewport = case.get('viewport')
    require(isinstance(viewport, dict) and all(type(viewport.get(k)) is int and viewport[k] > 0
                                             for k in ('width', 'height')), 'viewport requires positive integer width/height')
    alignment = case.get('alignment')
    require(isinstance(alignment, dict) and alignment.get('method') in
            ('element', 'page-top', 'page-bottom', 'unmatched'), 'alignment method required')
    text_field(alignment, 'anchor')
    text_field(alignment, 'note')
    if alignment['method'] == 'unmatched':
        require(case['result'] == 'unverified', 'incomparable alignment requires unverified result')
    issues = case.get('issues')
    require(isinstance(issues, list), 'issues must be an array')
    if case['result'] == 'needs-review':
        require(bool(issues), 'needs-review requires a classified issue in v2')
    for issue in issues:
        require(isinstance(issue, dict), 'issue must be an object')
        require(issue.get('origin') in ORIGINS and issue.get('priority') in PRIORITIES, 'invalid issue classification')
        for key in ('summary', 'evidence', 'impact'):
            text_field(issue, key)
        origin, priority = issue['origin'], issue['priority']
        require(case['after']['state'] == 'captured', 'issues require captured After evidence')
        if origin in ('pre-existing', 'worsened'):
            require(case['before']['state'] == 'captured', 'existing/worsened issues require captured Before evidence')
        if origin == 'unknown':
            require(priority == 'investigate', 'unknown causality requires investigate')
        if priority == 'required':
            require(origin in ('introduced', 'worsened') and case['result'] == 'needs-review',
                    'PR requirements need an introduced/worsened issue and needs-review result')


def scope_text(report):
    t = lambda value: translate(report, value)
    if 'scope' not in report:
        return t('対象端末の記録なし（旧形式）')
    devices = report['scope']['devices']
    label = 'PC・SP' if len(devices) == 2 else DEVICES[devices[0]] + 'のみ'
    basis = '明示指定' if report['scope']['basis'] == 'explicit' else '既定'
    return f"{t(label)} / {t(basis)} — {report['scope']['note']}"


def group(case):
    """Where a case appears in Markdown: expanded body, or one of the collapsed groups."""
    if case['result'] in ('unverified', 'unchanged'):
        return case['result']
    if case['result'] == 'needs-review' or (case['before']['state'], case['after']['state']) == ('captured', 'captured'):
        return 'body'
    return 'new'


def summary_lines(report):
    """Counts shown at the top. Action-required is always shown; zero counts are otherwise omitted."""
    t = lambda value: translate(report, value)
    cases = report['cases']
    issues = [issue for case in cases for issue in case.get('issues', [])]
    counts = [('要対応', sum(i['priority'] == 'required' for i in issues)),
              ('要確認', sum(c['result'] == 'needs-review' for c in cases)),
              ('変更あり', sum(c['result'] == 'intended' and group(c) == 'body' for c in cases)),
              ('変化なし', sum(c['result'] == 'unchanged' for c in cases)),
              ('新規・削除画面', sum(group(c) == 'new' for c in cases)),
              ('未確認', sum(c['result'] == 'unverified' for c in cases))]
    return [f'{t(label)} {count}' for label, count in counts if count or label == '要対応']


def viewport_text(report):
    """Distinct device/viewport pairs across cases, in scope order (v2 only)."""
    t = lambda value: translate(report, value)
    seen = []
    for case in report['cases']:
        if 'device' in case:
            item = (case['device'], case['viewport']['width'], case['viewport']['height'])
            if item not in seen:
                seen.append(item)
    return ' · '.join(f'{t(DEVICES[d])} {w}×{h}' for d, w, h in seen)


def captured_text(report):
    """ISO timestamp trimmed to minutes for display."""
    return datetime.fromisoformat(report['captured_at'].replace('Z', '+00:00')).isoformat(timespec='minutes')


def case_context(case, report):
    t = lambda value: translate(report, value)
    lines = []
    if 'device' in case:
        vp = case['viewport']
        lines.append(f"{t(DEVICES[case['device']])} / {vp['width']} × {vp['height']} CSS px")
    if 'alignment' in case:
        a = case['alignment']
        lines.append(f"{t('撮影基準')}: {a['anchor']} — {a['note']}")
    else:
        lines.append(t('撮影基準の記録なし。操作手順を参照してください。'))
    return lines


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text_field(obj, key):
    value = obj.get(key)
    require(isinstance(value, str) and bool(value.strip()), f'{key}: non-empty text required')
    return value


def safe_text(value):
    """Escape user/source text, including Markdown links and GitHub mentions."""
    value = re.sub(r'([\\`*_{}\[\]()#!|~])', r'\\\1', str(value))
    value = html.escape(value, quote=True).replace('@', '&#64;')
    return value.replace('\r', '').replace('\n', '<br>')


def image_path(value, root):
    require(isinstance(value, str) and bool(value), 'image path required')
    path = Path(value)
    require(not path.is_absolute() and '..' not in path.parts, 'image must be relative to report directory')
    root = Path(root).resolve()
    resolved = (root / path).resolve()
    require(resolved.is_relative_to(root), 'image escapes report directory')
    require(resolved.is_file(), f'image missing: {value}')
    with resolved.open('rb') as source:
        signature = source.read(12)
    valid = (signature.startswith(b'\x89PNG\r\n\x1a\n') or signature.startswith(b'\xff\xd8\xff')
             or (signature.startswith(b'RIFF') and signature[8:12] == b'WEBP'))
    require(valid, f'expected PNG, JPEG or WebP: {value}')
    return quote(path.as_posix(), safe='/')


def image_url(value):
    require(isinstance(value, str) and bool(value), 'uploaded image URL missing')
    require(not any(c.isspace() or ord(c) < 32 for c in value), 'image URL contains whitespace')
    parsed = urlsplit(value)
    require(parsed.scheme == 'https' and bool(parsed.hostname), 'image URL must use HTTPS')
    require(not parsed.username and not parsed.password, 'image URL must not contain credentials')
    host = parsed.hostname.lower().rstrip('.')
    require('.' in host and host != 'localhost' and not host.endswith(('.localhost', '.local', '.internal')),
            'image URL must be accessible to PR readers')
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    require(address is None or address.is_global, 'image URL must not be a local/private address')
    return quote(value, safe=':/?=&%+,-._~#')


def validate(report, root, remote=False):
    require(isinstance(report, dict), 'report must be an object')
    require(report.get('language', 'ja') in ('ja', 'en'), 'language must be ja or en')
    if 'authentication' in report:
        validate_authentication(report['authentication'])
    require(type(report.get('schema_version')) is int and report['schema_version'] in (1, 2), 'schema_version must be 1 or 2')
    modern = report['schema_version'] == 2
    if modern:
        validate_scope(report)
    else:
        require('scope' not in report, 'scope requires schema_version=2')
    require(re.fullmatch(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+', text_field(report, 'repository')) is not None,
            'repository must be owner/repo (github.com only)')
    require(type(report.get('pr')) is int and report['pr'] > 0, 'pr must be a positive integer')
    for key in ('before_sha', 'head_sha'):
        require(re.fullmatch(r'[a-f0-9]{40}', text_field(report, key)) is not None, f'{key}: full 40-character SHA required')
    require(report.get('comparison') in ('merge-base', 'explicit-base'), 'invalid comparison mode')
    date = datetime.fromisoformat(text_field(report, 'captured_at').replace('Z', '+00:00'))
    require(date.tzinfo is not None, 'captured_at must include timezone')
    for key in ('browser', 'conditions'):
        text_field(report, key)
    require(isinstance(report.get('limitations'), list) and all(isinstance(v, str) and v.strip() for v in report['limitations']),
            'limitations must be an array of non-empty strings')
    cases = report.get('cases')
    require(isinstance(cases, list), 'cases must be an array')
    require(bool(cases) or bool(report['limitations']), 'no cases: explain why in limitations')
    ids = set()
    for case in cases:
        require(isinstance(case, dict), 'case must be an object')
        for key in ('id', 'title', 'route', 'reason', 'finding'):
            text_field(case, key)
        for key in ('browser', 'conditions'):
            if key in case:
                text_field(case, key)
        require(re.fullmatch(r'[a-z0-9-]+', case['id']) is not None and case['id'] not in ids, 'case id must be unique lowercase slug')
        ids.add(case['id'])
        require(isinstance(case.get('steps'), list) and bool(case['steps'])
                and all(isinstance(v, str) and v.strip() for v in case['steps']), 'steps must contain the replay procedure')
        require(case.get('result') in RESULTS, 'unknown result')
        states = []
        for side in ('before', 'after'):
            capture = case.get(side)
            require(isinstance(capture, dict) and capture.get('state') in STATES, f'{side}: invalid capture state')
            states.append(capture['state'])
            if capture['state'] == 'captured':
                image_path(capture.get('image'), root)
                if remote:
                    image_url(capture.get('url'))
                if 'detail_image' in capture:
                    image_path(capture['detail_image'], root)
                    if remote:
                        image_url(capture.get('detail_url'))
            else:
                text_field(capture, 'note')
                require(not any(key in capture for key in ('image', 'url', 'detail_image', 'detail_url')),
                        'absent/unverified state cannot carry a comparison image')
        if 'composite_image' in case:
            require(states == ['captured', 'captured'], 'a composite needs both captures')
            image_path(case['composite_image'], root)
            if remote:
                require(isinstance(case.get('composite_url'), str) and bool(case['composite_url']),
                        'composite_url missing: upload the Before | After PNG before publishing')
                image_url(case['composite_url'])
        if 'unverified' in states:
            require(case['result'] == 'unverified', 'an unverified side requires result=unverified')
        if case['result'] == 'unchanged':
            require(states == ['captured', 'captured'], 'unchanged requires both captures')
        if case['result'] != 'unverified':
            require('captured' in states, 'verified result requires actual screenshot evidence')
        if modern:
            validate_case_v2(case, report['scope']['devices'])
            image_annotations.validate(case)
        else:
            require(not any(key in case for key in ('issues', 'device', 'viewport', 'alignment', 'annotations')), 'structured evidence requires v2')
    if modern and cases:
        require(set(report['scope']['devices']) == {c['device'] for c in cases},
                'include each requested device, using unverified cases when blocked')


def marker(report):
    return f"<!-- pr-visual-review:v1 repo={report['repository']} pr={report['pr']} -->"


def annotate(report, root):
    validate(report, root)
    return image_annotations.export(report, root)


def annotation_legend(case, report):
    t = lambda value: translate(report, value)
    return [f"{a['id']} · {t('変更' if a['kind'] == 'change' else '問題')}: {a['label']}"
            for a in case.get('annotations', [])]


def capture_cell(case, side, root, remote, report):
    """Image cell for Markdown. Non-captured sides show a short label; the note lives in the details block."""
    capture = case[side.lower()]
    t = lambda value: translate(report, value)
    if capture['state'] != 'captured':
        return t(f'{side}なし') if capture['state'] == 'absent' else t('未確認')
    url = image_url(capture['url']) if remote else image_path(capture['image'], root)
    if image_annotations.marks(case, side.lower()):
        image_annotations.verify_derivative(case, side.lower(), root)
        local = image_path(capture['annotated_image'], root)
        if remote:
            require(isinstance(capture.get('annotated_url'), str) and bool(capture['annotated_url']),
                    f'annotated_url missing for {side}: upload the annotated PNG before publishing')
        marked = image_url(capture['annotated_url']) if remote else local
        cell = f"![{side} ({t('注釈付き')})](<{marked}>)<br>[{t('原画像')}](<{url}>)"
    else:
        cell = f'![{side}](<{url}>)'
    if 'detail_image' in capture:
        detail = image_url(capture['detail_url']) if remote else image_path(capture['detail_image'], root)
        cell += f"<br>[{t('拡大')}](<{detail}>)"
    return cell


def composite_block(case, report, root, remote):
    """One Before | After image plus links to the untouched originals."""
    t = lambda value: translate(report, value)
    image_annotations.verify_composite(case, root)
    src = image_url(case.get('composite_url')) if remote else image_path(case['composite_image'], root)
    originals = []
    for side in ('Before', 'After'):
        capture = case[side.lower()]
        originals.append(f"[{side}](<{image_url(capture['url']) if remote else image_path(capture['image'], root)}>)")
        if 'detail_image' in capture:
            originals.append(f"[{side} {t('拡大')}](<{image_url(capture['detail_url']) if remote else image_path(capture['detail_image'], root)}>)")
    return [f'![Before / After](<{src}>)', '', f"{t('原画像')}: " + ' · '.join(originals), '']


def case_block(case, report, root, remote, heading):
    """Heading, images, one-line finding, and issue lines. Everything else goes to the details block."""
    t = lambda value: translate(report, value)
    lines = [f"{heading} {safe_text(case['title'])} — {t(RESULTS[case['result']])}", '']
    if 'composite_image' in case:
        lines += composite_block(case, report, root, remote)
    else:
        lines += ['| Before | After |', '| --- | --- |',
                  f"| {capture_cell(case, 'Before', root, remote, report)} | {capture_cell(case, 'After', root, remote, report)} |", '']
    lines += [safe_text(case['finding']), '']
    for issue in case.get('issues', []):
        lines.append(f"- **{t(PRIORITIES[issue['priority']])}** · {t(ORIGINS[issue['origin']])}: {safe_text(issue['summary'])}")
    if case.get('issues'):
        lines.append('')
    return lines


def details_block(report, root, remote):
    """Everything a reviewer needs to reproduce or audit, collapsed once at the end."""
    t = lambda value: translate(report, value)
    lines = ['<details>', f"<summary>{t('確認条件・未確認事項')}</summary>", '']
    annotated = [case for case in report['cases'] if case.get('annotations')]
    if annotated:
        lines += [f"**{t('注釈')}** — {t('灰色はBeforeの参照箇所、青は変更、赤は問題です。番号は説明と対応します。')}", '']
        for case in annotated:
            lines += [f"- {safe_text(case['title'])}: " + ' / '.join(safe_text(line) for line in annotation_legend(case, report))]
        lines.append('')
    lines += [f"- {t('コミット')}: Before `{report['before_sha']}` → After `{report['head_sha']}` / {report['comparison']}",
              f"- {t('撮影')}: {safe_text(captured_text(report))}",
              f"- {authentication_text(report)}",
              f"- {t('条件')}: {safe_text(report['conditions'])}",
              f"- {t('確認範囲')}: {safe_text(scope_text(report))}", '',
              f"**{t('各ケースの手順')}**", '']
    for case in report['cases']:
        parts = [f"{t('操作')}: " + ' → '.join(safe_text(step) for step in case['steps']),
                 f"{t('理由')}: {safe_text(case['reason'])}"]
        if 'alignment' in case:
            parts.append(f"{t('撮影基準')}: {safe_text(case['alignment']['anchor'])} — {safe_text(case['alignment']['note'])}")
        for side in ('before', 'after'):
            if case[side]['state'] != 'captured':
                parts.append(f"{side.capitalize()}: {safe_text(case[side]['note'])}")
        # Per-case browser/conditions only when they differ from the shared values above.
        for key, label in (('browser', 'ブラウザ'), ('conditions', '条件')):
            if key in case and case[key] != report[key]:
                parts.append(f"{t(label)}: {safe_text(case[key])}")
        for issue in case.get('issues', []):
            parts.append(f"{t(PRIORITIES[issue['priority']])} · {t('根拠')}: {safe_text(issue['evidence'])} / {t('影響')}: {safe_text(issue['impact'])}")
        lines.append(f"- **{safe_text(case['title'])}** — {safe_text(case['route'])}")
        lines += [f'  - {part}' for part in parts]
    lines += ['', f"**{t('未確認事項')}**", '']
    lines += ['- ' + safe_text(item) for item in report['limitations']] or ['- ' + t('未確認事項なし')]
    lines += ['', t('この画面・状態だけを確認しました。0件でも安全性やマージ可否を保証するものではありません。'), '', '</details>']
    return lines


def render(report, root, remote=False, format='markdown'):
    validate(report, root, remote)
    require(format in ('markdown', 'html'), 'unsupported report format')
    if format == 'html':
        return render_html(report, root, remote)
    t = lambda value: translate(report, value)
    env = ' · '.join(part for part in (viewport_text(report), safe_text(report['browser'])) if part)
    lines = [marker(report), '## PR Visual Review', '',
             '**' + ' · '.join(summary_lines(report)) + '**', '']
    if env:
        lines += [env, '']
    groups = {name: [case for case in report['cases'] if group(case) == name] for name in GROUPS}
    # Action-required findings first, then other expanded cases.
    body = sorted(groups['body'], key=lambda c: c['result'] != 'needs-review')
    for case in body:
        lines += case_block(case, report, root, remote, '###')
    collapsed = [('unchanged', '変化なし'), ('new', '新規・削除画面'), ('unverified', '未確認')]
    for name, label in collapsed:
        if not groups[name]:
            continue
        lines += ['<details>', f"<summary>{t(label)} {len(groups[name])}</summary>", '']
        for case in groups[name]:
            lines += case_block(case, report, root, remote, '####')
        lines += ['</details>', '']
    lines += details_block(report, root, remote)
    return '\n'.join(lines) + '\n'


def render_html(report, root, remote):
    """Called only after validation; no scripts, network assets, or Markdown parsing."""
    esc = lambda value: html.escape(str(value), quote=True)
    t = lambda value: translate(report, value)
    css = (SKILL_DIR / 'assets/report.css').read_text(encoding='utf-8')

    def figure(capture, side, title, detail=False, case=None):
        label = side + (' / ' + t('詳細') if detail else '')
        if capture['state'] != 'captured':
            state = f'{side}なし' if capture['state'] == 'absent' else '未確認'
            return f'<figure><figcaption>{label} — {t(state)}</figcaption><p class="missing">{esc(capture["note"])}</p></figure>'
        key = 'detail_image' if detail else 'image'
        if key not in capture:
            return f'<figure><figcaption>{label}</figcaption><p class="missing">{t("詳細画像なし。上の文脈画像を参照してください。")}</p></figure>'
        url_key = 'detail_url' if detail else 'url'
        src = image_url(capture[url_key]) if remote else image_path(capture[key], root)
        selected = image_annotations.marks(case, side.lower()) if case and not detail else []
        overlays = []
        for a in selected:
            box = a[side.lower()]
            kind = 'reference' if side == 'Before' else a['kind']
            style = ';'.join(f'{prop}:{box[key] * 100:g}%' for prop, key in
                             [('left', 'x'), ('top', 'y'), ('width', 'width'), ('height', 'height')])
            badge = f"{a['id']} · {t('参照' if side == 'Before' else '変更' if a['kind']=='change' else '問題')}"
            right = ' badge-right' if box['x'] + box['width'] > .75 else ''
            overlays.append(f'<span class="annotation-box {kind}{right}" style="{style}" aria-hidden="true"><span>{esc(badge)}</span></span>')
        annotated = f' — {t("注釈付き")}' if selected else ''
        return (f'<figure><figcaption>{label}{annotated}</figcaption><a class="image-frame" href="{esc(src)}" aria-label="{esc(title)} — {label} — {t("原画像")}">'
                f'<img src="{esc(src)}" loading="lazy" alt="{esc(title)} — {label}">{"".join(overlays)}</a></figure>')

    sections = []
    nav = []
    for case in report['cases']:
        title = esc(case['title'])
        nav.append(f'<li><a href="#{case["id"]}">{title}</a></li>')
        issues = ''.join(
            f'<li class="issue {i["priority"]}"><strong>{t(ORIGINS[i["origin"]])} · {t(PRIORITIES[i["priority"]])}</strong>'
            f'<p>{esc(i["summary"])}</p><p>{t("根拠")}: {esc(i["evidence"])}</p><p>{t("影響")}: {esc(i["impact"])}</p></li>'
            for i in case.get('issues', []))
        details = ''
        if 'composite_image' in case:
            image_annotations.verify_composite(case, root)
            composite_src = image_url(case.get('composite_url')) if remote else image_path(case['composite_image'], root)
            details += (f'<details class="details-images"><summary>{t("Before / After の合成画像")}</summary>'
                        f'<a class="image-frame" href="{esc(composite_src)}"><img src="{esc(composite_src)}" loading="lazy" alt="{title} — Before / After"></a></details>')
        if any('detail_image' in case[s] for s in ('before', 'after')):
            details += (f'<details class="details-images"><summary>{t("変更箇所の詳細を開く")}</summary><div class="pair">' +
                       figure(case['before'], 'Before', case['title'], True) +
                       figure(case['after'], 'After', case['title'], True) + '</div></details>')
        context = ''.join(f'<p>{esc(line)}</p>' for line in case_context(case, report))
        steps = ''.join(f'<li>{esc(step)}</li>' for step in case['steps'])
        annotation_notes = ''
        originals = ''
        if case.get('annotations'):
            annotation_notes = (f'<div class="annotation-legend"><p>{t("灰色はBeforeの参照箇所、青は変更、赤は問題です。番号は説明と対応します。")}</p><ul>'
                                + ''.join(f'<li>{esc(line)}</li>' for line in annotation_legend(case, report)) + '</ul></div>')
            originals = (f'<details><summary>{t("注釈なしの原画像")}</summary><div class="pair">'
                         + figure(case['before'], 'Before', case['title']) + figure(case['after'], 'After', case['title']) + '</div></details>')
        sections.append(
            f'<section id="{case["id"]}"><div class="case-heading"><h2>{title}</h2>'
            f'<span class="status {case["result"]}">{t(RESULTS[case["result"]])}</span></div>'
            f'<p class="finding">{esc(case["finding"])}</p>'
            + (f'<ul class="issues">{issues}</ul>' if issues else '') +
            f'<div class="context">{context}</div><div class="pair">' +
            figure(case['before'], 'Before', case['title'], case=case) + figure(case['after'], 'After', case['title'], case=case) +
            '</div>' + annotation_notes + originals + details +
            f'<details><summary>{t("操作手順と比較条件")}</summary><p>{t("画面")}: {esc(case["route"])}</p>'
            f'<p>{t("選定根拠")}: {esc(case["reason"])}</p><p>{t("ブラウザ")}: {esc(case.get("browser",report["browser"]))}</p>'
            f'<p>{t("共通条件")}: {esc(report["conditions"])}</p>'
            f'<p>{t("個別条件")}: {esc(case.get("conditions",report["conditions"]))}</p><ol>{steps}</ol></details></section>')
    limits = ''.join(f'<li>{esc(item)}</li>' for item in report['limitations']) or f'<li>{t("未確認事項なし")}</li>'
    counts = ''.join(f'<li>{esc(line)}</li>' for line in summary_lines(report))
    return (f'<!doctype html>\n<html lang="{report.get("language", "ja")}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' https:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>PR #{report["pr"]} · {t("画面比較")}</title><style>{css}</style></head><body><main>'
            f'<header><p class="eyebrow">PR VISUAL REVIEW / {esc(report["repository"])}</p>'
            f'<h1>PR #{report["pr"]} {t("の画面比較")}</h1><p class="scope">{esc(scope_text(report))}</p>'
            f'<ul class="summary">{counts}</ul>'
            f'<details><summary>{t("コミットと実行条件")}</summary><dl><dt>Before</dt><dd><code>{report["before_sha"]}</code></dd>'
            f'<dt>After</dt><dd><code>{report["head_sha"]}</code></dd><dt>{t("比較元")}</dt><dd>{report["comparison"]}</dd>'
            f'<dt>{t("撮影日時")}</dt><dd>{esc(captured_text(report))}</dd><dt>{t("ブラウザ")}</dt><dd>{esc(report["browser"])}</dd></dl>'
            f'<p>{esc(report["conditions"])}</p><p>{esc(authentication_text(report))}</p></details></header>'
            f'<nav aria-label="{t("確認した画面")}"><ol>{"".join(nav)}</ol></nav>{"".join(sections)}'
            f'<section><h2>{t("未確認事項")}</h2><ul>{limits}</ul></section>'
            f'<footer>{t("この画面・状態だけを確認しました。0件でも安全性やマージ可否を保証するものではありません。")}</footer></main></body></html>\n')


def json_documents(text):
    """Parse concatenated JSON documents, which is how `gh api --paginate` prints pages."""
    decoder = json.JSONDecoder()
    documents = []
    index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            return documents
        document, index = decoder.raw_decode(text, index)
        documents.append(document)


def gh_api(endpoint, method='GET', payload=None, paginate=False):
    command = ['gh', 'api', '--hostname', 'github.com', '--method', method, endpoint]
    if paginate:
        # No --slurp: it needs a newer gh than --paginate, and the pages are easy to join here.
        command.append('--paginate')
    if payload is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        # Do not print API response bodies: they can contain source/customer data.
        raise RuntimeError(f'gh API {method} {endpoint} failed (exit {result.returncode}); check gh auth/permissions')
    if not paginate:
        return json.loads(result.stdout)
    pages = json_documents(result.stdout)
    require(all(isinstance(page, list) for page in pages), f'gh API {endpoint}: expected list pages')
    return [item for page in pages for item in page]


def publish(report, root, execute=False, images_reviewed=False, api=None):
    body = render(report, root, remote=True)
    require(len(body) <= 60000, 'comment too large; reduce the selected scope before posting')
    if execute:
        require(images_reviewed, 'inspect screenshots and hosted image access before using --images-reviewed')
    api = api or gh_api
    repo = report['repository']
    pr_endpoint = f"repos/{repo}/pulls/{report['pr']}"
    comments_endpoint = f"repos/{repo}/issues/{report['pr']}/comments"

    def check_head():
        require(api(pr_endpoint)['head']['sha'] == report['head_sha'],
                'PR head changed since capture; recapture before publishing')

    check_head()
    user_id = api('user')['id']
    comments = api(comments_endpoint, paginate=True)
    # `user` is null for comments whose author account no longer exists.
    owned = [c for c in comments if (c.get('user') or {}).get('id') == user_id
             and (c.get('body') or '').splitlines()[:1] == [marker(report)]]
    require(len(owned) <= 1, 'multiple owned review comments found; resolve ambiguity before publishing')
    action = 'update' if owned else 'create'
    result = {'action': action, 'executed': False, 'body': body}
    if not execute:
        return result
    check_head()
    if owned:
        response = api(f"repos/{repo}/issues/comments/{int(owned[0]['id'])}", method='PATCH', payload={'body': body})
    else:
        response = api(comments_endpoint, method='POST', payload={'body': body})
    result.update(executed=True, comment_url=response['html_url'], comment_id=response['id'])
    # The PR and comment APIs are not an atomic transaction. Surface the race.
    try:
        result['head_still_current'] = api(pr_endpoint)['head']['sha'] == report['head_sha']
    except (RuntimeError, ValueError, KeyError):
        result['head_still_current'] = None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('render', 'publish', 'annotate'):
        command = sub.add_parser(name)
        command.add_argument('report', type=Path, help='report.json; images are relative to this file')
        if name == 'render':
            command.add_argument('--remote', action='store_true', help='require hosted URLs instead of local paths')
            command.add_argument('--format', choices=['markdown', 'html'], default='markdown', help='offline HTML or Markdown')
        elif name == 'annotate':
            command.add_argument('--out', type=Path, required=True, help='new report JSON beside the original; never overwrite the input')
        else:
            command.add_argument('--execute', action='store_true', help='perform the user-authorized GitHub comment write')
            command.add_argument('--images-reviewed', action='store_true', help='confirm visual inspection and hosted-image access')
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding='utf-8'))
        if args.command == 'render':
            print(render(report, args.report.parent, args.remote, args.format), end='')
        elif args.command == 'annotate':
            require(args.out.resolve() != args.report.resolve(), 'annotation report must not overwrite input')
            require(not args.out.is_symlink() and args.out.parent.resolve() == args.report.parent.resolve(), 'save the derived JSON beside the original')
            require(args.out.suffix.lower() == '.json', 'annotation report output must be a JSON file')
            for case in report['cases']:
                sources = [case[side][key] for side in ('before', 'after') for key in ('image', 'detail_image', 'annotated_image')
                           if key in case[side]] + ([case['composite_image']] if 'composite_image' in case else [])
                for relative in sources:
                    source = args.report.parent / relative
                    require(args.out.resolve() != source.resolve() and not (args.out.exists() and source.exists() and args.out.samefile(source)),
                            'annotation report must not overwrite a screenshot')
            output = annotate(report, args.report.parent)
            args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(json.dumps({'report': str(args.out),
                              'annotated_sides': sum(bool(image_annotations.marks(c, s)) for c in output['cases'] for s in ('before', 'after')),
                              'composites': sum('composite_image' in c for c in output['cases'])}))
        else:
            print(json.dumps(publish(report, args.report.parent, args.execute, args.images_reviewed), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f'pr-visual-review: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
