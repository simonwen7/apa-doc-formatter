import assert from "node:assert/strict";
import { afterEach, describe, it } from "node:test";

import {
  AuthSessionError,
  __setGetSessionForTests,
  authenticatedFetch,
  downloadAuthenticatedFile,
  filenameFromContentDisposition,
} from "./apiClient.js";

afterEach(() => {
  __setGetSessionForTests(null);
});

describe("apiClient auth UX", () => {
  it("maps HTTP 401 to AuthSessionError", async () => {
    __setGetSessionForTests(async () => ({
      data: { session: { access_token: "test-access-token" } },
      error: null,
    }));

    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () =>
      new Response(JSON.stringify({ detail: "Authentication required." }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      });

    try {
      await assert.rejects(
        () => authenticatedFetch("http://example.test/documents/analyze"),
        (err) =>
          err instanceof AuthSessionError &&
          /session has expired/i.test(err.message)
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("fails closed when session is missing", async () => {
    __setGetSessionForTests(async () => ({
      data: { session: null },
      error: null,
    }));

    await assert.rejects(
      () => authenticatedFetch("http://example.test/documents/analyze"),
      (err) => err instanceof AuthSessionError
    );
  });
});

describe("downloadAuthenticatedFile hygiene", () => {
  it("parses safe Content-Disposition filenames", () => {
    assert.equal(
      filenameFromContentDisposition('attachment; filename="paper.docx"'),
      "paper.docx"
    );
    assert.equal(
      filenameFromContentDisposition("attachment; filename=../../etc/passwd"),
      "passwd"
    );
    assert.equal(filenameFromContentDisposition(null), null);
  });

  it("revokes object URLs after successful download", async () => {
    const revoked = [];
    const created = [];

    globalThis.document = {
      body: {
        appendChild() {},
      },
      createElement() {
        return {
          click() {},
          remove() {},
          set href(_v) {},
          set download(_v) {},
          set rel(_v) {},
        };
      },
    };

    await downloadAuthenticatedFile(
      "http://example.test/documents/download/x",
      "formatted.docx",
      {
        revokeImmediately: true,
        createObjectURL: (blob) => {
          const url = `blob:mock-${created.length}`;
          created.push({ url, size: blob.size });
          return url;
        },
        revokeObjectURL: (url) => revoked.push(url),
        fetchImpl: async () =>
          new Response(new Blob([new Uint8Array([0x50, 0x4b])]), {
            status: 200,
            headers: {
              "Content-Disposition": 'attachment; filename="safe.docx"',
            },
          }),
      }
    );

    assert.equal(created.length, 1);
    assert.deepEqual(
      revoked,
      created.map((item) => item.url)
    );
  });

  it("does not create object URLs when fetch fails", async () => {
    let created = 0;
    await assert.rejects(
      () =>
        downloadAuthenticatedFile("http://example.test/fail", "formatted.docx", {
          createObjectURL: () => {
            created += 1;
            return "blob:should-not";
          },
          revokeObjectURL: () => {},
          fetchImpl: async () =>
            new Response(JSON.stringify({ detail: "Fixed document not found." }), {
              status: 404,
              headers: { "Content-Type": "application/json" },
            }),
        }),
      /not found|Download failed/i
    );
    assert.equal(created, 0);
  });
});
