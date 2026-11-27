// Worker situs CCTV: halaman disajikan dari aset statis; jadwal (cron) memicu workflow GitHub
// supaya berita, kondisi ruas dan titik api tetap diperbarui walau jadwal GitHub sendiri telat.
// Butuh secret GH_TOKEN (token GitHub fine-grained, repo cctvpalembang/cctv, izin Actions: Read and write).
const REPO = "cctvpalembang/cctv", WORKFLOW = "berita.yml";

export default {
  async fetch(request, env) {
    return env.ASSETS.fetch(request);
  },
  async scheduled(event, env, ctx) {
    if (!env.GH_TOKEN) { console.log("GH_TOKEN belum diisi; jadwal dilewati"); return; }
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + env.GH_TOKEN,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "cctv-worker-cron",
      },
      body: JSON.stringify({ ref: "main" }),
    });
    console.log("dispatch", r.status, r.status === 204 ? "ok" : await r.text());
  },
};
