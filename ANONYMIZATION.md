# Anonymous Submission Notes

This public artifact snapshot is intended to support double-blind review. The
repository contents avoid paper drafts, author names, compiled PDFs,
machine-local paths, credentials, live-service tokens, and local runner
configuration.

For a double-blind submission, do not provide a URL that reveals author identity
through the account name, organization name, commit metadata, issue tracker, or
repository settings. If the conference asks for an artifact URL during review,
mirror this repository snapshot through an anonymous artifact-sharing service or
otherwise provide an anonymized archive. The post-acceptance public release can
then point to the maintained project repository.

Before sharing an artifact URL with reviewers, rerun:

```bash
scripts/sanity_check.sh
git grep -n -I -E "(sk-[A-Za-z0-9]{8,}|/Users/|OPENAI_API_KEY|ANTHROPIC_AUTH_TOKEN)" -- .
```

To create a clean zip from the committed artifact snapshot:

```bash
scripts/make_anonymous_archive.sh
```

The generated archive is written under `dist/`, which is gitignored.
