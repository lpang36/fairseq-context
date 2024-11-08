# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in
# the root directory of this source tree. An additional grant of patent rights
# can be found in the PATENTS file in the same directory.

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from fairseq import options, utils
from fairseq.modules import (
    AdaptiveSoftmax, BeamableMM, GradMultiply, LearnedPositionalEmbedding,
    LinearizedConvolution,
)

from . import (
    FairseqEncoder, FairseqIncrementalDecoder, FairseqModel,
    FairseqLanguageModel, FairseqContextModel, FairseqMultiContextModel,
    register_model, register_model_architecture,
)


@register_model('fconv')
class FConvModel(FairseqModel):
    """
    A fully convolutional model, i.e. a convolutional encoder and a
    convolutional decoder, as described in `"Convolutional Sequence to Sequence
    Learning" (Gehring et al., 2017) <https://arxiv.org/abs/1705.03122>`_.

    Args:
        encoder (FConvEncoder): the encoder
        decoder (FConvDecoder): the decoder

    The Convolutional model provides the following named architectures and
    command-line arguments:

    .. argparse::
        :ref: fairseq.models.fconv_parser
        :prog:
    """

    def __init__(self, encoder, decoder):
        super().__init__(encoder, decoder)
        self.encoder.num_attention_layers = sum(layer is not None for layer in decoder.attention)

    @staticmethod
    def add_args(parser):
        """Add model-specific arguments to the parser."""
        parser.add_argument('--dropout', type=float, metavar='D',
                            help='dropout probability')
        parser.add_argument('--encoder-embed-dim', type=int, metavar='N',
                            help='encoder embedding dimension')
        parser.add_argument('--encoder-embed-path', type=str, metavar='STR',
                            help='path to pre-trained encoder embedding')
        parser.add_argument('--encoder-layers', type=str, metavar='EXPR',
                            help='encoder layers [(dim, kernel_size), ...]')
        parser.add_argument('--decoder-embed-dim', type=int, metavar='N',
                            help='decoder embedding dimension')
        parser.add_argument('--decoder-embed-path', type=str, metavar='STR',
                            help='path to pre-trained decoder embedding')
        parser.add_argument('--decoder-layers', type=str, metavar='EXPR',
                            help='decoder layers [(dim, kernel_size), ...]')
        parser.add_argument('--decoder-out-embed-dim', type=int, metavar='N',
                            help='decoder output embedding dimension')
        parser.add_argument('--decoder-attention', type=str, metavar='EXPR',
                            help='decoder attention [True, ...]')
        parser.add_argument('--share-input-output-embed', action='store_true',
                            help='share input and output embeddings (requires'
                                 ' --decoder-out-embed-dim and --decoder-embed-dim'
                                 ' to be equal)')

    @classmethod
    def build_model(cls, args, task):
        """Build a new model instance."""
        # make sure that all args are properly defaulted (in case there are any new ones)
        base_architecture(args)

        encoder_embed_dict = None
        if args.encoder_embed_path:
            encoder_embed_dict = utils.parse_embedding(args.encoder_embed_path)
            utils.print_embed_overlap(encoder_embed_dict, task.source_dictionary)

        decoder_embed_dict = None
        if args.decoder_embed_path:
            decoder_embed_dict = utils.parse_embedding(args.decoder_embed_path)
            utils.print_embed_overlap(decoder_embed_dict, task.target_dictionary)

        encoder = FConvEncoder(
            dictionary=task.source_dictionary,
            embed_dim=args.encoder_embed_dim,
            embed_dict=encoder_embed_dict,
            convolutions=eval(args.encoder_layers),
            dropout=args.dropout,
            max_positions=args.max_source_positions,
        )
        decoder = FConvDecoder(
            dictionary=task.target_dictionary,
            embed_dim=args.decoder_embed_dim,
            embed_dict=decoder_embed_dict,
            convolutions=eval(args.decoder_layers),
            out_embed_dim=args.decoder_out_embed_dim,
            attention=eval(args.decoder_attention),
            dropout=args.dropout,
            max_positions=args.max_target_positions,
            share_embed=args.share_input_output_embed,
        )
        return FConvModel(encoder, decoder)


@register_model('fconv_context')
class FConvContextModel(FairseqContextModel):

    def __init__(self, encoder, decoder):
        super().__init__(encoder, decoder)
        self.encoder.set_num_attention_layers(sum(layer is not None for layer in decoder.attention))

    @staticmethod
    def add_args(parser):
        """Add model-specific arguments to the parser."""
        parser.add_argument('--dropout', type=float, metavar='D',
                            help='dropout probability')
        parser.add_argument('--encoder-embed-dim', type=int, metavar='N',
                            help='encoder embedding dimension')
        parser.add_argument('--encoder-embed-path', type=str, metavar='STR',
                            help='path to pre-trained encoder embedding')
        parser.add_argument('--encoder-layers', type=str, metavar='EXPR',
                            help='encoder layers [(dim, kernel_size), ...]')
        parser.add_argument('--decoder-embed-dim', type=int, metavar='N',
                            help='decoder embedding dimension')
        parser.add_argument('--decoder-embed-path', type=str, metavar='STR',
                            help='path to pre-trained decoder embedding')
        parser.add_argument('--decoder-layers', type=str, metavar='EXPR',
                            help='decoder layers [(dim, kernel_size), ...]')
        parser.add_argument('--decoder-out-embed-dim', type=int, metavar='N',
                            help='decoder output embedding dimension')
        parser.add_argument('--decoder-attention', type=str, metavar='EXPR',
                            help='decoder attention [True, ...]')
        parser.add_argument('--share-input-output-embed', action='store_true',
                            help='share input and output embeddings (requires'
                                 ' --decoder-out-embed-dim and --decoder-embed-dim'
                                 ' to be equal)')

    @classmethod
    def build_model(cls, args, task):
        base_architecture(args)

        encoder_embed_dict = None
        if args.encoder_embed_path:
            encoder_embed_dict = utils.parse_embedding(args.encoder_embed_path)
            utils.print_embed_overlap(encoder_embed_dict, task.source_dictionary)

        decoder_embed_dict = None
        if args.decoder_embed_path:
            decoder_embed_dict = utils.parse_embedding(args.decoder_embed_path)
            utils.print_embed_overlap(decoder_embed_dict, task.target_dictionary)

        encoder = FConvContextEncoder(
            dictionary=task.source_dictionary,
            embed_dim=args.encoder_embed_dim,
            embed_dict=encoder_embed_dict,
            convolutions=eval(args.encoder_layers),
            dropout=args.dropout,
            max_positions=args.max_source_positions,
        )
        decoder = FConvDecoder(
            dictionary=task.target_dictionary,
            embed_dim=args.decoder_embed_dim,
            embed_dict=decoder_embed_dict,
            convolutions=eval(args.decoder_layers),
            out_embed_dim=args.decoder_out_embed_dim,
            attention=eval(args.decoder_attention),
            dropout=args.dropout,
            max_positions=args.max_target_positions,
            share_embed=args.share_input_output_embed,
            use_context=True
        )
        return FConvContextModel(encoder, decoder)


@register_model('fconv_multicontext')
class FConvMultiContextModel(FairseqMultiContextModel):

    def __init__(self, encoder, decoder):
        super().__init__(encoder, decoder)
        self.encoder.set_num_attention_layers(sum(layer is not None for layer in decoder.attention))

    @staticmethod
    def add_args(parser):
        """Add model-specific arguments to the parser."""
        parser.add_argument('--dropout', type=float, metavar='D',
                            help='dropout probability')
        parser.add_argument('--encoder-embed-dim', type=int, metavar='N',
                            help='encoder embedding dimension')
        parser.add_argument('--encoder-embed-path', type=str, metavar='STR',
                            help='path to pre-trained encoder embedding')
        parser.add_argument('--encoder-layers', type=str, metavar='EXPR',
                            help='encoder layers [(dim, kernel_size), ...]')
        parser.add_argument('--decoder-embed-dim', type=int, metavar='N',
                            help='decoder embedding dimension')
        parser.add_argument('--decoder-embed-path', type=str, metavar='STR',
                            help='path to pre-trained decoder embedding')
        parser.add_argument('--decoder-layers', type=str, metavar='EXPR',
                            help='decoder layers [(dim, kernel_size), ...]')
        parser.add_argument('--decoder-out-embed-dim', type=int, metavar='N',
                            help='decoder output embedding dimension')
        parser.add_argument('--decoder-attention', type=str, metavar='EXPR',
                            help='decoder attention [True, ...]')
        parser.add_argument('--share-input-output-embed', action='store_true',
                            help='share input and output embeddings (requires'
                                 ' --decoder-out-embed-dim and --decoder-embed-dim'
                                 ' to be equal)')
        parser.add_argument('--adaptive-softmax-cutoff', metavar='EXPR',
                            help='comma separated list of adaptive softmax cutoff points. '
                            'Must be used with adaptive_loss criterion')
        parser.add_argument('--adaptive-softmax-dropout', type=float, metavar='D',
                            help='sets adaptive softmax dropout for the tail projections')
        parser.add_argument('--max-leaf-positions', type=int, default=128,
                            help='max tokens in a single leaf node')
        parser.add_argument('--max-path-positions', type=int, default=128,
                            help='max nodes in a single path')


    @classmethod
    def build_model(cls, args, task):
        base_architecture(args)

        encoder_embed_dict = None
        if args.encoder_embed_path:
            encoder_embed_dict = utils.parse_embedding(args.encoder_embed_path)
            utils.print_embed_overlap(encoder_embed_dict, task.source_dictionary)

        decoder_embed_dict = None
        if args.decoder_embed_path:
            decoder_embed_dict = utils.parse_embedding(args.decoder_embed_path)
            utils.print_embed_overlap(decoder_embed_dict, task.target_dictionary)

        encoder = FConvMultiContextEncoder(
            dictionary=[task.source_dictionary, task.leaf_dictionary, task.path_dictionary],
            embed_dim=args.encoder_embed_dim,
            embed_dict=encoder_embed_dict,
            convolutions=eval(args.encoder_layers),
            dropout=args.dropout,
            max_positions=args.max_source_positions,
            max_leaf_positions=args.max_leaf_positions,
            max_path_positions=args.max_path_positions,
        )
        decoder = FConvDecoder(
            dictionary=task.target_dictionary,
            embed_dim=args.decoder_embed_dim,
            embed_dict=decoder_embed_dict,
            convolutions=eval(args.decoder_layers),
            out_embed_dim=args.decoder_out_embed_dim,
            attention=eval(args.decoder_attention),
            dropout=args.dropout,
            max_positions=args.max_target_positions,
            share_embed=args.share_input_output_embed,
            positional_embeddings=True,
            adaptive_softmax_cutoff=(
                options.eval_str_list(args.adaptive_softmax_cutoff, type=int)
                    if args.criterion == 'adaptive_loss' else None
            ),
            adaptive_softmax_dropout=args.adaptive_softmax_dropout,
        )
        return FConvMultiContextModel(encoder, decoder)


@register_model('fconv_lm')
class FConvLanguageModel(FairseqLanguageModel):
    def __init__(self, decoder):
        super().__init__(decoder)

    @staticmethod
    def add_args(parser):
        """Add model-specific arguments to the parser."""
        parser.add_argument('--dropout', type=float, metavar='D',
                            help='dropout probability')
        parser.add_argument('--decoder-embed-dim', type=int, metavar='N',
                            help='decoder embedding dimension')
        parser.add_argument('--decoder-layers', type=str, metavar='EXPR',
                            help='decoder layers [(dim, kernel_size), ...]')
        parser.add_argument('--decoder-out-embed-dim', type=int, metavar='N',
                            help='decoder output embedding dimension')
        parser.add_argument('--adaptive-softmax-cutoff', metavar='EXPR',
                            help='comma separated list of adaptive softmax cutoff points. '
                                 'Must be used with adaptive_loss criterion')
        parser.add_argument('--adaptive-softmax-dropout', type=float, metavar='D',
                            help='sets adaptive softmax dropout for the tail projections')
        parser.add_argument('--decoder-attention', type=str, metavar='EXPR',
                            help='decoder attention [True, ...]')

    @classmethod
    def build_model(cls, args, task):
        """Build a new model instance."""
        # make sure all arguments are present in older models
        base_lm_architecture(args)

        if hasattr(args, 'max_target_positions'):
            args.tokens_per_sample = args.max_target_positions

        decoder = FConvDecoder(
            dictionary=task.target_dictionary,
            embed_dim=args.decoder_embed_dim,
            convolutions=eval(args.decoder_layers),
            out_embed_dim=args.decoder_embed_dim,
            attention=eval(args.decoder_attention),
            dropout=args.dropout,
            max_positions=args.tokens_per_sample,
            share_embed=False,
            positional_embeddings=False,
            adaptive_softmax_cutoff=(
                options.eval_str_list(args.adaptive_softmax_cutoff, type=int)
                if args.criterion == 'adaptive_loss' else None
            ),
            adaptive_softmax_dropout=args.adaptive_softmax_dropout,
        )
        return FConvLanguageModel(decoder)


class FConvEncoder(FairseqEncoder):
    """
    Convolutional encoder consisting of `len(convolutions)` layers.

    Args:
        dictionary (~fairseq.data.Dictionary): encoding dictionary
        embed_dim (int, optional): embedding dimension
        embed_dict (str, optional): filename from which to load pre-trained
            embeddings
        max_positions (int, optional): maximum supported input sequence length
        convolutions (list, optional): the convolutional layer structure. Each
            list item `i` corresponds to convolutional layer `i`. Layers are
            given as ``(out_channels, kernel_width, [residual])``. Residual
            connections are added between layers when ``residual=1`` (which is
            the default behavior).
        dropout (float, optional): dropout to be applied before each conv layer
        normalization_constant (float, optional): multiplies the result of the
            residual block by sqrt(value)
        left_pad (bool, optional): whether the input is left-padded. Default:
            ``True``
    """

    def __init__(
            self, dictionary, embed_dim=512, embed_dict=None, max_positions=1024,
            convolutions=((512, 3),) * 20, dropout=0.1, left_pad=True,
    ):
        super().__init__(dictionary)
        self.dropout = dropout
        self.left_pad = left_pad
        self.num_attention_layers = None

        num_embeddings = len(dictionary)
        self.padding_idx = dictionary.pad()
        self.embed_tokens = Embedding(num_embeddings, embed_dim, self.padding_idx)
        if embed_dict:
            self.embed_tokens = utils.load_embedding(embed_dict, self.dictionary, self.embed_tokens)

        self.embed_positions = PositionalEmbedding(
            max_positions,
            embed_dim,
            self.padding_idx,
            left_pad=self.left_pad,
        )

        convolutions = extend_conv_spec(convolutions)
        in_channels = convolutions[0][0]
        self.fc1 = Linear(embed_dim, in_channels, dropout=dropout)
        self.projections = nn.ModuleList()
        self.convolutions = nn.ModuleList()
        self.residuals = []

        layer_in_channels = [in_channels]
        for i, (out_channels, kernel_size, residual) in enumerate(convolutions):
            if residual == 0:
                residual_dim = out_channels
            else:
                residual_dim = layer_in_channels[-residual]
            self.projections.append(Linear(residual_dim, out_channels)
                                    if residual_dim != out_channels else None)
            if kernel_size % 2 == 1:
                padding = kernel_size // 2
            else:
                padding = 0
            self.convolutions.append(
                ConvTBC(in_channels, out_channels * 2, kernel_size,
                        dropout=dropout, padding=padding)
            )
            self.residuals.append(residual)
            in_channels = out_channels
            layer_in_channels.append(out_channels)
        self.fc2 = Linear(in_channels, embed_dim)

    def forward(self, src_tokens, src_lengths):
        """
        Args:
            src_tokens (LongTensor): tokens in the source language of shape
                `(batch, src_len)`
            src_lengths (LongTensor): lengths of each source sentence of shape
                `(batch)`

        Returns:
            dict:
                - **encoder_out** (tuple): a tuple with two elements, where the
                  first element is the last encoder layer's output and the
                  second element is the same quantity summed with the input
                  embedding (used for attention). The shape of both tensors is
                  `(batch, src_len, embed_dim)`.
                - **encoder_padding_mask** (ByteTensor): the positions of
                  padding elements of shape `(batch, src_len)`
        """
        # embed tokens and positions
        m1 = self.embed_tokens(src_tokens)
        m2 = self.embed_positions(src_tokens)
        x = m1+m2
        x = F.dropout(x, p=self.dropout, training=self.training)
        input_embedding = x

        # project to size of convolution
        x = self.fc1(x)

        # used to mask padding in input
        encoder_padding_mask = src_tokens.eq(self.padding_idx).t()  # -> T x B
        if not encoder_padding_mask.any():
            encoder_padding_mask = None

        # B x T x C -> T x B x C
        x = x.transpose(0, 1)

        residuals = [x]
        # temporal convolutions
        for proj, conv, res_layer in zip(self.projections, self.convolutions, self.residuals):
            if res_layer > 0:
                residual = residuals[-res_layer]
                residual = residual if proj is None else proj(residual)
            else:
                residual = None

            if encoder_padding_mask is not None:
                x = x.masked_fill(encoder_padding_mask.unsqueeze(-1), 0)

            x = F.dropout(x, p=self.dropout, training=self.training)
            if conv.kernel_size[0] % 2 == 1:
                # padding is implicit in the conv
                x = conv(x)
            else:
                padding_l = (conv.kernel_size[0] - 1) // 2
                padding_r = conv.kernel_size[0] // 2
                x = F.pad(x, (0, 0, 0, 0, padding_l, padding_r))
                x = conv(x)
            x = F.glu(x, dim=2)

            if residual is not None:
                x = (x + residual) * math.sqrt(0.5)
            residuals.append(x)

        # T x B x C -> B x T x C
        x = x.transpose(1, 0)

        # project back to size of embedding
        x = self.fc2(x)

        if encoder_padding_mask is not None:
            encoder_padding_mask = encoder_padding_mask.t()  # -> B x T
            x = x.masked_fill(encoder_padding_mask.unsqueeze(-1), 0)

        # scale gradients (this only affects backward, not forward)
        x = GradMultiply.apply(x, 1.0 / (2.0 * self.num_attention_layers))

        # add output to input embedding for attention
        y = (x + input_embedding) * math.sqrt(0.5)

        return {
            'encoder_out': (x, y),
            'encoder_padding_mask': encoder_padding_mask,  # B x T
        }

    def reorder_encoder_out(self, encoder_out, new_order):
        if encoder_out['encoder_out'] is not None:
            encoder_out['encoder_out'] = (
                encoder_out['encoder_out'][0].index_select(0, new_order),
                encoder_out['encoder_out'][1].index_select(0, new_order),
            )
        if encoder_out['encoder_padding_mask'] is not None:
            encoder_out['encoder_padding_mask'] = \
                encoder_out['encoder_padding_mask'].index_select(0, new_order)
        return encoder_out

    def max_positions(self):
        """Maximum input length supported by the encoder."""
        return self.embed_positions.max_positions()


class FConvContextEncoder(FairseqEncoder):

    def __init__(
            self, dictionary, embed_dim=512, embed_dict=None, max_positions=1024,
            convolutions=((512, 3),) * 20, dropout=0.1, left_pad=True,
    ):
        super(FConvContextEncoder,self).__init__(dictionary)
        self.input_encoder = FConvEncoder(dictionary,embed_dim,embed_dict,max_positions,convolutions,dropout,left_pad)
        self.context_encoder = FConvEncoder(dictionary,embed_dim,embed_dict,max_positions,convolutions,dropout,left_pad)

    def set_num_attention_layers(self, num_attention_layers):
        self.input_encoder.num_attention_layers = num_attention_layers
        self.context_encoder.num_attention_layers = num_attention_layers

    def forward(self, src_tokens, src_lengths, ctx_tokens, ctx_lengths):
        src_output = self.input_encoder.forward(src_tokens,src_lengths)
        ctx_output = self.context_encoder.forward(src_tokens,src_lengths)
        if src_output['encoder_padding_mask'] is None or ctx_output['encoder_padding_mask'] is None:
            encoder_padding_mask = None
        else:
            encoder_padding_mask = src_output['encoder_padding_mask']*ctx_output['encoder_padding_mask']
        return {
          'encoder_out': (torch.cat([src_output['encoder_out'][0],ctx_output['encoder_out'][0]],2),
                          torch.cat([src_output['encoder_out'][1],ctx_output['encoder_out'][1]],2)),
          'encoder_padding_mask': encoder_padding_mask
        }

    def reorder_encoder_out(self, encoder_out, new_order):
        if encoder_out['encoder_out'] is not None:
            encoder_out['encoder_out'] = (
                encoder_out['encoder_out'][0].index_select(0, new_order),
                encoder_out['encoder_out'][1].index_select(0, new_order),
            )
        if encoder_out['encoder_padding_mask'] is not None:
            encoder_out['encoder_padding_mask'] = \
                encoder_out['encoder_padding_mask'].index_select(0, new_order)
        return encoder_out

    def max_positions(self):
        return min(self.input_encoder.max_positions(),self.context_encoder.max_positions())


class FConvMultiContextEncoder(FairseqEncoder):

    def __init__(
            self, dictionary, embed_dim=256, embed_dict=None, max_positions=1024,
            max_leaf_positions=128, max_path_positions=128,
            convolutions=((512, 3),) * 20, dropout=0.1, left_pad=True,
    ):
        super(FConvMultiContextEncoder,self).__init__(dictionary[0])
        self.source_dictionary, self.leaf_dictionary, self.path_dictionary = dictionary
        self.input_encoder = FConvEncoder(self.source_dictionary,embed_dim,embed_dict,max_positions,convolutions,dropout,left_pad)
        #self.context_encoder = self.input_encoder
        self.context_encoder = Code2SeqEncoder(self.leaf_dictionary,self.path_dictionary,embed_dim,embed_dict,max_positions,max_leaf_positions,max_path_positions,dropout,left_pad)
        self.embed_dim = embed_dim

    def set_num_attention_layers(self, num_attention_layers):
        self.input_encoder.num_attention_layers = num_attention_layers
        self.context_encoder.num_attention_layers = num_attention_layers

    def forward(self, src_tokens, src_lengths, start_leaf_tokens, start_leaf_lengths, end_leaf_tokens, end_leaf_lengths, path_tokens, path_lengths):
        src_output = self.input_encoder.forward(src_tokens,src_lengths)
        ctx_output = self.context_encoder.forward(start_leaf_tokens,start_leaf_lengths,end_leaf_tokens,end_leaf_lengths,path_tokens,path_lengths)
        batch_size = src_tokens.size()[0]
        embed_dim = src_output['encoder_out'][0].size()[2]
        if src_output['encoder_padding_mask'] is None:
            encoder_padding_mask = None
        else:
            encoder_padding_mask = torch.cat((src_output['encoder_padding_mask'], torch.zeros(batch_size, 1).cuda().byte()), 1)
        return {
          'encoder_out': (torch.cat([src_output['encoder_out'][0],ctx_output['encoder_out'].view((batch_size, 1, embed_dim))],1),
                          torch.cat([src_output['encoder_out'][1],ctx_output['encoder_out'].view((batch_size, 1, embed_dim))],1)),
          'encoder_padding_mask': encoder_padding_mask
        }

    def reorder_encoder_out(self, encoder_out, new_order):
        if encoder_out['encoder_out'] is not None:
            encoder_out['encoder_out'] = (
                encoder_out['encoder_out'][0].index_select(0, new_order),
                encoder_out['encoder_out'][1].index_select(0, new_order),
            )
        if encoder_out['encoder_padding_mask'] is not None:
            encoder_out['encoder_padding_mask'] = \
                encoder_out['encoder_padding_mask'].index_select(0, new_order)
        return encoder_out

    def max_positions(self):
        return min(self.input_encoder.max_positions(),self.context_encoder.max_positions())


class Code2SeqEncoder(FairseqEncoder):
    def __init__(
        self, leaf_dictionary, path_dictionary, embed_dim=512, embed_dict=None,
        max_positions=1024, max_leaf_positions=128, max_path_positions=128, dropout=0.1, left_pad=True,
    ):
        super(Code2SeqEncoder, self).__init__(leaf_dictionary)
        self.embed_dim = embed_dim
        self.leaf_dictionary, self.path_dictionary = leaf_dictionary, path_dictionary
        self.path_bilstm = nn.LSTM(embed_dim, embed_dim, batch_first=True, bidirectional=True)
        self.leaf_embedding = Embedding(len(leaf_dictionary), embed_dim, leaf_dictionary.pad())
        self.path_embedding = Embedding(len(path_dictionary), embed_dim, path_dictionary.pad())
        self.fc = Linear(4 * embed_dim, embed_dim)
        self.tanh = nn.Tanh()
        self.max_leaf_positions = max_leaf_positions
        self.max_path_positions = max_path_positions

    def forward(self, start_leaf_tokens, start_leaf_lengths, end_leaf_tokens, end_leaf_lengths, path_tokens, path_lengths):
        default_return = {
            'encoder_out': torch.zeros((start_leaf_tokens.size()[0], self.embed_dim)).cuda(),
            'encoder_padding_mask': None,
        }
        
        leaf_split_mask = start_leaf_tokens == self.leaf_dictionary.path()
        split_inds = torch.cat((torch.tensor([0]).cuda(), torch.cumsum(leaf_split_mask.sum(1), 0)), 0).tolist()

        start_leaf_inds = torch.nonzero(leaf_split_mask)
        end_leaf_inds = torch.nonzero(end_leaf_tokens == self.leaf_dictionary.path())
        path_inds = torch.nonzero(path_tokens == self.path_dictionary.path())

        if start_leaf_inds.numel() == 0 or end_leaf_inds.numel() == 0 or path_inds.numel() == 0 or \
                not torch.equal(start_leaf_inds[:, 0], end_leaf_inds[:, 0]) or \
                not torch.equal(start_leaf_inds[:, 0], path_inds[:, 0]):
            return default_return

        start_leaf_seqs, _, start_leaf_mask = self._split_seq(start_leaf_tokens, start_leaf_lengths, start_leaf_inds, split_inds)
        end_leaf_seqs, _, end_leaf_mask = self._split_seq(end_leaf_tokens, end_leaf_lengths, end_leaf_inds, split_inds)
        path_seqs, path_lens, _ = self._split_seq(path_tokens, path_lengths, path_inds, split_inds)

        start_leaf_seqs, _, start_leaf_mask = self._truncate_seqs(self.max_leaf_positions, start_leaf_seqs, None, start_leaf_mask)
        end_leaf_seqs, _, end_leaf_mask = self._truncate_seqs(self.max_leaf_positions, end_leaf_seqs, None, end_leaf_mask)
        path_seqs, path_lens, _ = self._truncate_seqs(self.max_path_positions, path_seqs, path_lens)

        start_leaf_sums = torch.sum(self.leaf_embedding(start_leaf_seqs).masked_fill_(start_leaf_mask.unsqueeze(2), 0), dim=1)
        end_leaf_sums = torch.sum(self.leaf_embedding(end_leaf_seqs).masked_fill_(end_leaf_mask.unsqueeze(2), 0), dim=1)
        #start_leaf_sums = torch.cat([self.leaf_embedding(seq).sum(0).unsqueeze(0) for seq in start_leaf_seqs], dim=0)
        #end_leaf_sums = torch.cat([self.leaf_embedding(seq).sum(0).unsqueeze(0) for seq in end_leaf_seqs], dim=0)
        path_seqs = self.path_embedding(path_seqs)

        # sort
        path_lens, sort_order = path_lens.sort(descending=True)
        path_seqs = path_seqs.index_select(0, sort_order)

        packed_paths = nn.utils.rnn.pack_padded_sequence(path_seqs, path_lens, batch_first=True)
        _, (h_n, _) = self.path_bilstm(packed_paths)
        h_n = h_n.transpose(1, 0).contiguous().view(path_seqs.size()[0], 2 * self.embed_dim)

        # unsort
        _, sort_order = sort_order.sort()
        h_n = h_n.index_select(0, sort_order)

        z = self.tanh(self.fc(torch.cat((h_n, start_leaf_sums, end_leaf_sums), dim=1)))

        output_sums = []
        cur_max = -1
        for i in range(start_leaf_tokens.size()[0]):
            start, end = split_inds[i], split_inds[i + 1]
            if start != end:
                cur_max = end + i
                output_sums.append(torch.sum(z[(start + i):(cur_max + 1), :], 0) / (end - start))
            else:
                cur_max += 1
                output_sums.append(z[cur_max].squeeze())

        encoder_out = torch.cat([s.unsqueeze(0) for s in output_sums])

        return {
            'encoder_out': encoder_out,
            'encoder_padding_mask': None,
        }

    def _split_seq(self, tokens, lengths, splits, split_inds):
        seqs = []
        seq_lengths = []
        max_length = tokens.size()[1]
        for i in range(tokens.size()[0]):
            sentence_splits = splits[split_inds[i]:split_inds[i + 1], 1]
            #subsplit = torch.cat((torch.tensor([max_length - lengths[i] - 1]).cuda(), splits[splits[:, 0] == i, 1], torch.tensor([max_length]).cuda())) + 1
            subsplit = torch.cat((torch.tensor([max_length - lengths[i] - 1]).cuda(), sentence_splits, torch.tensor([max_length]).cuda())) + 1
            split_lengths = subsplit[1:] - subsplit[:-1] - 1
            starts, ends = subsplit[:-1].tolist(), (subsplit[:-1] + split_lengths).tolist()
            seqs.extend(tokens[i, start:end] for start, end in zip(starts, ends))
            seq_lengths.append(split_lengths)
        seq_lengths = torch.cat(seq_lengths)
        padded = nn.utils.rnn.pad_sequence(seqs, batch_first=True, padding_value=self.leaf_dictionary.pad())
        return (padded, seq_lengths, padded != self.leaf_dictionary.pad())

    def _truncate_seqs(self, max_length, seqs, seq_lens=None, seq_masks=None):
        if seqs.size()[1] <= max_length:
            return seqs, seq_lens, seq_masks
        print('Warning: Truncated sequence of shape {}'.format(tuple(seqs.size())))
        return (
            seqs[:, :max_length], 
            None if seq_lens is None else torch.clamp(seq_lens, 0, max_length),
            None if seq_masks is None else seq_masks[:, :max_length]
        )

    def reorder_encoder_out(self, encoder_out, new_order):
        if encoder_out['encoder_out'] is not None:
            encoder_out['encoder_out'] = (
                encoder_out['encoder_out'][0].index_select(0, new_order),
                encoder_out['encoder_out'][1].index_select(0, new_order),
            )
        if encoder_out['encoder_padding_mask'] is not None:
            encoder_out['encoder_padding_mask'] = \
                encoder_out['encoder_padding_mask'].index_select(0, new_order)
        return encoder_out


class AttentionLayer(nn.Module):
    def __init__(self, conv_channels, embed_dim, bmm=None, use_context=False):
        super().__init__()
        # projects from output of convolution to embedding dimension
        self.in_projection = Linear(conv_channels, embed_dim)
        # projects from embedding dimension to convolution size
        self.out_projection = Linear(embed_dim, conv_channels)

        if use_context:
            self.double_projection = Linear(embed_dim,2*embed_dim)
            self.half_projection = Linear(2*embed_dim,embed_dim)

        self.bmm = bmm if bmm is not None else torch.bmm
        self.use_context = use_context

    def forward(self, x, target_embedding, encoder_out, encoder_padding_mask):
        residual = x

        # attention
        x = (self.in_projection(x) + target_embedding) * math.sqrt(0.5)
        if self.use_context:
             x = self.double_projection(x)
        x = self.bmm(x, encoder_out[0])

        # don't attend over padding
        if encoder_padding_mask is not None:
            x = x.float().masked_fill(
                encoder_padding_mask.unsqueeze(1),
                float('-inf')
            ).type_as(x)  # FP16 support: cast to float and back

        # softmax over last dim
        sz = x.size()
        x = F.softmax(x.view(sz[0] * sz[1], sz[2]), dim=1)
        x = x.view(sz)
        attn_scores = x

        x = self.bmm(x, encoder_out[1])

        # scale attention output (respecting potentially different lengths)
        s = encoder_out[1].size(1)
        if encoder_padding_mask is None:
            x = x * (s * math.sqrt(1.0 / s))
        else:
            s = s - encoder_padding_mask.type_as(x).sum(dim=1, keepdim=True)  # exclude padding
            s = s.unsqueeze(-1)
            x = x * (s * s.rsqrt())

        # project back
        if self.use_context:
            x = self.half_projection(x)
        x = (self.out_projection(x) + residual) * math.sqrt(0.5)
        return x, attn_scores

    def make_generation_fast_(self, beamable_mm_beam_size=None, **kwargs):
        """Replace torch.bmm with BeamableMM."""
        if beamable_mm_beam_size is not None:
            del self.bmm
            self.add_module('bmm', BeamableMM(beamable_mm_beam_size))


class FConvDecoder(FairseqIncrementalDecoder):
    """Convolutional decoder"""

    def __init__(
            self, dictionary, embed_dim=512, embed_dict=None, out_embed_dim=256,
            max_positions=1024, convolutions=((512, 3),) * 20, attention=True,
            dropout=0.1, share_embed=False, positional_embeddings=True,
            adaptive_softmax_cutoff=None, adaptive_softmax_dropout=0,
            left_pad=False, use_context=False,
    ):
        super().__init__(dictionary)
        self.register_buffer('version', torch.Tensor([2]))
        self.dropout = dropout
        self.left_pad = left_pad
        self.need_attn = True

        convolutions = extend_conv_spec(convolutions)
        in_channels = convolutions[0][0]
        if isinstance(attention, bool):
            # expand True into [True, True, ...] and do the same with False
            attention = [attention] * len(convolutions)
        if not isinstance(attention, list) or len(attention) != len(convolutions):
            raise ValueError('Attention is expected to be a list of booleans of '
                             'length equal to the number of layers.')

        num_embeddings = len(dictionary)
        padding_idx = dictionary.pad()
        self.embed_tokens = Embedding(num_embeddings, embed_dim, padding_idx)
        if embed_dict:
            self.embed_tokens = utils.load_embedding(embed_dict, self.dictionary, self.embed_tokens)

        self.embed_positions = PositionalEmbedding(
            max_positions,
            embed_dim,
            padding_idx,
            left_pad=self.left_pad,
        ) if positional_embeddings else None

        self.fc1 = Linear(embed_dim, in_channels, dropout=dropout)
        self.projections = nn.ModuleList()
        self.convolutions = nn.ModuleList()
        self.attention = nn.ModuleList()
        self.residuals = []

        layer_in_channels = [in_channels]
        for i, (out_channels, kernel_size, residual) in enumerate(convolutions):
            if residual == 0:
                residual_dim = out_channels
            else:
                residual_dim = layer_in_channels[-residual]
            self.projections.append(Linear(residual_dim, out_channels)
                                    if residual_dim != out_channels else None)
            self.convolutions.append(
                LinearizedConv1d(in_channels, out_channels * 2, kernel_size,
                                 padding=(kernel_size - 1), dropout=dropout)
            )
            self.attention.append(AttentionLayer(out_channels, embed_dim, None, use_context)
                                  if attention[i] else None)
            self.residuals.append(residual)
            in_channels = out_channels
            layer_in_channels.append(out_channels)

        self.adaptive_softmax = None
        self.fc2 = self.fc3 = None

        if adaptive_softmax_cutoff is not None:
            assert not share_embed
            self.adaptive_softmax = AdaptiveSoftmax(num_embeddings, in_channels, adaptive_softmax_cutoff,
                                                    dropout=adaptive_softmax_dropout)
        else:
            self.fc2 = Linear(in_channels, out_embed_dim)
            if share_embed:
                assert out_embed_dim == embed_dim, \
                    "Shared embed weights implies same dimensions " \
                    " out_embed_dim={} vs embed_dim={}".format(out_embed_dim, embed_dim)
                self.fc3 = nn.Linear(out_embed_dim, num_embeddings)
                self.fc3.weight = self.embed_tokens.weight
            else:
                self.fc3 = Linear(out_embed_dim, num_embeddings, dropout=dropout)

    def forward(self, prev_output_tokens, encoder_out_dict=None, incremental_state=None):
        if encoder_out_dict is not None:
            encoder_out = encoder_out_dict['encoder_out']
            encoder_padding_mask = encoder_out_dict['encoder_padding_mask']

            # split and transpose encoder outputs
            encoder_a, encoder_b = self._split_encoder_out(encoder_out, incremental_state)
        
        if self.embed_positions is not None:
            pos_embed = self.embed_positions(prev_output_tokens, incremental_state)
        else:
            pos_embed = 0

        if incremental_state is not None:
            prev_output_tokens = prev_output_tokens[:, -1:]
        x = self._embed_tokens(prev_output_tokens, incremental_state)

        # embed tokens and combine with positional embeddings
        x += pos_embed
        x = F.dropout(x, p=self.dropout, training=self.training)
        target_embedding = x

        # project to size of convolution
        x = self.fc1(x)

        # B x T x C -> T x B x C
        x = self._transpose_if_training(x, incremental_state)

        # temporal convolutions
        avg_attn_scores = None
        num_attn_layers = len(self.attention)
        residuals = [x]
        for proj, conv, attention, res_layer in zip(self.projections, self.convolutions, self.attention,
                                                    self.residuals):
            if res_layer > 0:
                residual = residuals[-res_layer]
                residual = residual if proj is None else proj(residual)
            else:
                residual = None

            x = F.dropout(x, p=self.dropout, training=self.training)
            x = conv(x, incremental_state)
            x = F.glu(x, dim=2)

            # attention
            if attention is not None:
                x = self._transpose_if_training(x, incremental_state)

                x, attn_scores = attention(x, target_embedding, (encoder_a, encoder_b), encoder_padding_mask)

                if not self.training and self.need_attn:
                    attn_scores = attn_scores / num_attn_layers
                    if avg_attn_scores is None:
                        avg_attn_scores = attn_scores
                    else:
                        avg_attn_scores.add_(attn_scores)

                x = self._transpose_if_training(x, incremental_state)

            # residual
            if residual is not None:
                x = (x + residual) * math.sqrt(0.5)
            residuals.append(x)

        # T x B x C -> B x T x C
        x = self._transpose_if_training(x, incremental_state)

        # project back to size of vocabulary if not using adaptive softmax
        if self.fc2 is not None and self.fc3 is not None:
            x = self.fc2(x)
            x = F.dropout(x, p=self.dropout, training=self.training)
            x = self.fc3(x)

        return x, avg_attn_scores

    def reorder_incremental_state(self, incremental_state, new_order):
        super().reorder_incremental_state(incremental_state, new_order)
        encoder_out = utils.get_incremental_state(self, incremental_state, 'encoder_out')
        if encoder_out is not None:
            encoder_out = tuple(eo.index_select(0, new_order) for eo in encoder_out)
            utils.set_incremental_state(self, incremental_state, 'encoder_out', encoder_out)

    def max_positions(self):
        """Maximum output length supported by the decoder."""
        return self.embed_positions.max_positions() if self.embed_positions is not None else float('inf')

    def upgrade_state_dict(self, state_dict):
        if utils.item(state_dict.get('decoder.version', torch.Tensor([1]))[0]) < 2:
            # old models use incorrect weight norm dimension
            for i, conv in enumerate(self.convolutions):
                # reconfigure weight norm
                nn.utils.remove_weight_norm(conv)
                self.convolutions[i] = nn.utils.weight_norm(conv, dim=0)
            state_dict['decoder.version'] = torch.Tensor([1])
        return state_dict

    def make_generation_fast_(self, need_attn=False, **kwargs):
        self.need_attn = need_attn

    def _embed_tokens(self, tokens, incremental_state):
        if incremental_state is not None:
            # keep only the last token for incremental forward pass
            tokens = tokens[:, -1:]
        return self.embed_tokens(tokens)

    def _split_encoder_out(self, encoder_out, incremental_state):
        """Split and transpose encoder outputs.

        This is cached when doing incremental inference.
        """
        cached_result = utils.get_incremental_state(self, incremental_state, 'encoder_out')
        if cached_result is not None:
            return cached_result

        # transpose only once to speed up attention layers
        encoder_a, encoder_b = encoder_out
        encoder_a = encoder_a.transpose(1, 2).contiguous()
        result = (encoder_a, encoder_b)

        if incremental_state is not None:
            utils.set_incremental_state(self, incremental_state, 'encoder_out', result)
        return result

    def _transpose_if_training(self, x, incremental_state):
        if incremental_state is None:
            x = x.transpose(0, 1)
        return x


def extend_conv_spec(convolutions):
    """
    Extends convolutional spec that is a list of tuples of 2 or 3 parameters
    (kernel size, dim size and optionally how many layers behind to look for residual)
    to default the residual propagation param if it is not specified
    """
    extended = []
    for spec in convolutions:
        if len(spec) == 3:
            extended.append(spec)
        elif len(spec) == 2:
            extended.append(spec + (1,))
        else:
            raise Exception('invalid number of parameters in convolution spec ' + str(spec) + '. expected 2 or 3')
    return tuple(extended)


def Embedding(num_embeddings, embedding_dim, padding_idx):
    m = nn.Embedding(num_embeddings, embedding_dim, padding_idx=padding_idx)
    nn.init.normal_(m.weight, 0, 0.1)
    nn.init.constant_(m.weight[padding_idx], 0)
    return m


def PositionalEmbedding(num_embeddings, embedding_dim, padding_idx, left_pad):
    m = LearnedPositionalEmbedding(num_embeddings, embedding_dim, padding_idx, left_pad)
    nn.init.normal_(m.weight, 0, 0.1)
    nn.init.constant_(m.weight[padding_idx], 0)
    return m


def Linear(in_features, out_features, dropout=0):
    """Weight-normalized Linear layer (input: N x T x C)"""
    m = nn.Linear(in_features, out_features)
    nn.init.normal_(m.weight, mean=0, std=math.sqrt((1 - dropout) / in_features))
    nn.init.constant_(m.bias, 0)
    return nn.utils.weight_norm(m)


def LinearizedConv1d(in_channels, out_channels, kernel_size, dropout=0, **kwargs):
    """Weight-normalized Conv1d layer optimized for decoding"""
    m = LinearizedConvolution(in_channels, out_channels, kernel_size, **kwargs)
    std = math.sqrt((4 * (1.0 - dropout)) / (m.kernel_size[0] * in_channels))
    nn.init.normal_(m.weight, mean=0, std=std)
    nn.init.constant_(m.bias, 0)
    return nn.utils.weight_norm(m, dim=2)


def ConvTBC(in_channels, out_channels, kernel_size, dropout=0, **kwargs):
    """Weight-normalized Conv1d layer"""
    from fairseq.modules import ConvTBC
    m = ConvTBC(in_channels, out_channels, kernel_size, **kwargs)
    std = math.sqrt((4 * (1.0 - dropout)) / (m.kernel_size[0] * in_channels))
    nn.init.normal_(m.weight, mean=0, std=std)
    nn.init.constant_(m.bias, 0)
    return nn.utils.weight_norm(m, dim=2)


@register_model_architecture('fconv_lm', 'fconv_lm')
def base_lm_architecture(args):
    args.dropout = getattr(args, 'dropout', 0.1)
    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 128)
    args.decoder_layers = getattr(args, 'decoder_layers', '[(1268, 4)] * 13')
    args.decoder_attention = getattr(args, 'decoder_attention', 'False')
    args.adaptive_softmax_cutoff = getattr(args, 'adaptive_softmax_cutoff', None)
    args.adaptive_softmax_dropout = getattr(args, 'adaptive_softmax_dropout', 0)


@register_model_architecture('fconv_lm', 'fconv_lm_dauphin_wikitext103')
def fconv_lm_dauphin_wikitext103(args):
    layers = '[(850, 6)] * 3'
    layers += ' + [(850, 1)] * 1'
    layers += ' + [(850, 5)] * 4'
    layers += ' + [(850, 1)] * 1'
    layers += ' + [(850, 4)] * 3'
    layers += ' + [(1024, 4)] * 1'
    layers += ' + [(2048, 4)] * 1'
    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 280)
    args.decoder_layers = getattr(args, 'decoder_layers', layers)
    args.decoder_attention = getattr(args, 'decoder_attention', 'False')
    args.adaptive_softmax_cutoff = getattr(args, 'adaptive_softmax_cutoff', '10000,20000,200000')
    base_lm_architecture(args)


@register_model_architecture('fconv_lm', 'fconv_lm_dauphin_gbw')
def fconv_lm_dauphin_gbw(args):
    layers = '[(512, 5)]'
    layers += ' + [(128, 1, 0), (128, 5, 0), (512, 1, 3)] * 3'
    layers += ' + [(512, 1, 0), (512, 5, 0), (1024, 1, 3)] * 3'
    layers += ' + [(1024, 1, 0), (1024, 5, 0), (2048, 1, 3)] * 6'
    layers += ' + [(1024, 1, 0), (1024, 5, 0), (4096, 1, 3)]'
    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 128)
    args.decoder_layers = getattr(args, 'decoder_layers', layers)
    args.decoder_attention = getattr(args, 'decoder_attention', 'False')
    args.adaptive_softmax_cutoff = getattr(args, 'adaptive_softmax_cutoff', '10000,50000,200000')
    base_lm_architecture(args)


@register_model_architecture('fconv', 'fconv')
def base_architecture(args):
    args.dropout = getattr(args, 'dropout', 0.1)
    args.encoder_embed_dim = getattr(args, 'encoder_embed_dim', 512)
    args.encoder_embed_path = getattr(args, 'encoder_embed_path', None)
    args.encoder_layers = getattr(args, 'encoder_layers', '[(512, 3)] * 20')
    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 512)
    args.decoder_embed_path = getattr(args, 'decoder_embed_path', None)
    args.decoder_layers = getattr(args, 'decoder_layers', '[(512, 3)] * 20')
    args.decoder_out_embed_dim = getattr(args, 'decoder_out_embed_dim', 256)
    args.decoder_attention = getattr(args, 'decoder_attention', 'True')
    args.share_input_output_embed = getattr(args, 'share_input_output_embed', False)


@register_model_architecture('fconv', 'fconv_iwslt_de_en')
def fconv_iwslt_de_en(args):
    args.encoder_embed_dim = getattr(args, 'encoder_embed_dim', 256)
    args.encoder_layers = getattr(args, 'encoder_layers', '[(256, 3)] * 4')
    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 256)
    args.decoder_layers = getattr(args, 'decoder_layers', '[(256, 3)] * 3')
    args.decoder_out_embed_dim = getattr(args, 'decoder_out_embed_dim', 256)
    base_architecture(args)


@register_model_architecture('fconv', 'fconv_wmt_en_ro')
def fconv_wmt_en_ro(args):
    args.decoder_out_embed_dim = getattr(args, 'decoder_out_embed_dim', 512)
    base_architecture(args)


@register_model_architecture('fconv', 'fconv_wmt_en_de')
def fconv_wmt_en_de(args):
    convs = '[(512, 3)] * 9'  # first 9 layers have 512 units
    convs += ' + [(1024, 3)] * 4'  # next 4 layers have 1024 units
    convs += ' + [(2048, 1)] * 2'  # final 2 layers use 1x1 convolutions

    args.encoder_embed_dim = getattr(args, 'encoder_embed_dim', 768)
    args.encoder_layers = getattr(args, 'encoder_layers', convs)
    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 768)
    args.decoder_layers = getattr(args, 'decoder_layers', convs)
    args.decoder_out_embed_dim = getattr(args, 'decoder_out_embed_dim', 512)
    base_architecture(args)


@register_model_architecture('fconv', 'fconv_wmt_en_fr')
def fconv_wmt_en_fr(args):
    convs = '[(512, 3)] * 6'  # first 6 layers have 512 units
    convs += ' + [(768, 3)] * 4'  # next 4 layers have 768 units
    convs += ' + [(1024, 3)] * 3'  # next 3 layers have 1024 units
    convs += ' + [(2048, 1)] * 1'  # next 1 layer uses 1x1 convolutions
    convs += ' + [(4096, 1)] * 1'  # final 1 layer uses 1x1 convolutions

    args.encoder_embed_dim = getattr(args, 'encoder_embed_dim', 768)
    args.encoder_layers = getattr(args, 'encoder_layers', convs)
    args.decoder_embed_dim = getattr(args, 'decoder_embed_dim', 768)
    args.decoder_layers = getattr(args, 'decoder_layers', convs)
    args.decoder_out_embed_dim = getattr(args, 'decoder_out_embed_dim', 512)
    base_architecture(args)

@register_model_architecture('fconv_context','fconv_context')
def base_fconv_context(args):
    base_architecture(args)

@register_model_architecture('fconv_multicontext','fconv_multicontext')
def base_fconv_multicontext(args):
    base_architecture(args)
