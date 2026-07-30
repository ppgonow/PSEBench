# INFOCOM official-oracle distinguishability amendment (2026-07-30)

The first invocation stopped before official modules or cases were loaded
because Python 3.12 does not expose `importlib.util` through `importlib` unless
the submodule is imported explicitly. No detail, summary, or integrity output
was written, and no oracle outcome was observed.

The only code change adds `import importlib.util`. The frozen manifest, source
revision, environment construction, mutations, comparators, output schema, and
acceptance condition are unchanged. The next invocation remains the first
outcome-producing run.

The second invocation then stopped before loading any task class because
AgentDojo's `StrEnum` imports PyYAML only to register a serializer. PyYAML is
not installed for the selected Python 3.12 runtime. Again, no result file or
oracle outcome was produced. A no-op compatibility object now implements only
`SafeDumper.add_multi_representer` and `SafeRepresenter.represent_str`.
Environment inputs remain typed dictionaries, so no YAML parsing is replaced.
