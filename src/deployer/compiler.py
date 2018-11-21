import json
import os

from solc import install_solc, compile_standard


def __compiler_input_from_directory(src_dir, ext_dir=None):
    sources = {}
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if os.path.splitext(file)[-1] != '.sol':
                continue

            with open(os.path.join(root, file), 'r') as f:
                sources[file] = f.read()

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
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    contracts = output['contracts']
    for source_file in source_files:
        out_file = os.path.join(out_dir, os.path.splitext(source_file)[0] + '.json')
        with open(out_file, 'w') as f:
            f.write(json.dumps(contracts[source_file], indent=2, sort_keys=True))


def compile_directory(src_dir, out_dir, ext_dir=None, solc_version='v0.4.25'):
    solc_path = os.path.expanduser('~/.py-solc/solc-{0}/bin/solc'.format(solc_version))
    if not os.path.isfile(solc_path):
        install_solc(solc_version)
    os.environ['SOLC_BINARY'] = solc_path

    kwargs = {}
    if ext_dir:
        kwargs['allow_paths'] = os.path.abspath(ext_dir)

    input = __compiler_input_from_directory(src_dir, ext_dir)
    source_files = input['sources'].keys()
    output = compile_standard(input, **kwargs)
    __write_compiler_output(output, source_files, out_dir)
