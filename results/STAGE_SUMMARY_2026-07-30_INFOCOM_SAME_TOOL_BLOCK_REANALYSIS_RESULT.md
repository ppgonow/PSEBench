# INFOCOM same-tool block reanalysis result (2026-07-30)

Holm correction across the four alias-level attack comparisons leaves only the
Grok-4.5 condition significant. Adjusted p-values are 0.1875, 2.38e-7, 0.1875,
and 0.1875 for GPT-5.5, Grok-4.5, GPT-5.4, and GPT-5.6-sol, respectively.

A fixed-seed 20,000-resample bootstrap over the 12 carrier/style blocks gives
permissive-minus-IACG attack-rate differences and percentile intervals of:

- GPT-5.5: 10.4 percentage points [2.1, 20.8];
- Grok-4.5: 52.1 points [39.6, 62.5];
- GPT-5.4: 8.3 points [2.1, 14.6];
- GPT-5.6-sol: 10.4 points [2.1, 20.8].

The exact block sign-flip test remains the conservative inference check. Its
p-values are 0.125, 0.000977, 0.125, and 0.125. The bootstrap is reported as a
post-hoc uncertainty description, not a replacement hypothesis test.

With 48 pairs, an all-one-direction exact McNemar comparison needs at least six
discordant pairs for unadjusted p < 0.05 and eight for the worst-case four-test
familywise threshold. Under the optimistic assumption that all discordance
favors one policy, power to detect 10-, 20-, and 30-point discordance rates is
34.7%, 93.8%, and 99.9%. This explains why the three low-frequency aliases do
not support alias-specific claims.

Descriptively, permissive attacks occur in calendar 4/48, file 11/48, message
20/48, and reminder 4/48 workflow cells across aliases. Carrier totals are
message 19/64, retrieved-document 10/64, and tool-output 10/64. These totals are
not pooled for inference.

