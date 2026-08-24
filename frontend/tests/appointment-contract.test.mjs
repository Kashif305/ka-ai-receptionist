import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const actions = readFileSync(new URL("../app/appointments/actions.ts", import.meta.url), "utf8");
const manager = readFileSync(new URL("../components/appointments-manager.tsx", import.meta.url), "utf8");

test("dashboard reschedule uses general availability and backend reschedule contracts", () => {
  assert.match(actions, /\/dashboard\/availability\?\$\{query\}/);
  assert.match(actions, /\/dashboard\/appointments\/\$\{appointmentId\}\/reschedule/);
  assert.match(actions, /start_at: startAt/);
  assert.match(actions, /staff_id: staffId/);
  assert.match(manager, /setError\(result\.error\)/);
});

test("appointment filters expose all owner controls and clear action", () => {
  for (const name of ["search", "date", "service_id", "staff_id", "time_of_day"]) {
    assert.match(manager, new RegExp(`name="${name}"`));
  }
  assert.match(manager, /router\.replace\("\/appointments"\)/);
  assert.match(manager, /No appointments match these filters/);
});
