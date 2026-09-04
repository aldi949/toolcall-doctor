# Score case-02 (after ground-truth reveal)

Blind diagnosis hashed before reveal: `6f9d5d3cff36e79605e971cffd5b697aa01f99c7d0708e6635402cdc3c139725`

Doctor: PROTOCOL_FAILURE, DIMENSION=D_HTTP_STATUS, LOCALIZATION=MEDIUM, INTERNAL=UNKNOWN.

Reproduction: YES. Control HTTP 200 3/3 with tool_calls. Broken HTTP 400 3/3. Raw body:
`json: cannot unmarshal number into Go struct field .tools.function.parameters.properties.enum of type string`

Ground truth: numeric enum unmarshal (PR #10166). Internal Go struct not claimed by Doctor.

Score: **B** (CORRECT_USEFUL_FAMILY)
Rationale: HTTP 4xx unique is the useful family. Exact `enum []string` cause remains UNKNOWN (correct; endpoint status is not the Go type). Not A.

Remediation: CONFIGURATION_FIX (string enum). Verified: control request is that workaround, 3/3 HTTP 200.
