/**
 * Problem-report endpoint for SD Video Backup.
 *
 * The app posts a report here. This Worker stores the full log in R2 and
 * opens a GitHub issue summarising it. The GitHub token lives here as a
 * Worker secret, never in the app: a credential shipped inside a binary
 * handed to users is extractable with a text editor, which is why the app
 * itself has no GitHub access at all.
 *
 * The endpoint is necessarily open - the app has no user accounts - so it
 * is built on the assumption that anyone can post to it: small bodies
 * only, a shared key for friction rather than security, and a cap on how
 * many issues can be opened per hour so a flood cannot spam the repo.
 */

const MAX_BODY_BYTES = 256 * 1024;   // reports are a few KB; this is slack
const MAX_ISSUE_CHARS = 50 * 1024;   // GitHub caps issue bodies at 65536
const MAX_ISSUES_PER_HOUR = 12;

function text(status, body) {
  return new Response(body, { status, headers: { "content-type": "text/plain" } });
}

/** Rate limit by the hour, if a KV namespace is bound. Fails open. */
async function overIssueLimit(env) {
  if (!env.REPORTS_KV) return false;
  const key = `issues:${new Date().toISOString().slice(0, 13)}`;
  const used = parseInt((await env.REPORTS_KV.get(key)) || "0", 10);
  if (used >= MAX_ISSUES_PER_HOUR) return true;
  await env.REPORTS_KV.put(key, String(used + 1), { expirationTtl: 7200 });
  return false;
}

async function openIssue(env, title, body) {
  const res = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/issues`, {
    method: "POST",
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept: "application/vnd.github+json",
      "user-agent": "sd-video-backup-reporter",
      "content-type": "application/json",
    },
    body: JSON.stringify({ title, body, labels: ["problem report"] }),
  });
  if (!res.ok) throw new Error(`GitHub ${res.status}: ${(await res.text()).slice(0, 300)}`);
  return (await res.json()).html_url;
}

export default {
  async fetch(request, env) {
    if (request.method === "GET") return text(200, "SD Video Backup report endpoint\n");
    if (request.method !== "POST") return text(405, "POST only\n");

    if (env.REPORT_KEY && request.headers.get("x-report-key") !== env.REPORT_KEY) {
      return text(401, "bad key\n");
    }
    const declared = parseInt(request.headers.get("content-length") || "0", 10);
    if (declared > MAX_BODY_BYTES) return text(413, "report too large\n");

    let report;
    try {
      const raw = await request.text();
      if (raw.length > MAX_BODY_BYTES) return text(413, "report too large\n");
      report = JSON.parse(raw);
    } catch {
      return text(400, "expected JSON\n");
    }

    const now = new Date();
    const id = crypto.randomUUID();
    const meta = {
      version: String(report.version || "?"),
      platform: String(report.platform || "?"),
      language: String(report.language || "?"),
      machine: String(report.machine || "?"),
      note: String(report.note || "").slice(0, 2000),
    };
    const log = String(report.log || "");

    // Full log to R2; the issue carries only the tail, to stay well inside
    // GitHub's body limit and remain readable.
    let objectKey = null;
    if (env.REPORTS) {
      objectKey = `reports/${now.toISOString().slice(0, 7)}/${now.toISOString()
        .replace(/[:.]/g, "-")}_${id}.txt`;
      await env.REPORTS.put(objectKey, log, {
        httpMetadata: { contentType: "text/plain; charset=utf-8" },
        customMetadata: meta,
      });
    }

    const tail = log.split("\n").slice(-200).join("\n").slice(-MAX_ISSUE_CHARS);
    const body = [
      `**Version:** ${meta.version}`,
      `**Platform:** ${meta.platform}`,
      `**Language:** ${meta.language}`,
      `**Machine:** ${meta.machine}`,
      `**Received:** ${now.toISOString()}`,
      objectKey ? `**Full log:** \`${objectKey}\` in R2` : "**Full log:** not stored (no R2 binding)",
      "",
      meta.note ? `**What the user said:**\n\n> ${meta.note.replace(/\n/g, "\n> ")}\n` : "",
      "---",
      "",
      "Last 200 log lines:",
      "",
      "```",
      tail || "(empty log)",
      "```",
    ].join("\n");

    let issueUrl = null;
    if (env.GITHUB_TOKEN && env.GITHUB_REPO) {
      if (await overIssueLimit(env)) {
        // Still stored in R2; just don't open an issue for it.
        return Response.json({ ok: true, stored: objectKey, issue: null, limited: true });
      }
      try {
        issueUrl = await openIssue(env, `Problem report - ${meta.version} on ${meta.platform}`, body);
      } catch (err) {
        // The report is already safe in R2, so report partial success
        // rather than telling the user it failed.
        return Response.json({ ok: Boolean(objectKey), stored: objectKey,
                               issue: null, error: String(err).slice(0, 300) },
                             { status: objectKey ? 200 : 502 });
      }
    }
    return Response.json({ ok: true, stored: objectKey, issue: issueUrl });
  },
};
