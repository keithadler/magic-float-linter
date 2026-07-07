# Security Policy

## Scope

`exact` is a static linter. It parses Python source into an AST and inspects
numeric literals; it does not import, execute, or evaluate the code it scans,
and it makes no network calls. Its only runtime dependency is `mpmath`.

The most plausible security-relevant defect would be a way to make `exact`
crash, hang, or consume excessive resources on a crafted input file (a
denial-of-service against a CI pipeline that runs it). If you find one, please
report it.

## A note on "magic constants as backdoors"

A natural question this tool raises: could a truncated constant be a deliberate
backdoor rather than a typo? In practice, no - and understanding why is useful.
A backdoor needs a reliable, controllable effect, but the perturbation from a
truncated float constant is typically orders of magnitude below the working
precision of the surrounding computation (e.g. ~1e-10 against float32's ~1e-7),
so it cannot reliably control anything. It is also trivially greppable and
resolves cleanly to a famous constant - the opposite of what an attacker with
commit access, who has far better options, would choose. `exact` surfaces these
as *anomalies* and is honest that the overwhelmingly likely explanation is
human transcription, not malice. See the "backdoor" discussion in the
false-positive audit for the full reasoning.

## Reporting a vulnerability

Please use GitHub's private ["Report a vulnerability"](https://github.com/keithadler/magic-float-linter/security/advisories/new)
flow rather than a public issue, so a fix can ship before details are public.
Include the input that triggers the problem and what you observed. This is a
spare-time project, so response may take a few days; thank you for your
patience.
