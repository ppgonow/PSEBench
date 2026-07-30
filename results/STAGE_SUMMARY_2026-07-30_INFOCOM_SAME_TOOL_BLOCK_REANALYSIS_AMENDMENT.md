# INFOCOM same-tool block reanalysis amendment (2026-07-30)

## Timing and scope

This is a post-hoc reanalysis of the completed four-alias same-tool matrix. It
does not alter requests, responses, scenario membership, policies, or retained
rows. Raw JSONL and previously generated summaries remain unchanged.

## Motivation

The 48 workflow-specific templates per alias reuse 12 carrier/style blocks.
The existing exact block sign-flip test exposes this dependence, but the paper
also needs multiplicity-aware alias comparisons, uncertainty that resamples
whole blocks, and descriptive workflow/carrier heterogeneity.

## Added analyses

1. Holm adjustment across the four alias-specific primary attack comparisons;
2. a fixed-seed, 20,000-resample cluster bootstrap over the 12 style blocks;
3. workflow and carrier breakdowns retained as descriptive estimates;
4. a precision and detectable-discordance statement based on the fixed
   denominators.

The bootstrap and block tests are sensitivity analyses, not preregistered
primary tests. Aliases remain separate and are never pooled for inference.

## Outputs

- `analysis/same_tool_native_commit_multiplicity.csv`
- `analysis/same_tool_native_commit_cluster_bootstrap.csv`
- `analysis/same_tool_native_commit_precision.csv`

