// Worker situs CCTV: halaman disajikan dari aset statis; jadwal (cron) memicu workflow GitHub
// supaya berita, kondisi ruas dan titik api tetap diperbarui walau jadwal GitHub sendiri telat.
// Butuh secret GH_TOKEN (token GitHub fine-grained, repo cctvpalembang/cctv, izin Actions: Read and write).
const REPO = "cctvpalembang/cctv", WORKFLOW = "berita.yml";

export default {
  async fetch(request, env) {
    // Uji manual: buka /uji-jadwal (situs tetap dilindungi Cloudflare Access)
    if (new URL(request.url).pathname === "/uji-jadwal") {
      const hasil = await picu(env);
      return new Response(hasil, { headers: { "content-type": "text/plain; charset=utf-8" } });
    }
    return env.ASSETS.fetch(request);
  },
  async scheduled(event, env, ctx) {
    console.log(await picu(env));
  },
};

async function picu(env) {
    if (!env.GH_TOKEN) return "GAGAL: GH_TOKEN belum terbaca oleh worker (simpan di Settings > Variables and secrets, bukan di Builds)";
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
    if (r.status === 204) return "BERHASIL: pembaruan berita dipicu (" + new Date().toISOString() + ")";
    return "GAGAL: GitHub menjawab " + r.status + " — " + (await r.text()).slice(0, 300);
}
