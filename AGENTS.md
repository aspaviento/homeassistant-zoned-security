# Agent Guidance

## Project Scope

This repository is the public source for Zoned Security, a Home Assistant custom
integration that provides a zone-based alarm state machine with pre-alarm,
delayed alarm, manual inhibition, notifications, and Logbook activity entries.

The integration is designed to be useful from Home Assistant directly and from
HomeKit workflows exposed through Home Assistant's HomeKit Bridge. It is inspired
by the former `homebridge-automation-switches` security-system model, but this
repository must remain a generic Home Assistant integration.

## Repository Layout

- `custom_components/zoned_security/`: Home Assistant custom integration.
- `examples/`: public, sanitized YAML examples.
- `README.md`: public installation, configuration, and behavior documentation.
- `hacs.json`: HACS metadata for custom repository installation.

## Local Validation

Before committing code changes, run:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/zoned-security-pycache python3 -m compileall custom_components/zoned_security
python3 -m json.tool custom_components/zoned_security/manifest.json >/dev/null
ruby -e 'require "yaml"; YAML.load_file("examples/zoned_security.yaml")'
git diff --check
```

Before publishing, scan for private household details:

```bash
git grep -n -E 'mataberrypi|onepi|zeropi|/home/pi|192\.168|fdf2|HA (Zona|Modo|Security)|[Aa]larm(a|ed)|[Pp]re[- ]?alarma|[Áá]tico|[Ss][óo]tano|Primera|Segunda' -- ':!AGENTS.md'
```

## Operating Rules

- Keep this repository public-safe. Do not add private hostnames, private paths,
  local network details, tokens, Home Assistant secrets, real household zone
  names, or private deployment notes.
- Keep production Home Assistant YAML outside this repository. Only sanitized
  examples belong under `examples/`.
- Do not assume a user's HomeKit or Home Assistant setup. Document HomeKit as an
  optional usage model, not as a hard dependency.
- Keep the integration YAML-based until a config flow is intentionally designed.
- Update `README.md` when public behavior, YAML options, entity behavior, or
  notification semantics change.
- Treat this as an alarm workflow helper, not a certified safety-critical alarm
  system.
- Do not restart Home Assistant or Homebridge unless the user explicitly asks.
  The user normally performs restarts after installing or updating through HACS.
- Do not deploy changes to a live Home Assistant instance by directly copying
  files into `custom_components` once the integration is managed through HACS,
  unless the user explicitly authorizes that exception.
- For changes that should be consumed through HACS, use the release flow:
  validate locally, bump `manifest.json`, commit, push, tag, create a GitHub
  release, then let the user redownload or update through HACS and restart Home
  Assistant.

## Change Expectations

- Keep behavior conservative and predictable: explicit zones, explicit helpers,
  and no hidden external dependencies.
- Preserve backwards compatibility for documented YAML keys within a minor
  version when possible.
- Validate both Python syntax and example YAML before committing.
