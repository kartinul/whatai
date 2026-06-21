import Groq from "groq-sdk";

export async function callGroqLlm(
  system: string,
  prompt: string,
): Promise<string> {
  const groq = new Groq({ apiKey: process.env.GROQ_API_KEY });

  try {
    const chatCompletion = await groq.chat.completions.create({
      messages: [
        { role: "system", content: system },
        { role: "user", content: prompt },
      ],
      model: "llama-3.1-8b-instant", // Fast, default groq model
    });

    return chatCompletion.choices[0]?.message?.content || "";
  } catch (error: any) {
    console.error("[groq] Error calling Groq LLM:", error.message);
    throw error;
  }
}
