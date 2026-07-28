#!/usr/bin/env bats

setup() {
  export PROBE="$(cd "$BATS_TEST_DIRNAME/.." && pwd)/.apm/skills/pr-shepherd/scripts/merge-probe.sh"
}

@test "draft PR is ignored before release classification" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":true,"headRefName":"feature/x","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = draft ]
}

@test "release-please branch is ignored" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":false,"headRefName":"release-please--branches--main","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = release ]
}

@test "autorelease pending label is ignored" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":false,"headRefName":"release-main","labels":[{"name":"autorelease: pending"}]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = release ]
}

@test "release-looking title is not a release anchor" {
  run bash -c 'printf "%s" '\''{"state":"OPEN","isDraft":false,"headRefName":"feature/x","title":"chore: release main","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = eligible ]
}

@test "merged PR is routed to reconciliation" {
  run bash -c 'printf "%s" '\''{"state":"MERGED","isDraft":false,"headRefName":"feature/x","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = merged ]
}

@test "merged release PR remains excluded" {
  run bash -c 'printf "%s" '\''{"state":"MERGED","isDraft":false,"headRefName":"release-please--branches--main","labels":[{"name":"autorelease: pending"}]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = release ]
}

@test "closed-unmerged PR is not eligible" {
  run bash -c 'printf "%s" '\''{"state":"CLOSED","isDraft":false,"headRefName":"feature/x","labels":[]}'\'' | "$PROBE" eligibility'
  [ "$status" -eq 0 ]
  [ "$output" = closed ]
}

