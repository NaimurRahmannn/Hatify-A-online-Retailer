const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const scriptPath = path.join(
  __dirname,
  "..",
  "public",
  "static",
  "js",
  "ai_assistant.js"
);
const assistantScript = fs.readFileSync(scriptPath, "utf8");

class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  add(value) {
    this.values.add(value);
  }

  remove(value) {
    this.values.delete(value);
  }

  contains(value) {
    return this.values.has(value);
  }
}

class FakeElement {
  constructor(tagName = "div") {
    this.tagName = tagName.toUpperCase();
    this.classList = new FakeClassList();
    this.listeners = {};
    this.style = {};
    this.children = [];
    this.value = "";
    this.disabled = false;
    this.scrollHeight = 0;
    this.scrollTop = 0;
    this.attributes = {};
    this.focusCalls = 0;
  }

  addEventListener(name, listener) {
    this.listeners[name] ||= [];
    this.listeners[name].push(listener);
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  insertBefore(child) {
    this.children.push(child);
    return child;
  }

  async dispatch(name, overrides = {}) {
    const event = {
      preventDefault() {},
      key: undefined,
      ...overrides,
    };
    for (const listener of this.listeners[name] || []) {
      await listener(event);
    }
  }

  setAttribute(name, value) {
    this.attributes[name] = value;
  }

  focus() {
    this.focusCalls += 1;
  }
}

function createFrontend({
  includeCloseButton = false,
  storedConversationId = null,
  responses = [],
} = {}) {
  const elements = {
    "ai-chat-toggle": new FakeElement(),
    "ai-chat-window": new FakeElement(),
    "ai-chat-messages": new FakeElement(),
    "ai-chat-form": new FakeElement("form"),
    "ai-chat-input": new FakeElement(),
    "ai-chat-send": new FakeElement("button"),
    "ai-typing-indicator": new FakeElement(),
  };

  if (includeCloseButton) {
    elements["ai-chat-close"] = new FakeElement();
  }

  const createdElements = [];
  const documentListeners = {};
  const document = {
    cookie: "",
    addEventListener(name, listener) {
      if (name === "DOMContentLoaded") {
        listener();
        return;
      }
      documentListeners[name] ||= [];
      documentListeners[name].push(listener);
    },
    getElementById(id) {
      return elements[id] || null;
    },
    querySelector(selector) {
      if (selector === "[name=csrfmiddlewaretoken]") {
        return { value: "csrf-test-token" };
      }
      return null;
    },
    createElement(tagName) {
      const element = new FakeElement(tagName);
      createdElements.push(element);
      return element;
    },
    createTextNode(text) {
      return { textContent: text };
    },
    async dispatch(name, overrides = {}) {
      const event = { key: undefined, ...overrides };
      for (const listener of documentListeners[name] || []) {
        await listener(event);
      }
    },
  };

  const storage = new Map();
  if (storedConversationId) {
    storage.set("haatify_ai_conversation", storedConversationId);
  }
  const requests = [];
  const dispatchedEvents = [];
  const consoleErrors = [];
  const fetch = async (url, options) => {
    requests.push({ url, options });
    const response = responses.shift();
    if (!response) throw new Error("No fake response configured");
    return {
      ok: response.status >= 200 && response.status < 300,
      status: response.status,
      async json() {
        return response.body;
      },
    };
  };
  class FakeCustomEvent {
    constructor(type, init) {
      this.type = type;
      this.detail = init.detail;
    }
  }
  const window = {
    document,
    localStorage: {
      getItem(key) {
        return storage.get(key) || null;
      },
      setItem(key, value) {
        storage.set(key, value);
      },
      removeItem(key) {
        storage.delete(key);
      },
    },
    fetch,
    CustomEvent: FakeCustomEvent,
    dispatchEvent(event) {
      dispatchedEvents.push(event);
    },
  };

  const context = {
    console: {
      error(...args) {
        consoleErrors.push(args);
      },
      log() {},
    },
    document,
    localStorage: window.localStorage,
    fetch,
    CustomEvent: FakeCustomEvent,
    window,
    setTimeout(listener) {
      listener();
    },
  };

  return {
    context,
    consoleErrors,
    createdElements,
    dispatchedEvents,
    elements,
    requests,
    storage,
  };
}

test("a missing optional close button does not prevent send initialization", () => {
  const frontend = createFrontend();

  assert.doesNotThrow(() => {
    vm.runInNewContext(assistantScript, frontend.context);
  });
  assert.equal(frontend.elements["ai-chat-form"].listeners.submit.length, 1);
});

test("form submission reuses and persists the conversation id", async () => {
  const frontend = createFrontend({
    includeCloseButton: true,
    storedConversationId: "old-conversation",
    responses: [
      {
        status: 200,
        body: {
          conversation_id: "continued-conversation",
          answer: "A tailored answer",
          products: [],
          metadata: {},
        },
      },
    ],
  });
  frontend.elements["ai-chat-input"].value = "Find a black hoodie";
  vm.runInNewContext(assistantScript, frontend.context);

  await frontend.elements["ai-chat-form"].dispatch("submit");

  assert.equal(frontend.requests.length, 1);
  assert.deepEqual(JSON.parse(frontend.requests[0].options.body), {
    message: "Find a black hoodie",
    conversation_id: "old-conversation",
  });
  assert.equal(
    frontend.storage.get("haatify_ai_conversation"),
    "continued-conversation"
  );
});

test("product cards use API links and dispatch AI_PRODUCT_CLICK", async () => {
  const frontend = createFrontend({
    includeCloseButton: true,
    responses: [
      {
        status: 200,
        body: {
          conversation_id: "conversation-1",
          answer: "Try this.",
          products: [
            {
              id: "23",
              name: "Red Dress",
              price: 0,
              category: "Dresses",
              image: "/media/red-dress.jpg",
              url: "/product/red-dress/",
            },
          ],
          metadata: {},
        },
      },
    ],
  });
  frontend.elements["ai-chat-input"].value = "Show me a red dress";
  vm.runInNewContext(assistantScript, frontend.context);

  await frontend.elements["ai-chat-form"].dispatch("submit");

  const card = frontend.createdElements.find(
    (element) => element.tagName === "A" && element.className === "ai-product-card"
  );
  assert.ok(card);
  assert.equal(card.href, "/product/red-dress/");
  await card.dispatch("click");
  assert.equal(frontend.dispatchedEvents.length, 1);
  assert.equal(frontend.dispatchedEvents[0].type, "AI_PRODUCT_CLICK");
  assert.equal(frontend.dispatchedEvents[0].detail.product_id, "23");
  assert.equal(frontend.dispatchedEvents[0].detail.conversation_id, "conversation-1");
  assert.equal(frontend.dispatchedEvents[0].detail.product_url, "/product/red-dress/");
});

test("an expired stored conversation is cleared and retried once", async () => {
  const frontend = createFrontend({
    includeCloseButton: true,
    storedConversationId: "expired-conversation",
    responses: [
      { status: 404, body: { error: "Conversation not found." } },
      {
        status: 200,
        body: {
          conversation_id: "new-conversation",
          answer: "We can start fresh.",
          products: [],
          metadata: {},
        },
      },
    ],
  });
  frontend.elements["ai-chat-input"].value = "Continue helping me";
  vm.runInNewContext(assistantScript, frontend.context);

  await frontend.elements["ai-chat-form"].dispatch("submit");

  assert.equal(frontend.requests.length, 2);
  assert.equal(
    JSON.parse(frontend.requests[0].options.body).conversation_id,
    "expired-conversation"
  );
  assert.equal(JSON.parse(frontend.requests[1].options.body).conversation_id, undefined);
  assert.equal(frontend.storage.get("haatify_ai_conversation"), "new-conversation");
});

test("an API error restores input controls and renders an error", async () => {
  const frontend = createFrontend({
    includeCloseButton: true,
    responses: [{ status: 429, body: { error: "Too many requests." } }],
  });
  frontend.elements["ai-chat-input"].value = "One more request";
  vm.runInNewContext(assistantScript, frontend.context);

  await frontend.elements["ai-chat-form"].dispatch("submit");

  assert.equal(frontend.elements["ai-chat-input"].disabled, false);
  assert.equal(frontend.elements["ai-chat-send"].disabled, false);
  const errorMessage = frontend.createdElements.find((element) =>
    element.classList.contains("ai-error-msg")
  );
  assert.ok(errorMessage);
  assert.equal(errorMessage.children[0].textContent, "Too many requests.");
});

test("Escape closes the panel, updates aria state, and returns focus", async () => {
  const frontend = createFrontend({ includeCloseButton: true });
  vm.runInNewContext(assistantScript, frontend.context);

  await frontend.elements["ai-chat-toggle"].dispatch("click");
  assert.equal(frontend.elements["ai-chat-toggle"].attributes["aria-expanded"], "true");
  assert.equal(frontend.elements["ai-chat-window"].classList.contains("is-open"), true);

  await frontend.context.document.dispatch("keydown", { key: "Escape" });

  assert.equal(frontend.elements["ai-chat-toggle"].attributes["aria-expanded"], "false");
  assert.equal(frontend.elements["ai-chat-window"].classList.contains("is-open"), false);
  assert.equal(frontend.elements["ai-chat-toggle"].focusCalls, 1);
});

test("divided collections and filter chips are rendered when mixed products are returned", async () => {
  const frontend = createFrontend({
    includeCloseButton: true,
    responses: [
      {
        status: 200,
        body: {
          conversation_id: "mixed-conv",
          answer: "Here are options for both men and women.",
          products: [
            {
              id: "1",
              name: "Men Jacket",
              price: 3000,
              category: "Jackets",
              image: "/media/men-jacket.jpg",
              url: "/product/men-jacket/",
              metadata: { category_type: "Men", gender: "men" },
            },
            {
              id: "2",
              name: "Women Jacket",
              price: 3500,
              category: "Jackets",
              image: "/media/women-jacket.jpg",
              url: "/product/women-jacket/",
              metadata: { category_type: "Women", gender: "women" },
            },
          ],
          metadata: {},
        },
      },
      {
        status: 200,
        body: {
          conversation_id: "mixed-conv",
          answer: "Here are only men's items.",
          products: [
            {
              id: "1",
              name: "Men Jacket",
              price: 3000,
              category: "Jackets",
              image: "/media/men-jacket.jpg",
              url: "/product/men-jacket/",
              metadata: { category_type: "Men", gender: "men" },
            },
          ],
          metadata: {},
        },
      },
    ],
  });
  frontend.elements["ai-chat-input"].value = "Show me jackets";
  vm.runInNewContext(assistantScript, frontend.context);

  await frontend.elements["ai-chat-form"].dispatch("submit");

  const dividedWrapper = frontend.createdElements.find(
    (el) => el.className === "ai-divided-collection"
  );
  assert.ok(dividedWrapper, "Should render ai-divided-collection container");

  const filterChips = frontend.createdElements.filter(
    (el) => el.tagName === "BUTTON" && el.className === "ai-filter-chip"
  );
  assert.equal(filterChips.length, 2, "Should render 2 filter chips (Men Only, Women Only)");

  // Click the 'Men Only' chip to verify follow-up query submission
  await filterChips[0].dispatch("click");

  assert.equal(frontend.requests.length, 2);
  assert.deepEqual(JSON.parse(frontend.requests[1].options.body), {
    message: "Show me only men's items",
    conversation_id: "mixed-conv",
  });
});

