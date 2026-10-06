"""Create two Git revisions and serve the public README demo on loopback.

python3 tests/demo_server.py; stop with Ctrl-C. Does not capture or claim results.
"""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import signal
import tempfile
import threading
from smoke_server import git


def main():
    output = Path(__file__).resolve().parents[1] / 'examples/demo'
    template = (output / 'app.html').read_text()
    addition = '<section class="notifications"><h2>Email notifications</h2><p>Get an email when a review is requested or updated.</p><label><input type="checkbox" checked>Notify me about review updates</label></section>'
    with tempfile.TemporaryDirectory(prefix='pr-visual-demo-') as tmp:
        root=Path(tmp); repo=root/'repo'; repo.mkdir()
        git(repo,'init','-q')
        revisions={}
        for version in ('before','after'):
            (repo/'index.html').write_text(template.replace('__VERSION__',version).replace('__NOTIFICATIONS__',addition if version=='after' else ''))
            git(repo,'add','index.html'); git(repo,'commit','-qm','demo: '+version)
            revisions[version]=git(repo,'rev-parse','HEAD')
        assert git(repo,'merge-base',revisions['before'],revisions['after'])==revisions['before']
        (output/'change.patch').write_text(git(repo,'diff',revisions['before'],revisions['after'])+'\n')
        servers=[]; trees=[]
        metadata={'fixture_only':True,'before_sha':revisions['before'],'head_sha':revisions['after']}
        for version,sha in revisions.items():
            path=root/version
            git(repo,'worktree','add','--detach',str(path),sha); trees.append(path)
            server=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(path)))
            threading.Thread(target=server.serve_forever,daemon=True).start(); servers.append(server)
            metadata[version+'_url']=f'http://127.0.0.1:{server.server_port}'
        (output/'run.json').write_text(json.dumps(metadata,indent=2)+'\n')
        print(json.dumps(metadata,indent=2),flush=True)
        try: signal.pause()
        except KeyboardInterrupt: pass
        finally:
            for server in servers: server.shutdown(); server.server_close()
            for path in trees: git(repo,'worktree','remove',str(path))


if __name__=='__main__': main()
