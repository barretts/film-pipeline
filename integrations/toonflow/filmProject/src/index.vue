<template>
  <nodeSkeleton v-bind="nodeProps">
    <div class="filmProject nodrag nopan nowheel">
      <p class="policy">Local CPU preparation · GPU worker requires separate opt-in</p>
      <label>Film project ID <input v-model="projectId" aria-label="Film project ID" @change="refresh" /></label>
      <button :disabled="busy" @click="create">New Signal in the Snow</button>
      <button :disabled="busy || !projectId" @click="refresh">Refresh</button>
      <p role="status">{{ message }}</p>
      <template v-if="project">
        <h3>{{ project.spec.title }}</h3>
        <p>{{ project.status }} · revision {{ project.revision }} · {{ Object.keys(project.approved_takes).length }}/{{ project.spec.shots.length }} approved shots</p>
        <a :href="client.reviewUrl(projectId)" target="_blank" rel="noreferrer">Open storyboard, take and film review</a>
        <video v-if="project.preparation" :src="client.artifactUrl(projectId, project.preparation.animatic_artifact_id)" controls preload="none" />
        <button :disabled="busy" @click="command('prepare-assets')">Prepare voices &amp; animatic</button>
        <button :disabled="busy" @click="command('render-ready')">Prepare ready shot requests</button>
        <button :disabled="busy" @click="command('assemble')">Assemble approved takes</button>
        <button :disabled="busy" @click="command('cancel')">Cancel work</button>
        <button :disabled="busy" @click="command('resume')">Resume</button>
        <button v-if="data.pendingCommand" :disabled="busy" @click="retry">Retry interrupted request</button>
        <details><summary>Script and shot specification</summary><textarea v-model="specText" aria-label="Film specification" @input="editing=true" /><button :disabled="busy" @click="save">Save revision</button><button :disabled="busy" @click="command('draft')">Draft from brief on CPU</button></details>
        <a v-if="project.film_artifact_id" :href="client.artifactUrl(projectId, project.film_artifact_id)" target="_blank" rel="noreferrer">Open assembled film for review</a>
        <pre>{{ project.commands }}</pre>
      </template>
    </div>
  </nodeSkeleton>
</template>
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { nodeSkeleton, nodeTools, useNode, z } from "@toonflow/nodes-scaffold/runtime";
import { filmClient, filmSummary, FilmHttpError, type FilmAction, type FilmProject } from "../../filmClient";
defineOptions({ inheritAttrs: false, handles: [{ id: "project", type: "source", dataType: "STRING", label: "Film project" },
  { id: "film", type: "source", dataType: "VIDEO", label: "Approved film" }] });
const { node, nodeProps, outputs } = useNode({ label: "Film Project", outputs: {
  project: { dataType: "STRING", value: "" }, film: { dataType: "VIDEO", value: { url: "", mimeType: "video/mp4" } } } });
type Pending = { id: string; revision: number; action: FilmAction; payload: unknown };
const data = computed(() => node.data as typeof node.data & { projectId?: string; creationId?: string; pendingCommand?: Pending });
const projectId = computed({ get: () => data.value.projectId ?? "", set: value => { data.value.projectId = value; } });
const client = filmClient();
const project = ref<FilmProject>(); const busy = ref(false); const message = ref(""); const specText = ref(""); const editing = ref(false);
let timer: ReturnType<typeof setInterval> | undefined;
let disposed = false;
async function refresh() {
  if (!projectId.value || disposed) return;
  try { const value = await client.get(projectId.value); if(disposed)return; project.value = value; outputs.value.project.value = projectId.value;
    outputs.value.film.value.url = value.status === "complete" && value.film_current && value.film_artifact_id
      ? client.artifactUrl(projectId.value, value.film_artifact_id) : "";
    if (!editing.value) specText.value = JSON.stringify(value.spec, null, 2);
  } catch(error) { message.value = (error as Error).message + ". Start tools/start_cpu_film.py if the backend is offline."; }
}
async function create() {
  busy.value = true;
  try { await client.capabilities(); data.value.creationId ??= crypto.randomUUID(); const value = await client.create(data.value.creationId);
    projectId.value = value.project_id; delete data.value.creationId; await refresh(); message.value = "Project created. Prepare and review its animatic."; return true;
  } catch(error) { message.value = (error as Error).message; return false; } finally { busy.value = false; }
}
async function retry() {
  const pending = data.value.pendingCommand;
  if (!pending) return;
  busy.value = true;
  try { await client.command(projectId.value, pending.id, pending.revision, pending.action, pending.payload);
    delete data.value.pendingCommand; message.value = "Request saved. CPU work continues if this canvas closes."; return true;
  } catch(error) { if(error instanceof FilmHttpError)delete data.value.pendingCommand;message.value = (error as Error).message; return false;
  } finally { busy.value = false; await refresh(); }
}
async function command(action: FilmAction, payload: unknown = {}) {
  if (!project.value) throw new Error("Load a film project first");
  if (data.value.pendingCommand) { message.value = "Retry the interrupted request before starting another command.";return false; }
  data.value.pendingCommand = { id: crypto.randomUUID(), revision: project.value.revision, action, payload }; return retry();
}
async function save() { try { const spec = JSON.parse(specText.value); editing.value = false; await command("update", { spec }); } catch(error) { message.value = (error as Error).message; } }
nodeTools.register({ name: "getFilmProject", description: "Read authoritative film project state and review links.", parameters: z.object({}), execute: async () => filmSummary(await client.get(projectId.value)) });
nodeTools.register({ name: "createFilmProject", description: "Create the local Signal in the Snow short; GPU disabled.", parameters: z.object({}), execute: async () => { if(!await create())throw Error(message.value);return filmSummary(project.value!); } });
nodeTools.register({ name: "prepareFilmAssets", description: "Queue CPU voices, storyboard cards and a timing animatic; never approves or renders shots.", parameters: z.object({}), execute: async () => { if(!await command("prepare-assets"))throw Error(message.value);return filmSummary(await client.get(projectId.value)); } });
onMounted(() => { void refresh();timer = setInterval(() => { if(!busy.value)void refresh(); }, 3000); });
onUnmounted(() => { disposed = true;if(timer)clearInterval(timer); });
</script>
<style scoped>
.filmProject{width:580px;padding:18px;background:#162235;color:#eef3fa;line-height:1.5}.policy{color:#8bd2e7}button{margin:6px 6px 6px 0;padding:8px;cursor:pointer}input,textarea{display:block;width:100%;background:#25374c;color:white;border:1px solid #62738a;padding:8px;box-sizing:border-box}textarea{height:220px}a{color:#8bd2e7}video{width:100%;margin:12px 0}pre{max-height:150px;overflow:auto;font-size:12px;white-space:pre-wrap}
</style>
