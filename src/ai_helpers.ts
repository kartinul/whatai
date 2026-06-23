import { GoogleGenerativeAI } from "@google/generative-ai";

const MODELS = [
  "gemini-3.1-flash-lite",
  "gemini-2.5-flash-lite",
  "gemini-2.0-flash-lite",
];
const RPM = 15;

class ModelClient {
  model: string;
  apiKey: string;
  private client: GoogleGenerativeAI;
  private history: number[] = [];
  private cooldownUntil: number = 0;

  constructor(model: string, apiKey: string) {
    this.model = model;
    this.apiKey = apiKey;
    this.client = new GoogleGenerativeAI(apiKey);
  }

  isAvailable(): boolean {
    const now = Date.now() / 1000;
    if (now < this.cooldownUntil) {
      return false;
    }

    // Clean old history
    while (this.history.length > 0 && now - this.history[0] >= 60) {
      this.history.shift();
    }

    return this.history.length < RPM;
  }

  private stamp(): void {
    this.history.push(Date.now() / 1000);
  }

  cooldown(seconds: number = 60.0): void {
    this.cooldownUntil = Date.now() / 1000 + seconds;
  }

  async call(systemInstruction: string, prompt: string): Promise<string> {
    this.stamp();
    console.log(`[llm] ${this.model} | key ...${this.apiKey.slice(-4)}`);

    const generativeModel = this.client.getGenerativeModel({
      model: this.model,
      systemInstruction: systemInstruction,
    });

    const result = await generativeModel.generateContent(prompt);
    return result.response.text();
  }

  toString(): string {
    return `ModelClient(model='${this.model}', key=...${this.apiKey.slice(-4)})`;
  }
}

// Pool
let pool: ModelClient[] | null = null;

function getPool(): ModelClient[] {
  if (pool === null) {
    const keys: string[] = [];
    for (const [k, v] of Object.entries(process.env)) {
      if (k.startsWith("GEMINI_KEY_") && v && v.trim()) {
        keys.push(v.trim());
      }
    }

    if (keys.length === 0) {
      throw new Error("No GEMINI_KEY_* found in environment.");
    }

    pool = [];
    for (const model of MODELS) {
      for (const key of keys) {
        pool.push(new ModelClient(model, key));
      }
    }
  }
  return pool;
}

function parseRetryAfter(errorMsg: string): number {
  // RetryInfo logic ported from Python
  // try to match retry_delay { seconds: N }
  let m = errorMsg.match(/retry_delay\s*\{\s*seconds:\s*(\d+)/i);
  if (m) return parseFloat(m[1]);

  m = errorMsg.match(/retry.?delay['"]?\s*:?\s*['"]?(\d+)s?/i);
  if (m) return parseFloat(m[1]);

  m = errorMsg.match(/retry\s+after\s+(\d+)\s*s/i);
  if (m) return parseFloat(m[1]);

  m = errorMsg.match(/wait\s+(\d+)\s*(minute|min|hour|hr)/i);
  if (m) {
    const n = parseFloat(m[1]);
    const unit = m[2].toLowerCase();
    return unit.startsWith("h") ? n * 3600 : n * 60;
  }

  return 60.0;
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function callLlm(system: string, prompt: string): Promise<string> {
  const clients = getPool();
  const deadline = Date.now() + 120000; // 120 seconds

  while (Date.now() < deadline) {
    for (const client of clients) {
      if (!client.isAvailable()) continue;

      try {
        return await client.call(system, prompt);
      } catch (error: any) {
        const msg = error.toString();
        console.log(`[llm] ${client} failed: ${msg}`);

        if (
          msg.includes("429") ||
          msg.includes("RESOURCE_EXHAUSTED") ||
          msg.toLowerCase().includes("quota")
        ) {
          const wait = parseRetryAfter(msg);
          console.log(
            `[llm] rate-limited -- cooling ${client} for ${wait}s (${(wait / 60).toFixed(1)} min)`,
          );
          client.cooldown(wait);
        } else if (msg.includes("503") || msg.includes("UNAVAILABLE")) {
          client.cooldown(60);
        } else {
          await sleep(1000);
        }
      }
    }
    await sleep(500);
  }
  throw new Error("All ModelClients exhausted or on cooldown.");
}
