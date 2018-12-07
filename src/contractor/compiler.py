import json
import logging
import os

from solc import install_solc, compile_standard

DEFAULT_SOLC_VERSION = 'v0.4.25'

logger = logging.getLogger(__name__)


def __compiler_input_from_directory(src_dir, ext_dir=None):
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
                'runs': 200,
            },
            # XXX: We might not need all of these, definitely require abi and bytecode object though
            'outputSelection': {
                '*': {
                    '*': [
                        'abi',
                        'ast',
                        'evm.bytecode.object',
                        'evm.bytecode.sourceMap',
                        'evm.bytecode.linkReferences',
                        'evm.deployedBytecode.object',
                        'evm.deployedBytecode.sourceMap',
                        'evm.deployedBytecode.linkReferences',
                    ]
                }
            }
        }
    }

    if remappings:
        ret['settings']['remappings'] = remappings

    return ret


def __write_compiler_output(output, source_files, out_dir):
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
    # py-solc lets us select a version of the compiler to use, which is nice,
    # but requires some massaging to actually use it
    solc_path = os.path.expanduser('~/.py-solc/solc-{0}/bin/solc'.format(solc_version))
    if not os.path.isfile(solc_path):
        install_solc(solc_version)
    os.environ['SOLC_BINARY'] = solc_path
    return solc_path


def compile_directory(solc_version, src_dir, out_dir, ext_dir=None):
    configure_compiler(solc_version)

    kwargs = {}
    if ext_dir:
        kwargs['allow_paths'] = os.path.abspath(ext_dir)

    input = __compiler_input_from_directory(src_dir, ext_dir)
    source_files = input['sources'].keys()
    output = compile_standard(input, **kwargs)
    # TODO: Compilation errors will be reported via a SolcError, should report these in a friendlier manner

    return __write_compiler_output(output, source_files, out_dir)
