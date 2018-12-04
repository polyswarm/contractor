import subprocess

def get_git_status(cwd):
    commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd).decode('utf-8').rstrip()
    tree_dirty = subprocess.call(['git', 'diff', '--quiet'], cwd=cwd) != 0

    return commit_hash, tree_dirty
