# Temporal completion amendment v4

The frozen local-only amendment selected all 96 contaminated `date_set_check` jobs from the parent run: 24 bases x 2 proposals x 2 expressions. It reused the parent prompts, schema, model digest, and all options except `num_predict=512`. Parent protocol/raw hashes are `cf685b59b15f7af6e1e090c39107df828243515f068ebb5fe8827bc0f2953821` and `adb69773bebe5ae8b7663a107382f556039a28693e0180511c2d7feaf429f868`.

Execution completed 96/96 attempts with no API or schema errors. Reserved budget was 49,152 tokens; accounted output was 25,377 tokens over 1,580.47 seconds. The new protocol, raw log, completion record, and audit hashes are recorded in the handoff message and protocol metadata.

Against the planned denominator, 256 tokens had 32 valid and 64 schema-error rows; 512 tokens had 96 valid rows. Exact authorized/proposed extraction was 32/32 at 256 and 95/96, 96/96 at 512. Fail-closed subset approvals were 3/96 at 256 and 47/96 at 512. False approvals were 0 in both conditions; the 512 condition had one valid authorized-case false rejection. Paired transitions were 64 schema-invalid to valid, 44 false-to-approval transitions, and 49 false-to-false transitions; no new false approvals.

The audit preserves unresolved rows and does not treat errors as model denials. The append-only audit output is created once after inference; rerunning it is intentionally rejected to prevent overwrite.
