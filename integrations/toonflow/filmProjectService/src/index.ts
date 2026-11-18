import { z } from "zod";
import type { ToolPlugin } from "@toonflow/tools-scaffold/runtime";
import { agentActions, filmClient, filmSummary, type FilmProject } from "../../filmClient";
const schema = z.object({ operation: z.enum(["list", "get", "create", ...agentActions]), projectId: z.string().optional(),
  creationId: z.string().optional(), commandId: z.string().optional(), expectedRevision: z.number().int().optional(),
  spec: z.record(z.string(), z.json()).optional(), brief: z.string().optional(), includeSpec: z.boolean().optional() }).strict();
const plugin: ToolPlugin = {
  validateConfig: config => z.object({}).strict().parse(config),
  createTools() { return [{ name: "filmProject", label: "Film project", description: "Create, inspect or prepare a local CPU-only film project. Use get to obtain the current revision; stable ids are mandatory for writes. Approvals are made by the owner at review_url.",
    parameters: z.toJSONSchema(schema, { target: "draft-07" }), executionMode: "sequential",
    async execute(_id, input, signal) {
      const args = schema.parse(input), client = filmClient();
      await client.capabilities(signal);
      let result: FilmProject | FilmProject[];
      if(args.operation === "list")result = await client.list(signal);
      else if(args.operation === "create") {
        if(!args.creationId)throw Error("create needs a stable creationId");
        result = await client.create(args.creationId,args.spec,signal);
      } else {
        if(!args.projectId)throw Error("projectId is required");
        if(args.operation === "get") result = await client.get(args.projectId,signal);
        else {
          if(!args.commandId || args.expectedRevision === undefined)throw Error("Write needs commandId and expectedRevision from get");
          await client.command(args.projectId,args.commandId,args.expectedRevision,args.operation,
            args.operation === "update" ? { spec: args.spec } : args.operation === "draft" ? { brief: args.brief } : {},signal);
          result = await client.get(args.projectId,signal);
        }
      }
      const summary = Array.isArray(result) ? { count: result.length, projects: result.slice(0, 20).map(p => filmSummary(p)) }
        : filmSummary(result, args.includeSpec);
      return { content: [{ type: "text", text: JSON.stringify(summary) }], details: summary };
    },
  }]; },
};
export default plugin;
