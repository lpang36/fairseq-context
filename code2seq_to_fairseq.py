import argparse
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input_file')
    parser.add_argument('-o', '--output_dir')
    parser.add_argument('-s', '--split')
    args = parser.parse_args()

    with open(os.path.join(args.output_dir, '%s.%s' % (args.split, 'src')), 'w') as src_file:
        with open(os.path.join(args.output_dir, '%s.%s' % (args.split, 'trg')), 'w') as trg_file:
            with open(os.path.join(args.output_dir, '%s.%s' % (args.split, 'leaf')), 'w') as leaf_file:
                with open(os.path.join(args.output_dir, '%s.%s' % (args.split, 'path')), 'w') as path_file:
                    for line in open(args.input_file):
                        line = line.strip().split(' ')
                        if len(line) < 3:
                            continue
                        trg = ' '.join(line[0].split('|'))
                        src = ' '.join(line[1].split('|'))
                        leaves = []
                        paths = []
                        for path in line[2:]:
                            path = path.strip().split('|')
                            if len(path) < 3:
                                continue
                            leaves.append('|'.join([path[0], path[-1]]))
                            paths.append('|'.join(path[1:-1]))
                        src_file.write(src + '\n')
                        trg_file.write(trg + '\n')
                        leaf_file.write(' '.join(leaves) + '\n')
                        path_file.write(' '.join(paths) + '\n')
