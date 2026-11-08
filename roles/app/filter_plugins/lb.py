def _sub(value, paths):
  for key, path in paths.items():
    value = value.replace("{" + key + "}", path)
  return value


def lb_units(app, home, state_root):
  paths = {"current": home + "/current", "home": home, "state": state_root}
  default_wd = "{state}" if app["type"] == "external" else "{current}"
  units = []
  for key, unit in app["units"].items():
    base = "lb-" + (app["name"] if key == app["name"] else app["name"] + "-" + key)
    instances = unit.get("instances") or []
    file = base + ("@" if instances else "") + ".service"
    writable = unit.get("writable", ["{state}"]) + app.get("writable", [])

    env = dict(app.get("env") or {})
    env.update(unit.get("env") or {})

    description = app["description"] or app["name"]
    if key != app["name"]:
      description += " (%s)" % key

    units.append({
      "key": key,
      "file": file,
      "instances": [base + "@" + i + ".service" for i in instances] or [file],
      "description": unit.get("description") or description,
      "exec": _sub(unit["exec"], paths),
      "exec_stop": _sub(unit.get("exec_stop", ""), paths),
      "working_dir": _sub(unit.get("working_dir", default_wd), paths),
      "writable": [_sub(p, paths) for p in writable],
      "env": env,
      "restart": unit.get("restart", "always"),
      "restart_sec": unit.get("restart_sec", 3),
      "timeout_stop": unit.get("timeout_stop", ""),
      "overrides": list(app.get("hardening_overrides") or []) + list(unit.get("overrides") or []),
    })
  return units


class FilterModule:
  def filters(self):
    return {"lb_units": lb_units}
