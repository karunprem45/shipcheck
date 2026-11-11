package main

import (
	"strings"
	"testing"
)

func good() Evidence {
	return Evidence{
		Tests:            &Tests{Total: 10},
		Security:         &Security{Low: 2},
		Review:           map[string]int{"minor": 1},
		TestsChanged:     true,
		ChangedFunctions: 2,
		LLMStatus:        "ok",
	}
}

func TestReadyWhenAllChecksPass(t *testing.T) {
	if !Ready(Evaluate(good(), DefaultPolicy())) {
		t.Fatal("expected READY")
	}
}

func TestMissingTestReportFails(t *testing.T) {
	ev := good()
	ev.Tests = nil
	if Ready(Evaluate(ev, DefaultPolicy())) {
		t.Fatal("missing tests must not pass")
	}
}

func TestZeroTestsFails(t *testing.T) {
	ev := good()
	ev.Tests = &Tests{Total: 0}
	if Ready(Evaluate(ev, DefaultPolicy())) {
		t.Fatal("a run with zero tests must not pass")
	}
}

func TestHighSecurityFindingBlocks(t *testing.T) {
	ev := good()
	ev.Security.High = 1
	if Ready(Evaluate(ev, DefaultPolicy())) {
		t.Fatal("high severity finding should block")
	}
}

func TestBlockerReviewFindingBlocks(t *testing.T) {
	ev := good()
	ev.Review["blocker"] = 1
	if Ready(Evaluate(ev, DefaultPolicy())) {
		t.Fatal("blocker should block")
	}
}

func TestCodeWithoutTestsBlocksByDefault(t *testing.T) {
	ev := good()
	ev.TestsChanged = false
	if Ready(Evaluate(ev, DefaultPolicy())) {
		t.Fatal("code change without tests should block")
	}
	p := DefaultPolicy()
	p.RequireTestsChange = false
	if !Ready(Evaluate(ev, p)) {
		t.Fatal("policy should be able to relax the tests rule")
	}
}

func TestLLMDownIsAdvisoryByDefault(t *testing.T) {
	ev := good()
	ev.LLMStatus = "invalid_output: bad json"
	if !Ready(Evaluate(ev, DefaultPolicy())) {
		t.Fatal("LLM outage should not block unless policy requires it")
	}
}

func TestMarkdownShowsVerdict(t *testing.T) {
	ev := good()
	ev.Security.High = 2
	md := Markdown(Evaluate(ev, DefaultPolicy()))
	if !strings.Contains(md, "NOT READY") || !strings.Contains(md, "FAIL") {
		t.Fatalf("unexpected markdown:\n%s", md)
	}
}
