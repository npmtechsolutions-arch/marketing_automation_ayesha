/**
 * The support case this helper exists for: a failure whose message sent
 * someone looking in the wrong place.
 */
import { describe, expect, it } from "vitest";
import { apiErrorMessage } from "./apiError";

describe("apiErrorMessage", () => {
  it("names the unreachable API instead of saying 'try again'", () => {
    // Axios reports a CORS block or a dead port with no `response` at all.
    // This is exactly what produced "Registration failed. Please try again."
    const msg = apiErrorMessage({ message: "Network Error" }, "Registration failed.", {
      apiBase: "http://localhost:8000/api/v1",
    });
    expect(msg).toContain("Could not reach");
    expect(msg).toContain("http://localhost:8000/api/v1");
    expect(msg).not.toContain("Registration failed.");
  });

  it("says the backend is the wrong one when a 404 has no detail of its own", () => {
    const msg = apiErrorMessage(
      { response: { status: 404, data: { detail: "Not Found" } } },
      "Registration failed.",
      { apiBase: "http://localhost:8000/api/v1" }
    );
    expect(msg).toContain("wrong backend");
  });

  it("does not tell someone to retry immediately when they are rate limited", () => {
    const msg = apiErrorMessage(
      { response: { status: 429, data: { detail: "Too many registrations. Try again in an hour." } } },
      "Registration failed."
    );
    expect(msg).toBe("Too many registrations. Try again in an hour.");
  });

  it("passes the server's own reason through unchanged", () => {
    const msg = apiErrorMessage(
      { response: { status: 409, data: { detail: "That email is already registered." } } },
      "Registration failed."
    );
    expect(msg).toBe("That email is already registered.");
  });

  it("reads a Pydantic validation list rather than printing [object Object]", () => {
    const msg = apiErrorMessage(
      {
        response: {
          status: 422,
          data: { detail: [{ loc: ["body", "password"], msg: "too short" }] },
        },
      },
      "Registration failed."
    );
    expect(msg).toBe("password: too short");
  });

  it("falls back only when the server answered something uninterpretable", () => {
    expect(
      apiErrorMessage({ response: { status: 400, data: {} } }, "Registration failed.")
    ).toBe("Registration failed.");
  });

  it("says a timeout is a timeout", () => {
    const msg = apiErrorMessage({ code: "ECONNABORTED" }, "x", { apiBase: "/api/v1" });
    expect(msg).toContain("did not answer in time");
  });
});
