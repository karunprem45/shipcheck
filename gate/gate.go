// Package main implements the ShipCheck release-readiness gate.
// It reads evidence.json (written by the Python agent) and a policy file,
// prints a Markdown checklist, and exits 1 if any required check fails.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"strings"
)

type Tests struct {
	Total   int `json:"total"`
	Failed  int `json:"failed"`
	Skipped int `json:"skipped"`
}

type Security struct {
	Low    int `json:"low"`
	Medium int `json:"medium"`
	High   int `json:"high"`
}

type Evidence struct {
	Tests            *Tests         `json:"tests"`
	Security         *Security      `json:"security"`
	Review           map[string]int `json:"review"`
	TestsChanged     bool           `json:"tests_changed"`
	DocsChanged      bool           `json:"docs_changed"`
	ChangedFunctions int            `json:"changed_functions"`
	LLMStatus        string         `json:"llm_status"`
}

type Policy struct {
	MaxFailedTests      int  `json:"max_failed_tests"`
	MaxHighSecurity     int  `json:"max_high_security"`
	MaxMediumSecurity   int  `json:"max_medium_security"`
	MaxBlockers         int  `json:"max_blockers"`
	RequireTestsChange  bool `json:"require_tests_when_code_changes"`
	RequireDocsChange   bool `json:"require_docs_when_code_changes"`
	RequireLLMReview    bool `json:"require_llm_review"`
}

type Check struct {
	Name     string
	Passed   bool
	Required bool
	Detail   string
}

func DefaultPolicy() Policy {
	return Policy{MaxHighSecurity: 0, MaxMediumSecurity: 3, MaxBlockers: 0, RequireTestsChange: true}
}

// Evaluate turns evidence into a list of checks. A missing input is a failure,
// not a pass: the gate should never go green because a step did not run.
func Evaluate(ev Evidence, p Policy) []Check {
	var checks []Check

	if ev.Tests == nil {
		checks = append(checks, Check{"Tests ran", false, true, "no JUnit report found"})
	} else {
		ok := ev.Tests.Total > 0 && ev.Tests.Failed <= p.MaxFailedTests
		checks = append(checks, Check{"Tests pass", ok, true,
			fmt.Sprintf("%d total, %d failed, %d skipped", ev.Tests.Total, ev.Tests.Failed, ev.Tests.Skipped)})
	}

	if ev.Security == nil {
		checks = append(checks, Check{"Security scan ran", false, true, "no scan report found"})
	} else {
		ok := ev.Security.High <= p.MaxHighSecurity && ev.Security.Medium <= p.MaxMediumSecurity
		checks = append(checks, Check{"Security scan within limits", ok, true,
			fmt.Sprintf("high %d, medium %d, low %d", ev.Security.High, ev.Security.Medium, ev.Security.Low)})
	}

	blockers := ev.Review["blocker"]
	checks = append(checks, Check{"No blocker review findings", blockers <= p.MaxBlockers, true,
		fmt.Sprintf("%d blocker, %d major", blockers, ev.Review["major"])})

	if ev.ChangedFunctions > 0 {
		checks = append(checks, Check{"Tests updated with code", ev.TestsChanged, p.RequireTestsChange,
			fmt.Sprintf("%d changed functions", ev.ChangedFunctions)})
		checks = append(checks, Check{"Docs updated with code", ev.DocsChanged, p.RequireDocsChange, ""})
	}

	checks = append(checks, Check{"AI review completed", ev.LLMStatus == "ok", p.RequireLLMReview,
		"status: " + ev.LLMStatus})
	return checks
}

func Ready(checks []Check) bool {
	for _, c := range checks {
		if c.Required && !c.Passed {
			return false
		}
	}
	return true
}

func Markdown(checks []Check) string {
	var b strings.Builder
	verdict := "READY"
	if !Ready(checks) {
		verdict = "NOT READY"
	}
	fmt.Fprintf(&b, "## Release readiness: %s\n\n| Check | Result | Required | Detail |\n|---|---|---|---|\n", verdict)
	for _, c := range checks {
		res := "pass"
		if !c.Passed {
			res = "FAIL"
		}
		req := "no"
		if c.Required {
			req = "yes"
		}
		fmt.Fprintf(&b, "| %s | %s | %s | %s |\n", c.Name, res, req, c.Detail)
	}
	return b.String()
}

func loadJSON(path string, v any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(data, v)
}

func main() {
	evPath := flag.String("evidence", "evidence.json", "evidence file from the agent")
	polPath := flag.String("policy", "", "policy JSON (optional)")
	flag.Parse()

	var ev Evidence
	if err := loadJSON(*evPath, &ev); err != nil {
		fmt.Fprintln(os.Stderr, "read evidence:", err)
		os.Exit(2)
	}
	p := DefaultPolicy()
	if *polPath != "" {
		if err := loadJSON(*polPath, &p); err != nil {
			fmt.Fprintln(os.Stderr, "read policy:", err)
			os.Exit(2)
		}
	}
	checks := Evaluate(ev, p)
	fmt.Print(Markdown(checks))
	if !Ready(checks) {
		os.Exit(1)
	}
}
