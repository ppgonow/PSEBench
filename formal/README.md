# Bounded security audits

The two scripts in this directory are dependency-free executable checks for
the bounded models stated in the paper:

```text
python3 formal/bounded_security_model.py
python3 formal/bounded_oracle_lattice.py
python3 formal/bounded_multi_principal_authority.py
```

`bounded_security_model.py` enumerates post-check mutations, receipt-field
omissions, replay, short compositions with an aggregate budget, two
commit/mutation orderings, and the indistinguishable-prefix witness for the
proposal-time safety--availability limit. It reports the unique matching
counterexample for each omitted receipt field and an explicit concurrent
aggregate-budget overflow witness. It models only the
service-local assumptions stated in the paper; it is not a provider or network
model.  `bounded_oracle_lattice.py` exhaustively enumerates a small
persistence/target/scope lattice to demonstrate oracle distinguishability.
The outputs are deterministic and are intended to be rerun from the released
artifact.

`bounded_multi_principal_authority.py` enumerates 36 cases over owner and
delegated principals, partial target/lifetime/scope grants, aggregate-budget
shrinkage, delegation revocation, and an owner conflict.  It compares a
receipt-bound current-grant check with a cached proposal-time allow.  The
matrix is a bounded conformance audit, not a model prevalence estimate.
