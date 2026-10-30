import { chromium } from "playwright-core";

const edgePath =
  process.env.EDGE_PATH ??
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

const browser = await chromium.launch({
  executablePath: edgePath,
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1360, height: 960 } });
const errors = [];

page.on("console", (message) => {
  if (
    message.text().includes("401") &&
    message.location().url.includes("/api/admin/session")
  ) {
    return;
  }
  if (message.type() === "error") {
    errors.push(`${message.text()} @ ${message.location().url}`);
  }
});
page.on("pageerror", (error) => errors.push(error.message));

const pendingItem = {
  item_id: "item-1",
  filename: "tablet-manual.pdf",
  sha256: "a".repeat(64),
  product_ids: ["huawei_c7"],
  version_label: "2.1",
  confidence: "high",
  conflict_type: null,
  conflict_version_label: null,
  detected_product_name: null,
  status: "pending",
};
let batchItem = {
  ...pendingItem,
  version_label: "2.0",
  conflict_type: "same_name",
  conflict_version_label: "2.0",
  status: "conflict",
};
let batchItems = [
  batchItem,
  {
    ...pendingItem,
    item_id: "item-2",
    filename: "low-confidence.pdf",
    sha256: "b".repeat(64),
    product_ids: [],
    version_label: "1.0",
    confidence: "low",
    detected_product_name: "HUAWEI MateBook B7-420",
    status: "uploaded",
  },
];
let versionState = {
  id: "version-1",
  document_id: "document-1",
  version_label: "2.1",
  status: "validated",
  requires_manual_approval: true,
  approved_at: null,
  approved_by: null,
  document_name: "guide.pdf",
  indexes: [
    {
      index_version_id: "i4",
      status: "completed",
      chunk_count: 56,
      error_message: null,
    },
  ],
};

await page.route("**/api/admin/**", async (route) => {
  const request = route.request();
  const url = new URL(request.url());
  const pathname = url.pathname;

  if (pathname === "/api/admin/session") {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "admin session required" }),
    });
    return;
  }

  if (pathname === "/api/admin/login" && request.method() === "POST") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "ok" }),
    });
    return;
  }

  if (pathname === "/api/admin/imports" && request.method() === "POST") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ batch_id: "batch-1", accepted: 1 }),
    });
    return;
  }

  if (pathname === "/api/admin/imports" && request.method() === "GET") {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          batch_id: "batch-1",
          source_type: "files",
          status: "queued",
          created_by: "admin",
          item_count: 1,
        },
      ]),
    });
    return;
  }

  if (
    pathname === "/api/admin/imports/batch-1" &&
    request.method() === "GET"
  ) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        batch_id: "batch-1",
        items: batchItems,
      }),
    });
    return;
  }

  if (pathname.includes("/metadata") && request.method() === "PATCH") {
    const body = JSON.parse(request.postData() ?? "{}");
    const itemId = pathname.split("/items/")[1]?.split("/")[0];
    batchItems = batchItems.map((item) =>
      item.item_id === itemId
        ? {
            ...item,
            product_ids: body.product_name
              ? ["custom_b7_420"]
              : body.product_ids,
            version_label: body.version_label,
          }
        : item,
    );
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ batch_id: "batch-1", items: batchItems }),
    });
    return;
  }

  if (pathname.includes("/conflicts/") && request.method() === "POST") {
    const itemId = pathname.split("/conflicts/")[1]?.split("/")[0];
    batchItems = batchItems.map((item) =>
      item.item_id === itemId
        ? {
            ...item,
            conflict_type: null,
            conflict_version_label: null,
            status: "uploaded",
          }
        : item,
    );
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ batch_id: "batch-1", items: batchItems }),
    });
    return;
  }

  if (pathname.includes("/prepare") && request.method() === "POST") {
    const itemId = pathname.split("/items/")[1]?.split("/")[0];
    batchItems = batchItems.map((item) =>
      item.item_id === itemId ? { ...item, status: "queued" } : item,
    );
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        batch_id: "batch-1",
        items: batchItems,
      }),
    });
    return;
  }

  if (
    pathname === "/api/admin/products/pending-approval" &&
    request.method() === "GET"
  ) {
    const pending =
      versionState.requires_manual_approval &&
      versionState.approved_at === null;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(pending ? ["huawei_c7"] : []),
    });
    return;
  }

  if (
    pathname === "/api/admin/products/approved" &&
    request.method() === "GET"
  ) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(
        versionState.approved_at ? ["huawei_c7"] : [],
      ),
    });
    return;
  }

  if (
    /^\/api\/admin\/products\/[^/]+\/versions$/.test(pathname) &&
    request.method() === "GET"
  ) {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([versionState]),
    });
    return;
  }

  if (
    pathname === "/api/admin/versions/version-1/approve" &&
    request.method() === "POST"
  ) {
    versionState = {
      ...versionState,
      approved_at: "2026-10-29T12:00:00Z",
      approved_by: "admin",
    };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "approved" }),
    });
    return;
  }

  if (
    pathname === "/api/admin/versions/version-1/publish" &&
    request.method() === "POST"
  ) {
    versionState = { ...versionState, status: "active" };
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "active" }),
    });
    return;
  }

  await route.fulfill({
    status: 404,
    contentType: "application/json",
    body: JSON.stringify({ detail: "unexpected admin request" }),
  });
});

await page.route("**/api/products", async (route) => {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([
      {
        id: "huawei_c7",
        display_name: "华为平板 C7",
        category: "tablet",
        aliases: ["C7", "DBY-W09"],
      },
    ]),
  });
});

await page.goto("http://127.0.0.1:3000/admin", {
  waitUntil: "networkidle",
});
await page.locator("#admin-password").fill("test-password");
await page.getByRole("button", { name: "登录" }).click();
await page.getByRole("heading", { name: "文档导入" }).waitFor();

await page.locator("#manual-files").setInputFiles({
  name: "tablet-manual.pdf",
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.7\n%%EOF"),
});
await page.getByRole("button", { name: /上传/ }).click();
await page.getByText("是 · 同名不同内容").waitFor();

const conflictRow = page
  .locator(".admin-batch")
  .nth(1)
  .locator("tbody tr")
  .filter({ hasText: "tablet-manual.pdf" });
await conflictRow
  .getByRole("button", { name: "加入排队列表" })
  .click();
await page.getByRole("heading", { name: "文件冲突" }).waitFor();
await page.locator("#new-version").fill("2.1");
await page.getByRole("button", { name: "覆盖" }).click();
await page.locator(".admin-queue-table tbody tr").waitFor();

const queueRows = await page.locator(".admin-queue-table tbody tr").count();
const fileRows = await page
  .locator(".admin-batch")
  .nth(1)
  .locator(".admin-table tbody tr")
  .count();
const lowConfidenceRow = page
  .locator(".admin-batch")
  .nth(1)
  .locator("tbody tr")
  .filter({ hasText: "low-confidence.pdf" });
await lowConfidenceRow
  .getByRole("button", { name: "加入排队列表" })
  .click();
await page.getByRole("heading", { name: "填写产品名称" }).waitFor();
const prefilledProduct = await page.locator("#product-name").inputValue();
if (prefilledProduct !== "HUAWEI MateBook B7-420") {
  errors.push(`unexpected product prefill: ${prefilledProduct}`);
}
await page.getByRole("button", { name: "确认" }).click();
await page.waitForFunction(
  () => document.querySelectorAll(".admin-queue-table tbody tr").length === 2,
);
const finalQueueRows = await page
  .locator(".admin-queue-table tbody tr")
  .count();
const finalFileRows = await page
  .locator(".admin-batch")
  .nth(1)
  .locator(".admin-table tbody tr")
  .count();
const statuses = await page
  .locator(".admin-tag.status-queued")
  .allTextContents();
const pendingBefore = await page
  .locator(".admin-version-group.pending tbody tr")
  .count();
const approvedBefore = await page
  .locator(".admin-version-group.approved tbody tr")
  .count();
if (pendingBefore !== 1 || approvedBefore !== 0) {
  throw new Error(
    `unexpected version groups before approval: ${pendingBefore}/${approvedBefore}`,
  );
}
const approvalOptionsBefore = await page
  .getByLabel("版本产品")
  .locator("option")
  .allTextContents();
if (
  approvalOptionsBefore.length !== 1 ||
  approvalOptionsBefore[0] !== "华为平板 C7"
) {
  throw new Error(
    `unexpected approval products: ${approvalOptionsBefore.join(", ")}`,
  );
}
await page.getByRole("button", { name: "审批通过" }).first().click();
await page.waitForFunction(() => {
  const approved = document.querySelectorAll(
    ".admin-version-group.approved tbody tr",
  ).length;
  const selectedTab = document.querySelector(
    '[role="tab"][aria-selected="true"]',
  );
  return approved === 1 && selectedTab?.textContent?.includes("已审批");
});
await page.getByRole("button", { name: "发布" }).waitFor();
await page.getByText("未发布").waitFor();
await page.getByRole("button", { name: "发布" }).click();
await page.getByText("当前活动").waitFor();
const versionStatus = await page
  .locator(".admin-version-table tbody tr")
  .filter({ hasText: "2.1" })
  .innerText();
await page.screenshot({ path: "logs/admin-smoke.png", fullPage: true });
await page.setViewportSize({ width: 390, height: 844 });
await page.screenshot({
  path: "logs/admin-smoke-mobile.png",
  fullPage: true,
});
const mobileOverflow = await page.evaluate(
  () => document.documentElement.scrollWidth > window.innerWidth,
);
if (mobileOverflow) errors.push("admin page overflows on mobile viewport");

console.log(
  JSON.stringify(
    {
      queueRows,
      fileRows,
      finalQueueRows,
      finalFileRows,
      statuses,
      pendingBefore,
      approvedBefore,
      versionStatus,
      mobileOverflow,
      errors,
    },
    null,
    2,
  ),
);

await browser.close();
