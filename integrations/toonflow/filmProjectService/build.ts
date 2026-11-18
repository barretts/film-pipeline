import { createToolConfig } from "@toonflow/tools-scaffold";
await createToolConfig({ name: "filmProject", displayName: "Local film projects", description: "Prepare and inspect local short films on CPU. Human review is separate; GPU execution is disabled.",
  author: "Local Film Pipeline", github: "", configRules: [],
  prompt: "Use filmProject for durable film state. Supply stable creationId/commandId for writes and expectedRevision from get. A lost response must be retried with exactly the same id and payload. The tool cannot approve a storyboard, take or film. Give the local review link to the owner and wait for its recorded decision. render-ready saves request bundles only; do not call external media providers or GPU endpoints." }, import.meta.url,
  { outDir: "../build/tools", syncToData: false });
