import { enableFailure, failureEnabled } from "../src/faultToggle";

test("toggle failure", () => {
  enableFailure(true);
  expect(failureEnabled()).toBe(true);
  enableFailure(false);
  expect(failureEnabled()).toBe(false);
});
