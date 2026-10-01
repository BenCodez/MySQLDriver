# MySQLDriver

Bundles JDBC drivers for MySQL, MariaDB and PostgreSQL in a plugin for Spigot,
BungeeCord and Velocity.

## Build

Use JDK 21 and Maven 3.9:

```sh
mvn --batch-mode --no-transfer-progress -f MySQLDriver/pom.xml clean verify
```

The shaded plugin is `MySQLDriver/target/MySQLDriver.jar`. Its name and the normal
Maven build are unchanged for Jenkins and existing consumers. The release workflow
copies that exact file to a versioned filename; it does not rebuild or repackage
it in the publishing job.

## Versioned GitHub releases

Before the first release, a repository administrator should enable **Settings →
General → Releases → Enable release immutability**. See GitHub's
[immutable release setup guide](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes).
This is a repository setting, not something this workflow enables. It applies to
future published releases, so enable it before publishing. Restrict release tag
creation to trusted maintainers using the repository's chosen tag rules.

1. Choose a new stable version (`1.0`, `1.1` or `1.0.1`, for example). Update the
   version in `MySQLDriver/pom.xml`, `Resources/plugin.yml`, `Resources/bungee.yml`
   (both under `MySQLDriver/`), and the Velocity `@Plugin` annotation in
   `MySQLDriver/src/com/bencodez/mysqldriver/velocity/MySQLDriverVelocity.java`.
2. Merge the reviewed commit after the **Build and release / build** check passes.
3. On GitHub, open **Actions → Build and release → Run workflow**. Leave the
   branch set to **master**, enter the same version **without** the `v` prefix
   (for example, `1.0` for the current version), and click **Run workflow**.
   The button is available once this workflow is merged into `master`.
4. The workflow validates the branch and version, builds and verifies the actual
   shaded JAR, stages `MySQLDriver-<version>.jar` and
   `MySQLDriver-<version>.jar.sha256`, and retains that exact pair as a run artifact
   for 30 days. A separate publishing job creates `v<version>` at the exact built
   commit, uploads both files to a draft release, checks the tag again, and only
   then publishes. Watch that run finish, then find the assets under **Releases**.

No local Git commands or extra token secret are needed for the web flow. It uses
`GITHUB_TOKEN`; repository rules must permit that token to create new release
tags. It never moves an existing tag. An existing lightweight or annotated tag is
accepted only when it resolves to the exact commit built by this run.

The web flow does not change project versions for you: commit and merge all four
version updates first. The workflow checks that the Maven version, requested
version/tag and all packaged plugin descriptors agree, and that all three plugin
entry points, JDBC drivers and service providers are present. Only manual runs
from `master` and version-tag pushes can publish; ordinary PR and `master` push
builds cannot. Write permission is granted only to the publishing job.

### Alternative: push a tag

You can still create and push a new tag pointing to the reviewed commit:

```sh
git tag -a v1.0 -m "MySQLDriver 1.0" <commit>
git push origin v1.0
```

That tag push uses the same build, verification and draft-then-publish flow. Both
entry points share a per-tag concurrency group. Tags created by `GITHUB_TOKEN`
do not start another tag-push workflow, so the manual run publishes its own assets.

### Consumers

Pin the versioned release asset URL and the SHA-256 of that release together.
Avoid `latest` URLs or Jenkins `lastSuccessfulBuild` URLs when pinning a digest.
For example, after publishing `v1.0`, the asset path is
`https://github.com/BenCodez/MySQLDriver/releases/download/v1.0/MySQLDriver-1.0.jar`.
Download the matching `.jar.sha256` file and run:

```sh
sha256sum --check MySQLDriver-1.0.jar.sha256
```

### Failed runs and retries

The workflow never overwrites any existing release, including a draft. If no
release was created, use **Re-run failed jobs** on the original run to reuse the
retained build artifact and exact commit, even if `master` has advanced. If the
tag was already created, the job reuses it only when it still points to that
commit. Starting a new manual run builds the currently selected `master` commit
and will reject an existing tag for another commit. If creation/upload/publishing
failed after making a draft, inspect that draft and the run artifact first. A maintainer can finish uploading the exact
retained files and publish it, or delete only the incomplete **draft** (keep the
tag) before rerunning the failed publishing job. Do not publish a partial draft.
If the release is already published, leave it untouched; a retry deliberately
stops. Fixes require a new version and tag. Rebuilding a tag later is not guaranteed
to produce identical bytes because build dependencies include snapshots.

To run the release-script regression tests locally:

```sh
python3 -m unittest discover -s .github/tests -v
```
