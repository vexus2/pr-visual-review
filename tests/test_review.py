import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/pr-visual-review/scripts/review.py'
sys.path.insert(0, str(SCRIPT.parent))
spec = importlib.util.spec_from_file_location('review', SCRIPT)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)


def sample():
    return {
        'schema_version': 1, 'repository': 'owner/app', 'pr': 42,
        'before_sha': 'a' * 40, 'head_sha': 'b' * 40,
        'comparison': 'merge-base', 'captured_at': '2026-10-07T12:00:00+09:00',
        'browser': 'Google Chrome 140 (example)',
        'conditions': '1440x900 CSS px; DPR 1; ja-JP; Asia/Tokyo; fixture user; scroll top',
        'cases': [{
            'id': 'settings', 'title': '設定モーダル', 'route': '/settings',
            'reason': 'src/Button.tsx → settings dialog',
            'steps': ['設定を開く', '通知設定を編集'],
            'result': 'intended', 'finding': '保存ボタンの重なりが解消しています。',
            'before': {'state': 'captured', 'image': 'images/before.png', 'url': 'https://example.com/before.png'},
            'after': {'state': 'captured', 'image': 'images/after.png', 'url': 'https://example.com/after.png'},
        }],
        'limitations': ['Safari未実施'],
    }


class FakeAPI:
    def __init__(self, comments=None, head=None):
        self.comments = comments or []
        self.head = head or 'b' * 40
        self.calls = []

    def __call__(self, endpoint, method='GET', payload=None, paginate=False):
        self.calls.append((endpoint, method, payload, paginate))
        if method != 'GET':
            return {'id': 99, 'html_url': 'https://github.com/owner/app/pull/42#issuecomment-99'}
        if endpoint == 'user':
            return {'id': 7, 'login': 'me'}
        if endpoint.endswith('pulls/42'):
            return {'head': {'sha': self.head}}
        if endpoint.endswith('comments'):
            return self.comments
        raise AssertionError(endpoint)

    @property
    def writes(self):
        return [c for c in self.calls if c[1] != 'GET']


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'images').mkdir()
        # Tiny valid PNG; no browser evidence is claimed by this fixture.
        import base64
        image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')
        for name in ('before', 'after'):
            (self.root / f'images/{name}.png').write_bytes(image)
        self.report = sample()

    def tearDown(self):
        self.temp.cleanup()

    def test_local_report_keeps_images_and_limitations(self):
        md = review.render(self.report, self.root)
        self.assertIn('images/before.png', md)
        self.assertNotIn('https://example.com/before', md)
        self.assertIn('Safari未実施', md)
        self.assertIn('a' * 40, md)
        self.assertIn('変更あり', md)

    def test_remote_report_uses_urls(self):
        md = review.render(self.report, self.root, remote=True)
        self.assertIn('https://example.com/before.png', md)
        self.assertNotIn('images/before.png', md)

    def test_multiple_viewports_and_browsers_survive_one_comment(self):
        mobile = copy.deepcopy(self.report['cases'][0])
        mobile.update(id='settings-mobile', title='設定モバイル', browser='Google Chrome 140',
                      conditions='390x844 CSS px; DPR 1')
        self.report['cases'].append(mobile)
        api = FakeAPI()
        result = review.publish(self.report, self.root, execute=True, images_reviewed=True, api=api)
        self.assertIn('1440x900', result['body'])
        self.assertIn('390x844', result['body'])
        self.assertIn('設定モーダル', result['body'])
        self.assertEqual(len(api.writes), 1)

    def test_absent_before_has_no_fake_image(self):
        self.report['cases'][0]['before'] = {'state': 'absent', 'note': 'コミットのルート定義に存在しません。'}
        md = review.render(self.report, self.root)
        self.assertIn('Beforeなし', md)
        self.assertIn('コミットのルート定義に存在しません', md)
        self.assertNotIn('images/before.png', md)

    def test_unverified_cannot_be_no_change(self):
        self.report['cases'][0]['before'] = {'state': 'unverified', 'note': 'ログイン不可'}
        self.report['cases'][0]['result'] = 'unchanged'
        with self.assertRaises(ValueError):
            review.render(self.report, self.root)
        self.report['cases'][0]['result'] = 'unverified'
        self.assertIn('未確認', review.render(self.report, self.root))

    def test_unchanged_requires_two_real_captures(self):
        self.report['cases'][0]['before'] = {'state': 'absent', 'note': '新規'}
        self.report['cases'][0]['result'] = 'unchanged'
        with self.assertRaises(ValueError):
            review.render(self.report, self.root)

    def test_reject_missing_image_and_traversal_and_symlink(self):
        for path in ('images/missing.png', '../secret.png', '/tmp/secret.png'):
            self.report['cases'][0]['before']['image'] = path
            with self.subTest(path=path), self.assertRaises(ValueError):
                review.render(self.report, self.root)
        (self.root / 'images/link.png').symlink_to('/etc/hosts')
        self.report['cases'][0]['before']['image'] = 'images/link.png'
        with self.assertRaises(ValueError):
            review.render(self.report, self.root)

    def test_reject_remote_local_and_unsafe_urls(self):
        for url in ('file:///tmp/a.png', 'http://example.com/a.png', 'https://localhost/a.png',
                    'https://127.0.0.1/a.png', 'https://10.0.0.1/a.png', 'https://user:pass@example.com/a.png',
                    'https://example.com/a.png\nhi', ''):
            self.report['cases'][0]['before']['url'] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                review.render(self.report, self.root, remote=True)

    def test_escape_markdown_html_and_mentions(self):
        self.report['cases'][0]['finding'] = '<script>x</script> | [link](https://evil.test) @someone'
        md = review.render(self.report, self.root)
        self.assertNotIn('<script>', md)
        self.assertNotIn('[link](', md)
        self.assertNotIn('@someone', md)

    def test_escape_preserves_readable_quotes_and_mentions(self):
        self.assertEqual(review.safe_text("O'Reilly @owner"), 'O&#x27;Reilly &#64;owner')

    def test_dry_run_never_mutates(self):
        api = FakeAPI()
        result = review.publish(self.report, self.root, api=api)
        self.assertEqual(result['action'], 'create')
        self.assertFalse(api.writes)

    def test_execute_requires_reviewed_images(self):
        api = FakeAPI()
        with self.assertRaises(ValueError):
            review.publish(self.report, self.root, execute=True, api=api)
        self.assertFalse(api.writes)

    def test_only_owned_marker_updated_with_pagination(self):
        marker = review.marker(self.report)
        api = FakeAPI([
            {'id': 1, 'user': {'id': 8}, 'body': marker + '\nother'},
            {'id': 2, 'user': {'id': 7}, 'body': 'unrelated'},
            {'id': 3, 'user': {'id': 7}, 'body': marker + '\nold'}])
        result = review.publish(self.report, self.root, execute=True, images_reviewed=True, api=api)
        self.assertEqual(result['action'], 'update')
        self.assertEqual(api.writes[0][0], 'repos/owner/app/issues/comments/3')
        self.assertEqual(api.writes[0][1], 'PATCH')
        self.assertTrue(any(c[3] for c in api.calls))

    def test_create_preserves_others(self):
        api = FakeAPI([{'id': 1, 'user': {'id': 8}, 'body': review.marker(self.report)}])
        review.publish(self.report, self.root, execute=True, images_reviewed=True, api=api)
        self.assertEqual(api.writes[0][1], 'POST')

    def test_duplicate_owned_comments_fail_without_write(self):
        api = FakeAPI([{'id': i, 'user': {'id': 7}, 'body': review.marker(self.report)} for i in (1, 2)])
        with self.assertRaises(ValueError):
            review.publish(self.report, self.root, execute=True, images_reviewed=True, api=api)
        self.assertFalse(api.writes)

    def test_stale_head_fails_without_write(self):
        api = FakeAPI(head='c' * 40)
        with self.assertRaises(ValueError):
            review.publish(self.report, self.root, execute=True, images_reviewed=True, api=api)
        self.assertFalse(api.writes)

    def test_head_change_during_discovery_fails(self):
        api = FakeAPI()
        def changing(endpoint, **kwargs):
            response = api(endpoint, **kwargs)
            if endpoint.endswith('comments'):
                api.head = 'c' * 40
            return response
        with self.assertRaises(ValueError):
            review.publish(self.report, self.root, execute=True, images_reviewed=True, api=changing)
        self.assertFalse(api.writes)

    def test_head_change_after_write_is_reported(self):
        api = FakeAPI()
        def changing(endpoint, **kwargs):
            response = api(endpoint, **kwargs)
            if kwargs.get('method', 'GET') != 'GET':
                api.head = 'c' * 40
            return response
        result = review.publish(self.report, self.root, execute=True, images_reviewed=True, api=changing)
        self.assertFalse(result['head_still_current'])

    def test_comment_without_author_is_ignored_not_crashed(self):
        # GitHub returns user=null for comments whose author account was deleted.
        api = FakeAPI([{'id': 1, 'user': None, 'body': review.marker(self.report)}])
        result = review.publish(self.report, self.root, api=api)
        self.assertEqual(result['action'], 'create')
        self.assertFalse(api.writes)

    def test_paginated_gh_output_is_parsed_without_slurp(self):
        # `gh api --paginate` prints one JSON document per page, concatenated.
        self.assertEqual(review.json_documents('[{"id": 1}]\n[{"id": 2}, {"id": 3}]\n'), [[{'id': 1}], [{'id': 2}, {'id': 3}]])
        self.assertEqual(review.json_documents('   '), [])
        with self.assertRaises(ValueError):
            review.json_documents('[1] trailing')
        calls = []

        class Completed:
            returncode = 0
            stdout = '[{"id": 1}][{"id": 2}]'

        def fake_run(command, **kwargs):
            calls.append(command)
            return Completed()
        original = review.subprocess.run
        review.subprocess.run = fake_run
        try:
            self.assertEqual(review.gh_api('repos/owner/app/issues/42/comments', paginate=True), [{'id': 1}, {'id': 2}])
        finally:
            review.subprocess.run = original
        self.assertIn('--paginate', calls[0])
        self.assertNotIn('--slurp', calls[0])

    def test_help_works_without_label_assets(self):
        import shutil
        import subprocess
        scripts = self.root / 'scripts'
        shutil.copytree(SCRIPT.parent, scripts, ignore=lambda d, names: ['__pycache__'])
        result = subprocess.run([sys.executable, str(scripts / 'review.py'), '--help'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_remote_missing_url_never_posts(self):
        del self.report['cases'][0]['before']['url']
        api = FakeAPI()
        with self.assertRaises(ValueError):
            review.publish(self.report, self.root, execute=True, images_reviewed=True, api=api)
        self.assertFalse(api.writes)

    def test_bad_identity_and_sha_rejected(self):
        for key, value in [('repository', '../../x'), ('pr', True), ('head_sha', 'main'), ('schema_version', 3)]:
            report = copy.deepcopy(self.report)
            report[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                review.render(report, self.root)

    def test_no_visual_cases_still_reports_reason(self):
        self.report['cases'] = []
        self.report['limitations'] = ['API内部の変更のみ。画面に影響する利用箇所なし。']
        self.assertIn('API内部', review.render(self.report, self.root))

    def v2(self, device='pc'):
        report = copy.deepcopy(self.report)
        report['schema_version'] = 2
        report['scope'] = {'devices': [device], 'basis': 'explicit', 'note': '指定された範囲だけ'}
        case = report['cases'][0]
        case.update(device=device, viewport={'width': 1280 if device == 'pc' else 375, 'height': 1000},
                    alignment={'method': 'element', 'anchor': '通知設定の見出し', 'note': '見出しを上端から24pxに揃えた'},
                    issues=[])
        return report

    def test_pc_and_sp_scopes_render_in_both_formats(self):
        for device, label in [('pc', 'PCのみ'), ('sp', 'SPのみ')]:
            r = self.v2(device)
            for fmt in ['markdown', 'html']:
                with self.subTest(device=device, format=fmt):
                    rendered = review.render(r, self.root, format=fmt)
                    self.assertIn(label, rendered)
                    self.assertIn('通知設定の見出し', rendered)
                    self.assertIn('375' if device == 'sp' else '1280', rendered)

    def layout_report(self):
        """One case per Markdown group: changed, needs-review, unchanged, new, unverified."""
        r = self.v2()
        r['scope']['devices'] = ['pc']
        base = r['cases'][0]
        base.update(id='changed', title='変更ケース', finding='欄が増えた')
        review_case = copy.deepcopy(base)
        review_case.update(id='broken', title='崩れケース', result='needs-review', finding='ボタンが隠れる',
                           issues=[{'origin': 'introduced', 'priority': 'required', 'summary': '保存ボタンが画面外',
                                    'evidence': 'After画像', 'impact': '保存できない'}])
        unchanged = copy.deepcopy(base)
        unchanged.update(id='same', title='同じケース', result='unchanged', finding='差なし', conditions='個別条件XYZ')
        new = copy.deepcopy(base)
        new.update(id='fresh', title='新規ケース', finding='新しい画面', before={'state': 'absent', 'note': '新規route'})
        unverified = copy.deepcopy(base)
        unverified.update(id='blocked', title='未確認ケース', result='unverified', finding='起動できず',
                          before={'state': 'unverified', 'note': 'install失敗'}, after={'state': 'unverified', 'note': 'install失敗'})
        r['cases'] = [base, new, unchanged, review_case, unverified]
        return r

    def test_markdown_body_shows_only_changed_cases_and_collapses_the_rest(self):
        md = review.render(self.layout_report(), self.root)
        body, details = md.split('<details>', 1)
        self.assertIn('### 崩れケース — 要確認', body)
        self.assertIn('### 変更ケース — 変更あり', body)
        self.assertLess(body.index('崩れケース'), body.index('変更ケース'), 'action-required cases come first')
        for title in ('同じケース', '新規ケース', '未確認ケース'):
            self.assertNotIn(title, body)
            self.assertIn(title, details)
        self.assertIn('<summary>変化なし 1</summary>', details)
        self.assertIn('<summary>新規・削除画面 1</summary>', details)
        self.assertIn('<summary>未確認 1</summary>', details)
        self.assertIn('| Beforeなし |', details)
        self.assertIn('- **要対応** · 今回発生: 保存ボタンが画面外', body)

    def test_markdown_states_shared_conditions_once_and_overrides_only_when_different(self):
        md = review.render(self.layout_report(), self.root)
        self.assertEqual(md.count(self.report['conditions']), 1)
        self.assertEqual(md.count(review.safe_text(self.report['browser'])), 1)
        self.assertEqual(md.count('個別条件XYZ'), 1)
        self.assertEqual(md.count('設定を開く'), 5, 'steps appear once per case, inside the details block')
        self.assertLess(md.index('<summary>確認条件・未確認事項</summary>'), md.index('設定を開く'))
        self.assertIn('2026-10-07T12:00+09:00', md)
        self.assertNotIn('12:00:00', md)

    def test_summary_counts_omit_zero_except_action_required(self):
        md = review.render(self.layout_report(), self.root)
        self.assertIn('**要対応 1 · 要確認 1 · 変更あり 1 · 変化なし 1 · 新規・削除画面 1 · 未確認 1**', md)
        self.assertIn('**要対応 0 · 変更あり 1**', review.render(self.v2(), self.root))

    def test_scope_does_not_allow_other_device_cases(self):
        r = self.v2('sp')
        r['cases'][0]['device'] = 'pc'
        with self.assertRaises(ValueError):
            review.render(r, self.root)

    def test_both_scope_requires_each_device_even_if_unverified(self):
        r = self.v2()
        r['scope']['devices'] = ['pc', 'sp']
        with self.assertRaises(ValueError):
            review.render(r, self.root)
        case = copy.deepcopy(r['cases'][0])
        case.update(id='sp', device='sp', viewport={'width': 390, 'height': 844}, result='unverified')
        case['before'] = case['after'] = {'state':'unverified', 'note':'撮影できず'}
        r['cases'].append(case)
        self.assertIn('PC・SP', review.render(r, self.root))

    def test_v2_requires_explicit_scope_alignment_and_viewport(self):
        for key in ['device', 'viewport', 'alignment', 'issues']:
            r = self.v2()
            del r['cases'][0][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                review.render(r, self.root)
        r = self.v2()
        r['cases'][0]['viewport']['width'] = True
        with self.assertRaises(ValueError):
            review.render(r, self.root)

    def test_preexisting_issue_is_not_a_pr_requirement(self):
        r = self.v2()
        r['cases'][0].update(result='unchanged', issues=[{
            'origin':'pre-existing', 'priority':'optional', 'summary':'横スクロール',
            'evidence':'前後ともdocument幅916px', 'impact':'今回の悪化は観測していません'}])
        for fmt in ['markdown','html']:
            output = review.render(r, self.root, format=fmt)
            self.assertIn('既存', output)
            self.assertIn('任意', output)
            self.assertIn('要対応 0', output)
        r['cases'][0]['issues'][0]['priority'] = 'required'
        with self.assertRaises(ValueError):
            review.render(r, self.root)

    def test_unknown_issue_cannot_be_required(self):
        r = self.v2()
        r['cases'][0].update(result='needs-review', issues=[{
            'origin':'unknown','priority':'required','summary':'読みにくい',
            'evidence':'Afterのみ確認','impact':'操作が難しい'}])
        with self.assertRaises(ValueError):
            review.render(r, self.root)
        r['cases'][0]['issues'][0]['priority'] = 'investigate'
        self.assertIn('原因不明', review.render(r,self.root))

    def test_required_issue_requires_impact_and_visual_evidence(self):
        r = self.v2()
        r['cases'][0].update(result='needs-review', issues=[{
            'origin':'introduced','priority':'required','summary':'一文字ずつ折返す',
            'evidence':'新規GA4欄で観測','impact':''}])
        with self.assertRaises(ValueError):
            review.render(r, self.root)
        r['cases'][0]['issues'][0]['impact'] = '選択肢が判読困難'
        self.assertIn('要対応 1', review.render(r,self.root))
        r['cases'][0]['result'] = 'unverified'
        r['cases'][0]['after'] = {'state':'unverified','note':'ログイン不可'}
        with self.assertRaises(ValueError):
            review.render(r, self.root)

    def test_worsened_requires_real_before(self):
        r=self.v2()
        r['cases'][0].update(result='needs-review',before={'state':'absent','note':'新規画面'},issues=[{
            'origin':'worsened','priority':'required','summary':'重なり',
            'evidence':'Beforeなし','impact':'ボタンが押せない'}])
        with self.assertRaises(ValueError): review.render(r,self.root)

    def test_unmatched_alignment_cannot_claim_unchanged(self):
        r = self.v2()
        r['cases'][0]['alignment']['method'] = 'unmatched'
        r['cases'][0]['result'] = 'unchanged'
        with self.assertRaises(ValueError): review.render(r,self.root)

    def test_html_is_offline_escaped_and_keeps_local_images(self):
        r=self.v2()
        r['cases'][0]['finding'] = '<script>alert("x")</script> & O\'Reilly'
        output=review.render(r,self.root,format='html')
        self.assertIn('<!doctype html>',output.lower())
        self.assertNotIn('<script',output.lower())
        self.assertNotIn('src="https://',output)
        self.assertIn('images/before.png',output)
        self.assertIn('&lt;script&gt;',output)
        self.assertIn('O&#x27;Reilly',output)
        self.assertIn('通知設定の見出し',output)
        self.assertIn('Safari未実施',output)

    def test_legacy_html_does_not_invent_scope_or_causality(self):
        self.report['cases'][0]['result']='needs-review'
        output=review.render(self.report,self.root,format='html')
        self.assertIn('対象端末の記録なし',output)
        self.assertIn('要確認 1',output)
        self.assertIn('要対応 0',output)

    def test_cli_generates_html_from_saved_report(self):
        import subprocess
        path=self.root/'report.json'
        path.write_text(json.dumps(self.v2()))
        result=subprocess.run([__import__('sys').executable,str(SCRIPT),'render',str(path),'--format','html'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('<!doctype html>',result.stdout.lower())

    def test_authentication_report_only_contains_statuses(self):
        r = self.v2()
        r['authentication'] = {'mode':'manual', 'before':'verified', 'after':'unverified', 'equivalence':'unverified'}
        for fmt in ['markdown', 'html']:
            output = review.render(r, self.root, format=fmt)
            self.assertIn('手動ログイン', output)
            self.assertIn('After 未確認', output)
        r['authentication']['password'] = 'SECRET'
        with self.assertRaises(ValueError) as caught: review.render(r,self.root)
        self.assertNotIn('SECRET',str(caught.exception))

    def test_authentication_equivalence_requires_both_verified(self):
        r=self.v2()
        r['authentication']={'mode':'form','before':'verified','after':'unverified','equivalence':'verified'}
        with self.assertRaises(ValueError): review.render(r,self.root)
        r['authentication']['after']='verified'
        self.assertIn('権限・データ一致 確認済み',review.render(r,self.root))

    def test_public_authentication_does_not_claim_login(self):
        r=self.v2()
        r['authentication']={'mode':'none','before':'not-required','after':'not-required','equivalence':'not-required'}
        self.assertIn('ログイン不要',review.render(r,self.root))
        r['authentication']['after']='verified'
        with self.assertRaises(ValueError): review.render(r,self.root)

    def test_english_report_translates_labels_without_rewriting_evidence(self):
        import re
        r=self.v2()
        r['language']='en'
        r['scope']['note']='Desktop only'
        r['conditions']='1280x760; fixed data'
        r['limitations']=['No live delivery test.']
        r['authentication']={'mode':'none','before':'not-required','after':'not-required','equivalence':'not-required'}
        c=r['cases'][0]
        c.update(title='Notification settings',reason='Added controls',steps=['Open settings'],finding='Controls are visible.',
                 alignment={'method':'page-top','anchor':'Page heading','note':'Same position'})
        for fmt in ['markdown','html']:
            output=review.render(r,self.root,format=fmt)
            self.assertIn('Action required 0',output)
            self.assertIn('Changed',output)
            self.assertIsNone(re.search(r'[\u3040-\u30ff\u4e00-\u9fff]',output))
        c['finding']='Keep the observed text: 保存'
        self.assertIn('Keep the observed text: 保存',review.render(r,self.root,format='html'))
        self.assertIn('lang="en"',review.render(r,self.root,format='html'))

    def test_unsupported_report_language_fails(self):
        self.report['language']='xx'
        with self.assertRaises(ValueError): review.render(self.report,self.root)

    def annotated(self):
        r = self.v2()
        r['language'] = 'en'
        r['cases'][0]['annotations'] = [{'id': 1, 'kind': 'change', 'label': 'New notification controls',
                                        'after': {'x': .1, 'y': .2, 'width': .6, 'height': .4}}]
        return r

    def test_annotation_html_has_overlay_legend_and_original_link(self):
        r=self.annotated()
        output=review.render(r,self.root,format='html')
        self.assertIn('annotation-box change',output)
        self.assertIn('left:10%',output)
        self.assertIn('New notification controls',output)
        self.assertIn('Original screenshots',output)
        self.assertIn('images/after.png',output)

    def test_annotation_validation_rejects_bad_boxes_and_missing_capture(self):
        for box in [{'x':-.1,'y':0,'width':.3,'height':.3},
                    {'x':.9,'y':0,'width':.3,'height':.3},
                    {'x':0,'y':0,'width':0,'height':.3},
                    {'x':True,'y':0,'width':.3,'height':.3},
                    {'x':float('nan'),'y':0,'width':.3,'height':.3}]:
            r=self.annotated();r['cases'][0]['annotations'][0]['after']=box
            with self.subTest(box=box),self.assertRaises(ValueError):review.render(r,self.root,format='html')
        r=self.annotated();r['cases'][0]['after']={'state':'unverified','note':'not captured'};r['cases'][0]['result']='unverified'
        with self.assertRaises(ValueError):review.render(r,self.root,format='html')

    def test_annotation_issue_requires_matching_issue_and_unique_ids(self):
        r=self.annotated();r['cases'][0]['annotations'][0]['kind']='issue'
        with self.assertRaises(ValueError):review.render(r,self.root,format='html')
        r=self.annotated();r['cases'][0]['annotations']*=2
        with self.assertRaises(ValueError):review.render(r,self.root,format='html')

    def test_annotation_cannot_claim_change_in_unchanged_case(self):
        r=self.annotated();r['cases'][0]['result']='unchanged'
        with self.assertRaises(ValueError):review.render(r,self.root,format='html')

    def test_markdown_requires_static_annotation_png(self):
        r=self.annotated()
        with self.assertRaisesRegex(ValueError,'annotate'):review.render(r,self.root)

    def test_annotation_text_is_escaped(self):
        r=self.annotated();r['cases'][0]['annotations'][0]['label']='<script>bad</script>'
        output=review.render(r,self.root,format='html')
        self.assertNotIn('<script>bad',output)
        self.assertIn('&lt;script&gt;bad',output)

    def test_png_export_preserves_source_and_checks_freshness(self):
        try: from PIL import Image
        except ImportError: self.skipTest('Optional PNG tests require Pillow')
        import hashlib
        # A single-capture case (new screen) gets a per-side annotated PNG; a two-capture case gets a composite.
        for name in ['before','after']:Image.new('RGB',(400,300),'white').save(self.root/f'images/{name}.png')
        r=self.annotated();r['cases'][0]['before']={'state':'absent','note':'new screen'}
        source=(self.root/'images/after.png').read_bytes()
        output=review.annotate(r,self.root)
        c=output['cases'][0]['after']
        self.assertEqual((self.root/'images/after.png').read_bytes(),source)
        self.assertNotIn('composite_image',output['cases'][0])
        with Image.open(self.root/c['annotated_image']) as im:
            self.assertEqual(im.size,(400,300))
            self.assertEqual(im.getpixel((390,290))[:3],(255,255,255))
            self.assertNotEqual(im.getpixel((40,60))[:3],(255,255,255))
        md=review.render(output,self.root)
        self.assertIn(c['annotated_image'],md)
        self.assertIn('[original](<images/after.png>)',md)
        # Edited box and changed source both invalidate the derived file.
        stale=copy.deepcopy(output);stale['cases'][0]['annotations'][0]['after']['x']=.2
        with self.assertRaises(ValueError):review.render(stale,self.root)
        Image.new('RGB',(400,300),'black').save(self.root/'images/after.png')
        with self.assertRaises(ValueError):review.render(output,self.root)
        # Export can refresh an old derivative after a metadata/source change.
        self.assertIn('annotated_image',review.annotate(stale,self.root)['cases'][0]['after'])
        # With both captures the frames live in the composite and no per-side PNG is written.
        both=review.annotate(self.annotated(),self.root)['cases'][0]
        self.assertIn('composite_image',both)
        self.assertNotIn('annotated_image',both['after'])

    def test_annotation_publication_requires_both_hosted_versions(self):
        try: from PIL import Image
        except ImportError: self.skipTest('Optional PNG tests require Pillow')
        for name in ['before','after']:Image.new('RGB',(400,300),'white').save(self.root/f'images/{name}.png')
        r=review.annotate(self.annotated(),self.root);api=FakeAPI()
        with self.assertRaisesRegex(ValueError,'composite_url'):review.publish(r,self.root,execute=True,images_reviewed=True,api=api)
        self.assertFalse(api.writes)
        r['cases'][0]['composite_url']='https://example.com/composite.png'
        result=review.publish(r,self.root,api=api)
        self.assertIn('https://example.com/composite.png',result['body'])
        self.assertIn('https://example.com/after.png',result['body'])
        # Single-capture cases still need the hosted annotated PNG.
        single=self.annotated();single['cases'][0]['before']={'state':'absent','note':'new screen'}
        single=review.annotate(single,self.root)
        with self.assertRaisesRegex(ValueError,'annotated_url'):review.publish(single,self.root,api=api)
        single['cases'][0]['after']['annotated_url']='https://example.com/annotated.png'
        self.assertIn('https://example.com/annotated.png',review.publish(single,self.root,api=api)['body'])

    def test_annotation_png_preserves_transparency_and_display_orientation(self):
        try: from PIL import Image
        except ImportError: self.skipTest('Optional PNG tests require Pillow')
        Image.new('RGBA',(400,300),(0,0,0,0)).save(self.root/'images/after.png')
        r=self.annotated();r['cases'][0]['before']={'state':'absent','note':'new screen'}
        r=review.annotate(r,self.root)
        with self.subTest('transparency'), Image.open(self.root/r['cases'][0]['after']['annotated_image']) as im:
            self.assertEqual(im.mode,'RGBA')
            self.assertEqual(im.getpixel((390,290)),(0,0,0,0))
        src=Image.new('RGB',(400,300),'white');exif=Image.Exif();exif[274]=6
        src.save(self.root/'images/rotated.jpg',exif=exif)
        r=self.annotated();r['cases'][0]['before']={'state':'absent','note':'new screen'};r['cases'][0]['after']['image']='images/rotated.jpg'
        r=review.annotate(r,self.root)
        with Image.open(self.root/r['cases'][0]['after']['annotated_image']) as im:
            self.assertEqual(im.size,(300,400))

    def composite_fixture(self, insert_rows=40):
        """Before: a textured page where every row looks different (like real UI rows).
        After: the same page with `insert_rows` white rows inserted at y=50, pushing the rest down."""
        from PIL import Image
        before = Image.new('RGB', (400, 300))
        before.putdata([(((x // 8) * 37 + y * 53) % 200 + 40,) * 3 for y in range(300) for x in range(400)])
        after = Image.new('RGB', (400, 300), 'white')
        after.paste(before.crop((0, 0, 400, 50)), (0, 0))
        after.paste(before.crop((0, 50, 400, 300 - insert_rows)), (0, 50 + insert_rows))
        before.save(self.root / 'images/before.png')
        after.save(self.root / 'images/after.png')
        return self.v2()

    def diff_origin(self):
        ia = review.image_annotations
        return (ia.PANEL_PAD + (400 + ia.GUTTER + ia.PANEL_GAP) * 2 + ia.GUTTER, ia.PANEL_PAD + ia.PANEL_HEAD)

    def test_composite_is_written_for_both_captures_and_marks_inserted_rows_not_shifted_content(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Optional PNG tests require Pillow')
        output = review.annotate(self.composite_fixture(), self.root)
        case = output['cases'][0]
        self.assertIn('composite_image', case)
        self.assertNotIn('annotated_image', case['after'], 'no annotations were requested')
        ia = review.image_annotations
        with Image.open(self.root / case['composite_image']) as im:
            self.assertEqual(im.size, (ia.PANEL_PAD * 2 + (400 + ia.GUTTER) * 3 + ia.PANEL_GAP * 2,
                                       ia.PANEL_PAD * 2 + ia.PANEL_HEAD + 300), 'three panels side by side for narrow captures')
            diff_x, diff_y = self.diff_origin()
            inserted = im.getpixel((diff_x + 200, diff_y + 70))[:3]
            self.assertGreater(inserted[2], inserted[0], 'inserted rows are tinted blue')
            self.assertEqual(im.getpixel((diff_x - ia.GUTTER + 2, diff_y + 70))[:3], ia.DIFF_INSERTED, 'gutter marks the band')
            shifted = im.getpixel((diff_x + 200, diff_y + 200))[:3]
            self.assertEqual(len(set(shifted)), 1, 'content that only moved down stays gray, not red')
            self.assertNotEqual(im.getpixel((diff_x + 200, diff_y + 20))[:3], ia.DIFF_CHANGED, 'rows above the insert are unchanged')

    def test_composite_changed_pixels_are_red_and_markdown_uses_one_image(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Optional PNG tests require Pillow')
        r = self.composite_fixture(insert_rows=0)
        with Image.open(self.root / 'images/after.png') as after:
            after = after.copy()
        after.paste((200, 0, 0), (20, 140, 380, 160))  # same rows, different pixels
        after.save(self.root / 'images/after.png')
        output = review.annotate(r, self.root)
        case = output['cases'][0]
        ia = review.image_annotations
        with Image.open(self.root / case['composite_image']) as im:
            diff_x, diff_y = self.diff_origin()
            self.assertEqual(im.getpixel((diff_x + 200, diff_y + 150))[:3], ia.DIFF_CHANGED)
            self.assertEqual(len(set(im.getpixel((diff_x + 200, diff_y + 250))[:3])), 1, 'unchanged rows stay gray')
        md = review.render(output, self.root)
        self.assertIn(f"![Before / After / Diff](<{case['composite_image']}>)", md)
        self.assertNotIn('| Before | After |', md.split('<details>')[0], 'the body shows the composite instead of the pair')
        self.assertIn('[Before](<images/before.png>)', md)
        self.assertIn('[After](<images/after.png>)', md)
        html = review.render(output, self.root, format='html')
        self.assertIn(case['composite_image'], html)

    def test_composite_goes_stale_and_remote_needs_its_url(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest('Optional PNG tests require Pillow')
        output = review.annotate(self.composite_fixture(), self.root)
        api = FakeAPI()
        with self.assertRaisesRegex(ValueError, 'composite'):
            review.publish(output, self.root, api=api)
        output['cases'][0]['composite_url'] = 'https://example.com/composite.png'
        self.assertIn('https://example.com/composite.png', review.publish(output, self.root, api=api)['body'])
        Image.new('RGB', (400, 300), 'black').save(self.root / 'images/before.png')
        with self.assertRaisesRegex(ValueError, 'Stale composite'):
            review.render(output, self.root)
        # A report with a composite but an absent side is rejected before any image work.
        broken = self.v2()
        broken['cases'][0].update(composite_image='annotated/x.png', before={'state': 'absent', 'note': 'new'})
        with self.assertRaises(ValueError):
            review.render(broken, self.root)

    def test_annotation_cli_cannot_overwrite_source_images(self):
        import subprocess
        try: from PIL import Image
        except ImportError: self.skipTest('Optional PNG tests require Pillow')
        Image.new('RGB',(400,300),'white').save(self.root/'images/after.png')
        for filename in ['source.png','source.json']:
            original=(self.root/'images/after.png').read_bytes()
            (self.root/filename).write_bytes(original)
            r=self.annotated();r['cases'][0]['after']['image']=filename
            p=self.root/'report.json';p.write_text(json.dumps(r))
            process=subprocess.run([sys.executable,str(SCRIPT),'annotate',str(p),'--out',str(self.root/filename)],capture_output=True,text=True)
            self.assertNotEqual(process.returncode,0)
            self.assertEqual((self.root/filename).read_bytes(),original)


if __name__ == '__main__':
    unittest.main()
