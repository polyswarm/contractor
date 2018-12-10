from contractor.util import call_with_output


def solium_analyze_directory(src_dir):
    cmd = ['solium', '-d', src_dir]
    return call_with_output(cmd)
