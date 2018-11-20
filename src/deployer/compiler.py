import os

from solc import compile_standard

def compiler_json_from_directory(dir):
    for root, dirs, files in os.walk(dir):
        for file in files:
            print(os.path.join(root, file))
