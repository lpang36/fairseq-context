#!/bin/bash

DATASET_NAME=java-context
SOURCE_DIR=
TARGET_DIR=

for SPLIT in "test" "val" "train"; do
    python code2seq_to_fairseq.py --input_file="${SOURCE_DIR}/${DATASET_NAME}.${SPLIT}.c2s" --output_dir=$TARGET_DIR --split=$SPLIT
done

TRAINPREF=$TARGET_DIR/train
VALIDPREF=$TARGET_DIR/val
TESTPREF=$TARGET_DIR/test

python preprocess.py --source-lang src --target-lang trg --trainpref $TRAINPREF --validpref $VALIDPREF --testpref $TESTPREF --destdir $TARGET_DIR/bin --joined-dictionary --workers 10
python preprocess.py --source-lang leaf --source-only --trainpref $TRAINPREF --validpref $VALIDPREF --testpref $TESTPREF --destdir $TARGET_DIR/bin --workers 10 --nested-line
python preprocess.py --source-lang path --source-only --trainpref $TRAINPREF --validpref $VALIDPREF --testpref $TESTPREF --destdir $TARGET_DIR/bin --workers 10 --nested-line
