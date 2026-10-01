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
3. Create and push a new tag `v<version>` pointing to that commit, for example:
   `git tag -a v1.0 -m "MySQLDriver 1.0" <commit>` then `git push origin v1.0`.
4. The tag workflow builds and verifies the actual shaded JAR, stages
   `MySQLDriver-<version>.jar` and `MySQLDriver-<version>.jar.sha256`, and retains
   that exact pair as a run artifact for 30 days. A separate publishing job checks
   the remote tag, uploads both files to a draft release, checks the tag again,
   and only then publishes. PR and `master` builds never publish releases.

The workflow checks that the Maven version, tag and packaged plugin descriptors
agree, and that all three plugin entry points, JDBC drivers and service providers
are present. It grants write permission only to the tag-only publishing job.

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
release was created, rerun the failed publishing job to reuse the retained build
artifact. If creation/upload/publishing failed after making a draft, inspect that
draft and the run artifact first. A maintainer can finish uploading the exact
retained files and publish it, or delete only the incomplete **draft** (keep the
tag) before rerunning the failed publishing job. Do not publish a partial draft.
If the release is already published, leave it untouched; a retry deliberately
stops. Fixes require a new version and tag. Rebuilding a tag later is not guaranteed
to produce identical bytes because build dependencies include snapshots.

To run the release-script regression tests locally:

```sh
python3 -m unittest discover -s .github/tests -v
```
