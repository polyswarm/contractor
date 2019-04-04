import logging
import subprocess

logger = logging.getLogger(__name__)


def get_git_status(cwd):
    """Retrieve the Git status of our source tree, for tracking what version of contractor was used in a deployment.

    :param cwd: Current working directory
    :return: Commit hash and dirty status of our source tree, as a tuple
    """
    try:
        commit_hash = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=cwd).decode('utf-8').rstrip()
        tree_dirty = subprocess.call(['git', 'diff', '--quiet'], cwd=cwd) != 0

        return commit_hash, tree_dirty
    except subprocess.CalledProcessError:
        logger.warning('Could not retrieve git status')
        return None, True
