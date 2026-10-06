#!/usr/bin/env python3
"""Validate evidence, render Markdown/offline HTML, and upsert an owned PR comment.

Python 3.10+, standard library only. Does not capture, upload, start apps, or
infer visual findings. `publish` is a dry run unless --execute is supplied.
"""

import argparse
from datetime import datetime
import html
import ipaddress
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote, urlsplit

RESULTS = {
    'intended': '意図した変更を確認',
    'needs-review': '要確認',
    'unchanged': '見た目の変化なし',
    'unverified': '未確認',
}
STATES = {'captured', 'absent', 'unverified'}
DEVICES = {'pc': 'PC', 'sp': 'SP'}
ORIGINS = {'introduced': '新規UI・今回発生', 'worsened': '今回悪化',
           'pre-existing': '既存の問題', 'unknown': '因果未確定'}
PRIORITIES = {'required': 'PRで要対応', 'optional': '任意改善', 'investigate': '要調査'}
AUTH_MODES = {'existing-session': '既存セッション', 'form': '通常ログイン',
              'manual': 'ユーザーによるログイン', 'fixture': '開発用fixture', 'none': 'ログイン不要'}
AUTH_STATES = {'verified': '確認済み', 'unverified': '未確認', 'not-required': '不要'}


def authentication_text(report):
    auth = report.get('authentication')
    if auth is None:
        return '認証方法・結果の構造化記録なし'
    return (f"認証: {AUTH_MODES[auth['mode']]} / Before: {AUTH_STATES[auth['before']]} / "
            f"After: {AUTH_STATES[auth['after']]} / 権限・データ一致: {AUTH_STATES[auth['equivalence']]}")


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
    if 'scope' not in report:
        return '対象端末の記録なし（旧形式）'
    devices = report['scope']['devices']
    label = 'PC・SP' if len(devices) == 2 else DEVICES[devices[0]] + 'のみ'
    basis = '明示指定' if report['scope']['basis'] == 'explicit' else '既定'
    return f"{label} / {basis} — {report['scope']['note']}"


def summary_lines(report):
    issues = [issue for case in report['cases'] for issue in case.get('issues', [])]
    legacy = sum(case['result'] == 'needs-review' and not case.get('issues') for case in report['cases'])
    return [f"PRで要対応: {sum(i['priority'] == 'required' for i in issues)}",
            f"任意改善: {sum(i['priority'] == 'optional' for i in issues)}",
            f"要調査: {sum(i['priority'] == 'investigate' for i in issues)}",
            f"未確認ケース: {sum(c['result'] == 'unverified' for c in report['cases'])}"] + (
                [f'要確認（未分類）: {legacy}'] if legacy else [])


def case_context(case):
    lines = []
    if 'device' in case:
        vp = case['viewport']
        lines.append(f"{DEVICES[case['device']]} / {vp['width']} × {vp['height']} CSS px")
    if 'alignment' in case:
        a = case['alignment']
        lines.append(f"撮影基準: {a['anchor']} — {a['note']}")
    else:
        lines.append('撮影基準の構造化記録なし。操作手順を参照してください。')
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
        if 'unverified' in states:
            require(case['result'] == 'unverified', 'an unverified side requires result=unverified')
        if case['result'] == 'unchanged':
            require(states == ['captured', 'captured'], 'unchanged requires both captures')
        if case['result'] != 'unverified':
            require('captured' in states, 'verified result requires actual screenshot evidence')
        if modern:
            validate_case_v2(case, report['scope']['devices'])
        else:
            require(not any(key in case for key in ('issues', 'device', 'viewport', 'alignment')), 'structured evidence requires v2')
    if modern and cases:
        require(set(report['scope']['devices']) == {c['device'] for c in cases},
                'include each requested device, using unverified cases when blocked')


def marker(report):
    return f"<!-- pr-visual-review:v1 repo={report['repository']} pr={report['pr']} -->"


def capture_cell(capture, side, root, remote):
    if capture['state'] != 'captured':
        label = '存在しない' if capture['state'] == 'absent' else '未確認'
        return f"{label}: {safe_text(capture['note'])}"
    url = image_url(capture['url']) if remote else image_path(capture['image'], root)
    cell = f'![{side}](<{url}>)'
    if 'detail_image' in capture:
        detail = image_url(capture['detail_url']) if remote else image_path(capture['detail_image'], root)
        cell += f'<br>[変更箇所の拡大](<{detail}>)'
    return cell


def render(report, root, remote=False, format='markdown'):
    validate(report, root, remote)
    require(format in ('markdown', 'html'), 'unsupported report format')
    if format == 'html':
        return render_html(report, root, remote)
    lines = [marker(report), '## PR Visual Review', '',
             f"対象: {safe_text(report['repository'])} #{report['pr']}", '',
             f"確認範囲: {safe_text(scope_text(report))}", '',
             ' / '.join(summary_lines(report)), '',
             '件数は記録された指摘の集計です。0件でも安全性・マージ可否の保証ではありません。', '',
             '| Before commit | After commit | 比較元 |', '| --- | --- | --- |',
             f"| `{report['before_sha']}` | `{report['head_sha']}` | {report['comparison']} |", '',
             f"撮影日時: {safe_text(report['captured_at'])}", '',
             f"ブラウザ: {safe_text(report['browser'])}", '',
             authentication_text(report), '',
             f"条件: {safe_text(report['conditions'])}", '',
             '記載した画面・状態だけを確認しています。全画面の回帰がないことは保証しません。', '']
    for case in report['cases']:
        lines += [f"### {safe_text(case['title'])}", '',
                  f"画面: {safe_text(case['route'])}", '',
                  f"選定根拠: {safe_text(case['reason'])}", '',
                  f"ブラウザ: {safe_text(case.get('browser', report['browser']))}", '',
                  f"条件: {safe_text(case.get('conditions', report['conditions']))}", '',
                  *[safe_text(line) + '\n' for line in case_context(case)],
                  '操作: ' + ' → '.join(safe_text(step) for step in case['steps']), '',
                  '| Before | After |', '| --- | --- |',
                  f"| {capture_cell(case['before'], 'Before', root, remote)} | {capture_cell(case['after'], 'After', root, remote)} |", '',
                  f"**{RESULTS[case['result']]}**: {safe_text(case['finding'])}", '']
        for issue in case.get('issues', []):
            lines += [f"- **{ORIGINS[issue['origin']]} / {PRIORITIES[issue['priority']]}**: {safe_text(issue['summary'])}",
                      f"  - 根拠: {safe_text(issue['evidence'])}", f"  - 影響: {safe_text(issue['impact'])}", '']
    lines += ['### 未確認事項・制約', '']
    lines += ['- ' + safe_text(item) for item in report['limitations']] or ['- 記録された対象内に追加の制約はありません。']
    return '\n'.join(lines) + '\n'


def render_html(report, root, remote):
    """Called only after validation; no scripts, network assets, or Markdown parsing."""
    esc = lambda value: html.escape(str(value), quote=True)
    css = (Path(__file__).resolve().parents[1] / 'assets/report.css').read_text(encoding='utf-8')

    def figure(capture, side, title, detail=False):
        label = side + (' / 詳細' if detail else '')
        if capture['state'] != 'captured':
            state = '存在しない' if capture['state'] == 'absent' else '未確認'
            return f'<figure><figcaption>{label} — {state}</figcaption><p class="missing">{esc(capture["note"])}</p></figure>'
        key = 'detail_image' if detail else 'image'
        if key not in capture:
            return f'<figure><figcaption>{label}</figcaption><p class="missing">詳細画像なし。上の文脈画像を参照してください。</p></figure>'
        url_key = 'detail_url' if detail else 'url'
        src = image_url(capture[url_key]) if remote else image_path(capture[key], root)
        return (f'<figure><figcaption>{label}</figcaption><a href="{esc(src)}">'
                f'<img src="{esc(src)}" loading="lazy" alt="{esc(title)} — {label}"></a></figure>')

    sections = []
    nav = []
    for case in report['cases']:
        title = esc(case['title'])
        nav.append(f'<li><a href="#{case["id"]}">{title}</a></li>')
        issues = ''.join(
            f'<li class="issue {i["priority"]}"><strong>{ORIGINS[i["origin"]]} · {PRIORITIES[i["priority"]]}</strong>'
            f'<p>{esc(i["summary"])}</p><p>根拠: {esc(i["evidence"])}</p><p>影響: {esc(i["impact"])}</p></li>'
            for i in case.get('issues', []))
        details = ''
        if any('detail_image' in case[s] for s in ('before', 'after')):
            details = ('<details class="details-images"><summary>変更箇所の詳細を開く</summary><div class="pair">' +
                       figure(case['before'], 'Before', case['title'], True) +
                       figure(case['after'], 'After', case['title'], True) + '</div></details>')
        context = ''.join(f'<p>{esc(line)}</p>' for line in case_context(case))
        steps = ''.join(f'<li>{esc(step)}</li>' for step in case['steps'])
        sections.append(
            f'<section id="{case["id"]}"><div class="case-heading"><h2>{title}</h2>'
            f'<span class="status {case["result"]}">{RESULTS[case["result"]]}</span></div>'
            f'<p class="finding">{esc(case["finding"])}</p>'
            + (f'<ul class="issues">{issues}</ul>' if issues else '') +
            f'<div class="context">{context}</div><div class="pair">' +
            figure(case['before'], 'Before', case['title']) + figure(case['after'], 'After', case['title']) +
            '</div>' + details +
            f'<details><summary>操作手順と比較条件</summary><p>画面: {esc(case["route"])}</p>'
            f'<p>選定根拠: {esc(case["reason"])}</p><p>ブラウザ: {esc(case.get("browser",report["browser"]))}</p>'
            f'<p>共通条件: {esc(report["conditions"])}</p>'
            f'<p>個別条件: {esc(case.get("conditions",report["conditions"]))}</p><ol>{steps}</ol></details></section>')
    limits = ''.join(f'<li>{esc(item)}</li>' for item in report['limitations']) or '<li>記録された対象内に追加の制約はありません。</li>'
    counts = ''.join(f'<li>{esc(line)}</li>' for line in summary_lines(report))
    return (f'<!doctype html>\n<html lang="ja"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\' https:; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>PR #{report["pr"]} · 画面比較</title><style>{css}</style></head><body><main>'
            f'<header><p class="eyebrow">PR VISUAL REVIEW / {esc(report["repository"])}</p>'
            f'<h1>PR #{report["pr"]} の画面比較</h1><p class="scope">{esc(scope_text(report))}</p>'
            f'<ul class="summary">{counts}</ul><p class="muted">件数は記録された指摘の集計です。0件でも安全性・マージ可否の保証ではありません。</p>'
            f'<details><summary>コミットと実行条件</summary><dl><dt>Before</dt><dd><code>{report["before_sha"]}</code></dd>'
            f'<dt>After</dt><dd><code>{report["head_sha"]}</code></dd><dt>比較元</dt><dd>{report["comparison"]}</dd>'
            f'<dt>撮影日時</dt><dd>{esc(report["captured_at"])}</dd><dt>ブラウザ</dt><dd>{esc(report["browser"])}</dd></dl>'
            f'<p>{esc(report["conditions"])}</p><p>{esc(authentication_text(report))}</p></details></header>'
            f'<nav aria-label="確認した画面"><ol>{"".join(nav)}</ol></nav>{"".join(sections)}'
            f'<section><h2>未確認事項・制約</h2><ul>{limits}</ul></section>'
            '<footer>記載した画面・状態だけを確認しています。全画面の回帰がないことは保証しません。</footer></main></body></html>\n')


def gh_api(endpoint, method='GET', payload=None, paginate=False):
    command = ['gh', 'api', '--hostname', 'github.com', '--method', method, endpoint]
    if paginate:
        command += ['--paginate', '--slurp']
    if payload is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                            text=True, capture_output=True, check=False)
    if result.returncode:
        # Do not print API response bodies: they can contain source/customer data.
        raise RuntimeError(f'gh API {method} {endpoint} failed (exit {result.returncode}); check gh auth/permissions')
    data = json.loads(result.stdout)
    return [item for page in data for item in page] if paginate else data


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
    owned = [c for c in comments if c.get('user', {}).get('id') == user_id
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
    for name in ('render', 'publish'):
        command = sub.add_parser(name)
        command.add_argument('report', type=Path, help='report.json; images are relative to this file')
        if name == 'render':
            command.add_argument('--remote', action='store_true', help='require hosted URLs instead of local paths')
            command.add_argument('--format', choices=['markdown', 'html'], default='markdown', help='offline HTML or Markdown')
        else:
            command.add_argument('--execute', action='store_true', help='perform the user-authorized GitHub comment write')
            command.add_argument('--images-reviewed', action='store_true', help='confirm visual inspection and hosted-image access')
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding='utf-8'))
        if args.command == 'render':
            print(render(report, args.report.parent, args.remote, args.format), end='')
        else:
            print(json.dumps(publish(report, args.report.parent, args.execute, args.images_reviewed), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as error:
        print(f'pr-visual-review: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
