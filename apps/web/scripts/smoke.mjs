import { chromium } from "playwright-core";

const edgePath =
  process.env.EDGE_PATH ??
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";

const browser = await chromium.launch({
  executablePath: edgePath,
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
const failedResponses = [];

page.on("console", (message) => {
  if (message.type() === "error") {
    errors.push(`${message.text()} @ ${message.location().url}`);
  }
});
page.on("pageerror", (error) => errors.push(error.message));
page.on("response", (response) => {
  if (response.status() >= 400) {
    failedResponses.push(`${response.status()} ${response.url()}`);
  }
});

await page.goto("http://127.0.0.1:3000", { waitUntil: "networkidle" });
await page.waitForFunction(
  () =>
    document.querySelectorAll("#product-select option").length > 1,
  { timeout: 15000 },
);

const options = await page.locator("#product-select option").count();
await page.locator("#product-select").selectOption("");
await page.locator("#chat-question").fill("M272Q 的 HDMI 接口怎么用？");
await page.locator(".send-button").click();
await page.waitForFunction(
  () => {
    const text = document.querySelector(".message.assistant .message-content")
      ?.textContent;
    return Boolean(text && text.length > 10);
  },
  { timeout: 60000 },
);

const answer = await page
  .locator(".message.assistant .message-content")
  .last()
  .textContent();
const citations = await page.locator(".citation").count();

await page.locator("#product-select").selectOption("huawei_c7");
await page.waitForTimeout(500);
await page.locator("#chat-question").fill("C7 支持蓝牙吗？");
await page.locator(".send-button").click();
await page.waitForFunction(
  () =>
    document.querySelectorAll(".message.assistant .message-content")
      .length === 1,
  { timeout: 60000 },
);
await page.locator("#chat-question").fill("那怎么连接？");
await page.locator(".send-button").click();
await page.waitForFunction(
  () =>
    document.querySelector(".message.assistant:last-of-type .mode")
      ?.textContent === "需要澄清",
  { timeout: 30000 },
);
const clarification = await page
  .locator(".message.assistant:last-of-type .mode")
  .textContent();

await page.screenshot({ path: "logs/web-smoke.png", fullPage: true });

console.log(
  JSON.stringify(
    {
      options,
      answer: answer?.slice(0, 160),
      citations,
      clarification,
      errors,
      failedResponses,
    },
    null,
    2,
  ),
);

await browser.close();
