#!/usr/bin/env bats
# The SSH forced command must only ever run a fixed set of well-formed commands.

load helpers

setup() { setup_env; }

entry() { SSH_ORIGINAL_COMMAND="$1" run briefer-entry; }

@test "rejects an empty command" {
  entry ""
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}

@test "rejects unknown commands" {
  entry "bash -c id"
  [ "$status" -eq 2 ]
}

@test "rejects shell metacharacters smuggled into arguments" {
  entry "deploy aaaaaaaaaaaa;id $(printf 'a%.0s' {1..64})"
  [ "$status" -eq 2 ]
  entry "promote aaaaaaaaaaaa && reboot"
  [ "$status" -eq 2 ]
}

@test "rejects malformed build ids and checksums" {
  entry "deploy AAAAAAAAAAAA $(printf 'a%.0s' {1..64})"
  [ "$status" -eq 2 ]
  entry "deploy aaaaaaaaaaaa deadbeef"
  [ "$status" -eq 2 ]
  entry "promote ../../etc"
  [ "$status" -eq 2 ]
}

@test "there is no way to deploy directly to prod" {
  entry "deploy prod aaaaaaaaaaaa $(printf 'a%.0s' {1..64})"
  [ "$status" -eq 2 ]
}

@test "status runs" {
  entry "status"
  [ "$status" -eq 0 ]
  [[ "$output" == *"prod:"* ]]
}
