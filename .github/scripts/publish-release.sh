#!/usr/bin/env bash
set -euo pipefail

: "${GH_REPO:?}" "${RELEASE_TAG:?}" "${RELEASE_COMMIT:?}"
[[ "$RELEASE_TAG" =~ ^v[0-9]+(\.[0-9]+){1,2}$ ]] || { echo 'Invalid stable release tag' >&2; exit 1; }
[[ "$RELEASE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid commit SHA' >&2; exit 1; }
cd "${1:?Release asset directory required}"
jar="MySQLDriver-${RELEASE_TAG#v}.jar"
test -s "$jar"
sha256sum --check --strict "$jar.sha256"

# Fail closed on lookup errors or any existing draft/published release. Never
# clobber assets, delete releases, move tags, or silently replace a partial draft.
existing=$(gh api --paginate "repos/$GH_REPO/releases" --jq ".[] | select(.tag_name == \"$RELEASE_TAG\") | .id")
if [[ -n "$existing" ]]; then
  echo "Release $RELEASE_TAG already exists. Inspect it; see readme.md for recovery." >&2
  exit 1
fi
check_tag() {
  local actual
  actual=$(gh api "repos/$GH_REPO/commits/refs/tags/$RELEASE_TAG" --jq .sha)
  [[ "$actual" == "$RELEASE_COMMIT" ]] || { echo 'Remote tag no longer matches the built commit' >&2; exit 1; }
}
if [[ "${CREATE_RELEASE_TAG:-false}" == true ]]; then
  # Matching refs returns an empty array for a missing tag. Do not treat an API
  # failure as absence, or confuse a prefix match (v1.0.1) with the exact tag.
  tag_ref=$(gh api "repos/$GH_REPO/git/matching-refs/tags/$RELEASE_TAG" \
    --jq ".[] | select(.ref == \"refs/tags/$RELEASE_TAG\") | .ref")
  if [[ -z "$tag_ref" ]]; then
    # POST creates only; never force-update an existing tag. If another run won
    # the race or the response was lost, accept only the same exact commit.
    if ! gh api --method POST "repos/$GH_REPO/git/refs" \
      -f "ref=refs/tags/$RELEASE_TAG" -f "sha=$RELEASE_COMMIT" >/dev/null; then
      check_tag
    fi
  fi
fi
check_tag
# --draft keeps even a partially failed upload unpublished. --verify-tag prevents
# gh from creating a tag on the default branch if the intended tag is missing.
gh release create "$RELEASE_TAG" "$jar" "$jar.sha256" \
  --repo "$GH_REPO" --verify-tag --draft \
  --title "MySQLDriver ${RELEASE_TAG#v}" \
  --notes "Built from commit $RELEASE_COMMIT. Verify the JAR with its accompanying SHA-256 checksum."
check_tag
gh release edit "$RELEASE_TAG" --repo "$GH_REPO" --draft=false
