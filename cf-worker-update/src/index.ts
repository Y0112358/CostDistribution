export interface Env {
  GH_TOKEN: string
  OWNER: string
  REPO: string
  WORKFLOW: string
}

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type',
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url)

    // 瀏覽器跨域 preflight
    if (req.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS })
    }

    if (req.method === 'POST' && url.pathname === '/update') {
      const res = await fetch(
        `https://api.github.com/repos/${env.OWNER}/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${env.GH_TOKEN}`,
            Accept: 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'theme-rotation-update',
          },
          body: JSON.stringify({ ref: 'main' }),
        },
      )
      const body = res.ok
        ? JSON.stringify({ ok: true })
        : JSON.stringify({ ok: false, status: res.status, detail: res.statusText })
      return new Response(body, {
        status: res.ok ? 200 : res.status,
        headers: { 'Content-Type': 'application/json', ...CORS },
      })
    }
    return new Response(JSON.stringify({ error: 'POST /update' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json', ...CORS },
    })
  },
}
