import { createNodeConfig } from "@toonflow/nodes-scaffold";
export default createNodeConfig({ name: "filmProject", displayName: "Film Project", author: "Local Film Pipeline",
  github: "", serverTool: "../build/tools/filmProject.tool.js" }, import.meta.url,
  { outDir: "../build/nodes", syncToData: false });
