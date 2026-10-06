"""Serve isolated Git revisions for manual real-browser Skill validation.

Run from repository root: python3 tests/smoke_server.py
Stops with Ctrl-C. No network services beyond two loopback-only HTTP servers.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import threading

PAGE = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<title>PR Visual Review fixture</title>
<style>
body { font: 18px system-ui; margin: 48px; color: #17212b; background: #fafafa; }
button { padding: 10px 18px; font: inherit; cursor: pointer; }
dialog { padding: 28px; width: 420px; border: 1px solid #999; }
dialog::backdrop { background: #0004; }
.actions { display: flex; gap: GAP; margin-top: 24px; }
#metrics { font: 12px monospace; }
</style>
<h1>設定 — ローカル検証用</h1>
<p>実顧客データ・外部接続なし。通知モーダルのボタン間隔を比較します。</p>
<button id="open">通知設定を編集</button>
<p id="metrics"></p>
<dialog><h2>通知設定</h2><p>メール通知: オフ（固定fixture）</p>
<div class="actions"><button id="cancel">キャンセル</button><button>保存</button></div></dialog>
<script>
document.querySelector('#open').onclick = () => document.querySelector('dialog').showModal();
document.querySelector('#cancel').onclick = () => document.querySelector('dialog').close();
document.querySelector('#metrics').textContent = `Viewport: ${innerWidth}x${innerHeight}; DPR: ${devicePixelRatio}; locale: ${navigator.language}; timezone: ${Intl.DateTimeFormat().resolvedOptions().timeZone}`;
</script></html>'''


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), '-c', 'user.name=Skill Fixture',
                                    '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgSign=false',
                                    '-c', 'core.hooksPath=/dev/null', *args], text=True).strip()


def main():
    output = Path('examples/smoke').resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='pr-visual-review-') as temporary:
        root = Path(temporary)
        repo = root / 'repo'
        repo.mkdir()
        git(repo, 'init', '-q')
        (repo / 'index.html').write_text(PAGE.replace('GAP', '0px'))
        git(repo, 'add', 'index.html')
        git(repo, 'commit', '-qm', 'fixture: before')
        before = git(repo, 'rev-parse', 'HEAD')
        (repo / 'index.html').write_text(PAGE.replace('GAP', '24px'))
        git(repo, 'commit', '-qam', 'fixture: add button spacing')
        after = git(repo, 'rev-parse', 'HEAD')
        assert git(repo, 'merge-base', before, after) == before
        servers = []
        paths = []
        metadata = {'before_sha': before, 'head_sha': after, 'fixture_only': True}
        for label, sha in [('before', before), ('after', after)]:
            path = root / label
            git(repo, 'worktree', 'add', '--detach', str(path), sha)
            assert git(path, 'rev-parse', 'HEAD') == sha
            handler = partial(SimpleHTTPRequestHandler, directory=str(path))
            server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            servers.append(server)
            paths.append(path)
            metadata[label + '_url'] = f'http://127.0.0.1:{server.server_port}'
        (output / 'run.json').write_text(json.dumps(metadata, indent=2) + '\n')
        print(json.dumps(metadata, indent=2), flush=True)
        try:
            signal.pause()
        except KeyboardInterrupt:
            pass
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()
            for path in paths:
                git(repo, 'worktree', 'remove', str(path))


if __name__ == '__main__':
    main()
