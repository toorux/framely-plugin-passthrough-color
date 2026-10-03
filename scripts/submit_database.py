"""Register a published plugin in the author's database fork."""
import argparse
import json
import os
import pathlib
import re
import subprocess
import tempfile

def run(*args, cwd=None):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def channel(version):
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?', version):
        raise ValueError('Expected a semantic version')
    return 'testing' if '-' in version.split('+')[0] else 'main'


def prepare(database, plugin_url, commit, identifier):
    """Stage only the submodule registration, preserving the rest of the database."""
    if not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)+', identifier):
        raise ValueError('Invalid plugin ID')
    path = 'plugins/' + identifier
    modules = pathlib.Path(database) / '.gitmodules'
    existing = run('git', 'config', '-f', str(modules), '--get-regexp', r'^submodule\..*\.path$') if modules.exists() and modules.read_text().strip() else ''
    sections = [line.rsplit(' ', 1)[0][:-5] for line in existing.splitlines() if line.rsplit(' ', 1)[-1] == path]
    if sections:
        registered_url = run('git', 'config', '-f', str(modules), '--get', sections[0] + '.url')
        if registered_url != plugin_url:
            raise ValueError('Existing submodule belongs to another repository')
        run('git', 'submodule', 'update', '--init', '--', path, cwd=database)
    else:
        run('git', 'submodule', 'add', plugin_url, path, cwd=database)
    source = pathlib.Path(database) / path
    run('git', 'fetch', 'origin', commit, cwd=source)
    run('git', 'checkout', '--detach', commit, cwd=source)
    run('git', 'add', '.gitmodules', path, cwd=database)
    return path


def submit(tag):
    repository = os.environ.get('DATABASE_REPOSITORY', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Configure DATABASE_REPOSITORY as owner/repository in Actions variables')
    if not os.environ.get('GH_TOKEN'):
        raise ValueError('Configure the DATABASE_TOKEN Actions secret before submitting')
    plugin_repo = os.environ['GITHUB_REPOSITORY']
    plugin_url = 'https://github.com/' + plugin_repo + '.git'
    commit = run('git', 'rev-parse', '--verify', 'refs/tags/' + tag + '^{commit}')
    manifest = json.loads(run('git', 'show', commit + ':manifest.json'))
    version, identifier = manifest['version'], manifest['id']
    if tag != 'v' + version:
        raise ValueError('Release tag must match manifest.version')
    base = channel(version)
    release = json.loads(run('gh', 'api', 'repos/' + plugin_repo + '/releases/tags/' + tag))
    if release['draft']:
        raise ValueError('Release must be published before submission')
    if release['prerelease']:
        base = 'testing'
    filename = identifier + '-' + version + '.framely'
    expected_url = 'https://github.com/' + plugin_repo + '/releases/download/' + tag + '/' + filename
    if manifest.get('downloadUrl') != expected_url or expected_url not in [a['browser_download_url'] for a in release['assets']]:
        raise ValueError('Release asset must exist and match manifest.downloadUrl')
    with tempfile.TemporaryDirectory() as temporary:
        database = pathlib.Path(temporary) / 'database'
        run('gh', 'auth', 'setup-git')
        run('git', 'clone', '--branch', base, 'https://github.com/' + repository + '.git', str(database))
        prepare(database, plugin_url, commit, identifier)
        # Validate the pinned manifests and actual release packages before updating the channel.
        run('python3', 'scripts/database.py', 'fetch', cwd=database)
        run('python3', 'scripts/database.py', 'validate', '--packages', cwd=database)
        if subprocess.run(['git', 'diff', '--cached', '--quiet'], cwd=database).returncode == 0:
            print('Plugin release is already registered on ' + base)
            return
        run('git', 'config', 'user.name', 'github-actions[bot]', cwd=database)
        run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com', cwd=database)
        run('git', 'commit', '-m', 'Register ' + identifier + ' ' + version, cwd=database)
        run('git', 'push', 'origin', 'HEAD:refs/heads/' + base, cwd=database)
        url = 'https://github.com/' + repository + '/tree/' + base
        print('Registered ' + identifier + ' ' + version + ': ' + url)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
                summary.write(f'已更新数据库 {base} 分支：{url}\n')



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('tag')
    submit(parser.parse_args().tag)
