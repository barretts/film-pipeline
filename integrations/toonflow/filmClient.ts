export type FilmProject = {
  project_id: string; revision: number; status: string; gpu_policy: "disabled"; gpu_active?: boolean;
  spec: { title: string; brief: string; shots: { id: string }[]; [key: string]: unknown };
  review_url: string; commands: { id: string; status: string; error?: string }[];
  approved_takes: Record<string, string>; ready_shots: string[];
  preparation?: { animatic_artifact_id: string; shots: Record<string, { card_artifact_id: string }> };
  film_artifact_id?: string;
  takes?: { id: string; shot_id: string; status: string; artifact_id?: string; request_artifact_id: string;
    gpu?: { state: string; error?: string } }[];
  blocked_shots?: { shot_id: string; reason: string }[];
  film_current?: boolean;
};

export function filmSummary(project: FilmProject, includeSpec = false) {
  const client = filmClient();
  return { project_id: project.project_id, revision: project.revision, status: project.status,
    gpu_policy: project.gpu_policy, gpu_active: project.gpu_active, title: project.spec.title, brief: project.spec.brief,
    review_url: client.reviewUrl(project.project_id), ready_shots: project.ready_shots,
    approved_takes: project.approved_takes, blocked_shots: project.blocked_shots, commands: project.commands.slice(-5),
    takes: project.takes?.map(t => ({ id: t.id, shot_id: t.shot_id, status: t.status,
      execution_state: t.gpu?.state, execution_error: t.gpu?.error,
      request_url: client.artifactUrl(project.project_id, t.request_artifact_id),
      video_url: t.artifact_id ? client.artifactUrl(project.project_id, t.artifact_id) : undefined })),
    ...(includeSpec ? { spec: project.spec } : {}),
    animatic_url: project.preparation ? client.artifactUrl(project.project_id, project.preparation.animatic_artifact_id) : undefined,
    film_current: project.film_current,
    film_url: project.film_artifact_id ? client.artifactUrl(project.project_id, project.film_artifact_id) : undefined };
}

export const agentActions = ["update", "draft", "prepare-assets", "render-ready", "assemble", "cancel", "resume"] as const;
export type FilmAction = typeof agentActions[number];

export class FilmHttpError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export function filmClient(address = "http://127.0.0.1:8766") {
  const base = new URL(address);
  if (base.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(base.hostname) ||
      base.username || base.password || base.search || base.hash || base.pathname !== "/") {
    throw new Error("Film backend must be a loopback HTTP origin, for example http://127.0.0.1:8766");
  }
  const origin = base.origin;
  async function request<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    const response = await fetch(origin + path, { method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body), signal });
    const value = await response.json();
    if (!response.ok) throw new FilmHttpError(value.error || `Film backend returned ${response.status}`, response.status);
    return value as T;
  }
  const api = "/api/film/v1/projects";
  function id(value: string) {
    if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}$/.test(value)) throw new Error("Invalid film identifier");
    return value;
  }
  return {
    origin,
    async capabilities(signal?: AbortSignal) {
      const value = await request<{ gpu_policy: string; account_required: boolean }>("/api/film/v1/capabilities", undefined, signal);
      if (value.gpu_policy !== "disabled" || value.account_required) throw new Error("A CPU-only, account-free film backend is required");
      return value;
    },
    list: (signal?: AbortSignal) => request<FilmProject[]>(api, undefined, signal),
    get: (projectId: string, signal?: AbortSignal) => request<FilmProject>(`${api}/${id(projectId)}`, undefined, signal),
    create: (creationId: string, spec?: unknown, signal?: AbortSignal) => request<FilmProject>(api,
      { creation_id: id(creationId), ...(spec ? { spec } : { template: "signal-in-the-snow" }) }, signal),
    command(projectId: string, commandId: string, revision: number, action: FilmAction, payload: unknown = {}, signal?: AbortSignal) {
      if (!(agentActions as readonly string[]).includes(action)) throw new Error("Agent interfaces cannot approve stories, takes or final films");
      return request(`${api}/${id(projectId)}/commands`, { command_id: id(commandId), expected_revision: revision, action, payload }, signal);
    },
    reviewUrl: (projectId: string) => `${origin}/film/projects/${id(projectId)}/review`,
    artifactUrl: (projectId: string, artifactId: string) => `${origin}${api}/${id(projectId)}/artifacts/${id(artifactId)}`,
  };
}
