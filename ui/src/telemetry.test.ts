import { describe, expect, it } from "vitest";
import {
  startControl,
  acknowledgeControl,
  observeControls,
  timingEvidence,
} from "./telemetry";

describe("actual worker control observations", () => {
  it("does not equate a durable pause request with a paused worker", () => {
    startControl("pause-test", "pause");
    acknowledgeControl("pause-test", "CHECKING");
    observeControls([
      { id: "pause-test", status: "CHECKING", desired_action: "pause" },
    ]);
    expect(
      timingEvidence()
        .records.filter((r) => r.run_id === "pause-test")
        .map((r) => r.kind),
    ).toEqual(["control_request_durable", "control_request_rendered"]);
    observeControls([
      { id: "pause-test", status: "PAUSED", desired_action: "pause" },
    ]);
    expect(
      timingEvidence()
        .records.filter((r) => r.run_id === "pause-test")
        .at(-1),
    ).toMatchObject({
      kind: "control_state_rendered",
      status: "PAUSED",
      achieved: true,
    });
  });
  it("records terminal failure without claiming a successful control transition", () => {
    startControl("failure-test", "pause");
    acknowledgeControl("failure-test", "CHECKING");
    observeControls([
      { id: "failure-test", status: "FAILED", desired_action: "pause" },
    ]);
    expect(
      timingEvidence()
        .records.filter((r) => r.run_id === "failure-test")
        .at(-1),
    ).toMatchObject({
      status: "FAILED",
      expected_status: "PAUSED",
      achieved: false,
    });
  });
  it("does not claim a step completed merely because its request returned PAUSED", () => {
    startControl("step-test", "step");
    acknowledgeControl("step-test", "PAUSED");
    observeControls([
      { id: "step-test", status: "PAUSED", desired_action: "step" },
    ]);
    expect(
      timingEvidence().records.filter(
        (r) => r.run_id === "step-test" && r.kind === "control_state_rendered",
      ),
    ).toEqual([]);
  });
});
