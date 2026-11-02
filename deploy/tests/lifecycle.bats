#!/usr/bin/env bats
# Deploy -> verify -> promote -> rollback against real PocketBase processes.

load helpers

setup_file() { build_fixture_releases; }
setup() { setup_env; }
teardown() { teardown_env; }

@test "deploy installs a build to staging and serves it" {
  run briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  [ "$status" -eq 0 ]
  [ "$(current_build staging)" = "$BUILD_A" ]
  [ "$(served_build staging)" = "$BUILD_A" ]
  [ -f "$BRIEFER_ROOT/builds/$BUILD_A/.staged-ok" ]
}

@test "deploy rejects a bundle whose checksum does not match" {
  run briefer-deploy "$BUILD_A" "$(printf '0%.0s' {1..64})"
  [ "$status" -ne 0 ]
  [[ "$output" == *"checksum"* ]]
  [ ! -e "$BRIEFER_ROOT/envs/staging/current" ]
  [ ! -d "$BRIEFER_ROOT/builds/$BUILD_A" ]
}

@test "a staging deploy that fails its smoke test reverts to the previous build" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  run briefer-deploy cccccccccccc "$(sha_of cccccccccccc)"
  [ "$status" -ne 0 ]
  [ "$(current_build staging)" = "$BUILD_A" ]
  [ "$(served_build staging)" = "$BUILD_A" ]
  [ ! -f "$BRIEFER_ROOT/builds/cccccccccccc/.staged-ok" ]
}

@test "staging data is refreshed from prod on each deploy" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  briefer-promote "$BUILD_A"
  add_prod_superuser "me@example.com"
  [ "$(has_superuser prod me@example.com)" = "1" ]

  run briefer-deploy "$BUILD_B" "$(sha_of "$BUILD_B")"
  [ "$status" -eq 0 ]
  [ "$(has_superuser staging me@example.com)" = "1" ]
  [ "$(served_build prod)" = "$BUILD_A" ]
}

@test "promote refuses a build that never passed staging" {
  run briefer-promote "$BUILD_B"
  [ "$status" -ne 0 ]
  [[ "$output" == *"not been deployed to staging"* ]]
  [ ! -e "$BRIEFER_ROOT/envs/prod/current" ]
}

@test "promote moves the staged build to prod and snapshots prod data first" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  briefer-promote "$BUILD_A"
  add_prod_superuser "me@example.com"
  briefer-deploy "$BUILD_B" "$(sha_of "$BUILD_B")"

  run briefer-promote "$BUILD_B"
  [ "$status" -eq 0 ]
  [ "$(current_build prod)" = "$BUILD_B" ]
  [ "$(served_build prod)" = "$BUILD_B" ]
  [ "$(has_superuser prod me@example.com)" = "1" ]
  [ "$(ls "$BRIEFER_DATA/snapshots" | grep -c "prod-.*-$BUILD_A.tar.gz")" = "1" ]
}

@test "promoting the build prod already runs is a no-op" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  briefer-promote "$BUILD_A"
  run briefer-promote "$BUILD_A"
  [ "$status" -eq 0 ]
  [[ "$output" == *"already"* ]]
}

@test "a promote that fails its smoke test restores the previous build and data" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  briefer-promote "$BUILD_A"
  add_prod_superuser "me@example.com"
  briefer-deploy "$BUILD_B" "$(sha_of "$BUILD_B")"
  # Break prod's environment so the new build's smoke check fails.
  sed -i 's/^BRIEFER_ENV=prod/BRIEFER_ENV=staging/' "$BRIEFER_ETC/prod.env"

  run briefer-promote "$BUILD_B"
  [ "$status" -ne 0 ]
  [[ "$output" == *"rolled back"* ]]
  [ "$(current_build prod)" = "$BUILD_A" ]
  [ "$(has_superuser prod me@example.com)" = "1" ]
}

@test "rollback reverts the most recent promote, including data" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  briefer-promote "$BUILD_A"
  briefer-deploy "$BUILD_B" "$(sha_of "$BUILD_B")"
  briefer-promote "$BUILD_B"
  # Data written after the promote is discarded by a rollback.
  add_prod_superuser "after-promote@example.com"

  run briefer-rollback
  [ "$status" -eq 0 ]
  [ "$(current_build prod)" = "$BUILD_A" ]
  [ "$(served_build prod)" = "$BUILD_A" ]
  [ "$(has_superuser prod after-promote@example.com)" = "0" ]

  run briefer-rollback
  [ "$status" -ne 0 ]
  [[ "$output" == *"nothing to roll back"* ]]
}

@test "verify runs smoke checks on a throwaway copy and cleans up" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  run briefer-verify "$BUILD_A"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Smoke checks: PASS"* ]]
  [[ "$output" == *"rss "*" MB"* ]]   # the memory check found the process
  [[ "$output" == *"Claude verification: skipped"* ]]
  run "$BRIEFER_SVC" is-active briefer@verify
  [ "$status" -ne 0 ]
  [ ! -d "$BRIEFER_DATA/verify" ]
  [ "$(served_build staging)" = "$BUILD_A" ]
}

@test "verify refuses a build that is not live on staging" {
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  run briefer-verify "$BUILD_B"
  [ "$status" -ne 0 ]
}

fake_claude() {
  # fake_claude <exit-code> — a stand-in `claude` that echoes its environment.
  mkdir -p "$T/fakebin"
  cat > "$T/fakebin/claude" <<SH
#!/usr/bin/env bash
echo "fake claude report: token=\${CLAUDE_CODE_OAUTH_TOKEN:-none} args=\$*"
exit $1
SH
  chmod +x "$T/fakebin/claude"
  export PATH="$T/fakebin:$PATH" BRIEFER_VERIFY_CLAUDE=1
}

@test "verify appends the Claude report, passing only claude.env credentials" {
  fake_claude 0
  printf 'CLAUDE_CODE_OAUTH_TOKEN=tok123\n' > "$BRIEFER_ETC/claude.env"
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  run briefer-verify "$BUILD_A"
  [ "$status" -eq 0 ]
  [[ "$output" == *"Claude verification (advisory):"* ]]
  [[ "$output" == *"fake claude report: token=tok123"* ]]
  [[ "$output" == *"--allowedTools Bash(curl:*)"* ]]
  # The token must not leak into the PocketBase process environment.
  ! grep -q tok123 "/proc/$(cat "$BRIEFER_RUN/staging.pid")/environ"
}

@test "a failing Claude pass does not fail verify" {
  fake_claude 1
  briefer-deploy "$BUILD_A" "$(sha_of "$BUILD_A")"
  run briefer-verify "$BUILD_A"
  [ "$status" -eq 0 ]
  [[ "$output" == *"did not complete"* ]]
}
