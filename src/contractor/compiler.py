import json
import logging
import os

from solc import install_solc, compile_standard

DEFAULT_SOLC_VERSION = 'v0.5.3'

logger = logging.getLogger(__name__)


def __compiler_input_from_directory(src_dir, ext_dir=None, optimizer_runs=200):
    """Generate input JSON for solc given directories of contracts to compile.

    :param src_dir: Directory containing contract Solidity source
    :param ext_dir: Directory containing external dependencies
    :return: Dictionary containing solc input
    """
    sources = {}
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if os.path.splitext(file)[-1] != '.sol':
                continue

            with open(os.path.join(root, file), 'r') as f:
                sources[file] = f.read()

    logger.info('Compiling %s', ', '.join(sources.keys()))

    remappings = []
    if ext_dir:
        for ext in os.listdir(ext_dir):
            remappings.append(ext + '=' + os.path.join(ext_dir, ext))

    ret = {
        'language': 'Solidity',
        'sources': {k: {'content': v} for k, v in sources.items()},
        'settings': {
            'optimizer': {
                'enabled': True,
                'runs': optimizer_runs,
            },
            'outputSelection': {
                '*': {
                    '*': [
                        'abi',
                        'evm.bytecode.object',
                        'evm.bytecode.linkReferences',
                    ]
                }
            }
        }
    }

    if remappings:
        ret['settings']['remappings'] = remappings

    return ret


def __write_compiler_output(output, source_files, out_dir):
    """Write output JSON from solc to a directory.

    :param output: Output from solc
    :param source_files: Source files compiled to generate provided output
    :param out_dir: Directory to write output JSON to
    :return: True if contracts have changed, else False
    """
    is_dirty = False

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    contracts = output['contracts']
    for source_file in source_files:
        out_file = os.path.join(out_dir, os.path.splitext(source_file)[0] + '.json')

        # Restructure this for compatibility with polyswarmd et al
        name = next(iter(contracts[source_file]))
        contract = contracts[source_file][name]
        contract['contractName'] = name

        # Attempt to match bytecode to see if we need to redeploy
        if not os.path.exists(out_file):
            is_dirty = True
        else:
            with open(out_file, 'r') as f:
                orig_contract = json.load(f)
                if orig_contract != contract:
                    is_dirty = True

        logger.info('Writing %s', out_file)
        with open(out_file, 'w') as f:
            json.dump(contract, f, indent=2, sort_keys=True)

    return is_dirty


def configure_compiler(solc_version):
    """Set up a specific solc version.

    :param solc_version: Version of solc to configure
    :return: Path to the solc executable
    """
    # py-solc lets us select a version of the compiler to use, which is nice,
    # but requires some massaging to actually use it
    solc_path = os.path.expanduser('~/.py-solc/solc-{0}/bin/solc'.format(solc_version))
    if not os.path.isfile(solc_path):
        install_solc(solc_version)
    os.environ['SOLC_BINARY'] = solc_path
    return solc_path


def compile_directory(solc_version, src_dir, out_dir, ext_dir=None, optimizer_runs=200):
    """Compile a directory of contracts into output JSON.

    :param solc_version: Version of solc to use
    :param src_dir: Directory containing contract Solidity source
    :param out_dir: Directory to output compiled JSON into
    :param ext_dir: Directory containing external dependencies
    :param optimizer_runs: Number of runs to put the contract through the optimizer
    :return: True if contracts have changed, else False
    """
    configure_compiler(solc_version)

    kwargs = {}
    if ext_dir:
        kwargs['allow_paths'] = os.path.abspath(ext_dir)

    input = __compiler_input_from_directory(src_dir, ext_dir=ext_dir, optimizer_runs=optimizer_runs)
    source_files = input['sources'].keys()
    output = compile_standard(input, **kwargs)
    # TODO: Compilation errors will be reported via a SolcError, should report these in a friendlier manner

    return __write_compiler_output(output, source_files, out_dir)
