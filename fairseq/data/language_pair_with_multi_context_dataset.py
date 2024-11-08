# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in
# the root directory of this source tree. An additional grant of patent rights
# can be found in the PATENTS file in the same directory.

import numpy as np
import torch

from fairseq import utils

from . import data_utils, FairseqDataset, ConcatDataset, LanguagePairDataset


def collate(
    samples, pad_idx, eos_idx, left_pad_source=True, left_pad_target=False,
    input_feeding=True,
):
    if len(samples) == 0:
        return {}

    def merge(key, left_pad, move_eos_to_beginning=False):
        return data_utils.collate_tokens(
            [s[key] for s in samples],
            pad_idx, eos_idx, left_pad, move_eos_to_beginning,
        )

    id = torch.LongTensor([s['id'] for s in samples])
    src_tokens = merge('source', left_pad=left_pad_source)
    start_leaf_tokens = merge('start_leaf', left_pad=left_pad_source)
    end_leaf_tokens = merge('end_leaf', left_pad=left_pad_source)
    path_tokens = merge('path', left_pad=left_pad_source)

    # sort by descending source length
    src_lengths = torch.LongTensor([s['source'].numel() for s in samples])
    start_leaf_lengths = torch.LongTensor([s['start_leaf'].numel() for s in samples])
    end_leaf_lengths = torch.LongTensor([s['end_leaf'].numel() for s in samples])
    path_lengths = torch.LongTensor([s['path'].numel() for s in samples])
    src_lengths, sort_order = src_lengths.sort(descending=True)
    id = id.index_select(0, sort_order)
    src_tokens = src_tokens.index_select(0, sort_order)
    start_leaf_tokens = start_leaf_tokens.index_select(0, sort_order)
    start_leaf_lengths = start_leaf_lengths.index_select(0, sort_order)
    end_leaf_tokens = end_leaf_tokens.index_select(0, sort_order)
    end_leaf_lengths = end_leaf_lengths.index_select(0, sort_order)
    path_tokens = path_tokens.index_select(0, sort_order)
    path_lengths = path_lengths.index_select(0, sort_order)

    prev_output_tokens = None
    target = None
    if samples[0].get('target', None) is not None:
        target = merge('target', left_pad=left_pad_target)
        target = target.index_select(0, sort_order)
        ntokens = sum(len(s['target']) for s in samples)

        if input_feeding:
            # we create a shifted version of targets for feeding the
            # previous output token(s) into the next decoder step
            prev_output_tokens = merge(
                'target',
                left_pad=left_pad_target,
                move_eos_to_beginning=True,
            )
            prev_output_tokens = prev_output_tokens.index_select(0, sort_order)
    else:
        ntokens = sum(len(s['source']) for s in samples)

    batch = {
        'id': id,
        'ntokens': ntokens,
        'net_input': {
            'src_tokens': src_tokens,
            'src_lengths': src_lengths,
            'start_leaf_tokens': start_leaf_tokens,
            'start_leaf_lengths': start_leaf_lengths,
            'end_leaf_tokens': end_leaf_tokens,
            'end_leaf_lengths': end_leaf_lengths,
            'path_tokens': path_tokens,
            'path_lengths': path_lengths,
        },
        'target': target,
        'nsentences': samples[0]['source'].size(0),
    }
    if prev_output_tokens is not None:
        batch['net_input']['prev_output_tokens'] = prev_output_tokens
    return batch


class LanguagePairWithMultiContextDataset(LanguagePairDataset):
    """
    A pair of torch.utils.data.Datasets.

    Args:
        src (torch.utils.data.Dataset): source dataset to wrap
        src_sizes (List[int]): source sentence lengths
        src_dict (~fairseq.data.Dictionary): source vocabulary
        tgt (torch.utils.data.Dataset, optional): target dataset to wrap
        tgt_sizes (List[int], optional): target sentence lengths
        tgt_dict (~fairseq.data.Dictionary, optional): target vocabulary
        leaf
        leaf_sizes
        leaf_dict
        path
        path_sizes
        path_dict
        left_pad_source (bool, optional): pad source tensors on the left side.
            Default: ``True``
        left_pad_target (bool, optional): pad target tensors on the left side.
            Default: ``False``
        max_source_positions (int, optional): max number of tokens in the source
            sentence. Default: ``1024``
        max_target_positions (int, optional): max number of tokens in the target
            sentence. Default: ``1024``
        shuffle (bool, optional): shuffle dataset elements before batching.
            Default: ``True``
        input_feeding (bool, optional): create a shifted version of the targets
            to be passed into the model for input feeding/teacher forcing.
            Default: ``True``
        remove_eos_from_source (bool, optional): if set, removes eos from end of
            source if it's present. Default: ``False``
        append_eos_to_target (bool, optional): if set, appends eos to end of
            target if it's absent. Default: ``False``
    """

    def __init__(
        self, src, src_sizes, src_dict,
        tgt=None, tgt_sizes=None, tgt_dict=None,
        leaf=None, leaf_sizes=None, leaf_dict=None,
        path=None, path_sizes=None, path_dict=None,
        left_pad_source=True, left_pad_target=False,
        max_source_positions=1024, max_target_positions=1024,
        shuffle=True, input_feeding=True, remove_eos_from_source=False, append_eos_to_target=False,
    ):
        super(LanguagePairWithMultiContextDataset,self).__init__(
            src, src_sizes, src_dict,
            tgt, tgt_sizes, tgt_dict,
            left_pad_source, left_pad_target,
            max_source_positions, max_target_positions,
            shuffle, input_feeding, remove_eos_from_source, append_eos_to_target,
        )
        self.leaf = leaf
        self.path = path
        self.leaf_sizes = np.array(leaf_sizes)
        self.path_sizes = np.array(path_sizes) if path_sizes is not None else None
        self.leaf_dict = leaf_dict
        self.path_dict = path_dict

    def __getitem__(self, index):
        tgt_item = self.tgt[index] if self.tgt is not None else None
        src_item = self.src[index]
        leaf_item = self.leaf[index]
        path_item = self.path[index]

        ind = torch.nonzero(leaf_item == self.leaf_dict.leaf())[0]
        start_leaf_item = leaf_item[:ind]
        end_leaf_item = leaf_item[(ind+1):]

        # Append EOS to end of tgt sentence if it does not have an EOS and remove
        # EOS from end of src sentence if it exists. This is useful when we use
        # use existing datasets for opposite directions i.e., when we want to
        # use tgt_dataset as src_dataset and vice versa
        if self.append_eos_to_target:
            eos = self.tgt_dict.eos() if self.tgt_dict else self.src_dict.eos()
            if self.tgt and self.tgt[index][-1] != eos:
                tgt_item = torch.cat([self.tgt[index], torch.LongTensor([eos])])

        if self.remove_eos_from_source:
            eos = self.src_dict.eos()
            if self.src[index][-1] == eos:
                src_item = self.src[index][:-1]

        return {
            'id': index,
            'source': src_item,
            'target': tgt_item,
            'start_leaf': start_leaf_item,
            'end_leaf': end_leaf_item,
            'path': path_item,
        }

    def __len__(self):
        return len(self.src)

    def collater(self, samples):
        """Merge a list of samples to form a mini-batch.

        Args:
            samples (List[dict]): samples to collate

        Returns:
            dict: a mini-batch with the following keys:

                - `id` (LongTensor): example IDs in the original input order
                - `ntokens` (int): total number of tokens in the batch
                - `net_input` (dict): the input to the Model, containing keys:

                  - `src_tokens` (LongTensor): a padded 2D Tensor of tokens in
                    the source sentence of shape `(bsz, src_len)`. Padding will
                    appear on the left if *left_pad_source* is ``True``.
                  - `src_lengths` (LongTensor): 1D Tensor of the unpadded
                    lengths of each source sentence of shape `(bsz)`
                  - `ctx_tokens` (LongTensor)
                  - `ctx_lengths` (LongTensor)
                  - `prev_output_tokens` (LongTensor): a padded 2D Tensor of
                    tokens in the target sentence, shifted right by one position
                    for input feeding/teacher forcing, of shape `(bsz,
                    tgt_len)`. This key will not be present if *input_feeding*
                    is ``False``. Padding will appear on the left if
                    *left_pad_target* is ``True``.

                - `target` (LongTensor): a padded 2D Tensor of tokens in the
                  target sentence of shape `(bsz, tgt_len)`. Padding will appear
                  on the left if *left_pad_target* is ``True``.
        """
        return collate(
            samples, pad_idx=self.src_dict.pad(), eos_idx=self.src_dict.eos(),
            left_pad_source=self.left_pad_source, left_pad_target=self.left_pad_target,
            input_feeding=self.input_feeding,
        )

    def get_dummy_batch(self, num_tokens, max_positions, src_len=128, tgt_len=128):
        """Return a dummy batch with a given number of tokens."""
        src_len, tgt_len = utils.resolve_max_positions(
            (src_len, tgt_len),
            max_positions,
            (self.max_source_positions, self.max_target_positions),
        )
        bsz = max(num_tokens // max(src_len, tgt_len), 1)
        return self.collater([
            {
                'id': i,
                'source': self.src_dict.dummy_sentence(src_len),
                'target': self.tgt_dict.dummy_sentence(tgt_len) if self.tgt_dict is not None else None,
                'start_leaf': self.leaf_dict.dummy_sentence(src_len),
                'end_leaf': self.leaf_dict.dummy_sentence(src_len),
                'path': self.path_dict.dummy_sentence(src_len),
            }
            for i in range(bsz)
        ])

    def prefetch(self, indices):
        self.src.prefetch(indices)
        self.tgt.prefetch(indices)
        self.leaf.prefetch(indices)
        self.path.prefetch(indices)

    @property
    def supports_prefetch(self):
        return (
            hasattr(self.src, 'supports_prefetch')
            and self.src.supports_prefetch
            and hasattr(self.tgt, 'supports_prefetch')
            and self.tgt.supports_prefetch
            and hasattr(self.leaf, 'supports_prefetch')
            and self.leaf.supports_prefetch
            and hasattr(self.path, 'supports_prefetch')
            and self.path.supports_prefetch
        )
