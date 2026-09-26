# robotmonaco.com

## This is its own project

robotmonaco.com and robotrental.sk are two separate projects. They are not one site in two
languages and not a shared codebase, and work on one is never work on the other.

- Never change, test, deploy or send mail through robotrental.sk while working here, and never
  quote robotrental as evidence that something works here. Each site is verified on its own.
- Contact details, prices, mailboxes, hosting credentials and analytics belong to this site alone.
  Enquiries from this site go to its own mailbox; they must not land in robotrental's.
- The only tie between them is the footer credit and the `sameAs` entry in the Organization
  schema, both of which say "partner", nothing more.
- They share some design ancestry: `src/styles.css` began as a copy of robotrental's and still
  carries its header comment. That is history, not a live dependency — never edit one expecting
  the other to follow, and never sync them.

## Build and deploy

- `python3.12 build.py` writes `dist/` (Python 3.12: the templates use nested f-strings).
- Content lives in `content/en/` and `content/fr/`; a language ships only once its tree has every
  file English has.
- Pushing to `main` deploys over FTPS via GitHub Actions. `tools/deploy.py` adds and overwrites
  everywhere, and additionally deletes remote leftovers inside the directories listed in `SWEPT`.
- `.glb` models are committed, because a build machine without them silently falls back to a
  placeholder instead of the 3D stage.

## Copy

Claims have to be defensible. Say what a picture shows, credit photography that is not ours, and
do not imply an event, a client or a partnership that did not happen.
